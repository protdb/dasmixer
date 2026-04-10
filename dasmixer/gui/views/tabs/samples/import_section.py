"""Import section - import spectra files."""

import flet as ft
from dasmixer.api.project.project import Project
from .base_section import BaseSection
from .shared_state import SamplesTabState


class ImportSection(BaseSection):
    """Section for importing spectra files."""
    
    def _build_content(self) -> ft.Control:
        """Build section content."""
        return ft.Column([
            ft.Text("Import Spectra", size=18, weight=ft.FontWeight.BOLD),
            ft.ElevatedButton(
                content=ft.Text("Import Spectra Files"),
                icon=ft.Icons.UPLOAD_FILE,
                on_click=lambda e: self.parent_tab.show_import_spectra()
            )
        ], spacing=10)
