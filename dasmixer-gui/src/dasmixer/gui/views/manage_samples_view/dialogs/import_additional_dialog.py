"""Import additional data dialog for samples."""

import json
import asyncio
from typing import Callable, Awaitable

import flet as ft
import pandas as pd

from dasmixer.utils import logger
from dasmixer.api.project.project import Project


class ImportAdditionalDialog:
    """
    Dialog for importing additional sample data from xlsx/csv files.
    
    Workflow:
    1. Select file via FilePicker
    2. Read file with pandas
    3. Show preview dialog with column selector and color-coded intersection table
    4. Import matching samples (merge additions)
    """

    def __init__(self, project: Project, page: ft.Page):
        self.project = project
        self.page = page
        self.df: pd.DataFrame | None = None
        self._file_path: str | None = None

    async def show(self):
        """Start the import workflow: pick file first."""
        files = await ft.FilePicker().pick_files(
            dialog_title="Import additional sample data",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["xlsx", "csv"],
            allow_multiple=False,
        )
        if not files or not files[0].path:
            return

        self._file_path = files[0].path
        
        # Read file
        try:
            if self._file_path.endswith('.csv'):
                self.df = pd.read_csv(self._file_path)
            else:
                self.df = pd.read_excel(self._file_path)
        except Exception as e:
            self._show_error(f"Failed to read file: {e}")
            return

        if self.df is None or len(self.df) == 0:
            self._show_error("File is empty")
            return

        await self._show_preview_dialog()

    async def _show_preview_dialog(self):
        """Show dialog with column selector and preview table."""
        columns = list(self.df.columns)
        
        # Column selector dropdown
        column_dropdown = ft.Dropdown(
            label="Select sample column",
            options=[ft.DropdownOption(key=c, text=c) for c in columns],
            value=columns[0] if columns else None,
            width=300,
        )

        # Preview table
        preview_container = ft.Container(
            content=ft.Text("Click Preview to see intersection", size=12, color=ft.Colors.GREY_600),
            padding=10,
        )

        # Import button
        import_btn = ft.ElevatedButton(
            content=ft.Text("Import"),
            icon=ft.Icons.UPLOAD_FILE,
            disabled=True,
            style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_600, color=ft.Colors.WHITE),
        )

        preview_btn = ft.ElevatedButton(
            content=ft.Text("Preview"),
            icon=ft.Icons.PREVIEW,
        )

        result_event = asyncio.Event()
        confirmed = False

        async def on_preview(e):
            col = column_dropdown.value
            if not col or col not in self.df.columns:
                return
            
            file_names = set(self.df[col].astype(str))
            samples = await self.project.get_samples()
            project_names = {s.name for s in samples}
            
            intersection = file_names & project_names
            only_file = file_names - project_names
            only_project = project_names - file_names
            
            # Build preview table
            table_rows = []
            
            # Green: in both
            for name in sorted(intersection):
                table_rows.append(ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(name, size=12)),
                        ft.DataCell(ft.Icon(ft.Icons.CHECK, color=ft.Colors.GREEN_600, size=16)),
                        ft.DataCell(ft.Icon(ft.Icons.CHECK, color=ft.Colors.GREEN_600, size=16)),
                    ],
                    color=ft.Colors.GREEN_50,
                ))
            
            # Yellow: only in project
            for name in sorted(only_project):
                table_rows.append(ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(name, size=12)),
                        ft.DataCell(ft.Text("-", size=12, color=ft.Colors.GREY_400)),
                        ft.DataCell(ft.Icon(ft.Icons.CHECK, color=ft.Colors.GREEN_600, size=16)),
                    ],
                    color=ft.Colors.AMBER_50,
                ))
            
            # Red: only in file
            for name in sorted(only_file):
                table_rows.append(ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(name, size=12)),
                        ft.DataCell(ft.Icon(ft.Icons.CHECK, color=ft.Colors.GREEN_600, size=16)),
                        ft.DataCell(ft.Text("-", size=12, color=ft.Colors.GREY_400)),
                    ],
                    color=ft.Colors.RED_50,
                ))

            preview_container.content = ft.Column([
                ft.Text(f"Found {len(intersection)} matching samples", size=13, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.DataTable(
                                columns=[
                                    ft.DataColumn(ft.Text("Sample name", weight=ft.FontWeight.BOLD, size=12)),
                                    ft.DataColumn(ft.Text("File ✓", weight=ft.FontWeight.BOLD, size=12)),
                                    ft.DataColumn(ft.Text("Project ✓", weight=ft.FontWeight.BOLD, size=12)),
                                ],
                                rows=table_rows,
                                column_spacing=30,
                            ),
                        ],
                        scroll=ft.ScrollMode.AUTO,
                    ),
                    border=ft.border.all(1, ft.Colors.GREY_300),
                    border_radius=5,
                    padding=10,
                    height=300,
                ),
            ], spacing=6)
            
            # Enable import if at least one green
            if intersection:
                import_btn.disabled = False
            else:
                import_btn.disabled = True
            
            if preview_container.page:
                preview_container.page.update()

        async def on_import(e):
            nonlocal confirmed
            confirmed = True
            dlg.open = False
            if dlg.page:
                dlg.page.update()
            result_event.set()

        def on_cancel(e):
            dlg.open = False
            if dlg.page:
                dlg.page.update()
            result_event.set()

        preview_btn.on_click = lambda e: e.page.run_task(on_preview, e) if e.page else None
        import_btn.on_click = lambda e: e.page.run_task(on_import, e) if e.page else None

        dlg = ft.AlertDialog(
            title=ft.Text("Import Additional Data"),
            content=ft.Column([
                column_dropdown,
                ft.Row([preview_btn], alignment=ft.MainAxisAlignment.END),
                ft.Container(height=10),
                preview_container,
            ], tight=True, width=600),
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel),
                import_btn,
            ],
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()
        await result_event.wait()

        if confirmed:
            await self._do_import(column_dropdown.value)

    async def _do_import(self, column_name: str):
        """Import additionals for matching samples."""
        if not column_name or column_name not in self.df.columns or self.df is None:
            return

        samples = await self.project.get_samples()
        project_map = {s.name: s for s in samples}
        file_names = set(self.df[column_name].astype(str))
        intersection = file_names & project_map.keys()

        count = 0
        for name in intersection:
            sample = project_map[name]
            # Get the row data as dict
            row = self.df[self.df[column_name].astype(str) == name].iloc[0]
            row_dict = row.to_dict()
            # Remove the key column itself
            row_dict.pop(column_name, None)
            # Filter out NaN values and non-serializable types
            clean_dict = {}
            for k, v in row_dict.items():
                if isinstance(v, (str, int, float, bool)) and not (isinstance(v, float) and pd.isna(v)):
                    clean_dict[k] = v
                elif isinstance(v, pd.Timestamp):
                    clean_dict[k] = v.isoformat()
            
            if not clean_dict:
                continue

            # Merge with existing additions
            existing = sample.additions or {}
            merged = {**existing, **clean_dict}
            sample.additions = merged
            await self.project.update_sample(sample)
            count += 1

        if count > 0:
            await self.project.save()
            self._show_success(f"Additional data imported for {count} sample(s)")
        else:
            self._show_warning("No samples to import")

    def _show_error(self, msg: str):
        from dasmixer.gui.utils import show_snack
        if self.page:
            show_snack(self.page, msg, ft.Colors.RED_400)
            self.page.update()

    def _show_success(self, msg: str):
        from dasmixer.gui.utils import show_snack
        if self.page:
            show_snack(self.page, msg, ft.Colors.GREEN_400)
            self.page.update()

    def _show_warning(self, msg: str):
        from dasmixer.gui.utils import show_snack
        if self.page:
            show_snack(self.page, msg, ft.Colors.ORANGE_400)
            self.page.update()
