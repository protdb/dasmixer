"""Dialog for importing a multi-file mzTab identification file."""

from pathlib import Path

import flet as ft
from dasmixer.api.inputs.registry import registry
from dasmixer.api.project.project import Project
from dasmixer.gui.utils import show_snack

from dasmixer.utils import logger


class ImportMzTabDialog:
    """Dialog for multi-file mzTab identification import.

    One mzTab file may reference several spectra files (via ms_run locations).
    The user picks the file, optionally enables protein collection, chooses a
    duplicate policy, and starts the import. Sample/spectra binding is resolved
    by the import handler from the file's ms_run metadata (no per-file sample
    name).
    """

    def __init__(
        self,
        project: Project,
        page: ft.Page,
        tool_id: int,
        on_import_callback=None,
    ):
        self.project = project
        self.page = page
        self.tool_id = tool_id
        self.on_import_callback = on_import_callback

        self._file_path: Path | None = None
        self._tool = None
        self._parser_class = None

        self._cb_collect_proteins: ft.Checkbox | None = None
        self._cb_is_uniprot: ft.Checkbox | None = None
        self._on_duplicates_group: ft.RadioGroup | None = None

        self.dialog: ft.AlertDialog | None = None

    async def show(self):
        """Pick a file, then show the configuration dialog."""
        try:
            result = await ft.FilePicker().pick_files(
                dialog_title="Select mzTab Identification File",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["mztab", "mzTab", "tsv"],
                allow_multiple=False,
            )
        except Exception as ex:
            logger.exception(ex)
            show_snack(self.page, f"Error opening file picker: {ex}", ft.Colors.RED_400)
            self.page.update()
            return

        if not result or not result[0].path:
            return

        self._file_path = Path(result[0].path)

        self._tool = await self.project.get_tool(self.tool_id)
        if not self._tool:
            show_snack(self.page, "Tool not found", ft.Colors.RED_400)
            self.page.update()
            return

        self._parser_class = registry.get_parser(self._tool.parser, "identification")
        supports_proteins = getattr(self._parser_class, "contain_proteins", False)

        protein_section = ft.Container()
        if supports_proteins:
            self._cb_collect_proteins = ft.Checkbox(
                label="Import protein IDs from file",
                value=False,
            )
            self._cb_is_uniprot = ft.Checkbox(
                label="Proteins are UniProt IDs",
                value=False,
            )
            protein_section = ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Protein import options:", weight=ft.FontWeight.BOLD, size=12),
                        self._cb_collect_proteins,
                        self._cb_is_uniprot,
                    ],
                    spacing=5,
                ),
                padding=10,
                border=ft.border.all(1, ft.Colors.GREEN_300),
                border_radius=5,
                bgcolor=ft.Colors.GREEN_50,
            )

        self._on_duplicates_group = ft.RadioGroup(
            value="skip",
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text("On duplicates:", weight=ft.FontWeight.BOLD, size=12),
                        ft.Radio(value="skip", label="Skip"),
                        ft.Radio(value="reload", label="Reload"),
                        ft.Radio(value="add_as_new", label="Add as new"),
                    ],
                    spacing=2,
                ),
                padding=10,
                border=ft.border.all(1, ft.Colors.GREY_300),
                border_radius=5,
            ),
        )

        self.dialog = ft.AlertDialog(
            title=ft.Text(f"Import Multi-file mzTab — {self._tool.name}"),
            content=ft.Column(
                [
                    ft.Text(
                        f"File: {self._file_path.name}",
                        weight=ft.FontWeight.BOLD,
                        size=12,
                    ),
                    ft.Text(
                        "Identifications will be matched to spectra files via the "
                        "ms_run locations stored in the file.",
                        size=11,
                        italic=True,
                        color=ft.Colors.GREY_600,
                    ),
                    ft.Container(height=8),
                    protein_section,
                    self._on_duplicates_group,
                ],
                tight=True,
                width=550,
                scroll=ft.ScrollMode.AUTO,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self._close),
                ft.ElevatedButton(
                    content=ft.Text("Import"),
                    icon=ft.Icons.DOWNLOAD,
                    on_click=lambda e: self.page.run_task(self._start_import, e),
                ),
            ],
        )
        self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    def _close(self, e=None):
        if self.dialog:
            self.dialog.open = False
        self.page.update()

    async def _start_import(self, e):
        self._close()

        if not self.on_import_callback:
            return

        collect = bool(self._cb_collect_proteins and self._cb_collect_proteins.value)
        is_uniprot = bool(self._cb_is_uniprot and self._cb_is_uniprot.value)
        on_duplicates = self._on_duplicates_group.value or "skip"

        try:
            await self.on_import_callback(
                self._file_path,
                self.tool_id,
                collect_proteins=collect,
                is_uniprot_proteins=is_uniprot,
                on_duplicates=on_duplicates,
            )
        except Exception as ex:
            logger.exception(ex)
            show_snack(self.page, f"Import error: {ex}", ft.Colors.RED_400)
            self.page.update()
