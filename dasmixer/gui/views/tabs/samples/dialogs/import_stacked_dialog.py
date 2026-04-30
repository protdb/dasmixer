"""Dialog for importing a stacked identification file (one file — multiple samples)."""

import flet as ft
from pathlib import Path
from typing import Optional
from dasmixer.api.project.project import Project
from dasmixer.api.inputs.registry import registry
from dasmixer.gui.utils import show_snack
from dasmixer.utils import logger


class ImportStackedDialog:
    """
    Dialog for importing a stacked identification file.
    
    Flow:
    1. User selects a file via FilePicker.
    2. User optionally overrides the "Sample field" (column name).
    3. User clicks "Get samples list" — dialog calls parser.get_sample_ids()
       and populates the sample list with sample_name <-> existing_sample mapping.
    4. User reviews and optionally edits sample name overrides.
    5. User clicks "Import" — for each matched sample, a separate
       identification_file record is created and identifications are imported
       with filtering by sample value.
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
        self._parser_class = None
        self._tool = None
        self._sample_field_override: str | None = None
        
        # Controls
        self.dialog: ft.AlertDialog | None = None
        self._file_path_text: ft.Text | None = None
        self._sample_field_tf: ft.TextField | None = None
        self._samples_list: ft.ListView | None = None
        self._import_btn: ft.ElevatedButton | None = None
        
        # Sample entries: list of {'file_id': str, 'sample_name': ft.TextField, 'include': ft.Checkbox}
        self._sample_entries: list[dict] = []

    async def show(self):
        """Show the stacked import dialog."""
        # Step 1: FilePicker
        result = await ft.FilePicker().pick_files(
            dialog_title="Select Stacked Identification File",
            allow_multiple=False,
        )
        if not result or not result[0].path:
            return
        
        self._file_path = Path(result[0].path)
        
        # Load tool and parser class
        self._tool = await self.project.get_tool(self.tool_id)
        if not self._tool:
            show_snack(self.page, "Tool not found", ft.Colors.RED_400)
            self.page.update()
            return
        
        self._parser_class = registry.get_parser(self._tool.parser, "identification")
        
        # Default sample field
        default_field = getattr(self._parser_class, 'sample_id_column', '') or ''
        
        # Build dialog UI
        self._file_path_text = ft.Text(
            f"File: {self._file_path.name}",
            weight=ft.FontWeight.BOLD,
            size=12,
        )
        self._sample_field_tf = ft.TextField(
            label="Sample field (column name)",
            value=default_field,
            hint_text="e.g. Raw file",
            width=300,
        )
        self._samples_list = ft.ListView(spacing=3, height=260)
        self._import_btn = ft.ElevatedButton(
            content=ft.Text("Import"),
            icon=ft.Icons.DOWNLOAD,
            disabled=True,
            on_click=lambda e: self.page.run_task(self._start_import, e),
        )
        
        self.dialog = ft.AlertDialog(
            title=ft.Text(f"Import Stacked File — {self._tool.name}"),
            content=ft.Column(
                [
                    self._file_path_text,
                    ft.Container(height=8),
                    ft.Row(
                        [
                            self._sample_field_tf,
                            ft.ElevatedButton(
                                content=ft.Text("Get samples list"),
                                icon=ft.Icons.REFRESH,
                                on_click=lambda e: self.page.run_task(self._load_samples, e),
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.END,
                    ),
                    ft.Container(height=8),
                    ft.Text("Match file sample IDs to project samples:", size=13),
                    ft.Text(
                        "Values must match existing sample names exactly. "
                        "Edit manually if needed.",
                        size=11,
                        italic=True,
                        color=ft.Colors.GREY_600,
                    ),
                    ft.Container(
                        content=self._samples_list,
                        border=ft.border.all(1, ft.Colors.GREY_300),
                        border_radius=5,
                        padding=10,
                    ),
                ],
                tight=True,
                width=650,
                scroll=ft.ScrollMode.AUTO,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self._close),
                self._import_btn,
            ],
        )
        self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    async def _load_samples(self, e):
        """Load sample IDs from file and populate the matching list."""
        self._samples_list.controls.clear()
        self._samples_list.controls.append(
            ft.ProgressRing(width=24, height=24, stroke_width=3)
        )
        self._samples_list.update()
        
        try:
            override_col = self._sample_field_tf.value.strip() or None
            
            # Instantiate parser and get sample IDs
            parser = self._parser_class(str(self._file_path))
            sample_ids_in_file = await parser.get_sample_ids(override_column=override_col)
            
            if not sample_ids_in_file:
                self._samples_list.controls = [
                    ft.Text("No samples found in file", italic=True, color=ft.Colors.GREY_600)
                ]
                self._samples_list.update()
                return
            
            # Get existing DB samples for comparison
            db_samples = await self.project.get_samples()
            db_sample_names = {s.name for s in db_samples}
            
            self._sample_entries.clear()
            self._samples_list.controls.clear()
            
            # Header row
            self._samples_list.controls.append(
                ft.Row(
                    [
                        ft.Text("Include", size=11, width=60),
                        ft.Text("ID in file", size=11, width=200, weight=ft.FontWeight.BOLD),
                        ft.Text("Sample name in project", size=11, expand=True, weight=ft.FontWeight.BOLD),
                    ],
                    spacing=5,
                )
            )
            
            for file_sample_id in sample_ids_in_file:
                # Auto-match: exact name match
                matched = file_sample_id if file_sample_id in db_sample_names else ""
                
                include_cb = ft.Checkbox(value=bool(matched))
                sample_tf = ft.TextField(
                    value=matched,
                    hint_text="Project sample name",
                    expand=True,
                    border_color=ft.Colors.RED if not matched else None,
                    on_change=lambda e, sid=file_sample_id: self._on_sample_name_change(sid, e),
                )
                
                entry = {
                    'file_id': file_sample_id,
                    'include': include_cb,
                    'sample_name_tf': sample_tf,
                }
                self._sample_entries.append(entry)
                
                self._samples_list.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                include_cb,
                                ft.Text(file_sample_id, size=12, width=200),
                                sample_tf,
                            ],
                            spacing=5,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        padding=ft.padding.symmetric(vertical=2),
                    )
                )
            
            self._update_import_btn_state()
            self._samples_list.update()
            
        except Exception as ex:
            logger.exception(ex)
            self._samples_list.controls = [
                ft.Text(f"Error: {ex}", color=ft.Colors.RED_400)
            ]
            self._samples_list.update()
            show_snack(self.page, f"Error loading samples: {ex}", ft.Colors.RED_400)
            self.page.update()

    def _on_sample_name_change(self, file_sample_id: str, e):
        for entry in self._sample_entries:
            if entry['file_id'] == file_sample_id:
                val = e.control.value or ""
                e.control.border_color = ft.Colors.RED if not val.strip() else None
                if e.control.page:
                    e.control.update()
        self._update_import_btn_state()

    def _update_import_btn_state(self):
        if self._import_btn is None:
            return
        has_valid = any(
            entry['include'].value and bool(entry['sample_name_tf'].value.strip())
            for entry in self._sample_entries
        )
        self._import_btn.disabled = not has_valid
        if self._import_btn.page:
            self._import_btn.update()

    def _close(self, e=None):
        if self.dialog:
            self.dialog.open = False
        self.page.update()

    async def _start_import(self, e):
        """
        Start stacked import.
        
        For each included sample entry:
        1. Find the Sample in DB by name.
        2. Get its spectra files.
        3. Create a separate identification_file record with selection_field and
           selection_field_value.
        4. Import only rows matching that sample's file_id value.
        """
        self._close()
        
        if not self.on_import_callback:
            return
        
        override_col = self._sample_field_tf.value.strip() or None
        effective_field = override_col or getattr(self._parser_class, 'sample_id_column', None)
        
        # Build list of (file_path, project_sample_name, file_sample_id, selection_field)
        entries_to_import = [
            {
                'file_path': self._file_path,
                'project_sample_name': entry['sample_name_tf'].value.strip(),
                'file_sample_id': entry['file_id'],
                'selection_field': effective_field,
            }
            for entry in self._sample_entries
            if entry['include'].value and entry['sample_name_tf'].value.strip()
        ]
        
        await self.on_import_callback(
            entries_to_import,
            self.tool_id,
        )
