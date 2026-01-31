"""
Data Pod Creation with Encrypted Audio Tokens

🎯 CRITICAL: This follows ENCRYPTION.md data pod pattern exactly:
- Include creator_public_key for subscriber's ECDH derivation
- Include recipient_public_key for authorization verification
- Use same metadata structure as image encryption
"""

import asyncio
import base64
import json
import os
import time
from datetime import datetime
from typing import Dict, Any, List, Optional

from nicegui import run

from audio_tokens import (
    get_user_keypair,
    get_user_public_key,
    extract_audio_from_token,
    detect_audio_format,
)
from png_chunks import extract_audio_token, extract_audio_base64, has_audio_data


def determine_image_type(img_hash: str, img_info: Dict[str, Any], app) -> str:
    """
    Determine the type of image for proper rendering

    Args:
        img_hash: Image hash
        img_info: Image information dictionary
        app: NiceGUI app instance

    Returns:
        str: Image type ('raw', 'processed', 'aposematic', 'enciphered')
    """
    # Check explicit type field
    if "image_type" in img_info:
        return img_info["image_type"]

    # Infer type from storage location
    storage_lists = [
        ("raw_img_hashes", "raw"),
        ("processed_img_hashes", "processed"),
        ("aposematic_img_hashes", "aposematic"),
        ("enciphered_img_hashes", "enciphered"),
    ]

    for list_name, type_name in storage_lists:
        if list_name in app.storage.user and img_hash in app.storage.user[list_name]:
            return type_name

    # Check processing flags
    if img_info.get("is_aposematic", False):
        return "aposematic"
    elif img_info.get("is_enciphered", False):
        return "enciphered"
    elif img_info.get("is_processed", False):
        return "processed"

    # Default to raw
    return "raw"


async def create_ninjs_data_pod_with_encrypted_tokens(
    app, prefix: str = "processed",
    receiver_public_key: Optional[str] = None,
    creator_public_key: Optional[str] = None  # NEW: Allow override for debug flow
) -> Optional[str]:
    """
    Create data pod with encrypted audio tokens (subscriber decrypts locally)

    🎯 CRITICAL: This follows ENCRYPTION.md data pod pattern exactly:
    - Include creator_public_key for subscriber's ECDH derivation
    - Include recipient_public_key for authorization verification
    - Use same metadata structure as image encryption

    Args:
        app: NiceGUI app instance
        prefix: Image prefix to process
        receiver_public_key: Subscriber's public key for token creation

    Returns:
        str: Path to created data pod
    """
    try:
        # Get all processed images
        processed_hashes = app.storage.user.get(f"{prefix}_img_hashes", [])
        if not processed_hashes:
            app.storage.user["notification"] = {
                "type": "warning",
                "message": "No processed images found",
            }
            return None

        # Create list to hold all news items
        data_items = []
        audio_token_images = []  # Track which images have audio tokens

        for img_hash in processed_hashes:
            try:
                img_info = app.storage.user.get(img_hash)
                if not img_info:
                    continue

                img_path = img_info.get("path")
                if not img_path or not os.path.exists(img_path):
                    continue

                # Determine image type for processing
                image_type = determine_image_type(img_hash, img_info, app)
                print(
                    f"📋 Image {img_info.get('name', 'Unknown')} detected as type: {image_type}"
                )

                # Get metadata using existing function
                try:
                    metadata_list = await app.get_img_metadata(img_path)
                    metadata = (
                        metadata_list[0]
                        if metadata_list and isinstance(metadata_list, list)
                        else {}
                    )
                except Exception as e:
                    print(f"Warning: Could not get metadata for {img_path}: {e}")
                    metadata = {}

                # CRITICAL: Determine image type for rendering
                image_type = determine_image_type(img_hash, img_info, app)

                # Build news item with type-specific rendering
                render_flag = img_info.get("render_metadata", True)
                has_audio = img_info.get("has_audio", False)
                audio_method = img_info.get("audio_method", "metadata")

                # Get IPFS gateway settings for full URLs
                ipfs_webui = app.storage.user.get("ipfs_webui", "127.0.0.1")
                ipfs_webui_port = app.storage.user.get("ipfs_webui_port", "8080")

                # Handle case where ipfs_webui might already include scheme
                if ipfs_webui.startswith("http://") or ipfs_webui.startswith(
                    "https://"
                ):
                    gateway_base = f"{ipfs_webui}:{ipfs_webui_port}"
                else:
                    gateway_base = f"http://{ipfs_webui}:{ipfs_webui_port}"

                # Use the existing cipher key from storage (already set during recreation)
                cipher_key = app.storage.user.get("cipher_key", "")

                item = {
                    "type": "audio_image" if has_audio else image_type,
                    "guid": f"urn:uuid:{img_hash}",
                    "version": "1",
                    "language": "en",
                    "pubstatus": "usable",
                    "title": img_info.get("name", "Unknown"),
                    "byline": metadata.get("By-line", ""),
                    "creditline": metadata.get("Credit", ""),
                    "copyright": metadata.get("Copyright Notice", ""),
                    "ednote": f"Type: {image_type}, Audio method: {audio_method}",
                    "renditions": [
                        {
                            "name": "original",
                            "href": f"{gateway_base}/ipfs/{img_hash}",  # Full URL for downloading
                            "mimetype": "image/png",
                            "width": metadata.get("ImageWidth", 0),
                            "height": metadata.get("ImageHeight", 0),
                        }
                    ],
                    # CRITICAL: Include image type for client-side rendering decisions
                    "imageType": image_type,
                    "hasAudio": has_audio,
                    "audioMethod": audio_method,
                    # For enciphered images, include original_hash so audio can be extracted
                    # (enciphered images lose audio during ImageMagick encryption)
                    "original_hash": img_info.get("original_hash"),
                }

                # For token-based audio, ensure receiver key is set for future decryption
                if has_audio and audio_method == "token":
                    if not receiver_public_key:
                        raise ValueError(
                            "Receiver public key required for token-based audio"
                        )

                    # Track that this image contains an audio token
                    audio_token_images.append(img_hash)

                    # Store receiver key for subscriber's reference
                    # Handle no-expiry tokens (None = permanent)
                    token_expires = img_info.get("audio_token_expires")
                    no_expiry = img_info.get("audio_token_no_expiry", token_expires is None)

                    item["audioTokenInfo"] = {
                        "receiverPublicKey": receiver_public_key,
                        "tokenExpiry": token_expires,  # None for no expiry
                        "noExpiry": no_expiry,
                    }

                if render_flag:
                    data_items.append(item)

            except Exception as e:
                print(f"Error processing {img_hash}: {e}")
                continue

        # Create NINJS package with encryption metadata (following ENCRYPTION.md pattern)
        ninjs_data = {
            "uri": f"urn:ninjs:v2:com.example.gallery:{prefix}",
            "version": "http://iptc.org/std/ninjs/2.1",
            "content_created": datetime.now().isoformat(),
            "items": data_items,
            # CRITICAL: Encryption metadata for subscriber decryption (per ENCRYPTION.md)
            "creator_public_key": creator_public_key or get_user_public_key(app),
            "recipient_public_key": receiver_public_key,  # Subscriber's key
            "content_type": "mixed",  # May contain original, aposematic, enciphered
            "audio_token_images": audio_token_images,  # NEW: Track token-based images
            # Include type distribution metadata
            "type_distribution": {
                "raw": len([i for i in data_items if i["imageType"] == "raw"]),
                "processed": len(
                    [i for i in data_items if i["imageType"] == "processed"]
                ),
                "aposematic": len(
                    [i for i in data_items if i["imageType"] == "aposematic"]
                ),
                "enciphered": len(
                    [i for i in data_items if i["imageType"] == "enciphered"]
                ),
                "total_with_audio": len(
                    [i for i in data_items if i.get("hasAudio", False)]
                ),
                "audio_token_count": len(audio_token_images),
            },
        }

        # Add aposematic/encryption parameters if present (per ENCRYPTION.md)
        if any(i["imageType"] == "aposematic" for i in data_items):
            ninjs_data["op_string"] = app.storage.user.get(
                "aposematic_op_string", "-^+"
            )
            ninjs_data["scramble_mode"] = app.storage.user.get(
                "aposematic_scramble_mode", 2
            )

        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(
            "exports", f"ninjs_data_pod_{prefix}_{timestamp}.json"
        )

        os.makedirs("exports", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ninjs_data, f, indent=2, ensure_ascii=False)

        app.storage.user["latest_data_pod_timestamp"] = timestamp
        print(f"Successfully created NINJS data pod with {len(data_items)} items")
        print(f"Audio token images: {len(audio_token_images)}")
        print(f"Type distribution: {ninjs_data['type_distribution']}")

        # Store success notification
        app.storage.user["notification"] = {
            "type": "success",
            "message": f"Created data pod with {len(data_items)} items",
        }

        return output_path

    except Exception as e:
        # Store error notification
        app.storage.user["notification"] = {
            "type": "error",
            "message": f"Error creating data pod: {str(e)}",
        }
        print(f"Error in create_ninjs_data_pod: {str(e)}")
        return None


async def process_data_pod_locally(
    data_pod_path: str, subscriber_stellar_secret: str, app,
    embed_images_as_base64: bool = False
) -> Dict[str, Any]:
    """
    Process downloaded data pod locally - decrypt images and audio tokens
    This runs on subscriber's machine following ENCRYPTION.md pattern

    🎯 CRITICAL: This follows ENCRYPTION.md browser-side decoding exactly:
    - Generate shared key using recipient_public_key from data pod
    - Use same StellarSharedKey ECDH derivation as image decryption
    - Process all content types (images + audio tokens) in unified pass
    - Optionally convert to base64 for offline rendering

    Args:
        data_pod_path: Path to downloaded data pod JSON file
        subscriber_stellar_secret: Subscriber's Stellar secret key
        app: NiceGUI app instance
        embed_images_as_base64: If True, embed images as base64 data URIs (for offline HTML).
                                If False, keep IPFS URLs (for local preview with IPFS running).
                                Default False to avoid large HTML files.

    Returns:
        dict: Processed data pod with decrypted content ready for rendering
    """
    try:
        # Load data pod
        with open(data_pod_path, "r") as f:
            data_pod = json.load(f)

        print(f"Processing data pod: {data_pod.get('uri', 'Unknown')}")
        print(f"Items to process: {len(data_pod.get('items', []))}")

        # Generate shared key (following ENCRYPTION.md exactly)
        recipient_public_key = data_pod.get("recipient_public_key")
        if not recipient_public_key:
            raise ValueError("Data pod missing recipient_public_key for decryption")

        # 🎯 CRITICAL: Use proper shared key derivation (hvym-stellar is now fixed!)
        # This will now generate consistent shared keys across instances

        print(
            f"🔐 Subscriber stellar secret (first 16): {subscriber_stellar_secret[:16]}..."
        )

        # Generate shared key using proper ECDH derivation
        from stellar_sdk.keypair import Keypair
        from hvym_stellar import StellarSharedKey, Stellar25519KeyPair

        # Create subscriber key pair
        stellar_kp = Keypair.from_secret(subscriber_stellar_secret)
        subscriber_keys = Stellar25519KeyPair(stellar_kp)

        # Get creator's public key from data pod
        creator_public_key = data_pod.get("creator_public_key")
        if not creator_public_key:
            raise ValueError("Data pod missing creator_public_key for decryption")

        # Generate shared key (now consistent across instances!)
        shared_key = StellarSharedKey(subscriber_keys, creator_public_key)
        cipher_key = shared_key.shared_secret().hex()  # Uses deterministic derivation

        print(
            f"🔐 Using debug secret + creator public key: {creator_public_key[:16]}..."
        )
        print(f"🔑 Generated cipher key (first 16 chars): {cipher_key[:16]}...")
        print(f"🔑 Creator public key: {creator_public_key[:16]}...")
        print(f"🔑 Subscriber public key: {subscriber_keys.public_key()[:16]}...")

        # Import required functions from main module
        import main

        download_ipfs_image = getattr(main, "download_ipfs_image", None)
        new_deciphered_img = getattr(main, "new_deciphered_img", None)
        recover_aposematic_img = getattr(main, "recover_aposematic_img", None)
        image_to_base64_uri = getattr(main, "image_to_base64_uri", None)
        ipfs_add = getattr(main, "ipfs_add", None)
        _ipfs_add_pure = getattr(main, "_ipfs_add_pure", None)  # Pure version for threading
        ipfs_webui = getattr(main, "ipfs_webui", "http://localhost")
        ipfs_webui_port = getattr(main, "ipfs_webui_port", "8080")

        # Construct gateway base URL for IPFS access (needed for downloading original images)
        if ipfs_webui.startswith("http://") or ipfs_webui.startswith("https://"):
            gateway_base = f"{ipfs_webui}:{ipfs_webui_port}"
        else:
            gateway_base = f"http://{ipfs_webui}:{ipfs_webui_port}"

        if not all(
            [
                download_ipfs_image,
                new_deciphered_img,
                recover_aposematic_img,
                image_to_base64_uri,
            ]
        ):
            raise ValueError(
                "Missing required image processing functions in main module"
            )

        # Process each item (unified processing of images + audio tokens)
        processed_items = []
        for item in data_pod.get("items", []):
            try:
                # Fix: renditions is a list, not a dictionary
                if not item.get("renditions") or len(item["renditions"]) == 0:
                    print(f"❌ No renditions found for item: {item.get('title')}")
                    continue

                rendition = item["renditions"][0]  # Get first rendition
                href = rendition.get("href")
                if not href:
                    print(
                        f"❌ No href found in rendition for item: {item.get('title')}"
                    )
                    continue

                # I/O-bound: Download IPFS image
                temp_path = await run.io_bound(download_ipfs_image, href)
                if not temp_path:
                    print(f"❌ Failed to download image from {href}")
                    continue

                # Check if downloaded file exists and get its size
                if os.path.exists(temp_path):
                    file_size = os.path.getsize(temp_path)
                    print(f"🔍 DEBUG: Downloaded file size: {file_size} bytes")
                    print(f"🔍 DEBUG: Downloaded file path: {temp_path}")
                    print(f"🔍 DEBUG: Original IPFS href: {href}")
                else:
                    print(f"❌ Downloaded file not found: {temp_path}")
                    continue

                # Decrypt image if needed (following ENCRYPTION.md patterns)
                image_type = item.get("imageType", "original")
                decoded_path = temp_path

                print(f"🔍 Processing image: {item.get('title')}, type: {image_type}")

                # 🎯 CRITICAL: Extract audio BEFORE decryption/recovery!
                # recover_aposematic_img() and new_deciphered_img() create NEW PNGs
                # that don't preserve tEXt chunks where audio is stored.
                # So we must extract audio from the aposematic/enciphered image first.
                pre_extracted_audio = None
                if item.get("hasAudio") and image_type in ("aposematic", "enciphered"):
                    print(f"🎵 Pre-extracting audio from {image_type} image before recovery...")

                    # For enciphered images, audio is lost during enciphering (ImageMagick limitation)
                    # We need to extract from the ORIGINAL processed image instead
                    if image_type == "enciphered":
                        original_hash = item.get("original_hash")
                        if original_hash:
                            print(f"🔍 Enciphered image - extracting audio from original: {original_hash[:16]}...")
                            try:
                                # I/O-bound: Download original processed image
                                original_href = f"{gateway_base}/ipfs/{original_hash}"
                                original_path = await run.io_bound(download_ipfs_image, original_href)
                                if original_path:
                                    has_audio, actual_method = has_audio_data(original_path)
                                    print(f"🔍 Audio check on original: has_audio={has_audio}, actual_method={actual_method}")

                                    if has_audio:
                                        if actual_method == "token" or item.get("audioMethod") == "token":
                                            serialized_token = extract_audio_token(original_path)
                                            if serialized_token:
                                                pre_extracted_audio = {
                                                    "type": "token",
                                                    "data": serialized_token
                                                }
                                                print(f"✅ Pre-extracted audio token from original ({len(serialized_token)} chars)")
                                        if not pre_extracted_audio and (actual_method == "base64" or has_audio):
                                            audio_base64 = extract_audio_base64(original_path)
                                            if audio_base64:
                                                pre_extracted_audio = {
                                                    "type": "base64",
                                                    "data": audio_base64
                                                }
                                                print(f"✅ Pre-extracted audio base64 from original ({len(audio_base64)} chars)")
                                    # Clean up temp file
                                    try:
                                        os.remove(original_path)
                                    except:
                                        pass
                            except Exception as e:
                                print(f"⚠️ Failed to extract audio from original image: {e}")
                        else:
                            print(f"⚠️ Enciphered image has no original_hash - cannot extract audio")
                    else:
                        # For aposematic images, audio is in the image itself (re-embedded after scramble)
                        try:
                            has_audio, actual_method = has_audio_data(temp_path)
                            print(f"🔍 Audio check on source: has_audio={has_audio}, actual_method={actual_method}")

                            if has_audio:
                                if actual_method == "token" or item.get("audioMethod") == "token":
                                    serialized_token = extract_audio_token(temp_path)
                                    if serialized_token:
                                        pre_extracted_audio = {
                                            "type": "token",
                                            "data": serialized_token
                                        }
                                        print(f"✅ Pre-extracted audio token ({len(serialized_token)} chars)")
                                if not pre_extracted_audio and (actual_method == "base64" or has_audio):
                                    audio_base64 = extract_audio_base64(temp_path)
                                    if audio_base64:
                                        pre_extracted_audio = {
                                            "type": "base64",
                                            "data": audio_base64
                                        }
                                        print(f"✅ Pre-extracted audio base64 ({len(audio_base64)} chars)")
                        except Exception as e:
                            print(f"⚠️ Pre-extraction of audio failed: {e}")

                if image_type == "enciphered":
                    print(f"🔓 Deciphering enciphered image: {item.get('title')}")
                    try:
                        # CPU-bound: deciphering is computationally intensive
                        decoded_path = await run.cpu_bound(
                            new_deciphered_img,
                            os.path.basename(temp_path),  # file_name
                            temp_path,  # encrypted_img_path
                            cipher_key,  # cipher_key
                        )
                        print(f"✅ Successfully deciphered image: {decoded_path}")
                    except Exception as e:
                        print(f"❌ Error deciphering image: {e}")
                        raise
                elif image_type == "aposematic":
                    print(f"🔓 Recovering aposematic image: {item.get('title')}")
                    try:
                        # 🎯 Uses same parameters as working main.py version
                        op_string = data_pod.get("op_string", "-^+")
                        print(f"🔍 DEBUG: Using op_string: '{op_string}'")
                        print(f"🔍 DEBUG: Cipher key: {cipher_key[:16]}...")
                        print(f"🔍 DEBUG: Temp path: {temp_path}")

                        # CPU-bound: aposematic recovery is computationally intensive
                        result = await run.cpu_bound(
                            recover_aposematic_img,
                            temp_path, cipher_key=cipher_key, op_string=op_string
                        )

                        print(f"🔍 DEBUG: Recovery result type: {type(result)}")
                        print(f"🔍 DEBUG: Recovery result: {result}")

                        # recover_aposematic_img returns a string path, not a dict
                        if isinstance(result, str):
                            decoded_path = result
                        else:
                            # Handle unexpected result types
                            print(f"❌ Unexpected recovery result type: {type(result)}")
                            decoded_path = str(result) if result else None

                        if not decoded_path:
                            print("❌ No decoded path returned from recovery")
                            raise ValueError("Failed to recover aposematic image")

                        print(
                            f"✅ Successfully recovered aposematic image: {decoded_path}"
                        )
                    except Exception as e:
                        print(f"❌ Error recovering aposematic image: {e}")
                        raise
                else:
                    print(f"ℹ️ Image type '{image_type}' - no decryption needed")

                # Extract/process audio if present
                if item.get("hasAudio"):
                    print(f"🎵 Processing audio for: {item.get('title')}")
                    audio_extracted = False

                    # 🎯 CRITICAL: Use pre-extracted audio for aposematic/encrypted images
                    # because recover_aposematic_img() and new_deciphered_img() don't preserve tEXt chunks
                    if pre_extracted_audio:
                        print(f"🎵 Using pre-extracted audio ({pre_extracted_audio['type']})")
                        try:
                            if pre_extracted_audio["type"] == "token":
                                # Decrypt the token
                                audio_bytes, metadata = extract_audio_from_token(
                                    subscriber_keys, pre_extracted_audio["data"], verify_hash=True
                                )

                                if audio_bytes:
                                    audio_base64 = base64.b64encode(audio_bytes).decode("ascii")
                                    audio_format = None
                                    if metadata:
                                        filename = metadata.get("filename", "")
                                        if filename and "." in filename:
                                            audio_format = filename.rsplit(".", 1)[-1].lower()
                                    if not audio_format:
                                        audio_format = detect_audio_format(audio_bytes)

                                    item["audio"] = {
                                        "data": audio_base64,
                                        "format": audio_format,
                                        "extractedAt": time.time(),
                                        "method": "token",
                                        "metadata": {
                                            "fileSize": metadata.get("size") if metadata else len(audio_bytes),
                                            "fileHash": metadata.get("hash") if metadata else None,
                                            "fileName": metadata.get("filename") if metadata else None,
                                            "verified": metadata is not None,
                                        },
                                    }
                                    print(f"✅ Audio decrypted from pre-extracted token ({len(audio_base64)} chars)")
                                    audio_extracted = True
                            else:
                                # Pre-extracted base64 audio
                                audio_base64 = pre_extracted_audio["data"]
                                audio_bytes = base64.b64decode(audio_base64)
                                audio_format = detect_audio_format(audio_bytes)

                                item["audio"] = {
                                    "data": audio_base64,
                                    "format": audio_format,
                                    "extractedAt": time.time(),
                                    "method": "metadata",
                                    "metadata": {
                                        "fileSize": len(audio_bytes),
                                        "verified": True,
                                    },
                                }
                                print(f"✅ Audio from pre-extracted base64 ({len(audio_base64)} chars)")
                                audio_extracted = True
                        except Exception as e:
                            print(f"⚠️ Pre-extracted audio processing failed: {e}")

                    # For non-aposematic/encrypted images, extract from decoded_path
                    if not audio_extracted:
                        has_audio, actual_method = has_audio_data(decoded_path)
                        print(f"🔍 Audio check on decoded: has_audio={has_audio}, actual_method={actual_method}")

                        # Try token extraction first if that's what we expect
                        if actual_method == "token" or item.get("audioMethod") == "token":
                            try:
                                serialized_token = extract_audio_token(decoded_path)
                                if serialized_token:
                                    audio_bytes, metadata = extract_audio_from_token(
                                        subscriber_keys, serialized_token, verify_hash=True
                                    )

                                    if audio_bytes:
                                        audio_base64 = base64.b64encode(audio_bytes).decode("ascii")
                                        audio_format = None
                                        if metadata:
                                            filename = metadata.get("filename", "")
                                            if filename and "." in filename:
                                                audio_format = filename.rsplit(".", 1)[-1].lower()
                                        if not audio_format:
                                            audio_format = detect_audio_format(audio_bytes)

                                        item["audio"] = {
                                            "data": audio_base64,
                                            "format": audio_format,
                                            "extractedAt": time.time(),
                                            "method": "token",
                                            "metadata": {
                                                "fileSize": metadata.get("size") if metadata else len(audio_bytes),
                                                "fileHash": metadata.get("hash") if metadata else None,
                                                "fileName": metadata.get("filename") if metadata else None,
                                                "verified": metadata is not None,
                                            },
                                        }
                                        print(f"✅ Audio extracted from token ({len(audio_base64)} chars)")
                                        audio_extracted = True
                            except Exception as e:
                                print(f"⚠️ Token extraction failed: {e}")

                        # Fallback: try base64/metadata extraction
                        if not audio_extracted and (actual_method == "base64" or has_audio):
                            try:
                                audio_base64 = extract_audio_base64(decoded_path)
                                if audio_base64:
                                    audio_bytes = base64.b64decode(audio_base64)
                                    audio_format = detect_audio_format(audio_bytes)

                                    item["audio"] = {
                                        "data": audio_base64,
                                        "format": audio_format,
                                        "extractedAt": time.time(),
                                        "method": "metadata",
                                        "metadata": {
                                            "fileSize": len(audio_bytes),
                                            "verified": True,
                                        },
                                    }
                                    print(f"✅ Audio extracted from metadata ({len(audio_base64)} chars)")
                                    audio_extracted = True
                            except Exception as e:
                                print(f"⚠️ Metadata extraction failed: {e}")

                    if not audio_extracted:
                        print(f"❌ No audio could be extracted from image")

                # Convert image to base64 for display (only if requested)
                # For local preview with IPFS running, skip this to avoid huge HTML files
                if embed_images_as_base64:
                    print(f"🖼️ Converting image to base64: {decoded_path}")
                    try:
                        base64_uri = image_to_base64_uri(decoded_path)
                        if base64_uri and base64_uri.startswith("data:image"):
                            # Fix: Update the correct rendition in the list
                            item["renditions"][0]["href"] = base64_uri
                            print(
                                f"✅ Successfully converted to base64 URI (length: {len(base64_uri)})"
                            )
                        else:
                            print(
                                f"❌ Invalid base64 URI generated: {base64_uri[:100] if base64_uri else 'None'}"
                            )
                            raise ValueError("Invalid base64 URI generated")
                    except Exception as e:
                        print(f"❌ Error converting image to base64: {e}")
                        raise
                else:
                    # For enciphered/aposematic images, make decrypted version accessible
                    if image_type in ("aposematic", "enciphered"):
                        try:
                            # I/O-bound: IPFS upload (use pure version for threading)
                            if _ipfs_add_pure:
                                decrypted_hash, _, _ = await run.io_bound(_ipfs_add_pure, decoded_path)
                                if decrypted_hash:
                                    gateway_base = f"{ipfs_webui}:{ipfs_webui_port}"
                                    item["renditions"][0]["href"] = f"{gateway_base}/ipfs/{decrypted_hash}"
                                    item["renditions"][0]["ipfs_hash"] = decrypted_hash
                                    item["renditions"][0]["decrypted"] = True
                                    print(f"✅ Updated href to decrypted IPFS: {decrypted_hash[:16]}...")
                                else:
                                    raise ValueError("_ipfs_add_pure returned None")
                            elif ipfs_add:
                                # Fallback to regular ipfs_add (blocking)
                                decrypted_hash = ipfs_add(decoded_path)
                                if decrypted_hash:
                                    gateway_base = f"{ipfs_webui}:{ipfs_webui_port}"
                                    item["renditions"][0]["href"] = f"{gateway_base}/ipfs/{decrypted_hash}"
                                    item["renditions"][0]["ipfs_hash"] = decrypted_hash
                                    item["renditions"][0]["decrypted"] = True
                                    print(f"✅ Updated href to decrypted IPFS: {decrypted_hash[:16]}...")
                                else:
                                    raise ValueError("ipfs_add returned None")
                            else:
                                raise ValueError("ipfs_add function not available")
                        except Exception as e:
                            print(f"⚠️ Failed to add decrypted image to IPFS: {e}")
                            # Fallback to base64
                            try:
                                base64_uri = image_to_base64_uri(decoded_path)
                                if base64_uri and base64_uri.startswith("data:image"):
                                    item["renditions"][0]["href"] = base64_uri
                                    print(f"⚠️ Using base64 fallback for decrypted image")
                                else:
                                    print(f"❌ Base64 fallback failed: {base64_uri[:100] if base64_uri else 'None'}")
                            except Exception as fallback_e:
                                print(f"❌ Base64 fallback error: {fallback_e}")
                                raise
                    else:
                        # Original images don't need decryption - keep IPFS URL
                        print(f"🖼️ Keeping IPFS URL for original image (embed_images_as_base64=False)")

                processed_items.append(item)
                print(f"✅ Processed item: {item.get('title')}")

                # Yield control to event loop for UI updates between items
                await asyncio.sleep(0)

            except Exception as e:
                print(f"❌ Error processing item {item.get('title', 'Unknown')}: {e}")
                continue

        # Update data pod with processed items
        data_pod["items"] = processed_items
        data_pod["processed_at"] = time.time()
        data_pod["processed_by"] = (
            subscriber_stellar_secret[:8] + "..."
        )  # Last 8 chars for ID

        print(f"✅ Data pod processing complete: {len(processed_items)} items ready")
        return data_pod

    except Exception as e:
        print(f"❌ Critical error processing data pod: {e}")
        raise


def create_test_data_pod(app, receiver_public_key: str) -> Optional[str]:
    """
    Create a test data pod for development/testing

    Args:
        app: NiceGUI app instance
        receiver_public_key: Test receiver public key

    Returns:
        str: Path to created test data pod
    """
    try:
        # Create test data with audio tokens
        test_items = [
            {
                "type": "raw_image",
                "guid": "urn:uuid:test-raw-001",
                "version": "1",
                "language": "en",
                "pubstatus": "usable",
                "title": "Test Raw Image with Audio",
                "byline": "Test Creator",
                "creditline": "Test Credit",
                "copyright": "Test Copyright",
                "ednote": "Type: raw, Audio method: token",
                "renditions": [
                    {
                        "name": "original",
                        "href": "/ipfs/test-raw-001",
                        "mimetype": "image/png",
                        "width": 800,
                        "height": 600,
                    }
                ],
                "imageType": "raw",
                "hasAudio": True,
                "audioMethod": "token",
                "audioTokenInfo": {
                    "receiverPublicKey": receiver_public_key,
                    "tokenExpiry": time.time() + 3600,
                },
            },
            {
                "type": "aposematic_image",
                "guid": "urn:uuid:test-aposematic-001",
                "version": "1",
                "language": "en",
                "pubstatus": "usable",
                "title": "Test Aposematic Image",
                "byline": "Test Creator",
                "creditline": "Test Credit",
                "copyright": "Test Copyright",
                "ednote": "Type: aposematic, Audio method: metadata",
                "renditions": [
                    {
                        "name": "original",
                        "href": "/ipfs/test-aposematic-001",
                        "mimetype": "image/png",
                        "width": 800,
                        "height": 600,
                    }
                ],
                "imageType": "aposematic",
                "hasAudio": False,
                "audioMethod": "metadata",
            },
        ]

        # Create test data pod
        test_data_pod = {
            "uri": "urn:ninjs:v2:com.example.gallery:test",
            "version": "http://iptc.org/std/ninjs/2.1",
            "content_created": datetime.now().isoformat(),
            "items": test_items,
            "creator_public_key": get_user_public_key(app),
            "recipient_public_key": receiver_public_key,
            "content_type": "mixed",
            "audio_token_images": ["test-raw-001"],
            "op_string": "-^+",
            "scramble_mode": 2,
            "type_distribution": {
                "raw": 1,
                "processed": 0,
                "aposematic": 1,
                "enciphered": 0,
                "total_with_audio": 1,
                "audio_token_count": 1,
            },
        }

        # Save test data pod
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join("exports", f"test_data_pod_{timestamp}.json")

        os.makedirs("exports", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(test_data_pod, f, indent=2, ensure_ascii=False)

        print(f"✅ Created test data pod: {output_path}")
        return output_path

    except Exception as e:
        print(f"❌ Error creating test data pod: {e}")
        return None
