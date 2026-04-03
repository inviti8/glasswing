#!/usr/bin/env python3
"""
Cross-platform build script for Glasswing
Supports building for Linux, macOS, and Windows
"""

import shutil
import subprocess
import sys
import os
from pathlib import Path
import argparse
import platform

# ASCII-compatible status symbols for Windows compatibility
CHECK = '[OK]'
WARN = '[!]'


class GlasswingBuilder:
    def __init__(self):
        self.cwd = Path.cwd()
        self.build_dir = self.cwd / 'build'
        self.scripts_dir = self.cwd / 'scripts'
        self.spec_file = self.scripts_dir / 'glasswing.spec'

    def clean_build_directory(self):
        """Clean the build directory"""
        if self.build_dir.exists():
            print(f"Cleaning {self.build_dir}...")
            shutil.rmtree(self.build_dir)
        self.build_dir.mkdir(parents=True)
        print("Build directory cleaned.")

    def get_platform(self):
        """Detect current platform"""
        system = platform.system().lower()
        if system == 'darwin':
            return 'macos'
        elif system == 'windows':
            return 'windows'
        else:
            return 'linux'

    def check_native_dependencies(self):
        """Check for required native dependencies"""
        print("\nChecking native dependencies...")

        deps = {
            'ImageMagick (Windows)': ['magick', '--version'],
            'ImageMagick (Unix)': ['convert', '--version'],
            'ExifTool': ['exiftool', '-ver'],
        }

        missing = []
        for name, cmd in deps.items():
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=5)
                if result.returncode == 0:
                    print(f"  {CHECK} {name} found")
                else:
                    missing.append(name)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass  # Try next

        if len(missing) == len(deps):
            print(f"  {WARN} WARNING: No native dependencies found")
            print("  The built executable will require these to be installed separately.")
            print("  See INSTALL.md for installation instructions.")
        else:
            print(f"  {CHECK} At least one ImageMagick variant found")

        return True  # Non-blocking

    def sync_dependencies(self):
        """Sync dependencies using uv"""
        print("Syncing dependencies with uv...")
        try:
            subprocess.run(['uv', 'sync'], check=True, cwd=str(self.cwd))
            print(f"{CHECK} Dependencies synced successfully")
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
                print(f"{CHECK} pywebview[qt] dependencies verified")
                return True
            except subprocess.CalledProcessError:
                print("Installing pywebview[qt] for Linux compatibility...")
                try:
                    subprocess.run(['uv', 'add', 'pywebview[qt]'], check=True, cwd=str(self.cwd))
                    print(f"{CHECK} pywebview[qt] installed successfully")
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
            print(f"\n{CHECK} Build completed successfully!")

            # Show output location (all platforms now use onedir / .app bundle)
            if target_platform == 'macos':
                output_path = self.build_dir / 'dist' / 'andromica.app'
            else:
                output_path = self.build_dir / 'dist' / 'andromica'

            if output_path.exists():
                print(f"\nBuild output at: {output_path}")
                size = sum(f.stat().st_size for f in output_path.rglob('*') if f.is_file())
                size_mb = size / (1024 * 1024)
                print(f"Size: {size_mb:.1f} MB")

            return True
        except subprocess.CalledProcessError as e:
            print(f"\n{WARN} Build failed: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(description='Build andromica for target platform using uv')
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
