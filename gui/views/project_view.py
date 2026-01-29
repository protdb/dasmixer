"""Project view - main workspace with tabs."""

import flet as ft
from api.project.project import Project


class ProjectView(ft.UserControl):
    """
    Main project workspace with tabs.
    
    Tabs:
    - Samples: Manage samples, groups, import data
    - Peptides: View identifications, ion matches
    - Proteins: Protein identifications (stub)
    - Analysis: Comparative analysis (stub)
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
    
    def build(self):
        """Build the view."""
        # Import tab views
        from gui.views.tabs.samples_tab import SamplesTab
        from gui.views.tabs.peptides_tab import PeptidesTab
        from gui.views.tabs.proteins_tab import ProteinsTab
        from gui.views.tabs.analysis_tab import AnalysisTab
        
        # Create tabs
        tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            tabs=[
                ft.Tab(
                    text="Samples",
                    icon=ft.icons.SCIENCE,
                    content=SamplesTab(self.project)
                ),
                ft.Tab(
                    text="Peptides",
                    icon=ft.icons.BIOTECH,
                    content=PeptidesTab(self.project)
                ),
                ft.Tab(
                    text="Proteins",
                    icon=ft.icons.BUBBLE_CHART,
                    content=ProteinsTab(self.project)
                ),
                ft.Tab(
                    text="Analysis",
                    icon=ft.icons.ANALYTICS,
                    content=AnalysisTab(self.project)
                ),
            ],
            expand=True
        )
        
        return ft.Container(
            content=tabs,
            expand=True,
            padding=0
        )
