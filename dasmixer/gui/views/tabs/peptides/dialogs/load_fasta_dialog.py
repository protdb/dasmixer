"""Modal dialog for loading FASTA protein sequence files."""

import asyncio
import flet as ft

from dasmixer.api.inputs.proteins.fasta import FastaParser
from dasmixer.api.project.project import Project
from dasmixer.gui.utils import show_snack


class LoadFastaDialog:
    """
    Modal dialog for selecting and loading a FASTA file into the project database.

    Usage:
        dialog = LoadFastaDialog(project, page, on_loaded_callback)
        await dialog.show()
    """

    def __init__(self, project: Project, page: ft.Page, on_loaded=None):
        """
        Args:
            project: Project instance
            page: Flet page
            on_loaded: async callback(protein_count: int) called after successful load
        """
        self.project = project
        self.page = page
        self.on_loaded = on_loaded
        self._dialog: ft.AlertDialog | None = None
        self._file_path: str | None = None
        self._is_uniprot_cb: ft.Checkbox | None = None
        self._file_path_field: ft.TextField | None = None
        self._load_btn: ft.ElevatedButton | None = None

    async def show(self):
        """Show the FASTA load dialog."""
        self._file_path_field = ft.TextField(
            label="FASTA file path",
            hint_text="Select FASTA file...",
            expand=True,
            read_only=True,
        )

        self._is_uniprot_cb = ft.Checkbox(
            label="Sequences in UniProt format",
            value=True,
        )

        self._load_btn = ft.ElevatedButton(
            "Load",
            icon=ft.Icons.UPLOAD_FILE,
            disabled=True,
            on_click=lambda e: self.page.run_task(self._on_load, e),
        )

        self._dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Load Protein Sequences"),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            self._file_path_field,
                            ft.IconButton(
                                icon=ft.Icons.FOLDER_OPEN,
                                tooltip="Browse",
                                on_click=lambda e: self.page.run_task(self._browse, e),
                            ),
                        ],
                        spacing=5,
                    ),
                    self._is_uniprot_cb,
                ],
                tight=True,
                width=500,
                spacing=12,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self._close),
                self._load_btn,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.overlay.append(self._dialog)
        self._dialog.open = True
        self.page.update()

    async def _browse(self, e):
        """Open file picker."""
        try:
            result = await ft.FilePicker().pick_files(
                dialog_title="Select FASTA File",
                allowed_extensions=["fasta", "fa", "txt"],
                allow_multiple=False,
            )
            if result and result[0].path:
                self._file_path = result[0].path
                self._file_path_field.value = self._file_path
                self._file_path_field.update()
                self._load_btn.disabled = False
                self._load_btn.update()
        except Exception as ex:
            show_snack(self.page, f"Error: {ex}", ft.Colors.RED_400)
            self.page.update()

    async def _on_load(self, e):
        """Start loading FASTA file."""
        if not self._file_path:
            return

        # Switch dialog content to progress mode
        progress_status = ft.Text("Validating...", size=13, color=ft.Colors.GREY_600)
        self._dialog.content = ft.Container(
            content=ft.Column(
                [
                    ft.ProgressRing(width=36, height=36, stroke_width=3),
                    progress_status,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=12,
            ),
            alignment=ft.Alignment.CENTER,
            width=500,
            height=120,
        )
        self._dialog.actions = []
        self.page.update()

        try:
            parser = FastaParser(
                file_path=self._file_path,
                is_uniprot=self._is_uniprot_cb.value,
                enrich_from_uniprot=False,
            )

            if not await parser.validate():
                self._close()
                show_snack(self.page, "Invalid FASTA format", ft.Colors.RED_400)
                self.page.update()
                return

            progress_status.value = "Importing sequences..."
            self.page.update()

            total = 0
            async for batch in parser.parse_batch(batch_size=500):
                await self.project.add_proteins_batch(batch)
                total += len(batch)
                progress_status.value = f"Loaded {total:,} proteins..."
                self.page.update()

            await self.project.save()

            progress_status.value = f"Done: {total:,} proteins loaded"
            self.page.update()
            await asyncio.sleep(1)

            self._close()

            if self.on_loaded:
                await self.on_loaded(total)

        except Exception as ex:
            import traceback
            traceback.print_exc()
            self._close()
            show_snack(self.page, f"Error loading FASTA: {ex}", ft.Colors.RED_400)
            self.page.update()

    def _close(self, e=None):
        if self._dialog:
            self._dialog.open = False
            self.page.update()
