"""Proteins tab - protein identifications (stub for stage 3.2)."""

import flet as ft
from api.project.project import Project


class ProteinsTab(ft.UserControl):
    """Proteins tab - will be implemented in stage 4."""
    
    def __init__(self, project: Project):
        super().__init__()
        self.project = project
    
    def build(self):
        return ft.Container(
            content=ft.Column([
                ft.Icon(ft.icons.BUBBLE_CHART, size=64, color=ft.colors.PRIMARY),
                ft.Text(
                    "Protein Identifications",
                    size=24,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Text(
                    "Coming soon in Stage 4",
                    size=16,
                    color=ft.colors.ON_SURFACE_VARIANT
                ),
                ft.Container(height=20),
                ft.Text(
                    "Features:",
                    size=14,
                    weight=ft.FontWeight.BOLD
                ),
                ft.Text("• Protein database search", size=12),
                ft.Text("• UniProt enrichment", size=12),
                ft.Text("• LFQ quantification", size=12),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10
            ),
            alignment=ft.alignment.center,
            expand=True
        )
