# Subscriber Flow — Design Document

## Overview

Subscribers receive encrypted content from publishers via Pintheon nodes. The subscriber's Andromica **App Key** (Stellar secret) serves as their identity — their public key is the directory name on the publisher's Pintheon node.

## Key Insight

The subscriber does NOT need to enter a private key. Andromica already knows the App Key (`stellar_secret`), from which the Stellar 25519 public key is derived. This public key is what the publisher used as the IPNS directory name when deploying content. The subscriber only needs to provide the **Pintheon node address**.

## Current State

- **Publisher flow** (working): Creates data pod, uploads images + data pod to Pintheon, directory named by subscriber's public key
- **Local debug flow** (working): Creates and decrypts data pod locally using debug keys, renders in browser tab
- **Subscriber flow** (missing): No mechanism for a subscriber to connect to a Pintheon node, discover their content, download, decrypt, and view it

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
    "node_url": "https://local.pintheon.com:9999",
    "node_gateway": "https://local.pintheon.com:9998",  # Public gateway port
    "label": "My Publisher",                             # User-friendly name
    "added": "2026-03-30T12:00:00",                     # When subscription was added
    "last_fetched": None,                                # Last successful fetch timestamp
    "data_pod_hash": None,                               # CID of last fetched data pod
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

## Access Token Consideration

The subscriber needs a Pintheon **access token** to query the API (`api_get_directory_ipns`, etc.). Two options:

1. **Token exchange**: Publisher generates an access token for the subscriber and shares it out-of-band (current mechanism via Pintheon admin)
2. **Public gateway only**: Skip the API entirely and resolve content via the public IPFS gateway (port 9998) — the IPNS directory and files are publicly accessible if the subscriber knows the IPNS hash

Option 2 is simpler for MVP: the subscriber just needs the node's **public gateway URL** and their IPNS hash. No access token required for reading public IPFS/IPNS content. The access token is only needed for write operations (upload, create directory).

However, this means the subscriber needs the IPNS hash, not just the node URL. The publisher would share the IPNS hash after deployment (shown in the deployment summary dialog we added).

### Revised Subscription Input (Option 2 — MVP)

The subscriber enters:
- **Pintheon Gateway URL** (e.g., `https://local.pintheon.com:9998`)
- **IPNS Hash** (e.g., `k51qzi5uqu5dm9cmfob3ky72uluj1u0wvcpenzwvswxv0f06c8az3kfpsqulm2`)

Andromica resolves `{gateway}/ipns/{ipns_hash}/` to list files and download the data pod.

### Future Enhancement (Option 1 — Full API)

With an access token, the subscriber can:
- Query `api_get_directory_ipns` using their public key as directory name
- No need to know the IPNS hash — the node resolves it from the directory name
- Enables auto-discovery: subscriber adds a node + token, Andromica finds their content automatically

## Implementation Steps

1. **Subscription storage**: Define subscription data structure, persist in data.json
2. **Browser Settings UI**: Add subscription management (add/remove/list)
3. **Content fetching**: Download data pod and images from Pintheon gateway via IPNS
4. **Decryption**: Wire up `process_data_pod_locally()` with subscriber's App Key
5. **Rendering**: Display in browser iframe using existing `render_gallery_html()`
6. **Refresh/polling**: Manual refresh button, optional auto-refresh interval

## Dependencies

- `process_data_pod_locally()` in `data_pod_audio.py` — already handles decryption
- `render_gallery_html()` in `main.py` — already handles HTML generation
- Browser iframe — already set up
- Subscription list in storage — field exists but unused

## Open Questions

- Should subscriptions auto-refresh when the BROWSER tab is opened?
- Should there be a notification when new content is available?
- How does the publisher share the IPNS hash with the subscriber? (Currently shown in deployment dialog — could also be a shareable link)
- Should the subscriber be able to browse multiple subscriptions, or one at a time?
