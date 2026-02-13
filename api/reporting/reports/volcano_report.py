import numpy as np
import pandas as pd
import plotly.express as px
from flet import Icons
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy.stats import false_discovery_control, mannwhitneyu, ttest_ind
from ..base import BaseReport
from smart_round import format_dataframe

class VolcanoReport(BaseReport):
    name = "Volcano Report (not conected)"
    description = "Reporting FC/p-value changes and Volcano plots"
    icon = Icons.VOLCANO

    @staticmethod
    def get_parameter_defaults() -> dict[str, tuple[type, str]]:
        return {
            'control_subset': (str, 'Control'),
            'exptl_subsets': (str, 'subset1,subset2'),
            'lfq_type': (str, 'emPAI'),
            'stats_method': (str, 'Mann-Whitney'),
            'fdc': (str, 'BH'),
            'percent_to_caculate': (int, 20),
            'fc_threshold': (float, '1.5'),
            'p_threshold': (float, '0.05'),
        }

    async def get_data(self, lfq_type: str, subsets: list[str]) -> pd.DataFrame:
        return await self.project.get_protein_quantification_data(
            method=lfq_type, subsets=subsets
        )

    async def draw_plot(self, data: pd.DataFrame, p_threshold: float, fc_threshold_log2: float) -> go.Figure:
        subsets = await self.project.get_subsets()
        subset_colors = {x.name: x.display_color for x in subsets}
        df = data.copy()
        df.columns = ['protein_id', 'subset', 'p_value', 'fc', 'fc_log2']
        
        fig = go.Figure()
        
        # Отрисовываем точки для каждого subset
        for subset in df['subset'].unique():
            subset_data = df[df['subset'] == subset].copy()
            print(subset)
            print(subset_data)
            
            # Получаем цвет для текущего subset
            color = subset_colors.get(subset, '#808080')
            
            # Добавляем scatter plot для этого subset
            fig.add_trace(go.Scatter(
                x=subset_data['fc_log2'].values,
                y=subset_data['p_value'].values,
                mode='markers',
                name=subset,
                marker=dict(
                    color=color,
                    size=20,
                    opacity=0.8
                ),
                customdata=np.column_stack((
                    subset_data['protein_id'].values,
                    subset_data['fc'].values  # Оригинальный FC (не log2) для hover
                )),
                hovertemplate=(
                    '<b>%{customdata[0]}</b><br>' +
                    'Fold Change: %{customdata[1]:.3f}<br>' +
                    'Log2(FC): %{x:.3f}<br>' +
                    'P-value: %{y:.4g}<br>' +
                    '<extra></extra>'
                )
            ))
        
        # Добавляем горизонтальную линию для порога p-value
        fig.add_hline(
            y=p_threshold,
            line_dash="dash",
            line_color="red",
            annotation_text=f"p={p_threshold}",
            annotation_position="right"
        )
        
        # Добавляем вертикальные линии для порогов fold change
        # Положительная линия (увеличение)
        fig.add_vline(
            x=fc_threshold_log2,
            line_dash="dash",
            line_color="blue",
            annotation_text=f"FC={2**fc_threshold_log2:.2f}",
            annotation_position="top"
        )
        
        # Отрицательная линия (уменьшение)
        fig.add_vline(
            x=-fc_threshold_log2,
            line_dash="dash",
            line_color="blue",
            annotation_text=f"FC={2**(-fc_threshold_log2):.2f}",
            annotation_position="top"
        )
        
        # Настройка осей
        fig.update_xaxes(
            title_text="Log2 Fold Change",
            zeroline=True,
            zerolinewidth=1,
            zerolinecolor='gray'
        )
        
        fig.update_yaxes(
            title_text="P-value",
            type="log",  # Логарифмическая шкала
            zeroline=False,
            autorange="reversed"  # Меньшие p-values выше
        )
        
        # Настройка заголовка и легенды
        fig.update_layout(
            title="Volcano Plot",
            showlegend=True,
            hovermode='closest'
        )
        
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
        control_subset = params['control_subset']
        exptl_subsets = params['exptl_subsets'].split(',')
        all_subsets = exptl_subsets + [control_subset]

        calc_share = params['percent_to_caculate'] / 100
        criteria = params['stats_method']

        fc_threshold = params['fc_threshold']
        fc_threshold_log2 = np.log2(fc_threshold)
        p_threshold = params['p_threshold']

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
            res = {
                'protein_id': protein,
            }
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
        fig = await self.draw_plot(
            figure_df,
            params['p_threshold'],
            fc_threshold_log2  # Исправлено: передаём log2 значение
        )
        return [
            ('Volcano Plot', fig)
        ], [
            ('FC table', calculated, False),
            ('POI', format_dataframe(pois), False),
        ]

from ..registry import registry
registry.register(VolcanoReport)