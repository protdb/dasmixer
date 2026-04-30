"""Dialog for pattern-based file import."""

import flet as ft
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List
from dasmixer.api.project.project import Project
from dasmixer.api.inputs.registry import registry
from dasmixer.utils.seek_files import seek_files
from dasmixer.gui.utils import show_snack
from dasmixer.utils import logger


@dataclass
class FileEntry:
    path: Path
    sample_id: str        # пустая строка если не определён
    included: bool = True
    checkbox: object = None   # ft.Checkbox
    id_field: object = None   # ft.TextField


class ImportPatternDialog:
    """Dialog for importing files using pattern matching."""

    def __init__(
        self,
        project: Project,
        page: ft.Page,
        import_type: str,
        tool_id: Optional[int] = None,
        on_import_callback=None
    ):
        """
        Initialize pattern import dialog.

        Args:
            project: Project instance
            page: Flet page
            import_type: "spectra" or "identifications"
            tool_id: Tool ID (required for identifications)
            on_import_callback: Callback(file_list, subset_id, parser_name) or
                               callback(file_list, tool_id) for identifications
        """
        self.project = project
        self.page = page
        self.import_type = import_type
        self.tool_id = tool_id
        self.on_import_callback = on_import_callback

        # Dialog controls
        self.folder_field = None
        self.file_pattern_field = None
        self.id_pattern_field = None
        self.parser_dropdown = None
        self.group_dropdown = None
        self.files_list = None
        self.dialog = None
        self._file_entries: List[FileEntry] = []
        self._import_btn = None

    async def show(self):
        """Show dialog immediately, then load data and populate fields."""
        dlg_title = f"Import {self.import_type.title()} — Pattern Matching"

        # Open spinner dialog right away
        self.dialog = ft.AlertDialog(
            title=ft.Text(dlg_title),
            content=ft.Container(
                content=ft.ProgressRing(width=28, height=28, stroke_width=3),
                alignment=ft.Alignment.CENTER,
                width=700,
                height=80,
            ),
            actions=[ft.TextButton("Cancel", on_click=self._close)],
        )
        self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

        # Fetch data
        if self.import_type == "spectra":
            parsers = registry.get_spectra_parsers()
            parser_type_label = "Spectra Format"
            default_pattern = "*.mgf"
            default_id_pattern = "{id}.mgf"

            parser_options = [
                ft.DropdownOption(
                    key=name,
                    text=f"{name} - {parser_class.__doc__.split('.')[0].strip() if parser_class.__doc__ else name}",
                )
                for name, parser_class in parsers.items()
            ]

            if not parser_options:
                self.dialog.open = False
                self.page.update()
                show_snack(self.page, "No spectra parsers available", ft.Colors.RED_400)
                self.page.update()
                return

            groups = await self.project.get_subsets()
            group_options = [ft.DropdownOption(key=str(g.id), text=g.name) for g in groups]

            if not group_options:
                self.dialog.open = False
                self.page.update()
                show_snack(self.page, "Please create at least one comparison group first", ft.Colors.ORANGE_400)
                self.page.update()
                return
        else:
            tool = await self.project.get_tool(self.tool_id) if self.tool_id else None
            parser_name = tool.parser if tool else "Unknown"
            parser_type_label = f"Format: {parser_name}"
            default_pattern = "*.csv"
            default_id_pattern = "{id}*.csv"
            parser_options = None
            group_options = None

            samples = await self.project.get_samples()
            if not samples:
                self.dialog.open = False
                self.page.update()
                show_snack(self.page, "Please import spectra first", ft.Colors.ORANGE_400)
                self.page.update()
                return

        # Build fields
        self.folder_field = ft.TextField(
            label="Folder path", hint_text="/path/to/files", expand=True
        )
        file_pattern_help = ft.Tooltip(
            message=(
                "File search pattern with glob syntax support.\n"
                "Examples:\n"
                "  *.mgf — all MGF files in folder\n"
                "  **/*.mgf — recursive search\n"
                "  sample_*.csv — files with prefix"
            )
        )
        self.file_pattern_field = ft.TextField(
            label="File pattern",
            value=default_pattern,
            hint_text=f"e.g., {default_pattern}",
            tooltip=file_pattern_help,
            width=200,
        )

        id_pattern_help = ft.Tooltip(
            message=(
                "Pattern for extracting sample ID from file name.\n"
                "Use {id} to mark the part that becomes the Sample ID.\n"
                "Examples:\n"
                "  {id}.mgf — 'Sample1.mgf' → ID = 'Sample1'\n"
                "  sample_{id}.csv — 'sample_ABC.csv' → ID = 'ABC'\n"
                "  {id}_{}_results.csv — '2024-01-15_S01_results.csv' → ID = '2024-01-15'\n"
                "  {id}_results.csv — 'S01_results.csv' → ID = 'S01'"
            )
        )

        self.id_pattern_field = ft.TextField(
            label="Sample ID pattern",
            value=default_id_pattern,
            hint_text=f"e.g., {default_id_pattern}",
            tooltip=id_pattern_help,
            expand=True,
        )


        dropdown_controls = []
        if self.import_type == "spectra":
            self.parser_dropdown = ft.Dropdown(
                label=parser_type_label,
                options=parser_options,
                value=parser_options[0].key,
                width=300,
            )
            dropdown_controls.append(self.parser_dropdown)
            self.group_dropdown = ft.Dropdown(
                label="Assign to group",
                options=group_options,
                value=group_options[0].key,
                width=200,
            )
            dropdown_controls.append(self.group_dropdown)
        else:
            dropdown_controls.append(
                ft.Text(parser_type_label, weight=ft.FontWeight.BOLD, size=14)
            )

        self.files_list = ft.ListView(spacing=3, height=250)
        dropdown_row = ft.Row(dropdown_controls, spacing=10) if dropdown_controls else ft.Container()

        self._import_btn = ft.ElevatedButton(
            "Import",
            icon=ft.Icons.DOWNLOAD,
            disabled=True,
            on_click=lambda e: self.page.run_task(self._start_import, e),
        )

        # Replace spinner with real form
        self.dialog.content = ft.Column(
            [
                ft.Row(
                    [
                        self.folder_field,
                        ft.IconButton(
                            icon=ft.Icons.FOLDER_OPEN,
                            on_click=lambda e: self.page.run_task(self._browse_folder, e),
                        ),
                    ],
                    spacing=5,
                ),
                ft.Row(
                    [self.file_pattern_field, self.id_pattern_field],
                    spacing=10,
                ),
                dropdown_row,
                ft.Container(height=5),
                ft.ElevatedButton(
                    content=ft.Text("Preview Files"),
                    icon=ft.Icons.PREVIEW,
                    on_click=lambda e: self.page.run_task(self._preview_files, e),
                ),
                ft.Container(height=5),
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.TextButton(
                                    "Select All",
                                    icon=ft.Icons.CHECK_BOX,
                                    on_click=self._select_all_files,
                                ),
                                ft.TextButton(
                                    "Deselect All",
                                    icon=ft.Icons.CHECK_BOX_OUTLINE_BLANK,
                                    on_click=self._deselect_all_files,
                                ),
                            ],
                            spacing=5,
                        ),
                        ft.Container(
                            content=self.files_list,
                            border=ft.border.all(1, ft.Colors.GREY_300),
                            border_radius=5,
                            padding=10,
                        ),
                    ],
                    spacing=5,
                ),
            ],
            tight=True,
            width=700,
            scroll=ft.ScrollMode.AUTO,
        )
        self.dialog.actions = [
            ft.TextButton("Cancel", on_click=self._close),
            self._import_btn,
        ]
        self.page.update()

    def _close(self, e=None):
        """Close the dialog."""
        self.dialog.open = False
        self.page.update()

    async def _browse_folder(self, e):
        """Browse for folder using FilePicker."""
        try:
            folder_path = await ft.FilePicker().get_directory_path(
                dialog_title=f"Select Folder with {self.import_type.title()} Files"
            )
            if folder_path:
                self.folder_field.value = folder_path
                self.folder_field.update()
        except Exception as ex:
            logger.exception(ex)
            show_snack(self.page, f"Error selecting folder: {ex}", ft.Colors.RED_400)
            self.page.update()

    async def _preview_files(self, e):
        """Preview files matching the pattern."""
        if not self.folder_field.value:
            show_snack(self.page, "Please select a folder first", ft.Colors.ORANGE_400)
            self.page.update()
            return

        try:
            folder_path = Path(self.folder_field.value)
            if not folder_path.exists():
                show_snack(self.page, "Folder does not exist", ft.Colors.RED_400)
                self.page.update()
                return

            # Find files using pattern
            found_files = seek_files(
                folder_path,
                self.file_pattern_field.value,
                self.id_pattern_field.value
            )

            self._file_entries.clear()
            self.files_list.controls.clear()

            if not found_files:
                self.files_list.controls.append(
                    ft.Text("No files found", italic=True, color=ft.Colors.GREY_600)
                )
                self._update_import_btn_state()
                self.files_list.update()
                return

            self.files_list.controls.append(
                ft.Text(f"Found {len(found_files)} file(s):", weight=ft.FontWeight.BOLD)
            )

            for file_path, sample_id in found_files:
                sample_id_str = sample_id if sample_id and sample_id != "UNKNOWN" else ""

                entry = FileEntry(path=file_path, sample_id=sample_id_str)

                cb = ft.Checkbox(
                    value=True,
                    on_change=lambda e, en=entry: self._on_entry_toggle(en, e),
                )
                entry.checkbox = cb

                id_tf = ft.TextField(
                    value=entry.sample_id,
                    width=180,
                    hint_text="Sample ID",
                    border_color=ft.Colors.RED if not entry.sample_id.strip() else None,
                    on_change=lambda e, en=entry: self._on_id_change(en, e),
                )
                entry.id_field = id_tf

                self._file_entries.append(entry)

                self.files_list.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [cb, ft.Text(file_path.name, size=12, expand=True), id_tf],
                            spacing=5,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.padding.symmetric(vertical=2, horizontal=2),
                    )
                )

            self._update_import_btn_state()
            self.files_list.update()

        except Exception as ex:
            logger.exception(ex)
            show_snack(self.page, f"Error: {ex}", ft.Colors.RED_400)
            self.page.update()

    # ------------------------------------------------------------------
    # Entry state handlers
    # ------------------------------------------------------------------

    def _on_entry_toggle(self, entry: FileEntry, e):
        entry.included = e.control.value
        if entry.id_field:
            entry.id_field.border_color = (
                ft.Colors.RED if (entry.included and not entry.sample_id.strip()) else None
            )
            if entry.id_field.page:
                entry.id_field.update()
        self._update_import_btn_state()

    def _on_id_change(self, entry: FileEntry, e):
        entry.sample_id = e.control.value or ""
        if entry.id_field:
            entry.id_field.border_color = (
                ft.Colors.RED if (entry.included and not entry.sample_id.strip()) else None
            )
            if entry.id_field.page:
                entry.id_field.update()
        self._update_import_btn_state()

    def _select_all_files(self, e):
        for entry in self._file_entries:
            entry.included = True
            if entry.checkbox:
                entry.checkbox.value = True
                if entry.checkbox.page:
                    entry.checkbox.update()
        self._update_import_btn_state()

    def _deselect_all_files(self, e):
        for entry in self._file_entries:
            entry.included = False
            if entry.checkbox:
                entry.checkbox.value = False
                if entry.checkbox.page:
                    entry.checkbox.update()
        self._update_import_btn_state()

    def _update_import_btn_state(self):
        """Activate Import button only when preview done and all included files have Sample ID."""
        if self._import_btn is None:
            return
        if not self._file_entries:
            self._import_btn.disabled = True
        else:
            all_ok = all(
                (not entry.included) or bool(entry.sample_id.strip())
                for entry in self._file_entries
            )
            self._import_btn.disabled = not all_ok
        if self._import_btn.page:
            self._import_btn.update()

    # ------------------------------------------------------------------
    # Import
    # ------------------------------------------------------------------

    async def _start_import(self, e):
        """Start the import process using cached file entries."""
        included_files = [
            (entry.path, entry.sample_id)
            for entry in self._file_entries
            if entry.included and entry.sample_id.strip()
        ]

        if not included_files:
            show_snack(self.page, "No files selected for import", ft.Colors.ORANGE_400)
            self.page.update()
            return

        self._close()

        if self.on_import_callback:
            if self.import_type == "spectra":
                await self.on_import_callback(
                    included_files,
                    int(self.group_dropdown.value),
                    self.parser_dropdown.value
                )
            else:
                await self.on_import_callback(
                    included_files,
                    self.tool_id
                )
