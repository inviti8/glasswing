from nicegui import binding, app, ui, run
from typing import Callable, Awaitable, Any, Union
import asyncio
from stellar_sdk import Keypair
from hvym_stellar import Stellar25519KeyPair, StellarSharedKey
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
from audio_tokens import is_audio_file
from video_tokens import is_video_file
from markdown_tokens import is_markdown_file, MAX_BUNDLE_SIZE
from task_runner import TaskRunner, TaskDialog, TaskType, TaskResult

# Explicit exports for PyInstaller compatibility with 'from dialogs import *'
__all__ = [
    'create_shared_key',
    'get_recipient_options',
    'edit_markdown_info',
    'is_markdown',
    'handle_markdown_selection',
    'edit_metadata_dialog',
    'iptc_dialog',
    'cipher_dialog',
    'aposematic_dialog',
    'assign_iptc_dialog',
    'process_dialog',
    'process_batch_dialog',
    'add_body_text_dialog',
    'add_subscriber_dialog',
    'add_subscription_dialog',
    'view_subscriptions_dialog',
    'select_channel_dialog',
    'edit_audio_info',
    'is_audio',
    'browse_audio_file',
    'handle_audio_selection',
    'edit_video_info',
    'is_video',
    'handle_video_selection',
    'gallery_info_dialog',
]

def create_shared_key(receiver_public_key):
    stellar_secret = app.storage.user.get('stellar_secret', Keypair.random().secret)
    stellar_keys = Keypair.from_secret(stellar_secret)
    hvym_keys = Stellar25519KeyPair(stellar_keys)


    shared_key = StellarSharedKey(hvym_keys, receiver_public_key)
    app.storage.user['cipher_key'] = shared_key.shared_secret_as_hex()
    return shared_key.shared_secret_as_hex()

def get_recipient_options():
    """Build recipient options from subscribers list with Debug key at the top."""
    options = {}

    # Add Debug key first if available
    debug_public_key = app.storage.user.get('debug_public_key', None)
    if debug_public_key:
        options[debug_public_key] = 'Debug (Test Key)'

    # Add subscribers
    subscribers = app.storage.user.get('subscribers', [])
    for sub in subscribers:
        name = sub.get('name', 'Unknown')
        public_key = sub.get('public_key', '')
        if public_key:
            options[public_key] = name

    return options

def is_markdown(file):
    """Check if file is a markdown/text format."""
    return is_markdown_file(file)


async def handle_markdown_selection(file_list_container, selected_files, choose_files=None):
    """
    Handle markdown file selection with multi-file support.

    Args:
        file_list_container: UI container to display selected files
        selected_files: list (mutable) holding selected file paths
        choose_files: Async callback to open file dialog
    """
    if not choose_files:
        ui.notify('File selection not available', type='warning')
        return
    try:
        files = await choose_files()
        if not files:
            return
        for file in files:
            if not is_markdown(file):
                ui.notify(f'Skipped non-markdown file: {os.path.basename(file)}', type='warning')
                continue
            file_size = os.path.getsize(file)
            if file_size > MAX_BUNDLE_SIZE:
                ui.notify(f'{os.path.basename(file)} exceeds 1 MB limit', type='warning')
                continue
            if file not in selected_files:
                selected_files.append(file)

        # Refresh the file list display
        file_list_container.clear()
        with file_list_container:
            for fp in selected_files:
                with ui.row().classes('items-center gap-2'):
                    ui.icon('description').classes('text-green-600')
                    ui.label(os.path.basename(fp)).classes('text-sm')
                    sz = os.path.getsize(fp)
                    ui.label(f'({sz / 1024:.1f} KB)').classes('text-xs text-gray-500')
                    ui.button(
                        icon='close', on_click=lambda f=fp: _remove_md_file(f, selected_files, file_list_container)
                    ).props('flat dense round size=xs')

    except Exception as e:
        ui.notify(f'Error selecting files: {str(e)}', type='negative')


def _remove_md_file(file_path, selected_files, file_list_container):
    """Remove a file from the selected markdown files list."""
    if file_path in selected_files:
        selected_files.remove(file_path)
    file_list_container.clear()
    with file_list_container:
        for fp in selected_files:
            with ui.row().classes('items-center gap-2'):
                ui.icon('description').classes('text-green-600')
                ui.label(os.path.basename(fp)).classes('text-sm')
                sz = os.path.getsize(fp)
                ui.label(f'({sz / 1024:.1f} KB)').classes('text-xs text-gray-500')
                ui.button(
                    icon='close', on_click=lambda f=fp: _remove_md_file(f, selected_files, file_list_container)
                ).props('flat dense round size=xs')


def edit_markdown_info(hash_value, on_close, process_func, choose_files=None):
    """Dialog for embedding markdown files into an existing image with token support.

    Follows the process_dialog pattern used by edit_audio_info and edit_video_info.

    Args:
        hash_value: Image hash to embed markdown into
        on_close: Callback when dialog closes (typically process_dialog)
        process_func: Function to process the markdown embedding
        choose_files: Async callback to open file dialog
    """
    # Get image info
    img_path = app.storage.user[hash_value]['path']
    img_name = app.storage.user[hash_value]['name']

    # Get recipient options for token sharing
    recipient_options = get_recipient_options()

    # Track selected files (mutable list) and confirmation state
    selected_files = []
    confirmed = {'value': False}

    def on_confirm():
        """Store values and mark as confirmed before closing."""
        if not selected_files:
            ui.notify('Please select at least one markdown file', type='warning')
            return

        if not recipient_select.value:
            ui.notify('Please select a recipient for token sharing', type='warning')
            return

        # Validate total size
        total = sum(os.path.getsize(f) for f in selected_files if os.path.exists(f))
        if total > MAX_BUNDLE_SIZE:
            ui.notify(f'Total size ({total / 1024:.0f} KB) exceeds 1 MB limit', type='warning')
            return

        app.storage.user['_markdown_embed_params'] = {
            'img_name': img_name,
            'img_path': img_path,
            'hash_value': hash_value,
            'markdown_files': list(selected_files),
            'receiver_public_key': recipient_select.value,
            'expiry_option': expiry_select.value,
        }
        confirmed['value'] = True
        dialog.close()

    async def on_dialog_hide():
        """Called when dialog closes - trigger processing if confirmed."""
        if confirmed['value']:
            await on_close(process_func)

    with ui.dialog().on('hide', on_dialog_hide) as dialog:
        with ui.card().classes('w-full max-w-2xl'):
            ui.label('Embed Markdown in Image').classes('text-lg font-semibold mb-4')
            ui.label(f'Image: {img_name}').classes('text-sm mb-4')

            # File selection
            with ui.column().classes('w-full mb-4'):
                with ui.row().classes('w-full items-center gap-4'):
                    ui.label('Markdown Files:').classes('font-medium')
                    ui.button(
                        'Add Files',
                        on_click=lambda: handle_markdown_selection(
                            file_list, selected_files, choose_files
                        )
                    ).props('flat')
                file_list = ui.column().classes('w-full gap-1 ml-4')

            # Token sharing options
            with ui.column().classes('w-full mb-4'):
                ui.label('Token Sharing Options').classes('font-medium mb-2')

                with ui.row().classes('w-full gap-4 mb-4'):
                    ui.label('Recipient:').classes('font-medium')
                    recipient_select = ui.select(
                        options=recipient_options,
                        value=list(recipient_options.keys())[0] if recipient_options else ''
                    ).classes('flex-grow')

                with ui.row().classes('w-full gap-4 mb-4'):
                    ui.label('Token Expiry:').classes('font-medium')
                    expiry_select = ui.select(
                        options={
                            'never': 'Never',
                            '1h': '1 Hour',
                            '24h': '24 Hours',
                            '7d': '7 Days',
                            '30d': '30 Days',
                            '365d': '1 Year'
                        },
                        value='never'
                    ).classes('flex-grow')

                ui.label(
                    'Markdown files will be encrypted and can only be accessed by the selected recipient'
                ).classes('text-sm text-green-600')

            # Action buttons
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=lambda: dialog.close()).props('flat')
                ui.button('Encrypt & Embed', on_click=on_confirm).props('color=primary')

    dialog.open()
    return dialog

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
                    ui.checkbox('Use Creator').bind_value(app.storage.user, 'iptc_data.use_byline').classes('w-32')
                    with ui.column().classes('flex-1').bind_visibility(app.storage.user, 'iptc_data.use_byline'):
                        ui.input('Creator', value=iptc_data.byline).bind_value(app.storage.user, 'iptc_data.byline').classes('w-full')
                
                # Object Name
                with ui.row().classes('w-full items-center'):
                    ui.checkbox('Use Object Name').bind_value(app.storage.user, 'iptc_data.use_objectname').classes('w-32')
                    with ui.column().classes('flex-1').bind_visibility(app.storage.user, 'iptc_data.use_objectname'):
                        ui.input('Object Name', value=iptc_data.objectname).bind_value(app.storage.user, 'iptc_data.objectname').classes('w-full')
                
                # Caption/Abstract
                with ui.row().classes('w-full items-start'):
                    ui.checkbox('Use Description').bind_value(app.storage.user, 'iptc_data.use_caption_abstract').classes('w-32 pt-2')
                    with ui.column().classes('flex-1').bind_visibility(app.storage.user, 'iptc_data.use_caption_abstract'):
                        ui.textarea('Description', value=iptc_data.caption_abstract).bind_value(app.storage.user, 'iptc_data.caption_abstract').classes('w-full')
                
                # Keywords
                with ui.row().classes('w-full items-start'):
                    ui.checkbox('Use Keywords').bind_value(app.storage.user, 'iptc_data.use_keywords').classes('w-32 pt-2')
                    with ui.column().classes('flex-1').bind_visibility(app.storage.user, 'iptc_data.use_keywords'):
                        ui.textarea('Keywords (comma separated)', 
                                  value=', '.join(iptc_data.keywords_array())).classes('w-full')\
                                  .on('blur', lambda e: setattr(app.storage.user, 'iptc_data.keywords', e.sender.value.split(',')))\
                                  .bind_value(app.storage.user, 'iptc_data.keywords')
                
                # Copyright
                with ui.row().classes('w-full items-center'):
                    ui.checkbox('Use Copyright').bind_value(app.storage.user, 'iptc_data.use_copyright_notice').classes('w-32')
                    with ui.column().classes('flex-1').bind_visibility(app.storage.user, 'iptc_data.use_copyright_notice'):
                        ui.input('Copyright Notice', 
                               value=iptc_data.copyright_notice).bind_value(app.storage.user, 'iptc_data.copyright_notice').classes('w-full')
                
                # Location
                with ui.row().classes('w-full items-center'):
                    ui.checkbox('Use Location').bind_value(app.storage.user, 'iptc_data.use_city').classes('w-32')
                    with ui.row().classes('flex-1 gap-2').bind_visibility(app.storage.user, 'iptc_data.use_city'):
                        ui.input('City', value=iptc_data.city).bind_value(app.storage.user, 'iptc_data.city').classes('flex-1')
                        ui.input('Country', value=iptc_data.country).bind_value(app.storage.user, 'iptc_data.country').classes('flex-1')
                
                # Data Mining
                with ui.row().classes('w-full items-center'):
                    ui.checkbox('Data Mining').bind_value(app.storage.user, 'iptc_data.use_data_mining').classes('w-32')
                    with ui.column().classes('flex-1').bind_visibility(app.storage.user, 'iptc_data.use_data_mining'):
                        ui.select(
                            label='Data Mining Restriction',
                            options=iptc_data.get_data_mining_options(),
                            value=iptc_data.data_mining
                        ).bind_value(app.storage.user, 'iptc_data.data_mining').classes('w-full')
                
                # Other Constraints
                with ui.row().classes('w-full items-start'):
                    ui.checkbox('Other Constraints').bind_value(app.storage.user, 'iptc_data.use_other_constraints').classes('w-32 pt-2')
                    with ui.column().classes('flex-1').bind_visibility(app.storage.user, 'iptc_data.use_other_constraints'):
                        ui.textarea('Additional Constraints', 
                                  value=iptc_data.other_constraints).bind_value(app.storage.user, 'iptc_data.other_constraints').classes('w-full')
            
            # Action buttons
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=dialog.close).props('flat')
                ui.button('Save', on_click=lambda: [iptc_data.update_from_storage(), dialog.submit(True)])\
                    .props('flat color=primary')
    
    return dialog


def cipher_dialog(on_close, process_func):
    recipient_options = get_recipient_options()
    current_recipient = app.storage.user.get('recipient_public_key', None)
    # Default to first option (Debug key) if no current recipient or if current isn't in options
    default_value = current_recipient if current_recipient in recipient_options else (list(recipient_options.keys())[0] if recipient_options else None)

    with ui.dialog().on('hide', lambda: on_close(process_func)) as dialog:
        with ui.card().classes('w-full max-w-xl'):
            ui.label('Select Recipient').classes('text-md font-medium')
            if recipient_options:
                pub = ui.select(
                    options=recipient_options,
                    value=default_value,
                    on_change=lambda e: app.storage.user.update({'recipient_public_key': e.value})
                ).classes('w-full')
            else:
                ui.label('No subscribers available. Add subscribers first.').classes('text-gray-500')
                pub = None
            with ui.row().classes('w-full justify-end'):
                ui.button('CREATE', on_click=lambda: [create_shared_key(pub.value), dialog.close()] if pub else dialog.close()).props('flat')
    return dialog

def aposematic_dialog(on_close, process_func):
    scramble_modes = {i.value: i.name for i in SCRAMBLE_MODE}
    recipient_options = get_recipient_options()
    current_recipient = app.storage.user.get('recipient_public_key', None)
    # Default to first option (Debug key) if no current recipient or if current isn't in options
    default_value = current_recipient if current_recipient in recipient_options else (list(recipient_options.keys())[0] if recipient_options else None)

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
                ui.label('Select Recipient').classes('text-md font-medium')
                if recipient_options:
                    pub = ui.select(
                        options=recipient_options,
                        value=default_value,
                        on_change=lambda e: app.storage.user.update({'recipient_public_key': e.value})
                    ).classes('w-full')
                else:
                    ui.label('No subscribers available. Add subscribers first.').classes('text-gray-500')
                    pub = None
            with ui.row().classes('w-full justify-end'):
                ui.button('CREATE', on_click=lambda: [app.storage.user.update({'recipient_public_key': pub.value}), create_shared_key(pub.value), dialog.close()] if pub else dialog.close()).props('flat')
    return dialog

def assign_iptc_dialog(on_close, process_func):
    with ui.dialog().on('hide', lambda: on_close(process_func)) as dialog:
        with ui.card().classes('w-full max-w-xl'):
            ui.label('Assign IPTC Metadata').classes('text-md font-medium')
            btn = ui.button('ASSIGN', on_click=lambda: dialog.close()).props('flat')
            with ui.row().classes('w-full justify-end'):
                btn
    return dialog

async def process_dialog(
    process_func: Union[Callable, Callable[..., Awaitable]],
    title: str = "Processing...",
    task_type: TaskType = TaskType.IO,
    show_cancel: bool = False
):
    """
    Display a processing dialog while running a blocking task.

    This function properly handles blocking operations by running them
    in thread/process pools, preventing the "Connection lost" popup.

    Args:
        process_func: The function to execute (sync or async with blocking calls)
        title: Dialog title message
        task_type: TaskType.IO for I/O-bound, TaskType.CPU for CPU-intensive
        show_cancel: Whether to show a cancel button

    Note:
        For async functions that contain blocking operations (like ImageMagick
        or requests calls), you should refactor them to be sync functions
        and pass task_type appropriately. The async wrapper doesn't help
        if the inner operations are blocking.
    """
    runner = TaskRunner()

    with ui.dialog() as dialog:
        with ui.card().classes('w-full max-w-md'):
            with ui.column().classes('w-full gap-3'):
                with ui.row().classes('items-center gap-3'):
                    spinner = ui.spinner('dots', size='lg', color='primary')
                    status = ui.label(title).classes('text-lg font-medium')

                if show_cancel:
                    with ui.row().classes('w-full justify-end'):
                        def on_cancel():
                            runner.cancel()
                            status.set_text("Cancelling...")
                        ui.button('Cancel', on_click=on_cancel).props('flat color=negative')

    async def run_process():
        try:
            if asyncio.iscoroutinefunction(process_func):
                # Async function - but may still contain blocking calls
                # We await it directly since we can't easily wrap async funcs
                # The function itself should use run.io_bound/cpu_bound internally
                result = await process_func()
            else:
                # Sync function - run in appropriate executor
                result = await runner.run(process_func, task_type=task_type)

            dialog.close()
            return result
        except Exception as e:
            dialog.close()
            ui.notify(f'Error: {str(e)}', type='negative')
            raise

    dialog.open()
    # Small delay to ensure dialog renders before heavy work starts
    await asyncio.sleep(0.05)
    result = await run_process()
    return result


async def process_batch_dialog(
    items: List[Any],
    process_func: Callable[[Any], Any],
    title: str = "Processing...",
    task_type: TaskType = TaskType.IO,
    item_label: str = "item",
    stop_on_error: bool = False
) -> List[TaskResult]:
    """
    Display a progress dialog while processing a batch of items.

    Args:
        items: List of items to process
        process_func: Sync function to process each item
        title: Dialog title
        task_type: TaskType.IO or TaskType.CPU
        item_label: Label for progress (e.g., "image", "file")
        stop_on_error: Stop processing on first error

    Returns:
        List of TaskResult objects with success/failure for each item
    """
    async with TaskDialog(
        title=title,
        show_progress=True,
        show_cancel=True
    ) as dialog:
        results = await dialog.run_batch(
            items=items,
            process_func=process_func,
            task_type=task_type,
            item_label=item_label,
            stop_on_error=stop_on_error
        )
        return results 
    
async def add_body_text_dialog(img_name, img_path, hash_value, on_save):
    selected_type = ui.select(['IPTC', 'XMP'], value='IPTC').classes('w-full')
    with ui.dialog() as dialog:
        with ui.card().classes('w-full max-w-xl'):
            ui.label('Metadata Type')
            selected_type = ui.select(['IPTC', 'XMP'], value='IPTC').classes('w-full')
            ui.label('Body Text')
            txt = ui.textarea(value='').classes('w-full')
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=dialog.close).props('flat')
                ui.button('Save', on_click=lambda: on_save(img_name, img_path, hash_value, txt.value, selected_type.value)).props('flat color=primary')

    dialog.open()
    return 

async def add_subscriber_dialog(on_save):
    with ui.dialog().on('hide', lambda: on_save(name.value, pub.value)) as dialog:
        with ui.card().classes('w-full max-w-xl'):
            ui.label('Add Subscriber').classes('text-md font-medium')
            with ui.row().classes('w-full justify-end'):
                name = ui.input('Subscriber Name', value='').bind_value(app.storage.user, 'subscriber_name').classes('w-full')
            with ui.row().classes('w-full justify-end'):
                pub = ui.input('Subscriber Public Key', value='').bind_value(app.storage.user, 'subscriber_public_key').classes('w-full')
            with ui.row().classes('w-full justify-end'):
                ui.button('ADD', on_click=lambda: dialog.close()).props('flat')

    dialog.open()
    return

async def add_subscription_dialog(on_save):
    """Dialog for adding a subscription to a Pintheon node."""
    with ui.dialog() as dialog:
        with ui.card().classes('w-full max-w-xl'):
            ui.label('Add Subscription').classes('text-xl font-bold mb-4')
            ui.label('Enter the Pintheon node address to subscribe. Your App Key is used to find your content automatically.').classes('text-sm text-gray-500 mb-4')

            with ui.column().classes('w-full gap-4'):
                label_input = ui.input('Label',
                                       placeholder='e.g., My Publisher') \
                    .classes('w-full')

                url_input = ui.input('Pintheon Node URL',
                                     placeholder='e.g., https://mypublisher.pintheon.com') \
                    .classes('w-full')

            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=dialog.close).props('flat')
                ui.button('Subscribe', on_click=lambda: (
                    on_save(label_input.value, url_input.value),
                    dialog.close()
                )).props('flat color=primary')

    dialog.open()
    return

def view_subscriptions_dialog(fetch_subscription_content=None, remove_subscription=None):
    """
    Dialog for viewing and managing subscriptions.

    Args:
        fetch_subscription_content: Callback to fetch subscription content
        remove_subscription: Callback to remove a subscription
    """
    subscriptions = app.storage.user.get('subscriptions', [])

    async def fetch_and_notify(label, dialog):
        """Helper to fetch subscription content and show notification."""
        dialog.close()
        if fetch_subscription_content:
            await fetch_subscription_content(label)

    async def remove_and_refresh(label, dialog):
        """Helper to remove subscription and refresh dialog."""
        if remove_subscription:
            await remove_subscription(label)
        dialog.close()
        view_subscriptions_dialog(fetch_subscription_content, remove_subscription)

    with ui.dialog() as dialog:
        with ui.card().classes('w-full max-w-2xl'):
            ui.label('Subscriptions').classes('text-xl font-bold mb-4')

            if not subscriptions:
                ui.label('No subscriptions yet. Add one to get started!').classes('text-gray-500')
            else:
                with ui.column().classes('w-full gap-2'):
                    for sub in subscriptions:
                        with ui.card().classes('w-full'):
                            with ui.row().classes('w-full items-center justify-between'):
                                with ui.column().classes('gap-1'):
                                    ui.label(sub.get('label', sub.get('name', 'Unknown'))).classes('font-bold')
                                    ui.label(sub.get('url', '')).classes('text-sm text-gray-500')
                                    last = sub.get('last_fetched')
                                    ui.label(f"Last fetched: {last or 'never'}").classes('text-xs text-gray-400')
                                with ui.row().classes('gap-2'):
                                    ui.button(icon='sync', on_click=lambda s=sub: fetch_and_notify(s['label'], dialog)).props('flat round').tooltip('Fetch Content')
                                    ui.button(icon='delete', on_click=lambda s=sub: remove_and_refresh(s['label'], dialog)).props('flat round color=negative').tooltip('Remove')

            with ui.row().classes('w-full justify-end mt-4'):
                ui.button('Close', on_click=dialog.close).props('flat')

    dialog.open()

def select_channel_dialog(on_select, fetch_subscription_channels=None):
    """
    Dialog for selecting a channel (data pod) from a subscription.

    Args:
        on_select: Callback function(subscription_name, channel_info) when a channel is selected
        fetch_subscription_channels: Callback to fetch channels for a subscription
    """
    subscriptions = app.storage.user.get('subscriptions', [])
    fetched_subscriptions = app.storage.user.get('fetched_subscriptions', {})

    with ui.dialog() as dialog:
        with ui.card().classes('w-full max-w-2xl'):
            ui.label('Select Channel').classes('text-xl font-bold mb-4')

            if not subscriptions:
                ui.label('No subscriptions yet. Add a subscription first!').classes('text-gray-500')
            else:
                # Subscription selector
                subscription_names = [s.get('label', s.get('name', 'Unknown')) for s in subscriptions]
                selected_sub = ui.select(
                    label='Select Subscription',
                    options=subscription_names,
                    value=subscription_names[0] if subscription_names else None
                ).classes('w-full mb-4')

                # Channel list container
                channel_container = ui.column().classes('w-full gap-2')

                async def load_channels():
                    """Load channels for the selected subscription."""
                    channel_container.clear()
                    sub_name = selected_sub.value
                    if not sub_name:
                        return

                    # Get subscription info
                    sub = next((s for s in subscriptions if s.get('label', s.get('name')) == sub_name), None)
                    if not sub:
                        return

                    with channel_container:
                        ui.label('Loading channels...').classes('text-gray-500')

                    # Fetch channels from the subscription
                    channels = await fetch_subscription_channels(sub_name) if fetch_subscription_channels else []

                    channel_container.clear()
                    with channel_container:
                        if not channels:
                            ui.label('No channels found. Try fetching the subscription first.').classes('text-gray-500')
                        else:
                            for channel in channels:
                                with ui.card().classes('w-full cursor-pointer hover:bg-gray-100'):
                                    with ui.row().classes('w-full items-center justify-between'):
                                        with ui.column().classes('gap-1'):
                                            ui.label(channel.get('name', 'Unknown Channel')).classes('font-bold')
                                            ui.label(channel.get('description', '')).classes('text-sm text-gray-500')
                                        ui.button('Select', on_click=lambda c=channel: (
                                            on_select(sub_name, c),
                                            dialog.close()
                                        )).props('flat color=primary')

                # Load channels when subscription changes
                selected_sub.on('update:model-value', lambda: load_channels())

                # Initial load
                ui.timer(0.1, load_channels, once=True)

            with ui.row().classes('w-full justify-end mt-4'):
                ui.button('Cancel', on_click=dialog.close).props('flat')

    dialog.open()


def edit_audio_info(hash_value, on_close, process_func, choose_files=None):
    """Enhanced dialog for embedding audio into an existing image with token support.

    Follows the process_dialog pattern used by aposematic_dialog and cipher_dialog.

    Args:
        hash_value: Image hash to embed audio into
        on_close: Callback when dialog closes (typically process_dialog)
        process_func: Function to process the audio embedding
        choose_files: Async callback to open file dialog
    """
    # Get image info
    img_path = app.storage.user[hash_value]['path']
    img_name = app.storage.user[hash_value]['name']

    # Get recipient options for token sharing
    recipient_options = get_recipient_options()

    # Track if user confirmed (vs cancelled)
    confirmed = {'value': False}

    def on_confirm():
        """Store values and mark as confirmed before closing."""
        # Validate audio file
        if not audio_input.value:
            ui.notify('Please select an audio file', type='warning')
            return

        # Validate recipient (always required — token-only)
        if not recipient_select.value:
            ui.notify('Please select a recipient for token sharing', type='warning')
            return

        # Store values for process_func to use (always token method)
        app.storage.user['_audio_embed_params'] = {
            'img_name': img_name,
            'img_path': img_path,
            'hash_value': hash_value,
            'audio_file': audio_input.value,
            'audio_method': 'token',
            'receiver_public_key': recipient_select.value,
            'expiry_option': expiry_select.value
        }
        confirmed['value'] = True
        dialog.close()

    async def on_dialog_hide():
        """Called when dialog closes - trigger processing if confirmed."""
        if confirmed['value']:
            await on_close(process_func)

    with ui.dialog().on('hide', on_dialog_hide) as dialog:
        with ui.card().classes('w-full max-w-2xl'):
            ui.label('Add Audio to Image').classes('text-lg font-semibold mb-4')
            ui.label(f'Image: {img_name}').classes('text-sm mb-4')

            # Audio file selection - following Andromica pattern
            with ui.row().classes('w-full gap-4 mb-4'):
                ui.label('Audio File:').classes('font-medium')
                audio_input = ui.input(
                    placeholder='Select audio file (WAV, MP3, FLAC, OGG)',
                    value=''
                ).props('clearable').classes('flex-grow')
                ui.button('Browse', on_click=lambda: handle_audio_selection(audio_input, choose_files)).props('flat')

            # Token sharing options (always visible — audio is always encrypted)
            with ui.column().classes('w-full mb-4'):
                ui.label('Token Sharing Options').classes('font-medium mb-2')

                with ui.row().classes('w-full gap-4 mb-4'):
                    ui.label('Recipient:').classes('font-medium')
                    recipient_select = ui.select(
                        options=recipient_options,
                        value=list(recipient_options.keys())[0] if recipient_options else ''
                    ).classes('flex-grow')

                with ui.row().classes('w-full gap-4 mb-4'):
                    ui.label('Token Expiry:').classes('font-medium')
                    expiry_select = ui.select(
                        options={
                            'never': 'Never',
                            '1h': '1 Hour',
                            '24h': '24 Hours',
                            '7d': '7 Days',
                            '30d': '30 Days',
                            '365d': '1 Year'
                        },
                        value='never'
                    ).classes('flex-grow')

                ui.label('Audio will be encrypted and can only be accessed by the selected recipient').classes('text-sm text-blue-600')

            # Action buttons
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=lambda: dialog.close()).props('flat')
                ui.button('Encrypt & Embed Audio', on_click=on_confirm).props('color=primary')

    dialog.open()
    return dialog

def is_audio(file):
    """Check if file is an audio format."""
    return is_audio_file(file)

async def handle_audio_selection(input_field, choose_files=None):
    """
    Handle audio file selection following Andromica pattern.

    Args:
        input_field: The input field to update with selected file
        choose_files: Async callback to open file dialog
    """
    if not choose_files:
        ui.notify('File selection not available', type='warning')
        return
    try:
        files = await choose_files()
        audio_files = [file for file in files if is_audio(file)]
        if audio_files:
            input_field.value = audio_files[0]
        else:
            ui.notify('Please select a valid audio file (WAV, MP3, FLAC, OGG)', type='warning')
    except Exception as e:
        ui.notify(f'Error selecting file: {str(e)}', type='negative')

def browse_audio_file(input_field, choose_files=None):
    """
    Browse for audio file following Andromica pattern.

    Args:
        input_field: The input field to update with selected file
        choose_files: Async callback to open file dialog
    """
    async def handle_file_selection():
        if not choose_files:
            ui.notify('File selection not available', type='warning')
            return
        try:
            files = await choose_files()
            audio_files = [file for file in files if is_audio(file)]
            if audio_files:
                input_field.value = audio_files[0]
            else:
                ui.notify('Please select a valid audio file (WAV, MP3, FLAC, OGG)', type='warning')
        except Exception as e:
            ui.notify(f'Error selecting file: {str(e)}', type='negative')

    return handle_file_selection

def is_video(file):
    """Check if file is a video format."""
    return is_video_file(file)


async def handle_video_selection(input_field, choose_files=None):
    """
    Handle video file selection following the same pattern as handle_audio_selection.

    Args:
        input_field: The input field to update with selected file
        choose_files: Async callback to open file dialog
    """
    if not choose_files:
        ui.notify('File selection not available', type='warning')
        return
    try:
        files = await choose_files()
        video_files = [file for file in files if is_video(file)]
        if video_files:
            input_field.value = video_files[0]
        else:
            ui.notify('Please select a valid video file (MP4, WebM, MOV, AVI, MKV)', type='warning')
    except Exception as e:
        ui.notify(f'Error selecting file: {str(e)}', type='negative')


def edit_video_info(hash_value, on_close, process_func, choose_files=None):
    """Dialog for embedding video into an existing image with token support.

    Follows the process_dialog pattern used by edit_audio_info.

    Args:
        hash_value: Image hash to embed video into
        on_close: Callback when dialog closes (typically process_dialog)
        process_func: Function to process the video embedding
        choose_files: Async callback to open file dialog
    """
    # Get image info
    img_path = app.storage.user[hash_value]['path']
    img_name = app.storage.user[hash_value]['name']

    # Get recipient options for token sharing
    recipient_options = get_recipient_options()

    # Track if user confirmed (vs cancelled)
    confirmed = {'value': False}

    def on_confirm():
        """Store values and mark as confirmed before closing."""
        if not video_input.value:
            ui.notify('Please select a video file', type='warning')
            return

        if not recipient_select.value:
            ui.notify('Please select a recipient for token sharing', type='warning')
            return

        # Store values for process_func to use
        app.storage.user['_video_embed_params'] = {
            'img_name': img_name,
            'img_path': img_path,
            'hash_value': hash_value,
            'video_file': video_input.value,
            'receiver_public_key': recipient_select.value,
            'expiry_option': expiry_select.value
        }
        confirmed['value'] = True
        dialog.close()

    async def on_dialog_hide():
        """Called when dialog closes - trigger processing if confirmed."""
        if confirmed['value']:
            await on_close(process_func)

    with ui.dialog().on('hide', on_dialog_hide) as dialog:
        with ui.card().classes('w-full max-w-2xl'):
            ui.label('Add Video to Image').classes('text-lg font-semibold mb-4')
            ui.label(f'Image: {img_name}').classes('text-sm mb-4')

            # Video file selection
            with ui.row().classes('w-full gap-4 mb-4'):
                ui.label('Video File:').classes('font-medium')
                video_input = ui.input(
                    placeholder='Select video file (MP4, WebM, MOV, AVI, MKV)',
                    value=''
                ).props('clearable').classes('flex-grow')
                ui.button('Browse', on_click=lambda: handle_video_selection(video_input, choose_files)).props('flat')

            # Token sharing options (always visible — video is always encrypted)
            with ui.column().classes('w-full mb-4'):
                ui.label('Token Sharing Options').classes('font-medium mb-2')

                with ui.row().classes('w-full gap-4 mb-4'):
                    ui.label('Recipient:').classes('font-medium')
                    recipient_select = ui.select(
                        options=recipient_options,
                        value=list(recipient_options.keys())[0] if recipient_options else ''
                    ).classes('flex-grow')

                with ui.row().classes('w-full gap-4 mb-4'):
                    ui.label('Token Expiry:').classes('font-medium')
                    expiry_select = ui.select(
                        options={
                            'never': 'Never',
                            '1h': '1 Hour',
                            '24h': '24 Hours',
                            '7d': '7 Days',
                            '30d': '30 Days',
                            '365d': '1 Year'
                        },
                        value='never'
                    ).classes('flex-grow')

                ui.label('Video will be encrypted and stored on IPFS. Only the selected recipient can decrypt it.').classes('text-sm text-purple-600')

            # Action buttons
            with ui.row().classes('w-full justify-end gap-2'):
                ui.button('Cancel', on_click=lambda: dialog.close()).props('flat')
                ui.button('Encrypt & Embed Video', on_click=on_confirm).props('color=primary')

    dialog.open()
    return dialog


def gallery_info_dialog():
    """Dialog for setting gallery title and description."""
    with ui.dialog() as dialog:
        with ui.card().classes('w-full max-w-2xl'):
            ui.label('Gallery Information').classes('text-xl font-bold mb-4')

            with ui.column().classes('w-full gap-4'):
                ui.input('Gallery Title',
                        value=app.storage.user.get('gallery_title', ''),
                        placeholder='Enter gallery title (leave empty to hide)') \
                    .bind_value(app.storage.user, 'gallery_title') \
                    .classes('w-full')

                ui.textarea('Gallery Description',
                           value=app.storage.user.get('gallery_description', ''),
                           placeholder='Enter gallery description (leave empty to hide)') \
                    .bind_value(app.storage.user, 'gallery_description') \
                    .classes('w-full')

            # Action buttons
            with ui.row().classes('w-full justify-end gap-2 mt-4'):
                ui.button('Cancel', on_click=dialog.close).props('flat')
                ui.button('Save', on_click=lambda: [dialog.close(), ui.notify('Gallery info saved', type='positive')]) \
                    .props('flat color=primary')

    dialog.open()
    return dialog
