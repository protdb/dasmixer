"""Analysis tab - comparative analysis (stub for stage 3.2)."""

import flet as ft
from api.project.project import Project


class AnalysisTab(ft.Container):
    """Analysis tab - will be implemented in stage 5."""
    
    def __init__(self, project: Project):
        super().__init__()
        self.project = project
        
        # Build content
        self.content = self._build_content()
        self.alignment = ft.alignment.center
        self.expand = True
    
    def _build_content(self):
        return ft.Column([
            ft.Icon(ft.Icons.ANALYTICS, size=64, color=ft.Colors.PRIMARY),
            ft.Text(
                "Comparative Analysis",
                size=24,
                weight=ft.FontWeight.BOLD
            ),
            ft.Text(
                "Coming soon in Stage 5",
                size=16,
                color=
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
        )
