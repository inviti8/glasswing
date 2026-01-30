#!/usr/bin/env python3
"""
Verify audio feature dependencies are correctly bundled.
Run this after building to ensure all audio modules work.
"""

import sys
import os

# ASCII-compatible status symbols for Windows compatibility
CHECK = '[OK]'
CROSS = '[X]'


def verify_audio_modules():
    """Verify all audio-related modules can be imported."""
    print("Verifying audio feature modules...\n")

    modules = [
        ('audio_tokens', 'Audio token creation/extraction'),
        ('png_chunks', 'PNG tEXt chunk manipulation'),
        ('data_pod_audio', 'Data pod audio processing'),
        ('hvym_stellar', 'HVYM Stellar cryptography'),
        ('biscuit_auth', 'Biscuit token library'),
        ('pynacl', 'NaCl cryptography'),
    ]

    all_ok = True
    for module, description in modules:
        try:
            __import__(module)
            print(f"  {CHECK} {module} - {description}")
        except ImportError as e:
            print(f"  {CROSS} {module} - {description}")
            print(f"      Error: {e}")
            all_ok = False

    return all_ok


def verify_audio_token_creation():
    """Verify HVYMDataToken can be created."""
    print("\nVerifying HVYMDataToken creation...")

    try:
        from hvym_stellar import HVYMDataToken, Stellar25519KeyPair
        from stellar_sdk import Keypair

        # Create test keypairs
        sender_kp = Keypair.random()
        receiver_kp = Keypair.random()

        sender_keys = Stellar25519KeyPair(sender_kp)

        # Create test token
        test_data = b"test audio data"
        token = HVYMDataToken.create_from_bytes(
            senderKeyPair=sender_keys,
            receiverPub=receiver_kp.public_key,
            file_data=test_data,
            filename="test.wav",
            expires_in=None  # No expiry
        )

        print(f"  {CHECK} HVYMDataToken creation works")
        print(f"      Token length: {len(token.serialize())} chars")
        return True

    except Exception as e:
        print(f"  {CROSS} HVYMDataToken creation failed: {e}")
        return False


def verify_png_chunks():
    """Verify PNG chunk operations work."""
    print("\nVerifying PNG chunk operations...")

    try:
        from png_chunks import embed_audio_base64, extract_audio_base64
        from PIL import Image
        import tempfile

        # Create test image
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            test_img_path = f.name

        img = Image.new('RGB', (100, 100), color='red')
        img.save(test_img_path)

        # Test embedding
        test_audio = "dGVzdCBhdWRpbyBkYXRh"  # base64 of "test audio data"
        output_path = test_img_path.replace('.png', '_audio.png')

        embed_audio_base64(test_img_path, test_audio, output_path)

        # Test extraction
        extracted = extract_audio_base64(output_path)

        # Cleanup
        os.unlink(test_img_path)
        if os.path.exists(output_path):
            os.unlink(output_path)

        if extracted == test_audio:
            print(f"  {CHECK} PNG chunk embed/extract works")
            return True
        else:
            print(f"  {CROSS} PNG chunk extract mismatch")
            return False

    except Exception as e:
        print(f"  {CROSS} PNG chunk operations failed: {e}")
        return False


def main():
    print("=" * 50)
    print("Audio Feature Build Verification")
    print("=" * 50 + "\n")

    results = []

    results.append(verify_audio_modules())
    results.append(verify_audio_token_creation())
    results.append(verify_png_chunks())

    print("\n" + "=" * 50)
    if all(results):
        print(f"{CHECK} All audio feature verifications passed!")
        return 0
    else:
        print(f"{CROSS} Some verifications failed!")
        return 1


if __name__ == '__main__':
    sys.exit(main())
