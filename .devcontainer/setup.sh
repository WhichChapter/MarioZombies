#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$ROOT/figure8_tools"
SOURCE="$TOOLS/hltools-src"
BUILD="$SOURCE/build"
SOURCE_BINARY="$SOURCE/bin/hltools"
INSTALL_BINARY="$TOOLS/hltools"

echo "=============================================="
echo " MarioZombies - Codespaces compiler setup"
echo "=============================================="

sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    ca-certificates

python -m pip install --user --upgrade Pillow

mkdir -p "$TOOLS"

if [ ! -d "$SOURCE/.git" ]; then
    rm -rf "$SOURCE"
    git clone --depth 1 https://github.com/speedrun-16/hltools.git "$SOURCE"
else
    git -C "$SOURCE" fetch --depth 1 origin
    git -C "$SOURCE" reset --hard FETCH_HEAD
fi

echo "[+] Configuring native Linux compiler..."
cmake -S "$SOURCE" -B "$BUILD" \
    -DCMAKE_BUILD_TYPE=Release \
    -DHLTOOLS_GPU=OFF \
    -DBUILD_TESTING=OFF

echo "[+] Building hltools..."
cmake --build "$BUILD" --target hltools --parallel 2

if [ ! -x "$SOURCE_BINARY" ]; then
    echo "[ERROR] Expected compiler was not produced at:"
    echo "        $SOURCE_BINARY"
    exit 1
fi

install -m 755 "$SOURCE_BINARY" "$INSTALL_BINARY"

echo "[+] Verifying compiler..."
"$INSTALL_BINARY" -h

echo
echo "[SUCCESS] Native Linux compiler installed:"
echo "          $INSTALL_BINARY"
echo
echo "Build the Figure-8 BSP with:"
echo "          python main.py"
