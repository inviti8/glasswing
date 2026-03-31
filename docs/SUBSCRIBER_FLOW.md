# Subscriber Flow — Design Document

## Overview

Subscribers receive encrypted content from publishers via Pintheon nodes. The subscriber's Andromica **App Key** (Stellar secret) serves as their identity — their public key is the directory name on the publisher's Pintheon node.

## Key Insight

The subscriber does NOT need to enter a private key. Andromica already knows the App Key (`stellar_secret`), from which the Stellar 25519 public key is derived. This public key is what the publisher used as the IPNS directory name when deploying content. The subscriber only needs to provide the **Pintheon node address**.

## Current State

- **Publisher flow** (working): Creates data pod, uploads images + data pod to Pintheon, directory named by subscriber's public key
- **Local debug flow** (working): Creates and decrypts data pod locally using debug keys, renders in browser tab
- **Subscriber flow** (scaffolded, incomplete): UI and handler skeleton exists but needs wiring

### Existing Subscriber Skeleton

**Browser mode FAB buttons** (main.py ~line 4660):
- "View Subscriptions" → `view_subscriptions_dialog()` — lists saved subscriptions with fetch/remove
- "Add Subscription" → `add_subscription_dialog()` — name, URL, IPNS hash inputs
- "Select Channel" → `select_channel_dialog()` — pick subscription, load channels, select one to render

**Dialog implementations** (dialogs.py lines 649-796):
- `add_subscription_dialog(on_save)` — collects name, node URL, IPNS hash
- `view_subscriptions_dialog(fetch_fn, remove_fn)` — lists subs with sync/delete buttons
- `select_channel_dialog(on_select, fetch_channels_fn)` — subscription dropdown + channel list

**Handler functions** (main.py):
- `add_subscription(name, url, ipns_hash)` (line 2753) — saves to storage
- `remove_subscription(name)` (line 2774) — removes from storage
- `fetch_subscription_content(name)` (line 2788) — fetches IPNS content (basic, needs work)
- `fetch_subscription_channels(name)` (line 2869) — parses directory for data pods (basic, needs work)
- `select_channel(name, channel_info)` (line 3162) — renders data pod in browser (partially implemented)

### What's Missing

1. **Add Subscription dialog** still asks for IPNS hash — should be auto-derived from App Key
2. **fetch_subscription_content** does a basic GET but doesn't download individual files or find the data pod JSON
3. **fetch_subscription_channels** parses response but doesn't handle IPFS directory listings properly
4. **select_channel** calls `decode_protected_images` which may not exist; should use `process_data_pod_locally`
5. **No SSL verify=False** on subscription requests (Pintheon uses self-signed certs)
6. Image references in data pod use creator's local gateway URL — need to be resolved via the subscription's node gateway

## Subscription Flow

### Step 1: Add Subscription

**UI**: Browser Settings panel (currently a placeholder)

The subscriber enters:
- **Pintheon Node URL** (e.g., `https://local.pintheon.com:9999`)

That's it. Andromica derives the rest:
- `stellar_secret` → `Keypair` → `Stellar25519KeyPair` → `public_key` (= directory name on Pintheon)
- IPNS directory URL: `{node_url}/ipns/{ipns_key_for_directory}/`

The subscription is saved to `app.storage.user["subscriptions"]` (already exists as an empty list).

### Step 2: Resolve Content

When the subscriber opens the BROWSER tab or triggers a refresh:

1. **Query Pintheon** for the IPNS directory:
   - `POST {node_url}/api_get_directory_ipns` with `access_token` and `directory={public_key}`
   - Returns the IPNS hash for the directory
   - Alternatively, list files via the IPFS gateway: `{node_gateway}/ipns/{ipns_hash}/`

2. **Find the data pod** in the directory:
   - Look for `ninjs_data_pod_*.json` file in the listing
   - Download it via IPFS gateway: `{gateway}/ipfs/{data_pod_cid}`

3. **Download images** referenced in the data pod:
   - Each item's `renditions[0].href` contains an IPFS CID URL
   - Download via the Pintheon node's gateway (port 9998)

### Step 3: Decrypt & Render

Use the existing `process_data_pod_locally()` function:
- **Creator public key**: from `data_pod["creator_public_key"]`
- **Subscriber secret**: from `app.storage.user["stellar_secret"]` (the App Key)
- ECDH shared secret is derived, used to decrypt aposematic images and media tokens

Then render with `render_gallery_html()` and display in the browser iframe.

## Data Flow

```
Subscriber's Andromica
    │
    ├── Knows: stellar_secret (App Key)
    ├── Derives: public_key (= Pintheon directory name)
    │
    ▼
Pintheon Node (publisher's)
    │
    ├── IPNS directory: /{public_key}/
    │   ├── aposematic_image_1.png
    │   ├── aposematic_image_2.png
    │   └── ninjs_data_pod_aposematic_20260330.json
    │
    ▼
Download & Decrypt
    │
    ├── data_pod["creator_public_key"] + subscriber's stellar_secret
    │   → ECDH shared secret → cipher key
    │
    ├── Recover aposematic images (using Stellar keypair + op_string)
    ├── Decrypt audio/video/markdown tokens
    │
    ▼
Render in Browser Tab
```

## Subscription Data Structure

```python
# Stored in app.storage.user["subscriptions"]
subscription = {
    "url": "https://mypublisher.pintheon.com",  # Single public address
    "label": "My Publisher",                     # User-friendly name
    "ipns_hash": "k51qzi5uqu5d...",             # IPNS hash (from publisher)
    "added": "2026-03-30T12:00:00",
    "last_fetched": None,
    "data_pod_hash": None,
}
```

## UI Changes

### Browser Settings Panel

Replace the placeholder with:

```
┌─────────────────────────────────────────┐
│ Subscriptions                           │
│                                         │
│ [Node URL input          ] [Add]        │
│                                         │
│ ┌─ My Publisher ───────────────────┐    │
│ │ https://local.pintheon.com:9999  │    │
│ │ Last fetched: 2026-03-30 12:00   │    │
│ │ [Refresh]  [Remove]              │    │
│ └──────────────────────────────────┘    │
│                                         │
│ ┌─ Gallery Node ───────────────────┐    │
│ │ https://gallery.pintheon.com:9999│    │
│ │ Last fetched: never              │    │
│ │ [Refresh]  [Remove]              │    │
│ └──────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

### Browser Tab Behavior

When switching to BROWSER tab:
- If a subscription has content, show the most recently fetched gallery
- A dropdown or selector lets the subscriber switch between subscriptions
- "Refresh" re-fetches from the Pintheon node

## Content Access Model

No access token is required for subscribers. Pintheon nodes are self-sovereign web
services that expose IPFS, IPNS, and homepage content via a Warren tunnel to the
open internet (see `/hvym_tunnler`). The public gateway (port 9998) serves content
to anyone who requests it.

**Security is at the content layer, not the transport layer.** All images are
aposematic-encrypted and can only be decrypted by the intended recipient (using
ECDH with the creator's public key + subscriber's private key) or the creator
themselves. The content is safe to serve publicly — without the subscriber's
Stellar 25519 private key, it's just scrambled pixels.

### Subscription Input

The subscriber enters:
- **Pintheon Node URL** (e.g., `https://mypublisher.pintheon.com`)
- **IPNS Hash** (shared by publisher from deployment summary dialog)

The IPNS hash is required because IPNS key IDs are random (generated by IPFS
when `ipfs key gen` is called) — they cannot be derived from the subscriber's
public key. The IPNS key **name** is deterministic (derived from the public key),
but the key **ID** (the `k51q...` hash) is not.

Future: Pintheon could expose a public endpoint to resolve directory name → IPNS
hash, eliminating the need to share it manually.

## Implementation Status

### Phase 1: Add Subscription dialog — DONE
- Subscriber enters: label, node URL, and IPNS hash (from publisher)
- Subscription saved to storage and persisted in data.json

### Phase 2: Content fetching — DONE
- `fetch_subscription_content()` fetches IPNS directory listing from public gateway
- Parses HTML directory listing for data pod JSON and image links
- Downloads data pod JSON and rewrites image hrefs to subscription node gateway
- SSL verification disabled for self-signed Pintheon certs

### Phase 3: Decryption — DONE
- `select_channel()` uses `process_data_pod_locally()` with subscriber's App Key
- Images embedded as base64 for reliable display
- ECDH shared key derived from subscriber's Stellar secret + creator's public key

### Phase 4: Rendering — DONE
- Uses `render_gallery_html()` for consistent template rendering
- Renders immediately when already on BROWSER tab
- Falls back to pending_browser_html if on another tab

### Phase 5: Polish — DONE
- Browser Settings panel shows subscription list with labels and last-fetched times
- Comprehensive logging with `[SUBSCRIPTION]` prefix for debugging

### Future Work
- Public IPNS hash discovery endpoint on Pintheon (eliminate manual hash sharing)
- Auto-refresh subscriptions when BROWSER tab is opened
- Loading indicator during fetch/decrypt
- Multiple subscription content switching

## Dependencies

- `process_data_pod_locally()` in `data_pod_audio.py` — already handles decryption
- `render_gallery_html()` in `main.py` — already handles HTML generation
- Browser iframe — already set up
- Subscription list in storage — field exists but unused

## Open Questions

- Should subscriptions auto-refresh when the BROWSER tab is opened?
- Should there be a notification when new content is available?
- Should the subscriber be able to browse multiple subscriptions, or one at a time?
