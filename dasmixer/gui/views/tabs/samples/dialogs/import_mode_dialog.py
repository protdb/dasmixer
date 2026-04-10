"""Dialog for selecting import mode."""

import flet as ft
from dasmixer.api.project.project import Project


class ImportModeDialog:
    """Dialog for selecting import mode: single files or pattern matching."""
    
    def __init__(
        self,
        project: Project,
        page: ft.Page,
        import_type: str,
        tool_id: int = None,
        on_single_files_callback=None,
        on_pattern_callback=None
    ):
        """
        Initialize import mode dialog.
        
        Args:
            project: Project instance
            page: Flet page
            import_type: "spectra" or "identifications"
            tool_id: Tool ID (required for identifications)
            on_single_files_callback: Callback for single files mode
            on_pattern_callback: Callback for pattern matching mode
        """
        self.project = project
        self.page = page
        self.import_type = import_type
        self.tool_id = tool_id
        self.on_single_files_callback = on_single_files_callback
        self.on_pattern_callback = on_pattern_callback
        
        self.dialog = None
    
    async def show(self):
        """Show the dialog."""
        # Configure dialog text based on import type
        if self.import_type == "spectra":
            title = "Import Spectra"
            desc = "Import mass spectrometry spectra data files"
        else:
            # Get tool name
            tool = await self.project.get_tool(self.tool_id)
            title = f"Import Identifications - {tool.name}"
            desc = f"Import identification files for {tool.name}"
        
        # Create dialog
        self.dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Column([
                ft.Text("Choose import mode:", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(desc, size=11, italic=True, color=ft.Colors.GREY_600),
                ft.Container(height=10),
                ft.ElevatedButton(
                    content=ft.Text("Select individual files"),
                    icon=ft.Icons.INSERT_DRIVE_FILE,
                    on_click=lambda e: self.page.run_task(self._on_single_files, e),
                    width=300
                ),
                ft.Container(height=5),
                ft.ElevatedButton(
                    content=ft.Text("Pattern matching from folder"),
                    icon=ft.Icons.FOLDER_OPEN,
                    on_click=lambda e: self.page.run_task(self._on_pattern, e),
                    width=300
                ),
                ft.Container(height=10),
                ft.Text(
                    "Pattern matching allows automatic sample ID extraction from filenames",
                    size=11,
                    italic=True,
                    color=ft.Colors.GREY_600
                )
            ], tight=True, width=400),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=self._close
                )
            ]
        )
        
        self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()
    
    def _close(self, e=None):
        """Close the dialog."""
        self.dialog.open = False
        self.page.update()
    
    async def _on_single_files(self, e):
        """Handle single files mode selection."""
        self._close()
        if self.on_single_files_callback:
            await self.on_single_files_callback()
    
    async def _on_pattern(self, e):
        """Handle pattern matching mode selection."""
        self._close()
        if self.on_pattern_callback:
            await self.on_pattern_callback()
