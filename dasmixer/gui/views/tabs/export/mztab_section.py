"""MzTab export section UI."""

from datetime import datetime

import flet as ft

from dasmixer.api.export.mztab_export import export_mztab
from dasmixer.api.export.shared_state import ExportTabState
from dasmixer.gui.components.progress_dialog import ProgressDialog
from dasmixer.gui.components.sample_select_dialog import SampleSelectDialog
from dasmixer.gui.utils import show_snack
from dasmixer.utils import logger

_LFQ_METHODS = ["emPAI", "iBAQ", "NSAF", "Top3"]


class MzTabExportSection(ft.Card):
    def __init__(self, project, state: ExportTabState, tab_ref):
        super().__init__()
        self.project = project
        self.state = state
        self.tab_ref = tab_ref
        self._sample_dialog = None
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
        title = ft.Text("Export MzTab", size=18, weight=ft.FontWeight.BOLD)

        self._title_field = ft.TextField(
            label="Title",
            expand=True,
            value=self.state.mztab_title,
            on_change=self._save_meta,
        )
        self._description_field = ft.TextField(
            label="Description",
            expand=True,
            value=self.state.mztab_description,
            on_change=self._save_meta,
        )

        self._selected_label = ft.Text("None", size=14)
        btn_select_samples = ft.ElevatedButton(
            content=ft.Text("Select Samples..."),
            on_click=self._on_select_samples,
        )
        samples_row = ft.Row(
            [
                ft.Text("Samples:", size=14, weight=ft.FontWeight.W_600),
                self._selected_label,
                btn_select_samples,
            ],
            spacing=8,
            alignment=ft.MainAxisAlignment.START,
        )

        self._lfq_dropdown = ft.Dropdown(
            label="LFQ Method",
            width=200,
            options=[ft.DropdownOption(m) for m in _LFQ_METHODS],
            value=self.state.mztab_lfq_method,
        )

        self._export_btn = ft.ElevatedButton(
            content=ft.Text("Export"),
            icon=ft.Icons.DOWNLOAD,
            on_click=self._on_export,
        )

        return [
            title,
            ft.Row([self._title_field], spacing=8),
            ft.Row([self._description_field], spacing=8),
            samples_row,
            ft.Row([self._lfq_dropdown], spacing=8),
            ft.Row([self._export_btn], alignment=ft.MainAxisAlignment.END),
        ]

    def did_mount(self):
        self._sample_dialog = SampleSelectDialog(self._page(), self.project)
        self.page.run_task(self._load_saved_meta)

    async def _load_saved_meta(self):
        self._title_field.value = await self.project.get_setting(
            "mztab_export_title", default="",
        )
        self._description_field.value = await self.project.get_setting(
            "mztab_export_description", default="",
        )
        self.state.mztab_title = self._title_field.value
        self.state.mztab_description = self._description_field.value
        self._page().update()

    async def _save_meta(self, e=None):
        self.state.mztab_title = self._title_field.value
        self.state.mztab_description = self._description_field.value
        await self.project.set_setting("mztab_export_title", self._title_field.value)
        await self.project.set_setting("mztab_export_description", self._description_field.value)

    async def _on_select_samples(self, e):
        if self._sample_dialog is None:
            return
        selected = await self._sample_dialog.show(self.state.mztab_sample_ids)
        if selected is not None:
            self.state.mztab_sample_ids = selected
            samples = await self.project.get_samples()
            self._selected_label.value = self._sample_dialog.get_selected_text(selected, samples)
            self._page().update()

    async def _on_export(self, e):
        if not self.state.mztab_sample_ids:
            show_snack(self._page(), "No samples selected", ft.Colors.ORANGE)
            return

        title = self._title_field.value or None
        description = self._description_field.value or None
        lfq_method: str = self._lfq_dropdown.value or self.state.mztab_lfq_method or _LFQ_METHODS[0]

        self.state.mztab_title = self._title_field.value
        self.state.mztab_description = self._description_field.value
        self.state.mztab_lfq_method = lfq_method

        file_path = await ft.FilePicker().save_file(
            dialog_title="Save MzTab File",
            file_name=f"dasmixer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mzTab",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["mzTab", "txt"],
        )
        if not file_path:
            return

        output_path = file_path

        progress = ProgressDialog("Exporting MzTab...")
        self._page().show_dialog(progress)

        async def _on_progress(value: float, status: str):
            progress.update_progress(value, status)

        try:
            created = await export_mztab(
                self.project,
                sample_ids=self.state.mztab_sample_ids,
                lfq_method=lfq_method,
                title=title,
                description=description,
                output_path=output_path,
                progress_callback=_on_progress,
            )
            progress.open = False
            self._page().update()
            show_snack(self._page(), f"MzTab exported to {created}", ft.Colors.GREEN_400)
        except Exception as err:
            progress.open = False
            self._page().update()
            show_snack(self._page(), f"Export failed: {err}", ft.Colors.RED_400)
            logger.exception(err)
