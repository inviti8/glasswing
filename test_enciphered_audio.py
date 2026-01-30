"""
Test: Enciphered Image Audio Preservation - Code Analysis

This test analyzes the code to identify bugs in the enciphered image flow.
It doesn't require ImageMagick/wand to run.

Key findings to verify:
1. ImageMagick encipher/decipher creates new image files (loses tEXt chunks)
2. data_pod_audio.py uses wrong image type check ('encrypted' vs 'enciphered')
3. Audio cannot be re-embedded into enciphered images (encryption would be corrupted)
"""

import os
import sys
import re

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_imagemagick_creates_new_file():
    """Verify that ImageMagick encipher/decipher creates new files."""
    print("\n" + "=" * 60)
    print("TEST 1: Does ImageMagick encipher/decipher create new files?")
    print("=" * 60)

    with open("img_edit.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Check new_enciphered_img
    if "img.save(filename=temp_path)" in content and "img.encipher(cipher_key)" in content:
        print("\n[OK] new_enciphered_img() creates a NEW file after encipher:")
        print("   - img.encipher(cipher_key)")
        print("   - img.save(filename=temp_path)")
        print("\n   [WARN] ImageMagick save() does NOT preserve PNG tEXt chunks!")
        print("   Audio embedded in tEXt chunks will be LOST.")
        encipher_new = True
    else:
        print("\n[?] Could not confirm new_enciphered_img() behavior")
        encipher_new = False

    # Check new_deciphered_img
    if "img.save(filename=temp_path)" in content and "img.decipher(cipher_key)" in content:
        print("\n[OK] new_deciphered_img() creates a NEW file after decipher:")
        print("   - img.decipher(cipher_key)")
        print("   - img.save(filename=temp_path)")
        print("\n   [WARN] Even if audio survived encryption, it's lost during decryption!")
        decipher_new = True
    else:
        print("\n[?] Could not confirm new_deciphered_img() behavior")
        decipher_new = False

    return encipher_new and decipher_new


def test_data_pod_image_type_check():
    """Test that data_pod_audio.py uses correct image type for enciphered."""
    print("\n" + "=" * 60)
    print("TEST 2: Data pod pre-extraction image type check")
    print("=" * 60)

    with open("data_pod_audio.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Find the pre-extraction condition
    match = re.search(r'image_type in \(["\']aposematic["\'],\s*["\'](\w+)["\']\)', content)

    if match:
        found_type = match.group(1)
        print(f"\n   Found condition: image_type in ('aposematic', '{found_type}')")

        if found_type == "encrypted":
            print("\n[BUG] BUG FOUND!")
            print("   The code uses 'encrypted' but the actual image type is 'enciphered'")
            print("   This means enciphered images will NOT have audio pre-extracted!")
            print("\n   Current:  image_type in ('aposematic', 'encrypted')")
            print("   Should be: image_type in ('aposematic', 'enciphered')")
            return False
        elif found_type == "enciphered":
            print("\n[OK] Code correctly uses 'enciphered' image type")
            return True
        else:
            print(f"\n[?] Unexpected type: {found_type}")
            return False
    else:
        print("\n[?] Could not find image type check pattern")
        # Try alternative pattern
        if '"encrypted"' in content and '"enciphered"' not in content.split("# ")[0]:
            print("   Found 'encrypted' in code but not 'enciphered' in pre-extraction")
            return False
        return None


def test_process_enciphering_audio_handling():
    """Test that process_enciphering() correctly handles audio."""
    print("\n" + "=" * 60)
    print("TEST 3: process_enciphering() audio handling")
    print("=" * 60)

    with open("main.py", "r", encoding="utf-8") as f:
        content = f.read()

    # Look for the skip pattern in process_enciphering
    if "Skipping audio re-embedding for enciphered image" in content:
        print("\n[OK] process_enciphering() correctly SKIPS audio re-embedding")
        print("   This is CORRECT because:")
        print("   - ImageMagick encipher() encrypts the entire image")
        print("   - Re-embedding audio would corrupt the encrypted data")
        print("   - Audio must be handled differently for enciphered images")
        return True
    else:
        print("\n[WARN] Could not confirm audio skip in process_enciphering()")
        return False


def test_image_type_consistency():
    """Check that 'enciphered' is used consistently throughout codebase."""
    print("\n" + "=" * 60)
    print("TEST 4: Image type consistency check")
    print("=" * 60)

    # Check main.py
    with open("main.py", "r", encoding="utf-8") as f:
        main_content = f.read()

    # Check data_pod_audio.py
    with open("data_pod_audio.py", "r", encoding="utf-8") as f:
        data_pod_content = f.read()

    # Find all occurrences
    main_encrypted = main_content.count('"encrypted"') + main_content.count("'encrypted'")
    main_enciphered = main_content.count('"enciphered"') + main_content.count("'enciphered'")

    data_encrypted = data_pod_content.count('"encrypted"') + data_pod_content.count("'encrypted'")
    data_enciphered = data_pod_content.count('"enciphered"') + data_pod_content.count("'enciphered'")

    print(f"\nmain.py:")
    print(f"   'encrypted' occurrences:  {main_encrypted}")
    print(f"   'enciphered' occurrences: {main_enciphered}")

    print(f"\ndata_pod_audio.py:")
    print(f"   'encrypted' occurrences:  {data_encrypted}")
    print(f"   'enciphered' occurrences: {data_enciphered}")

    # Check specific problematic areas
    issues = []

    # Check for any remaining "encrypted" in code logic (not comments or function names)
    # Look for patterns like: image_type == "encrypted" or in ("...", "encrypted")
    import re
    # Find all image_type checks with "encrypted"
    encrypted_checks = re.findall(r'image_type\s*(?:==|in\s*\([^)]*)"encrypted"', data_pod_content)
    if encrypted_checks:
        issues.append(f"Found {len(encrypted_checks)} image_type checks using 'encrypted' instead of 'enciphered'")

    if issues:
        print("\n[WARN] ISSUES FOUND:")
        for issue in issues:
            print(f"   - {issue}")
        return False
    else:
        print("\n[OK] No obvious type inconsistencies found")
        return True


def analyze_enciphered_audio_implications():
    """Analyze what happens to audio in enciphered images."""
    print("\n" + "=" * 60)
    print("ANALYSIS: Enciphered Images and Audio")
    print("=" * 60)

    print("""
FLOW ANALYSIS:

1. SOURCE IMAGE (with embedded audio)
   Audio stored in PNG tEXt chunks (audio_base64_* or audio_token_*)

2. ENCIPHERING (new_enciphered_img)
   - img.encipher(cipher_key) - encrypts pixel data
   - img.save(temp_path) - creates NEW PNG
   - [WARN] NEW PNG does NOT have original tEXt chunks!
   - Audio is LOST at this step

3. ENCIPHERED IMAGE (no audio)
   - Cannot re-embed audio (would corrupt encryption)

4. DECIPHERING (new_deciphered_img)
   - img.decipher(cipher_key) - decrypts pixel data
   - img.save(temp_path) - creates another NEW PNG
   - Even if audio somehow survived, it's lost here

CONCLUSION:
   Unlike aposematic images where we can re-embed audio after scrambling,
   enciphered images CANNOT preserve embedded audio because:

   a) ImageMagick encipher() encrypts the entire image data
   b) Re-embedding audio after encryption would corrupt the encrypted data
   c) The decryption would fail or produce garbage

SOLUTION OPTIONS:
   1. Store audio separately (not in the image)
   2. Store reference to original processed image for audio extraction
   3. Include decrypted audio in data pod (like token method does)
   4. Accept that enciphered images don't support embedded audio

CURRENT BUGS:
   1. data_pod_audio.py uses 'encrypted' instead of 'enciphered' for pre-extraction
   2. Even with correct type, pre-extraction happens on enciphered image which has NO audio
   3. The audio was already lost during process_enciphering()
""")


def main():
    print("=" * 60)
    print("ENCIPHERED IMAGE AUDIO PRESERVATION - CODE ANALYSIS")
    print("=" * 60)

    results = {}

    # Test 1: ImageMagick creates new files
    results["imagemagick_new_file"] = test_imagemagick_creates_new_file()

    # Test 2: Image type check bug
    results["type_check"] = test_data_pod_image_type_check()

    # Test 3: process_enciphering audio handling
    results["process_enciphering"] = test_process_enciphering_audio_handling()

    # Test 4: Type consistency
    results["type_consistency"] = test_image_type_consistency()

    # Analysis
    analyze_enciphered_audio_implications()

    # Final summary
    print("\n" + "=" * 60)
    print("BUGS IDENTIFIED")
    print("=" * 60)

    bugs = []

    # Bug 1: Type mismatch
    if results["type_check"] == False:
        bugs.append({
            "id": 1,
            "severity": "HIGH",
            "location": "data_pod_audio.py:411",
            "description": "Pre-extraction check uses 'encrypted' instead of 'enciphered'",
            "impact": "Enciphered images skip audio pre-extraction entirely",
            "fix": "Change 'encrypted' to 'enciphered' in the condition"
        })

    # Bug 2: Decryption type check
    if results["type_consistency"] == False:
        bugs.append({
            "id": 2,
            "severity": "HIGH",
            "location": "data_pod_audio.py:437",
            "description": "Decryption check uses 'encrypted' instead of 'enciphered'",
            "impact": "Enciphered images are not decrypted during data pod processing",
            "fix": "Change 'encrypted' to 'enciphered' in the condition"
        })

    # Bug 3: Fundamental issue - audio lost during enciphering
    bugs.append({
        "id": 3,
        "severity": "DESIGN",
        "location": "main.py:process_enciphering()",
        "description": "Audio is permanently lost when images are enciphered",
        "impact": "Enciphered images cannot have embedded audio",
        "fix": "Either accept this limitation or store audio separately"
    })

    if bugs:
        for bug in bugs:
            print(f"\nBUG #{bug['id']} [{bug['severity']}]")
            print(f"   Location: {bug['location']}")
            print(f"   Issue: {bug['description']}")
            print(f"   Impact: {bug['impact']}")
            print(f"   Fix: {bug['fix']}")
    else:
        print("\n[OK] No bugs found!")

    return bugs


if __name__ == "__main__":
    bugs = main()
