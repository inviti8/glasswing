# HVYM Network Name Service — Design Document

## Overview

A two-layer resolution system for the HVYM network:

1. **Soroban Name Registry** — maps human-readable names to Pintheon node
   tunnel endpoints. Shared schema for both **Andromica** (first production
   consumer) and **Lepus Browser** (future Firefox fork).

2. **Pintheon stellar.toml** — maps subscriber public keys to IPNS hashes.
   Served by each node on its public gateway. Free, scales to millions of
   subscribers without on-chain costs.

## Problem Statement

Currently, subscribing to a Pintheon node in Andromica requires:
1. The node URL (e.g., `https://mypublisher.pintheon.com`)
2. The IPNS hash (e.g., `k51qzi5uqu5d...`) — shared manually by the publisher

The IPNS hash is non-deterministic (random per `ipfs key gen`) and opaque
to users. This is a UX barrier, especially for crypto-averse users.

## Solution: Two-Layer Resolution

```
Layer 1: Name → Node (Soroban, on-chain)
  "alice" → tunnel_id + tunnel_relay + services

Layer 2: Subscriber → IPNS (Pintheon stellar.toml, off-chain)
  subscriber_public_key → ipns_hash

Combined flow:
  Subscriber types "alice" in Andromica
    → Soroban resolves "alice" to Pintheon node endpoint
    → Pintheon's stellar.toml resolves subscriber's key to IPNS hash
    → Fetch IPNS directory → list datapods → select → decrypt → render
```

### Why Two Layers?

| Concern | Layer 1 (Soroban) | Layer 2 (stellar.toml) |
|---------|-------------------|----------------------|
| Data | Name → node endpoint | Subscriber key → IPNS hash |
| Cost | ~$0.005 per registration | Free (served by node) |
| Scale | One record per creator | Millions of subscribers |
| Update frequency | Rarely (node changes) | Often (new deployments) |
| Trust model | Ledger consensus | Node operator |

Putting per-subscriber IPNS mappings on-chain would cost $3,000+ for a
creator with 1M subscribers per content update. The stellar.toml approach
is free and leverages an existing Stellar protocol that Pintheon already
implements.

## Layer 1: Soroban Name Registry

### NameRecord (On-Chain)

```rust
#[contracttype]
pub struct NameRecord {
    // Identity
    pub name: String,               // "alice" — unique, lowercase
    pub owner: Address,             // Stellar address of the name owner

    // Tunnel Resolution
    pub tunnel_id: Address,         // Stellar address for tunnel authentication
    pub tunnel_relay: String,       // Relay server: "tunnel.hvym.link"

    // Service Routing (for Lepus @ addresses)
    pub services: Map<Symbol, ServiceEndpoint>,

    // Metadata
    pub ttl: u32,                   // Cache TTL in seconds (default: 300)
    pub registered_at: u64,         // Ledger timestamp
    pub expires_at: u64,            // Expiration (annual renewal)
    pub member_id: Address,         // Cooperative member credential
    pub status: NameStatus,         // Active, Expired, Suspended, Transferring
}

#[contracttype]
pub struct ServiceEndpoint {
    pub path: String,               // URL path on the Pintheon node
    pub description: String,        // Human-readable description
}
```

### Contract Interface

```rust
pub trait HvymNameRegistry {
    // === Write (Soroban tx fee) ===
    fn register(env: Env, name: String, tunnel_id: Address,
                tunnel_relay: String, services: Map<Symbol, ServiceEndpoint>)
        -> Result<NameRecord, RegistryError>;
    fn renew(env: Env, name: String) -> Result<NameRecord, RegistryError>;
    fn transfer(env: Env, name: String, new_owner: Address)
        -> Result<NameRecord, RegistryError>;
    fn update(env: Env, name: String, tunnel_id: Option<Address>,
              tunnel_relay: Option<String>,
              services: Option<Map<Symbol, ServiceEndpoint>>)
        -> Result<NameRecord, RegistryError>;

    // === Read (free via RPC) ===
    fn resolve(env: Env, name: String) -> Option<NameRecord>;
    fn available(env: Env, name: String) -> bool;
}
```

### Name Rules

- Characters: `a-z`, `0-9`, `-` (lowercase only)
- Length: 3-63 characters
- No leading/trailing hyphens
- Cooperative membership required
- Annual renewal

### How Names Map for Andromica vs Lepus

| Field | Andromica Use | Lepus Browser Use |
|-------|--------------|-------------------|
| `name` | Subscription lookup | URL bar: `alice@gallery` |
| `tunnel_id` | Not used directly (uses public gateway) | Warren tunnel auth |
| `tunnel_relay` | Derive public gateway URL | Tunnel relay connection |
| `services` | Not used (content is IPNS-based) | Path routing for @ services |

For Andromica, the name resolves to the node's public gateway URL. For
Lepus, it resolves to a full tunnel endpoint with service routing.

## Layer 2: Pintheon stellar.toml Subscriber Resolution

### Extending stellar.toml

Pintheon nodes already serve `/.well-known/stellar.toml` on the public
gateway (port 9998). This is a standard Stellar protocol for domain
verification. We extend it with a `SUBSCRIBER_DIRECTORIES` section:

```toml
VERSION = "2.0.0"
NETWORK_PASSPHRASE = "Test SDF Network ; September 2015"

[DOCUMENTATION]
ORG_NAME = "Alice's Gallery"
ORG_URL = "https://alice.pintheon.com"

ACCOUNTS = ["GALICE123..."]

[SUBSCRIBER_DIRECTORIES]
# Maps subscriber Stellar 25519 public keys to IPNS directory hashes
"Lo05eOX99L6D0D99jEhZ5-399-4WoInd4DZEZ-13X1E=" = "k51qzi5uqu5dizy5yl4fle50vzyparjgrcupo1mclslh0qexv69bmmyeb4h74z"
"cdf2VgO63i7wix7h5Z60hf5-IyaMnAagvJGhH2gRcn4=" = "k51qzi5uqu5dk25an4tq8q0uq53d5xk1g9lq0qbraf9oby6n4sdha462h73p8z"
```

### Why stellar.toml?

1. **Standard Stellar protocol** — already served by Pintheon, already
   has CORS headers (`Access-Control-Allow-Origin: *`)
2. **Free** — no blockchain transactions, just a file on the node
3. **Scales infinitely** — adding a subscriber is appending a line
4. **Auto-updated** — Pintheon updates it when deploying content
5. **Publicly accessible** — no auth needed to read
6. **Cacheable** — standard HTTP caching applies

### Alternative: Dedicated Endpoint

For nodes with very large subscriber lists, a TOML file becomes unwieldy.
Pintheon could also expose a dedicated public endpoint:

```
GET /api/public/resolve_subscriber?pub=Lo05eOX99L6D0D99...
→ {"ipns_hash": "k51qzi5uqu5dizy5...", "name": "Lo05eOX99..."}
```

This would be added to the nginx public port (9998) route list and
wouldn't require authentication. For MVP, stellar.toml is sufficient.

## Multiple Datapods Per Subscriber

### The Problem

A creator publishes multiple works — a book, an album, a graphic novel.
Each is a separate datapod. The subscriber's IPNS directory may contain:

```
/Lo05eOX99.../
  ├── ninjs_data_pod_aposematic_20260330_book.json      (Book)
  ├── ninjs_data_pod_aposematic_20260401_album.json     (Album)
  ├── ninjs_data_pod_aposematic_20260405_novel.json     (Graphic Novel)
  ├── aposematic_book_cover.png
  ├── aposematic_album_art.png
  ├── aposematic_novel_page1.png
  └── ...
```

### Current Behavior (Broken)

`fetch_subscription_content` currently grabs only the last `.json` file
and `fetch_subscription_channels` returns it as a single channel. Multiple
datapods are ignored.

### Required Behavior

Each datapod should appear as a separate selectable item in the channel
list. The Select Channel dialog should show:

```
┌────────────────────────────────────┐
│ Select Channel                     │
│                                    │
│ Subscription: [Alice's Gallery ▼]  │
│                                    │
│ ┌── "Evolve" Book ────────────┐   │
│ │ 12 images, 2 audio tracks   │   │
│ │ Published: 2026-03-30       │   │
│ │                    [Select]  │   │
│ └─────────────────────────────┘   │
│                                    │
│ ┌── "Predators" Album ────────┐   │
│ │ 8 images, 8 audio tracks    │   │
│ │ Published: 2026-04-01       │   │
│ │                    [Select]  │   │
│ └─────────────────────────────┘   │
│                                    │
│                        [Cancel]    │
└────────────────────────────────────┘
```

### Implementation

`fetch_subscription_content` downloads ALL `.json` files from the IPNS
directory. `fetch_subscription_channels` returns one channel per datapod.
Each channel carries its own data pod, and `select_channel` processes
and renders the selected one independently.

## Resolution Flow

### Andromica Subscriber Flow

```
Subscriber adds subscription:
    Name: "alice"
        │
        ▼
Step 1: Resolve name (Soroban RPC, free)
    record = HvymNameRegistry.resolve("alice")
    → tunnel_relay: "tunnel.hvym.link"
    → node public gateway derived from tunnel_relay
        │
        ▼
Step 2: Fetch stellar.toml from node (HTTP GET, free)
    GET https://alice.tunnel.hvym.link/.well-known/stellar.toml
    → Parse [SUBSCRIBER_DIRECTORIES]
    → Find subscriber's public key → IPNS hash
        │
        ▼
Step 3: Fetch IPNS directory listing
    GET https://alice.tunnel.hvym.link/ipns/{ipns_hash}/
    → Parse directory → find ALL datapod .json files
        │
        ▼
Step 4: Present datapods as selectable channels
    → User selects "Evolve Book"
        │
        ▼
Step 5: Download selected datapod + referenced images
    → process_data_pod_locally() with subscriber's App Key
    → Render in browser tab
```

### Lepus Browser Flow

```
User types: alice@gallery
        │
        ▼
Step 1: Resolve "alice" (3-tier cache → Soroban RPC)
    → tunnel_relay + tunnel_id + services["gallery"].path
        │
        ▼
Step 2: Warren tunnel connection
    → Authenticate with Stellar JWT
    → Route to /gallery on Pintheon node
        │
        ▼
Step 3: Pintheon serves content
    → Render with Vello + Pelt (HVYM subnet)
```

## Publisher Deployment Flow

When a publisher deploys a gallery from Andromica to their Pintheon node:

```
1. Upload images + datapod to Pintheon (existing flow)
2. Pintheon creates IPNS directory for subscriber's public key
3. Pintheon auto-updates stellar.toml:
   - Appends subscriber key → IPNS hash mapping
   - [SUBSCRIBER_DIRECTORIES] section updated
4. Publisher registers name on Soroban (one-time, or update):
   - HvymNameRegistry.register("alice", tunnel_id, tunnel_relay, services)
```

Step 3 happens inside Pintheon automatically — no extra cost, no
blockchain transaction. Step 4 is a one-time registration.

## Pintheon Changes Required

### stellar.toml Update on Deploy

When `_auto_publish_directory_to_ipns` runs after an upload, Pintheon
should also update the stellar.toml:

```python
def _update_subscriber_directory_toml(self, subscriber_pub, ipns_hash):
    """Update stellar.toml with subscriber's IPNS directory mapping."""
    toml_path = os.path.join(self.static_path, 'stellar.toml')
    with open(toml_path, 'r') as f:
        data = toml.load(f)

    if 'SUBSCRIBER_DIRECTORIES' not in data:
        data['SUBSCRIBER_DIRECTORIES'] = {}

    data['SUBSCRIBER_DIRECTORIES'][subscriber_pub] = ipns_hash

    with open(toml_path, 'w') as f:
        toml.dump(data, f)
```

### nginx Route for stellar.toml (Already Exists)

The `/.well-known/stellar.toml` route is already served on the public
port via Flask. No nginx changes needed — it falls through to the
Flask app which serves the static file.

## Caching Strategy

### Three-Tier Cache (Shared Schema)

| Tier | What | Location | TTL |
|------|------|----------|-----|
| **L1** | Name → node | App memory / browser cache | 5 min |
| **L2** | Name → node | Warren relay Redis | 5 min |
| **L3** | Name → node | Soroban RPC (source of truth) | Authoritative |
| **L1** | Subscriber → IPNS | App memory | 5 min |
| **—** | Subscriber → IPNS | HTTP cache (stellar.toml) | per Cache-Control |

Name resolution uses the three-tier strategy from the Lepus research.
Subscriber IPNS resolution is simpler — just HTTP GET with standard
caching.

## Cost Model

| Operation | Cost | Who Pays | Frequency |
|-----------|------|----------|-----------|
| Name registration | ~$0.005 + cooperative fee | Publisher | Once |
| Name renewal | ~$0.003 + cooperative fee | Publisher | Annual |
| Name resolution | Free (RPC read) | Nobody | Every subscription |
| stellar.toml update | Free (file write) | Nobody | Every deployment |
| stellar.toml read | Free (HTTP GET) | Nobody | Every fetch |
| Subscriber IPNS resolve | Free (stellar.toml) | Nobody | Every fetch |

**Key insight**: Per-subscriber operations are always free. Only per-creator
operations have (negligible) blockchain costs.

## Implementation Phases

### Phase 1: Pintheon stellar.toml (No Blockchain Required)
- Update Pintheon to write `[SUBSCRIBER_DIRECTORIES]` on deploy
- Update Andromica to read stellar.toml for IPNS resolution
- Remove IPNS hash from Add Subscription dialog
- Subscriber enters: name/label + node URL (or just name once Phase 2 lands)
- **This alone solves the manual IPNS sharing problem**

### Phase 2: Multiple Datapod Support in Andromica
- `fetch_subscription_content` downloads ALL datapod .json files
- `fetch_subscription_channels` returns one channel per datapod
- Select Channel dialog shows each datapod with metadata
- Each datapod loaded/rendered independently

### Phase 3: Soroban Name Registry Contract
- Deploy `HvymNameRegistry` to testnet
- Implement register, resolve, update, renew
- Test name resolution from Andromica

### Phase 4: Andromica Name Integration
- Add Soroban RPC client
- Add Subscription dialog accepts just a **name**
- Resolution: name → node URL (Soroban) → stellar.toml → IPNS → content

### Phase 5: Lepus Browser Integration
- Subnet selector in navbar
- `@` address parser
- Native resolver with L1 cache
- Warren tunnel client

## Relationship to Existing Systems

```
                    ┌──────────────────────┐
                    │  HvymNameRegistry    │
                    │  (Soroban Contract)  │
                    │                      │
                    │  "alice" → node      │
                    └──────┬───────────────┘
                           │ resolve (free)
              ┌────────────┼────────────────┐
              ▼            ▼                ▼
         Andromica    Lepus Browser    Warren Relay
              │            │                │
              └────────────┼────────────────┘
                           │
                           ▼
                    ┌──────────────────────┐
                    │   Pintheon Node      │
                    │                      │
                    │  stellar.toml:       │
                    │  subscriber → IPNS   │
                    │                      │
                    │  IPNS directories:   │
                    │  /sub1/ → datapods   │
                    │  /sub2/ → datapods   │
                    └──────────────────────┘
```

## Open Questions

- Should Andromica support both name-based AND URL-based subscriptions
  during the rollout? (Yes for backward compatibility)
- Should stellar.toml use a dedicated `[SUBSCRIBER_DIRECTORIES]` section
  or a separate `subscribers.toml` file to avoid bloating the main toml?
- How does Stellar Account Abstraction (passkey-kit) interact with name
  ownership? Smart wallets could own names, session keys could update
  stellar.toml mappings.
- Should datapods in an IPNS directory have a manifest file (e.g.,
  `manifest.json`) that lists all datapods with metadata, instead of
  relying on directory listing HTML parsing?
