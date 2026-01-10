# Andromica Technical Architecture

## Overview

Andromica is a decentralized content creation and distribution system built on IPFS and Stellar cryptography. It enables creators to publish protected galleries that can only be viewed by authorized subscribers.

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
│  │ • Create aposematic │    │ • Decrypt content   │            │
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
- `process_aposematic()` - Generate scrambled images
- `process_enciphering()` - Generate encrypted images
- `create_ninjs_data_pod()` - Create NINJS-format data pods
- `select_channel()` - Browser mode channel rendering
- `decode_protected_images()` - Decrypt/descramble for viewing

**Global State:**
- `app.storage.user` - Persistent user data (NiceGUI storage)
- `img_states = {1: 'raw', 2: 'processed', 3: 'aposematic', 4: 'enciphered'}`

### dialogs.py
UI dialog components for user interactions.

**Key Functions:**
- `create_shared_key(receiver_public_key)` - Generate shared encryption key
- `get_recipient_options()` - Build subscriber dropdown options
- `cipher_dialog()` - Encryption recipient selection
- `aposematic_dialog()` - Aposematic settings and recipient selection
- `add_subscriber_dialog()` - Add new subscriber
- `add_subscription_dialog()` - Subscribe to a channel

### img_edit.py
Image processing and manipulation.

**Key Functions:**
- `new_enciphered_img()` - Encrypt image using ImageMagick
- `new_deciphered_img()` - Decrypt image
- `iptc_set_field_value()` - Write IPTC metadata
- `iptc_get_field_value()` - Read IPTC metadata

### metadata.py
IPTC metadata management and data classes.

## Data Flow

### Creator Flow (Image Mode)

```
┌─────────┐    ┌───────────┐    ┌─────────────┐    ┌──────────┐
│  RAW    │───▶│ PROCESSED │───▶│ APOSEMATIC  │───▶│  DEPLOY  │
│ Images  │    │  Images   │    │ or ENCRYPTED│    │  to IPFS │
└─────────┘    └───────────┘    └─────────────┘    └──────────┘
     │              │                  │                 │
     ▼              ▼                  ▼                 ▼
  Import      Watermark,          Select            Create
  from        resize,             recipient,        data pod,
  folder      metadata            generate          upload to
                                  shared key        Pintheon
```

### Consumer Flow (Browser Mode)

```
┌─────────────┐    ┌───────────┐    ┌─────────────┐    ┌──────────┐
│ SUBSCRIBE   │───▶│   FETCH   │───▶│   DECODE    │───▶│  RENDER  │
│ to channel  │    │  data pod │    │   images    │    │  gallery │
└─────────────┘    └───────────┘    └─────────────┘    └──────────┘
      │                  │                 │                 │
      ▼                  ▼                 ▼                 ▼
   Add IPNS         Download         Generate           Convert to
   hash and         from IPFS        shared key,        base64 URI,
   node URL                          decrypt/           display in
                                     descramble         template
```

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
    # ... additional settings
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
        "original_hash": str        # For processed images
    }
}
```

## Key Technologies

| Component | Technology | Purpose |
|-----------|------------|---------|
| UI Framework | NiceGUI | Web-based desktop UI |
| Desktop Wrapper | pywebview | Native window container |
| Image Processing | Wand/ImageMagick | Encryption, watermarking |
| Metadata | exiftool, exiv2 | IPTC/EXIF/XMP handling |
| Cryptography | hvym-stellar | Stellar-based shared keys |
| Aposematic | aiposematic | Image scrambling |
| Storage | IPFS | Decentralized file storage |
| Deployment | Pintheon | Gallery hosting platform |

## File Structure

```
andromica/
├── main.py              # Application entry, UI, core logic
├── dialogs.py           # Dialog components
├── img_edit.py          # Image processing functions
├── metadata.py          # IPTC data management
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

## Integration Points

### IPFS
- Local daemon at `127.0.0.1:5001`
- Functions: `ipfs_add()`, `ipfs_get()`, `ipns_*` operations
- Used for image storage and data pod distribution

### Pintheon
- REST API for gallery deployment
- Handles IPNS pinning and directory management
- Access token authentication

### Stellar/hvym-stellar
- `Stellar25519KeyPair` - Ed25519 key derivation
- `StellarSharedKey` - ECDH shared secret generation
- Keys stored as Stellar-format secrets

## Error Handling

The application uses a combination of:
- Try/catch with console logging for debugging
- `ui.notify()` for user-facing messages
- Graceful degradation when IPFS is unavailable
