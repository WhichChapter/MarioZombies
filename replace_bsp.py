
import zipfile
import shutil
from pathlib import Path
import tempfile
import os

# Paths
PK3 = Path(r"C:\Users\reube\Music\WAW\nzp_complete\nzp.gay\nzp\game.pk3")
NEW_BSP = Path(r"C:\Users\reube\Music\WAW\figure8_build\nzp_warehouse.bsp")

# Backup location
BACKUP_DIR = PK3.parent / "bsp_backups"
BACKUP_DIR.mkdir(exist_ok=True)

print("[1] Checking files...")

if not PK3.exists():
    raise FileNotFoundError(PK3)

if not NEW_BSP.exists():
    raise FileNotFoundError(NEW_BSP)

# Find existing BSP files
with zipfile.ZipFile(PK3, "r") as archive:
    bsp_files = [
        name for name in archive.namelist()
        if name.lower().endswith(".bsp")
    ]

    if not bsp_files:
        raise RuntimeError("No BSP files found in game.pk3")

    print("\nBSP files found:")
    for i, name in enumerate(bsp_files):
        print(f"{i}: {name}")

    if len(bsp_files) > 1:
        choice = int(input("\nWhich BSP should be replaced? Enter index: "))
        target_bsp = bsp_files[choice]
    else:
        target_bsp = bsp_files[0]

    print(f"\nTarget: {target_bsp}")

    # Backup original BSP
    backup_path = BACKUP_DIR / Path(target_bsp).name

    if backup_path.exists():
        backup_path = BACKUP_DIR / (
            backup_path.stem + "_backup" + backup_path.suffix
        )

    print(f"[2] Backing up to: {backup_path}")
    backup_path.write_bytes(archive.read(target_bsp))

print("[3] Creating replacement PK3...")

temp_pk3 = PK3.with_name(PK3.stem + "_temp.pk3")

with zipfile.ZipFile(PK3, "r") as source:
    with zipfile.ZipFile(temp_pk3, "w") as output:
        for item in source.infolist():
            if item.filename == target_bsp:
                print(f"Replacing: {item.filename}")

                output.writestr(
                    item,
                    NEW_BSP.read_bytes()
                )
            else:
                output.writestr(item, source.read(item.filename))

print("[4] Verifying replacement...")

with zipfile.ZipFile(temp_pk3, "r") as check:
    replaced = check.read(target_bsp)

    if replaced != NEW_BSP.read_bytes():
        temp_pk3.unlink()
        raise RuntimeError("Verification failed!")

# Replace original PK3
os.replace(temp_pk3, PK3)

print("\nSUCCESS!")
print(f"Replaced: {target_bsp}")
print(f"Backup:   {backup_path}")
print(f"PK3:      {PK3}")
print("All other archive entries preserved.")
