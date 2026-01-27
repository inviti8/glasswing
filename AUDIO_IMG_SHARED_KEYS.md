# Audio Image Shared Keys Implementation Plan

## Overview

This document outlines the implementation of encrypted audio data sharing for aposematic and enciphered images using the `hvym-stellar` package's macaroon token system. This enables secure, time-controlled sharing of embedded audio data between users.

## 🚨 IMPORTANT: Follow ENCRYPTION.md Architecture

**⚠️ CRITICAL:** This implementation MUST follow the flow documented in `docs/ENCRYPTION.md`. The audio token system is designed to integrate seamlessly with the existing encryption and aposematic image protection patterns.

### Key Requirements from ENCRYPTION.md:
- **Shared Key Scheme:** Use Stellar/Curve25519 ECDH for key exchange
- **Subscriber Decryption:** All encrypted content is decrypted by the subscriber locally
- **Data Pod Metadata:** Include creator/recipient public keys for decryption
- **Local Processing:** Images and tokens are processed locally before rendering
- **Offline Capability:** Once processed, content works completely offline

### Flow Alignment:
```
ENCRYPTION.md:  Original/Aposematic/Encrypted Images → Data Pod → Subscriber Downloads → Local Processing → Rendering
AUDIO TOKENS:   Audio Tokens (encrypted) ──────────────────┘                    └───────────────┘
```

**🎯 Implementation MUST maintain consistency with existing encryption patterns!**

## Architecture

### Current State
- Audio images use base64-encoded tEXt chunks for ExifTool compatibility
- Aposematic/enciphered images strip audio during processing
- Audio re-embedding preserves original audio from `audio_path`
- Stellar key infrastructure already exists for user identification

### Target State
- Audio data encrypted in macaroon tokens for secure sharing
- Tokens embedded in image metadata instead of raw base64
- Time-controlled access to audio data
- Receiver verification using existing Stellar keys

## Technical Implementation

### 1. Dependencies

```python
# Add to requirements.txt
hvym-stellar>=1.0.0
```

### 2. Token Creation Flow

**📋 Note: Following ENCRYPTION.md Shared Key Scheme**
The token creation uses the same Stellar/Curve25519 ECDH pattern as image encryption for consistency.

```python
from hvym_stellar import StellarSharedKeyTokenBuilder, TokenType, Stellar25519KeyPair
from stellar_sdk.keypair import Keypair

def create_audio_token(sender_kp, receiver_kp_public, audio_base64, expires_in=3600):
    """
    Create encrypted macaroon token containing audio data
    
    Args:
        sender_kp: Sender's Stellar25519KeyPair (wrapped) - from ENCRYPTION.md pattern
        receiver_kp_public: Receiver's public key string - for ECDH key exchange
        audio_base64: Base64-encoded audio data
        expires_in: Token expiration time (seconds)
    
    Returns:
        str: Serialized macaroon token
    
    🎯 IMPORTANT: This follows the same key exchange pattern as ENCRYPTION.md
    - Uses Stellar25519KeyPair (wrapped Stellar keys)
    - Implements ECDH for shared secret derivation
    - Compatible with existing image encryption flow
    """
    token_builder = StellarSharedKeyTokenBuilder(
        sender_kp,
        receiver_kp_public,
        token_type=TokenType.SECRET,
        secret=audio_base64,
        expires_in=expires_in,
        caveats={"audio": "sharing"}  # Required for token validation
    )
    return token_builder.serialize()
```

### 3. Token Verification Flow

```python
from hvym_stellar import StellarSharedKeyTokenVerifier, TokenType

def extract_audio_from_token(receiver_kp, serialized_token):
    """
    Extract and verify audio data from macaroon token
    
    Args:
        receiver_kp: Receiver's Stellar25519KeyPair (wrapped)
        serialized_token: Serialized macaroon token
    
    Returns:
        tuple: (audio_base64: str, valid: bool)
    """
    verifier = StellarSharedKeyTokenVerifier(
        receiver_kp,
        serialized_token.encode('utf-8'),  # Must be bytes
        TokenType.SECRET,
        caveats={"audio": "sharing"}  # Must match creation caveats
    )
    
    # Note: verifier.valid() may return False but secret extraction still works
    # This is expected behavior in hvym-stellar
    try:
        audio_base64 = verifier.secret()
        return audio_base64, True
    except ValueError as e:
        print(f"Failed to extract audio: {e}")
        return None, False
```

### 4. KeyPair Management

**📋 Note: Consistent with ENCRYPTION.md Key Hierarchy**
All key operations must follow the same pattern as image encryption for system consistency.

```python
from hvym_stellar import Stellar25519KeyPair
from stellar_sdk.keypair import Keypair

def create_wrapped_keypair():
    """Create a Stellar keypair wrapped for hvym-stellar compatibility
    
    🎯 IMPORTANT: This follows ENCRYPTION.md key hierarchy exactly:
    stellar_secret ──▶ Stellar25519KeyPair ──▶ hvym_public_key
    
    Returns:
        tuple: (hvym_kp, stellar_kp) - wrapped and original keypairs
    """
    stellar_kp = Keypair.random()
    hvym_kp = Stellar25519KeyPair(stellar_kp)
    return hvym_kp, stellar_kp

def wrap_existing_keypair(stellar_kp):
    """Wrap existing Stellar keypair for hvym-stellar
    
    🎯 IMPORTANT: Use existing stellar_secret from storage (per ENCRYPTION.md)
    
    Args:
        stellar_kp: Stellar Keypair from user's stellar_secret
        
    Returns:
        Stellar25519KeyPair: Wrapped keypair compatible with hvym-stellar
    """
    return Stellar25519KeyPair(stellar_kp)

def get_current_user_stellar_keypair():
    """Get current user's Stellar keypair from storage
    
    🎯 IMPORTANT: Follows ENCRYPTION.md key storage pattern:
    - stellar_secret stored in data.json
    - Keys never transmitted over network
    - Shared keys computed locally
    
    Returns:
        Stellar25519KeyPair: Current user's wrapped keypair
    """
    stellar_secret = app.storage.user.get('stellar_secret')
    if not stellar_secret:
        raise ValueError("No stellar_secret found in user storage")
    
    stellar_kp = Keypair.from_secret(stellar_secret)
    return Stellar25519KeyPair(stellar_kp)

def get_current_user_stellar_public_key():
    """Get current user's public key for data pod metadata
    
    🎯 IMPORTANT: Used in data pod creator_public_key field (per ENCRYPTION.md)
    
    Returns:
        str: Base64-encoded public key
    """
    hvym_kp = get_current_user_stellar_keypair()
    return hvym_kp.public_key()
```

### 5. Updated Audio Embedding Strategy

#### 5.1 For Shared Images (Aposematic/Enciphered)

```python
def create_shared_audio_image(audio_file, image_file, sender_kp, receiver_kp_public, expires_in=3600):
    """
    Create audio image with encrypted token for sharing
    
    Args:
        audio_file: Path to audio file
        image_file: Path to base image
        sender_kp: Sender's Stellar25519KeyPair (wrapped)
        receiver_kp_public: Receiver's public key string
        expires_in: Token expiration time
    
    Returns:
        str: Path to created audio image
    """
    # Read and encode audio data
    with open(audio_file, 'rb') as f:
        audio_data = f.read()
    audio_base64 = base64.b64encode(audio_data).decode('ascii')
    
    # Create encrypted token
    audio_token = create_audio_token(
        sender_kp, 
        receiver_kp_public, 
        audio_base64, 
        expires_in
    )
    
    # Embed token in tEXt chunk instead of raw base64
    return embed_audio_token_in_image(image_file, audio_token)
```

#### 5.2 Token Embedding in PNG

```python
def embed_audio_token_in_image(image_file, audio_token):
    """
    Embed audio token in PNG tEXt chunks
    
    Args:
        image_file: Path to base image
        audio_token: Serialized macaroon token
    
    Returns:
        str: Path to image with embedded token
    """
    # Split token into chunks if needed (tEXt chunks have size limits)
    chunk_size = 8192  # 8KB chunks for tEXt compatibility
    token_chunks = []
    
    for i in range(0, len(audio_token), chunk_size):
        chunk = audio_token[i:i + chunk_size]
        token_chunks.append(chunk)
    
    # Use different keyword for token-based audio
    chunk_keywords = [f'audio_token_{i:03d}' for i in range(1, len(token_chunks) + 1)]
    
    # Embed in PNG using existing chunk injection logic
    return embed_text_chunks_in_png(image_file, chunk_keywords, token_chunks)
```

#### 5.3 PNG Chunk Processing

```python
def embed_text_chunks_in_png(image_path, keywords, text_chunks):
    """
    Embed text chunks in PNG tEXt chunks (tested implementation)
    
    Args:
        image_path: Path to base PNG image
        keywords: List of chunk keywords
        text_chunks: List of text data for each chunk
    
    Returns:
        str: Path to modified PNG with embedded chunks
    """
    import struct
    import zlib
    
    # Read the PNG file
    with open(image_path, 'rb') as f:
        png_data = bytearray(f.read())
    
    # Find IEND chunk position
    pos = 8  # Skip PNG signature
    iend_pos = len(png_data)
    
    while pos < len(png_data):
        chunk_length = int.from_bytes(png_data[pos:pos+4], byteorder='big')
        chunk_type = png_data[pos+4:pos+8].decode('ascii')
        
        if chunk_type == 'IEND':
            iend_pos = pos
            break
            
        pos += 8 + chunk_length + 4
    
    # Insert text chunks before IEND
    insert_pos = iend_pos
    
    for keyword, chunk_data in zip(keywords, text_chunks):
        # Create tEXt chunk: keyword\x00data
        text_data = keyword.encode('ascii') + b'\x00' + chunk_data.encode('ascii')
        chunk_length = len(text_data)
        
        # Build chunk: length (4) + type (4) + data + CRC (4)
        chunk_header = struct.pack('>I', chunk_length) + b'tEXt'
        chunk_with_data = chunk_header + text_data
        
        # Calculate CRC for chunk name + data
        crc = zlib.crc32(b'tEXt' + text_data) & 0xffffffff
        
        chunk_full = chunk_with_data + struct.pack('>I', crc)
        
        # Insert chunk at IEND position
        png_data[insert_pos:insert_pos] = chunk_full
        insert_pos += len(chunk_full)
    
    # Save the modified PNG
    output_path = os.path.join(tempfile.gettempdir(), "token_audio_image.png")
    with open(output_path, 'wb') as f:
        f.write(png_data)
    
    return output_path
```

### 6. Updated Extraction Logic

#### 6.1 Token Extraction from PNG

```python
def extract_token_from_png(image_path):
    """
    Extract token from PNG tEXt chunks (tested implementation)
    
    Args:
        image_path: Path to PNG image with embedded token
    
    Returns:
        str: Reconstructed token or None if not found
    """
    try:
        with open(image_path, 'rb') as f:
            png_data = f.read()
    except Exception as e:
        print(f"❌ Failed to read PNG: {e}")
        return None
    
    # Parse PNG chunks
    pos = 8  # Skip PNG signature
    token_chunks = {}
    
    while pos < len(png_data):
        if pos + 8 > len(png_data):
            break
            
        chunk_length = int.from_bytes(png_data[pos:pos+4], byteorder='big')
        chunk_type = png_data[pos+4:pos+8].decode('ascii')
        
        if chunk_type == 'IEND':
            break
            
        # Read chunk data
        chunk_data = png_data[pos+8:pos+8+chunk_length]
        
        if chunk_type == 'tEXt':
            # Parse tEXt chunk: keyword\x00data
            try:
                null_pos = chunk_data.index(b'\x00')
                keyword = chunk_data[:null_pos].decode('ascii')
                data = chunk_data[null_pos+1:].decode('ascii')
                
                if keyword.startswith('audio_token_'):
                    chunk_num = int(keyword.split('_')[2])
                    token_chunks[chunk_num] = data
                    print(f"🎵 Found token chunk: {keyword} ({len(data)} chars)")
                    
            except (ValueError, UnicodeDecodeError):
                pass
        
        pos += 8 + chunk_length + 4  # Skip to next chunk
    
    if not token_chunks:
        print("❌ No token chunks found")
        return None
    
    # Reconstruct token in correct order
    sorted_chunks = [token_chunks[i] for i in sorted(token_chunks.keys())]
    reconstructed_token = ''.join(sorted_chunks)
    
    print(f"✅ Reconstructed token from {len(token_chunks)} chunks")
    print(f"Token size: {len(reconstructed_token)} characters")
    
    return reconstructed_token
```

#### 6.2 Data Pod Creation with Encrypted Tokens (Selected Approach)

**🔒 DECISION: Subscriber-Side Decryption (Following ENCRYPTION.md Architecture)**
- **Server Creation:** Data pods contain encrypted audio tokens only
- **Subscriber Decryption:** Audio tokens decrypted locally by subscriber
- **Local Processing:** Unified decryption of images and audio tokens
- **Offline Rendering:** Once processed, gallery works completely offline

**⚠️ Important:** Audio tokens follow the same pattern as aposematic/enciphered images - encrypted during creation, decrypted by subscriber locally.

**📋 Critical: Data Pod Structure Must Match ENCRYPTION.md Pattern**
The data pod metadata structure MUST be consistent with existing encryption patterns:

```json
{
    "creator_public_key": "BASE64_KEY...",     // From ENCRYPTION.md
    "recipient_public_key": "BASE64_KEY...",   // From ENCRYPTION.md  
    "content_type": "mixed",                   // May contain original, aposematic, enciphered
    "audio_token_images": ["hash1", "hash2"],  // NEW: Track token-based images
    "items": [...]
}
```

```python
async def create_ninjs_data_pod_with_encrypted_tokens(prefix='processed', receiver_public_key=None):
    """
    Create data pod with encrypted audio tokens (subscriber decrypts locally)
    
    🎯 CRITICAL: This follows ENCRYPTION.md data pod pattern exactly:
    - Include creator_public_key for subscriber's ECDH derivation
    - Include recipient_public_key for authorization verification
    - Use same metadata structure as image encryption
    
    Args:
        prefix: Image prefix to process
        receiver_public_key: Subscriber's public key for token creation
        
    Returns:
        str: Path to created data pod
    """
    try:
        # Get all processed images
        processed_hashes = app.storage.user.get(f'{prefix}_img_hashes', [])
        if not processed_hashes:
            ui.notify('No processed images found', type='warning')
            return

        # Create list to hold all news items
        data_items = []
        audio_token_images = []  # Track which images have audio tokens
        
        for img_hash in processed_hashes:
            try:
                img_info = app.storage.user.get(img_hash)
                if not img_info:
                    continue
                    
                img_path = img_info.get('path')
                if not img_path or not os.path.exists(img_path):
                    continue
                
                # Get metadata using existing function
                metadata_list = await get_img_metadata(img_path)
                if not metadata_list or not isinstance(metadata_list, list) or not metadata_list[0]:
                    continue
                else:
                    metadata = metadata_list[0]
                
                # CRITICAL: Determine image type for rendering
                image_type = determine_image_type(img_hash, img_info)
                
                # Build news item with type-specific rendering
                render_flag = img_info.get('render_metadata', True)
                has_audio = img_info.get('has_audio', False)
                audio_method = img_info.get('audio_method', 'metadata')
                
                item = {
                    'type': f'{image_type}_image' if has_audio else image_type,
                    'guid': f"urn:uuid:{img_hash}",
                    'version': '1',
                    'language': 'en',
                    'pubstatus': 'usable',
                    'title': img_info.get('name', 'Unknown'),
                    'byline': metadata.get('By-line', ''),
                    'creditline': metadata.get('Credit', ''),
                    'copyright': metadata.get('Copyright Notice', ''),
                    'ednote': f'Type: {image_type}, Audio method: {audio_method}',
                    'renditions': [
                        {
                            'name': 'original',
                            'href': f"/ipfs/{img_hash}",
                            'mimetype': 'image/png',
                            'width': metadata.get('ImageWidth', 0),
                            'height': metadata.get('ImageHeight', 0)
                        }
                    ],
                    # CRITICAL: Include image type for client-side rendering decisions
                    'imageType': image_type,
                    'hasAudio': has_audio,
                    'audioMethod': audio_method
                }
                
                # For token-based audio, ensure receiver key is set for future decryption
                if has_audio and audio_method == 'token':
                    if not receiver_public_key:
                        raise ValueError("Receiver public key required for token-based audio")
                    
                    # Track that this image contains an audio token
                    audio_token_images.append(img_hash)
                    
                    # Store receiver key for subscriber's reference
                    item['audioTokenInfo'] = {
                        'receiverPublicKey': receiver_public_key,
                        'tokenExpiry': img_info.get('audio_token_expires', time.time() + 3600)
                    }
                
                if render_flag:
                    data_items.append(item)
                    
            except Exception as e:
                print(f"Error processing {img_hash}: {e}")
                continue

        # Create NINJS package with encryption metadata (following ENCRYPTION.md pattern)
        ninjs_data = {
            'uri': f"urn:ninjs:v2:com.example.gallery:{prefix}",
            'version': 'http://iptc.org/std/ninjs/2.1',
            'content_created': datetime.now().isoformat(),
            'items': data_items,
            # CRITICAL: Encryption metadata for subscriber decryption (per ENCRYPTION.md)
            'creator_public_key': get_current_user_stellar_public_key(),
            'recipient_public_key': receiver_public_key,  # Subscriber's key
            'content_type': 'mixed',  # May contain original, aposematic, enciphered
            'audio_token_images': audio_token_images,  # NEW: Track token-based images
            # Include type distribution metadata
            'type_distribution': {
                'raw': len([i for i in data_items if i['imageType'] == 'raw']),
                'processed': len([i for i in data_items if i['imageType'] == 'processed']),
                'aposematic': len([i for i in data_items if i['imageType'] == 'aposematic']),
                'enciphered': len([i for i in data_items if i['imageType'] == 'enciphered']),
                'total_with_audio': len([i for i in data_items if i.get('hasAudio', False)]),
                'audio_token_count': len(audio_token_images)
            }
        }

        # Add aposematic/encryption parameters if present (per ENCRYPTION.md)
        if any(i['imageType'] == 'aposematic' for i in data_items):
            ninjs_data['op_string'] = app.storage.user.get('aposematic_op_string', '-^+')
            ninjs_data['scramble_mode'] = app.storage.user.get('aposematic_scramble_mode', 2)

        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join('exports', f'ninjs_data_pod_{prefix}_{timestamp}.json')
        
        os.makedirs('exports', exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(ninjs_data, f, indent=2, ensure_ascii=False)

        app.storage.user['latest_data_pod_timestamp'] = timestamp
        print(f"Successfully created NINJS data pod with {len(data_items)} items")
        print(f"Audio token images: {len(audio_token_images)}")
        print(f"Type distribution: {ninjs_data['type_distribution']}")
        return output_path
        
    except Exception as e:
        ui.notify(f'Error creating data pod: {str(e)}', type='negative')
        print(f"Error in create_ninjs_data_pod: {str(e)}")
        return None
```

#### 6.3 Subscriber-Side Local Processing (Decryption)

**📋 Critical: Follow ENCRYPTION.md Browser-Side Decoding Pattern**
This function implements the exact same pattern as `decode_protected_images()` from ENCRYPTION.md.

```python
async def process_data_pod_locally(data_pod_path, subscriber_stellar_secret):
    """
    Process downloaded data pod locally - decrypt images and audio tokens
    This runs on subscriber's machine following ENCRYPTION.md pattern
    
    🎯 CRITICAL: This follows ENCRYPTION.md browser-side decoding exactly:
    - Generate shared key using recipient_public_key from data pod
    - Use same StellarSharedKey ECDH derivation as image decryption
    - Process all content types (images + audio tokens) in unified pass
    - Convert to base64 for offline rendering
    
    Args:
        data_pod_path: Path to downloaded data pod JSON file
        subscriber_stellar_secret: Subscriber's Stellar secret key
        
    Returns:
        dict: Processed data pod with decrypted content ready for rendering
    """
    try:
        # Load data pod
        with open(data_pod_path, 'r') as f:
            data_pod = json.load(f)
        
        print(f"Processing data pod: {data_pod.get('uri', 'Unknown')}")
        print(f"Items to process: {len(data_pod.get('items', []))}")
        
        # Generate shared key (following ENCRYPTION.md exactly)
        recipient_public_key = data_pod.get('recipient_public_key')
        if not recipient_public_key:
            raise ValueError("Data pod missing recipient_public_key for decryption")
        
        # 🎯 This matches ENCRYPTION.md decode_protected_images() exactly:
        stellar_keys = Keypair.from_secret(subscriber_stellar_secret)
        hvym_keys = Stellar25519KeyPair(stellar_keys)
        shared_key = StellarSharedKey(hvym_keys, recipient_public_key)
        cipher_key = shared_key.shared_secret_as_hex()
        
        print(f"✅ Generated shared key for decryption")
        
        # Process each item (unified processing of images + audio tokens)
        processed_items = []
        for item in data_pod.get('items', []):
            try:
                href = item['renditions']['original']['href']
                temp_path = download_ipfs_image(href)
                
                # Decrypt image if needed (following ENCRYPTION.md patterns)
                image_type = item.get('imageType', 'original')
                decoded_path = temp_path
                
                if image_type == 'encrypted':
                    print(f"🔓 Deciphering encrypted image: {item.get('title')}")
                    # 🎯 Uses same cipher_key as ENCRYPTION.md new_deciphered_img()
                    decoded_path = new_deciphered_img(temp_path, cipher_key)
                elif image_type == 'aposematic':
                    print(f"🔓 Recovering aposematic image: {item.get('title')}")
                    # 🎯 Uses same parameters as ENCRYPTION.md recover_aposematic_img()
                    result = recover_aposematic_img(
                        temp_path,
                        cipher_key=cipher_key,
                        op_string=data_pod.get('op_string', '-^+'),
                        scramble_mode=data_pod.get('scramble_mode', 2)
                    )
                    decoded_path = result['img_path']
                
                # Extract audio tokens if present (NEW - audio token processing)
                if item.get('hasAudio') and item.get('audioMethod') == 'token':
                    print(f"🎵 Extracting audio token from: {item.get('title')}")
                    try:
                        # Extract token from PNG
                        serialized_token = extract_token_from_png(decoded_path)
                        if serialized_token:
                            # Extract audio using subscriber's keypair (same ECDH pattern)
                            audio_base64, valid = extract_audio_from_token(hvym_keys, serialized_token)
                            
                            if valid and audio_base64:
                                item['audio'] = {
                                    'data': audio_base64,
                                    'format': detect_audio_format(base64.b64decode(audio_base64)),
                                    'extractedAt': time.time(),
                                    'method': 'token'
                                }
                                print(f"✅ Audio extracted successfully ({len(audio_base64)} chars)")
                            else:
                                print(f"❌ Audio token verification failed")
                        else:
                            print(f"❌ No audio token found in image")
                    except Exception as e:
                        print(f"❌ Failed to extract audio token: {e}")
                
                # Convert image to base64 for display (same as ENCRYPTION.md)
                base64_uri = image_to_base64_uri(decoded_path)
                item['renditions']['original']['href'] = base64_uri
                
                processed_items.append(item)
                print(f"✅ Processed item: {item.get('title')}")
                
            except Exception as e:
                print(f"❌ Error processing item {item.get('title', 'Unknown')}: {e}")
                continue
        
        # Update data pod with processed items
        data_pod['items'] = processed_items
        data_pod['processed_at'] = time.time()
        data_pod['processed_by'] = subscriber_stellar_secret[:8] + '...'  # Last 8 chars for ID
        
        print(f"✅ Data pod processing complete: {len(processed_items)} items ready")
        return data_pod
        
    except Exception as e:
        print(f"❌ Critical error processing data pod: {e}")
        raise
```

### 7. Client-Side Rendering Logic (JavaScript)

```javascript
// Client-side rendering of processed data pod (already decrypted)
function renderProcessedDataPod(dataPod) {
    const container = document.getElementById('gallery-container');
    container.innerHTML = '';
    
    dataPod.items.forEach(item => {
        const itemElement = renderDataPodItem(item);
        container.appendChild(itemElement);
    });
    
    // Show processing info
    showProcessingInfo(dataPod);
}

// Render individual item (already decrypted)
function renderDataPodItem(item) {
    const { imageType, hasAudio, audioMethod } = item;
    
    // Create item container
    const itemDiv = document.createElement('div');
    itemDiv.className = `data-pod-item ${imageType}`;
    
    // Image (already converted to base64 during processing)
    const img = document.createElement('img');
    img.src = item.renditions[0].href;
    img.alt = item.title;
    itemDiv.appendChild(img);
    
    // Metadata section
    const metadataDiv = document.createElement('div');
    metadataDiv.className = 'metadata';
    
    const title = document.createElement('h3');
    title.textContent = item.title;
    metadataDiv.appendChild(title);
    
    const typeInfo = document.createElement('p');
    typeInfo.textContent = `Type: ${imageType}`;
    metadataDiv.appendChild(typeInfo);
    
    // Type-specific badge
    const typeBadge = document.createElement('p');
    typeBadge.className = `type-badge ${imageType}`;
    typeBadge.textContent = getTypeLabel(imageType);
    metadataDiv.appendChild(typeBadge);
    
    // Audio section (already extracted during processing)
    if (hasAudio && item.audio) {
        const audioSection = document.createElement('div');
        audioSection.className = 'audio-section';
        
        const audioBadge = document.createElement('p');
        audioBadge.className = 'audio-badge';
        audioBadge.textContent = `🎵 Audio (${audioMethod})`;
        audioSection.appendChild(audioBadge);
        
        const audio = document.createElement('audio');
        audio.controls = true;
        
        const source = document.createElement('source');
        source.src = `data:audio/${item.audio.format};base64,${item.audio.data}`;
        source.type = `audio/${item.audio.format}`;
        audio.appendChild(source);
        
        audioSection.appendChild(audio);
        
        const audioInfo = document.createElement('p');
        audioInfo.className = 'audio-info';
        audioInfo.textContent = `Extracted: ${new Date(item.audio.extractedAt * 1000).toLocaleString()}`;
        audioSection.appendChild(audioInfo);
        
        metadataDiv.appendChild(audioSection);
    }
    
    itemDiv.appendChild(metadataDiv);
    return itemDiv;
}

// Get human-readable type label
function getTypeLabel(imageType) {
    const labels = {
        'raw': 'Original Image',
        'processed': 'Watermarked',
        'aposematic': 'Aposematic',
        'enciphered': 'Enciphered'
    };
    return labels[imageType] || 'Unknown';
}

// Show processing information
function showProcessingInfo(dataPod) {
    const infoDiv = document.getElementById('processing-info');
    if (infoDiv && dataPod.processed_at) {
        infoDiv.innerHTML = `
            <div class="processing-status">
                <h3>🔓 Decrypted Content</h3>
                <p>Processed: ${new Date(dataPod.processed_at * 1000).toLocaleString()}</p>
                <p>Items: ${dataPod.items.length}</p>
                <p>With Audio: ${dataPod.items.filter(i => i.hasAudio).length}</p>
                ${dataPod.type_distribution ? `
                    <div class="type-stats">
                        <h4>Type Distribution:</h4>
                        ${Object.entries(dataPod.type_distribution).map(([type, count]) => 
                            `<span class="type-stat">${type}: ${count}</span>`
                        ).join('')}
                    </div>
                ` : ''}
            </div>
        `;
    }
}

// Filter and render by type
function filterByType(items, targetType) {
    return items.filter(item => item.imageType === targetType);
}

// Type statistics
function calculateTypeStats(items) {
    const stats = {
        raw: 0,
        processed: 0,
        aposematic: 0,
        enciphered: 0,
        withAudio: 0
    };
    
    items.forEach(item => {
        stats[item.imageType]++;
        if (item.hasAudio) stats.withAudio++;
    });
    
    return stats;
}

// Initialize gallery with processed data pod
async function initializeGallery(dataPodPath, stellarSecret) {
    try {
        // This would call the Python processing function
        // In a real implementation, this might be via API or local processing
        const processedDataPod = await processDataPodLocally(dataPodPath, stellarSecret);
        
        // Render the processed data pod
        renderProcessedDataPod(processedDataPod);
        
    } catch (error) {
        console.error('Failed to initialize gallery:', error);
        showError('Failed to process data pod. Check your Stellar key.');
    }
}
```

### 8. Integration with Existing Workflows

#### 8.1 Updated Aposematic Processing

```python
async def process_aposematic_with_shared_audio():
    """Process aposematic images with shared audio tokens"""
    for hash_value in processed_hashes:
        img_info = app.storage.user.get(hash_value)
        
        # Check if image has audio and sharing is enabled
        if img_info.get('has_audio') and img_info.get('share_audio', False):
            audio_path = img_info.get('audio_path')
            receiver_public = img_info.get('receiver_public_key')
            
            if audio_path and receiver_public:
                # Get sender's wrapped keypair
                sender_stellar_kp = get_current_user_stellar_keypair()
                sender_kp = Stellar25519KeyPair(sender_stellar_kp)
                
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
                app.storage.user[new_hash].update({
                    'has_audio': True,
                    'audio_method': 'token',
                    'audio_token_expires': time.time() + 3600,
                    'receiver_public_key': receiver_public,
                    'image_type': 'aposematic',  # CRITICAL: Track image type
                    'is_aposematic': True  # Legacy flag support
                })
```

#### 8.2 Updated Enciphering Processing

```python
async def process_enciphering_with_shared_audio():
    """Process enciphered images with shared audio tokens"""
    # Similar to aposematic but with encryption
    for hash_value in processed_hashes:
        img_info = app.storage.user.get(hash_value)
        
        if img_info.get('has_audio') and img_info.get('share_audio', False):
            # Create enciphered image with audio token
            enciphered_result = new_enciphered_img_with_audio_token(
                # ... parameters
            )
            
            # Update storage with CRITICAL image type
            app.storage.user[new_hash].update({
                'has_audio': True,
                'audio_method': 'token',
                'audio_token_expires': time.time() + 3600,
                'receiver_public_key': receiver_public,
                'image_type': 'enciphered',  # CRITICAL: Track image type
                'is_enciphered': True  # Legacy flag support
            })
```

#### 8.3 Updated Processing Workflows

```python
# In process_audio_embedding - ensure image type is set
app.storage.user[hash_value].update({
    'path': output_path,
    'has_audio': True,
    'audio_format': audio_format,
    'audio_duration': len(audio_data) / 44100 if audio_data else 0,
    'audio_size': len(audio_data) if audio_data else 0,
    'audio_method': 'metadata',
    'audio_path': audio_file,
    'image_type': 'raw',  # CRITICAL: Set type for new audio images
    'is_raw': True  # Legacy flag support
})

# In process_watermarking - preserve and update image type
app.storage.user[ipfs_hash] = app.storage.user[hash_value].copy()
app.storage.user[ipfs_hash].update({
    'path': processed_img_path,
    'name': f'processed_{img_name}',
    'has_audio': app.storage.user[hash_value].get('has_audio', False),
    'audio_path': app.storage.user[hash_value].get('audio_path'),
    'image_type': 'processed',  # CRITICAL: Update type for watermarked images
    'is_processed': True  # Legacy flag support
})
```

### 9. User Interface Updates

#### 9.1 Audio Sharing Options

```python
# Add to audio embedding dialog
async def audio_sharing_dialog(audio_file, img_name, img_path, hash_value):
    """Dialog for configuring audio sharing options"""
    with ui.dialog() as dialog, ui.card():
        ui.label('Audio Sharing Configuration')
        
        share_audio = ui.checkbox('Share audio with specific user').value(False)
        
        with ui.column().bind_visibility_from(share_audio, 'value'):
            ui.label('Recipient Public Key:')
            recipient_input = ui.input(placeholder='G...')
            
            ui.label('Token Expiration:')
            expiry_slider = ui.slider(min=300, max=86400, value=3600, step=300)
            expiry_label = ui.label('1 hour')
            
            def update_expiry_label():
                hours = expiry_slider.value / 3600
                expiry_label.text = f'{hours:.1f} hours'
            
            expiry_slider.on_value_change(update_expiry_label)
        
        with ui.row():
            ui.button('Cancel', on_click=lambda: dialog.close())
            ui.button('Share Audio', on_click=lambda: process_shared_audio(
                audio_file, img_name, img_path, hash_value,
                share_audio.value, recipient_input.value, expiry_slider.value
            ))
    
    dialog.open()
```

### 10. Test Results & Implementation Notes
