# Glasswing Build System

## Overview

Glasswing uses PyInstaller for creating cross-platform executables with GitHub Actions for automated builds.

## Local Development Build

### Prerequisites

```bash
# Install build dependencies
pip install pyinstaller pillow icnsutil

# Install application dependencies
pip install -r requirements.txt
```

### Build Process

```bash
# Generate icons
python scripts/generate_icons.py

# Check dependencies
python scripts/check_dependencies.py

# Build for current platform
python scripts/build_cross_platform.py

# Or specify platform
python scripts/build_cross_platform.py --platform linux

# Clean build before building
python scripts/build_cross_platform.py --clean
```

### Output

Executables are created in:
- Linux: `build/dist/glasswing`
- Windows: `build/dist/glasswing.exe`
- macOS: `build/dist/glasswing.app`

## CI/CD Builds

### Triggering Builds

**Simple Executables:**
```bash
git tag v0.1.0
git push origin v0.1.0
```

This triggers the GitHub Actions workflow that builds for all platforms.

### Build Matrix

- **Linux:** Ubuntu 22.04, Python 3.11
- **Windows:** windows-latest, Python 3.11
- **macOS Intel:** macos-13, Python 3.11
- **macOS ARM:** macos-latest, Python 3.11

### Artifacts

GitHub Actions creates artifacts for each platform:
- `glasswing-linux` - Linux executable
- `glasswing-windows` - Windows .exe
- `glasswing-macos-amd64` - macOS Intel .zip
- `glasswing-macos-arm64` - macOS ARM .zip

## Project Structure

```
glasswing/
├── .github/workflows/
│   └── build-simple.yml      # GitHub Actions workflow
├── scripts/
│   ├── build_cross_platform.py
│   ├── generate_icons.py
│   ├── check_dependencies.py
│   └── glasswing.spec
├── docs/
│   ├── INSTALL.md
│   └── BUILD.md
├── main.py
├── dialogs.py
├── img_edit.py
├── metadata.py
├── static/
├── templates/
└── requirements.txt
```

## PyInstaller Configuration

Main spec file: `scripts/glasswing.spec`

### Key Configurations

**Data files:**
- `static/` - Icons, fonts, logo.json
- `templates/` - Jinja2 templates

**Hidden imports:**
- nicegui, pywebview, wand, exiv2, etc.

**Exclusions:**
- pytest, unittest, tkinter

**Platform-specific:**
- Windows: icon.ico, --onefile
- macOS: icon.icns, .app bundle
- Linux: icon.png, --onefile

## Native Dependencies

Not bundled in Phase 1:
- ImageMagick/Wand
- ExifTool
- libexiv2

Users must install these separately (see docs/INSTALL.md).

## Known Issues

1. **pywebview + PyInstaller:** Some renderers may bundle unnecessarily
2. **Large executable size:** 114 dependencies = 80-150MB expected
3. **Font licensing:** OCR-A.ttf requires license verification
4. **macOS Gatekeeper:** Users must right-click > Open first time

## Debugging Builds

### Local Testing

```bash
# Clean build
python scripts/build_cross_platform.py --clean

# Check all dependencies
python scripts/check_dependencies.py

# Test executable
# Linux:
./build/dist/glasswing

# Windows:
build\dist\glasswing.exe

# macOS:
open build/dist/glasswing.app
```

### CI Debugging

View logs in GitHub Actions:
1. Go to Actions tab in GitHub
2. Click on the workflow run
3. Check "Build [platform] executable" step
4. Look for PyInstaller warnings
5. Verify artifact upload succeeded

### Common Issues

**Missing static files:**
- Check `datas` in spec file
- Verify paths relative to project root
- Test with `--clean` flag

**ImportError at runtime:**
- Add to `hiddenimports` in spec file
- Try `--collect-all <package>` for complex packages

**Native dependency errors:**
- Check system package installation in CI
- Verify PATH includes tool directories
- Review build logs for installation errors

## Testing Checklist

### Before Committing

- [ ] All scripts created
- [ ] Icons generated successfully
- [ ] check_dependencies.py passes
- [ ] Local build succeeds on development platform
- [ ] Executable runs and shows UI
- [ ] Static files load
- [ ] Templates render

### Before Tagging Release

- [ ] Version number updated in relevant files
- [ ] CHANGELOG updated
- [ ] All tests pass
- [ ] Documentation updated
- [ ] Workflow file syntax valid

### After Release

- [ ] GitHub Actions triggers on tag push
- [ ] All platform builds complete successfully
- [ ] All artifacts uploaded
- [ ] GitHub Release created with correct assets
- [ ] Test executables on actual hardware:
  - [ ] Windows 10
  - [ ] Windows 11
  - [ ] macOS Intel
  - [ ] macOS ARM
  - [ ] Ubuntu 22.04
  - [ ] Ubuntu 20.04

## Maintenance

### Updating Dependencies

1. Update `requirements.txt`
2. Test locally
3. Update `hiddenimports` in spec file if needed
4. Test CI build
5. Update INSTALL.md if new native deps required

### Updating Icons

1. Replace `static/icon.png`
2. Delete generated icon.ico and icon.icns
3. Run `python scripts/generate_icons.py`
4. Commit new icons

### Version Numbering

Follow semantic versioning:
- v0.x.x: Pre-release
- v1.0.0: First stable release
- v1.x.x: Minor updates
- v2.0.0: Major changes

### Creating a Release

```bash
# 1. Update version information
# 2. Test locally
python scripts/generate_icons.py
python scripts/build_cross_platform.py --clean
# Test the executable

# 3. Commit changes
git add .
git commit -m "Prepare v0.1.0 release"

# 4. Create and push tag
git tag v0.1.0
git push origin main
git push origin v0.1.0

# 5. Monitor GitHub Actions
# Visit: https://github.com/<user>/<repo>/actions

# 6. Download and test artifacts from GitHub Release
```

## Future Enhancements (Phase 2)

- Platform-specific installers (MSI, DMG, DEB)
- Code signing for Windows and macOS
- Native dependency bundling where feasible
- Automatic update mechanism
- Executable size optimization
- Build cache to speed up CI
