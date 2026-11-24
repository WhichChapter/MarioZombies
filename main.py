
from __future__ import annotations

import json
import math
import struct
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parent

OBJ_FILE = ROOT / "cross_course" / "cross_course.obj"
PK3_FILE = ROOT / "NZPortable-Offline" / "nzp" / "game.pk3"

BUILD = ROOT / "figure8_build"
TOOLS = ROOT / "figure8_tools"

MAP_FILE = BUILD / "nzp_warehouse.map"
BSP_FILE = BUILD / "nzp_warehouse.bsp"
WAD_FILE = BUILD / "figure8_textures.wad"

REPOSITORY = "speedrun-16/hltools"
RELEASE_API = (
    f"https://api.github.com/repos/{REPOSITORY}/releases/tags/nightly"
)

SCALE = 3.0
BRUSH_DEPTH = 24.0

MIN_UPWARD_NORMAL = 0.25
DEDUPLICATION_PRECISION = 2

ROOM_MARGIN = 180.0
ROOM_FLOOR = -160.0
ROOM_CEILING = 650.0
WALL_THICKNESS = 64.0

# Used for the room's walls and floor.
ROOM_TEXTURE = "LAMBERT202"

# ============================================================
# GENERAL UTILITIES
# ============================================================

def log(message):
    print(f"[+] {message}", flush=True)


def fail(message):
    print(f"\n[ERROR] {message}", flush=True)
    sys.exit(1)


def download(url, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Figure8-NZP-Map-Builder",
            "Accept": "application/octet-stream",
        },
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        total = int(response.headers.get("Content-Length", 0))
        received = 0

        with destination.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)

                if not chunk:
                    break

                output.write(chunk)
                received += len(chunk)

                if total:
                    print(
                        f"\r    Downloaded {received / 1048576:.1f} / "
                        f"{total / 1048576:.1f} MB",
                        end="",
                        flush=True,
                    )

    print()


# ============================================================
# FIND INPUTS
# ============================================================

if not OBJ_FILE.is_file():
    alternatives = [
        ROOT / "cross_course.obj",
        ROOT / "cross_course_clean" / "cross_course" / "cross_course.obj",
    ]

    for candidate in alternatives:
        if candidate.is_file():
            OBJ_FILE = candidate
            break

if not OBJ_FILE.is_file():
    fail(f"Could not find OBJ: {OBJ_FILE}")

BUILD.mkdir(parents=True, exist_ok=True)
TOOLS.mkdir(parents=True, exist_ok=True)

print("=" * 68)
print(" FIGURE-8 CIRCUIT -> NZ: PORTABLE MAP BUILDER")
print("=" * 68)

log(f"OBJ: {OBJ_FILE}")
log(f"WAD: {WAD_FILE}")
if PK3_FILE.is_file():
    log(f"NZP archive available (not modified): {PK3_FILE}")
else:
    log("NZP archive not present; standalone BSP compilation does not require it.")


# ============================================================
# FIND COMPILER
# ============================================================

def find_hltools():
    executable = "hltools.exe" if sys.platform == "win32" else "hltools"
    existing = [
        path for path in TOOLS.rglob(executable)
        if path.is_file()
    ]

    if existing:
        compiler = existing[0]

        if sys.platform != "win32":
            compiler.chmod(compiler.stat().st_mode | 0o111)

        return compiler

    # Codespaces and other Linux environments must use a native build.
    # The devcontainer setup script builds and installs it here.
    if sys.platform != "win32":
        fail(
            "Native Linux hltools compiler not found.\n"
            "Run: bash .devcontainer/setup.sh"
        )

    log("Checking hltools nightly release...")

    try:
        request = urllib.request.Request(
            RELEASE_API,
            headers={
                "User-Agent": "Figure8-NZP-Map-Builder",
                "Accept": "application/vnd.github+json",
            },
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            release = json.loads(response.read().decode("utf-8"))

    except Exception as error:
        fail(f"Could not retrieve compiler release: {error}")

    assets = release.get("assets", [])

    candidates = [
        asset for asset in assets
        if asset.get("name", "").lower().endswith(".zip")
        and any(
            word in asset.get("name", "").lower()
            for word in ("windows", "win", "x64")
        )
    ]

    if not candidates:
        candidates = [
            asset for asset in assets
            if asset.get("name", "").lower().endswith(".zip")
        ]

    if not candidates:
        fail("No compiler ZIP found in the nightly release.")

    asset = candidates[0]
    archive = TOOLS / asset["name"]

    log(f"Downloading {asset['name']}...")
    download(asset["browser_download_url"], archive)

    log("Extracting compiler...")

    try:
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                target = (TOOLS / item.filename).resolve()

                if not target.is_relative_to(TOOLS.resolve()):
                    fail("Compiler archive contains an unsafe path.")

            z.extractall(TOOLS)

    except Exception as error:
        fail(f"Could not extract compiler: {error}")

    matches = list(TOOLS.rglob("hltools.exe"))

    if not matches:
        fail("hltools.exe was not found in the downloaded archive.")

    return matches[0]

COMPILER = find_hltools()
log(f"Compiler: {COMPILER}")

if not WAD_FILE.is_file():
    texture_script = ROOT / "build_textures.py"

    if not texture_script.is_file():
        fail(f"Texture builder not found: {texture_script}")

    log("Texture WAD is missing; generating it now...")
    try:
        subprocess.run(
            [sys.executable, str(texture_script)],
            cwd=ROOT,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        fail(f"Texture generation failed with exit code {error.returncode}.")

if not WAD_FILE.is_file():
    fail(f"Texture WAD was not created: {WAD_FILE}")


# ============================================================
# PARSE OBJ, INCLUDING MATERIAL ASSIGNMENTS
# ============================================================

log("Reading OBJ geometry and materials...")

vertices = []
faces = []

current_material = ROOM_TEXTURE
material_names = set()

with OBJ_FILE.open(
    "r",
    encoding="utf-8",
    errors="ignore",
) as source:

    for line in source:
        line = line.strip()

        if not line or line.startswith("#"):
            continue

        parts = line.split()
        command = parts[0]

        if command == "v" and len(parts) >= 4:
            try:
                point = tuple(float(x) for x in parts[1:4])

                if all(math.isfinite(x) for x in point):
                    vertices.append(point)

            except ValueError:
                continue

        elif command == "usemtl" and len(parts) >= 2:
            current_material = parts[1].upper()
            material_names.add(current_material)

        elif command == "f" and len(parts) >= 4:
            indices = []

            for item in parts[1:]:
                try:
                    index = int(item.split("/")[0])

                    if index < 0:
                        index = len(vertices) + index
                    else:
                        index -= 1

                    if 0 <= index < len(vertices):
                        indices.append(index)

                except ValueError:
                    continue

            # Triangulate polygons while retaining their material.
            if len(indices) >= 3:
                for i in range(1, len(indices) - 1):
                    faces.append((
                        (
                            indices[0],
                            indices[i],
                            indices[i + 1],
                        ),
                        current_material,
                    ))

if not vertices or not faces:
    fail("No usable OBJ geometry was found.")

log(f"Vertices: {len(vertices):,}")
log(f"Triangles: {len(faces):,}")
log(f"Materials referenced: {len(material_names)}")


# ============================================================
# VERIFY MATERIALS AGAINST WAD
# ============================================================

# The WAD was already built from the matching PNG filenames.
# Verify that the expected BMP inputs exist as well.

TEXTURE_DIR = BUILD / "indexed_textures"

available_textures = {
    path.stem.upper()
    for path in TEXTURE_DIR.glob("*.bmp")
}

missing_materials = sorted(
    material
    for material in material_names
    if material not in available_textures
)

if missing_materials:
    fail(
        "Some OBJ materials have no corresponding WAD input texture:\n"
        + "\n".join(missing_materials)
    )

log("All OBJ materials have matching texture files.")


# ============================================================
# COORDINATE CONVERSION
# ============================================================

mins = [
    min(point[i] for point in vertices)
    for i in range(3)
]

maxs = [
    max(point[i] for point in vertices)
    for i in range(3)
]

print("\nOBJ dimensions:")

for axis, low, high in zip("XYZ", mins, maxs):
    print(f"  {axis}: {low:.2f} to {high:.2f}")

converted = []

for x, y, z in vertices:
    converted.append((
        (x - (mins[0] + maxs[0]) / 2) * SCALE,
        (z - (mins[2] + maxs[2]) / 2) * SCALE,
        (y - mins[1]) * SCALE + 32.0,
    ))

log("Converted OBJ coordinates.")


# ============================================================
# VECTOR OPERATIONS
# ============================================================

def sub(a, b):
    return tuple(a[i] - b[i] for i in range(3))


def dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def magnitude(v):
    return math.sqrt(dot(v, v))


def normal(a, b, c):
    n = cross(sub(b, a), sub(c, a))
    size = magnitude(n)

    if size < 0.00001:
        return None

    return tuple(x / size for x in n)


# ============================================================
# GOLDsrc BRUSH GENERATION
# ============================================================

def plane_line(points, centre, texture):
    if len(points) < 3:
        return None

    points = list(points)

    a, b, c = points[:3]
    n = normal(a, b, c)

    if n is None:
        return None

    # Orient the plane consistently towards the brush interior.
    if dot(n, sub(centre, a)) < 0:
        points.reverse()

    a, b, c = points[:3]

    return (
        f"( {a[0]:.4f} {a[1]:.4f} {a[2]:.4f} ) "
        f"( {b[0]:.4f} {b[1]:.4f} {b[2]:.4f} ) "
        f"( {c[0]:.4f} {c[1]:.4f} {c[2]:.4f} ) "
        f"{texture} 0 0 0 1 1"
    )


def brush_from_polygons(polygons, texture):
    all_points = [
        point
        for polygon in polygons
        for point in polygon
    ]

    centre = tuple(
        sum(p[i] for p in all_points) / len(all_points)
        for i in range(3)
    )

    lines = []

    for polygon in polygons:
        line = plane_line(polygon, centre, texture)

        if line is None:
            return None

        lines.append(line)

    return "{\n" + "\n".join(lines) + "\n}"


def triangle_prism(a, b, c, depth, texture):
    ba = (a[0], a[1], a[2] - depth)
    bb = (b[0], b[1], b[2] - depth)
    bc = (c[0], c[1], c[2] - depth)

    polygons = [
        [a, b, c],
        [ba, bc, bb],
        [a, b, bb, ba],
        [b, c, bc, bb],
        [c, a, ba, bc],
    ]

    return brush_from_polygons(polygons, texture)


def box_brush(x1, y1, z1, x2, y2, z2, texture):
    p000 = (x1, y1, z1)
    p100 = (x2, y1, z1)
    p110 = (x2, y2, z1)
    p010 = (x1, y2, z1)

    p001 = (x1, y1, z2)
    p101 = (x2, y1, z2)
    p111 = (x2, y2, z2)
    p011 = (x1, y2, z2)

    polygons = [
        [p000, p010, p110, p100],
        [p001, p101, p111, p011],
        [p000, p100, p101, p001],
        [p100, p110, p111, p101],
        [p110, p010, p011, p111],
        [p010, p000, p001, p011],
    ]

    return brush_from_polygons(polygons, texture)


# ============================================================
# SELECT UPWARD-FACING TRACK SURFACES
# ============================================================

log("Finding upward-facing track surfaces...")

selected = {}

for triangle, material in faces:
    a, b, c = (converted[i] for i in triangle)

    n = normal(a, b, c)

    if n is None:
        continue

    # Reject downward-facing and near-vertical faces.
    if n[2] < MIN_UPWARD_NORMAL:
        continue

    projected = tuple(sorted(
        (
            round(p[0], DEDUPLICATION_PRECISION),
            round(p[1], DEDUPLICATION_PRECISION),
        )
        for p in (a, b, c)
    ))

    average_height = (a[2] + b[2] + c[2]) / 3.0

    previous = selected.get(projected)

    if previous is None or average_height > previous[0]:
        selected[projected] = (
            average_height,
            (a, b, c),
            material,
        )

surface_triangles = [
    (item[1], item[2])
    for item in selected.values()
]

if not surface_triangles:
    fail("No upward-facing track surfaces were detected.")

log(f"Selected surfaces: {len(surface_triangles):,}")

material_counts = {}

for triangle, material in surface_triangles:
    material_counts[material] = material_counts.get(material, 0) + 1

print("\nSelected material distribution:")

for material, count in sorted(material_counts.items()):
    print(f"  {material}: {count}")


# ============================================================
# BUILD TRACK BRUSHES
# ============================================================

log("Building textured track brushes...")

track_brushes = []

for index, (triangle, material) in enumerate(
    surface_triangles,
    1,
):
    brush = triangle_prism(
        *triangle,
        BRUSH_DEPTH,
        material,
    )

    if brush:
        track_brushes.append(brush)

    if index % 50 == 0:
        print(
            f"\r    Processed {index}/"
            f"{len(surface_triangles)} surfaces",
            end="",
            flush=True,
        )

print()

if not track_brushes:
    fail("No valid track brushes were generated.")

all_points = [
    point
    for triangle, _ in surface_triangles
    for point in triangle
]

min_x = min(p[0] for p in all_points)
max_x = max(p[0] for p in all_points)
min_y = min(p[1] for p in all_points)
max_y = max(p[1] for p in all_points)
max_z = max(p[2] for p in all_points)

left = min_x - ROOM_MARGIN
right = max_x + ROOM_MARGIN
back = min_y - ROOM_MARGIN
front = max_y + ROOM_MARGIN

room_brushes = [
    box_brush(
        left, back, ROOM_FLOOR - WALL_THICKNESS,
        right, front, ROOM_FLOOR,
        ROOM_TEXTURE,
    ),
    box_brush(
        left, back, ROOM_CEILING,
        right, front, ROOM_CEILING + WALL_THICKNESS,
        ROOM_TEXTURE,
    ),
    box_brush(
        left - WALL_THICKNESS, back, ROOM_FLOOR,
        left, front, ROOM_CEILING,
        ROOM_TEXTURE,
    ),
    box_brush(
        right, back, ROOM_FLOOR,
        right + WALL_THICKNESS, front, ROOM_CEILING,
        ROOM_TEXTURE,
    ),
    box_brush(
        left, back - WALL_THICKNESS, ROOM_FLOOR,
        right, back, ROOM_CEILING,
        ROOM_TEXTURE,
    ),
    box_brush(
        left, front, ROOM_FLOOR,
        right, front + WALL_THICKNESS, ROOM_CEILING,
        ROOM_TEXTURE,
    ),
]

room_brushes = [b for b in room_brushes if b]

if len(room_brushes) != 6:
    fail("Could not create all six room brushes.")

log(f"Track brushes: {len(track_brushes):,}")
log(f"Room brushes: {len(room_brushes)}")


# ============================================================
# SPAWN AND LIGHTING
# ============================================================

spawn_triangle, _ = max(
    surface_triangles,
    key=lambda item: sum(p[2] for p in item[0]) / 3,
)

spawn_x = sum(p[0] for p in spawn_triangle) / 3
spawn_y = sum(p[1] for p in spawn_triangle) / 3
spawn_z = sum(p[2] for p in spawn_triangle) / 3 + 48

light_z = min(ROOM_CEILING - 80, max_z + 250)

entities = f'''
{{
"classname" "info_player_start"
"origin" "{spawn_x:.2f} {spawn_y:.2f} {spawn_z:.2f}"
"angle" "0"
}}
{{
"classname" "light"
"origin" "0 0 {light_z:.2f}"
"light" "255"
}}
'''


# ============================================================
# WRITE MAP
# ============================================================

log("Writing MAP file...")

wad_path = WAD_FILE.resolve().as_posix()

with MAP_FILE.open(
    "w",
    encoding="ascii",
    newline="\n",
) as output:

    output.write("{\n")
    output.write('"classname" "worldspawn"\n')
    output.write('"message" "Figure 8 Circuit"\n')
    output.write(f'"wad" "{wad_path}"\n')

    for brush in room_brushes:
        output.write(brush + "\n")

    for brush in track_brushes:
        output.write(brush + "\n")

    output.write("}\n")
    output.write(entities)

log(f"MAP: {MAP_FILE}")
log(f"MAP size: {MAP_FILE.stat().st_size / 1048576:.2f} MB")


# ============================================================
# COMPILE AND SAVE LOG
# ============================================================

log("Starting GoldSrc compilation...")
log("Stages: CSG -> BSP -> VIS -> RAD")

print("\nCompilation may take several minutes.\n", flush=True)

compile_log = BUILD / "compile_output.log"

try:
    with compile_log.open(
        "w",
        encoding="utf-8",
        errors="replace",
    ) as log_file:

        result = subprocess.run(
            [
                str(COMPILER),
                "compile",
                "-fast",
                MAP_FILE.name,
            ],
            cwd=BUILD,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            timeout=3600,
            check=False,
        )

except subprocess.TimeoutExpired:
    fail("Compiler exceeded the one-hour timeout.")

except KeyboardInterrupt:
    fail("Compilation was interrupted.")

except Exception as error:
    fail(f"Could not run compiler: {error}")

if result.returncode != 0:
    print("\nLast compiler output:\n")

    try:
        lines = compile_log.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()

        print("\n".join(lines[-70:]))

    except Exception:
        pass

    fail(
        f"Compiler returned exit code {result.returncode}.\n"
        f"Full log: {compile_log}"
    )


# ============================================================
# VALIDATE BSP
# ============================================================

if not BSP_FILE.is_file():
    fail(
        "Compiler returned success but no expected BSP was found.\n"
        f"Check: {BUILD}"
    )

if BSP_FILE.stat().st_size < 1024:
    fail("Generated BSP is unexpectedly small.")

with BSP_FILE.open("rb") as file:
    version = struct.unpack("<i", file.read(4))[0]

if version != 30:
    fail(
        f"Unexpected BSP version {version}; expected BSP30."
    )

log(f"Valid BSP30 created: {BSP_FILE}")
log(f"BSP size: {BSP_FILE.stat().st_size / 1048576:.2f} MB")


# ============================================================
# FINISH
# ============================================================

print("\n" + "=" * 68)
print(" BUILD COMPLETE")
print("=" * 68)

print(f"Input OBJ:       {OBJ_FILE}")
print(f"Texture WAD:     {WAD_FILE}")
print(f"Output MAP:      {MAP_FILE}")
print(f"Output BSP:      {BSP_FILE}")
print(f"Track surfaces:  {len(surface_triangles):,}")
print(f"Track brushes:   {len(track_brushes):,}")
print(f"Room brushes:    {len(room_brushes)}")
print(f"BSP version:     {version}")

print("\nOriginal game.pk3 has NOT been modified.")
print("Compiler log:", compile_log)

print("\nThis remains a geometry prototype.")
print("NZP gameplay entities and navigation are not yet integrated.")

print("=" * 68)
