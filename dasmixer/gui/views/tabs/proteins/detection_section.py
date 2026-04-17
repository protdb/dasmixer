"""Detection section - protein identification calculation."""

import flet as ft
import asyncio

from .base_section import BaseSection
from dasmixer.gui.views.tabs.peptides.dialogs.progress_dialog import ProgressDialog
from dasmixer.api.calculations.proteins.map_identifications import find_protein_identifications


class DetectionSection(BaseSection):
    """
    Protein Detection section.
    
    Manages parameters and execution of protein identification calculation.
    """
    
    def __init__(self, project, state, parent_tab):
        """
        Initialize detection section.
        
        Args:
            project: Project instance
            state: Shared state
            parent_tab: Reference to parent ProteinsTab
        """
        self.parent_tab = parent_tab
        super().__init__(project, state)
    
    def _build_content(self) -> ft.Control:
        """Build detection section UI."""
        # Input fields
        self.min_peptides_field = ft.TextField(
            label="Minimum peptides",
            value=str(self.state.min_peptides),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=200,
            on_change=self._on_min_peptides_changed
        )
        
        self.min_unique_field = ft.TextField(
            label="Minimum unique peptides",
            value=str(self.state.min_unique_evidence),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=200,
            on_change=self._on_min_unique_changed
        )
        
        # Calculate button
        self.calculate_btn = ft.ElevatedButton(
            content=ft.Text("Calculate Protein Identifications"),
            icon=ft.Icons.PLAY_CIRCLE,
            on_click=lambda e: self.page.run_task(self.calculate_identifications, e),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.BLUE_600,
                color=ft.Colors.WHITE
            )
        )
        
        return ft.Column([
            ft.Text("Protein Detection", size=18, weight=ft.FontWeight.BOLD),
            ft.Container(height=10),
            ft.Row([
                self.min_peptides_field,
                ft.Container(width=10),
                self.min_unique_field
            ]),
            ft.Container(height=10),
            self.calculate_btn
        ], spacing=10)
    
    async def load_data(self):
        """Load settings from project."""
        # Load from project_settings
        min_pep = await self.project.get_setting('proteins_min_peptides')
        if min_pep is not None:
            self.state.min_peptides = int(min_pep)
            self.min_peptides_field.value = min_pep
        
        min_uq = await self.project.get_setting('proteins_min_unique_evidence')
        if min_uq is not None:
            self.state.min_unique_evidence = int(min_uq)
            self.min_unique_field.value = min_uq
        
        if self.page:
            self.update()
    
    def _on_min_peptides_changed(self, e):
        """Update state when minimum peptides changes."""
        try:
            value = int(e.control.value)
            self.state.min_peptides = value
        except ValueError:
            pass
    
    def _on_min_unique_changed(self, e):
        """Update state when minimum unique peptides changes."""
        try:
            value = int(e.control.value)
            self.state.min_unique_evidence = value
        except ValueError:
            pass
    
    async def calculate_identifications(self, e, sample_id: int | None = None):
        """
        Calculate protein identifications. Delegates to ProteinIdentificationsAction.
        """
        try:
            min_pep = int(self.min_peptides_field.value)
            min_uq = int(self.min_unique_field.value)
            if min_pep < 1:
                self.show_error("Minimum peptides must be at least 1")
                return
            if min_uq < 0:
                self.show_error("Minimum unique peptides cannot be negative")
                return
        except ValueError:
            self.show_error("Please enter valid numbers")
            return

        # Save settings to project
        await self.project.set_setting('proteins_min_peptides', str(min_pep))
        await self.project.set_setting('proteins_min_unique_evidence', str(min_uq))

        from dasmixer.gui.actions.protein_ident_action import ProteinIdentificationsAction
        action = ProteinIdentificationsAction(self.project, self.page)
        total = await action.run(
            min_peptides=min_pep,
            min_uq_evidence=min_uq,
            sample_id=sample_id,
        )

        # Update counts and refresh table
        self.state.protein_identification_count = await self.project.get_protein_identification_count()
        if hasattr(self.parent_tab, 'sections') and 'table' in self.parent_tab.sections:
            await self.parent_tab.sections['table'].load_data()
