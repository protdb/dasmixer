"""MaxQuant project import dialog — 3-screen wizard: parse → configure → progress."""

import flet as ft
from pathlib import Path

from dasmixer.api.project.project import Project
from dasmixer.api.inputs.complex.MaxQuantProject.mqpar_parser import (
    get_paths_from_mqpar, MQParPaths,
)
from dasmixer.api.inputs.complex.MaxQuantProject.importer import (
    MaxQuantImportOptions, run_maxquant_import, MaxQuantImportProgress,
)
from dasmixer.gui.utils import show_snack
from dasmixer.utils import logger


class ImportMaxQuantDialog:
    """Three-screen wizard for MaxQuant project import."""

    def __init__(
        self,
        project: Project,
        page: ft.Page,
        on_complete_callback=None,
    ):
        self.project = project
        self.page = page
        self.on_complete_callback = on_complete_callback

        # State
        self._mqpar_path: Path | None = None
        self._mqpar_paths: MQParPaths | None = None
        self._raw_file_checkboxes: dict[str, ft.Checkbox] = {}
        self._tool_status_ok: bool = True

        # Progress controls (created in _show_progress_screen)
        self._progress_text = None
        self._progress_bar = None
        self._progress_details = None

        # Converting status text (shown in configure dialog during converting)
        self._converting_status = None

        # Build dialog
        self.dialog = ft.AlertDialog(
            title=ft.Text("Import From MaxQuant"),
            modal=True,
        )

    # ─── Public API ───────────────────────────────────────────────

    async def show(self):
        """Open the dialog and show screen 1."""
        self._show_screen1()
        self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    # ─── Screen 1: Select mqpar.xml ───────────────────────────────

    def _show_screen1(self):
        mqpar_field = ft.TextField(
            label="MQPar File",
            hint_text="Path to mqpar.xml",
            read_only=True,
            expand=True,
        )
        browse_btn = ft.ElevatedButton("Browse", icon=ft.Icons.FOLDER_OPEN)
        parse_btn = ft.ElevatedButton("Parse", icon=ft.Icons.PLAY_ARROW, disabled=True)
        cancel_btn = ft.TextButton("Cancel", on_click=lambda e: self._close())

        async def on_browse():
            result = await ft.FilePicker().pick_files(
                dialog_title="Select mqpar.xml",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["xml"],
                allow_multiple=False,
            )
            if result and result[0].path:
                mqpar_field.value = result[0].path
                parse_btn.disabled = False
                self.page.update()

        async def on_parse():
            path_str = mqpar_field.value
            if not path_str or not Path(path_str).exists():
                return
            # Show spinner
            self.dialog.content = ft.Column([
                ft.ProgressRing(width=28, height=28, stroke_width=3),
                ft.Text("Parsing mqpar.xml..."),
            ], tight=True, width=400, height=80, alignment=ft.Alignment.CENTER)
            self.dialog.actions = []
            self.page.update()

            try:
                self._mqpar_path = Path(path_str)
                self._mqpar_paths = get_paths_from_mqpar(self._mqpar_path)
            except Exception as ex:
                logger.exception(ex)
                show_snack(self.page, f"Error parsing mqpar.xml: {ex}", ft.Colors.RED_400)
                self._show_screen1()
                return

            await self._show_screen2()

        browse_btn.on_click = lambda e: self.page.run_task(on_browse)
        parse_btn.on_click = lambda e: self.page.run_task(on_parse)

        self.dialog.content = ft.Column([
            ft.Row([mqpar_field, browse_btn], spacing=10),
            ft.Row([parse_btn], alignment=ft.MainAxisAlignment.END),
        ], tight=True, width=500)
        self.dialog.actions = [cancel_btn]
        self.page.update()

    # ─── Screen 2: Configure ─────────────────────────────────────

    async def _show_screen2(self):
        mp = self._mqpar_paths

        # ── Create all controls ──
        raw_default = str(mp.raw_parents[0].path) if mp.raw_parents else ""
        raw_field = ft.TextField(label="RAW files path", value=raw_default, expand=True)
        raw_status = ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color=ft.Colors.GREEN_600)
        raw_browse = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="Browse for RAW files folder",
        )

        txt_default = str(mp.custom_txt_path.path) if mp.custom_txt_path.path else ""
        txt_field = ft.TextField(label="Custom TXT folder", value=txt_default, expand=True)
        txt_status = ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color=ft.Colors.GREEN_600)
        txt_browse = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="Browse for TXT folder",
        )

        fasta_default = str(mp.fasta_path.path) if mp.fasta_path.path else ""
        fasta_field = ft.TextField(label="FASTA file", value=fasta_default, expand=True)
        fasta_status = ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color=ft.Colors.GREEN_600)
        fasta_browse = ft.IconButton(
            icon=ft.Icons.FOLDER_OPEN,
            tooltip="Browse for FASTA file",
        )

        cb_import_fasta = ft.Checkbox(label="Import proteins from FASTA file", value=True)
        cb_fasta_uniprot = ft.Checkbox(label="Sequences are in UniProt format", value=True)

        tool_field = ft.TextField(label="Tool name", value="MaxQuant", expand=True)
        tool_status = ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color=ft.Colors.GREEN_600)

        subset_field = ft.TextField(label="Subset name", value="MaxQuant Import", expand=True)

        cb_delete_temp = ft.Checkbox(
            label="Delete temporary MGF and identification files after import",
            value=True,
        )
        cb_skip_contaminants = ft.Checkbox(
            label="Skip contaminant identifications",
            value=True,
        )

        on_duplicates_group = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="skip", label="Skip (keep existing)"),
                ft.Radio(value="reload", label="Reload (replace existing)"),
                ft.Radio(value="add_as_new", label="Add as new (keep both)"),
            ]),
            value="skip",
        )

        # RAW file checkboxes
        self._raw_file_checkboxes = {}
        raw_checkboxes = []
        for rf in mp.raw_files:
            cb = ft.Checkbox(label=rf.name, value=True)
            self._raw_file_checkboxes[rf.name] = cb
            raw_checkboxes.append(cb)
        raw_list = ft.ListView(controls=raw_checkboxes, height=150, spacing=5)

        select_btn = ft.ElevatedButton("Select All")
        deselect_btn = ft.ElevatedButton("Deselect All")
        import_btn = ft.ElevatedButton("Import", icon=ft.Icons.UPLOAD_FILE, disabled=True)
        cancel_btn = ft.TextButton("Cancel", on_click=lambda e: self._close())

        # Converting status (shown inline during converting stage)
        self._converting_status = ft.Text("", size=11, color=ft.Colors.GREY_600)

        # ── Define all helpers (closures over controls) ──

        def _set_path_status(field, status, is_dir_check=True):
            val = field.value
            if not val:
                status.icon = ft.Icons.ERROR_OUTLINE
                status.color = ft.Colors.RED_600
            else:
                p = Path(val)
                ok = p.is_dir() if is_dir_check else p.is_file()
                if ok:
                    status.icon = ft.Icons.CHECK_CIRCLE_OUTLINE
                    status.color = ft.Colors.GREEN_600
                else:
                    status.icon = ft.Icons.ERROR_OUTLINE
                    status.color = ft.Colors.RED_600

        def _update_import_btn_state():
            raw_ok = bool(raw_field.value and Path(raw_field.value).is_dir())
            txt_ok = bool(txt_field.value and Path(txt_field.value).is_dir())
            fasta_ok = (
                not cb_import_fasta.value
                or bool(fasta_field.value and Path(fasta_field.value).is_file())
            )
            any_raw = any(cb.value for cb in self._raw_file_checkboxes.values())
            import_btn.disabled = not (
                raw_ok and txt_ok and fasta_ok and self._tool_status_ok and any_raw
            )

        async def check_tool_status():
            tools = await self.project.get_tools()
            existing = next((t for t in tools if t.name == tool_field.value), None)
            if existing is None or existing.parser == "MaxQuant":
                tool_status.icon = ft.Icons.CHECK_CIRCLE_OUTLINE
                tool_status.color = ft.Colors.GREEN_600
                self._tool_status_ok = True
            else:
                tool_status.icon = ft.Icons.WARNING_AMBER
                tool_status.color = ft.Colors.AMBER_600
                self._tool_status_ok = False
            _update_import_btn_state()

        def select_all():
            for cb in self._raw_file_checkboxes.values():
                cb.value = True
            _update_import_btn_state()
            self.page.update()

        def deselect_all():
            for cb in self._raw_file_checkboxes.values():
                cb.value = False
            _update_import_btn_state()
            self.page.update()

        def on_path_change(field, status, is_dir_check):
            _set_path_status(field, status, is_dir_check)
            _update_import_btn_state()
            self.page.update()

        def on_raw_checkbox_change():
            _update_import_btn_state()
            self.page.update()

        def on_fasta_import_toggle():
            cb_fasta_uniprot.disabled = not cb_import_fasta.value
            _set_path_status(fasta_field, fasta_status, is_dir_check=False)
            _update_import_btn_state()
            self.page.update()

        async def on_tool_blur():
            await check_tool_status()
            self.page.update()

        # ── Browse handlers (FilePicker) ──

        async def on_browse_raw():
            dir_path = await ft.FilePicker().get_directory_path(
                dialog_title="Select RAW files folder",
            )
            if dir_path:
                raw_field.value = dir_path
                _set_path_status(raw_field, raw_status, is_dir_check=True)
                _update_import_btn_state()
                self.page.update()

        async def on_browse_txt():
            dir_path = await ft.FilePicker().get_directory_path(
                dialog_title="Select TXT results folder",
            )
            if dir_path:
                txt_field.value = dir_path
                _set_path_status(txt_field, txt_status, is_dir_check=True)
                _update_import_btn_state()
                self.page.update()

        async def on_browse_fasta():
            result = await ft.FilePicker().pick_files(
                dialog_title="Select FASTA file",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["fasta", "fa", "fas", "txt"],
                allow_multiple=False,
            )
            if result and result[0].path:
                fasta_field.value = result[0].path
                _set_path_status(fasta_field, fasta_status, is_dir_check=False)
                _update_import_btn_state()
                self.page.update()

        # ── Wire up event handlers ──
        raw_field.on_change = lambda e: on_path_change(raw_field, raw_status, True)
        raw_field.on_blur = lambda e: on_path_change(raw_field, raw_status, True)
        txt_field.on_change = lambda e: on_path_change(txt_field, txt_status, True)
        txt_field.on_blur = lambda e: on_path_change(txt_field, txt_status, True)
        fasta_field.on_change = lambda e: on_path_change(fasta_field, fasta_status, False)
        fasta_field.on_blur = lambda e: on_path_change(fasta_field, fasta_status, False)

        raw_browse.on_click = lambda e: self.page.run_task(on_browse_raw)
        txt_browse.on_click = lambda e: self.page.run_task(on_browse_txt)
        fasta_browse.on_click = lambda e: self.page.run_task(on_browse_fasta)

        tool_field.on_blur = lambda e: self.page.run_task(on_tool_blur)
        cb_import_fasta.on_change = lambda e: on_fasta_import_toggle()
        select_btn.on_click = lambda e: select_all()
        deselect_btn.on_click = lambda e: deselect_all()

        for cb in self._raw_file_checkboxes.values():
            cb.on_change = lambda e: on_raw_checkbox_change()

        import_btn.on_click = lambda e: self.page.run_task(
            self._start_import,
            raw_field, txt_field, fasta_field,
            tool_field, subset_field,
            cb_import_fasta, cb_fasta_uniprot,
            cb_delete_temp, cb_skip_contaminants,
            on_duplicates_group,
        )

        # ── Initial async setup ──
        await check_tool_status()

        # ── Initial status computation (just set properties, no .update()) ──
        _set_path_status(raw_field, raw_status, True)
        _set_path_status(txt_field, txt_status, True)
        _set_path_status(fasta_field, fasta_status, False)
        _update_import_btn_state()

        # ── Build layout and push to UI once ──
        self.dialog.content = ft.Column([
            ft.Text("Configure Import", size=16, weight=ft.FontWeight.BOLD),
            ft.Divider(),

            ft.Text("Paths", weight=ft.FontWeight.BOLD, size=13),
            ft.Row([raw_field, raw_browse, raw_status], spacing=5),
            ft.Row([txt_field, txt_browse, txt_status], spacing=5),
            ft.Row([fasta_field, fasta_browse, fasta_status], spacing=5),
            cb_import_fasta,
            ft.Container(content=cb_fasta_uniprot, padding=ft.padding.only(left=20)),
            ft.Divider(),

            ft.Text("Tool & Subset", weight=ft.FontWeight.BOLD, size=13),
            ft.Row([tool_field, tool_status], spacing=5),
            subset_field,
            ft.Divider(),

            ft.Text("Options", weight=ft.FontWeight.BOLD, size=13),
            cb_delete_temp,
            cb_skip_contaminants,
            ft.Text("On duplicates:", size=12),
            on_duplicates_group,
            ft.Divider(),

            ft.Text("RAW files:", weight=ft.FontWeight.BOLD, size=13),
            ft.Row([select_btn, deselect_btn], spacing=5),
            ft.Container(content=raw_list, height=150),
            ft.Divider(),
            self._converting_status,
        ], tight=True, width=580, height=600, scroll=ft.ScrollMode.AUTO)

        self.dialog.actions = [cancel_btn, import_btn]
        self.page.update()

    # ─── Progress screen ─────────────────────────────────────────

    def _show_progress_screen(self):
        self._progress_text = ft.Text("Preparing...")
        self._progress_bar = ft.ProgressBar(value=0)
        self._progress_details = ft.Text("", size=11, color=ft.Colors.GREY_600)

        self.dialog.content = ft.Column([
            self._progress_text,
            self._progress_bar,
            ft.Container(height=5),
            self._progress_details,
        ], tight=True, width=450)
        self.dialog.actions = []  # No Cancel/Import buttons during progress
        self.page.update()

    async def _on_progress(self, p: MaxQuantImportProgress):
        # Progress screen is already shown by _start_import before the run starts.
        # Just update the content based on stage.
        if self._progress_text is None:
            return

        self._progress_text.value = p.message
        if p.total > 0:
            self._progress_bar.value = p.current / p.total
        self._progress_details.value = f"Stage: {p.stage}"
        self.page.update()

    async def _start_import(
        self,
        raw_field, txt_field, fasta_field,
        tool_field, subset_field,
        cb_import_fasta, cb_fasta_uniprot,
        cb_delete_temp, cb_skip_contaminants,
        on_duplicates_group,
    ):
        # Switch to progress screen immediately, before any work starts
        self._show_progress_screen()

        options = MaxQuantImportOptions(
            mqpar_path=self._mqpar_path,
            txt_path=Path(txt_field.value),
            raw_parent=Path(raw_field.value),
            fasta_path=Path(fasta_field.value) if fasta_field.value else None,
            import_fasta=cb_import_fasta.value,
            fasta_is_uniprot=cb_fasta_uniprot.value,
            tool_name=tool_field.value,
            subset_name=subset_field.value,
            delete_temp_files=cb_delete_temp.value,
            keep_contaminants=not cb_skip_contaminants.value,
            selected_raw_names=[name for name, cb in self._raw_file_checkboxes.items() if cb.value],
            on_duplicates=on_duplicates_group.value,
        )

        try:
            summary = await run_maxquant_import(
                self.project, options,
                progress_callback=self._on_progress,
            )
            self._close()
            msg = (
                f"MaxQuant import complete: {summary['samples_processed']} sample(s), "
                f"{summary['spectra_imported']} spectra, "
                f"{summary['identifications_imported']} identifications"
            )
            if summary['proteins_imported']:
                msg += f", {summary['proteins_imported']} proteins"
            if not options.delete_temp_files and summary.get('temp_dir'):
                msg += f"\nTemporary files kept at: {summary['temp_dir']}"
            show_snack(self.page, msg, ft.Colors.GREEN_400)
            if self.on_complete_callback:
                await self.on_complete_callback()
        except Exception as ex:
            logger.exception(ex)
            self._close()
            show_snack(self.page, f"MaxQuant import error: {ex}", ft.Colors.RED_400)
        self.page.update()

    # ─── Helpers ─────────────────────────────────────────────────

    def _close(self):
        self.dialog.open = False
        self.page.update()
