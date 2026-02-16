"""Project view - main workspace with tabs."""

import flet as ft
from api.project.project import Project


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
        from gui.views.tabs.samples import SamplesTab
        from gui.views.tabs.peptides import PeptidesTab
        from gui.views.tabs.proteins import ProteinsTab
        from gui.views.tabs.reports import ReportsTab
        from gui.views.tabs.plots import PlotsTab
        
        # Create tabs using new Flet API
        print("building tabs...")
        tabs = ft.Tabs(
            selected_index=0,
            length=3,  # Number of tabs (added Plots)
            expand=True,
            content=ft.Column(
                expand=True,
                controls=[
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label="Samples", icon=ft.Icons.SCIENCE),
                            ft.Tab(label="Peptides", icon=ft.Icons.BIOTECH),
                            # ft.Tab(label="Proteins", icon=ft.Icons.BUBBLE_CHART),
                            ft.Tab(label="Reports", icon=ft.Icons.ASSESSMENT),
                            # ft.Tab(label="Plots", icon=ft.Icons.SHOW_CHART),
                        ]
                    ),
                    ft.TabBarView(
                        expand=True,
                        controls=[
                            SamplesTab(self.project),
                            PeptidesTab(self.project),
                            # ProteinsTab(self.project),
                            ReportsTab(self.project),
                            # PlotsTab(self.project),
                        ],
                    ),
                ],
            ),
        )
        
        return tabs
