# Andromica Audio Embedding Bug Report

## Issue Summary

**Problem:** When audio is added to an image using the metadata flow, the `has_audio` parameter is properly assigned and the UI chip with a music icon displays correctly. However, this doesn't happen for the shared flow, indicating the `has_audio` parameter is being incorrectly assigned or lost somewhere in the shared flow.

## System Architecture Understanding

Based on `/docs/ARCHITECTURE.md`, Andromica has two distinct modes:

### Creator Flow (Image Mode)
- **Local Editing:** Import images → Process/Watermark → Add metadata → Create data pods → Deploy to IPFS
- **Storage:** Images stored in local IPFS repository with metadata in `app.storage.user[hash]`
- **Rendering:** `render_gallery()` displays images from local IPFS based on `img_states`

### Consumer Flow (Browser Mode)  
- **Data Pod Consumption:** Subscribe to channels → Fetch data pods → Decrypt content → Render galleries
- **Storage:** Processed data pods rendered via Jinja2 templates
- **Rendering:** HTML templates display content from data pods, not local IPFS

## Scope Analysis

The issue is specifically in **Image Mode (Creator Flow)** where `render_gallery()` is used to display images for editing. The user mentions:

1. ✅ **Metadata flow works correctly:** `has_audio` parameter assigned, UI chip shows music icon
2. ❌ **Shared flow broken:** `has_audio` parameter incorrectly assigned or lost

## Investigation Findings

### Audio Embedding Functions
- `edit_audio_info_main()` → `process_audio_from_storage()` → `process_audio_embedding()`
- `process_audio_embedding()` creates new audio image and sets `has_audio: True`

### Processing Functions That Preserve Audio Metadata
- ✅ `process_aposematic()` (lines 1614-1620): Preserves all audio fields
- ✅ `process_enciphering()` (lines 1697-1703): Preserves all audio fields  
- ✅ `process_shared_iptc_metadata()` (lines 1564-1574): Preserves all audio fields
- ❌ `process_audio_embedding()` (lines 4711-4717): **MISSING audio metadata preservation**

### Root Cause Identified

In `process_audio_embedding()` function in `main.py:4711-4717`:

```python
app.storage.user[new_hash] = {
    "name": f"audio_{img_name}",
    "path": output_path,
    "has_audio": True,           # ✅ CORRECTLY SET
    "audio_method": audio_method,
    "image_type": old_info.get("image_type", "raw"),
    # ❌ MISSING FIELDS:
    # "audio_path": old_info.get("audio_path"),
    # "audio_format": old_info.get("audio_format"), 
    # "audio_duration": old_info.get("audio_duration"),
    # "audio_size": old_info.get("audio_size"),
}
```

**Problem:** When creating audio images, only `has_audio` is preserved, but the detailed audio metadata fields (`audio_path`, `audio_format`, `audio_duration`, `audio_size`) are lost.

## Impact Analysis

### Raw Image Import Issue (PRIMARY)
🔍 **CRITICAL:** `choose_img()` function (lines 1247-1249) imports raw images but **NEVER sets any metadata**:

```python
ipfs_hash = ipfs_add(img)
app.storage.user.get("raw_img_hashes", []).append(ipfs_hash)
# ❌ MISSING: app.storage.user[ipfs_hash] metadata initialization
```

**Result:** Raw images have **no `has_audio` or any audio metadata** in storage, so they never show music chips.

### Audio Embedding Issue (SECONDARY)
🔍 **CONFIRMED:** `process_audio_embedding()` function (lines 4711-4717) preserves `has_audio: True` but **MISSING audio metadata fields**:

```python
app.storage.user[new_hash] = {
    "has_audio": True,           # ✅ CORRECTLY SET
    # ❌ MISSING: audio_path, audio_format, audio_duration, audio_size
}
```

**Impact:** Breaks downstream processing (aposematic/enciphering) that expects complete audio metadata.

### Combined Failure Scenario
1. User imports raw image → **No metadata stored** → No music chip shown
2. User adds audio → `has_audio` set but **metadata incomplete** → Shared flow breaks
3. Both scenarios prevent proper music icon display in shared workflows

## Root Cause Analysis

### Issue 1: Raw Image Import
- `choose_img()` function fails to initialize metadata for imported images
- Raw images need audio detection during import or proper metadata initialization

### Issue 2: Audio Embedding  
- `process_audio_embedding()` incomplete metadata preservation
- Missing fields affect downstream processing functions

## Fix Requirements

### Fix 1: Raw Image Metadata Initialization
Update `choose_img()` to initialize basic metadata structure:

```python
app.storage.user[ipfs_hash] = {
    "name": os.path.basename(img),
    "path": img,
    "has_audio": False,  # Default, will be updated if audio detected
    "image_type": "raw",
    # Initialize other audio fields to None
    "audio_path": None,
    "audio_format": None, 
    "audio_duration": None,
    "audio_size": None,
    "audio_method": None,
}
```

### Fix 2: Complete Audio Metadata Preservation
Update `process_audio_embedding()` to preserve all audio metadata fields:

```python
app.storage.user[new_hash] = {
    "name": f"audio_{img_name}",
    "path": output_path,
    "has_audio": True,
    "audio_method": audio_method,
    "audio_path": old_info.get("audio_path"),      # ✅ PRESERVE
    "audio_format": old_info.get("audio_format"),    # ✅ PRESERVE
    "audio_duration": old_info.get("audio_duration"),  # ✅ PRESERVE
    "audio_size": old_info.get("audio_size"),        # ✅ PRESERVE
    "image_type": old_info.get("image_type", "raw"),
}
```

## Files Affected

- `main.py` - `choose_img()` function (lines 1247-1249)
- `main.py` - `process_audio_embedding()` function (lines 4711-4717)

## Testing Strategy

1. Import raw image → Verify metadata structure created in storage
2. Add audio to raw image → Verify complete audio metadata preserved  
3. Process through aposematic/enciphering → Verify shared flow works correctly
4. Confirm music icon displays in all scenarios

```python
app.storage.user[new_hash] = {
    "name": f"audio_{img_name}",
    "path": output_path,
    "has_audio": True,
    "audio_method": audio_method,
    "audio_path": old_info.get("audio_path"),      # PRESERVE
    "audio_format": old_info.get("audio_format"),    # PRESERVE
    "audio_duration": old_info.get("audio_duration"),  # PRESERVE  
    "audio_size": old_info.get("audio_size"),        # PRESERVE
    "image_type": old_info.get("image_type", "raw"),
}
```

This maintains consistency with other processing functions and ensures audio metadata is available throughout all flows in the Image Mode editing workflow.

## Files Affected

- `main.py` - `process_audio_embedding()` function (lines 4711-4717)

## Testing Strategy

1. Add audio to image using metadata flow
2. Verify `has_audio` and all audio metadata fields are set
3. Process through aposematic/enciphering to test shared flow
4. Verify UI music chip displays correctly in all scenarios