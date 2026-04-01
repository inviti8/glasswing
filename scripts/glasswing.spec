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
    # SSL (ensure DLLs are bundled for uv's standalone Python)
    'ssl',
    '_ssl',
    # Crypto / token dependencies
    'biscuit_auth',
    'nacl',
    'nacl.bindings',
    'nacl.secret',
]

# Exclusions to reduce size
excludes = [
    'tkinter',
    'pytest',
    'unittest',
    'doctest',
    'matplotlib.tests',
    'numpy.tests',
]

# Collect SSL DLLs — uv's standalone Python may bundle them outside PyInstaller's search path
_ssl_binaries = []
_ssl_exts = ('.dll', '.pyd') if sys.platform == 'win32' else ('.so', '.dylib')
try:
    import _ssl
    _ssl_dir = os.path.dirname(_ssl.__file__) if hasattr(_ssl, '__file__') else None
    if _ssl_dir:
        for f in os.listdir(_ssl_dir):
            if f.lower().startswith(('libssl', 'libcrypto', '_ssl')) and f.endswith(_ssl_exts):
                _ssl_binaries.append((os.path.join(_ssl_dir, f), '.'))
except Exception:
    pass
# Also try next to the Python executable
_python_dir = os.path.dirname(sys.executable)
for f in os.listdir(_python_dir):
    if f.lower().startswith(('libssl', 'libcrypto')) and f.endswith(_ssl_exts):
        _ssl_binaries.append((os.path.join(_python_dir, f), '.'))
if _ssl_binaries:
    print(f"Collecting SSL binaries: {[b[0] for b in _ssl_binaries]}")

a = Analysis(
    [str(main_script)],
    pathex=[str(spec_root)],
    binaries=_ssl_binaries,
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

# Splash screen disabled — Tcl/Tk conflicts with PyQt6 in frozen builds on Windows,
# hangs macOS builds, and uv's standalone Python often lacks shared Tcl/Tk libs.
# TODO: Revisit when PyInstaller resolves Tcl/Tk + Qt coexistence issues.
_has_splash = False
splash = None

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
