"""SampleViewPanel — a single sample panel with checkbox, header and body."""

import json
from pathlib import Path
from typing import Callable, Awaitable

import flet as ft

from dasmixer.api.project.dataclasses import Sample


def _empty_stats() -> dict:
    return {
        'spectra_files_count': 0, 'ident_files_count': 0,
        'identifications_count': 0, 'preferred_count': 0,
        'coverage_known_count': 0, 'protein_ids_count': 0,
        'empty_ident_files_count': 0,
    }


def compute_sample_status(stats: dict, tools_count: int, min_proteins: int, min_idents: int) -> str:
    """Return 'OK' | 'WARNING' | 'ERROR' for a sample given its stats and thresholds."""
    sf_count = stats.get('spectra_files_count', 0)
    if_count = stats.get('ident_files_count', 0)
    idents = stats.get('identifications_count', 0)
    proteins = stats.get('protein_ids_count', 0)
    empty_if = stats.get('empty_ident_files_count', 0)

    has_spectra = sf_count > 0
    has_ident = if_count > 0
    expected_if = tools_count * sf_count if sf_count > 0 else 0
    ident_ok = (expected_if == 0) or (if_count == expected_if)
    idents_ok = idents >= min_idents
    proteins_ok = (proteins == 0) or (proteins >= min_proteins)

    if not has_spectra or (has_spectra and not has_ident):
        return 'ERROR'
    elif has_spectra and has_ident and ident_ok and idents_ok and proteins_ok and empty_if == 0:
        return 'OK'
    else:
        return 'WARNING'


def _build_sample_header(
    sample: Sample,
    stats: dict,
    tools_count: int,
    min_proteins: int,
    min_idents: int,
    any_has_additionals: bool = False,
) -> ft.Control:
    sf_count = stats.get('spectra_files_count', 0)
    if_count = stats.get('ident_files_count', 0)
    idents = stats.get('identifications_count', 0)
    preferred = stats.get('preferred_count', 0)
    coverage = stats.get('coverage_known_count', 0)
    proteins = stats.get('protein_ids_count', 0)
    empty_if = stats.get('empty_ident_files_count', 0)

    status = compute_sample_status(stats, tools_count, min_proteins, min_idents)
    if status == 'ERROR':
        marker_icon, marker_color = ft.Icons.ERROR_OUTLINE_OUTLINED, ft.Colors.RED_600
    elif status == 'OK':
        marker_icon, marker_color = ft.Icons.CHECK_CIRCLE_OUTLINE_OUTLINED, ft.Colors.GREEN_600
    else:
        marker_icon, marker_color = ft.Icons.WARNING_AMBER_OUTLINED, ft.Colors.AMBER_600

    has_ident = if_count > 0
    expected_if = tools_count * sf_count if sf_count > 0 else 0
    ident_ok = (expected_if == 0) or (if_count == expected_if)
    idents_ok = idents >= min_idents
    proteins_ok = (proteins == 0) or (proteins >= min_proteins)

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

    # Additionals indicator
    additionals = sample.additions
    has_additionals = bool(additionals)
    add_symbol = "☑" if has_additionals else "☐"
    add_color = ft.Colors.GREY_800
    if any_has_additionals and not has_additionals:
        add_color = ft.Colors.AMBER_600  # warning: others have, this one doesn't
    controls.append(ft.Text(f"Add: {add_symbol}", size=11, color=add_color))

    return ft.Row(controls, spacing=6, wrap=False)


class SampleViewPanel(ft.Container):
    """Panel representing a single sample with checkbox, header and body."""

    def __init__(
        self,
        sample: Sample,
        stats: dict,
        tools_count: int,
        min_proteins: int,
        min_idents: int,
        on_action: Callable,
        on_selection_changed: Callable[[int, bool], None] | None = None,
        any_has_additionals: bool = False,
    ):
        super().__init__()
        self._sample = sample
        self._stats = stats
        self._tools_count = tools_count
        self._min_proteins = min_proteins
        self._min_idents = min_idents
        self._on_action = on_action
        self._on_selection_changed = on_selection_changed
        self._any_has_additionals = any_has_additionals

        self._checkbox = ft.Checkbox(
            value=False,
            on_change=self._on_checkbox_change,
        )
        self._expansion_panel: ft.ExpansionPanel | None = None

        # Lazy loading state
        self._body_cache: ft.Control | None = None
        self._detail_cache: list[dict] | None = None
        self._is_expanded: bool = False

    @property
    def sample_id(self) -> int:
        return int(self._sample.id or 0)

    @property
    def is_selected(self) -> bool:
        return self._checkbox.value

    def set_selected(self, value: bool) -> None:
        self._checkbox.value = value
        if self._checkbox.page:
            self._checkbox.update()

    def _on_checkbox_change(self, e):
        if self._on_selection_changed:
            self._on_selection_changed(self.sample_id, self._checkbox.value)

    async def build(self) -> ft.ExpansionPanel:
        """Build the ExpansionPanel for this sample (header only, body loaded lazily)."""
        header_row = ft.Row(
            [self._checkbox],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        header_row.controls.append(
            _build_sample_header(
                self._sample, self._stats,
                self._tools_count, self._min_proteins, self._min_idents,
                self._any_has_additionals,
            )
        )

        self._expansion_panel = ft.ExpansionPanel(
            header=ft.ListTile(title=header_row),
            content=ft.Container(
                content=self._collapsed_placeholder(),
                padding=ft.padding.only(left=16, right=16, bottom=16),
            ),
            expanded=False,
            can_tap_header=True,
        )
        return self._expansion_panel

    def update_stats(self, stats: dict, min_proteins: int, min_idents: int, any_has_additionals: bool = False) -> None:
        """Update statistics and thresholds for the panel."""
        self._stats = stats
        self._min_proteins = min_proteins
        self._min_idents = min_idents
        self._any_has_additionals = any_has_additionals

    def _collapsed_placeholder(self) -> ft.Control:
        """Lightweight placeholder shown while the panel is collapsed."""
        return ft.Container(height=0)

    async def on_expand(self) -> None:
        """Called by ManageSamplesView when this panel becomes expanded.
        Builds the body lazily, using cached detail data if available."""
        if self._is_expanded:
            return
        self._is_expanded = True
        if self._body_cache is None:
            self._body_cache = await self._build_body()
        self._expansion_panel.content.content = self._body_cache
        self._expansion_panel.expanded = True
        if self._expansion_panel.page:
            self._expansion_panel.update()

    def on_collapse(self) -> None:
        """Called by ManageSamplesView when this panel becomes collapsed.
        Removes the body controls from the Flet tree while keeping
        self._body_cache / self._detail_cache in memory for instant reopen."""
        if not self._is_expanded:
            return
        self._is_expanded = False
        self._expansion_panel.content.content = self._collapsed_placeholder()
        self._expansion_panel.expanded = False
        if self._expansion_panel.page:
            self._expansion_panel.update()

    def invalidate_detail_cache(self) -> None:
        """Call after any operation that changes this sample's file tree,
        so the next expand re-fetches fresh detail data."""
        self._detail_cache = None
        self._body_cache = None

    async def _build_body(self) -> ft.Control:
        if self._detail_cache is None:
            self._detail_cache = await self._on_action('get_detail', self._sample.id)
        detail = self._detail_cache
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
                        on_click=lambda e, _sf_id=sf_id: e.page.run_task(
                            self._on_action, 'add_ident_file', _sf_id, self._sample
                        ),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE_OUTLINE,
                        icon_color=ft.Colors.RED_400,
                        tooltip="Delete spectra file",
                        on_click=lambda e, _sf_id=sf_id: e.page.run_task(
                            self._on_action, 'delete_spectra_file', _sf_id, self._sample
                        ),
                    ),
                ], spacing=4)
                body_controls.append(spectra_row)

                for ident_file in sf.get('ident_files', []):
                    if_id = int(ident_file['id'])
                    count = int(ident_file.get('ident_count', 0))
                    is_empty = count == 0
                    is_below = 0 < count < self._min_idents
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
                                on_click=lambda e, _if_id=if_id: e.page.run_task(
                                    self._on_action, 'delete_ident_file', _if_id, self._sample
                                ),
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
                on_click=lambda e: e.page.run_task(
                    self._on_action, 'add_spectra_file', self._sample
                ),
            )
        )
        body_controls.append(ft.Divider(height=8))

        if self._sample.additions:
            try:
                additions_text = json.dumps(self._sample.additions, indent=2, ensure_ascii=False)
            except Exception:
                additions_text = str(self._sample.additions)
            body_controls.append(
                ft.Text(f"Additions:\n{additions_text}", size=11, color=ft.Colors.GREY_700,
                        font_family="monospace")
            )
            body_controls.append(ft.Container(height=6))

        # Action buttons
        sample = self._sample
        left_buttons = ft.Row([
            ft.ElevatedButton(content=ft.Text("Calculate ions"), icon=ft.Icons.BOLT,
                on_click=lambda e, s=sample: e.page.run_task(self._on_action, 'calculate_ions', s)),
            ft.ElevatedButton(content=ft.Text("Select preferred"), icon=ft.Icons.STAR_OUTLINE,
                on_click=lambda e, s=sample: e.page.run_task(self._on_action, 'select_preferred', s)),
            ft.ElevatedButton(content=ft.Text("Match proteins"), icon=ft.Icons.LINK,
                on_click=lambda e, s=sample: e.page.run_task(self._on_action, 'match_proteins', s)),
            ft.ElevatedButton(content=ft.Text("Protein Identifications"), icon=ft.Icons.BIOTECH,
                on_click=lambda e, s=sample: e.page.run_task(self._on_action, 'protein_identifications', s)),
            ft.ElevatedButton(content=ft.Text("LFQ"), icon=ft.Icons.ANALYTICS,
                on_click=lambda e, s=sample: e.page.run_task(self._on_action, 'lfq', s)),
        ], spacing=6, wrap=True)

        right_buttons = ft.Row([
            ft.ElevatedButton(
                content=ft.Row([ft.Icon(ft.Icons.EDIT_OUTLINED, size=20)], spacing=4, tight=True),
                tooltip="Edit sample properties",
                on_click=lambda e, s=sample: e.page.run_task(self._on_action, 'edit_sample', s),
            ),
            ft.ElevatedButton(
                content=ft.Row([
                    ft.Icon(ft.Icons.FLAG if sample.outlier else ft.Icons.FLAG_OUTLINED, size=20,
                            color=ft.Colors.RED_500 if sample.outlier else None),
                ], spacing=4, tight=True),
                tooltip="Toggle outlier mark",
                on_click=lambda e, s=sample: e.page.run_task(self._on_action, 'toggle_outlier', s),
            ),
            ft.ElevatedButton(
                content=ft.Row([
                    ft.Icon(ft.Icons.DELETE_OUTLINED, size=20, color=ft.Colors.RED_600),
                ], spacing=4, tight=True),
                tooltip="Delete sample",
                on_click=lambda e, s=sample: e.page.run_task(self._on_action, 'delete_sample', s),
            ),
        ], spacing=6)

        body_controls.append(ft.Row([left_buttons, ft.Container(expand=True), right_buttons]))
        return ft.Column(body_controls, spacing=6)
