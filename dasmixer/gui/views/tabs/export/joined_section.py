"""Joined Data export section UI."""

from datetime import datetime

import flet as ft

from dasmixer.api.export.joined_export import export_joined_data
from dasmixer.api.export.shared_state import ExportTabState
from dasmixer.gui.components.progress_dialog import ProgressDialog
from dasmixer.gui.utils import show_snack
from dasmixer.utils import logger

_SECTIONS = {
    "sample_details": "Sample details",
    "identifications": "Identifications",
    "protein_identifications": "Protein identifications",
    "protein_statistics": "Protein Statistics",
}


class JoinedDataSection(ft.Card):
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
        title = ft.Text("Joined Data", size=18, weight=ft.FontWeight.BOLD)

        btn_select_all = ft.TextButton(
            content=ft.Text("Select All"),
            on_click=self._on_select_all,
        )
        btn_deselect_all = ft.TextButton(
            content=ft.Text("Deselect All"),
            on_click=self._on_deselect_all,
        )

        self._checkboxes = {}
        for key, label in _SECTIONS.items():
            cb = ft.Checkbox(
                label=label,
                value=self.state.joined_flags.get(key, True),
            )
            self._checkboxes[key] = cb

        checkbox_controls = []
        for key in _SECTIONS:
            checkbox_controls.append(ft.Row([self._checkboxes[key]], tight=True))

        self._format_group = ft.RadioGroup(
            content=ft.Row(
                [
                    ft.Radio(value="csv", label="CSV"),
                    ft.Radio(value="xlsx", label="XLSX"),
                ],
                spacing=16,
            ),
            value=self.state.joined_format,
        )

        self._one_per_sample = ft.Checkbox(
            label="One file per sample",
            value=self.state.joined_one_per_sample,
        )

        self._export_btn = ft.ElevatedButton(
            content=ft.Text("Export"),
            icon=ft.Icons.DOWNLOAD,
            on_click=self._on_export,
        )

        return [
            title,
            ft.Row([btn_select_all, btn_deselect_all], spacing=12),
            ft.Column(checkbox_controls, spacing=2),
            ft.Divider(),
            ft.Text("Format:", weight=ft.FontWeight.W_600),
            self._format_group,
            self._one_per_sample,
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

        fmt: str = self._format_group.value or self.state.joined_format
        one_per_sample: bool = bool(self._one_per_sample.value)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.state.joined_format = fmt
        self.state.joined_one_per_sample = one_per_sample

        total_sections = sum(flags.values())
        if one_per_sample and (flags.get("identifications") or flags.get("protein_identifications")):
            samples = await self.project.get_samples()
            if flags.get("identifications"):
                total_sections += len(samples) - 1
            if flags.get("protein_identifications"):
                total_sections += len(samples) - 1

        progress_dlg = ProgressDialog("Exporting joined data...")
        self._page().show_dialog(progress_dlg)

        async def _on_progress(value: float, status: str):
            progress_dlg.update_progress(value, status)

        try:
            created = await export_joined_data(
                self.project, flags, fmt, one_per_sample, folder, timestamp, _on_progress,
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