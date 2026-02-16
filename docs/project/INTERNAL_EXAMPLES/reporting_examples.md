# Примеры графиков для новых отчетов

## Upset plot

```python
from itertools import product
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from numpy import isnan

# Создание шаблона графика
template = go.layout.Template()
template.layout.paper_bgcolor = 'white'  # Белый фон
template.layout.font.size = 25  # Размер шрифта для надписей
template.layout.title.font.size = 25  # Размер шрифта для заголовка

# Темно-сервые линии для осей
template.layout.xaxis.gridcolor = 'darkgray'
template.layout.yaxis.gridcolor = 'darkgray'
template.layout.xaxis.linecolor = 'black'
template.layout.xaxis.showline = True
template.layout.yaxis.linecolor = 'black'
template.layout.yaxis.showline = True

def generate_decart(input_list):
    all_combinations = list(product([False, True], repeat=len(input_list)))
    columns = {i: input_list[i] for i in range(len(input_list))}
    df = pd.DataFrame(all_combinations, columns=input_list)
    return df


def place_to_groups(df: pd.DataFrame) -> pd.DataFrame:
    subsets = df['subset'].unique()
    proteins = df['uniprot_id'].unique()
    tgt = []
    for protein in proteins:
        res = {
            'protein': protein,
        }
        for subset in subsets:
            res[subset] = len(df.query('subset == @subset & uniprot_id == @protein'))
        tgt.append(res)
    target_df = pd.json_normalize(tgt)
    elems = []
    for _, row in generate_decart(subsets).iterrows():
        filtered = target_df.copy()
        for idx, subset in enumerate(subsets):
            if row[subset]:
                filtered = filtered.query(f"{subset} > 0").copy()
            else:
                filtered = filtered.query(f"{subset} == 0").copy()
        elem = {k: None if not v else 1 for k, v in row.to_dict().items()}
        elem['name'] = '_'.join([str(x) for x in elem.keys() if elem[x] is not None])
        elem['count'] = len(filtered)
        elems.append(elem)
    elems.sort(key=lambda x: x['count'], reverse=True)
    return pd.json_normalize(elems)


def get_subset_sample_counts(df: pd.DataFrame) -> dict:
    """
    Подсчитывает количество уникальных образцов для каждой группы (subset)
    
    Args:
        df: DataFrame с колонками 'subset', 'uniprot_id', 'sample'
    
    Returns:
        Словарь вида {subset: sample_count}
    """
    subset_counts = {}
    for subset in df['subset'].unique():
        subset_df = df[df['subset'] == subset]
        sample_count = len(subset_df['sample'].unique())
        subset_counts[subset] = sample_count
    return subset_counts


def plot_upset(df: pd.DataFrame) -> go.Figure:
    subsets = df['subset'].unique()
    
    # Получаем количество уникальных образцов для каждой группы
    subset_sample_counts = get_subset_sample_counts(df)
    
    comb_df = place_to_groups(df)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)
    
    # Добавляем столбцы
    x_positions = [x + 1 for x in comb_df.index]
    counts = comb_df['count']
    
    fig.add_trace(go.Bar(
        x=x_positions,
        y=counts,
        text=counts,  # Используем значения count в качестве текста
        textposition='outside',  # Размещаем текст над столбцами
        textfont=dict(
            size=16,  # Размер шрифта для подписей
            color='black'
        ),
        hoverinfo='y'  # Показываем только y-значение при наведении
    ), row=1, col=1)
    
    # Создаем список для хранения названий подмножеств с количеством образцов
    subset_labels = []
    for subset in subsets:
        sample_count = subset_sample_counts.get(subset, 0)
        subset_labels.append(f"{subset} (N={sample_count})")
    
    # Заменяем метки на оси Y в нижней части графика
    for idx, subset_label in enumerate(subset_labels):
        fig.add_trace(
            go.Scatter(
                mode='markers',
                marker={
                    'size': 10
                },
                x=x_positions,
                y=[subsets[idx] if not isnan(x) else None for x in comb_df[subsets[idx]]],
                name=subset_label,  # Используем обогащенное название для легенды
            ), row=2, col=1
        )
    
    # Обновляем параметры графика
    fig.update_layout(template=template)
    fig.update_layout({'showlegend': False})  # Включаем легенду для отображения названий подмножеств
    fig.update_xaxes({'showticklabels': False, 'range': [0.5, 12.5]})
    
    # Обновляем верхнюю ось Y, чтобы было немного больше места для подписей
    fig.update_yaxes(range=[0, max(counts) * 1.1], row=1, col=1)
    
    # Настраиваем правое положение легенды
    fig.update_layout(
        legend=dict(
            orientation="v",
            yanchor="top",
            y=0.3,
            xanchor="right",
            x=1.1
        )
    )
    
    # Заменяем метки на оси Y в нижней части графика
    fig.update_yaxes(
        ticktext=subset_labels,  # Используем наши обогащенные метки
        tickvals=subsets,        # Позиции меток соответствуют исходным подмножествам
        row=2, 
        col=1
    )
    
    return fig
```

## PCA

