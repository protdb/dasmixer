"""Analysis tab - comparative analysis (stub for stage 3.2)."""

import flet as ft
from api.project.project import Project


class AnalysisTab(ft.UserControl):
    """Analysis tab - will be implemented in stage 5."""
    
    def __init__(self, project: Project):
        super().__init__()
        self.project = project
    
    def build(self):
        return ft.Container(
            content=ft.Column([
                ft.Icon(ft.icons.ANALYTICS, size=64, color=ft.colors.PRIMARY),
                ft.Text(
                    "Comparative Analysis",
                    size=24,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Text(
                    "Coming soon in Stage 5",
                    size=16,
                    color=ft.colors.ON_SURFACE_VARIANT
                ),
                ft.Container(height=20),
                ft.Text(
                    "Features:",
                    size=14,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Text("• Differential expression analysis", size=12),
                ft.Text("• Volcano plots", size=12),
                ft.Text("• PCA visualization", size=12),
                ft.Text("• Statistical testing", size=12),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10
            ),
            alignment=ft.alignment.center,
            expand=True
        )
