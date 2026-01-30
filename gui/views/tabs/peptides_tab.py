"""Peptides tab - view identifications and ion matches."""

import flet as ft
from api.project.project import Project


class PeptidesTab(ft.Container):
    """
    Peptides tab for:
    - Searching identifications
    - Viewing identification results
    - Displaying ion match visualizations
    """
    
    def __init__(self, project: Project):
        super().__init__()
        self.project = project
        
        # Build content
        self.content = self._build_content()
        self.padding = 20
        self.expand = True
    
    def _build_content(self):
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
                        content=ft.Text("Search"),
                        icon=ft.Icons.SEARCH,
                        on_click=self.search_identifications
                    )
                ], spacing=10)
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY),
            border_radius=10
        )
        
        # Results section (placeholder)
        results_section = ft.Container(
            content=ft.Column([
                ft.Text("Results", size=18, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "No search performed yet",
                    italic=True,
                    color=
                )
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY),
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
                    color=
                )
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY),
            border_radius=10
        )
        
        # Main layout
        return ft.Column([
            search_section,
            ft.Container(height=10),
            results_section,
            ft.Container(height=10),
            visualization_section
        ],
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        expand=True
        )
    
    def search_identifications(self, e):
        """Search for identifications."""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("Search functionality coming soon. Import identifications first."),
            bgcolor=ft.Colors.BLUE_400
        )
        self.page.snack_bar.open = True
        self.page.update()
