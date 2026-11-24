
import re
import struct
import zipfile
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent
PK3 = ROOT / "NZPortable-Offline" / "nzp" / "game.pk3"
OUTPUT = ROOT / "figure8_build" / "warehouse_entity_dump.txt"

MAP_NAME = "maps/nzp_warehouse.bsp"


def extract_entities(data):
    if struct.unpack_from("<i", data, 0)[0] != 30:
        raise ValueError("Not a BSP30 file")

    offset, length = struct.unpack_from("<ii", data, 4)
    raw = data[offset:offset + length].decode(
        "latin-1", errors="replace"
    )

    entities = []

    for block in re.findall(r"\{(.*?)\}", raw, re.S):
        pairs = re.findall(
            r'"([^"]*)"\s*"([^"]*)"',
            block
        )

        entity = dict(pairs)

        if entity:
            entities.append(entity)

    return entities


with zipfile.ZipFile(PK3) as archive:
    data = archive.read(MAP_NAME)

entities = extract_entities(data)

counts = Counter(
    entity.get("classname", "unknown")
    for entity in entities
)

lines = []

lines.append("NZP WAREHOUSE ENTITY ANALYSIS")
lines.append("=" * 70)
lines.append(f"Total entities: {len(entities)}")
lines.append("")

lines.append("ENTITY COUNTS")
lines.append("-" * 70)

for classname, count in counts.most_common():
    lines.append(f"{classname:30} {count}")

lines.append("")
lines.append("FULL ENTITY PROPERTIES")
lines.append("=" * 70)

for number, entity in enumerate(entities, 1):
    classname = entity.get("classname", "unknown")

    lines.append("")
    lines.append(f"ENTITY {number}: {classname}")
    lines.append("-" * 50)

    for key, value in entity.items():
        lines.append(f"  {key}: {value}")

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text("\n".join(lines), encoding="utf-8")

print(f"Extracted {len(entities)} entities.")
print(f"Entity types: {len(counts)}")
print(f"Saved to: {OUTPUT}")

print("\nImportant entity groups:")

interesting = [
    "info_player_1_spawn",
    "info_player_2_spawn",
    "info_player_3_spawn",
    "info_player_4_spawn",
    "spawn_zombie",
    "path_corner",
    "item_barricade",
    "func_door_nzp",
    "power_switch",
    "mystery_box",
]

for name in interesting:
    matching = [
        e for e in entities
        if e.get("classname") == name
    ]

    print(f"  {name}: {len(matching)}")
