

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
    
    # Create output file path with original extension
    base_name = Path(file_name).stem
    ext = Path(file_name).suffix.lower()
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"processed_{base_name}{ext}")
    
    # Ensure the directory exists
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)
    
    # Convert iptc_data to dictionary
    iptc_dict = iptc_data.to_dict() if hasattr(iptc_data, 'to_dict') else dict(iptc_data)
    
    # Map field names to ExifTool tags
    field_to_tag = {
        'Object Name': 'IPTC:ObjectName',
        'Caption/Abstract': 'IPTC:Caption-Abstract',
        'Keywords': 'IPTC:Keywords',
        'Credit Line': 'IPTC:Credit',
        'Copyright Notice': 'IPTC:CopyrightNotice',
        'Byline': 'IPTC:By-line',
        'City': 'IPTC:City',
        'Country': 'IPTC:Country-PrimaryLocationName',
        'Destination': 'IPTC:Destination',
        'Data Mining': 'IPTC:SpecialInstructions'
    }
    
    try:
        # First, copy the original file to preserve all other metadata
        shutil.copy2(base_img_path, temp_path)
        
        # Prepare the metadata dictionary for ExifTool
        exif_dict = {}
        for field_name, value in iptc_dict.items():
            if not value or field_name not in field_to_tag:
                continue
                
            tag_name = field_to_tag[field_name]
            if field_name == 'keywords':
                # Handle keywords as a list
                if isinstance(value, str):
                    keywords = [k.strip() for k in value.split(',') if k.strip()]
                    exif_dict[tag_name] = keywords
                elif isinstance(value, (list, tuple)):
                    exif_dict[tag_name] = [str(v).strip() for v in value if str(v).strip()]
            else:
                exif_dict[tag_name] = str(value)
        
        # Use ExifTool to write the metadata
        with exiftool.ExifTool() as et:
            # Convert the dictionary to the format ExifTool expects
            tags = []
            for tag, value in exif_dict.items():
                if isinstance(value, list):
                    for v in value:
                        tags.append(f'-{tag}={v}')
                else:
                    tags.append(f'-{tag}={value}')
            
            # Execute the command
            et.execute(*tags, temp_path)
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        print(temp_path)
        print('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
        return temp_path
        
    except Exception as e:
        # Clean up the temp file if it was created
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as cleanup_error:
                print(f"Error cleaning up temporary file: {cleanup_error}")
        raise Exception(f"Error processing image metadata with ExifTool: {str(e)}")
    