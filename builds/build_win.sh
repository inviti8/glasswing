#!/usr/bin/env bash
# PyInstaller build + WiX MSI installer for Andromica — Windows
# Run from the repo root: bash builds/build_win.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Resolve version from environment or pyproject.toml
VERSION="${BUILD_VERSION:-$(python -c "
try:
    import tomllib
except ImportError:
    import tomli as tomllib
with open('pyproject.toml', 'rb') as f:
    print(tomllib.load(f).get('project', {}).get('version', '0.1.0'))
" 2>/dev/null || echo '0.1.0')}"

# Extract numeric version (e.g. "v1.0.0" -> "1.0.0")
VERSION="$(echo "$VERSION" | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)"
VERSION="${VERSION:-0.1.0}"

echo "=== Andromica Windows Build ==="
echo "Version: $VERSION"

# 1. Build with PyInstaller (onedir mode via spec)
uv run pyinstaller scripts/glasswing.spec \
  --distpath build/dist --workpath build/work --noconfirm

DIST_DIR="$REPO_ROOT/build/dist/andromica"
if [ ! -d "$DIST_DIR" ]; then
  echo "[ERROR] Build output not found at $DIST_DIR"
  exit 1
fi

EXE="$DIST_DIR/andromica.exe"
if [ -f "$EXE" ]; then
  SIZE=$(stat --printf="%s" "$EXE" 2>/dev/null || stat -f "%z" "$EXE" 2>/dev/null || echo 0)
  SIZE_MB=$((SIZE / 1024 / 1024))
  echo "Executable: $EXE ($SIZE_MB MB)"
else
  echo "[ERROR] andromica.exe not found in $DIST_DIR"
  exit 1
fi

# 2. Create MSI with WiX Toolset
echo "=== Creating MSI installer ==="
DIST_PATH="$(cd "$DIST_DIR" && pwd -W 2>/dev/null || pwd)"
ICON_PATH="$(cd "$REPO_ROOT" && pwd -W 2>/dev/null || pwd)/icon.ico"

wix build \
  -d SourceDir="$DIST_PATH" \
  -d Version="$VERSION" \
  -d IconPath="$ICON_PATH" \
  -o "$REPO_ROOT/build/dist/andromica-${VERSION}-win64.msi" \
  "$SCRIPT_DIR/andromica.wxs"

echo "=== MSI created ==="
ls -lh "$REPO_ROOT/build/dist/"*.msi
