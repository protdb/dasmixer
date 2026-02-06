import pandas as pd
import plotly.express as px
from flet import Icons
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from ..base import BaseReport


class ToolMatchReport(BaseReport):
    name = "Tool Match"
    description = "Sows increase in identifications between two selected tools"
    icon = Icons.PIE_CHART
    both_color = 'yellow'

    @staticmethod
    def get_parameter_defaults() -> dict[str, tuple[type, str]]:
        return {
            'tool1': (str, 'Library'),
            'tool2': (str, 'Denovo'),
            'min_psm': (int, 1),
        }

    async def _generate_impl(
        self,
        params: dict
    ) -> tuple[list[tuple[str, go.Figure]], list[tuple[str, pd.DataFrame, bool]]]:
        tool1 = params['tool1']
        tool2 = params['tool2']
        tools = [tool1, tool2]
        min_psm = params['min_psm']
        print('loading data...')
        joined_data = await self.project.get_joined_peptide_data(
            sequence_identified=True
        )
        min_peptides = int(await self.project.get_setting('proteins_min_peptides', '2'))
        min_uq = int(await self.project.get_setting('proteins_min_unique_evidence', '1'))
        all_proteins = joined_data.query('protein_id==protein_id and is_preferred==1')[['protein_id', 'tool', 'unique_evidence']]
        all_proteins['occur'] = all_proteins.groupby('protein_id')['protein_id'].transform('size')
        all_proteins['uq_evidences'] = all_proteins.groupby('protein_id')['unique_evidence'].transform('sum')
        all_proteins = all_proteins[['protein_id', 'tool', 'occur', 'uq_evidences']].drop_duplicates().query(
            "occur >= @min_peptides and uq_evidences >= @min_uq"
        )
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
        joined_data = joined_data.query("tool==@tools")[
            ['sample_id', 'seq_no', 'tool', 'identification_id', 'sequence', 'canonical_sequence', 'is_preferred', 'protein_id']
        ].drop_duplicates()
        t1_df = joined_data.query("tool==@tool1")
        t1_df['seq_occur'] = t1_df.groupby('canonical_sequence')['canonical_sequence'].transform('size')
        t2_df = joined_data.query("tool==@tool2")
        t2_df['seq_occur'] = t2_df.groupby('canonical_sequence')['canonical_sequence'].transform('size')
        merged = pd.merge(
            t1_df,
            t2_df,
            how='outer',
            on=['sample_id', 'seq_no'],
            suffixes=('_t1', '_t2')
        )
        merged = merged.query("is_preferred_t1==1 or is_preferred_t2==1").query("seq_occur_t1 >= @min_psm or seq_occur_t2 >= @min_psm")
        merged['sequences_match'] = merged['canonical_sequence_t1'] == merged['canonical_sequence_t2']

        def get_peptide_tool(row):
            if row['sequences_match']:
                return 'Both'
            if row['is_preferred_t1'] == 1:
                return tool1
            return tool2

        merged['tool_win'] = merged.apply(get_peptide_tool, axis=1)
        merged['seq_win'] = merged.apply(
            lambda r: r['canonical_sequence_t1'] if r['is_preferred_t1'] else r['canonical_sequence_t2'], axis=1)
        anls = merged[['seq_win', 'tool_win']].drop_duplicates()
        print(anls)
        peptide_win = anls['tool_win'].value_counts().reset_index(name='cnt')

        print(peptide_win)
        print(protein_count)
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
            values=list(peptide_win['cnt']),
            labels=list(peptide_win['tool_win']),
            marker = {
                'colors': [colors[x] for x in list(peptide_win['tool_win'])],
            },
            textinfo='label+value'
        ), col=1, row=1)
        chart.add_trace(go.Pie(
            values=list(protein_count['cnt']),
            labels=list(protein_count['tool']),
            marker={
                'colors': [colors[x] for x in list(protein_count['tool'])],
            },
            textinfo='label+value'
        ), col=2, row=1)
        return [
            ('Occurence charts', chart)
        ], [
            ('Peptides', merged, False),
            ('Proteins', proteins_combined, False),
            ('Peptide counts', peptide_win, True),
            ('Protein counts', protein_count, True)
        ]


from ..registry import registry
registry.register(ToolMatchReport)