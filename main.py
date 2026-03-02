"""
Andromica - Audio Image Processing with Token Support
"""

import argparse
import time
import base64
import os
import sys
from typing import Optional, Dict, List, Any, Tuple, Callable, Union
import http.server
import socketserver
import threading
import webbrowser
import PIL
from PIL import Image
import io
import struct
import zlib
import json
import requests
import wand
from hvym_stellar import Stellar25519KeyPair, StellarSharedKey, HVYMDataToken
from stellar_sdk import Keypair
import asyncio

# Define app early to avoid circular imports
from nicegui import app, ui, run
from fastapi.staticfiles import StaticFiles


# Define choose_files early to avoid circular imports
async def choose_files():
    files = await app.native.main_window.create_file_dialog(allow_multiple=True)
    return files


# Audio Token Integration
from audio_tokens import (
    get_user_keypair,
    get_user_public_key,
    create_token_audio_image,
    extract_token_audio,
    detect_audio_format,
    is_audio_file,
)
from png_chunks import (
    has_audio_data,
    has_video_data,
    copy_token_chunks,
    remove_text_chunks,
    VIDEO_TOKEN_CID_PREFIX,
)
from video_tokens import (
    create_token_video_image,
    extract_token_video,
    is_video_file as is_video_file_check,
)
from data_pod_audio import (
    create_ninjs_data_pod_with_encrypted_tokens,
    process_data_pod_locally,
    determine_image_type,
)
from client_rendering import render_processed_data_pod, save_gallery_html

from nicegui import binding
from nicegui.binding import BindableProperty
from dialogs import *
from metadata import IPTC
from img_edit import *
from aiposematic import new_aposematic_img, recover_aposematic_img, SCRAMBLE_MODE
from iptcinfo3 import IPTCInfo
import exiv2
import atexit
import hashlib
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# APP NAME: Andromicae

# Configure static files directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
# Mount static files
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Session-scoped temp directory for editor images (raw/processed)
# Cleaned up automatically on app exit — no unprotected content persists
EDITOR_STORAGE_DIR = tempfile.mkdtemp(prefix="glasswing_editor_")
atexit.register(shutil.rmtree, EDITOR_STORAGE_DIR, ignore_errors=True)
app.mount("/editor", StaticFiles(directory=EDITOR_STORAGE_DIR), name="editor")

_INITIALIZED = False

ipfs_endpoint = "http://127.0.0.1"
port = "5001"
artist = "Unknown"
watermark = False
iptc = False
access_token = ""

ipfs_webui = "http://localhost"
ipfs_webui_port = "8081"


pintheon_endpoint = "http://127.0.0.1"
pintheon_port = "9999"

gateway_url = ""

# Browser content globals
update_browser_content = None
pending_browser_html = None

# Command-line argument parsing
def parse_args():
    parser = argparse.ArgumentParser(description="Andromica - Audio Image Processing")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode for the native webview (opens DevTools)"
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Show console output (useful for debugging)"
    )
    # Parse known args to avoid conflicts with NiceGUI/uvicorn args
    args, _ = parser.parse_known_args()
    return args

cli_args = parse_args()

app.native.window_args["resizable"] = True
if cli_args.debug:
    app.native.start_args["debug"] = True
app.native.settings["ALLOW_DOWNLOADS"] = True
app.native.window_args["title"] = "Andromica"
# app.native.window_args['frameless'] = True

print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
print(app.native.settings)
print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")

stellar_keys = None
hvym_keys = None
hvym_public_key = None

file_container = None
state_container = None
tabs = None
dark_mode_instance = None

PRIMARY_COLOR = "#25F5F8"
SECONDARY_COLOR = "#E59F61"
TEXT_COLOR = "#6C9D9D"
BG_COLOR = "#FBF7F4"
CARD_BG = "#E5D4C8"
BORDER_COLOR = "#FFAD20"

DARK_PRIMARY = "#578485"
DARK_SECONDARY = "#A4856A"
DARK_TEXT = "#EFF1C6"
DARK_BG = "#1A1A1A"
DARK_CARD = "#625146"
DARK_BORDER = "#EFF1C6"


# ============================================================================
# HELPER FUNCTIONS FOR DEPLOY FLOWS
# ============================================================================

def get_gallery_colors() -> dict:
    """Get current color scheme based on dark mode setting."""
    app_colors = app.storage.user.get("app_colors", {})
    is_dark_mode = app.storage.user.get("dark_mode", None)

    if is_dark_mode:
        return {
            "primary": app_colors.get("dark-primary", DARK_PRIMARY),
            "secondary": app_colors.get("dark-secondary", DARK_SECONDARY),
            "text": app_colors.get("dark-text", DARK_TEXT),
            "bg": app_colors.get("dark-bg", DARK_BG),
            "card": app_colors.get("dark-card", DARK_CARD),
            "border": app_colors.get("dark-border", DARK_BORDER),
        }
    else:
        return {
            "primary": app_colors.get("primary", PRIMARY_COLOR),
            "secondary": app_colors.get("secondary", SECONDARY_COLOR),
            "text": app_colors.get("text-color", TEXT_COLOR),
            "bg": app_colors.get("bg-color", BG_COLOR),
            "card": app_colors.get("card-bg", CARD_BG),
            "border": app_colors.get("border-color", BORDER_COLOR),
        }


def render_gallery_html(data_pod: dict) -> str:
    """
    Render gallery HTML from data pod using Jinja2 template.

    Args:
        data_pod: Processed data pod dictionary

    Returns:
        str: Rendered HTML content
    """
    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    jinja_env = Environment(loader=FileSystemLoader(template_dir))
    template = jinja_env.get_template("gallery.html")

    colors = get_gallery_colors()
    is_dark_mode = app.storage.user.get("dark_mode", None)

    template_context = {
        "data_pod": data_pod,
        "ipfs_gateway": f"{ipfs_webui}:{ipfs_webui_port}",
        "ipfs_webui": ipfs_webui,
        "ipfs_webui_port": ipfs_webui_port,
        "gallery_title": app.storage.user.get("gallery_title", ""),
        "gallery_description": app.storage.user.get("gallery_description", ""),
        "colors": colors,
        "is_dark_mode": is_dark_mode,
    }
    return template.render(**template_context)


def save_gallery_to_ipfs(html_content: str) -> tuple:
    """
    Save rendered gallery HTML to temp file and IPFS.

    Args:
        html_content: Rendered HTML string

    Returns:
        tuple: (html_temp_path, html_hash) - hash is None if IPFS add failed
    """
    timestamp = app.storage.user.get(
        "latest_data_pod_timestamp", datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    html_temp_path = os.path.join(
        tempfile.gettempdir(), f"ninjs_data_pod_{timestamp}.html"
    )
    with open(html_temp_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    html_hash = ipfs_add(html_temp_path)
    if html_hash:
        app.storage.user["latest_gallery_html_hash"] = html_hash
        # Fix: Properly persist tmp_files list
        tmp_files = app.storage.user.get("tmp_files", [])
        tmp_files.append(html_temp_path)
        app.storage.user["tmp_files"] = tmp_files
        print(f"Saved rendered HTML to IPFS: {html_hash}")
    else:
        print(f"Failed to add HTML to IPFS, saved locally at: {html_temp_path}")

    return html_temp_path, html_hash


def ensure_storage_list(key: str) -> list:
    """
    Ensure a storage list exists and return it.
    This avoids the bug where app.storage.user.get("key", []).append() doesn't persist.

    Args:
        key: Storage key name

    Returns:
        list: The storage list (creates empty list if doesn't exist)
    """
    if key not in app.storage.user:
        app.storage.user[key] = []
    return app.storage.user[key]


def append_to_storage_list(key: str, value) -> None:
    """
    Safely append a value to a storage list with proper persistence.

    Args:
        key: Storage key name
        value: Value to append
    """
    lst = app.storage.user.get(key, [])
    lst.append(value)
    app.storage.user[key] = lst


def validate_img_state() -> tuple:
    """
    Validate and return the current image state.

    Returns:
        tuple: (state_index, state_name) or (None, None) if invalid
    """
    img_states = {1: "raw", 2: "processed", 3: "aposematic", 4: "enciphered"}
    idex = app.storage.user.get("img_state", 1)
    if idex not in img_states:
        return None, None
    return idex, img_states[idex]


def init():
    global _INITIALIZED
    if _INITIALIZED:
        return
    global file_container
    global state_container
    global browser_content
    global update_browser_content
    global watermark_container
    global stellar_keys
    global hvym_keys
    global hvym_public_key
    global stellar_secret
    global artist
    global use_watermark
    global watermark
    global watermark_size
    global watermark_position
    global watermark_padding
    global iptc_data
    global current_img_folder
    global img_states
    global tmp_files
    global scramble_modes
    global tabs
    global editor_ctrls
    global editor_settings
    global browser_ctrls
    global browser_settings
    global PRIMARY_COLOR
    global SECONDARY_COLOR
    global TEXT_COLOR
    global BG_COLOR
    global CARD_BG
    global BORDER_COLOR
    global DARK_PRIMARY
    global DARK_SECONDARY
    global DARK_TEXT
    global DARK_BG
    global DARK_CARD
    global DARK_BORDER

    iptc_data = IPTC()
    iptc_data.init()

    data_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")

    if os.path.exists(data_file):
        with open(data_file, "r") as f:
            data = json.load(f)
            # Get values from data or use defaults
            stellar_secret = data["stellar_secret"]
            artist = data["artist"]
            app.storage.user["use_watermark"] = data["use_watermark"]
            app.storage.user["watermark"] = data["watermark"]
            app.storage.user["watermark_size"] = data["watermark_size"]
            app.storage.user["watermark_position"] = data["watermark_position"]
            app.storage.user["watermark_padding"] = data["watermark_padding"]
            app.storage.user["scramble_mode"] = data["scramble_mode"]
            app.storage.user["op_string"] = data["op_string"]
            app.storage.user["use_iptc"] = data["use_iptc"]
            iptc_data = IPTC.from_dict(data["iptc_data"])
            iptc_data.init_storage()
            app.storage.user["tmp_files"] = data["tmp_files"]
            app.storage.user["subscribers"] = data["subscribers"]
            app.storage.user["subscriptions"] = data["subscriptions"]
            app.storage.user["content_folders"] = data["content_folders"]
            app.storage.user["app_mode"] = data["app_mode"]
            # Load app_colors with fallback to defaults if not in data.json
            app.storage.user["app_colors"] = data.get(
                "app_colors",
                {
                    "primary": PRIMARY_COLOR,
                    "secondary": SECONDARY_COLOR,
                    "text-color": TEXT_COLOR,
                    "bg-color": BG_COLOR,
                    "card-bg": CARD_BG,
                    "border-color": BORDER_COLOR,
                    "dark-primary": DARK_PRIMARY,
                    "dark-secondary": DARK_SECONDARY,
                    "dark-text": DARK_TEXT,
                    "dark-bg": DARK_BG,
                    "dark-card": DARK_CARD,
                    "dark-border": DARK_BORDER,
                },
            )
            app.storage.user["latest_data_pod_hash"] = data.get(
                "latest_data_pod_hash", None
            )
            app.storage.user["latest_gallery_html_hash"] = data.get(
                "latest_gallery_html_hash", None
            )
            app.storage.user["latest_data_pod_timestamp"] = data.get(
                "latest_data_pod_timestamp", None
            )
            app.storage.user["gallery_title"] = data.get("gallery_title", "")
            app.storage.user["gallery_description"] = data.get(
                "gallery_description", ""
            )
            app.storage.user["dark_mode"] = data.get("dark_mode", None)
            app.storage.user["debug_secret"] = data.get("debug_secret", None)
    else:
        # Initialize app_colors with defaults before calling persistent_save_data()
        app.storage.user["app_colors"] = {
            "primary": PRIMARY_COLOR,
            "secondary": SECONDARY_COLOR,
            "text-color": TEXT_COLOR,
            "bg-color": BG_COLOR,
            "card-bg": CARD_BG,
            "border-color": BORDER_COLOR,
            "dark-primary": DARK_PRIMARY,
            "dark-secondary": DARK_SECONDARY,
            "dark-text": DARK_TEXT,
            "dark-bg": DARK_BG,
            "dark-card": DARK_CARD,
            "dark-border": DARK_BORDER,
        }
        persistent_save_data()
        with open(data_file, "r") as f:
            data = json.load(f)
            stellar_secret = data["stellar_secret"]
            artist = data["artist"]
            app.storage.user["use_watermark"] = data["use_watermark"]
            app.storage.user["watermark"] = data["watermark"]
            app.storage.user["watermark_size"] = data["watermark_size"]
            app.storage.user["watermark_position"] = data["watermark_position"]
            app.storage.user["watermark_padding"] = data["watermark_padding"]
            app.storage.user["scramble_mode"] = data["scramble_mode"]
            app.storage.user["op_string"] = data["op_string"]
            app.storage.user["use_iptc"] = data["use_iptc"]
            iptc_data = IPTC.from_dict(data["iptc_data"])
            iptc_data.init_storage()
            app.storage.user["tmp_files"] = data["tmp_files"]
            app.storage.user["subscribers"] = data["subscribers"]
            app.storage.user["subscriptions"] = data["subscriptions"]
            app.storage.user["content_folders"] = data["content_folders"]
            app.storage.user["app_mode"] = data["app_mode"]
            # app_colors already initialized above
            app.storage.user["latest_data_pod_hash"] = data.get(
                "latest_data_pod_hash", None
            )
            app.storage.user["latest_gallery_html_hash"] = data.get(
                "latest_gallery_html_hash", None
            )
            app.storage.user["latest_data_pod_timestamp"] = data.get(
                "latest_data_pod_timestamp", None
            )
            app.storage.user["gallery_title"] = data.get("gallery_title", "")
            app.storage.user["gallery_description"] = data.get(
                "gallery_description", ""
            )
            app.storage.user["dark_mode"] = data.get("dark_mode", None)
            app.storage.user["debug_secret"] = data.get("debug_secret", None)

    stellar_keys = Keypair.from_secret(stellar_secret)
    hvym_keys = Stellar25519KeyPair(stellar_keys)
    hvym_public_key = hvym_keys.public_key()

    if not ipns_folder_exists(hvym_public_key):
        ipns_new_folder(hvym_public_key)
        print(f"Created IPFS folder: {hvym_public_key}")
    else:
        print(f"IPFS folder already exists: {hvym_public_key}")

    app.storage.user["hvym_public_key"] = hvym_public_key

    app.storage.user["img_state"] = app.storage.user.get("img_state", 1)

    # Raw and processed images are session-only (stored in temp dir, not IPFS)
    # Clear on startup since files from previous session no longer exist
    app.storage.user["raw_img_hashes"] = []
    app.storage.user["processed_img_hashes"] = []

    # Protected images persist on IPFS across sessions
    app.storage.user["aposematic_img_hashes"] = app.storage.user.get(
        "aposematic_img_hashes", []
    )
    app.storage.user["enciphered_img_hashes"] = app.storage.user.get(
        "enciphered_img_hashes", []
    )
    app.storage.user["deciphered_img_hashes"] = app.storage.user.get(
        "decrypted_img_hashes", []
    )
    app.storage.user["tmp_files"] = app.storage.user.get("tmp_files", [])
    app.storage.user["recipient_public_key"] = app.storage.user.get(
        "recipient_public_key", None
    )
    app.storage.user["cipher_key"] = app.storage.user.get("cipher_key", None)
    app.storage.user["app_mode"] = app.storage.user.get("app_mode", "image")

    # Initialize IPFS data pod storage
    app.storage.user["latest_data_pod_hash"] = app.storage.user.get(
        "latest_data_pod_hash", None
    )
    app.storage.user["latest_gallery_html_hash"] = app.storage.user.get(
        "latest_gallery_html_hash", None
    )
    app.storage.user["latest_data_pod_timestamp"] = app.storage.user.get(
        "latest_data_pod_timestamp", None
    )

    # Initialize gallery info
    app.storage.user["gallery_title"] = app.storage.user.get("gallery_title", "")
    app.storage.user["gallery_description"] = app.storage.user.get(
        "gallery_description", ""
    )

    img_states = {
        1: "raw",
        2: "processed",
        3: "aposematic",
        4: "enciphered",
    }
    scramble_modes = {i.value: i.name for i in SCRAMBLE_MODE}
    folder_states = {1: "raw", 2: "processed", 3: "aposematic", 4: "enciphered"}

    remove_tmp_files()

    # Initialize or load Debug key for testing encryption/aposematic
    debug_secret = app.storage.user.get("debug_secret", None)
    if debug_secret is None:
        debug_secret = Keypair.random().secret
        app.storage.user["debug_secret"] = debug_secret
    debug_key = Keypair.from_secret(debug_secret)
    debug_keys = Stellar25519KeyPair(debug_key)
    debug_public_key = debug_keys.public_key()
    app.storage.user["debug_public_key"] = debug_public_key
    print(f"Debug Public Key: {debug_public_key}")


def persistent_save_data():
    data_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
    stellar_secret = app.storage.user.get("stellar_secret", Keypair.random().secret)
    app.storage.user["stellar_secret"] = stellar_secret
    artist = app.storage.user.get("artist", "unknown")
    use_watermark = app.storage.user.get("use_watermark", False)
    watermark = app.storage.user.get("watermark", None)
    watermark_size = app.storage.user.get("watermark_size", 0.2)
    watermark_position = app.storage.user.get("watermark_position", 1)
    watermark_padding = app.storage.user.get("watermark_padding", 0.05)
    scramble_mode = app.storage.user.get("scramble_mode", 2)
    op_string = app.storage.user.get("op_string", "-^+")
    use_iptc = app.storage.user.get("use_iptc", False)
    tmp_files = app.storage.user.get("tmp_files", [])
    app.storage.user["tmp_files"] = tmp_files
    public_key = app.storage.user.get("hvym_public_key", None)
    content_folders = app.storage.user.get("content_folders", [])
    subscribers = app.storage.user.get("subscribers", [])
    subscriptions = app.storage.user.get("subscriptions", [])
    app.storage.user["content_folders"] = content_folders
    app_mode = app.storage.user.get("app_mode", "image")
    app_colors = app.storage.user.get(
        "app_colors",
        {
            "primary": PRIMARY_COLOR,
            "secondary": SECONDARY_COLOR,
            "text-color": TEXT_COLOR,
            "bg-color": BG_COLOR,
            "card-bg": CARD_BG,
            "border-color": BORDER_COLOR,
            "dark-primary": DARK_PRIMARY,
            "dark-secondary": DARK_SECONDARY,
            "dark-text": DARK_TEXT,
            "dark-bg": DARK_BG,
            "dark-card": DARK_CARD,
            "dark-border": DARK_BORDER,
        },
    )
    latest_data_pod_hash = app.storage.user.get("latest_data_pod_hash", None)
    latest_gallery_html_hash = app.storage.user.get("latest_gallery_html_hash", None)
    latest_data_pod_timestamp = app.storage.user.get("latest_data_pod_timestamp", None)
    gallery_title = app.storage.user.get("gallery_title", "")
    gallery_description = app.storage.user.get("gallery_description", "")
    dark_mode = app.storage.user.get("dark_mode", None)
    debug_secret = app.storage.user.get("debug_secret", None)
    iptc_data.update_from_storage()
    print(iptc_data.to_dict())
    with open(data_file, "w") as f:
        json.dump(
            {
                "stellar_secret": stellar_secret,
                "debug_secret": debug_secret,
                "artist": artist,
                "use_watermark": use_watermark,
                "watermark": watermark,
                "watermark_size": watermark_size,
                "watermark_position": watermark_position,
                "watermark_padding": watermark_padding,
                "scramble_mode": scramble_mode,
                "op_string": op_string,
                "tmp_files": tmp_files,
                "content_folders": content_folders,
                "subscribers": subscribers,
                "subscriptions": subscriptions,
                "app_mode": app_mode,
                "app_colors": app_colors,
                "dark_mode": dark_mode,
                "use_iptc": use_iptc,
                "iptc_data": iptc_data.to_dict(),
                "latest_data_pod_hash": latest_data_pod_hash,
                "latest_gallery_html_hash": latest_gallery_html_hash,
                "latest_data_pod_timestamp": latest_data_pod_timestamp,
                "gallery_title": gallery_title,
                "gallery_description": gallery_description,
            },
            f,
        )


def apply_theme_colors():
    """Apply theme colors using ui.colors() and CSS variables"""
    print("\n=== apply_theme_colors() CALLED ===")

    colors = app.storage.user.get(
        "app_colors",
        {
            "primary": PRIMARY_COLOR,
            "secondary": SECONDARY_COLOR,
            "text-color": TEXT_COLOR,
            "bg-color": BG_COLOR,
            "card-bg": CARD_BG,
            "border-color": BORDER_COLOR,
            "dark-primary": DARK_PRIMARY,
            "dark-secondary": DARK_SECONDARY,
            "dark-text": DARK_TEXT,
            "dark-bg": DARK_BG,
            "dark-card": DARK_CARD,
            "dark-border": DARK_BORDER,
        },
    )

    print("Colors from storage:")
    print(f"  Light Primary: {colors.get('primary', PRIMARY_COLOR)}")
    print(f"  Dark Primary: {colors.get('dark-primary', DARK_PRIMARY)}")

    # Update CSS variables - simplified with debug logging
    primary_color = colors.get("primary", PRIMARY_COLOR)
    secondary_color = colors.get("secondary", SECONDARY_COLOR)
    text_color = colors.get("text-color", TEXT_COLOR)
    bg_color = colors.get("bg-color", BG_COLOR)
    card_bg = colors.get("card-bg", CARD_BG)
    border_color = colors.get("border-color", BORDER_COLOR)

    dark_primary = colors.get("dark-primary", DARK_PRIMARY)
    dark_secondary = colors.get("dark-secondary", DARK_SECONDARY)
    dark_text = colors.get("dark-text", DARK_TEXT)
    dark_bg = colors.get("dark-bg", DARK_BG)
    dark_card = colors.get("dark-card", DARK_CARD)
    dark_border = colors.get("dark-border", DARK_BORDER)

    # Determine which color palette to use based on dark mode
    global dark_mode_instance

    # Get dark mode value: True, False, or None (auto)
    dark_mode_value = dark_mode_instance.value if dark_mode_instance else None
    is_auto_mode = dark_mode_value is None

    print(f"Dark mode value: {dark_mode_value} (auto: {is_auto_mode})")

    # For auto mode, JavaScript will decide based on system preference
    # For explicit modes, use the set value
    if not is_auto_mode:
        is_dark = dark_mode_value
        print(f"Explicit mode - is_dark: {is_dark}")

    # Inject/update dynamic CSS with active colors
    ui.run_javascript(f"""
        (function() {{
            const root = document.documentElement;
            const body = document.body;

            console.log("=== APPLYING THEME COLORS ===");
            console.log("Auto mode: {is_auto_mode}");

            // Set light mode source colors
            root.style.setProperty('--light-primary-color', '{primary_color}');
            root.style.setProperty('--light-secondary-color', '{secondary_color}');
            root.style.setProperty('--light-text-color', '{text_color}');
            root.style.setProperty('--light-bg-color', '{bg_color}');
            root.style.setProperty('--light-card-bg', '{card_bg}');
            root.style.setProperty('--light-border-color', '{border_color}');

            // Set dark mode source colors
            root.style.setProperty('--dark-primary-color', '{dark_primary}');
            root.style.setProperty('--dark-secondary-color', '{dark_secondary}');
            root.style.setProperty('--dark-text-color', '{dark_text}');
            root.style.setProperty('--dark-bg-color', '{dark_bg}');
            root.style.setProperty('--dark-card-bg', '{dark_card}');
            root.style.setProperty('--dark-border-color', '{dark_border}');

            // Determine which colors to use
            let isDark;
            if ({str(is_auto_mode).lower()}) {{
                // Auto mode - detect from system
                isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                console.log("Auto mode - system dark:", isDark);
            }} else {{
                // Explicit mode - use Python value
                isDark = {str(dark_mode_value).lower() if not is_auto_mode else "false"};
                console.log("Explicit mode - isDark:", isDark);
            }}

            // Choose colors based on determined mode
            const activeColors = isDark ? {{
                primary: '{dark_primary}',
                secondary: '{dark_secondary}',
                text: '{dark_text}',
                bg: '{dark_bg}',
                card: '{dark_card}',
                border: '{dark_border}'
            }} : {{
                primary: '{primary_color}',
                secondary: '{secondary_color}',
                text: '{text_color}',
                bg: '{bg_color}',
                card: '{card_bg}',
                border: '{border_color}'
            }};

            console.log("Active colors:", activeColors);

            // Set active color variables (our custom ones)
            root.style.setProperty('--primary-color', activeColors.primary);
            root.style.setProperty('--secondary-color', activeColors.secondary);
            root.style.setProperty('--text-color', activeColors.text);
            root.style.setProperty('--bg-color', activeColors.bg);
            root.style.setProperty('--card-bg', activeColors.card);
            root.style.setProperty('--border-color', activeColors.border);

            // ALSO update body element directly to force background/text colors
            body.style.backgroundColor = activeColors.bg;
            body.style.color = activeColors.text;

            // Try updating common Quasar CSS variables on body
            body.style.setProperty('--q-primary', activeColors.primary);
            body.style.setProperty('--q-secondary', activeColors.secondary);
            body.style.setProperty('--q-color-primary', activeColors.primary);
            body.style.setProperty('--q-color-secondary', activeColors.secondary);

            // Update on root as well
            root.style.setProperty('--q-primary', activeColors.primary);
            root.style.setProperty('--q-secondary', activeColors.secondary);

            console.log("CSS variables set");

            // Inject/update dynamic CSS rules
            let styleEl = document.getElementById('dynamic-theme-colors');
            if (!styleEl) {{
                styleEl = document.createElement('style');
                styleEl.id = 'dynamic-theme-colors';
                document.head.appendChild(styleEl);
            }}

            // Create CSS rules using the active colors directly (not variables)
            styleEl.textContent = `
                /* Force these colors with highest specificity */
                body, .q-page, .q-drawer, .q-tab-panel {{
                    background-color: ${{activeColors.bg}} !important;
                    color: ${{activeColors.text}} !important;
                }}

                .q-btn:not(.pallete-btn) {{
                    background-color: ${{activeColors.secondary}} !important;
                    color: white !important;
                }}

                .q-tab {{
                    color: ${{activeColors.text}} !important;
                }}

                .q-tab--active, .q-tab--active .q-icon {{
                    color: ${{activeColors.primary}} !important;
                }}

                .q-card:not(.card-no-border) {{
                    background-color: ${{activeColors.card}} !important;
                    color: ${{activeColors.text}} !important;
                    border: 1px solid ${{activeColors.border}} !important;
                }}

                /* Explicitly keep card-no-border transparent */
                .card-no-border {{
                    background-color: transparent !important;
                    border: none !important;
                    box-shadow: none !important;
                }}

                .q-field, .q-input, .q-select, .q-textarea, .q-icon {{
                    color: ${{activeColors.text}} !important;
                }}

                .q-field__control, .q-field__native, .q-field__label {{
                    color: ${{activeColors.text}} !important;
                }}

                /* Gradient backgrounds for header/footer */
                .gradient-background {{
                    background: linear-gradient(90deg, ${{activeColors.primary}}, ${{activeColors.secondary}}) !important;
                    color: white !important;
                }}

                /* Transparent chip background */
                .transparent-chip {{
                    background-color: transparent !important;
                    backdrop-filter: blur(2px);
                }}
            `;

            console.log("Dynamic CSS injected");
            console.log("=== THEME COLORS APPLIED ===");
        }})();
    """)

    print("JavaScript theme update sent")
    print("===========================")


def is_ipfs_running():
    try:
        response = requests.post(f"{ipfs_endpoint}:{port}/api/v0/version", timeout=5)
        return response.status_code == 200 and "Version" in response.json()
    except (requests.exceptions.RequestException, ValueError):
        return False


def url_valid(url):
    try:
        response = requests.get(url, timeout=5)
        return response.status_code == 200
    except (requests.exceptions.RequestException, ValueError):
        return False


def is_pintheon_running():
    """Check if the Pintheon node is running and accessible."""
    try:
        response = requests.get(f"{pintheon_endpoint}:{pintheon_port}/", timeout=5)
        return response.status_code == 200
    except (requests.exceptions.RequestException, ValueError):
        return False


def pintheon_create_directory(name, access_token=None):
    """
    Create a directory on the Pintheon node using the API.

    Args:
        name (str): Name of the directory to create
        access_token (str): Optional access token. If not provided, will try to get from app storage.

    Returns:
        dict: Response with success status and directories list, or None on failure
    """
    if not is_pintheon_running():
        print("Error: Pintheon node is not running or not accessible")
        return None

    if not access_token:
        access_token = app.storage.user.get("access_token")
        if not access_token:
            print("Error: No access token provided for Pintheon API")
            return None

    try:
        url = f"{pintheon_endpoint}:{pintheon_port}/api_create_directory"
        data = {"access_token": access_token, "name": name}
        response = requests.post(url, data=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            print(f"Successfully created directory: {name}")
            return result
        elif response.status_code == 403:
            print("Error: Invalid or unauthorized access token")
            return None
        else:
            error_msg = response.json().get("error", "Unknown error")
            print(f"Error creating directory: {error_msg}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error creating Pintheon directory: {e}")
        return None


def pintheon_upload_file(file_path, directory=None, encrypted=False, access_token=None):
    """
    Upload a file to the Pintheon node using the API.

    Args:
        file_path (str): Local file path to upload
        directory (str): Optional MFS directory path to store file
        encrypted (bool): Whether to encrypt the file
        access_token (str): Optional access token. If not provided, will try to get from app storage.

    Returns:
        dict: File info dict with Name, Type, Hash, Size, or None on failure
    """
    if not is_pintheon_running():
        print("Error: Pintheon node is not running or not accessible")
        return None

    if not access_token:
        access_token = app.storage.user.get("access_token")
        if not access_token:
            print("Error: No access token provided for Pintheon API")
            return None

    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return None

    try:
        url = f"{pintheon_endpoint}:{pintheon_port}/api_upload"

        with open(file_path, "rb") as f:
            files = {"file": (os.path.basename(file_path), f)}
            data = {
                "access_token": access_token,
                "encrypted": "true" if encrypted else "false",
            }
            if directory:
                data["directory"] = directory

            response = requests.post(url, files=files, data=data, timeout=60)

        if response.status_code == 200:
            result = response.json()
            print(f"Successfully uploaded file: {os.path.basename(file_path)}")
            return result
        elif response.status_code == 403:
            print("Error: Invalid or unauthorized access token")
            return None
        else:
            error_msg = response.json().get("error", "Unknown error")
            print(f"Error uploading file: {error_msg}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error uploading to Pintheon: {e}")
        return None


def pintheon_list_directories(access_token=None):
    """
    List directories on the Pintheon node.

    Args:
        access_token (str): Optional access token. If not provided, will try to get from app storage.

    Returns:
        list: List of directory dicts with Name and Path, or None on failure
    """
    if not is_pintheon_running():
        print("Error: Pintheon node is not running or not accessible")
        return None

    if not access_token:
        access_token = app.storage.user.get("access_token")
        if not access_token:
            print("Error: No access token provided for Pintheon API")
            return None

    try:
        url = f"{pintheon_endpoint}:{pintheon_port}/api_list_directories"
        data = {"access_token": access_token}
        response = requests.post(url, data=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            return result.get("directories", [])
        elif response.status_code == 403:
            print("Error: Invalid or unauthorized access token")
            return None
        else:
            error_msg = response.json().get("error", "Unknown error")
            print(f"Error listing directories: {error_msg}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error listing Pintheon directories: {e}")
        return None


def ipns_folder_exists(folder):
    """
    Check if a folder exists in IPFS MFS.

    Args:
        folder (str): Folder path to check

    Returns:
        bool: True if folder exists, False otherwise
    """
    if not is_ipfs_running():
        return False

    try:
        url = f"{ipfs_endpoint}:{port}/api/v0/files/stat"
        params = {"arg": f"/{folder}"}
        response = requests.post(url, params=params, timeout=10)
        return response.status_code == 200
    except (requests.exceptions.RequestException, ValueError):
        return False


def ipns_new_folder(name):
    if not is_ipfs_running():
        print("Error: IPFS daemon is not running or not accessible")
        return False

    try:
        url = f"{ipfs_endpoint}:{port}/api/v0/files/mkdir"
        params = {
            "arg": f"/{name}",
            "parents": True,  # Changed from string 'true' to boolean
            "cid-version": 1,  # Use CIDv1 for better compatibility
        }

        response = requests.post(url, params=params, timeout=30)
        response.raise_for_status()

        # Verify the directory was actually created
        verify_url = f"{ipfs_endpoint}:{port}/api/v0/files/stat"
        verify_params = {"arg": f"/{name}"}
        verify_response = requests.post(verify_url, params=verify_params, timeout=10)

        if verify_response.status_code == 200:
            content_folders = app.storage.user.get("content_folders", [])
            content_folders.append(name)
            app.storage.user["content_folders"] = content_folders
            return True
        return False

    except requests.exceptions.RequestException as e:
        print(f"Error creating IPFS folder: {e}")
        if hasattr(e, "response") and e.response is not None:
            try:
                error_msg = e.response.json()
                print(f"IPFS API error: {error_msg.get('Message', 'Unknown error')}")
            except:
                print(f"Error response: {e.response.text}")
        return False


def ipns_ensure_folder(name):
    """
    Ensure an IPFS MFS folder exists. Creates it if it doesn't exist.

    Args:
        name (str): Name of the folder (without leading/trailing slashes)

    Returns:
        bool: True if folder exists or was created, False otherwise
    """
    if not is_ipfs_running():
        print("IPFS daemon is not running")
        return False

    try:
        # Check if folder exists
        stat_url = f"{ipfs_endpoint}:{port}/api/v0/files/stat"
        stat_params = {"arg": f"/{name}"}
        stat_response = requests.post(stat_url, params=stat_params, timeout=10)

        if stat_response.status_code == 200:
            # Folder exists
            return True
        else:
            # Folder doesn't exist, create it
            print(f"Folder /{name} doesn't exist, creating it...")
            return ipns_new_folder(name)

    except requests.exceptions.RequestException as e:
        # If we get an error, try to create the folder
        print(f"Folder /{name} check failed, attempting to create...")
        return ipns_new_folder(name)


def ipns_clean_folder(name):
    """
    Remove all files from a specific folder in IPFS MFS.

    Args:
        name (str): Name of the folder to clean (without leading/trailing slashes)

    Returns:
        bool: True if successful, False otherwise
    """
    if not is_ipfs_running():
        print("IPFS daemon is not running")
        return False

    # Ensure folder exists first
    if not ipns_ensure_folder(name):
        print(f"Could not ensure folder /{name} exists")
        return False

    try:
        # First, list all files in the folder
        list_url = f"{ipfs_endpoint}:{port}/api/v0/files/ls"
        list_params = {"arg": f"/{name}"}

        list_response = requests.post(list_url, params=list_params, timeout=10)
        list_response.raise_for_status()

        # Remove each file in the folder
        files = list_response.json().get("Entries", [])
        if not files:
            print(f"Folder /{name} is already empty")
            return True

        for file_info in files:
            if file_info["Type"] == 0:  # Regular file
                file_path = f"/{name}/{file_info['Name']}"
                rm_url = f"{ipfs_endpoint}:{port}/api/v0/files/rm"
                rm_params = {"arg": file_path}

                try:
                    rm_response = requests.post(rm_url, params=rm_params, timeout=10)
                    rm_response.raise_for_status()
                    print(f"Removed {file_path}")
                except requests.exceptions.RequestException as e:
                    print(f"Error removing file {file_path}: {e}")
                    continue

        return True

    except requests.exceptions.RequestException as e:
        print(f"Error cleaning IPFS folder: {e}")
        if hasattr(e, "response") and e.response is not None:
            try:
                error_msg = e.response.json()
                print(f"IPFS API error: {error_msg.get('Message', 'Unknown error')}")
            except:
                print(f"Error response: {e.response.text}")
        return False


def ipns_add_to_folder(folder, file_path):
    """
    Add a file to a specific folder in IPFS MFS.

    Args:
        folder (str): Target folder path in MFS (without leading/trailing slashes)
        file_path (str): Local file path to add

    Returns:
        dict: Dictionary containing file info if successful, None if failed
    """
    if not is_ipfs_running():
        print("Error: IPFS daemon is not running or not accessible")
        return None

    try:
        # Normalize folder path (remove leading/trailing slashes)
        folder = folder.strip("/")

        # Ensure folder exists, create if it doesn't
        if not ipns_ensure_folder(folder):
            print(f"Could not ensure folder /{folder} exists")
            return None

        # First add the file to IPFS to get its hash
        with open(file_path, "rb") as f:
            url = f"{ipfs_endpoint}:{port}"
            files = {"file": (os.path.basename(file_path), f)}
            add_response = requests.post(
                f"{url}/api/v0/add",
                params={"no-announce": "true"},
                files=files,
                timeout=30,
            )
            add_response.raise_for_status()
            add_result = add_response.json()
            hash_value = add_result.get("Hash")

            if not hash_value:
                print("Error: Failed to get hash from IPFS add response")
                return None

            # Store the file info with the hash as the key
            file_info = {
                "name": os.path.basename(file_path),
                "path": file_path,
                "ipns_path": f"/{folder}/{hash_value}",
                "extension": os.path.splitext(file_path)[1],
                "render_metadata": False,
            }
            app.storage.user[hash_value] = file_info

            # Now copy the file from the IPFS repo to the MFS folder
            copy_url = f"{ipfs_endpoint}:{port}/api/v0/files/cp"
            copy_params = {
                "arg": [
                    f"/ipfs/{hash_value}",
                    f"/{folder}/{os.path.basename(file_path)}",
                ]
            }
            copy_response = requests.post(copy_url, params=copy_params, timeout=30)
            copy_response.raise_for_status()

            # Get the file stat to return some useful info
            file_path_in_ipfs = f"/{folder}/{os.path.basename(file_path)}"
            stat_params = {"arg": file_path_in_ipfs}
            stat_response = requests.post(
                f"{ipfs_endpoint}:{port}/api/v0/files/stat",
                params=stat_params,
                timeout=10,
            )

            if stat_response.status_code == 200:
                return {
                    "hash": hash_value,
                    "path": file_path_in_ipfs,
                    "size": stat_response.json().get("Size", 0),
                    "type": "file",
                }
            return None

    except requests.exceptions.RequestException as e:
        print(f"Error adding file to IPFS folder: {e}")
        if hasattr(e, "response") and e.response is not None:
            try:
                error_msg = e.response.json()
                print(f"IPFS API error: {error_msg.get('Message', 'Unknown error')}")
            except:
                print(f"Error response: {e.response.text}")
        return None


def ipns_add_gallery_to_folder(name):
    idex = app.storage.user.get("img_state", 1)
    state = img_states[idex]
    hashes = app.storage.user.get(f"{state}_img_hashes", [])

    for hash_value in hashes:
        # Get the file info from storage
        file_info = app.storage.user.get(hash_value)
        if not file_info:
            print(f"No file info found for hash: {hash_value}")
            continue

        file_path = file_info.get("path")
        if not file_path or not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            continue

        # Add the file to the specified MFS folder
        result = ipns_add_to_folder(name, file_path)
        if result:
            print(f"Added {file_path} to MFS folder {name}")
        else:
            print(f"Failed to add {file_path} to MFS folder {name}")


def _local_hash_file(file_path):
    """Compute a SHA-256 content hash for a file. Returns hex string."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _local_store_image_pure(file_path):
    """
    Copy an image to the session editor directory and compute a content hash.
    Pure function — no app.storage.user access. Safe for run.io_bound().

    Returns tuple: (hash_value, file_name, editor_url) or (None, None, None) on error.
    """
    try:
        file_name = os.path.basename(file_path)
        ext = os.path.splitext(file_name)[1]
        content_hash = _local_hash_file(file_path)
        stored_name = f"{content_hash}{ext}"
        dest = os.path.join(EDITOR_STORAGE_DIR, stored_name)
        shutil.copy2(file_path, dest)
        editor_url = f"/editor/{stored_name}"
        return (content_hash, file_name, editor_url)
    except Exception as e:
        print(f"Error storing image locally: {e}")
        return (None, None, None)


def local_store_image(file_path):
    """
    Store an image in the session editor directory and register metadata.
    Returns the content hash, or None on error.
    """
    content_hash, file_name, editor_url = _local_store_image_pure(file_path)
    if content_hash:
        app.storage.user[content_hash] = {
            "name": file_name,
            "path": file_path,
            "editor_url": editor_url,
            "extension": os.path.splitext(file_name)[1],
            "render_metadata": False,
        }
    return content_hash


def local_remove_image(hash_value):
    """Remove an image from the session editor directory."""
    info = app.storage.user.get(hash_value, {})
    editor_url = info.get("editor_url", "")
    if editor_url:
        stored_name = editor_url.split("/")[-1]
        path = os.path.join(EDITOR_STORAGE_DIR, stored_name)
        try:
            if os.path.exists(path):
                os.remove(path)
                print(f"Removed editor image: {stored_name}")
        except Exception as e:
            print(f"Error removing editor image: {e}")


def _ipfs_add_pure(file_path):
    """
    Pure IPFS add operation - no app.storage.user access.
    Safe to use with run.io_bound().

    Returns tuple: (hash_value, file_name, extension) or (None, None, None) on error.
    """
    try:
        with open(file_path, "rb") as f:
            url = f"{ipfs_endpoint}:{port}"
            files = {"file": (os.path.basename(file_path), f)}
            response = requests.post(
                f"{url}/api/v0/add",
                params={"no-announce": "true"},
                files=files,
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            hash_value = result.get("Hash")
            return (hash_value, os.path.basename(file_path), os.path.splitext(file_path)[1])
    except requests.exceptions.RequestException as e:
        print(f"Error uploading to IPFS: {e}")
        return (None, None, None)
    except (ValueError, KeyError) as e:
        print(f"Error processing IPFS response: {e}")
        return (None, None, None)


def ipfs_add(file_path):
    """
    Add file to IPFS and store metadata in app.storage.user.
    NOTE: Cannot be used with run.io_bound() - use _ipfs_add_pure() instead.
    """
    if not is_ipfs_running():
        print("Error: IPFS daemon is not running or not accessible")
        return None

    hash_value, file_name, extension = _ipfs_add_pure(file_path)
    if hash_value:
        app.storage.user[hash_value] = {
            "name": file_name,
            "path": file_path,
            "ipns_path": None,
            "extension": extension,
            "render_metadata": False,
        }
    return hash_value


def _ipfs_load_to_temp_file_pure(hash_value, filename=None):
    """
    Pure IPFS load operation - no app.storage.user access.
    Safe to use with run.io_bound().

    Args:
        hash_value: IPFS hash to load
        filename: Optional filename to use (if None, uses hash_value)

    Returns:
        temp_path on success, None on error
    """
    print(f"Loading IPFS hash: {hash_value}")
    try:
        params = {"arg": hash_value}
        response = requests.post(
            f"{ipfs_webui}:{ipfs_webui_port}/ipfs/{hash_value}",
            params=params,
            timeout=30,
            stream=True,
        )

        response.raise_for_status()

        # Create a temp directory to store the file with its original name
        temp_dir = tempfile.mkdtemp()
        # Use provided filename or fall back to hash
        actual_filename = filename if filename else hash_value
        temp_path = os.path.join(temp_dir, actual_filename)
        print(f"Saving to: {temp_path}")

        # Stream the content to the file
        with open(temp_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # Verify the file was created and has content
        if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
            raise ValueError("Downloaded file is empty")

        return temp_path

    except Exception as e:
        print(f"Error loading from IPFS: {e}")
        if "temp_path" in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)
        if "temp_dir" in locals() and os.path.exists(temp_dir):
            os.rmdir(temp_dir)
        return None


def ipfs_load_to_temp_file(hash_value, original_filename=None):
    """
    Load file from IPFS to temp file and track in app.storage.user.
    NOTE: Cannot be used with run.io_bound() - use _ipfs_load_to_temp_file_pure() instead.
    """
    print(hash_value)
    if not is_ipfs_running():
        print("Error: IPFS daemon is not running or not accessible")
        return None

    # Get filename from storage if not provided
    file_info = app.storage.user.get(hash_value, {})
    print(file_info)
    filename = original_filename or file_info.get("name", hash_value)

    temp_path = _ipfs_load_to_temp_file_pure(hash_value, filename)
    if temp_path:
        app.storage.user["tmp_files"].append(temp_path)

    return temp_path


def ipfs_remove(hash_value):
    if not is_ipfs_running():
        print("Error: IPFS daemon is not running or not accessible")
        return None

    try:
        params = {"arg": hash_value}
        response = requests.post(
            f"{ipfs_endpoint}:{port}/api/v0/pin/rm", params=params, timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error removing from IPFS: {e}")
        return None
    except ValueError as e:
        print(f"Error processing IPFS response: {e}")
        return None
    except Exception as e:
        print(f"Error removing from IPFS: {e}")
        return None


def ipfs_gc():
    try:
        response = requests.post(f"{ipfs_endpoint}:{port}/api/v0/repo/gc")
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError:
                # In case the response isn't JSON
                return {"status": "success", "message": "Garbage collection completed"}
        else:
            error_msg = (
                f"Error in garbage collection: {response.status_code} - {response.text}"
            )
            print(error_msg)
            return {"status": "error", "message": error_msg}
    except requests.exceptions.RequestException as e:
        error_msg = f"Request failed: {str(e)}"
        print(error_msg)
        return {"status": "error", "message": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error in garbage collection: {str(e)}"
        print(error_msg)
        return {"status": "error", "message": error_msg}


def is_imagemagick_available():
    try:
        import wand.version

        magick_version = wand.version.MAGICK_VERSION
        return bool(magick_version and len(magick_version) > 0)
    except (ImportError, AttributeError, Exception):
        return False


def is_image(file_path):
    try:
        with PIL.Image.open(file_path) as img:
            img.verify()  # Verify that it is an image
        return True
    except (IOError, OSError, UnidentifiedImageError):
        return False


def filter_imgs(files):
    return [file for file in files if is_image(file)]


async def choose_img():
    files = await choose_files()
    imgs = filter_imgs(files)
    for img in imgs:
        # Store locally in session temp dir (not IPFS) to protect raw content
        content_hash, file_name, editor_url = _local_store_image_pure(img)
        if not content_hash:
            ui.notify(f"Failed to add {img}", type="warning")
            continue
        print(f"Stored locally: {content_hash}")

        # Initialize metadata structure for raw image
        app.storage.user[content_hash] = {
            "name": os.path.basename(img),
            "path": img,
            "editor_url": editor_url,
            "has_audio": False,
            "image_type": "raw",
            "audio_path": None,
            "audio_format": None,
            "audio_duration": None,
            "audio_size": None,
            "audio_method": None,
        }

        # Ensure the list exists, then append
        if "raw_img_hashes" not in app.storage.user:
            app.storage.user["raw_img_hashes"] = []
        app.storage.user["raw_img_hashes"].append(content_hash)
        ui.notify(f"Added {img}")
        render_gallery()


async def remove_img(hash_value):
    idex = app.storage.user.get("img_state", 1)
    state = img_states[idex]

    # Clean up video token from IPFS if present
    file_info = app.storage.user.get(hash_value, {})
    video_cid = file_info.get("video_token_cid")
    if video_cid and is_ipfs_running():
        try:
            ipfs_remove(video_cid)
            print(f"Unpinned video token CID: {video_cid}")
        except Exception as e:
            print(f"Error unpinning video token CID: {e}")

    if state in ("raw", "processed"):
        # Local session storage — remove from temp dir
        local_remove_image(hash_value)
    else:
        # IPFS-backed (aposematic/enciphered) — unpin and GC
        ipfs_remove(hash_value)
        ipfs_gc()

    try:
        app.storage.user.get(f"{state}_img_hashes", []).remove(hash_value)
    except ValueError:
        pass  # Hash not found, that's okay
    ui.notify(f"Removed {hash_value}")
    render_gallery()


def copy_img(hash_value):
    ui.notify(f"Copied {hash_value}")
    ui.clipboard.write(hash_value)


def remove_tmp_files():
    if "tmp_files" in app.storage.user:
        for file in app.storage.user["tmp_files"]:
            os.remove(file)
        app.storage.user["tmp_files"] = []
    persistent_save_data()


def remove_img_by_name_from_storage(img_name, storage_key):
    if storage_key in app.storage.user:
        for hash_value in app.storage.user[storage_key]:
            img_path = app.storage.user[hash_value]["path"]
            img_filename = app.storage.user[hash_value]["name"]
            if img_name == img_filename:
                app.storage.user[storage_key].remove(hash_value)
                persistent_save_data()
                break


async def choose_watermark(watermark_container):
    files = await app.native.main_window.create_file_dialog(allow_multiple=True)
    file = files[0]
    if is_image(file):
        # Store watermark locally in session temp dir (not IPFS)
        content_hash, file_name, editor_url = _local_store_image_pure(file)
        if not content_hash:
            ui.notify("Failed to store watermark", type="negative")
            return
        app.storage.user["watermark"] = content_hash
        app.storage.user[content_hash] = {
            "name": file_name,
            "path": file,
            "editor_url": editor_url,
        }
        print(f"Watermark stored locally: {content_hash}")
        persistent_save_data()
        ui.notify(f"Chose {file}")
        render_watermark(watermark_container)
    else:
        ui.notify(f"{file} is not an image")


async def choose_files():
    files = await app.native.main_window.create_file_dialog(allow_multiple=True)
    return files


async def choose_file():
    file = await app.native.main_window.create_file_dialog(allow_multiple=False)
    return file


async def delete_all_metadata(hash_value):
    img_path = app.storage.user[hash_value]["path"]
    img_name = app.storage.user[hash_value]["name"]
    try:
        new_img_path = await clear_img_metadata(img_name, img_path)
        # Store locally in session temp dir
        content_hash, file_name, editor_url = _local_store_image_pure(new_img_path)
        if not content_hash:
            ui.notify("Failed to store image", type="negative")
            return
        app.storage.user[content_hash] = {
            "name": file_name,
            "path": new_img_path,
            "editor_url": editor_url,
        }
        idex = app.storage.user.get("img_state", 1)
        state = img_states[idex]

        ui.notify(f"Deleted all metadata from {content_hash}")
        remove_img_by_name_from_storage(img_name, f"{state}_img_hashes")
        processed_hashes = app.storage.user.get(f"{state}_img_hashes", [])

        try:
            index = processed_hashes.index(hash_value)
            processed_hashes[index] = content_hash
        except ValueError:
            processed_hashes.append(content_hash)

        app.storage.user[f"{state}_img_hashes"] = processed_hashes
        # Optionally refresh the gallery to show the updated file
        render_gallery()
    except Exception as e:
        ui.notify(f"Error deleting metadata: {str(e)}", type="negative")


async def edit_exif_info(hash_value):
    img_path = app.storage.user[hash_value]["path"]
    img_name = app.storage.user[hash_value]["name"]
    try:
        metadata = await get_exif_metadata(img_path)
        await edit_metadata_dialog(
            img_path, metadata, process_metadata, img_name, img_path, hash_value
        )

    except Exception as e:
        ui.notify(f"Error loading XMP data: {str(e)}", type="negative")
        print(f"Error in edit_xmp_info: {str(e)}")
        import traceback

        traceback.print_exc()


async def edit_xmp_info(hash_value):
    img_path = app.storage.user[hash_value]["path"]
    img_name = app.storage.user[hash_value]["name"]
    try:
        metadata = await get_xmp_metadata(img_path)
        await edit_metadata_dialog(
            img_path, metadata, process_metadata, img_name, img_path, hash_value
        )

    except Exception as e:
        ui.notify(f"Error loading XMP data: {str(e)}", type="negative")
        print(f"Error in edit_xmp_info: {str(e)}")
        import traceback

        traceback.print_exc()


async def edit_iptc_info(hash_value):
    img_path = app.storage.user[hash_value]["path"]
    img_name = app.storage.user[hash_value]["name"]
    try:
        metadata = await get_iptc_metadata(img_path)
        await edit_metadata_dialog(
            img_path, metadata, process_metadata, img_name, img_path, hash_value
        )

    except Exception as e:
        ui.notify(f"Error loading IPTC data: {str(e)}", type="negative")
        print(f"Error in edit_iptc_info: {str(e)}")
        import traceback

        traceback.print_exc()


async def edit_all_info(hash_value):
    img_path = app.storage.user[hash_value]["path"]
    img_name = app.storage.user[hash_value]["name"]
    try:
        metadata = await get_img_metadata(img_path)
        await edit_metadata_dialog(
            img_path, metadata, process_metadata, img_name, img_path, hash_value
        )

    except Exception as e:
        ui.notify(f"Error loading IPTC data: {str(e)}", type="negative")
        print(f"Error in edit_iptc_info: {str(e)}")
        import traceback

        traceback.print_exc()


async def process_body_text(img_name, img_path, hash_value, txt, data_type):
    # Create a new dictionary with just the fields we want to update
    metadata_changes = {}

    if data_type == "IPTC":
        metadata_changes["IPTC:Caption-Abstract"] = txt
    elif data_type == "XMP":
        metadata_changes["XMP:Description"] = txt

    print(f"Updating {data_type} with changes: {metadata_changes}")

    await process_metadata(img_name, img_path, hash_value, metadata_changes)


async def edit_body_text(hash_value):
    img_path = app.storage.user[hash_value]["path"]
    img_name = app.storage.user[hash_value]["name"]
    await add_body_text_dialog(img_name, img_path, hash_value, process_body_text)


async def update_render_metadata(hash_value, render_metadata):
    """Update the render metadata flag for an image"""
    img_path = app.storage.user[hash_value]["path"]
    img_name = app.storage.user[hash_value]["name"]

    # Store the render metadata flag in the image's metadata
    if "render_metadata" not in app.storage.user[hash_value]:
        app.storage.user[hash_value]["render_metadata"] = True

    app.storage.user[hash_value]["render_metadata"] = render_metadata
    persistent_save_data()

    print(f"Updated render_metadata for {img_name}: {render_metadata}")


async def process_metadata(img_name, img_path, hash_value, metadata):
    try:
        # Process with new IPTC data
        final_path = await new_iptc_img(img_name, img_path, metadata)

        # Store locally in session temp dir
        content_hash, file_name, editor_url = _local_store_image_pure(final_path)
        if not content_hash:
            ui.notify("Failed to store processed image", type="negative")
            return None, None

        # Update the UI and storage
        if content_hash != hash_value:
            app.storage.user[content_hash] = {
                "name": file_name,
                "path": final_path,
                "editor_url": editor_url,
            }
            idex = app.storage.user.get("img_state", 1)
            state = img_states[idex]

            if state == "raw":
                state = "processed"

            remove_img_by_name_from_storage(file_name, f"{state}_img_hashes")
            processed_hashes = app.storage.user.get(f"{state}_img_hashes", [])

            try:
                index = processed_hashes.index(hash_value)
                processed_hashes[index] = content_hash
            except ValueError:
                processed_hashes.append(content_hash)

            app.storage.user[f"{state}_img_hashes"] = processed_hashes

            ui.notify(f"Edited {content_hash}")
            render_gallery()

        return content_hash, final_path

    except Exception as e:
        ui.notify(f"Error processing image: {str(e)}", type="negative")
        raise


async def process_watermarking():
    """
    Process images with watermarking.

    Uses run.io_bound for I/O operations and run.cpu_bound (via new_watermarked_img)
    to prevent blocking the UI event loop ("Connection lost" issue).
    """
    use_watermark = app.storage.user.get("use_watermark", False)
    watermark = app.storage.user.get("watermark", None)

    if not use_watermark or not watermark:
        ui.notify("Watermarking is disabled")
        return

    # Reset the processed image list (assignment ensures NiceGUI detects the change)
    app.storage.user["processed_img_hashes"] = []

    # Get watermark info once before loop (can't access app.storage in thread)
    watermark_hash = app.storage.user["watermark"]
    watermark_info = app.storage.user.get(watermark_hash, {})
    # Load watermark from local session storage (path on disk)
    watermark_path = watermark_info.get("path")
    if not watermark_path or not os.path.exists(watermark_path):
        ui.notify("Watermark file not found", type="negative")
        return

    for hash_value in app.storage.user.get("raw_img_hashes", []):
        img_path = app.storage.user[hash_value]["path"]
        img_name = app.storage.user[hash_value]["name"]
        size = app.storage.user.get("watermark_size", 0.2)
        pos_idx = app.storage.user.get("watermark_position", 1)
        pos = WATERMARK_POSITIONS[pos_idx]
        print(img_name)

        # CPU-bound: watermarking (new_watermarked_img already uses run.cpu_bound internally)
        processed_img_path = await new_watermarked_img(
            img_name, img_path, watermark_path, size, pos
        )
        print("------------------------------------")
        print(processed_img_path)
        print("------------------------------------")

        # Copy audio token chunks from raw image if it had audio
        if app.storage.user[hash_value].get("has_audio", False):
            print(f"Copying audio token from {img_path} into watermarked image")
            # I/O-bound: file operations (reembed_media_if_needed is pure)
            processed_img_path = await run.io_bound(
                reembed_media_if_needed, processed_img_path, img_path
            )

        # Store processed image locally in session temp dir (not IPFS)
        content_hash, file_name, editor_url = await run.io_bound(
            _local_store_image_pure, processed_img_path
        )

        if not content_hash:
            ui.notify("Failed to store processed image", type="negative")
            continue

        # Preserve audio metadata when processing (storage update in main thread)
        app.storage.user[content_hash] = app.storage.user[hash_value].copy()
        app.storage.user[content_hash].update(
            {
                "path": processed_img_path,
                "name": f"processed_{img_name}",
                "editor_url": editor_url,
                "has_audio": app.storage.user[hash_value].get("has_audio", False),
                "audio_path": app.storage.user[hash_value].get(
                    "audio_path"
                ),  # Preserve audio_path
                "audio_format": app.storage.user[hash_value].get("audio_format"),
                "audio_duration": app.storage.user[hash_value].get("audio_duration"),
                "audio_size": app.storage.user[hash_value].get("audio_size"),
                "audio_method": app.storage.user[hash_value].get("audio_method"),
            }
        )

        app.storage.user["processed_img_hashes"].append(content_hash)
        ui.notify(f"Processed {hash_value}")

        # Yield control to event loop for UI updates between images
        await asyncio.sleep(0)

    persistent_save_data()
    render_gallery()


def get_scramble_mode():
    mode = app.storage.user.get("scramble_mode", 2)
    if mode == 1:
        return SCRAMBLE_MODE.BUTTERFLY
    elif mode == 2:
        return SCRAMBLE_MODE.BUTTERFLY
    elif mode == 3:
        return SCRAMBLE_MODE.QR


async def process_aposematic():
    """
    Process images with aposematic encoding.

    Uses run.cpu_bound for CPU-intensive operations and run.io_bound for I/O
    to prevent blocking the UI event loop ("Connection lost" issue).
    """
    # Reset the aposematic image list (assignment ensures NiceGUI detects the change)
    app.storage.user["aposematic_img_hashes"] = []

    processed_hashes = app.storage.user.get("processed_img_hashes", [])

    if not processed_hashes:
        ui.notify("No processed images to convert", type="warning")
        return

    stellar_secret = app.storage.user.get("stellar_secret")
    subscriber_public_key = app.storage.user.get("recipient_public_key")

    if not stellar_secret:
        ui.notify("No stellar secret configured.", type="warning")
        return

    # Fall back to debug key if no recipient explicitly selected
    if not subscriber_public_key:
        subscriber_public_key = app.storage.user.get("debug_public_key")
        if subscriber_public_key:
            print(f"[DEBUG] No recipient selected, using debug key: {subscriber_public_key[:16]}...")
        else:
            ui.notify("No recipient selected. Please select a recipient first.", type="warning")
            return

    stellar_kp = Keypair.from_secret(stellar_secret)
    stellar_keypair = Stellar25519KeyPair(stellar_kp)

    print(
        f"Processing {len(processed_hashes)} images with stellar keypair for subscriber: {subscriber_public_key[:16]}..."
    )

    # Get these values once before the loop (they're used in cpu_bound which can't access app.storage)
    op_string = app.storage.user.get("op_string", "-^+")
    scramble_mode = get_scramble_mode()

    for hash_value in processed_hashes:
        try:
            img_info = app.storage.user.get(hash_value)
            if not img_info:
                print(f"No info found for hash {hash_value}")
                continue

            img_path = img_info.get("path")
            img_name = img_info.get("name")

            if not img_path or not os.path.exists(img_path):
                print(f"Image file not found: {img_path}")
                continue

            print(f"Processing aposematic for: {img_name}")

            # CPU-bound: aposematic encoding is computationally intensive
            aposematic = await run.cpu_bound(
                new_aposematic_img,
                img_path,
                stellar_keypair=stellar_keypair,
                subscriber_public_key=subscriber_public_key,
                op_string=op_string,
                scramble_mode=scramble_mode,
            )
            print(f"Aposematic result: {aposematic}")

            aposematic_img_path = aposematic["img_path"]

            # Copy audio token chunks from processed image if it had audio
            if img_info.get("has_audio", False):
                print(f"Copying audio token from {img_path} into aposematic image")
                # I/O-bound: file operations
                aposematic_img_path = await run.io_bound(
                    reembed_media_if_needed,
                    aposematic_img_path,
                    img_path
                )

            # I/O-bound: network request to IPFS (using pure version)
            ipfs_hash, _, _ = await run.io_bound(_ipfs_add_pure, aposematic_img_path)

            if not ipfs_hash:
                ui.notify(f"Failed to upload to IPFS", type="negative")
                continue

            app.storage.user["aposematic_img_hashes"].append(ipfs_hash)

            # Store info for the new hash (storage update in main thread)
            app.storage.user[ipfs_hash] = {
                "path": aposematic_img_path,
                "name": f"aposematic_{img_name}",
                "original_hash": hash_value,
                "has_audio": img_info.get("has_audio", False),
                "audio_path": img_info.get("audio_path"),  # Preserve audio_path
                "audio_format": img_info.get("audio_format"),
                "audio_duration": img_info.get("audio_duration"),
                "audio_size": img_info.get("audio_size"),
                "audio_method": img_info.get("audio_method"),
            }

            ui.notify(f"Processed {img_name}")

            # Yield control to event loop for UI updates between images
            await asyncio.sleep(0)

        except Exception as e:
            print(f"Error processing {hash_value}: {e}")
            import traceback

            traceback.print_exc()
            ui.notify(f"Error processing image: {e}", type="negative")

    print(
        f"Aposematic processing complete. {len(app.storage.user['aposematic_img_hashes'])} images created."
    )
    persistent_save_data()
    render_gallery()


async def process_enciphering():
    """
    Process images with ImageMagick enciphering.

    Uses run.cpu_bound (via new_enciphered_img) for CPU-intensive operations
    and run.io_bound for I/O to prevent blocking the UI event loop.
    """
    # Reset the enciphered image list (assignment ensures NiceGUI detects the change)
    app.storage.user["enciphered_img_hashes"] = []

    processed_hashes = app.storage.user.get("processed_img_hashes", [])
    cipher_key = app.storage.user.get("cipher_key")

    if not processed_hashes:
        ui.notify("No processed images to encrypt", type="warning")
        return

    if not cipher_key:
        ui.notify("No cipher key set. Please select a recipient first.", type="warning")
        return

    print(
        f"Enciphering {len(processed_hashes)} images with cipher_key: {cipher_key[:16]}..."
    )

    for hash_value in processed_hashes:
        try:
            img_info = app.storage.user.get(hash_value)
            if not img_info:
                print(f"No info found for hash {hash_value}")
                continue

            img_path = img_info.get("path")
            img_name = img_info.get("name")

            if not img_path or not os.path.exists(img_path):
                print(f"Image file not found: {img_path}")
                continue

            print(f"Enciphering: {img_name}")
            # CPU-bound: enciphering (new_enciphered_img already uses run.cpu_bound internally)
            enciphered_img_path = await new_enciphered_img(
                img_name, img_path, cipher_key
            )
            print(f"Enciphered path: {enciphered_img_path}")

            # Re-embed audio if the original image had audio
            audio_path = img_info.get("audio_path")
            if audio_path and os.path.exists(audio_path):
                print(
                    f"Skipping audio re-embedding for enciphered image (preserves encryption)"
                )
                print(f"Enciphered images should not be modified after encryption")
                # CRITICAL: Do NOT re-embed audio for enciphered images
                # Modifying the PNG would destroy the enciphered data

            # I/O-bound: network request to IPFS (using pure version)
            ipfs_hash, _, _ = await run.io_bound(_ipfs_add_pure, enciphered_img_path)

            if not ipfs_hash:
                ui.notify(f"Failed to upload to IPFS", type="negative")
                continue

            app.storage.user["enciphered_img_hashes"].append(ipfs_hash)

            # Store info for the new hash (storage update in main thread)
            app.storage.user[ipfs_hash] = {
                "path": enciphered_img_path,
                "name": f"enciphered_{img_name}",
                "original_hash": hash_value,
                "has_audio": img_info.get("has_audio", False),
                "audio_path": img_info.get("audio_path"),  # Preserve audio_path
                "audio_format": img_info.get("audio_format"),
                "audio_duration": img_info.get("audio_duration"),
                "audio_size": img_info.get("audio_size"),
                "audio_method": img_info.get("audio_method"),
            }

            ui.notify(f"Enciphered {img_name}")

            # Yield control to event loop for UI updates between images
            await asyncio.sleep(0)

        except Exception as e:
            print(f"Error enciphering {hash_value}: {e}")
            import traceback

            traceback.print_exc()
            ui.notify(f"Error enciphering image: {e}", type="negative")

    print(
        f"Enciphering complete. {len(app.storage.user['enciphered_img_hashes'])} images created."
    )
    persistent_save_data()
    render_gallery()


async def process_deciphering():
    """
    Process images with ImageMagick deciphering.

    Uses run.cpu_bound for CPU-intensive decryption and run.io_bound for I/O
    to prevent blocking the UI event loop.
    """
    # Reset the deciphered image list (assignment ensures NiceGUI detects the change)
    app.storage.user["deciphered_img_hashes"] = []

    cipher_key = app.storage.user.get("cipher_key")
    if not cipher_key:
        ui.notify("No cipher key set", type="warning")
        return

    for hash_value in app.storage.user.get("enciphered_img_hashes", []):
        img_path = app.storage.user[hash_value]["path"]

        # CPU-bound: deciphering is computationally intensive
        deciphered_img_path = await run.cpu_bound(
            new_deciphered_img,
            os.path.basename(img_path),  # file_name
            img_path,  # encrypted_img_path
            cipher_key,  # cipher_key
        )

        # I/O-bound: network request to IPFS (using pure version)
        ipfs_hash, _, _ = await run.io_bound(_ipfs_add_pure, deciphered_img_path)

        if not ipfs_hash:
            ui.notify(f"Failed to upload to IPFS", type="negative")
            continue

        app.storage.user["deciphered_img_hashes"].append(ipfs_hash)
        # Store basic info for the deciphered hash
        app.storage.user[ipfs_hash] = {
            "path": deciphered_img_path,
            "name": f"deciphered_{os.path.basename(img_path)}",
            "original_hash": hash_value,
        }
        ui.notify(f"Deciphered {hash_value}")

        # Yield control to event loop for UI updates between images
        await asyncio.sleep(0)

    persistent_save_data()
    render_gallery()


async def process_shared_iptc_metadata():
    """
    Process images with shared IPTC metadata.

    Uses run.io_bound for I/O operations to prevent blocking the UI event loop.
    """
    # Reset the processed image list (assignment ensures NiceGUI detects the change)
    app.storage.user["processed_img_hashes"] = []

    for hash_value in app.storage.user.get("raw_img_hashes", []):
        img_path = app.storage.user[hash_value]["path"]
        img_name = app.storage.user[hash_value]["name"]
        iptc_img_path = await new_iptc_img(img_name, img_path, iptc_data.to_exif_dict())

        # Store processed image locally in session temp dir (not IPFS)
        content_hash, _, editor_url = await run.io_bound(
            _local_store_image_pure, iptc_img_path
        )

        if not content_hash:
            ui.notify("Failed to store processed image", type="negative")
            continue

        # Preserve audio metadata when processing (storage update in main thread)
        app.storage.user[content_hash] = app.storage.user[hash_value].copy()
        app.storage.user[content_hash].update(
            {
                "path": iptc_img_path,
                "name": f"processed_{img_name}",
                "editor_url": editor_url,
                "has_audio": app.storage.user[hash_value].get("has_audio", False),
                "audio_format": app.storage.user[hash_value].get("audio_format"),
                "audio_duration": app.storage.user[hash_value].get("audio_duration"),
                "audio_size": app.storage.user[hash_value].get("audio_size"),
                "audio_method": app.storage.user[hash_value].get("audio_method"),
            }
        )

        app.storage.user["processed_img_hashes"].append(content_hash)
        ui.notify(f"Processed {hash_value}")

        # Yield control to event loop for UI updates between images
        await asyncio.sleep(0)

    persistent_save_data()
    render_gallery()


async def process_add_mardown_file(text):
    # TODO: Implement markdown file addition
    ui.notify("Markdown file addition not yet implemented")


async def process_debug_deploy_gallery():
    try:
        # Validate image state
        idex, state = validate_img_state()
        if state is None:
            ui.notify(f"Invalid image state: {idex}", type="negative")
            return

        # CRITICAL: Debug flow: debug key = creator, app key = recipient
        hvym_public_key = app.storage.user.get("hvym_public_key", "")
        current_public_key = hvym_public_key
        print(
            f"[DEBUG] Debug flow using app public key as recipient: {current_public_key[:16]}..."
        )

        # CRITICAL: Recreate aposematic images with correct shared key
        if state == "aposematic":
            from stellar_sdk.keypair import Keypair
            from hvym_stellar import Stellar25519KeyPair

            # CRITICAL: For debugging, use debug secret key (not app's stellar_secret)
            debug_secret = app.storage.user.get("debug_secret", "")
            print(f"[DEBUG] Debug stellar secret (first 16): {debug_secret[:16]}...")

            # Create the key pair ONCE and reuse it
            stellar_kp = Keypair.from_secret(debug_secret)
            creator_keys = Stellar25519KeyPair(stellar_kp)

            print(f"[DEBUG] creator_keys.public_key(): {creator_keys.public_key()}")
            print(f"[DEBUG] current_public_key (recipient): {current_public_key}")

            print(
                f"[DEBUG] Recreating aposematic images with stellar keypair for subscriber: {current_public_key[:16]}..."
            )

            # Recreate all aposematic images with the correct shared key
            processed_hashes = app.storage.user.get("processed_img_hashes", [])
            if processed_hashes:
                # Fix: Properly clear and manage the aposematic hash list
                app.storage.user["aposematic_img_hashes"] = []

                for hash_value in processed_hashes:
                    try:
                        img_info = app.storage.user.get(hash_value)
                        if not img_info:
                            continue

                        img_path = img_info.get("path")
                        img_name = img_info.get("name")

                        if not img_path or not os.path.exists(img_path):
                            continue

                        print(f"Recreating aposematic for: {img_name}")
                        from aiposematic import new_aposematic_img, SCRAMBLE_MODE

                        # Get op_string before cpu_bound call (can't access storage in process)
                        op_string = app.storage.user.get("op_string", "-^+")

                        # CPU-bound: aposematic encoding
                        aposematic = await run.cpu_bound(
                            new_aposematic_img,
                            img_path,
                            stellar_keypair=creator_keys,
                            subscriber_public_key=current_public_key,
                            op_string=op_string,
                            scramble_mode=SCRAMBLE_MODE.BUTTERFLY,
                        )

                        aposematic_img_path = aposematic["img_path"]

                        # Copy audio token chunks from processed image if it had audio
                        if img_info.get("has_audio", False):
                            print(
                                f"Copying audio token from {img_path} into aposematic image"
                            )
                            # I/O-bound: file operations
                            aposematic_img_path = await run.io_bound(
                                reembed_media_if_needed,
                                aposematic_img_path, img_path
                            )

                        # I/O-bound: IPFS upload (using pure version)
                        ipfs_hash, _, _ = await run.io_bound(_ipfs_add_pure, aposematic_img_path)
                        if not ipfs_hash:
                            print(f"Failed to upload aposematic image to IPFS")
                            continue
                        # Fix: Use helper for proper persistence
                        append_to_storage_list("aposematic_img_hashes", ipfs_hash)

                        # Update info for the new hash
                        app.storage.user[ipfs_hash] = {
                            "path": aposematic_img_path,
                            "name": f"aposematic_{img_name}",
                            "original_hash": hash_value,
                            "has_audio": img_info.get("has_audio", False),
                            "audio_path": img_info.get("audio_path"),
                            "audio_format": img_info.get("audio_format"),
                            "audio_duration": img_info.get("audio_duration"),
                            "audio_size": img_info.get("audio_size"),
                            "audio_method": img_info.get("audio_method"),
                        }

                    except Exception as e:
                        print(f"Error recreating aposematic {hash_value}: {e}")
                        continue

                print(
                    f"Recreated {len(app.storage.user.get('aposematic_img_hashes', []))} aposematic images"
                )

        debug_public_key = app.storage.user.get("debug_public_key", "")
        output_path = await create_ninjs_data_pod_with_encrypted_tokens(
            app, state,
            receiver_public_key=current_public_key,  # App's hvym_public_key
            creator_public_key=debug_public_key      # Debug as creator
        )

        # I/O-bound: clean IPFS folder (pure function, no storage access)
        await run.io_bound(ipns_clean_folder, state)

        # ipns_add_gallery_to_folder accesses storage, so run in main thread
        # but yield control periodically
        ipns_add_gallery_to_folder(state)
        await asyncio.sleep(0)

        if output_path:
            ui.notify(f"Successfully created data pod at: {output_path}")

            # Process data pod locally to decrypt images before rendering
            # CRITICAL: Debug flow: app acts as subscriber to decrypt
            subscriber_secret = app.storage.user.get("stellar_secret", "")
            print(
                f"[DEBUG] Debug flow using app secret as subscriber: {subscriber_secret[:16]}..."
            )

            if not subscriber_secret:
                ui.notify(
                    "No debug secret found - cannot decrypt images", type="warning"
                )
                return

            ui.notify("Processing data pod locally to decrypt images...", type="info")
            processed_data_pod = await process_data_pod_locally(
                output_path, subscriber_secret, app,
                download_ipfs_image=download_ipfs_image,
                new_deciphered_img=new_deciphered_img,
                recover_aposematic_img=recover_aposematic_img,
                image_to_base64_uri=image_to_base64_uri,
                ipfs_add=ipfs_add,
                _ipfs_add_pure=_ipfs_add_pure,
                _ipfs_load_to_temp_file_pure=_ipfs_load_to_temp_file_pure,
                ipfs_webui=ipfs_webui,
                ipfs_webui_port=ipfs_webui_port,
                video_temp_dir=EDITOR_STORAGE_DIR,
            )

            if processed_data_pod:
                ui.notify(
                    "Successfully processed and decrypted data pod", type="positive"
                )
                data_pod = processed_data_pod
            else:
                ui.notify("Failed to process data pod, using original", type="warning")
                # Load the original JSON data pod as fallback
                with open(output_path, "r", encoding="utf-8") as f:
                    data_pod = json.load(f)

            # Render gallery HTML using helper function
            print(f"[DEBUG] data_pod keys: {data_pod.keys() if data_pod else 'None'}")
            print(f"[DEBUG] data_pod['items'] count: {len(data_pod.get('items', [])) if data_pod else 0}")
            if data_pod and data_pod.get('items'):
                for i, item in enumerate(data_pod['items']):
                    print(f"[DEBUG] Item {i}: title={item.get('title')}, hasAudio={item.get('hasAudio')}")
            else:
                print("[DEBUG] WARNING: No items in data_pod!")
            html_content = render_gallery_html(data_pod)

            # Save to IPFS using helper function
            html_temp_path, html_hash = save_gallery_to_ipfs(html_content)
            if html_hash:
                ui.notify(f"Gallery HTML saved to IPFS: {html_hash}", type="positive")
            else:
                ui.notify("Failed to add HTML to IPFS", type="warning")

            # Store content for user to view when they switch to BROWSER tab
            global pending_browser_html
            pending_browser_html = html_content
            print(
                f"Stored pending HTML content for browser view, length: {len(html_content)}"
            )
            ui.notify("Gallery ready - switch to BROWSER tab to view", type="positive")

            # Persist storage changes
            persistent_save_data()
        else:
            ui.notify("No valid images found to create data pods", type="warning")

    except Exception as e:
        ui.notify(f"Error processing gallery: {str(e)}", type="negative")
        print(f"Error in process_debug_deploy_gallery: {str(e)}")
        import traceback

        traceback.print_exc()


async def process_pintheon_deploy_gallery():
    """
    Deploy gallery data pod and all associated assets to a local Pintheon node.
    This performs local IPFS operations AND uploads to Pintheon.

    Now unified with debug flow:
    - Uses create_ninjs_data_pod_with_encrypted_tokens() for consistent data pod structure
    - Processes data pod locally for decrypted preview
    - Uses helper functions for template rendering
    """
    try:
        # Check if Pintheon is running
        if not is_pintheon_running():
            ui.notify("Pintheon node is not running", type="negative")
            return

        # Check for access token
        access_token = app.storage.user.get("access_token")
        if not access_token:
            ui.notify("No access token configured for Pintheon", type="negative")
            return

        # Validate image state
        idex, state = validate_img_state()
        if state is None:
            ui.notify(f"Invalid image state: {idex}", type="negative")
            return

        ui.notify(f"Starting Pintheon deployment for {state} gallery...", type="info")

        # Get the recipient public key (uses selected subscriber or debug key)
        recipient_public_key = app.storage.user.get("recipient_public_key", "")
        if not recipient_public_key:
            # Fall back to debug key if no recipient selected
            recipient_public_key = app.storage.user.get("debug_public_key", "")
            print(f"[DEBUG] Pintheon: No recipient selected, using debug key for encryption")

        print(f"[DEBUG] Pintheon flow using recipient key: {recipient_public_key[:16]}...")

        # Create the NINJS data pod with encryption support (unified with debug flow)
        output_path = await create_ninjs_data_pod_with_encrypted_tokens(
            app, state, recipient_public_key
        )

        # I/O-bound: clean IPFS folder (pure function)
        await run.io_bound(ipns_clean_folder, state)

        # ipns_add_gallery_to_folder accesses storage, run in main thread
        ipns_add_gallery_to_folder(state)
        await asyncio.sleep(0)

        if not output_path:
            ui.notify("No valid images found to create data pods", type="warning")
            return

        ui.notify(f"Data pod created, uploading to Pintheon...", type="info")

        # Create directory on Pintheon for this gallery state
        directory_name = f"gallery_{state}"
        # I/O-bound: create directory (pass access_token to make it pure)
        dir_result = await run.io_bound(
            pintheon_create_directory, directory_name, access_token
        )
        if not dir_result:
            ui.notify(
                f"Failed to create directory on Pintheon: {directory_name}",
                type="warning",
            )
            # Continue anyway - directory might already exist

        # Upload all gallery images to Pintheon
        # Extract file info from storage BEFORE the loop (can't access in thread)
        hashes = app.storage.user.get(f"{state}_img_hashes", [])
        files_to_upload = []
        for hash_value in hashes:
            file_info = app.storage.user.get(hash_value)
            if file_info:
                file_path = file_info.get("path")
                file_name = file_info.get("name")
                if file_path and os.path.exists(file_path):
                    files_to_upload.append((hash_value, file_path, file_name))

        uploaded_files = []
        failed_uploads = []

        for hash_value, file_path, file_name in files_to_upload:
            # I/O-bound: upload file (pass access_token to make it pure)
            result = await run.io_bound(
                pintheon_upload_file,
                file_path, directory_name, False, access_token
            )
            if result:
                uploaded_files.append(result)
                print(
                    f"Uploaded to Pintheon: {file_name} -> {result.get('Hash')}"
                )
            else:
                failed_uploads.append(hash_value)
                print(f"Failed to upload: {file_name}")

            # Yield control for UI updates
            await asyncio.sleep(0)

        # I/O-bound: upload the data pod JSON file to Pintheon
        data_pod_result = await run.io_bound(
            pintheon_upload_file,
            output_path, directory_name, False, access_token
        )
        if data_pod_result:
            print(f"Uploaded data pod to Pintheon: {data_pod_result.get('Hash')}")
            app.storage.user["pintheon_data_pod_hash"] = data_pod_result.get("Hash")
            print(f"[DEBUG] Pintheon: Deployed encrypted data pod to production: {data_pod_result.get('Hash')}")
            ui.notify(f"Successfully deployed data pod to Pintheon: {data_pod_result.get('Hash')}", type="positive")
        else:
            ui.notify("Failed to upload data pod to Pintheon", type="warning")

        # Report results
        if failed_uploads:
            ui.notify(
                f"Pintheon deployment complete with {len(failed_uploads)} failures. {len(uploaded_files)} files uploaded.",
                type="warning",
            )
        else:
            ui.notify(
                f"Successfully deployed {len(uploaded_files)} files to Pintheon!",
                type="positive",
            )

        ui.notify("Gallery ready - switch to BROWSER tab to view", type="positive")
        persistent_save_data()

    except Exception as e:
        ui.notify(f"Error deploying to Pintheon: {str(e)}", type="negative")
        print(f"Error in process_pintheon_deploy_gallery: {str(e)}")
        import traceback

        traceback.print_exc()


def add_subscriber(name, public_key):
    subscribers = app.storage.user.get("subscribers", [])
    subscribers.append({"name": name, "public_key": public_key})
    app.storage.user["subscribers"] = subscribers
    persistent_save_data()


async def remove_subscriber(name):
    subscribers = app.storage.user.get("subscribers", [])
    subscribers = [s for s in subscribers if s["name"] != name]
    app.storage.user["subscribers"] = subscribers
    persistent_save_data()


async def get_subscribers():
    return app.storage.user.get("subscribers", [])


async def add_subscription(name, url, ipns_hash):
    """
    Add a subscription to a Pintheon node channel.

    Args:
        name: User-created name for the subscription
        url: Pintheon node URL (e.g., 'https://some-pintheon.com')
        ipns_hash: IPNS hash for the content channel
    """
    subscriptions = app.storage.user.get("subscriptions", [])
    # Check if subscription with this name already exists
    for sub in subscriptions:
        if sub["name"] == name:
            ui.notify(f'Subscription "{name}" already exists', type="warning")
            return
    subscriptions.append({"name": name, "url": url, "ipns_hash": ipns_hash})
    app.storage.user["subscriptions"] = subscriptions
    persistent_save_data()
    ui.notify(f"Added subscription: {name}")


async def remove_subscription(name):
    """Remove a subscription by name."""
    subscriptions = app.storage.user.get("subscriptions", [])
    subscriptions = [s for s in subscriptions if s["name"] != name]
    app.storage.user["subscriptions"] = subscriptions
    persistent_save_data()
    ui.notify(f"Removed subscription: {name}")


async def get_subscriptions():
    """Get all subscriptions."""
    return app.storage.user.get("subscriptions", [])


async def fetch_subscription_content(subscription_name):
    """
    Fetch content from a subscription's IPNS address and copy to local IPFS.

    Args:
        subscription_name: Name of the subscription to fetch

    Returns:
        List of fetched file info dicts, or None on failure
    """
    subscriptions = app.storage.user.get("subscriptions", [])
    subscription = None
    for sub in subscriptions:
        if sub["name"] == subscription_name:
            subscription = sub
            break

    if not subscription:
        ui.notify(f'Subscription "{subscription_name}" not found', type="negative")
        return None

    url = subscription.get("url")
    ipns_hash = subscription.get("ipns_hash")

    if not url or not ipns_hash:
        ui.notify("Invalid subscription data", type="negative")
        return None

    try:
        # Resolve IPNS to get the current CID via the Pintheon node's gateway
        # The Pintheon node acts as an IPFS gateway, serving content at /ipns/<hash>
        gateway_url = f"{url.rstrip('/')}/ipns/{ipns_hash}"

        ui.notify(f"Fetching content from {subscription_name}...", type="info")
        print(f"Fetching IPNS content from: {gateway_url}")

        # First, try to resolve the IPNS to get directory listing
        # We'll fetch the content and copy files to local MFS
        response = requests.get(gateway_url, timeout=60)

        if response.status_code != 200:
            ui.notify(
                f"Failed to fetch content: HTTP {response.status_code}", type="negative"
            )
            return None

        # Ensure local MFS directory exists for this subscription
        mfs_folder = f"subscriptions/{subscription_name}"
        ipns_ensure_folder(mfs_folder)

        # The response should be the directory content
        # For now, we'll save the raw content and handle it
        # In a full implementation, we'd parse the directory listing

        content_type = response.headers.get("Content-Type", "")
        print(f"Content-Type: {content_type}")

        # If it's a UnixFS directory, we need to handle it differently
        # For now, let's store info about what we fetched
        fetched_info = {
            "subscription": subscription_name,
            "ipns_hash": ipns_hash,
            "gateway_url": gateway_url,
            "content_type": content_type,
            "size": len(response.content),
        }

        # Store the fetched content info
        fetched_subscriptions = app.storage.user.get("fetched_subscriptions", {})
        fetched_subscriptions[subscription_name] = fetched_info
        app.storage.user["fetched_subscriptions"] = fetched_subscriptions

        ui.notify(f"Fetched content from {subscription_name}", type="positive")
        return fetched_info

    except requests.exceptions.RequestException as e:
        ui.notify(f"Error fetching subscription: {str(e)}", type="negative")
        print(f"Error fetching subscription content: {e}")
        return None


async def fetch_subscription_channels(subscription_name):
    """
    Fetch available channels (data pods) from a subscription.

    Args:
        subscription_name: Name of the subscription

    Returns:
        List of channel info dicts, or empty list on failure
    """
    subscriptions = app.storage.user.get("subscriptions", [])
    subscription = None
    for sub in subscriptions:
        if sub["name"] == subscription_name:
            subscription = sub
            break

    if not subscription:
        return []

    url = subscription.get("url")
    ipns_hash = subscription.get("ipns_hash")

    if not url or not ipns_hash:
        return []

    try:
        # Fetch the directory listing from the IPNS address
        gateway_url = f"{url.rstrip('/')}/ipns/{ipns_hash}"
        print(f"Fetching channels from: {gateway_url}")

        response = requests.get(gateway_url, timeout=60)

        if response.status_code != 200:
            print(f"Failed to fetch channels: HTTP {response.status_code}")
            return []

        content_type = response.headers.get("Content-Type", "")

        # If it's JSON, try to parse as a data pod or list of data pods
        if "json" in content_type.lower():
            data = response.json()
            # If it's a single data pod (NINJS format)
            if isinstance(data, dict) and "items" in data:
                return [
                    {
                        "name": data.get("uri", "Channel"),
                        "description": f"{len(data.get('items', []))} items",
                        "data": data,
                    }
                ]
            # If it's a list of data pods
            elif isinstance(data, list):
                return [
                    {
                        "name": item.get("uri", f"Channel {i}"),
                        "description": "",
                        "data": item,
                    }
                    for i, item in enumerate(data)
                ]

        # If it's HTML (directory listing), try to parse links
        if "html" in content_type.lower():
            # For now, return a placeholder indicating we need to parse the directory
            # In a full implementation, we'd parse the HTML for links to data pods
            return [
                {
                    "name": subscription_name,
                    "description": "Directory content available",
                    "url": gateway_url,
                }
            ]

        return []

    except requests.exceptions.RequestException as e:
        print(f"Error fetching channels: {e}")
        return []
    except json.JSONDecodeError as e:
        print(f"Error parsing channel data: {e}")
        return []


def download_ipfs_image(url):
    """Download an image from IPFS and return the file path."""
    try:
        # Extract IPFS hash from URL
        if "/ipfs/" in url:
            ipfs_hash = url.split("/ipfs/")[-1]
        else:
            ipfs_hash = url

        print(f"[DEBUG] IPFS hash extracted: {ipfs_hash}")

        # Try IPFS API first (preserves metadata)
        try:
            # Use IPFS HTTP API with ?format=raw to get raw file
            api_url = f"http://localhost:5001/api/v0/cat?arg={ipfs_hash}"
            print(f"[DEBUG] Trying IPFS API: {api_url}")

            response = requests.post(api_url, timeout=30)
            response.raise_for_status()

            # Create temp file with appropriate extension
            ext = ".png"  # Assume PNG for aposematic images
            temp_path = os.path.join(
                tempfile.gettempdir(), f"ipfs_download_{hash(url)}{ext}"
            )

            with open(temp_path, "wb") as f:
                f.write(response.content)

            print(
                f"[DEBUG] Downloaded via IPFS API, size: {len(response.content)} bytes"
            )
            return temp_path

        except Exception as api_error:
            print(f"[DEBUG] IPFS API failed: {api_error}")

            # Fallback to HTTP gateway (might strip metadata)
            print(f"[DEBUG] Falling back to HTTP gateway: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Create temp file with appropriate extension
            content_type = response.headers.get("content-type", "image/jpeg")
            ext = (
                ".jpg"
                if "jpeg" in content_type
                else ".png"
                if "png" in content_type
                else ".jpg"
            )
            temp_path = os.path.join(
                tempfile.gettempdir(), f"ipfs_download_{hash(url)}{ext}"
            )

            with open(temp_path, "wb") as f:
                f.write(response.content)

            print(
                f"[DEBUG] Downloaded via HTTP gateway, size: {len(response.content)} bytes"
            )
            return temp_path

    except Exception as e:
        print(f"Error downloading image from {url}: {e}")
        return None


def image_to_base64_uri(file_path):
    """Convert an image file to a base64 data URI."""
    try:
        import mimetypes

        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "image/jpeg"

        with open(file_path, "rb") as f:
            image_data = f.read()

        b64_data = base64.b64encode(image_data).decode("utf-8")
        return f"data:{mime_type};base64,{b64_data}"
    except Exception as e:
        print(f"Error converting image to base64: {e}")
        return None


def get_scramble_mode_from_value(mode_value):
    """Convert scramble mode integer to SCRAMBLE_MODE enum."""
    if mode_value == 1:
        return SCRAMBLE_MODE.BUTTERFLY
    elif mode_value == 2:
        return SCRAMBLE_MODE.BUTTERFLY
    else:
        return SCRAMBLE_MODE.QR


async def decode_protected_images(data_pod, stellar_secret):
    """
    Decode aposematic or encrypted images and update data_pod with base64 URIs.

    Args:
        data_pod: The NINJ data pod dictionary
        stellar_secret: The subscriber's stellar secret key

    Returns:
        Modified data_pod with base64 image URIs, or original if decoding fails
    """
    content_type = data_pod.get("content_type", "original")

    if content_type == "original":
        return data_pod

    # Get creator's public key for ECDH shared key derivation
    creator_public_key = data_pod.get("creator_public_key")
    if not creator_public_key:
        print("No creator_public_key in data pod, cannot decode")
        return data_pod

    # Optional: verify subscriber is authorized (their public key matches recipient_public_key)
    recipient_public_key = data_pod.get("recipient_public_key")
    if recipient_public_key:
        try:
            subscriber_keys = Keypair.from_secret(stellar_secret)
            subscriber_hvym = Stellar25519KeyPair(subscriber_keys)
            subscriber_public = subscriber_hvym.public_key()
            if subscriber_public != recipient_public_key:
                print(
                    f"Warning: Subscriber key mismatch. This content may not have been shared with you."
                )
                # Continue anyway - decryption will fail if keys don't match
        except Exception as e:
            print(f"Could not verify subscriber authorization: {e}")

    # Generate keys for decryption
    try:
        stellar_keys = Keypair.from_secret(stellar_secret)
        hvym_keys = Stellar25519KeyPair(stellar_keys)
    except Exception as e:
        print(f"Error creating stellar keypair: {e}")
        return data_pod

    # For encrypted content type, derive cipher_key manually (non-aposematic path)
    cipher_key = None
    if content_type == "encrypted":
        try:
            shared_key = StellarSharedKey(hvym_keys, creator_public_key)
            cipher_key = shared_key.shared_secret_as_hex()
        except Exception as e:
            print(f"Error generating shared key for encrypted content: {e}")
            return data_pod

    # Get aposematic parameters if needed
    op_string = data_pod.get("op_string", "-^+")
    # Process each item
    for item in data_pod.get("items", []):
        renditions = item.get("renditions", {})
        original = renditions.get("original", {})
        href = original.get("href")

        if not href:
            continue

        try:
            # Download the image
            temp_path = download_ipfs_image(href)
            if not temp_path:
                continue

            # Decode based on content type
            if content_type == "encrypted":
                from img_edit import new_deciphered_img

                decoded_path = new_deciphered_img(
                    os.path.basename(temp_path), temp_path, cipher_key
                )
            elif content_type == "aposematic":
                decoded_path = recover_aposematic_img(
                    temp_path,
                    stellar_keypair=hvym_keys,
                    artist_public_key=creator_public_key,
                    op_string=op_string,
                )
            else:
                continue

            if decoded_path and os.path.exists(decoded_path):
                # Convert to base64 URI
                base64_uri = image_to_base64_uri(decoded_path)
                if base64_uri:
                    original["href"] = base64_uri
                    original["decoded"] = True

                # Clean up temp files
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                if decoded_path != temp_path and os.path.exists(decoded_path):
                    os.unlink(decoded_path)

        except Exception as e:
            print(f"Error decoding image {href}: {e}")
            import traceback

            traceback.print_exc()
            continue

    return data_pod


async def select_channel(subscription_name, channel_info):
    """
    Handle selection of a channel (data pod) from a subscription.

    Args:
        subscription_name: Name of the subscription
        channel_info: Channel info dict with name, description, and data/url
    """
    global pending_browser_html

    print(f"Selected channel: {channel_info.get('name')} from {subscription_name}")

    # If we have the data pod directly, render it
    if "data" in channel_info:
        data_pod = channel_info["data"]

        # Decode protected images if necessary (aposematic/encrypted)
        content_type = data_pod.get("content_type", "original")
        if content_type in ("aposematic", "encrypted"):
            stellar_secret = app.storage.user.get("stellar_secret")
            if stellar_secret:
                ui.notify(f"Decoding {content_type} content...", type="info")
                data_pod = await decode_protected_images(data_pod, stellar_secret)
            else:
                ui.notify("Cannot decode: no stellar secret configured", type="warning")

        # Set up Jinja2 environment
        template_dir = os.path.join(os.path.dirname(__file__), "templates")
        jinja_env = Environment(loader=FileSystemLoader(template_dir))
        template = jinja_env.get_template("gallery.html")

        # Get current color scheme
        app_colors = app.storage.user.get("app_colors", {})
        is_dark_mode = app.storage.user.get("dark_mode", None)

        if is_dark_mode:
            colors = {
                "primary": app_colors.get("dark-primary", DARK_PRIMARY),
                "secondary": app_colors.get("dark-secondary", DARK_SECONDARY),
                "text": app_colors.get("dark-text", DARK_TEXT),
                "bg": app_colors.get("dark-bg", DARK_BG),
                "card": app_colors.get("dark-card", DARK_CARD),
                "border": app_colors.get("dark-border", DARK_BORDER),
            }
        else:
            colors = {
                "primary": app_colors.get("primary", PRIMARY_COLOR),
                "secondary": app_colors.get("secondary", SECONDARY_COLOR),
                "text": app_colors.get("text-color", TEXT_COLOR),
                "bg": app_colors.get("bg-color", BG_COLOR),
                "card": app_colors.get("card-bg", CARD_BG),
                "border": app_colors.get("border-color", BORDER_COLOR),
            }

        # Get subscription info for gateway URL
        subscriptions = app.storage.user.get("subscriptions", [])
        subscription = next(
            (s for s in subscriptions if s["name"] == subscription_name), None
        )
        gateway = (
            subscription.get("url", ipfs_webui + ":" + ipfs_webui_port)
            if subscription
            else ipfs_webui + ":" + ipfs_webui_port
        )

        # Render the template
        template_context = {
            "data_pod": data_pod,
            "ipfs_gateway": gateway,
            "ipfs_webui": gateway.split(":")[0] if ":" in gateway else gateway,
            "ipfs_webui_port": gateway.split(":")[1] if ":" in gateway else "443",
            "gallery_title": channel_info.get("name", ""),
            "gallery_description": channel_info.get("description", ""),
            "colors": colors,
            "is_dark_mode": is_dark_mode,
        }
        html_content = template.render(**template_context)

        # Store for browser view
        pending_browser_html = html_content
        app.storage.user["current_channel"] = {
            "subscription": subscription_name,
            "channel": channel_info.get("name"),
        }

        ui.notify(
            f"Channel loaded: {channel_info.get('name')}. Switch to BROWSER tab to view.",
            type="positive",
        )

    elif "url" in channel_info:
        # If we have a URL, fetch and display
        ui.notify(f"Fetching content from {channel_info.get('name')}...", type="info")
        # Could implement fetching and rendering here

    else:
        ui.notify("No content available for this channel", type="warning")


async def load_iptc_template():
    try:
        file_path = await choose_file()
        if file_path:
            with open(file_path[0], "r") as f:
                iptc_data = json.load(f)
            app.storage.user["iptc_data"] = iptc_data
            persistent_save_data()
            ui.notify("IPTC Template loaded successfully")
    except Exception as e:
        ui.notify(f"Error loading IPTC template: {str(e)}", type="negative")


def save_iptc_template():
    try:
        ui.download.content(json.dumps(iptc_data.to_dict()), "iptc_template.json")
    except Exception as e:
        ui.notify(f"Error saving IPTC template: {str(e)}", type="negative")


def render_state(hashes):
    idex = app.storage.user.get("img_state", 1)
    state = img_states[idex]
    if file_container and state_container:
        state_container.clear()
        with state_container:
            ui.chip(f"{state} ({len(hashes)})", icon="view_array")


def render_gallery(folder=None):
    # tabs.set_value('IMAGES')
    idex = app.storage.user.get("img_state", 1)
    state = img_states[idex]
    hashes = app.storage.user.get(f"{state}_img_hashes", [])
    print(f"[DEBUG render_gallery] state={state}, hashes={hashes}")

    render_state(hashes)

    if file_container:
        file_container.clear()
        with file_container:
            # ui.chip(f'{state} ({len(hashes)})', icon='view_array')

            for hash_value in hashes:
                # Create a card to contain the image and FAB
                with ui.card().classes(
                    "relative overflow-visible w-full max-w-2xl mx-auto"
                ):
                    file_info = app.storage.user.get(hash_value, {})
                    print(f"[DEBUG render_gallery] hash={hash_value}, file_info={file_info}")
                    print(f"[DEBUG render_gallery] has_audio={file_info.get('has_audio', False)}")

                    # Use local editor URL for raw/processed, IPFS for protected images
                    editor_url = file_info.get("editor_url")
                    if editor_url and state in ("raw", "processed"):
                        img_url = editor_url
                    elif folder:
                        img_url = (
                            f"{ipfs_webui}:{ipfs_webui_port}/ipfs/{folder}/{hash_value}"
                        )
                    else:
                        img_url = f"{ipfs_webui}:{ipfs_webui_port}/ipfs/{hash_value}"

                    if not folder:
                        # Show media indicator chips, otherwise show filename
                        has_audio_chip = file_info.get("has_audio", False)
                        has_video_chip = file_info.get("has_video", False)
                        if has_audio_chip or has_video_chip:
                            with ui.row().classes("absolute top-2 left-2 z-10 gap-1"):
                                if has_audio_chip:
                                    ui.chip(
                                        "Audio",
                                        icon="music_note",
                                        color="blue",
                                    ).props("square")
                                if has_video_chip:
                                    ui.chip(
                                        "Video",
                                        icon="videocam",
                                        color="purple",
                                    ).props("square")
                        else:
                            ui.chip(
                                file_info.get("name", "Unknown"),
                                icon="image",
                                color="white",
                            ).props("square").classes(
                                "absolute top-2 left-2 z-10 transparent-chip"
                            )

                    img_container = ui.image(img_url).classes("w-full")

                    # FAB container positioned absolutely over image
                    with ui.row().classes("absolute top-2 right-2 z-10"):
                        with ui.fab("edit", direction="left").classes(
                            "q-secondary-color"
                        ):
                            if is_ipfs_running():
                                ui.fab_action(
                                    "copy_all",
                                    on_click=lambda h=hash_value: copy_img(h),
                                ).tooltip("Copy image")
                            # Audio/Video embedding actions (mutually exclusive)
                            has_audio_flag = file_info.get("has_audio", False)
                            has_video_flag = file_info.get("has_video", False)
                            if has_audio_flag:
                                ui.fab_action(
                                    "music_note",
                                    on_click=lambda h=hash_value: play_audio_from_image(
                                        h
                                    ),
                                ).tooltip("Play Audio")
                                ui.fab_action(
                                    "music_off",
                                    on_click=lambda h=hash_value: remove_audio_from_image(
                                        h
                                    ),
                                    color="negative",
                                ).tooltip("Remove Audio")
                            elif has_video_flag:
                                ui.fab_action(
                                    "videocam",
                                    on_click=lambda h=hash_value: play_video_from_image(
                                        h
                                    ),
                                ).tooltip("Play Video")
                                ui.fab_action(
                                    "videocam_off",
                                    on_click=lambda h=hash_value: remove_video_from_image(
                                        h
                                    ),
                                    color="negative",
                                ).tooltip("Remove Video")
                            else:
                                # No media embedded — show both "Add" options
                                ui.fab_action(
                                    "music_note",
                                    on_click=lambda h=hash_value: edit_audio_info_main(
                                        h
                                    ),
                                ).tooltip("Add Audio")
                                ui.fab_action(
                                    "videocam",
                                    on_click=lambda h=hash_value: edit_video_info_main(
                                        h
                                    ),
                                ).tooltip("Add Video")
                            ui.fab_action(
                                "delete",
                                on_click=lambda h=hash_value: remove_img(h),
                                color="negative",
                            ).tooltip("Delete image")
                        with ui.fab("data_object", direction="left").classes(
                            "q-secondary-color"
                        ):
                            if is_ipfs_running():
                                ui.fab_action(
                                    "edit",
                                    label="ALL",
                                    on_click=lambda h=hash_value: edit_all_info(h),
                                ).tooltip("Edit all metadata")
                                ui.fab_action(
                                    "edit",
                                    label="IPTC",
                                    on_click=lambda h=hash_value: edit_iptc_info(h),
                                ).tooltip("Edit IPTC metadata")
                                ui.fab_action(
                                    "edit",
                                    label="XMP",
                                    on_click=lambda h=hash_value: edit_xmp_info(h),
                                ).tooltip("Edit XMP metadata")
                                ui.fab_action(
                                    "edit",
                                    label="EXIF",
                                    on_click=lambda h=hash_value: edit_exif_info(h),
                                ).tooltip("Edit EXIF metadata")
                                ui.fab_action(
                                    "delete",
                                    label="ALL",
                                    on_click=lambda h=hash_value: remove_img(h),
                                    color="negative",
                                ).tooltip("Delete metadata")

                    with ui.row().classes("absolute bottom-2 right-2 z-10"):

                        def handle_checkbox_change(val):
                            print(f"Checkbox changed for {hash_value}: {val}")
                            asyncio.create_task(update_render_metadata(hash_value, val))

                        checkbox = ui.checkbox(
                            "render metadata",
                            value=app.storage.user[hash_value].get(
                                "render_metadata", True
                            ),
                        ).on(
                            "update:model-value",
                            lambda e: handle_checkbox_change(checkbox.value),
                        )
                # Add some spacing between cards
                ui.space().classes("h-4")


def render_watermark(watermark_container):
    if watermark_container:
        watermark_container.clear()
        with watermark_container:
            wm_hash = app.storage.user.get("watermark", "")
            wm_info = app.storage.user.get(wm_hash, {})
            wm_url = wm_info.get("editor_url")
            if wm_url:
                ui.image(wm_url).classes("w-full")
            else:
                # Fallback to IPFS for watermarks stored before local storage migration
                ui.image(
                    f"{ipfs_webui}:{ipfs_webui_port}/ipfs/{wm_hash}"
                ).classes("w-full")


def setup_browser_tab():
    if browser_content:
        with browser_content:
            # Minimal iframe structure - no wrapper div
            iframe = ui.html(
                """
                <iframe
                    id="browser-frame"
                    style="width: 100%; height: 100%; min-height: 100vh; border: none; margin: 0; padding: 0; display: block;"
                    srcdoc="<html><body style='margin:0;padding:0;overflow:hidden;background:transparent;'></body></html>"
                ></iframe>
            """,
                sanitize=lambda x: x,
            ).style(
                "width: 100%; height: 100%; min-height: 100vh; margin: 0; padding: 0; display: block;"
            )

            # Function to update the iframe content
            def update_browser_content(html_content=None):
                if html_content is None:
                    # Clear the iframe
                    js = """
                        const iframe = document.querySelector('#browser-frame');
                        if (iframe) {
                            iframe.srcdoc = "<html><body style='margin:0;padding:0;overflow:hidden;background:transparent;'></body></html>";
                        }
                    """
                    ui.run_javascript(js)
                else:
                    # Use base64 encoding to safely pass large HTML content
                    # This avoids all escaping issues
                    encoded_html = base64.b64encode(
                        html_content.encode("utf-8")
                    ).decode("ascii")
                    js = f"""
                        (function updateIframe() {{
                            function decodeBase64Utf8(base64Str) {{
                                const binaryStr = atob(base64Str);
                                const bytes = new Uint8Array(binaryStr.length);
                                for (let i = 0; i < binaryStr.length; i++) {{
                                    bytes[i] = binaryStr.charCodeAt(i);
                                }}
                                return new TextDecoder('utf-8').decode(bytes);
                            }}

                            console.log('Looking for iframe #browser-frame...');
                            const iframe = document.querySelector('#browser-frame');
                            console.log('iframe element:', iframe);

                            if (iframe) {{
                                console.log('Found iframe, decoding and setting content...');
                                const encodedHtml = '{encoded_html}';
                                const decodedHtml = decodeBase64Utf8(encodedHtml);
                                console.log('Decoded HTML length:', decodedHtml.length);
                                console.log('First 200 chars:', decodedHtml.substring(0, 200));

                                iframe.srcdoc = decodedHtml;
                                console.log('✓ Iframe srcdoc set successfully');

                                // Also try setting via contentWindow as a fallback
                                setTimeout(() => {{
                                    if (iframe.contentDocument) {{
                                        console.log('Iframe contentDocument accessible');
                                    }} else {{
                                        console.warn('Iframe contentDocument not accessible (may be CORS)');
                                    }}
                                }}, 100);
                            }} else {{
                                console.error('✗ Iframe #browser-frame not found in DOM');
                                console.log('Available iframes:', document.querySelectorAll('iframe').length);

                                // The iframe might not be in the DOM yet if the BROWSER tab hasn't been opened
                                // Try again after a short delay
                                setTimeout(() => {{
                                    console.log('Retrying iframe update...');
                                    const retryIframe = document.querySelector('#browser-frame');
                                    if (retryIframe) {{
                                        console.log('Found iframe on retry!');
                                        const encodedHtml = '{encoded_html}';
                                        const decodedHtml = decodeBase64Utf8(encodedHtml);
                                        retryIframe.srcdoc = decodedHtml;
                                        console.log('✓ Iframe srcdoc set on retry');
                                    }} else {{
                                        console.error('✗ Iframe still not found. User may need to switch to BROWSER tab first.');
                                    }}
                                }}, 500);
                            }}
                        }})();
                    """
                    print(
                        f"Updating iframe with base64 encoded HTML, original length: {len(html_content)}"
                    )
                    ui.run_javascript(js)

            return update_browser_content


def safe_get(metadata, key, default=""):
    """Safely get a value from metadata with a default fallback."""
    return metadata.get(key, default)


def safe_list_from_metadata(metadata, key, separator="|"):
    """
    Safely convert metadata field to a list.
    Handles both string (with separator) and already-list values.
    """
    value = safe_get(metadata, key, "")
    if isinstance(value, list):
        # Already a list, just strip whitespace from each item
        return [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str) and value:
        # String, split by separator
        return [item.strip() for item in value.split(separator) if item.strip()]
    else:
        return []


def parse_dimensions(dim_str):
    """Parse image dimensions from 'width height' string."""
    if not dim_str:
        return None, None
    try:
        width, height = dim_str.split()[:2]
        return int(width), int(height)
    except (ValueError, AttributeError):
        return None, None


def get_mimetype(file_path):
    """Get MIME type based on file extension."""
    if not file_path:
        return "image/jpeg"
    ext = os.path.splitext(file_path)[1].lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".tiff": "image/tiff",
        ".webp": "image/webp",
    }.get(ext, "application/octet-stream")


async def create_ninjs_data_pod(prefix="processed"):
    try:
        # Guard: only allow publishing protected content types
        if prefix in ("raw", "processed"):
            ui.notify(
                "Cannot publish unprotected content. Apply aposematic or encipher protection first.",
                type="warning",
            )
            return

        # Get all processed images
        processed_hashes = app.storage.user.get(f"{prefix}_img_hashes", [])
        if not processed_hashes:
            ui.notify("No processed images found", type="warning")
            return

        # Create list to hold all news items
        data_items = []
        processed_count = 0
        error_count = 0

        for img_hash in processed_hashes:
            try:
                # Get image metadata
                img_info = app.storage.user.get(img_hash)
                if not img_info:
                    print(f"Warning: No info found for hash {img_hash}")
                    error_count += 1
                    continue

                img_path = img_info.get("path")
                if not img_path or not os.path.exists(img_path):
                    print(f"Warning: Image file not found: {img_path}")
                    error_count += 1
                    continue

                # Get metadata using existing function
                try:
                    metadata_list = await get_img_metadata(img_path)
                    if (
                        not metadata_list
                        or not isinstance(metadata_list, list)
                        or not metadata_list[0]
                    ):
                        print(f"Warning: No metadata found for {img_path}")
                        # For media images, create basic metadata if ExifTool fails
                        if img_info.get("has_audio", False) or img_info.get("has_video", False):
                            print(
                                f"Creating basic metadata for media image: {img_path}"
                            )
                            metadata = {
                                "FileName": os.path.basename(img_path),
                                "FileSize": os.path.getsize(img_path),
                                "FileType": "PNG",
                            }
                        else:
                            error_count += 1
                            continue
                    else:
                        metadata = metadata_list[0]
                except Exception as e:
                    print(f"Error getting metadata for {img_path}: {str(e)}")
                    if img_info.get("has_audio", False) or img_info.get("has_video", False):
                        print(
                            f"Creating basic metadata for media image due to ExifTool error: {img_path}"
                        )
                        metadata = {
                            "FileName": os.path.basename(img_path),
                            "FileSize": os.path.getsize(img_path),
                            "FileType": "PNG",
                        }
                    else:
                        error_count += 1
                        continue

                # Build news item with safe defaults
                render_flag = img_info.get("render_metadata", True)
                print(f"DEBUG: render_metadata for {img_hash} = {render_flag}")

                # Check media flags
                has_audio = img_info.get("has_audio", False)
                has_video = img_info.get("has_video", False)

                # Set type: video takes precedence over audio
                if has_video:
                    item_type = "video_image"
                elif has_audio:
                    item_type = "audio_image"
                else:
                    item_type = "picture"

                data_item = {
                    "uri": f"{app.storage.user.get('gateway_url', '')}:{img_hash}",
                    "type": item_type,
                    "version": "1.0",
                    "versioncreated": datetime.utcnow().isoformat() + "Z",
                    "firstcreated": safe_get(metadata, "XMP:CreateDate", ""),
                    "pubstatus": "usable",
                    "language": "en",
                    "headline": safe_get(
                        metadata,
                        "IPTC:ObjectName",
                        "Video Image" if has_video else ("Audio Image" if has_audio else "Untitled"),
                    ),
                    "description_text": safe_get(
                        metadata,
                        "IPTC:Caption-Abstract",
                        "Video encoded in image" if has_video else ("Audio encoded in image" if has_audio else ""),
                    ),
                    "keywords": safe_list_from_metadata(metadata, "IPTC:Keywords"),
                    "copyrightnotice": safe_get(metadata, "IPTC:CopyrightNotice", ""),
                    "creditline": safe_get(metadata, "IPTC:Credit", ""),
                    "byline": safe_list_from_metadata(metadata, "IPTC:By-line"),
                    "render_metadata": render_flag,
                }

                # Add audio-specific fields if this is an audio image
                if has_audio:
                    data_item.update(
                        {
                            "audio_format": img_info.get("audio_format", "wav"),
                            "audio_duration": img_info.get("audio_duration", 0),
                            "audio_size": img_info.get("audio_size", 0),
                            "audio_method": "token",
                        }
                    )

                # Add video-specific fields if this image has video
                if has_video:
                    data_item.update(
                        {
                            "has_video": True,
                            "video_method": "token",
                            "video_token_cid": img_info.get("video_token_cid"),
                        }
                    )

                # Add renditions with proper MIME type and dimensions
                width, height = parse_dimensions(
                    safe_get(metadata, "Composite:ImageSize")
                )
                mimetype = get_mimetype(img_path)

                # Use the IPFS gateway URL for browser access
                # This allows the HTML to display images when loaded in a browser
                gateway_base = f"{ipfs_webui}:{ipfs_webui_port}"
                rendition = {
                    "href": f"{gateway_base}/ipfs/{img_hash}",
                    "ipfs_hash": img_hash,  # Store the hash separately for reference
                    "mimetype": mimetype,
                }
                if width and height:
                    rendition["width"] = width
                    rendition["height"] = height
                # Template expects renditions as a list, accessed via renditions[0]
                data_item["renditions"] = [rendition]

                # Add place information if available
                city = safe_get(metadata, "IPTC:City")
                country = safe_get(metadata, "IPTC:Country-PrimaryLocationName")
                if city or country:
                    data_item["place"] = [{"name": city, "country": country}]

                # Add usage terms if available
                if usage_terms := safe_get(metadata, "XMP:UsageTerms"):
                    data_item["usageterms"] = usage_terms

                # Add rights info
                data_item["rightsinfo"] = {
                    "langid": "http://www.lexvo.org/page/iso639-3/eng",
                    "usagetypes": ["publish", "archive"],
                }

                # Add data mining constraints if present
                if constraints := safe_get(metadata, "XMP:OtherConstraints"):
                    data_item["restrictions"] = {
                        "type": "restricted",
                        "constraints": [constraints]
                        if isinstance(constraints, str)
                        else constraints,
                    }

                data_items.append(data_item)
                processed_count += 1

            except Exception as e:
                print(f"Unexpected error processing image {img_hash}: {str(e)}")
                import traceback

                traceback.print_exc()
                error_count += 1
                continue

        if not data_items:
            ui.notify("No valid news items to export", type="warning")
            return

        # Map prefix to content type for the data pod
        content_type_map = {
            "processed": "original",
            "aposematic": "aposematic",
            "enciphered": "encrypted",
        }
        content_type = content_type_map.get(prefix, "original")

        # Create NINJ package
        ninj_package = {
            "version": "1.0",
            "uri": f"urn:newsml:package:{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "type": "package",
            "content_type": content_type,
            "versioncreated": datetime.utcnow().isoformat() + "Z",
            "language": "en",
            "items": data_items,
        }

        # Include keys for encrypted/aposematic content
        # creator_public_key: needed by subscriber for ECDH shared key derivation
        # recipient_public_key: identifies who the content was shared with (for verification)
        if prefix in ("aposematic", "enciphered"):
            creator_key = app.storage.user.get("hvym_public_key")
            if creator_key:
                ninj_package["creator_public_key"] = creator_key
            recipient_key = app.storage.user.get("recipient_public_key")
            if recipient_key:
                ninj_package["recipient_public_key"] = recipient_key

        # Include aposematic parameters for descrambling
        if prefix == "aposematic":
            ninj_package["op_string"] = app.storage.user.get("op_string", "-^+")
            ninj_package["scramble_mode"] = app.storage.user.get("scramble_mode", 2)

        # Save to temp file then add to IPFS
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_path = os.path.join(
            tempfile.gettempdir(), f"ninjs_data_pod_{timestamp}.json"
        )

        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(ninj_package, f, indent=2, ensure_ascii=False)

        # Add to IPFS
        json_hash = ipfs_add(temp_path)
        if not json_hash:
            ui.notify("Failed to add data pod to IPFS", type="negative")
            return None

        # Store the hash for later retrieval
        app.storage.user["latest_data_pod_hash"] = json_hash
        app.storage.user["latest_data_pod_timestamp"] = timestamp
        app.storage.user["tmp_files"].append(temp_path)

        ui.notify(f"Successfully exported {len(data_items)} items to IPFS: {json_hash}")
        return temp_path

    except Exception as e:
        ui.notify(f"Error creating NINJ package: {str(e)}", type="negative")
        raise


async def deploy_ninjs_data_pod(
    prefix="processed", access_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Creates and deploys a NINJS data pod to the gallery API endpoint.

    Args:
        prefix: The prefix for the image hashes in storage (e.g., 'processed', 'original')
        access_token: Optional access token for the API. If not provided, will try to get from app storage.

    Returns:
        Dictionary containing the deployment status and result.
    """
    # First create the NINJS data pod
    try:
        json_file = await create_ninjs_data_pod(prefix)
        if not json_file or not os.path.exists(json_file):
            ui.notify("Failed to create NINJS data pod", type="negative")
            return {"status": "error", "message": "Failed to create NINJS data pod"}
    except Exception as e:
        ui.notify(f"Error creating NINJS data pod: {str(e)}", type="negative")
        return {"status": "error", "message": str(e)}

    # Get access token if not provided
    if not access_token:
        access_token = app.storage.user.get("api_access_token")
        if not access_token:
            ui.notify("No access token provided", type="negative")
            return {"status": "error", "message": "No access token provided"}

    # Prepare the upload URL
    upload_url = f"{app.storage.user.get('api_base_url', '')}/api_upload"
    if not upload_url.startswith("http"):
        ui.notify("Invalid API base URL", type="negative")
        return {"status": "error", "message": "Invalid API base URL"}

    try:
        # Prepare the file for upload
        with open(json_file, "rb") as f:
            files = {"file": (os.path.basename(json_file), f, "application/json")}
            data = {
                "access_token": access_token,
                "encrypted": "false",  # Set to 'true' if encryption is needed
            }

            # Make the request
            response = requests.post(
                upload_url,
                files=files,
                data=data,
                timeout=30,  # 30 seconds timeout
            )

            if response.status_code == 200:
                result = response.json()
                ui.notify("Successfully deployed NINJS data pod", type="positive")
                return {"status": "success", "file_info": result, "path": json_file}
            else:
                error_msg = (
                    f"Upload failed with status {response.status_code}: {response.text}"
                )
                ui.notify(error_msg, type="negative")
                return {
                    "status": "error",
                    "message": error_msg,
                    "status_code": response.status_code,
                }

    except Exception as e:
        error_msg = f"Error uploading NINJS data pod: {str(e)}"
        ui.notify(error_msg, type="negative")
        return {"status": "error", "message": error_msg}


async def deploy_gallery_images(
    prefix: str = "processed", access_token: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Upload all images to the gallery API endpoint.

    Args:
        prefix: The prefix for the image hashes in storage (e.g., 'processed', 'original')
        access_token: Optional access token for the API. If not provided, will try to get from app storage.

    Returns:
        List of upload results with status and file information.
    """
    if not access_token:
        access_token = app.storage.user.get("api_access_token")
        if not access_token:
            ui.notify("No access token provided", type="negative")
            return []

    hashes = app.storage.user.get(f"{prefix}_img_hashes", [])
    if not hashes:
        ui.notify(f"No images found with prefix: {prefix}", type="warning")
        return []

    upload_url = f"{app.storage.user.get('api_base_url', '')}/api_upload"
    if not upload_url.startswith("http"):
        ui.notify("Invalid API base URL", type="negative")
        return []

    results = []
    successful_uploads = 0

    for img_hash in hashes:
        try:
            img_info = app.storage.user.get(img_hash)
            if not img_info:
                results.append(
                    {
                        "status": "error",
                        "hash": img_hash,
                        "message": "Image info not found",
                    }
                )
                continue

            img_path = img_info.get("path")
            if not img_path or not os.path.exists(img_path):
                results.append(
                    {
                        "status": "error",
                        "hash": img_hash,
                        "message": f"Image file not found: {img_path}",
                    }
                )
                continue

            # Prepare the file for upload
            with open(img_path, "rb") as img_file:
                files = {"file": (os.path.basename(img_path), img_file, "image/jpeg")}
                data = {
                    "access_token": access_token,
                    "encrypted": "false",  # Set to 'true' if encryption is needed
                }

                # Make the request
                response = requests.post(
                    upload_url,
                    files=files,
                    data=data,
                    timeout=30,  # 30 seconds timeout
                )

                if response.status_code == 200:
                    result = response.json()
                    results.append(
                        {
                            "status": "success",
                            "hash": img_hash,
                            "file_info": result,
                            "path": img_path,
                        }
                    )
                    successful_uploads += 1
                else:
                    results.append(
                        {
                            "status": "error",
                            "hash": img_hash,
                            "message": f"Upload failed with status {response.status_code}",
                            "response": response.text,
                        }
                    )

        except Exception as e:
            results.append({"status": "error", "hash": img_hash, "message": str(e)})
            continue

    # Notify user of results
    total = len(hashes)
    if successful_uploads == total:
        ui.notify(
            f"Successfully uploaded all {successful_uploads} images", type="positive"
        )
    elif successful_uploads > 0:
        ui.notify(f"Uploaded {successful_uploads} of {total} images", type="warning")
    else:
        ui.notify("Failed to upload any images", type="negative")

    return results


async def fadeout_element(element):
    element.style("opacity: 0; transition: opacity 0.25s ease-out;")
    await asyncio.sleep(0.25)
    element.visible = False


async def fadein_element(element):
    element.visible = True
    # Set initial state (invisible)
    element.style("opacity: 0;")
    # Force reflow
    await asyncio.sleep(0.01)
    # Apply transition and trigger fade in
    element.style("opacity: 1; transition: opacity 0.25s ease-in;")
    await asyncio.sleep(0.25)


async def fade_swap_elements(elem1, elem2):
    await fadeout_element(elem1)
    await fadein_element(elem2)


def toggle_app_mode():
    current_mode = app.storage.user.get("app_mode", "image")
    new_mode = "browser" if current_mode == "image" else "image"
    app.storage.user["app_mode"] = new_mode
    persistent_save_data()


def on_close():
    print("Closing")
    # remove_tmp_files()
    shutil.rmtree(EDITOR_STORAGE_DIR, ignore_errors=True)


def close_app():
    ui.notify("Closing")
    remove_tmp_files()
    app.shutdown()


@ui.page("/")
def main_page():
    # Add Lottie player script to the head
    ui.add_head_html("""
        <script src="https://unpkg.com/@lottiefiles/lottie-player@latest/dist/lottie-player.js"></script>
        <style>
        @font-face {
            font-family: 'phino';
            src: url('/static/PhinoVariation.ttf') format('truetype');
            font-weight: normal;
            font-style: normal;
            font-display: swap;
        }
        
        /* Apply Phino font globally */
        body, button, input, select, textarea, .q-btn, .q-tab, .q-field__native, .q-item {
            font-family: 'phino', monospace, sans-serif !important;
            letter-spacing: 0.5px;
        }
            lottie-player {
                width: 80px;
                height: 80px;
                margin: 0;
                padding: 0;
            }
        </style>
    """)
    logo_anim = "/static/logo.json"

    # Get stored colors for initial CSS
    stored_colors = app.storage.user.get(
        "app_colors",
        {
            "primary": PRIMARY_COLOR,
            "secondary": SECONDARY_COLOR,
            "text-color": TEXT_COLOR,
            "bg-color": BG_COLOR,
            "card-bg": CARD_BG,
            "border-color": BORDER_COLOR,
            "dark-primary": DARK_PRIMARY,
            "dark-secondary": DARK_SECONDARY,
            "dark-text": DARK_TEXT,
            "dark-bg": DARK_BG,
            "dark-card": DARK_CARD,
            "dark-border": DARK_BORDER,
        },
    )

    # Debug: Print stored colors
    print("=== STORED COLORS FROM STORAGE ===")
    for key, value in stored_colors.items():
        print(f"  {key}: {value}")
    print("==================================")

    # Set default Quasar colors (will be immediately overridden by JavaScript based on dark mode)
    ui.colors(
        primary=stored_colors.get("primary", PRIMARY_COLOR),
        secondary=stored_colors.get("secondary", SECONDARY_COLOR),
    )

    # Inject initial CSS variables
    ui.add_head_html(f"""
        <style>
            :root {{
                /* Light mode source colors */
                --light-primary-color: {stored_colors.get("primary", PRIMARY_COLOR)};
                --light-secondary-color: {stored_colors.get("secondary", SECONDARY_COLOR)};
                --light-text-color: {stored_colors.get("text-color", TEXT_COLOR)};
                --light-bg-color: {stored_colors.get("bg-color", BG_COLOR)};
                --light-card-bg: {stored_colors.get("card-bg", CARD_BG)};
                --light-border-color: {stored_colors.get("border-color", BORDER_COLOR)};

                /* Dark mode source colors */
                --dark-primary-color: {stored_colors.get("dark-primary", DARK_PRIMARY)};
                --dark-secondary-color: {stored_colors.get("dark-secondary", DARK_SECONDARY)};
                --dark-text-color: {stored_colors.get("dark-text", DARK_TEXT)};
                --dark-bg-color: {stored_colors.get("dark-bg", DARK_BG)};
                --dark-card-bg: {stored_colors.get("dark-card", DARK_CARD)};
                --dark-border-color: {stored_colors.get("dark-border", DARK_BORDER)};

                /* Active colors default to light mode */
                --primary-color: var(--light-primary-color);
                --secondary-color: var(--light-secondary-color);
                --text-color: var(--light-text-color);
                --bg-color: var(--light-bg-color);
                --card-bg: var(--light-card-bg);
                --border-color: var(--light-border-color);
            }}

            @media (prefers-color-scheme: dark) {{
                :root {{
                    --primary-color: var(--dark-primary-color);
                    --secondary-color: var(--dark-secondary-color);
                    --text-color: var(--dark-text-color);
                    --bg-color: var(--dark-bg-color);
                    --card-bg: var(--dark-card-bg);
                    --border-color: var(--dark-border-color);
                }}
            }}
        </style>
        <script>
            // Set initial colors based on dark mode
            (function() {{
                const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                const root = document.documentElement;
                const body = document.body;
                console.log("Initial dark mode detection:", isDark);

                if (isDark) {{
                    console.log("Setting initial colors to DARK mode");
                    // Update Quasar color variables
                    body.style.setProperty('--q-primary', '{stored_colors.get("dark-primary", DARK_PRIMARY)}');
                    body.style.setProperty('--q-secondary', '{stored_colors.get("dark-secondary", DARK_SECONDARY)}');
                    body.style.setProperty('--q-color-primary', '{stored_colors.get("dark-primary", DARK_PRIMARY)}');
                    body.style.setProperty('--q-color-secondary', '{stored_colors.get("dark-secondary", DARK_SECONDARY)}');
                }} else {{
                    console.log("Setting initial colors to LIGHT mode");
                    // Update Quasar color variables
                    body.style.setProperty('--q-primary', '{stored_colors.get("primary", PRIMARY_COLOR)}');
                    body.style.setProperty('--q-secondary', '{stored_colors.get("secondary", SECONDARY_COLOR)}');
                    body.style.setProperty('--q-color-primary', '{stored_colors.get("primary", PRIMARY_COLOR)}');
                    body.style.setProperty('--q-color-secondary', '{stored_colors.get("secondary", SECONDARY_COLOR)}');
                }}
            }})();
        </script>
    """)

    ui.add_css("""
        /* Buttons */
        .q-btn, .q-button-item, .q-button--standard, .q-button--fab {{
            background-color: var(--secondary-color) !important;
            color: white !important;
        }}

        .pallete-btn {{
            border: 2px solid white !important;
            box-shadow: 0 0 0 1px rgba(0,0,0,0.2) !important;
        }}

        /* Custom gradient background */
        .gradient-background {{
            background: linear-gradient(90deg, var(--primary-color), var(--secondary-color)) !important;
            color: white !important; /* Override text color for better contrast */
        }}

        @layer components {{
            body, .q-page, .q-drawer, .q-tab-panel{{
                background-color: var(--bg-color) !important;
                color: var(--text-color) !important;
            }}
            .bg-primary{{
                background-color: var(--primary-color) !important;
                color: var(--text-color) !important;
            }}
            .q-secondary-color, bg-secondary{{
                background-color: var(--secondary-color) !important;
                color: var(--text-color) !important;
            }}

            .q-focus-helper, .block{{
                color: var(--text-color) !important;
            }}

            /* Inputs and selects */
            .q-field, .q-input, .q-select, .q-textarea, .q-icon, .text-sm {{
                color: var(--text-color) !important;
            }}
            
            .q-field__control, .q-field__native, .q-field__label, .q-fab__label {{
                color: var(--text-color) !important;
            }}

            /* Tabs */
            .q-tab {{
                color: var(--text-color) !important;
            }}
            
            .q-tab--active, .q-tab--active .q-icon, .q-tab--active .q-tab__icon, .q-button--active, .text-white, .q-tab__indicator {{
                color: var(--primary-color) !important;
            }}

            /* Cards and dialogs */
            .q-card:not(.card-no-border), .q-dialog, .q-menu, .q-tooltip {{
                background-color: var(--card-bg) !important;
                color: var(--text-color) !important;
                border: 1px solid var(--border-color) !important;
            }}

            .card-no-border {{
                background-color: transparent !important;
                border: none !important;
                box-shadow: none !important;
            }}
        }}
    """)

    init()

    # Create state for toggling header/footer visibility
    show_header_footer = True

    def toggle_header_footer():
        nonlocal show_header_footer
        show_header_footer = not show_header_footer

        if show_header_footer:
            # Make elements visible first
            header.visible = True
            footer.visible = True
            # Small delay to ensure visibility is applied before transform
            ui.timer(
                0.01,
                lambda: [
                    header.classes(
                        replace="row items-center justify-between p-0 gradient-background transition-all duration-300 transform translate-y-0"
                    ),
                    footer.classes(
                        replace="gradient-background transition-all duration-300 transform translate-y-0"
                    ),
                ],
                once=True,
            )
        else:
            # Apply transform to hide
            header.classes(
                replace="row items-center justify-between p-0 gradient-background transition-all duration-300 transform -translate-y-full"
            )
            footer.classes(
                replace="gradient-background transition-all duration-300 transform translate-y-full"
            )
            # Hide after animation completes
            ui.timer(
                300,
                lambda: [
                    setattr(header, "visible", False),
                    setattr(footer, "visible", False),
                ],
                once=True,
            )

    async def on_tab_change():
        global pending_browser_html
        print(f"Tab changed to: {tabs.value}")
        if tabs.value == "IMAGES" and app.storage.user.get("app_mode") != "image":
            toggle_app_mode()
            await fade_swap_elements(browser_ctrls, editor_ctrls)
            await fade_swap_elements(browser_content, file_container)
            editor_settings.visible = True
            browser_settings.visible = False
        elif tabs.value == "BROWSER" and app.storage.user.get("app_mode") != "browser":
            toggle_app_mode()
            await fade_swap_elements(editor_ctrls, browser_ctrls)
            await fade_swap_elements(file_container, browser_content)
            editor_settings.visible = False
            browser_settings.visible = True

            # Load pending content if available
            if pending_browser_html and update_browser_content:
                print("Loading pending HTML content into iframe")

                # Use process_dialog to show loading indicator
                async def load_browser_content():
                    global pending_browser_html
                    # Small delay to ensure iframe is in DOM after tab switch
                    await asyncio.sleep(0.1)
                    update_browser_content(pending_browser_html)
                    pending_browser_html = None

                await process_dialog(load_browser_content)

    with ui.header().classes(
        "row items-center justify-between p-0 gradient-background transition-all duration-300 transform"
    ) as header:
        # Left side: Tabs
        global tabs
        with ui.row().classes("items-center"):
            with ui.tabs().on("update:model-value", on_tab_change) as tabs:
                ui.tab("IMAGES", icon="image")
                ui.tab("BROWSER", icon="web")
                ui.tab("SETTINGS", icon="settings")

            state_container = ui.row().classes("items-center")

        # Right side: Dark mode toggle, Lottie animation and close button
        with ui.row().classes("items-center gap-2 pr-2"):
            # Dark mode toggle - store reference for use in settings
            # If not stored, detect system preference and use that
            global dark_mode_instance
            stored_dark_mode = app.storage.user.get("dark_mode", None)

            # If None (first time or auto mode), we'll detect system preference via JavaScript
            # For now, initialize with stored value or None
            dark_mode = ui.dark_mode(value=stored_dark_mode)
            dark_mode_instance = dark_mode

            # Bind to storage for persistence
            dark_mode.bind_value(app.storage.user, "dark_mode")

            # Add on_change handler to save when dark mode changes
            def on_dark_mode_change_header(e):
                print(f"Dark mode changed to: {e.value}")
                persistent_save_data()

            dark_mode.on("update:model-value", on_dark_mode_change_header)

            # If stored value is None (first time), detect system preference and set explicitly
            # This ensures we store an actual boolean value instead of null
            if stored_dark_mode is None:
                print(
                    "Dark mode not set in storage - will detect from system preference"
                )

                # Use a small delay to detect after page loads
                def detect_and_set_system_preference():
                    # NiceGUI's auto mode will already be following system preference for display
                    # We just need to convert None to an explicit True/False for storage

                    # Use JavaScript to detect system preference
                    # The JavaScript will print the detected value
                    # Then we'll set dark_mode based on assumption it's dark (since you mentioned your system is dark)
                    # TODO: Ideally we'd get the JS value back to Python, but for now we'll set to True (dark)
                    # If your system is light, change this to dark_mode.disable()

                    print("Detecting system preference...")
                    ui.run_javascript("""
                        const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                        console.log("=== SYSTEM DARK MODE DETECTED:", isDark, "===");
                        console.log("This value should be stored explicitly");
                    """)

                    # Set to dark mode (True) - this will be saved via the binding and on_change handler
                    # If you're on a light mode system, change to: dark_mode.disable()
                    dark_mode.enable()  # Sets value to True
                    print(f"Dark mode explicitly set to: {dark_mode.value}")

                ui.timer(0.3, detect_and_set_system_preference, once=True)

            ui.html(
                f'''
                <lottie-player
                    src="{logo_anim}"
                    loop
                    autoplay
                    style="width: 192px; height: 96px;"
                ></lottie-player>
            ''',
                sanitize=False,
            )
            # ui.button(icon='close', on_click=close_app).classes('outline q-secondary-color').props('flat')

    # Define color change handler (defined here so it's in scope for color pickers below)
    def on_color_change():
        """Handle color picker changes - save and apply theme"""
        print("\n=== COLOR PICKER CHANGED ===")
        print("Saving and reapplying theme...")
        persistent_save_data()
        # Reapply theme colors when user changes them
        apply_theme_colors()
        print("===========================\n")

    # Apply theme colors on page load
    # CSS media queries automatically switch between light/dark mode colors
    ui.timer(0.2, apply_theme_colors, once=True)

    # Add a floating button to toggle header/footer visibility
    fab = ui.button(icon="visibility", color="primary").classes(
        "fixed-bottom-right q-mb-xl q-mr-xl shadow-5"
    )
    fab.style("z-index: 9999; width: 56px; height: 56px; border-radius: 50%;")
    fab.on("click", toggle_header_footer)

    with ui.footer().classes(
        "gradient-background transition-all duration-300 transform"
    ) as footer:
        with ui.card().classes("w-full card-no-border") as editor_ctrls:
            with ui.fab("image").classes("q-secondary-color"):
                if is_ipfs_running():
                    ui.fab_action("info", on_click=gallery_info_dialog).tooltip(
                        "Set Gallery Info"
                    )
                    ui.fab_action("add_photo_alternate", on_click=choose_img).tooltip(
                        "Add images"
                    )
                    # ui.fab_action('text_snippet', on_click=lambda: markdown_block_dialog( update_from_storage, process_add_mardown_file)).tooltip('Add Markdown Block')
                    ui.fab_action(
                        "person_add",
                        on_click=lambda: add_subscriber_dialog(add_subscriber),
                    ).tooltip("Add Subscriber")
                    ui.fab_action(
                        "approval",
                        on_click=lambda: process_dialog(process_watermarking),
                    ).tooltip("Add watermark to images")
                    ui.fab_action(
                        "dataset",
                        on_click=lambda: assign_iptc_dialog(
                            process_dialog, process_shared_iptc_metadata
                        ),
                    ).tooltip("Assign Shared IPTC metadata")
                    ui.fab_action(
                        "emoji_nature",
                        on_click=lambda: aposematic_dialog(
                            process_dialog, process_aposematic
                        ),
                    ).tooltip("Create Aposematic images")
                    ui.fab_action(
                        "lock",
                        on_click=lambda: cipher_dialog(
                            process_dialog, process_enciphering
                        ),
                    ).tooltip("Encipher images")
                    # ui.fab_action('lock_open', on_click=lambda: process_dialog(process_deciphering))
                    ui.fab_action(
                        "cloud_upload",
                        on_click=lambda: process_dialog(
                            process_pintheon_deploy_gallery
                        ),
                    ).tooltip("Deploy to Pintheon")
                    ui.fab_action(
                        "drive_folder_upload",
                        on_click=lambda: process_dialog(process_debug_deploy_gallery),
                    ).tooltip("Local Debug")
            ui.toggle(img_states, on_change=render_gallery).bind_value(
                app.storage.user, "img_state"
            )
        with ui.card().classes("w-full card-no-border") as browser_ctrls:
            with ui.fab("web_stories").classes("q-secondary-color"):
                if is_ipfs_running():
                    ui.fab_action(
                        "subscriptions", on_click=lambda: view_subscriptions_dialog(
                            fetch_subscription_content=fetch_subscription_content,
                            remove_subscription=remove_subscription
                        )
                    ).tooltip("View Subscriptions")
                    ui.fab_action(
                        "add",
                        on_click=lambda: add_subscription_dialog(add_subscription),
                    ).tooltip("Add Subscription")
                    ui.fab_action(
                        "play_circle",
                        on_click=lambda: select_channel_dialog(
                            select_channel,
                            fetch_subscription_channels=fetch_subscription_channels
                        ),
                    ).tooltip("Select Channel")

    with ui.tab_panels(tabs, value="IMAGES").classes("w-full h-full") as tab_panel:
        with ui.tab_panel("IMAGES"):
            with ui.column().classes("w-full gap-2"):
                # Show warnings if services are not available
                if not is_ipfs_running():
                    ui.notify("IPFS is not running", type="warning")
                if not is_imagemagick_available():
                    ui.notify("ImageMagick is not available", type="warning")

                # Main Image File content
                global file_container
                file_container = ui.column().classes("w-full")
                render_gallery()

        # In your tab panel initialization:
        with ui.tab_panel("BROWSER"):
            global browser_content, update_browser_content
            # Use minimal structure with explicit height
            browser_content = ui.element().style(
                "width: 100%; height: 100%; min-height: 100vh;"
            )

            # Set up the browser tab and get the update function
            update_func = setup_browser_tab()
            update_browser_content = update_func

            # Initialize with empty iframe
            if update_browser_content:
                update_browser_content()  # This will clear/initialize the iframe
                print(
                    f"Browser tab initialized, update_browser_content is: {type(update_browser_content)}"
                )

        with ui.tab_panel("SETTINGS"):
            with ui.card().classes("w-full card-no-border") as editor_settings:
                ui.label("editor settings").classes("text-md font-medium")
                with ui.grid(columns=2).classes("w-full"):
                    # Left column
                    with ui.column().classes("w-full gap-1"):
                        # IPFS WebUI Card
                        with ui.card().classes("w-full"):
                            with ui.expansion("IPFS").classes("w-full"):
                                with ui.row().classes("w-full items-end gap-2"):
                                    ui.input("WebUI URL", value=ipfs_webui).bind_value(
                                        app.storage.user, "ipfs_webui"
                                    ).classes("grow")
                                    ui.input("Port", value=ipfs_webui_port).bind_value(
                                        app.storage.user, "ipfs_webui_port"
                                    ).classes("w-30")
                                with ui.row().classes("w-full items-end gap-2"):
                                    ui.input("API URL", value=ipfs_endpoint).bind_value(
                                        app.storage.user, "ipfs_endpoint"
                                    ).classes("grow")
                                    ui.input("Port", value=port).bind_value(
                                        app.storage.user, "port"
                                    ).classes("w-30")
                        with ui.card().classes("w-full"):
                            with ui.expansion("Pintheon").classes("w-full"):
                                with ui.row().classes("w-full items-end gap-2"):
                                    ui.input("Gateway", value=gateway_url).bind_value(
                                        app.storage.user, "gateway_url"
                                    ).classes("grow")
                                with ui.row().classes("w-full items-end gap-2"):
                                    ui.input(
                                        "Local API", value=pintheon_endpoint
                                    ).bind_value(
                                        app.storage.user, "pintheon_endpoint"
                                    ).classes("grow")
                                    ui.input("Port", value=pintheon_port).bind_value(
                                        app.storage.user, "pintheon_port"
                                    ).classes("w-30")
                                ui.textarea("access token").classes(
                                    "w-full"
                                ).bind_value(app.storage.user, "access_token")

                    # Right column
                    with ui.column().classes("w-full gap-1"):
                        use_watermark = app.storage.user.get("use_watermark", False)
                        # Metadata Settings Card
                        with ui.card().classes("w-full"):
                            with ui.expansion("Metadata").classes("w-full"):
                                with ui.row().classes("w-full items-center"):
                                    ui.input("Artist", value=artist).bind_value(
                                        app.storage.user, "artist"
                                    ).on_value_change(persistent_save_data).classes(
                                        "w-full"
                                    )
                                    with ui.expansion("Stamp", icon="approval").classes(
                                        "w-full"
                                    ):
                                        w_switch = (
                                            ui.switch("Stamp", value=use_watermark)
                                            .bind_value(
                                                app.storage.user, "use_watermark"
                                            )
                                            .on_value_change(persistent_save_data)
                                        )
                                        watermark_size = app.storage.user.get(
                                            "watermark_size", 0.2
                                        )
                                        with (
                                            ui.row()
                                            .classes("w-full items-center")
                                            .bind_visibility_from(w_switch, "value")
                                        ):
                                            ui.label("Size").classes(
                                                "text-md font-small"
                                            )
                                            w_size = (
                                                ui.slider(
                                                    min=0.01,
                                                    max=1.0,
                                                    step=0.01,
                                                    value=watermark_size,
                                                )
                                                .classes("w-1/2")
                                                .bind_value(
                                                    app.storage.user, "watermark_size"
                                                )
                                                .on_value_change(persistent_save_data)
                                            )
                                        with (
                                            ui.row()
                                            .classes("w-full items-center")
                                            .bind_visibility_from(w_switch, "value")
                                        ):
                                            ui.label("Padding").classes(
                                                "text-md font-small"
                                            )
                                            w_padding = app.storage.user.get(
                                                "watermark_padding", 0.05
                                            )
                                            w_pad = (
                                                ui.slider(
                                                    min=0.0,
                                                    max=0.25,
                                                    step=0.01,
                                                    value=w_padding,
                                                )
                                                .classes("w-1/2")
                                                .bind_value(
                                                    app.storage.user,
                                                    "watermark_padding",
                                                )
                                                .on_value_change(persistent_save_data)
                                            )
                                        with (
                                            ui.row()
                                            .classes("w-full items-center")
                                            .bind_visibility_from(w_switch, "value")
                                        ):
                                            ui.label("Position").classes(
                                                "text-md font-small"
                                            )
                                            w_position = app.storage.user.get(
                                                "watermark_position", 1
                                            )
                                            w_pos = (
                                                ui.select(
                                                    WATERMARK_POSITIONS,
                                                    value=w_position,
                                                )
                                                .classes("grow")
                                                .bind_value(
                                                    app.storage.user,
                                                    "watermark_position",
                                                )
                                                .on_value_change(persistent_save_data)
                                            )
                                        with ui.row().classes("w-full"):
                                            w_img = app.storage.user.get(
                                                "watermark", None
                                            )
                                            with (
                                                ui.row()
                                                .classes("w-1/4")
                                                .bind_visibility_from(
                                                    w_switch, "value"
                                                ) as watermark_container
                                            ):
                                                if w_img:
                                                    print(w_img)
                                                    url = f"{ipfs_webui}:{ipfs_webui_port}/ipfs/{w_img}"
                                                    if url_valid(url):
                                                        render_watermark(
                                                            watermark_container
                                                        )
                                            w_upload = ui.button(
                                                "Watermark",
                                                on_click=lambda: choose_watermark(
                                                    watermark_container
                                                ),
                                                icon="upload",
                                            ).bind_visibility_from(w_switch, "value")

                                with ui.expansion(
                                    "Shared IPTC Metadata", icon="data_array"
                                ).classes("w-full"):
                                    iptc_switch = (
                                        ui.switch("IPTC Metadata", value=iptc)
                                        .bind_value(app.storage.user, "iptc")
                                        .on_value_change(persistent_save_data)
                                    )
                                    with ui.row().classes("w-full items-center"):
                                        ui.button(
                                            "Set Shared IPTC Metadata",
                                            icon="perm_data_setting",
                                            on_click=lambda: iptc_dialog(
                                                iptc_data, persistent_save_data
                                            ),
                                        ).bind_visibility_from(iptc_switch, "value")
                                    with (
                                        ui.row()
                                        .classes("w-full items-center")
                                        .bind_visibility_from(iptc_switch, "value")
                                    ):
                                        ui.label("Template IPTC Fields")
                                        ui.button(
                                            "Load Template",
                                            icon="download",
                                            on_click=lambda: load_iptc_template(),
                                        ).props("flat")
                                        ui.button(
                                            "Save Template",
                                            icon="save",
                                            on_click=lambda: save_iptc_template(),
                                        ).props("flat")

                        # Additional settings can be added here
                        with ui.card().classes("w-full"):
                            with ui.expansion("App Data").classes("w-full"):
                                with ui.row().classes("w-full items-center"):
                                    key_input = (
                                        ui.input("App Key", value=hvym_public_key)
                                        .bind_value(app.storage.user, "hvym_public_key")
                                        .classes("grow")
                                        .props("disable")
                                    )
                                    ui.button(
                                        icon="copy_all",
                                        on_click=lambda: [
                                            ui.clipboard.write(hvym_public_key),
                                            ui.notify("Copied App Key"),
                                        ],
                                    ).classes("w-10").props("flat color=primary")

                                with ui.row().classes("w-full items-center"):
                                    secret_input = (
                                        ui.input(
                                            "App Secret",
                                            value=stellar_secret,
                                            password=True,
                                        )
                                        .bind_value(app.storage.user, "stellar_secret")
                                        .classes("grow")
                                        .props("disable")
                                    )
                                    ui.button(
                                        icon="copy_all",
                                        on_click=lambda: [
                                            ui.clipboard.write(stellar_secret),
                                            ui.notify("Copied App Secret"),
                                        ],
                                    ).classes("w-10").props("flat color=primary")

                        with ui.card().classes("w-full") as app_colors_card:
                            with ui.expansion("App Colors").classes("w-full"):
                                app_colors = app.storage.user.get(
                                    "app_colors",
                                    {
                                        "primary": PRIMARY_COLOR,
                                        "secondary": SECONDARY_COLOR,
                                        "text-color": TEXT_COLOR,
                                        "bg-color": BG_COLOR,
                                        "card-bg": CARD_BG,
                                        "border-color": BORDER_COLOR,
                                        "dark-primary": DARK_PRIMARY,
                                        "dark-secondary": DARK_SECONDARY,
                                        "dark-text": DARK_TEXT,
                                        "dark-bg": DARK_BG,
                                        "dark-card": DARK_CARD,
                                        "dark-border": DARK_BORDER,
                                    },
                                )
                                with ui.card().classes(
                                    "w-full light-palette-card"
                                ) as light_colors:
                                    ui.label("light").classes("text-md font-medium")
                                    with ui.row().classes("w-full items-center"):
                                        for key, value in app_colors.items():
                                            if "dark" not in key:
                                                with ui.button().classes(
                                                    "no-underline pallete-btn"
                                                ) as btn:
                                                    btn._props["no-caps"] = True
                                                    btn._props["flat"] = True
                                                    btn.style(
                                                        f"background-color: {value} !important;"
                                                    )

                                                    def make_color_handler(
                                                        color_key, btn_ref
                                                    ):
                                                        def handler(e):
                                                            # e.color contains the actual hex color value
                                                            btn_ref.style(
                                                                f"background-color: {e.color} !important;"
                                                            )
                                                            app.storage.user[
                                                                "app_colors"
                                                            ][color_key] = e.color
                                                            print(
                                                                f"Color changed: {color_key} = {e.color}"
                                                            )
                                                            on_color_change()

                                                        return handler

                                                    color_picker = ui.color_picker(
                                                        on_pick=make_color_handler(
                                                            key, btn
                                                        )
                                                    )
                                                    color_picker.value = value
                                with ui.card().classes(
                                    "w-full dark-palette-card"
                                ) as dark_colors:
                                    ui.label("dark").classes("text-md font-medium")
                                    with ui.row().classes("w-full items-center"):
                                        for key, value in app_colors.items():
                                            if "dark" in key:
                                                with ui.button().classes(
                                                    "no-underline pallete-btn"
                                                ) as btn:
                                                    btn._props["no-caps"] = True
                                                    btn._props["flat"] = True
                                                    btn.style(
                                                        f"background-color: {value} !important;"
                                                    )

                                                    def make_color_handler(
                                                        color_key, btn_ref
                                                    ):
                                                        def handler(e):
                                                            # e.color contains the actual hex color value
                                                            btn_ref.style(
                                                                f"background-color: {e.color} !important;"
                                                            )
                                                            app.storage.user[
                                                                "app_colors"
                                                            ][color_key] = e.color
                                                            print(
                                                                f"Color changed: {color_key} = {e.color}"
                                                            )
                                                            on_color_change()

                                                        return handler

                                                    color_picker = ui.color_picker(
                                                        on_pick=make_color_handler(
                                                            key, btn
                                                        )
                                                    )
                                                    color_picker.value = value

                                # Add dark mode toggle that updates palette visibility and applies colors
                                def on_dark_mode_change():
                                    # Update palette visibility
                                    if dark_mode.value:
                                        light_colors.visible = False
                                        dark_colors.visible = True
                                    else:
                                        light_colors.visible = True
                                        dark_colors.visible = False
                                    # Apply theme colors
                                    apply_theme_colors()

                                # Bind switch to dark mode
                                with ui.row().classes("w-full items-center"):
                                    ui.label("Dark Mode").classes("text-md font-medium")
                                    ui.switch().bind_value(dark_mode).on(
                                        "update:model-value", on_dark_mode_change
                                    )

                                # Show only the color palette that matches current mode
                                # dark_mode.value can be True, False, or None (auto/system preference)
                                print(f"Dark mode value at init: {dark_mode.value}")

                                # When dark_mode is None (auto), use JavaScript to detect system preference
                                # and update palette visibility accordingly
                                if dark_mode.value is None:
                                    # Auto mode - use JavaScript to detect and set visibility
                                    ui.run_javascript(f"""
                                        const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                                        console.log("Auto mode - system dark:", isDark);

                                        // Find and toggle palette visibility based on system preference
                                        const lightCard = document.querySelector('.light-palette-card');
                                        const darkCard = document.querySelector('.dark-palette-card');

                                        if (lightCard) lightCard.style.display = isDark ? 'none' : '';
                                        if (darkCard) darkCard.style.display = isDark ? '' : 'none';
                                    """)
                                    # Default to showing light until JavaScript runs
                                    light_colors.visible = True
                                    dark_colors.visible = False
                                elif dark_mode.value:
                                    # Explicitly dark mode
                                    light_colors.visible = False
                                    dark_colors.visible = True
                                else:
                                    # Explicitly light mode
                                    light_colors.visible = True
                                    dark_colors.visible = False

            with ui.card().classes("w-full card-no-border") as browser_settings:
                ui.label("browser settings").classes("text-md font-medium")
                with ui.grid(columns=2).classes("w-full"):
                    # Left column
                    with ui.column().classes("w-full gap-1"):
                        with ui.card().classes("w-full"):
                            ui.label("browser settings").classes("text-md font-medium")

        with ui.tab_panel("BROWSER"):
            global content_container
            content_container = ui.column().classes("w-full")

    print(app.storage.user.get("app_mode"))
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

    if app.storage.user.get("app_mode") == "browser":
        tab_panel.set_value("BROWSER")
        editor_ctrls.visible = True
        editor_settings.visible = True
        browser_ctrls.visible = False
        browser_settings.visible = False
    else:
        tab_panel.set_value("IMAGES")
        editor_ctrls.visible = True
        editor_settings.visible = True
        browser_ctrls.visible = False
        browser_settings.visible = False


def check_native_dependencies():
    """Check for required native tools at runtime"""
    missing = []

    # Check ImageMagick
    try:
        from wand.image import Image

        with Image(width=1, height=1, background="white") as img:
            pass
    except Exception:
        missing.append(("ImageMagick", "https://imagemagick.org/script/download.php"))

    # Check ExifTool
    try:
        import exiftool

        with exiftool.ExifTool() as et:
            pass
    except Exception:
        missing.append(("ExifTool", "https://exiftool.org/"))

    if missing:
        msg = "Missing required dependencies:\n\n"
        for name, url in missing:
            msg += f"- {name}: {url}\n"
        msg += "\nPlease install these tools and try again.\nSee docs/INSTALL.md for installation instructions."

        # Show error dialog using NiceGUI
        with ui.dialog() as dialog, ui.card():
            ui.label("Missing Dependencies").classes("text-h6")
            ui.markdown(msg)
            ui.button("Exit", on_click=lambda: sys.exit(1))
        dialog.open()
        return False

    return True


def reembed_media_if_needed(target_image_path, source_image_path):
    """Copy audio token and video CID chunks from source image to target image.

    Used when an image is re-processed (watermarking, aposematic) and the
    output PNG loses tEXt chunks. Copies encrypted audio tokens and video
    CID references from the source image into the new target image.

    Args:
        target_image_path: New PNG that needs media chunks
        source_image_path: Original PNG that contains media chunks

    Returns:
        str: Path to target image (modified in-place with copied chunks)
    """
    if source_image_path and os.path.exists(source_image_path):
        # Copy audio token chunks
        print(f"Copying media chunks from {source_image_path} into {target_image_path}")
        target_image_path = copy_token_chunks(source_image_path, target_image_path)
        # Copy video CID chunks
        target_image_path = copy_token_chunks(
            source_image_path, target_image_path,
            keyword_prefix=VIDEO_TOKEN_CID_PREFIX
        )
    return target_image_path


async def process_audio_from_storage():
    """Process audio embedding using params stored by edit_audio_info dialog.

    This function follows the process_dialog pattern - it reads parameters
    from app.storage.user['_audio_embed_params'] set by the dialog.
    """
    params = app.storage.user.get("_audio_embed_params")
    if not params:
        ui.notify("No audio embedding parameters found", type="negative")
        return

    try:
        img_name = params["img_name"]
        img_path = params["img_path"]
        hash_value = params["hash_value"]
        audio_file = params["audio_file"]
        audio_method = params["audio_method"]
        receiver_public_key = params.get("receiver_public_key")
        expiry_option = params.get("expiry_option", "never")

        # Parse expiry option to hours (None for never)
        expiry_mapping = {
            'never': None,
            '1h': 1,
            '24h': 24,
            '7d': 168,      # 7 * 24
            '30d': 720,     # 30 * 24
            '365d': 8760    # 365 * 24
        }
        expiry_hours = expiry_mapping.get(expiry_option)

        # DEBUG: Log parameters
        print(f"[DEBUG process_audio_from_storage] img_name={img_name}")
        print(f"[DEBUG process_audio_from_storage] hash_value={hash_value}")
        print(f"[DEBUG process_audio_from_storage] audio_method={audio_method}")
        print(f"[DEBUG process_audio_from_storage] expiry_option={expiry_option}, expiry_hours={expiry_hours}")
        print(f"[DEBUG process_audio_from_storage] receiver_public_key={receiver_public_key[:20] if receiver_public_key else None}...")

        if not audio_file:
            ui.notify("Please select an audio file", type="warning")
            return

        if not os.path.exists(audio_file):
            ui.notify("Audio file not found", type="negative")
            return

        # Validate audio format
        if not is_audio(audio_file):
            ui.notify(
                "Unsupported audio format. Please select WAV, MP3, FLAC, or OGG file.",
                type="negative",
            )
            return

        # Process audio embedding
        # Handle no-expiry case (None) or convert hours to seconds
        if expiry_hours is None:
            expires_in = None  # No expiration
        else:
            expires_in = int(expiry_hours * 3600)  # Convert hours to seconds (must be int for Biscuit)
        result = await process_audio_embedding(
            img_name,
            img_path,
            hash_value,
            audio_file,
            audio_method,
            receiver_public_key,
            expires_in,
        )

        # DEBUG: Log result
        print(f"[DEBUG process_audio_from_storage] result={result}")
        if result:
            print(f"[DEBUG process_audio_from_storage] new_hash={result[0]}, output_path={result[1]}")

        if result and result[0] is not None:
            if expires_in is None:
                ui.notify("Audio embedded with permanent access token", type="positive")
            else:
                hours = expires_in / 3600
                ui.notify(f"Audio embedded with {hours:.0f}h expiry token", type="positive")
            render_gallery()
        else:
            ui.notify("Failed to embed audio", type="negative")

    except Exception as e:
        ui.notify(f"Error embedding audio: {str(e)}", type="negative")
        print(f"Audio embedding error: {e}")
    finally:
        # Clean up stored params
        if "_audio_embed_params" in app.storage.user:
            del app.storage.user["_audio_embed_params"]


def edit_audio_info_main(hash_value):
    """Edit audio information using standard dialog with process_dialog pattern."""
    edit_audio_info(hash_value, process_dialog, process_audio_from_storage, choose_files)


def play_audio_from_image(hash_value):
    """Play audio from an image with embedded audio token."""
    ui.notify("Audio playback not yet implemented", type="info")


def remove_audio_from_image(hash_value):
    """Remove audio from an image."""
    ui.notify("Audio removal not yet implemented", type="info")


def edit_video_info_main(hash_value):
    """Open video embedding dialog using standard dialog with process_dialog pattern."""
    edit_video_info(hash_value, process_dialog, process_video_from_storage, choose_files)


async def process_video_from_storage():
    """Process video embedding using params stored by edit_video_info dialog.

    Reads parameters from app.storage.user['_video_embed_params'] set by the dialog.
    """
    params = app.storage.user.get("_video_embed_params")
    if not params:
        ui.notify("No video embedding parameters found", type="negative")
        return

    try:
        img_name = params["img_name"]
        img_path = params["img_path"]
        hash_value = params["hash_value"]
        video_file = params["video_file"]
        receiver_public_key = params.get("receiver_public_key")
        expiry_option = params.get("expiry_option", "never")

        # Parse expiry option to hours (None for never)
        expiry_mapping = {
            'never': None,
            '1h': 1,
            '24h': 24,
            '7d': 168,
            '30d': 720,
            '365d': 8760
        }
        expiry_hours = expiry_mapping.get(expiry_option)

        print(f"[DEBUG process_video_from_storage] img_name={img_name}")
        print(f"[DEBUG process_video_from_storage] hash_value={hash_value}")
        print(f"[DEBUG process_video_from_storage] expiry_option={expiry_option}, expiry_hours={expiry_hours}")

        if not video_file:
            ui.notify("Please select a video file", type="warning")
            return

        if not os.path.exists(video_file):
            ui.notify("Video file not found", type="negative")
            return

        if not is_video_file_check(video_file):
            ui.notify(
                "Unsupported video format. Please select MP4, WebM, MOV, AVI, or MKV file.",
                type="negative",
            )
            return

        # Convert hours to seconds (or None for no expiry)
        if expiry_hours is None:
            expires_in = None
        else:
            expires_in = int(expiry_hours * 3600)

        result = await process_video_embedding(
            img_name,
            img_path,
            hash_value,
            video_file,
            receiver_public_key,
            expires_in,
        )

        if result and result[0] is not None:
            if expires_in is None:
                ui.notify("Video embedded with permanent access token", type="positive")
            else:
                hours = expires_in / 3600
                ui.notify(f"Video embedded with {hours:.0f}h expiry token", type="positive")
            render_gallery()
        else:
            ui.notify("Failed to embed video", type="negative")

    except Exception as e:
        ui.notify(f"Error embedding video: {str(e)}", type="negative")
        print(f"Video embedding error: {e}")
    finally:
        if "_video_embed_params" in app.storage.user:
            del app.storage.user["_video_embed_params"]


async def process_video_embedding(
    img_name,
    img_path,
    hash_value,
    video_file,
    receiver_public_key=None,
    expires_in=None,
):
    """
    Embed video into image using encrypted HVYMDataToken stored on IPFS.

    1. Create encrypted video token from video file
    2. Upload token to IPFS
    3. Embed IPFS CID in PNG tEXt chunk

    Args:
        img_name: Image name
        img_path: Image path
        hash_value: Current image hash
        video_file: Video file path
        receiver_public_key: Required — subscriber's public key
        expires_in: Token expiration time in seconds (None for no expiry)

    Returns:
        tuple: (new_hash, output_path) or (None, None) on failure
    """
    try:
        if not video_file or not os.path.exists(video_file):
            ui.notify("Video file not found", type="negative")
            return None, None

        if not is_video_file_check(video_file):
            ui.notify("Unsupported video format", type="negative")
            return None, None

        if not receiver_public_key:
            ui.notify("Receiver public key required for video token", type="negative")
            return None, None

        sender_kp = get_user_keypair(app)
        print(f"[DEBUG process_video_embedding] Creating token video image...")

        # Create token, upload to IPFS, embed CID in PNG (CPU+IO bound)
        output_path, video_cid = await run.io_bound(
            create_token_video_image,
            video_file, img_path, sender_kp, receiver_public_key,
            expires_in, _ipfs_add_pure
        )

        print(f"[DEBUG process_video_embedding] output_path={output_path}, cid={video_cid}")
        if not output_path or not video_cid:
            return None, None

        # Store locally in session temp dir
        new_hash, _, editor_url = _local_store_image_pure(output_path)
        print(f"[DEBUG process_video_embedding] new_hash={new_hash}")
        if not new_hash:
            return None, None

        # Update storage with new image info
        old_info = app.storage.user.get(hash_value, {})

        import time
        token_expires = None
        if expires_in is not None:
            token_expires = time.time() + expires_in

        new_info = {
            "name": f"video_{img_name}",
            "path": output_path,
            "editor_url": editor_url,
            "has_video": True,
            "video_method": "token",
            "video_token_cid": video_cid,
            "video_path": video_file,
            "video_token_expires": token_expires,
            "video_token_no_expiry": expires_in is None,
            # Preserve existing audio info if present
            "has_audio": old_info.get("has_audio", False),
            "audio_method": old_info.get("audio_method"),
            "audio_path": old_info.get("audio_path"),
            "image_type": old_info.get("image_type", "raw"),
        }
        app.storage.user[new_hash] = new_info
        print(f"[DEBUG process_video_embedding] Stored new_info for {new_hash}")

        # Update hash list for current state
        state_idx = app.storage.user.get("img_state", 1)
        state_names = ["raw", "processed", "aposematic", "enciphered"]
        state = state_names[state_idx - 1] if state_idx <= 4 else "raw"
        hash_list_key = f"{state}_img_hashes"

        hash_list = app.storage.user.get(hash_list_key, [])
        if hash_value in hash_list:
            idx = hash_list.index(hash_value)
            hash_list[idx] = new_hash
        else:
            hash_list.append(new_hash)
        app.storage.user[hash_list_key] = hash_list

        # Clean up old entry
        if hash_value in app.storage.user:
            del app.storage.user[hash_value]

        return new_hash, output_path

    except Exception as e:
        print(f"Error in process_video_embedding: {e}")
        ui.notify(f"Video embedding failed: {str(e)}", type="negative")
        return None, None


async def play_video_from_image(hash_value):
    """Decrypt and play video from an image with embedded video token CID.

    Fetches the encrypted token from IPFS, decrypts it server-side,
    writes to the session temp dir, and opens a video player dialog.
    """
    file_info = app.storage.user.get(hash_value, {})
    if not file_info:
        ui.notify("Image not found", type="negative")
        return

    img_path = file_info.get("path")
    video_cid = file_info.get("video_token_cid")

    if not video_cid:
        # Try extracting CID from the PNG itself
        if img_path and os.path.exists(img_path):
            from png_chunks import extract_video_token_cid
            video_cid = extract_video_token_cid(img_path)
        if not video_cid:
            ui.notify("No video token found in this image", type="warning")
            return

    ui.notify("Decrypting video...", type="info")

    try:
        receiver_kp = get_user_keypair(app)

        # Fetch from IPFS and decrypt (IO-bound)
        video_bytes, video_format, metadata = await run.io_bound(
            extract_token_video,
            img_path, receiver_kp, _ipfs_load_to_temp_file_pure, True
        )

        if not video_bytes:
            ui.notify("Failed to decrypt video — you may not be the intended recipient", type="negative")
            return

        if not video_format or video_format == 'unknown':
            video_format = 'mp4'

        # Write decrypted video to session temp dir for serving
        video_filename = f"video_{hash_value[:16]}.{video_format}"
        video_temp_path = os.path.join(EDITOR_STORAGE_DIR, video_filename)
        with open(video_temp_path, 'wb') as f:
            f.write(video_bytes)

        video_url = f"/editor/{video_filename}"

        # Build video player popup dialog
        with ui.dialog().props('maximized') as video_dialog:
            with ui.card().classes('w-full h-full items-center justify-center bg-black'):
                with ui.column().classes('items-center gap-4'):
                    video_name = ''
                    if metadata:
                        video_name = metadata.get('filename', '')
                    if video_name:
                        ui.label(video_name).classes('text-white text-lg')
                    ui.video(video_url).classes('w-full max-w-4xl').style('max-height: 80vh')
                    ui.button('Close', on_click=video_dialog.close).props('flat color=white')

        video_dialog.open()

    except Exception as e:
        print(f"Error playing video: {e}")
        ui.notify(f"Video playback failed: {str(e)}", type="negative")


async def remove_video_from_image(hash_value):
    """Remove video from an image.

    1. Unpin encrypted token from IPFS
    2. Strip video CID tEXt chunks from PNG
    3. Update metadata and refresh gallery
    """
    file_info = app.storage.user.get(hash_value, {})
    if not file_info:
        ui.notify("Image not found", type="negative")
        return

    img_path = file_info.get("path")
    video_cid = file_info.get("video_token_cid")

    if not video_cid and img_path and os.path.exists(img_path):
        from png_chunks import extract_video_token_cid
        video_cid = extract_video_token_cid(img_path)

    if not video_cid:
        ui.notify("No video found in this image", type="warning")
        return

    try:
        # Unpin token from IPFS
        if video_cid:
            await run.io_bound(ipfs_remove, video_cid)
            await run.io_bound(ipfs_gc)

        # Strip video CID chunks from the PNG
        if img_path and os.path.exists(img_path):
            await run.io_bound(
                remove_text_chunks, img_path, VIDEO_TOKEN_CID_PREFIX
            )

        # Re-store the cleaned PNG to get a new hash
        new_hash, _, editor_url = _local_store_image_pure(img_path)
        if not new_hash:
            ui.notify("Failed to update image", type="negative")
            return

        # Update metadata — remove video fields, keep everything else
        new_info = dict(file_info)
        new_info["path"] = img_path
        new_info["editor_url"] = editor_url
        new_info["has_video"] = False
        for key in ("video_method", "video_token_cid", "video_path",
                     "video_token_expires", "video_token_no_expiry"):
            new_info.pop(key, None)

        app.storage.user[new_hash] = new_info

        # Update hash list
        state_idx = app.storage.user.get("img_state", 1)
        state_names = ["raw", "processed", "aposematic", "enciphered"]
        state = state_names[state_idx - 1] if state_idx <= 4 else "raw"
        hash_list_key = f"{state}_img_hashes"

        hash_list = app.storage.user.get(hash_list_key, [])
        if hash_value in hash_list:
            idx = hash_list.index(hash_value)
            hash_list[idx] = new_hash
        app.storage.user[hash_list_key] = hash_list

        # Clean up old entry
        if hash_value != new_hash and hash_value in app.storage.user:
            del app.storage.user[hash_value]

        ui.notify("Video removed from image", type="positive")
        render_gallery()

    except Exception as e:
        print(f"Error removing video: {e}")
        ui.notify(f"Failed to remove video: {str(e)}", type="negative")


async def process_audio_embedding(
    img_name,
    img_path,
    hash_value,
    audio_file,
    audio_method="token",
    receiver_public_key=None,
    expires_in=None,
):
    """
    Embed audio into image using encrypted HVYMDataToken.

    Args:
        img_name: Image name
        img_path: Image path
        hash_value: Current image hash
        audio_file: Audio file path
        audio_method: Always 'token' (encrypted via HVYMDataToken)
        receiver_public_key: Required — subscriber's public key
        expires_in: Token expiration time in seconds (None for no expiry)

    Returns:
        tuple: (new_hash, output_path) or (None, None) on failure
    """
    try:
        # Validation
        if not audio_file or not os.path.exists(audio_file):
            ui.notify("Audio file not found", type="negative")
            return None, None

        if not is_audio_file(audio_file):
            ui.notify("Unsupported audio format", type="negative")
            return None, None

        if not receiver_public_key:
            ui.notify("Receiver public key required for audio token", type="negative")
            return None, None

        # Create encrypted audio token image
        sender_kp = get_user_keypair(app)
        print(f"[DEBUG process_audio_embedding] Creating token audio image...")
        output_path = create_token_audio_image(
            audio_file, img_path, sender_kp, receiver_public_key, expires_in
        )

        print(f"[DEBUG process_audio_embedding] output_path={output_path}")
        if not output_path:
            print(f"[DEBUG process_audio_embedding] output_path is None, returning failure")
            return None, None

        # Store locally in session temp dir (not IPFS)
        new_hash, _, editor_url = _local_store_image_pure(output_path)
        print(f"[DEBUG process_audio_embedding] new_hash={new_hash}")
        if not new_hash:
            print("[DEBUG process_audio_embedding] Failed to store image locally")
            return None, None

        # Update storage with new image info
        old_info = app.storage.user.get(hash_value, {})
        print(f"[DEBUG process_audio_embedding] old_info for {hash_value}={old_info}")

        # Calculate expiry timestamp if expires_in is set
        import time
        token_expires = None
        if expires_in is not None:
            token_expires = time.time() + expires_in

        new_info = {
            "name": f"audio_{img_name}",
            "path": output_path,
            "editor_url": editor_url,
            "has_audio": True,
            "audio_method": audio_method,
            "audio_path": audio_file,  # Set to current audio file
            "audio_format": old_info.get("audio_format"),  # [OK] PRESERVE
            "audio_duration": old_info.get("audio_duration"),  # [OK] PRESERVE
            "audio_size": old_info.get("audio_size"),  # [OK] PRESERVE
            "image_type": old_info.get("image_type", "raw"),
            "audio_token_expires": token_expires,  # None for no expiry
            "audio_token_no_expiry": expires_in is None,
        }
        app.storage.user[new_hash] = new_info
        print(f"[DEBUG process_audio_embedding] Stored new_info for {new_hash}: {new_info}")

        # Update hash list for current state
        state_idx = app.storage.user.get("img_state", 1)
        state_names = ["raw", "processed", "aposematic", "enciphered"]
        state = state_names[state_idx - 1] if state_idx <= 4 else "raw"
        hash_list_key = f"{state}_img_hashes"
        print(f"[DEBUG process_audio_embedding] state={state}, hash_list_key={hash_list_key}")

        hash_list = app.storage.user.get(hash_list_key, [])
        print(f"[DEBUG process_audio_embedding] hash_list BEFORE update: {hash_list}")
        if hash_value in hash_list:
            idx = hash_list.index(hash_value)
            hash_list[idx] = new_hash
            print(f"[DEBUG process_audio_embedding] Replaced hash at index {idx}")
        else:
            hash_list.append(new_hash)
            print(f"[DEBUG process_audio_embedding] Appended new_hash to list")
        app.storage.user[hash_list_key] = hash_list
        print(f"[DEBUG process_audio_embedding] hash_list AFTER update: {app.storage.user.get(hash_list_key)}")

        # Clean up old entry
        if hash_value in app.storage.user:
            del app.storage.user[hash_value]
            print(f"[DEBUG process_audio_embedding] Deleted old entry for {hash_value}")

        # Verify storage
        print(f"[DEBUG process_audio_embedding] VERIFY: app.storage.user[{new_hash}] = {app.storage.user.get(new_hash)}")

        return new_hash, output_path

    except Exception as e:
        print(f"Error in process_audio_embedding: {e}")
        ui.notify(f"Audio embedding failed: {str(e)}", type="negative")
        return None, None


# Check native dependencies before running the app
if __name__ in {"__main__", "__mp_main__"}:
    # Note: Dependency check will be called by NiceGUI after app initialization
    # For now, we'll allow the app to start and check on first use of features
    pass

app.on_shutdown(on_close)
ui.run(
    native=True,
    storage_secret="your-secret-key-here",  # Replace with a secure secret key in production
    favicon=os.path.join(static_dir, "icon.png"),
)
