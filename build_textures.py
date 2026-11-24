
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "cross_course"
TOOLS = ROOT / "figure8_tools"
BUILD = ROOT / "figure8_build"
BMP_DIR = BUILD / "indexed_textures"
WAD_FILE = BUILD / "figure8_textures.wad"
COMPILER = TOOLS / ("hltools.exe" if sys.platform == "win32" else "hltools")


def require_pillow():
    try:
        from PIL import Image
        return Image
    except ImportError:
        print("Installing Pillow...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "Pillow"]
        )
        from PIL import Image
        return Image


def nearest_multiple_of_16(value):
    return max(16, min(512, round(value / 16) * 16))


def main():
    Image = require_pillow()

    if not COMPILER.is_file():
        raise FileNotFoundError(
            f"Compiler not found: {COMPILER}. "
            "In Codespaces run: bash .devcontainer/setup.sh"
        )

    if sys.platform != "win32":
        COMPILER.chmod(COMPILER.stat().st_mode | 0o111)

    pngs = sorted(SOURCE.glob("*.png"))
    if not pngs:
        raise FileNotFoundError(f"No PNG textures found in {SOURCE}")

    BMP_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Converting {len(pngs)} textures...")
    for png in pngs:
        name = png.stem.upper()

        if len(name) > 15:
            raise ValueError(f"Texture name too long for WAD3: {name}")

        with Image.open(png) as original:
            image = original.convert("RGBA")

            # GoldSrc WAD textures use dimensions divisible by 16.
            width = nearest_multiple_of_16(image.width)
            height = nearest_multiple_of_16(image.height)

            if image.size != (width, height):
                image = image.resize(
                    (width, height),
                    Image.Resampling.LANCZOS
                )

            # Initial pass: flatten transparency and create an indexed image.
            background = Image.new("RGBA", image.size, (0, 0, 0, 255))
            background.alpha_composite(image)
            rgb = background.convert("RGB")

            indexed = rgb.quantize(
                colors=256,
                method=Image.Quantize.MEDIANCUT
            )

            output = BMP_DIR / f"{name}.bmp"
            indexed.save(output, format="BMP")

            print(
                f"  {png.name} -> {output.name} "
                f"({width}x{height})"
            )

    # Remove an older test archive so the build cannot silently reuse it.
    if WAD_FILE.exists():
        WAD_FILE.unlink()

    print("\nBuilding WAD3 archive...")
    subprocess.run(
        [
            str(COMPILER),
            "wad",
            "build",
            str(BMP_DIR),
            str(WAD_FILE),
        ],
        check=True,
    )

    if not WAD_FILE.exists() or WAD_FILE.stat().st_size < 12:
        raise RuntimeError("WAD build did not produce a valid-sized file.")

    print("\nWAD created successfully:")
    print(WAD_FILE)
    print(f"Size: {WAD_FILE.stat().st_size:,} bytes")

    print("\nVerifying WAD contents...")
    subprocess.run(
        [str(COMPILER), "wad", "list", str(WAD_FILE)],
        check=True,
    )


if __name__ == "__main__":
    main()
