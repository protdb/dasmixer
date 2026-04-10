"""Project view - main workspace with tabs."""

import flet as ft
from dasmixer.api.project.project import Project


class ProjectView(ft.Container):
    """
    Main project workspace with tabs.
    
    Tabs:
    - Samples: Manage samples, groups, import data
    - Peptides: View identifications, ion matches
    - Proteins: Protein identifications
    - Reports: Generate and view reports
    - Plots: Manage saved plots
    """
    
    def __init__(self, project: Project, on_close):
        """
        Initialize project view.
        
        Args:
            project: Active Project instance
            on_close: Callback for closing project
        """
        super().__init__()
        self.project = project
        self.on_close = on_close
        
        # Build content
        self.content = self._build_content()
        self.expand = True
        self.padding = 0
    
    def _build_content(self):
        """Build the view."""
        # Import tab views
        from dasmixer.gui.views.tabs.samples import SamplesTab
        from dasmixer.gui.views.tabs.peptides import PeptidesTab
        from dasmixer.gui.views.tabs.proteins import ProteinsTab
        from dasmixer.gui.views.tabs.reports import ReportsTab
        from dasmixer.gui.views.tabs.plots import PlotsTab


        # Create tabs using new Flet API
        print("building tabs...")

        tabs_list = [
            (ft.Tab(label=ft.Text("Samples"), icon=ft.Icons.SCIENCE), SamplesTab(self.project)),
            (ft.Tab(label=ft.Text("Peptides"), icon=ft.Icons.BIOTECH), PeptidesTab(self.project)),
            (ft.Tab(label=ft.Text("Proteins"), icon=ft.Icons.BUBBLE_CHART), ProteinsTab(self.project)),
            (ft.Tab(label=ft.Text("Reports"), icon=ft.Icons.ASSESSMENT), ReportsTab(self.project)),
            # (ft.Tab(label=ft.Text("Plots"), icon=ft.Icons.SHOW_CHART), PlotsTab(self.project)),
        ]

        tabs = ft.Tabs(
            selected_index=0,
            length=len(tabs_list),  # Number of tabs
            expand=True,
            content=ft.Column(
                expand=True,
                controls=[
                    ft.TabBar(
                        tabs=[x[0] for x in tabs_list],
                    ),
                    ft.TabBarView(
                        expand=True,
                        controls=[x[1] for x in tabs_list],
                    ),
                ],
            ),
        )


        
        return tabs
