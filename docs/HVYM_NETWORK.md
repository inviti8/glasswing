# HVYM Network Name Service — Design Document

## Overview

A Soroban-based name service that maps human-readable names to Pintheon node
tunnel endpoints. Designed as a shared schema for both **Andromica** (first
production consumer) and **Lepus Browser** (future Firefox fork with native
HVYM subnet support).

This replaces the current manual IPNS hash sharing requirement in the
subscriber flow with automatic, ledger-backed name resolution.

## Problem Statement

Currently, subscribing to a Pintheon node in Andromica requires:
1. The node URL (e.g., `https://mypublisher.pintheon.com`)
2. The IPNS hash (e.g., `k51qzi5uqu5d...`) — shared manually by the publisher

The IPNS hash is non-deterministic (random per `ipfs key gen`) and opaque
to users. This is a UX barrier, especially for crypto-averse users.

## Solution

A Soroban smart contract (`HvymNameRegistry`) that maps names to tunnel
endpoints. Publishers register a name, subscribers look it up. Resolution
is free (read-only RPC query).

```
Current flow:
  Publisher → "here's my IPNS hash: k51qzi5..." → Subscriber pastes into Andromica

With name service:
  Publisher registers "alice" → Subscriber types "alice" in Andromica → resolved
```

## Name Service Schema

### NameRecord (On-Chain)

```rust
#[contracttype]
pub struct NameRecord {
    // Identity
    pub name: String,               // "alice" — unique, lowercase alphanumeric + hyphens
    pub owner: Address,             // Stellar address of the name owner

    // Tunnel Resolution
    pub tunnel_id: Address,         // Stellar address for tunnel authentication
    pub tunnel_relay: String,       // Relay server: "tunnel.hvym.link"

    // Service Routing
    pub services: Map<Symbol, ServiceEndpoint>,
    // e.g., "gallery" -> {path: "/gallery", ipns_hash: "k51q..."}

    // Metadata
    pub ttl: u32,                   // Cache TTL in seconds (default: 300)
    pub registered_at: u64,         // Ledger timestamp
    pub expires_at: u64,            // Expiration (annual renewal)
    pub member_id: Address,         // Cooperative member credential
    pub status: NameStatus,         // Active, Expired, Suspended, Transferring
}

#[contracttype]
pub struct ServiceEndpoint {
    pub path: String,               // URL path on the Pintheon node: "/gallery"
    pub ipns_hash: Option<String>,  // IPNS directory hash (if applicable)
    pub description: String,        // "Photo gallery"
}

#[contracttype]
pub enum NameStatus {
    Active,
    Expired,
    Suspended,
    Transferring,
}
```

### Why This Schema Works for Both Andromica and Lepus

| Field | Andromica Use | Lepus Browser Use |
|-------|--------------|-------------------|
| `name` | Subscription label (auto-resolved) | URL bar: `alice@gallery` |
| `tunnel_id` | Connect to publisher's Pintheon node | Route HTTP through tunnel |
| `tunnel_relay` | Warren tunnel server address | Warren tunnel server address |
| `services` | Find IPNS hash for subscriber's content | Path routing for `@service` |
| `ipns_hash` | Auto-discover subscriber's IPNS directory | Resolve content directory |
| `member_id` | Verify publisher is cooperative member | Display trust badge |

## Contract Interface

```rust
pub trait HvymNameRegistry {
    // === Write Operations (require Stellar tx fee) ===

    /// Register a new name. Caller must be a cooperative member.
    fn register(
        env: Env,
        name: String,
        tunnel_id: Address,
        tunnel_relay: String,
        services: Map<Symbol, ServiceEndpoint>,
    ) -> Result<NameRecord, RegistryError>;

    /// Renew an existing name (extend expiration).
    fn renew(env: Env, name: String) -> Result<NameRecord, RegistryError>;

    /// Transfer ownership to another cooperative member.
    fn transfer(
        env: Env,
        name: String,
        new_owner: Address,
    ) -> Result<NameRecord, RegistryError>;

    /// Update tunnel endpoint or services for an owned name.
    fn update(
        env: Env,
        name: String,
        tunnel_id: Option<Address>,
        tunnel_relay: Option<String>,
        services: Option<Map<Symbol, ServiceEndpoint>>,
    ) -> Result<NameRecord, RegistryError>;

    /// Add or update an IPNS hash for a specific subscriber on a service.
    /// Called by the publisher after deploying content for a subscriber.
    fn set_subscriber_ipns(
        env: Env,
        name: String,
        service: Symbol,
        subscriber_pub: String,
        ipns_hash: String,
    ) -> Result<(), RegistryError>;

    // === Read Operations (free, via Soroban RPC) ===

    /// Resolve a name to its full record.
    fn resolve(env: Env, name: String) -> Option<NameRecord>;

    /// Look up the IPNS hash for a specific subscriber on a service.
    fn resolve_subscriber(
        env: Env,
        name: String,
        service: Symbol,
        subscriber_pub: String,
    ) -> Option<String>;  // Returns IPNS hash

    /// Check if a name is available for registration.
    fn available(env: Env, name: String) -> bool;
}
```

## Resolution Flow

### Andromica Subscriber Flow (Phase 1 — Production)

```
Subscriber adds subscription:
    Label: "Alice's Gallery"
    Name:  "alice"
        │
        ▼
Andromica resolves "alice" via Soroban RPC:
    name_record = HvymNameRegistry.resolve("alice")
        │
        ├── tunnel_relay: "tunnel.hvym.link"
        ├── tunnel_id: GALICE123...
        └── services: {"gallery": {path: "/gallery", ipns_hash: null}}
        │
        ▼
Look up subscriber's IPNS hash:
    ipns = HvymNameRegistry.resolve_subscriber(
        "alice", "gallery", subscriber_public_key
    )
    → "k51qzi5uqu5dizy5yl4fle50vzyparjgrcupo1mclslh0qexv69bmmyeb4h74z"
        │
        ▼
Fetch content from publisher's node:
    GET https://{tunnel_relay}/ipns/{ipns}/
    → Parse directory → download data pod → decrypt → render
```

### Lepus Browser Flow (Phase 2 — Future)

```
User types in URL bar: alice@gallery
        │
        ▼
Subnet selector: [hvym ▼]
        │
        ▼
HvymNavigationThrottle intercepts:
    Parse: name="alice", service="gallery"
        │
        ▼
Three-tier resolution:
    1. Browser cache (hit → skip to tunnel)
    2. Relay Redis cache (hit → skip to tunnel)
    3. Soroban RPC query (source of truth)
        │
        ▼
Establish Warren tunnel:
    WebSocket to tunnel.hvym.link
    Authenticate with subscriber's Stellar JWT
        │
        ▼
Route HTTP through tunnel:
    GET /gallery HTTP/1.1
    Host: alice
    X-HVYM-Service: gallery
        │
        ▼
Pintheon node serves content
    → Vello + Pelt rendering (if HVYM subnet)
    → Standard HTML/CSS (if DNS fallback)
```

## Publisher Registration Flow

### From Andromica (Deploy to Pintheon + Register Name)

After deploying a gallery to Pintheon, the publisher can register or update
their name in the registry:

```
Publisher deploys gallery to Pintheon:
    → Images + data pod uploaded
    → IPNS directory created (keyed by subscriber's public key)
    → IPNS hash returned
        │
        ▼
Publisher registers/updates name service:
    HvymNameRegistry.update("alice", services: {
        "gallery": {path: "/gallery", ipns_hash: null}
    })
        │
        ▼
Publisher sets subscriber-specific IPNS:
    HvymNameRegistry.set_subscriber_ipns(
        "alice", "gallery",
        subscriber_pub="Lo05eOX99L6D0D99...",
        ipns_hash="k51qzi5uqu5dizy5..."
    )
```

This means the publisher registers their name once and updates the
subscriber IPNS mapping each time they deploy new content. The subscriber
never needs to know the IPNS hash — they just subscribe to "alice".

## Subscriber-Specific IPNS Storage

The key innovation for Andromica: store per-subscriber IPNS hashes
on-chain so subscribers can auto-discover their content.

```rust
// On-chain storage: Map<(name, service, subscriber_pub), ipns_hash>
// Example:
//   ("alice", "gallery", "Lo05eOX99...") → "k51qzi5uqu5dizy5..."
//   ("alice", "gallery", "cdf2VgO63...") → "k51qzi5uqu5dk25a..."
```

This is small data (name + key + hash ≈ 200 bytes per subscriber) and
Soroban storage rent is negligible ($0.001-0.002/year per record).

## Caching Strategy

### Three-Tier Cache (Shared Between Andromica and Lepus)

| Tier | Location | TTL | Update Trigger |
|------|----------|-----|----------------|
| **L1** | App memory (Andromica) / Browser cache (Lepus) | 5 min | Manual refresh or TTL expiry |
| **L2** | Warren relay Redis | 5 min | Soroban contract events |
| **L3** | Soroban RPC | Authoritative | On-chain state |

### Event-Driven Invalidation

```rust
// Contract emits events on state changes:
env.events().publish(("name_registered",), (name, record));
env.events().publish(("name_updated",), (name, record));
env.events().publish(("subscriber_ipns_set",), (name, service, subscriber_pub, ipns_hash));
```

Warren relay servers subscribe to these events and invalidate L2 cache
immediately. Andromica can optionally subscribe for push notifications.

## Cost Model

| Operation | Cost | Who Pays |
|-----------|------|----------|
| Name registration | ~$0.005 (Soroban tx) + cooperative fee | Publisher |
| Name renewal | ~$0.003 (Soroban tx) + cooperative fee | Publisher |
| Name resolution | Free (RPC read) | Nobody |
| Set subscriber IPNS | ~$0.003 (Soroban tx) | Publisher |
| Resolve subscriber IPNS | Free (RPC read) | Nobody |

Resolution is always free — this is critical for subscriber UX. Publishers
pay negligible fees to register and update.

## Name Rules

- **Characters**: lowercase alphanumeric + hyphens (`a-z`, `0-9`, `-`)
- **Length**: 3-63 characters (no 1-2 char names outside auctions)
- **No leading/trailing hyphens**
- **Unique**: first-come, first-served (for cooperative members)
- **Membership required**: only cooperative members can register
- **Annual renewal**: prevents abandoned name squatting

## Integration with Existing Code

### Andromica Changes

1. **Add Subscription dialog** — replace URL + IPNS hash with just a **name**:
   ```
   ┌─────────────────────────────┐
   │ Subscribe                   │
   │                             │
   │ Name: [alice          ]     │
   │                             │
   │        [Cancel] [Subscribe] │
   └─────────────────────────────┘
   ```

2. **`fetch_subscription_content`** — resolve name via Soroban RPC instead
   of requiring IPNS hash upfront

3. **Pintheon deploy flow** — after deployment, call `set_subscriber_ipns`
   to register the IPNS hash for the subscriber

4. **Settings** — Soroban RPC endpoint configuration (testnet/mainnet)

### Pintheon Changes

None required initially. Pintheon continues to serve content via IPFS/IPNS
gateway. The name service is a layer above Pintheon.

### Lepus Browser (Future)

1. Subnet selector in navbar (`dns` / `hvym`)
2. `@` address parser in URL bar
3. `HvymNavigationThrottle` for interception
4. Built-in resolver with L1 cache
5. Warren tunnel client for content delivery

## Implementation Phases

### Phase 1: Soroban Contract (Shared Foundation)
- Deploy `HvymNameRegistry` contract to testnet
- Implement: `register`, `resolve`, `set_subscriber_ipns`, `resolve_subscriber`
- Test with Andromica locally

### Phase 2: Andromica Integration
- Add Soroban RPC client to Andromica
- Update Add Subscription to resolve by name
- Update deploy flow to call `set_subscriber_ipns`
- Remove IPNS hash from subscription dialog

### Phase 3: Warren Relay Cache
- Add Redis-based L2 cache to tunnel relay servers
- Subscribe to Soroban contract events for invalidation
- Expose resolution endpoint for tunnel clients

### Phase 4: Lepus Browser
- Fork Firefox/Chromium
- Implement subnet selector
- Implement `@` address parser
- Integrate resolver with L1 cache + fallback to L2/L3
- Warren tunnel client for content delivery

## Relationship to Existing Systems

```
                    ┌──────────────────────┐
                    │  HvymNameRegistry    │
                    │  (Soroban Contract)  │
                    └──────┬───────────────┘
                           │ resolve / set_subscriber_ipns
              ┌────────────┼────────────────┐
              ▼            ▼                ▼
         Andromica    Lepus Browser    Warren Relay
         (Phase 2)    (Phase 4)        (Phase 3)
              │            │                │
              └────────────┼────────────────┘
                           │ tunnel connection
                           ▼
                    ┌──────────────────────┐
                    │   Warren Tunnel      │
                    │  (hvym_tunnler)      │
                    └──────┬───────────────┘
                           │ E2E encrypted
                           ▼
                    ┌──────────────────────┐
                    │   Pintheon Node      │
                    │  (self-sovereign)    │
                    └──────────────────────┘
                           │
                    IPFS / IPNS content
```

## Open Questions

- Should Andromica support both name-based AND URL-based subscriptions
  (for backward compatibility during rollout)?
- Should the name service support wildcard services (e.g., `alice@*`
  routes everything to a single Pintheon endpoint)?
- How does name service interact with the Stellar Account Abstraction SDK
  for passkey-based auth? (Smart wallets could own names, session keys
  could update IPNS mappings)
- Should subscriber IPNS mappings be encrypted on-chain (only the
  subscriber can read their IPNS hash) or is the hash safe to be public?
