# Andromica Cross-Platform Installer Plan

## Goal

Replace the current raw-binary release workflow with proper platform-native installers,
matching the pattern used by metavinci. Andromica should install and launch independently
without relying on metavinci to launch it.

---

## Current State

- PyInstaller builds via `scripts/glasswing.spec` produce raw executables
- GitHub Actions (`build-simple.yml`) uploads `andromica.exe`, `andromica` (Linux), `andromica.app` (macOS zip)
- No installers, no desktop shortcuts, no auto-update, no code signing
- metavinci downloads the raw exe to `~/AppData/Local/heavymeta-andromica/` and launches it via subprocess (causes WebView2 handle-inheritance issues)

---

## Target State

| Platform | Format | Install Location | Launcher |
|----------|--------|------------------|----------|
| Windows | `.msi` (WiX) | `%LOCALAPPDATA%\Programs\Andromica\` | Start Menu + Desktop shortcut |
| macOS | `.dmg` (signed + notarized) | `/Applications/Andromica.app` | Launchpad / Applications |
| Linux | `.deb` | `/opt/andromica/` + `/usr/bin/andromica` symlink | `.desktop` file |

---

## Phase 1: Windows MSI Installer (WiX Toolset)

### Files to create

- `builds/andromica.wxs` -- WiX XML installer definition
- `builds/build_win.sh` -- Build script (PyInstaller + WiX)

### WiX installer spec (`andromica.wxs`)

```xml
<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">
  <Package Name="Andromica"
           Manufacturer="Heavymeta"
           Version="$(var.Version)"
           UpgradeCode="GENERATE-NEW-GUID-HERE">

    <MajorUpgrade DowngradeErrorMessage="A newer version is already installed." />
    <MediaTemplate EmbedCab="yes" />

    <!-- Install to %LOCALAPPDATA%\Programs\Andromica -->
    <StandardDirectory Id="LocalAppDataFolder">
      <Directory Id="ProgramsDir" Name="Programs">
        <Directory Id="INSTALLDIR" Name="Andromica">
          <!-- Harvest all files from PyInstaller dist -->
          <Files Include="$(var.SourceDir)\**" />
        </Directory>
      </Directory>
    </StandardDirectory>

    <!-- Desktop shortcut -->
    <StandardDirectory Id="DesktopFolder">
      <Component Id="DesktopShortcut">
        <Shortcut Id="DesktopLink"
                  Name="Andromica"
                  Target="[INSTALLDIR]andromica.exe"
                  WorkingDirectory="INSTALLDIR"
                  Icon="andromica.ico" />
        <RegistryValue Root="HKCU" Key="Software\Heavymeta\Andromica"
                       Name="DesktopShortcut" Type="integer" Value="1" KeyPath="yes" />
      </Component>
    </StandardDirectory>

    <!-- Start Menu shortcut -->
    <StandardDirectory Id="ProgramMenuFolder">
      <Directory Id="ProgramMenuDir" Name="Andromica">
        <Component Id="StartMenuShortcut">
          <Shortcut Id="StartMenuLink"
                    Name="Andromica"
                    Target="[INSTALLDIR]andromica.exe"
                    WorkingDirectory="INSTALLDIR"
                    Icon="andromica.ico" />
          <RegistryValue Root="HKCU" Key="Software\Heavymeta\Andromica"
                         Name="StartMenuShortcut" Type="integer" Value="1" KeyPath="yes" />
          <RemoveFolder Id="CleanProgramMenu" On="uninstall" />
        </Component>
      </Directory>
    </StandardDirectory>

    <Icon Id="andromica.ico" SourceFile="$(var.IconPath)" />

    <Feature Id="MainFeature" Title="Andromica" Level="1">
      <ComponentGroupRef Id="INSTALLDIR" />
      <ComponentRef Id="DesktopShortcut" />
      <ComponentRef Id="StartMenuShortcut" />
    </Feature>
  </Package>
</Wix>
```

### Windows build script (`builds/build_win.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail

VERSION="${BUILD_VERSION:-1.0.0}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

# 1. Build with PyInstaller (--onedir for MSI packaging)
cd "$ROOT"
uv run pyinstaller scripts/glasswing.spec \
  --distpath build/dist --workpath build/work --noconfirm

# 2. Package into MSI with WiX
wix build \
  -d SourceDir="$ROOT/build/dist/andromica" \
  -d Version="$VERSION" \
  -d IconPath="$ROOT/icon.ico" \
  -o "$ROOT/build/dist/andromica-${VERSION}-windows.msi" \
  "$SCRIPT_DIR/andromica.wxs"

# 3. Optional: Sign with signtool (CI only)
if [ -f "$CERT_PATH" ]; then
  signtool sign /f "$CERT_PATH" /p "$CERT_PASSWORD" \
    /fd sha256 /td sha256 \
    /tr http://timestamp.digicert.com \
    "$ROOT/build/dist/andromica-${VERSION}-windows.msi"
fi
```

### Spec file change required

The current spec builds Windows/Linux as `--onefile` (single exe). For MSI packaging,
Windows needs `--onedir` mode so WiX can harvest the directory tree. Update
`scripts/glasswing.spec` to use `COLLECT` on Windows (like macOS already does).

---

## Phase 2: macOS DMG Installer

### Files to create

- `builds/build_mac.sh` -- Build script (PyInstaller + DMG + signing)

### macOS build script (`builds/build_mac.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail

VERSION="${BUILD_VERSION:-1.0.0}"
ARCH="$(uname -m)"  # arm64 or x86_64
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

# 1. Build with PyInstaller (spec already creates .app bundle on macOS)
cd "$ROOT"
uv run pyinstaller scripts/glasswing.spec \
  --distpath build/dist --workpath build/work --noconfirm

APP_PATH="$ROOT/build/dist/andromica.app"

# 2. Code sign (CI only)
if [ -n "${CODESIGN_IDENTITY:-}" ]; then
  codesign --force --options runtime --timestamp \
    --sign "$CODESIGN_IDENTITY" --deep "$APP_PATH"
fi

# 3. Create DMG
DMG_NAME="andromica-${VERSION}-macos-${ARCH}.dmg"
hdiutil create -volname "Andromica" \
  -srcfolder "$APP_PATH" \
  -ov -format UDZO \
  "$ROOT/build/dist/$DMG_NAME"

# 4. Sign & notarize DMG (CI only)
if [ -n "${CODESIGN_IDENTITY:-}" ]; then
  codesign --force --sign "$CODESIGN_IDENTITY" "$ROOT/build/dist/$DMG_NAME"

  xcrun notarytool submit "$ROOT/build/dist/$DMG_NAME" \
    --apple-id "$APPLE_ID" \
    --password "$APPLE_APP_PASSWORD" \
    --team-id "$APPLE_TEAM_ID" \
    --wait

  xcrun stapler staple "$ROOT/build/dist/$DMG_NAME"
fi
```

---

## Phase 3: Linux .deb Package

### Files to create

- `builds/build_linux.sh` -- Build script (PyInstaller + dpkg-deb)
- `builds/linux/control` -- Debian package metadata
- `builds/linux/andromica.desktop` -- Desktop entry

### Debian control file (`builds/linux/control`)

```
Package: andromica
Version: VERSION_PLACEHOLDER
Section: graphics
Priority: optional
Architecture: amd64
Maintainer: Heavymeta <support@heavymeta.digital>
Description: Andromica - Creative media application
 Audio/image processing with token support, IPFS integration,
 and Stellar blockchain connectivity.
```

### Desktop entry (`builds/linux/andromica.desktop`)

```ini
[Desktop Entry]
Name=Andromica
Comment=Creative media application
Exec=/opt/andromica/andromica
Icon=/usr/share/icons/hicolor/512x512/apps/andromica.png
Terminal=false
Type=Application
Categories=Graphics;AudioVideo;
```

### Linux build script (`builds/build_linux.sh`)

```bash
#!/usr/bin/env bash
set -euo pipefail

VERSION="${BUILD_VERSION:-1.0.0}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
PKG="andromica_${VERSION}_amd64"
STAGING="$ROOT/build/$PKG"

# 1. Build with PyInstaller (--onedir for .deb packaging)
cd "$ROOT"
uv run pyinstaller scripts/glasswing.spec \
  --distpath build/dist --workpath build/work --noconfirm

# 2. Assemble .deb structure
rm -rf "$STAGING"
mkdir -p "$STAGING/DEBIAN"
mkdir -p "$STAGING/opt/andromica"
mkdir -p "$STAGING/usr/bin"
mkdir -p "$STAGING/usr/share/applications"
mkdir -p "$STAGING/usr/share/icons/hicolor/512x512/apps"

# Control file
sed "s/VERSION_PLACEHOLDER/$VERSION/" \
  "$SCRIPT_DIR/linux/control" > "$STAGING/DEBIAN/control"

# Copy built files
cp -r "$ROOT/build/dist/andromica/"* "$STAGING/opt/andromica/"
chmod +x "$STAGING/opt/andromica/andromica"

# Symlink + desktop entry + icon
ln -sf /opt/andromica/andromica "$STAGING/usr/bin/andromica"
cp "$SCRIPT_DIR/linux/andromica.desktop" "$STAGING/usr/share/applications/"
cp "$ROOT/static/icon.png" "$STAGING/usr/share/icons/hicolor/512x512/apps/andromica.png"

# 3. Build .deb
dpkg-deb --build "$STAGING" "$ROOT/build/dist/andromica-${VERSION}-linux-amd64.deb"
```

---

## Phase 4: GitHub Actions Workflow

### File to create

- `.github/workflows/build-installers.yml`

### Trigger

```yaml
on:
  push:
    tags: ['v*']
  workflow_dispatch:
```

### Jobs

| Job | Runner | Output |
|-----|--------|--------|
| `build-windows` | `windows-latest` | `andromica-VERSION-windows.msi` |
| `build-macos-arm` | `macos-14` | `andromica-VERSION-macos-arm64.dmg` |
| `build-linux` | `ubuntu-22.04` | `andromica-VERSION-linux-amd64.deb` |
| `create-release` | `ubuntu-latest` | GitHub Release with all artifacts |

### Required GitHub Secrets

| Secret | Purpose |
|--------|---------|
| `WINDOWS_CERT_PFX` | Base64-encoded code signing certificate |
| `WINDOWS_CERT_PASSWORD` | PFX password |
| `APPLE_CERT_P12` | Base64-encoded Developer ID certificate |
| `APPLE_CERT_PASSWORD` | P12 password |
| `APPLE_ID` | Apple Developer account email |
| `APPLE_APP_PASSWORD` | App-specific password for notarization |
| `APPLE_TEAM_ID` | Apple Developer Team ID |

---

## Phase 5: Release Script

### File to create

- `scripts/create_release.py` -- Tag + push to trigger CI

```
Usage:
  python scripts/create_release.py v1.0.0     # Create release
  python scripts/create_release.py --list      # Show existing tags
  python scripts/create_release.py --suggest   # Suggest next version
```

---

## PyInstaller Spec Changes Required

The current spec builds `--onefile` on Windows/Linux (everything packed into a single exe).
For MSI and .deb packaging, we need `--onedir` mode so the installer can harvest files.

Change the Windows/Linux section in `scripts/glasswing.spec` from single-exe to directory mode:

```python
# Current (onefile):
exe = EXE(pyz, a.scripts, a.binaries, a.datas, ...)

# New (onedir — same as macOS already does):
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, ...)
coll = COLLECT(exe, a.binaries, a.datas, name='andromica')
```

This change is backwards-compatible — `build_cross_platform.py` (used for dev builds)
can keep using `--onefile` via a separate spec or flag.

---

## Rollout Order

1. **Windows MSI** -- highest priority, solves the WebView2 data directory issue
   by installing to a stable location instead of extracting from a temp dir
2. **macOS DMG** -- needed for Gatekeeper compliance (signed + notarized)
3. **Linux .deb** -- lowest friction for Ubuntu/Debian users
4. **Code signing** -- can be deferred; installers work unsigned (with warnings)
5. **Release script** -- convenience, adapt from metavinci's `create_release.py`

---

## Dependencies

| Tool | Platform | Install |
|------|----------|---------|
| WiX Toolset v5 | Windows CI | `dotnet tool install -g wix` |
| `hdiutil` | macOS | Built-in |
| `dpkg-deb` | Linux CI | Built-in on Ubuntu |
| `signtool` | Windows CI | Comes with Windows SDK |
| `codesign` / `notarytool` | macOS CI | Comes with Xcode |

---

## File Tree (new files)

```
glasswing/
  builds/
    andromica.wxs              # WiX installer definition
    build_win.sh               # Windows build + MSI
    build_mac.sh               # macOS build + DMG
    build_linux.sh             # Linux build + .deb
    linux/
      control                  # Debian package metadata
      andromica.desktop        # Linux desktop entry
  scripts/
    create_release.py          # Tag + push release trigger
  .github/
    workflows/
      build-installers.yml     # CI pipeline for all platforms
```
