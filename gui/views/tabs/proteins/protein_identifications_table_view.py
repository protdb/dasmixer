"""Table view for detailed protein identifications."""

import flet as ft
import pandas as pd

from gui.components.base_table_view import BaseTableView
from api.project.project import Project


class ProteinIdentificationsTableView(BaseTableView):
    """Detailed protein identifications table."""
    
    table_view_name = "protein_identifications"
    plot_id_field = "protein_id"
    
    def __init__(self, project: Project, plot_callback=None):
        super().__init__(project, title="Protein Identifications (Detailed)", plot_callback=plot_callback)
    
    def get_default_filters(self) -> dict:
        """Get default filters."""
        return {
            'sample': 'all',
            'min_peptides': 0,
            'min_unique': 0
        }
    
    def _build_filter_view(self) -> ft.Control:
        """Build filters UI."""
        self.sample_dropdown = ft.Dropdown(
            label="Sample",
            options=[ft.dropdown.Option(key="all", text="All Samples")],
            value="all",
            width=200
        )
        
        self.min_peptides_field = ft.TextField(
            label="Min Peptides",
            value="0",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        self.min_unique_field = ft.TextField(
            label="Min Unique",
            value="0",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        return ft.Column([
            ft.Row([self.sample_dropdown], spacing=10),
            ft.Row([self.min_peptides_field, self.min_unique_field], spacing=10)
        ], spacing=10)
    
    async def _update_filters_from_ui(self):
        """Update filters from UI controls."""
        self.filter['sample'] = self.sample_dropdown.value
        self.filter['min_peptides'] = int(self.min_peptides_field.value or 0)
        self.filter['min_unique'] = int(self.min_unique_field.value or 0)
    
    async def load_data(self):
        """Load dropdown options and table data."""
        await self._load_filter_options()
        await super().load_data()
    
    async def _load_filter_options(self):
        """Load options for dropdowns."""
        samples = await self.project.get_samples()
        self.sample_dropdown.options = [
            ft.dropdown.Option(key="all", text="All Samples")
        ] + [
            ft.dropdown.Option(key=s.name, text=s.name)
            for s in samples
        ]
        
        if self.page:
            self.sample_dropdown.update()
    
    async def get_data(self, limit: int = 100, offset: int = 0) -> pd.DataFrame:
        """Get filtered protein identifications."""
        sample = None if self.filter['sample'] == 'all' else self.filter['sample']
        
        df = await self.project.get_protein_results_joined(
            sample=sample,
            limit=limit,
            offset=offset
        )
        
        # Apply peptide count filters
        if self.filter['min_peptides'] > 0:
            df = df[df['peptide_count'] >= self.filter['min_peptides']]
        
        if self.filter['min_unique'] > 0:
            df = df[df['unique_evidence_count'] >= self.filter['min_unique']]
        
        return df
    
    async def get_total_count(self) -> int:
        """Get total count of filtered rows."""
        sample = None if self.filter['sample'] == 'all' else self.filter['sample']
        
        # Get all data
        df = await self.project.get_protein_results_joined(
            sample=sample,
            limit=999999,
            offset=0
        )
        
        # Apply filters
        if self.filter['min_peptides'] > 0:
            df = df[df['peptide_count'] >= self.filter['min_peptides']]
        
        if self.filter['min_unique'] > 0:
            df = df[df['unique_evidence_count'] >= self.filter['min_unique']]
        
        return len(df)
