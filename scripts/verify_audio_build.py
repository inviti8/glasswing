#!/usr/bin/env python3
"""
Verify audio and video feature dependencies are correctly bundled.
Run this after building to ensure all media modules work.
"""

import sys
import os

# Add project root to Python path (parent of scripts/ directory)
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# ASCII-compatible status symbols for Windows compatibility
CHECK = '[OK]'
CROSS = '[X]'


def verify_audio_modules():
    """Verify all audio and video related modules can be imported."""
    print("Verifying media feature modules...\n")

    modules = [
        ('audio_tokens', 'Audio token creation/extraction'),
        ('video_tokens', 'Video token creation/extraction'),
        ('png_chunks', 'PNG tEXt chunk manipulation'),
        ('data_pod_audio', 'Data pod audio/video processing'),
        ('client_rendering', 'Client-side rendering'),
        ('dialogs', 'UI dialogs'),
        ('metadata', 'IPTC metadata handling'),
        ('img_edit', 'Image editing operations'),
        ('hvym_stellar', 'HVYM Stellar cryptography'),
        ('biscuit_auth', 'Biscuit token library'),
        ('nacl', 'NaCl cryptography (PyNaCl)'),
        ('task_runner', 'Non-blocking task execution'),
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
        import base64
        from hvym_stellar import HVYMDataToken, Stellar25519KeyPair
        from stellar_sdk import Keypair

        # Create test keypairs
        sender_kp = Keypair.random()
        receiver_kp = Keypair.random()

        sender_keys = Stellar25519KeyPair(sender_kp)

        # Get raw 32-byte public key and encode as base64 URL-safe string
        receiver_pub_bytes = receiver_kp.raw_public_key()
        receiver_pub_b64 = base64.urlsafe_b64encode(receiver_pub_bytes).decode('utf-8')

        # Create test token
        test_data = b"test audio data"
        token = HVYMDataToken.create_from_bytes(
            senderKeyPair=sender_keys,
            receiverPub=receiver_pub_b64,
            file_data=test_data,
            filename="test.wav",
            expires_in=None  # No expiry
        )

        print(f"  {CHECK} HVYMDataToken creation works")
        print(f"      Token length: {len(token.serialize())} chars")
        return True

    except Exception as e:
        print(f"  {CROSS} HVYMDataToken creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_png_chunks():
    """Verify PNG chunk operations work."""
    print("\nVerifying PNG chunk operations...")

    try:
        from png_chunks import (embed_audio_token, extract_audio_token,
                                embed_video_token_cid, extract_video_token_cid)
        from PIL import Image
        import tempfile

        # Create test image
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            test_img_path = f.name

        img = Image.new('RGB', (100, 100), color='red')
        img.save(test_img_path)

        all_ok = True

        # Test audio token embed/extract
        test_token = "test_serialized_token_data_here"
        audio_output = test_img_path.replace('.png', '_audio.png')
        embed_audio_token(test_img_path, test_token, audio_output)
        extracted_token = extract_audio_token(audio_output)

        if extracted_token == test_token:
            print(f"  {CHECK} PNG audio token embed/extract works")
        else:
            print(f"  {CROSS} PNG audio token extract mismatch")
            all_ok = False

        # Test video CID embed/extract
        test_cid = "QmTestCid1234567890abcdef"
        video_output = test_img_path.replace('.png', '_video.png')
        embed_video_token_cid(test_img_path, test_cid, video_output)
        extracted_cid = extract_video_token_cid(video_output)

        if extracted_cid == test_cid:
            print(f"  {CHECK} PNG video CID embed/extract works")
        else:
            print(f"  {CROSS} PNG video CID extract mismatch")
            all_ok = False

        # Cleanup
        for f in [test_img_path, audio_output, video_output]:
            if os.path.exists(f):
                os.unlink(f)

        return all_ok

    except Exception as e:
        print(f"  {CROSS} PNG chunk operations failed: {e}")
        return False


def main():
    print("=" * 50)
    print("Media Feature Build Verification")
    print("=" * 50 + "\n")

    results = []

    results.append(verify_audio_modules())
    results.append(verify_audio_token_creation())
    results.append(verify_png_chunks())

    print("\n" + "=" * 50)
    if all(results):
        print(f"{CHECK} All media feature verifications passed!")
        return 0
    else:
        print(f"{CROSS} Some verifications failed!")
        return 1


if __name__ == '__main__':
    sys.exit(main())
