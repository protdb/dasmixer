import flet as ft
from .base_section import BaseSection
from dasmixer.api.calculations.proteins.enrich import enrich_proteins


class EnrichmentSection(BaseSection):
    def __init__(self, project, state, parent_tab):
        """
        Initialize LFQ section.

        Args:
            project: Project instance
            state: Shared state
            parent_tab: Reference to parent ProteinsTab
        """
        self.parent_tab = parent_tab
        super().__init__(project, state)

    def _build_content(self) -> ft.Control:
        self.force_update_checkbox = ft.Checkbox(
            label="Force update",
            value=False,
        )
        self.update_fasta_checkbox = ft.Checkbox(
            label="Overwrite names from FASTA",
            value=True,
        )

        self.calculate_btn = ft.ElevatedButton(
            content=ft.Text("Enrich proteins data from UniProt"),
            icon=ft.Icons.CLOUD_DOWNLOAD_OUTLINED,
            on_click=lambda e: print("NOT IMPLEMENTED"),
        )

        control = ft.Column([
            ft.Text("Enrich protein metadata from UniProt KB", size=18, weight=ft.FontWeight.BOLD),
            ft.Row([self.update_fasta_checkbox, self.force_update_checkbox]),
            self.calculate_btn,
        ], spacing=10)