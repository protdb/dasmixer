from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from dasmixer.api.reporting._icons import Icons
from dasmixer.utils.logger import logger

from ..base import BaseReport

if TYPE_CHECKING:
    import plotly.graph_objects as go


class ToolMatchReport(BaseReport):
    name = "Tool Match"
    description = "Shows increase in identifications between two selected tools"
    icon = Icons.PIE_CHART
    both_color = 'yellow'
    parameters = None

    async def _get_proteins_data(self, tools: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Protein list is taken from ``protein_identification_result`` (the set
        of identified proteins). All preferred identifications are fetched from
        the DB and then filtered in python to those proteins; within this
        filtered set PSMs are counted per tool to classify each protein as
        Both / tool1 / tool2.
        """
        tool1, tool2 = tools

        # 1. Unique proteins from protein_identification_result
        identified_proteins = await self.project.get_identified_proteins()
        if not identified_proteins:
            empty = pd.DataFrame(columns=['protein_id', 'tool', 'occur', 'uq_evidences'])
            return self._merge_and_classify_proteins(empty, tool1, tool2)
        protein_set = set(identified_proteins)

        # 2. All preferred identifications
        preferred = await self.project.get_joined_peptide_data(
            is_preferred=True,
            sequence_identified=True,
            protein_identified=True,
        )

        # 3. Filter to proteins present in protein_identification_result (in python)
        preferred = preferred[preferred['protein_id'].isin(protein_set)]

        # 4. Count PSMs per (protein, tool)
        if preferred.empty:
            all_proteins = pd.DataFrame(columns=['protein_id', 'tool', 'occur', 'uq_evidences'])
        else:
            all_proteins = (
                preferred.groupby(['protein_id', 'tool'])
                .agg(
                    occur=('matched_sequence', 'size'),
                    uq_evidences=('unique_evidence', 'sum'),
                )
                .reset_index()
                [['protein_id', 'tool', 'occur', 'uq_evidences']]
            )

        return self._merge_and_classify_proteins(all_proteins, tool1, tool2)

    @staticmethod
    def _merge_and_classify_proteins(
        all_proteins: pd.DataFrame,
        tool1: str,
        tool2: str,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Outer-join two tool slices and assign 'Both' / tool1 / tool2 label."""
        proteins_combined = pd.merge(
            all_proteins.query('tool==@tool1'),
            all_proteins.query('tool==@tool2'),
            on='protein_id',
            how='outer',
            suffixes=('_t1', '_t2'),
        )

        def get_protein_tool(row):
            if row['tool_t1'] == tool1 and row['tool_t2'] == tool2:
                return 'Both'
            if row['tool_t1'] == tool1:
                return tool1
            return tool2

        proteins_combined['tool'] = proteins_combined.apply(get_protein_tool, axis=1)
        protein_count = proteins_combined['tool'].value_counts().reset_index(name='cnt')

        return proteins_combined, protein_count

    def _get_peptides_data(self, data: pd.DataFrame, tools: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
        tool1, tool2 = tools
        all_peptides = data[
            ['sample_id', 'seq_no', 'ppm', 'tool', 'identification_id', 'canonical_sequence', 'matched_sequence', 'is_preferred', 'identity', 'unique_evidence']
        ].sort_values(by='identity').drop_duplicates(subset=[
            'identification_id', 'tool'
        ])
        def agg_proteins_list(s: pd.Series) -> str:
            return ', '.join(s.tolist())
        proteins_for_id = data.groupby(['identification_id'])['protein_id'].agg(agg_proteins_list).reset_index(name='proteins')
        logger.debug(proteins_for_id)
        all_peptides = pd.merge(all_peptides, proteins_for_id, on='identification_id', how='outer')
        t1_df = all_peptides.query('tool==@tool1').copy()
        t2_df = all_peptides.query('tool==@tool2').copy()
        merged = pd.merge(
            t1_df,
            t2_df,
            how='outer',
            on=['sample_id', 'seq_no'],
            suffixes=('_t1', '_t2')
        ).query(
            "(is_preferred_t1==1 or is_preferred_t2==1)"
        ).copy()
        merged['sequences_match'] = merged['matched_sequence_t1'] == merged['matched_sequence_t2']

        def nan_to_none(val) -> bool:
            if type(val) is float:
                return not np.isnan(val)
            return bool(val)

        merged['is_preferred_t1'] = merged['is_preferred_t1'].apply(nan_to_none)
        merged['is_preferred_t2'] = merged['is_preferred_t2'].apply(nan_to_none)

        def get_peptide_tool(row):
            if row['sequences_match']:
                return 'Both'
            if row['is_preferred_t1'] == 1:
                return tool1
            return tool2

        merged['tool'] = merged.apply(get_peptide_tool, axis=1)
        merged['seq'] = merged.apply(
            lambda r: r['matched_sequence_t1'] if r['is_preferred_t1'] else r['matched_sequence_t2'],
            axis=1
        )

        anls = merged[['seq', 'tool']].drop_duplicates()
        logger.debug(anls)
        peptide_win = anls['tool'].value_counts().reset_index(name='cnt')
        return merged, peptide_win

    async def _generate_impl(
        self,
        params: dict
    ) -> tuple[list[tuple[str, go.Figure]], list[tuple[str, pd.DataFrame, bool]]]:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        logger.debug(params)
        tool1 = str(params['tool1'])
        tool2 = str(params['tool2'])
        tools = [tool1, tool2]
        logger.debug('loading data...')
        joined_data = await self.project.get_joined_peptide_data(
            sequence_identified=True,
            protein_identified=True,
        )

        peptides, peptide_stats = self._get_peptides_data(joined_data, tools)
        proteins, protein_stats = await self._get_proteins_data(tools)

        chart = make_subplots(
            rows=1,
            cols=2,
            column_titles=['Peptide identifications', 'Protein identifications'],
            specs=[[{'type': 'domain'}, {'type': 'domain'}]]
        )
        tool_reg = await self.project.get_tools()

        colors = {t.name: t.display_color for t in tool_reg if t.name in tools}
        colors['Both'] = self.both_color

        chart.add_trace(go.Pie(
            values=list(peptide_stats['cnt']),
            labels=list(peptide_stats['tool']),
            marker = {
                'colors': [colors[x] for x in list(peptide_stats['tool'])],
            },
            textinfo='label+value'
        ), col=1, row=1)
        chart.add_trace(go.Pie(
            values=list(protein_stats['cnt']),
            labels=list(protein_stats['tool']),
            marker={
                'colors': [colors[x] for x in list(protein_stats['tool'])],
            },
            textinfo='label+value'
        ), col=2, row=1)
        return [
            ('Occurence charts', chart)
        ], [
            ('Peptides', peptides, False),
            ('Proteins', proteins, False),
            ('Peptide counts', peptide_stats, True),
            ('Protein counts', protein_stats, True)
        ]


from ..registry import registry

registry.register(ToolMatchReport)
