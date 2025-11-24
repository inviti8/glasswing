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
    
def iptc_dialog(iptc_data, on_close):
    """Dialog for shared IPTC metadata editing."""
    iptc_info = iptc_data.to_dict()
    
    with ui.dialog().on('hide', on_close) as dialog:
        with ui.card().classes('w-full max-w-2xl'):
            ui.label('Edit IPTC Metadata').classes('text-xl font-bold mb-4')
            
            with ui.column().classes('w-full gap-4'):
                # Creator/By-line
                with ui.row().classes('w-full items-center'):
                    ui.checkbox('Use Creator').bind_value(iptc_data, 'use_byline').classes('w-32')
                    with ui.column().classes('flex-1').bind_visibility(iptc_data, 'use_byline'):
                        ui.input('Creator', value=iptc_data.byline).bind_value(iptc_data, 'byline').classes('w-full')
                
                # Object Name
                with ui.row().classes('w-full items-center'):
                    ui.checkbox('Use Object Name').bind_value(iptc_data, 'use_objectname').classes('w-32')
                    with ui.column().classes('flex-1').bind_visibility(iptc_data, 'use_objectname'):
                        ui.input('Object Name', value=iptc_data.objectname).bind_value(iptc_data, 'objectname').classes('w-full')
                
                # Caption/Abstract
                with ui.row().classes('w-full items-start'):
                    ui.checkbox('Use Description').bind_value(iptc_data, 'use_caption_abstract').classes('w-32 pt-2')
                    with ui.column().classes('flex-1').bind_visibility(iptc_data, 'use_caption_abstract'):
                        ui.textarea('Description', value=iptc_data.caption_abstract).bind_value(iptc_data, 'caption_abstract').classes('w-full')
                
                # Keywords
                with ui.row().classes('w-full items-start'):
                    ui.checkbox('Use Keywords').bind_value(iptc_data, 'use_keywords').classes('w-32 pt-2')
                    with ui.column().classes('flex-1').bind_visibility(iptc_data, 'use_keywords'):
                        ui.textarea('Keywords (comma separated)', 
                                  value=', '.join(iptc_data.keywords_array())).classes('w-full')\
                                  .on('blur', lambda e: setattr(iptc_data, 'keywords', e.sender.value))
                
                # Copyright
                with ui.row().classes('w-full items-center'):
                    ui.checkbox('Use Copyright').bind_value(iptc_data, 'use_copyright_notice').classes('w-32')
                    with ui.column().classes('flex-1').bind_visibility(iptc_data, 'use_copyright_notice'):
                        ui.input('Copyright Notice', 
                               value=iptc_data.copyright_notice).bind_value(iptc_data, 'copyright_notice').classes('w-full')
                
                # Location
                with ui.row().classes('w-full items-center'):
                    ui.checkbox('Use Location').bind_value(iptc_data, 'use_city').classes('w-32')
                    with ui.row().classes('flex-1 gap-2').bind_visibility(iptc_data, 'use_city'):
                        ui.input('City', value=iptc_data.city).bind_value(iptc_data, 'city').classes('flex-1')
                        ui.input('Country', value=iptc_data.country).bind_value(iptc_data, 'country').classes('flex-1')
                
                # Data Mining
                with ui.row().classes('w-full items-center'):
                    ui.checkbox('Data Mining').bind_value(iptc_data, 'use_data_mining').classes('w-32')
                    with ui.column().classes('flex-1').bind_visibility(iptc_data, 'use_data_mining'):
                        ui.select(
                            label='Data Mining Restriction',
                            options=iptc_data.get_data_mining_options(),
                            value=iptc_data.data_mining
                        ).bind_value(iptc_data, 'data_mining').classes('w-full')
                
                # Other Constraints
                with ui.row().classes('w-full items-start'):
                    ui.checkbox('Other Constraints').bind_value(iptc_data, 'use_other_constraints').classes('w-32 pt-2')
                    with ui.column().classes('flex-1').bind_visibility(iptc_data, 'use_other_constraints'):
                        ui.textarea('Additional Constraints', 
                                  value=iptc_data.other_constraints).bind_value(iptc_data, 'other_constraints').classes('w-full')
            
            # Action buttons
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=dialog.close).props('flat')
                ui.button('Save', on_click=lambda: [iptc_data.init_storage(), dialog.submit(True)])\
                    .props('flat color=primary')
    
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
