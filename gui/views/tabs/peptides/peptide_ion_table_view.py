"""Table view for peptide identifications with filtering."""

import flet as ft
import pandas as pd

from gui.components.base_table_view import BaseTableView
from api.project.project import Project

_MAX_SEQ_LEN = 31


class PeptideIonTableView(BaseTableView):
    """Table view for peptide identifications."""

    table_view_name = "peptide_identifications"
    plot_id_field = "spectre_id"

    header_name_mapping = {
        'identification_id': 'ID',
        'spectre_id': 'Spectrum ID',
        'sample': 'Sample',
        'seq_no': 'Seq #',
        'scans': 'Scans',
        'tool': 'Tool',
        'sequence': 'Sequence',
        'ppm': 'PPM',
        'intensity_coverage': 'Ion Coverage, %',
        'ions_matched': 'Ions Matched',
        'ion_match_type': 'Ion Type',
        'top_peaks_covered': 'Top-10 Peaks',
        'is_preferred': 'Preferred',
        'protein_id': 'Protein',
        'gene': 'Gene',
    }

    column_filter_mapping = {
        'scans': 'scans',
        'spectre_id': 'spectre_id',
        'identification_id': 'identification_id',
    }

    default_columns = {
        'identification_id', 'spectre_id', 'sample', 'seq_no', 'scans',
        'tool', 'sequence', 'ppm', 'intensity_coverage', 'ions_matched',
        'ion_match_type', 'top_peaks_covered', 'is_preferred',
        'protein_id', 'gene',
    }

    def __init__(self, project: Project, plot_callback=None):
        super().__init__(project, title="Peptide Identifications", plot_callback=plot_callback)

    def get_default_filters(self) -> dict:
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
            'spectre_id': None,
        }

    def _build_filter_view(self) -> ft.Control:
        self.identification_id_field = ft.TextField(
            label="Identification ID", value="",
            keyboard_type=ft.KeyboardType.NUMBER, width=150
        )
        self.sample_dropdown = ft.Dropdown(
            label="Sample",
            options=[ft.DropdownOption(key="all", text="All Samples")],
            value="all", width=200
        )
        self.seq_no_field = ft.TextField(
            label="Spectre Seq #", value="",
            keyboard_type=ft.KeyboardType.NUMBER, width=150
        )
        self.scans_field = ft.TextField(
            label="Scans", value="",
            keyboard_type=ft.KeyboardType.NUMBER, width=150
        )
        self.spectre_id_field = ft.TextField(
            label="Spectrum ID", value="",
            keyboard_type=ft.KeyboardType.NUMBER, width=150
        )
        self.tool_dropdown = ft.Dropdown(
            label="Tool",
            options=[ft.DropdownOption(key="all", text="All Tools")],
            value="all", width=200
        )
        self.min_score_field = ft.TextField(
            label="Min Score", value="0",
            width=150, keyboard_type=ft.KeyboardType.NUMBER
        )
        self.max_ppm_field = ft.TextField(
            label="Max PPM", value="",
            width=150, keyboard_type=ft.KeyboardType.NUMBER
        )
        self.sequence_field = ft.TextField(
            label="Sequence contains", value="", width=200
        )
        self.canonical_sequence_field = ft.TextField(
            label="Canonical sequence contains", value="", width=200
        )
        self.is_preferred_field = ft.Dropdown(
            label="Is Preferred", value='None',
            options=[
                ft.DropdownOption(key="None", text="All"),
                ft.DropdownOption(key="True", text="Yes"),
                ft.DropdownOption(key="False", text="No"),
            ],
            width=150,
        )

        # Register filter_controls (for set_filters_in_ui)
        self.filter_controls = {
            'identification_id': self.identification_id_field,
            'scans': self.scans_field,
            'spectre_id': self.spectre_id_field,
            'seq_no': self.seq_no_field,
        }

        return ft.Column([
            ft.Row([
                self.identification_id_field,
                self.sample_dropdown,
                self.seq_no_field,
                self.scans_field,
                self.spectre_id_field,
                self.is_preferred_field,
            ], spacing=10),
            ft.Row([
                self.tool_dropdown,
                self.min_score_field,
                self.max_ppm_field,
                self.sequence_field,
                self.canonical_sequence_field
            ], spacing=10),
        ], spacing=10)

    async def _update_filters_from_ui(self):
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
        self.filter['spectre_id'] = self.spectre_id_field.value

    async def load_data(self):
        await self._load_filter_options()
        await super().load_data()

    async def _load_filter_options(self):
        samples = await self.project.get_samples()
        self.sample_dropdown.options = [
            ft.DropdownOption(key="all", text="All Samples")
        ] + [ft.DropdownOption(key=str(s.id), text=s.name) for s in samples]

        tools = await self.project.get_tools()
        self.tool_dropdown.options = [
            ft.DropdownOption(key="all", text="All Tools")
        ] + [ft.DropdownOption(key=str(t.id), text=t.name) for t in tools]

        if self.page:
            self.sample_dropdown.update()
            self.tool_dropdown.update()

    def _build_filter_kwargs(self) -> dict:
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

        if self.filter.get('identification_id'):
            try:
                kwargs['identification_id'] = int(self.filter['identification_id'])
            except (ValueError, TypeError):
                pass

        if self.filter.get('scans'):
            try:
                kwargs['scans'] = int(self.filter['scans'])
            except (ValueError, TypeError):
                pass

        if self.filter.get('seq_no'):
            try:
                kwargs['seq_no'] = int(self.filter['seq_no'])
            except (ValueError, TypeError):
                pass

        return kwargs

    async def get_data(self, limit: int = 100, offset: int = 0) -> tuple[pd.DataFrame, pd.DataFrame | None]:
        kwargs = self._build_filter_kwargs()

        # limit=-1 means no pagination (export)
        if limit == -1:
            df = await self.project.get_joined_peptide_data(**kwargs)
        else:
            df = await self.project.get_joined_peptide_data(**kwargs, limit=limit, offset=offset)

        if df.empty:
            return df, None

        # Apply score and ppm filters in pandas
        if self.filter['min_score'] > 0 and 'score' in df.columns:
            df = df[df['score'].fillna(0) >= self.filter['min_score']]

        max_ppm = self.filter.get('max_ppm')
        if max_ppm and float(max_ppm) < 1000 and 'ppm' in df.columns:
            df = df[df['ppm'].fillna(1000).abs() <= float(max_ppm)]

        df = df.copy()

        # Format is_preferred
        if 'is_preferred' in df.columns:
            df['is_preferred'] = df['is_preferred'].apply(lambda x: '✓' if x else '')

        # Build tooltips_df for long sequences
        tooltips_data = {}
        if 'sequence' in df.columns:
            mask = df['sequence'].str.len() > _MAX_SEQ_LEN
            if mask.any():
                tooltips_data['sequence'] = df['sequence'].copy()
                df.loc[mask, 'sequence'] = df.loc[mask, 'sequence'].str[:_MAX_SEQ_LEN] + '…'

        if tooltips_data:
            tooltips_df = pd.DataFrame(tooltips_data, index=df.index)
        else:
            tooltips_df = None

        return df, tooltips_df

    async def get_total_count(self) -> int:
        kwargs = self._build_filter_kwargs()
        return await self.project.count_joined_peptide_data(**kwargs)
