"""Lightweight summary of samples — replaces the heavy ExpansionPanelList on the tab."""

import flet as ft

from dasmixer.api.project.project import Project
from .base_section import BaseSection
from .shared_state import SamplesTabState


class SamplesSummarySection(BaseSection):
    """
    Shows total samples count + OK / Warning / Error breakdown from cache.
    Heavy per-sample management is opened via "Manage Samples" → ft.View /samples.

    No ExpansionPanelList here — this section loads in O(1) (single aggregated query).
    """

    def __init__(self, project: Project, state: SamplesTabState, parent_tab):
        self._total_text: ft.Text | None = None
        self._ok_chip: ft.Chip | None = None
        self._warn_chip: ft.Chip | None = None
        self._err_chip: ft.Chip | None = None
        self._uncached_chip: ft.Chip | None = None
        self._manage_btn: ft.ElevatedButton | None = None
        super().__init__(project, state, parent_tab)

    # ------------------------------------------------------------------
    # Build skeleton (no data yet)
    # ------------------------------------------------------------------

    def _build_content(self) -> ft.Control:
        self._total_text = ft.Text(
            "Samples: —",
            size=18,
            weight=ft.FontWeight.BOLD,
        )

        def _chip(icon, color, label, tooltip):
            return ft.Chip(
                label=ft.Text(label, size=12),
                leading=ft.Icon(icon, color=color, size=16),
                bgcolor=ft.Colors.with_opacity(0.08, color),
                padding=ft.padding.symmetric(horizontal=6, vertical=2),
                disabled_color=ft.Colors.TRANSPARENT,
                tooltip=tooltip,
            )

        self._ok_chip   = _chip(ft.Icons.CHECK_CIRCLE_OUTLINE, ft.Colors.GREEN_600,  "— OK",      "Samples with all data complete")
        self._warn_chip = _chip(ft.Icons.WARNING_AMBER_OUTLINED, ft.Colors.AMBER_600, "— Warning", "Samples with incomplete data")
        self._err_chip  = _chip(ft.Icons.ERROR_OUTLINE, ft.Colors.RED_600,  "— Error",   "Samples missing spectra or identification files")
        self._uncached_chip = _chip(ft.Icons.HOURGLASS_EMPTY, ft.Colors.GREY_500, "— Pending", "Samples with no cached stats yet")

        self._manage_btn = ft.ElevatedButton(
            content=ft.Text("Manage Samples"),
            icon=ft.Icons.MANAGE_ACCOUNTS,
            on_click=self._on_manage_clicked,
        )

        return ft.Column(
            [
                ft.Text("Samples", size=18, weight=ft.FontWeight.BOLD),
                ft.Row(
                    [
                        self._total_text,
                        ft.Container(width=12),
                        self._ok_chip,
                        self._warn_chip,
                        self._err_chip,
                        self._uncached_chip,
                        ft.Container(expand=True),
                        self._manage_btn,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=6,
                ),
            ],
            spacing=8,
        )

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    async def load_data(self):
        """Load summary counters from cache — single aggregate query."""
        summary = await self.project.get_sample_status_summary()
        self._apply_summary(summary)
        self.state.samples_count = summary['total']

    def _apply_summary(self, s: dict):
        total = s.get('total', 0)
        ok    = s.get('ok', 0)
        warn  = s.get('warning', 0)
        err   = s.get('error', 0)
        unc   = s.get('uncached', 0)

        if self._total_text:
            self._total_text.value = f"Samples: {total}"

        def _lbl(chip, n, suffix):
            if chip:
                chip.label = ft.Text(f"{n} {suffix}", size=12)
                chip.visible = n > 0

        _lbl(self._ok_chip,       ok,   "OK")
        _lbl(self._warn_chip,     warn, "Warning")
        _lbl(self._err_chip,      err,  "Error")
        _lbl(self._uncached_chip, unc,  "Pending")

        if self.page:
            for ctrl in [self._total_text, self._ok_chip, self._warn_chip,
                         self._err_chip, self._uncached_chip]:
                if ctrl and ctrl.page:
                    ctrl.update()

    # ------------------------------------------------------------------
    # Navigation to ManageSamplesView
    # ------------------------------------------------------------------

    def _on_manage_clicked(self, e):
        """Push /samples view onto the page view stack."""
        if self.page:
            self.page.run_task(self._navigate_to_manage)

    async def _navigate_to_manage(self):
        from dasmixer.gui.views.manage_samples_view import ManageSamplesView

        view = ManageSamplesView(
            project=self.project,
            on_back=self._on_back_from_manage,
        )
        self.page.views.append(view)
        self.page.route = "/samples"
        self.page.update()

    async def _on_back_from_manage(self):
        """Called when ManageSamplesView navigates back. Refresh summary."""
        # Pop the /samples view if it's still on top
        if len(self.page.views) > 1 and getattr(self.page.views[-1], 'route', None) == "/samples":
            self.page.views.pop()
        self.page.route = "/project"
        self.page.update()
        # Refresh counters (cache may have been updated inside ManageSamplesView)
        await self.load_data()
