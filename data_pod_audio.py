"""
Data Pod Creation with Encrypted Audio Tokens

[INFO] CRITICAL: This follows ENCRYPTION.md data pod pattern exactly:
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
from video_tokens import (
    extract_video_from_token,
    detect_video_format,
)
from png_chunks import extract_audio_token, has_audio_data, extract_video_token_cid, extract_markdown_token
from markdown_tokens import extract_markdown_from_token, _unbundle_markdown_payload


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

    [INFO] CRITICAL: This follows ENCRYPTION.md data pod pattern exactly:
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
        # Guard: only allow publishing protected content types
        if prefix in ("raw", "processed"):
            app.storage.user["notification"] = {
                "type": "warning",
                "message": "Cannot publish unprotected content. Apply aposematic or encipher protection first.",
            }
            return None

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
        video_token_images = []  # Track which images have video tokens
        markdown_token_images = []  # Track which images have markdown tokens

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
                    f"[INFO] Image {img_info.get('name', 'Unknown')} detected as type: {image_type}"
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
                audio_method = img_info.get("audio_method", "token")
                has_video = img_info.get("has_video", False)
                video_method = img_info.get("video_method", "token") if has_video else None
                has_markdown = img_info.get("has_markdown", False)
                markdown_method = img_info.get("markdown_method", "token") if has_markdown else None

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

                # Determine item type: video > audio > markdown > picture
                if has_video:
                    item_type = "video_image"
                elif has_audio:
                    item_type = "audio_image"
                elif has_markdown:
                    item_type = "markdown_image"
                else:
                    item_type = image_type

                item = {
                    "type": item_type,
                    "guid": f"urn:uuid:{img_hash}",
                    "version": "1",
                    "language": "en",
                    "pubstatus": "usable",
                    "title": img_info.get("name", "Unknown"),
                    "byline": metadata.get("By-line", ""),
                    "creditline": metadata.get("Credit", ""),
                    "copyright": metadata.get("Copyright Notice", ""),
                    "ednote": f"Type: {image_type}, Audio: {audio_method}, Video: {video_method}",
                    "renditions": [
                        {
                            "name": "original",
                            "href": f"{gateway_base}/ipfs/{img_hash}",
                            "mimetype": "image/png",
                            "width": metadata.get("ImageWidth", 0),
                            "height": metadata.get("ImageHeight", 0),
                        }
                    ],
                    "imageType": image_type,
                    "hasAudio": has_audio,
                    "audioMethod": audio_method,
                    "hasVideo": has_video,
                    "videoMethod": video_method,
                    "hasMarkdown": has_markdown,
                    "markdownMethod": markdown_method,
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

                # For video token images, include CID and token info
                if has_video and video_method == "token":
                    if not receiver_public_key:
                        raise ValueError(
                            "Receiver public key required for token-based video"
                        )

                    video_token_images.append(img_hash)

                    video_token_cid = img_info.get("video_token_cid")
                    video_token_expires = img_info.get("video_token_expires")
                    video_no_expiry = img_info.get(
                        "video_token_no_expiry", video_token_expires is None
                    )

                    item["videoTokenCid"] = video_token_cid
                    item["videoTokenInfo"] = {
                        "receiverPublicKey": receiver_public_key,
                        "tokenExpiry": video_token_expires,
                        "noExpiry": video_no_expiry,
                    }

                # For markdown token images, extract serialized token and include in data pod
                # NOTE: Markdown tokens are stored in the data pod JSON (not reembedded
                # into aposematic/enciphered images) because extra tEXt chunks can
                # interfere with pixel-based recovery algorithms.
                if has_markdown and markdown_method == "token":
                    if not receiver_public_key:
                        raise ValueError(
                            "Receiver public key required for token-based markdown"
                        )

                    markdown_token_images.append(img_hash)

                    markdown_token_expires = img_info.get("markdown_token_expires")
                    markdown_no_expiry = img_info.get(
                        "markdown_token_no_expiry", markdown_token_expires is None
                    )

                    item["markdownTokenInfo"] = {
                        "receiverPublicKey": receiver_public_key,
                        "tokenExpiry": markdown_token_expires,
                        "noExpiry": markdown_no_expiry,
                    }
                    item["markdownFiles"] = img_info.get("markdown_files", [])

                    # Extract the serialized token from the source image and store
                    # in the data pod so subscribers can decrypt without needing
                    # the token embedded in the (possibly recovered) image.
                    # NOTE: Markdown chunks are NOT reembedded into aposematic/enciphered
                    # images, so we may need to fall back to the original processed image.
                    try:
                        serialized_md_token = extract_markdown_token(img_path)
                        if not serialized_md_token:
                            # Aposematic/enciphered images don't have markdown chunks —
                            # extract from the original processed image instead
                            original_hash = img_info.get("original_hash")
                            if original_hash:
                                original_info = app.storage.user.get(original_hash, {})
                                original_path = original_info.get("path")
                                if original_path and os.path.exists(original_path):
                                    serialized_md_token = extract_markdown_token(original_path)
                                    if serialized_md_token:
                                        print(f"[MARKDOWN] Extracted token from original image ({original_hash[:16]}...)")
                        if serialized_md_token:
                            item["markdownToken"] = serialized_md_token
                            print(f"[MARKDOWN] Stored serialized token in data pod ({len(serialized_md_token)} chars)")
                        else:
                            print(f"[WARN] No markdown token found in image or original")
                    except Exception as e:
                        print(f"[WARN] Could not extract markdown token from {img_path}: {e}")

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
            "audio_token_images": audio_token_images,
            "video_token_images": video_token_images,
            "markdown_token_images": markdown_token_images,
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
                "total_with_video": len(
                    [i for i in data_items if i.get("hasVideo", False)]
                ),
                "total_with_markdown": len(
                    [i for i in data_items if i.get("hasMarkdown", False)]
                ),
                "audio_token_count": len(audio_token_images),
                "video_token_count": len(video_token_images),
                "markdown_token_count": len(markdown_token_images),
            },
        }

        # Add aposematic/encryption parameters if present (per ENCRYPTION.md)
        if any(i["imageType"] == "aposematic" for i in data_items):
            ninjs_data["op_string"] = app.storage.user.get(
                "op_string", "-^+"
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
        print(f"Video token images: {len(video_token_images)}")
        print(f"Markdown token images: {len(markdown_token_images)}")
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
    embed_images_as_base64: bool = False,
    # Required functions passed from main to avoid circular import
    download_ipfs_image=None,
    new_deciphered_img=None,
    recover_aposematic_img=None,
    image_to_base64_uri=None,
    ipfs_add=None,
    _ipfs_add_pure=None,
    _ipfs_load_to_temp_file_pure=None,
    ipfs_webui="http://localhost",
    ipfs_webui_port="8080",
    video_temp_dir=None,
) -> Dict[str, Any]:
    """
    Process downloaded data pod locally - decrypt images, audio tokens, and video tokens.
    This runs on subscriber's machine following ENCRYPTION.md pattern.

    Args:
        data_pod_path: Path to downloaded data pod JSON file
        subscriber_stellar_secret: Subscriber's Stellar secret key
        app: NiceGUI app instance
        embed_images_as_base64: If True, embed images as base64 data URIs (for offline HTML).
                                If False, keep IPFS URLs (for local preview with IPFS running).
        download_ipfs_image: Function to download image from IPFS
        new_deciphered_img: Function to decipher encrypted images
        recover_aposematic_img: Function to recover aposematic images
        image_to_base64_uri: Function to convert image to base64 URI
        ipfs_add: Function to add file to IPFS
        _ipfs_add_pure: Pure version for threading
        _ipfs_load_to_temp_file_pure: Function to load IPFS content to temp file (for video tokens)
        ipfs_webui: IPFS gateway host
        ipfs_webui_port: IPFS gateway port
        video_temp_dir: Directory to write decrypted video files for serving

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

        # [INFO] CRITICAL: Use proper shared key derivation (hvym-stellar is now fixed!)
        # This will now generate consistent shared keys across instances

        print(
            f"[DEBUG] Subscriber stellar secret (first 16): {subscriber_stellar_secret[:16]}..."
        )

        # Generate keys using proper ECDH derivation
        from stellar_sdk.keypair import Keypair
        from hvym_stellar import StellarSharedKey, Stellar25519KeyPair

        # Create subscriber key pair
        stellar_kp = Keypair.from_secret(subscriber_stellar_secret)
        subscriber_keys = Stellar25519KeyPair(stellar_kp)

        # Get creator's public key from data pod
        creator_public_key = data_pod.get("creator_public_key")
        if not creator_public_key:
            raise ValueError("Data pod missing creator_public_key for decryption")

        # For encrypted (non-aposematic) images, derive cipher_key manually
        shared_key = StellarSharedKey(subscriber_keys, creator_public_key)
        cipher_key = shared_key.shared_secret().hex()  # Used only for enciphered images

        print(f"[KEY] Creator public key: {creator_public_key[:16]}...")
        print(f"[KEY] Subscriber public key: {subscriber_keys.public_key()[:16]}...")

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
                    print(f"[ERROR] No renditions found for item: {item.get('title')}")
                    continue

                rendition = item["renditions"][0]  # Get first rendition
                href = rendition.get("href")
                if not href:
                    print(
                        f"[ERROR] No href found in rendition for item: {item.get('title')}"
                    )
                    continue

                # I/O-bound: Download IPFS image
                temp_path = await run.io_bound(download_ipfs_image, href)
                if not temp_path:
                    print(f"[ERROR] Failed to download image from {href}")
                    continue

                # Check if downloaded file exists and get its size
                if os.path.exists(temp_path):
                    file_size = os.path.getsize(temp_path)
                    print(f"[DEBUG] DEBUG: Downloaded file size: {file_size} bytes")
                    print(f"[DEBUG] DEBUG: Downloaded file path: {temp_path}")
                    print(f"[DEBUG] DEBUG: Original IPFS href: {href}")
                else:
                    print(f"[ERROR] Downloaded file not found: {temp_path}")
                    continue

                # Decrypt image if needed (following ENCRYPTION.md patterns)
                image_type = item.get("imageType", "original")
                decoded_path = temp_path

                print(f"[DEBUG] Processing image: {item.get('title')}, type: {image_type}")

                # [INFO] CRITICAL: Extract audio BEFORE decryption/recovery!
                # recover_aposematic_img() and new_deciphered_img() create NEW PNGs
                # that don't preserve tEXt chunks where audio is stored.
                # So we must extract audio from the aposematic/enciphered image first.
                pre_extracted_audio = None
                if item.get("hasAudio") and image_type in ("aposematic", "enciphered"):
                    print(f"[AUDIO] Pre-extracting audio from {image_type} image before recovery...")

                    # For enciphered images, audio is lost during enciphering (ImageMagick limitation)
                    # We need to extract from the ORIGINAL processed image instead
                    if image_type == "enciphered":
                        original_hash = item.get("original_hash")
                        if original_hash:
                            print(f"[DEBUG] Enciphered image - extracting audio token from original: {original_hash[:16]}...")
                            try:
                                # I/O-bound: Download original processed image
                                original_href = f"{gateway_base}/ipfs/{original_hash}"
                                original_path = await run.io_bound(download_ipfs_image, original_href)
                                if original_path:
                                    serialized_token = extract_audio_token(original_path)
                                    if serialized_token:
                                        pre_extracted_audio = {
                                            "type": "token",
                                            "data": serialized_token
                                        }
                                        print(f"[OK] Pre-extracted audio token from original ({len(serialized_token)} chars)")
                                    # Clean up temp file
                                    try:
                                        os.remove(original_path)
                                    except:
                                        pass
                            except Exception as e:
                                print(f"[WARN] Failed to extract audio from original image: {e}")
                        else:
                            print(f"[WARN] Enciphered image has no original_hash - cannot extract audio")
                    else:
                        # For aposematic images, audio token is in the image itself
                        try:
                            serialized_token = extract_audio_token(temp_path)
                            if serialized_token:
                                pre_extracted_audio = {
                                    "type": "token",
                                    "data": serialized_token
                                }
                                print(f"[OK] Pre-extracted audio token ({len(serialized_token)} chars)")
                        except Exception as e:
                            print(f"[WARN] Pre-extraction of audio failed: {e}")

                # [INFO] CRITICAL: Pre-extract video CID BEFORE recovery!
                # Video CID is stored in tEXt chunks which are lost during recovery.
                # Try data pod metadata first (most reliable), then fall back to PNG extraction.
                pre_extracted_video_cid = item.get("videoTokenCid")
                if pre_extracted_video_cid:
                    print(f"[VIDEO] CID from data pod metadata: {pre_extracted_video_cid[:20]}...")
                elif item.get("hasVideo") and image_type in ("aposematic", "enciphered"):
                    print(f"[VIDEO] Pre-extracting video CID from {image_type} image before recovery...")
                    if image_type == "enciphered":
                        original_hash = item.get("original_hash")
                        if original_hash:
                            try:
                                original_href = f"{gateway_base}/ipfs/{original_hash}"
                                original_path = await run.io_bound(download_ipfs_image, original_href)
                                if original_path:
                                    pre_extracted_video_cid = extract_video_token_cid(original_path)
                                    if pre_extracted_video_cid:
                                        print(f"[OK] Pre-extracted video CID from original: {pre_extracted_video_cid[:20]}...")
                                    try:
                                        os.remove(original_path)
                                    except:
                                        pass
                            except Exception as e:
                                print(f"[WARN] Failed to extract video CID from original: {e}")
                    else:
                        try:
                            pre_extracted_video_cid = extract_video_token_cid(temp_path)
                            if pre_extracted_video_cid:
                                print(f"[OK] Pre-extracted video CID ({pre_extracted_video_cid[:20]}...)")
                        except Exception as e:
                            print(f"[WARN] Pre-extraction of video CID failed: {e}")

                # Markdown tokens are stored in the data pod JSON (not in PNG chunks)
                # so no pre-extraction from the image is needed.
                pre_extracted_markdown = None
                if item.get("hasMarkdown") and item.get("markdownToken"):
                    pre_extracted_markdown = {
                        "type": "token",
                        "data": item["markdownToken"]
                    }
                    print(f"[MARKDOWN] Using token from data pod JSON ({len(item['markdownToken'])} chars)")

                if image_type == "enciphered":
                    print(f"[UNLOCK] Deciphering enciphered image: {item.get('title')}")
                    try:
                        # CPU-bound: deciphering is computationally intensive
                        decoded_path = await run.cpu_bound(
                            new_deciphered_img,
                            os.path.basename(temp_path),  # file_name
                            temp_path,  # encrypted_img_path
                            cipher_key,  # cipher_key
                        )
                        print(f"[OK] Successfully deciphered image: {decoded_path}")
                    except Exception as e:
                        print(f"[ERROR] Error deciphering image: {e}")
                        raise
                elif image_type == "aposematic":
                    print(f"[UNLOCK] Recovering aposematic image: {item.get('title')}")
                    try:
                        # [INFO] Uses aiposematic v1.1 native Stellar key derivation
                        # recover_aposematic_img auto-detects scramble_mode from the image
                        op_string = data_pod.get("op_string", "-^+")

                        # CPU-bound: aposematic recovery is computationally intensive
                        result = await run.cpu_bound(
                            recover_aposematic_img,
                            temp_path,
                            stellar_keypair=subscriber_keys,
                            artist_public_key=creator_public_key,
                            op_string=op_string,
                        )

                        # recover_aposematic_img returns a string path, not a dict
                        if isinstance(result, str):
                            decoded_path = result
                        else:
                            # Handle unexpected result types
                            print(f"[ERROR] Unexpected recovery result type: {type(result)}")
                            decoded_path = str(result) if result else None

                        if not decoded_path:
                            print("[ERROR] No decoded path returned from recovery")
                            raise ValueError("Failed to recover aposematic image")

                        print(
                            f"[OK] Successfully recovered aposematic image: {decoded_path}"
                        )
                    except Exception as e:
                        print(f"[ERROR] Error recovering aposematic image: {e}")
                        raise
                else:
                    print(f"[INFO] Image type '{image_type}' - no decryption needed")

                # Extract/process audio if present
                if item.get("hasAudio"):
                    print(f"[AUDIO] Processing audio for: {item.get('title')}")
                    audio_extracted = False

                    # [INFO] CRITICAL: Use pre-extracted audio for aposematic/encrypted images
                    # because recover_aposematic_img() and new_deciphered_img() don't preserve tEXt chunks
                    if pre_extracted_audio:
                        print(f"[AUDIO] Using pre-extracted audio ({pre_extracted_audio['type']})")
                        try:
                            # Decrypt the pre-extracted token
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
                                print(f"[OK] Audio decrypted from pre-extracted token ({len(audio_base64)} chars)")
                                audio_extracted = True
                        except Exception as e:
                            print(f"[WARN] Pre-extracted audio processing failed: {e}")

                    # For non-aposematic/encrypted images, extract token from decoded_path
                    if not audio_extracted:
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
                                    print(f"[OK] Audio extracted from token ({len(audio_base64)} chars)")
                                    audio_extracted = True
                        except Exception as e:
                            print(f"[WARN] Token extraction failed: {e}")

                    if not audio_extracted:
                        print(f"[ERROR] No audio could be extracted from image")

                # Extract/process video if present
                if item.get("hasVideo"):
                    print(f"[VIDEO] Processing video for: {item.get('title')}")
                    video_extracted = False

                    # Get CID from pre-extraction or data pod metadata or decoded image
                    video_cid = pre_extracted_video_cid if pre_extracted_video_cid else None
                    if not video_cid:
                        video_cid = item.get("videoTokenCid")
                    if not video_cid:
                        try:
                            video_cid = extract_video_token_cid(decoded_path)
                        except Exception:
                            pass

                    if video_cid and _ipfs_load_to_temp_file_pure:
                        try:
                            print(f"[VIDEO] Fetching video token from IPFS: {video_cid[:20]}...")
                            # Fetch serialized token from IPFS
                            token_temp_path = await run.io_bound(
                                _ipfs_load_to_temp_file_pure, video_cid, "video_token.bin",
                                ipfs_webui, ipfs_webui_port
                            )
                            if token_temp_path:
                                with open(token_temp_path, 'r') as vf:
                                    serialized_token = vf.read()
                                # Clean up token temp file
                                try:
                                    os.remove(token_temp_path)
                                    token_dir = os.path.dirname(token_temp_path)
                                    if token_dir and os.path.isdir(token_dir):
                                        os.rmdir(token_dir)
                                except OSError:
                                    pass

                                # Decrypt video token
                                video_bytes, video_metadata = extract_video_from_token(
                                    subscriber_keys, serialized_token, verify_hash=True
                                )

                                if video_bytes:
                                    # Detect format
                                    video_format = None
                                    if video_metadata:
                                        vfn = video_metadata.get("filename", "")
                                        if vfn and "." in vfn:
                                            video_format = vfn.rsplit(".", 1)[-1].lower()
                                    if not video_format:
                                        video_format = detect_video_format(video_bytes)
                                    if not video_format or video_format == 'unknown':
                                        video_format = 'mp4'

                                    # Write decrypted video to temp file for serving
                                    import uuid
                                    vid_filename = f"video_{uuid.uuid4().hex[:12]}.{video_format}"
                                    if video_temp_dir and os.path.isdir(video_temp_dir):
                                        vid_path = os.path.join(video_temp_dir, vid_filename)
                                    else:
                                        import tempfile as _tf
                                        vid_path = os.path.join(_tf.gettempdir(), vid_filename)

                                    with open(vid_path, 'wb') as vf:
                                        vf.write(video_bytes)

                                    # Build served URL if video is in the editor temp dir
                                    video_served_url = f"/editor/{vid_filename}" if video_temp_dir else vid_path

                                    item["video"] = {
                                        "src": video_served_url,
                                        "localPath": vid_path,
                                        "filename": vid_filename,
                                        "format": video_format,
                                        "method": "token",
                                        "metadata": {
                                            "fileSize": video_metadata.get("size") if video_metadata else len(video_bytes),
                                            "fileHash": video_metadata.get("hash") if video_metadata else None,
                                            "fileName": video_metadata.get("filename") if video_metadata else None,
                                            "verified": video_metadata is not None,
                                        },
                                    }
                                    print(f"[OK] Video decrypted ({len(video_bytes)} bytes) -> {vid_path}")
                                    video_extracted = True
                                else:
                                    print(f"[ERROR] Failed to decrypt video token")
                            else:
                                print(f"[ERROR] Failed to fetch video token from IPFS: {video_cid}")
                        except Exception as e:
                            print(f"[WARN] Video token extraction failed: {e}")

                    if not video_extracted:
                        if not video_cid:
                            print(f"[ERROR] No video CID found for image")
                        elif not _ipfs_load_to_temp_file_pure:
                            print(f"[ERROR] IPFS load function not available for video token fetch")

                # Extract/process markdown if present
                if item.get("hasMarkdown"):
                    print(f"[MARKDOWN] Processing markdown for: {item.get('title')}")
                    markdown_extracted = False

                    # Use pre-extracted markdown for aposematic/encrypted images
                    if pre_extracted_markdown:
                        print(f"[MARKDOWN] Using pre-extracted markdown ({pre_extracted_markdown['type']})")
                        try:
                            payload_bytes, metadata = extract_markdown_from_token(
                                subscriber_keys, pre_extracted_markdown["data"], verify_hash=True
                            )
                            if payload_bytes:
                                md_entries = _unbundle_markdown_payload(payload_bytes)
                                md_files_out = []
                                for entry in md_entries:
                                    text = entry["content"].decode("utf-8", errors="replace")
                                    try:
                                        import markdown2
                                        text_html = markdown2.markdown(
                                            text, extras=["fenced-code-blocks", "tables"]
                                        )
                                    except ImportError:
                                        text_html = f"<pre>{text}</pre>"
                                    md_files_out.append({
                                        "filename": entry["filename"],
                                        "text": text,
                                        "text_html": text_html,
                                        "size": entry["size"],
                                    })
                                item["markdown"] = {
                                    "files": md_files_out,
                                    "method": "token",
                                    "extractedAt": time.time(),
                                }
                                print(f"[OK] Markdown decrypted from pre-extracted token ({len(md_files_out)} files)")
                                markdown_extracted = True
                        except Exception as e:
                            print(f"[WARN] Pre-extracted markdown processing failed: {e}")

                    # For non-aposematic/encrypted images, extract token from decoded_path
                    if not markdown_extracted:
                        try:
                            serialized_token = extract_markdown_token(decoded_path)
                            if serialized_token:
                                payload_bytes, metadata = extract_markdown_from_token(
                                    subscriber_keys, serialized_token, verify_hash=True
                                )
                                if payload_bytes:
                                    md_entries = _unbundle_markdown_payload(payload_bytes)
                                    md_files_out = []
                                    for entry in md_entries:
                                        text = entry["content"].decode("utf-8", errors="replace")
                                        try:
                                            import markdown2
                                            text_html = markdown2.markdown(
                                                text, extras=["fenced-code-blocks", "tables"]
                                            )
                                        except ImportError:
                                            text_html = f"<pre>{text}</pre>"
                                        md_files_out.append({
                                            "filename": entry["filename"],
                                            "text": text,
                                            "text_html": text_html,
                                            "size": entry["size"],
                                        })
                                    item["markdown"] = {
                                        "files": md_files_out,
                                        "method": "token",
                                        "extractedAt": time.time(),
                                    }
                                    print(f"[OK] Markdown extracted from token ({len(md_files_out)} files)")
                                    markdown_extracted = True
                        except Exception as e:
                            print(f"[WARN] Markdown token extraction failed: {e}")

                    if not markdown_extracted:
                        print(f"[ERROR] No markdown could be extracted from image")

                # Convert image to base64 for display (only if requested)
                # For local preview with IPFS running, skip this to avoid huge HTML files
                if embed_images_as_base64:
                    print(f"[IMG] Converting image to base64: {decoded_path}")
                    try:
                        base64_uri = image_to_base64_uri(decoded_path)
                        if base64_uri and base64_uri.startswith("data:image"):
                            # Fix: Update the correct rendition in the list
                            item["renditions"][0]["href"] = base64_uri
                            print(
                                f"[OK] Successfully converted to base64 URI (length: {len(base64_uri)})"
                            )
                        else:
                            print(
                                f"[ERROR] Invalid base64 URI generated: {base64_uri[:100] if base64_uri else 'None'}"
                            )
                            raise ValueError("Invalid base64 URI generated")
                    except Exception as e:
                        print(f"[ERROR] Error converting image to base64: {e}")
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
                                    print(f"[OK] Updated href to decrypted IPFS: {decrypted_hash[:16]}...")
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
                                    print(f"[OK] Updated href to decrypted IPFS: {decrypted_hash[:16]}...")
                                else:
                                    raise ValueError("ipfs_add returned None")
                            else:
                                raise ValueError("ipfs_add function not available")
                        except Exception as e:
                            print(f"[WARN] Failed to add decrypted image to IPFS: {e}")
                            # Fallback to base64
                            try:
                                base64_uri = image_to_base64_uri(decoded_path)
                                if base64_uri and base64_uri.startswith("data:image"):
                                    item["renditions"][0]["href"] = base64_uri
                                    print(f"[WARN] Using base64 fallback for decrypted image")
                                else:
                                    print(f"[ERROR] Base64 fallback failed: {base64_uri[:100] if base64_uri else 'None'}")
                            except Exception as fallback_e:
                                print(f"[ERROR] Base64 fallback error: {fallback_e}")
                                raise
                    else:
                        # Original images don't need decryption - keep IPFS URL
                        print(f"[IMG] Keeping IPFS URL for original image (embed_images_as_base64=False)")

                processed_items.append(item)
                print(f"[OK] Processed item: {item.get('title')}")

                # Yield control to event loop for UI updates between items
                await asyncio.sleep(0)

            except Exception as e:
                print(f"[ERROR] Error processing item {item.get('title', 'Unknown')}: {e}")
                continue

        # Update data pod with processed items
        data_pod["items"] = processed_items
        data_pod["processed_at"] = time.time()
        data_pod["processed_by"] = (
            subscriber_stellar_secret[:8] + "..."
        )  # Last 8 chars for ID

        print(f"[OK] Data pod processing complete: {len(processed_items)} items ready")
        print(f"[DEBUG] Final data_pod keys: {list(data_pod.keys())}")
        print(f"[DEBUG] Final processed_items count: {len(processed_items)}")
        for i, item in enumerate(processed_items):
            print(f"[DEBUG] Returning item {i}: {item.get('title')}, hasAudio={item.get('hasAudio')}, hasVideo={item.get('hasVideo')}")
        return data_pod

    except Exception as e:
        print(f"[ERROR] Critical error processing data pod: {e}")
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

        print(f"[OK] Created test data pod: {output_path}")
        return output_path

    except Exception as e:
        print(f"[ERROR] Error creating test data pod: {e}")
        return None
