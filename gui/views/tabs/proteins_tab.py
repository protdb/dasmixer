"""Proteins tab - protein identifications (stub for stage 3.2)."""

import flet as ft
from api.project.project import Project


class ProteinsTab(ft.Container):
    """Proteins tab - will be implemented in stage 4."""
    
    def __init__(self, project: Project):
        super().__init__()
        self.project = project
        
        # Build content
        self.content = self._build_content()
        self.alignment = ft.alignment.center
        self.expand = True
    
    def _build_content(self):
        return ft.Column([
            ft.Icon(ft.Icons.BUBBLE_CHART, size=64, color=ft.Colors.PRIMARY),
            ft.Text(
                "Protein Identifications",
                size=24,
                weight=ft.FontWeight.BOLD
            ),
            ft.Text(
                "Coming soon in Stage 4",
                size=16,
                color=
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
        )
