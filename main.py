from nicegui import binding, app, ui
from nicegui.binding import BindableProperty
import time
import hashlib
import multihash
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

app.native.window_args['resizable'] = True
app.native.start_args['debug'] = False
app.native.settings['ALLOW_DOWNLOADS'] = True
app.native.window_args['title'] = 'Glass Wing'
app.native.window_args['frameless'] = True

print('^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^')
print(app.native.settings)
print('^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^')

stellar_keys = None
hvym_keys = None
hvym_public_key = None

file_container = None 
state_container = None

def init():
    global _INITIALIZED
    if _INITIALIZED:
        return
    global file_container
    global state_container
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
    global img_states
    global tmp_files
    global scramble_modes
    global tabs

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

    stellar_keys = Keypair.from_secret(stellar_secret)
    hvym_keys = Stellar25519KeyPair(stellar_keys)
    hvym_public_key = hvym_keys.public_key()

    app.storage.user['img_state'] = app.storage.user.get('img_state', 1)
    app.storage.user['raw_img_hashes'] = app.storage.user.get('raw_img_hashes', [])
    app.storage.user['processed_img_hashes'] = app.storage.user.get('processed_img_hashes', [])
    app.storage.user['aposematic_img_hashes'] = app.storage.user.get('aposematic_img_hashes', [])
    app.storage.user['enciphered_img_hashes'] = app.storage.user.get('enciphered_img_hashes', [])
    app.storage.user['deciphered_img_hashes'] = app.storage.user.get('decrypted_img_hashes', [])
    app.storage.user['tmp_files'] = app.storage.user.get('tmp_files', [])
    app.storage.user['recipient_public_key'] = app.storage.user.get('recipient_public_key', None)
    app.storage.user['cipher_key'] = app.storage.user.get('cipher_key', None)

    img_states = {1: 'raw', 2: 'processed', 3: 'aposematic', 4: 'enciphered'}
    scramble_modes = {i.value: i.name for i in SCRAMBLE_MODE}

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
    iptc_data.update_from_storage()
    print(iptc_data.to_dict())
    with open(data_file, 'w') as f:
        json.dump({ 'stellar_secret': stellar_secret, 'artist': artist, 'use_watermark': use_watermark, 'watermark': watermark, 'watermark_size': watermark_size, 'watermark_position': watermark_position, 'watermark_padding': watermark_padding, 'scramble_mode': scramble_mode, 'op_string': op_string, 'tmp_files': tmp_files, 'use_iptc': use_iptc, 'iptc_data': iptc_data.to_dict()}, f)   

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
            app.storage.user[hash_value] = {'name': os.path.basename(file_path), 'path': file_path, 'extension': os.path.splitext(file_path)[1]}
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
    files = await choose_file()
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

async def choose_file():
    files = await app.native.main_window.create_file_dialog(allow_multiple=True)
    # tabs.set_value('IMAGES')
    return files

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

def render_state(hashes):
    idex = app.storage.user.get('img_state', 1)
    state = img_states[idex]
    if file_container and state_container:
        state_container.clear()
        with state_container:
            ui.chip(f'{state} ({len(hashes)})', icon='view_array')

def render_gallery():
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
                    img_container = ui.image(f'{ipfs_webui}:{ipfs_webui_port}/ipfs/{hash_value}').classes('w-full')
                    
                    # FAB container positioned absolutely over the image
                    ui.chip(file_info.get('name', 'Unknown'), icon='image', color='white').props('square').classes('absolute top-2 left-2 z-10')
                    with ui.row().classes('absolute top-2 right-2 z-10'):
                        with ui.fab('edit', direction='left', color='primary'):
                            if is_ipfs_running():
                                ui.fab_action('copy_all', on_click=lambda h=hash_value: copy_img(h))
                            if is_ipfs_running():
                                ui.fab_action('delete', on_click=lambda h=hash_value: remove_img(h), color='negative')
                        with ui.fab('data_object', direction='left', color='primary'):
                            if is_ipfs_running():
                                ui.fab_action('edit', label='ALL', on_click=lambda h=hash_value: edit_all_info(h))
                                ui.fab_action('edit', label='IPTC', on_click=lambda h=hash_value: edit_iptc_info(h))
                                ui.fab_action('edit', label='XMP', on_click=lambda h=hash_value: edit_xmp_info(h))
                                ui.fab_action('edit', label='EXIF', on_click=lambda h=hash_value: edit_exif_info(h))
                                ui.fab_action('delete', label='ALL', on_click=lambda h=hash_value: remove_img(h), color='negative')
                # Add some spacing between cards
                ui.space().classes('h-4')
                
def render_watermark(watermark_container):
    if watermark_container:
        watermark_container.clear()
        with watermark_container:
            ui.image(f'{ipfs_webui}:{ipfs_webui_port}/ipfs/{app.storage.user.get("watermark", "")}').classes('w-full')

def on_close():
    print('Closing')
    # remove_tmp_files()

def close_app():
    ui.notify('Closing')
    remove_tmp_files()
    app.shutdown()
    
@ui.page('/')
def main_page():

    init()

    with ui.header().classes('row items-center justify-between p-0') as header:
        with ui.row().classes('w-full justify-end'):
            ui.button(icon='close', on_click=close_app).classes('outline').props('fab')
        with ui.row().classes('w-full items-center'):
            with ui.tabs() as tabs:
                ui.tab('IMAGES', icon="image")
                # ui.tab('LAYO.classes('items-center gap-2 pr-2'):UT', icon="grid_view")
                ui.tab('SETTINGS', icon="settings")
            state_container = ui.row().classes('w-full items-center')

    with ui.footer() as footer:
        
        with ui.fab('image'):
            if is_ipfs_running():
                ui.fab_action('add', on_click=choose_img)
                ui.fab_action('approval', on_click=lambda: process_dialog(process_watermarking))
                ui.fab_action('dataset', on_click=lambda: assign_iptc_dialog(process_dialog, process_shared_iptc_metadata))
                ui.fab_action('emoji_nature', on_click=lambda: aposematic_dialog(process_dialog, process_aposematic))
                ui.fab_action('lock', on_click=lambda: cipher_dialog(process_dialog, process_enciphering))
                ui.fab_action('lock_open', on_click=lambda: process_dialog(process_deciphering))
                ui.fab_action('perm_media', on_click=lambda: ui.notify('Rocket'))
        ui.toggle(img_states, on_change=render_gallery).bind_value(app.storage.user, 'img_state')


    with ui.tab_panels(tabs, value='IMAGES').classes('w-full'):
        with ui.tab_panel('IMAGES'):
            with ui.column().classes('w-full gap-2'):
                # Show warnings if services are not available
                if not is_ipfs_running():
                    ui.notify('IPFS is not running', type='warning')
                if not is_imagemagick_available():
                    ui.notify('ImageMagick is not available', type='warning')
                
                # Main content
                global file_container
                file_container = ui.column().classes('w-full')
                render_gallery()

        with ui.tab_panel('SETTINGS'):
            with ui.grid(columns=2).classes('w-full'):
                # Left column
                with ui.column().classes('w-full gap-1'):
                    # IPFS WebUI Card
                    with ui.card().classes('w-full'):
                        ui.label('IPFS').classes('text-md font-medium')
                        with ui.row().classes('w-full items-end gap-2'):
                            ui.input('WebUI URL', value=ipfs_webui).bind_value(app.storage.user, 'ipfs_webui').classes('grow')
                            ui.input('Port', value=ipfs_webui_port).bind_value(app.storage.user, 'ipfs_webui_port').classes('w-30')
                        with ui.row().classes('w-full items-end gap-2'):
                            ui.input('API URL', value=ipfs_endpoint).bind_value(app.storage.user, 'ipfs_endpoint').classes('grow')
                            ui.input('Port', value=port).bind_value(app.storage.user, 'port').classes('w-30')
                    with ui.card().classes('w-full'):
                        ui.label('Pintheon').classes('text-md font-medium')
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
                        ui.label('Metadata').classes('text-md font-medium')
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

                            with ui.expansion('IPTC', icon='data_array').classes('w-full'):
                                iptc_switch = ui.switch('IPTC Metadata', value=iptc).bind_value(app.storage.user, 'iptc').on_value_change(persistent_save_data)
                                ui.button('Set Shared IPTC Metadata', icon='perm_data_setting', on_click=lambda: iptc_dialog(iptc_data, persistent_save_data)) \
                                .bind_visibility_from(iptc_switch, 'value')
                    
                    # Additional settings can be added here
                    with ui.card().classes('w-full'):
                        ui.label('App Data').classes('text-md font-medium')
                        with ui.row().classes('w-full items-center'):
                            key_input = ui.input('App Key', value=hvym_public_key).bind_value(app.storage.user, 'hvym_public_key').classes('grow').props('disable')
                            ui.button(icon='copy_all', on_click=lambda: [ui.clipboard.write(hvym_public_key), ui.notify('Copied App Key')]) \
                                .classes('w-10').props('flat color=primary')

                        with ui.row().classes('w-full items-center'):

                            secret_input = ui.input('App Secret', value=stellar_secret, password=True) \
                                .bind_value(app.storage.user, 'stellar_secret').classes('grow').props('disable')
                            ui.button(icon='copy_all', on_click=lambda: [ui.clipboard.write(stellar_secret), ui.notify('Copied App Secret')]) \
                                .classes('w-10').props('flat color=primary')

app.on_shutdown(on_close)
ui.run(
    native=True,
    storage_secret='your-secret-key-here'  # Replace with a secure secret key in production
)