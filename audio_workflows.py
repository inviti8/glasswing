"""
Enhanced Audio Embedding Workflows with Token Support

🎯 CRITICAL: This follows ENCRYPTION.md patterns for audio token sharing
- Integrates with existing process_audio_embedding function
- Adds token-based sharing options for aposematic/enciphered workflows
- Maintains image type tracking throughout processing
"""

import os
import time
import base64
from typing import Optional, Tuple, Dict, Any, List

from audio_tokens import (
    create_audio_token,
    create_shared_audio_image,
    get_current_user_stellar_keypair,
    get_current_user_stellar_public_key,
    detect_audio_format,
    extract_token_from_png,
    extract_audio_from_token
)

# Import from main.py to avoid circular imports
def get_audio_functions():
    """Get audio functions from main module to avoid circular imports"""
    import main
    return {
        'create_audio_image': main.create_audio_image,
        'extract_audio_from_image': main.extract_audio_from_image,
        'download_ipfs_image': getattr(main, 'download_ipfs_image', None),
        'new_deciphered_img': getattr(main, 'new_deciphered_img', None),
        'recover_aposematic_img': getattr(main, 'recover_aposematic_img', None),
        'image_to_base64_uri': getattr(main, 'image_to_base64_uri', None)
    }


async def process_audio_embedding_with_tokens(
    app, img_name: str, img_path: str, hash_value: str, 
    audio_file: str, audio_method: str = 'metadata',
    receiver_public_key: Optional[str] = None,
    expires_in: int = 3600
) -> Tuple[Optional[str], Optional[str]]:
    """
    Enhanced audio embedding with token support
    
    Args:
        app: NiceGUI app instance
        img_name: Original image name
        img_path: Original image path
        hash_value: Original image hash
        audio_file: Audio file path
        audio_method: 'metadata' or 'token'
        receiver_public_key: Required for token method
        expires_in: Token expiration time
        
    Returns:
        tuple: (new_hash, output_path)
    """
    try:
        if not audio_file:
            app.storage.user['notification'] = {
                'type': 'warning',
                'message': 'Please select an audio file'
            }
            return None, None
        
        if not os.path.exists(audio_file):
            app.storage.user['notification'] = {
                'type': 'error',
                'message': 'Audio file not found'
            }
            return None, None
        
        # Validate audio format
        file_ext = os.path.splitext(audio_file)[1].lower()
        supported_formats = ['.wav', '.mp3', '.flac', '.ogg']
        if file_ext not in supported_formats:
            app.storage.user['notification'] = {
                'type': 'error',
                'message': f'Unsupported audio format: {file_ext}'
            }
            return None, None
        
        # Validate token method requirements
        if audio_method == 'token' and not receiver_public_key:
            app.storage.user['notification'] = {
                'type': 'error',
                'message': 'Receiver public key required for token-based sharing'
            }
            return None, None
        
        app.storage.user['notification'] = {
            'type': 'info',
            'message': f'Processing audio embedding ({audio_method} method)...'
        }
        
        # Create audio image based on method
        if audio_method == 'token':
            # Token-based sharing: create encrypted token
            output_path = await create_token_audio_image(
                app, audio_file, img_path, receiver_public_key, expires_in
            )
        else:
            # Standard metadata embedding - always use original image as cover
            audio_funcs = get_audio_functions()
            create_audio_image = audio_funcs['create_audio_image']
            
            # Always use original image as cover (no spectrogram generation)
            if img_path and os.path.exists(img_path):
                output_path = create_audio_image(audio_file, img_path)
            else:
                # Fallback: create simple placeholder if no image provided
                from PIL import Image, ImageDraw, ImageFont
                img = Image.new('RGB', (800, 600), color='#25F5F8')
                draw = ImageDraw.Draw(img)
                
                try:
                    font = ImageFont.truetype("arial.ttf", 40)
                except:
                    font = ImageFont.load_default()
                
                draw.text((400, 300), "🎵 Audio Embedded", fill='white', anchor='mm', font=font)
                
                temp_path = f'{os.path.splitext(audio_file)[0]}_audio.png'
                img.save(temp_path, 'PNG')
                output_path = temp_path
        
        # Extract audio data for metadata
        audio_funcs = get_audio_functions()
        extract_audio_from_image = audio_funcs['extract_audio_from_image']
        audio_data, audio_format = extract_audio_from_image(output_path)
        
        # Get current processing state
        idex = app.storage.user.get('img_state', 1)
        state = ['raw', 'processed', 'aposematic', 'enciphered'][idex - 1] if idex <= 4 else 'raw'
        
        # Determine image type
        image_type = determine_image_type_for_state(state)
        
        # Update storage with comprehensive metadata
        storage_update = {
            'path': output_path,
            'has_audio': True,
            'audio_path': audio_file,
            'audio_format': audio_format,
            'audio_duration': len(audio_data) / 44100 if audio_data else 0,
            'audio_size': len(audio_data) if audio_data else 0,
            'audio_method': audio_method,
            'image_type': image_type,  # CRITICAL: Track image type
            f'is_{image_type}': True,  # Legacy flag support
        }
        
        # Add token-specific metadata
        if audio_method == 'token':
            storage_update.update({
                'receiver_public_key': receiver_public_key,
                'audio_token_expires': time.time() + expires_in,
                'share_audio': True  # Enable sharing for token-based audio
            })
        
        # Get IPFS hash
        from main import ipfs_add
        new_hash = ipfs_add(output_path)
        app.storage.user['tmp_files'].append(output_path)
        
        # Update storage based on current state
        await update_storage_for_audio_image(
            app, img_name, hash_value, new_hash, output_path, 
            storage_update, audio_file, audio_format, audio_data, state
        )
        
        app.storage.user['notification'] = {
            'type': 'success',
            'message': f'Audio embedded ({audio_method}): {new_hash}'
        }
        
        # Trigger gallery refresh
        if hasattr(app, 'render_gallery'):
            app.render_gallery()
        
        return new_hash, output_path
        
    except Exception as e:
        app.storage.user['notification'] = {
            'type': 'error',
            'message': f'Error processing audio: {str(e)}'
        }
        print(f"Error in process_audio_embedding_with_tokens: {e}")
        return None, None


async def create_token_audio_image(
    app, audio_file: str, img_path: str, 
    receiver_public_key: str, expires_in: int
) -> str:
    """
    Create audio image with encrypted token
    
    Args:
        app: NiceGUI app instance
        audio_file: Audio file path
        img_path: Base image path
        receiver_public_key: Receiver's public key
        expires_in: Token expiration time
        
    Returns:
        str: Path to created audio image with token
    """
    # Get sender's keypair
    sender_kp = get_current_user_stellar_keypair(app)
    
    # Create shared audio image with encrypted token
    output_path = create_shared_audio_image(
        audio_file=audio_file,
        image_file=img_path,
        sender_kp=sender_kp,
        receiver_kp_public=receiver_public_key,
        expires_in=expires_in
    )
    
    print(f"✅ Created token-based audio image: {output_path}")
    return output_path


def determine_image_type_for_state(state: str) -> str:
    """
    Determine image type from processing state
    
    Args:
        state: Current processing state
        
    Returns:
        str: Image type ('raw', 'processed', 'aposematic', 'enciphered')
    """
    state_mapping = {
        'raw': 'raw',
        'processed': 'processed', 
        'aposematic': 'aposematic',
        'enciphered': 'enciphered'
    }
    return state_mapping.get(state, 'raw')


async def update_storage_for_audio_image(
    app, img_name: str, hash_value: str, new_hash: str, 
    output_path: str, storage_update: Dict[str, Any],
    audio_file: str, audio_format: str, audio_data: bytes, state: str
) -> None:
    """
    Update storage for audio image based on processing state
    
    Args:
        app: NiceGUI app instance
        img_name: Original image name
        hash_value: Original hash
        new_hash: New hash for audio image
        output_path: Output path
        storage_update: Metadata to store
        audio_file: Audio file path
        audio_format: Audio format
        audio_data: Audio data
        state: Processing state
    """
    if state == 'raw':
        # Update raw_img_hashes
        raw_hashes = app.storage.user.get('raw_img_hashes', [])
        
        try:
            # Find and update existing hash entry
            index = raw_hashes.index(hash_value)
            raw_hashes[index] = new_hash
            app.storage.user['raw_img_hashes'] = raw_hashes
            
            # Update storage to point to audio version
            app.storage.user[new_hash] = app.storage.user[hash_value].copy()
            app.storage.user[new_hash].update(storage_update)
            app.storage.user[new_hash].update({
                'name': f'audio_{img_name}',
            })
            
            # Remove old hash entry
            del app.storage.user[hash_value]
            
        except ValueError:
            # Fallback: add to raw hashes if not found
            raw_hashes.append(new_hash)
            app.storage.user['raw_img_hashes'] = raw_hashes
            app.storage.user[new_hash] = storage_update.copy()
            app.storage.user[new_hash]['name'] = f'audio_{img_name}'
    
    else:
        # For non-raw states, update state-specific hash list
        from main import remove_img_by_name_from_storage
        remove_img_by_name_from_storage(img_name, f'{state}_img_hashes')
        
        processed_hashes = app.storage.user.get(f'{state}_img_hashes', [])
        
        try:
            index = processed_hashes.index(hash_value)
            processed_hashes[index] = new_hash
        except ValueError:
            processed_hashes.append(new_hash)
        
        app.storage.user[f'{state}_img_hashes'] = processed_hashes
        app.storage.user[new_hash] = storage_update.copy()
        app.storage.user[new_hash]['name'] = f'audio_{img_name}'


async def process_aposematic_with_shared_audio(
    app, processed_hashes: list, cipher_key: str
) -> None:
    """
    Process aposematic images with shared audio tokens
    
    Args:
        app: NiceGUI app instance
        processed_hashes: List of processed image hashes
        cipher_key: Cipher key for aposematic processing
    """
    from aiposematic import new_aposematic_img
    from main import ipfs_add
    
    for hash_value in processed_hashes:
        img_info = app.storage.user.get(hash_value)
        
        if not img_info or not img_info.get('has_audio'):
            continue
        
        # Check if audio sharing is enabled
        if not img_info.get('share_audio', False):
            continue
        
        audio_path = img_info.get('audio_path')
        receiver_public = img_info.get('receiver_public_key')
        
        if not audio_path or not receiver_public:
            continue
        
        try:
            # Get sender's wrapped keypair
            sender_kp = get_current_user_stellar_keypair(app)
            
            # Create aposematic image with audio token
            aposematic_result = new_aposematic_img_with_audio_token(
                img_path=img_info.get('path'),
                audio_file=audio_path,
                sender_kp=sender_kp,
                receiver_kp_public=receiver_public,
                cipher_key=cipher_key,
                expires_in=app.storage.user.get('audio_token_expiry', 3600)
            )
            
            # Update storage with token-based audio and CRITICAL image type
            new_hash = ipfs_add(aposematic_result)
            app.storage.user[new_hash] = app.storage.user[hash_value].copy()
            app.storage.user[new_hash].update({
                'path': aposematic_result,
                'has_audio': True,
                'audio_method': 'token',
                'audio_token_expires': time.time() + 3600,
                'receiver_public_key': receiver_public,
                'image_type': 'aposematic',  # CRITICAL: Track image type
                'is_aposematic': True  # Legacy flag support
            })
            
            # Update aposematic hash list
            aposematic_hashes = app.storage.user.get('aposematic_img_hashes', [])
            try:
                index = aposematic_hashes.index(hash_value)
                aposematic_hashes[index] = new_hash
            except ValueError:
                aposematic_hashes.append(new_hash)
            
            app.storage.user['aposematic_img_hashes'] = aposematic_hashes
            
            print(f"✅ Created aposematic image with audio token: {new_hash}")
            
        except Exception as e:
            print(f"❌ Error creating aposematic audio image: {e}")


async def process_enciphering_with_shared_audio(
    app, processed_hashes: list, cipher_key: str
) -> None:
    """
    Process enciphered images with shared audio tokens
    
    Args:
        app: NiceGUI app instance
        processed_hashes: List of processed image hashes
        cipher_key: Cipher key for enciphering
    """
    from img_edit import new_enciphered_img
    from main import ipfs_add
    
    for hash_value in processed_hashes:
        img_info = app.storage.user.get(hash_value)
        
        if not img_info or not img_info.get('has_audio'):
            continue
        
        # Check if audio sharing is enabled
        if not img_info.get('share_audio', False):
            continue
        
        audio_path = img_info.get('audio_path')
        receiver_public = img_info.get('receiver_public_key')
        
        if not audio_path or not receiver_public:
            continue
        
        try:
            # Get sender's wrapped keypair
            sender_kp = get_current_user_stellar_keypair(app)
            
            # Create enciphered image with audio token
            enciphered_result = new_enciphered_img_with_audio_token(
                img_path=img_info.get('path'),
                audio_file=audio_path,
                sender_kp=sender_kp,
                receiver_kp_public=receiver_public,
                cipher_key=cipher_key,
                expires_in=app.storage.user.get('audio_token_expiry', 3600)
            )
            
            # Update storage with CRITICAL image type
            new_hash = ipfs_add(enciphered_result)
            app.storage.user[new_hash] = app.storage.user[hash_value].copy()
            app.storage.user[new_hash].update({
                'path': enciphered_result,
                'has_audio': True,
                'audio_method': 'token',
                'audio_token_expires': time.time() + 3600,
                'receiver_public_key': receiver_public,
                'image_type': 'enciphered',  # CRITICAL: Track image type
                'is_enciphered': True  # Legacy flag support
            })
            
            # Update enciphered hash list
            enciphered_hashes = app.storage.user.get('enciphered_img_hashes', [])
            try:
                index = enciphered_hashes.index(hash_value)
                enciphered_hashes[index] = new_hash
            except ValueError:
                enciphered_hashes.append(new_hash)
            
            app.storage.user['enciphered_img_hashes'] = enciphered_hashes
            
            print(f"✅ Created enciphered image with audio token: {new_hash}")
            
        except Exception as e:
            print(f"❌ Error creating enciphered audio image: {e}")


# Helper functions for aposematic/enciphering with audio tokens
async def new_aposematic_img_with_audio_token(
    img_path: str, audio_file: str, sender_kp, receiver_kp_public: str,
    cipher_key: str, expires_in: int
) -> str:
    """
    Create aposematic image with embedded audio token
    
    This is a placeholder - actual implementation would integrate with aiposematic
    """
    # For now, create token-based audio image then apply aposematic
    from aiposematic import new_aposematic_img
    
    # First create token audio image
    token_img_path = create_shared_audio_image(
        audio_file, img_path, sender_kp, receiver_kp_public, expires_in
    )
    
    # Then apply aposematic processing
    aposematic_result = new_aposematic_img(
        token_img_path,
        cipher_key=cipher_key,
        op_string='-^+',
        scramble_mode=2
    )
    
    return aposematic_result


async def new_enciphered_img_with_audio_token(
    img_path: str, audio_file: str, sender_kp, receiver_kp_public: str,
    cipher_key: str, expires_in: int
) -> str:
    """
    Create enciphered image with embedded audio token
    
    This is a placeholder - actual implementation would integrate with img_edit
    """
    # For now, create token-based audio image then apply enciphering
    from img_edit import new_enciphered_img
    
    # First create token audio image
    token_img_path = create_shared_audio_image(
        audio_file, img_path, sender_kp, receiver_kp_public, expires_in
    )
    
    # Then apply enciphering
    enciphered_result = new_enciphered_img(
        "enciphered_audio", token_img_path, cipher_key
    )
    
    return enciphered_result
