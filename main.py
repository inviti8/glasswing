from nicegui import binding, app, ui
from nicegui.binding import BindableProperty
from fastapi.staticfiles import StaticFiles
import time
import hashlib
import multihash
import os
import base58
import tempfile
import os
from PIL import Image
import PIL.Image
from PIL.Image import UnidentifiedImageError
import requests
import wand
from hvym_stellar import  Stellar25519KeyPair, StellarSharedKeyTokenBuilder, TokenType
from stellar_sdk import Keypair
import json
from dialogs import *
from metadata import IPTC
from img_edit import *
from aiposematic import new_aposematic_img, recover_aposematic_img, SCRAMBLE_MODE
from iptcinfo3 import IPTCInfo
import exiv2
import shutil
import tempfile
import os
from datetime import datetime
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import base64

#APP NAME: Andromicae

# Configure static files directory
static_dir = os.path.join(os.path.dirname(__file__), 'static')
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
# Mount static files
app.mount('/static', StaticFiles(directory=static_dir), name='static')

_INITIALIZED = False

ipfs_endpoint = 'http://127.0.0.1'
port = '5001'
artist = 'Unknown'
watermark = False
iptc = False
access_token = ''

ipfs_webui = 'http://localhost'
ipfs_webui_port = '8080'


pintheon_endpoint = 'http://127.0.0.1'
pintheon_port = '9999'

gateway_url = ''

# Browser content globals
update_browser_content = None
pending_browser_html = None

app.native.window_args['resizable'] = True
app.native.start_args['debug'] = True
app.native.settings['ALLOW_DOWNLOADS'] = True
app.native.window_args['title'] = 'Glass Wing'
#app.native.window_args['frameless'] = True

print('^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^')
print(app.native.settings)
print('^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^')

stellar_keys = None
hvym_keys = None
hvym_public_key = None

file_container = None
state_container = None
tabs = None

PRIMARY_COLOR = '#25F5F8'
SECONDARY_COLOR = '#E59F61'
TEXT_COLOR = '#6C9D9D'
BG_COLOR = '#FBF7F4'
CARD_BG = '#E5D4C8'
BORDER_COLOR = '#FFAD20'

DARK_PRIMARY = '#578485'
DARK_SECONDARY = '#A4856A'
DARK_TEXT = '#EFF1C6'
DARK_BG = '#1A1A1A'
DARK_CARD = '#625146'
DARK_BORDER = '#EFF1C6'

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

    iptc_data = IPTC()
    iptc_data.init()
    
    data_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')
    
    if os.path.exists(data_file):
       with open(data_file, 'r') as f:
           data = json.load(f)
           # Get values from data or use defaults
           stellar_secret = data['stellar_secret']
           artist = data['artist']
           app.storage.user['use_watermark'] = data['use_watermark']
           app.storage.user['watermark'] = data['watermark']
           app.storage.user['watermark_size'] = data['watermark_size']
           app.storage.user['watermark_position'] = data['watermark_position']
           app.storage.user['watermark_padding'] = data['watermark_padding']
           app.storage.user['scramble_mode'] = data['scramble_mode']
           app.storage.user['op_string'] = data['op_string']
           app.storage.user['use_iptc'] = data['use_iptc']
           iptc_data = IPTC.from_dict(data['iptc_data'])
           iptc_data.init_storage()
           app.storage.user['tmp_files'] = data['tmp_files']
           app.storage.user['subscribers'] = data['subscribers']
           app.storage.user['subscriptions'] = data['subscriptions']
           app.storage.user['content_folders'] = data['content_folders']
           app.storage.user['app_mode'] = data['app_mode']
           app.storage.user['app_colors'] = data['app_colors']
           app.storage.user['latest_data_pod_hash'] = data.get('latest_data_pod_hash', None)
           app.storage.user['latest_gallery_html_hash'] = data.get('latest_gallery_html_hash', None)
           app.storage.user['latest_data_pod_timestamp'] = data.get('latest_data_pod_timestamp', None)
           app.storage.user['gallery_title'] = data.get('gallery_title', '')
           app.storage.user['gallery_description'] = data.get('gallery_description', '')
    else:
        persistent_save_data()
        with open(data_file, 'r') as f:
           data = json.load(f)
           stellar_secret = data['stellar_secret']
           artist = data['artist']
           app.storage.user['use_watermark'] = data['use_watermark']
           app.storage.user['watermark'] = data['watermark']
           app.storage.user['watermark_size'] = data['watermark_size']
           app.storage.user['watermark_position'] = data['watermark_position']
           app.storage.user['watermark_padding'] = data['watermark_padding']
           app.storage.user['scramble_mode'] = data['scramble_mode']
           app.storage.user['op_string'] = data['op_string']
           app.storage.user['use_iptc'] = data['use_iptc']
           iptc_data = IPTC.from_dict(data['iptc_data'])
           iptc_data.init_storage()
           app.storage.user['tmp_files'] = data['tmp_files']
           app.storage.user['subscribers'] = data['subscribers']
           app.storage.user['subscriptions'] = data['subscriptions']
           app.storage.user['content_folders'] = data['content_folders']
           app.storage.user['app_mode'] = data['app_mode']
           app.storage.user['app_colors'] = data['app_colors']
           app.storage.user['latest_data_pod_hash'] = data.get('latest_data_pod_hash', None)
           app.storage.user['latest_gallery_html_hash'] = data.get('latest_gallery_html_hash', None)
           app.storage.user['latest_data_pod_timestamp'] = data.get('latest_data_pod_timestamp', None)
           app.storage.user['gallery_title'] = data.get('gallery_title', '')
           app.storage.user['gallery_description'] = data.get('gallery_description', '')

    stellar_keys = Keypair.from_secret(stellar_secret)
    hvym_keys = Stellar25519KeyPair(stellar_keys)
    hvym_public_key = hvym_keys.public_key()

    if not ipns_folder_exists(hvym_public_key):
        ipns_new_folder(hvym_public_key)
        print(f"Created IPFS folder: {hvym_public_key}")
    else:
        print(f"IPFS folder already exists: {hvym_public_key}")

    app.storage.user['hvym_public_key'] = hvym_public_key
    app.storage.user['img_state'] = app.storage.user.get('img_state', 1)
    app.storage.user['raw_img_hashes'] = app.storage.user.get('raw_img_hashes', [])
    app.storage.user['processed_img_hashes'] = app.storage.user.get('processed_img_hashes', [])
    app.storage.user['aposematic_img_hashes'] = app.storage.user.get('aposematic_img_hashes', [])
    app.storage.user['enciphered_img_hashes'] = app.storage.user.get('enciphered_img_hashes', [])
    app.storage.user['deciphered_img_hashes'] = app.storage.user.get('decrypted_img_hashes', [])
    app.storage.user['tmp_files'] = app.storage.user.get('tmp_files', [])
    app.storage.user['recipient_public_key'] = app.storage.user.get('recipient_public_key', None)
    app.storage.user['cipher_key'] = app.storage.user.get('cipher_key', None)
    app.storage.user['app_mode'] = app.storage.user.get('app_mode', 'image')

    # Initialize IPFS data pod storage
    app.storage.user['latest_data_pod_hash'] = app.storage.user.get('latest_data_pod_hash', None)
    app.storage.user['latest_gallery_html_hash'] = app.storage.user.get('latest_gallery_html_hash', None)
    app.storage.user['latest_data_pod_timestamp'] = app.storage.user.get('latest_data_pod_timestamp', None)

    # Initialize gallery info
    app.storage.user['gallery_title'] = app.storage.user.get('gallery_title', '')
    app.storage.user['gallery_description'] = app.storage.user.get('gallery_description', '')

    PRIMARY_COLOR = app.storage.user.get('app_colors')['primary']
    SECONDARY_COLOR = app.storage.user.get('app_colors')['secondary']
    TEXT_COLOR = app.storage.user.get('app_colors')['text-color']
    BG_COLOR = app.storage.user.get('app_colors')['bg-color']
    CARD_BG = app.storage.user.get('app_colors')['card-bg']
    BORDER_COLOR = app.storage.user.get('app_colors')['border-color']

    DARK_PRIMARY = app.storage.user.get('app_colors')['dark-primary']
    DARK_SECONDARY = app.storage.user.get('app_colors')['dark-secondary']
    DARK_TEXT = app.storage.user.get('app_colors')['dark-text']
    DARK_BG = app.storage.user.get('app_colors')['dark-bg']
    DARK_CARD = app.storage.user.get('app_colors')['dark-card']
    DARK_BORDER = app.storage.user.get('app_colors')['dark-border']
    
    img_states = {1: 'raw', 2: 'processed', 3: 'aposematic', 4: 'enciphered'}
    scramble_modes = {i.value: i.name for i in SCRAMBLE_MODE}
    folder_states = {1: 'raw', 2: 'processed', 3: 'aposematic', 4: 'enciphered'}

    remove_tmp_files()

    print('!!------------------------------------!!')
    test_secret = Keypair.random().secret
    test_key = Keypair.from_secret(test_secret)
    test_keys = Stellar25519KeyPair(test_key)
    test_public_key = test_keys.public_key()
    print(test_public_key)
    print('!!------------------------------------!!')

def persistent_save_data():
    data_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.json')
    stellar_secret = app.storage.user.get('stellar_secret', Keypair.random().secret)
    app.storage.user['stellar_secret'] = stellar_secret
    artist = app.storage.user.get('artist', 'unknown')
    use_watermark = app.storage.user.get('use_watermark', False)
    watermark = app.storage.user.get('watermark', None)
    watermark_size = app.storage.user.get('watermark_size', 0.2)
    watermark_position = app.storage.user.get('watermark_position', 1)
    watermark_padding = app.storage.user.get('watermark_padding', 0.05)
    scramble_mode = app.storage.user.get('scramble_mode', 2)
    op_string = app.storage.user.get('op_string', '-^+')
    use_iptc = app.storage.user.get('use_iptc', False)
    tmp_files = app.storage.user.get('tmp_files', [])
    app.storage.user['tmp_files'] = tmp_files
    public_key = app.storage.user.get('hvym_public_key', None)
    content_folders = app.storage.user.get('content_folders', [])
    subscribers = app.storage.user.get('subscribers', [])
    subscriptions = app.storage.user.get('subscriptions', [])
    app.storage.user['content_folders'] = content_folders
    app_mode = app.storage.user.get('app_mode', 'image')
    app_colors = app.storage.user.get('app_colors', {'primary': PRIMARY_COLOR, 'secondary': SECONDARY_COLOR, 'text-color': TEXT_COLOR, 'bg-color': BG_COLOR, 'card-bg': CARD_BG, 'border-color': BORDER_COLOR, 'dark-primary': DARK_PRIMARY, 'dark-secondary': DARK_SECONDARY, 'dark-text': DARK_TEXT, 'dark-bg': DARK_BG, 'dark-card': DARK_CARD, 'dark-border': DARK_BORDER})
    latest_data_pod_hash = app.storage.user.get('latest_data_pod_hash', None)
    latest_gallery_html_hash = app.storage.user.get('latest_gallery_html_hash', None)
    latest_data_pod_timestamp = app.storage.user.get('latest_data_pod_timestamp', None)
    gallery_title = app.storage.user.get('gallery_title', '')
    gallery_description = app.storage.user.get('gallery_description', '')
    iptc_data.update_from_storage()
    print(iptc_data.to_dict())
    with open(data_file, 'w') as f:
        json.dump({ 'stellar_secret': stellar_secret, 'artist': artist, 'use_watermark': use_watermark, 'watermark': watermark, 'watermark_size': watermark_size, 'watermark_position': watermark_position, 'watermark_padding': watermark_padding, 'scramble_mode': scramble_mode, 'op_string': op_string, 'tmp_files': tmp_files, 'content_folders': content_folders, 'subscribers': subscribers, 'subscriptions': subscriptions, 'app_mode': app_mode, 'app_colors': app_colors, 'use_iptc': use_iptc, 'iptc_data': iptc_data.to_dict(), 'latest_data_pod_hash': latest_data_pod_hash, 'latest_gallery_html_hash': latest_gallery_html_hash, 'latest_data_pod_timestamp': latest_data_pod_timestamp, 'gallery_title': gallery_title, 'gallery_description': gallery_description}, f)   

def is_ipfs_running():
    try:
        response = requests.post(f'{ipfs_endpoint}:{port}/api/v0/version', timeout=5)
        return response.status_code == 200 and 'Version' in response.json()
    except (requests.exceptions.RequestException, ValueError):
        return False

def url_valid(url):
    try:
        response = requests.get(url, timeout=5)
        return response.status_code == 200
    except (requests.exceptions.RequestException, ValueError):
        return False

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
        url = f'{ipfs_endpoint}:{port}/api/v0/files/stat'
        params = {'arg': f'/{folder}'}
        response = requests.post(url, params=params, timeout=10)
        return response.status_code == 200
    except (requests.exceptions.RequestException, ValueError):
        return False

def ipns_new_folder(name):
    if not is_ipfs_running():
        print("Error: IPFS daemon is not running or not accessible")
        return False
        
    try:
        url = f'{ipfs_endpoint}:{port}/api/v0/files/mkdir'
        params = {
            'arg': f'/{name}',
            'parents': True,  # Changed from string 'true' to boolean
            'cid-version': 1  # Use CIDv1 for better compatibility
        }
        
        response = requests.post(url, params=params, timeout=30)
        response.raise_for_status()
        
        # Verify the directory was actually created
        verify_url = f'{ipfs_endpoint}:{port}/api/v0/files/stat'
        verify_params = {'arg': f'/{name}'}
        verify_response = requests.post(verify_url, params=verify_params, timeout=10)
        
        if verify_response.status_code == 200:
            content_folders = app.storage.user.get('content_folders', [])
            content_folders.append(name)
            app.storage.user['content_folders'] = content_folders
            return True
        return False
        
    except requests.exceptions.RequestException as e:
        print(f"Error creating IPFS folder: {e}")
        if hasattr(e, 'response') and e.response is not None:
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
        stat_url = f'{ipfs_endpoint}:{port}/api/v0/files/stat'
        stat_params = {'arg': f'/{name}'}
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
        list_url = f'{ipfs_endpoint}:{port}/api/v0/files/ls'
        list_params = {'arg': f'/{name}'}

        list_response = requests.post(list_url, params=list_params, timeout=10)
        list_response.raise_for_status()

        # Remove each file in the folder
        files = list_response.json().get('Entries', [])
        if not files:
            print(f"Folder /{name} is already empty")
            return True

        for file_info in files:
            if file_info['Type'] == 0:  # Regular file
                file_path = f'/{name}/{file_info["Name"]}'
                rm_url = f'{ipfs_endpoint}:{port}/api/v0/files/rm'
                rm_params = {'arg': file_path}

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
        if hasattr(e, 'response') and e.response is not None:
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
        folder = folder.strip('/')

        # Ensure folder exists, create if it doesn't
        if not ipns_ensure_folder(folder):
            print(f"Could not ensure folder /{folder} exists")
            return None
        
        # First add the file to IPFS to get its hash
        with open(file_path, 'rb') as f:
            url = f'{ipfs_endpoint}:{port}'
            files = {'file': (os.path.basename(file_path), f)}
            add_response = requests.post(f'{url}/api/v0/add', params={'no-announce': 'true'}, files=files, timeout=30)
            add_response.raise_for_status()
            add_result = add_response.json()
            hash_value = add_result.get('Hash')
            
            if not hash_value:
                print("Error: Failed to get hash from IPFS add response")
                return None
            
            # Store the file info with the hash as the key
            file_info = {
                'name': os.path.basename(file_path),
                'path': file_path,
                'ipns_path': f'/{folder}/{hash_value}',
                'extension': os.path.splitext(file_path)[1]
            }
            app.storage.user[hash_value] = file_info
            
            # Now copy the file from the IPFS repo to the MFS folder
            copy_url = f'{ipfs_endpoint}:{port}/api/v0/files/cp'
            copy_params = {
                'arg': [f'/ipfs/{hash_value}', f'/{folder}/{os.path.basename(file_path)}']
            }
            copy_response = requests.post(copy_url, params=copy_params, timeout=30)
            copy_response.raise_for_status()
            
            # Get the file stat to return some useful info
            file_path_in_ipfs = f'/{folder}/{os.path.basename(file_path)}'
            stat_params = {'arg': file_path_in_ipfs}
            stat_response = requests.post(
                f'{ipfs_endpoint}:{port}/api/v0/files/stat',
                params=stat_params,
                timeout=10
            )
            
            if stat_response.status_code == 200:
                return {
                    'hash': hash_value,
                    'path': file_path_in_ipfs,
                    'size': stat_response.json().get('Size', 0),
                    'type': 'file'
                }
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Error adding file to IPFS folder: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_msg = e.response.json()
                print(f"IPFS API error: {error_msg.get('Message', 'Unknown error')}")
            except:
                print(f"Error response: {e.response.text}")
        return None

def ipns_add_gallery_to_folder(name):
    idex = app.storage.user.get('img_state', 1)
    state = img_states[idex]
    hashes = app.storage.user.get(f'{state}_img_hashes', [])
    
    for hash_value in hashes:
        # Get the file info from storage
        file_info = app.storage.user.get(hash_value)
        if not file_info:
            print(f"No file info found for hash: {hash_value}")
            continue
            
        file_path = file_info.get('path')
        if not file_path or not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            continue
            
        # Add the file to the specified MFS folder
        result = ipns_add_to_folder(name, file_path)
        if result:
            print(f"Added {file_path} to MFS folder {name}")
        else:
            print(f"Failed to add {file_path} to MFS folder {name}")
    

def ipfs_add(file_path):
    if not is_ipfs_running():
        print("Error: IPFS daemon is not running or not accessible")
        return None
        
    try:
        with open(file_path, 'rb') as f:
            url = f'{ipfs_endpoint}:{port}'
            files = {'file': (os.path.basename(file_path), f)}
            response = requests.post(f'{url}/api/v0/add', params={'no-announce': 'true'}, files=files, timeout=30)
            response.raise_for_status()
            result = response.json()
            hash_value = result.get('Hash')
            app.storage.user[hash_value] = {'name': os.path.basename(file_path), 'path': file_path, 'ipns_path': None, 'extension': os.path.splitext(file_path)[1]}
            return hash_value
    except requests.exceptions.RequestException as e:
        print(f"Error uploading to IPFS: {e}")
        return None
    except (ValueError, KeyError) as e:
        print(f"Error processing IPFS response: {e}")
        return None

def ipfs_load_to_temp_file(hash_value, original_filename=None):
    print(hash_value)
    if not is_ipfs_running():
        print("Error: IPFS daemon is not running or not accessible")
        return None
    
    try:
        params = {'arg': hash_value}
        response = requests.post(
            f'{ipfs_webui}:{ipfs_webui_port}/ipfs/{hash_value}',
            params=params,
            timeout=30,
            stream=True
        )

        response.raise_for_status()
        
        # Create a temp directory to store the file with its original name
        temp_dir = tempfile.mkdtemp()
        file_info = app.storage.user.get(hash_value, {})
        print(file_info)
        # Use original filename if provided, otherwise use the hash
        filename = file_info.get('name', hash_value)
        temp_path = os.path.join(temp_dir, filename)
        print(temp_path)
        app.storage.user['tmp_files'].append(temp_path)
        
        # Stream the content to the file
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        # Verify the file was created and has content
        if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
            raise ValueError("Downloaded file is empty")
        
        return temp_path
        
    except Exception as e:
        print(f"Error loading from IPFS: {e}")
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.unlink(temp_path)
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            os.rmdir(temp_dir)
        return None

def ipfs_remove(hash_value):
    if not is_ipfs_running():
        print("Error: IPFS daemon is not running or not accessible")
        return None
        
    try:
        params = {'arg': hash_value}
        response = requests.post(
            f'{ipfs_endpoint}:{port}/api/v0/pin/rm',
            params=params,
            timeout=30
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
        response = requests.post(f'{ipfs_endpoint}:{port}/api/v0/repo/gc')
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError:
                # In case the response isn't JSON
                return {'status': 'success', 'message': 'Garbage collection completed'}
        else:
            error_msg = f"Error in garbage collection: {response.status_code} - {response.text}"
            print(error_msg)
            return {'status': 'error', 'message': error_msg}
    except requests.exceptions.RequestException as e:
        error_msg = f"Request failed: {str(e)}"
        print(error_msg)
        return {'status': 'error', 'message': error_msg}
    except Exception as e:
        error_msg = f"Unexpected error in garbage collection: {str(e)}"
        print(error_msg)
        return {'status': 'error', 'message': error_msg}

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
        ipfs_hash = ipfs_add(img)
        print(ipfs_hash)
        app.storage.user.get('raw_img_hashes', []).append(ipfs_hash)
        ui.notify(f'Added {img}')
    render_gallery()

async def remove_img(hash_value):
    idex = app.storage.user.get('img_state', 1)
    state = img_states[idex]
    ipfs_remove(hash_value)
    try:
        app.storage.user.get(f'{state}_img_hashes', []).remove(hash_value)
    except ValueError:
        pass  # Hash not found, that's okay
    ipfs_gc()
    ui.notify(f'Removed {hash_value}')
    render_gallery()

def copy_img(hash_value):
    ui.notify(f'Copied {hash_value}')
    ui.clipboard.write(hash_value)

def remove_tmp_files():
    if 'tmp_files' in app.storage.user:
        for file in app.storage.user['tmp_files']:
            os.remove(file)
        app.storage.user['tmp_files'] = []
    persistent_save_data()

def remove_img_by_name_from_storage(img_name, storage_key):
    if storage_key in app.storage.user:
        for hash_value in app.storage.user[storage_key]:
            img_path = app.storage.user[hash_value]['path']
            img_filename = app.storage.user[hash_value]['name']
            if img_name == img_filename:
                app.storage.user[storage_key].remove(hash_value)
                persistent_save_data()
                break        

async def choose_watermark(watermark_container):
    files = await app.native.main_window.create_file_dialog(allow_multiple=True)
    file = files[0]
    if is_image(file):
        ipfs_hash = ipfs_add(file)
        print(ipfs_hash)
        app.storage.user['watermark'] = ipfs_hash
        print(app.storage.user['watermark'])
        persistent_save_data()
        ui.notify(f'Chose {file}')
        render_watermark(watermark_container)
    else:
        ui.notify(f'{file} is not an image')

async def choose_files():
    files = await app.native.main_window.create_file_dialog(allow_multiple=True)
    return files

async def choose_file():
    file = await app.native.main_window.create_file_dialog(allow_multiple=False)
    return file

async def delete_all_metadata(hash_value):
    img_path = app.storage.user[hash_value]['path']
    img_name = app.storage.user[hash_value]['name']
    try:
        new_img_path = await clear_img_metadata(img_name, img_path)
        # Get the IPFS hash of the final image
        ipfs_hash = ipfs_add(new_img_path)
        new_img_name = app.storage.user[ipfs_hash]['name']
        idex = app.storage.user.get('img_state', 1)
        state = img_states[idex]

        app.storage.user['tmp_files'].append(new_img_path)
        ui.notify(f'Deleted all metadata from {ipfs_hash}')
        remove_img_by_name_from_storage(img_name, f'{state}_img_hashes')
        processed_hashes = app.storage.user.get(f'{state}_img_hashes', [])
            
        try:
            index = processed_hashes.index(hash_value)
            processed_hashes[index] = ipfs_hash
        except ValueError:
            processed_hashes.append(ipfs_hash)

        app.storage.user[f'{state}_img_hashes'] = processed_hashe
        # Optionally refresh the gallery to show the updated file
        render_gallery()
    except Exception as e:
        ui.notify(f"Error deleting metadata: {str(e)}", type='negative')

async def edit_exif_info(hash_value):
    img_path = app.storage.user[hash_value]['path']
    img_name = app.storage.user[hash_value]['name']
    try:
        metadata = await get_exif_metadata(img_path)
        await edit_metadata_dialog(img_path, metadata, process_metadata, img_name, img_path, hash_value)
        
    except Exception as e:
        ui.notify(f"Error loading XMP data: {str(e)}", type='negative')
        print(f"Error in edit_xmp_info: {str(e)}")
        import traceback
        traceback.print_exc()

async def edit_xmp_info(hash_value):
    img_path = app.storage.user[hash_value]['path']
    img_name = app.storage.user[hash_value]['name']
    try:
        metadata = await get_xmp_metadata(img_path)
        await edit_metadata_dialog(img_path, metadata, process_metadata, img_name, img_path, hash_value)
        
    except Exception as e:
        ui.notify(f"Error loading XMP data: {str(e)}", type='negative')
        print(f"Error in edit_xmp_info: {str(e)}")
        import traceback
        traceback.print_exc()

async def edit_iptc_info(hash_value):
    img_path = app.storage.user[hash_value]['path']
    img_name = app.storage.user[hash_value]['name']
    try:
        metadata = await get_iptc_metadata(img_path)
        await edit_metadata_dialog(img_path, metadata, process_metadata, img_name, img_path, hash_value)
        
    except Exception as e:
        ui.notify(f"Error loading IPTC data: {str(e)}", type='negative')
        print(f"Error in edit_iptc_info: {str(e)}")
        import traceback
        traceback.print_exc()

async def edit_all_info(hash_value):
    img_path = app.storage.user[hash_value]['path']
    img_name = app.storage.user[hash_value]['name']
    try:
        metadata = await get_img_metadata(img_path)
        await edit_metadata_dialog(img_path, metadata, process_metadata, img_name, img_path, hash_value)
        
    except Exception as e:
        ui.notify(f"Error loading IPTC data: {str(e)}", type='negative')
        print(f"Error in edit_iptc_info: {str(e)}")
        import traceback
        traceback.print_exc()

async def process_body_text(img_name, img_path, hash_value, txt, data_type):
    # Create a new dictionary with just the fields we want to update
    metadata_changes = {}
    
    if data_type == 'IPTC':
        metadata_changes['IPTC:Caption-Abstract'] = txt
    elif data_type == 'XMP':
        metadata_changes['XMP:Description'] = txt
    
    print(f"Updating {data_type} with changes: {metadata_changes}")
    
    await process_metadata(img_name, img_path, hash_value, metadata_changes)
    

async def edit_body_text(hash_value):
    img_path = app.storage.user[hash_value]['path']
    img_name = app.storage.user[hash_value]['name']
    await add_body_text_dialog(img_name, img_path, hash_value, process_body_text)
    

async def process_metadata(img_name, img_path, hash_value, metadata):
    try:
        # Process with new IPTC data
        final_path = await new_iptc_img(img_name, img_path, metadata)
            
        # Get the IPFS hash of the final image
        ipfs_hash = ipfs_add(final_path)
        app.storage.user['tmp_files'].append(final_path)
        
        # Update the UI and storage
        if ipfs_hash and ipfs_hash != hash_value:
            im_name = app.storage.user[ipfs_hash]['name']
            idex = app.storage.user.get('img_state', 1)
            state = img_states[idex]

            if state == 'raw':
                state = 'processed'

            remove_img_by_name_from_storage(im_name, f'{state}_img_hashes')
            processed_hashes = app.storage.user.get(f'{state}_img_hashes', [])
            
            try:
                index = processed_hashes.index(hash_value)
                processed_hashes[index] = ipfs_hash
            except ValueError:
                processed_hashes.append(ipfs_hash)

            app.storage.user[f'{state}_img_hashes'] = processed_hashes
            
            ui.notify(f'Edited {ipfs_hash}')
            render_gallery()
            
        return ipfs_hash, final_path  # Return both the hash and the path
            
    except Exception as e:
        ui.notify(f'Error processing image: {str(e)}', type='negative')
        raise

async def process_watermarking():
    use_watermark = app.storage.user.get('use_watermark', False)
    watermark = app.storage.user.get('watermark', None)

    if not use_watermark or not watermark:
        ui.notify('Watermarking is disabled')
        return

    app.storage.user.get('processed_img_hashes', []).clear()
    for hash_value in app.storage.user.get('raw_img_hashes', []):
        img_path = app.storage.user[hash_value]['path']
        img_name = app.storage.user[hash_value]['name']
        size = app.storage.user.get('watermark_size', 0.2)
        pos_idx = app.storage.user.get('watermark_position', 1)
        pos = WATERMARK_POSITIONS[pos_idx]
        print(img_name)
        watermark_path = ipfs_load_to_temp_file(app.storage.user['watermark'])
        processed_img_path = await new_watermarked_img(img_name, img_path, watermark_path, size, pos)
        print('------------------------------------')
        print(processed_img_path)
        print('------------------------------------')
        ipfs_hash = ipfs_add(processed_img_path)
        app.storage.user.get('processed_img_hashes', []).append(ipfs_hash)
        ui.notify(f'Processed {hash_value}')
    persistent_save_data()
    render_gallery()

def get_scramble_mode():
    mode = app.storage.user.get('scramble_mode', 2)
    if mode == 1:
        return SCRAMBLE_MODE.BUTTERFLY
    elif mode == 2:
        return SCRAMBLE_MODE.BUTTERFLY
    elif mode == 3:
        return SCRAMBLE_MODE.QR

async def process_aposematic():
    app.storage.user.get('aposematic_img_hashes', []).clear()
    for hash_value in app.storage.user.get('processed_img_hashes', []):
        img_path = app.storage.user[hash_value]['path']
        img_name = app.storage.user[hash_value]['name']
        aposematic = new_aposematic_img(
            img_path,
            cipher_key=app.storage.user['cipher_key'],
            op_string= app.storage.user.get('op_string', '-^+'),
            scramble_mode=get_scramble_mode()
        )
        print(aposematic)
        aposematic_img_path = aposematic['img_path']
        ipfs_hash = ipfs_add(aposematic_img_path)
        app.storage.user.get('aposematic_img_hashes', []).append(ipfs_hash)
        ui.notify(f'Processed {hash_value}')
    persistent_save_data()
    render_gallery()

async def process_enciphering():
    app.storage.user.get('enciphered_img_hashes', []).clear()
    for hash_value in app.storage.user.get('processed_img_hashes', []):
        img_path = app.storage.user[hash_value]['path']
        img_name = app.storage.user[hash_value]['name']
        enciphered_img_path = await new_enciphered_img(img_name, img_path, app.storage.user['cipher_key'])
        ipfs_hash = ipfs_add(enciphered_img_path)
        app.storage.user.get('enciphered_img_hashes', []).append(ipfs_hash)
        ui.notify(f'Enciphered {hash_value}')
    persistent_save_data()
    render_gallery()

async def process_deciphering():
    app.storage.user.get('deciphered_img_hashes', []).clear()
    for hash_value in app.storage.user.get('enciphered_img_hashes', []):
        img_path = app.storage.user[hash_value]['path']
        deciphered_img_path = await new_deciphered_img(img_path, app.storage.user['cipher_key'])
        ipfs_hash = ipfs_add(deciphered_img_path)
        app.storage.user.get('deciphered_img_hashes', []).append(ipfs_hash)
        ui.notify(f'Deciphered {hash_value}')
    persistent_save_data()
    render_gallery()

async def process_shared_iptc_metadata():
    app.storage.user.get('processed_img_hashes', []).clear()
    for hash_value in app.storage.user.get('raw_img_hashes', []):
        img_path = app.storage.user[hash_value]['path']
        img_name = app.storage.user[hash_value]['name']
        iptc_img_path = await new_iptc_img(img_name, img_path, iptc_data.to_exif_dict())
        ipfs_hash = ipfs_add(iptc_img_path)
        app.storage.user.get('processed_img_hashes', []).append(ipfs_hash)
        ui.notify(f'Processed {hash_value}')
    persistent_save_data()
    render_gallery()

async def process_debug_deploy_gallery():
    try:
        # Get the current gallery state
        idex = app.storage.user.get('img_state', 1)
        state = img_states[idex]

        # Create the NINJS data pod using the existing function
        output_path = await create_ninjs_data_pod(state)

        ipns_clean_folder(state)
        ipns_add_gallery_to_folder(state)

        if output_path:
            ui.notify(f'Successfully created data pod at: {output_path}')

            # Load the created JSON data pod
            with open(output_path, 'r', encoding='utf-8') as f:
                data_pod = json.load(f)

            # Set up Jinja2 environment
            template_dir = os.path.join(os.path.dirname(__file__), 'templates')
            jinja_env = Environment(loader=FileSystemLoader(template_dir))
            template = jinja_env.get_template('gallery.html')

            # Render the template with the data pod and gateway configuration
            template_context = {
                'data_pod': data_pod,
                'ipfs_gateway': f"{ipfs_webui}:{ipfs_webui_port}",
                'ipfs_webui': ipfs_webui,
                'ipfs_webui_port': ipfs_webui_port,
                'gallery_title': app.storage.user.get('gallery_title', ''),
                'gallery_description': app.storage.user.get('gallery_description', '')
            }
            html_content = template.render(**template_context)

            # Save the rendered HTML to temp file then add to IPFS
            timestamp = app.storage.user.get('latest_data_pod_timestamp', datetime.now().strftime("%Y%m%d_%H%M%S"))
            html_temp_path = os.path.join(tempfile.gettempdir(), f"ninjs_data_pod_{timestamp}.html")
            with open(html_temp_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            # Add HTML to IPFS
            html_hash = ipfs_add(html_temp_path)
            if html_hash:
                app.storage.user['latest_gallery_html_hash'] = html_hash
                app.storage.user['tmp_files'].append(html_temp_path)
                print(f"Saved rendered HTML to IPFS: {html_hash}")
                ui.notify(f'Gallery HTML saved to IPFS: {html_hash}', type='positive')
            else:
                print(f"Failed to add HTML to IPFS, saved locally at: {html_temp_path}")
                ui.notify('Failed to add HTML to IPFS', type='warning')

            # Store the HTML content and switch to BROWSER tab
            global pending_browser_html, tabs
            pending_browser_html = html_content
            print(f"Stored pending HTML content, length: {len(html_content)}")

            # Switch to BROWSER tab
            if tabs:
                tabs.value = 'BROWSER'
                print("Switched to BROWSER tab")

                # Use timer to load content after tab panel is rendered
                def load_gallery_content():
                    global pending_browser_html
                    if update_browser_content and pending_browser_html:
                        print(f"Timer loading gallery content, length: {len(pending_browser_html)}")
                        update_browser_content(pending_browser_html)
                        pending_browser_html = None  # Clear after loading
                        ui.notify('Gallery rendered in browser view', type='positive')
                        print("Gallery content loaded successfully")
                    else:
                        print(f"Timer check failed: update_browser_content={update_browser_content is not None}, pending_browser_html={pending_browser_html is not None}")

                # Give the tab panel time to render in the DOM
                ui.timer(0.5, load_gallery_content, once=True)
            else:
                ui.notify('Browser tab not initialized', type='warning')
                print("tabs object not available")

            # Optionally, you can also deploy the data pod
            # Uncomment the following lines if you want to deploy automatically
            # deployment_result = await deploy_ninjs_data_pod(state)
            # if deployment_result and deployment_result.get('success'):
            #     ui.notify('Successfully deployed data pod to gallery')
            # else:
            #     ui.notify('Failed to deploy data pod', type='warning')
        else:
            ui.notify('No valid images found to create data pods', type='warning')

    except Exception as e:
        ui.notify(f'Error processing gallery: {str(e)}', type='negative')
        print(f"Error in process_debug_deploy_gallery: {str(e)}")
        import traceback
        traceback.print_exc()

def add_subscriber(name, public_key):
    subscribers = app.storage.user.get('subscribers', [])
    subscribers.append({'name': name, 'public_key': public_key})
    app.storage.user['subscribers'] = subscribers
    persistent_save_data()   

async def remove_subscriber(name):
    subscribers = app.storage.user.get('subscribers', [])
    subscribers = [s for s in subscribers if s['name'] != name]
    app.storage.user['subscribers'] = subscribers
    persistent_save_data()

async def get_subscribers():
    return app.storage.user.get('subscribers', [])

async def add_subscription(name, public_key):
    subscriptions = app.storage.user.get('subscriptions', [])
    subscriptions.append({'name': name, 'public_key': public_key})
    app.storage.user['subscriptions'] = subscriptions
    persistent_save_data()
    ui.notify(f'Added subscription for {name}')

async def remove_subscription(name):
    subscriptions = app.storage.user.get('subscriptions', [])
    subscriptions = [s for s in subscribers if s['name'] != name]
    app.storage.user['subscriptions'] = subscribers
    persistent_save_data()
    ui.notify(f'Removed subscription for {name}')

async def get_subscriptions():
    return app.storage.user.get('subscriptions', [])    

async def load_iptc_template():
    try:
        file_path = await choose_file()
        if file_path:
            with open(file_path[0], 'r') as f:
                iptc_data = json.load(f)
            app.storage.user['iptc_data'] = iptc_data
            persistent_save_data()
            ui.notify('IPTC Template loaded successfully')
    except Exception as e:
        ui.notify(f'Error loading IPTC template: {str(e)}', type='negative')

def save_iptc_template():
    try:
        ui.download.content(json.dumps(iptc_data.to_dict()), 'iptc_template.json')
    except Exception as e:
        ui.notify(f'Error saving IPTC template: {str(e)}', type='negative')

def render_state(hashes):
    idex = app.storage.user.get('img_state', 1)
    state = img_states[idex]
    if file_container and state_container:
        state_container.clear()
        with state_container:
            ui.chip(f'{state} ({len(hashes)})', icon='view_array')

def render_gallery(folder=None):
    # tabs.set_value('IMAGES')
    idex = app.storage.user.get('img_state', 1)
    state = img_states[idex]
    hashes = app.storage.user.get(f'{state}_img_hashes', [])

    render_state(hashes)

    if file_container:
        file_container.clear()
        with file_container:
            #ui.chip(f'{state} ({len(hashes)})', icon='view_array')
            
            for hash_value in hashes:
                # Create a card to contain the image and FAB
                with ui.card().classes('relative overflow-visible w-full max-w-2xl mx-auto'):
                    
                    file_info = app.storage.user.get(hash_value, {})
                    img_url = f'{ipfs_webui}:{ipfs_webui_port}/ipfs/{hash_value}'
                    if folder:
                        img_url = f'{ipfs_webui}:{ipfs_webui_port}/ipfs/{folder}/{hash_value}'
                    img_container = ui.image(img_url).classes('w-full')
                    
                    # FAB container positioned absolutely over the image
                    ui.chip(file_info.get('name', 'Unknown'), icon='image', color='white').props('square').classes('absolute top-2 left-2 z-10')
                    with ui.row().classes('absolute top-2 right-2 z-10'):
                        with ui.fab('edit', direction='left').classes('q-secondary-color'):
                            if is_ipfs_running():
                                ui.fab_action('copy_all', on_click=lambda h=hash_value: copy_img(h)).tooltip('Copy image')
                            if is_ipfs_running():
                                ui.fab_action('article', on_click=lambda h=hash_value: edit_body_text(h)).tooltip('Edit body text')
                            if is_ipfs_running():
                                ui.fab_action('delete', on_click=lambda h=hash_value: remove_img(h), color='negative').tooltip('Delete image')
                        with ui.fab('data_object', direction='left').classes('q-secondary-color'):
                            if is_ipfs_running():
                                ui.fab_action('edit', label='ALL', on_click=lambda h=hash_value: edit_all_info(h)).tooltip('Edit all metadata')
                                ui.fab_action('edit', label='IPTC', on_click=lambda h=hash_value: edit_iptc_info(h)).tooltip('Edit IPTC metadata')
                                ui.fab_action('edit', label='XMP', on_click=lambda h=hash_value: edit_xmp_info(h)).tooltip('Edit XMP metadata')
                                ui.fab_action('edit', label='EXIF', on_click=lambda h=hash_value: edit_exif_info(h)).tooltip('Edit EXIF metadata')
                                ui.fab_action('delete', label='ALL', on_click=lambda h=hash_value: remove_img(h), color='negative').tooltip('Delete metadata')
                # Add some spacing between cards
                ui.space().classes('h-4')
                
def render_watermark(watermark_container):
    if watermark_container:
        watermark_container.clear()
        with watermark_container:
            ui.image(f'{ipfs_webui}:{ipfs_webui_port}/ipfs/{app.storage.user.get("watermark", "")}').classes('w-full')

def setup_browser_tab():
    if browser_content:
        with browser_content:
            # Minimal iframe structure - no wrapper div
            iframe = ui.html('''
                <iframe
                    id="browser-frame"
                    style="width: 100%; height: 100%; min-height: 100vh; border: none; margin: 0; padding: 0; display: block;"
                    srcdoc="<html><body style='margin:0;padding:0;overflow:hidden;background:transparent;'></body></html>"
                ></iframe>
            ''', sanitize=lambda x: x).style('width: 100%; height: 100%; min-height: 100vh; margin: 0; padding: 0; display: block;')
            
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
                    encoded_html = base64.b64encode(html_content.encode('utf-8')).decode('ascii')
                    js = f"""
                        (function updateIframe() {{
                            console.log('Looking for iframe #browser-frame...');
                            const iframe = document.querySelector('#browser-frame');
                            console.log('iframe element:', iframe);

                            if (iframe) {{
                                console.log('Found iframe, decoding and setting content...');
                                const encodedHtml = '{encoded_html}';
                                const decodedHtml = atob(encodedHtml);
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
                                        const decodedHtml = atob(encodedHtml);
                                        retryIframe.srcdoc = decodedHtml;
                                        console.log('✓ Iframe srcdoc set on retry');
                                    }} else {{
                                        console.error('✗ Iframe still not found. User may need to switch to BROWSER tab first.');
                                    }}
                                }}, 500);
                            }}
                        }})();
                    """
                    print(f"Updating iframe with base64 encoded HTML, original length: {len(html_content)}")
                    ui.run_javascript(js)
            
            return update_browser_content


def safe_get(metadata, key, default=''):
    """Safely get a value from metadata with a default fallback."""
    return metadata.get(key, default)

def safe_list_from_metadata(metadata, key, separator='|'):
    """
    Safely convert metadata field to a list.
    Handles both string (with separator) and already-list values.
    """
    value = safe_get(metadata, key, '')
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
        return 'image/jpeg'
    ext = os.path.splitext(file_path)[1].lower()
    return {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.tiff': 'image/tiff',
        '.webp': 'image/webp',
    }.get(ext, 'application/octet-stream')

async def create_ninjs_data_pod(prefix='processed'):
    try:
        # Get all processed images
        processed_hashes = app.storage.user.get(f'{prefix}_img_hashes', [])
        if not processed_hashes:
            ui.notify('No processed images found', type='warning')
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
                    
                img_path = img_info.get('path')
                if not img_path or not os.path.exists(img_path):
                    print(f"Warning: Image file not found: {img_path}")
                    error_count += 1
                    continue
                
                # Get metadata using existing function
                try:
                    metadata_list = await get_img_metadata(img_path)
                    if not metadata_list or not isinstance(metadata_list, list) or not metadata_list[0]:
                        print(f"Warning: No metadata found for {img_path}")
                        error_count += 1
                        continue
                    metadata = metadata_list[0]
                except Exception as e:
                    print(f"Error getting metadata for {img_path}: {str(e)}")
                    error_count += 1
                    continue
                
                # Build news item with safe defaults
                data_item = {
                    "uri": f"{app.storage.user.get('gateway_url', '')}:{img_hash}",
                    "type": "picture",
                    "version": "1.0",
                    "versioncreated": datetime.utcnow().isoformat() + "Z",
                    "firstcreated": safe_get(metadata, 'XMP:CreateDate', ''),
                    "pubstatus": "usable",
                    "language": "en",
                    "headline": safe_get(metadata, 'IPTC:ObjectName', 'Untitled'),
                    "description_text": safe_get(metadata, 'IPTC:Caption-Abstract', ''),
                    "keywords": safe_list_from_metadata(metadata, 'IPTC:Keywords'),
                    "copyrightnotice": safe_get(metadata, 'IPTC:CopyrightNotice', ''),
                    "creditline": safe_get(metadata, 'IPTC:Credit', ''),
                    "byline": safe_list_from_metadata(metadata, 'IPTC:By-line'),
                }
                
                # Add renditions with proper MIME type and dimensions
                width, height = parse_dimensions(safe_get(metadata, 'Composite:ImageSize'))
                mimetype = get_mimetype(img_path)

                # Use the IPFS gateway URL for browser access
                # This allows the HTML to display images when loaded in a browser
                gateway_base = f"{ipfs_webui}:{ipfs_webui_port}"
                renditions = {
                    "original": {
                        "href": f"{gateway_base}/ipfs/{img_hash}",
                        "ipfs_hash": img_hash,  # Store the hash separately for reference
                        "mimetype": mimetype,
                    }
                }
                if width and height:
                    renditions["original"]["width"] = width
                    renditions["original"]["height"] = height
                data_item["renditions"] = renditions
                
                # Add place information if available
                city = safe_get(metadata, 'IPTC:City')
                country = safe_get(metadata, 'IPTC:Country-PrimaryLocationName')
                if city or country:
                    data_item["place"] = [{"name": city, "country": country}]
                
                # Add usage terms if available
                if usage_terms := safe_get(metadata, 'XMP:UsageTerms'):
                    data_item["usageterms"] = usage_terms
                
                # Add rights info
                data_item["rightsinfo"] = {
                    "langid": "http://www.lexvo.org/page/iso639-3/eng",
                    "usagetypes": ["publish", "archive"]
                }
                
                # Add data mining constraints if present
                if constraints := safe_get(metadata, 'XMP:OtherConstraints'):
                    data_item["restrictions"] = {
                        "type": "restricted",
                        "constraints": [constraints] if isinstance(constraints, str) else constraints
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
            ui.notify('No valid news items to export', type='warning')
            return

        # Create NINJ package
        ninj_package = {
            "version": "1.0",
            "uri": f"urn:newsml:package:{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
            "type": "package",
            "versioncreated": datetime.utcnow().isoformat() + "Z",
            "language": "en",
            "items": data_items
        }

        # Save to temp file then add to IPFS
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_path = os.path.join(tempfile.gettempdir(), f"ninjs_data_pod_{timestamp}.json")

        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(ninj_package, f, indent=2, ensure_ascii=False)

        # Add to IPFS
        json_hash = ipfs_add(temp_path)
        if not json_hash:
            ui.notify('Failed to add data pod to IPFS', type='negative')
            return None

        # Store the hash for later retrieval
        app.storage.user['latest_data_pod_hash'] = json_hash
        app.storage.user['latest_data_pod_timestamp'] = timestamp
        app.storage.user['tmp_files'].append(temp_path)

        ui.notify(f"Successfully exported {len(data_items)} items to IPFS: {json_hash}")
        return temp_path
        
    except Exception as e:
        ui.notify(f"Error creating NINJ package: {str(e)}", type='negative')
        raise

async def deploy_ninjs_data_pod(prefix='processed', access_token: Optional[str] = None) -> Dict[str, Any]:
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
            ui.notify('Failed to create NINJS data pod', type='negative')
            return {'status': 'error', 'message': 'Failed to create NINJS data pod'}
    except Exception as e:
        ui.notify(f'Error creating NINJS data pod: {str(e)}', type='negative')
        return {'status': 'error', 'message': str(e)}
    
    # Get access token if not provided
    if not access_token:
        access_token = app.storage.user.get('api_access_token')
        if not access_token:
            ui.notify('No access token provided', type='negative')
            return {'status': 'error', 'message': 'No access token provided'}
    
    # Prepare the upload URL
    upload_url = f"{app.storage.user.get('api_base_url', '')}/api_upload"
    if not upload_url.startswith('http'):
        ui.notify('Invalid API base URL', type='negative')
        return {'status': 'error', 'message': 'Invalid API base URL'}
    
    try:
        # Prepare the file for upload
        with open(json_file, 'rb') as f:
            files = {
                'file': (os.path.basename(json_file), f, 'application/json')
            }
            data = {
                'access_token': access_token,
                'encrypted': 'false'  # Set to 'true' if encryption is needed
            }
            
            # Make the request
            response = requests.post(
                upload_url,
                files=files,
                data=data,
                timeout=30  # 30 seconds timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                ui.notify('Successfully deployed NINJS data pod', type='positive')
                return {
                    'status': 'success',
                    'file_info': result,
                    'path': json_file
                }
            else:
                error_msg = f'Upload failed with status {response.status_code}: {response.text}'
                ui.notify(error_msg, type='negative')
                return {
                    'status': 'error',
                    'message': error_msg,
                    'status_code': response.status_code
                }
                
    except Exception as e:
        error_msg = f'Error uploading NINJS data pod: {str(e)}'
        ui.notify(error_msg, type='negative')
        return {
            'status': 'error',
            'message': error_msg
        }
    


async def deploy_gallery_images(prefix: str = 'processed', access_token: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Upload all images to the gallery API endpoint.
    
    Args:
        prefix: The prefix for the image hashes in storage (e.g., 'processed', 'original')
        access_token: Optional access token for the API. If not provided, will try to get from app storage.
    
    Returns:
        List of upload results with status and file information.
    """
    if not access_token:
        access_token = app.storage.user.get('api_access_token')
        if not access_token:
            ui.notify('No access token provided', type='negative')
            return []
    
    hashes = app.storage.user.get(f'{prefix}_img_hashes', [])
    if not hashes:
        ui.notify(f'No images found with prefix: {prefix}', type='warning')
        return []
    
    upload_url = f"{app.storage.user.get('api_base_url', '')}/api_upload"
    if not upload_url.startswith('http'):
        ui.notify('Invalid API base URL', type='negative')
        return []
    
    results = []
    successful_uploads = 0
    
    for img_hash in hashes:
        try:
            img_info = app.storage.user.get(img_hash)
            if not img_info:
                results.append({
                    'status': 'error',
                    'hash': img_hash,
                    'message': 'Image info not found'
                })
                continue
                
            img_path = img_info.get('path')
            if not img_path or not os.path.exists(img_path):
                results.append({
                    'status': 'error',
                    'hash': img_hash,
                    'message': f'Image file not found: {img_path}'
                })
                continue
            
            # Prepare the file for upload
            with open(img_path, 'rb') as img_file:
                files = {
                    'file': (os.path.basename(img_path), img_file, 'image/jpeg')
                }
                data = {
                    'access_token': access_token,
                    'encrypted': 'false'  # Set to 'true' if encryption is needed
                }
                
                # Make the request
                response = requests.post(
                    upload_url,
                    files=files,
                    data=data,
                    timeout=30  # 30 seconds timeout
                )
                
                if response.status_code == 200:
                    result = response.json()
                    results.append({
                        'status': 'success',
                        'hash': img_hash,
                        'file_info': result,
                        'path': img_path
                    })
                    successful_uploads += 1
                else:
                    results.append({
                        'status': 'error',
                        'hash': img_hash,
                        'message': f'Upload failed with status {response.status_code}',
                        'response': response.text
                    })
                    
        except Exception as e:
            results.append({
                'status': 'error',
                'hash': img_hash,
                'message': str(e)
            })
            continue
    
    # Notify user of results
    total = len(hashes)
    if successful_uploads == total:
        ui.notify(f'Successfully uploaded all {successful_uploads} images', type='positive')
    elif successful_uploads > 0:
        ui.notify(f'Uploaded {successful_uploads} of {total} images', type='warning')
    else:
        ui.notify('Failed to upload any images', type='negative')
    
    return results

async def fadeout_element(element):
    element.style('opacity: 0; transition: opacity 0.25s ease-out;')
    await asyncio.sleep(0.25)
    element.visible = False

async def fadein_element(element):
    element.visible = True
    # Set initial state (invisible)
    element.style('opacity: 0;')
    # Force reflow
    await asyncio.sleep(0.01)
    # Apply transition and trigger fade in
    element.style('opacity: 1; transition: opacity 0.25s ease-in;')
    await asyncio.sleep(0.25)

async def fade_swap_elements(elem1, elem2):
    await fadeout_element(elem1)
    await fadein_element(elem2)

def toggle_app_mode():
    current_mode = app.storage.user.get('app_mode', 'image')
    new_mode = 'browser' if current_mode == 'image' else 'image'
    app.storage.user['app_mode'] = new_mode
    persistent_save_data()

def on_close():
    print('Closing')
    # remove_tmp_files()

def close_app():
    ui.notify('Closing')
    remove_tmp_files()
    app.shutdown()
    
@ui.page('/')
def main_page():
    # Add Lottie player script to the head
    ui.add_head_html('''
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
    ''')
    logo_anim = '/static/logo.json'

    ui.add_css(f"""
        :root {{
            --primary-color: {PRIMARY_COLOR};
            --secondary-color: {SECONDARY_COLOR};
            --text-color: {TEXT_COLOR};
            --bg-color: {BG_COLOR};
            --card-bg: {CARD_BG};
            --border-color: {BORDER_COLOR};
        }}

        @media (prefers-color-scheme: dark) {{
            :root {{
                --primary-color: {DARK_PRIMARY};
                --secondary-color: {DARK_SECONDARY};
                --text-color: {DARK_TEXT};
                --bg-color: {DARK_BG};
                --card-bg: {DARK_CARD};
                --border-color: {DARK_BORDER};
            }}
        }}

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
            .q-card, .q-dialog, .q-menu, .q-tooltip {{
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
            ui.timer(0.01, lambda: [
                header.classes(replace='row items-center justify-between p-0 gradient-background transition-all duration-300 transform translate-y-0'),
                footer.classes(replace='gradient-background transition-all duration-300 transform translate-y-0')
            ], once=True)
        else:
            # Apply transform to hide
            header.classes(replace='row items-center justify-between p-0 gradient-background transition-all duration-300 transform -translate-y-full')
            footer.classes(replace='gradient-background transition-all duration-300 transform translate-y-full')
            # Hide after animation completes
            ui.timer(300, lambda: [setattr(header, 'visible', False), setattr(footer, 'visible', False)], once=True)

    async def on_tab_change():
        global pending_browser_html
        print(tabs.value)
        if tabs.value == 'IMAGES' and app.storage.user.get('app_mode') != 'image':
            toggle_app_mode()
            await fade_swap_elements(browser_ctrls, editor_ctrls)
            await fade_swap_elements(browser_content, file_container)
            editor_settings.visible = True
            browser_settings.visible = False
        elif tabs.value == 'BROWSER' and app.storage.user.get('app_mode') != 'browser':
            toggle_app_mode()
            await fade_swap_elements(editor_ctrls, browser_ctrls)
            await fade_swap_elements(file_container, browser_content)
            editor_settings.visible = False
            browser_settings.visible = True

        # Load pending browser content if available (regardless of mode change)
        if tabs.value == 'BROWSER' and pending_browser_html and update_browser_content:
            print(f"Loading pending HTML content into iframe, length: {len(pending_browser_html)}")
            # Use a small delay to ensure the iframe is fully rendered in the DOM
            import asyncio
            await asyncio.sleep(0.5)
            update_browser_content(pending_browser_html)
            pending_browser_html = None  # Clear after loading
            print("Pending HTML loaded and cleared")


    with ui.header().classes('row items-center justify-between p-0 gradient-background transition-all duration-300 transform') as header:
        # Left side: Tabs
        global tabs
        with ui.row().classes('items-center'):
            with ui.tabs().on('update:model-value', on_tab_change) as tabs:
                ui.tab('IMAGES', icon="image")
                ui.tab('BROWSER', icon="web")
                ui.tab('SETTINGS', icon="settings")
                
            state_container = ui.row().classes('items-center')
        
        # Right side: Lottie animation and close button
        with ui.row().classes('items-center gap-2 pr-2'):
            ui.html(f'''
                <lottie-player 
                    src="{logo_anim}" 
                    loop 
                    autoplay 
                    style="width: 192px; height: 96px;"
                ></lottie-player>
            ''', sanitize=False)
            # ui.button(icon='close', on_click=close_app).classes('outline q-secondary-color').props('flat')

    # Add a floating button to toggle header/footer visibility
    fab = ui.button(icon='visibility', color='primary').classes('fixed-bottom-right q-mb-xl q-mr-xl shadow-5')
    fab.style('z-index: 9999; width: 56px; height: 56px; border-radius: 50%;')
    fab.on('click', toggle_header_footer)
    
    with ui.footer().classes('gradient-background transition-all duration-300 transform') as footer:
        with ui.card().classes('w-full card-no-border') as editor_ctrls:
            with ui.fab('image').classes('q-secondary-color'):
                if is_ipfs_running():
                    ui.fab_action('info', on_click=gallery_info_dialog).tooltip('Set Gallery Info')
                    ui.fab_action('add_photo_alternate', on_click=choose_img).tooltip('Choose images')
                    ui.fab_action('person_add', on_click=lambda: add_subscriber_dialog(add_subscriber)).tooltip('Add Subscriber')
                    ui.fab_action('approval', on_click=lambda: process_dialog(process_watermarking)).tooltip('Add watermark to images')
                    ui.fab_action('dataset', on_click=lambda: assign_iptc_dialog(process_dialog, process_shared_iptc_metadata)).tooltip('Assign Shared IPTC metadata')
                    ui.fab_action('emoji_nature', on_click=lambda: aposematic_dialog(process_dialog, process_aposematic)).tooltip('Create Aposematic images')
                    ui.fab_action('lock', on_click=lambda: cipher_dialog(process_dialog, process_enciphering)).tooltip('Encipher images')
                    # ui.fab_action('lock_open', on_click=lambda: process_dialog(process_deciphering))
                    ui.fab_action('cloud_upload', on_click=lambda: ui.notify('Upload to IPFS')).tooltip('Deploy to Pintheon')
                    ui.fab_action('drive_folder_upload', on_click=lambda: process_dialog(process_debug_deploy_gallery)).tooltip('Local Debug')
            ui.toggle(img_states, on_change=render_gallery).bind_value(app.storage.user, 'img_state')
        with ui.card().classes('w-full card-no-border') as browser_ctrls:
            with ui.fab('web_stories').classes('q-secondary-color'):
                if is_ipfs_running():
                    ui.fab_action('subscriptions', on_click=choose_img)
                    ui.fab_action('add', on_click=choose_img)


    with ui.tab_panels(tabs, value='IMAGES').classes('w-full h-full') as tab_panel:
        with ui.tab_panel('IMAGES'):
            with ui.column().classes('w-full gap-2'):
                # Show warnings if services are not available
                if not is_ipfs_running():
                    ui.notify('IPFS is not running', type='warning')
                if not is_imagemagick_available():
                    ui.notify('ImageMagick is not available', type='warning')
                
                # Main Image File content
                global file_container
                file_container = ui.column().classes('w-full')
                render_gallery()

        # In your tab panel initialization:
        with ui.tab_panel('BROWSER'):
            global browser_content, update_browser_content
            # Use minimal structure with explicit height
            browser_content = ui.element().style('width: 100%; height: 100%; min-height: 100vh;')

            # Set up the browser tab and get the update function
            update_func = setup_browser_tab()
            update_browser_content = update_func

            # Initialize with empty iframe
            if update_browser_content:
                update_browser_content()  # This will clear/initialize the iframe
                print(f"Browser tab initialized, update_browser_content is: {type(update_browser_content)}")

        with ui.tab_panel('SETTINGS'):
            with ui.card().classes('w-full card-no-border') as editor_settings:
                ui.label('editor settings').classes('text-md font-medium')
                with ui.grid(columns=2).classes('w-full'):
                    # Left column
                    with ui.column().classes('w-full gap-1'):
                        # IPFS WebUI Card
                        with ui.card().classes('w-full'):
                            with ui.expansion('IPFS').classes('w-full'):
                                with ui.row().classes('w-full items-end gap-2'):
                                    ui.input('WebUI URL', value=ipfs_webui).bind_value(app.storage.user, 'ipfs_webui').classes('grow')
                                    ui.input('Port', value=ipfs_webui_port).bind_value(app.storage.user, 'ipfs_webui_port').classes('w-30')
                                with ui.row().classes('w-full items-end gap-2'):
                                    ui.input('API URL', value=ipfs_endpoint).bind_value(app.storage.user, 'ipfs_endpoint').classes('grow')
                                    ui.input('Port', value=port).bind_value(app.storage.user, 'port').classes('w-30')
                        with ui.card().classes('w-full'):
                            with ui.expansion('Pintheon').classes('w-full'):
                                with ui.row().classes('w-full items-end gap-2'):
                                    ui.input('Gateway', value=gateway_url).bind_value(app.storage.user, 'gateway_url').classes('grow')
                                with ui.row().classes('w-full items-end gap-2'):
                                    ui.input('Local API', value=pintheon_endpoint).bind_value(app.storage.user, 'pintheon_endpoint').classes('grow')
                                    ui.input('Port', value=pintheon_port).bind_value(app.storage.user, 'pintheon_port').classes('w-30')
                                ui.textarea('access token').classes('w-full') \
                                .bind_value(app.storage.user, 'access_token')
                    
                    # Right column
                    with ui.column().classes('w-full gap-1'):
                        use_watermark = app.storage.user.get('use_watermark', False)
                        # Metadata Settings Card
                        with ui.card().classes('w-full'):
                            with ui.expansion('Metadata').classes('w-full'):
                                with ui.row().classes('w-full items-center'):
                                    ui.input('Artist', value=artist).bind_value(app.storage.user, 'artist').on_value_change(persistent_save_data).classes('w-full')
                                    with ui.expansion('Stamp', icon='approval').classes('w-full'):
                                        w_switch = ui.switch('Stamp', value=use_watermark).bind_value(app.storage.user, 'use_watermark').on_value_change(persistent_save_data)
                                        watermark_size = app.storage.user.get('watermark_size', 0.2)
                                        with ui.row().classes('w-full items-center').bind_visibility_from(w_switch, 'value'):
                                            ui.label('Size').classes('text-md font-small')
                                            w_size = ui.slider(min=0.01, max=1.0, step=0.01, value=watermark_size).classes('w-1/2').bind_value(app.storage.user, 'watermark_size').on_value_change(persistent_save_data)
                                        with ui.row().classes('w-full items-center').bind_visibility_from(w_switch, 'value'):
                                            ui.label('Padding').classes('text-md font-small')
                                            w_padding = app.storage.user.get('watermark_padding', 0.05)
                                            w_pad = ui.slider(min=0.0, max=0.25, step=0.01, value=w_padding).classes('w-1/2').bind_value(app.storage.user, 'watermark_padding').on_value_change(persistent_save_data)
                                        with ui.row().classes('w-full items-center').bind_visibility_from(w_switch, 'value'):
                                            ui.label('Position').classes('text-md font-small')
                                            w_position = app.storage.user.get('watermark_position', 1)
                                            w_pos = ui.select(WATERMARK_POSITIONS, value=w_position).classes('grow').bind_value(app.storage.user, 'watermark_position').on_value_change(persistent_save_data)
                                        with ui.row().classes('w-full'):
                                            w_img = app.storage.user.get('watermark', None)
                                            with ui.row().classes('w-1/4').bind_visibility_from(w_switch, 'value') as watermark_container:
                                                if w_img:
                                                    print(w_img)
                                                    url = f'{ipfs_webui}:{ipfs_webui_port}/ipfs/{w_img}'
                                                    if url_valid(url):
                                                        render_watermark(watermark_container)
                                            w_upload = ui.button('Watermark', 
                                                            on_click=lambda: choose_watermark(watermark_container),
                                                            icon='upload'
                                                        ).bind_visibility_from(w_switch, 'value')

                                with ui.expansion('Shared IPTC Metadata', icon='data_array').classes('w-full'):
                                    iptc_switch = ui.switch('IPTC Metadata', value=iptc).bind_value(app.storage.user, 'iptc').on_value_change(persistent_save_data)
                                    with ui.row().classes('w-full items-center'):
                                        ui.button('Set Shared IPTC Metadata', icon='perm_data_setting', on_click=lambda: iptc_dialog(iptc_data, persistent_save_data)) \
                                        .bind_visibility_from(iptc_switch, 'value')
                                    with ui.row().classes('w-full items-center').bind_visibility_from(iptc_switch, 'value'):
                                        ui.label('Template IPTC Fields')
                                        ui.button('Load Template', icon='download', on_click=lambda: load_iptc_template()).props('flat')
                                        ui.button('Save Template', icon='save', on_click=lambda: save_iptc_template()).props('flat')
                        
                        # Additional settings can be added here
                        with ui.card().classes('w-full'):
                            with ui.expansion('App Data').classes('w-full'):
                                with ui.row().classes('w-full items-center'):
                                    key_input = ui.input('App Key', value=hvym_public_key).bind_value(app.storage.user, 'hvym_public_key').classes('grow').props('disable')
                                    ui.button(icon='copy_all', on_click=lambda: [ui.clipboard.write(hvym_public_key), ui.notify('Copied App Key')]) \
                                        .classes('w-10').props('flat color=primary')

                                with ui.row().classes('w-full items-center'):

                                    secret_input = ui.input('App Secret', value=stellar_secret, password=True) \
                                        .bind_value(app.storage.user, 'stellar_secret').classes('grow').props('disable')
                                    ui.button(icon='copy_all', on_click=lambda: [ui.clipboard.write(stellar_secret), ui.notify('Copied App Secret')]) \
                                        .classes('w-10').props('flat color=primary')

                        with ui.card().classes('w-full') as app_colors_card:
                            with ui.expansion('App Colors').classes('w-full'):
                                app_colors = app.storage.user.get('app_colors', {
                                    'primary': PRIMARY_COLOR,
                                    'secondary': SECONDARY_COLOR,
                                    'text-color': TEXT_COLOR,
                                    'bg-color': BG_COLOR,
                                    'card-bg': CARD_BG,
                                    'border-color': BORDER_COLOR,
                                    'dark-primary': DARK_PRIMARY,
                                    'dark-secondary': DARK_SECONDARY,
                                    'dark-text': DARK_TEXT,
                                    'dark-bg': DARK_BG,
                                    'dark-card': DARK_CARD,
                                    'dark-border': DARK_BORDER
                                })
                                with ui.card().classes('w-full') as light_colors:
                                    ui.label('light').classes('text-md font-medium')
                                    with ui.row().classes('w-full items-center'):
                                        for key, value in app_colors.items():
                                            if 'dark' not in key:
                                                with ui.button().classes('no-underline pallete-btn') as btn:
                                                    btn._props['no-caps'] = True
                                                    btn._props['flat'] = True
                                                    btn.style(f'background-color: {value} !important;')
                                                    def update_btn_color(e, b=btn):
                                                        b.style(f'background-color: {e.color} !important;')
                                                    color_picker = ui.color_picker(on_pick=update_btn_color)
                                                    color_picker.value = value
                                                    color_picker.on('update:model-value', lambda e, k=key: app_colors.update({k: color_picker.value}))
                                                    color_picker.on_value_change(persistent_save_data)
                                with ui.card().classes('w-full') as dark_colors:
                                    ui.label('dark').classes('text-md font-medium')
                                    with ui.row().classes('w-full items-center'):
                                        for key, value in app_colors.items():
                                            if 'dark' in key:
                                                with ui.button().classes('no-underline pallete-btn') as btn:
                                                    btn._props['no-caps'] = True
                                                    btn._props['flat'] = True
                                                    btn.style(f'background-color: {value} !important;')
                                                    def update_btn_color(e, b=btn):
                                                        b.style(f'background-color: {e.color} !important;')
                                                    color_picker = ui.color_picker(on_pick=update_btn_color)
                                                    color_picker.value = value
                                                    color_picker.on('update:model-value', lambda e, k=key: app_colors.update({k: color_picker.value}))
                                                    color_picker.on_value_change(persistent_save_data)
                                #TODO: NEED TO FIX LOGIC FOR UPDATING APP COLORS
                                app_colors_card.visible = False
                                dark_colors.visible = False
                                light_colors.visible = False
                                # if ui.dark_mode:
                                #     dark_colors.visible = True
                                #     light_colors.visible = False
                                # else:
                                #     dark_colors.visible = False
                                #     light_colors.visible = True
                                        
                                    

            with ui.card().classes('w-full card-no-border') as browser_settings:
                ui.label('browser settings').classes('text-md font-medium')
                with ui.grid(columns=2).classes('w-full'):
                    # Left column
                    with ui.column().classes('w-full gap-1'):
                        with ui.card().classes('w-full'):
                            ui.label('browser settings').classes('text-md font-medium')
                            

        with ui.tab_panel('BROWSER'):
            global content_container
            content_container = ui.column().classes('w-full')

    print(app.storage.user.get('app_mode'))
    print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
    
    if app.storage.user.get('app_mode') == 'browser':
        tab_panel.set_value('BROWSER')
        editor_ctrls.visible = True
        editor_settings.visible = True
        browser_ctrls.visible = False
        browser_settings.visible = False
    else:
        tab_panel.set_value('IMAGES')
        editor_ctrls.visible = True
        editor_settings.visible = True
        browser_ctrls.visible = False
        browser_settings.visible = False


app.on_shutdown(on_close)
ui.run(
    native=True,
    storage_secret='your-secret-key-here'  # Replace with a secure secret key in production
)