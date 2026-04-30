"""MGF export section UI."""

from datetime import datetime

import flet as ft

from dasmixer.api.export.mgf_export import export_mgf
from dasmixer.api.export.shared_state import ExportTabState
from dasmixer.gui.components.progress_dialog import ProgressDialog
from dasmixer.gui.components.sample_select_dialog import SampleSelectDialog
from dasmixer.gui.utils import show_snack
from dasmixer.utils import logger


class MgfExportSection(ft.Card):
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
        title = ft.Text("Export MGF", size=18, weight=ft.FontWeight.BOLD)

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

        self._by_group = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="all", label="All"),
                    ft.Radio(value="all_preferred", label="All preferred"),
                    ft.Radio(value="preferred_by_tool", label="All preferred by tool"),
                ],
                spacing=2,
            ),
            value=self.state.mgf_by,
            on_change=self._on_change_by,
        )

        self._tool_dropdown = ft.Dropdown(
            width=250,
            visible=False,
            hint_text="Select tool",
        )

        self._cb_write_offset = ft.Checkbox(
            label="Write offset from identification",
            value=self.state.mgf_write_offset,
        )
        
        self._cb_write_spectra = ft.Checkbox(
            label="Write spectra from identification",
            value=self.state.mgf_write_spectra,
        )

        self._cb_write_seq = ft.Checkbox(
            label="Write SEQ from identification",
            value=self.state.mgf_write_seq,
            on_change=self._update_seq_type_visibility,
        )

        self._seq_type_dropdown = ft.Dropdown(
            width=150,
            visible=self.state.mgf_write_seq,
            options=[
                ft.DropdownOption("canonical"),
                ft.DropdownOption("modified"),
            ],
            value=self.state.mgf_seq_type,
        )

        self._compression_group = ft.RadioGroup(
            content=ft.Column(
                controls=[
                    ft.Radio(value="gzip", label="GZIP"),
                    ft.Radio(value="zip_all", label="ZIP (All in one)"),
                    ft.Radio(value="zip_each", label="ZIP (One file per archive)"),
                    ft.Radio(value="none", label="None"),
                ],
                spacing=2,
            ),
            value=self.state.mgf_compression,
        )

        self._export_btn = ft.ElevatedButton(
            content=ft.Text("Export"),
            icon=ft.Icons.DOWNLOAD,
            on_click=self._on_export,
        )

        return [
            title,
            samples_row,
            ft.Text("By identification:", weight=ft.FontWeight.W_600),
            self._by_group,
            self._tool_dropdown,
            self._cb_write_offset,
            self._cb_write_spectra,
            ft.Row(
                [
                    self._cb_write_seq,
                    self._seq_type_dropdown,
                ],
                spacing=8,
            ),
            ft.Text("Compression:", weight=ft.FontWeight.W_600),
            self._compression_group,
            ft.Row([self._export_btn], alignment=ft.MainAxisAlignment.END),
        ]

    def did_mount(self):
        self._sample_dialog = SampleSelectDialog(self._page(), self.project)
        self._update_tool_dropdown_visibility()
        self.page.run_task(self._load_tools)

    async def _load_tools(self):
        tools = await self.project.get_tools()
        self._tool_dropdown.options = [
            ft.DropdownOption(text=t.name, key=str(t.id)) for t in tools
        ]

    async def _on_select_samples(self, e):
        selected = await self._sample_dialog.show(self.state.mgf_sample_ids)
        if selected is not None:
            self.state.mgf_sample_ids = selected
            samples = await self.project.get_samples()
            self._selected_label.value = self._sample_dialog.get_selected_text(selected, samples)
            self._page().update()

    def _update_seq_type_visibility(self, e):
        self._seq_type_dropdown.visible = self._cb_write_seq.value
        self._page().update()

    def _update_tool_dropdown_visibility(self, e=None):
        self._tool_dropdown.visible = self._by_group.value == "preferred_by_tool"
        self._page().update()

    async def _on_change_by(self, e):
        self._update_tool_dropdown_visibility()

    async def _on_export(self, e):
        if not self.state.mgf_sample_ids:
            show_snack(self._page(), "No samples selected", ft.Colors.ORANGE)
            return

        self.state.mgf_by = self._by_group.value
        self.state.mgf_tool_id = int(self._tool_dropdown.value) if self._tool_dropdown.value else None
        self.state.mgf_write_offset = self._cb_write_offset.value
        self.state.mgf_write_spectra = self._cb_write_spectra.value
        self.state.mgf_write_seq = self._cb_write_seq.value
        self.state.mgf_seq_type = self._seq_type_dropdown.value if self._seq_type_dropdown.value else "canonical"
        self.state.mgf_compression = self._compression_group.value

        folder = await ft.FilePicker().get_directory_path(
            dialog_title="Select Export Directory",
        )
        if not folder:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        progress_dlg = ProgressDialog("Exporting MGF...")
        self._page().show_dialog(progress_dlg)

        async def _on_progress(value: float, status: str):
            progress_dlg.update_progress(value, status)

        try:
            created = await export_mgf(
                self.project,
                sample_ids=self.state.mgf_sample_ids,
                by=self.state.mgf_by,
                tool_id=self.state.mgf_tool_id,
                write_offset=self.state.mgf_write_offset,
                write_spectra_charge=self.state.mgf_write_spectra,
                write_seq=self.state.mgf_write_seq,
                seq_type=self.state.mgf_seq_type,
                compression=self.state.mgf_compression,
                output_dir=folder,
                timestamp=timestamp,
                progress_callback=_on_progress,
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
