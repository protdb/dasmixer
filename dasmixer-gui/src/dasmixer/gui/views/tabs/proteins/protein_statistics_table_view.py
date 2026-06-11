"""Table view for aggregated protein statistics."""

import flet as ft
import pandas as pd

from dasmixer.gui.components.base_table_view import BaseTableView
from dasmixer.api.project.project import Project
from dasmixer.utils.show_pathways import (
    get_pathways_from_uniprot,
    get_mol_functions_from_uniprot,
    get_biological_processes_from_uniprot,
    get_locations_from_uniprot,
)


VIRTUAL_FIELD_FUNCS: dict[str, callable] = {
    'pathways': get_pathways_from_uniprot,
    'mol_functions': get_mol_functions_from_uniprot,
    'bio_processes': get_biological_processes_from_uniprot,
    'subcellular_locations': get_locations_from_uniprot,
}


class ProteinStatisticsTableView(BaseTableView):
    """Aggregated protein statistics table."""

    table_view_name = "protein_statistics"
    plot_id_field = "protein_id"

    header_name_mapping = {
        'protein_id': 'Protein ID',
        'gene': 'Gene',
        'fasta_name': 'FASTA Name',
        'samples': 'Samples',
        'subsets': 'Groups',
        'PSMs': 'PSMs',
        'unique_evidence': 'Unique Evidence',
        'name': 'Protein Name',
        'taxon_id': 'Taxon ID',
        'organism_name': 'Organism',
        'pathways': 'Pathways',
        'mol_functions': 'Molecular Functions',
        'bio_processes': 'Biological Processes',
        'subcellular_locations': 'Subcellular Locations',
    }

    column_filter_mapping = {
        'protein_id': 'protein_id',
        'gene': 'gene',
    }

    default_columns = {
        'protein_id', 'gene', 'name', 'samples', 'subsets', 'PSMs', 'unique_evidence', 'subcellular_locations',
    }

    def __init__(self, project: Project, plot_callback=None):
        super().__init__(project, title="Protein Statistics (Aggregated)", plot_callback=plot_callback)

    def get_default_filters(self) -> dict:
        return {
            'protein_id': '',
            'gene': '',
            'fasta_name': '',
            'min_samples': 0,
            'min_subsets': 0,
            'only_identified': True,
        }

    def _build_filter_view(self) -> ft.Control:
        self.protein_id_field = ft.TextField(
            label="Protein ID contains", value="", width=200
        )
        self.gene_field = ft.TextField(
            label="Gene contains", value="", width=200
        )
        self.fasta_name_field = ft.TextField(
            label="FASTA name contains", value="", width=250
        )
        self.min_samples_field = ft.TextField(
            label="Min Samples", value="0",
            width=150, keyboard_type=ft.KeyboardType.NUMBER
        )
        self.min_subsets_field = ft.TextField(
            label="Min Groups", value="0",
            width=150, keyboard_type=ft.KeyboardType.NUMBER
        )
        self.only_identified_cb = ft.Checkbox(
            label="Only identified (≥1 sample)",
            value=True
        )

        self.filter_controls = {
            'protein_id': self.protein_id_field,
            'gene': self.gene_field,
        }

        return ft.Column([
            ft.Row([self.protein_id_field, self.gene_field], spacing=10),
            ft.Row([self.fasta_name_field], spacing=10),
            ft.Row([self.min_samples_field, self.min_subsets_field, self.only_identified_cb], spacing=10)
        ], spacing=10)

    async def _update_filters_from_ui(self):
        self.filter['protein_id'] = self.protein_id_field.value or ''
        self.filter['gene'] = self.gene_field.value or ''
        self.filter['fasta_name'] = self.fasta_name_field.value or ''
        self.filter['min_samples'] = _parse_int(self.min_samples_field.value)
        self.filter['min_subsets'] = _parse_int(self.min_subsets_field.value)
        self.filter['only_identified'] = bool(self.only_identified_cb.value)

    def _build_filter_kwargs(self) -> dict:
        return {
            'protein_id': self.filter.get('protein_id', ''),
            'gene': self.filter.get('gene', ''),
            'fasta_name': self.filter.get('fasta_name', ''),
            'min_samples': self.filter.get('min_samples', 0),
            'min_subsets': self.filter.get('min_subsets', 0),
            'only_identified': self.filter.get('only_identified', True),
        }

    async def get_data(self, limit: int = 100, offset: int = 0) -> tuple[pd.DataFrame, pd.DataFrame | None]:
        kwargs = self._build_filter_kwargs()
        try:
            if limit == -1:
                df = await self.project.get_protein_statistics(**kwargs, limit=-1, offset=0)
            else:
                df = await self.project.get_protein_statistics(**kwargs, limit=limit, offset=offset)
        except Exception:
            import traceback
            traceback.print_exc()
            return pd.DataFrame(columns=list(self.header_name_mapping.keys())), None

        # Вычисляем виртуальные поля из uniprot_data
        tooltip_data = {
            'fasta_name': df['fasta_name'].to_list()
        }
        for vfield, func in VIRTUAL_FIELD_FUNCS.items():
            display_vals = []
            tooltip_vals = []
            for uniprot_obj in df.get('uniprot_data', pd.Series(dtype=object)):
                if uniprot_obj is not None:
                    disp, tip = func(uniprot_obj)
                else:
                    disp, tip = None, None
                display_vals.append(disp)
                tooltip_vals.append(tip)
            df[vfield] = display_vals
            tooltip_data[vfield] = tooltip_vals

        # Убираем служебную колонку перед отображением
        if 'uniprot_data' in df.columns:
            df = df.drop(columns=['uniprot_data'])
        df['fasta_name'] = df['fasta_name'].apply(lambda x: x if len(x) <= 32 else x[:30]+'…')

        # Строим tooltip_df для виртуальных полей
        if tooltip_data:
            tooltip_df = pd.DataFrame(tooltip_data, index=df.index)
        else:
            tooltip_df = None

        return df, tooltip_df

    async def get_total_count(self) -> int:
        kwargs = self._build_filter_kwargs()
        try:
            return await self.project.count_protein_statistics(**kwargs)
        except Exception as ex:
            import traceback
            traceback.print_exc()
            return 0


def _parse_int(value, default: int = 0) -> int:
    """Safely parse integer from string input."""
    try:
        return int(value or default)
    except (ValueError, TypeError):
        return default
