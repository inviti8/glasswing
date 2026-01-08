#!/usr/bin/env python3
"""
Generate platform-specific icon files from icon.png
"""

import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Pillow is required. Install with: pip install Pillow")
    sys.exit(1)


def make_ico(png_path, out_path, sizes=None):
    """Generate Windows .ico file"""
    if sizes is None:
        sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]

    img = Image.open(png_path)
    img.save(out_path, sizes=sizes)
    print(f"Generated {out_path}")


def make_icns(png_path, out_path):
    """Generate macOS .icns file"""
    try:
        from icnsutil import IcnsFile
    except ImportError:
        print("icnsutil is required for macOS icons. Install with: pip install icnsutil")
        return False

    import tempfile

    img = Image.open(png_path)
    icns = IcnsFile()

    size_code_map = [
        (16, "icp4"),
        (32, "icp5"),
        (64, "icp6"),
        (128, "ic07"),
        (256, "ic08"),
        (512, "ic09"),
        (1024, "ic10"),
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        for size, code in size_code_map:
            icon = img.resize((size, size), Image.LANCZOS)
            tmp_png = Path(tmpdir) / f"icon_{size}x{size}.png"
            icon.save(tmp_png, format="PNG")
            icns.add_media(code, file=str(tmp_png))
        icns.write(str(out_path))

    print(f"Generated {out_path}")
    return True


def main():
    cwd = Path.cwd()
    source_icon = cwd / 'static' / 'icon.png'

    if not source_icon.exists():
        print(f"Error: Source icon not found at {source_icon}")
        sys.exit(1)

    # Generate Windows .ico
    ico_path = cwd / 'icon.ico'
    if not ico_path.exists():
        make_ico(source_icon, ico_path)
    else:
        print(f"{ico_path} already exists, skipping")

    # Generate macOS .icns
    icns_path = cwd / 'icon.icns'
    if not icns_path.exists():
        if not make_icns(source_icon, icns_path):
            print("Skipping .icns generation (macOS builds may fail)")
    else:
        print(f"{icns_path} already exists, skipping")

    print("\nIcon generation complete!")


if __name__ == '__main__':
    main()
