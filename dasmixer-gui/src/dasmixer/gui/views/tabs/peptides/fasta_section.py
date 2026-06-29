"""FASTA loading and protein mapping section."""

import flet as ft

from .base_section import BaseSection
from dasmixer.utils import logger


class FastaSection(BaseSection):
    """Protein sequence library status and mapping configuration."""

    def _build_content(self) -> ft.Control:
        """Build FASTA section UI."""
        self.protein_count_text = ft.Text(
            "No proteins loaded",
            size=12,
            color=ft.Colors.GREY_600,
            italic=True,
        )

        # Load FASTA button — opens modal dialog
        self.load_fasta_btn = ft.ElevatedButton(
            content=ft.Text("Load FASTA"),
            icon=ft.Icons.UPLOAD_FILE,
            on_click=lambda e: self.page.run_task(self._open_load_dialog, e),
        )

        # Protein mapping settings
        self.blast_max_accepts_field = ft.TextField(
            label="BLAST Max Accepts",
            value="5",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        self.blast_max_rejects_field = ft.TextField(
            label="BLAST Max Rejects",
            value="16",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        return ft.Column(
            [
                ft.Text("Protein Sequence Library", size=18, weight=ft.FontWeight.BOLD),
                ft.Row(
                    [self.load_fasta_btn, self.protein_count_text],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=15),
                ft.Text("Protein Mapping Settings", size=16, weight=ft.FontWeight.BOLD),
                ft.Row([self.blast_max_accepts_field, self.blast_max_rejects_field], spacing=10),
            ],
            spacing=10,
        )

    async def load_data(self):
        """Load initial data."""
        await self.load_blast_settings()
        await self.update_protein_count()

    async def update_protein_count(self):
        """Update protein count display."""
        try:
            count = await self.project.get_protein_count()
            self.state.protein_count = count
            if count > 0:
                self.protein_count_text.value = f"{count:,} proteins in database"
                self.protein_count_text.color = ft.Colors.GREEN_700
                self.protein_count_text.italic = False
            else:
                self.protein_count_text.value = "No proteins loaded"
                self.protein_count_text.color = ft.Colors.GREY_600
                self.protein_count_text.italic = True
            if self.protein_count_text.page:
                self.protein_count_text.update()
        except Exception as ex:
            logger.exception(f"Error updating protein count: {ex}")

    async def _open_load_dialog(self, e):
        """Open the FASTA load dialog."""
        from dasmixer.gui.views.tabs.peptides.dialogs.load_fasta_dialog import LoadFastaDialog
        dialog = LoadFastaDialog(
            project=self.project,
            page=self.page,
            on_loaded=self._on_fasta_loaded,
        )
        await dialog.show()

    async def _on_fasta_loaded(self, protein_count: int):
        """Called after successful FASTA load."""
        await self.update_protein_count()
        from dasmixer.gui.utils import show_snack
        if self.page:
            show_snack(self.page, f"Loaded {protein_count:,} proteins", ft.Colors.GREEN_400)
            self.page.update()

    async def load_blast_settings(self):
        """Load BLAST settings from project."""
        try:
            max_accepts = await self.project.get_setting('max_blast_accept', '16')
            max_rejects = await self.project.get_setting('max_blast_reject', '5')
            self.blast_max_accepts_field.value = max_accepts
            self.blast_max_rejects_field.value = max_rejects
        except Exception as ex:
            logger.exception(f"Error loading BLAST settings: {ex}")

    async def save_blast_settings(self):
        """Save BLAST settings to project."""
        await self.project.set_setting('max_blast_accept', self.blast_max_accepts_field.value)
        await self.project.set_setting('max_blast_reject', self.blast_max_rejects_field.value)

    async def match_proteins_internal(self, sample_id: int | None = None):
        """Match proteins to identifications. Called from ActionsSection."""
        from dasmixer.gui.actions.protein_map_action import MatchProteinsAction
        action = MatchProteinsAction(self.project, self.page)
        await action.run(state=self.state, sample_id=sample_id)
