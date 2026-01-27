# HVYM Stellar v0.19 Migration Guide

This document outlines the breaking changes in hvym_stellar v0.19 and provides a migration plan for updating existing code.

## Overview of Breaking Changes

v0.19 introduces three breaking changes:

1. **Parameter spelling corrections** (no backward compatibility)
2. **Required `from_address` parameter** for `decrypt()` method
3. **Removed deprecated parameter aliases**

---

## Breaking Change 1: Parameter Spelling Corrections

### What Changed

The following parameter names were corrected:

| Old (Incorrect) | New (Correct) |
|-----------------|---------------|
| `recieverPub` | `receiverPub` |
| `recieverKeyPair` | `receiverKeyPair` |

### Affected Classes and Methods

- `StellarSharedKey.__init__(senderKeyPair, receiverPub)`
- `StellarSharedKeyTokenBuilder.__init__(senderKeyPair, receiverPub, ...)`
- `StellarSharedKeyTokenVerifier.__init__(receiverKeyPair, serializedToken, ...)`
- `HVYMDataToken.__init__(senderKeyPair, receiverPub, ...)`
- `HVYMDataToken.create_from_file(senderKeyPair, receiverPub, ...)`
- `HVYMDataToken.create_from_bytes(senderKeyPair, receiverPub, ...)`
- `HVYMDataToken.extract_from_token(serialized_token, receiver_keypair)`

### Migration Steps

1. **Find all occurrences** of the old parameter names:
   ```
   recieverPub
   recieverKeyPair
   reciever_kp
   reciever_stellar_kp
   reciever (as standalone variable)
   ```

2. **Replace with corrected spelling**:
   ```
   receiverPub
   receiverKeyPair
   receiver_kp
   receiver_stellar_kp
   receiver
   ```

### Code Examples

**Before:**
```python
shared_key = StellarSharedKey(
    senderKeyPair=sender_kp,
    recieverPub=receiver_kp.public_key()  # OLD
)

verifier = StellarSharedKeyTokenVerifier(
    recieverKeyPair=receiver_kp,  # OLD
    serializedToken=token
)
```

**After:**
```python
shared_key = StellarSharedKey(
    senderKeyPair=sender_kp,
    receiverPub=receiver_kp.public_key()  # NEW
)

verifier = StellarSharedKeyTokenVerifier(
    receiverKeyPair=receiver_kp,  # NEW
    serializedToken=token
)
```

---

## Breaking Change 2: Required `from_address` Parameter

### What Changed

The `decrypt()` method on `StellarSharedDecryption` now **requires** a `from_address` parameter for signature verification. This provides cryptographic authentication of the sender.

### Method Signature Change

**Before:**
```python
def decrypt(self, encrypted_data: bytes) -> bytes:
```

**After:**
```python
def decrypt(self, encrypted_data: bytes, from_address: str) -> bytes:
```

### Migration Steps

1. **Identify all `decrypt()` calls** on these variable types:
   - `StellarSharedDecryption` instances
   - Common variable names: `shared_decrypt`, `decryptor`, `receiver_key`, `decrypt_key`

2. **Determine the sender's public key** for each call:
   - If you have a `Stellar25519KeyPair`: use `sender_kp.public_key()`
   - If you have a `stellar_sdk.Keypair`: use `Stellar25519KeyPair(kp).public_key()`
   - If stored in a class: use `self.sender.public_key()` or similar

3. **Add the `from_address` parameter** to each call

### Code Examples

**Before:**
```python
decryptor = StellarSharedDecryption(receiver_kp, sender_kp.public_key())
plaintext = decryptor.decrypt(ciphertext)  # OLD - missing from_address
```

**After:**
```python
decryptor = StellarSharedDecryption(receiver_kp, sender_kp.public_key())
plaintext = decryptor.decrypt(
    ciphertext,
    from_address=sender_kp.public_key()  # NEW - required
)
```

### Common Patterns

**Pattern 1: Direct keypair access**
```python
# If sender_kp is a Stellar25519KeyPair
decryptor.decrypt(ct, from_address=sender_kp.public_key())
```

**Pattern 2: Class member access**
```python
# If sender is stored in self
decryptor.decrypt(ct, from_address=self.sender.public_key())
```

**Pattern 3: Stellar SDK keypair**
```python
# If you have a stellar_sdk.Keypair
sender_hvym = Stellar25519KeyPair(sender_stellar_kp)
decryptor.decrypt(ct, from_address=sender_hvym.public_key())

# Or directly from the base keypair
decryptor.decrypt(ct, from_address=sender_kp.base_stellar_keypair().public_key)
```

### What NOT to Migrate

Do **not** add `from_address` to these methods (they have different signatures):
- `asymmetric_decrypt()` - does not require from_address
- `StellarSharedKeyTokenVerifier.secret()` - handles decryption internally

---

## Breaking Change 3: Removed Deprecated Aliases

### What Changed

The following deprecated parameter aliases have been removed:

- `recieverPub` parameter alias (use `receiverPub`)
- `recieverKeyPair` parameter alias (use `receiverKeyPair`)

Code using these old names will raise `TypeError: unexpected keyword argument`.

---

## Automated Migration

A migration script is provided at `migrate_to_v019.py`:

```bash
# Dry run (preview changes)
python migrate_to_v019.py --dry-run path/to/your/code

# Apply changes
python migrate_to_v019.py path/to/your/code
```

### What the Script Does

1. **Spelling fixes**: Automatically renames all parameter/variable occurrences
2. **Decrypt migration**: Attempts to add `from_address` parameter by detecting sender variables in context
3. **Manual review markers**: Adds `# TODO` comments where automatic detection fails

### Script Limitations

The script may not correctly identify the sender in all cases. After running, search for:
```
# TODO: Add from_address=sender_address
```

And manually add the correct sender public key.

---

## Verification Checklist

After migration, verify:

- [ ] No `TypeError` for unexpected keyword arguments
- [ ] No `TypeError` for missing `from_address` parameter
- [ ] All decryption operations succeed with valid sender addresses
- [ ] Decryption fails when given incorrect sender addresses (security check)

### Test Commands

```bash
# Run main tests
python -m pytest test.py test_hvym_data_token.py -v

# Run crypto harness (if available)
cd crypto_test && python runner.py
```

---

## Quick Reference

### Import Statement (unchanged)
```python
from hvym_stellar import (
    Stellar25519KeyPair,
    StellarSharedKey,
    StellarSharedDecryption,
    StellarSharedKeyTokenBuilder,
    StellarSharedKeyTokenVerifier,
    HVYMDataToken,
    TokenType,
)
```

### Encryption (sender side)
```python
sender_kp = Stellar25519KeyPair(Keypair.random())
receiver_pub = receiver_kp.public_key()

# Create shared key for encryption
shared_key = StellarSharedKey(
    senderKeyPair=sender_kp,
    receiverPub=receiver_pub  # Corrected spelling
)

# Encrypt
ciphertext = shared_key.encrypt(plaintext)
```

### Decryption (receiver side)
```python
receiver_kp = Stellar25519KeyPair(Keypair.random())
sender_pub = sender_kp.public_key()

# Create decryption instance
decryptor = StellarSharedDecryption(
    receiverKeyPair=receiver_kp,  # Corrected spelling
    senderPub=sender_pub
)

# Decrypt with sender verification
plaintext = decryptor.decrypt(
    ciphertext,
    from_address=sender_pub  # NEW: Required parameter
)
```

### Token Creation
```python
token_builder = StellarSharedKeyTokenBuilder(
    senderKeyPair=sender_kp,
    receiverPub=receiver_pub,  # Corrected spelling
    token_type=TokenType.SECRET,
    secret="my secret data",
    expires_in=3600
)
serialized = token_builder.serialize()
```

### Token Verification
```python
verifier = StellarSharedKeyTokenVerifier(
    receiverKeyPair=receiver_kp,  # Corrected spelling
    serializedToken=serialized,
    token_type=TokenType.SECRET
)

if verifier.valid():
    secret = verifier.secret()
```

---

## AI Migration Instructions

When migrating code to v0.19, follow this systematic approach:

1. **Search for old parameter names** using regex:
   ```
   \brecieverPub\b
   \brecieverKeyPair\b
   \breciever_kp\b
   \breciever\b(?![\w])
   ```

2. **Replace all matches** with corrected spelling

3. **Find all decrypt() calls** on StellarSharedDecryption instances:
   ```
   \.decrypt\s*\([^)]+\)
   ```

4. **For each decrypt() call**, identify the sender:
   - Look for variable assignments creating the decryptor
   - The sender public key is typically passed to `StellarSharedDecryption` constructor
   - Or find sender keypair variables in scope

5. **Add from_address parameter** using the identified sender public key

6. **Run tests** to verify migration success

7. **Handle edge cases** manually where automatic detection fails
