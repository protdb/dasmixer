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
        on_pattern_callback=None,
        on_stacked_callback=None,
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
            on_stacked_callback: Callback for stacked file import mode
        """
        self.project = project
        self.page = page
        self.import_type = import_type
        self.tool_id = tool_id
        self.on_single_files_callback = on_single_files_callback
        self.on_pattern_callback = on_pattern_callback
        self.on_stacked_callback = on_stacked_callback
        
        self.dialog = None
    
    async def show(self):
        """Show the dialog immediately, then fill content asynchronously."""
        # Show dialog right away with a loading indicator
        self._content_col = ft.Column(
            [ft.ProgressRing(width=28, height=28, stroke_width=3)],
            tight=True,
            width=400,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.dialog = ft.AlertDialog(
            title=ft.Text("Import Spectra" if self.import_type == "spectra" else "Import Identifications"),
            content=self._content_col,
            actions=[ft.TextButton("Cancel", on_click=self._close)],
        )
        self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

        # Now fetch data and replace content
        if self.import_type == "spectra":
            title = "Import Spectra"
            desc = "Import mass spectrometry spectra data files"
        else:
            tool = await self.project.get_tool(self.tool_id)
            title = f"Import Identifications — {tool.name}"
            desc = f"Import identification files for {tool.name}"

        # Check stacked support
        show_stacked_btn = False
        if self.import_type == "identifications" and self.tool_id:
            from dasmixer.api.inputs.registry import registry as _registry
            _tool = await self.project.get_tool(self.tool_id)
            if _tool:
                _parser_class = _registry.get_parser(_tool.parser, "identification")
                show_stacked_btn = getattr(_parser_class, 'can_import_stacked', False)

        self.dialog.title = ft.Text(title)
        controls = [
            ft.Text("Choose import mode:", size=16, weight=ft.FontWeight.BOLD),
            ft.Text(desc, size=11, italic=True, color=ft.Colors.GREY_600),
            ft.Container(height=10),
            ft.ElevatedButton(
                content=ft.Text("Select individual files"),
                icon=ft.Icons.INSERT_DRIVE_FILE,
                on_click=lambda e: self.page.run_task(self._on_single_files, e),
                width=300,
            ),
            ft.Container(height=5),
            ft.ElevatedButton(
                content=ft.Text("Pattern matching from folder"),
                icon=ft.Icons.FOLDER_OPEN,
                on_click=lambda e: self.page.run_task(self._on_pattern, e),
                width=300,
            ),
        ]
        if show_stacked_btn:
            controls += [
                ft.Container(height=5),
                ft.ElevatedButton(
                    content=ft.Text("Import stacked file"),
                    icon=ft.Icons.TABLE_VIEW,
                    on_click=lambda e: self.page.run_task(self._on_stacked, e),
                    width=300,
                ),
                ft.Container(height=5),
                ft.Text(
                    "Stacked file contains identifications for multiple samples",
                    size=11,
                    italic=True,
                    color=ft.Colors.GREY_600,
                ),
            ]
        controls += [
            ft.Container(height=10),
            ft.Text(
                "Pattern matching allows automatic sample ID extraction from filenames",
                size=11,
                italic=True,
                color=ft.Colors.GREY_600,
            ),
        ]
        self._content_col.controls = controls
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
    
    async def _on_stacked(self, e):
        """Handle stacked file import mode selection."""
        self._close()
        if self.on_stacked_callback:
            await self.on_stacked_callback()
