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
    
    async def calculate_identifications(self, e):
        """
        Calculate protein identifications.
        
        Workflow:
        1. Validate parameters
        2. Show progress dialog
        3. Clear old results
        4. Get peptide data and protein DB
        5. Run find_protein_identifications()
        6. Save results
        7. Update state and refresh table
        """
        # Validate parameters
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
        
        # Create progress dialog
        dialog = ProgressDialog(self.page, "Calculating Protein Identifications")
        dialog.show()
        
        try:
            # Clear old results
            dialog.update_progress(None, "Clearing old results...")
            await self.project.clear_protein_identifications()
            
            # Get data
            dialog.update_progress(None, "Loading peptide data...")
            joined_data = await self.project.get_joined_peptide_data(
                is_preferred=True,
                protein_identified=True
            )
            
            if len(joined_data) == 0:
                dialog.close()
                self.show_warning("No protein-matched identifications found. Please run peptide matching first.")
                return
            
            dialog.update_progress(None, "Loading protein database...")
            sequences_db = await self.project.get_protein_db_to_search()
            
            if len(sequences_db) == 0:
                dialog.close()
                self.show_warning("No proteins loaded. Please load a FASTA file first.")
                return
            
            # Calculate total samples for progress
            total_samples = joined_data['sample_id'].nunique()
            current_sample = 0
            
            # Run identification calculation
            async for result_df, sample_id in find_protein_identifications(
                joined_data=joined_data,
                sequences_db=sequences_db,
                min_peptides=min_pep,
                min_uq_evidence=min_uq
            ):
                current_sample += 1
                dialog.update_progress(
                    current_sample / total_samples,
                    f"Processing sample {current_sample} of {total_samples}"
                )
                
                # Save batch
                if len(result_df) > 0:
                    await self.project.add_protein_identifications_batch(result_df)
            
            # Update counts
            self.state.protein_identification_count = await self.project.get_protein_identification_count()
            
            # Complete
            dialog.complete()
            await asyncio.sleep(1)
            dialog.close()
            
            self.show_success(f"Protein identifications calculated: {self.state.protein_identification_count} total")
            
            # Refresh table
            if hasattr(self.parent_tab, 'sections') and 'table' in self.parent_tab.sections:
                await self.parent_tab.sections['table'].load_data()
        
        except Exception as ex:
            import traceback
            traceback.print_exc()
            dialog.close()
            self.show_error(f"Error: {str(ex)}")
