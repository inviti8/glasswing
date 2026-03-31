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
    "video_token_images": ["QmHash3..."],
    "markdown_token_images": ["QmHash4..."],
    "type_distribution": {
        "raw": 0,
        "processed": 0,
        "aposematic": 3,
        "enciphered": 0,
        "total_with_audio": 2,
        "audio_token_count": 2,
        "total_with_video": 1,
        "video_token_count": 1,
        "total_with_markdown": 1,
        "markdown_token_count": 1
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
| `video_token_images` | List of image hashes containing video token CID references |
| `markdown_token_images` | List of image hashes containing markdown tokens |
| `type_distribution` | Counts of each image/media type in the data pod |

### Item Structure

Each image in the gallery:

```json
{
    "type": "video_image",
    "guid": "urn:uuid:QmHash...",
    "version": "1",
    "language": "en",
    "pubstatus": "usable",
    "title": "image_name.png",
    "byline": "Creator Name",
    "creditline": "Photographer Name",
    "copyright": "All Rights Reserved",
    "ednote": "Type: aposematic, Video method: token",
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
    "hasAudio": false,
    "audioMethod": "token",
    "hasVideo": true,
    "videoMethod": "token",
    "videoTokenCid": "QmVideoCID...",
    "hasMarkdown": true,
    "markdownMethod": "token",
    "markdownToken": "<serialized HVYMDataToken>",
    "original_hash": "QmOriginalProcessedHash...",
    "audioTokenInfo": null,
    "videoTokenInfo": {
        "receiverPublicKey": "GXYZ123...",
        "tokenExpiry": null,
        "noExpiry": true
    },
    "markdownTokenInfo": {
        "receiverPublicKey": "GXYZ123...",
        "tokenExpiry": null,
        "noExpiry": true
    }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `type` | string | `"video_image"`, `"audio_image"`, `"markdown_image"`, or `"picture"` |
| `guid` | string | Unique identifier using IPFS hash |
| `imageType` | string | `"raw"`, `"processed"`, `"aposematic"`, or `"enciphered"` |
| `hasAudio` | boolean | Whether image contains embedded audio token |
| `audioMethod` | string | `"token"` (encrypted) |
| `hasVideo` | boolean | Whether image contains embedded video token CID |
| `videoMethod` | string | `"token"` (encrypted, stored on IPFS) |
| `videoTokenCid` | string | IPFS CID for the encrypted video token |
| `hasMarkdown` | boolean | Whether image contains embedded markdown token |
| `markdownMethod` | string | `"token"` (encrypted) |
| `markdownToken` | string | Serialized HVYMDataToken (stored in data pod JSON, not in image chunks) |
| `original_hash` | string | For enciphered images: hash of original processed image (for media extraction) |
| `audioTokenInfo` | object | Receiver key, expiry for audio token |
| `videoTokenInfo` | object | Receiver key, expiry for video token |
| `markdownTokenInfo` | object | Receiver key, expiry for markdown token |
| `renditions` | array | List of image renditions (note: array, not object) |

**Item Type Precedence:** `video_image` > `audio_image` > `markdown_image` > `picture`

An image with both audio and markdown is typed `audio_image` (with `hasMarkdown: true`). Markdown is independent — it can coexist with audio or video.

**audioTokenInfo / videoTokenInfo Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `receiverPublicKey` | string | Recipient's Stellar public key |
| `tokenExpiry` | number/null | Unix timestamp when token expires, or `null` for no expiry |
| `noExpiry` | boolean | `true` if token never expires |

### Media in Processed Items

After `process_data_pod_locally()`, items may include decoded audio, video, and/or markdown:

```json
{
    "audio": {
        "data": "base64_encoded_audio_data...",
        "format": "wav"
    },
    "video": {
        "src": "/editor/video_abc123.mp4",
        "format": "mp4",
        "localPath": "/tmp/glasswing_editor_xxx/video_abc123.mp4"
    },
    "markdown": {
        "files": [
            {
                "filename": "description.md",
                "text": "# Raw markdown text...",
                "text_html": "<h1>Raw markdown text...</h1>",
                "size": 1234
            }
        ]
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
    "label": "My Publisher",
    "url": "https://mypublisher.pintheon.com",
    "ipns_hash": "k51qzi5uqu5d...",
    "added": "2026-03-30T12:00:00",
    "last_fetched": "2026-03-30T14:00:00",
    "data_pod_hash": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `label` | string | User-friendly subscription name |
| `url` | string | Pintheon node public gateway URL (auto-prepends `https://`) |
| `ipns_hash` | string/null | IPNS key ID (auto-discovered from stellar.toml, or cached) |
| `added` | string | ISO timestamp when subscription was added |
| `last_fetched` | string/null | ISO timestamp of last successful fetch |

**IPNS Resolution:** The subscriber's public key (derived from App Key) is used as the
directory name on Pintheon. The IPNS hash is auto-discovered by reading the node's
`/.well-known/stellar.toml` `[SUBSCRIBER_DIRECTORIES]` section, with fallback to the
IPFS key list API.

### Fetched Subscription Metadata

Stored in `app.storage.user['fetched_subscriptions']` as a dict keyed by label:

```json
{
    "My Publisher": {
        "label": "My Publisher",
        "node_url": "https://mypublisher.pintheon.com",
        "ipns_hash": "k51qzi5uqu5d...",
        "data_pods": [
            {
                "name": "ninjs_data_pod_aposematic_20260330.json",
                "data": { "...full data pod JSON..." },
                "items_count": 5,
                "content_type": "mixed",
                "created": "2026-03-30T12:00:00"
            }
        ],
        "image_links": [
            {"name": "image1.png", "href": "https://.../ipfs/QmHash..."}
        ],
        "fetched_at": "2026-03-30T14:00:00"
    }
}
```

**Multiple Datapods:** A subscription directory may contain multiple data pod JSON files
(book, album, graphic novel). Each appears as a selectable channel in the Select Channel dialog.
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
    "editor_url": "/editor/abc123def.png",
    "extension": ".png",
    "render_metadata": true,
    "image_type": "aposematic",
    "has_audio": true,
    "audio_method": "token",
    "audio_path": "/path/to/audio.wav",
    "audio_format": "wav",
    "audio_duration": 5.2,
    "audio_size": 230400,
    "audio_token_expires": null,
    "audio_token_no_expiry": true,
    "has_video": false,
    "video_method": null,
    "video_token_cid": null,
    "video_path": null,
    "video_token_expires": null,
    "video_token_no_expiry": false,
    "has_markdown": true,
    "markdown_method": "token",
    "markdown_files": [{"filename": "description.md", "size": 1234}],
    "markdown_token_expires": null,
    "markdown_token_no_expiry": true,
    "original_hash": "QmOriginalProcessedHash..."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `path` | string | Local filesystem path to image |
| `name` | string | Original filename |
| `editor_url` | string | `/editor/{filename}` URL for display in UI |
| `image_type` | string | Current state: `raw`, `processed`, `aposematic`, `enciphered` |
| `has_audio` | boolean | Whether audio token is embedded |
| `audio_method` | string | `"token"` |
| `audio_path` | string | Path to original audio file |
| `audio_format` | string | Audio format (e.g., `"wav"`, `"mp3"`) |
| `audio_duration` | float | Audio duration in seconds |
| `audio_size` | integer | Audio file size in bytes |
| `audio_token_expires` | number/null | Unix timestamp when token expires, or `null` for no expiry |
| `audio_token_no_expiry` | boolean | `true` if token never expires |
| `has_video` | boolean | Whether video token CID is embedded |
| `video_method` | string | `"token"` |
| `video_token_cid` | string | IPFS CID for encrypted video token |
| `video_path` | string | Path to original video file |
| `video_token_expires` | number/null | Unix timestamp when token expires |
| `video_token_no_expiry` | boolean | `true` if token never expires |
| `has_markdown` | boolean | Whether markdown token is embedded |
| `markdown_method` | string | `"token"` |
| `markdown_files` | list | List of `{"filename": str, "size": int}` for bundled files |
| `markdown_token_expires` | number/null | Unix timestamp when token expires, or `null` for no expiry |
| `markdown_token_no_expiry` | boolean | `true` if token never expires |
| `original_hash` | string | For enciphered: hash of processed image (contains media) |

## Media Embedding

### Audio, Video, and Markdown Methods

An image supports **audio OR video** (not both), **plus markdown independently**. All use HVYMDataToken encryption.

| Media | Storage | Encryption | tEXt Chunk Keywords |
|-------|---------|------------|---------------------|
| Audio | Encrypted token in PNG tEXt chunks | HVYMDataToken (ChaCha20-Poly1305) | `audio_token_001`, `audio_token_002`, ... |
| Video | Encrypted token on IPFS; CID in PNG tEXt chunks | HVYMDataToken (ChaCha20-Poly1305) | `video_token_cid_001`, `video_token_cid_002`, ... |
| Markdown | Encrypted token in PNG tEXt chunks | HVYMDataToken (ChaCha20-Poly1305) | `markdown_token_001`, `markdown_token_002`, ... |

**Note:** Markdown tokens are NOT reembedded into aposematic images. The serialized token is extracted during data pod creation and stored in the data pod JSON (`markdownToken` field). On the subscriber side, the token is read from the JSON and decrypted directly.

### HVYMDataToken Structure

Audio, video, and markdown tokens all use the hvym-stellar library's Biscuit-based format:

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

### Video Token IPFS Storage

Video tokens are too large for PNG tEXt chunks. Instead:
1. The encrypted video token is uploaded to IPFS as a standalone file
2. The IPFS CID (~50 bytes) is embedded in the PNG tEXt chunks
3. On playback, the CID is extracted → token is fetched from IPFS → decrypted

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
    "raw_img_hashes": ["hash1...", "hash2..."],
    "processed_img_hashes": ["hash3..."],
    "aposematic_img_hashes": ["QmHash4..."],
    "enciphered_img_hashes": ["QmHash5..."]
}
```

| Field | Description |
|-------|-------------|
| `hvym_public_key` | Derived from stellar_secret |
| `debug_public_key` | Derived from debug_secret |
| `recipient_public_key` | Currently selected subscriber's key |
| `cipher_key` | Current ECDH shared key (hex) |
| `img_state` | Current view state (1-4) |
| `*_img_hashes` | Local hashes (raw/processed) or IPFS hashes (aposematic/enciphered) |

**Note:** Raw and processed images are stored in the session-scoped `EDITOR_STORAGE_DIR` (a `tempfile.mkdtemp()` served at `/editor`). They are NOT uploaded to IPFS until deployment. Aposematic and enciphered images are stored on IPFS.
