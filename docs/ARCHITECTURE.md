# Andromica Technical Architecture

## Overview

Andromica is a decentralized content creation and distribution system built on IPFS and Stellar cryptography. It enables creators to publish protected galleries that can only be viewed by authorized subscribers. The application supports audio embedding in images using two methods: metadata (base64) and encrypted tokens.

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
│  │ • Embed audio       │    │ • Decrypt content   │            │
│  │ • Create aposematic │    │ • Extract audio     │            │
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
- `init()` - Application initialization, storage setup, key generation
- `render_gallery()` - Display images based on current view state
- `process_watermarking()` - Apply watermarks to raw images
- `process_aposematic()` - Generate scrambled images with visual noise
- `process_enciphering()` - Generate encrypted images via ImageMagick
- `process_deciphering()` - Decrypt enciphered images
- `process_audio_embedding()` - Embed audio via metadata or token method
- `reembed_audio_if_needed()` - Re-embed audio after image processing
- `create_ninjs_data_pod_with_encrypted_tokens()` - Create NINJS-format data pods
- `process_debug_deploy_gallery()` - Debug deployment with local decryption
- `process_pintheon_deploy_gallery()` - Production deployment to Pintheon node
- `select_channel()` - Browser mode channel rendering
- `decode_protected_images()` - Decrypt/descramble for viewing

**Global State:**
- `app.storage.user` - Persistent user data (NiceGUI storage)
- `img_states = {1: 'raw', 2: 'processed', 3: 'aposematic', 4: 'enciphered'}`

### data_pod_audio.py
Data pod creation and processing with audio token support.

**Key Functions:**
- `determine_image_type()` - Identify image state from metadata/storage
- `create_ninjs_data_pod_with_encrypted_tokens()` - Create encrypted data pods
- `process_data_pod_locally()` - Decrypt data pod for subscriber viewing

### audio_tokens.py
Encrypted audio token handling using HVYMDataToken.

**Key Functions:**
- `create_audio_token()` - Create encrypted audio token
- `create_token_audio_image()` - Embed encrypted token in image
- `extract_audio_from_token()` - Decrypt audio from token
- `extract_token_audio()` - Full extraction pipeline from image

### png_chunks.py
PNG tEXt chunk manipulation for audio embedding.

**Key Functions:**
- `embed_audio_base64()` - Embed base64-encoded audio in PNG
- `embed_audio_token()` - Embed encrypted token in PNG
- `extract_audio_base64()` - Extract base64 audio from PNG
- `extract_audio_token()` - Extract token from PNG
- `has_audio_data()` - Check if PNG contains audio

### img_edit.py
Image processing and manipulation.

**Key Functions:**
- `new_watermarked_img()` - Apply watermark overlay
- `new_enciphered_img()` - Encrypt image using ImageMagick
- `new_deciphered_img()` - Decrypt image
- `new_iptc_img()` - Write IPTC metadata

### dialogs.py
UI dialog components for user interactions.

**Key Functions:**
- `create_shared_key()` - Generate shared encryption key via ECDH
- `get_recipient_options()` - Build subscriber dropdown options
- `cipher_dialog()` - Encryption recipient selection
- `aposematic_dialog()` - Aposematic settings and recipient selection

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
               embed audio
```

### Image States

| State | Index | Description | Storage Key |
|-------|-------|-------------|-------------|
| Raw | 1 | Original imported images | `raw_img_hashes` |
| Processed | 2 | Watermarked, metadata added, audio embedded | `processed_img_hashes` |
| Aposematic | 3 | Visually scrambled (reversible with key) | `aposematic_img_hashes` |
| Enciphered | 4 | Fully encrypted (ImageMagick cipher) | `enciphered_img_hashes` |

### Processing Functions

#### 1. Watermarking (`process_watermarking()`)
```python
# main.py:1640-1694
async def process_watermarking():
    for hash_value in raw_img_hashes:
        # Apply watermark overlay
        watermarked_path = await new_watermarked_img(
            file_name, img_path, watermark_path,
            amount=watermark_size,
            position=watermark_position,
            padding=watermark_padding
        )
        # Re-embed audio if original had it
        if audio_path:
            watermarked_path = reembed_audio_if_needed(watermarked_path, audio_path)
        # Add to IPFS and update storage
        ipfs_hash = ipfs_add(watermarked_path)
        processed_img_hashes.append(ipfs_hash)
```

#### 2. Aposematic Processing (`process_aposematic()`)
```python
# main.py:1707-1787
async def process_aposematic():
    for hash_value in processed_img_hashes:
        # Apply visual scrambling
        aposematic = new_aposematic_img(
            img_path,
            cipher_key=cipher_key,        # Shared key for recipient
            op_string="-^+",              # Operation sequence
            scramble_mode=SCRAMBLE_MODE   # BUTTERFLY or QR
        )
        aposematic_img_path = aposematic["img_path"]

        # CRITICAL: Re-embed audio (scrambling creates new PNG without tEXt chunks)
        if audio_path:
            aposematic_img_path = reembed_audio_if_needed(aposematic_img_path, audio_path)

        # Add to IPFS
        ipfs_hash = ipfs_add(aposematic_img_path)
        aposematic_img_hashes.append(ipfs_hash)
```

**Aposematic Characteristics:**
- Uses `aiposematic` library for visual noise patterns
- Scramble modes: BUTTERFLY (default), QR
- Operation string (`op_string`) controls scramble sequence
- Reversible with same cipher_key and op_string
- Creates NEW PNG file (does not preserve tEXt chunks - audio must be re-embedded)

#### 3. Enciphering (`process_enciphering()`)
```python
# main.py:1790-1868
async def process_enciphering():
    for hash_value in processed_img_hashes:
        # Encrypt via ImageMagick
        enciphered_path = await new_enciphered_img(
            file_name,
            img_path,
            cipher_key
        )
        # NOTE: Audio is NOT re-embedded for enciphered images
        # (encryption would corrupt embedded data)

        ipfs_hash = ipfs_add(enciphered_path)
        enciphered_img_hashes.append(ipfs_hash)
```

**Enciphering Characteristics:**
- Uses ImageMagick's `encipher()` function
- Full image encryption (pixels become unrecognizable)
- Audio cannot be preserved in enciphered images (data corruption)
- Requires exact cipher_key for decryption

#### 4. Deciphering (`process_deciphering()`)
```python
# main.py:1871-1886
async def process_deciphering():
    for hash_value in enciphered_img_hashes:
        deciphered_path = new_deciphered_img(
            file_name,
            encrypted_img_path,
            cipher_key
        )
        ipfs_hash = ipfs_add(deciphered_path)
        deciphered_img_hashes.append(ipfs_hash)
```

### Aposematic vs Enciphered Comparison

| Feature | Aposematic | Enciphered |
|---------|------------|------------|
| Visual appearance | Scrambled pattern visible | Completely encrypted |
| Audio support | Yes (re-embedded after scramble) | Yes (via `original_hash` reference) |
| Audio location | In the aposematic image itself | Extracted from original processed image |
| Reversibility | Same key + op_string | Same cipher_key only |
| Library | aiposematic | ImageMagick (Wand) |
| Use case | Visual protection with audio | Maximum security with audio |

**Note on Enciphered Audio:** ImageMagick's `encipher()` creates a new PNG that doesn't preserve tEXt chunks. Audio cannot be re-embedded into enciphered images because it would corrupt the encryption. Instead, audio is extracted from the original processed image using the `original_hash` reference stored in the data pod.

---

## Audio Embedding Flow

### Two Audio Methods

#### 1. Metadata Method (Base64)
- Audio encoded as base64 string
- Stored in PNG tEXt chunks
- Keywords: `audio_base64_001`, `audio_base64_002`, etc.
- No encryption - anyone can extract
- Use case: Public audio, no subscriber restriction

#### 2. Token Method (Encrypted)
- Audio encrypted using HVYMDataToken (Biscuit-based)
- Stored in PNG tEXt chunks
- Keywords: `audio_token_001`, `audio_token_002`, etc.
- Only recipient with correct key can decrypt
- Use case: Protected audio for subscribers only

### Audio Embedding Functions

```python
# Metadata method (main.py:4587-4632)
def create_audio_image(audio_file, image_file):
    audio_data = read_audio_bytes(audio_file)
    audio_base64 = base64.b64encode(audio_data).decode()
    return embed_audio_base64(image_file, audio_base64, output_path)

# Token method (audio_tokens.py:149-183)
def create_token_audio_image(audio_file, image_file, sender_kp, receiver_pub, expires_in):
    audio_data = read_audio_bytes(audio_file)
    token = create_audio_token(sender_kp, receiver_pub, audio_data, filename, expires_in)
    return embed_audio_token(image_file, token, output_path)
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
│  │  tEXt chunk: audio_base64_001 = <base64 data>   │   │
│  │  tEXt chunk: audio_base64_002 = <base64 data>   │   │
│  │  ... (8KB max per chunk)                        │   │
│  └─────────────────────────────────────────────────┘   │
│  IEND chunk                                             │
└─────────────────────────────────────────────────────────┘
```

### Critical: Audio Preservation Through Pipeline

**Problem:** Image transformation functions create NEW PNG files that don't preserve tEXt chunks:
- `new_aposematic_img()` / `recover_aposematic_img()` - PIL creates new image
- `new_enciphered_img()` / `new_deciphered_img()` - ImageMagick creates new image

**Solution for Aposematic:** Extract audio BEFORE transformation, re-embed AFTER.

```python
# Re-embedding helper (main.py:4500-4505)
def reembed_audio_if_needed(image_path, audio_path):
    if audio_path and os.path.exists(audio_path):
        return create_audio_image(audio_path, image_path)
    return image_path

# During data pod processing - pre-extract from aposematic image
pre_extracted_audio = None
if item.get("hasAudio") and image_type == "aposematic":
    # Extract from temp_path (aposematic image still has tEXt chunks)
    has_audio, actual_method = has_audio_data(temp_path)
    if actual_method == "token":
        serialized_token = extract_audio_token(temp_path)
        pre_extracted_audio = {"type": "token", "data": serialized_token}

# THEN recover the image (creates new PNG without tEXt chunks)
decoded_path = recover_aposematic_img(temp_path, cipher_key, op_string)
```

**Solution for Enciphered:** Extract audio from ORIGINAL processed image (via `original_hash`).

```python
# During data pod processing (data_pod_audio.py:415-447)
if item.get("hasAudio") and image_type == "enciphered":
    # Enciphered images lose audio during encryption - extract from original
    original_hash = item.get("original_hash")
    if original_hash:
        # Download original processed image from IPFS
        original_href = f"{gateway_base}/ipfs/{original_hash}"
        original_path = download_ipfs_image(original_href)

        # Extract audio from original (has tEXt chunks intact)
        has_audio, actual_method = has_audio_data(original_path)
        if actual_method == "token":
            serialized_token = extract_audio_token(original_path)
            pre_extracted_audio = {"type": "token", "data": serialized_token}

# THEN decipher the enciphered image (for display)
decoded_path = new_deciphered_img(temp_path, cipher_key)
```

**Why Enciphered is Different:**
- ImageMagick `encipher()` encrypts the entire image data structure
- Re-embedding audio after encryption would corrupt the encrypted payload
- Decryption would fail or produce garbage
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

```python
from hvym_stellar import StellarSharedKey, Stellar25519KeyPair
from stellar_sdk import Keypair

# Creator side
creator_kp = Keypair.from_secret(creator_stellar_secret)
creator_keys = Stellar25519KeyPair(creator_kp)

# Generate shared key with recipient's public key
shared_key = StellarSharedKey(creator_keys, recipient_public_key)
cipher_key = shared_key.shared_secret().hex()

# Subscriber side (same result!)
subscriber_kp = Keypair.from_secret(subscriber_stellar_secret)
subscriber_keys = Stellar25519KeyPair(subscriber_kp)
shared_key_sub = StellarSharedKey(subscriber_keys, creator_public_key)
cipher_key_sub = shared_key_sub.shared_secret().hex()  # Same key!
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
2. If aposematic: Recreate with correct shared key (debug→app)
3. Re-embed audio into aposematic images
4. Create data pod with `debug_public_key` as creator
5. Process data pod locally using `stellar_secret`
6. Render HTML with decrypted images
7. Display in browser tab

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
1. Check Pintheon running and access token
2. Validate image state
3. Create data pod with real creator key
4. Create directory on Pintheon
5. Upload all images to Pintheon
6. Upload data pod JSON
7. Store hash for subscriber access

**Key Difference:** Debug flow decrypts locally for preview; Pintheon flow is deployment-only (subscribers decrypt on their end).

---

## Consumer/Browser Flow

### Data Pod Processing (`process_data_pod_locally()`)

```
┌─────────────┐    ┌───────────┐    ┌─────────────┐    ┌──────────┐
│  DOWNLOAD   │───▶│ PRE-EXTRACT│───▶│   DECRYPT   │───▶│  RENDER  │
│  data pod   │    │   AUDIO   │    │   images    │    │  gallery │
│  + images   │    │  (before  │    │  + process  │    │  with    │
│  from IPFS  │    │  recovery)│    │   audio     │    │  audio   │
└─────────────┘    └───────────┘    └─────────────┘    └──────────┘
      │                  │                 │                 │
      ▼                  ▼                 ▼                 ▼
   Load JSON,       Extract from      Generate shared    HTML with
   fetch images     encrypted PNG     key, recover       base64 images
   via IPFS API     (tEXt chunks)     aposematic         + audio player
```

**Processing Steps:**

1. **Load Data Pod**
   - Parse JSON from file
   - Extract creator_public_key, recipient_public_key

2. **Generate Shared Key**
   ```python
   subscriber_keys = Stellar25519KeyPair(Keypair.from_secret(subscriber_secret))
   shared_key = StellarSharedKey(subscriber_keys, creator_public_key)
   cipher_key = shared_key.shared_secret().hex()
   ```

3. **For Each Item:**
   - Download image from IPFS
   - **Pre-extract audio** (BEFORE recovery - critical!)
   - Decrypt/recover image based on type
   - Process pre-extracted audio (decrypt token if needed)
   - Update item with decrypted image href and audio data

4. **Render Gallery**
   - Use Jinja2 template with processed data pod
   - Images as IPFS URLs or base64 data URIs
   - Audio as base64 in `<audio>` element

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
│   • Store locally      • Load data pod     • Play audio                │
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
                "type": "audio_image",
                "headline": "Image Title",
                "renditions": [{"href": "ipfs://..."}],
                "hasAudio": true,
                "audioMethod": "token",
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
│  • Audio playable           │
│  • Metadata visible         │
└─────────────────────────────┘
```

---

## Data Pod Structure (NINJS Format)

```json
{
  "uri": "urn:ninjs:v2:com.example.gallery:aposematic",
  "version": "http://iptc.org/std/ninjs/2.1",
  "content_created": "2024-01-15T10:30:00Z",

  "creator_public_key": "GABCD...",
  "recipient_public_key": "GEFGH...",
  "op_string": "-^+",
  "scramble_mode": 2,

  "items": [
    {
      "type": "audio_image",
      "guid": "urn:uuid:QmXYZ...",
      "title": "image_name.png",
      "imageType": "aposematic",
      "hasAudio": true,
      "audioMethod": "token",
      "renditions": [{
        "name": "original",
        "href": "http://localhost:8080/ipfs/QmXYZ...",
        "mimetype": "image/png"
      }],
      "audioTokenInfo": {
        "receiverPublicKey": "GEFGH...",
        "tokenExpiry": 1705312200
      }
    }
  ],

  "audio_token_images": ["QmXYZ..."],
  "type_distribution": {
    "raw": 0,
    "processed": 0,
    "aposematic": 3,
    "enciphered": 0,
    "total_with_audio": 2,
    "audio_token_count": 2
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
    "raw_img_hashes": [str],        # IPFS hashes
    "processed_img_hashes": [str],
    "aposematic_img_hashes": [str],
    "enciphered_img_hashes": [str],
    "{hash}": {                     # Per-image metadata
        "path": str,
        "name": str,
        "image_type": str,
        "has_audio": bool,
        "audio_method": str,        # "metadata" or "token"
        "audio_path": str,
        "audio_format": str,
        "audio_duration": float,
        "audio_size": int,
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
| Aposematic | aiposematic | Visual scrambling |
| Audio Tokens | hvym-stellar (HVYMDataToken) | Encrypted audio tokens |
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
├── dialogs.py           # Dialog components
├── img_edit.py          # Image processing (watermark, encrypt)
├── metadata.py          # IPTC data management
├── data_pod_audio.py    # Data pod creation and processing
├── audio_tokens.py      # HVYMDataToken audio encryption
├── png_chunks.py        # PNG tEXt chunk manipulation
├── client_rendering.py  # Gallery HTML rendering
├── data.json            # Persistent user data
├── static/
│   ├── icon.png         # App icon
│   ├── OCR-A.ttf        # Font for aposematic
│   └── logo.json        # Logo configuration
├── templates/
│   └── gallery.html     # Jinja2 gallery template
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

---

## Error Handling

The application uses a combination of:
- Try/catch with console logging for debugging
- `ui.notify()` for user-facing messages
- Graceful degradation when IPFS is unavailable
- Pre-extraction patterns to handle data loss during transformations

---

## Critical Implementation Notes

### Audio Preservation
PNG tEXt chunks (where audio is stored) are NOT preserved when:
- `new_aposematic_img()` creates scrambled image
- `recover_aposematic_img()` recovers original
- `new_enciphered_img()` encrypts image
- `new_deciphered_img()` decrypts image

**Solutions by Image Type:**

| Image Type | Audio Strategy |
|------------|----------------|
| Aposematic | Re-embed after scramble; pre-extract before recovery |
| Enciphered | Extract from original processed image via `original_hash` |

**Why Enciphered Cannot Re-embed:** ImageMagick encryption modifies the entire image data structure. Adding tEXt chunks after encryption corrupts the payload and breaks decryption.

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
- Creator and subscriber derive same `cipher_key` independently
