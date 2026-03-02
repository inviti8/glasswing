"""
Markdown Token Implementation for Embedding Text in PNG Images

Bundles multiple .md files into a single JSON payload, encrypts via
HVYMDataToken, and stores in PNG tEXt chunks. Mirrors audio_tokens.py
structure.
"""

import base64
import json
import os
import tempfile
from typing import List, Optional, Tuple

from hvym_stellar import (
    HVYMDataToken,
    Stellar25519KeyPair,
)

from png_chunks import embed_markdown_token, extract_markdown_token


# Supported markdown file extensions
SUPPORTED_MARKDOWN_EXTENSIONS = ['.md', '.markdown', '.txt']

# Maximum total payload size (1 MB)
MAX_BUNDLE_SIZE = 1 * 1024 * 1024


def is_markdown_file(file_path: str) -> bool:
    """Check if file is a supported markdown format by extension."""
    ext = os.path.splitext(file_path)[1].lower()
    return ext in SUPPORTED_MARKDOWN_EXTENSIONS


def _bundle_markdown_files(file_paths: List[str]) -> bytes:
    """
    Read multiple markdown files and bundle into a single JSON payload.

    Each file's content is base64-encoded to handle binary-safe transport.
    The resulting JSON array is returned as bytes.

    Args:
        file_paths: List of paths to markdown files

    Returns:
        bytes: JSON payload containing all files

    Raises:
        ValueError: If total size exceeds MAX_BUNDLE_SIZE or files are invalid
    """
    entries = []
    total_size = 0

    for fp in file_paths:
        if not os.path.exists(fp):
            raise ValueError(f"File not found: {fp}")

        with open(fp, 'rb') as f:
            content = f.read()

        total_size += len(content)
        if total_size > MAX_BUNDLE_SIZE:
            raise ValueError(
                f"Total markdown size ({total_size} bytes) exceeds "
                f"1 MB limit"
            )

        entries.append({
            "filename": os.path.basename(fp),
            "content": base64.b64encode(content).decode('ascii'),
            "size": len(content),
        })

    return json.dumps(entries).encode('utf-8')


def _unbundle_markdown_payload(payload_bytes: bytes) -> List[dict]:
    """
    Decode a bundled markdown JSON payload.

    Args:
        payload_bytes: JSON payload from _bundle_markdown_files

    Returns:
        list of dicts with keys: filename, content (bytes), size
    """
    entries = json.loads(payload_bytes.decode('utf-8'))
    result = []
    for entry in entries:
        result.append({
            "filename": entry["filename"],
            "content": base64.b64decode(entry["content"]),
            "size": entry["size"],
        })
    return result


def create_markdown_token(sender_kp: Stellar25519KeyPair, receiver_pub: str,
                          md_data: bytes, filename: Optional[str] = None,
                          expires_in: int = 3600) -> str:
    """
    Create encrypted HVYMDataToken containing markdown data.

    Args:
        sender_kp: Sender's Stellar25519KeyPair
        receiver_pub: Receiver's public key string
        md_data: Raw markdown payload bytes (bundled JSON)
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
            file_data=md_data,
            filename=filename or "markdown_bundle.json",
            expires_in=expires_in_int
        )
        return token.serialize()
    except Exception as e:
        print(f"Error creating markdown token: {e}")
        raise


def extract_markdown_from_token(receiver_kp: Stellar25519KeyPair,
                                serialized_token: str,
                                verify_hash: bool = True) -> Tuple[Optional[bytes], Optional[dict]]:
    """
    Extract markdown data from HVYMDataToken.

    Args:
        receiver_kp: Receiver's Stellar25519KeyPair
        serialized_token: Serialized token string
        verify_hash: Whether to verify file integrity (default True)

    Returns:
        tuple: (payload_bytes, metadata_dict) on success, (None, None) on error
    """
    try:
        file_bytes, metadata = HVYMDataToken.extract_from_token(
            serialized_token=serialized_token,
            receiver_keypair=receiver_kp,
            verify_hash=verify_hash,
            enforce_caveats=True
        )
        return file_bytes, metadata
    except Exception:
        # Expected when creator (not recipient) tries to decrypt — not an error
        return None, None


def create_token_markdown_image(md_files: List[str], image_file: str,
                                sender_kp: Stellar25519KeyPair,
                                receiver_pub: str,
                                expires_in: int = 3600) -> str:
    """
    Bundle markdown files, create encrypted token, embed in PNG.

    Args:
        md_files: List of paths to markdown files
        image_file: Path to base PNG image
        sender_kp: Sender's keypair
        receiver_pub: Receiver's public key
        expires_in: Token expiration time

    Returns:
        str: Path to image with embedded token
    """
    # Bundle all markdown files into a single payload
    payload = _bundle_markdown_files(md_files)

    # Create encrypted token
    token = create_markdown_token(
        sender_kp, receiver_pub, payload, "markdown_bundle.json", expires_in
    )

    # Write to temp dir — caller copies result into session storage
    base_name = os.path.splitext(os.path.basename(image_file))[0]
    output_path = os.path.join(
        tempfile.gettempdir(), f'{base_name}_markdown.png'
    )

    # Embed in image
    return embed_markdown_token(image_file, token, output_path)


def extract_token_markdowns(image_path: str, receiver_kp: Stellar25519KeyPair,
                            verify_hash: bool = True) -> Optional[List[dict]]:
    """
    Extract markdown files from token-based markdown image.

    Args:
        image_path: Path to image with embedded markdown token
        receiver_kp: Receiver's keypair for decryption
        verify_hash: Whether to verify file integrity

    Returns:
        list of dicts with keys: filename, content (bytes), size
        or None if extraction fails
    """
    # Extract token from image
    token = extract_markdown_token(image_path)
    if not token:
        return None

    # Decrypt token
    payload_bytes, metadata = extract_markdown_from_token(
        receiver_kp, token, verify_hash
    )
    if not payload_bytes:
        return None

    # Unbundle the payload
    return _unbundle_markdown_payload(payload_bytes)
