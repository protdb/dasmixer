import pandas as pd
import plotly.graph_objects as go
from ..base import BaseReport

class MedianReport(BaseReport):
    """Median Report class."""

    name = "Basic statistics"
    description = "Creates table with common statistic parameters (mean, median, variance etc per subset"

    async def _get_data(
        self, lfq_type, lfq_measure, subsets, exclude_outliers: bool = True
    ) -> pd.DataFrame:
        data = await self.project.get_protein_quantification_data(
            method=lfq_type,
            subsets=subsets if subsets else None,
            exclude_outliers=exclude_outliers,
        )
        if data.empty:
            return pd.DataFrame()

        # Normalize subsets: None / empty list → all subsets present in data.
        if not subsets:
            subsets = list(data['subset'].dropna().unique())

        # True sample counts per subset (excluding outliers by default),
        # used as denominators for "% of subset_samples".
        sample_counts = await self.project.get_subset_sample_counts(
            exclude_outliers=exclude_outliers, subsets=subsets
        )

        data['value'] = data[lfq_measure]
        uq_proteins = data[['protein_id', 'protein_name', 'gene']].drop_duplicates()
        all_samples = len(data['sample_id'].unique()) or 1

        results = []
        for _, protein_row in uq_proteins.iterrows():
            sub_df = data[data['protein_id'] == protein_row['protein_id']]
            protein_total = len(sub_df)
            res = {
                ('protein', 'ID'): protein_row['protein_id'],
                ('protein', 'Name'): protein_row['protein_name'],
                ('protein', 'Gene'): protein_row['gene'],
                ('protein', 'Total samples'): protein_total,
                ('protein', '% of all samples'): protein_total / all_samples * 100,
            }
            for subset in subsets:
                subset_subdf = sub_df.query('subset==@subset')
                n_sub = len(subset_subdf)
                sub_total = sample_counts.get(subset, 0)
                values = subset_subdf['value']
                mean_val = values.mean()
                res[(subset, 'Samples')] = n_sub
                res[(subset, '% of total samples')] = (
                    n_sub / protein_total * 100 if protein_total > 0 else 0
                )
                res[(subset, '% of subset_samples')] = (
                    n_sub / sub_total * 100 if sub_total > 0 else 0
                )
                res[(subset, 'Mean')] = mean_val
                res[(subset, 'Median')] = values.median()
                res[(subset, 'STD')] = values.std()
                res[(subset, 'Min')] = values.min()
                res[(subset, 'Max')] = values.max()
                res[(subset, 'Variance')] = values.var()
                # CV undefined when mean is 0 / NaN — leave as None instead of inf/NaN.
                if mean_val is not None and not pd.isna(mean_val) and mean_val != 0:
                    res[(subset, 'CV')] = values.std() / mean_val
                else:
                    res[(subset, 'CV')] = None
                res[(subset, 'Skew')] = values.skew()
                res[(subset, 'Kurtosis')] = values.kurtosis()
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
        include_outliers = bool(params.get('include_outliers', False))
        exclude_outliers = not include_outliers
        df = await self._get_data(
            lfq_type, lfq_measure, params.get('subsets', None),
            exclude_outliers=exclude_outliers,
        )
        if not df.empty:
            df.columns = [f"{col[0]}_{col[1]}" for col in df.columns]
        return [], [('Full statistic offload', df, False)]

from ..registry import registry
registry.register(MedianReport)