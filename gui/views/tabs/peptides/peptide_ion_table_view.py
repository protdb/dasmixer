"""Table view for peptide identifications with filtering."""

import flet as ft
import pandas as pd

from gui.components.base_table_view import BaseTableView
from api.project.project import Project


class PeptideIonTableView(BaseTableView):
    """Table view for peptide identifications."""
    
    table_view_name = "peptide_identifications"
    plot_id_field = "spectre_id"
    
    def __init__(self, project: Project, plot_callback=None):
        super().__init__(project, title="Peptide Identifications", plot_callback=plot_callback)
    
    def get_default_filters(self) -> dict:
        """Get default filters."""
        return {
            'identification_id': None,
            'sample_id': 'all',
            'tool_id': 'all',
            'min_score': 0.0,
            'max_ppm': "",
            'sequence': '',
            'canonical_sequence': '',
            'is_preferred': 'None',
            'seq_no': None,
            'scans': None,
        }
    
    def _build_filter_view(self) -> ft.Control:
        """Build filters UI."""
        self.identification_id_field = ft.TextField(
            label="Identification ID",
            value="",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=150
        )

        self.sample_dropdown = ft.Dropdown(
            label="Sample",
            options=[ft.DropdownOption(key="all", text="All Samples")],
            value="all",
            width=200
        )

        self.seq_no_field = ft.TextField(
            label="Spectre sequence number",
            value="",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=150
        )

        self.scans_field = ft.TextField(
            label="Spectre scans",
            value="",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=150
        )
        
        self.tool_dropdown = ft.Dropdown(
            label="Tool",
            options=[ft.DropdownOption(key="all", text="All Tools")],
            value="all",
            width=200
        )
        
        self.min_score_field = ft.TextField(
            label="Min Score",
            value="0",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        self.max_ppm_field = ft.TextField(
            label="Max PPM",
            value="",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        self.sequence_field = ft.TextField(
            label="Sequence contains",
            value="",
            width=200
        )
        
        self.canonical_sequence_field = ft.TextField(
            label="Canonical sequence contains",
            value="",
            width=200
        )

        self.is_preferred_field = ft.Dropdown(
            label="Is Preferred",
            value='None',
            options=[
                ft.DropdownOption(key="None", text="All"),
                ft.DropdownOption(key="True", text="Yes"),
                ft.DropdownOption(key="False", text="No"),
            ],
            width=150,
        )
        
        return ft.Column([
            ft.Row([
                self.identification_id_field,
                self.sample_dropdown,
                self.seq_no_field,
                self.scans_field,
                self.is_preferred_field,
            ], spacing=10),
            ft.Row([
                self.tool_dropdown,
                self.min_score_field,
                self.max_ppm_field,
                self.sequence_field,
                self.canonical_sequence_field
            ], spacing=10),
            # ft.Row([self.sample_dropdown, self.tool_dropdown, self.min_score_field, self.max_ppm_field], spacing=10),
            # ft.Row([, ], spacing=10),
            # ft.Row([self.sequence_field, self.canonical_sequence_field, self.is_preferred_field], spacing=10)
        ], spacing=10)
    
    async def _update_filters_from_ui(self):
        """Update filters from UI controls."""
        self.filter['sample_id'] = self.sample_dropdown.value
        self.filter['tool_id'] = self.tool_dropdown.value
        self.filter['min_score'] = float(self.min_score_field.value or 0)
        self.filter['max_ppm'] = float(self.max_ppm_field.value or 1000)
        self.filter['sequence'] = self.sequence_field.value
        self.filter['canonical_sequence'] = self.canonical_sequence_field.value
        self.filter['is_preferred'] = self.is_preferred_field.value
        self.filter['identification_id'] = self.identification_id_field.value
        self.filter['scans'] = self.scans_field.value
        self.filter['seq_no'] = self.seq_no_field.value
    
    async def load_data(self):
        """Load dropdown options and table data."""
        await self._load_filter_options()
        await super().load_data()
    
    async def _load_filter_options(self):
        """Load options for dropdowns."""
        # Load samples
        samples = await self.project.get_samples()
        self.sample_dropdown.options = [
            ft.DropdownOption(key="all", text="All Samples")
        ] + [
            ft.DropdownOption(key=str(s.id), text=s.name)
            for s in samples
        ]
        
        # Load tools
        tools = await self.project.get_tools()
        self.tool_dropdown.options = [
            ft.DropdownOption(key="all", text="All Tools")
        ] + [
            ft.DropdownOption(key=str(t.id), text=t.name)
            for t in tools
        ]
        
        if self.page:
            self.sample_dropdown.update()
            self.tool_dropdown.update()
    
    def _build_filter_kwargs(self) -> dict:
        """Build kwargs for peptide query from current filters."""
        kwargs = {}
        
        if self.filter['sample_id'] != 'all':
            kwargs['sample_id'] = int(self.filter['sample_id'])
        
        if self.filter['tool_id'] != 'all':
            kwargs['tool_id'] = int(self.filter['tool_id'])
        
        if self.filter['sequence']:
            kwargs['sequence'] = self.filter['sequence']
        
        if self.filter['canonical_sequence']:
            kwargs['canonical_sequence'] = self.filter['canonical_sequence']

        if self.filter['is_preferred'] != 'None':
            kwargs['is_preferred'] = self.filter['is_preferred'] == 'True'

        if self.filter['identification_id'] != '':
            kwargs['identification_id'] = int(self.filter['identification_id'])

        if self.filter['scans']:
            kwargs['scans'] = int(self.filter['scans'])

        if self.filter['seq_no']:
            kwargs['seq_no'] = int(self.filter['seq_no'])
        
        return kwargs
    
    async def get_data(self, limit: int = 100, offset: int = 0) -> pd.DataFrame:
        """Get filtered peptide data with pagination."""
        # Build filter parameters
        kwargs = self._build_filter_kwargs()
        
        # Get data with LIMIT/OFFSET from database
        df = await self.project.get_joined_peptide_data(
            **kwargs,
            limit=limit,
            offset=offset
        )
        
        if df.empty:
            return df
        
        # Apply score and ppm filters in pandas (these are not in the API yet)
        if self.filter['min_score'] > 0:
            # score might not exist in all rows
            if 'score' in df.columns:
                df = df[df['score'].fillna(0) >= self.filter['min_score']]
        
        if self.filter['max_ppm'] < 1000:
            if 'ppm' in df.columns:
                df = df[df['ppm'].fillna(1000).abs() <= self.filter['max_ppm']]
        
        # Select display columns
        display_columns = []
        for col in [
            'identification_id',
            'spectre_id',
            'sample',
            'seq_no',
            'tool',
            'sequence',
            'ppm',
            'intensity_coverage',
            'ions_matched',
            'ion_match_type',
            'top_peaks_covered',
            'is_preferred',
            'protein_id',
            'gene',
        ]:
            if col in df.columns:
                display_columns.append(col)
        
        if display_columns:
            df = df[display_columns]
        
        # Format is_preferred as boolean
        if 'is_preferred' in df.columns:
            df['is_preferred'] = df['is_preferred'].apply(lambda x: '✓' if x else '')
        
        return df
    
    async def get_total_count(self) -> int:
        """Get total count of filtered rows."""
        # Build filter parameters
        kwargs = self._build_filter_kwargs()
        
        # Get count from database
        total = await self.project.count_joined_peptide_data(**kwargs)
        
        # Note: min_score and max_ppm filters are applied in pandas after retrieval
        # For accurate count, we would need to fetch all data and filter
        # But this is acceptable for now - count might be slightly higher than actual
        # TODO: Add score/ppm filters to count_joined_peptide_data API
        
        return total
