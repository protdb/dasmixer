"""UpSet Plot report for protein identifications across comparison groups."""

from itertools import product

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from flet import Icons
from plotly.subplots import make_subplots

from ..base import BaseReport
from dasmixer.gui.components.report_form import ReportForm, MultiSubsetSelector, IntSelector


# ---------------------------------------------------------------------------
# UpSet plot logic (ported from volcanizer/create_upset.py)
# ---------------------------------------------------------------------------

def _generate_cartesian(subset_names: list[str]) -> pd.DataFrame:
    """Generate all True/False combinations for the given subset names."""
    all_combinations = list(product([False, True], repeat=len(subset_names)))
    df = pd.DataFrame(all_combinations)
    df.columns = pd.Index(subset_names)
    return df


def place_to_groups(df: pd.DataFrame) -> pd.DataFrame:
    """
    For every combination of subsets, count proteins that belong
    exclusively to that intersection.

    Args:
        df: DataFrame with columns ['subset', 'uniprot_id', 'sample']

    Returns:
        DataFrame with columns: <subset_names>..., 'name', 'count',
        sorted descending by count.
    """
    subsets = list(df['subset'].unique())
    proteins = df['uniprot_id'].unique()

    # Per-protein presence table: protein × subset → occurrence count
    presence_records = []
    for protein in proteins:
        rec = {'protein': protein}
        for subset in subsets:
            rec[subset] = int(len(df.query('subset == @subset & uniprot_id == @protein')))
        presence_records.append(rec)
    presence_df = pd.json_normalize(presence_records)

    elems = []
    for _, row in _generate_cartesian(subsets).iterrows():
        row_dict: dict[str, bool] = {str(k): bool(v) for k, v in row.to_dict().items()}
        filtered = presence_df.copy()
        for subset in subsets:
            if row_dict[subset]:
                filtered = filtered.query(f"`{subset}` > 0").copy()
            else:
                filtered = filtered.query(f"`{subset}` == 0").copy()

        # Subset membership flags for this intersection (1 = present, None = absent)
        membership: dict[str, object] = {k: (1 if v else None) for k, v in row_dict.items()}
        intersection_name = '_'.join(k for k, v in row_dict.items() if v)
        membership['name'] = intersection_name
        membership['count'] = len(filtered)
        elems.append(membership)

    elems.sort(key=lambda x: x['count'], reverse=True)  # type: ignore[arg-type]
    return pd.json_normalize(elems)


def get_subset_sample_counts(df: pd.DataFrame) -> dict[str, int]:
    """Return {subset_name: number_of_unique_samples}."""
    return {
        subset: int(df.loc[df['subset'] == subset, 'sample'].nunique())
        for subset in df['subset'].unique()
    }


def get_intersection_proteins(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each non-empty intersection, list the proteins belonging to it.

    Args:
        df: DataFrame with columns ['subset', 'uniprot_id', 'sample']

    Returns:
        DataFrame with columns ['intersection', 'protein_id']
        (one row per protein per intersection).
    """
    subsets = list(df['subset'].unique())
    proteins = df['uniprot_id'].unique()

    # Per-protein presence table
    presence_records = []
    for protein in proteins:
        rec = {'protein': protein}
        for subset in subsets:
            rec[subset] = int(len(df.query('subset == @subset & uniprot_id == @protein')))
        presence_records.append(rec)
    presence_df = pd.json_normalize(presence_records)

    rows = []
    for _, row in _generate_cartesian(subsets).iterrows():
        row_dict: dict[str, bool] = {str(k): bool(v) for k, v in row.to_dict().items()}
        intersection_name = '_'.join(k for k, v in row_dict.items() if v)
        if not intersection_name:
            continue  # Skip the all-False combination

        filtered = presence_df.copy()
        for subset in subsets:
            if row_dict[subset]:
                filtered = filtered.query(f"`{subset}` > 0").copy()
            else:
                filtered = filtered.query(f"`{subset}` == 0").copy()

        for protein in filtered['protein'].tolist():
            rows.append({'intersection': intersection_name, 'protein_id': protein})

    if rows:
        _tmp = pd.DataFrame(rows)
        return pd.DataFrame({'intersection': _tmp['intersection'], 'protein_id': _tmp['protein_id']})
    return pd.DataFrame({'intersection': pd.Series(dtype=str), 'protein_id': pd.Series(dtype=str)})


def plot_upset(df: pd.DataFrame, min_proteins: int = 1) -> go.Figure:
    """
    Build an UpSet plot using Plotly.

    Args:
        df: DataFrame with columns ['subset', 'uniprot_id', 'sample']
        min_proteins: Only show intersections with at least this many proteins.
                      Intersections below the threshold are hidden from the plot
                      (but still present in the summary table).

    Returns:
        go.Figure — two-row subplot: bar chart (top) + dot matrix (bottom).
    """
    subsets = list(df['subset'].unique())
    subset_sample_counts = get_subset_sample_counts(df)
    comb_df = place_to_groups(df)

    # Filter for plot only — keep intersections meeting the threshold
    plot_df = comb_df[comb_df['count'] >= min_proteins].copy().reset_index(drop=True)

    n_combinations = len(plot_df)
    x_positions = list(range(1, n_combinations + 1))
    counts = plot_df['count'].tolist()

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.7, 0.3],
        vertical_spacing=0.05,
    )

    # Top: bar chart of intersection sizes
    fig.add_trace(go.Bar(
        x=x_positions,
        y=counts,
        text=counts,
        textposition='outside',
        textfont=dict(size=14, color='black'),
        hoverinfo='y',
        marker_color='steelblue',
        showlegend=False,
    ), row=1, col=1)

    # Bottom: dot matrix indicating set membership
    subset_labels = [
        f"{subset} (N={subset_sample_counts.get(subset, 0)})"
        for subset in subsets
    ]

    for idx, subset in enumerate(subsets):
        # Dot present only when this subset is part of the intersection
        col_values = plot_df[subset].tolist()
        y_values = [
            subset if (v is not None and not (isinstance(v, float) and np.isnan(v)))
            else None
            for v in col_values
        ]
        fig.add_trace(go.Scatter(
            mode='markers',
            marker=dict(size=12, color='steelblue'),
            x=x_positions,
            y=y_values,
            name=subset_labels[idx],
            showlegend=False,
        ), row=2, col=1)

    # Layout
    fig.update_xaxes(showticklabels=False, range=[0.5, n_combinations + 0.5])
    fig.update_yaxes(
        range=[0, max(counts) * 1.15] if counts else [0, 1],
        row=1, col=1,
    )
    fig.update_yaxes(
        ticktext=subset_labels,
        tickvals=subsets,
        row=2, col=1,
    )
    fig.update_layout(
        title="UpSet Plot — Protein Identifications",
        template='plotly_white',
    )

    return fig


# ---------------------------------------------------------------------------
# ReportForm
# ---------------------------------------------------------------------------

class UpsetReportForm(ReportForm):
    subsets = MultiSubsetSelector(label="Subsets to include")
    min_proteins = IntSelector(default=1, label="Min proteins per intersection")


# ---------------------------------------------------------------------------
# Report class
# ---------------------------------------------------------------------------

class UpsetReport(BaseReport):
    name = "Upset Plot"
    description = "Upset plot for protein identifications across comparison groups"
    icon = Icons.INSERT_CHART_ROUNDED
    parameters = UpsetReportForm

    async def _get_upset_data(self, selected_subsets: list[str]) -> pd.DataFrame:
        """Fetch protein × sample × subset data from the project DB."""
        if selected_subsets:
            placeholders = ','.join('?' * len(selected_subsets))
            query = f"""
                SELECT
                    pir.protein_id  AS uniprot_id,
                    s.name          AS sample,
                    sb.name         AS subset
                FROM protein_identification_result pir
                JOIN sample  s  ON pir.sample_id  = s.id
                JOIN subset  sb ON s.subset_id    = sb.id
                WHERE sb.name IN ({placeholders})
            """
            return await self.project.execute_query_df(query, tuple(selected_subsets))
        else:
            query = """
                SELECT
                    pir.protein_id  AS uniprot_id,
                    s.name          AS sample,
                    sb.name         AS subset
                FROM protein_identification_result pir
                JOIN sample  s  ON pir.sample_id  = s.id
                JOIN subset  sb ON s.subset_id    = sb.id
            """
            return await self.project.execute_query_df(query)

    async def _generate_impl(
        self,
        params: dict,
    ) -> tuple[list[tuple[str, go.Figure]], list[tuple[str, pd.DataFrame, bool]]]:
        selected_subsets: list[str] = params.get('subsets', [])
        if isinstance(selected_subsets, str):
            # Backward compatibility
            selected_subsets = [s.strip() for s in selected_subsets.split(',') if s.strip()]

        min_proteins = int(params.get('min_proteins', 1))

        df = await self._get_upset_data(selected_subsets)

        if df.empty:
            raise ValueError(
                "No protein identification data found for the selected subsets. "
                "Run protein identification first."
            )

        # Deduplicate: one row per (protein, sample, subset) is enough
        df = df.drop_duplicates()

        fig = plot_upset(df, min_proteins=min_proteins)

        summary_df = place_to_groups(df)
        # Keep only human-readable columns for the summary table
        summary_table = pd.DataFrame({'name': summary_df['name'], 'count': summary_df['count']})

        intersection_df = get_intersection_proteins(df)

        return (
            [("Upset Plot", fig)],
            [
                ("Intersection Summary", summary_table, True),
                ("Proteins by Intersection", intersection_df, True),
            ],
        )


from ..registry import registry
registry.register(UpsetReport)
