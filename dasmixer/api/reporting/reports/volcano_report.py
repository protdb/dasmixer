import numpy as np
import pandas as pd
from flet import Icons
import plotly.graph_objects as go
from scipy.stats import false_discovery_control, mannwhitneyu, ttest_ind

from ..base import BaseReport
from dasmixer.gui.components.report_form import (
    ReportForm,
    SubsetSelector,
    MultiSubsetSelector,
    EnumSelector,
    IntSelector,
    FloatSelector,
)
from smart_round import format_dataframe


class VolcanoReportForm(ReportForm):
    control_subset = SubsetSelector(label="Control subset")
    exptl_subsets = MultiSubsetSelector(label="Experimental subsets")
    lfq_type = EnumSelector(
        values=["emPAI", "iBAQ", "NSAF", "Top3"],
        label="LFQ method",
    )
    stats_method = EnumSelector(
        values=["Mann-Whitney", "T-test"],
        label="Statistical method",
    )
    fdc = EnumSelector(
        values=["BH", "BY", "Bonferroni"],
        label="FDR correction",
    )
    percent_to_calculate = IntSelector(default=20, label="Min % samples with value")
    fc_threshold = FloatSelector(default=1.5, label="FC threshold")
    p_threshold = FloatSelector(default=0.05, label="p-value threshold")


class VolcanoReport(BaseReport):
    name = "Volcano Report (not conected)"
    description = "Reporting FC/p-value changes and Volcano plots"
    icon = Icons.VOLCANO
    parameters = VolcanoReportForm

    async def get_data(self, lfq_type: str, subsets: list[str]) -> pd.DataFrame:
        return await self.project.get_protein_quantification_data(
            method=lfq_type, subsets=subsets
        )

    async def draw_plot(self, data: pd.DataFrame, p_threshold: float, fc_threshold_log2: float) -> go.Figure:
        subsets = await self.project.get_subsets()
        subset_colors = {x.name: x.display_color for x in subsets}
        df = data.copy()
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
    def get_pval(value_list1, value_list2, criteria) -> float:
        if criteria == 'Mann-Whitney':
            return mannwhitneyu(value_list1, value_list2).pvalue
        elif criteria == 'T-test':
            return ttest_ind(value_list1, value_list2).pvalue

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

        fc_threshold = float(params['fc_threshold'])
        fc_threshold_log2 = np.log2(fc_threshold)
        p_threshold = float(params['p_threshold'])

        df = await self.get_data(params['lfq_type'], all_subsets)
        subset_lenghts_df = df[['subset', 'sample']].drop_duplicates(ignore_index=True).groupby('subset').count().reset_index(names='subset')
        print(subset_lenghts_df)
        subset_lenghts = {}
        for _, row in subset_lenghts_df.iterrows():
            subset_lenghts[row['subset']] = row['sample']
        good_proteins = df[['protein_id', 'subset']].groupby(['protein_id', 'subset']).agg('size')
        print(good_proteins)
        good_proteins = good_proteins.reset_index(name='count')
        print(good_proteins)
        good_proteins['subset_size'] = good_proteins['subset'].map(subset_lenghts)
        good_proteins['is_sufficient'] = (good_proteins['count'] / good_proteins['subset_size']) >= calc_share
        print(len(df))
        df = pd.merge(
            df,
            good_proteins[['protein_id', 'subset', 'is_sufficient']],
            on=['protein_id', 'subset'],
            how='left',
        ).query('is_sufficient==True').copy()
        print(len(df))
        result = []
        figure_data = []

        for protein in df['protein_id'].unique():
            ctrl_values = df.query("protein_id==@protein & subset==@control_subset")['rel_value']
            if len(ctrl_values) == 0:
                continue
            print(protein, ctrl_values)
            subsets = []
            p_values = []
            fc_values = []
            samples_no = []
            for subset in exptl_subsets:
                exptl_values = df.query("protein_id==@protein & subset==@subset")['rel_value']
                if len(exptl_values) == 0:
                    continue
                pval = self.get_pval(ctrl_values, exptl_values, criteria)
                if pval is not None and not np.isnan(pval):
                    p_values.append(pval)
                    subsets.append(subset)
                    fc_values.append(exptl_values.median() / ctrl_values.median())
                    samples_no.append(len(exptl_values))
            p_vals_corr = list(false_discovery_control(p_values))
            res = {'protein_id': protein}
            for idx in range(len(subsets)):
                res[f'{subsets[idx]}_pval'] = p_vals_corr[idx]
                res[f'{subsets[idx]}_fc'] = fc_values[idx]
                res[f'{subsets[idx]}_pval_uncorr'] = p_values[idx]
                res[f'{subsets[idx]}_fc_log2'] = np.log2(fc_values[idx])
                res[f'{subsets[idx]}_samples'] = samples_no[idx]
                res[f'{subsets[idx]}_samples_perc'] = samples_no[idx] / subset_lenghts[subsets[idx]] * 100

                figure_data.append({
                    'protein_id': protein,
                    'subset': subsets[idx],
                    'pval': p_vals_corr[idx],
                    'fc': fc_values[idx],
                    'fc_log2': np.log2(fc_values[idx])
                })
            result.append(res)
        calculated = pd.json_normalize(result)

        def get_min_pval(row):
            try:
                return min(row[x] for x in row.keys() if x.endswith('_pval'))
            except ValueError:
                print(row)
                return None

        def get_max_fc_log2(row):
            try:
                return max(abs(row[x]) for x in row.keys() if x.endswith('_fc_log2'))
            except ValueError:
                print(row)
                return None

        calculated['max_fc'] = calculated.apply(lambda row: get_max_fc_log2(row.to_dict()), axis=1)
        calculated['min_pval'] = calculated.apply(lambda row: get_min_pval(row.to_dict()), axis=1)

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
