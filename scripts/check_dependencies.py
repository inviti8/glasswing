#!/usr/bin/env python3
"""
Check for required dependencies before building
"""

import subprocess
import sys
from pathlib import Path

# ASCII-compatible status symbols for Windows compatibility
CHECK = '[OK]'
CROSS = '[X]'
WARN = '[!]'


def check_python_package(package_name):
    """Check if Python package is installed"""
    try:
        __import__(package_name)
        return True
    except ImportError:
        return False


def check_system_command(cmd):
    """Check if system command is available"""
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=5)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def main():
    print("Checking build dependencies...\n")

    all_ok = True

    # Python packages
    print("Python packages:")
    required_packages = [
        'nicegui',
        'pywebview',
        'wand',
        'exiv2',
        'exiftool',
        'PIL',
        'jinja2',
        'hvym_stellar',
        'stellar_sdk',
        'aiposematic',
        'ipfslib',
    ]

    for pkg in required_packages:
        if check_python_package(pkg):
            print(f"  {CHECK} {pkg}")
        else:
            print(f"  {CROSS} {pkg} - MISSING")
            all_ok = False

    # Build tools
    print("\nBuild tools:")
    build_tools = [
        ('PyInstaller', 'pyinstaller'),
        ('Pillow', 'PIL'),
    ]

    for name, pkg in build_tools:
        if check_python_package(pkg):
            print(f"  {CHECK} {name}")
        else:
            print(f"  {CROSS} {name} - MISSING")
            all_ok = False

    # Native dependencies (warnings only)
    print("\nNative dependencies (optional but recommended):")
    native_deps = [
        ('ImageMagick', ['magick', '--version']),
        ('ImageMagick (Unix)', ['convert', '--version']),
        ('ExifTool', ['exiftool', '-ver']),
    ]

    for name, cmd in native_deps:
        if check_system_command(cmd):
            print(f"  {CHECK} {name}")
        else:
            print(f"  {WARN} {name} - not found (users will need to install)")

    # Static files
    print("\nStatic files:")
    static_files = [
        Path('static/icon.png'),
        Path('static/OCR-A.ttf'),
        Path('static/PhinoVariation.ttf'),
        Path('templates/gallery.html'),
    ]

    for file in static_files:
        if file.exists():
            print(f"  {CHECK} {file}")
        else:
            print(f"  {CROSS} {file} - MISSING")
            all_ok = False

    print("\n" + "="*50)
    if all_ok:
        print(f"{CHECK} All critical dependencies satisfied!")
        return 0
    else:
        print(f"{CROSS} Some dependencies are missing. Install them and try again.")
        return 1


if __name__ == '__main__':
    sys.exit(main())
