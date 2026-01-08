# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Glasswing
"""

import sys
from pathlib import Path

# Application metadata
APP_NAME = 'glasswing'

# Paths - SPECPATH is provided by PyInstaller and points to the directory containing the spec file
# Go up one level from scripts/ to project root
spec_root = Path(SPECPATH).parent if 'SPECPATH' in dir() else Path('.').resolve()
static_dir = spec_root / 'static'
templates_dir = spec_root / 'templates'
main_script = spec_root / 'main.py'

# Collect data files
datas = [
    (str(static_dir), 'static'),
    (str(templates_dir), 'templates'),
]

# Platform-specific settings
if sys.platform == 'win32':
    icon_file = str(spec_root / 'icon.ico')
    console = False
elif sys.platform == 'darwin':
    icon_file = str(spec_root / 'icon.icns')
    console = False
else:  # Linux
    icon_file = str(spec_root / 'static' / 'icon.png')
    console = False

# Hidden imports for NiceGUI and dependencies
hiddenimports = [
    'nicegui',
    'fastapi',
    'uvicorn',
    'starlette',
    'pywebview',
    'wand',
    'exiv2',
    'exiftool',
    'hvym_stellar',
    'stellar_sdk',
    'aiposematic',
    'ipfslib',
    'jinja2',
    'PIL._tkinter_finder',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'cv2',
    'skimage',
    'numpy',
    'scipy',
]

# Exclusions to reduce size
excludes = [
    'pytest',
    'unittest',
    'doctest',
    'tkinter',
    'matplotlib.tests',
    'numpy.tests',
]

a = Analysis(
    [str(main_script)],
    pathex=[str(spec_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Different build strategies per platform
if sys.platform == 'darwin':
    # macOS: Create .app bundle (not --onefile)
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=console,
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=icon_file,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name=APP_NAME,
    )
    app = BUNDLE(
        coll,
        name=f'{APP_NAME}.app',
        icon=icon_file,
        bundle_identifier='com.metavinci.glasswing',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'LSBackgroundOnly': 'False',
        },
    )
else:
    # Windows/Linux: Single executable
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=console,
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=icon_file,
    )
