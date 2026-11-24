
import re
import struct
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BUILD = ROOT / "figure8_build"
PK3 = ROOT / "NZPortable-Offline" / "nzp" / "game.pk3"

GENERATED = BUILD / "nzp_warehouse.bsp"
ORIGINAL_NAME = "maps/nzp_warehouse.bsp"

LUMP_NAMES = [
    "entities", "planes", "textures", "vertices", "visibility",
    "nodes", "texinfo", "faces", "lighting", "clipnodes",
    "leaves", "marksurfaces", "edges", "surfedges", "models",
]

RECORD_SIZES = {
    "planes": 20,
    "vertices": 12,
    "nodes": 24,
    "texinfo": 40,
    "faces": 20,
    "clipnodes": 8,
    "leaves": 28,
    "marksurfaces": 2,
    "edges": 4,
    "surfedges": 4,
    "models": 64,
}


def inspect_bsp(label, data):
    print("\n" + "=" * 65)
    print(label)
    print("=" * 65)

    if len(data) < 124:
        print("ERROR: File is too small to be a BSP30.")
        return

    version = struct.unpack_from("<i", data, 0)[0]
    print(f"Version: {version}")
    print(f"File size: {len(data):,} bytes")

    if version != 30:
        print("WARNING: Expected BSP version 30.")

    lumps = {}

    for i, name in enumerate(LUMP_NAMES):
        offset, length = struct.unpack_from(
            "<ii", data, 4 + i * 8
        )

        if offset < 0 or length < 0 or offset + length > len(data):
            print(f"{name}: INVALID LUMP RANGE")
            continue

        lumps[name] = data[offset:offset + length]

        if name in RECORD_SIZES:
            size = RECORD_SIZES[name]
            count = length // size
            print(f"{name:14} {count:8,} records ({length:,} bytes)")
        else:
            print(f"{name:14} {length:8,} bytes")

    # Entity classnames
    entity_data = lumps.get("entities", b"")
    entity_text = entity_data.decode("latin-1", errors="replace")

    classnames = re.findall(
        r'"classname"\s*"([^"]+)"',
        entity_text,
        re.IGNORECASE,
    )

    print("\nEntity classnames:")
    for classname, count in Counter(classnames).most_common():
        print(f"  {classname}: {count}")

    print(f"Total entities: {len(classnames)}")

    # Embedded miptex names
    texture_data = lumps.get("textures", b"")

    if len(texture_data) >= 4:
        count = struct.unpack_from("<i", texture_data, 0)[0]
        print(f"\nEmbedded texture count: {count}")

        if 0 <= count <= 10000 and len(texture_data) >= 4 + count * 4:
            names = []

            for i in range(count):
                offset = struct.unpack_from(
                    "<i", texture_data, 4 + i * 4
                )[0]

                if offset < 0:
                    continue

                if offset + 16 > len(texture_data):
                    continue

                name = texture_data[offset:offset + 16]
                name = name.split(b"\0", 1)[0].decode(
                    "ascii", errors="replace"
                )

                if name:
                    names.append(name)

            for name in sorted(set(names)):
                print("  " + name)
    else:
        print("\nNo embedded texture lump.")


if not GENERATED.is_file():
    raise SystemExit(f"Generated BSP not found: {GENERATED}")

inspect_bsp("GENERATED FIGURE-8 BSP", GENERATED.read_bytes())

with zipfile.ZipFile(PK3) as archive:
    if ORIGINAL_NAME not in archive.namelist():
        print(f"\nOriginal map not found in archive: {ORIGINAL_NAME}")
    else:
        original_data = archive.read(ORIGINAL_NAME)
        inspect_bsp("ORIGINAL NZP WAREHOUSE BSP", original_data)

print("\n" + "=" * 65)
print("INSPECTION COMPLETE")
print("=" * 65)
