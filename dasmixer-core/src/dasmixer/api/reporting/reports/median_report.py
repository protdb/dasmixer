import pandas as pd
import plotly.graph_objects as go
from ..base import BaseReport

class MedianReport(BaseReport):
    """Median Report class."""

    name = "Basic statistics"
    description = "Creates table with common statistic parameters (mean, median, variance etc per subset"

    async def _get_data(self, lfq_type, lfq_measure, subsets) -> pd.DataFrame:
        data = await self.project.get_protein_quantification_data(
            method=lfq_type,
            subsets=subsets,
        )
        sample_data = await self.project.execute_query_df(
            """
            select
              sb.name as subset_name,
              sb.id as subset_id,
              s.cnt as sample_count
            FROM
              subset sb,
              (select subset_id, count() as cnt from sample group by subset_id) as s
            WHERE
              s.subset_id = sb.id
            """
        )
        sample_counts = {}
        for _, row in sample_data.iterrows():
            if subsets is not None and row['subset_name'] in subsets:
                sample_counts[row['subset_name']] = row['sample_count']
        data['value'] = data[lfq_measure]
        uq_proteins = data[['protein_id', 'protein_name', 'gene']].drop_duplicates()
        all_samples = len(data['sample_id'].unique())

        results = []
        for _, protein_row in uq_proteins.iterrows():
            sub_df = data[data['protein_id'] == protein_row['protein_id']]
            res = {
                ('protein','ID'): protein_row['protein_id'],
                ('protein', 'Name'): protein_row['protein_name'],
                ('protein', 'Gene'): protein_row['gene'],
                ('protein', 'Total samples'): len(sub_df),
                ('protein', '% of all samples'): len(sub_df) / all_samples * 100,
            }
            for subset in subsets:
                subset_subdf = sub_df.query(f'subset==@subset')
                res[(subset, 'Samples')] = len(subset_subdf)
                res[(subset, '% of total samples')] = len(subset_subdf) / len(sub_df) * 100
                res[(subset, '% of subset_samples')] = len(subset_subdf) / sample_counts[subset] * 100
                res[(subset, 'Mean')] = subset_subdf['value'].mean()
                res[(subset, 'Median')] = subset_subdf['value'].median()
                res[(subset, 'STD')] = subset_subdf['value'].std()
                res[(subset, 'Min')] = subset_subdf['value'].min()
                res[(subset, 'Max')] = subset_subdf['value'].max()
                res[(subset, 'Variance')] = subset_subdf['value'].var()
                res[(subset, 'CV')] = subset_subdf['value'].std() / subset_subdf['value'].mean()
                res[(subset, 'Skew')] = subset_subdf['value'].skew()
                res[(subset, 'Kurtosis')] = subset_subdf['value'].kurtosis()
            results.append(res)
        df = pd.json_normalize(results)
        df.columns = pd.MultiIndex.from_tuples(list(df.columns))
        return df




    async def _generate_impl(
        self,
        params: dict
    ) -> tuple[list[tuple[str, go.Figure]], list[tuple[str, pd.DataFrame, bool]]]:
        lfq_value = params.get('lfq', ('emPAI', 'rel_value'))
        if isinstance(lfq_value, (tuple, list)) and len(lfq_value) == 2:
            lfq_type = lfq_value[0]
            lfq_measure = lfq_value[1]
        else:
            lfq_type = str(lfq_value)
            lfq_measure = 'rel_value'
        df = await self._get_data(lfq_type, lfq_measure, params.get('subsets', None))
        df.columns = [f"{col[0]}_{col[1]}" for col in df.columns]
        return [], [('Full statistic offload', df, False)]

from ..registry import registry
registry.register(MedianReport)