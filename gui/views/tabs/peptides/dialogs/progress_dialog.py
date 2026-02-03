"""Universal progress dialog."""

import flet as ft
import asyncio


class ProgressDialog:
    """
    Universal progress dialog for long-running operations.
    
    Usage:
        dialog = ProgressDialog(page, "Loading Data")
        dialog.show()
        
        dialog.update_progress(0.5, "Processing 50/100...")
        
        dialog.complete("Done! Processed 100 items")
        await asyncio.sleep(1)
        dialog.close()
    """
    
    def __init__(
        self,
        page: ft.Page,
        title: str,
        show_details: bool = True,
        width: int = 400
    ):
        """
        Initialize progress dialog.
        
        Args:
            page: Flet page
            title: Dialog title
            show_details: Show details text below progress bar
            width: Dialog width
        """
        self.page = page
        
        self.progress_text = ft.Text("Processing...")
        self.progress_bar = ft.ProgressBar(value=0)
        self.progress_details = ft.Text("", size=11, color=ft.Colors.GREY_600)
        
        content_controls = [
            self.progress_text,
            self.progress_bar
        ]
        
        if show_details:
            content_controls.append(ft.Container(height=5))
            content_controls.append(self.progress_details)
        
        self.dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Column(content_controls, tight=True, width=width),
            modal=True
        )
    
    def show(self):
        """Show dialog."""
        self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()
    
    def close(self):
        """Close dialog."""
        self.dialog.open = False
        self.page.update()
    
    def update_progress(
        self,
        value: float | None,
        status: str = "",
        details: str = ""
    ):
        """
        Update progress.
        
        Args:
            value: Progress value (0.0-1.0) or None for indeterminate
            status: Status text
            details: Details text
        """
        if value is not None:
            self.progress_bar.value = value
        else:
            self.progress_bar.value = None
        
        if status:
            self.progress_text.value = status
        
        if details:
            self.progress_details.value = details
        
        self.progress_text.update()
        self.progress_bar.update()
        self.progress_details.update()
    
    def complete(self, message: str = "Complete!"):
        """Mark as complete."""
        self.progress_text.value = message
        self.progress_bar.value = 1.0
        self.progress_text.update()
        self.progress_bar.update()
    
    async def run_with_progress(
        self,
        coro,
        status: str = "Processing...",
        complete_message: str = "Complete!",
        auto_close_delay: float = 1.0
    ):
        """
        Run coroutine with progress dialog.
        
        Args:
            coro: Async coroutine to run
            status: Initial status text
            complete_message: Completion message
            auto_close_delay: Delay before auto-close (seconds)
        
        Returns:
            Result from coroutine
        """
        self.show()
        self.update_progress(None, status)
        
        try:
            result = await coro
            self.complete(complete_message)
            await asyncio.sleep(auto_close_delay)
            self.close()
            return result
        except Exception as ex:
            self.close()
            raise ex
