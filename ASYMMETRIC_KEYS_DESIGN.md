# Asymmetric Derived Keys Design for hvym_stellar

## Problem Analysis

The current implementation uses a **self-encryption pattern**:
```python
# CURRENT (PROBLEMATIC)
derived_key = hashlib.sha256(salt + ecdh_secret).digest()
private_key = PrivateKey(derived_key)
public_key = PublicKey(derived_key)  # Same key!
box = Box(private_key, public_key)   # Self-encryption
```

This creates security issues and violates standard cryptographic practices.

## Proposed Solution: Proper Asymmetric Encryption

### Core Design Principles

1. **Use Standard X25519**: Leverage the existing ECDH shared secret directly
2. **Maintain API Compatibility**: Keep the current salt/nonce parameter model
3. **Support Both Patterns**: Allow both derived key usage AND standard encryption
4. **Backward Compatibility**: Existing code continues to work

### Implementation Strategy

#### Option 1: Enhanced Encryption (Recommended)

```python
def encrypt(self, text: bytes) -> bytes:
    """Encrypt using standard X25519 asymmetric encryption."""
    # Generate new random salt and nonce for each encryption
    self._salt = secrets.token_bytes(32)
    self._nonce = secrets.token_bytes(secret.SecretBox.NONCE_SIZE)
    
    # Use the standard X25519 box for encryption
    # This is the proper asymmetric encryption pattern
    encrypted = self._box.encrypt(text, self._nonce, encoder=nacl.encoding.HexEncoder)
    
    # Return salt + '|' + nonce + '|' + ciphertext
    return (base64.urlsafe_b64encode(self._salt) + b'|' +
            base64.urlsafe_b64encode(self._nonce) + b'|' +
            encrypted.ciphertext)

def _derive_key(self, salt: bytes = None, nonce: bytes = None) -> bytes:
    """
    Derive a key using salt and ECDH shared secret.
    
    This remains for backward compatibility and specific use cases
    where you need a derived key (not for encryption).
    """
    if salt is None:
        salt = self._salt
    # Combine salt and shared secret
    combined = salt + self._box.shared_key()
    # Hash the combination to get the derived key
    return hashlib.sha256(combined).digest()
```

#### Option 2: Dual-Mode Encryption

```python
def encrypt(self, text: bytes, use_derived_key: bool = False) -> bytes:
    """
    Encrypt with option to use derived key or standard X25519.
    
    Args:
        text: Message to encrypt
        use_derived_key: If True, use derived key (current behavior)
                       If False, use standard X25519 (recommended)
    """
    # Generate new random salt and nonce
    self._salt = secrets.token_bytes(32)
    self._nonce = secrets.token_bytes(secret.SecretBox.NONCE_SIZE)
    
    if use_derived_key:
        # Current behavior (self-encryption) - DEPRECATED
        derived_key = self._derive_key()
        private_key = PrivateKey(derived_key)
        public_key = PublicKey(derived_key)
        box = Box(private_key, public_key)
        encrypted = box.encrypt(text, self._nonce, encoder=nacl.encoding.HexEncoder)
    else:
        # New behavior (proper asymmetric encryption)
        encrypted = self._box.encrypt(text, self._nonce, encoder=nacl.encoding.HexEncoder)
    
    return (base64.urlsafe_b64encode(self._salt) + b'|' +
            base64.urlsafe_b64encode(self._nonce) + b'|' +
            encrypted.ciphertext)
```

### Updated Decryption

```python
def decrypt(self, encrypted_data: bytes) -> bytes:
    """Decrypt using standard X25519 asymmetric decryption."""
    try:
        # Parse encrypted data
        parts = encrypted_data.split(b'|', 2)
        if len(parts) != 3:
            raise ValueError("Invalid encrypted data format")
            
        salt_b64, nonce_b64, ciphertext = parts
        
        # Decode components
        salt = base64.urlsafe_b64decode(salt_b64)
        nonce = base64.urlsafe_b64decode(nonce_b64)
        
        # Use standard X25519 decryption
        # The _box was initialized with receiver's private key and sender's public key
        if not isinstance(ciphertext, bytes):
            ciphertext = ciphertext.encode('utf-8')
        
        return self._box.decrypt(ciphertext, nonce, encoder=nacl.encoding.HexEncoder)
        
    except Exception as e:
        raise ValueError(f"Decryption failed: {str(e)}")
```

## Complete Implementation

### Updated StellarSharedKey Class

```python
class StellarSharedKey:
    def __init__(self, senderKeyPair: Stellar25519KeyPair, recieverPub: str):
        # Generate a random 32-byte salt for this instance
        self._salt = secrets.token_bytes(32)
        self._nonce = secrets.token_bytes(secret.SecretBox.NONCE_SIZE)
        self._hasher = hashlib.sha256()
        self._private = senderKeyPair.private_key()
        self._raw_pub = base64.urlsafe_b64decode(recieverPub.encode("utf-8"))
        # This box is used for standard X25519 encryption
        self._box = Box(self._private, PublicKey(self._raw_pub))

    def encrypt(self, text: bytes) -> bytes:
        """
        Encrypt using standard X25519 asymmetric encryption.
        
        This is the recommended approach that uses proper asymmetric cryptography.
        """
        # Generate new random salt and nonce for each encryption
        self._salt = secrets.token_bytes(32)
        self._nonce = secrets.token_bytes(secret.SecretBox.NONCE_SIZE)
        
        # Use standard X25519 encryption (proper asymmetric pattern)
        encrypted = self._box.encrypt(text, self._nonce, encoder=nacl.encoding.HexEncoder)
        
        # Return salt + '|' + nonce + '|' + ciphertext
        return (base64.urlsafe_b64encode(self._salt) + b'|' +
                base64.urlsafe_b64encode(self._nonce) + b'|' +
                encrypted.ciphertext)
    
    def encrypt_with_derived_key(self, text: bytes) -> bytes:
        """
        Encrypt using derived key (legacy behavior).
        
        DEPRECATED: Use encrypt() for new implementations.
        This method exists for backward compatibility.
        """
        # Generate new random salt and nonce
        self._salt = secrets.token_bytes(32)
        self._nonce = secrets.token_bytes(secret.SecretBox.NONCE_SIZE)
        
        # Use derived key (self-encryption pattern)
        derived_key = self._derive_key()
        private_key = PrivateKey(derived_key)
        public_key = PublicKey(derived_key)
        box = Box(private_key, public_key)
        encrypted = box.encrypt(text, self._nonce, encoder=nacl.encoding.HexEncoder)
        
        return (base64.urlsafe_b64encode(self._salt) + b'|' +
                base64.urlsafe_b64encode(self._nonce) + b'|' +
                encrypted.ciphertext)

    def _derive_key(self, salt: bytes = None, nonce: bytes = None) -> bytes:
        """
        Derive a key using salt and ECDH shared secret.
        
        This method remains for:
        1. Backward compatibility
        2. Specific use cases requiring derived keys
        3. Hash operations and key derivation scenarios
        """
        if salt is None:
            salt = self._salt
        # Combine salt and shared secret
        combined = salt + self._box.shared_key()
        # Hash the combination to get the derived key
        return hashlib.sha256(combined).digest()
```

### Updated StellarSharedDecryption Class

```python
class StellarSharedDecryption:
    def __init__(self, recieverKeyPair: Stellar25519KeyPair, senderPub: str):
        self._hasher = hashlib.sha256()
        self._private = recieverKeyPair.private_key()
        self._raw_pub = base64.urlsafe_b64decode(senderPub.encode("utf-8"))
        # This box is used for standard X25519 decryption
        self._box = Box(self._private, PublicKey(self._raw_pub))

    def decrypt(self, encrypted_data: bytes) -> bytes:
        """
        Decrypt using standard X25519 asymmetric decryption.
        """
        try:
            # Parse encrypted data
            parts = encrypted_data.split(b'|', 2)
            if len(parts) != 3:
                raise ValueError("Invalid encrypted data format")
                
            salt_b64, nonce_b64, ciphertext = parts
            
            # Decode nonce (salt is extracted for potential key derivation)
            nonce = base64.urlsafe_b64decode(nonce_b64)
            
            # Use standard X25519 decryption
            if not isinstance(ciphertext, bytes):
                ciphertext = ciphertext.encode('utf-8')
            
            return self._box.decrypt(ciphertext, nonce, encoder=nacl.encoding.HexEncoder)
                
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")
    
    def decrypt_with_derived_key(self, encrypted_data: bytes) -> bytes:
        """
        Decrypt using derived key (legacy behavior).
        
        DEPRECATED: Use decrypt() for new implementations.
        """
        try:
            # Parse encrypted data
            parts = encrypted_data.split(b'|', 2)
            if len(parts) != 3:
                raise ValueError("Invalid encrypted data format")
                
            salt_b64, nonce_b64, ciphertext = parts
            
            # Decode components
            salt = base64.urlsafe_b64decode(salt_b64)
            nonce = base64.urlsafe_b64decode(nonce_b64)
            
            # Use derived key for decryption
            derived_key = self._derive_key(salt)
            private_key = PrivateKey(derived_key)
            public_key = PublicKey(derived_key)
            box = Box(private_key, public_key)
            
            if not isinstance(ciphertext, bytes):
                ciphertext = ciphertext.encode('utf-8')
            
            return box.decrypt(ciphertext, nonce, encoder=nacl.encoding.HexEncoder)
                
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")
```

## Usage Examples

### New Recommended Pattern (Proper Asymmetric)

```python
# === SENDER SIDE ===
sender_key = StellarSharedKey(sender_kp, receiver_kp.public_key())
message = b"Secret message using proper asymmetric encryption"
encrypted = sender_key.encrypt(message)  # Uses standard X25519

# Extract salt/nonce for key derivation (if needed)
salt = extract_salt_from_encrypted(encrypted)
nonce = extract_nonce_from_encrypted(encrypted)

# === RECEIVER SIDE ===
receiver_key = StellarSharedDecryption(receiver_kp, sender_kp.public_key())
decrypted = receiver_key.decrypt(encrypted)  # Uses standard X25519

# Both can still derive consistent keys for other operations
sender_derived = sender_key.shared_secret(salt=salt)
receiver_derived = receiver_key.shared_secret(salt=salt)
```

### Legacy Pattern (Backward Compatible)

```python
# === SENDER SIDE ===
sender_key = StellarSharedKey(sender_kp, receiver_kp.public_key())
message = b"Secret message using derived key"
encrypted = sender_key.encrypt_with_derived_key(message)  # Uses derived key

# === RECEIVER SIDE ===
receiver_key = StellarSharedDecryption(receiver_kp, sender_kp.public_key())
decrypted = receiver_key.decrypt_with_derived_key(encrypted)  # Uses derived key
```

## Migration Path

### Phase 1: Add New Methods
- Add `encrypt()` and `decrypt()` with proper asymmetric encryption
- Keep existing methods with `_with_derived_key` suffix
- Add deprecation warnings

### Phase 2: Update Defaults
- Make `encrypt()` use proper asymmetric encryption
- Keep legacy methods available

### Phase 3: Remove Legacy (Future Major Version)
- Remove deprecated methods in v2.0.0

## Security Benefits

1. **Proper Asymmetric Encryption**: Uses standard X25519 pattern
2. **No Self-Encryption**: Eliminates unusual cryptographic pattern
3. **Industry Standard**: Aligns with Signal Protocol, TLS 1.3
4. **Backward Compatible**: Existing code continues to work
5. **Security Rating**: Improves from MODERATE to HIGH

## Compatibility

- ✅ **Existing API**: Maintained for backward compatibility
- ✅ **Salt/Nonce Model**: Still works for key derivation
- ✅ **Sender-Receiver Pattern**: Enhanced with proper encryption
- ✅ **Token System**: Can be updated to use new encryption
- ✅ **Test Suite**: Can be updated to cover both patterns

This design solves the security issues while maintaining the functionality and API that users expect.
