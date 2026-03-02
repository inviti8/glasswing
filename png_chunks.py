"""
PNG Chunk Utilities for Audio/Video/Data Embedding

Unified PNG tEXt chunk handling for the application.
All PNG chunk read/write operations should use this module.
"""

import struct
import zlib
import tempfile
import os
from typing import Optional, Dict, List, Tuple


# Constants
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
CHUNK_SIZE = 8192  # 8KB chunks for tEXt compatibility

# Keyword patterns
AUDIO_TOKEN_PREFIX = 'audio_token_'
VIDEO_TOKEN_CID_PREFIX = 'video_token_cid_'


def is_valid_png(data: bytes) -> bool:
    """Check if data has valid PNG signature."""
    return len(data) >= 8 and data[:8] == PNG_SIGNATURE


def read_text_chunks(png_path: str, keyword_prefix: str) -> Dict[int, str]:
    """
    Read tEXt chunks from PNG file matching a keyword prefix.

    Args:
        png_path: Path to PNG file
        keyword_prefix: Prefix to match (e.g., 'audio_token_')

    Returns:
        dict: {chunk_number: chunk_data} sorted by chunk number
    """
    try:
        with open(png_path, 'rb') as f:
            png_data = f.read()
    except Exception as e:
        print(f"Failed to read PNG: {e}")
        return {}

    if not is_valid_png(png_data):
        print(f"Invalid PNG file: {png_path}")
        return {}

    chunks = {}
    pos = 8  # Skip PNG signature

    while pos < len(png_data):
        if pos + 8 > len(png_data):
            break

        chunk_length = int.from_bytes(png_data[pos:pos+4], byteorder='big')
        chunk_type = png_data[pos+4:pos+8].decode('ascii')

        if chunk_type == 'IEND':
            break

        chunk_data = png_data[pos+8:pos+8+chunk_length]

        if chunk_type == 'tEXt' and b'\x00' in chunk_data:
            try:
                null_pos = chunk_data.index(b'\x00')
                keyword = chunk_data[:null_pos].decode('ascii')
                data = chunk_data[null_pos+1:].decode('ascii')

                if keyword.startswith(keyword_prefix):
                    # Extract chunk number from keyword (e.g., audio_token_001 -> 1)
                    chunk_num = int(keyword.split('_')[-1])
                    chunks[chunk_num] = data
            except (ValueError, UnicodeDecodeError):
                pass

        pos += 8 + chunk_length + 4

    return chunks


def write_text_chunks(png_path: str, keyword_prefix: str, data: str,
                      output_path: Optional[str] = None) -> str:
    """
    Write data as tEXt chunks to PNG file.

    Args:
        png_path: Path to source PNG file
        keyword_prefix: Prefix for chunk keywords (e.g., 'audio_token_')
        data: Data to embed (will be split into chunks)
        output_path: Output path (defaults to temp file)

    Returns:
        str: Path to modified PNG
    """
    with open(png_path, 'rb') as f:
        png_data = bytearray(f.read())

    if not is_valid_png(png_data):
        raise ValueError(f"Invalid PNG file: {png_path}")

    # Split data into chunks
    data_chunks = []
    for i in range(0, len(data), CHUNK_SIZE):
        data_chunks.append(data[i:i + CHUNK_SIZE])

    # Find IEND chunk position
    pos = 8
    iend_pos = len(png_data)

    while pos < len(png_data):
        chunk_length = int.from_bytes(png_data[pos:pos+4], byteorder='big')
        chunk_type = png_data[pos+4:pos+8].decode('ascii')

        if chunk_type == 'IEND':
            iend_pos = pos
            break

        pos += 8 + chunk_length + 4

    # Insert tEXt chunks before IEND
    insert_pos = iend_pos

    for i, chunk_data in enumerate(data_chunks, 1):
        keyword = f'{keyword_prefix}{i:03d}'
        text_data = keyword.encode('ascii') + b'\x00' + chunk_data.encode('ascii')
        chunk_length = len(text_data)

        chunk_header = struct.pack('>I', chunk_length) + b'tEXt'
        chunk_with_data = chunk_header + text_data
        crc = zlib.crc32(b'tEXt' + text_data) & 0xffffffff
        chunk_full = chunk_with_data + struct.pack('>I', crc)

        png_data[insert_pos:insert_pos] = chunk_full
        insert_pos += len(chunk_full)

    # Determine output path
    if output_path is None:
        output_path = os.path.join(tempfile.gettempdir(), "embedded_png.png")

    with open(output_path, 'wb') as f:
        f.write(png_data)

    return output_path


def extract_combined_data(png_path: str, keyword_prefix: str) -> Optional[str]:
    """
    Extract and combine data from numbered tEXt chunks.

    Args:
        png_path: Path to PNG file
        keyword_prefix: Prefix to match

    Returns:
        str: Combined data or None if not found
    """
    chunks = read_text_chunks(png_path, keyword_prefix)

    if not chunks:
        return None

    # Combine chunks in order
    sorted_chunks = [chunks[i] for i in sorted(chunks.keys())]
    return ''.join(sorted_chunks)


def embed_audio_token(png_path: str, token: str, output_path: Optional[str] = None) -> str:
    """
    Embed audio token in PNG.

    Args:
        png_path: Path to source PNG
        token: Serialized audio token
        output_path: Output path (optional)

    Returns:
        str: Path to PNG with embedded token
    """
    return write_text_chunks(png_path, AUDIO_TOKEN_PREFIX, token, output_path)


def extract_audio_token(png_path: str) -> Optional[str]:
    """Extract audio token from PNG."""
    return extract_combined_data(png_path, AUDIO_TOKEN_PREFIX)


def has_audio_data(png_path: str) -> Tuple[bool, str]:
    """
    Check if PNG has embedded audio data.

    Returns:
        tuple: (has_audio, method) where method is 'token' or None
    """
    if extract_combined_data(png_path, AUDIO_TOKEN_PREFIX):
        return True, 'token'
    return False, None


def copy_token_chunks(source_png: str, target_png: str,
                      keyword_prefix: str = AUDIO_TOKEN_PREFIX,
                      output_path: Optional[str] = None) -> str:
    """
    Copy tEXt chunks matching a prefix from one PNG to another.

    Used to preserve audio token chunks when an image is re-processed
    (e.g., watermarking, aposematic) and the output PNG loses tEXt chunks.

    Args:
        source_png: PNG file containing the chunks to copy
        target_png: PNG file to copy chunks into
        keyword_prefix: Prefix to match (default: audio token prefix)
        output_path: Output path (defaults to overwriting target_png)

    Returns:
        str: Path to the target PNG with copied chunks
    """
    # Extract combined token data from source
    token_data = extract_combined_data(source_png, keyword_prefix)
    if not token_data:
        # No chunks to copy — return target unchanged
        return target_png

    # Write the token data into the target PNG
    if output_path is None:
        output_path = target_png
    return write_text_chunks(target_png, keyword_prefix, token_data, output_path)


def remove_text_chunks(png_path: str, keyword_prefix: str,
                       output_path: Optional[str] = None) -> str:
    """
    Remove all tEXt chunks matching a keyword prefix from a PNG file.

    Args:
        png_path: Path to PNG file
        keyword_prefix: Prefix to match for removal
        output_path: Output path (defaults to overwriting png_path)

    Returns:
        str: Path to modified PNG
    """
    with open(png_path, 'rb') as f:
        png_data = f.read()

    if not is_valid_png(png_data):
        raise ValueError(f"Invalid PNG file: {png_path}")

    result = bytearray()
    result.extend(png_data[:8])  # PNG signature
    pos = 8

    while pos < len(png_data):
        if pos + 8 > len(png_data):
            break

        chunk_length = int.from_bytes(png_data[pos:pos+4], byteorder='big')
        chunk_type = png_data[pos+4:pos+8]
        chunk_end = pos + 8 + chunk_length + 4  # header + data + CRC

        skip = False
        if chunk_type == b'tEXt':
            chunk_data = png_data[pos+8:pos+8+chunk_length]
            if b'\x00' in chunk_data:
                try:
                    null_pos = chunk_data.index(b'\x00')
                    keyword = chunk_data[:null_pos].decode('ascii')
                    if keyword.startswith(keyword_prefix):
                        skip = True
                except (ValueError, UnicodeDecodeError):
                    pass

        if not skip:
            result.extend(png_data[pos:chunk_end])

        pos = chunk_end

    if output_path is None:
        output_path = png_path

    with open(output_path, 'wb') as f:
        f.write(result)

    return output_path


def embed_video_token_cid(png_path: str, cid: str,
                           output_path: Optional[str] = None) -> str:
    """
    Embed video token IPFS CID in PNG.

    Args:
        png_path: Path to source PNG
        cid: IPFS CID string for the encrypted video token
        output_path: Output path (optional)

    Returns:
        str: Path to PNG with embedded CID
    """
    return write_text_chunks(png_path, VIDEO_TOKEN_CID_PREFIX, cid, output_path)


def extract_video_token_cid(png_path: str) -> Optional[str]:
    """Extract video token IPFS CID from PNG."""
    return extract_combined_data(png_path, VIDEO_TOKEN_CID_PREFIX)


def has_video_data(png_path: str) -> Tuple[bool, str]:
    """
    Check if PNG has embedded video data (CID reference).

    Returns:
        tuple: (has_video, method) where method is 'token' or None
    """
    if extract_combined_data(png_path, VIDEO_TOKEN_CID_PREFIX):
        return True, 'token'
    return False, None
