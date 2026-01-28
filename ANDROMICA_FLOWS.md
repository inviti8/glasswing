# Andromica Deployment Flows

This document outlines all flows related to debug and Pintheon deployment in Andromica, covering data pod creation, processing, and rendering optimizations.

## Overview

Andromica supports two deployment targets:
1. **Debug Deploy** - Local testing with debug keys, renders immediately in browser tab
2. **Pintheon Deploy** - Production deployment to Heavymeta Pintheon nodes for distributed access

Both flows share common data pod creation and rendering logic but differ in key management and upload destinations.

---

## Flow Diagrams

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           ANDROMICA                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌──────────┐ │
│  │    RAW      │───▶│  PROCESSED  │───▶│  PROTECTED  │───▶│  DEPLOY  │ │
│  │   Images    │    │   Images    │    │   Images    │    │          │ │
│  └─────────────┘    └─────────────┘    └─────────────┘    └──────────┘ │
│        │                  │                  │                  │       │
│        ▼                  ▼                  ▼                  ▼       │
│    Import &           Watermark,        Aposematic         Debug OR     │
│    Audio Embed        Metadata          or Encrypt         Pintheon     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
            ┌───────────────────────┴───────────────────────┐
            │                                               │
            ▼                                               ▼
    ┌───────────────┐                             ┌───────────────┐
    │  DEBUG FLOW   │                             │ PINTHEON FLOW │
    │               │                             │               │
    │ • Debug key   │                             │ • Subscriber  │
    │ • Local IPFS  │                             │ • Pintheon    │
    │ • Immediate   │                             │   node upload │
    │   browser     │                             │ • IPNS        │
    │   preview     │                             │   publishing  │
    └───────────────┘                             └───────────────┘
```

---

## Image State Machine

Images progress through defined states, each stored with separate IPFS hash lists:

```
State 1: raw         → raw_img_hashes[]
State 2: processed   → processed_img_hashes[]
State 3: aposematic  → aposematic_img_hashes[]
State 4: enciphered  → enciphered_img_hashes[]
```

### State Transitions

```
┌─────────────┐
│    RAW      │  Import from folder, optional audio embedding
│  (state 1)  │
└──────┬──────┘
       │
       ▼ process_watermarking() / process_shared_iptc_metadata()
┌─────────────┐
│  PROCESSED  │  Watermark applied, IPTC metadata written
│  (state 2)  │
└──────┬──────┘
       │
       ├─────────────────────────────────────┐
       │                                     │
       ▼ process_aposematic()                ▼ process_enciphering()
┌─────────────┐                       ┌─────────────┐
│ APOSEMATIC  │  Visual scrambling    │ ENCIPHERED  │  Full encryption
│  (state 3)  │                       │  (state 4)  │
└─────────────┘                       └─────────────┘
```

---

## Debug Deploy Flow

**Entry Point:** `process_debug_deploy_gallery()` (main.py:1799)

### Flow Steps

```
1. Get Current State
   └─▶ img_state → state name (raw/processed/aposematic/enciphered)

2. Key Setup (Debug-Specific)
   └─▶ Uses debug_public_key as recipient
   └─▶ Regenerates shared key: creator_secret + debug_public_key

3. Recreate Protected Images (if aposematic state)
   └─▶ For each processed image:
       ├─▶ Generate new aposematic with correct shared key
       ├─▶ Add to IPFS → aposematic_img_hashes[]
       └─▶ Preserve audio metadata (do NOT re-embed)

4. Create Data Pod
   └─▶ create_ninjs_data_pod_with_encrypted_tokens()
       └─▶ Builds NINJS package with:
           ├─▶ Image metadata & renditions
           ├─▶ Audio metadata (format, size, method)
           ├─▶ Encryption keys (creator_public_key, recipient_public_key)
           └─▶ Aposematic params (op_string, scramble_mode)

5. Local IPFS Operations
   └─▶ ipns_clean_folder(state)
   └─▶ ipns_add_gallery_to_folder(state)

6. Process Data Pod Locally
   └─▶ process_data_pod_locally(output_path, debug_secret, app)
       ├─▶ Download images from IPFS
       ├─▶ Decrypt/descramble using debug key pair
       ├─▶ Extract audio tokens if present
       └─▶ Return processed data pod (images decrypted in-place)

7. Render Gallery HTML
   └─▶ Jinja2 template: templates/gallery.html
   └─▶ Context: data_pod, colors, gateway URLs
   └─▶ Store as pending_browser_html for BROWSER tab

8. Add HTML to IPFS
   └─▶ latest_gallery_html_hash stored for reference
```

### Key Configuration

| Component | Value | Source |
|-----------|-------|--------|
| Recipient Key | `debug_public_key` | `app.storage.user` |
| Subscriber Secret | `debug_secret` | `app.storage.user` |
| Shared Key | ECDH(creator_secret, debug_public_key) | Computed |

---

## Pintheon Deploy Flow

**Entry Point:** `process_pintheon_deploy_gallery()` (main.py:2114)

> **Note:** Now unified with debug flow - uses same data pod creation and preview decryption.

### Flow Steps

```
1. Pre-flight Checks
   ├─▶ is_pintheon_running() - verify node accessible
   ├─▶ access_token present
   └─▶ validate_img_state() - ensure valid state

2. Get Recipient Key
   └─▶ recipient_public_key (or fall back to debug_public_key)

3. Create Data Pod (UNIFIED with debug flow)
   └─▶ create_ninjs_data_pod_with_encrypted_tokens(app, state, recipient_key)
       └─▶ Full encryption metadata, audio tokens, type distribution

4. Local IPFS Operations
   └─▶ ipns_clean_folder(state)
   └─▶ ipns_add_gallery_to_folder(state)

5. Upload to Pintheon
   ├─▶ pintheon_create_directory(f"gallery_{state}")
   ├─▶ For each image hash:
   │   └─▶ pintheon_upload_file(file_path, directory, access_token)
   └─▶ pintheon_upload_file(data_pod.json, directory, access_token)

6. Process for Local Preview (NEW - unified with debug)
   └─▶ process_data_pod_locally(output_path, debug_secret, app)
       └─▶ Decrypts images for browser preview

7. Render Gallery HTML (using helper functions)
   └─▶ render_gallery_html(data_pod)
   └─▶ save_gallery_to_ipfs(html_content)

8. Upload HTML to Pintheon
   └─▶ pintheon_upload_file(gallery.html, directory, access_token)
   └─▶ Store pintheon_gallery_html_hash

9. Persist and Notify
   └─▶ persistent_save_data()
```

### Pintheon API Endpoints

| Function | Endpoint | Purpose |
|----------|----------|---------|
| `pintheon_create_directory()` | POST /api/mkdir | Create gallery directory |
| `pintheon_upload_file()` | POST /api/upload | Upload file with pinning |
| `pintheon_list_directories()` | GET /api/ls | List existing directories |

---

## Data Pod Creation

**Function:** `create_ninjs_data_pod(prefix)` (main.py:3063)

### NINJS Package Structure

```json
{
    "version": "1.0",
    "uri": "urn:newsml:package:TIMESTAMP",
    "type": "package",
    "content_type": "original|aposematic|encrypted",
    "creator_public_key": "BASE64...",      // For ECDH derivation
    "recipient_public_key": "BASE64...",    // Verification
    "op_string": "-^+",                     // Aposematic only
    "scramble_mode": 2,                     // Aposematic only
    "versioncreated": "ISO8601",
    "language": "en",
    "items": [...]
}
```

### Item Structure

```json
{
    "uri": "gateway:hash",
    "type": "picture|audio_image",
    "headline": "Title",
    "description_text": "Description",
    "renditions": [{
        "href": "http://gateway/ipfs/HASH",
        "ipfs_hash": "HASH",
        "mimetype": "image/png",
        "width": 1920,
        "height": 1080
    }],
    // Audio fields (if audio_image type)
    "audio_format": "wav|mp3|flac|ogg",
    "audio_duration": 0,
    "audio_size": 12345,
    "audio_method": "metadata|token"
}
```

### Optimization: No Inline Audio Data

Audio data is **NOT** embedded in the data pod to prevent large HTML files:

```python
# ✅ CORRECT - Only metadata, JavaScript extracts audio
"audio_format": "wav",
"audio_size": 5700000,
"audio_method": "metadata"

# ❌ WRONG - Would cause 30MB+ HTML files
"audio_data": "BASE64_ENCODED_AUDIO..."
```

---

## Data Pod Processing

**Function:** `process_data_pod_locally()` (data_pod_audio.py:273)

### Processing Steps

```
1. Load Data Pod JSON

2. Generate Shared Key
   └─▶ StellarSharedKey(subscriber_keys, creator_public_key)
   └─▶ cipher_key = shared_secret().hex()

3. For Each Item:
   ├─▶ Download image from IPFS
   │
   ├─▶ Decrypt if needed:
   │   ├─▶ encrypted → new_deciphered_img(path, cipher_key)
   │   └─▶ aposematic → recover_aposematic_img(path, cipher_key, op_string)
   │
   ├─▶ Extract audio if present:
   │   ├─▶ Check actual audio method: has_audio_data(path)
   │   ├─▶ If token: extract_audio_token() → extract_audio_from_token()
   │   └─▶ If metadata: extract_audio_from_image() (base64 fallback)
   │
   └─▶ Update item with decrypted paths/data

4. Return processed data pod
```

### embed_images_as_base64 Parameter

```python
async def process_data_pod_locally(
    data_pod_path: str,
    subscriber_stellar_secret: str,
    app,
    embed_images_as_base64: bool = False  # Default FALSE for performance
)
```

- `False` (default): Keep IPFS URLs, requires local IPFS daemon
- `True`: Convert to base64 data URIs for offline HTML (larger file size)

---

## Gallery HTML Rendering

**Template:** `templates/gallery.html`

### Unified Helper Functions (main.py)

Both debug and Pintheon flows now use shared helper functions:

```python
def get_gallery_colors() -> dict:
    """Get current color scheme based on dark mode setting."""
    # Returns appropriate light/dark color dict

def render_gallery_html(data_pod: dict) -> str:
    """Render gallery HTML from data pod using Jinja2 template."""
    # Sets up Jinja2, applies colors, renders template

def save_gallery_to_ipfs(html_content: str) -> tuple:
    """Save rendered gallery HTML to temp file and IPFS."""
    # Returns (html_temp_path, html_hash)
```

### Template Context

```python
template_context = {
    "data_pod": processed_data_pod,
    "ipfs_gateway": "http://127.0.0.1:8080",
    "colors": get_gallery_colors(),  # Helper function
    "is_dark_mode": True/False,
    "gallery_title": "...",
    "gallery_description": "..."
}
```

### Audio Playback Strategy

```html
{% if item.audio and item.audio.data %}
    <!-- Pre-extracted audio (base64 in data pod) -->
    <button onclick="playPreExtractedAudio('{{ item.audio.data }}', '{{ item.audio_format }}')">
{% else %}
    <!-- JavaScript extraction from image -->
    <button onclick="playAudioFromImage('{{ item.renditions[0].href }}', '{{ item.audio_format }}')">
{% endif %}
```

---

## Audio Handling

### Audio Methods

| Method | Storage | Encryption | Extraction |
|--------|---------|------------|------------|
| `metadata` | PNG tEXt chunk (base64) | None | `extract_audio_from_image()` |
| `token` | PNG tEXt chunk (HVYMDataToken) | ECDH + Biscuit | `extract_audio_token()` + `extract_audio_from_token()` |

### Audio Token Flow (Encrypted Audio)

```
Creation:
  audio_data → HVYMDataToken.create_from_bytes() → serialize() → embed in PNG

Extraction:
  PNG → extract_audio_token() → HVYMDataToken.extract_from_token() → audio_data
```

### Audio Metadata Flow (Unencrypted Audio)

```
Creation:
  audio_data → base64 encode → embed_audio_metadata() → PNG tEXt chunk

Extraction:
  PNG → extract_audio_from_image() → base64 decode → audio_data
```

---

## Storage Patterns

### Helper Functions (main.py)

The following helper functions ensure proper NiceGUI storage persistence:

```python
def ensure_storage_list(key: str) -> list:
    """Ensure a storage list exists and return it."""
    if key not in app.storage.user:
        app.storage.user[key] = []
    return app.storage.user[key]

def append_to_storage_list(key: str, value) -> None:
    """Safely append a value to a storage list with proper persistence."""
    lst = app.storage.user.get(key, [])
    lst.append(value)
    app.storage.user[key] = lst  # Reassignment triggers persistence

def validate_img_state() -> tuple:
    """Validate and return the current image state."""
    img_states = {1: "raw", 2: "processed", 3: "aposematic", 4: "enciphered"}
    idex = app.storage.user.get("img_state", 1)
    if idex not in img_states:
        return None, None
    return idex, img_states[idex]
```

### List Reset Pattern

```python
# ✅ CORRECT - Direct assignment (triggers NiceGUI change detection)
app.storage.user["processed_img_hashes"] = []

# ❌ WRONG - In-place clear may not trigger persistence
app.storage.user["processed_img_hashes"].clear()
```

### List Append Pattern

```python
# ✅ CORRECT - Use helper function
append_to_storage_list("processed_img_hashes", ipfs_hash)

# ✅ ALSO CORRECT - Manual reassignment
lst = app.storage.user.get("processed_img_hashes", [])
lst.append(ipfs_hash)
app.storage.user["processed_img_hashes"] = lst

# ❌ WRONG - Returns temporary list, changes not persisted
app.storage.user.get("processed_img_hashes", []).append(ipfs_hash)
```

### Per-Image Metadata Storage

```python
app.storage.user[ipfs_hash] = {
    "path": "/path/to/file.png",
    "name": "original_filename.png",
    "original_hash": "QmOriginal...",  # For processed images
    "has_audio": True,
    "audio_path": "/path/to/audio.wav",
    "audio_format": "wav",
    "audio_method": "metadata|token",
    "render_metadata": True
}
```

---

## Optimization Guidelines

### Data Pod Size

1. **Never embed audio data inline** - use JavaScript extraction
2. **Use IPFS URLs by default** - set `embed_images_as_base64=False`
3. **Only include necessary metadata** in items

### Performance

1. **Parallel image processing** where possible
2. **Lazy audio extraction** - only when user clicks play
3. **Cache decrypted images** in temp directory

### Error Handling

1. **Fallback audio extraction** - try token, then metadata
2. **Basic metadata for audio images** if ExifTool fails
3. **Graceful degradation** when IPFS unavailable

---

## Function Reference

### Deploy Functions

| Function | File | Line | Purpose |
|----------|------|------|---------|
| `process_debug_deploy_gallery()` | main.py | 1799 | Debug deploy with local preview |
| `process_pintheon_deploy_gallery()` | main.py | 2035 | Production Pintheon deploy |
| `create_ninjs_data_pod()` | main.py | 3063 | Create NINJS format data pod |
| `create_ninjs_data_pod_with_encrypted_tokens()` | main.py | - | Data pod with audio tokens |
| `deploy_ninjs_data_pod()` | main.py | 3319 | API deployment helper |
| `deploy_gallery_images()` | main.py | 3393 | Upload images to API |

### Pintheon Functions

| Function | File | Line | Purpose |
|----------|------|------|---------|
| `is_pintheon_running()` | main.py | 667 | Check node availability |
| `pintheon_create_directory()` | main.py | 676 | Create directory on node |
| `pintheon_upload_file()` | main.py | 719 | Upload and pin file |
| `pintheon_list_directories()` | main.py | 777 | List existing directories |

### Processing Functions

| Function | File | Line | Purpose |
|----------|------|------|---------|
| `process_data_pod_locally()` | data_pod_audio.py | 273 | Decrypt and process data pod |
| `extract_audio_from_image()` | data_pod_audio.py | - | Extract base64 audio |
| `has_audio_data()` | data_pod_audio.py | - | Check audio presence/method |

### Audio Token Functions

| Function | File | Purpose |
|----------|------|---------|
| `create_audio_token()` | audio_tokens.py | Create encrypted audio token |
| `extract_audio_from_token()` | audio_tokens.py | Decrypt audio from token |
| `embed_audio_token()` | png_chunks.py | Embed token in PNG |
| `extract_audio_token()` | png_chunks.py | Extract token from PNG |

---

## Troubleshooting

### Common Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| 30MB+ HTML file | Audio data embedded inline | Set `embed_images_as_base64=False` |
| Images not appearing | Hash list not persisted | Use correct storage pattern |
| Audio won't play | Wrong extraction method | Check `audioMethod` vs actual |
| Decryption fails | Key mismatch | Verify creator/subscriber keys |
| `name 'audio_method' is not defined` | Variable typo | Use `item.get("audioMethod")` |

### Debug Logging

Key debug points in the flow:

```python
print(f"🔍 Debug flow using debug public key: {current_public_key[:16]}...")
print(f"🔐 Subscriber stellar secret (first 16): {subscriber_secret[:16]}...")
print(f"🔑 Generated cipher key (first 16 chars): {cipher_key[:16]}...")
print(f"🔍 Audio check: has_audio={has_audio}, actual_method={actual_method}")
```
