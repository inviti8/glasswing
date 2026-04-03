#!/usr/bin/env bash
# PyInstaller build + DMG installer for Andromica — macOS
# Run from the repo root: bash builds/build_mac.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Resolve version from environment or pyproject.toml
VERSION="${BUILD_VERSION:-$(python3 -c "
try:
    import tomllib
except ImportError:
    import tomli as tomllib
with open('pyproject.toml', 'rb') as f:
    print(tomllib.load(f).get('project', {}).get('version', '0.1.0'))
" 2>/dev/null || echo '0.1.0')}"

VERSION="$(echo "$VERSION" | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)"
VERSION="${VERSION:-0.1.0}"
ARCH="$(uname -m)"  # arm64 or x86_64

echo "=== Andromica macOS Build ==="
echo "Version: $VERSION"
echo "Architecture: $ARCH"

# 1. Build with PyInstaller (spec creates .app bundle on macOS)
uv run pyinstaller scripts/glasswing.spec \
  --distpath build/dist --workpath build/work --noconfirm

APP_PATH="$REPO_ROOT/build/dist/andromica.app"
if [ ! -d "$APP_PATH" ]; then
  echo "[ERROR] .app bundle not found at $APP_PATH"
  exit 1
fi
echo ".app bundle: $APP_PATH ($(du -sm "$APP_PATH" | cut -f1) MB)"

# 2. Code sign (CI only — requires CODESIGN_IDENTITY env var)
if [ -n "${CODESIGN_IDENTITY:-}" ]; then
  echo "=== Code signing ==="
  codesign --force --options runtime --timestamp \
    --sign "$CODESIGN_IDENTITY" --deep "$APP_PATH"
  codesign --verify --deep --strict --verbose=2 "$APP_PATH"
fi

# 3. Create DMG
echo "=== Creating DMG ==="
mkdir -p build/dist
DMG_NAME="andromica-${VERSION}-macos-${ARCH}.dmg"
hdiutil create -volname "Andromica" \
  -srcfolder "$APP_PATH" \
  -ov -format UDZO \
  "build/dist/$DMG_NAME"

# 4. Sign DMG (CI only)
if [ -n "${CODESIGN_IDENTITY:-}" ]; then
  codesign --force --timestamp --sign "$CODESIGN_IDENTITY" "build/dist/$DMG_NAME"
fi

echo "=== DMG created ==="
ls -lh "build/dist/$DMG_NAME"
