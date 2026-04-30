import numpy as np
import pandas as pd
import plotly.express as px
from flet import Icons
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ..base import BaseReport
from dasmixer.gui.components.report_form import ReportForm, ToolSelector, IntSelector, BoolSelector
from dasmixer.utils.logger import logger


class ToolMatchReportForm(ReportForm):
    tool1 = ToolSelector(label="Tool 1 (Library)")
    tool2 = ToolSelector(label="Tool 2 (De Novo)")
    min_psm = IntSelector(default=1, label="Min PSM count")
    min_unique_psm = IntSelector(default=1, label="Min unique PSM count")
    count_per_sample = BoolSelector(
        default=False,
        label="Count unique peptides per sample (matches UpSet/PIR logic)",
    )


class ToolMatchReport(BaseReport):
    name = "Tool Match"
    description = "Shows increase in identifications between two selected tools"
    icon = Icons.PIE_CHART
    both_color = 'yellow'
    parameters = ToolMatchReportForm

    def _get_proteins_data(self, data: pd.DataFrame, tools: list[str], min_peptides: int, min_uq: int, min_unique_psm: int = 1) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Original logic: counts total PSM rows per protein_id across all tools
        combined (via groupby transform). min_peptides applies to that combined
        PSM count, not to unique peptides per sample.
        """
        tool1, tool2 = tools
        all_proteins = data.query('is_preferred==1')[['protein_id', 'tool', 'unique_evidence']]
        all_proteins['occur'] = all_proteins.groupby('protein_id')['protein_id'].transform('size')
        all_proteins['uq_evidences'] = all_proteins.groupby('protein_id')['unique_evidence'].transform('sum')
        all_proteins = all_proteins[['protein_id', 'tool', 'occur', 'uq_evidences']].drop_duplicates().query(
            "occur >= @min_peptides and uq_evidences >= @min_uq and uq_evidences >= @min_unique_psm"
        )

        return self._merge_and_classify_proteins(all_proteins, tool1, tool2)

    def _get_proteins_data_per_sample(self, data: pd.DataFrame, tools: list[str], min_peptides: int, min_uq: int, min_unique_psm: int = 1) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Per-sample logic: mirrors protein_identification_result criteria.

        A protein passes the filter for a given tool if there exists at least
        one sample in which that tool identified it with:
          - >= min_peptides unique matched_sequences
          - >= min_uq unique-evidence peptides (unique_evidence == 1)
          - >= min_unique_psm unique-evidence peptides (same threshold, per sample)

        This produces counts consistent with UpSet Plot / protein_identification_result.
        """
        tool1, tool2 = tools
        preferred = data.query('is_preferred==1')[
            ['protein_id', 'tool', 'sample_id', 'matched_sequence', 'unique_evidence']
        ]

        # Per (protein, tool, sample): count unique peptides and unique-evidence peptides
        per_sample = (
            preferred
            .groupby(['protein_id', 'tool', 'sample_id'])
            .agg(
                uniq_pep=('matched_sequence', 'nunique'),
                uq_ev=('unique_evidence', 'sum'),
            )
            .reset_index()
        )

        # A protein qualifies for a tool if ANY sample passes all thresholds
        qualifies = per_sample.query(
            "uniq_pep >= @min_peptides and uq_ev >= @min_uq and uq_ev >= @min_unique_psm"
        )

        # Collapse to one row per (protein, tool) — keep best-sample stats for display
        _tmp = qualifies.sort_values('uniq_pep', ascending=False).drop_duplicates(
            subset=['protein_id', 'tool']
        )
        best = pd.DataFrame({
            'protein_id': _tmp['protein_id'].values,
            'tool': _tmp['tool'].values,
            'occur': _tmp['uniq_pep'].values,
            'uq_evidences': _tmp['uq_ev'].values,
        })

        return self._merge_and_classify_proteins(best, tool1, tool2)

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

    def _get_peptides_data(self, data: pd.DataFrame, min_psm: int, min_unique_psm: int, tools: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
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
        t1_df['seq_occur'] = t1_df.groupby('matched_sequence')['matched_sequence'].transform('size')
        t1_df['seq_uq_occur'] = t1_df.groupby('matched_sequence')['unique_evidence'].transform('sum')
        t2_df = all_peptides.query('tool==@tool2').copy()
        t2_df['seq_occur'] = t2_df.groupby('matched_sequence')['matched_sequence'].transform('size')
        t2_df['seq_uq_occur'] = t2_df.groupby('matched_sequence')['unique_evidence'].transform('sum')
        merged = pd.merge(
            t1_df,
            t2_df,
            how='outer',
            on=['sample_id', 'seq_no'],
            suffixes=('_t1', '_t2')
        ).query(
            "(is_preferred_t1==1 or is_preferred_t2==1) and "
            "(seq_occur_t1 >= @min_psm or seq_occur_t2 >= @min_psm) and "
            "(seq_uq_occur_t1 >= @min_unique_psm or seq_uq_occur_t2 >= @min_unique_psm)"
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
        logger.debug(params)
        tool1 = str(params['tool1'])
        tool2 = str(params['tool2'])
        tools = [tool1, tool2]
        min_psm = int(params['min_psm'])
        min_unique_psm = int(params['min_unique_psm'])
        count_per_sample = bool(params.get('count_per_sample', False))
        logger.debug('loading data...')
        joined_data = await self.project.get_joined_peptide_data(
            sequence_identified=True,
            protein_identified=True,
        )
        min_peptides = int(await self.project.get_setting('proteins_min_peptides', '2'))
        min_uq = int(await self.project.get_setting('proteins_min_unique_evidence', '1'))

        peptides, peptide_stats = self._get_peptides_data(joined_data, min_psm, min_unique_psm, tools)

        if count_per_sample:
            proteins, protein_stats = self._get_proteins_data_per_sample(
                joined_data, tools, min_peptides, min_uq, min_unique_psm
            )
        else:
            proteins, protein_stats = self._get_proteins_data(
                joined_data, tools, min_peptides, min_uq, min_unique_psm
            )

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
