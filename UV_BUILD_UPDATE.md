# UV Build Migration Guide

## Overview

This document outlines the migration of our build system from traditional pip/venv to uv for improved dependency management and cross-platform compatibility. The migration ensures proper environment setup, dependency installation, and build reproducibility across Windows, macOS, and Linux.

## Key Changes Required

### 1. pyproject.toml Configuration

Our `pyproject.toml` now includes all dependencies with proper version pinning:

```toml
[project]
name = "glasswing"
version = "0.1.0"
description = "Glasswing project"
authors = [{name = "Glasswing Team"}]
readme = "README.md"
license = "MIT"
requires-python = ">=3.11"
dependencies = [
    # ... all dependencies including:
    "pywebview[qt]==6.1",  # Critical for Linux compatibility
]
```

**Critical Note**: `pywebview[qt]` is essential for Linux support. Without the Qt extra, pywebview fails to find a suitable backend on Linux systems.

### 2. Environment Setup Changes

#### Before (pip/venv):
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or .venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

#### After (uv):
```bash
# uv automatically creates and manages virtual environments
uv sync  # Installs all dependencies from pyproject.toml
uv run python main.py  # Runs with proper environment
```

### 3. Build Script Updates

#### Updated build_cross_platform.py

The main changes needed in `/scripts/build_cross_platform.py`:

```python
#!/usr/bin/env python3
"""
Cross-platform build script for Glasswing using uv
Supports building for Linux, macOS, and Windows
"""

import shutil
import subprocess
import sys
import os
from pathlib import Path
import argparse
import platform

class GlasswingBuilder:
    def __init__(self):
        self.cwd = Path.cwd()
        self.build_dir = self.cwd / 'build'
        self.scripts_dir = self.cwd / 'scripts'
        self.spec_file = self.scripts_dir / 'glasswing.spec'

    def sync_dependencies(self):
        """Sync dependencies using uv"""
        print("Syncing dependencies with uv...")
        try:
            subprocess.run(['uv', 'sync'], check=True, cwd=str(self.cwd))
            print("✅ Dependencies synced successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to sync dependencies: {e}")
            return False

    def ensure_pywebview_qt(self):
        """Ensure pywebview[qt] is installed for Linux compatibility"""
        if platform.system().lower() == 'linux':
            print("Ensuring pywebview[qt] is available for Linux...")
            try:
                # Check if pywebview[qt] is properly installed
                result = subprocess.run([
                    'uv', 'run', 'python', '-c', 
                    'import PyQt6.QtWebEngineWidgets; print("PyQt6 WebEngine available")'
                ], check=True, capture_output=True, cwd=str(self.cwd))
                print("✅ pywebview[qt] dependencies verified")
                return True
            except subprocess.CalledProcessError:
                print("Installing pywebview[qt] for Linux compatibility...")
                try:
                    subprocess.run(['uv', 'add', 'pywebview[qt]'], check=True, cwd=str(self.cwd))
                    print("✅ pywebview[qt] installed successfully")
                    return True
                except subprocess.CalledProcessError as e:
                    print(f"❌ Failed to install pywebview[qt]: {e}")
                    return False
        return True  # Not needed for other platforms

    def build_executable(self, target_platform=None):
        """Build executable using PyInstaller with uv"""
        if target_platform is None:
            target_platform = self.get_platform()

        print(f"\nBuilding for {target_platform}...")

        # Ensure dependencies are synced
        if not self.sync_dependencies():
            return False

        # Ensure pywebview[qt] for Linux
        if not self.ensure_pywebview_qt():
            return False

        # Use spec file with uv run
        if not self.spec_file.exists():
            print(f"Error: Spec file not found at {self.spec_file}")
            return False

        cmd = [
            'uv', 'run', 'pyinstaller',  # Key change: use uv run
            '--clean',
            '--noconfirm',
            '--distpath', str(self.build_dir / 'dist'),
            '--workpath', str(self.build_dir / 'work'),
            str(self.spec_file)
        ]

        print(f"Running: {' '.join(cmd)}")
        print("This may take several minutes...")

        try:
            result = subprocess.run(cmd, cwd=str(self.cwd), check=True)
            print(f"\n✅ Build completed successfully!")
            return True
        except subprocess.CalledProcessError as e:
            print(f"\n❌ Build failed: {e}")
            return False

def main():
    parser = argparse.ArgumentParser(description='Build glasswing for target platform using uv')
    parser.add_argument('--platform', choices=['linux', 'macos', 'windows'],
                       help='Target platform (auto-detected if not specified)')
    parser.add_argument('--clean', action='store_true',
                       help='Clean build directory before building')
    parser.add_argument('--check-deps', action='store_true',
                       help='Check and sync dependencies only')

    args = parser.parse_args()

    builder = GlasswingBuilder()

    if args.check_deps:
        success = builder.sync_dependencies() and builder.ensure_pywebview_qt()
        sys.exit(0 if success else 1)

    if args.clean:
        builder.clean_build_directory()

    # Build
    success = builder.build_executable(args.platform)

    if not success:
        sys.exit(1)

    print("\n" + "="*50)
    print("Build process complete!")
    print("Next steps:")
    print("1. Test executable manually")
    print("2. Verify static files load correctly")
    print("3. Check pywebview functionality on target platform")

if __name__ == "__main__":
    main()
```

### 4. GitHub Actions Updates

#### Updated .github/workflows/build-simple.yml

**Key Changes to Existing Workflow:**

1. **Replace Python setup with uv**:
   ```yaml
   # OLD:
   - name: Set up Python 3.11
     uses: actions/setup-python@v4
     with:
       python-version: '3.11'
   
   # NEW:
   - name: Install uv
     uses: astral-sh/setup-uv@v3
     with:
       version: "latest"
   
   - name: Set up Python
     run: |
       uv python install 3.11
   ```

2. **Update dependency installation**:
   ```yaml
   # OLD:
   - name: Install Python dependencies
     run: |
       python -m pip install --upgrade pip
       pip install -r requirements.txt
       pip install pyinstaller pillow
   
   # NEW:
   - name: Install Python dependencies
     run: |
       uv sync
       uv add --dev pyinstaller pillow
   ```

3. **Add Linux Qt dependencies** (critical for pywebview):
   ```yaml
   # Add to Linux job before dependency installation:
   - name: Install Qt dependencies for pywebview
     if: matrix.os == 'ubuntu-22.04'
     run: |
       sudo apt-get update
       sudo apt-get install -y \
         python3-pyqt6 \
         python3-pyqt6.qtwebengine \
         python3-pyqt6.qtwebchannel \
         libqt6webenginecore6 \
         libqt6webenginewidgets6 \
         libqt6gui6 \
         libqt6widgets6
   ```

4. **Update build commands**:
   ```yaml
   # OLD:
   - name: Build Linux executable
     run: python scripts/build_cross_platform.py
   
   # NEW:
   - name: Build Linux executable
     run: uv run python scripts/build_cross_platform.py
   ```

#### Complete Updated Workflow:

```yaml
name: Build Simple Cross-Platform

on:
  push:
    tags: [ 'v*' ]
  workflow_dispatch:

permissions:
  contents: write
  actions: read

jobs:
  build-linux:
    runs-on: ubuntu-22.04

    steps:
    - uses: actions/checkout@v4

    - name: Install uv
      uses: astral-sh/setup-uv@v3
      with:
        version: "latest"

    - name: Set up Python
      run: |
        uv python install 3.11

    - name: Install system dependencies
      run: |
        sudo apt-get update
        sudo apt-get install -y \
          imagemagick libmagickwand-dev \
          libexiv2-27 libexiv2-dev \
          libxcb-xinerama0 libxcb-cursor0 \
          libwebkit2gtk-4.0-37 \
          python3-pyqt6 \
          python3-pyqt6.qtwebengine \
          python3-pyqt6.qtwebchannel \
          libqt6webenginecore6 \
          libqt6webenginewidgets6 \
          libqt6gui6 \
          libqt6widgets6

    - name: Install Python dependencies
      run: |
        uv sync
        uv add --dev pyinstaller pillow

    - name: Ensure pywebview[qt] for Linux
      run: |
        uv add pywebview[qt]

    - name: Verify media dependencies
      run: |
        uv run python -c "import biscuit_auth; import nacl; import hvym_stellar; import aiposematic; print('Media deps OK')"

    - name: Generate icons
      run: uv run python scripts/generate_icons.py

    - name: Verify media features
      run: uv run python scripts/verify_audio_build.py

    - name: Build Linux executable
      run: uv run python scripts/build_cross_platform.py

    - name: Upload Linux build
      uses: actions/upload-artifact@v4
      with:
        name: glasswing-linux
        path: build/dist/glasswing
        retention-days: 30

  build-windows:
    runs-on: windows-latest

    steps:
    - uses: actions/checkout@v4

    - name: Install uv
      uses: astral-sh/setup-uv@v3
      with:
        version: "latest"

    - name: Set up Python
      run: |
        uv python install 3.11

    - name: Install Python dependencies
      run: |
        uv sync
        uv add --dev pyinstaller pillow

    - name: Verify media dependencies
      run: |
        uv run python -c "import biscuit_auth; import nacl; import hvym_stellar; import aiposematic; print('Media deps OK')"

    - name: Generate icons
      run: uv run python scripts/generate_icons.py

    - name: Verify media features
      run: uv run python scripts/verify_audio_build.py

    - name: Build Windows executable
      run: uv run python scripts/build_cross_platform.py

    - name: Upload Windows build
      uses: actions/upload-artifact@v4
      with:
        name: glasswing-windows
        path: build/dist/glasswing.exe
        retention-days: 30

  build-macos:
    runs-on: macos-14  # Apple Silicon (M1+)

    steps:
    - uses: actions/checkout@v4

    - name: Install uv
      uses: astral-sh/setup-uv@v3
      with:
        version: "latest"

    - name: Set up Python
      run: |
        uv python install 3.11

    - name: Install system dependencies
      run: |
        brew install imagemagick

    - name: Install Python dependencies
      run: |
        uv sync
        uv add --dev pyinstaller pillow icnsutil

    - name: Verify media dependencies
      run: |
        uv run python -c "import biscuit_auth; import nacl; import hvym_stellar; import aiposematic; print('Media deps OK')"

    - name: Generate icons
      run: uv run python scripts/generate_icons.py

    - name: Verify media features
      run: uv run python scripts/verify_audio_build.py

    - name: Build macOS executable
      run: uv run python scripts/build_cross_platform.py

    - name: Create ZIP
      run: |
        cd build/dist
        zip -r glasswing-macos.zip glasswing.app

    - name: Upload macOS build
      uses: actions/upload-artifact@v4
      with:
        name: glasswing-macos
        path: build/dist/glasswing-macos.zip
        retention-days: 30

  create-release:
    runs-on: ubuntu-latest
    needs: [build-linux, build-windows, build-macos]
    if: startsWith(github.ref, 'refs/tags/')

    steps:
    - uses: actions/checkout@v4

    - name: Download all builds
      uses: actions/download-artifact@v4
      with:
        path: builds

    - name: Create release package
      run: |
        mkdir -p release
        cp builds/glasswing-linux/glasswing release/glasswing-linux
        cp builds/glasswing-windows/glasswing.exe release/glasswing-windows.exe
        cp builds/glasswing-macos/*.zip release/

    - name: Create installation guide
      run: |
        cat > release/INSTALL.txt << 'EOF'
        # Glasswing Installation Guide

        ## Prerequisites

        Glasswing requires following native tools to be installed:

        ### Windows
        1. ImageMagick: https://imagemagick.org/script/download.php#windows
           - Select 16-bit dynamic version
           - During installation, check "Add to PATH"
        2. ExifTool: https://exiftool.org/
           - Download and add to PATH
        3. (Optional) IPFS Desktop: https://docs.ipfs.tech/install/ipfs-desktop/

        ### macOS
        brew install imagemagick exiftool
        # Optional: brew install ipfs

        ### Linux (Ubuntu/Debian)
        sudo apt install imagemagick libmagickwand-dev exiftool libexiv2-27
        # Optional: sudo apt install ipfs

        ## Installation

        ### Linux
        chmod +x glasswing-linux
        ./glasswing-linux

        ### Windows
        Double-click glasswing-windows.exe or run from command prompt.

        ### macOS
        1. Unzip glasswing-macos.zip
        2. Move glasswing.app to Applications
        3. Right-click and select "Open" (first time only, due to Gatekeeper)

        Note: This is an ARM (Apple Silicon) build. Intel Macs can run it
        via Rosetta 2, which macOS enables automatically.

        ## Notes

        - IPFS Features: Require IPFS daemon running at 127.0.0.1:5001
        - Font Licensing: OCR-A.ttf is copyrighted by Monotype (1994)

        For detailed documentation, see docs/INSTALL.md in the repository.
        EOF

    - name: Create GitHub Release
      uses: softprops/action-gh-release@v1
      with:
        files: release/*
        body_path: release/INSTALL.txt
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

**Key Migration Points:**
1. **Keep existing workflow structure** - maintains your current job organization
2. **Replace `actions/setup-python` with `astral-sh/setup-uv`**
3. **Replace `pip install` with `uv sync`**
4. **Add `uv run` prefix to all Python commands**
5. **Add Linux Qt dependencies** for pywebview compatibility
6. **Keep existing artifact upload and release logic**

### 5. Development Workflow Changes

#### For Developers:

1. **Initial Setup**:
   ```bash
   # Clone repository
   git clone <repository>
   cd glasswing
   
   # Install uv (if not already installed)
   curl -LsSf https://astral.sh/uv/install.sh | sh
   
   # Sync dependencies
   uv sync
   ```

2. **Development**:
   ```bash
   # Run the application
   uv run python main.py
   
   # Run any script with proper environment
   uv run python scripts/check_dependencies.py
   ```

3. **Building**:
   ```bash
   # Build for current platform
   python scripts/build_cross_platform.py
   
   # Build for specific platform
   python scripts/build_cross_platform.py --platform linux
   
   # Clean build
   python scripts/build_cross_platform.py --clean
   ```

## Platform-Specific Considerations

### Linux

**Critical Requirements:**
- `pywebview[qt]` with PyQt6 WebEngine
- System Qt libraries: `libqt6webenginecore6`, `libqt6webenginewidgets6`
- Python Qt bindings: `python3-pyqt6.qtwebengine`

**Build Issues Resolved:**
- White screen rendering: Fixed by proper Qt backend
- Import errors: Resolved with `pywebview[qt]` extra
- Missing dependencies: Handled by `uv sync`

### macOS

**Requirements:**
- PyObjC frameworks (usually included)
- Optional: Homebrew for additional dependencies

### Windows

**Requirements:**
- WebView2 Runtime (usually pre-installed on Windows 10+)
- .NET Framework (pre-installed)

## Testing Strategy

### Pre-Build Tests
```bash
# Test dependency resolution
uv run python -c "import webview; print('pywebview OK')"

# Test Qt availability on Linux
uv run python -c "import PyQt6.QtWebEngineWidgets; print('Qt WebEngine OK')"
```

### Post-Build Tests
```bash
# Test executable functionality
./build/dist/glasswing --help  # Linux/macOS
./build/dist/glasswing.exe --help  # Windows

# Test pywebview functionality
./build/dist/glasswing --test-webview
```

## Migration Checklist

- [x] Update `pyproject.toml` with all dependencies
- [x] Add `pywebview[qt]` for Linux compatibility
- [ ] Update `build_cross_platform.py` to use `uv run`
- [ ] Update GitHub Actions workflow
- [ ] Update development documentation
- [ ] Test builds on all target platforms
- [ ] Update CI/CD pipeline
- [ ] Create migration guide for team members

## Troubleshooting

### Common Issues

1. **"pywebview backend not found" on Linux**:
   ```bash
   uv add pywebview[qt]
   sudo apt-get install python3-pyqt6.qtwebengine
   ```

2. **Build fails with import errors**:
   ```bash
   uv sync --refresh  # Refresh dependency cache
   ```

3. **Executable runs but shows white screen**:
   - Verify Qt WebEngine is installed
   - Check system Qt library versions
   - Test with `uv run python -c "import webview; webview.create_window('Test', html='<html><body>Test</body></html>').start()"`

## Benefits of Migration

1. **Faster dependency resolution**: uv is significantly faster than pip
2. **Cross-platform consistency**: Same toolchain everywhere
3. **Better caching**: Intelligent dependency caching
4. **Simplified CI/CD**: Single tool for all platforms
5. **Improved reliability**: Better dependency conflict resolution
6. **Future-proof**: Actively maintained with regular updates

## Rollback Plan

If issues arise during migration:

1. Keep `requirements.txt` as backup
2. Maintain old build script temporarily
3. Use feature flags for gradual rollout
4. Document issues and solutions for team reference

---

**Last Updated**: 2025-03-06  
**Migration Owner**: Development Team  
**Review Date**: 2025-03-20
