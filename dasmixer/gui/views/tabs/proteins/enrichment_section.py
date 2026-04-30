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

    async def _run_enrich(self, e=None):
        """Run protein enrichment from UniProt with progress dialog."""
        force_update = self.force_update_checkbox.value
        overwrite_fasta = self.update_fasta_checkbox.value

        from dasmixer.gui.components.progress_dialog import ProgressDialog
        from dasmixer.gui.utils import show_snack

        dialog = ProgressDialog("Enriching proteins from UniProt...")
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

        processed = 0
        total = 0
        try:
            async for protein_id, total in enrich_proteins(
                self.project,
                force_update=force_update,
                overwrite_fasta=overwrite_fasta
            ):
                processed += 1
                progress_value = processed / total if total > 0 else 0
                dialog.update_progress(
                    progress_value,
                    f"Processing {processed}/{total}: {protein_id}"
                )

        except Exception as ex:
            from dasmixer.utils import logger
            logger.exception(ex)
            dialog.open = False
            self.page.update()
            show_snack(self.page, f"Enrichment error: {ex}", ft.Colors.RED_400)
            self.page.update()
            return

        dialog.open = False
        self.page.update()
        show_snack(
            self.page,
            f"Enrichment complete: {processed} proteins processed",
            ft.Colors.GREEN_400
        )
        self.page.update()

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
            on_click=lambda e: self.page.run_task(self._run_enrich),
        )

        control = ft.Column([
            ft.Text("Enrich protein metadata from UniProt KB", size=18, weight=ft.FontWeight.BOLD),
            ft.Row([self.update_fasta_checkbox, self.force_update_checkbox]),
            self.calculate_btn,
        ], spacing=10)

        return control