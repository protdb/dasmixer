from __future__ import annotations

import numpy as np
import pandas as pd
from dasmixer.api.reporting._icons import Icons
from scipy.stats import false_discovery_control, mannwhitneyu, ttest_ind
import plotly.graph_objects as go
from ..base import BaseReport
from smart_round import format_dataframe


class VolcanoReport(BaseReport):
    name = "Volcano Report (independent)"
    description = "Reporting FC/p-value changes and Volcano plots"
    icon = Icons.VOLCANO
    parameters = None

    async def get_data(
        self, lfq_type: str, subsets: list[str], exclude_outliers: bool = True
    ) -> pd.DataFrame:
        return await self.project.get_protein_quantification_data(
            method=lfq_type, subsets=subsets, exclude_outliers=exclude_outliers
        )

    async def draw_plot(self, data: pd.DataFrame, p_threshold: float, fc_threshold_log2: float) -> go.Figure:
        import plotly.graph_objects as go

        subsets = await self.project.get_subsets()
        subset_colors = {x.name: x.display_color for x in subsets}
        df = data.copy()
        if df.empty or len(df.columns) != 5:
            raise ValueError(
                "No valid data points to draw the Volcano plot "
                "(no protein passed the statistical test with finite values)."
            )
        df.columns = ['protein_id', 'subset', 'p_value', 'fc', 'fc_log2']
        
        # Фильтруем невалидные данные
        df = df[df['p_value'] > 0].copy()
        df = df[~df['p_value'].isna()].copy()
        df = df[~df['fc_log2'].isna()].copy()
        df = df[np.isfinite(df['fc_log2'])].copy()
        
        df['neg_log10_pval'] = -np.log10(df['p_value'])
        df = df[np.isfinite(df['neg_log10_pval'])].copy()
        
        fig = go.Figure()
        
        for subset in df['subset'].unique():
            subset_data = df[df['subset'] == subset].copy()
            color = subset_colors.get(subset, '#808080')
            x_data = subset_data['fc_log2'].tolist()
            y_data = subset_data['neg_log10_pval'].tolist()
            protein_ids = subset_data['protein_id'].tolist()
            fc_data = subset_data['fc'].tolist()
            pval_data = subset_data['p_value'].tolist()
            
            fig.add_trace(go.Scatter(
                x=x_data,
                y=y_data,
                mode='markers',
                name=subset,
                marker=dict(color=color, size=20, opacity=0.6),
                customdata=list(zip(protein_ids, fc_data, pval_data)),
                hovertemplate=(
                    '<b>%{customdata[0]}</b><br>' +
                    'Fold Change: %{customdata[1]:.3f}<br>' +
                    'Log2(FC): %{x:.3f}<br>' +
                    'P-value: %{customdata[2]:.4g}<br>' +
                    '-log10(p): %{y:.3f}<br>' +
                    '<extra></extra>'
                )
            ))
        
        neg_log10_p_threshold = -np.log10(p_threshold)
        fig.add_hline(
            y=neg_log10_p_threshold,
            line_dash="dash",
            line_color="red",
            annotation_text=f"p={p_threshold}",
            annotation_position="right"
        )
        fig.add_vline(
            x=fc_threshold_log2,
            line_dash="dash",
            line_color="blue",
            annotation_text=f"FC={2**fc_threshold_log2:.2f}",
            annotation_position="top"
        )
        fig.add_vline(
            x=-fc_threshold_log2,
            line_dash="dash",
            line_color="blue",
            annotation_text=f"FC={2**(-fc_threshold_log2):.2f}",
            annotation_position="top"
        )
        
        fig.update_xaxes(title_text="Log2 Fold Change", zeroline=True, zerolinewidth=1, zerolinecolor='gray')
        fig.update_yaxes(title_text="-Log10(P-value)", zeroline=False)
        fig.update_layout(title="Volcano Plot", showlegend=True, hovermode='closest')
        
        return fig

    @staticmethod
    def get_pval(value_list1, value_list2, criteria) -> float | None:
        """Return p-value for the chosen test, or None on degenerate input."""
        try:
            if criteria == 'Mann-Whitney':
                return mannwhitneyu(value_list1, value_list2).pvalue
            elif criteria == 'T-test':
                return ttest_ind(value_list1, value_list2).pvalue
        except Exception:
            return None
        return None

    @staticmethod
    def correct_pvals(p_values: list[float], method: str) -> list[float]:
        """
        Apply multiple-testing correction.

        ``BH`` / ``BY`` delegate to scipy.stats.false_discovery_control;
        ``Bonferroni`` is computed manually as p * n clipped to 1.
        Returns the adjusted p-values in the original order.
        """
        if not p_values:
            return []
        n = len(p_values)
        method = (method or 'BH').upper()
        if method == 'BONFERRONI':
            return [min(p * n, 1.0) for p in p_values]
        scipy_method = 'by' if method == 'BY' else 'bh'
        arr = np.asarray(p_values, dtype=float)
        return list(false_discovery_control(arr, method=scipy_method))

    async def _generate_impl(
        self,
        params: dict
    ) -> tuple[list[tuple[str, go.Figure]], list[tuple[str, pd.DataFrame, bool]]]:
        control_subset = str(params['control_subset'])
        # exptl_subsets is now list[str] (from MultiSubsetSelector)
        exptl_subsets: list[str] = params['exptl_subsets']
        if isinstance(exptl_subsets, str):
            # Backward compatibility: old text format "subset1,subset2"
            exptl_subsets = [s.strip() for s in exptl_subsets.split(',') if s.strip()]
        all_subsets = exptl_subsets + [control_subset]

        calc_share = int(params['percent_to_calculate']) / 100
        criteria = str(params['stats_method'])
        fdc = str(params.get('fdc', 'BH'))

        fc_threshold = float(params['fc_threshold'])
        fc_threshold_log2 = np.log2(fc_threshold)
        p_threshold = float(params['p_threshold'])

        lfq_value = params.get('lfq', ('emPAI', 'rel_value'))
        if isinstance(lfq_value, (tuple, list)) and len(lfq_value) == 2:
            lfq_type = lfq_value[0]
            lfq_measure = lfq_value[1]
        else:
            lfq_type = str(lfq_value)
            lfq_measure = 'rel_value'

        include_outliers = bool(params.get('include_outliers', False))
        exclude_outliers = not include_outliers

        df = await self.get_data(lfq_type, all_subsets, exclude_outliers=exclude_outliers)

        # True subset sizes (number of non-outlier samples per subset) from DB.
        # Using the real denominator instead of counting distinct samples in
        # quantification data — the latter undercounts when a sample has no
        # quantified proteins and wrongly includes outliers.
        subset_counts = await self.project.get_subset_sample_counts(
            exclude_outliers=exclude_outliers, subsets=all_subsets
        )
        subset_lenghts = {
            name: subset_counts.get(name, 0) for name in all_subsets
        }

        good_proteins = df[['protein_id', 'subset']].groupby(['protein_id', 'subset']).agg('size')
        good_proteins = good_proteins.reset_index(name='count')
        good_proteins['subset_size'] = good_proteins['subset'].map(subset_lenghts)
        # Guard against a zero denominator (subset has no samples at all).
        good_proteins['is_sufficient'] = good_proteins.apply(
            lambda r: r['subset_size'] > 0
            and (r['count'] / r['subset_size']) >= calc_share,
            axis=1,
        )
        df = pd.merge(
            df,
            good_proteins[['protein_id', 'subset', 'is_sufficient']],
            on=['protein_id', 'subset'],
            how='left',
        ).query('is_sufficient==True').copy()
        result = []
        figure_data = []

        for protein in df['protein_id'].unique():
            ctrl_values = (
                df.query("protein_id==@protein & subset==@control_subset")[lfq_measure]
                .dropna()
                .tolist()
            )
            if len(ctrl_values) == 0:
                continue
            ctrl_median = float(np.median(ctrl_values))
            subsets = []
            p_values = []
            fc_values = []
            samples_no = []
            for subset in exptl_subsets:
                exptl_values = (
                    df.query("protein_id==@protein & subset==@subset")[lfq_measure]
                    .dropna()
                    .tolist()
                )
                if len(exptl_values) == 0:
                    continue
                pval = self.get_pval(ctrl_values, exptl_values, criteria)
                if pval is None or np.isnan(pval):
                    continue
                exptl_median = float(np.median(exptl_values))
                # Fold change is undefined when the control median is zero
                # (division by zero → inf) or NaN — skip this comparison.
                if ctrl_median == 0 or not np.isfinite(ctrl_median) or not np.isfinite(exptl_median):
                    continue
                p_values.append(pval)
                subsets.append(subset)
                fc_values.append(exptl_median / ctrl_median)
                samples_no.append(len(exptl_values))
            if not subsets:
                continue
            p_vals_corr = self.correct_pvals(p_values, fdc)
            res = {'protein_id': protein}
            for idx in range(len(subsets)):
                fc = fc_values[idx]
                fc_l2 = np.log2(fc) if fc > 0 else float('nan')
                res[f'{subsets[idx]}_pval'] = p_vals_corr[idx]
                res[f'{subsets[idx]}_fc'] = fc
                res[f'{subsets[idx]}_pval_uncorr'] = p_values[idx]
                res[f'{subsets[idx]}_fc_log2'] = fc_l2
                res[f'{subsets[idx]}_samples'] = samples_no[idx]
                res[f'{subsets[idx]}_samples_perc'] = (
                    samples_no[idx] / subset_lenghts[subsets[idx]] * 100
                    if subset_lenghts.get(subsets[idx], 0) > 0 else 0
                )

                figure_data.append({
                    'protein_id': protein,
                    'subset': subsets[idx],
                    'pval': p_vals_corr[idx],
                    'fc': fc,
                    'fc_log2': fc_l2,
                })
            result.append(res)
        calculated = pd.json_normalize(result)

        def _row_values(row, suffix):
            """Collect finite floats from row keys ending with ``suffix``."""
            vals = []
            for k, v in row.items():
                if k.endswith(suffix):
                    try:
                        fv = float(v)
                    except (TypeError, ValueError):
                        continue
                    if np.isfinite(fv):
                        vals.append(fv)
            return vals

        def get_min_pval(row):
            vals = _row_values(row, '_pval')
            return min(vals) if vals else None

        def get_max_fc_log2(row):
            vals = _row_values(row, '_fc_log2')
            return max(abs(v) for v in vals) if vals else None

        calculated['max_fc'] = calculated.apply(lambda row: get_max_fc_log2(row.to_dict()), axis=1)
        calculated['min_pval'] = calculated.apply(lambda row: get_min_pval(row.to_dict()), axis=1)
        # Drop rows where no finite FC / p-value could be computed — comparing
        # None/NaN in the query below would otherwise raise on object dtype.
        calculated = calculated.dropna(subset=['max_fc', 'min_pval']).copy()

        pois = calculated.query('min_pval <= @p_threshold & max_fc >= @fc_threshold_log2')
        figure_df = pd.json_normalize(figure_data)
        fig = await self.draw_plot(figure_df, p_threshold, fc_threshold_log2)
        return [
            ('Volcano Plot', fig)
        ], [
            ('FC table', calculated, False),
            ('POI', format_dataframe(pois), False),
        ]


from ..registry import registry
registry.register(VolcanoReport)
