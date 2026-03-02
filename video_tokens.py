"""
Video Token Implementation for Encrypted Video Embedding

Uses HVYMDataToken for encryption and IPFS for storage.
Video tokens are stored on IPFS (too large for PNG tEXt chunks);
only the IPFS CID is embedded in the PNG image.

Mirrors audio_tokens.py structure.
"""

import os
import tempfile
from typing import Optional, Tuple

from hvym_stellar import (
    HVYMDataToken,
    Stellar25519KeyPair,
)

from png_chunks import embed_video_token_cid, extract_video_token_cid


# Video format signatures (magic bytes)
VIDEO_SIGNATURES = {
    b'\x1a\x45\xdf\xa3': 'webm',   # EBML header (Matroska/WebM)
    b'RIFF': 'avi',                  # AVI uses RIFF container
}

SUPPORTED_VIDEO_EXTENSIONS = ['.mp4', '.webm', '.mov', '.avi', '.mkv']


def detect_video_format(video_data: bytes) -> str:
    """Detect video format from binary data using magic bytes."""
    if not video_data:
        return 'unknown'

    # Check simple prefix signatures
    for sig, format_name in VIDEO_SIGNATURES.items():
        if video_data.startswith(sig):
            return format_name

    # MP4/MOV: ftyp box at bytes 4-7
    if len(video_data) >= 8 and video_data[4:8] == b'ftyp':
        # Check sub-type for MOV vs MP4
        ftyp_brand = video_data[8:12] if len(video_data) >= 12 else b''
        if ftyp_brand == b'qt  ':
            return 'mov'
        return 'mp4'

    return 'unknown'


def is_video_file(file_path: str) -> bool:
    """Check if file is a supported video format by extension."""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in SUPPORTED_VIDEO_EXTENSIONS


def create_video_token(sender_kp: Stellar25519KeyPair, receiver_pub: str,
                       video_data: bytes, filename: Optional[str] = None,
                       expires_in: int = 3600) -> str:
    """
    Create encrypted HVYMDataToken containing video data.

    Args:
        sender_kp: Sender's Stellar25519KeyPair
        receiver_pub: Receiver's public key string
        video_data: Raw video data bytes
        filename: Optional filename for metadata
        expires_in: Token expiration time (seconds, None for no expiry)

    Returns:
        str: Serialized HVYMDataToken
    """
    try:
        expires_in_int = int(expires_in) if expires_in is not None else None
        token = HVYMDataToken.create_from_bytes(
            senderKeyPair=sender_kp,
            receiverPub=receiver_pub,
            file_data=video_data,
            filename=filename,
            expires_in=expires_in_int
        )
        return token.serialize()
    except Exception as e:
        print(f"Error creating video token: {e}")
        raise


def extract_video_from_token(receiver_kp: Stellar25519KeyPair,
                              serialized_token: str,
                              verify_hash: bool = True) -> Tuple[Optional[bytes], Optional[dict]]:
    """
    Extract video data from HVYMDataToken.

    Args:
        receiver_kp: Receiver's Stellar25519KeyPair
        serialized_token: Serialized token string
        verify_hash: Whether to verify file integrity (default True)

    Returns:
        tuple: (video_bytes, metadata_dict) on success, (None, None) on error
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
        print(f"Error extracting video from token: {e}")
        return None, None


def create_token_video_image(video_file: str, image_file: str,
                              sender_kp: Stellar25519KeyPair,
                              receiver_pub: str,
                              expires_in: int = 3600,
                              ipfs_add_fn=None) -> Tuple[Optional[str], Optional[str]]:
    """
    Create encrypted video token, upload to IPFS, embed CID in PNG.

    Args:
        video_file: Path to video file
        image_file: Path to base PNG image
        sender_kp: Sender's keypair
        receiver_pub: Receiver's public key
        expires_in: Token expiration time
        ipfs_add_fn: IPFS add function (callable: file_path -> (hash, name, ext))

    Returns:
        tuple: (path_to_modified_png, ipfs_cid) or (None, None) on error
    """
    if ipfs_add_fn is None:
        raise ValueError("ipfs_add_fn is required to upload video token to IPFS")

    # Read video as raw bytes
    with open(video_file, 'rb') as f:
        video_data = f.read()

    filename = os.path.basename(video_file)

    # Create encrypted token
    serialized_token = create_video_token(
        sender_kp, receiver_pub, video_data, filename, expires_in
    )

    # Write serialized token to temp file for IPFS upload
    token_temp_path = os.path.join(
        tempfile.gettempdir(), f"video_token_{os.getpid()}.bin"
    )
    try:
        with open(token_temp_path, 'w') as f:
            f.write(serialized_token)

        # Upload to IPFS
        cid, _, _ = ipfs_add_fn(token_temp_path)
        if not cid:
            print("Error: Failed to upload video token to IPFS")
            return None, None
    finally:
        if os.path.exists(token_temp_path):
            os.unlink(token_temp_path)

    # Embed CID in PNG tEXt chunk
    base_name = os.path.splitext(os.path.basename(image_file))[0]
    output_path = os.path.join(
        os.path.dirname(image_file) or '.', f'{base_name}_video.png'
    )
    result_path = embed_video_token_cid(image_file, cid, output_path)

    return result_path, cid


def extract_token_video(image_path: str, receiver_kp: Stellar25519KeyPair,
                         ipfs_load_fn=None,
                         verify_hash: bool = True) -> Tuple[Optional[bytes], Optional[str], Optional[dict]]:
    """
    Extract video from token-based video image.

    1. Extract CID from PNG tEXt chunk
    2. Fetch serialized token from IPFS
    3. Decrypt via HVYMDataToken

    Args:
        image_path: Path to image with embedded video CID
        receiver_kp: Receiver's keypair for decryption
        ipfs_load_fn: IPFS load function (callable: cid -> temp_file_path)
        verify_hash: Whether to verify file integrity

    Returns:
        tuple: (video_bytes, format, metadata) or (None, None, None) on error
    """
    if ipfs_load_fn is None:
        raise ValueError("ipfs_load_fn is required to fetch video token from IPFS")

    # Extract CID from PNG
    cid = extract_video_token_cid(image_path)
    if not cid:
        print(f"No video token CID found in {image_path}")
        return None, None, None

    # Fetch serialized token from IPFS
    token_temp_path = ipfs_load_fn(cid, "video_token.bin")
    if not token_temp_path:
        print(f"Failed to fetch video token from IPFS: {cid}")
        return None, None, None

    try:
        with open(token_temp_path, 'r') as f:
            serialized_token = f.read()
    finally:
        if os.path.exists(token_temp_path):
            os.unlink(token_temp_path)
            # Clean up temp dir if empty
            token_dir = os.path.dirname(token_temp_path)
            if token_dir and os.path.isdir(token_dir):
                try:
                    os.rmdir(token_dir)
                except OSError:
                    pass

    # Decrypt token
    video_bytes, metadata = extract_video_from_token(
        receiver_kp, serialized_token, verify_hash
    )
    if not video_bytes:
        return None, None, None

    # Detect format from metadata filename or magic bytes
    video_format = None
    if metadata:
        filename = metadata.get('filename', '')
        if filename and '.' in filename:
            video_format = filename.rsplit('.', 1)[-1].lower()
    if not video_format or video_format == 'unknown':
        video_format = detect_video_format(video_bytes)

    return video_bytes, video_format, metadata
