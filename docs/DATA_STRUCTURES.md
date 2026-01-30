# Andromica Data Structures

## NINJS Data Pod

Andromica uses a NewsML-G2 inspired JSON format (NINJS) for gallery metadata.

### Package Structure

```json
{
    "version": "1.0",
    "uri": "urn:newsml:package:20260110123456",
    "type": "package",
    "content_type": "original",
    "versioncreated": "2026-01-10T12:34:56Z",
    "language": "en",
    "items": [...]
}
```

### Protected Content Fields

For `aposematic` or `enciphered` content:

```json
{
    "uri": "urn:ninjs:v2:com.example.gallery:aposematic",
    "version": "http://iptc.org/std/ninjs/2.1",
    "content_created": "2026-01-10T12:34:56Z",
    "content_type": "aposematic",
    "creator_public_key": "GABCDEF...",
    "recipient_public_key": "GXYZ123...",
    "op_string": "-^+",
    "scramble_mode": 2,
    "items": [...],
    "audio_token_images": ["QmHash1...", "QmHash2..."],
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

| Field | Purpose |
|-------|---------|
| `creator_public_key` | Used by subscriber for ECDH shared key derivation |
| `recipient_public_key` | Identifies authorized subscriber (verification) |
| `op_string` | Aposematic operation sequence (e.g., "-^+") |
| `scramble_mode` | Aposematic mode (1=BUTTERFLY, 2=BUTTERFLY, 3=QR) |
| `audio_token_images` | List of image hashes containing encrypted audio tokens |
| `type_distribution` | Counts of each image type in the data pod |

### Item Structure

Each image in the gallery:

```json
{
    "type": "audio_image",
    "guid": "urn:uuid:QmHash...",
    "version": "1",
    "language": "en",
    "pubstatus": "usable",
    "title": "image_name.png",
    "byline": "Creator Name",
    "creditline": "Photographer Name",
    "copyright": "All Rights Reserved",
    "ednote": "Type: aposematic, Audio method: token",
    "renditions": [
        {
            "name": "original",
            "href": "http://127.0.0.1:8080/ipfs/QmHash...",
            "mimetype": "image/png",
            "width": 1920,
            "height": 1080
        }
    ],
    "imageType": "aposematic",
    "hasAudio": true,
    "audioMethod": "token",
    "original_hash": "QmOriginalProcessedHash...",
    "audioTokenInfo": {
        "receiverPublicKey": "GXYZ123...",
        "tokenExpiry": 1705312200
    }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"audio_image"` if has audio, otherwise image type |
| `guid` | string | Unique identifier using IPFS hash |
| `imageType` | string | `"raw"`, `"processed"`, `"aposematic"`, or `"enciphered"` |
| `hasAudio` | boolean | Whether image contains embedded audio |
| `audioMethod` | string | `"token"` (encrypted) or `"metadata"` (base64) |
| `original_hash` | string | For enciphered images: hash of original processed image (for audio extraction) |
| `audioTokenInfo` | object | Only for token method: receiver key and expiry |
| `renditions` | array | List of image renditions (note: array, not object) |

### Audio in Processed Items

After `process_data_pod_locally()`, items may include decoded audio:

```json
{
    "audio": {
        "data": "base64_encoded_audio_data...",
        "format": "wav"
    }
}
```

## Subscriber Structure

```json
{
    "name": "Subscriber Display Name",
    "public_key": "GABCDEFGHIJKLMNOPQRSTUVWXYZ234567ABCDEFGHIJKLMNOPQRSTUV"
}
```

Stored in `app.storage.user['subscribers']` as a list.

## Subscription Structure

Stored in `app.storage.user['subscriptions']` as a list:

```json
{
    "name": "My Gallery Subscription",
    "url": "https://pintheon-node.example.com",
    "ipns_hash": "k51qzi5uqu5d..."
}
```

### Fetched Subscription Metadata

Stored in `app.storage.user['fetched_subscriptions']` as a dict:

```json
{
    "My Gallery Subscription": {
        "subscription": "My Gallery Subscription",
        "ipns_hash": "k51qzi5uqu5d...",
        "gateway_url": "https://pintheon-node.example.com/ipns/k51qzi5uqu5d...",
        "content_type": "application/json",
        "size": 4096
    }
}
```

### Current Channel

Stored in `app.storage.user['current_channel']`:

```json
{
    "subscription": "My Gallery Subscription",
    "channel": "Channel Name"
}
```

## Image Hash Metadata

For each image hash in storage (`app.storage.user[hash_value]`):

```json
{
    "path": "/path/to/local/file.png",
    "name": "original_filename.png",
    "ipns_path": null,
    "extension": ".png",
    "render_metadata": true,
    "image_type": "aposematic",
    "has_audio": true,
    "audio_method": "token",
    "audio_path": "/path/to/audio.wav",
    "audio_format": "wav",
    "audio_duration": 5.2,
    "audio_size": 230400,
    "audio_token_expires": 1705312200,
    "original_hash": "QmOriginalProcessedHash..."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `path` | string | Local filesystem path to image |
| `name` | string | Original filename |
| `image_type` | string | Current state: `raw`, `processed`, `aposematic`, `enciphered` |
| `has_audio` | boolean | Whether audio is embedded |
| `audio_method` | string | `"token"` or `"metadata"` |
| `audio_path` | string | Path to original audio file |
| `audio_format` | string | Audio format (e.g., `"wav"`, `"mp3"`) |
| `audio_duration` | float | Audio duration in seconds |
| `audio_size` | integer | Audio file size in bytes |
| `original_hash` | string | For enciphered: hash of processed image (contains audio) |

## Audio Embedding

### Two Audio Methods

| Method | Storage | Encryption | Use Case |
|--------|---------|------------|----------|
| `metadata` | PNG tEXt chunks as base64 | None | Public audio |
| `token` | PNG tEXt chunks as HVYMDataToken | ECDH + Biscuit | Subscriber-only audio |

### PNG tEXt Chunk Keywords

| Method | Chunk Keywords | Description |
|--------|----------------|-------------|
| Metadata | `audio_base64_001`, `audio_base64_002`, ... | Chunked base64 audio (8KB per chunk) |
| Token | `audio_token_001`, `audio_token_002`, ... | Chunked encrypted token |

### Audio Token Structure (HVYMDataToken)

Encrypted audio tokens use the hvym-stellar library's Biscuit-based format:

```
┌─────────────────────────────────────────────────────┐
│                  HVYMDataToken                       │
├─────────────────────────────────────────────────────┤
│  Biscuit Token:                                      │
│  ├─ Authority Block:                                │
│  │   ├─ sender_public_key                           │
│  │   ├─ receiver_public_key                         │
│  │   ├─ encrypted_data (ChaCha20-Poly1305)         │
│  │   ├─ nonce                                       │
│  │   └─ expiry_timestamp                            │
│  └─ Signature (Ed25519)                             │
└─────────────────────────────────────────────────────┘
```

**Decryption requires:**
1. Receiver's Stellar secret key
2. Sender's public key (from data pod)
3. ECDH shared secret derivation

## App Colors Configuration

```json
{
    "primary": "#25F5F8",
    "secondary": "#1A1A2E",
    "text-color": "#333333",
    "bg-color": "#FFFFFF",
    "card-bg": "#F5F5F5",
    "border-color": "#E0E0E0",
    "dark-primary": "#578485",
    "dark-secondary": "#2D2D44",
    "dark-text": "#E0E0E0",
    "dark-bg": "#1A1A2E",
    "dark-card": "#2D2D44",
    "dark-border": "#3D3D5C"
}
```

## IPTC Data Structure

```json
{
    "use_objectname": false,
    "use_caption_abstract": false,
    "use_keywords": false,
    "use_credit_line": false,
    "use_copyright_notice": true,
    "use_byline": false,
    "use_city": false,
    "use_country": false,
    "use_destination": false,
    "use_data_mining": true,
    "use_other_constraints": false,
    "Object Name": "",
    "Caption/Abstract": "",
    "Keywords": "",
    "Credit Line": "",
    "Copyright Notice": "All Rights Reserved",
    "By-line": "",
    "City": "",
    "Country": "",
    "Destination": "",
    "Data Mining": "DMI-PROHIBITED",
    "Other Constraints": ""
}
```

## Gallery Template Context

Data passed to `gallery.html` Jinja2 template:

```python
{
    'data_pod': {...},           # Full NINJS data pod
    'ipfs_gateway': str,         # e.g., "http://127.0.0.1:8080"
    'ipfs_webui': str,           # Gateway host
    'ipfs_webui_port': str,      # Gateway port
    'gallery_title': str,        # Optional title
    'gallery_description': str,  # Optional description
    'colors': {                  # Theme colors
        'primary': str,
        'secondary': str,
        'text': str,
        'bg': str,
        'card': str,
        'border': str
    },
    'is_dark_mode': bool
}
```

## Pintheon API Structures

### Upload Response

```json
{
    "Hash": "QmHash...",
    "Name": "filename.json",
    "Size": "1234"
}
```

### Directory Structure

```json
{
    "Hash": "QmDirHash...",
    "Links": [
        {"Name": "file1.json", "Hash": "QmHash1..."},
        {"Name": "file2.jpg", "Hash": "QmHash2..."}
    ]
}
```

## State Machine

### Image States

```python
img_states = {
    1: 'raw',        # Imported, unprocessed
    2: 'processed',  # Watermarked, metadata added
    3: 'aposematic', # Scrambled
    4: 'enciphered'  # Encrypted
}
```

### Image Hash Lists

| State | Storage Key | Description |
|-------|-------------|-------------|
| Raw | `raw_img_hashes` | Original imports |
| Processed | `processed_img_hashes` | After watermark/metadata |
| Aposematic | `aposematic_img_hashes` | After scrambling |
| Enciphered | `enciphered_img_hashes` | After encryption |

### State Transitions

```
         ┌──────────────────────────────────────┐
         │                                      │
         ▼                                      │
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    RAW      │───▶│  PROCESSED  │───▶│ APOSEMATIC  │
│  (state 1)  │    │  (state 2)  │    │  (state 3)  │
└─────────────┘    └─────────────┘    └─────────────┘
                          │
                          │           ┌─────────────┐
                          └──────────▶│ ENCIPHERED  │
                                      │  (state 4)  │
                                      └─────────────┘
```

## Persistent Storage (data.json)

Complete schema:

```json
{
    "stellar_secret": "S...",
    "debug_secret": "S...",
    "artist": "Creator Name",
    "use_watermark": false,
    "watermark": null,
    "watermark_size": 0.2,
    "watermark_position": 1,
    "watermark_padding": 0.05,
    "scramble_mode": 2,
    "op_string": "-^+",
    "use_iptc": false,
    "iptc_data": {...},
    "tmp_files": [],
    "content_folders": [],
    "subscribers": [],
    "subscriptions": [],
    "fetched_subscriptions": {},
    "current_channel": null,
    "app_mode": "image",
    "app_colors": {...},
    "dark_mode": null,
    "ipfs_webui": "http://localhost",
    "ipfs_webui_port": "8080",
    "pintheon_endpoint": null,
    "pintheon_access_token": null,
    "latest_data_pod_hash": null,
    "latest_gallery_html_hash": null,
    "latest_data_pod_timestamp": null,
    "gallery_title": "",
    "gallery_description": ""
}
```

## Runtime Storage (app.storage.user)

Additional runtime-only fields (not persisted to data.json):

```json
{
    "hvym_public_key": "GABCDEF...",
    "debug_public_key": "GXYZ123...",
    "recipient_public_key": "G...",
    "cipher_key": "hex_shared_key...",
    "img_state": 2,
    "raw_img_hashes": ["QmHash1...", "QmHash2..."],
    "processed_img_hashes": ["QmHash3..."],
    "aposematic_img_hashes": ["QmHash4..."],
    "enciphered_img_hashes": ["QmHash5..."],
    "audio_data": "base64_or_path...",
    "audio_src_img": "QmHashOfImageWithAudio..."
}
```

| Field | Description |
|-------|-------------|
| `hvym_public_key` | Derived from stellar_secret |
| `debug_public_key` | Derived from debug_secret |
| `recipient_public_key` | Currently selected subscriber's key |
| `cipher_key` | Current ECDH shared key (hex) |
| `img_state` | Current view state (1-4) |
| `*_img_hashes` | IPFS hashes for each image state |
| `audio_data` | Current audio data for embedding |
| `audio_src_img` | Image hash that has audio embedded |
