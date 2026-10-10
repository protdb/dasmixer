"""PRIDE dataset import section."""

import flet as ft

from .base_section import BaseSection


class PrideImportSection(BaseSection):
    """Section for importing PRIDE datasets."""

    def _build_content(self) -> ft.Control:
        return ft.Column([
            ft.Text("Import From PRIDE", size=18, weight=ft.FontWeight.BOLD),
            ft.ElevatedButton(
                content=ft.Text("Import PRIDE dataset..."),
                icon=ft.Icons.CLOUD_DOWNLOAD,
                on_click=lambda e: self.parent_tab.show_import_pride(),
            ),
        ], spacing=10)
