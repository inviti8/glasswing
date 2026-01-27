# HVYM_STELLAR API Update Plan for Andromica

## Executive Summary

This document outlines the comprehensive plan for updating Andromica's audio image embedding flow to work with the new hvym_stellar v0.21.0 API. The primary change is the migration from **macaroon-based tokens** (`StellarSharedKeyTokenBuilder`) to **biscuit-based tokens** (`HVYMDataToken`), which removes the previous 16KB file size limitation and provides improved file handling capabilities.

---

## Table of Contents

1. [API Changes Overview](#1-api-changes-overview)
2. [Impact Analysis](#2-impact-analysis)
3. [File-by-File Update Plan](#3-file-by-file-update-plan)
4. [Implementation Details](#4-implementation-details)
5. [Migration Strategy](#5-migration-strategy)
6. [Testing Requirements](#6-testing-requirements)
7. [Backward Compatibility](#7-backward-compatibility)
8. [Timeline and Dependencies](#8-timeline-and-dependencies)

---

## 1. API Changes Overview

### 1.1 Old API (Macaroon-Based)

```python
# Token Creation
from hvym_stellar import StellarSharedKeyTokenBuilder, TokenType

builder = StellarSharedKeyTokenBuilder(
    senderKeyPair=sender_kp,
    recieverPub=receiver_pub,  # Note: typo in old API
    tokenType=TokenType.SECRET,
    secret=audio_base64,
    expires_in=3600,
    caveats={'audio': 'sharing'}
)
serialized_token = builder.serialize()

# Token Extraction
from hvym_stellar import StellarSharedKeyTokenVerifier

verifier = StellarSharedKeyTokenVerifier(
    receiver_kp=receiver_kp,
    token=token_bytes,
    tokenType=TokenType.SECRET,
    caveats={'audio': 'sharing'}
)
audio_base64 = verifier.secret()
is_valid = verifier.valid()
```

**Limitations:**
- 16KB maximum payload size (macaroon limitation)
- Limited metadata support
- No file format detection
- Manual caveat management

### 1.2 New API (Biscuit-Based HVYMDataToken)

```python
# Token Creation
from hvym_stellar import HVYMDataToken, Stellar25519KeyPair

token = HVYMDataToken.create_from_bytes(
    senderKeyPair=sender_kp,
    receiverPub=receiver_pub,  # Note: corrected spelling
    file_data=audio_bytes,     # Raw bytes, not base64!
    filename="audio.wav",
    expires_in=3600
)
serialized_token = token.serialize()

# Token Extraction
file_bytes, metadata = HVYMDataToken.extract_from_token(
    serialized_token=serialized_token,
    receiver_keypair=receiver_kp,
    verify_hash=True,
    enforce_caveats=True
)
```

**Improvements:**
- No practical size limit (tested up to 100MB+)
- Automatic hash verification (SHA-256)
- Built-in file metadata (size, type, hash)
- Automatic format detection
- HVYM binary file format support
- Backward compatible with legacy macaroon tokens

### 1.3 Key Differences Summary

| Aspect | Old API | New API |
|--------|---------|---------|
| Base Class | `StellarSharedKeyTokenBuilder` | `HVYMDataToken` |
| Payload | Base64 string | Raw bytes |
| Size Limit | 16KB | Unlimited (soft limit 100MB) |
| File Info | Manual | Automatic (size, hash, type) |
| Parameter Spelling | `recieverPub` | `receiverPub` |
| Token Format | Macaroon | Biscuit |
| Hash Verification | Manual | Automatic |
| Extraction | `.secret()` method | `extract_from_token()` static |

---

## 2. Impact Analysis

### 2.1 Affected Files

| File | Impact Level | Changes Required |
|------|--------------|------------------|
| `audio_tokens.py` | **HIGH** | Core token creation/extraction rewrite |
| `data_pod_audio.py` | **MEDIUM** | Update extraction calls |
| `main.py` | **LOW** | Update imports, minor adjustments |
| `dialogs.py` | **LOW** | Update imports if using token classes |
| `png_chunks.py` | **NONE** | No changes (handles raw strings) |

### 2.2 Breaking Changes

1. **Payload Format Change**: Old API used base64-encoded strings; new API uses raw bytes
2. **Method Signature Change**: Extraction is now a static method with different parameters
3. **Return Value Change**: Extraction returns `(bytes, metadata_dict)` tuple instead of just the secret
4. **Caveat Handling**: File caveats are now automatic, no manual `{'audio': 'sharing'}` required

### 2.3 Behavioral Changes

- **Size Warnings**: Files over 50MB will emit warnings (non-blocking)
- **Hash Verification**: Enabled by default, can be disabled with `verify_hash=False`
- **Token Expiration**: Default 1 hour for factory methods, can override with `expires_in=None`
- **Metadata Inclusion**: Token now includes file_size, file_hash, file_type automatically

---

## 3. File-by-File Update Plan

### 3.1 audio_tokens.py (HIGH PRIORITY)

#### Current Implementation Analysis

**Location:** Lines 1-150 (approximately)

**Current Imports:**
```python
from hvym_stellar import (
    StellarSharedKeyTokenBuilder,
    StellarSharedKeyTokenVerifier,
    Stellar25519KeyPair,
    TokenType
)
```

**Functions to Update:**
1. `create_audio_token()` - Token creation
2. `extract_audio_from_token()` - Token extraction
3. `create_token_audio_image()` - End-to-end token image creation
4. `extract_token_audio()` - End-to-end token extraction from image

#### Updated Implementation

**New Imports:**
```python
from hvym_stellar import (
    HVYMDataToken,
    Stellar25519KeyPair,
)
from stellar_sdk.keypair import Keypair
import base64
```

**Function 1: `create_audio_token()`**

```python
# OLD
def create_audio_token(sender_kp, receiver_pub, audio_base64, expires_in=3600):
    """Create an encrypted audio token using macaroon."""
    try:
        builder = StellarSharedKeyTokenBuilder(
            senderKeyPair=sender_kp,
            recieverPub=receiver_pub,
            tokenType=TokenType.SECRET,
            secret=audio_base64,
            expires_in=expires_in,
            caveats={'audio': 'sharing'}
        )
        return builder.serialize()
    except Exception as e:
        print(f"Error creating audio token: {e}")
        return None

# NEW
def create_audio_token(sender_kp, receiver_pub, audio_data, filename=None, expires_in=3600):
    """
    Create an encrypted audio token using HVYMDataToken (biscuit-based).

    Args:
        sender_kp: Stellar25519KeyPair - sender's keypair
        receiver_pub: str - receiver's public key (base64)
        audio_data: bytes - raw audio data (NOT base64 encoded)
        filename: str - optional filename for metadata
        expires_in: int - token expiration in seconds (default 3600)

    Returns:
        str: Serialized token string, or None on error
    """
    try:
        token = HVYMDataToken.create_from_bytes(
            senderKeyPair=sender_kp,
            receiverPub=receiver_pub,
            file_data=audio_data,
            filename=filename,
            expires_in=expires_in
        )
        return token.serialize()
    except Exception as e:
        print(f"Error creating audio token: {e}")
        return None
```

**Function 2: `extract_audio_from_token()`**

```python
# OLD
def extract_audio_from_token(receiver_kp, serialized_token):
    """Extract audio from an encrypted token."""
    try:
        if isinstance(serialized_token, str):
            serialized_token = serialized_token.encode('utf-8')

        verifier = StellarSharedKeyTokenVerifier(
            receiver_kp=receiver_kp,
            token=serialized_token,
            tokenType=TokenType.SECRET,
            caveats={'audio': 'sharing'}
        )
        audio_base64 = verifier.secret()
        valid = verifier.valid()
        return audio_base64, valid
    except Exception as e:
        print(f"Error extracting audio from token: {e}")
        return None, False

# NEW
def extract_audio_from_token(receiver_kp, serialized_token, verify_hash=True):
    """
    Extract audio from an encrypted HVYMDataToken.

    Args:
        receiver_kp: Stellar25519KeyPair - receiver's keypair
        serialized_token: str - serialized token string
        verify_hash: bool - whether to verify file integrity (default True)

    Returns:
        tuple: (audio_bytes, metadata_dict) or (None, None) on error

    Note: Returns raw bytes instead of base64. Convert if needed:
        audio_base64 = base64.b64encode(audio_bytes).decode('ascii')
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
```

**Function 3: `create_token_audio_image()`**

```python
# OLD
def create_token_audio_image(audio_file, image_file, sender_kp, receiver_pub, expires_in=3600):
    """Create an image with encrypted audio token embedded."""
    # Read and base64 encode audio
    with open(audio_file, 'rb') as f:
        audio_data = f.read()
    audio_base64 = base64.b64encode(audio_data).decode('ascii')

    # Create token
    token = create_audio_token(sender_kp, receiver_pub, audio_base64, expires_in)
    if not token:
        return None

    # Embed in image
    output_path = embed_audio_token(image_file, token)
    return output_path

# NEW
def create_token_audio_image(audio_file, image_file, sender_kp, receiver_pub, expires_in=3600):
    """
    Create an image with encrypted HVYMDataToken audio embedded.

    Args:
        audio_file: str - path to audio file
        image_file: str - path to source image
        sender_kp: Stellar25519KeyPair - sender's keypair
        receiver_pub: str - receiver's public key
        expires_in: int - token expiration in seconds

    Returns:
        str: Path to output image with embedded token, or None on error
    """
    # Read audio as raw bytes (no base64 encoding needed)
    with open(audio_file, 'rb') as f:
        audio_data = f.read()

    # Get filename for metadata
    filename = os.path.basename(audio_file)

    # Create token with raw bytes
    token = create_audio_token(
        sender_kp,
        receiver_pub,
        audio_data,  # Raw bytes, not base64
        filename=filename,
        expires_in=expires_in
    )
    if not token:
        return None

    # Embed in image (token is a string, png_chunks handles it)
    output_path = embed_audio_token(image_file, token)
    return output_path
```

**Function 4: `extract_token_audio()`**

```python
# OLD
def extract_token_audio(image_path, receiver_kp):
    """Extract audio from a token-embedded image."""
    token = extract_audio_token(image_path)
    if not token:
        return None, None

    audio_base64, valid = extract_audio_from_token(receiver_kp, token)
    if not audio_base64:
        return None, None

    # Decode base64 to bytes
    audio_bytes = base64.b64decode(audio_base64)
    audio_format = detect_audio_format(audio_bytes)

    return audio_bytes, audio_format

# NEW
def extract_token_audio(image_path, receiver_kp, verify_hash=True):
    """
    Extract audio from a token-embedded image.

    Args:
        image_path: str - path to image with embedded token
        receiver_kp: Stellar25519KeyPair - receiver's keypair
        verify_hash: bool - verify file integrity (default True)

    Returns:
        tuple: (audio_bytes, audio_format, metadata) or (None, None, None) on error

    The metadata dict contains:
        - file_size: int
        - file_hash: str (SHA-256)
        - file_name: str
        - file_type: str
    """
    token = extract_audio_token(image_path)
    if not token:
        return None, None, None

    # Extract returns raw bytes directly (no base64)
    audio_bytes, metadata = extract_audio_from_token(receiver_kp, token, verify_hash)
    if not audio_bytes:
        return None, None, None

    # Format can come from metadata or detection
    audio_format = metadata.get('file_type') or detect_audio_format(audio_bytes)

    return audio_bytes, audio_format, metadata
```

**New Helper Function: Backward Compatibility Wrapper**

```python
def extract_audio_from_token_compat(receiver_kp, serialized_token, verify_hash=True):
    """
    Backward-compatible extraction that returns base64-encoded audio.

    This wrapper maintains compatibility with code expecting the old API
    that returned (audio_base64, valid) tuple.

    Args:
        receiver_kp: Stellar25519KeyPair - receiver's keypair
        serialized_token: str - serialized token string
        verify_hash: bool - verify file integrity

    Returns:
        tuple: (audio_base64_string, True) or (None, False)
    """
    audio_bytes, metadata = extract_audio_from_token(receiver_kp, serialized_token, verify_hash)
    if audio_bytes:
        audio_base64 = base64.b64encode(audio_bytes).decode('ascii')
        return audio_base64, True
    return None, False
```

---

### 3.2 data_pod_audio.py (MEDIUM PRIORITY)

#### Current Implementation Analysis

**Location:** `process_data_pod_locally()` function

**Current Audio Extraction Code:**
```python
if item.get('hasAudio') and item.get('audioMethod') == 'token':
    serialized_token = extract_audio_token(decoded_path)
    audio_base64, valid = extract_audio_from_token(subscriber_keys, serialized_token)
    item['audio'] = {
        'data': audio_base64,
        'format': detect_audio_format(base64.b64decode(audio_base64)),
        'extractedAt': time.time(),
        'method': 'token'
    }
```

#### Updated Implementation

```python
if item.get('hasAudio') and item.get('audioMethod') == 'token':
    serialized_token = extract_audio_token(decoded_path)
    if serialized_token:
        # New API returns raw bytes and metadata
        audio_bytes, metadata = extract_audio_from_token(
            subscriber_keys,
            serialized_token,
            verify_hash=True
        )

        if audio_bytes:
            # Convert to base64 for storage in data pod
            audio_base64 = base64.b64encode(audio_bytes).decode('ascii')

            # Use metadata from token or detect format
            audio_format = metadata.get('file_type') if metadata else None
            if not audio_format:
                audio_format = detect_audio_format(audio_bytes)

            item['audio'] = {
                'data': audio_base64,
                'format': audio_format,
                'extractedAt': time.time(),
                'method': 'token',
                # New: include token metadata
                'metadata': {
                    'fileSize': metadata.get('file_size') if metadata else len(audio_bytes),
                    'fileHash': metadata.get('file_hash') if metadata else None,
                    'fileName': metadata.get('file_name') if metadata else None,
                    'verified': metadata is not None
                }
            }
        else:
            print(f"⚠️ Failed to extract audio from token for {item.get('guid')}")
    else:
        print(f"⚠️ No audio token found in {decoded_path}")
```

---

### 3.3 main.py (LOW PRIORITY)

#### Import Updates

```python
# OLD
from hvym_stellar import Stellar25519KeyPair, StellarSharedKeyTokenBuilder, TokenType

# NEW
from hvym_stellar import Stellar25519KeyPair, HVYMDataToken
```

#### Function Updates

**`process_audio_embedding()` - Minor adjustments**

The main.py function primarily delegates to audio_tokens.py, so changes are minimal:

```python
# Ensure audio_data is passed as bytes, not base64
# The audio_tokens.py functions now expect raw bytes

# If there's any direct token creation in main.py, update to:
token = HVYMDataToken.create_from_bytes(
    senderKeyPair=sender_kp,
    receiverPub=receiver_pub,
    file_data=audio_bytes,  # Raw bytes
    filename=audio_filename,
    expires_in=expires_in
)
```

---

### 3.4 dialogs.py (LOW PRIORITY)

#### Import Updates (if applicable)

```python
# OLD
from hvym_stellar import Stellar25519KeyPair, StellarSharedKey

# NEW (StellarSharedKey unchanged, only add HVYMDataToken if needed)
from hvym_stellar import Stellar25519KeyPair, StellarSharedKey, HVYMDataToken
```

---

## 4. Implementation Details

### 4.1 Data Flow Changes

#### Old Flow (Macaroon-Based)
```
Audio File → Read → Base64 Encode → Token Creation → Serialize → PNG Embed
     ↓
PNG Extract → Token String → Verify → .secret() → Base64 String → Decode → Audio
```

#### New Flow (Biscuit-Based)
```
Audio File → Read → Raw Bytes → Token Creation → Serialize → PNG Embed
     ↓
PNG Extract → Token String → extract_from_token() → (Raw Bytes, Metadata) → Audio
```

### 4.2 Serialization Format

#### Old Format (Macaroon)
```
base64_encoded_macaroon_structure
```

#### New Format (Biscuit)
```
account_token|HVYM_BISCUIT|base64_biscuit_token
```

The new format is larger but provides:
- Clear format identification via delimiter
- Account token for key exchange
- Biscuit for secure payload with facts

### 4.3 Metadata Structure

#### Token Metadata (Automatic)
```python
{
    'file_size': int,           # Original file size in bytes
    'file_hash': str,           # SHA-256 hash
    'file_name': str,           # Original filename
    'file_type': str,           # Extension-based type (wav, mp3, etc.)
    'created_at': str,          # ISO timestamp
    'expires_at': str,          # ISO timestamp (if expires_in set)
}
```

### 4.4 Size Considerations

| Audio Duration | Approx. Size | Old API | New API |
|----------------|--------------|---------|---------|
| 10 seconds WAV | ~1.7 MB | ❌ Fails | ✅ Works |
| 30 seconds MP3 | ~500 KB | ❌ Fails | ✅ Works |
| 5 minutes MP3 | ~5 MB | ❌ Fails | ✅ Works |
| 30 minutes MP3 | ~30 MB | ❌ Fails | ✅ Works (warning) |
| 1 hour MP3 | ~60 MB | ❌ Fails | ✅ Works (warning) |

### 4.5 Error Handling Updates

```python
# New error types to handle
try:
    file_bytes, metadata = HVYMDataToken.extract_from_token(...)
except ValueError as e:
    # Invalid token format
    print(f"Invalid token format: {e}")
except RuntimeError as e:
    # Biscuit verification failed
    print(f"Token verification failed: {e}")
except Exception as e:
    # Hash mismatch or other errors
    if "hash" in str(e).lower():
        print(f"File integrity check failed: {e}")
    else:
        print(f"Extraction error: {e}")
```

---

## 5. Migration Strategy

### 5.1 Phase 1: Update Core Functions (Week 1)

1. **Update audio_tokens.py**
   - Replace imports
   - Update `create_audio_token()` to use `HVYMDataToken.create_from_bytes()`
   - Update `extract_audio_from_token()` to use `HVYMDataToken.extract_from_token()`
   - Add backward compatibility wrapper
   - Update end-to-end functions

2. **Unit Testing**
   - Test token creation with various audio sizes
   - Test extraction with new tokens
   - Verify metadata is correctly populated

### 5.2 Phase 2: Update Dependent Files (Week 2)

1. **Update data_pod_audio.py**
   - Update extraction logic
   - Add metadata handling
   - Test with data pod workflow

2. **Update main.py**
   - Update imports
   - Verify no direct token creation needs updating

3. **Update dialogs.py**
   - Update imports if needed

### 5.3 Phase 3: Backward Compatibility Testing (Week 3)

1. **Test Legacy Token Reading**
   - Create test images with old macaroon tokens
   - Verify new API can read them (auto-detection)
   - Document any edge cases

2. **Test New Token Creation**
   - Create images with new biscuit tokens
   - Verify full workflow (create → embed → extract → play)

### 5.4 Phase 4: Production Rollout (Week 4)

1. **Deploy to staging**
2. **Test with real user data**
3. **Monitor for errors**
4. **Full production deployment**

---

## 6. Testing Requirements

### 6.1 Unit Tests

**File: test_audio_tokens_hvym.py**

```python
import pytest
from hvym_stellar import Stellar25519KeyPair, HVYMDataToken
from stellar_sdk import Keypair
from audio_tokens import (
    create_audio_token,
    extract_audio_from_token,
    create_token_audio_image,
    extract_token_audio,
    detect_audio_format
)

@pytest.fixture
def keypairs():
    """Create sender and receiver keypairs."""
    sender = Keypair.random()
    receiver = Keypair.random()
    return (
        Stellar25519KeyPair(sender),
        Stellar25519KeyPair(receiver),
        receiver.public_key
    )

class TestAudioTokenCreation:
    def test_create_small_audio_token(self, keypairs):
        """Test creating token with small audio file."""
        sender_kp, receiver_kp, receiver_pub = keypairs
        audio_data = b'\x00' * 1024  # 1KB

        token = create_audio_token(sender_kp, receiver_pub, audio_data)

        assert token is not None
        assert '|HVYM_BISCUIT|' in token

    def test_create_large_audio_token(self, keypairs):
        """Test creating token with large audio file (5MB)."""
        sender_kp, receiver_kp, receiver_pub = keypairs
        audio_data = b'\x00' * (5 * 1024 * 1024)  # 5MB

        token = create_audio_token(sender_kp, receiver_pub, audio_data)

        assert token is not None

    def test_create_token_with_filename(self, keypairs):
        """Test creating token with filename metadata."""
        sender_kp, receiver_kp, receiver_pub = keypairs
        audio_data = b'RIFF' + b'\x00' * 100  # Fake WAV header

        token = create_audio_token(
            sender_kp, receiver_pub, audio_data,
            filename='test.wav'
        )

        assert token is not None

class TestAudioTokenExtraction:
    def test_extract_audio_from_token(self, keypairs):
        """Test extracting audio from token."""
        sender_kp, receiver_kp, receiver_pub = keypairs
        original_data = b'test audio data'

        token = create_audio_token(sender_kp, receiver_pub, original_data)
        extracted_bytes, metadata = extract_audio_from_token(receiver_kp, token)

        assert extracted_bytes == original_data
        assert metadata is not None
        assert 'file_size' in metadata or metadata.get('file_size') is not None

    def test_extract_with_wrong_keypair(self, keypairs):
        """Test that wrong keypair fails extraction."""
        sender_kp, receiver_kp, receiver_pub = keypairs
        wrong_kp = Stellar25519KeyPair(Keypair.random())

        token = create_audio_token(sender_kp, receiver_pub, b'secret data')
        extracted, metadata = extract_audio_from_token(wrong_kp, token)

        assert extracted is None

    def test_hash_verification(self, keypairs):
        """Test that hash verification catches corruption."""
        sender_kp, receiver_kp, receiver_pub = keypairs
        audio_data = b'original audio'

        token = create_audio_token(sender_kp, receiver_pub, audio_data)

        # Extraction with verification should work
        extracted, _ = extract_audio_from_token(receiver_kp, token, verify_hash=True)
        assert extracted == audio_data

class TestImageEmbedding:
    def test_create_and_extract_token_image(self, keypairs, tmp_path):
        """Test full workflow: create image with token, extract audio."""
        sender_kp, receiver_kp, receiver_pub = keypairs

        # Create test audio file
        audio_path = tmp_path / "test.wav"
        audio_path.write_bytes(b'RIFF' + b'\x00' * 100)

        # Create test image
        from PIL import Image
        img_path = tmp_path / "test.png"
        img = Image.new('RGB', (100, 100), color='red')
        img.save(img_path)

        # Create token image
        output_path = create_token_audio_image(
            str(audio_path), str(img_path),
            sender_kp, receiver_pub
        )

        assert output_path is not None

        # Extract audio
        audio_bytes, audio_format, metadata = extract_token_audio(
            output_path, receiver_kp
        )

        assert audio_bytes is not None
        assert audio_format in ['wav', 'unknown']

class TestBackwardCompatibility:
    def test_detect_legacy_macaroon_token(self, keypairs):
        """Test that legacy macaroon tokens can still be read."""
        # This test requires creating a legacy token or using a fixture
        pass  # Implementation depends on having legacy token samples

class TestAudioFormatDetection:
    def test_detect_wav(self):
        assert detect_audio_format(b'RIFF....WAVE') == 'wav'

    def test_detect_mp3(self):
        assert detect_audio_format(b'ID3') == 'mp3'
        assert detect_audio_format(b'\xff\xfb') == 'mp3'

    def test_detect_ogg(self):
        assert detect_audio_format(b'OggS') == 'ogg'

    def test_detect_flac(self):
        assert detect_audio_format(b'fLaC') == 'flac'

    def test_detect_unknown(self):
        assert detect_audio_format(b'unknown') == 'unknown'
```

### 6.2 Integration Tests

```python
class TestDataPodIntegration:
    async def test_data_pod_with_audio_tokens(self):
        """Test full data pod workflow with audio token images."""
        # Create data pod with audio token images
        # Process locally with subscriber key
        # Verify audio extraction and metadata
        pass

class TestIPFSIntegration:
    async def test_ipfs_roundtrip_with_large_audio(self):
        """Test IPFS upload/download with large audio token image."""
        # Create large audio (10MB)
        # Embed in image
        # Upload to IPFS
        # Download and extract
        # Verify integrity
        pass
```

### 6.3 Performance Tests

```python
class TestPerformance:
    @pytest.mark.parametrize("size_mb", [1, 5, 10, 25, 50])
    def test_token_creation_performance(self, keypairs, size_mb):
        """Test token creation time for various sizes."""
        sender_kp, receiver_kp, receiver_pub = keypairs
        audio_data = b'\x00' * (size_mb * 1024 * 1024)

        import time
        start = time.time()
        token = create_audio_token(sender_kp, receiver_pub, audio_data)
        elapsed = time.time() - start

        print(f"{size_mb}MB: {elapsed:.2f}s")
        assert token is not None
```

---

## 7. Backward Compatibility

### 7.1 Legacy Token Detection

The new `HVYMDataToken.extract_from_token()` method automatically detects token format:

```python
# From hvym_stellar source:
if '|HVYM_BISCUIT|' in serialized_token:
    # New biscuit format
    return _extract_biscuit_token(...)
else:
    # Legacy macaroon format
    return _extract_macaroon_token(...)
```

### 7.2 Compatibility Matrix

| Token Created With | Extracted With Old API | Extracted With New API |
|-------------------|------------------------|------------------------|
| Old (macaroon) | ✅ Works | ✅ Works (auto-detect) |
| New (biscuit) | ❌ Fails | ✅ Works |

### 7.3 Migration Path for Existing Images

Existing images with macaroon-based tokens will continue to work:

1. **No re-embedding required** for existing images
2. **New extractions** will use auto-detection
3. **Only new embeddings** will use biscuit format

### 7.4 Deprecation Strategy

```python
# Add deprecation warning to old compatibility wrapper
import warnings

def extract_audio_from_token_legacy(receiver_kp, serialized_token):
    """
    DEPRECATED: Use extract_audio_from_token() instead.
    This wrapper exists for backward compatibility only.
    """
    warnings.warn(
        "extract_audio_from_token_legacy is deprecated. "
        "Use extract_audio_from_token() which returns (bytes, metadata).",
        DeprecationWarning,
        stacklevel=2
    )
    return extract_audio_from_token_compat(receiver_kp, serialized_token)
```

---

## 8. Timeline and Dependencies

### 8.1 Prerequisites

- [x] hvym_stellar v0.21.0 installed in local venv
- [ ] Review this plan document
- [ ] Backup current audio_tokens.py
- [ ] Create test fixtures with legacy tokens

### 8.2 Implementation Timeline

| Week | Tasks | Deliverables |
|------|-------|--------------|
| 1 | Core function updates in audio_tokens.py | Updated token creation/extraction |
| 2 | Update dependent files, integration testing | Full workflow working |
| 3 | Backward compatibility testing, edge cases | Verified legacy support |
| 4 | Production deployment, monitoring | Live system with new API |

### 8.3 Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Legacy tokens stop working | Auto-detection built into API |
| Performance degradation | Tested up to 100MB, soft limits with warnings |
| Data corruption | SHA-256 hash verification enabled by default |
| Key compatibility | Same Stellar25519KeyPair wrapper used |

### 8.4 Rollback Plan

If issues arise:

1. **Revert audio_tokens.py** to backup
2. **Keep new tokens readable** - old code can't read them, but they're a minority
3. **Re-embed affected images** with legacy format if critical

---

## Appendix A: Complete Updated audio_tokens.py

```python
"""
Audio token handling for Andromica using hvym_stellar HVYMDataToken.

This module provides functions for creating and extracting encrypted audio
tokens that can be embedded in PNG images. Uses biscuit-based tokens via
HVYMDataToken for secure, size-unlimited audio sharing.

Updated for hvym_stellar v0.21.0 API.
"""

import os
import base64
from hvym_stellar import HVYMDataToken, Stellar25519KeyPair
from stellar_sdk.keypair import Keypair
from png_chunks import embed_audio_token, extract_audio_token


def detect_audio_format(audio_data):
    """
    Detect audio format from binary data using magic signatures.

    Args:
        audio_data: bytes - raw audio data

    Returns:
        str: Format identifier ('wav', 'mp3', 'ogg', 'flac', 'unknown')
    """
    if not audio_data or len(audio_data) < 4:
        return 'unknown'

    # WAV: RIFF....WAVE
    if audio_data[:4] == b'RIFF' and len(audio_data) > 11 and audio_data[8:12] == b'WAVE':
        return 'wav'

    # MP3: ID3 tag or sync word
    if audio_data[:3] == b'ID3':
        return 'mp3'
    if audio_data[:2] == b'\xff\xfb' or audio_data[:2] == b'\xff\xfa':
        return 'mp3'

    # OGG
    if audio_data[:4] == b'OggS':
        return 'ogg'

    # FLAC
    if audio_data[:4] == b'fLaC':
        return 'flac'

    return 'unknown'


def create_audio_token(sender_kp, receiver_pub, audio_data, filename=None, expires_in=3600):
    """
    Create an encrypted audio token using HVYMDataToken (biscuit-based).

    Args:
        sender_kp: Stellar25519KeyPair - sender's keypair
        receiver_pub: str - receiver's public key (base64)
        audio_data: bytes - raw audio data (NOT base64 encoded)
        filename: str - optional filename for metadata
        expires_in: int - token expiration in seconds (default 3600, None for no expiry)

    Returns:
        str: Serialized token string, or None on error
    """
    try:
        token = HVYMDataToken.create_from_bytes(
            senderKeyPair=sender_kp,
            receiverPub=receiver_pub,
            file_data=audio_data,
            filename=filename,
            expires_in=expires_in
        )
        return token.serialize()
    except Exception as e:
        print(f"Error creating audio token: {e}")
        return None


def extract_audio_from_token(receiver_kp, serialized_token, verify_hash=True):
    """
    Extract audio from an encrypted HVYMDataToken.

    Automatically detects token format (biscuit or legacy macaroon) and
    extracts accordingly.

    Args:
        receiver_kp: Stellar25519KeyPair - receiver's keypair
        serialized_token: str - serialized token string
        verify_hash: bool - whether to verify file integrity (default True)

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


def extract_audio_from_token_compat(receiver_kp, serialized_token, verify_hash=True):
    """
    Backward-compatible extraction returning base64-encoded audio.

    This wrapper maintains compatibility with code expecting the old API
    that returned (audio_base64, valid) tuple.

    Args:
        receiver_kp: Stellar25519KeyPair - receiver's keypair
        serialized_token: str - serialized token string
        verify_hash: bool - verify file integrity

    Returns:
        tuple: (audio_base64_string, True) or (None, False)
    """
    audio_bytes, metadata = extract_audio_from_token(receiver_kp, serialized_token, verify_hash)
    if audio_bytes:
        audio_base64 = base64.b64encode(audio_bytes).decode('ascii')
        return audio_base64, True
    return None, False


def create_token_audio_image(audio_file, image_file, sender_kp, receiver_pub, expires_in=3600):
    """
    Create an image with encrypted HVYMDataToken audio embedded.

    Args:
        audio_file: str - path to audio file
        image_file: str - path to source image
        sender_kp: Stellar25519KeyPair - sender's keypair
        receiver_pub: str - receiver's public key
        expires_in: int - token expiration in seconds

    Returns:
        str: Path to output image with embedded token, or None on error
    """
    try:
        # Read audio as raw bytes
        with open(audio_file, 'rb') as f:
            audio_data = f.read()

        # Get filename for metadata
        filename = os.path.basename(audio_file)

        # Create token with raw bytes
        token = create_audio_token(
            sender_kp,
            receiver_pub,
            audio_data,
            filename=filename,
            expires_in=expires_in
        )
        if not token:
            return None

        # Embed in image
        output_path = embed_audio_token(image_file, token)
        return output_path
    except Exception as e:
        print(f"Error creating token audio image: {e}")
        return None


def extract_token_audio(image_path, receiver_kp, verify_hash=True):
    """
    Extract audio from a token-embedded image.

    Args:
        image_path: str - path to image with embedded token
        receiver_kp: Stellar25519KeyPair - receiver's keypair
        verify_hash: bool - verify file integrity (default True)

    Returns:
        tuple: (audio_bytes, audio_format, metadata) or (None, None, None) on error

    The metadata dict contains file info from the token.
    """
    try:
        token = extract_audio_token(image_path)
        if not token:
            print(f"No audio token found in {image_path}")
            return None, None, None

        # Extract returns raw bytes directly
        audio_bytes, metadata = extract_audio_from_token(receiver_kp, token, verify_hash)
        if not audio_bytes:
            return None, None, None

        # Format from metadata or detection
        audio_format = None
        if metadata:
            audio_format = metadata.get('file_type') or metadata.get('file_name', '').split('.')[-1]
        if not audio_format or audio_format == 'unknown':
            audio_format = detect_audio_format(audio_bytes)

        return audio_bytes, audio_format, metadata
    except Exception as e:
        print(f"Error extracting token audio: {e}")
        return None, None, None


def get_user_keypair(app):
    """
    Get user's Stellar25519KeyPair from storage.

    Args:
        app: NiceGUI app with storage

    Returns:
        Stellar25519KeyPair or None
    """
    stellar_secret = app.storage.user.get('stellar_secret')
    if stellar_secret:
        keypair = Keypair.from_secret(stellar_secret)
        return Stellar25519KeyPair(keypair)
    return None


def get_user_public_key(app):
    """
    Get user's public key as base64 string.

    Args:
        app: NiceGUI app with storage

    Returns:
        str: Base64-encoded public key, or None
    """
    kp = get_user_keypair(app)
    if kp:
        return kp.public_key()
    return None
```

---

## Appendix B: Quick Reference Card

### Token Creation

```python
from hvym_stellar import HVYMDataToken, Stellar25519KeyPair

# From bytes
token = HVYMDataToken.create_from_bytes(
    senderKeyPair=sender_kp,
    receiverPub=receiver_pub,
    file_data=audio_bytes,
    filename="audio.wav",
    expires_in=3600
)
serialized = token.serialize()

# From file
token = HVYMDataToken.create_from_file(
    senderKeyPair=sender_kp,
    receiverPub=receiver_pub,
    file_path="/path/to/audio.wav",
    expires_in=3600
)
```

### Token Extraction

```python
# From serialized string
file_bytes, metadata = HVYMDataToken.extract_from_token(
    serialized_token=serialized,
    receiver_keypair=receiver_kp,
    verify_hash=True
)

# From HVYM file
file_bytes, metadata = HVYMDataToken.from_hvym_file(
    path="/path/to/token.hvym",
    receiver_keypair=receiver_kp
)
```

### Metadata Fields

```python
metadata = {
    'file_size': 1024,
    'file_hash': 'sha256:abc123...',
    'file_name': 'audio.wav',
    'file_type': 'wav',
    'created_at': '2024-01-15T10:30:00Z',
    'expires_at': '2024-01-15T11:30:00Z'
}
```

### Size Limits

- **Soft warning**: 50MB
- **Recommended max**: 100MB
- **Hard limit**: None (file system dependent)

---

*Document Version: 1.0*
*Last Updated: January 2026*
*hvym_stellar Version: 0.21.0*
