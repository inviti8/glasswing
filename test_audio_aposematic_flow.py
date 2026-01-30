"""
Test: Audio Image → Aposematic → Decipher → Audio Recovery

This test verifies that audio data embedded in a PNG image survives
the full aposematic scramble/recover cycle.

Flow:
1. Create a test image with embedded audio
2. Convert to aposematic (scramble)
3. Verify audio is still present in aposematic image
4. Recover (decipher) the aposematic image
5. Verify audio can be extracted from recovered image
6. Compare original and recovered audio data
"""

import os
import sys
import tempfile
import hashlib
from PIL import Image
import numpy as np

# Add the project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from png_chunks import (
    embed_audio_base64,
    extract_audio_base64,
    embed_audio_token,
    extract_audio_token,
    has_audio_data,
)
from aiposematic import new_aposematic_img, recover_aposematic_img, SCRAMBLE_MODE


def create_test_image(path: str, width: int = 256, height: int = 256):
    """Create a simple test image with a gradient pattern."""
    # Create a gradient image so we can visually verify scramble/recover
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        for x in range(width):
            arr[y, x] = [x % 256, y % 256, (x + y) % 256]

    img = Image.fromarray(arr, 'RGB')
    img.save(path, 'PNG')
    print(f"✅ Created test image: {path} ({width}x{height})")
    return path


def create_test_audio() -> bytes:
    """Create simple test audio data (WAV format header + silence)."""
    # Simple WAV file with 1 second of silence
    sample_rate = 44100
    num_samples = sample_rate  # 1 second
    bits_per_sample = 16
    num_channels = 1

    # WAV header
    data_size = num_samples * num_channels * (bits_per_sample // 8)
    file_size = 36 + data_size

    header = bytearray()
    header.extend(b'RIFF')
    header.extend(file_size.to_bytes(4, 'little'))
    header.extend(b'WAVE')
    header.extend(b'fmt ')
    header.extend((16).to_bytes(4, 'little'))  # Subchunk1Size
    header.extend((1).to_bytes(2, 'little'))   # AudioFormat (PCM)
    header.extend(num_channels.to_bytes(2, 'little'))
    header.extend(sample_rate.to_bytes(4, 'little'))
    byte_rate = sample_rate * num_channels * (bits_per_sample // 8)
    header.extend(byte_rate.to_bytes(4, 'little'))
    block_align = num_channels * (bits_per_sample // 8)
    header.extend(block_align.to_bytes(2, 'little'))
    header.extend(bits_per_sample.to_bytes(2, 'little'))
    header.extend(b'data')
    header.extend(data_size.to_bytes(4, 'little'))

    # Add some non-zero audio data so we can verify it's preserved
    audio_data = bytearray(header)
    for i in range(num_samples):
        # Simple sine wave pattern
        value = int(32767 * np.sin(2 * np.pi * 440 * i / sample_rate))
        audio_data.extend(value.to_bytes(2, 'little', signed=True))

    return bytes(audio_data)


def hash_data(data: bytes) -> str:
    """Get SHA256 hash of data."""
    return hashlib.sha256(data).hexdigest()


def run_test_base64_method():
    """Test audio preservation using base64 metadata method."""
    print("\n" + "="*60)
    print("TEST: Audio Aposematic Flow (Base64 Metadata Method)")
    print("="*60)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Step 1: Create test image and audio
        print("\n📌 Step 1: Create test image and audio")
        test_image_path = os.path.join(tmpdir, "test_image.png")
        create_test_image(test_image_path)

        original_audio = create_test_audio()
        original_audio_hash = hash_data(original_audio)
        print(f"   Audio size: {len(original_audio)} bytes")
        print(f"   Audio hash: {original_audio_hash[:16]}...")

        # Step 2: Embed audio into image
        print("\n📌 Step 2: Embed audio into image (base64 method)")
        audio_image_path = os.path.join(tmpdir, "audio_image.png")

        import base64
        audio_base64 = base64.b64encode(original_audio).decode('ascii')
        result = embed_audio_base64(test_image_path, audio_base64, audio_image_path)

        if not result or not os.path.exists(audio_image_path):
            print("   ❌ FAILED: Could not embed audio")
            return False

        # Verify audio is embedded
        has_audio, method = has_audio_data(audio_image_path)
        print(f"   Audio embedded: {has_audio}, method: {method}")

        if not has_audio:
            print("   ❌ FAILED: Audio not detected in embedded image")
            return False

        # Extract and verify
        extracted_b64 = extract_audio_base64(audio_image_path)
        if extracted_b64:
            extracted_audio = base64.b64decode(extracted_b64)
            extracted_hash = hash_data(extracted_audio)
            print(f"   Extracted audio hash: {extracted_hash[:16]}...")
            if extracted_hash == original_audio_hash:
                print("   ✅ Audio correctly embedded and extractable")
            else:
                print("   ❌ FAILED: Extracted audio doesn't match original")
                return False
        else:
            print("   ❌ FAILED: Could not extract audio from embedded image")
            return False

        # Step 3: Convert to aposematic
        print("\n📌 Step 3: Convert to aposematic")
        cipher_key = "test_cipher_key_1234567890abcdef"
        op_string = "-^+"

        try:
            aposematic_result = new_aposematic_img(
                audio_image_path,
                cipher_key=cipher_key,
                op_string=op_string,
                scramble_mode=SCRAMBLE_MODE.BUTTERFLY
            )
            aposematic_path = aposematic_result.get("img_path") if isinstance(aposematic_result, dict) else aposematic_result
            print(f"   Aposematic image: {aposematic_path}")
        except Exception as e:
            print(f"   ❌ FAILED: Could not create aposematic: {e}")
            return False

        if not aposematic_path or not os.path.exists(aposematic_path):
            print("   ❌ FAILED: Aposematic image not created")
            return False

        # Step 4: Check if audio survived aposematic conversion
        print("\n📌 Step 4: Check audio in aposematic image")
        has_audio_apo, method_apo = has_audio_data(aposematic_path)
        print(f"   Audio in aposematic: {has_audio_apo}, method: {method_apo}")

        if has_audio_apo:
            apo_audio_b64 = extract_audio_base64(aposematic_path)
            if apo_audio_b64:
                apo_audio = base64.b64decode(apo_audio_b64)
                apo_audio_hash = hash_data(apo_audio)
                print(f"   Aposematic audio hash: {apo_audio_hash[:16]}...")
                if apo_audio_hash == original_audio_hash:
                    print("   ✅ Audio preserved in aposematic image")
                else:
                    print("   ⚠️ WARNING: Audio data changed during aposematic conversion")
            else:
                print("   ❌ FAILED: Could not extract audio from aposematic")
                return False
        else:
            print("   ❌ FAILED: Audio LOST during aposematic conversion!")
            print("   This is the bug - aiposematic doesn't preserve PNG chunks")
            return False

        # Step 5: Recover from aposematic
        print("\n📌 Step 5: Recover from aposematic")
        try:
            recovered_result = recover_aposematic_img(
                aposematic_path,
                cipher_key=cipher_key,
                op_string=op_string
            )
            recovered_path = recovered_result.get("img_path") if isinstance(recovered_result, dict) else recovered_result
            print(f"   Recovered image: {recovered_path}")
        except Exception as e:
            print(f"   ❌ FAILED: Could not recover aposematic: {e}")
            return False

        if not recovered_path or not os.path.exists(recovered_path):
            print("   ❌ FAILED: Recovered image not created")
            return False

        # Step 6: Check if audio survived recovery
        print("\n📌 Step 6: Check audio in recovered image")
        has_audio_rec, method_rec = has_audio_data(recovered_path)
        print(f"   Audio in recovered: {has_audio_rec}, method: {method_rec}")

        if has_audio_rec:
            rec_audio_b64 = extract_audio_base64(recovered_path)
            if rec_audio_b64:
                rec_audio = base64.b64decode(rec_audio_b64)
                rec_audio_hash = hash_data(rec_audio)
                print(f"   Recovered audio hash: {rec_audio_hash[:16]}...")
                if rec_audio_hash == original_audio_hash:
                    print("   ✅ Audio preserved through full cycle!")
                else:
                    print("   ❌ FAILED: Recovered audio doesn't match original")
                    return False
            else:
                print("   ❌ FAILED: Could not extract audio from recovered image")
                return False
        else:
            print("   ❌ FAILED: Audio LOST during recovery!")
            return False

        # Summary
        print("\n" + "="*60)
        print("TEST RESULT: ✅ PASSED")
        print("="*60)
        print(f"Original audio:   {original_audio_hash[:32]}...")
        print(f"After embed:      {extracted_hash[:32]}...")
        print(f"After aposematic: {apo_audio_hash[:32]}...")
        print(f"After recovery:   {rec_audio_hash[:32]}...")
        return True


def run_test_token_method():
    """Test audio preservation using encrypted token method."""
    print("\n" + "="*60)
    print("TEST: Audio Aposematic Flow (Encrypted Token Method)")
    print("="*60)

    try:
        from stellar_sdk import Keypair
        from hvym_stellar import Stellar25519KeyPair, HVYMDataToken
        from audio_tokens import create_audio_token, extract_audio_from_token
    except ImportError as e:
        print(f"   ⚠️ SKIPPED: Missing dependencies for token test: {e}")
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        # Step 1: Create test image and audio
        print("\n📌 Step 1: Create test image and audio")
        test_image_path = os.path.join(tmpdir, "test_image.png")
        create_test_image(test_image_path)

        original_audio = create_test_audio()
        original_audio_hash = hash_data(original_audio)
        print(f"   Audio size: {len(original_audio)} bytes")
        print(f"   Audio hash: {original_audio_hash[:16]}...")

        # Step 2: Create keypairs
        print("\n📌 Step 2: Create sender/receiver keypairs")
        sender_stellar = Keypair.random()
        receiver_stellar = Keypair.random()
        sender_kp = Stellar25519KeyPair(sender_stellar)
        receiver_kp = Stellar25519KeyPair(receiver_stellar)
        print(f"   Sender public: {sender_kp.public_key()[:16]}...")
        print(f"   Receiver public: {receiver_kp.public_key()[:16]}...")

        # Step 3: Create audio token and embed
        print("\n📌 Step 3: Create audio token and embed in image")
        try:
            token = create_audio_token(
                sender_kp=sender_kp,
                receiver_pub=receiver_kp.public_key(),
                audio_data=original_audio,
                filename="test_audio.wav",
                expires_in=3600
            )
            print(f"   Token created: {len(token)} chars")
        except Exception as e:
            print(f"   ❌ FAILED: Could not create audio token: {e}")
            return False

        # Embed token in image
        audio_image_path = os.path.join(tmpdir, "audio_token_image.png")
        result = embed_audio_token(test_image_path, token, audio_image_path)

        if not result or not os.path.exists(audio_image_path):
            print("   ❌ FAILED: Could not embed token")
            return False

        # Verify token is embedded
        has_audio, method = has_audio_data(audio_image_path)
        print(f"   Token embedded: {has_audio}, method: {method}")

        if not has_audio or method != "token":
            print("   ❌ FAILED: Token not detected in embedded image")
            return False

        # Step 4: Convert to aposematic
        print("\n📌 Step 4: Convert to aposematic")
        cipher_key = "test_cipher_key_1234567890abcdef"
        op_string = "-^+"

        try:
            aposematic_result = new_aposematic_img(
                audio_image_path,
                cipher_key=cipher_key,
                op_string=op_string,
                scramble_mode=SCRAMBLE_MODE.BUTTERFLY
            )
            aposematic_path = aposematic_result.get("img_path") if isinstance(aposematic_result, dict) else aposematic_result
            print(f"   Aposematic image: {aposematic_path}")
        except Exception as e:
            print(f"   ❌ FAILED: Could not create aposematic: {e}")
            return False

        # Step 5: Check if token survived aposematic conversion
        print("\n📌 Step 5: Check token in aposematic image")
        has_audio_apo, method_apo = has_audio_data(aposematic_path)
        print(f"   Token in aposematic: {has_audio_apo}, method: {method_apo}")

        if not has_audio_apo:
            print("   ❌ FAILED: Token LOST during aposematic conversion!")
            return False

        # Try to extract token
        apo_token = extract_audio_token(aposematic_path)
        if apo_token:
            print(f"   Token extractable: {len(apo_token)} chars")
            # Try to decrypt
            try:
                audio_bytes, metadata = extract_audio_from_token(receiver_kp, apo_token)
                if audio_bytes:
                    apo_audio_hash = hash_data(audio_bytes)
                    print(f"   Decrypted audio hash: {apo_audio_hash[:16]}...")
                    if apo_audio_hash == original_audio_hash:
                        print("   ✅ Token preserved and decryptable in aposematic")
                    else:
                        print("   ❌ FAILED: Decrypted audio doesn't match")
                        return False
                else:
                    print("   ❌ FAILED: Could not decrypt token from aposematic")
                    return False
            except Exception as e:
                print(f"   ❌ FAILED: Token decryption error: {e}")
                return False
        else:
            print("   ❌ FAILED: Could not extract token from aposematic")
            return False

        # Step 6: Recover from aposematic
        print("\n📌 Step 6: Recover from aposematic")
        try:
            recovered_result = recover_aposematic_img(
                aposematic_path,
                cipher_key=cipher_key,
                op_string=op_string
            )
            recovered_path = recovered_result.get("img_path") if isinstance(recovered_result, dict) else recovered_result
            print(f"   Recovered image: {recovered_path}")
        except Exception as e:
            print(f"   ❌ FAILED: Could not recover aposematic: {e}")
            return False

        # Step 7: Check if token survived recovery
        print("\n📌 Step 7: Check token in recovered image")
        has_audio_rec, method_rec = has_audio_data(recovered_path)
        print(f"   Token in recovered: {has_audio_rec}, method: {method_rec}")

        if has_audio_rec:
            rec_token = extract_audio_token(recovered_path)
            if rec_token:
                try:
                    rec_audio, rec_metadata = extract_audio_from_token(receiver_kp, rec_token)
                    if rec_audio:
                        rec_audio_hash = hash_data(rec_audio)
                        print(f"   Recovered audio hash: {rec_audio_hash[:16]}...")
                        if rec_audio_hash == original_audio_hash:
                            print("   ✅ Token preserved through full cycle!")
                        else:
                            print("   ❌ FAILED: Recovered audio doesn't match")
                            return False
                    else:
                        print("   ❌ FAILED: Could not decrypt token from recovered")
                        return False
                except Exception as e:
                    print(f"   ❌ FAILED: Token decryption error: {e}")
                    return False
            else:
                print("   ❌ FAILED: Could not extract token from recovered")
                return False
        else:
            print("   ❌ FAILED: Token LOST during recovery!")
            return False

        # Summary
        print("\n" + "="*60)
        print("TEST RESULT: ✅ PASSED")
        print("="*60)
        return True


def main():
    """Run all audio aposematic flow tests."""
    print("\n" + "#"*60)
    print("# AUDIO APOSEMATIC FLOW TEST SUITE")
    print("#"*60)

    results = {}

    # Test 1: Base64 method
    try:
        results["base64"] = run_test_base64_method()
    except Exception as e:
        print(f"\n❌ Base64 test crashed: {e}")
        import traceback
        traceback.print_exc()
        results["base64"] = False

    # Test 2: Token method
    try:
        results["token"] = run_test_token_method()
    except Exception as e:
        print(f"\n❌ Token test crashed: {e}")
        import traceback
        traceback.print_exc()
        results["token"] = False

    # Final summary
    print("\n" + "#"*60)
    print("# FINAL SUMMARY")
    print("#"*60)

    for test_name, result in results.items():
        if result is True:
            status = "✅ PASSED"
        elif result is False:
            status = "❌ FAILED"
        else:
            status = "⚠️ SKIPPED"
        print(f"  {test_name.upper()} method: {status}")

    # Return exit code
    if all(r is True for r in results.values() if r is not None):
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
