"""Combined table and plot view."""

import flet as ft

from dasmixer.api.project.project import Project
from dasmixer.gui.components.base_table_view import BaseTableView
from dasmixer.gui.components.base_plot_view import BasePlotView


class BaseTableAndPlotView(ft.Container):
    """
    Combines table and plot views in a single layout.
    
    Automatically connects table's plot callback to plot view.
    """
    
    def __init__(
        self,
        project: Project,
        table_view: BaseTableView,
        plot_view: BasePlotView,
        title: str = "Data & Plot"
    ):
        super().__init__()
        self.project = project
        self.table_view = table_view
        self.plot_view = plot_view
        self.title = title
        
        # Connect table to plot
        self.table_view.plot_callback = self.plot_view.on_plot_requested
        
        # Build UI
        self.content = self._build_ui()
        self.padding = 10
        self.expand = True
    
    def _build_ui(self) -> ft.Control:
        """Build combined layout."""
        return ft.Column([
            ft.Text(self.title, size=18, weight=ft.FontWeight.BOLD),
            ft.Container(height=10),
            
            # Table
            self.table_view,
            
            ft.Container(height=20),
            ft.Divider(height=2, color=ft.Colors.GREY_400),
            ft.Container(height=20),
            
            # Plot
            self.plot_view
        ], spacing=0, expand=True, scroll=ft.ScrollMode.AUTO)
    
    async def load_data(self):
        """Load data for both table and plot."""
        await self.table_view.load_data()
        await self.plot_view.load_data()
