"""ManageSamplesView — full-screen view for per-sample management.

Refactored into a thin orchestrator that delegates to:
- SampleDataManager for data operations
- UpdateRow for the update/loader/threshold row
- SampleViewPanel for individual sample panels (with checkbox)
- MassOperationsRow for mass-operation buttons
- SamplesFilterRow for in-memory filtering
- SamplesPaginationRow for in-memory pagination
"""

import asyncio
from typing import Callable, Awaitable

import flet as ft

from dasmixer.api.project.dataclasses import Sample
from dasmixer.api.project.project import Project
from dasmixer.gui.utils import show_snack
from dasmixer.utils import logger

from .data_manager import SampleDataManager
from .update_row import UpdateRow
from .sample_panel import SampleViewPanel, compute_sample_status
from .mass_operations_row import MassOperationsRow
from .filters_row import SamplesFilterRow
from .pagination_row import SamplesPaginationRow


class ManageSamplesView(ft.View):
    """
    ft.View pushed on top of the view stack for /samples route.

    Thin orchestrator that delegates to helper components.
    """

    def __init__(self, project: Project, on_back: Callable[[], Awaitable[None]]):
        super().__init__(route="/samples", padding=0)
        self.project = project
        self._on_back_cb = on_back

        # Data manager
        self._data_manager = SampleDataManager(project)

        # State
        self._samples: list[Sample] = []
        self._all_stats: dict[int, dict] = {}
        self._filtered_samples: list[Sample] = []
        self._page_samples: list[Sample] = []
        self._tools_count: int = 0
        self._panel_index: dict[int, int] = {}
        self._selected_ids: set[int] = set()

        # Controls
        self._panels_list: ft.ExpansionPanelList | None = None
        self._update_row: UpdateRow | None = None
        self._mass_ops_row: MassOperationsRow | None = None
        self._filters_row: SamplesFilterRow | None = None
        self._pagination_row: SamplesPaginationRow | None = None
        self._panel_controls: list[SampleViewPanel] = []

        self.appbar = self._build_appbar()
        self.controls = [self._build_body()]

    # ------------------------------------------------------------------
    # AppBar
    # ------------------------------------------------------------------

    def _build_appbar(self) -> ft.AppBar:
        return ft.AppBar(
            leading=ft.IconButton(
                icon=ft.Icons.ARROW_BACK,
                tooltip="Back to Samples tab",
                on_click=lambda e: e.page.run_task(self._on_back_clicked),
            ),
            title=ft.Text("Manage Samples", size=18, weight=ft.FontWeight.BOLD),
        )

    # ------------------------------------------------------------------
    # Body
    # ------------------------------------------------------------------

    def _build_body(self) -> ft.Control:
        self._update_row = UpdateRow(
            project=self.project,
            on_update_clicked=self._on_update_clicked,
            on_import_additional=self._on_import_additional_clicked,
        )

        self._mass_ops_row = MassOperationsRow(
            on_select_all=self._on_select_all,
            on_deselect_all=self._on_deselect_all,
            on_outlier=self._on_mass_outlier,
            on_drop_file=self._on_mass_drop_file,
            on_assign_subset=self._on_mass_assign_subset,
            on_delete=self._on_mass_delete,
            on_drop_empty=self._on_drop_empty_files,
        )

        self._filters_row = SamplesFilterRow(
            subsets=[],
            on_apply=self._on_apply_filters,
        )

        self._pagination_row = SamplesPaginationRow(
            on_page_changed=self._recompute_page,
        )

        self._panels_list = ft.ExpansionPanelList(
            expand_icon_color=ft.Colors.BLUE_400,
            elevation=2,
            divider_color=ft.Colors.GREY_300,
            controls=[],
            on_change=self._on_panel_expansion_changed,
        )

        return ft.Column(
            [
                self._update_row,
                self._mass_ops_row,
                self._filters_row,
                self._pagination_row,
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
        if self._panels_list is not None:
            self._panels_list.controls.clear()
        self._samples.clear()
        self._all_stats.clear()
        self._filtered_samples.clear()
        self._page_samples.clear()
        self._panel_index.clear()
        self._panel_controls.clear()
        self._selected_ids.clear()

    # ------------------------------------------------------------------
    # Back navigation
    # ------------------------------------------------------------------

    async def _on_back_clicked(self):
        await self._on_back_cb()

    async def _on_import_additional_clicked(self):
        """Open ImportAdditionalData dialog."""
        from .dialogs.import_additional_dialog import ImportAdditionalDialog
        dialog = ImportAdditionalDialog(self.project, self.page)
        await dialog.show()
        self._samples, self._all_stats, self._tools_count = await self._data_manager.load_all()
        await self._recompute_filtered()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    async def _load_data(self):
        """Load panels: use cache where available, fetch fresh for uncached."""
        try:
            await self._update_row.load_thresholds()

            self._samples, self._all_stats, self._tools_count = await self._data_manager.load_all()

            subsets = await self.project.get_subsets()
            self._filters_row.subset_dropdown.options = [
                ft.DropdownOption(key="all", text="All Subsets")
            ] + [
                ft.DropdownOption(key=str(s.id), text=s.name) for s in subsets
            ]
            if self._filters_row.page:
                self._filters_row.subset_dropdown.update()

            await self._load_filter_persist()
            await self._recompute_filtered()

            if self._samples:
                uncached_ids = [
                    int(s.id)
                    for s in self._samples
                    if s.id is not None and int(s.id) not in self._all_stats
                ]
                for sample_id in uncached_ids:
                    await self._refresh_single_stats_in_place(sample_id, save_cache=True)
        except Exception:
            logger.exception("ManageSamplesView._load_data error")
            if self.page:
                show_snack(self.page, "Error loading samples data", ft.Colors.RED_400)
                self.page.update()

    # ------------------------------------------------------------------
    # Filters
    # ------------------------------------------------------------------

    async def _on_apply_filters(self):
        """Apply filters and reset pagination to page 0."""
        filters = self._filters_row.get_filters()
        await self.project.set_setting('manage_samples_filter_name', filters['name'])
        await self.project.set_setting('manage_samples_filter_status', filters['status'])
        await self.project.set_setting('manage_samples_filter_subset_id', filters['subset_id'])
        await self.project.set_setting('manage_samples_filter_outlier', filters['outlier'])
        self._pagination_row.current_page = 0
        await self._recompute_filtered()

    async def _load_filter_persist(self) -> None:
        """Load persisted filters from project_settings and apply to UI."""
        filters = {
            'name': await self.project.get_setting('manage_samples_filter_name', ''),
            'status': await self.project.get_setting('manage_samples_filter_status', 'all'),
            'subset_id': await self.project.get_setting('manage_samples_filter_subset_id', 'all'),
            'outlier': await self.project.get_setting('manage_samples_filter_outlier', 'all'),
        }
        self._filters_row.set_filters(filters)

    # ------------------------------------------------------------------
    # Filtering and pagination pipeline
    # ------------------------------------------------------------------

    async def _recompute_filtered(self):
        """Apply in-memory filters to self._samples → self._filtered_samples.
        Then recompute page. Called after data load or filter change."""
        filters = self._filters_row.get_filters()
        min_proteins, min_idents = self._update_row.get_thresholds()

        name_term = filters['name'].lower()
        status_filter = filters['status']
        subset_filter = filters['subset_id']
        outlier_filter = filters['outlier']

        result = []
        for sample in self._samples:
            if name_term and name_term not in (sample.name or '').lower():
                continue
            if subset_filter != 'all' and str(sample.subset_id) != subset_filter:
                continue
            if outlier_filter == 'yes' and not sample.outlier:
                continue
            if outlier_filter == 'no' and sample.outlier:
                continue
            if status_filter != 'all':
                sid = int(sample.id or 0)
                stats = self._all_stats.get(sid) or {}
                status = compute_sample_status(stats, self._tools_count, min_proteins, min_idents)
                if status != status_filter:
                    continue
            result.append(sample)

        self._filtered_samples = result
        await self._recompute_page()

    async def _recompute_page(self):
        """Apply pagination to self._filtered_samples → self._page_samples,
        then rebuild panels. Called after filter change or page change."""
        self._page_samples = self._pagination_row.slice(self._filtered_samples)
        await self._rebuild_panels_from_page()

    # ------------------------------------------------------------------
    # Update — full recalc
    # ------------------------------------------------------------------

    async def _on_update_clicked(self):
        if self._update_row:
            self._update_row.set_loading(True)
        try:
            self._samples, self._all_stats, self._tools_count = await self._data_manager.refresh_all_fresh()
            await self._recompute_filtered()
        except Exception:
            logger.exception("ManageSamplesView._on_update_clicked error")
            if self.page:
                show_snack(self.page, "Error updating samples", ft.Colors.RED_400)
                self.page.update()
        finally:
            if self._update_row:
                self._update_row.set_loading(False)

    # ------------------------------------------------------------------
    # Per-sample refresh
    # ------------------------------------------------------------------

    async def refresh_single_panel(self, sample_id: int) -> None:
        sample = next((s for s in self._samples if s.id == sample_id), None)
        if sample is None:
            await self._load_data()
            return

        refreshed_sample, stats = await self._data_manager.refresh_single(sample_id, save_cache=True)
        if refreshed_sample is None:
            await self._load_data()
            return

        for i, s in enumerate(self._samples):
            if s.id == sample_id:
                self._samples[i] = refreshed_sample
                break

        idx = self._panel_index.get(sample_id)
        if idx is not None and idx < len(self._panel_controls):
            self._panel_controls[idx].invalidate_detail_cache()

        await self._refresh_single_stats_in_place(sample_id, save_cache=True)

    async def _refresh_single_stats_in_place(self, sample_id: int, save_cache: bool = False) -> None:
        sample = next((s for s in self._samples if s.id == sample_id), None)
        if sample is None:
            return

        _, stats = await self._data_manager.refresh_single(sample_id, save_cache=save_cache)

        self._all_stats[sample_id] = stats

        idx = self._panel_index.get(sample_id)
        if idx is None or self._panels_list is None:
            return

        min_proteins, min_idents = self._update_row.get_thresholds()

        if idx < len(self._panel_controls):
            panel_ctrl = self._panel_controls[idx]
            was_expanded = panel_ctrl._is_expanded
            panel_ctrl.invalidate_detail_cache()
            panel_ctrl.update_stats(stats, min_proteins, min_idents)
            new_panel = await panel_ctrl.build()
            self._panels_list.controls[idx] = new_panel
            if was_expanded and self._panels_list.page:
                await panel_ctrl.on_expand()
            if self._panels_list.page:
                self._panels_list.update()

    # ------------------------------------------------------------------
    # Panel expansion handler
    # ------------------------------------------------------------------

    def _on_panel_expansion_changed(self, e: ft.ControlEvent):
        """ExpansionPanelList.on_change fires with e.data = index of the toggled panel."""
        try:
            idx = int(e.data)
        except (TypeError, ValueError):
            return
        if idx < 0 or idx >= len(self._panel_controls):
            return
        panel_ctrl = self._panel_controls[idx]
        is_now_expanded = self._panels_list.controls[idx].expanded
        if is_now_expanded:
            self.page.run_task(panel_ctrl.on_expand)
        else:
            panel_ctrl.on_collapse()

    # ------------------------------------------------------------------
    # Panel action dispatcher
    # ------------------------------------------------------------------

    async def _on_panel_action(self, action: str, *args):
        """Dispatch actions from SampleViewPanel."""
        if action == 'get_detail':
            return await self._data_manager.get_sample_detail(args[0])
        elif action == 'add_ident_file':
            sf_id, sample = args
            await self._add_identification_file(sf_id, sample)
        elif action == 'delete_spectra_file':
            sf_id, sample = args
            await self._delete_spectra_file(sf_id, sample)
        elif action == 'delete_ident_file':
            if_id, sample = args
            await self._delete_ident_file(if_id, sample)
        elif action == 'add_spectra_file':
            sample = args[0]
            await self._add_spectra_file(sample)
        elif action == 'calculate_ions':
            sample = args[0]
            await self._action_calculate_ions(sample)
        elif action == 'select_preferred':
            sample = args[0]
            await self._action_select_preferred(sample)
        elif action == 'match_proteins':
            sample = args[0]
            await self._action_match_proteins(sample)
        elif action == 'protein_identifications':
            sample = args[0]
            await self._action_protein_identifications(sample)
        elif action == 'lfq':
            sample = args[0]
            await self._action_lfq(sample)
        elif action == 'edit_sample':
            sample = args[0]
            await self._show_edit_dialog(sample)
        elif action == 'toggle_outlier':
            sample = args[0]
            await self._toggle_outlier(sample)
        elif action == 'delete_sample':
            sample = args[0]
            await self._delete_sample(sample)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _on_selection_changed(self, sample_id: int, selected: bool):
        if selected:
            self._selected_ids.add(sample_id)
        else:
            self._selected_ids.discard(sample_id)

    def _on_select_all(self):
        """Select all samples on the current page (not all samples in the project).
        _selected_ids preserves selections across page changes."""
        self._selected_ids.clear()
        for ctrl in self._panel_controls:
            self._selected_ids.add(ctrl.sample_id)
            ctrl.set_selected(True)

    def _on_deselect_all(self):
        self._selected_ids.clear()
        for ctrl in self._panel_controls:
            ctrl.set_selected(False)

    # ------------------------------------------------------------------
    # Mass operations
    # ------------------------------------------------------------------

    async def _on_mass_outlier(self):
        sids = list(self._selected_ids)
        if not sids:
            show_snack(self.page, "No samples selected", ft.Colors.ORANGE_400)
            self.page.update()
            return

        selected_samples = [s for s in self._samples if s.id in sids]
        all_outliers = all(s.outlier for s in selected_samples)
        new_outlier = not all_outliers

        count = 0
        for sample in selected_samples:
            sample.outlier = new_outlier
            await self.project.update_sample(sample)
            count += 1

        await self.project.save()

        for sid in sids:
            await self._refresh_single_stats_in_place(sid)

        label = "set" if new_outlier else "cleared"
        show_snack(self.page, f"Outlier {label} for {count} sample(s)", ft.Colors.GREEN_400)
        self.page.update()

    async def _on_mass_drop_file(self):
        from .dialogs.drop_file_dialog import DropFileDialog
        sids = list(self._selected_ids)
        dialog = DropFileDialog(
            project=self.project,
            page=self.page,
            selected_sample_ids=sids,
            on_complete=self._on_mass_op_complete,
        )
        await dialog.show()

    async def _on_mass_assign_subset(self):
        from .dialogs.assign_subset_dialog import AssignSubsetDialog
        sids = list(self._selected_ids)
        dialog = AssignSubsetDialog(
            project=self.project,
            page=self.page,
            selected_sample_ids=sids,
            on_complete=self._on_mass_op_complete,
        )
        await dialog.show()

    async def _on_mass_delete(self):
        sids = list(self._selected_ids)
        if not sids:
            show_snack(self.page, "No samples selected", ft.Colors.ORANGE_400)
            self.page.update()
            return

        samples_to_delete = [s for s in self._samples if s.id in sids]

        name_rows = []
        for s in samples_to_delete:
            name_rows.append(
                ft.Container(
                    content=ft.Text(f"• {s.name}", size=13),
                    padding=ft.padding.symmetric(vertical=1),
                )
            )

        name_list = ft.Container(
            content=ft.ListView(controls=name_rows, spacing=1, height=150),
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=5,
            padding=10,
        )

        confirmed = False
        event = asyncio.Event()

        async def on_delete(e):
            nonlocal confirmed
            confirmed = True
            dlg.open = False
            self.page.update()
            event.set()

        def on_cancel(e):
            dlg.open = False
            self.page.update()
            event.set()

        dlg = ft.AlertDialog(
            title=ft.Text("Delete samples?"),
            content=ft.Column([
                ft.Text("The following samples will be deleted:", size=13),
                name_list,
                ft.Text(
                    "All spectra, identifications and peptide matches will be permanently removed.",
                    size=12, color=ft.Colors.RED_600,
                ),
            ], tight=True, width=400),
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel),
                ft.ElevatedButton(
                    content=ft.Text("Delete"),
                    style=ft.ButtonStyle(bgcolor=ft.Colors.RED_600, color=ft.Colors.WHITE),
                    on_click=lambda e: e.page.run_task(on_delete, e),
                ),
            ],
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()
        await event.wait()

        if not confirmed:
            return

        count = 0
        for sid in sids:
            try:
                await self.project.delete_sample(sid)
                count += 1
            except Exception as ex:
                logger.exception(f"Error deleting sample id={sid}: {ex}")

        self._samples = [s for s in self._samples if s.id not in sids]
        self._all_stats = {sid: st for sid, st in self._all_stats.items() if sid not in sids}
        self._selected_ids.clear()
        await self._recompute_filtered()
        show_snack(self.page, f"Deleted {count} sample(s)", ft.Colors.GREEN_400)
        self.page.update()

    async def _on_drop_empty_files(self):
        try:
            deleted_spectra, deleted_idents = await self._data_manager.drop_empty_files()
            if deleted_spectra == 0 and deleted_idents == 0:
                show_snack(self.page, "No empty files found", ft.Colors.ORANGE_400)
            else:
                show_snack(
                    self.page,
                    f"Removed {deleted_spectra} spectra file(s) and {deleted_idents} identification file(s)",
                    ft.Colors.GREEN_400,
                )
            await self._on_mass_op_complete()
        except Exception as ex:
            logger.exception("Error dropping empty files")
            show_snack(self.page, f"Error: {ex}", ft.Colors.RED_400)
            self.page.update()

    async def _on_mass_op_complete(self):
        """Reload data and rebuild panels after a mass operation."""
        self._samples, self._all_stats, self._tools_count = await self._data_manager.load_all()
        await self._recompute_filtered()

    # ------------------------------------------------------------------
    # Rebuild panels from page
    # ------------------------------------------------------------------

    async def _rebuild_panels_from_page(self):
        """Build ExpansionPanel controls only for self._page_samples."""
        if self._panels_list is None:
            return
        min_proteins, min_idents = self._update_row.get_thresholds()
        self._panels_list.controls.clear()
        self._panel_index.clear()
        self._panel_controls.clear()

        if not self._page_samples:
            self._panels_list.controls.append(
                ft.ExpansionPanel(
                    header=ft.ListTile(
                        title=ft.Text(
                            "No samples match the current filters.",
                            color=ft.Colors.GREY_600, italic=True,
                        )
                    ),
                    content=ft.Container(),
                    can_tap_header=False,
                )
            )
        else:
            for idx, sample in enumerate(self._page_samples):
                sid = int(sample.id or 0)
                stats = self._all_stats.get(sid) or {}
                panel_ctrl = SampleViewPanel(
                    sample=sample,
                    stats=stats,
                    tools_count=self._tools_count,
                    min_proteins=min_proteins,
                    min_idents=min_idents,
                    on_action=self._on_panel_action,
                    on_selection_changed=self._on_selection_changed,
                )
                panel = await panel_ctrl.build()
                self._panel_index[sid] = idx
                self._panel_controls.append(panel_ctrl)
                self._panels_list.controls.append(panel)

        if self._panels_list.page:
            self._panels_list.update()

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
            self._all_stats = {sid: st for sid, st in self._all_stats.items() if sid != sample.id}
            await self._recompute_filtered()
        except Exception as ex:
            self._show_error(f"Error: {ex}")

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
    # Settings getters
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
    # Confirm dialog
    # ------------------------------------------------------------------

    async def _confirm(self, title: str, message: str) -> bool:
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
