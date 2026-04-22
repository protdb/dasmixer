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

    def __init__(self, project: Project, plot_callback=None):
        super().__init__(project, title="Protein Identifications (Detailed)", plot_callback=plot_callback)

    def get_default_filters(self) -> dict:
        return {
            'sample': 'all',
            'min_peptides': 0,
            'min_unique': 0
        }

    def _build_filter_view(self) -> ft.Control:
        self.sample_dropdown = ft.Dropdown(
            label="Sample",
            options=[ft.DropdownOption(key="all", text="All Samples")],
            value="all", width=200
        )
        self.min_peptides_field = ft.TextField(
            label="Min Peptides", value="0",
            width=150, keyboard_type=ft.KeyboardType.NUMBER
        )
        self.min_unique_field = ft.TextField(
            label="Min Unique", value="0",
            width=150, keyboard_type=ft.KeyboardType.NUMBER
        )

        return ft.Column([
            ft.Row([self.sample_dropdown], spacing=10),
            ft.Row([self.min_peptides_field, self.min_unique_field], spacing=10)
        ], spacing=10)

    async def _update_filters_from_ui(self):
        self.filter['sample'] = self.sample_dropdown.value
        self.filter['min_peptides'] = int(self.min_peptides_field.value or 0)
        self.filter['min_unique'] = int(self.min_unique_field.value or 0)

    async def load_data(self):
        await self._load_filter_options()
        await super().load_data()

    async def _load_filter_options(self):
        samples = await self.project.get_samples()
        self.sample_dropdown.options = [
            ft.DropdownOption(key="all", text="All Samples")
        ] + [ft.DropdownOption(key=s.name, text=s.name) for s in samples]
        if self.page:
            self.sample_dropdown.update()

    async def get_data(self, limit: int = 100, offset: int = 0) -> tuple[pd.DataFrame, pd.DataFrame | None]:
        sample = None if self.filter['sample'] == 'all' else self.filter['sample']

        if limit == -1:
            df = await self.project.get_protein_results_joined(sample=sample, limit=999999, offset=0)
        else:
            df = await self.project.get_protein_results_joined(sample=sample, limit=limit, offset=offset)

        if self.filter['min_peptides'] > 0 and 'peptide_count' in df.columns:
            df = df[df['peptide_count'] >= self.filter['min_peptides']]

        if self.filter['min_unique'] > 0 and 'unique_evidence_count' in df.columns:
            df = df[df['unique_evidence_count'] >= self.filter['min_unique']]

        return df, None

    async def get_total_count(self) -> int:
        sample = None if self.filter['sample'] == 'all' else self.filter['sample']
        return await self.project.count_protein_results_joined(
            sample=sample,
            min_peptides=self.filter['min_peptides'],
            min_unique=self.filter['min_unique'],
        )
