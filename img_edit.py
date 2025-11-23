

import tempfile
import os
from wand.image import Image
from wand.display import display
from enum import Enum
import exiftool
import shutil
from pathlib import Path

WATERMARK_POSITIONS = {
    1: 'bottom_right',
    2: 'top_right',
    3: 'bottom_left',
    4: 'top_left',
    5: 'center'
}

async def new_watermarked_img(file_name, base_img_path, wm_img_path, amount=0.2, position='bottom_right', padding=0.05, opacity=1.0):
    # Create a clean temp file path with the original extension
    base_name, ext = os.path.splitext(os.path.basename(file_name))
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"processed_{base_name}{ext}")
    # Ensure the directory exists
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)
    
    try:
        with Image(filename=base_img_path) as base:
            # Store original base alpha channel if it exists
            base_has_alpha = base.alpha_channel
            alpha_mask = None
            if base_has_alpha:
                # Create a copy of the base image for alpha mask
                alpha_mask = base.clone()
                alpha_mask.alpha_channel = 'extract'
            
            with Image(filename=wm_img_path) as watermark:
                # Calculate new dimensions maintaining aspect ratio
                base_width, base_height = base.width, base.height
                wm_ratio = watermark.width / watermark.height
                
                if base_width > base_height:
                    new_width = int(base_width * amount)
                    new_height = int(new_width / wm_ratio)
                else:
                    new_height = int(base_height * amount)
                    new_width = int(new_height * wm_ratio)
                
                # Resize watermark
                watermark.resize(new_width, new_height)
                
                # Apply opacity if needed
                if 0 < opacity < 1.0:
                    watermark.evaluate(operator='multiply', value=opacity, channel='alpha')

                padded_amount = int(min(base_width, base_height) * padding)  
                
                if position == 'top_left':
                    x = padded_amount
                    y = padded_amount
                elif position == 'top_right':
                    x = base_width - new_width - padded_amount
                    y = padded_amount
                elif position == 'bottom_left':
                    x = padded_amount
                    y = base_height - new_height - padded_amount
                elif position == 'center':
                    x = (base_width - new_width) // 2
                    y = (base_height - new_height) // 2
                else:  # bottom_right (default)
                    x = base_width - new_width - padded_amount
                    y = base_height - new_height - padded_amount
                
                # Create a copy of the base image
                result = base.clone()
                
                # Composite the watermark
                result.composite(watermark, left=x, top=y, operator='over')
                
                # If original had alpha, restore it
                if base_has_alpha and alpha_mask is not None:
                    # Make sure result has alpha channel
                    result.alpha_channel = 'on'
                    # Apply the original alpha mask
                    result.composite(alpha_mask, left=0, top=0, operator='copy_alpha')
                
                # Save the result
                result.save(filename=temp_path)
                
        return temp_path
                
    except Exception as e:
        print(f"Error in new_watermarked_img: {str(e)}")
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise
    finally:
        if 'alpha_mask' in locals() and alpha_mask is not None:
            alpha_mask.close()

async def new_enciphered_img(file_name, base_img_path, cipher_key):
    # Create a clean temp file path with the original extension
    base_name, ext = os.path.splitext(os.path.basename(file_name))
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"enciphered_{base_name}{ext}")
    # Ensure the directory exists
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)
    
    try:
        with Image(filename=base_img_path) as img:
            img.encipher(cipher_key)
            img.save(filename=temp_path)
            
        return temp_path
        
    except Exception as e:
        print(f"Error in new_enciphered_img: {str(e)}")
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise

def new_deciphered_img(file_name, encrypted_img_path, cipher_key):
    # Create a clean temp file path with the original extension
    base_name, ext = os.path.splitext(os.path.basename(file_name))
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"deciphered_{base_name}{ext}")
    # Ensure the directory exists
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)
    
    try:
        with Image(filename=encrypted_img_path) as img:
            img.decipher(cipher_key)
            img.save(filename=temp_path)
            
        return temp_path
        
    except Exception as e:
        print(f"Error in new_deciphered_img: {str(e)}")
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise

IPTC_FIELD_CONFIG = {
    'Object Name': {'label': 'Title', 'icon': 'title', 'type': 'text'},
    'Caption/Abstract': {'label': 'Description', 'icon': 'description', 'type': 'textarea'},
    'Keywords': {'label': 'Keywords', 'icon': 'sell', 'type': 'list'},
    'By-line': {'label': 'Creator', 'icon': 'person', 'type': 'text'},
    'CopyrightNotice': {'label': 'Copyright', 'icon': 'copyright', 'type': 'text'},
    'Credit': {'label': 'Credit', 'icon': 'credit_card', 'type': 'text'},
    'City': {'label': 'City', 'icon': 'location_city', 'type': 'text', 'group': 'location'},
    'Province-State': {'label': 'State/Province', 'icon': 'map', 'type': 'text', 'group': 'location'},
    'Country-PrimaryLocationName': {'label': 'Country', 'icon': 'public', 'type': 'text', 'group': 'location'},
    'Headline': {'label': 'Headline', 'icon': 'title', 'type': 'text'},
    'Source': {'label': 'Source', 'icon': 'source', 'type': 'text'},
    'SpecialInstructions': {'label': 'Instructions', 'icon': 'info', 'type': 'text'},
    'DateCreated': {'label': 'Date Created', 'icon': 'event', 'type': 'date'},
    'TimeCreated': {'label': 'Time Created', 'icon': 'schedule', 'type': 'time'}
}

def iptc_get_field_value(iptc_data, field_name):
    """Helper to get a field value from IPTC data, handling binary strings and various access methods."""
    try:
        value = None
            
        # First try direct dictionary access on _data
        if hasattr(iptc_data, '_data') and field_name in iptc_data._data:
            value = iptc_data._data[field_name]
        # Then try direct attribute access
        elif hasattr(iptc_data, field_name):
            value = getattr(iptc_data, field_name)
        # Finally try dictionary-style access if available
        elif hasattr(iptc_data, 'get'):
            value = iptc_data.get(field_name, '')
        else:
            return ''
            
        # Handle different value types
        if value is None:
            return ''
                
        # Handle lists/tuples of values
        if isinstance(value, (list, tuple)):
            return ', '.join(
                v.decode('utf-8', errors='ignore') if hasattr(v, 'decode') else str(v)
                for v in value
                if v is not None
            )
                
        # Handle single value
        if hasattr(value, 'decode'):
            return value.decode('utf-8', errors='ignore')
                
        return str(value) if value is not None else ''
            
    except Exception as e:
        print(f"Error getting field '{field_name}': {type(e).__name__}: {str(e)}")
        return ''

def iptc_set_field_value(iptc_data, field_name, value):
    """Helper to set a field value in IPTC data."""
    try:
        if hasattr(iptc_data, '_data'):
            if field_name == 'keywords' and value:
                iptc_data._data[field_name] = [k.strip() for k in value.split(',') if k.strip()]
            else:
                iptc_data._data[field_name] = value
        else:
            if field_name == 'keywords' and value:
                iptc_data[field_name] = [k.strip() for k in value.split(',') if k.strip()]
            else:
                iptc_data[field_name] = value
    except Exception as e:
        print(f"Error setting field '{field_name}': {str(e)}")

def iptc_delete_field(iptc_data, field_name, value_container):
    """Delete a specific IPTC field."""
    try:
        if hasattr(iptc_data, '_data') and field_name in iptc_data._data:
            del iptc_data._data[field_name]
        elif field_name in iptc_data:
            del iptc_data[field_name]
        if value_container:
            value_container.visible = False
    except Exception as e:
        print(f"Error deleting field '{field_name}': {str(e)}")
        if value_container:
            value_container.visible = False

async def clear_img_metadata(file_name, base_img_path):
    """Create a copy of the image with all metadata removed.
    
    Args:
        file_name: The name of the output file
        base_img_path: Path to the source image file
        
    Returns:
        str: Path to the new image file with all metadata removed
    """
    try:
        # Create a temporary directory that won't be automatically deleted
        temp_dir = tempfile.mkdtemp()
        try:
            # Create output file path with the same extension as input
            base_name = Path(file_name).stem
            ext = Path(base_img_path).suffix
            output_path = os.path.join(temp_dir, f"{base_name}_cleaned{ext}")
            
            print(f"Clearing metadata - Source: {base_img_path}")
            print(f"Clearing metadata - Output: {output_path}")
            
            # Ensure the source file exists
            if not os.path.exists(base_img_path):
                raise FileNotFoundError(f"Source file not found: {base_img_path}")
            
            # Ensure the output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Use exiftool to copy the image without metadata
            with exiftool.ExifTool() as et:
                # -all= clears all metadata
                result = et.execute(
                    '-all=',  # Remove all metadata
                    '-o', output_path,  # Output file
                    base_img_path  # Input file
                )
                
                # Verify the file was created
                if not os.path.exists(output_path):
                    raise Exception(f"Output file was not created. ExifTool output: {result}")
                
                print(f"Metadata cleared successfully: {output_path}")
                return output_path
                
        except Exception as e:
            # Clean up the temp directory if something went wrong
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise Exception(f"Error in clear_img_metadata: {str(e)}")
            
    except Exception as e:
        raise Exception(f"Error clearing image metadata: {str(e)}")

async def new_iptc_img(file_name, base_img_path, iptc_data):
    """
    Create a new image with updated IPTC metadata using ExifTool.
    
    Args:
        file_name: Original file name (used to generate output filename)
        base_img_path: Path to the source image
        iptc_data: Object containing IPTC metadata (must have to_dict() method)
        
    Returns:
        str: Path to the processed image with updated metadata
    """
    temp_dir = None
    try:
        # Get the base name without extension and the extension
        base_name = Path(file_name).stem
        ext = Path(file_name).suffix.lower()
        
        # Create a temporary directory that won't be automatically deleted
        temp_dir = tempfile.mkdtemp()
        
        # Create the output path with the correct extension
        output_filename = f"processed_{base_name}{ext}"
        temp_path = os.path.join(temp_dir, output_filename)
        
        print(f"Source path: {base_img_path}")
        print(f"Temp path: {temp_path}")
        
        # Ensure the source file exists
        if not os.path.exists(base_img_path):
            raise FileNotFoundError(f"Source file not found: {base_img_path}")
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        
        # First, copy the source file to the temp location
        shutil.copy2(base_img_path, temp_path)
        
        # Verify the file was copied
        if not os.path.exists(temp_path):
            raise FileNotFoundError(f"Failed to copy file to {temp_path}")
        
        # Convert iptc_data to dictionary
        iptc_dict = iptc_data.to_dict() if hasattr(iptc_data, 'to_dict') else dict(iptc_data)
        
        # Create a dictionary of EXIF data to write
        exif_dict = {}
        for field, value in iptc_dict.items():
            if value:  # Only include non-empty values
                if isinstance(value, list):
                    exif_dict[field] = [str(v).strip() for v in value if str(v).strip()]
                else:
                    exif_dict[field] = str(value).strip()
        
        # Use ExifTool to write the metadata
        with exiftool.ExifToolHelper() as et:
            # Convert lists to pipe-separated strings as ExifTool expects
            tags_to_write = {}
            for tag, value in exif_dict.items():
                if isinstance(value, list):
                    # Join list items with pipe (|) which is the standard separator for multi-value tags
                    tags_to_write[tag] = '|'.join(str(v) for v in value) if value else ''
                else:
                    tags_to_write[tag] = str(value) if value is not None else ''
            
            # Write all tags at once
            print(f"Writing metadata to {temp_path}")
            print(f"Tags to write: {tags_to_write}")
            
            # Use execute to write the tags
            params = []
            for tag, value in tags_to_write.items():
                params.extend([f"-{tag}={value}"])
            
            # Add the target file
            params.append(temp_path)
            
            # Execute the command
            result = et.execute(*params)
            print(f"ExifTool result: {result}")

            metadata = await get_img_metadata(temp_path)
            print(f"Metadata after writing: {metadata}!!!!!!!!!!!!!!!!!!!!!!!!!!")
        
        # Verify the output file was created
        if not os.path.exists(temp_path):
            raise Exception("Failed to create output file with metadata")
        
        print(f"Successfully created file at {temp_path}")
        return temp_path
        
    except Exception as e:
        # Clean up the temp directory if something went wrong
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except:
                pass
        print(f"Error in new_iptc_img: {str(e)}")
        raise Exception(f"Error processing image metadata with ExifTool: {str(e)}")
            
    except Exception as e:
        # Clean up the temp file if it was created
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        print(f"Error in new_iptc_img: {str(e)}")
        raise Exception(f"Error processing image metadata with ExifTool: {str(e)}")
            
    except Exception as e:
        # Clean up the temp file if it was created
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        print(f"Error in new_iptc_img: {str(e)}")
        raise Exception(f"Error processing image metadata with ExifTool: {str(e)}")

async def get_img_metadata(file_path):
    try:
        print(f"Attempting to read metadata from: {file_path}")
        print(f"File exists: {os.path.exists(file_path)}")
        print(f"File size: {os.path.getsize(file_path) if os.path.exists(file_path) else 0} bytes")
        
        with exiftool.ExifToolHelper() as et:
            print("ExifToolHelper created, getting metadata...")
            metadata = et.get_metadata(file_path)
            print(f"Successfully read metadata: {bool(metadata)}")
            return metadata
    except Exception as e:
        print(f"Error details - Type: {type(e).__name__}, Message: {str(e)}")
        import traceback
        traceback.print_exc()
        raise Exception(f"Error getting metadata with ExifTool: {str(e)}")

async def get_iptc_metadata(file_path):
    try:
        metadata_list = await get_img_metadata(file_path)
        if not metadata_list or not isinstance(metadata_list, list):
            return [{}]
        # Return a list containing a single filtered dictionary
        return [{
            k: v for k, v in metadata_list[0].items()
            if k.startswith(('IPTC:', 'Photoshop:IPTC'))
        }] if metadata_list else [{}]
    except Exception as e:
        raise Exception(f"Error getting IPTC metadata: {str(e)}")

async def get_xmp_metadata(file_path):
    try:
        metadata_list = await get_img_metadata(file_path)
        if not metadata_list or not isinstance(metadata_list, list):
            return [{}]
        # Return a list containing a single filtered dictionary
        return [{
            k: v for k, v in metadata_list[0].items()
            if k.startswith(('XMP:', 'XMP-xmp:'))
        }] if metadata_list else [{}]
    except Exception as e:
        raise Exception(f"Error getting XMP metadata: {str(e)}")

async def get_exif_metadata(file_path):
    try:
        metadata_list = await get_img_metadata(file_path)
        if not metadata_list or not isinstance(metadata_list, list):
            return [{}]
        # Return a list containing a single filtered dictionary
        return [{
            k: v for k, v in metadata_list[0].items()
            if k.startswith(('EXIF:', 'IFD0:'))
        }] if metadata_list else [{}]
    except Exception as e:
        raise Exception(f"Error getting EXIF metadata with ExifTool: {str(e)}")
    
    