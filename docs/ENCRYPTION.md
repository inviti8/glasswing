# Andromica Encryption & Content Protection

## Overview

Andromica provides two methods of content protection:
1. **Encryption** - Full image encryption using ImageMagick's encipher
2. **Aposematic** - Visual scrambling that hides content while remaining a valid image

Both methods use a shared key scheme based on Stellar/Curve25519 cryptography.

Additionally, media (audio/video) can be embedded in images as encrypted tokens using HVYMDataToken (Biscuit-based, ChaCha20-Poly1305). An image supports audio OR video, not both.

## Shared Key Scheme

### Key Hierarchy

```
Creator                              Recipient
───────                              ─────────
stellar_secret ──┐                   stellar_secret ──┐
                 ▼                                    ▼
         Stellar25519KeyPair                  Stellar25519KeyPair
                 │                                    │
                 ▼                                    ▼
         hvym_public_key ◄────────────────► recipient_public_key
                 │                                    │
                 └──────────┬─────────────────────────┘
                            ▼
                    StellarSharedKey
                            │
                            ▼
                   cipher_key (hex)
```

### Key Generation Flow

Two patterns exist depending on the operation:

**For enciphered images and non-aposematic operations** — derive `cipher_key` manually:

```python
# Creator side (dialogs.py)
def create_shared_key(receiver_public_key):
    stellar_secret = app.storage.user.get('stellar_secret')
    stellar_keys = Keypair.from_secret(stellar_secret)
    hvym_keys = Stellar25519KeyPair(stellar_keys)

    shared_key = StellarSharedKey(hvym_keys, receiver_public_key)
    cipher_key = shared_key.shared_secret_as_hex()
    return cipher_key
```

**For aposematic images (aiposematic v1.1)** — pass Stellar keypairs directly; the library derives the cipher key internally using domain-separated hashing: `SHA256(shared_secret + ":aiposematic:sbox")[:32]`.

```python
# Creator side — no manual cipher_key derivation needed
creator_keys = Stellar25519KeyPair(Keypair.from_secret(stellar_secret))
new_aposematic_img(img, stellar_keypair=creator_keys, subscriber_public_key=recipient_pub)

# Consumer side — same pattern
subscriber_keys = Stellar25519KeyPair(Keypair.from_secret(subscriber_secret))
recover_aposematic_img(img, stellar_keypair=subscriber_keys, artist_public_key=creator_pub)
```

### Cryptographic Primitives

| Component | Algorithm | Library |
|-----------|-----------|---------|
| Key Pair | Ed25519 | stellar-sdk |
| Key Exchange | X25519 (ECDH) | hvym-stellar |
| Shared Secret | HKDF-derived | hvym-stellar |
| Image Encryption | Proprietary | ImageMagick |
| Aposematic | Pixel manipulation | aiposematic |

## Encryption (Enciphered Images)

### Process

```
Original Image ──▶ ImageMagick encipher() ──▶ Encrypted Image
                         │
                    cipher_key
```

### Implementation

```python
# img_edit.py
async def new_enciphered_img(file_name, base_img_path, cipher_key):
    with Image(filename=base_img_path) as img:
        img.encipher(cipher_key)  # ImageMagick native encryption
        img.save(filename=temp_path)
    return temp_path

def new_deciphered_img(file_name, encrypted_img_path, cipher_key):
    with Image(filename=encrypted_img_path) as img:
        img.decipher(cipher_key)  # ImageMagick native decryption
        img.save(filename=temp_path)
    return temp_path
```

### Characteristics

- **File Format**: Remains valid image format (PNG/JPEG)
- **Visual Appearance**: Noise/static pattern
- **Reversibility**: Fully reversible with correct key
- **Security**: Dependent on ImageMagick's implementation

## Aposematic Images

### Concept

Aposematic images use visual scrambling to obscure content. The term comes from biology - "warning coloration" used by animals. The scrambled image serves as a visual warning that the content is protected.

### Scramble Modes

| Mode | Value | Description |
|------|-------|-------------|
| BUTTERFLY | 1, 2 | Block-based pixel rearrangement |
| QR | 3 | QR-code inspired pattern |

### Parameters

```python
# aiposematic v1.1 — native Stellar key integration
aposematic = new_aposematic_img(
    img_path,
    stellar_keypair=creator_keys,         # Creator's Stellar25519KeyPair
    subscriber_public_key=recipient_pub,  # Recipient's public key
    op_string='-^+',                      # Operation sequence
    scramble_mode=SCRAMBLE_MODE.BUTTERFLY
)
```

### Op String

The `op_string` defines the sequence of scrambling operations:
- `-` : Horizontal flip
- `^` : Vertical flip
- `+` : Rotate
- Additional operations defined by aiposematic

### Recovery

```python
# aiposematic v1.1 — pass Stellar keypair, not cipher_key
# Note: recover does NOT accept scramble_mode (only new_aposematic_img does)
decoded_path = recover_aposematic_img(
    scrambled_img_path,
    stellar_keypair=subscriber_keys,    # Subscriber's Stellar25519KeyPair
    artist_public_key=creator_pub,      # Creator's public key
    op_string=op_string,
)
# Returns the path to the recovered image (string), not a dict
```

## Data Pod Encryption Metadata

When deploying protected galleries, the data pod includes metadata needed for decryption:

```json
{
    "version": "1.0",
    "type": "package",
    "content_type": "aposematic",           // "original", "aposematic", "encrypted"
    "creator_public_key": "BASE64_KEY...",  // Creator's key for ECDH derivation
    "recipient_public_key": "BASE64_KEY...", // Subscriber's key for authorization
    "op_string": "-^+",                      // Aposematic only
    "scramble_mode": 2,                      // Aposematic only
    "items": [...]
}
```

### Key Roles

| Field | Role in ECDH |
|-------|--------------|
| `creator_public_key` | Subscriber uses this + their private key to derive shared secret |
| `recipient_public_key` | Verifies subscriber is authorized (optional check) |

## Browser-Side Decoding

When the Browser mode encounters protected content:

```python
async def decode_protected_images(data_pod, stellar_secret):
    content_type = data_pod.get('content_type', 'original')

    if content_type == 'original':
        return data_pod  # No decoding needed

    stellar_keys = Keypair.from_secret(stellar_secret)
    hvym_keys = Stellar25519KeyPair(stellar_keys)
    creator_public_key = data_pod.get('creator_public_key')

    # For enciphered: derive cipher_key manually
    if content_type == 'encrypted':
        shared_key = StellarSharedKey(hvym_keys, creator_public_key)
        cipher_key = shared_key.shared_secret_as_hex()

    # Decode each image
    for item in data_pod['items']:
        href = item['renditions'][0]['href']
        temp_path = download_ipfs_image(href)

        if content_type == 'encrypted':
            decoded_path = new_deciphered_img(temp_path, cipher_key)
        elif content_type == 'aposematic':
            # aiposematic v1.1: pass keypair directly
            decoded_path = recover_aposematic_img(
                temp_path,
                stellar_keypair=hvym_keys,
                artist_public_key=creator_public_key,
                op_string=data_pod.get('op_string'),
            )

        # Convert to base64 data URI for display
        base64_uri = image_to_base64_uri(decoded_path)
        item['renditions'][0]['href'] = base64_uri

    return data_pod
```

## Media Token Encryption

### Audio Tokens

Audio is encrypted as an HVYMDataToken and embedded directly in the PNG image's tEXt chunks (`audio_token_001`, `audio_token_002`, ...). The token uses ChaCha20-Poly1305 symmetric encryption with an ECDH-derived key.

```python
# Creation (audio_tokens.py)
token = create_audio_token(sender_kp, receiver_pub, audio_data, filename, expires_in)
output_path = embed_audio_token(image_file, token)

# Extraction (audio_tokens.py)
audio_bytes, metadata = extract_audio_from_token(receiver_kp, serialized_token)
```

### Video Tokens

Video tokens follow the same HVYMDataToken encryption but are too large for PNG tEXt chunks. Instead, the encrypted token is stored on IPFS and only the CID (~50 bytes) is embedded in the PNG.

```python
# Creation (video_tokens.py)
token = create_video_token(sender_kp, receiver_pub, video_data, filename, expires_in)
cid = ipfs_add(token_file)
embed_video_token_cid(image_file, cid)

# Extraction (video_tokens.py)
token_data = ipfs_load(cid)
video_bytes, metadata = extract_video_from_token(receiver_kp, token_data)
```

### Token Lifecycle

| Step | Audio | Video |
|------|-------|-------|
| Encrypt | `HVYMDataToken.create_from_bytes()` | `HVYMDataToken.create_from_bytes()` |
| Store | PNG tEXt chunks | IPFS (CID in PNG tEXt chunks) |
| Survive processing | `reembed_media_if_needed()` copies chunks | `reembed_media_if_needed()` copies CID chunks |
| Pre-extract (recovery) | `extract_audio_token()` before image recovery | `extract_video_token_cid()` before image recovery |
| Decrypt | `HVYMDataToken.extract_from_token()` | `HVYMDataToken.extract_from_token()` |
| Cleanup | Strip tEXt chunks | Unpin CID from IPFS + strip tEXt chunks |

## Debug Key

For testing, a persistent debug key is generated:

```python
# main.py - init()
debug_secret = app.storage.user.get('debug_secret', None)
if debug_secret is None:
    debug_secret = Keypair.random().secret
    app.storage.user['debug_secret'] = debug_secret

debug_keys = Stellar25519KeyPair(Keypair.from_secret(debug_secret))
debug_public_key = debug_keys.public_key()
```

The debug key appears as "Debug (Test Key)" in recipient dropdowns, allowing creators to test the full encryption/decryption flow locally.

## Security Considerations

### Key Storage
- `stellar_secret` stored in `data.json` (local file)
- Keys are never transmitted over network
- Shared keys computed locally on both ends

### Content Protection Levels
- **Original**: No protection
- **Aposematic**: Visual obfuscation (not cryptographically secure)
- **Encrypted**: Cryptographic protection

### Threat Model
- Assumes IPFS content is publicly accessible
- Protection depends on keeping `stellar_secret` private
- Subscriber must have matching key pair to decrypt

### Recommendations
1. Use encryption for sensitive content
2. Use aposematic for "preview protection" scenarios
3. Regularly rotate subscriber keys for high-security use cases
4. Consider the trust model when adding subscribers
5. Large video files (500MB+) may be slow to encrypt/decrypt — consider file size when embedding
6. MP4 (H.264) and WebM (VP8/VP9) have the best browser playback support
