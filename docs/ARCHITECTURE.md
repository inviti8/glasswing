# Andromica Technical Architecture

## Overview

Andromica is a decentralized content creation and distribution system built on IPFS and Stellar cryptography. It enables creators to publish protected galleries that can only be viewed by authorized subscribers. The application supports embedding encrypted audio, video, and markdown tokens in images using HVYMDataToken (Biscuit-based, ChaCha20-Poly1305 encryption). An image supports audio OR video (not both), plus markdown independently.

## System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        ANDROMICA                                 │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────┐    ┌─────────────────────┐            │
│  │    IMAGE MODE       │    │    BROWSER MODE     │            │
│  │    (Creator)        │    │    (Consumer)       │            │
│  ├─────────────────────┤    ├─────────────────────┤            │
│  │ • Import images     │    │ • Subscribe to      │            │
│  │ • Process/watermark │    │   channels          │            │
│  │ • Add metadata      │    │ • Fetch data pods   │            │
│  │ • Embed audio/video │    │ • Decrypt content   │            │
│  │ • Embed markdown    │    │ • Extract audio/    │            │
│  │ • Create aposematic │    │   video/markdown    │            │
│  │ • Encrypt images    │    │ • Render galleries  │            │
│  │ • Deploy to IPFS    │    │                     │            │
│  └─────────────────────┘    └─────────────────────┘            │
├─────────────────────────────────────────────────────────────────┤
│                      SHARED SERVICES                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │  IPFS    │ │ Stellar  │ │ Pintheon │ │ Storage  │           │
│  │  Client  │ │ Crypto   │ │ Deploy   │ │ Manager  │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

## Core Modules

### main.py
Primary application entry point and UI orchestration.

**Key Functions:**
- `init(restore_secret=None)` - Application initialization, storage setup, key generation
- `_first_run_dialog()` - NEW/RESTORE identity dialog on first launch (no data.json)
- `render_gallery()` - Display images based on current view state
- `render_gallery_html()` - Render data pod to HTML using selected Jinja2 template
- `process_watermarking()` - Apply watermarks to raw images
- `process_aposematic()` - Generate scrambled images with visual noise
- `process_enciphering()` - Generate encrypted images via ImageMagick
- `process_deciphering()` - Decrypt enciphered images
- `process_audio_embedding()` - Embed encrypted audio token in image
- `process_video_embedding()` - Embed encrypted video token in image (via IPFS CID)
- `process_markdown_embedding()` - Embed encrypted markdown token in image
- `reembed_media_if_needed()` - Re-embed audio/video chunks after image processing (markdown excluded)
- `play_video_from_image()` - Fetch, decrypt, and play video from image
- `remove_video_from_image()` - Strip video CID chunks and unpin from IPFS
- `create_ninjs_data_pod()` - Create NINJS-format data pod from current images
- `process_debug_deploy_gallery()` - Debug deployment with local decryption
- `process_pintheon_deploy_gallery()` - Production deployment to Pintheon node
- `detect_ipfs_gateway_port()` - Query IPFS daemon for gateway port at startup
- `_pintheon_url(base_url=None)` - Resolve Pintheon URL from storage or parameter
- `pintheon_get_directory_ipns()` - Get IPNS hash for a Pintheon directory
- `_subscriber_public_key()` - Derive subscriber's Stellar 25519 public key from App Key
- `fetch_subscription_content()` - Fetch data pods from Pintheon via stellar.toml IPNS resolution
- `fetch_subscription_channels()` - List available data pods (channels) from a subscription
- `select_channel()` - Download, decrypt, and render a subscription's data pod
- `GALLERY_TEMPLATES` - Registry of gallery templates (default, album, artspace, book, theater)

**Session-Scoped Storage:**
- `EDITOR_STORAGE_DIR` - `tempfile.mkdtemp()` served via FastAPI StaticFiles at `/editor`
- Raw and processed images stored locally (not on IPFS) during editing
- `_local_store_image_pure()` - Store image in session temp dir, returns `(hash, name, editor_url)`

**Global State:**
- `app.storage.user` - Persistent user data (NiceGUI storage)
- `img_states = {1: 'raw', 2: 'processed', 3: 'aposematic', 4: 'enciphered'}`

### data_pod_audio.py
Data pod creation and processing with audio/video/markdown token support.

**Key Functions:**
- `determine_image_type()` - Identify image state from metadata/storage
- `create_ninjs_data_pod_with_encrypted_tokens()` - Create encrypted data pods with audio/video/markdown metadata
- `process_data_pod_locally()` - Decrypt data pod for subscriber viewing (audio + video + markdown recovery)

### audio_tokens.py
Encrypted audio token handling using HVYMDataToken.

**Key Functions:**
- `create_audio_token()` - Create encrypted audio token
- `create_token_audio_image()` - Embed encrypted token in image PNG tEXt chunks
- `extract_audio_from_token()` - Decrypt audio from token
- `extract_token_audio()` - Full extraction pipeline from image

### video_tokens.py
Encrypted video token handling using HVYMDataToken + IPFS.

Video tokens are too large for PNG tEXt chunks, so the encrypted token is stored on IPFS and only the CID (~50 bytes) is embedded in the PNG.

**Key Functions:**
- `create_video_token()` - Create encrypted video token
- `create_token_video_image()` - Encrypt video → upload to IPFS → embed CID in PNG
- `extract_video_from_token()` - Decrypt video from token
- `extract_token_video()` - Fetch CID from PNG → download from IPFS → decrypt
- `detect_video_format()` - Detect format via magic bytes
- `is_video_file()` - Check file extension against supported formats

**Supported Formats:** MP4, WebM, MOV, AVI, MKV

### markdown_tokens.py
Encrypted markdown token handling using HVYMDataToken.

Markdown files are bundled into a single JSON payload, encrypted as one HVYMDataToken, and stored in PNG tEXt chunks (same pattern as audio). Multiple files per image are supported.

**Key Functions:**
- `create_markdown_token()` - Create encrypted markdown token
- `create_token_markdown_image()` - Bundle .md files, encrypt, embed in PNG
- `extract_markdown_from_token()` - Decrypt markdown from token
- `extract_token_markdowns()` - Full extraction pipeline from image

**Supported Extensions:** `.md`, `.markdown`, `.txt`

**Size Limit:** 1 MB total across all bundled files

### png_chunks.py
PNG tEXt chunk manipulation for audio/video/markdown embedding.

**Key Functions:**
- `embed_audio_token()` - Embed encrypted audio token in PNG tEXt chunks
- `extract_audio_token()` - Extract audio token from PNG
- `has_audio_data()` - Check if PNG contains audio token
- `embed_video_token_cid()` - Embed video IPFS CID in PNG tEXt chunks
- `extract_video_token_cid()` - Extract video CID from PNG
- `has_video_data()` - Check if PNG contains video CID
- `embed_markdown_token()` - Embed encrypted markdown token in PNG tEXt chunks
- `extract_markdown_token()` - Extract markdown token from PNG
- `has_markdown_data()` - Check if PNG contains markdown token
- `copy_token_chunks()` - Copy tEXt chunks between PNGs (used during reprocessing)
- `remove_text_chunks()` - Strip tEXt chunks by prefix (used when removing media)

### img_edit.py
Image processing and manipulation.

**Key Functions:**
- `new_watermarked_img()` - Apply watermark overlay
- `new_enciphered_img()` - Encrypt image using ImageMagick
- `new_deciphered_img()` - Decrypt image
- `new_iptc_img()` - Write IPTC metadata
- `COPY_ALPHA_OP` - Cross-platform constant: `'copy_alpha'` (ImageMagick 7) or `'copy_opacity'` (ImageMagick 6)

### dialogs.py
UI dialog components for user interactions.

**Key Functions:**
- `create_shared_key()` - Generate shared encryption key via ECDH
- `get_recipient_options()` - Build subscriber dropdown options
- `cipher_dialog()` - Encryption recipient selection
- `aposematic_dialog()` - Aposematic settings and recipient selection
- `edit_audio_info()` - Audio embedding dialog (file picker, recipient, expiry)
- `edit_video_info()` - Video embedding dialog (file picker, recipient, expiry)
- `edit_markdown_info()` - Markdown embedding dialog (file picker, recipient, expiry)
- `process_dialog()` - Async task runner with progress UI
- `add_subscription_dialog()` - Add Pintheon node subscription (label + URL)
- `view_subscriptions_dialog()` - List/manage subscriptions with fetch/remove
- `select_channel_dialog()` - Select and load a data pod channel from subscription
- `gallery_info_dialog()` - Gallery title, description, and template selection

---

## Image Processing Pipeline

### State Progression

```
┌─────────┐    ┌───────────┐    ┌─────────────────────────────────┐
│  RAW    │───▶│ PROCESSED │───▶│   APOSEMATIC  or  ENCIPHERED   │
│         │    │           │    │   (choose one protection type)  │
└─────────┘    └───────────┘    └─────────────────────────────────┘
     │              │                           │
     ▼              ▼                           ▼
  Import       Watermark,                  Select recipient,
  from         resize,                     generate shared key,
  folder       add metadata,               apply protection
               embed audio/video
```

### Image States

| State | Index | Description | Storage Key |
|-------|-------|-------------|-------------|
| Raw | 1 | Original imported images | `raw_img_hashes` |
| Processed | 2 | Watermarked, metadata added, audio/video embedded | `processed_img_hashes` |
| Aposematic | 3 | Visually scrambled (reversible with key) | `aposematic_img_hashes` |
| Enciphered | 4 | Fully encrypted (ImageMagick cipher) | `enciphered_img_hashes` |

### Processing Functions

#### 1. Watermarking (`process_watermarking()`)
```python
async def process_watermarking():
    for hash_value in raw_img_hashes:
        # Apply watermark overlay
        watermarked_path = await new_watermarked_img(
            file_name, img_path, watermark_path,
            amount=watermark_size,
            position=watermark_position,
            padding=watermark_padding
        )
        # Re-embed audio/video chunks if original had them
        watermarked_path = reembed_media_if_needed(watermarked_path, original_path)
        # Store locally and update storage
        new_hash, _, editor_url = _local_store_image_pure(watermarked_path)
        processed_img_hashes.append(new_hash)
```

#### 2. Aposematic Processing (`process_aposematic()`)
```python
async def process_aposematic():
    for hash_value in processed_img_hashes:
        # Apply visual scrambling (aiposematic v1.1 native Stellar key integration)
        aposematic = new_aposematic_img(
            img_path,
            stellar_keypair=creator_keys,           # Creator's Stellar25519KeyPair
            subscriber_public_key=recipient_pub,    # Recipient's public key
            op_string="-^+",                        # Operation sequence
            scramble_mode=SCRAMBLE_MODE             # BUTTERFLY or QR
        )
        aposematic_img_path = aposematic["img_path"]

        # CRITICAL: Re-embed audio/video (scrambling creates new PNG without tEXt chunks)
        aposematic_img_path = reembed_media_if_needed(aposematic_img_path, original_path)

        # Add to IPFS
        ipfs_hash, _, _ = _ipfs_add_pure(aposematic_img_path)
        aposematic_img_hashes.append(ipfs_hash)
```

**Aposematic Characteristics:**
- Uses `aiposematic` v1.1 with native Stellar key derivation (domain-separated hashing)
- Scramble modes: BUTTERFLY (default), QR
- Operation string (`op_string`) controls scramble sequence
- Reversible with same Stellar keypair and op_string
- Creates NEW PNG file (does not preserve tEXt chunks — media must be re-embedded)

#### 3. Enciphering (`process_enciphering()`)
```python
async def process_enciphering():
    for hash_value in processed_img_hashes:
        # Encrypt via ImageMagick
        enciphered_path = await new_enciphered_img(
            file_name,
            img_path,
            cipher_key
        )
        # NOTE: Audio/video is NOT re-embedded for enciphered images
        # (encryption would corrupt embedded data)

        ipfs_hash, _, _ = _ipfs_add_pure(enciphered_path)
        enciphered_img_hashes.append(ipfs_hash)
```

**Enciphering Characteristics:**
- Uses ImageMagick's `encipher()` function
- Full image encryption (pixels become unrecognizable)
- Audio/video cannot be preserved in enciphered images (data corruption)
- Requires exact cipher_key for decryption
- Audio/video tokens extracted from original processed image via `original_hash`

#### 4. Deciphering (`process_deciphering()`)
```python
async def process_deciphering():
    for hash_value in enciphered_img_hashes:
        deciphered_path = new_deciphered_img(
            file_name,
            encrypted_img_path,
            cipher_key
        )
        new_hash, _, editor_url = _local_store_image_pure(deciphered_path)
        deciphered_img_hashes.append(new_hash)
```

### Aposematic vs Enciphered Comparison

| Feature | Aposematic | Enciphered |
|---------|------------|------------|
| Visual appearance | Scrambled pattern visible | Completely encrypted |
| Media support | Yes (re-embedded after scramble) | Yes (via `original_hash` reference) |
| Media location | In the aposematic image tEXt chunks | Extracted from original processed image |
| Reversibility | Same Stellar keypair + op_string | Same cipher_key only |
| Library | aiposematic v1.1 | ImageMagick (Wand) |
| Key input | `stellar_keypair` + `subscriber_public_key` | `cipher_key` (ECDH hex) |
| Use case | Visual protection with media | Maximum security with media |

**Note on Enciphered Media:** ImageMagick's `encipher()` creates a new PNG that doesn't preserve tEXt chunks. Audio/video cannot be re-embedded into enciphered images because it would corrupt the encryption. Instead, media tokens are extracted from the original processed image using the `original_hash` reference stored in the data pod.

---

## Media Embedding Flow

### Audio, Video, and Markdown Embedding

An image supports **audio OR video** (not both), **plus markdown independently**. The editor UI enforces audio/video mutual exclusion; markdown can coexist with either.

| Media | Storage | Encryption | tEXt Chunk Keywords |
|-------|---------|------------|---------------------|
| Audio | Encrypted token in PNG tEXt chunks | HVYMDataToken (ChaCha20-Poly1305) | `audio_token_001`, `audio_token_002`, ... |
| Video | Encrypted token on IPFS; CID in PNG tEXt chunks | HVYMDataToken (ChaCha20-Poly1305) | `video_token_cid_001`, `video_token_cid_002`, ... |
| Markdown | Encrypted token in PNG tEXt chunks | HVYMDataToken (ChaCha20-Poly1305) | `markdown_token_001`, `markdown_token_002`, ... |

### Audio Token Embedding

```python
# audio_tokens.py
def create_token_audio_image(audio_file, image_file, sender_kp, receiver_pub, expires_in):
    audio_data = read_audio_bytes(audio_file)
    token = create_audio_token(sender_kp, receiver_pub, audio_data, filename, expires_in)
    return embed_audio_token(image_file, token, output_path)
```

### Video Token Embedding

Video tokens are too large for PNG tEXt chunks, so they are stored on IPFS with only the CID embedded in the PNG.

```python
# video_tokens.py
def create_token_video_image(video_file, image_file, sender_kp, receiver_pub,
                             expires_in=3600, ipfs_add_fn=None):
    video_data = read_video_bytes(video_file)
    token = create_video_token(sender_kp, receiver_pub, video_data, filename, expires_in)
    # Upload encrypted token to IPFS
    cid = ipfs_add_fn(token_temp_path)
    # Embed only the CID (~50 bytes) in the PNG
    output_path = embed_video_token_cid(image_file, cid)
    return output_path, cid
```

### PNG tEXt Chunk Storage

```
┌─────────────────────────────────────────────────────────┐
│                    PNG FILE STRUCTURE                    │
├─────────────────────────────────────────────────────────┤
│  PNG Signature (8 bytes)                                │
│  IHDR chunk (image header)                              │
│  ... other chunks ...                                   │
│  IDAT chunks (pixel data - may be scrambled)           │
│  ┌─────────────────────────────────────────────────┐   │
│  │  tEXt: audio_token_001 = <encrypted token>      │   │
│  │  tEXt: audio_token_002 = <encrypted token>      │   │
│  │  ... (8KB max per chunk)                        │   │
│  │                 OR                               │   │
│  │  tEXt: video_token_cid_001 = <IPFS CID>        │   │
│  │                                                  │   │
│  │  tEXt: markdown_token_001 = <encrypted token>   │   │
│  │  ... (can coexist with audio or video)          │   │
│  └─────────────────────────────────────────────────┘   │
│  IEND chunk                                             │
└─────────────────────────────────────────────────────────┘
```

### Critical: Media Preservation Through Pipeline

**Problem:** Image transformation functions create NEW PNG files that don't preserve tEXt chunks:
- `new_aposematic_img()` / `recover_aposematic_img()` - PIL creates new image
- `new_enciphered_img()` / `new_deciphered_img()` - ImageMagick creates new image

**Solution — Creator Side:** `reembed_media_if_needed()` copies audio and video tEXt chunks from the source PNG into the target PNG after any transformation. Markdown chunks are NOT reembedded — the serialized markdown token is stored in the data pod JSON instead.

```python
def reembed_media_if_needed(target_image_path, source_image_path):
    if source_image_path and os.path.exists(source_image_path):
        target_image_path = copy_token_chunks(source_image_path, target_image_path)
        target_image_path = copy_token_chunks(
            source_image_path, target_image_path,
            keyword_prefix=VIDEO_TOKEN_CID_PREFIX
        )
        # NOTE: Markdown chunks are NOT reembedded — stored in data pod JSON
    return target_image_path
```

**Solution — Subscriber Side (Aposematic):** Pre-extract audio tokens and video CIDs from the encrypted PNG BEFORE recovery, since recovery creates a new PNG that loses tEXt chunks. Markdown tokens are read from the data pod JSON (not the image).

```python
# Pre-extract before recovery (data_pod_audio.py)
pre_extracted_audio = extract_audio_token(temp_path)
pre_extracted_video_cid = extract_video_token_cid(temp_path)

# THEN recover the image (creates new PNG without tEXt chunks)
decoded_path = recover_aposematic_img(temp_path, stellar_keypair=..., artist_public_key=...)
```

**Solution — Subscriber Side (Enciphered):** Extract media from ORIGINAL processed image (via `original_hash`), since enciphered images can't preserve tEXt chunks at all.

**Why Enciphered is Different:**
- ImageMagick `encipher()` encrypts the entire image data structure
- Re-embedding media after encryption would corrupt the encrypted payload
- Solution: Keep reference to original processed image via `original_hash`

---

## Key Management

### Key Types

| Key | Source | Purpose |
|-----|--------|---------|
| `stellar_secret` | Generated or imported | Creator's master key |
| `hvym_public_key` | Derived from stellar_secret | Creator's public identity |
| `debug_secret` | Auto-generated | Testing without real keys |
| `debug_public_key` | Derived from debug_secret | Debug recipient identity |
| `cipher_key` | ECDH shared secret | Encryption/decryption key |

### ECDH Shared Key Derivation

Two patterns are used depending on the operation:

**Aposematic (aiposematic v1.1 — native Stellar):** Pass keypairs directly; aiposematic derives the cipher key internally using domain-separated hashing: `SHA256(shared_secret + ":aiposematic:sbox")[:32]`.

```python
from hvym_stellar import Stellar25519KeyPair
from stellar_sdk import Keypair

# Creator side — pass keypair + subscriber public key
creator_keys = Stellar25519KeyPair(Keypair.from_secret(creator_stellar_secret))
new_aposematic_img(img, stellar_keypair=creator_keys, subscriber_public_key=recipient_pub)

# Subscriber side — pass keypair + artist public key
subscriber_keys = Stellar25519KeyPair(Keypair.from_secret(subscriber_secret))
recover_aposematic_img(img, stellar_keypair=subscriber_keys, artist_public_key=creator_pub)
```

**Enciphered (ImageMagick) and non-aposematic operations:** Derive `cipher_key` manually.

```python
from hvym_stellar import StellarSharedKey, Stellar25519KeyPair
from stellar_sdk import Keypair

creator_keys = Stellar25519KeyPair(Keypair.from_secret(creator_stellar_secret))
shared_key = StellarSharedKey(creator_keys, recipient_public_key)
cipher_key = shared_key.shared_secret_as_hex()
```

### Key Flow in Debug vs Production

**Debug Flow:**
- Creator: `debug_secret` / `debug_public_key`
- Recipient: `stellar_secret` / `hvym_public_key` (app's own key)
- Purpose: Test encryption locally where app can decrypt

**Pintheon Flow:**
- Creator: `stellar_secret` / `hvym_public_key`
- Recipient: Subscriber's public key
- Purpose: Real encryption for external subscribers

---

## Deployment Flows

### Debug Deployment (`process_debug_deploy_gallery()`)

```
┌─────────────┐    ┌───────────┐    ┌─────────────┐    ┌──────────┐
│   CREATE    │───▶│  RECREATE │───▶│   DECRYPT   │───▶│  RENDER  │
│ DATA POD    │    │ APOSEMATIC│    │   locally   │    │  gallery │
│ with debug  │    │ with      │    │             │    │          │
│   keys      │    │ shared key│    │             │    │          │
└─────────────┘    └───────────┘    └─────────────┘    └──────────┘
      │                  │                 │                 │
      ▼                  ▼                 ▼                 ▼
   Debug key        Correct shared      App's secret      Local preview
   as creator       key for app to      decrypts          with decrypted
   + app key        decrypt             shared key        images
   as recipient
```

**Steps:**
1. Validate image state
2. Create data pod with `hvym_public_key` as creator, `debug_public_key` as recipient
3. Process data pod locally using `debug_secret` (decrypts images + audio/video/markdown tokens)
4. Render HTML with decrypted images and media
5. Display in browser tab

### Pintheon Deployment (`process_pintheon_deploy_gallery()`)

```
┌─────────────┐    ┌───────────┐    ┌─────────────┐    ┌──────────┐
│   CREATE    │───▶│  UPLOAD   │───▶│   UPLOAD    │───▶│  STORE   │
│ DATA POD    │    │  IMAGES   │    │  DATA POD   │    │  HASH    │
│ with real   │    │  to       │    │  to         │    │          │
│   keys      │    │ Pintheon  │    │ Pintheon    │    │          │
└─────────────┘    └───────────┘    └─────────────┘    └──────────┘
      │                  │                 │                 │
      ▼                  ▼                 ▼                 ▼
   Creator's        All images         JSON data        Subscribers
   real key         in state           pod with         access via
   + subscriber's   uploaded           encryption       IPNS hash
   public key                          metadata
```

**Steps:**
1. Resolve Pintheon URL from storage (`_pintheon_url()`)
2. Check Pintheon running (`is_pintheon_running()`) and access token
3. Validate image state
4. Create data pod with creator key + recipient (subscriber) public key
5. Clean IPFS MFS folder and re-add gallery images
6. Create directory on Pintheon named by subscriber's public key
7. Upload all images with proper filenames (not temp names)
8. Upload data pod JSON to same directory
9. Query IPNS hash via `pintheon_get_directory_ipns()`
10. Show deployment summary dialog (IPNS hash, file hashes, copy buttons)
11. Pintheon auto-publishes to IPNS and updates `stellar.toml` `[SUBSCRIBER_DIRECTORIES]`

**Pintheon API Notes:**
- Default endpoint: `https://local.pintheon.com:9999` (private port)
- SSL `verify=False` for self-signed certs
- All API functions accept `base_url` parameter for `run.io_bound` calls (avoids `app.storage.user` access outside UI context)
- Directory name = subscriber's Stellar 25519 public key (each subscriber gets their own IPNS channel)

**Key Difference:** Debug flow decrypts locally for preview; Pintheon flow is deployment-only (subscribers decrypt on their end).

---

## Consumer/Browser Flow

### Data Pod Processing (`process_data_pod_locally()`)

```
┌─────────────┐    ┌───────────┐    ┌─────────────┐    ┌──────────┐
│  DOWNLOAD   │───▶│PRE-EXTRACT│───▶│   DECRYPT   │───▶│  RENDER  │
│  data pod   │    │AUDIO+VIDEO│    │   images    │    │  gallery │
│  + images   │    │  (before  │    │  + process  │    │  with    │
│  from IPFS  │    │  recovery)│    │ audio/video │    │  media   │
└─────────────┘    └───────────┘    └─────────────┘    └──────────┘
      │                  │                 │                 │
      ▼                  ▼                 ▼                 ▼
   Load JSON,       Extract tokens    Generate keys,     HTML with
   fetch images     and video CIDs    recover images,    base64 images
   via IPFS API     from PNG chunks   decrypt tokens     + media players
```

**Processing Steps:**

1. **Load Data Pod**
   - Parse JSON from file
   - Extract creator_public_key, recipient_public_key

2. **Generate Shared Key**
   ```python
   subscriber_keys = Stellar25519KeyPair(Keypair.from_secret(subscriber_secret))
   # For aposematic: pass keypair directly to recover_aposematic_img()
   # For enciphered: derive cipher_key via StellarSharedKey
   ```

3. **For Each Item:**
   - Download image from IPFS
   - **Pre-extract audio token** (BEFORE recovery - critical!)
   - **Pre-extract video CID** (BEFORE recovery - critical!)
   - **Load markdown token** from data pod JSON (not from image)
   - Decrypt/recover image based on type
   - Process pre-extracted audio (decrypt token)
   - Process pre-extracted video (fetch from IPFS → decrypt token → write to temp dir)
   - Process markdown (decrypt token → convert to HTML via markdown2)
   - Update item with decrypted image href, audio data, video src URL, and markdown HTML

4. **Render Gallery**
   - Use Jinja2 template with processed data pod
   - Images as IPFS URLs or base64 data URIs
   - Audio as base64 in `<audio>` element
   - Video as `/editor/{filename}` URL in `<video>` element with fullscreen player overlay

---

## Browser Mode: Add Channel Flow

### Overview

Browser Mode is a viewing/consumption mode for displaying gallery content from Pintheon channels. It uses an iframe-based HTML renderer to display rich gallery layouts. Users subscribe to content sources, then select and view channels within those subscriptions.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         BROWSER MODE FLOW                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐            │
│   │     ADD      │────▶│    SELECT    │────▶│    VIEW      │            │
│   │ SUBSCRIPTION │     │   CHANNEL    │     │   GALLERY    │            │
│   └──────────────┘     └──────────────┘     └──────────────┘            │
│         │                    │                    │                      │
│         ▼                    ▼                    ▼                      │
│   • Pintheon URL       • Fetch channels    • Render HTML               │
│   • IPNS Hash          • Select from list  • Display in iframe         │
│   • Store locally      • Load data pod     • Play audio/video          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### App Mode Toggle

The application has two modes controlled by `app.storage.user["app_mode"]`:

| Mode | Value | Purpose | UI Tab |
|------|-------|---------|--------|
| Image Mode | `"image"` | Create and process images | IMAGES tab |
| Browser Mode | `"browser"` | View subscribed channels | BROWSER tab |

```python
# main.py:3543-3546
def toggle_app_mode():
    current = app.storage.user.get("app_mode", "image")
    app.storage.user["app_mode"] = "browser" if current == "image" else "image"
```

### Step 1: Add Subscription

Users add subscriptions via `add_subscription_dialog()` in `dialogs.py:381-408`.

**Dialog Input:**
- **Subscription Name**: User-friendly identifier
- **Pintheon Node URL**: e.g., `https://some-pintheon.com`
- **IPNS Hash**: e.g., `k51qzi5uqu5d...`

```python
# main.py:2259-2277
def add_subscription(name: str, url: str, ipns_hash: str):
    subscriptions = app.storage.user.get("subscriptions", [])
    subscriptions.append({
        "name": name,
        "url": url,
        "ipns_hash": ipns_hash
    })
    app.storage.user["subscriptions"] = subscriptions
    persistent_save_data()  # Persist to data.json
```

### Step 2: Fetch Channels from Subscription

When a user selects a subscription, channels are fetched from the IPNS address.

```python
# main.py:2614-2663
async def fetch_subscription_channels(subscription_name: str):
    subscription = get_subscription_by_name(subscription_name)
    if not subscription:
        return []

    # Resolve IPNS to get directory listing
    ipns_hash = subscription["ipns_hash"]
    gateway_url = subscription["url"]

    # Fetch IPNS content (returns list of channel entries)
    channels = await ipns_resolve_and_list(gateway_url, ipns_hash)

    return channels  # List of {name, description, data_pod_hash}
```

### Step 3: Select Channel

The `select_channel_dialog()` in `dialogs.py:452-524` presents available channels.

```
┌─────────────────────────────────────────────────┐
│           SELECT CHANNEL DIALOG                  │
├─────────────────────────────────────────────────┤
│  Subscription: [Dropdown - My Gallery    ▼]     │
│                                                  │
│  Channels:                                       │
│  ┌─────────────────────────────────────────┐    │
│  │ Channel A      (12 items)    [Select]  │    │
│  │ Channel B      (8 items)     [Select]  │    │
│  │ Channel C      (24 items)    [Select]  │    │
│  └─────────────────────────────────────────┘    │
│                                                  │
│                              [Cancel]           │
└─────────────────────────────────────────────────┘
```

When user clicks "Select", it calls `select_channel(subscription_name, channel_info)`.

### Step 4: Load and Render Channel

```python
# main.py:2665-2761
async def select_channel(subscription_name: str, channel_info: dict):
    # 1. Fetch the channel's data pod (NINJS format)
    data_pod = await fetch_channel_data_pod(subscription_name, channel_info)

    # 2. Decode protected images if user has decryption key
    if app.storage.user.get("stellar_secret"):
        data_pod = await decode_protected_images(data_pod)

    # 3. Get color scheme from user settings
    colors = get_gallery_colors()  # Based on dark_mode setting

    # 4. Render gallery.html Jinja2 template
    html = render_gallery_html(data_pod, colors)

    # 5. Store HTML for display when BROWSER tab is opened
    global pending_browser_html
    pending_browser_html = html

    # 6. Store current channel info
    app.storage.user["current_channel"] = {
        "subscription": subscription_name,
        "channel": channel_info["name"]
    }

    # 7. Notify user
    ui.notify(f"Channel loaded: {channel_info['name']}. Switch to BROWSER tab to view.")
```

### Step 5: Display in Browser Tab

When user switches to BROWSER tab, the HTML is injected into an iframe.

```python
# main.py:279 (global)
browser_content = None       # Container for iframe
update_browser_content = None  # Function to update iframe

# main.py:3801-3829 (on tab change)
def on_tab_change(tab_value):
    if tab_value == "BROWSER":
        toggle_app_mode()  # Switch to browser mode
        if pending_browser_html:
            update_browser_content(pending_browser_html)
```

**Iframe Update Mechanism:**

```python
# main.py:setup_browser_tab()
def update_browser_content(html: str):
    # Base64 encode HTML to avoid escaping issues
    html_b64 = base64.b64encode(html.encode()).decode()

    # JavaScript to update iframe srcdoc
    js = f'''
        const iframe = document.getElementById('browser-frame');
        const html = atob("{html_b64}");
        iframe.srcdoc = html;
    '''
    ui.run_javascript(js)
```

### Browser Tab UI Controls

Located in `main.py:3985-3998`, the FAB (Floating Action Button) provides three actions:

```python
with ui.fab("web_stories").classes("q-secondary-color"):
    ui.fab_action("subscriptions", on_click=view_subscriptions_dialog)
    ui.fab_action("add", on_click=lambda: add_subscription_dialog(add_subscription))
    ui.fab_action("play_arrow", on_click=lambda: select_channel_dialog(select_channel))
```

| Action | Icon | Function | Purpose |
|--------|------|----------|---------|
| View Subscriptions | subscriptions | `view_subscriptions_dialog()` | List/manage stored subscriptions |
| Add Subscription | add | `add_subscription_dialog()` | Add new Pintheon subscription |
| Select Channel | play_arrow | `select_channel_dialog()` | Choose channel to view |

### Channel Data Structure

Channels contain NINJS-format data pods:

```python
{
    "name": "Channel Name",
    "description": "12 items",
    "data": {
        # NINJS data pod (same structure as in deployment)
        "uri": "urn:newsml:...",
        "creator_public_key": "GABCD...",
        "recipient_public_key": "GEFGH...",
        "items": [
            {
                "type": "video_image",
                "headline": "Image Title",
                "renditions": [{"href": "ipfs://..."}],
                "hasAudio": false,
                "hasVideo": true,
                "videoMethod": "token",
                "videoTokenCid": "QmCID...",
                # ...
            }
        ]
    }
}
```

### Storage Keys for Browser Mode

```python
app.storage.user = {
    # Subscriptions (persisted to data.json)
    "subscriptions": [
        {"name": str, "url": str, "ipns_hash": str}
    ],

    # Fetched subscription metadata (runtime)
    "fetched_subscriptions": {
        "subscription_name": {
            "subscription": str,
            "ipns_hash": str,
            "gateway_url": str,
            "content_type": str,
            "size": int
        }
    },

    # Current viewing state
    "current_channel": {
        "subscription": str,
        "channel": str
    },

    # Mode
    "app_mode": "image" | "browser"
}
```

### Complete Flow Diagram

```
User clicks "Add Subscription" FAB
        │
        ▼
┌─────────────────────────────┐
│  add_subscription_dialog()  │  (dialogs.py:381-408)
│  • Enter name, URL, IPNS    │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  add_subscription()         │  (main.py:2259-2277)
│  • Store in subscriptions[] │
│  • Persist to data.json     │
└─────────────────────────────┘
        │
        ▼
User clicks "Select Channel" FAB
        │
        ▼
┌─────────────────────────────┐
│  select_channel_dialog()    │  (dialogs.py:452-524)
│  • User picks subscription  │
│  • Channels load from IPNS  │
│  • User clicks "Select"     │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  select_channel()           │  (main.py:2665-2761)
│  • Fetch data pod           │
│  • Decode protected images  │
│  • Render gallery.html      │
│  • Store in pending_browser │
└─────────────────────────────┘
        │
        ▼
User switches to BROWSER tab
        │
        ▼
┌─────────────────────────────┐
│  on_tab_change()            │  (main.py:3801-3829)
│  • toggle_app_mode()        │
│  • update_browser_content() │
└─────────────────────────────┘
        │
        ▼
┌─────────────────────────────┐
│  Gallery renders in iframe  │
│  • Images displayed         │
│  • Audio/video playable     │
│  • Metadata visible         │
└─────────────────────────────┘
```

---

## Data Pod Structure (NINJS Format)

```json
{
  "uri": "urn:ninjs:v2:com.example.gallery:aposematic",
  "version": "http://iptc.org/std/ninjs/2.1",
  "content_created": "2026-01-15T10:30:00Z",

  "creator_public_key": "GABCD...",
  "recipient_public_key": "GEFGH...",
  "op_string": "-^+",
  "scramble_mode": 2,

  "items": [
    {
      "type": "video_image",
      "guid": "urn:uuid:QmXYZ...",
      "title": "image_name.png",
      "imageType": "aposematic",
      "hasAudio": false,
      "hasVideo": true,
      "videoMethod": "token",
      "videoTokenCid": "QmVideoCID...",
      "hasMarkdown": true,
      "markdownMethod": "token",
      "markdownToken": "<serialized HVYMDataToken>",
      "renditions": [{
        "name": "original",
        "href": "http://localhost:8080/ipfs/QmXYZ...",
        "mimetype": "image/png"
      }],
      "videoTokenInfo": {
        "receiverPublicKey": "GEFGH...",
        "tokenExpiry": null,
        "noExpiry": true
      },
      "markdownTokenInfo": {
        "receiverPublicKey": "GEFGH...",
        "tokenExpiry": null,
        "noExpiry": true
      }
    }
  ],

  "audio_token_images": ["QmAudioImg..."],
  "video_token_images": ["QmVideoImg..."],
  "markdown_token_images": ["QmMarkdownImg..."],
  "type_distribution": {
    "raw": 0,
    "processed": 0,
    "aposematic": 3,
    "enciphered": 0,
    "total_with_audio": 1,
    "audio_token_count": 1,
    "total_with_video": 1,
    "video_token_count": 1,
    "total_with_markdown": 1,
    "markdown_token_count": 1
  }
}
```

---

## Storage Schema

### Persistent Storage (data.json)

```python
{
    "stellar_secret": str,          # Creator's Stellar secret key
    "debug_secret": str,            # Debug key for testing
    "artist": str,                  # Creator name
    "subscribers": [                # List of authorized recipients
        {"name": str, "public_key": str}
    ],
    "subscriptions": [              # Subscribed channels (Browser mode)
        {"name": str, "url": str, "ipns_hash": str}
    ],
    "app_mode": "image" | "browser",
    "scramble_mode": int,           # 1=BUTTERFLY, 2=BUTTERFLY, 3=QR
    "op_string": str,               # Aposematic operation string
    "app_colors": {...},            # Theme configuration
    "use_watermark": bool,
    "watermark": str,               # Path to watermark image
    "watermark_size": float,        # 0.0-1.0
    "watermark_position": str,      # bottom_right, top_left, etc.
    "iptc_data": {...},             # IPTC metadata defaults
}
```

### Runtime Storage (app.storage.user)

```python
{
    "hvym_public_key": str,         # Derived from stellar_secret
    "debug_public_key": str,        # Derived from debug_secret
    "recipient_public_key": str,    # Selected recipient
    "cipher_key": str,              # Current shared key (hex)
    "img_state": int,               # Current view (1-4)
    "raw_img_hashes": [str],        # Local hashes (raw/processed) or IPFS hashes
    "processed_img_hashes": [str],
    "aposematic_img_hashes": [str],
    "enciphered_img_hashes": [str],
    "{hash}": {                     # Per-image metadata
        "path": str,
        "name": str,
        "editor_url": str,          # /editor/{filename} URL for display
        "image_type": str,
        "has_audio": bool,
        "audio_method": str,        # "token"
        "audio_path": str,
        "audio_format": str,
        "audio_duration": float,
        "audio_size": int,
        "has_video": bool,
        "video_method": str,        # "token"
        "video_token_cid": str,     # IPFS CID for encrypted video token
        "video_path": str,
        "video_token_expires": float,
        "video_token_no_expiry": bool,
        "has_markdown": bool,
        "markdown_method": str,        # "token"
        "markdown_files": list,        # [{"filename": str, "size": int}]
        "markdown_token_expires": float,
        "markdown_token_no_expiry": bool,
        "original_hash": str        # For processed images
    }
}
```

---

## Key Technologies

| Component | Technology | Purpose |
|-----------|------------|---------|
| UI Framework | NiceGUI | Web-based desktop UI |
| Desktop Wrapper | pywebview | Native window container |
| Image Processing | Wand/ImageMagick | Encryption, watermarking |
| Aposematic | aiposematic v1.1 | Visual scrambling (native Stellar key derivation) |
| Audio Tokens | hvym-stellar (HVYMDataToken) | Encrypted audio tokens |
| Video Tokens | hvym-stellar (HVYMDataToken) + IPFS | Encrypted video tokens (CID in PNG) |
| Markdown Tokens | hvym-stellar (HVYMDataToken) | Encrypted markdown tokens (in PNG) |
| Metadata | exiftool, exiv2 | IPTC/EXIF/XMP handling |
| Cryptography | hvym-stellar | Stellar-based ECDH keys |
| Storage | IPFS | Decentralized file storage |
| Deployment | Pintheon | Gallery hosting platform |
| Templates | Jinja2 | HTML gallery rendering |

---

## File Structure

```
andromica/
├── main.py              # Application entry, UI, core logic
├── dialogs.py           # Dialog components (audio/video/markdown embed, cipher, aposematic)
├── img_edit.py          # Image processing (watermark, encrypt)
├── metadata.py          # IPTC data management
├── data_pod_audio.py    # Data pod creation and processing (audio + video + markdown)
├── audio_tokens.py      # HVYMDataToken audio encryption
├── video_tokens.py      # HVYMDataToken video encryption + IPFS CID
├── markdown_tokens.py   # HVYMDataToken markdown encryption (bundled JSON)
├── png_chunks.py        # PNG tEXt chunk manipulation (audio + video + markdown tokens)
├── client_rendering.py  # Gallery HTML rendering
├── task_runner.py       # Async task runner with progress UI
├── data.json            # Persistent user data
├── static/
│   ├── icon.png         # App icon
│   ├── OCR-A.ttf        # Font for aposematic
│   ├── PhinoVariation.ttf # Additional font
│   └── logo.json        # Logo configuration
├── templates/
│   └── gallery.html     # Jinja2 gallery template (audio + video player + markdown)
├── docs/
│   ├── ARCHITECTURE.md  # This file
│   ├── ENCRYPTION.md    # Cryptography details
│   ├── DATA_STRUCTURES.md
│   ├── INSTALL.md
│   └── BUILD.md
└── scripts/
    └── ...              # Build scripts
```

---

## Integration Points

### IPFS

Andromica uses two IPFS endpoints for different purposes:

#### IPFS HTTP API (Port 5001)

**Configuration:** `ipfs_endpoint = "http://127.0.0.1"` + `port = "5001"`

Used for programmatic backend operations:

| Function | Endpoint | Purpose |
|----------|----------|---------|
| `ipfs_add()` | `/api/v0/add` | Add files to IPFS |
| `is_ipfs_running()` | `/api/v0/version` | Health check |
| `download_ipfs_image()` | `/api/v0/cat?arg={hash}` | Fetch file content (primary) |
| `ipns_*` operations | `/api/v0/name/*` | IPNS publish/resolve |

#### IPFS HTTP Gateway (Port 8080)

**Configuration:** `ipfs_webui = "http://localhost"` + `ipfs_webui_port = "8080"`

> **Note:** The variable is named `ipfs_webui` but it's actually the IPFS Gateway, not the WebUI. The actual IPFS WebUI is at `http://localhost:5001/webui`.

Used for HTTP access in browser contexts:

| Usage | Example | Purpose |
|-------|---------|---------|
| Template URLs | `<img src="http://localhost:8080/ipfs/Qm...">` | Display images in HTML |
| Data pod hrefs | `gateway_base/ipfs/{hash}` | Build URLs for renditions |
| Fallback fetch | `download_ipfs_image()` fallback | When API fails |

#### Why Both Are Needed

```
┌─────────────────────────────────────────────────────────────────┐
│                      IPFS DAEMON                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────────┐      ┌─────────────────────┐          │
│   │   HTTP API (:5001)  │      │  HTTP Gateway (:8080)│          │
│   ├─────────────────────┤      ├─────────────────────┤          │
│   │ • Add files         │      │ • Serve content     │          │
│   │ • Cat/get content   │      │ • Browser-friendly  │          │
│   │ • Pin management    │      │ • GET requests only │          │
│   │ • IPNS operations   │      │ • Public access     │          │
│   │ • POST requests     │      │                     │          │
│   └─────────────────────┘      └─────────────────────┘          │
│            │                            │                        │
│            ▼                            ▼                        │
│     Backend Python              Browser/Templates                │
│     (main.py, etc.)             (gallery.html, iframe)          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Key Functions:**
- `ipfs_add()` - Add file to IPFS, returns hash
- `ipfs_load_to_temp_file()` - Download IPFS content to temp file
- `download_ipfs_image()` - Download image (tries API first, gateway fallback)
- `ipns_publish()`, `ipns_resolve()` - IPNS name operations

### Pintheon
- REST API for gallery deployment
- Handles IPNS pinning and directory management
- Access token authentication
- Functions: `pintheon_upload_file()`, `pintheon_create_directory()`

### Stellar/hvym-stellar
- `Stellar25519KeyPair` - Ed25519 key derivation from Stellar keys
- `StellarSharedKey` - ECDH shared secret generation
- `HVYMDataToken` - Biscuit-based encrypted data tokens
- Keys stored as Stellar-format secrets

### Application UI (Port 8090)

NiceGUI runs a local web server that pywebview displays in a native window.

**Default port:** 8090 (chosen to avoid conflict with IPFS Gateway on 8080)

**CLI override:** `python main.py --port 9000`

**Available CLI flags:**

| Flag | Default | Description |
|------|---------|-------------|
| `--port` | 8090 | Application UI port |
| `--debug` | off | Open DevTools in native window |
| `--console` | off | Show console output |

---

## Error Handling

The application uses a combination of:
- Try/catch with console logging for debugging
- `ui.notify()` for user-facing messages
- Graceful degradation when IPFS is unavailable
- Pre-extraction patterns to handle data loss during transformations

---

## Critical Implementation Notes

### Media Preservation
PNG tEXt chunks (where audio tokens and video CIDs are stored) are NOT preserved when:
- `new_aposematic_img()` creates scrambled image
- `recover_aposematic_img()` recovers original
- `new_enciphered_img()` encrypts image
- `new_deciphered_img()` decrypts image

**Solutions by Image Type:**

| Image Type | Media Strategy |
|------------|----------------|
| Aposematic | `reembed_media_if_needed()` after scramble; pre-extract before recovery |
| Enciphered | Extract from original processed image via `original_hash` |

**Why Enciphered Cannot Re-embed:** ImageMagick encryption modifies the entire image data structure. Adding tEXt chunks after encryption corrupts the payload and breaks decryption.

### Video Token Cleanup
When removing an image (`remove_img()`), the video token CID is unpinned from IPFS before the image itself is removed. Similarly, `remove_video_from_image()` unpins the CID and strips the tEXt chunks.

### PNG-Only Media Embedding
Audio and video tokens are stored in PNG tEXt chunks, so media embedding requires PNG images. Non-PNG images are rejected with a notification. Other image formats (JPEG, etc.) can still be imported and processed but cannot carry embedded media.

### No Dual Audio/Video Embedding
An image supports audio OR video, not both. Markdown is independent and can coexist with either. The editor FAB uses `if/elif/else` logic for audio/video:
- If audio embedded: show Play Audio + Remove Audio
- Elif video embedded: show Play Video + Remove Video
- Else: show Add Audio + Add Video

Markdown has its own separate FAB action (Embed Markdown / Remove Markdown) that is always available regardless of audio/video state.

### NiceGUI Storage Persistence
In-place list modifications don't trigger persistence:
```python
# BAD - doesn't persist
app.storage.user["list"].append(value)

# GOOD - triggers persistence
lst = app.storage.user.get("list", [])
lst.append(value)
app.storage.user["list"] = lst
```

### Shared Key Consistency
ECDH key derivation must use consistent parameters:
- Same `op_string` for aposematic
- Same `scramble_mode` for aposematic
- For aposematic (v1.1): `stellar_keypair` + `subscriber_public_key`/`artist_public_key` — key derivation is handled internally by aiposematic with domain-separated hashing
- For enciphered: Creator and subscriber derive same `cipher_key` via `StellarSharedKey` independently
