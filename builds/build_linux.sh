#!/usr/bin/env bash
# PyInstaller build + .deb installer for Andromica — Linux
# Run from the repo root: bash builds/build_linux.sh
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

echo "=== Andromica Linux Build ==="
echo "Version: $VERSION"

# 1. Build with PyInstaller (onedir mode via spec)
uv run pyinstaller scripts/glasswing.spec \
  --distpath build/dist --workpath build/work --noconfirm

DIST_DIR="$REPO_ROOT/build/dist/andromica"
if [ ! -d "$DIST_DIR" ]; then
  echo "[ERROR] Build output not found at $DIST_DIR"
  exit 1
fi
echo "Build output: $DIST_DIR ($(du -sm "$DIST_DIR" | cut -f1) MB)"

# 2. Assemble .deb structure
PKG_DIR="$REPO_ROOT/build/andromica_${VERSION}_amd64"
rm -rf "$PKG_DIR"

mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/opt/andromica"
mkdir -p "$PKG_DIR/usr/bin"
mkdir -p "$PKG_DIR/usr/share/applications"
mkdir -p "$PKG_DIR/usr/share/icons/hicolor/512x512/apps"

# Control file
sed "s/VERSION_PLACEHOLDER/$VERSION/" \
  "$SCRIPT_DIR/linux/control" > "$PKG_DIR/DEBIAN/control"

# Copy built files
cp -r "$DIST_DIR"/. "$PKG_DIR/opt/andromica/"
chmod +x "$PKG_DIR/opt/andromica/andromica"

# Symlink, desktop entry, icon
ln -sf /opt/andromica/andromica "$PKG_DIR/usr/bin/andromica"
cp "$SCRIPT_DIR/linux/andromica.desktop" "$PKG_DIR/usr/share/applications/"
cp "$REPO_ROOT/static/icon.png" "$PKG_DIR/usr/share/icons/hicolor/512x512/apps/andromica.png"

# Permissions
find "$PKG_DIR/opt/andromica" -name "*.so" -exec chmod 644 {} \; 2>/dev/null || true
chmod 755 "$PKG_DIR/DEBIAN"

# 3. Build .deb
echo "=== Creating .deb package ==="
dpkg-deb --build "$PKG_DIR"

mkdir -p build/dist
mv "${PKG_DIR}.deb" "build/dist/andromica-${VERSION}-linux-amd64.deb"

echo "=== .deb created ==="
ls -lh "build/dist/"*.deb
