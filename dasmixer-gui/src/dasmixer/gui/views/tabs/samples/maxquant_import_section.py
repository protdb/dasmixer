"""MaxQuant project import section."""

import flet as ft

from .base_section import BaseSection


class MaxQuantImportSection(BaseSection):
    """Section for importing full MaxQuant projects (mqpar.xml + txt + apl)."""

    def _build_content(self) -> ft.Control:
        return ft.Column([
            ft.Text("Import From MaxQuant", size=18, weight=ft.FontWeight.BOLD),
            ft.ElevatedButton(
                content=ft.Text("Import From MaxQuant..."),
                icon=ft.Icons.SCIENCE,
                on_click=lambda e: self.parent_tab.show_import_maxquant(),
            ),
        ], spacing=10)