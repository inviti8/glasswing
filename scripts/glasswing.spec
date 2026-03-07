# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Glasswing
"""

import sys
from pathlib import Path

# Application metadata
APP_NAME = 'andromica'

# Paths - SPECPATH is provided by PyInstaller and points to the directory containing the spec file
# Go up one level from scripts/ to project root
spec_root = Path(SPECPATH).parent if 'SPECPATH' in dir() else Path('.').resolve()
static_dir = spec_root / 'static'
templates_dir = spec_root / 'templates'
main_script = spec_root / 'main.py'

# Find pywebview lib directory (contains WebView2 DLLs needed at runtime)
import importlib
_webview_spec = importlib.util.find_spec('webview')
_webview_lib = Path(_webview_spec.origin).parent / 'lib' if _webview_spec else None

# Collect data files
datas = [
    (str(static_dir), 'static'),
    (str(templates_dir), 'templates'),
]

# Bundle pywebview's native DLLs (WebView2, .NET interop)
if _webview_lib and _webview_lib.exists():
    datas.append((str(_webview_lib), 'webview/lib'))

# Platform-specific settings
if sys.platform == 'win32':
    icon_file = str(spec_root / 'icon.ico')
    console = False  # Disabled by default
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
    'webview',
    'webview.platforms.edgechromium',
    'clr',
    'clr_loader',
    'pythonnet',
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
    # Local application modules
    'audio_tokens',
    'video_tokens',
    'markdown_tokens',
    'png_chunks',
    'data_pod_audio',
    'client_rendering',
    'dialogs',
    'metadata',
    'img_edit',
    'task_runner',
    # Crypto / token dependencies
    'biscuit_auth',
    'nacl',
    'nacl.bindings',
    'nacl.secret',
]

# Exclusions to reduce size
# Note: tkinter is NOT excluded — pyi_splash needs a minimal Tk subset
excludes = [
    'pytest',
    'unittest',
    'doctest',
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

# Splash screen — shown by the bootloader before Python starts
# Requires Tcl/Tk *shared* libraries. uv's standalone Python (python-build-standalone)
# often statically links Tcl/Tk, which makes _tkinter a built-in without __file__.
# PyInstaller intentionally calls sys.exit() when it can't find the shared libs
# (see pyinstaller/pyinstaller#9022), so we must pre-check before calling Splash().
_has_splash = False
splash = None
_tk_available = False
try:
    import _tkinter
    # If _tkinter has no __file__, it's statically linked and incompatible with splash
    _tk_available = hasattr(_tkinter, '__file__')
except ImportError:
    pass

if _tk_available:
    try:
        splash = Splash(
            str(spec_root / 'static' / 'splash.png'),
            binaries=a.binaries,
            datas=a.datas,
            text_pos=(10, 460),
            text_size=12,
            text_color='#25F5F8',
            text_default='Loading Andromica...',
            max_img_size=(760, 480),
            always_on_top=True,
        )
        _has_splash = True
    except (Exception, SystemExit) as e:
        splash = None
        print(f"WARNING: Splash screen disabled ({e})")
else:
    print("WARNING: Splash screen disabled (Tcl/Tk shared libraries not available)")

# Helper lists for splash binaries
_splash_args = [splash] if _has_splash else []
_splash_binaries = [splash.binaries] if _has_splash else []

# Different build strategies per platform
if sys.platform == 'darwin':
    # macOS: Create .app bundle (not --onefile)
    # Note: For multi-arch support, build separately on Intel and ARM Macs
    # universal2 requires all dependencies to be fat binaries which isn't always available
    exe = EXE(
        pyz,
        *_splash_args,
        a.scripts,
        [],
        exclude_binaries=True,
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,  # Disabled - UPX can corrupt files
        console=console,
        disable_windowed_traceback=False,
        target_arch=None,  # Build for native architecture (build on each platform separately)
        codesign_identity=None,
        entitlements_file=None,
        icon=icon_file,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        *_splash_binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,  # Disabled - UPX can corrupt files
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
            'LSMinimumSystemVersion': '10.13.0',  # macOS High Sierra minimum
            'CFBundleShortVersionString': '1.0.0',
        },
    )
else:
    # Windows/Linux: Single executable
    exe = EXE(
        pyz,
        *_splash_args,
        a.scripts,
        *_splash_binaries,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name=APP_NAME,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,  # Disabled - UPX corrupts JS files like echart assets
        upx_exclude=[],
        runtime_tmpdir=None,
        console=console,
        disable_windowed_traceback=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=icon_file,
    )
