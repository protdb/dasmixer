"""ManageSamplesView — full-screen view for per-sample management.

Opened from SamplesSummarySection via "Manage Samples" button.
Displays the full ExpansionPanelList with all sample details and actions.
On back-navigation the control list is cleared to release memory.
"""

import json
from pathlib import Path
from typing import Callable, Awaitable

import flet as ft

from dasmixer.api.project.dataclasses import Sample
from dasmixer.api.project.project import Project
from dasmixer.gui.utils import show_snack
from dasmixer.utils import logger


class ManageSamplesView(ft.View):
    """
    ft.View pushed on top of the view stack for /samples route.

    Manages:
    - Full ExpansionPanelList of samples (file tree + actions)
    - Update / recalculate stats button
    - min_proteins / min_idents threshold fields
    - Back button that pops this view and calls on_back callback
    """

    def __init__(self, project: Project, on_back: Callable[[], Awaitable[None]]):
        super().__init__(route="/samples", padding=0)
        self.project = project
        self._on_back_cb = on_back

        # State
        self._samples: list[Sample] = []
        self._tools_count: int = 0
        self._panel_index: dict[int, int] = {}

        # Controls
        self._panels_list: ft.ExpansionPanelList | None = None
        self._min_proteins_field: ft.TextField | None = None
        self._min_idents_field: ft.TextField | None = None
        self._update_btn: ft.ElevatedButton | None = None
        self._update_loader: ft.ProgressRing | None = None

        self.appbar = self._build_appbar()
        self.controls = [self._build_body()]

    # ------------------------------------------------------------------
    # AppBar with back button
    # ------------------------------------------------------------------

    def _build_appbar(self) -> ft.AppBar:
        return ft.AppBar(
            leading=ft.IconButton(
                icon=ft.Icons.ARROW_BACK,
                tooltip="Back to Samples tab",
                on_click=lambda e: self.page.run_task(self._on_back_clicked) if self.page else None,
            ),
            title=ft.Text("Manage Samples", size=18, weight=ft.FontWeight.BOLD),
        )

    # ------------------------------------------------------------------
    # Body
    # ------------------------------------------------------------------

    def _build_body(self) -> ft.Control:
        self._min_proteins_field = ft.TextField(
            label="Min proteins",
            value="30",
            width=130,
            keyboard_type=ft.KeyboardType.NUMBER,
            dense=True,
        )
        self._min_idents_field = ft.TextField(
            label="Min identifications",
            value="1000",
            width=170,
            keyboard_type=ft.KeyboardType.NUMBER,
            dense=True,
        )
        self._update_loader = ft.ProgressRing(
            width=20, height=20, stroke_width=2,
            color=ft.Colors.BLUE_400, visible=False,
        )
        self._update_btn = ft.ElevatedButton(
            content=ft.Text("Update"),
            icon=ft.Icons.REFRESH,
            on_click=lambda e: self.page.run_task(self._on_update_clicked) if self.page else None,
        )

        self._panels_list = ft.ExpansionPanelList(
            expand_icon_color=ft.Colors.BLUE_400,
            elevation=2,
            divider_color=ft.Colors.GREY_300,
            controls=[],
        )

        return ft.Column(
            [
                ft.Container(
                    content=ft.Row(
                        [
                            self._update_btn,
                            self._update_loader,
                            self._min_proteins_field,
                            self._min_idents_field,
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.symmetric(horizontal=16, vertical=8),
                ),
                ft.Container(
                    content=self._panels_list,
                    padding=ft.padding.symmetric(horizontal=16),
                    expand=True,
                ),
            ],
            spacing=0,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def did_mount(self):
        self.page.run_task(self._load_data)

    def will_unmount(self):
        """Free panel controls from memory when navigating away."""
        if self._panels_list is not None:
            self._panels_list.controls.clear()
        self._samples.clear()
        self._panel_index.clear()

    # ------------------------------------------------------------------
    # Back navigation
    # ------------------------------------------------------------------

    async def _on_back_clicked(self):
        await self._on_back_cb()

    # ------------------------------------------------------------------
    # Initial data load — fast path from cache
    # ------------------------------------------------------------------

    async def _load_data(self):
        """Load panels: use cache where available, fetch fresh for uncached."""
        self._samples = await self.project.get_samples()
        self._tools_count = await self.project.get_tools_count()
        min_proteins, min_idents = self._thresholds()
        all_cached = await self.project.get_all_cached_sample_stats()

        if self._panels_list is None:
            return

        self._panels_list.controls.clear()
        self._panel_index.clear()

        if not self._samples:
            self._panels_list.controls.append(
                ft.ExpansionPanel(
                    header=ft.ListTile(
                        title=ft.Text(
                            "No samples yet. Import spectra to add samples.",
                            color=ft.Colors.GREY_600, italic=True,
                        )
                    ),
                    content=ft.Container(),
                    can_tap_header=False,
                )
            )
        else:
            for idx, sample in enumerate(self._samples):
                sid = int(sample.id or 0)
                stats = all_cached.get(sid) or _empty_stats()
                panel = await self._build_sample_panel(sample, stats, min_proteins, min_idents)
                self._panel_index[sid] = idx
                self._panels_list.controls.append(panel)

        if self._panels_list.page:
            self._panels_list.update()

        # Background-refresh uncached samples
        if self._samples:
            uncached_ids = [
                int(s.id)
                for s in self._samples
                if s.id is not None and int(s.id) not in all_cached
            ]
            for sample_id in uncached_ids:
                await self._refresh_single_stats_in_place(sample_id, save_cache=True)

    # ------------------------------------------------------------------
    # Manual update — full recalc
    # ------------------------------------------------------------------

    async def _on_update_clicked(self):
        self._set_loader(True)
        try:
            self._samples = await self.project.get_samples()
            self._tools_count = await self.project.get_tools_count()
            min_proteins, min_idents = self._thresholds()

            if self._panels_list is not None:
                self._panels_list.controls.clear()
            self._panel_index.clear()

            if not self._samples:
                if self._panels_list is not None:
                    self._panels_list.controls.append(
                        ft.ExpansionPanel(
                            header=ft.ListTile(
                                title=ft.Text("No samples yet.", color=ft.Colors.GREY_600, italic=True)
                            ),
                            content=ft.Container(),
                            can_tap_header=False,
                        )
                    )
                if self._panels_list is not None and self._panels_list.page:
                    self._panels_list.update()
            else:
                for idx, sample in enumerate(self._samples):
                    sid = int(sample.id or 0)
                    stats = await self.project.get_sample_stats(sid)
                    await self.project.upsert_sample_status_cache(sid, stats)
                    panel = await self._build_sample_panel(sample, stats, min_proteins, min_idents)
                    self._panel_index[sid] = idx
                    if self._panels_list is not None:
                        self._panels_list.controls.append(panel)

                await self.project.save()

                if self._panels_list is not None and self._panels_list.page:
                    self._panels_list.update()

        except Exception:
            logger.exception("ManageSamplesView._on_update_clicked error")
            if self.page:
                show_snack(self.page, "Error updating samples", ft.Colors.RED_400)
                self.page.update()
        finally:
            self._set_loader(False)

    # ------------------------------------------------------------------
    # Per-sample refresh
    # ------------------------------------------------------------------

    async def refresh_single_panel(self, sample_id: int) -> None:
        sample = next((s for s in self._samples if s.id == sample_id), None)
        if sample is None:
            await self._load_data()
            return

        refreshed = await self.project.get_sample(sample_id)
        if refreshed is None:
            await self._load_data()
            return

        for i, s in enumerate(self._samples):
            if s.id == sample_id:
                self._samples[i] = refreshed
                break

        await self._refresh_single_stats_in_place(sample_id, save_cache=True)

    async def _refresh_single_stats_in_place(self, sample_id: int, save_cache: bool = False) -> None:
        sample = next((s for s in self._samples if s.id == sample_id), None)
        if sample is None:
            return

        stats = await self.project.get_sample_stats(sample_id)
        if save_cache:
            await self.project.upsert_sample_status_cache(sample_id, stats)
            await self.project.save()

        idx = self._panel_index.get(sample_id)
        if idx is None:
            return

        min_proteins, min_idents = self._thresholds()
        new_panel = await self._build_sample_panel(sample, stats, min_proteins, min_idents)
        if self._panels_list is not None:
            self._panels_list.controls[idx] = new_panel
            if self._panels_list.page:
                self._panels_list.update()

    # ------------------------------------------------------------------
    # Loader helper
    # ------------------------------------------------------------------

    def _set_loader(self, visible: bool) -> None:
        if self._update_loader is None:
            return
        self._update_loader.visible = visible
        if self._update_btn is not None:
            self._update_btn.disabled = visible
        if self.page:
            if self._update_loader.page:
                self._update_loader.update()
            if self._update_btn and self._update_btn.page:
                self._update_btn.update()

    def _thresholds(self) -> tuple[int, int]:
        try:
            mp = int(self._min_proteins_field.value or 30)
        except (ValueError, AttributeError):
            mp = 30
        try:
            mi = int(self._min_idents_field.value or 1000)
        except (ValueError, AttributeError):
            mi = 1000
        return mp, mi

    # ------------------------------------------------------------------
    # Panel builder — identical logic to old SamplesSection
    # ------------------------------------------------------------------

    async def _build_sample_panel(
        self,
        sample: Sample,
        stats: dict,
        min_proteins: int,
        min_idents: int,
    ) -> ft.ExpansionPanel:
        header = _build_sample_header(sample, stats, self._tools_count, min_proteins, min_idents)
        body   = await self._build_sample_body(sample, stats, min_idents)
        return ft.ExpansionPanel(
            header=ft.ListTile(title=header),
            content=ft.Container(
                content=body,
                padding=ft.padding.only(left=16, right=16, bottom=16),
            ),
            expanded=False,
            can_tap_header=True,
        )

    async def _build_sample_body(self, sample: Sample, stats: dict, min_idents: int) -> ft.Control:
        detail = await self.project.get_sample_detail(int(sample.id or 0))
        body_controls: list[ft.Control] = []

        if detail:
            for sf in detail:
                sf_id = int(sf['id'])
                sf_name = Path(sf['path']).name

                spectra_row = ft.Row([
                    ft.Icon(ft.Icons.GRAPHIC_EQ, size=16, color=ft.Colors.BLUE_600),
                    ft.Text(sf_name, weight=ft.FontWeight.BOLD, size=13),
                    ft.Text(f"({sf['format']})", size=11, color=ft.Colors.GREY_600),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.ADD_CIRCLE_OUTLINE,
                        icon_color=ft.Colors.BLUE_500,
                        tooltip="Add identification file",
                        on_click=lambda e, _sf_id=sf_id, _s=sample:
                            self.page.run_task(self._add_identification_file, _sf_id, _s)
                            if self.page else None,
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=ft.Colors.RED_400,
                        tooltip="Delete spectra file",
                        on_click=lambda e, _sf_id=sf_id, _s=sample:
                            self.page.run_task(self._delete_spectra_file, _sf_id, _s)
                            if self.page else None,
                    ),
                ], spacing=4)
                body_controls.append(spectra_row)

                for ident_file in sf.get('ident_files', []):
                    if_id = int(ident_file['id'])
                    count = int(ident_file.get('ident_count', 0))
                    is_empty = count == 0
                    is_below = 0 < count < min_idents
                    row_border = None
                    if is_empty:
                        row_border = ft.border.all(1, ft.Colors.RED_400)
                    elif is_below:
                        row_border = ft.border.all(1, ft.Colors.ORANGE_400)

                    ident_row = ft.Container(
                        content=ft.Row([
                            ft.Container(width=20),
                            ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=14, color=ft.Colors.GREY_600),
                            ft.Text(ident_file.get('tool_name', '?'), size=12, weight=ft.FontWeight.W_500),
                            ft.Text(Path(ident_file.get('file_path', '')).name, size=12, color=ft.Colors.GREY_700),
                            ft.Text(f"({count} idents)", size=11,
                                    color=ft.Colors.RED_600 if is_empty else ft.Colors.GREY_600),
                            ft.Container(expand=True),
                            ft.IconButton(
                                icon=ft.Icons.DELETE_OUTLINE,
                                icon_color=ft.Colors.RED_400,
                                tooltip="Delete identification file",
                                on_click=lambda e, _if_id=if_id, _s=sample:
                                    self.page.run_task(self._delete_ident_file, _if_id, _s)
                                    if self.page else None,
                            ),
                        ], spacing=4),
                        border=row_border,
                        border_radius=4,
                        padding=ft.padding.symmetric(horizontal=4, vertical=2),
                    )
                    body_controls.append(ident_row)

        body_controls.append(
            ft.TextButton(
                content=ft.Row([
                    ft.Icon(ft.Icons.ADD, size=16),
                    ft.Text("Add spectra file", size=13),
                ], spacing=4, tight=True),
                on_click=lambda e, s=sample:
                    self.page.run_task(self._add_spectra_file, s) if self.page else None,
            )
        )
        body_controls.append(ft.Divider(height=8))

        # Additions
        if sample.additions:
            try:
                additions_text = json.dumps(sample.additions, indent=2, ensure_ascii=False)
            except Exception:
                additions_text = str(sample.additions)
            body_controls.append(
                ft.Text(f"Additions:\n{additions_text}", size=11, color=ft.Colors.GREY_700,
                        font_family="monospace")
            )
            body_controls.append(ft.Container(height=6))

        # Action buttons
        left_buttons = ft.Row([
            ft.ElevatedButton(content=ft.Text("Calculate ions"), icon=ft.Icons.BOLT,
                on_click=lambda e, s=sample: self.page.run_task(self._action_calculate_ions, s) if self.page else None),
            ft.ElevatedButton(content=ft.Text("Select preferred"), icon=ft.Icons.STAR_OUTLINE,
                on_click=lambda e, s=sample: self.page.run_task(self._action_select_preferred, s) if self.page else None),
            ft.ElevatedButton(content=ft.Text("Match proteins"), icon=ft.Icons.LINK,
                on_click=lambda e, s=sample: self.page.run_task(self._action_match_proteins, s) if self.page else None),
            ft.ElevatedButton(content=ft.Text("Protein Identifications"), icon=ft.Icons.BIOTECH,
                on_click=lambda e, s=sample: self.page.run_task(self._action_protein_identifications, s) if self.page else None),
            ft.ElevatedButton(content=ft.Text("LFQ"), icon=ft.Icons.ANALYTICS,
                on_click=lambda e, s=sample: self.page.run_task(self._action_lfq, s) if self.page else None),
        ], spacing=6, wrap=True)

        right_buttons = ft.Row([
            ft.ElevatedButton(
                content=ft.Row([ft.Icon(ft.Icons.EDIT_OUTLINED, size=16), ft.Text("Edit")], spacing=4, tight=True),
                tooltip="Edit sample properties",
                on_click=lambda e, s=sample: self.page.run_task(self._show_edit_dialog, s) if self.page else None,
            ),
            ft.ElevatedButton(
                content=ft.Row([
                    ft.Icon(ft.Icons.FLAG if sample.outlier else ft.Icons.FLAG_OUTLINED, size=16,
                            color=ft.Colors.RED_500 if sample.outlier else None),
                    ft.Text("Outlier"),
                ], spacing=4, tight=True),
                tooltip="Toggle outlier mark",
                on_click=lambda e, s=sample: self.page.run_task(self._toggle_outlier, s) if self.page else None,
            ),
            ft.ElevatedButton(
                content=ft.Row([
                    ft.Icon(ft.Icons.DELETE_OUTLINED, size=16, color=ft.Colors.RED_600),
                    ft.Text("Delete", color=ft.Colors.RED_600),
                ], spacing=4, tight=True),
                tooltip="Delete sample",
                on_click=lambda e, s=sample: self.page.run_task(self._delete_sample, s) if self.page else None,
            ),
        ], spacing=6)

        body_controls.append(ft.Row([left_buttons, ft.Container(expand=True), right_buttons]))
        return ft.Column(body_controls, spacing=6)

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    async def _delete_spectra_file(self, sf_id: int, sample: Sample):
        if not await self._confirm("Delete spectra file?",
                "This will also delete all linked identifications and peptide matches."):
            return
        try:
            await self.project.delete_spectra_file(sf_id)
            self._show_success("Spectra file deleted")
            await self.refresh_single_panel(sample.id)
        except Exception as ex:
            self._show_error(f"Error: {ex}")

    async def _delete_ident_file(self, if_id: int, sample: Sample):
        if not await self._confirm("Delete identification file?",
                "This will also delete all linked identifications and peptide matches."):
            return
        try:
            await self.project.delete_identification_file(if_id)
            self._show_success("Identification file deleted")
            await self.refresh_single_panel(sample.id)
        except Exception as ex:
            self._show_error(f"Error: {ex}")

    async def _add_spectra_file(self, sample: Sample):
        from dasmixer.gui.views.tabs.samples.dialogs.import_single_dialog import ImportSingleDialog
        from dasmixer.gui.views.tabs.samples.import_handlers import ImportHandlers

        async def on_complete():
            await self.refresh_single_panel(sample.id)

        handlers = ImportHandlers(self.project, self.page, on_complete_callback=on_complete)
        dialog = ImportSingleDialog(
            project=self.project, page=self.page, import_type="spectra",
            on_import_callback=handlers.import_spectra_files,
            fixed_sample_name=sample.name, lock_group=True,
        )
        await dialog.show()

    async def _add_identification_file(self, sf_id: int, sample: Sample):
        tools = await self.project.get_tools()
        if not tools:
            self._show_warning("No tools configured.")
            return
        if len(tools) == 1:
            await self._do_add_identification_file(sf_id, sample, tools[0].id)
        else:
            await self._show_tool_picker(sf_id, sample, tools)

    async def _show_tool_picker(self, sf_id: int, sample: Sample, tools):
        options = [ft.DropdownOption(key=str(t.id), text=t.name) for t in tools]
        tool_dropdown = ft.Dropdown(label="Select Tool", options=options, value=str(tools[0].id), width=300)

        async def on_confirm(e):
            dlg.open = False
            self.page.update()
            await self._do_add_identification_file(sf_id, sample, int(tool_dropdown.value))

        dlg = ft.AlertDialog(
            title=ft.Text("Select Tool"),
            content=tool_dropdown,
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: setattr(dlg, 'open', False) or self.page.update()),
                ft.ElevatedButton("Select", on_click=lambda e: self.page.run_task(on_confirm, e)),
            ],
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    async def _do_add_identification_file(self, sf_id: int, sample: Sample, tool_id: int):
        from dasmixer.gui.views.tabs.samples.dialogs.import_single_dialog import ImportSingleDialog
        from dasmixer.gui.views.tabs.samples.import_handlers import ImportHandlers

        async def on_complete():
            await self.refresh_single_panel(sample.id)

        handlers = ImportHandlers(self.project, self.page, on_complete_callback=on_complete)
        dialog = ImportSingleDialog(
            project=self.project, page=self.page, import_type="identifications",
            tool_id=tool_id, on_import_callback=handlers.import_identification_files,
            fixed_sample_name=sample.name, fixed_spectra_file_id=sf_id, lock_group=True,
        )
        await dialog.show()

    # ------------------------------------------------------------------
    # Sample operations
    # ------------------------------------------------------------------

    async def _show_edit_dialog(self, sample: Sample):
        from dasmixer.gui.views.tabs.samples.dialogs.sample_dialog import SampleDialog

        async def on_saved():
            await self.refresh_single_panel(sample.id)

        dialog = SampleDialog(self.project, self.page, sample, on_success_callback=on_saved)
        await dialog.show()

    async def _toggle_outlier(self, sample: Sample):
        try:
            sample.outlier = not sample.outlier
            await self.project.update_sample(sample)
            await self.refresh_single_panel(sample.id)
        except Exception as ex:
            self._show_error(f"Error: {ex}")

    async def _delete_sample(self, sample: Sample):
        if not await self._confirm(f"Delete sample '{sample.name}'?",
                "This will delete all spectra files, identifications and peptide matches."):
            return
        try:
            await self.project.delete_sample(sample.id)
            self._show_success(f"Deleted sample: {sample.name}")
            self._samples = [s for s in self._samples if s.id != sample.id]
            await self._rebuild_panels_from_cache()
        except Exception as ex:
            self._show_error(f"Error: {ex}")

    async def _rebuild_panels_from_cache(self):
        all_cached = await self.project.get_all_cached_sample_stats()
        min_proteins, min_idents = self._thresholds()

        if self._panels_list is None:
            return

        self._panels_list.controls.clear()
        self._panel_index.clear()

        for idx, sample in enumerate(self._samples):
            stats = all_cached.get(sample.id) or _empty_stats()
            panel = await self._build_sample_panel(sample, stats, min_proteins, min_idents)
            self._panel_index[sample.id] = idx
            self._panels_list.controls.append(panel)

        if self._panels_list.page:
            self._panels_list.update()

    # ------------------------------------------------------------------
    # Action buttons
    # ------------------------------------------------------------------

    async def _action_calculate_ions(self, sample: Sample):
        state = self._get_peptides_state()
        if state is None:
            self._show_warning("Open Peptides tab first to configure ion settings")
            return
        from dasmixer.gui.actions.ion_actions import IonCoverageAction
        action = IonCoverageAction(self.project, self.page)
        await action.run(state=state, recalc_all=False, sample_id=sample.id)
        await self.refresh_single_panel(sample.id)

    async def _action_select_preferred(self, sample: Sample):
        tool_settings = self._get_tool_settings()
        if not tool_settings:
            self._show_warning("Configure tool settings in the Peptides tab first.")
            return
        criterion = self._get_matching_criterion()
        from dasmixer.gui.actions.ion_actions import SelectPreferredAction
        action = SelectPreferredAction(self.project, self.page)
        await action.run(tool_settings=tool_settings, criterion=criterion, sample_id=sample.id)
        await self.refresh_single_panel(sample.id)

    async def _action_match_proteins(self, sample: Sample):
        state = self._get_peptides_state()
        if state is None:
            self._show_warning("Open Peptides tab first to configure ion settings")
            return
        from dasmixer.gui.actions.protein_map_action import MatchProteinsAction
        action = MatchProteinsAction(self.project, self.page)
        await action.run(state=state, sample_id=sample.id)
        await self.refresh_single_panel(sample.id)

    async def _action_protein_identifications(self, sample: Sample):
        min_pep, min_uq = self._get_protein_detection_params()
        from dasmixer.gui.actions.protein_ident_action import ProteinIdentificationsAction
        action = ProteinIdentificationsAction(self.project, self.page)
        await action.run(min_peptides=min_pep, min_uq_evidence=min_uq, sample_id=sample.id)
        await self.refresh_single_panel(sample.id)

    async def _action_lfq(self, sample: Sample):
        state = self._get_proteins_state()
        if state is None:
            self._show_warning("Open Proteins tab first to configure LFQ settings")
            return
        from dasmixer.gui.actions.lfq_action import LFQAction
        action = LFQAction(self.project, self.page)
        await action.run(state=state, sample_id=sample.id)
        await self.refresh_single_panel(sample.id)

    # ------------------------------------------------------------------
    # Settings getters (same as old SamplesSection)
    # ------------------------------------------------------------------

    def _get_peptides_state(self):
        if self.page and hasattr(self.page, 'peptides_tab'):
            return self.page.peptides_tab.state
        return None

    def _get_tool_settings(self) -> dict:
        if self.page and hasattr(self.page, 'peptides_tab'):
            ts = self.page.peptides_tab.sections.get('tool_settings')
            if ts:
                return ts.get_tool_settings_for_matching()
        return {}

    def _get_matching_criterion(self) -> str:
        if self.page and hasattr(self.page, 'peptides_tab'):
            ms = self.page.peptides_tab.sections.get('matching')
            if ms and hasattr(ms, 'selection_criterion_group'):
                return ms.selection_criterion_group.value or 'intensity'
        return 'intensity'

    def _get_protein_detection_params(self) -> tuple[int, int]:
        if self.page and hasattr(self.page, 'proteins_tab'):
            ds = self.page.proteins_tab.sections.get('detection')
            if ds:
                try:
                    return int(ds.min_peptides_field.value), int(ds.min_unique_field.value)
                except (ValueError, AttributeError):
                    pass
        return 2, 1

    def _get_proteins_state(self):
        if self.page and hasattr(self.page, 'proteins_tab'):
            return self.page.proteins_tab.state
        return None

    # ------------------------------------------------------------------
    # Confirm dialog helper
    # ------------------------------------------------------------------

    async def _confirm(self, title: str, message: str) -> bool:
        import asyncio
        confirmed = False
        event = asyncio.Event()

        async def on_yes(e):
            nonlocal confirmed
            confirmed = True
            dlg.open = False
            self.page.update()
            event.set()

        def on_no(e):
            dlg.open = False
            self.page.update()
            event.set()

        dlg = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[
                ft.TextButton("Cancel", on_click=on_no),
                ft.ElevatedButton(
                    "Confirm",
                    style=ft.ButtonStyle(bgcolor=ft.Colors.RED_600, color=ft.Colors.WHITE),
                    on_click=lambda e: self.page.run_task(on_yes, e),
                ),
            ],
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()
        await event.wait()
        return confirmed

    # ------------------------------------------------------------------
    # Snack helpers
    # ------------------------------------------------------------------

    def _show_error(self, msg: str):
        if self.page:
            show_snack(self.page, msg, ft.Colors.RED_400)
            self.page.update()

    def _show_success(self, msg: str):
        if self.page:
            show_snack(self.page, msg, ft.Colors.GREEN_400)
            self.page.update()

    def _show_warning(self, msg: str):
        if self.page:
            show_snack(self.page, msg, ft.Colors.ORANGE_400)
            self.page.update()


# ------------------------------------------------------------------
# Module-level pure helpers (no self, reusable)
# ------------------------------------------------------------------

def _empty_stats() -> dict:
    return {
        'spectra_files_count': 0, 'ident_files_count': 0,
        'identifications_count': 0, 'preferred_count': 0,
        'coverage_known_count': 0, 'protein_ids_count': 0,
        'empty_ident_files_count': 0,
    }


def _build_sample_header(
    sample: Sample,
    stats: dict,
    tools_count: int,
    min_proteins: int,
    min_idents: int,
) -> ft.Control:
    sf_count  = stats.get('spectra_files_count', 0)
    if_count  = stats.get('ident_files_count', 0)
    idents    = stats.get('identifications_count', 0)
    preferred = stats.get('preferred_count', 0)
    coverage  = stats.get('coverage_known_count', 0)
    proteins  = stats.get('protein_ids_count', 0)
    empty_if  = stats.get('empty_ident_files_count', 0)

    has_spectra = sf_count > 0
    has_ident   = if_count > 0
    expected_if = tools_count * sf_count if sf_count > 0 else 0
    ident_ok    = (expected_if == 0) or (if_count == expected_if)
    idents_ok   = idents >= min_idents
    proteins_ok = (proteins == 0) or (proteins >= min_proteins)

    if not has_spectra or (has_spectra and not has_ident):
        marker_icon, marker_color = ft.Icons.ERROR_OUTLINE_OUTLINED, ft.Colors.RED_600
    elif has_spectra and has_ident and ident_ok and idents_ok and proteins_ok and empty_if == 0:
        marker_icon, marker_color = ft.Icons.CHECK_CIRCLE_OUTLINE_OUTLINED, ft.Colors.GREEN_600
    else:
        marker_icon, marker_color = ft.Icons.WARNING_AMBER_OUTLINED, ft.Colors.AMBER_600

    controls: list[ft.Control] = [ft.Icon(marker_icon, color=marker_color, size=20)]
    if sample.outlier:
        controls.append(ft.Icon(ft.Icons.FLAG, color=ft.Colors.RED_500, size=16))

    controls += [
        ft.Text(sample.name, weight=ft.FontWeight.BOLD, size=14, no_wrap=True),
        ft.Text("·", color=ft.Colors.GREY_400, size=12),
        ft.Text(sample.subset_name or "No group", color=ft.Colors.GREY_700, size=12, no_wrap=True),
        ft.Text("·", color=ft.Colors.GREY_400, size=12),
        ft.Text(f"Files: {sf_count}", size=11, color=ft.Colors.GREY_800),
        ft.Text(f"ID files: {if_count}", size=11, color=ft.Colors.GREY_800),
        ft.Text(f"Idents: {idents}", size=11,
                color=ft.Colors.RED_700 if not idents_ok and has_ident else ft.Colors.GREY_800),
        ft.Text(f"Coverage: {coverage}", size=11, color=ft.Colors.GREY_800),
        ft.Text(f"Preferred: {preferred}", size=11, color=ft.Colors.GREY_800),
        ft.Text(f"Proteins: {proteins}", size=11,
                color=ft.Colors.RED_700 if not proteins_ok and proteins > 0 else ft.Colors.GREY_800),
    ]

    if empty_if > 0:
        controls.append(ft.Icon(
            ft.Icons.WARNING_AMBER_OUTLINED, color=ft.Colors.ORANGE_500, size=14,
            tooltip=ft.Tooltip(message=f"{empty_if} identification file(s) have zero identifications"),
        ))

    return ft.Row(controls, spacing=6, wrap=False)
