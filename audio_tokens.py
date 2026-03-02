"""
Audio Token Implementation for Shared Audio System

Uses Stellar25519KeyPair for ECDH key exchange.
Compatible with existing image encryption flow.
"""

import base64
import os
import tempfile
from typing import Optional, Tuple

from hvym_stellar import (
    HVYMDataToken,
    Stellar25519KeyPair,
)
from stellar_sdk.keypair import Keypair

from png_chunks import embed_audio_token, extract_audio_token


# Audio format signatures
AUDIO_SIGNATURES = {
    b'RIFF': 'wav',
    b'ID3': 'mp3',
    b'OggS': 'ogg',
    b'fLaC': 'flac',
    b'\xff\xfb': 'mp3',
    b'\xff\xf3': 'mp3',
    b'\xff\xf2': 'mp3',
}

SUPPORTED_AUDIO_EXTENSIONS = ['.wav', '.mp3', '.flac', '.ogg']


def detect_audio_format(audio_data: bytes) -> str:
    """Detect audio format from binary data."""
    if not audio_data:
        return 'unknown'

    for sig, format_name in AUDIO_SIGNATURES.items():
        if audio_data.startswith(sig):
            return format_name

    return 'unknown'


def is_audio_file(file_path: str) -> bool:
    """Check if file is a supported audio format."""
    import os
    ext = os.path.splitext(file_path)[1].lower()
    return ext in SUPPORTED_AUDIO_EXTENSIONS


def create_audio_token(sender_kp: Stellar25519KeyPair, receiver_pub: str,
                       audio_data: bytes, filename: Optional[str] = None, expires_in: int = 3600) -> str:
    """
    Create encrypted HVYMDataToken containing audio data.

    Args:
        sender_kp: Sender's Stellar25519KeyPair
        receiver_pub: Receiver's public key string
        audio_data: Raw audio data bytes (NOT base64 encoded)
        filename: Optional filename for metadata
        expires_in: Token expiration time (seconds, None for no expiry)

    Returns:
        str: Serialized HVYMDataToken
    """
    try:
        # Ensure expires_in is an integer (Biscuit Datalog requires int, not float)
        expires_in_int = int(expires_in) if expires_in is not None else None
        token = HVYMDataToken.create_from_bytes(
            senderKeyPair=sender_kp,
            receiverPub=receiver_pub,
            file_data=audio_data,
            filename=filename,
            expires_in=expires_in_int
        )
        return token.serialize()
    except Exception as e:
        print(f"Error creating audio token: {e}")
        raise


def extract_audio_from_token(receiver_kp: Stellar25519KeyPair,
                             serialized_token: str, verify_hash: bool = True) -> Tuple[Optional[bytes], Optional[dict]]:
    """
    Extract audio data from HVYMDataToken.

    Automatically detects token format (biscuit or legacy macaroon) and extracts accordingly.

    Args:
        receiver_kp: Receiver's Stellar25519KeyPair
        serialized_token: Serialized token string
        verify_hash: Whether to verify file integrity (default True)

    Returns:
        tuple: (audio_bytes, metadata_dict) on success, (None, None) on error

    Metadata dict contains:
        - file_size: int
        - file_hash: str (SHA-256)
        - file_name: str (if provided during creation)
        - file_type: str
    """
    try:
        file_bytes, metadata = HVYMDataToken.extract_from_token(
            serialized_token=serialized_token,
            receiver_keypair=receiver_kp,
            verify_hash=verify_hash,
            enforce_caveats=True
        )
        return file_bytes, metadata
    except Exception as e:
        print(f"Error extracting audio from token: {e}")
        return None, None


def get_user_keypair(app) -> Stellar25519KeyPair:
    """
    Get current user's Stellar keypair from storage.

    Args:
        app: NiceGUI app instance with storage

    Returns:
        Stellar25519KeyPair: User's wrapped keypair
    """
    stellar_secret = app.storage.user.get('stellar_secret')
    if not stellar_secret:
        raise ValueError("No stellar_secret found in user storage")

    stellar_kp = Keypair.from_secret(stellar_secret)
    return Stellar25519KeyPair(stellar_kp)


def get_user_public_key(app) -> str:
    """
    Get current user's public key.

    Args:
        app: NiceGUI app instance

    Returns:
        str: Base64-encoded public key
    """
    return get_user_keypair(app).public_key()


def create_token_audio_image(audio_file: str, image_file: str,
                             sender_kp: Stellar25519KeyPair,
                             receiver_pub: str,
                             expires_in: int = 3600) -> str:
    """
    Create audio image with encrypted HVYMDataToken.

    Args:
        audio_file: Path to audio file
        image_file: Path to base image
        sender_kp: Sender's keypair
        receiver_pub: Receiver's public key
        expires_in: Token expiration time

    Returns:
        str: Path to image with embedded token
    """
    # Read audio as raw bytes (no base64 encoding needed)
    with open(audio_file, 'rb') as f:
        audio_data = f.read()

    # Get filename for metadata
    filename = os.path.basename(audio_file)

    # Create encrypted token with raw bytes
    token = create_audio_token(sender_kp, receiver_pub, audio_data, filename, expires_in)

    # Write to temp dir — caller copies result into session storage
    base_name = os.path.splitext(os.path.basename(image_file))[0]
    output_path = os.path.join(tempfile.gettempdir(), f'{base_name}_audio.png')

    # Embed in image
    return embed_audio_token(image_file, token, output_path)


def extract_token_audio(image_path: str, receiver_kp: Stellar25519KeyPair, verify_hash: bool = True) -> Tuple[Optional[bytes], Optional[str], Optional[dict]]:
    """
    Extract audio data from token-based audio image.

    Args:
        image_path: Path to image with embedded token
        receiver_kp: Receiver's keypair for decryption
        verify_hash: Whether to verify file integrity (default True)

    Returns:
        tuple: (audio_bytes, format, metadata) or (None, None, None) if extraction fails

    The metadata dict contains file info from the token.
    """
    # Extract token from image
    token = extract_audio_token(image_path)
    if not token:
        return None, None, None

    # Extract audio from token (returns raw bytes directly)
    audio_bytes, metadata = extract_audio_from_token(receiver_kp, token, verify_hash)
    if not audio_bytes:
        return None, None, None

    # Format from metadata or detection
    audio_format = None
    if metadata:
        # Metadata uses 'filename' key (not 'file_name')
        filename = metadata.get('filename', '')
        if filename and '.' in filename:
            audio_format = filename.rsplit('.', 1)[-1].lower()
    if not audio_format or audio_format == 'unknown':
        audio_format = detect_audio_format(audio_bytes)

    return audio_bytes, audio_format, metadata


def extract_audio_from_token_compat(receiver_kp: Stellar25519KeyPair,
                                    serialized_token: str, verify_hash: bool = True) -> Tuple[Optional[str], bool]:
    """
    Backward-compatible extraction returning base64-encoded audio.

    This wrapper maintains compatibility with code expecting the old API
    that returned (audio_base64, valid) tuple.

    Args:
        receiver_kp: Receiver's Stellar25519KeyPair
        serialized_token: Serialized token string
        verify_hash: Whether to verify file integrity

    Returns:
        tuple: (audio_base64_string, True) or (None, False)
    """
    audio_bytes, metadata = extract_audio_from_token(receiver_kp, serialized_token, verify_hash)
    if audio_bytes:
        audio_base64 = base64.b64encode(audio_bytes).decode('ascii')
        return audio_base64, True
    return None, False


def extract_token_audio_legacy(image_path: str, receiver_kp: Stellar25519KeyPair) -> Tuple[Optional[bytes], str]:
    """
    Legacy version of extract_token_audio for backward compatibility.
    
    Returns (audio_bytes, format) tuple instead of (audio_bytes, format, metadata).
    """
    audio_bytes, audio_format, metadata = extract_token_audio(image_path, receiver_kp)
    return audio_bytes, audio_format or 'unknown'


# Aliases for backward compatibility
get_current_user_stellar_keypair = get_user_keypair
get_current_user_stellar_public_key = get_user_public_key
create_shared_audio_image = create_token_audio_image
