from nicegui import binding, app, ui, run
from typing import Callable, Awaitable, Any, Union
import asyncio
from stellar_sdk import Keypair
from hvym_stellar import  Stellar25519KeyPair, StellarSharedKey
from img_edit import iptc_set_field_value, iptc_get_field_value, iptc_delete_field, new_iptc_img, IPTC_FIELD_CONFIG
from iptcinfo3 import IPTCInfo
import os
from typing import Dict, Any, Optional, List, Union, Callable
from PIL import Image, ExifTags
import tempfile
import shutil
import exiv2
import exiftool
from pprint import pprint

def create_shared_key(reciever_public_key):
    stellar_secret = app.storage.user.get('stellar_secret', Keypair.random().secret)
    stellar_keys = Keypair.from_secret(stellar_secret)
    hvym_keys = Stellar25519KeyPair(stellar_keys)

    
    shared_key = StellarSharedKey(hvym_keys, reciever_public_key)
    app.storage.user['cipher_key'] = shared_key.shared_secret_as_hex()
    return shared_key.shared_secret_as_hex()

async def edit_iptc_info_dialog(file_path, iptc_data, on_save, *args):
    """Dialog to edit IPTC metadata with delete functionality for each field.
    
    Args:
        file_path: Path to the image file
        iptc_data: Dictionary containing the IPTC metadata
    """
    def get_field_value(metadata, field_name):
        """Get a field value from the metadata dictionary."""
        # Map common IPTC field names to ExifTool tags
        field_map = {
            'Object Name': 'IPTC:ObjectName',
            'Caption/Abstract': 'IPTC:Caption-Abstract',
            'Keywords': 'IPTC:Keywords',
            'By-line': 'IPTC:By-line',
            'CopyrightNotice': 'IPTC:CopyrightNotice',
            'Credit': 'IPTC:Credit',
            'City': 'IPTC:City',
            'Province-State': 'IPTC:Province-State',
            'Country-PrimaryLocationName': 'IPTC:Country-PrimaryLocationName',
            'Headline': 'IPTC:Headline',
            'Source': 'IPTC:Source',
            'SpecialInstructions': 'IPTC:SpecialInstructions',
            'DateCreated': 'IPTC:DateCreated',
            'TimeCreated': 'IPTC:TimeCreated',
            'By-lineTitle': 'IPTC:By-lineTitle',
            'Sub-location': 'IPTC:Sub-location',
            'Country-PrimaryLocationCode': 'IPTC:Country-PrimaryLocationCode',
            'OriginalTransmissionReference': 'IPTC:OriginalTransmissionReference',
            'CreditLine': 'IPTC:CreditLine',
            'Writer/Editor': 'IPTC:Writer-Editor'
        }
        
        exif_field = field_map.get(field_name, f'IPTC:{field_name.replace(" ", "")}')
        return metadata.get(exif_field, '')

    def save_metadata(metadata, file_path):
        """Save metadata back to the file using exiftool."""
        try:
            with exiftool.ExifTool() as et:
                # Prepare the arguments for exiftool
                args = []
                for key, value in metadata.items():
                    if value:  # Only include non-empty values
                        args.extend([f'-{key}={value}'])
                    else:
                        args.extend([f'-{key}='])  # Empty value to clear the field
                
                if args:
                    args.append(file_path)
                    et.execute(*args)
                
                ui.notify('Metadata saved successfully', type='positive')
                return True
        except Exception as e:
            ui.notify(f'Error saving metadata: {str(e)}', type='negative')
            return False

    async def delete_field(metadata, field_name, value_container):
        """Show a confirmation dialog before deleting the field."""
        with ui.dialog() as confirm_dialog, ui.card():
            ui.label(f'Delete field "{field_name}"?').classes('text-lg font-medium')
            with ui.row():
                ui.button('Cancel', on_click=confirm_dialog.close).props('flat')
                ui.button('Delete', on_click=lambda: [
                    metadata.pop(field_name, None),
                    value_container.set_visibility(False),
                    confirm_dialog.close(),
                    ui.notify(f'Deleted field: {field_name}')
                ]).props('flat color=negative')
        await confirm_dialog

    def create_field_ui(metadata, field_name, config, iptc_data):
        """Create UI elements for a single field."""
        field_value = metadata.get(field_name, '')
        bind_field_value = iptc_data.get_storage_field(field_name)
        print(bind_field_value)

        with ui.row().classes('w-full items-start gap-2 group'):
            ui.icon(config.get('icon', 'text_fields')).classes('text-gray-500 mt-2')
            with ui.column().classes('flex-1'):
                label = config.get('label', field_name.replace('_', ' ').title())
                if 'hint' in config:
                    label += f" ({config['hint']})"
                ui.label(label).classes('text-sm font-medium')
                
                with ui.column().classes('w-full') as field_container:
                    if config.get('type') == 'textarea':
                        input_field = ui.textarea(
                            label=config.get('label', field_name),
                            value=field_value or '',
                            on_change=lambda e, fn=field_name: metadata.update({fn: e.value})
                        ).bind_value(app.storage.user, bind_field_value).classes('w-full')
                    elif config.get('type') == 'list':
                        input_field = ui.input(
                            label=config.get('label', field_name),
                            value=', '.join(field_value) if isinstance(field_value, list) else field_value or '',
                            on_change=lambda e, fn=field_name: metadata.update({fn: e.value})
                        ).bind_value(app.storage.user, bind_field_value).classes('w-full')
                    else:
                        input_field = ui.input(
                            label=config.get('label', field_name),
                            value=field_value or '',
                            on_change=lambda e, fn=field_name: metadata.update({fn: e.value})
                        ).bind_value(app.storage.user, bind_field_value).classes('w-full')
                    
                    ui.button(
                        icon='delete', 
                        on_click=lambda fn=field_name, c=field_container: delete_field(metadata, fn, c)
                    ).props('flat dense') \
                     .classes('opacity-0 group-hover:opacity-100 transition-opacity self-end')

    # Read existing metadata using exiftool
    try:
        # Check if file is PNG to use -fast option
        file_ext = os.path.splitext(file_path)[1].lower()
        common_args = ['-fast'] if file_ext == '.png' else []
        metadata_list = None
        with exiftool.ExifToolHelper(common_args=common_args) as et:
            # Get all metadata for the file
            metadata_list = et.get_metadata(file_path)
            print('-----------------------------------------------')
            print(file_path)
        
            # Process the metadata to extract IPTC fields
            iptc_metadata = {}
            if metadata_list and metadata_list[0]:  # Check if we have metadata
                # Get all valid IPTC fields from our configuration
                valid_iptc_fields = set(IPTC_FIELD_CONFIG.keys())
                
                # Extract only the fields that exist in our IPTC_FIELD_CONFIG
                for field in valid_iptc_fields:
                    if field in metadata_list[0]:
                        iptc_metadata[field] = metadata_list[0][field]
                
                # If we didn't find any IPTC fields, show a notification
                if not iptc_metadata:
                    ui.notify('No IPTC metadata found in the file. Creating new metadata structure.', type='info')
            else:
                ui.notify('No metadata found in the file. Creating new metadata structure.', type='info')
                iptc_metadata = {}

            # Now we can use iptc_metadata to populate the dialog UI
            # The keys in iptc_metadata will match the field names in IPTC_FIELD_CONFIG
    
    except Exception as e:
        ui.notify(f'Error reading metadata: {str(e)}', type='negative')
        return None

    with ui.dialog() as dialog:
        with ui.card().classes('w-full max-w-2xl'):
            ui.label('Edit IPTC Metadata').classes('text-xl font-bold mb-4')
            
            # Create a scrollable container for all the fields
            with ui.scroll_area().classes('w-full max-h-[70vh] pr-4'):
                with ui.column().classes('w-full gap-4'):
                    # Standard IPTC fields we want to include
                    standard_fields = [
                        'IPTC:ObjectName', 'IPTC:Caption-Abstract', 'IPTC:Keywords', 'IPTC:By-line', 
                        'IPTC:CopyrightNotice', 'IPTC:Credit', 'IPTC:City', 'IPTC:Province-State', 
                        'IPTC:Country-PrimaryLocationName', 'IPTC:Headline', 'IPTC:Source', 
                        'IPTC:SpecialInstructions', 'IPTC:DateCreated', 'IPTC:TimeCreated',
                        'IPTC:By-lineTitle', 'IPTC:Sub-location', 'IPTC:Country-PrimaryLocationCode',
                        'IPTC:OriginalTransmissionReference', 'IPTC:CreditLine', 'IPTC:Writer-Editor'
                    ]
                    
                    # Get all existing IPTC fields from the metadata
                    existing_fields = list(iptc_metadata.keys())
                    
                    # Combine standard fields with existing ones, removing duplicates
                    all_fields = list(dict.fromkeys(standard_fields + existing_fields))
                    
                # Process each field in the filtered metadata
                for field_name, field_value in iptc_metadata.items():
                    try:
                        # Get field config or use defaults
                        field_key = field_name.replace('-', ' ').replace('_', ' ').lower()
                        config = IPTC_FIELD_CONFIG.get(field_key, {
                            'icon': 'text_fields',
                            'label': ' '.join(word.capitalize() for word in field_key.split()),
                            'type': 'text'
                        })
                        
                        # Create the field UI
                        create_field_ui(iptc_metadata, field_name, config, iptc_data)
                            
                    except Exception as e:
                        print(f"Error processing field {field_name}: {str(e)}")
                        continue
                    
                    # Add a button to add a custom field
                    with ui.expansion('Add Custom Field').classes('w-full'):
                        with ui.column().classes('w-full gap-2'):
                            field_name = ui.input('Field Name', placeholder='e.g., IPTC:CustomField').classes('w-full')
                            field_value = ui.input('Field Value', placeholder='Enter value').classes('w-full')
                            
                            def add_custom_field():
                                name = field_name.value.strip()
                                value = field_value.value.strip()
                                if name and value:
                                    if not name.startswith('IPTC:'):
                                        name = f'IPTC:{name}'
                                    iptc_metadata[name] = value
                                    field_name.value = ''
                                    field_value.value = ''
                                    ui.notify(f'Added field: {name}')
                                    # Refresh the dialog to show the new field
                                    dialog.close()
                                    edit_iptc_info_dialog(file_path, iptc_metadata)
                                else:
                                    ui.notify('Please enter both field name and value', type='warning')
                            
                            ui.button('Add Field', on_click=add_custom_field).classes('self-end')
            
            # Add Save and Cancel buttons
            # Action buttons
            new_args = list(args)
            new_args.append(iptc_data)
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=dialog.close).props('flat')
                ui.button('Save', on_click=lambda: [
                    iptc_data.update_from_storage(),  # Save the changes
                    on_save(*args),
                    dialog.close()
                ]).props('flat').classes('bg-primary text-white')

    dialog.open()
    return dialog


def edit_xmp_info_dialog(file_path: str, xmp_properties: dict):
    """Open a dialog to edit XMP metadata using exiv2.
    
    Args:
        file_path: Path to the image file
        xmp_properties: Dictionary containing XMP properties information
    """
    try:
        # Create a copy to track changes
        original_props = {k: v.copy() for k, v in xmp_properties.items()}
        
        with ui.dialog() as dialog, ui.card().classes('w-full max-w-5xl h-[90vh]'):
            with ui.column().classes('w-full h-full gap-2'):
                # Header with title and search
                with ui.row().classes('w-full items-center justify-between'):
                    ui.label('Edit XMP Metadata').classes('text-2xl font-bold')
                
                # Property count
                ui.label(f"{len(xmp_properties)} properties found").classes('text-sm text-gray-500 -mt-2 mb-2')
                
                # Scrollable container for fields
                with ui.scroll_area().classes('w-full flex-grow border rounded'):
                    with ui.column().classes('w-full p-2 gap-3') as fields_container:
                        # Create input for each XMP property
                        field_inputs = {}
                        for key in sorted(xmp_properties.keys()):
                            prop_info = xmp_properties[key]
                            try:
                                with ui.card().classes('w-full p-3 hover:bg-gray-50 transition-colors'):
                                    with ui.row().classes('w-full items-start gap-3'):
                                        # Left column - Property info
                                        with ui.column().classes('w-1/3 gap-1'):
                                            # Property title (or key if no title)
                                            title = prop_info.get('title', key.split('.')[-1])
                                            ui.label(title).classes('font-medium text-sm')
                                            
                                            # Full key in small text
                                            with ui.row().classes('items-center gap-1 text-xs text-gray-500'):
                                                ui.icon('key', size='0.8rem')
                                                ui.label(key).classes('font-mono text-xxs')
                                            
                                            # Type info
                                            if 'type' in prop_info:
                                                with ui.row().classes('items-center gap-1 text-xs text-gray-500'):
                                                    ui.icon('info', size='0.8rem')
                                                    ui.label(str(prop_info['type'])).classes('font-mono')
                                            
                                        # Right column - Value input
                                        with ui.column().classes('flex-1 gap-1'):
                                            # Value input
                                            field_inputs[key] = ui.textarea(
                                                value=prop_info.get('value', ''),
                                                on_change=lambda e, k=key: xmp_properties[k].update({'value': e.value})
                                            ).props('dense outlined').classes('w-full h-full min-h-[2.5rem]').style('resize: none; flex-grow: 1;')
                                            
                                            # Description if available
                                            if prop_info.get('description'):
                                                ui.label(prop_info['description']).classes('text-xs text-gray-500 italic')
                                
                                    # Delete button
                                    with ui.row().classes('w-full justify-end'):
                                        ui.button(
                                            'Remove',
                                            icon='delete',
                                            on_click=lambda k=key: delete_xmp_field(k, field_inputs, xmp_properties)
                                        ).props('flat dense color=negative').classes('opacity-70 hover:opacity-100')
                            except Exception as e:
                                print(f"Error displaying XMP property {key}: {str(e)}")
                                
                                # Delete button
                                with ui.row().classes('w-full justify-end'):
                                    ui.button(
                                        'Remove',
                                        icon='delete',
                                        on_click=lambda k=key: delete_xmp_field(k, field_inputs, xmp_properties)
                                    ).props('flat dense color=negative').classes('opacity-70 hover:opacity-100')
                
                # Action buttons
                with ui.row().classes('w-full justify-end gap-2 mt-4'):
                    ui.button('Cancel', on_click=dialog.close).props('flat')
                    ui.button('Save', on_click=lambda: save_xmp_changes(
                        file_path, xmp_data, original_xmp, dialog
                    )).props('flat').classes('bg-primary text-white')
        
        return dialog
        
    except Exception as e:
        ui.notify(f'Error reading XMP data: {str(e)}', type='negative')
        import traceback
        traceback.print_exc()
        return None


def delete_xmp_field(field_name: str, field_inputs: dict, xmp_data: dict):
    """Delete an XMP field from the UI and data."""
    if field_name in xmp_data:
        del xmp_data[field_name]
        field_inputs[field_name].delete()
        ui.notify(f'Field {field_name} will be removed on save')


async def save_xmp_changes(file_path: str, xmp_properties: dict, original_props: dict, dialog):
    """Save changes made to XMP data back to the file."""
    try:
        # Open the image for writing
        image = exiv2.ImageFactory.open(file_path)
        image.readMetadata()
        xmp_data = image.xmpData()
        
        # Update or add modified properties
        for key, prop_info in xmp_properties.items():
            if key not in original_props or original_props[key].get('value') != prop_info.get('value'):
                # This is a new or modified property
                try:
                    xmp_data[key] = prop_info['value']
                except Exception as e:
                    print(f"Error setting XMP property {key}: {str(e)}")
        
        # Remove deleted properties
        for key in original_props:
            if key not in xmp_properties:
                try:
                    if key in xmp_data:
                        del xmp_data[key]
                except Exception as e:
                    print(f"Error removing XMP property {key}: {str(e)}")
        
        # Write changes back to file
        image.setXmpData(xmp_data)
        image.writeMetadata()
        
        ui.notify('XMP metadata saved successfully')
        dialog.submit(True)
        
    except Exception as e:
        ui.notify(f'Error saving XMP data: {str(e)}', type='negative')
        import traceback
        traceback.print_exc()


def iptc_dialog(iptc_data, on_close):
    """ dialog for shared IPTC metadata editing. """
    iptc_info = iptc_data.to_dict()
    # Try to get the creator from the IPTC data or use the artist from storage
    creator = app.storage.user.get('artist', 'unknown')
    byline = iptc_info.get('by-line', [''])[0] if isinstance(iptc_info.get('by-line'), list) else iptc_info.get('by-line', '')
    
    if byline and creator != 'unknown':
        creator = byline

    with ui.dialog().on('hide', on_close) as dialog:
        with ui.card().classes('w-full max-w-xl'):
            ui.label('Shared IPTC Metadata').classes('text-md font-medium')
            
            with ui.column().classes('w-full gap-4'):
                with ui.row().classes('w-full'):
                    ui.checkbox('Use Creator').bind_value(app.storage.user, 'use_objectname').classes('w-full')
                with ui.row().classes('w-full').bind_visibility(app.storage.user, 'use_objectname'):
                    ui.input('Creator', value=creator).bind_value(app.storage.user, 'iptc_data.byline').classes('w-full')
                with ui.row().classes('w-full'):
                    ui.checkbox('Use Caption Abstract').bind_value(app.storage.user, 'use_caption_abstract').classes('w-full')
                with ui.row().classes('w-full').bind_visibility(app.storage.user, 'use_caption_abstract'):
                    description = iptc_info.get('caption/abstract', '')
                    if isinstance(description, list):
                        description = description[0] if description else ''
                    ui.textarea('Description', value=description).classes('w-full')
                with ui.row().classes('w-full'):
                    ui.checkbox('Use Keywords').bind_value(app.storage.user, 'use_keywords').classes('w-full')
                with ui.row().classes('w-full').bind_visibility(app.storage.user, 'use_keywords'):
                    keywords = iptc_info.get('keywords', [])
                    if isinstance(keywords, list):
                        keywords = ', '.join(k.decode('utf-8', errors='ignore') if isinstance(k, bytes) else str(k) for k in keywords)
                        ui.input('Keywords', value=keywords).classes('w-full')
                with ui.row().classes('w-full'):
                    ui.checkbox('Use Copyright Notice').bind_value(app.storage.user, 'use_copyright_notice').classes('w-full')
                with ui.row().classes('w-full').bind_visibility(app.storage.user, 'use_copyright_notice'):
                    copyright_notice = iptc_info.get('copyright notice', '')
                    if isinstance(copyright_notice, list):
                        copyright_notice = copyright_notice[0] if copyright_notice else ''
                    ui.input('Copyright Notice', value=copyright_notice).classes('w-full')
                with ui.row().classes('w-full'):
                    ui.checkbox('Use Location').bind_value(app.storage.user, 'use_location').classes('w-full')
                with ui.row().classes('w-full').bind_visibility(app.storage.user, 'use_location'):
                    city = iptc_info.get('city', '')
                    if isinstance(city, list):
                        city = city[0] if city else ''
                    country = iptc_info.get('country/primary location name', '')
                    if isinstance(country, list):
                        country = country[0] if country else ''
                    
                    ui.input('City', value=city).classes('w-full')
                    ui.input('Country', value=country).classes('w-full')
                with ui.row().classes('w-full'):
                    with ui.checkbox('Use Data Mining').bind_value(app.storage.user, 'use_data_mining').classes('w-full'):
                        data_mining = iptc_info.get('data mining', 'DMI-PROHIBITED')
                        if isinstance(data_mining, list):
                            data_mining = data_mining[0] if data_mining else 'DMI-PROHIBITED'
                        options = iptc_data.get_data_mining_array()
                    with ui.row().classes('w-full').bind_visibility(app.storage.user, 'use_data_mining'):
                        ui.select(
                            options=options,
                            value=data_mining,
                            label='Data Mining',
                            on_change=lambda e: app.storage.user.update(iptc_data={'data_mining': e.value})
                        ).classes('w-full')
            
            with ui.row().classes('w-full justify-end'):
                ui.button('SAVE', on_click=lambda: [iptc_data.update_from_storage(), dialog.close()]).props('flat')
    return dialog

def cipher_dialog(on_close, process_func):
    with ui.dialog().on('hide', lambda: on_close(process_func)) as dialog:
        with ui.card().classes('w-full max-w-xl'):
            ui.label('Recipient Public Key').classes('text-md font-medium')
            pub = ui.input('Recipient Public Key', value=app.storage.user['cipher_key']).bind_value(app.storage.user, 'cipher_key').classes('w-full')
            with ui.row().classes('w-full justify-end'):
                ui.button('CREATE', on_click=lambda: [create_shared_key(pub.value), dialog.close()]).props('flat')
    return dialog

def assign_iptc_dialog(on_close, process_func):
    with ui.dialog().on('hide', lambda: on_close(process_func)) as dialog:
        with ui.card().classes('w-full max-w-xl'):
            ui.label('Assign IPTC Metadata').classes('text-md font-medium')
            btn = ui.button('ASSIGN', on_click=lambda: dialog.close()).props('flat')
            with ui.row().classes('w-full justify-end'):
                btn
    return dialog

async def process_dialog(process_func: Union[Callable, Callable[..., Awaitable]]):
    with ui.dialog() as dialog:
        with ui.card().classes('w-full max-w-xl'):
            with ui.row().classes('items-center'):
                spinner = ui.spinner('dots', size='lg', color='primary')
                status = ui.label('Processing...').classes('text-md font-medium')
    
    async def run_process():
        try:
            if asyncio.iscoroutinefunction(process_func):
                # For async functions, await them directly
                result = await process_func()
            else:
                # For sync functions, run in a thread
                result = await run.io_bound(process_func)
                
            dialog.close()
            return result
        except Exception as e:
            dialog.close()
            ui.notify(f'Error: {str(e)}', type='negative')
            raise
    
    # Start the process after the dialog is shown
    dialog.on('show', run_process)
    dialog.open()
    return dialog
