"""Progress dialog for long-running operations."""

import flet as ft


class ProgressDialog(ft.AlertDialog):
    """
    Modal dialog with progress bar for long-running operations.
    
    Example:
        >>> dialog = ProgressDialog("Importing files...")
        >>> page.dialog = dialog
        >>> dialog.open = True
        >>> page.update()
        >>> 
        >>> for i in range(100):
        >>>     dialog.update_progress(i / 100, f"Processing {i+1}/100")
        >>>     # do work
        >>> 
        >>> dialog.open = False
        >>> page.update()
    """
    
    def __init__(self, title: str = "Processing...", cancelable: bool = False):
        """
        Initialize progress dialog.
        
        Args:
            title: Dialog title
            cancelable: If True, shows Cancel button (not implemented yet)
        """
        self.progress_bar = ft.ProgressBar(width=400, value=0)
        self.status_text = ft.Text("", size=14)
        self.cancelable = cancelable
        self._cancelled = False
        
        content_items = [
            ft.Container(content=self.progress_bar, padding=ft.padding.only(bottom=10)),
            self.status_text
        ]
        
        super().__init__(
            title=ft.Text(title, size=18, weight=ft.FontWeight.BOLD),
            content=ft.Column(
                content_items,
                tight=True,
                width=450
            ),
            modal=True
        )
    
    def update_progress(self, value: float, status: str = ""):
        self.progress_bar.value = max(0.0, min(1.0, value))
        self.status_text.value = status
        try:
            self.update()
        except Exception:
            pass
    
    def is_cancelled(self) -> bool:
        """Check if user cancelled the operation."""
        return self._cancelled
    
    def reset(self):
        """Reset progress to zero."""
        self.progress_bar.value = 0
        self.status_text.value = ""
        self._cancelled = False
