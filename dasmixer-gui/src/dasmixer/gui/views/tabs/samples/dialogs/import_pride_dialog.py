"""PRIDE dataset import dialog — 3-screen wizard: PXD id → configure → progress."""

import asyncio

import flet as ft
from dasmixer.api.inputs.registry import registry
from dasmixer.api.project.project import Project
from dasmixer.gui.utils import show_snack
from dasmixer.utils import logger
from dasmixer.utils.exceptions import DasmixerNetworkException

# ---------------------------------------------------------------------------
# Lazy PRIDE module loading (pridepy may not be installed)
# ---------------------------------------------------------------------------

_pride_module = None
_pride_import_error: Exception | None = None


def _load_pride_module():
    """Import the PRIDE module lazily and cache the result.

    Returns a tuple ``(module_dict, error)``. Exactly one of them is None
    on the first successful/failed call; subsequent calls reuse the cache.
    """
    global _pride_module, _pride_import_error
    if _pride_module is None and _pride_import_error is None:
        try:
            from dasmixer.api.inputs.complex.pride import (
                PrideDataset,
                PrideDatasetNotFoundException,
                PrideImportOptions,
                PrideImportProgress,
                run_pride_import,
            )

            _pride_module = {
                "PrideDataset": PrideDataset,
                "PrideDatasetNotFoundException": PrideDatasetNotFoundException,
                "PrideImportOptions": PrideImportOptions,
                "PrideImportProgress": PrideImportProgress,
                "run_pride_import": run_pride_import,
            }
        except Exception as e:  # noqa: BLE001 — pridepy may be missing entirely
            _pride_import_error = e
    return _pride_module, _pride_import_error


class ImportPrideDialog:
    """Three-screen wizard for PRIDE dataset import."""

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
        self._dataset = None
        self._spectra_checkboxes: dict[str, ft.Checkbox] = {}
        self._ident_mapping_dropdowns: dict[str, ft.Dropdown] = {}
        self._ident_selection_container = None
        self._single_ident_dropdown: ft.Dropdown | None = None

        # Progress controls (created in _show_progress_screen)
        self._progress_text = None
        self._progress_bar = None
        self._progress_details = None

        # Build dialog
        self.dialog = ft.AlertDialog(
            title=ft.Text("Import PRIDE Dataset"),
            modal=True,
        )

    # ─── Public API ───────────────────────────────────────────────

    async def show(self):
        """Open the dialog and show screen 1 (or an error if pridepy missing)."""
        module, err = _load_pride_module()
        if err is not None:
            self.dialog.content = ft.Text(
                "PRIDE import is unavailable: pridepy not installed. "
                "Install with `pip install dasmixer-core[pride]`."
            )
            self.dialog.actions = [
                ft.TextButton("Cancel", on_click=lambda e: self._close()),
            ]
        else:
            self._show_screen1()
        self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    # ─── Screen 1: PXD identifier ─────────────────────────────────

    def _show_screen1(self):
        pxd_field = ft.TextField(label="PXD Identifier", hint_text="e.g. PXD000001", expand=True)
        check_btn = ft.ElevatedButton("Check", icon=ft.Icons.SEARCH)
        cancel_btn = ft.TextButton("Cancel", on_click=lambda e: self._close())
        self._error_text = ft.Text("", color=ft.Colors.RED_400, size=12)

        check_btn.on_click = lambda e: self.page.run_task(self._on_try, pxd_field)

        self.dialog.content = ft.Column([
            ft.Row([pxd_field, check_btn], spacing=10),
            self._error_text,
        ], tight=True, width=500, height=120)
        self.dialog.actions = [cancel_btn]
        self.page.update()

    async def _on_try(self, pxd_field, return_to_screen2: bool = False):
        identifier = (pxd_field.value or "").strip()
        if not identifier:
            self._error_text.value = "Please enter a PXD identifier."
            self.page.update()
            return

        # Show spinner
        self.dialog.content = ft.Column([
            ft.ProgressRing(width=28, height=28, stroke_width=3),
            ft.Text("Fetching dataset metadata..."),
        ], tight=True, width=400, height=80, alignment=ft.Alignment.CENTER)
        self.dialog.actions = []
        self.page.update()

        module, err = _load_pride_module()
        if err is not None:
            self._show_screen1()
            self._error_text.value = (
                "PRIDE import is unavailable: pridepy not installed. "
                "Install with `pip install dasmixer-core[pride]`."
            )
            self.page.update()
            return

        try:
            dataset = await asyncio.to_thread(module["PrideDataset"], identifier)
        except DasmixerNetworkException:
            self._show_screen1()
            self._error_text.value = "No network connection. Check your internet and try again."
            self.page.update()
            return
        except module["PrideDatasetNotFoundException"]:
            self._show_screen1()
            self._error_text.value = f"Dataset `{identifier}` not found in PRIDE."
            self.page.update()
            return
        except Exception as ex:
            logger.exception("Failed to fetch PRIDE dataset %s", identifier)
            self._show_screen1()
            self._error_text.value = f"Error fetching dataset: {ex}"
            self.page.update()
            return

        self._dataset = dataset

        if return_to_screen2:
            await self._show_screen2(
                no_files_error=(
                    len(dataset.spectra_files) == 0 or len(dataset.ident_files) == 0
                )
            )
            return

        if len(dataset.spectra_files) == 0 or len(dataset.ident_files) == 0:
            await self._show_screen2(no_files_error=True)
        else:
            await self._show_screen2(no_files_error=False)

    # ─── Screen 2: Configure ──────────────────────────────────────

    async def _show_screen2(self, no_files_error: bool = False):
        dataset = self._dataset
        identifier = dataset.dataset_id

        cancel_btn = ft.TextButton("Cancel", on_click=lambda e: self._close())

        # ── Common controls ──
        title_text = ft.Text(
            f"Dataset: {dataset.title or identifier}",
            weight=ft.FontWeight.BOLD,
            size=28,
        )
        description_field = ft.TextField(
            label="Description",
            value=dataset.description or "",
            read_only=True,
            multiline=True,
            max_lines=4,
            height=80,
            expand=True,
        )

        switch_field = ft.TextField(label="PXD Identifier", value=identifier)
        check_btn = ft.ElevatedButton("Check")
        check_btn.on_click = lambda e: self.page.run_task(self._on_switch, switch_field)

        if no_files_error:
            self.dialog.content = ft.Column([
                ft.Text("Configure Import", size=16, weight=ft.FontWeight.BOLD),
                ft.Divider(),
                ft.Row([switch_field, check_btn], spacing=10),
                title_text,
                description_field,
                ft.Text(
                    "This PRIDE dataset has no files of supported formats. "
                    "Supported: spectra — .mgf; identifications — .mztab.",
                    color=ft.Colors.AMBER_700,
                ),
            ], tight=True, width=580, height=620, scroll=ft.ScrollMode.AUTO)
            self.dialog.actions = [cancel_btn]
            self.page.update()
            return

        # ── Import-configuration controls ──
        subsets = await self.project.get_subsets()
        subset_dropdown = ft.Dropdown(
            label="Subset",
            options=[ft.DropdownOption(key=str(s.id), text=s.name) for s in subsets],
            value=(str(subsets[0].id) if subsets else None),
            expand=2,
        )

        spectra_parser_dropdown = ft.Dropdown(
            label="Spectra parser",
            options=[
                ft.DropdownOption(key=name)
                for name in registry.get_spectra_parsers().keys()
            ],
            value="MGF",
            expand=1,
        )

        # Spectra files list
        self._spectra_checkboxes = {}
        spectra_checkboxes = []
        for f in dataset.spectra_files:
            cb = ft.Checkbox(label=f.name, value=True)
            self._spectra_checkboxes[f.name] = cb
            spectra_checkboxes.append(cb)
        spectra_list = ft.ListView(controls=spectra_checkboxes, height=150, spacing=5)

        select_all_btn = ft.ElevatedButton("Select All")
        deselect_all_btn = ft.ElevatedButton("Deselect All")

        # Ident mode
        ident_mode_group = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="single", label="Single file"),
                ft.Radio(value="per_sample", label="Per sample"),
            ]),
            value=("single" if len(dataset.ident_files) <= 1 else "per_sample"),
        )

        # Ident parser
        ident_parser_dropdown = ft.Dropdown(label="Identifications parser", value="mzTab")

        def rebuild_ident_parser_options():
            mode = ident_mode_group.value
            options = [ft.DropdownOption(key="mzTab", text="MzTab")]
            if mode == "per_sample":
                options.append(ft.DropdownOption(key="CasaNovo", text="CasaNovo"))
            ident_parser_dropdown.options = options
            if ident_parser_dropdown.value not in ("mzTab", "CasaNovo") or (
                ident_parser_dropdown.value == "CasaNovo" and mode != "per_sample"
            ):
                ident_parser_dropdown.value = "mzTab"

        rebuild_ident_parser_options()

        tool_field = ft.TextField(label="Tool name", value="PRIDE", expand=1)

        # Ident file selection (mode-dependent)
        single_ident_dropdown = ft.Dropdown(
            label="Identification file",
            options=[ft.DropdownOption(key=f.name) for f in dataset.ident_files],
            value=(
                dataset.ident_files[0].name
                if len(dataset.ident_files) == 1
                else None
            ),
        )

        def _match_ident_by_stem(spectra_name):
            """Find ident file whose PrideFile.stem matches the spectra file stem."""
            spectra_file = next(
                (f for f in dataset.spectra_files if f.name == spectra_name), None
            )
            if spectra_file is None:
                return None
            spectra_stem = spectra_file.stem.lower()
            for f in dataset.ident_files:
                if f.stem.lower() == spectra_stem:
                    return f.name
            return None

        def _build_per_sample_mapping_area():
            rows = []
            for spectra_name, cb in self._spectra_checkboxes.items():
                matched = _match_ident_by_stem(spectra_name)
                ident_dropdown = ft.Dropdown(
                    options=[ft.DropdownOption(key=f.name) for f in dataset.ident_files],
                    expand=3,
                    value=matched,
                )
                self._ident_mapping_dropdowns[spectra_name] = ident_dropdown
                rows.append(ft.Row([
                    ft.Text(spectra_name, size=12, expand=2),
                    ident_dropdown,
                ], spacing=10))
            return ft.Column(rows, spacing=8, scroll=ft.ScrollMode.AUTO, height=180)

        def rebuild_ident_selection_area():
            self._ident_mapping_dropdowns = {}
            if ident_mode_group.value == "single":
                self._single_ident_dropdown = single_ident_dropdown
                self._ident_selection_container.content = ft.Column([
                    ft.Text("Identification file:", size=12),
                    single_ident_dropdown,
                ], spacing=5)
            else:
                self._ident_selection_container.content = ft.Column([
                    ft.Text("Map identifications to samples:", size=12),
                    _build_per_sample_mapping_area(),
                ], spacing=5)

        self._ident_selection_container = ft.Container()
        rebuild_ident_selection_area()

        # Checkboxes
        cb_import_fasta = ft.Checkbox(
            label="Import protein data (download FASTA from PRIDE)",
            value=True,
        )
        cb_collect_proteins = ft.Checkbox(
            label="Import protein mapping (collect proteins from identifications)",
            value=True,
        )
        cb_delete_temp = ft.Checkbox(
            label="Delete downloaded files after import",
            value=False,
        )

        import_btn = ft.ElevatedButton("Import", icon=ft.Icons.UPLOAD_FILE, disabled=True)

        # ── Helpers ──

        def _update_collect_proteins_state():
            cb_collect_proteins.disabled = ident_parser_dropdown.value == "CasaNovo"
            if cb_collect_proteins.disabled:
                cb_collect_proteins.value = False

        def _update_import_btn_state():
            any_spectra = any(cb.value for cb in self._spectra_checkboxes.values())
            import_btn.disabled = not (
                subset_dropdown.value is not None
                and any_spectra
                and bool((tool_field.value or "").strip())
            )

        def on_subset_change(e=None):
            _update_import_btn_state()
            self.page.update()

        def on_spectra_parser_change(e=None):
            self.page.update()

        def on_tool_change(e=None):
            _update_import_btn_state()
            self.page.update()

        def on_spectra_checkbox_change(e=None):
            _update_import_btn_state()
            self.page.update()

        def select_all(e=None):
            for cb in self._spectra_checkboxes.values():
                cb.value = True
            _update_import_btn_state()
            self.page.update()

        def deselect_all(e=None):
            for cb in self._spectra_checkboxes.values():
                cb.value = False
            _update_import_btn_state()
            self.page.update()

        def on_ident_mode_change(e=None):
            rebuild_ident_parser_options()
            rebuild_ident_selection_area()
            _update_collect_proteins_state()
            _update_import_btn_state()
            self.page.update()

        def on_ident_parser_change(e=None):
            _update_collect_proteins_state()
            self.page.update()

        # ── Wire up event handlers ──
        subset_dropdown.on_change = lambda e: on_subset_change()
        spectra_parser_dropdown.on_change = lambda e: on_spectra_parser_change()
        tool_field.on_change = lambda e: on_tool_change()
        select_all_btn.on_click = lambda e: select_all()
        deselect_all_btn.on_click = lambda e: deselect_all()
        for cb in self._spectra_checkboxes.values():
            cb.on_change = lambda e: on_spectra_checkbox_change()
        ident_mode_group.on_change = lambda e: on_ident_mode_change()
        ident_parser_dropdown.on_change = lambda e: on_ident_parser_change()

        import_btn.on_click = lambda e: self.page.run_task(
            self._start_import,
            subset_dropdown,
            spectra_parser_dropdown,
            ident_parser_dropdown,
            ident_mode_group,
            tool_field,
            cb_import_fasta,
            cb_collect_proteins,
            cb_delete_temp,
        )

        # ── Initial state ──
        _update_collect_proteins_state()
        _update_import_btn_state()

        # ── Build layout ──
        self.dialog.content = ft.Column([
            ft.Text("Configure Import", size=16, weight=ft.FontWeight.BOLD),
            ft.Divider(),

            ft.Row([switch_field, check_btn], spacing=10),
            title_text,
            description_field,
            ft.Divider(),

            ft.Text("Import Settings", weight=ft.FontWeight.BOLD, size=13),
            ft.Row([
                subset_dropdown,
                spectra_parser_dropdown,
                tool_field,
            ], spacing=10),
            ft.Divider(),

            ft.Text("Spectra Files (.mgf)", weight=ft.FontWeight.BOLD, size=13),
            ft.Row([select_all_btn, deselect_all_btn], spacing=5),
            ft.Container(content=spectra_list, height=150),
            ft.Divider(),

            ft.Text("Identifications", weight=ft.FontWeight.BOLD, size=13),
            ft.Text("Import type:", size=12),
            ident_mode_group,
            ident_parser_dropdown,
            self._ident_selection_container,
            ft.Divider(),

            ft.Text("Options", weight=ft.FontWeight.BOLD, size=13),
            cb_import_fasta,
            cb_collect_proteins,
            cb_delete_temp,
        ], tight=True, width=580, height=620, scroll=ft.ScrollMode.AUTO)

        self.dialog.actions = [cancel_btn, import_btn]
        self.page.update()

    async def _on_switch(self, switch_field):
        """Re-check a new PXD identifier entered on screen 2."""
        identifier = (switch_field.value or "").strip()
        if not identifier:
            show_snack(self.page, "Please enter a PXD identifier.", ft.Colors.RED_400)
            return

        module, err = _load_pride_module()
        if err is not None:
            show_snack(
                self.page,
                "PRIDE import is unavailable: pridepy not installed.",
                ft.Colors.RED_400,
            )
            return

        try:
            dataset = await asyncio.to_thread(module["PrideDataset"], identifier)
        except DasmixerNetworkException:
            show_snack(
                self.page,
                "No network connection. Check your internet and try again.",
                ft.Colors.RED_400,
            )
            return
        except module["PrideDatasetNotFoundException"]:
            show_snack(self.page, f"Dataset `{identifier}` not found in PRIDE.", ft.Colors.RED_400)
            return
        except Exception as ex:
            logger.exception("Failed to fetch PRIDE dataset %s", identifier)
            show_snack(self.page, f"Error fetching dataset: {ex}", ft.Colors.RED_400)
            return

        self._dataset = dataset
        await self._show_screen2(
            no_files_error=(
                len(dataset.spectra_files) == 0 or len(dataset.ident_files) == 0
            )
        )

    # ─── Screen 3: Progress ───────────────────────────────────────

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

    async def _on_progress(self, p):
        # Progress screen is already shown by _start_import before the run
        # starts. Just update the content based on stage.
        if self._progress_text is None:
            return

        self._progress_text.value = p.message
        if p.total > 0:
            self._progress_bar.value = p.current / p.total
        self._progress_details.value = f"Stage: {p.stage}"
        self.page.update()

    async def _start_import(
        self,
        subset_dropdown,
        spectra_parser_dropdown,
        ident_parser_dropdown,
        ident_mode_group,
        tool_field,
        cb_import_fasta,
        cb_collect_proteins,
        cb_delete_temp,
    ):
        module, err = _load_pride_module()
        if err is not None:
            show_snack(
                self.page,
                "PRIDE import is unavailable: pridepy not installed.",
                ft.Colors.RED_400,
            )
            return

        selected_spectra = [
            name for name, cb in self._spectra_checkboxes.items() if cb.value
        ]
        if not selected_spectra:
            show_snack(self.page, "Select at least one spectra file.", ft.Colors.RED_400)
            return

        ident_mode = ident_mode_group.value
        ident_parser = ident_parser_dropdown.value

        ident_file_mapping: dict[str, str] = {}
        single_ident_file: str | None = None

        if ident_mode == "single":
            single_ident_file = (
                self._single_ident_dropdown.value
                if self._single_ident_dropdown is not None
                else None
            )
            if not single_ident_file:
                show_snack(
                    self.page,
                    "Select an identification file.",
                    ft.Colors.RED_400,
                )
                return
        else:
            ident_file_mapping = {
                spectra_name: dd.value
                for spectra_name, dd in self._ident_mapping_dropdowns.items()
                if dd.value
            }

        self._show_progress_screen()

        options = module["PrideImportOptions"](
            dataset_id=self._dataset.dataset_id,
            subset_id=int(subset_dropdown.value),
            spectra_parser=spectra_parser_dropdown.value,
            ident_parser=ident_parser,
            ident_mode=ident_mode,
            tool_name=tool_field.value,
            selected_spectra_files=selected_spectra,
            ident_file_mapping=ident_file_mapping,
            single_ident_file=single_ident_file,
            import_fasta=cb_import_fasta.value,
            collect_proteins=cb_collect_proteins.value,
            delete_temp_files=cb_delete_temp.value,
        )

        try:
            summary = await module["run_pride_import"](
                self.project,
                self._dataset,
                options,
                progress_callback=self._on_progress,
            )
            self._close()
            msg = (
                f"PRIDE import complete: {summary['samples_processed']} sample(s), "
                f"{summary['spectra_imported']} spectra, "
                f"{summary['identifications_imported']} identifications"
            )
            if summary["fasta_files_imported"]:
                msg += f", {summary['fasta_files_imported']} FASTA file(s)"
            show_snack(self.page, msg, ft.Colors.GREEN_400)
            if self.on_complete_callback:
                await self.on_complete_callback()
        except Exception as ex:
            logger.exception(ex)
            self._close()
            show_snack(self.page, f"PRIDE import error: {ex}", ft.Colors.RED_400)
        self.page.update()

    # ─── Helpers ─────────────────────────────────────────────────

    def _close(self):
        self.dialog.open = False
        self.page.update()
