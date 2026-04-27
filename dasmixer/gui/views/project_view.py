"""Project view - main workspace with tabs (lazy-loaded, suspend/resume on switch)."""

import flet as ft
from dasmixer.api.project.project import Project


# Tab definitions: (label, icon, factory_import_path, factory_class_name)
_TAB_DEFS = [
    ("Samples",  ft.Icons.SCIENCE,       "dasmixer.gui.views.tabs.samples",  "SamplesTab"),
    ("Peptides", ft.Icons.BIOTECH,       "dasmixer.gui.views.tabs.peptides", "PeptidesTab"),
    ("Proteins", ft.Icons.BUBBLE_CHART,  "dasmixer.gui.views.tabs.proteins", "ProteinsTab"),
    ("Reports",  ft.Icons.ASSESSMENT,    "dasmixer.gui.views.tabs.reports",  "ReportsTab"),
    ("Plots",    ft.Icons.SHOW_CHART,    "dasmixer.gui.views.tabs.plots",    "PlotsTab"),
    ("Export",   ft.Icons.DOWNLOAD,      "dasmixer.gui.views.tabs.export.export_tab",  "ExportTab"),
]

# Tabs whose heavy table/plot widgets should be suspended on switch-away.
# (Peptides and Proteins both contain DataTables and PlotlyViewer instances.)
_SUSPENDABLE_TAB_INDICES = {1, 2}  # Peptides=1, Proteins=2


def _make_placeholder() -> ft.Control:
    """Lightweight placeholder shown before a tab is built."""
    return ft.Container(
        content=ft.Column(
            [ft.ProgressRing(width=32, height=32, stroke_width=3)],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        expand=True,
        alignment=ft.Alignment.CENTER,
    )


def _collect_suspendable(control) -> list:
    """
    Recursively collect all suspendable instances in a control subtree.
    A control is suspendable if it has both suspend() and resume() methods
    and custom marker attribute.
    """
    from dasmixer.gui.components.base_table_view import BaseTableView
    from dasmixer.gui.components.base_plot_view import BasePlotView

    found = []
    
    # Check if this control is our custom suspendable widget
    # A control is our custom suspendable if it has our marker attribute
    is_custom_suspendable = (
        hasattr(control, '_is_suspended') or
        hasattr(control, '_tool_settings_suspended')
    )
    if is_custom_suspendable and hasattr(control, 'suspend') and hasattr(control, 'resume'):
        found.append(control)
        # Skip BaseTableView/BasePlotView check if already added
    else:
        # Also keep original BaseTableView/BasePlotView detection for backward compatibility
        if isinstance(control, (BaseTableView, BasePlotView)):
            found.append(control)

    # Traverse known container attributes
    for attr in ('controls', 'content'):
        child = getattr(control, attr, None)
        if child is None:
            continue
        if isinstance(child, list):
            for c in child:
                found.extend(_collect_suspendable(c))
        elif hasattr(child, '__class__') and not isinstance(child, str):
            found.extend(_collect_suspendable(child))

    # Also check .sections dict (PeptidesTab, ProteinsTab pattern)
    sections = getattr(control, 'sections', None)
    if isinstance(sections, dict):
        for sec in sections.values():
            found.extend(_collect_suspendable(sec))

    # BaseTableAndPlotView wires table_view and plot_view directly
    for attr in ('table_view', 'plot_view',
                 'identifications_table', 'statistics_table', 'protein_plot'):
        child = getattr(control, attr, None)
        if child is not None:
            found.extend(_collect_suspendable(child))

    return found


class ProjectView(ft.Container):
    """
    Main project workspace with tabs.

    Tabs are lazily instantiated: only the first (Samples) tab is built on
    construction; every other tab is built the first time it is selected.

    When switching away from a "heavy" tab (Peptides, Proteins) all
    BaseTableView / BasePlotView instances inside it are suspended —
    their rendered controls are replaced with lightweight placeholders so
    Flet's reconciliation loop doesn't have to diff thousands of cells.
    On returning, they are resumed from cached data without any DB query.
    """

    def __init__(self, project: Project, on_close):
        super().__init__()
        self.project = project
        self.on_close = on_close

        # Track which tab indices have been built already.
        self._built: dict[int, bool] = {}
        # Actual tab content controls (parallel to _TAB_DEFS).
        self._tab_controls: list[ft.Control] = []
        # Currently active tab index
        self._active_index: int = 0

        self.content = self._build_content()
        self.expand = True
        self.padding = 0

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_content(self) -> ft.Control:
        n = len(_TAB_DEFS)

        # Fill with placeholders initially.
        self._tab_controls = [_make_placeholder() for _ in range(n)]

        # Build first tab immediately so the user sees something at once.
        self._build_tab(0)

        tabs = [
            ft.Tab(label=ft.Text(label), icon=icon)
            for label, icon, _, _ in _TAB_DEFS
        ]

        self._tabs_widget = ft.Tabs(
            selected_index=0,
            length=n,
            expand=True,
            on_change=self._on_tab_change,
            content=ft.Column(
                expand=True,
                controls=[
                    ft.TabBar(tabs=tabs),
                    ft.TabBarView(
                        expand=True,
                        controls=self._tab_controls,
                    ),
                ],
            ),
        )

        return self._tabs_widget

    # ------------------------------------------------------------------
    # Lazy tab factory
    # ------------------------------------------------------------------

    def _build_tab(self, index: int) -> None:
        """Instantiate the real tab control for *index* and replace placeholder."""
        if self._built.get(index):
            return

        label, _icon, module_path, class_name = _TAB_DEFS[index]
        print(f"[ProjectView] building tab {index}: {label}")

        import importlib
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        control = cls(self.project)

        self._tab_controls[index] = control
        self._built[index] = True

        # If the TabBarView is already mounted, patch it in-place.
        tabbar_view = self._get_tabbar_view()
        if tabbar_view is not None:
            tabbar_view.controls[index] = control
            if tabbar_view.page:
                tabbar_view.update()

    def _get_tabbar_view(self) -> ft.TabBarView | None:
        """Navigate the widget tree to find the TabBarView."""
        try:
            col: ft.Column = self._tabs_widget.content
            return col.controls[1]
        except (AttributeError, IndexError):
            return None

    # ------------------------------------------------------------------
    # Tab switch handler  — suspend old, build/resume new
    # ------------------------------------------------------------------

    def _on_tab_change(self, e):
        new_index = int(e.control.selected_index)
        old_index = self._active_index
        self._active_index = new_index

        # Suspend heavy widgets in the tab we're leaving
        if old_index in _SUSPENDABLE_TAB_INDICES and self._built.get(old_index):
            old_control = self._tab_controls[old_index]
            
            # For PeptidesTab: save tool settings before suspend
            if old_index == 1:  # Peptides tab index = 1
                tool_section = getattr(old_control, 'sections', {}).get('tool_settings')
                if tool_section and hasattr(tool_section, 'save_all_tool_settings'):
                    # Schedule async save (fire and forget)
                    # Use page.run_task() if available, otherwise ignore
                    # Tool settings will be saved on next explicit save action
                    try:
                        if self.page and hasattr(self.page, 'run_task'):
                            self.page.run_task(tool_section.save_all_tool_settings)
                    except (AttributeError, TypeError):
                        # page might not have run_task or might be None
                        pass
            
            for widget in _collect_suspendable(old_control):
                widget.suspend()

        # Build the new tab if not yet instantiated
        if not self._built.get(new_index):
            self._build_tab(new_index)
            return  # did_mount will handle the initial load — no resume needed

        # Resume heavy widgets in the tab we're entering
        if new_index in _SUSPENDABLE_TAB_INDICES:
            new_control = self._tab_controls[new_index]
            for widget in _collect_suspendable(new_control):
                widget.resume()

        # A single page.update() to flush all suspend/resume changes at once
        if self.page:
            self.page.update()
