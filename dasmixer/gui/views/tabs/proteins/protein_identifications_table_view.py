"""Table view for detailed protein identifications."""

import flet as ft
import pandas as pd

from dasmixer.gui.components.base_table_view import BaseTableView
from dasmixer.api.project.project import Project


class ProteinIdentificationsTableView(BaseTableView):
    """Detailed protein identifications table."""

    table_view_name = "protein_identifications"
    plot_id_field = "protein_id"

    header_name_mapping = {
        'protein_id': 'Protein ID',
        'sample': 'Sample',
        'subset': 'Group',
        'gene': 'Gene',
        'peptide_count': 'Peptides',
        'unique_evidence_count': 'Unique Peptides',
        'coverage_percent': 'Coverage, %',
        'intensity_sum': 'Intensity Sum',
        'weight': 'MW, Da',
        'EmPAI': 'emPAI',
        'iBAQ': 'iBAQ',
        'NSAF': 'NSAF',
        'Top3': 'Top3',
    }

    column_filter_mapping = {
        'protein_id': 'protein_id',
        'gene': 'gene',
        'sample': 'sample',
        'subset': 'subset',
    }

    def __init__(self, project: Project, plot_callback=None):
        super().__init__(project, title="Protein Identifications (Detailed)", plot_callback=plot_callback)

    def get_default_filters(self) -> dict:
        return {
            'sample': 'all',
            'subset': 'all',
            'protein_id': '',
            'gene': '',
            'min_peptides': 0,
            'min_unique': 0,
            'min_coverage': '',
            'max_coverage': '',
            'min_intensity': '',
            'max_intensity': '',
        }

    def _build_filter_view(self) -> ft.Control:
        self.sample_dropdown = ft.Dropdown(
            label="Sample",
            options=[ft.DropdownOption(key="all", text="All Samples")],
            value="all", width=200
        )
        self.subset_dropdown = ft.Dropdown(
            label="Group",
            options=[ft.DropdownOption(key="all", text="All Groups")],
            value="all", width=200
        )
        self.protein_id_field = ft.TextField(
            label="Protein ID contains", value="", width=200
        )
        self.gene_field = ft.TextField(
            label="Gene contains", value="", width=150
        )
        self.min_peptides_field = ft.TextField(
            label="Min Peptides", value="0",
            width=130, keyboard_type=ft.KeyboardType.NUMBER
        )
        self.min_unique_field = ft.TextField(
            label="Min Unique", value="0",
            width=130, keyboard_type=ft.KeyboardType.NUMBER
        )
        self.min_coverage_field = ft.TextField(
            label="Min Coverage, %", value="",
            width=150, keyboard_type=ft.KeyboardType.NUMBER
        )
        self.max_coverage_field = ft.TextField(
            label="Max Coverage, %", value="",
            width=150, keyboard_type=ft.KeyboardType.NUMBER
        )
        self.min_intensity_field = ft.TextField(
            label="Min Intensity", value="",
            width=150, keyboard_type=ft.KeyboardType.NUMBER
        )
        self.max_intensity_field = ft.TextField(
            label="Max Intensity", value="",
            width=150, keyboard_type=ft.KeyboardType.NUMBER
        )

        # Register clickable column → filter controls
        self.filter_controls = {
            'protein_id': self.protein_id_field,
            'gene': self.gene_field,
        }

        return ft.Column([
            ft.Row([self.sample_dropdown, self.subset_dropdown, self.protein_id_field, self.gene_field], spacing=10),
            ft.Row([self.min_peptides_field, self.min_unique_field,
                    self.min_coverage_field, self.max_coverage_field], spacing=10),
            ft.Row([self.min_intensity_field, self.max_intensity_field], spacing=10),
        ], spacing=10)

    async def _update_filters_from_ui(self):
        self.filter['sample'] = self.sample_dropdown.value
        self.filter['subset'] = self.subset_dropdown.value
        self.filter['protein_id'] = self.protein_id_field.value or ''
        self.filter['gene'] = self.gene_field.value or ''
        self.filter['min_peptides'] = _parse_int(self.min_peptides_field.value)
        self.filter['min_unique'] = _parse_int(self.min_unique_field.value)
        self.filter['min_coverage'] = self.min_coverage_field.value or ''
        self.filter['max_coverage'] = self.max_coverage_field.value or ''
        self.filter['min_intensity'] = self.min_intensity_field.value or ''
        self.filter['max_intensity'] = self.max_intensity_field.value or ''

    async def load_data(self):
        await self._load_filter_options()
        await super().load_data()

    async def _load_filter_options(self):
        samples = await self.project.get_samples()
        self.sample_dropdown.options = [
            ft.DropdownOption(key="all", text="All Samples")
        ] + [ft.DropdownOption(key=s.name, text=s.name) for s in samples]

        subsets = await self.project.get_subsets()
        self.subset_dropdown.options = [
            ft.DropdownOption(key="all", text="All Groups")
        ] + [ft.DropdownOption(key=sb.name, text=sb.name) for sb in subsets]

        if self.page:
            self.sample_dropdown.update()
            self.subset_dropdown.update()

    def _build_filter_kwargs(self) -> dict:
        kwargs = {}

        if self.filter['sample'] != 'all':
            kwargs['sample'] = self.filter['sample']

        if self.filter['subset'] != 'all':
            kwargs['subset'] = self.filter['subset']

        if self.filter['protein_id']:
            kwargs['protein_id'] = self.filter['protein_id']

        if self.filter['gene']:
            kwargs['gene'] = self.filter['gene']

        if self.filter['min_peptides'] > 0:
            kwargs['min_peptides'] = self.filter['min_peptides']

        if self.filter['min_unique'] > 0:
            kwargs['min_unique'] = self.filter['min_unique']

        if self.filter['min_coverage']:
            try:
                kwargs['min_coverage'] = float(self.filter['min_coverage'])
            except (ValueError, TypeError):
                pass

        if self.filter['max_coverage']:
            try:
                kwargs['max_coverage'] = float(self.filter['max_coverage'])
            except (ValueError, TypeError):
                pass

        if self.filter['min_intensity']:
            try:
                kwargs['min_intensity'] = float(self.filter['min_intensity'])
            except (ValueError, TypeError):
                pass

        if self.filter['max_intensity']:
            try:
                kwargs['max_intensity'] = float(self.filter['max_intensity'])
            except (ValueError, TypeError):
                pass

        return kwargs

    async def get_data(self, limit: int = 100, offset: int = 0) -> tuple[pd.DataFrame, pd.DataFrame | None]:
        kwargs = self._build_filter_kwargs()

        if limit == -1:
            df = await self.project.get_protein_results_joined(**kwargs, limit=999999, offset=0)
        else:
            df = await self.project.get_protein_results_joined(**kwargs, limit=limit, offset=offset)
        tooltip_df = df[['fasta_name']]
        df['fasta_name'] = df['fasta_name'].apply(lambda x: x if len(x) <= 32 else x[:30]+'…')
        return df, None

    async def get_total_count(self) -> int:
        kwargs = self._build_filter_kwargs()
        return await self.project.count_protein_results_joined(**kwargs)


def _parse_int(value, default: int = 0) -> int:
    """Safely parse integer from string input."""
    try:
        return int(value or default)
    except (ValueError, TypeError):
        return default
