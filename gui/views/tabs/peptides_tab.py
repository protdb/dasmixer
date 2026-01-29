"""Peptides tab - view identifications and ion matches."""

import flet as ft
from api.project.project import Project


class PeptidesTab(ft.UserControl):
    """
    Peptides tab for:
    - Searching identifications
    - Viewing identification results
    - Displaying ion match visualizations
    """
    
    def __init__(self, project: Project):
        super().__init__()
        self.project = project
    
    def build(self):
        """Build the tab content."""
        # Search section
        search_section = ft.Container(
            content=ft.Column([
                ft.Text("Search Identifications", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.Dropdown(
                        label="Search by",
                        options=[
                            ft.dropdown.Option("seq_no", "Sequence Number"),
                            ft.dropdown.Option("scans", "Scans"),
                            ft.dropdown.Option("canonical_sequence", "Sequence")
                        ],
                        value="seq_no",
                        width=200
                    ),
                    ft.TextField(
                        label="Search value",
                        expand=True
                    ),
                    ft.Dropdown(
                        label="Sample",
                        options=[ft.dropdown.Option("all", "All Samples")],
                        value="all",
                        width=200
                    ),
                    ft.ElevatedButton(
                        "Search",
                        icon=ft.icons.SEARCH,
                        on_click=self.search_identifications
                    )
                ], spacing=10)
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=10
        )
        
        # Results section (placeholder)
        results_section = ft.Container(
            content=ft.Column([
                ft.Text("Results", size=18, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "No search performed yet",
                    italic=True,
                    color=ft.colors.ON_SURFACE_VARIANT
                )
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=10,
            expand=True
        )
        
        # Ion match visualization section (placeholder)
        visualization_section = ft.Container(
            content=ft.Column([
                ft.Text("Ion Match Visualization", size=18, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "Select an identification to view ion match",
                    italic=True,
                    color=ft.colors.ON_SURFACE_VARIANT
                )
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.colors.OUTLINE),
            border_radius=10
        )
        
        # Main layout
        return ft.Container(
            content=ft.Column([
                search_section,
                ft.Container(height=10),
                results_section,
                ft.Container(height=10),
                visualization_section
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            expand=True
            ),
            padding=20,
            expand=True
        )
    
    def search_identifications(self, e):
        """Search for identifications."""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("Search functionality coming soon. Import identifications first."),
            bgcolor=ft.colors.BLUE_400
        )
        self.page.snack_bar.open = True
        self.page.update()
