
from pathlib import Path
import shutil

source = Path("nzp_complete/nzp.gay")
output = Path("NZPortable-Offline")

output.mkdir(exist_ok=True)

# Main HTML
html = source / "index"
if not html.exists():
    html = source / "index.html"

if html.exists():
    shutil.copy2(html, output / "index.html")
else:
    print("[MISSING] index.html")

# Engine and configuration
for name in [
    "ftewebgl.js",
    "ftewebgl.wasm",
    "default.fmf",
    "nzportable.ico"
]:
    file = source / name
    if file.exists():
        shutil.copy2(file, output / name)
        print("[COPIED]", name)
    else:
        print("[MISSING]", name)

# Game archives
game_dir = output / "nzp"
game_dir.mkdir(exist_ok=True)

for name in ["game.pk3", "progs.pk3"]:
    file = source / "nzp" / name

    if file.exists():
        shutil.copy2(file, game_dir / name)
        print("[COPIED]", name)
    else:
        print("[MISSING]", name)

print("\nOffline directory:", output.resolve())
