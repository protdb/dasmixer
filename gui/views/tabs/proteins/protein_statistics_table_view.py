"""Table view for aggregated protein statistics."""

import flet as ft
import pandas as pd

from gui.components.base_table_view import BaseTableView
from api.project.project import Project


class ProteinStatisticsTableView(BaseTableView):
    """Aggregated protein statistics table."""
    
    table_view_name = "protein_statistics"
    plot_id_field = "protein_id"
    
    def __init__(self, project: Project, plot_callback=None):
        super().__init__(project, title="Protein Statistics (Aggregated)", plot_callback=plot_callback)
    
    def get_default_filters(self) -> dict:
        """Get default filters."""
        return {
            'protein_id': '',
            'gene': '',
            'fasta_name': '',
            'min_samples': 0,
            'min_subsets': 0
        }
    
    def _build_filter_view(self) -> ft.Control:
        """Build filters UI."""
        self.protein_id_field = ft.TextField(
            label="Protein ID contains",
            value="",
            width=200
        )
        
        self.gene_field = ft.TextField(
            label="Gene contains",
            value="",
            width=200
        )
        
        self.fasta_name_field = ft.TextField(
            label="FASTA name contains",
            value="",
            width=250
        )
        
        self.min_samples_field = ft.TextField(
            label="Min Samples",
            value="0",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        self.min_subsets_field = ft.TextField(
            label="Min Subsets",
            value="0",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        return ft.Column([
            ft.Row([self.protein_id_field, self.gene_field], spacing=10),
            ft.Row([self.fasta_name_field], spacing=10),
            ft.Row([self.min_samples_field, self.min_subsets_field], spacing=10)
        ], spacing=10)
    
    async def _update_filters_from_ui(self):
        """Update filters from UI controls."""
        self.filter['protein_id'] = self.protein_id_field.value
        self.filter['gene'] = self.gene_field.value
        self.filter['fasta_name'] = self.fasta_name_field.value
        self.filter['min_samples'] = int(self.min_samples_field.value or 0)
        self.filter['min_subsets'] = int(self.min_subsets_field.value or 0)
    
    async def get_data(self, limit: int = 100, offset: int = 0) -> pd.DataFrame:
        """Get filtered protein statistics."""
        df = await self.project.get_protein_statistics(
            protein_id=self.filter['protein_id'],
            gene=self.filter['gene'],
            fasta_name=self.filter['fasta_name'],
            min_samples=self.filter['min_samples'],
            min_subsets=self.filter['min_subsets'],
            limit=limit,
            offset=offset
        )
        return df
    
    async def get_total_count(self) -> int:
        """Get total count of filtered rows."""
        # Get all data without limit
        # df = await self.project.get_protein_statistics(
        #     protein_id=self.filter['protein_id'],
        #     gene=self.filter['gene'],
        #     fasta_name=self.filter['fasta_name'],
        #     min_samples=self.filter['min_samples'],
        #     min_subsets=self.filter['min_subsets'],
        #     limit=999999,
        #     offset=0
        # )
        # return len(df)
        return 999999
