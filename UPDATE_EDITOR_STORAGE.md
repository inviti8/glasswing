# UPDATE_EDITOR_STORAGE: Local-First Image Storage for Editor Mode

## Problem

All images — including raw originals and watermarked/processed images — are immediately uploaded to the local IPFS Kubo node via `ipfs_add()` during editing. While IPFS is configured with `no-announce=true`, content is still retrievable by anyone who knows (or guesses) the CID. This exposes unprotected creator content.

**What's at risk:**
- `raw_img_hashes` — original creator images (highest sensitivity)
- `processed_img_hashes` — watermarked images (still unencrypted originals)
- Watermark image itself (`app.storage.user["watermark"]`)

**What's already protected:**
- `aposematic_img_hashes` — scrambled via aiposematic, only recoverable with correct keys
- `enciphered_img_hashes` — encrypted via ImageMagick encipher, requires cipher_key

## Goal

Keep raw and processed images in local filesystem storage during editing. Only publish to IPFS at gallery deploy time, and only for content types that are protected (aposematic/enciphered).

## Current Architecture

### Image Pipeline
```
raw → processed (watermarked/IPTC) → aposematic OR enciphered
 ↓         ↓                              ↓
IPFS     IPFS                           IPFS
```

### How Images Enter IPFS Today
| Call Site | Function | What | Why |
|-----------|----------|------|-----|
| `choose_img()` ~1442 | `ipfs_add(img)` | Raw original | Hash used as storage key + gallery URL |
| `choose_watermark()` ~1508 | `ipfs_add(wm)` | Watermark file | Loaded from IPFS during processing |
| `process_watermarking()` ~1704 | `_ipfs_add_pure()` | Processed image | Hash used as storage key + gallery URL |
| `process_shared_iptc_metadata()` ~2078 | `_ipfs_add_pure()` | IPTC-tagged image | Hash used as storage key + gallery URL |
| `process_aposematic()` ~1808 | `_ipfs_add_pure()` | Aposematic image | Hash used as storage key + gallery URL |
| `process_enciphering()` ~1932 | `_ipfs_add_pure()` | Enciphered image | Hash used as storage key + gallery URL |
| `process_debug_deploy_gallery()` ~2113 | `_ipfs_add_pure()` | Debug aposematic | Debug deploy testing |
| `save_gallery_to_ipfs()` ~218 | `ipfs_add()` | Gallery HTML + data pod JSON | Publication |

### How Images Are Displayed
`render_gallery()` (~3024) builds IPFS gateway URLs:
```python
img_url = f"{ipfs_webui}:{ipfs_webui_port}/ipfs/{hash_value}"
ui.image(img_url)
```
This is the core reason everything goes to IPFS — the gallery UI needs a URL to render.

## Proposed Architecture

### Image Pipeline (New)
```
raw → processed (watermarked/IPTC) → aposematic OR enciphered
 ↓         ↓                              ↓
LOCAL    LOCAL                           IPFS (protected, safe to store)
```

### Key Changes

#### 1. Session-Scoped Temp Storage Directory

Create an ephemeral temp directory on app startup, destroyed on shutdown. No files persist between sessions.

```python
import tempfile, atexit, shutil

EDITOR_STORAGE_DIR = tempfile.mkdtemp(prefix="glasswing_editor_")
atexit.register(shutil.rmtree, EDITOR_STORAGE_DIR, ignore_errors=True)
```

- Raw and processed images are copied/saved here with a unique filename (UUID or content hash)
- Use NiceGUI's `app.add_static_files()` to serve them locally via HTTP for `ui.image()` rendering
- Example: `app.add_static_files('/editor', EDITOR_STORAGE_DIR)`
- Gallery renders: `ui.image(f'/editor/{filename}')` instead of IPFS URL
- Directory is automatically cleaned up on app exit — no stale files across sessions
- Each app launch starts with a clean editor workspace

#### 2. Replace IPFS Hashing with Local Identifiers for Raw/Processed

Currently IPFS CIDs serve double duty as:
1. **Storage addresses** (retrieve from IPFS gateway)
2. **Unique identifiers** (keys into `app.storage.user`)

For local storage, we need a local identifier. Options:
- **Option A: Compute CID locally without uploading** — Use `_ipfs_add_pure` equivalent that only hashes (e.g. `ipfs add --only-hash`) so existing hash-based storage keys still work, but nothing is pinned/stored on the node.
- **Option B: Use content hash (SHA-256)** — Generate our own content hash as the storage key. Simpler, no IPFS dependency for raw/processed, but requires updating all hash-key references.
- **Option C: Use UUID filenames** — Simplest approach, decouple identifier from content entirely.

**Recommended: Option A** for minimal disruption — the hash-key pattern is deeply embedded in `app.storage.user[hash_value]` throughout the codebase. Kubo supports `ipfs add --only-hash` which computes the CID without storing content.

#### 3. Changes by Function

##### `choose_img()` (~1442)
- **Current:** `ipfs_add(img)` → uploads to IPFS, returns hash
- **New:** Copy file to session temp dir, compute hash locally (no upload), store metadata with local path
- The original file path is preserved in metadata — the temp copy is just for serving via HTTP
- Watermark image (`choose_watermark()`) also stored locally — already loaded from local path during processing anyway

##### `process_watermarking()` (~1704)
- **Current:** `_ipfs_add_pure(processed_img_path)` → uploads processed image to IPFS
- **New:** Save processed image to `EDITOR_STORAGE_DIR`, compute hash locally, store metadata
- Note: watermark is currently loaded from IPFS via `_ipfs_load_to_temp_file_pure()` — change to load from local storage

##### `process_shared_iptc_metadata()` (~2078)
- **Current:** `_ipfs_add_pure()` → uploads IPTC-tagged image to IPFS
- **New:** Save to `EDITOR_STORAGE_DIR`, compute hash locally

##### `process_aposematic()` (~1808)
- **Current:** `_ipfs_add_pure()` → uploads aposematic image to IPFS
- **Change:** Keep as-is — aposematic images are protected. IPFS storage is acceptable.

##### `process_enciphering()` (~1932)
- **Current:** `_ipfs_add_pure()` → uploads enciphered image to IPFS
- **Change:** Keep as-is — enciphered images are protected. IPFS storage is acceptable.

##### `render_gallery()` (~3024)
- **Current:** Always renders `http://localhost:8081/ipfs/{hash}`
- **New:** Check image state:
  - `raw`, `processed` → use local static URL: `/editor/{filename}`
  - `aposematic`, `enciphered` → use IPFS URL (as today)
- The metadata dict `app.storage.user[hash_value]` should include a `"local_path"` or `"editor_url"` field for local images

##### `remove_img()` (~1471)
- **Current:** `ipfs_remove(hash_value)` + `ipfs_gc()`
- **New:** For raw/processed, delete from `EDITOR_STORAGE_DIR`. For aposematic/enciphered, keep IPFS removal.

##### `copy_img()` and other utilities
- Any function that copies/references images by IPFS hash needs to check whether the image is local or on IPFS

#### 4. Deploy/Publish Flow

The publish flow (`create_ninjs_data_pod`, `deploy_gallery_images`, `save_gallery_to_ipfs`) is the point where protected images go to IPFS.

- `create_ninjs_data_pod()` (~3316): Currently builds IPFS URLs for rendition hrefs. At publish time, aposematic/enciphered images are already on IPFS. Raw/processed should NOT be in a published data pod (they're unprotected). Add a guard:
  - If `content_type` is `aposematic` or `enciphered`, proceed with IPFS hrefs
  - If `content_type` is `original` (raw/processed), either block or warn

- `deploy_gallery_images()` (~3646): Reads from local `path` field anyway (not from IPFS), so no change needed — it uploads directly from the file on disk.

#### 5. Watermark Storage

The watermark image (`choose_watermark()` ~1508) is currently stored on IPFS and loaded back via `_ipfs_load_to_temp_file_pure()` during processing.

- **New:** Store watermark in session temp dir alongside images
- Store the local path in `app.storage.user["watermark_path"]` (new field)
- In `process_watermarking()`, load watermark from local path instead of IPFS
- Keep `app.storage.user["watermark"]` for backward compat or migrate to path-based
- Note: watermark is selected per session anyway — user re-selects on each launch

#### 6. Session Lifecycle

Images are **ephemeral** — scoped to the current app session only.

- On **startup**: `tempfile.mkdtemp()` creates a fresh temp dir, `app.add_static_files()` serves it
- On **shutdown**: `atexit` handler calls `shutil.rmtree()` to wipe the temp dir
- **No persistence** of raw/processed images across sessions — user re-imports originals each session
- `app.storage.user` hash lists (`raw_img_hashes`, `processed_img_hashes`) should be cleared on startup since the referenced files no longer exist
- `persistent_save_data()` does NOT need to save raw/processed hash lists — they're session-only
- Aposematic/enciphered images on IPFS DO persist (they're published content)

#### 7. Startup Cleanup

On app startup, clear stale editor state from previous sessions:

```python
# Clear session-only image lists (files no longer exist)
app.storage.user["raw_img_hashes"] = []
app.storage.user["processed_img_hashes"] = []
# Aposematic/enciphered lists are kept (IPFS-backed, persistent)
```

This replaces the old approach of validating stale metadata. No reconciliation needed — just start clean.

## Implementation Order

### Phase 1: Session Storage Infrastructure
1. Create session temp dir via `tempfile.mkdtemp()` at app startup with `atexit` cleanup
2. Register with `app.add_static_files('/editor', EDITOR_STORAGE_DIR)`
3. Create `local_store_image(file_path)` — copies file to session dir, computes hash, returns (hash, editor_url)
4. Create `local_remove_image(hash_value)` — deletes from session dir
5. Add `"editor_url"` field to image metadata dict
6. Clear `raw_img_hashes` and `processed_img_hashes` on startup (stale from previous session)

### Phase 2: Raw Image Flow
7. Update `choose_img()` to use `local_store_image()` instead of `ipfs_add()`
8. Update `render_gallery()` to use `editor_url` for raw/processed states
9. Update `remove_img()` to use `local_remove_image()` for raw/processed
10. Test: add raw images, verify they display, verify NOT on IPFS

### Phase 3: Processed Image Flow
11. Update `process_watermarking()` to use `local_store_image()`
12. Update watermark storage (`choose_watermark()`) to session dir
13. Update `process_shared_iptc_metadata()` to use `local_store_image()`
14. Test: watermark processing, verify processed images display locally

### Phase 4: Protected Image Flow (Verify Unchanged)
15. Verify `process_aposematic()` still uploads to IPFS (no change)
16. Verify `process_enciphering()` still uploads to IPFS (no change)
17. Test: full pipeline raw → processed → aposematic, verify aposematic on IPFS

### Phase 5: Publish Guard
18. Add content type guard in `create_ninjs_data_pod()` — warn/block raw content
19. Verify `deploy_gallery_images()` still works (reads from local path)
20. Test: deploy flow end-to-end

### Phase 6: Cleanup
21. Remove IPFS upload calls from raw/processed paths
22. Update `ipfs_gc()` usage — only relevant for protected images now
23. Remove raw/processed hash lists from `persistent_save_data()` (session-only, no need to persist)

## Files to Modify
- **`main.py`** — Primary changes: `choose_img`, `process_watermarking`, `process_shared_iptc_metadata`, `render_gallery`, `remove_img`, `choose_watermark`, `create_ninjs_data_pod`
- **`dialogs.py`** — No changes expected
- **`data_pod_audio.py`** — Subscriber recovery reads from IPFS (published content), no change needed
- **`img_edit.py`** — Image processing functions, no change (they work on file paths)

## Risks & Considerations

- **Hash-based storage keys:** If using Option A (local CID computation), the `ipfs add --only-hash` endpoint still requires the IPFS daemon. Consider a pure Python CID computation as a fallback.
- **Gallery HTML export:** `save_gallery_to_ipfs()` generates HTML with image URLs. For local images, these URLs won't work outside the app. This is acceptable since gallery HTML is only meaningful for published (protected) content.
- **Audio re-embedding:** Audio embed/extract works on file paths, not IPFS — no impact.
- **Debug flow:** `process_debug_deploy_gallery()` uploads to IPFS — this should be fine since it only operates on aposematic images.
