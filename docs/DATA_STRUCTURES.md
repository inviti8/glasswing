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

For `aposematic` or `encrypted` content:

```json
{
    "version": "1.0",
    "uri": "urn:newsml:package:20260110123456",
    "type": "package",
    "content_type": "aposematic",
    "recipient_public_key": "GABCDEFGHIJKLMNOP...",
    "op_string": "-^+",
    "scramble_mode": 2,
    "versioncreated": "2026-01-10T12:34:56Z",
    "language": "en",
    "items": [...]
}
```

### Item Structure

Each image in the gallery:

```json
{
    "uri": "http://127.0.0.1:8080:QmHash...",
    "type": "picture",
    "version": "1.0",
    "versioncreated": "2026-01-10T12:34:56Z",
    "firstcreated": "2026-01-01T00:00:00",
    "pubstatus": "usable",
    "language": "en",
    "headline": "Image Title",
    "description_text": "Image description from IPTC caption",
    "keywords": ["keyword1", "keyword2"],
    "copyrightnotice": "All Rights Reserved",
    "creditline": "Photographer Name",
    "byline": ["Creator Name"],
    "renditions": {
        "original": {
            "href": "http://127.0.0.1:8080/ipfs/QmHash...",
            "ipfs_hash": "QmHash...",
            "mimetype": "image/jpeg",
            "width": 1920,
            "height": 1080
        }
    },
    "place": [
        {"name": "City", "country": "Country"}
    ],
    "usageterms": "Usage terms from XMP",
    "rightsinfo": {
        "langid": "http://www.lexvo.org/page/iso639-3/eng",
        "usagetypes": ["publish", "archive"]
    },
    "restrictions": {
        "type": "restricted",
        "constraints": ["DMI-PROHIBITED"]
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

```json
{
    "name": "Channel Name",
    "url": "https://pintheon-node.example.com",
    "ipns_hash": "k51qzi5uqu5d..."
}
```

Stored in `app.storage.user['subscriptions']` as a list.

## Image Hash Metadata

For each image hash in storage:

```json
{
    "path": "/path/to/local/file.jpg",
    "name": "original_filename.jpg",
    "original_hash": "QmOriginalHash..."
}
```

Accessed via `app.storage.user[hash_value]`.

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
    "app_mode": "image",
    "app_colors": {...},
    "dark_mode": null,
    "latest_data_pod_hash": null,
    "latest_gallery_html_hash": null,
    "latest_data_pod_timestamp": null,
    "gallery_title": "",
    "gallery_description": ""
}
```
