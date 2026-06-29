import os
from datetime import datetime

import flet as ft

from dasmixer.api.export.shared_state import ExportTabState
from dasmixer.api.export.system_export import TABLE_QUERIES, export_system_data
from dasmixer.gui.components.progress_dialog import ProgressDialog
from dasmixer.gui.utils import show_snack
from dasmixer.utils import logger


class SystemDataSection(ft.Card):
    def __init__(self, project, state: ExportTabState, tab_ref):
        super().__init__()
        self.project = project
        self.state = state
        self.tab_ref = tab_ref
        self.content = ft.Container(
            content=ft.Column(
                controls=self._build_controls(),
                spacing=10,
            ),
            padding=ft.padding.all(16),
        )

    def _page(self):
        return self.tab_ref.page

    def _build_controls(self):
        title = ft.Text("System Data", size=18, weight=ft.FontWeight.BOLD)

        btn_select_all = ft.TextButton(
            content=ft.Text('Select All'),
            on_click=self._on_select_all,
        )
        btn_deselect_all = ft.TextButton(
            content=ft.Text('Deselect All'),
            on_click=self._on_deselect_all,
        )

        self._checkboxes = {}
        for flag_name in TABLE_QUERIES:
            cb = ft.Checkbox(
                label=flag_name,
                value=self.state.system_flags.get(flag_name, True),
            )
            self._checkboxes[flag_name] = cb

        checkbox_controls = []
        for flag_name in TABLE_QUERIES:
            checkbox_controls.append(ft.Row([self._checkboxes[flag_name]], tight=True))

        self._export_btn = ft.ElevatedButton(
            content=ft.Text("Export (CSV)"),
            icon=ft.Icons.DOWNLOAD,
            on_click=self._on_export,
        )

        return [
            title,
            ft.Row([btn_select_all, btn_deselect_all], spacing=12),
            ft.Column(checkbox_controls, spacing=2),
            ft.Row([self._export_btn], alignment=ft.MainAxisAlignment.END),
        ]

    def _on_select_all(self, e):
        for cb in self._checkboxes.values():
            cb.value = True
        self._page().update()

    def _on_deselect_all(self, e):
        for cb in self._checkboxes.values():
            cb.value = False
        self._page().update()

    async def _on_export(self, e):
        flags = {key: cb.value for key, cb in self._checkboxes.items()}
        if not any(flags.values()):
            show_snack(self._page(), "No data selected for export", ft.Colors.ORANGE)
            return

        folder = await ft.FilePicker().get_directory_path(
            dialog_title="Select Export Directory",
        )
        if not folder:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        progress_dlg = ProgressDialog("Exporting system data...")
        self._page().show_dialog(progress_dlg)

        async def _on_progress(value: float, status: str):
            progress_dlg.update_progress(value, status)

        try:
            created = await export_system_data(
                self.project, flags, folder, timestamp, _on_progress,
            )
            progress_dlg.open = False
            self._page().update()
            if created:
                show_snack(self._page(), f"Exported {len(created)} files to {folder}", ft.Colors.GREEN_400)
            else:
                show_snack(self._page(), "No data exported", ft.Colors.ORANGE)
        except Exception as err:
            progress_dlg.open = False
            self._page().update()
            show_snack(self._page(), f"Export failed: {err}", ft.Colors.RED_400)
            logger.exception(err)