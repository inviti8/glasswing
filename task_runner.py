"""
TaskRunner - Non-blocking task execution for NiceGUI applications.

Solves the "Connection lost. Trying to reconnect..." issue by properly
executing blocking operations in thread/process pools.

Usage:
    from task_runner import TaskRunner, TaskType

    runner = TaskRunner()

    # For I/O operations (network, file)
    result = await runner.run(my_io_func, arg1, arg2, task_type=TaskType.IO)

    # For CPU operations (image processing)
    result = await runner.run(my_cpu_func, arg1, task_type=TaskType.CPU)

    # For batch processing with progress
    results = await runner.run_batch(
        items=image_list,
        process_func=process_single_image,
        task_type=TaskType.CPU,
        on_progress=update_progress_bar
    )
"""

from nicegui import run, background_tasks, ui
from typing import Callable, Any, Optional, List, TypeVar, Generic
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import traceback

T = TypeVar('T')


class TaskType(Enum):
    """Type of blocking operation."""
    IO = "io"      # Network requests, file I/O, database queries
    CPU = "cpu"    # Image processing, encryption, heavy computation


@dataclass
class TaskProgress:
    """Progress information for a running task."""
    current: int = 0
    total: int = 0
    message: str = ""
    percentage: float = 0.0

    def __post_init__(self):
        if self.total > 0:
            self.percentage = (self.current / self.total) * 100


@dataclass
class TaskResult(Generic[T]):
    """Result of a task execution."""
    success: bool
    value: Optional[T] = None
    error: Optional[Exception] = None
    error_message: str = ""


class TaskRunner:
    """
    Manages execution of blocking tasks without freezing the NiceGUI UI.

    This class wraps blocking operations and executes them in appropriate
    executors (thread pool for I/O, process pool for CPU) to prevent
    the "Connection lost" popup.
    """

    def __init__(self):
        self._progress = TaskProgress()
        self._cancelled = False
        self._running = False

    @property
    def progress(self) -> TaskProgress:
        """Get current progress."""
        return self._progress

    @property
    def is_running(self) -> bool:
        """Check if a task is currently running."""
        return self._running

    @property
    def is_cancelled(self) -> bool:
        """Check if cancellation was requested."""
        return self._cancelled

    def cancel(self):
        """Request task cancellation. Task should check is_cancelled periodically."""
        self._cancelled = True

    def reset(self):
        """Reset runner state for reuse."""
        self._cancelled = False
        self._running = False
        self._progress = TaskProgress()

    def update_progress(self, current: int, total: int, message: str = ""):
        """
        Update progress information.
        Safe to call from any context.
        """
        self._progress = TaskProgress(current=current, total=total, message=message)

    async def run(
        self,
        func: Callable[..., T],
        *args,
        task_type: TaskType = TaskType.IO,
        **kwargs
    ) -> T:
        """
        Execute a blocking function without blocking the UI.

        Args:
            func: The blocking function to execute
            *args: Positional arguments for func
            task_type: IO for I/O-bound, CPU for CPU-bound operations
            **kwargs: Keyword arguments for func

        Returns:
            The return value of func

        Raises:
            Exception: Any exception raised by func
        """
        self._running = True
        try:
            if task_type == TaskType.CPU:
                # CPU-bound: run in separate process (bypasses GIL)
                # Note: func must be picklable (module-level or static)
                result = await run.cpu_bound(func, *args, **kwargs)
            else:
                # I/O-bound: run in thread pool
                result = await run.io_bound(func, *args, **kwargs)
            return result
        finally:
            self._running = False

    async def run_safe(
        self,
        func: Callable[..., T],
        *args,
        task_type: TaskType = TaskType.IO,
        **kwargs
    ) -> TaskResult[T]:
        """
        Execute a blocking function and return a TaskResult (never raises).

        Args:
            func: The blocking function to execute
            *args: Positional arguments for func
            task_type: IO for I/O-bound, CPU for CPU-bound operations
            **kwargs: Keyword arguments for func

        Returns:
            TaskResult with success status and value or error
        """
        try:
            value = await self.run(func, *args, task_type=task_type, **kwargs)
            return TaskResult(success=True, value=value)
        except Exception as e:
            return TaskResult(
                success=False,
                error=e,
                error_message=str(e)
            )

    async def run_batch(
        self,
        items: List[Any],
        process_func: Callable[[Any], T],
        task_type: TaskType = TaskType.IO,
        on_progress: Optional[Callable[[TaskProgress], None]] = None,
        item_label: str = "item",
        stop_on_error: bool = False
    ) -> List[TaskResult[T]]:
        """
        Process a batch of items with progress tracking.

        Args:
            items: List of items to process
            process_func: Function to call for each item (must be sync)
            task_type: IO or CPU bound
            on_progress: Callback for progress updates
            item_label: Label for progress messages (e.g., "image", "file")
            stop_on_error: If True, stop batch on first error

        Returns:
            List of TaskResult objects, one per item
        """
        self._running = True
        self._cancelled = False
        results = []
        total = len(items)

        try:
            for i, item in enumerate(items):
                if self._cancelled:
                    # Mark remaining items as cancelled
                    for _ in range(i, total):
                        results.append(TaskResult(
                            success=False,
                            error_message="Cancelled"
                        ))
                    break

                # Update progress
                self.update_progress(
                    current=i + 1,
                    total=total,
                    message=f"Processing {item_label} {i + 1} of {total}"
                )

                if on_progress:
                    on_progress(self._progress)

                # Execute the task
                result = await self.run_safe(
                    process_func,
                    item,
                    task_type=task_type
                )
                results.append(result)

                if not result.success and stop_on_error:
                    # Mark remaining as skipped
                    for _ in range(i + 1, total):
                        results.append(TaskResult(
                            success=False,
                            error_message="Skipped due to previous error"
                        ))
                    break

                # Yield control to event loop for UI updates
                await asyncio.sleep(0)

            # Final progress update
            self.update_progress(
                current=total,
                total=total,
                message="Complete"
            )
            if on_progress:
                on_progress(self._progress)

        finally:
            self._running = False

        return results


class TaskDialog:
    """
    A dialog that displays progress while running a long task.

    Usage:
        async with TaskDialog("Processing images...") as dialog:
            result = await dialog.run(my_blocking_func, arg1, task_type=TaskType.CPU)

        # Or for batch processing:
        async with TaskDialog("Processing images...", show_progress=True) as dialog:
            results = await dialog.run_batch(images, process_image, task_type=TaskType.CPU)
    """

    def __init__(
        self,
        title: str = "Processing...",
        show_progress: bool = False,
        show_cancel: bool = True,
        auto_close: bool = True
    ):
        self.title = title
        self.show_progress = show_progress
        self.show_cancel = show_cancel
        self.auto_close = auto_close
        self.runner = TaskRunner()
        self._dialog = None
        self._status_label = None
        self._progress_bar = None

    async def __aenter__(self):
        """Create and open the dialog."""
        with ui.dialog() as self._dialog:
            with ui.card().classes('w-full max-w-md'):
                with ui.column().classes('w-full gap-4'):
                    # Header with spinner and title
                    with ui.row().classes('items-center gap-3'):
                        ui.spinner('dots', size='lg', color='primary')
                        self._status_label = ui.label(self.title).classes(
                            'text-lg font-medium'
                        )

                    # Progress bar (optional)
                    if self.show_progress:
                        self._progress_bar = ui.linear_progress(
                            value=0,
                            show_value=False
                        ).classes('w-full')
                        self._progress_label = ui.label('').classes(
                            'text-sm text-gray-500'
                        )

                    # Cancel button (optional)
                    if self.show_cancel:
                        with ui.row().classes('w-full justify-end'):
                            ui.button(
                                'Cancel',
                                on_click=self._on_cancel
                            ).props('flat color=negative')

        self._dialog.open()
        # Small delay to ensure dialog is rendered
        await asyncio.sleep(0.05)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close the dialog."""
        if self.auto_close and self._dialog:
            self._dialog.close()
        return False  # Don't suppress exceptions

    def _on_cancel(self):
        """Handle cancel button click."""
        self.runner.cancel()
        if self._status_label:
            self._status_label.set_text("Cancelling...")

    def _update_progress(self, progress: TaskProgress):
        """Update the progress UI."""
        if self._progress_bar:
            self._progress_bar.set_value(progress.percentage / 100)
        if hasattr(self, '_progress_label') and self._progress_label:
            self._progress_label.set_text(progress.message)

    def set_status(self, message: str):
        """Update the status message."""
        if self._status_label:
            self._status_label.set_text(message)

    async def run(
        self,
        func: Callable[..., T],
        *args,
        task_type: TaskType = TaskType.IO,
        **kwargs
    ) -> T:
        """
        Run a single blocking function.

        Args:
            func: The blocking function
            *args: Arguments for func
            task_type: IO or CPU bound
            **kwargs: Keyword arguments for func

        Returns:
            Result of func
        """
        return await self.runner.run(func, *args, task_type=task_type, **kwargs)

    async def run_batch(
        self,
        items: List[Any],
        process_func: Callable[[Any], T],
        task_type: TaskType = TaskType.IO,
        item_label: str = "item",
        stop_on_error: bool = False
    ) -> List[TaskResult[T]]:
        """
        Run a batch operation with progress tracking.

        Args:
            items: Items to process
            process_func: Function to process each item
            task_type: IO or CPU bound
            item_label: Label for progress messages
            stop_on_error: Stop on first error

        Returns:
            List of TaskResult objects
        """
        return await self.runner.run_batch(
            items=items,
            process_func=process_func,
            task_type=task_type,
            on_progress=self._update_progress,
            item_label=item_label,
            stop_on_error=stop_on_error
        )

    def close(self):
        """Manually close the dialog."""
        if self._dialog:
            self._dialog.close()


# Convenience function for simple cases
async def run_with_dialog(
    func: Callable[..., T],
    *args,
    title: str = "Processing...",
    task_type: TaskType = TaskType.IO,
    **kwargs
) -> T:
    """
    Run a blocking function with a simple progress dialog.

    Args:
        func: The blocking function to execute
        *args: Arguments for func
        title: Dialog title
        task_type: IO or CPU bound
        **kwargs: Keyword arguments for func

    Returns:
        Result of func
    """
    async with TaskDialog(title=title, show_progress=False) as dialog:
        return await dialog.run(func, *args, task_type=task_type, **kwargs)


async def run_batch_with_dialog(
    items: List[Any],
    process_func: Callable[[Any], T],
    title: str = "Processing...",
    task_type: TaskType = TaskType.IO,
    item_label: str = "item"
) -> List[TaskResult[T]]:
    """
    Run a batch operation with a progress dialog.

    Args:
        items: Items to process
        process_func: Function to process each item
        title: Dialog title
        task_type: IO or CPU bound
        item_label: Label for progress messages

    Returns:
        List of TaskResult objects
    """
    async with TaskDialog(title=title, show_progress=True) as dialog:
        return await dialog.run_batch(
            items=items,
            process_func=process_func,
            task_type=task_type,
            item_label=item_label
        )
