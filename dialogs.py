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
from aiposematic import SCRAMBLE_MODE

def create_shared_key(reciever_public_key):
    stellar_secret = app.storage.user.get('stellar_secret', Keypair.random().secret)
    stellar_keys = Keypair.from_secret(stellar_secret)
    hvym_keys = Stellar25519KeyPair(stellar_keys)

    
    shared_key = StellarSharedKey(hvym_keys, reciever_public_key)
    app.storage.user['cipher_key'] = shared_key.shared_secret_as_hex()
    return shared_key.shared_secret_as_hex()

async def edit_metadata_dialog(file_path, metadata_list, on_save, *args):
    """Dialog to edit metadata with delete functionality for each field.
    
    Args:
        file_path: Path to the image file
        metadata_list: List of dictionaries containing the metadata
    """
    if not metadata_list or not isinstance(metadata_list, list) or not metadata_list[0]:
        ui.notify('No metadata found', type='warning')
        return

    metadata = metadata_list[0]  # Get the first (and usually only) metadata dictionary
    metadata_changes = metadata_list[0].copy()

    def get_field_icon(field_name):
        """Return an appropriate icon based on the field name prefix."""
        if field_name.startswith('XMP:'):
            return 'code'
        elif field_name.startswith('IPTC:'):
            return 'photo_library'
        elif field_name.startswith('EXIF:'):
            return 'camera_alt'
        elif field_name.startswith('File:'):
            return 'insert_drive_file'
        elif field_name.startswith('Composite:'):
            return 'filter_hdr'
        return 'text_fields'

    def get_input_type(field_name, value):
        """Determine the appropriate input type based on field name and value."""
        if isinstance(value, bool):
            return 'toggle'
        elif isinstance(value, (int, float)):
            return 'number'
        elif isinstance(value, list):
            return 'textarea'
        elif any(ts in field_name.lower() for ts in ['date', 'time']):
            return 'date' if 'date' in field_name.lower() else 'time'
        return 'text'

    async def delete_field(field_name, card_container):
        """Delete a field from the metadata."""
        if field_name in metadata:
            del metadata[field_name]
            if field_name in metadata_changes:
                del metadata_changes[field_name]
            card_container.clear()
            ui.notify(f'Deleted field: {field_name}')

    with ui.dialog() as dialog, ui.card().classes('w-full max-w-4xl max-h-[90vh]'):
        ui.label('Edit Metadata').classes('text-xl font-bold mb-4')
        
        with ui.scroll_area().classes('w-full h-[70vh] pr-4'):
            with ui.column().classes('w-full gap-4'):
                for field_name, value in sorted(metadata.items()):
                    # Skip SourceFile as it's not editable
                    if field_name == 'SourceFile':
                        continue
                        
                    with ui.card().classes('w-full relative group') as card:
                        with ui.row().classes('w-full items-center gap-2'):
                            # Field icon
                            ui.icon(get_field_icon(field_name)).classes('text-gray-500')
                            
                            # Field name and input
                            with ui.column().classes('flex-1 gap-1'):
                                ui.label(field_name).classes('text-sm font-medium text-gray-600')
                                
                                # Handle different input types
                                input_type = get_input_type(field_name, value)
                                if input_type == 'toggle':
                                    ui.switch(value=bool(value)).bind_value(metadata_changes, field_name)
                                elif input_type == 'number':
                                    ui.number(
                                        value=float(value) if value is not None else 0,
                                        on_change=lambda e, fn=field_name: metadata_changes.update({fn: e.value})
                                    ).classes('w-full')
                                elif input_type == 'textarea':
                                    text_value = '\n'.join(str(v) for v in value) if isinstance(value, list) else str(value)
                                    ui.textarea(
                                        value=text_value,
                                        on_change=lambda e, fn=field_name: metadata_changes.update({fn: e.value.split('\n') if '\n' in e.value else e.value})
                                    ).classes('w-full')
                                else:
                                    ui.input(
                                        value=str(value) if value is not None else '',
                                        on_change=lambda e, fn=field_name: metadata_changes.update({fn: e.value})
                                    ).classes('w-full')
                            
                            # Delete button
                            with ui.row().classes('absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity'):
                                ui.button(icon='delete', on_click=lambda fn=field_name, c=card: delete_field(fn, c)) \
                                    .props('flat dense color=negative')
        
        # Action buttons
        with ui.row().classes('w-full justify-end gap-2 mt-4'):
            new_args = list(args)
            new_args.append(metadata_changes)
            ui.button('Cancel', on_click=dialog.close).props('flat')
            ui.button('Save', on_click=lambda: on_save(*new_args)).props('flat color=primary')

    async def save_metadata():
        """Save the modified metadata back to the file."""
        try:
            with exiftool.ExifTool() as et:
                args = []
                for field, value in metadata_changes.items():
                    if field in metadata and metadata[field] == value:
                        continue  # Skip unchanged fields
                    args.extend([f'-{field}={value}'])
                
                if args:
                    args.append(file_path)
                    et.execute(*args)
                
                ui.notify('Metadata saved successfully', type='positive')
                dialog.close()
                if on_save:
                    await on_save(*args)
        except Exception as e:
            ui.notify(f'Error saving metadata: {str(e)}', type='negative')

    await dialog
    

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
            pub = ui.input('Recipient Public Key', value=app.storage.user['recipient_public_key']).bind_value(app.storage.user, 'recipient_public_key').classes('w-full')
            with ui.row().classes('w-full justify-end'):
                ui.button('CREATE', on_click=lambda: [create_shared_key(pub.value), dialog.close()]).props('flat')
    return dialog

def aposematic_dialog(on_close, process_func):
    scramble_modes = {i.value: i.name for i in SCRAMBLE_MODE}
    with ui.dialog().on('hide', lambda: on_close(process_func)) as dialog:
        with ui.card().classes('w-full max-w-xl'):
            with ui.row().classes('w-full'):
                ui.label('Op String').classes('text-md font-medium')
                op_string = ui.input('Op String', value=app.storage.user['op_string']).bind_value(app.storage.user, 'op_string').classes('w-full')
            with ui.row().classes('w-full'):
                ui.label('Scramble Mode').classes('text-md font-medium')
                mode = ui.select(
                    options=scramble_modes,
                    value=app.storage.user['scramble_mode'],
                    on_change=lambda e: app.storage.user.update({'scramble_mode': e.value})
                ).classes('w-full')
            with ui.row().classes('w-full'):
                ui.label('Recipient Public Key').classes('text-md font-medium')
                pub = ui.input('Recipient Public Key', value=app.storage.user['recipient_public_key']).bind_value(app.storage.user, 'recipient_public_key').classes('w-full')
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
