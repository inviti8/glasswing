# VIDEO_SUPPORT: Encrypted Media Embedding for Images

## Problem

1. Glasswing currently supports embedding audio into images via PNG tEXt chunks with two methods: "metadata" (unencrypted base64) and "token" (encrypted HVYMDataToken). The unencrypted metadata path is unnecessary — all media should be encrypted to protect creator content.
2. There is no video support. Creators want to attach video content to their images, protected by the same Stellar key-based encryption used for audio tokens.

## Goals

1. **Remove the unencrypted audio "metadata" path** — audio embedding should always use HVYMDataToken (token-only). This aligns audio with the same security model as video.
2. **Add video embedding** to images using IPFS-stored encrypted file tokens, decryptable only by the designated subscriber.

## Design Principles

1. **Always encrypted**: Both audio and video are always wrapped in an HVYMDataToken before storage. No unencrypted "metadata" method for either media type — token-only.
2. **IPFS CID reference (video)**: Video tokens are stored on IPFS; the PNG image stores only the IPFS CID of the encrypted token. This keeps PNG file sizes manageable. Audio tokens remain embedded in PNG tEXt chunks (they're small enough).
3. **Server-side decryption**: Both audio and video tokens must be decrypted server-side during `process_data_pod_locally()` before the browser can render them.
4. **Video player popup**: In the gallery (both editor mode and browser), clicking play on a video image opens a video player element (popup/dialog), not inline playback.
5. **Parallel flows**: Audio and video share the same dialog pattern, FAB actions, data pod schema extensions, and recovery flow.

## Part 1: Audio Simplification — Remove "metadata" (Unencrypted) Path

### Current Audio Architecture

Audio embedding currently supports two methods:
- **`"metadata"`** — Audio is base64-encoded and stored directly in PNG tEXt chunks (`audio_base64_001`, `audio_base64_002`, ...). Unencrypted. Client-side JavaScript can extract and play it directly from the image file.
- **`"token"`** — Audio is encrypted via HVYMDataToken (ChaCha20-Poly1305 + ECDH) and stored in PNG tEXt chunks (`audio_token_001`, `audio_token_002`, ...). Requires server-side decryption before playback.

### What to Remove

The entire `"metadata"` code path — all base64-in-PNG audio embedding and client-side extraction.

### Changes by File

#### `dialogs.py` — `edit_audio_info()` (line ~630)

**Remove:**
- The "Audio Method" selector (`ui.select` with `metadata`/`token` options, line ~689)
- The `update_token_options()` visibility toggle (line ~736) — token options are always visible now
- The conditional logic in `on_confirm()` that checks `audio_method.value == 'token'` (line ~659)
- The conditional `receiver_public_key` / `expiry_option` logic (lines ~670-671)

**Change:**
- Always set `audio_method: "token"` in `_audio_embed_params`
- Always require recipient selection (no conditional)
- Always show recipient + expiry selectors (remove hide/show toggle)
- Rename button label from "Embed Audio" → keep or update to "Encrypt & Embed Audio"

#### `main.py` — `process_audio_embedding()` (line ~5129)

**Remove:**
- The `audio_method="metadata"` default parameter — change to `audio_method="token"`
- The `else` branch (lines ~5175-5177) that calls `create_audio_image(audio_file, img_path)` for metadata method
- The conditional `if audio_method == "token" and not receiver_public_key` — receiver is always required now

**Change:**
- Always use the token path: `create_token_audio_image(audio_file, img_path, sender_kp, receiver_public_key, expires_in)`
- `audio_method` field in metadata is always `"token"`

#### `main.py` — `create_audio_image()` (line ~4988)

**Remove entirely.** This is the unencrypted base64 embedding function. With token-only, it's dead code. Also remove `create_audio_visualization()` (line ~5036) if it's only used by the metadata path.

#### `main.py` — `extract_audio_chunks_endpoint()` (line ~5105)

**Remove entirely.** This POST endpoint extracts base64 audio from PNG chunks — only needed for the metadata path. Token audio is always decrypted server-side, not extracted by the client.

#### `png_chunks.py` — Base64 Audio Functions

**Remove:**
- `AUDIO_BASE64_PREFIX = 'audio_base64_'` (line ~20)
- `embed_audio_base64()` (line ~170)
- `extract_audio_base64()` (line ~200)

**Keep:**
- `AUDIO_TOKEN_PREFIX = 'audio_token_'` (line ~21)
- `embed_audio_token()` (line ~185)
- `extract_audio_token()` (line ~205)
- `has_audio_data()` (line ~210) — simplify to only check for token prefix
- All generic functions: `write_text_chunks()`, `read_text_chunks()`, `extract_combined_data()`

#### `audio_tokens.py`

**No changes needed.** This file only handles the token path. Keep all functions as-is.

#### `templates/gallery.html` — Client-Side Audio Extraction

**Remove:**
- `extractAudioFromImage()` function (line ~301) — fetches image and extracts base64 chunks
- `extractAudioChunks()` function (line ~333) — walks PNG binary to find `audio_base64_*` chunks
- `detectAudioFormat()` function (line ~413) — magic byte detection (keep if used elsewhere, but only needed for metadata path)
- `arrayBufferToBase64()` function (line ~440)
- `playAudioFromImage()` function (line ~462) — the metadata extraction + play path
- `tryBlobMethod()` function (line ~549) — fallback for metadata audio playback

**Keep:**
- `playPreExtractedAudio()` function (line ~450) — this is the token path (server-decrypted audio)
- `playExtractedAudio()` function (line ~502) — shared playback logic, used by both paths but keep for token

**Simplify template:**
```html
<!-- Audio Controls — token-only, always pre-extracted -->
<div class="audio-controls">
    {% if item.audio and item.audio.data %}
    <button class="audio-play-btn" onclick="playPreExtractedAudio('{{ item.audio.data }}', '{{ item.audio.format }}', this)">
        ▶️
    </button>
    {% else %}
    <button class="audio-play-btn" disabled title="Audio requires decryption">
        🔒
    </button>
    {% endif %}
</div>
```

The `{% else %}` branch that called `playAudioFromImage()` for metadata method is removed. If audio hasn't been decrypted yet, show a lock icon.

#### `data_pod_audio.py` — `process_data_pod_locally()` (line ~292)

**Simplify:**
- Remove the base64 audio extraction branches — no more `pre_extracted_audio["type"] == "base64"` handling
- Remove fallback `extract_audio_base64(decoded_path)` calls
- All audio is token-based: always extract via `extract_audio_from_token(subscriber_keys, serialized_token)`

#### `data_pod_audio.py` — `create_ninjs_data_pod_with_encrypted_tokens()`

**Simplify:**
- `audioMethod` is always `"token"` — can remove conditional logic
- `audioTokenInfo` is always present for audio images

#### `main.py` — `create_ninjs_data_pod()`

**Simplify:**
- `audio_method` is always `"token"`
- Remove any metadata-specific fields or conditional logic

### Audio Simplification Summary

| Component | Before | After |
|-----------|--------|-------|
| `edit_audio_info()` dialog | Method selector (metadata/token) | Token-only (no selector) |
| `process_audio_embedding()` | Branches on method | Always token path |
| `create_audio_image()` | Base64 embedding function | **Removed** |
| `extract_audio_chunks_endpoint()` | POST API for client extraction | **Removed** |
| `png_chunks.py` base64 functions | `embed/extract_audio_base64` | **Removed** |
| `gallery.html` JS extraction | `extractAudioChunks()`, `playAudioFromImage()` | **Removed** |
| `gallery.html` template | Two play button paths | Token path only, lock icon fallback |
| `process_data_pod_locally()` | Base64 + token branches | Token-only |

---

## Part 2: Video Embedding

### Current Audio Token Flow (Reference — Post-Simplification)
```
User selects audio file
  → edit_audio_info() dialog (recipient, expiry) — always token
  → create_token_audio_image()
    → HVYMDataToken.create_from_bytes(sender_kp, receiver_pub, audio_bytes, filename, expires_in)
    → token.serialize() → embed in PNG tEXt chunks (audio_token_001, audio_token_002, ...)
  → _local_store_image_pure() → editor storage
  → metadata: { has_audio: true, audio_method: "token", ... }
```

### Audio Recovery Flow (Reference — Post-Simplification)
```
process_data_pod_locally()
  → extract audio token from PNG tEXt chunks BEFORE image recovery
  → recover image (aposematic/enciphered)
  → HVYMDataToken.extract_from_token(receiver_kp, token)
  → item["audio"] = { data: base64, format: "wav", method: "token", ... }
  → gallery.html: playPreExtractedAudio(item.audio.data, item.audio.format)
```

## Proposed Video Architecture

### Video Embedding Flow
```
User selects video file
  → edit_video_info() dialog (recipient, expiry)  — always token method
  → create_video_token()
    → HVYMDataToken.create_from_bytes(sender_kp, receiver_pub, video_bytes, filename, expires_in)
    → token.serialize()
  → Upload serialized token to IPFS → get CID
  → Embed CID reference in PNG tEXt chunk (video_token_cid_001)
  → _local_store_image_pure() → editor storage
  → metadata: { has_video: true, video_method: "token", video_token_cid: "<ipfs_cid>", ... }
```

### Video Recovery Flow
```
process_data_pod_locally()
  → Read video_token_cid from PNG tEXt chunks (or from data pod item metadata)
  → Fetch encrypted token from IPFS using CID
  → HVYMDataToken.extract_from_token(receiver_kp, token) → raw video bytes
  → Detect video format from magic bytes
  → item["video"] = { data: base64, format: "mp4", method: "token", ... }
  → gallery.html: playPreExtractedVideo(item.video.data, item.video.format) → popup player
```

## Detailed Changes

### 1. New File: `video_tokens.py`

Mirrors `audio_tokens.py` structure. Handles video-specific token operations.

```python
# Constants
SUPPORTED_VIDEO_EXTENSIONS = ['.mp4', '.webm', '.mov', '.avi', '.mkv']
VIDEO_SIGNATURES = {
    b'\x00\x00\x00': 'mp4',      # ftyp box (need to check bytes 4-7 for 'ftyp')
    b'\x1a\x45\xdf\xa3': 'webm', # EBML header (Matroska/WebM)
    b'RIFF': 'avi',               # AVI uses RIFF container
}

def is_video_file(file_path) -> bool
def detect_video_format(video_data: bytes) -> str

def create_video_token(sender_kp, receiver_pub, video_data, filename, expires_in) -> str
    # Same as create_audio_token — HVYMDataToken.create_from_bytes()
    # Video data is raw bytes, encrypted via ChaCha20-Poly1305

def extract_video_from_token(receiver_kp, serialized_token, verify_hash=True) -> (bytes, dict)
    # Same as extract_audio_from_token — HVYMDataToken.extract_from_token()

def create_token_video_image(video_file, image_file, sender_kp, receiver_pub, expires_in) -> str
    # 1. Read video file as raw bytes
    # 2. Create HVYMDataToken from video bytes
    # 3. Serialize token → upload to IPFS → get CID
    # 4. Embed CID in PNG tEXt chunk using VIDEO_TOKEN_CID_PREFIX
    # Returns: path to modified PNG

def extract_token_video(image_path, receiver_kp, ipfs_gateway_base, verify_hash=True) -> (bytes, str, dict)
    # 1. Extract CID from PNG tEXt chunk
    # 2. Fetch serialized token from IPFS
    # 3. Decrypt via HVYMDataToken.extract_from_token()
    # 4. Return (video_bytes, format, metadata)

def get_user_keypair(app) -> Stellar25519KeyPair
    # Reuse from audio_tokens.py or import shared
```

### 2. `png_chunks.py` — New Video Chunk Prefix

Add a new prefix for storing the IPFS CID reference. Since a CID is small (~46 bytes for CIDv0, ~59 for CIDv1), it fits in a single tEXt chunk.

```python
# New constants
VIDEO_TOKEN_CID_PREFIX = 'video_token_cid_'

# New functions
def embed_video_token_cid(png_path, cid_string, output_path=None) -> str
    # Writes CID as a single tEXt chunk: video_token_cid_001
    return write_text_chunks(png_path, VIDEO_TOKEN_CID_PREFIX, cid_string, output_path)

def extract_video_token_cid(png_path) -> Optional[str]
    # Reads video_token_cid_* chunks, returns CID string
    return extract_combined_data(png_path, VIDEO_TOKEN_CID_PREFIX)

def has_video_data(png_path) -> (bool, str)
    # Check if PNG has video CID reference
    cid = extract_video_token_cid(png_path)
    if cid:
        return True, 'token'
    return False, None
```

### 3. `dialogs.py` — Video Embedding Dialog

New dialog `edit_video_info()` following the same pattern as `edit_audio_info()`.

- **No method selector** — video is always token-based (encrypted)
- **Video file browser** — filters for video extensions (.mp4, .webm, .mov, .avi, .mkv)
- **Recipient selector** — same as audio token: subscribers + debug key
- **Token expiry selector** — same options as audio (never / 1h / 24h / 7d / 30d / 365d)
- **"Embed Video" button** — stores params in `app.storage.user['_video_embed_params']`

```python
def edit_video_info(hash_value, on_close, process_func, choose_files):
    # Dialog with:
    # - Video file input + browse button (filtered to video extensions)
    # - Recipient selector (get_recipient_options())
    # - Token expiry selector
    # - "Embed Video" confirmation button
    # Stores to app.storage.user['_video_embed_params']

def handle_video_selection(input_field, choose_files):
    # File picker filtered to is_video_file()
```

### 4. `main.py` — Video Processing Functions

#### `process_video_embedding()` (~near process_audio_embedding)
```python
async def process_video_embedding(
    img_name, img_path, hash_value,
    video_file, receiver_public_key, expires_in=None
):
    # 1. Validate video file exists and is_video_file()
    # 2. Validate receiver_public_key is set
    # 3. Get sender keypair: get_user_keypair(app)
    # 4. Create token: create_video_token(sender_kp, receiver_pub, video_bytes, filename, expires_in)
    # 5. Upload serialized token to IPFS: ipfs_add(token_temp_file) → token_cid
    # 6. Embed CID in PNG: embed_video_token_cid(img_path, token_cid, output_path)
    # 7. Store locally: _local_store_image_pure(output_path)
    # 8. Update metadata:
    #    new_info = {
    #        "name": f"video_{img_name}",
    #        "path": output_path,
    #        "editor_url": editor_url,
    #        "has_video": True,
    #        "video_method": "token",
    #        "video_token_cid": token_cid,
    #        "video_path": video_file,
    #        "video_token_expires": token_expires,
    #        "video_token_no_expiry": expires_in is None,
    #        ...existing fields from original image...
    #    }
    # 9. Replace hash in state's hash list
    # 10. Return (new_hash, output_path)
```

#### `edit_video_info_main()` — Entry point from FAB action
```python
async def edit_video_info_main(hash_value):
    # Opens edit_video_info dialog
    # On confirm: process_video_from_storage() → process_video_embedding()
    # On success: render_gallery()
```

#### `process_video_from_storage()` — Reads dialog params
```python
async def process_video_from_storage():
    # Read from app.storage.user['_video_embed_params']
    # Convert expiry string to seconds
    # Call process_video_embedding(...)
```

### 5. `main.py` — Editor Gallery Rendering

#### `render_gallery()` updates

Add video indicator and FAB actions, parallel to audio:

```python
has_video_flag = file_info.get("has_video", False)

# Chip indicator (can have both audio AND video)
if has_video_flag:
    ui.chip("Video", icon="videocam", color="purple").props("square").classes(...)

# FAB actions for video
if has_video_flag:
    ui.fab_action("videocam", on_click=lambda h=hash_value: play_video_from_image(h)).tooltip("Play Video")
    ui.fab_action("edit", on_click=lambda h=hash_value: replace_video_dialog(h)).tooltip("Replace Video")
    ui.fab_action("delete", on_click=lambda h=hash_value: remove_video_from_image(h), color="negative").tooltip("Remove Video")
else:
    ui.fab_action("videocam", on_click=lambda h=hash_value: edit_video_info_main(h)).tooltip("Add Video")
```

#### `play_video_from_image()` — Video Player Popup

```python
async def play_video_from_image(hash_value):
    # 1. Get file_info from storage
    # 2. Get video_token_cid from metadata
    # 3. Fetch encrypted token from IPFS
    # 4. Decrypt with user's keypair (server-side)
    # 5. Write decrypted video to session temp dir
    # 6. Open NiceGUI dialog with <video> element:
    #    with ui.dialog() as video_dialog:
    #        with ui.card():
    #            ui.video(src=f'/editor/{video_filename}').classes('w-full')
    #            ui.button('Close', on_click=video_dialog.close)
    #    video_dialog.open()
```

### 6. Data Pod Schema Changes

#### `create_ninjs_data_pod_with_encrypted_tokens()` in `data_pod_audio.py`

Extend per-item schema for video:

```json
{
    "type": "video_image",
    "hasVideo": true,
    "videoMethod": "token",
    "videoTokenCid": "QmXyz...",
    "videoTokenInfo": {
        "receiverPublicKey": "xcLVR...",
        "tokenExpiry": null,
        "noExpiry": true
    }
}
```

Note: An image can have **both** audio and video. The `type` field precedence:
- `"video_image"` if has_video (video takes type priority)
- `"audio_image"` if has_audio but no video
- `"picture"` or `"aposematic_image"` otherwise

Add top-level field:
```json
{
    "video_token_images": ["hash1", "hash2"]
}
```

#### `create_ninjs_data_pod()` in `main.py`

Add video metadata fields to items:
```json
{
    "video_format": "mp4",
    "video_size": 52428800,
    "video_method": "token",
    "video_token_cid": "QmXyz..."
}
```

### 7. Subscriber Recovery — Video Decryption

#### `process_data_pod_locally()` in `data_pod_audio.py`

Add video handling alongside audio extraction:

```python
# Pre-extraction step (before image recovery):
# For video: read video_token_cid from item metadata or extract from PNG
video_token_cid = None
if item.get("hasVideo"):
    video_token_cid = item.get("videoTokenCid")
    # Or extract from PNG: extract_video_token_cid(image_path)

# After image recovery:
if video_token_cid:
    # 1. Fetch encrypted token from IPFS: ipfs_cat(video_token_cid) → serialized_token
    # 2. Decrypt: extract_video_from_token(subscriber_keys, serialized_token)
    # 3. Detect format from magic bytes or metadata filename
    # 4. Base64 encode for template:
    #    item["video"] = {
    #        "data": base64_video,
    #        "format": "mp4",
    #        "method": "token",
    #        "metadata": { "fileSize": ..., "fileHash": ..., "fileName": ... }
    #    }
```

**Important difference from audio**: Video files can be very large (100MB+). Base64-encoding the entire video into `item["video"]["data"]` and embedding it in the HTML template would be impractical. Instead:

```python
# For video: write decrypted bytes to a temp file, serve via local HTTP
video_temp_path = os.path.join(tempfile.gettempdir(), f"video_{uuid4().hex}.{video_format}")
with open(video_temp_path, 'wb') as f:
    f.write(video_bytes)

item["video"] = {
    "src": f"/editor/{os.path.basename(video_temp_path)}",  # local URL
    "format": video_format,
    "method": "token",
    "metadata": { ... }
}
```

Or if running in subscriber mode (not editor), use a temp directory served via static files.

### 8. Gallery HTML Template — Video Rendering

#### `templates/gallery.html`

Add video detection and player alongside audio:

```html
{% if item.type == 'video_image' or item.hasVideo %}
    <div class="video-container">
        <img src="{{ item.renditions[0].href }}" class="video-image" ...>

        <!-- Video Badge -->
        <div class="video-badge">
            🎬 Video{% if item.videoMethod %} ({{ item.videoMethod }}){% endif %}
        </div>

        <!-- Video Controls -->
        <div class="video-controls">
            {% if item.video and item.video.src %}
            <!-- Pre-decrypted video (served from temp file) -->
            <button class="video-play-btn"
                    onclick="openVideoPlayer('{{ item.video.src }}', '{{ item.video.format }}')">
                ▶️
            </button>
            {% elif item.video and item.video.data %}
            <!-- Base64 video (small files only) -->
            <button class="video-play-btn"
                    onclick="openVideoPlayerBase64('{{ item.video.data }}', '{{ item.video.format }}')">
                ▶️
            </button>
            {% else %}
            <button class="video-play-btn" disabled title="Video requires decryption">
                🔒
            </button>
            {% endif %}
        </div>
    </div>
{% endif %}
```

#### Video Player JavaScript

```javascript
function openVideoPlayer(videoSrc, videoFormat) {
    // Create modal overlay with <video> element
    const overlay = document.createElement('div');
    overlay.className = 'video-overlay';
    overlay.innerHTML = `
        <div class="video-modal">
            <button class="video-close-btn" onclick="this.parentElement.parentElement.remove()">✕</button>
            <video controls autoplay class="video-player">
                <source src="${videoSrc}" type="video/${videoFormat}">
                Your browser does not support video playback.
            </video>
        </div>
    `;
    document.body.appendChild(overlay);
}

function openVideoPlayerBase64(videoData, videoFormat) {
    // For small videos: create blob URL from base64
    const byteChars = atob(videoData);
    const byteArray = new Uint8Array(byteChars.length);
    for (let i = 0; i < byteChars.length; i++) {
        byteArray[i] = byteChars.charCodeAt(i);
    }
    const blob = new Blob([byteArray], { type: `video/${videoFormat}` });
    const blobUrl = URL.createObjectURL(blob);
    openVideoPlayer(blobUrl, videoFormat);
}
```

#### Video Player CSS

```css
.video-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.85);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
}

.video-modal {
    position: relative;
    max-width: 90vw;
    max-height: 90vh;
}

.video-player {
    max-width: 90vw;
    max-height: 85vh;
    border-radius: 8px;
}

.video-close-btn {
    position: absolute;
    top: -40px;
    right: 0;
    background: none;
    border: none;
    color: white;
    font-size: 24px;
    cursor: pointer;
}

.video-badge {
    position: absolute;
    top: 10px;
    left: 10px;
    background: rgba(128, 0, 128, 0.8);
    color: white;
    padding: 5px 10px;
    border-radius: 15px;
    font-size: 0.8rem;
}
```

### 9. `remove_video_from_image()` — Cleanup

```python
async def remove_video_from_image(hash_value):
    file_info = app.storage.user.get(hash_value, {})
    video_cid = file_info.get("video_token_cid")

    # 1. Remove encrypted token from IPFS
    if video_cid:
        await run.io_bound(ipfs_remove, video_cid)
        await run.io_bound(ipfs_gc)

    # 2. Re-create PNG without video CID tEXt chunk
    #    (re-write PNG excluding video_token_cid_* chunks)
    #    or: create clean copy from the source image path

    # 3. Update metadata: remove has_video, video_* fields
    # 4. _local_store_image_pure(cleaned_png)
    # 5. Update hash list + render_gallery()
```

## Implementation Order

### Phase 0: Audio Simplification — Remove Metadata Path
1. Update `edit_audio_info()` in `dialogs.py`: remove method selector, always use token, always show recipient + expiry
2. Update `process_audio_embedding()` in `main.py`: remove metadata branch, always use token path, require receiver_public_key
3. Delete `create_audio_image()` and `create_audio_visualization()` from `main.py` (dead code)
4. Delete `extract_audio_chunks_endpoint()` from `main.py` (dead code)
5. Remove `AUDIO_BASE64_PREFIX`, `embed_audio_base64()`, `extract_audio_base64()` from `png_chunks.py`; simplify `has_audio_data()` to token-only
6. Remove client-side JS extraction functions from `gallery.html`: `extractAudioFromImage()`, `extractAudioChunks()`, `detectAudioFormat()`, `arrayBufferToBase64()`, `playAudioFromImage()`, `tryBlobMethod()`
7. Simplify `gallery.html` template: token-only play button path, lock icon for undecrypted
8. Simplify `process_data_pod_locally()` in `data_pod_audio.py`: remove base64 audio branches
9. Simplify `create_ninjs_data_pod_with_encrypted_tokens()` and `create_ninjs_data_pod()`: audioMethod always "token"
10. Test: embed audio (token), debug deploy, verify playback still works end-to-end

### Phase 1: Video Token & Chunk Infrastructure
11. Create `video_tokens.py` with `create_video_token()`, `extract_video_from_token()`, `is_video_file()`, `detect_video_format()`
12. Add `VIDEO_TOKEN_CID_PREFIX`, `embed_video_token_cid()`, `extract_video_token_cid()`, `has_video_data()` to `png_chunks.py`
13. Test: create video token from a .mp4, embed CID in PNG, extract CID back

### Phase 2: Video Dialog & Embedding UI
14. Add `edit_video_info()` and `handle_video_selection()` to `dialogs.py`
15. Add `process_video_embedding()`, `edit_video_info_main()`, `process_video_from_storage()` to `main.py`
16. Test: embed video into image, verify CID stored in PNG, verify encrypted token on IPFS

### Phase 3: Video Editor Gallery Rendering
17. Update `render_gallery()` with video chip + FAB actions
18. Implement `play_video_from_image()` — decrypt + popup video player in NiceGUI dialog
19. Implement `remove_video_from_image()` and `replace_video_dialog()`
20. Test: add video to image, verify play button works, verify video player popup

### Phase 4: Video Data Pod Schema
21. Extend `create_ninjs_data_pod_with_encrypted_tokens()` with video fields (`hasVideo`, `videoMethod`, `videoTokenCid`, `videoTokenInfo`, `video_token_images`)
22. Extend `create_ninjs_data_pod()` with video metadata fields
23. Test: deploy gallery with video images, verify data pod JSON

### Phase 5: Video Subscriber Recovery
24. Extend `process_data_pod_locally()` to handle video token decryption
25. Write decrypted video to temp file, serve via static files (not base64 inline for large files)
26. Test: full round-trip — embed video → deploy → recover → play

### Phase 6: Video Gallery HTML Template
27. Add video container, badge, controls to `gallery.html`
28. Add `openVideoPlayer()`, `openVideoPlayerBase64()` JavaScript functions
29. Add video player CSS (overlay, modal, close button)
30. Test: debug deploy → browser tab renders video images → play button opens video player

### Phase 7: Edge Cases & Cleanup ✅
31. ✅ **No dual media embedding**: FAB buttons now use `if/elif/else` — audio has priority; when neither is embedded, both "Add Audio" and "Add Video" are shown; when either is embedded, only that media's play/remove actions appear.
32. ✅ CID chunk survival already handled by `reembed_media_if_needed()`.
33. ✅ `remove_img()` now unpins `video_token_cid` from IPFS before removing the image itself.
34. ✅ `persistent_save_data()` — no changes needed. Video CIDs are per-image metadata (stored in `app.storage.user[hash]`), not session config.

## Files to Modify
- **`video_tokens.py`** — NEW: Video token creation/extraction, format detection
- **`png_chunks.py`** — Remove `AUDIO_BASE64_PREFIX` + base64 functions; add `VIDEO_TOKEN_CID_PREFIX` + CID functions; simplify `has_audio_data()`
- **`dialogs.py`** — Simplify `edit_audio_info()` (remove method selector); add `edit_video_info()`, `handle_video_selection()`
- **`main.py`** — Simplify `process_audio_embedding()` (token-only); remove `create_audio_image()`, `create_audio_visualization()`, `extract_audio_chunks_endpoint()`; add `process_video_embedding()`, `edit_video_info_main()`, `play_video_from_image()`, `remove_video_from_image()`; update `render_gallery()`
- **`data_pod_audio.py`** — Simplify audio recovery (remove base64 branches); extend with video fields (consider renaming to `data_pod_media.py` in future)
- **`templates/gallery.html`** — Remove client-side audio extraction JS (~350 lines); simplify audio template to token-only; add video container, player overlay, video JavaScript

## Files NOT Changing
- **`audio_tokens.py`** — Token audio flow unchanged (it never handled the metadata path)
- **`img_edit.py`** — Image processing unaffected
- **`glasswing.spec`** — No new binary dependencies

## Risks & Considerations

### Audio Simplification
- **No backward compatibility for metadata audio**: Existing data pods with `audioMethod: "metadata"` will no longer be playable after this change. This is acceptable — no backward compatibility is required.
- **Reduced JS bundle**: Removing ~350 lines of client-side PNG parsing JavaScript from `gallery.html` simplifies the template significantly.

### Video Support
- **Large file tokens**: HVYMDataToken encrypts the entire video as a single payload. A 500MB video means a 500MB+ token on IPFS. This is fine for IPFS storage but may be slow to create/decrypt. Consider progress indication for the user.
- **Browser video format support**: Not all formats play in all browsers. MP4 (H.264) and WebM (VP8/VP9) have the best support. Consider warning the user if they select .avi or .mkv.
- **tEXt chunk survival**: Like audio, video CID tEXt chunks won't survive aposematic recovery or ImageMagick enciphering. The CID must be extracted BEFORE image recovery — same pre-extraction pattern used for audio tokens.
- **No dual media**: An image supports audio OR video, not both. The editor UI hides the "Add" button for the other media type when one is already embedded. This avoids complex dual-token interactions.
- **Token size on IPFS**: Unlike audio tokens (embedded in PNG), video tokens live on IPFS as standalone files. The encrypted token CID should be tracked so it can be removed during cleanup (`remove_video_from_image`, `remove_img`).
- **Memory during token creation**: Creating a token from a large video file means reading the entire file into memory. For very large files (1GB+), this could be an issue. Consider streaming or chunked token creation if hvym_stellar supports it in the future.
