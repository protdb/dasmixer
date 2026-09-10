"""PCA + ROC/AUC report for sample-level proteomics data."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dasmixer.api.reporting._icons import Icons
from dasmixer.utils.logger import logger
from sklearn.decomposition import PCA
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler, label_binarize

from ..base import BaseReport

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Palette of up to 20 distinguishable colors
_COLOR_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
    "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5",
    "#c49c94", "#f7b6d2", "#c7c7c7", "#dbdb8d", "#9edae5",
]


def _assign_colors(subsets: list[str], color_map: dict[str, str | None]) -> dict[str, str]:
    """Return a color per subset, falling back to palette for those without a DB color."""
    result: dict[str, str] = {}
    palette_idx = 0
    for s in subsets:
        db_color = color_map.get(s)
        if db_color:
            result[s] = db_color
        else:
            result[s] = _COLOR_PALETTE[palette_idx % len(_COLOR_PALETTE)]
            palette_idx += 1
    return result


def _build_pca_figure(
    matrix: pd.DataFrame,
    point_labels: pd.Series,
    subset_labels: pd.Series,
    colors: dict[str, str],
    explained: np.ndarray,
    show_labels: bool = True,
    entity_name: str = "Samples",
) -> go.Figure:
    """
    Build 2-D PCA scatter plot.

    Args:
        matrix: shape (n_points, 2) — PC1, PC2 scores.
        point_labels: labels for each point (index-aligned with matrix).
        subset_labels: subset names (index-aligned with matrix).
        colors: {subset_name: hex_color}.
        explained: explained variance ratio array (at least 2 elements).
        entity_name: label for the plot title (e.g. "Samples" or "Proteins").
    """
    fig = go.Figure()
    for subset in subset_labels.unique():
        mask = (subset_labels == subset).values
        x_vals = [float(v) for v in matrix.loc[mask, "PC1"]]
        y_vals = [float(v) for v in matrix.loc[mask, "PC2"]]
        text_vals = [str(v) for v in point_labels.values[mask]]
        fig.add_trace(go.Scatter(
            x=x_vals,
            y=y_vals,
            mode="markers+text" if show_labels else "markers",
            name=str(subset),
            text=text_vals,
            textposition="top center",
            textfont={"size": 10},
            marker={"size": 12, "color": colors.get(str(subset), "#888888"), "opacity": 0.85},
        ))

    pct1 = explained[0] * 100
    pct2 = explained[1] * 100
    fig.update_layout(
        title=f"PCA — {entity_name}",
        xaxis_title=f"PC1 ({pct1:.1f}% variance)",
        yaxis_title=f"PC2 ({pct2:.1f}% variance)",
        legend_title="Subset",
        template="plotly_white",
    )
    return fig


def _build_roc_figure(
    roc_data: list[dict],
    colors: dict[str, str],
    entity_name: str = "Samples",
) -> go.Figure:
    """
    Build ROC curves figure.

    Args:
        roc_data: list of {subset, fpr, tpr, auc}.
        colors: {subset_name: hex_color}.
        entity_name: label for the legend/title context.
    """
    fig = go.Figure()
    # Diagonal reference line
    fig.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1],
        mode="lines",
        line={"dash": "dash", "color": "gray", "width": 1},
        showlegend=False,
        hoverinfo="skip",
    ))
    for item in roc_data:
        subset = item["subset"]
        auc_val = item["auc"]
        fig.add_trace(go.Scatter(
            x=item["fpr"],
            y=item["tpr"],
            mode="lines",
            name=f"{subset} (AUC={auc_val:.3f})",
            line={"color": colors.get(subset, "#888888"), "width": 2},
        ))
    fig.update_layout(
        title=f"ROC / AUC — per subset (one-vs-rest, {entity_name.lower()})",
        xaxis_title="False Positive Rate",
        yaxis_title="True Positive Rate",
        xaxis={"range": [0, 1]},
        yaxis={"range": [0, 1.02]},
        legend_title="Subset",
        template="plotly_white",
    )
    return fig


def _compute_pca(wide: pd.DataFrame, n_components: int = 2) -> tuple[pd.DataFrame, PCA]:
    """
    Run PCA on the wide (samples × proteins) matrix.

    Proteins (columns) with no value in any sample and constant-value
    columns are dropped before scaling. Remaining missing values are filled
    with column medians.

    Raises ValueError when the cleaned matrix has no usable features or fewer
    than 2 independent dimensions (a 2D PCA cannot be produced).

    Returns (scores_df, fitted_pca). ``scores_df`` keeps the input row index.
    """
    # Drop proteins (columns) with no value in any sample.
    wide = wide.dropna(axis=1, how="all")
    # Drop constant-value columns: they carry no information and inflate the
    # explained-variance denominator.
    nunique = wide.nunique(axis=0)
    wide = wide.loc[:, nunique > 1]

    if wide.shape[1] == 0:
        raise ValueError(
            "No proteins with measurable variation across samples remain "
            "after removing all-NaN and constant-value entries. "
            "Cannot run PCA."
        )

    # Fill remaining NaN with column medians (per-protein central tendency).
    filled = wide.fillna(wide.median(numeric_only=True))
    scaler = StandardScaler()
    scaled = scaler.fit_transform(filled)

    n_comp = min(n_components, scaled.shape[0], scaled.shape[1])
    if n_comp < 2:
        raise ValueError(
            f"Not enough independent dimensions for a 2D PCA "
            f"(samples={scaled.shape[0]}, usable proteins={scaled.shape[1]}). "
            f"At least 2 samples and 2 proteins with variation are required."
        )

    pca = PCA(n_components=n_comp)
    scores = pca.fit_transform(scaled)
    cols = [f"PC{i+1}" for i in range(scores.shape[1])]
    return pd.DataFrame(scores, index=wide.index, columns=cols), pca


def _compute_roc(
    scores_df: pd.DataFrame,
    subset_series: pd.Series,
) -> list[dict]:
    """
    Compute one-vs-rest ROC/AUC for each subset using PCA scores.

    Returns list of {subset, fpr, tpr, auc}.
    Only subsets with at least 2 unique values (present/absent) are included.
    """
    from sklearn.metrics import roc_curve

    subsets = list(subset_series.unique())
    # label_binarize returns shape (n, 1) for binary case — expand to (n, 2)
    y_bin_raw = label_binarize(subset_series.values, classes=subsets)
    if len(subsets) == 2 and y_bin_raw.ndim == 2 and y_bin_raw.shape[1] == 1:
        # Binary: column 0 = class[1], add column for class[0]
        y_bin = np.hstack([1 - y_bin_raw, y_bin_raw])
    else:
        y_bin = y_bin_raw

    results = []
    for idx, subset in enumerate(subsets):
        if idx >= y_bin.shape[1]:
            continue
        y_true = y_bin[:, idx]
        if y_true.sum() == 0 or y_true.sum() == len(y_true):
            # All same class — skip
            continue

        # Use PC1 as the discriminant score; sign may be arbitrary but AUC handles it
        pc1 = scores_df["PC1"].values
        # Ensure AUC >= 0.5 (flip sign if needed)
        try:
            auc = roc_auc_score(y_true, pc1)
        except Exception:
            logger.warning("ROC AUC computation failed for subset '%s', skipping", subset, exc_info=True)
            continue
        if auc < 0.5:
            pc1 = -pc1
            auc = roc_auc_score(y_true, pc1)

        try:
            fpr, tpr, _ = roc_curve(y_true, pc1)
        except Exception:
            logger.warning("ROC curve computation failed for subset '%s', skipping", subset, exc_info=True)
            continue
        results.append({
            "subset": subset,
            "fpr": fpr.tolist(),
            "tpr": tpr.tolist(),
            "auc": float(auc),
        })

    return results


def _protein_label(row: pd.Series) -> str:
    """Pick the best available display label for a protein row."""
    for col in ("gene", "name", "fasta_name", "protein_id"):
        val = row.get(col)
        if val is not None and str(val).strip():
            return str(val)
    return str(row.get("protein_id", "?"))


def _build_protein_group_matrix(
    df: pd.DataFrame,
    measure: str,
    top_n_proteins: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Build a (protein × group) matrix for PCA.

    Each row is a (protein_id, subset) pair. Columns are ``rep_1..rep_N``
    where the values are the LFQ ``measure`` of that protein inside the
    given subset, **sorted in descending order** (rep_1 = maximum).

    Rows with fewer replicates than ``N`` are padded with the mean of their
    own measured values.

    Args:
        df: long-format DataFrame from ``get_protein_quantification_data``
            (must contain at least: protein_id, subset, gene, name,
            fasta_name, and the ``measure`` column).
        measure: column name in ``df`` holding the LFQ value.
        top_n_proteins: if > 0, keep only the N proteins with the highest
            variance of ``measure`` across all rows in ``df``.

    Returns:
        (wide, meta) where:
        - ``wide``: index = ``"protein_id||subset"`` strings,
          columns = ``rep_1 .. rep_N``, values = float.
        - ``meta``: same row order, columns = ``protein_id, subset, label``.

    Raises:
        ValueError: if no usable data remains after filtering.
    """
    if df.empty:
        raise ValueError("No quantification data available for Protein mode.")

    # Keep only rows with an actual measurement.
    df = df.dropna(subset=[measure]).copy()
    if df.empty:
        raise ValueError(
            f"No rows with a non-null '{measure}' value remain. "
            "Cannot build protein × group matrix."
        )

    # --- Top-N proteins by variance across all selected samples ---
    if top_n_proteins and top_n_proteins > 0:
        variances = df.groupby("protein_id")[measure].var(ddof=0)
        variances = variances.fillna(0.0)
        if len(variances) > top_n_proteins:
            top_ids = variances.nlargest(top_n_proteins).index
            df = df[df["protein_id"].isin(top_ids)]
            if df.empty:
                raise ValueError(
                    f"No proteins left after applying top_n_proteins={top_n_proteins}."
                )

    # --- Protein label map (gene → name → fasta_name → protein_id) ---
    label_map: dict[str, str] = {}
    for pid, row in df.groupby("protein_id", sort=False).first().iterrows():
        label_map[str(pid)] = _protein_label(row)

    # --- Group by (protein_id, subset), sort values descending ---
    grouped = (
        df.groupby(["protein_id", "subset"], sort=False)[measure]
        .apply(lambda s: sorted(s.dropna().tolist(), reverse=True))
    )
    if grouped.empty:
        raise ValueError("No (protein, subset) groups with data could be built.")

    max_reps = grouped.apply(len).max()
    if max_reps == 0:
        raise ValueError("All (protein, subset) groups are empty after filtering.")

    rows: list[list[float]] = []
    meta_rows: list[tuple[str, str, str]] = []
    for (pid, subset), vals in grouped.items():
        if not vals:
            continue
        row_mean = float(np.mean(vals))
        padded = list(vals) + [row_mean] * (max_reps - len(vals))
        rows.append(padded)
        meta_rows.append((str(pid), str(subset), label_map.get(str(pid), str(pid))))

    rep_cols = [f"rep_{i + 1}" for i in range(max_reps)]
    index_keys = [f"{pid}||{subset}" for pid, subset, _ in meta_rows]
    wide = pd.DataFrame(rows, columns=rep_cols, index=index_keys, dtype=float)
    meta = pd.DataFrame(meta_rows, columns=["protein_id", "subset", "label"], index=index_keys)

    return wide, meta


# ---------------------------------------------------------------------------
# Report class
# ---------------------------------------------------------------------------

class PCAReport(BaseReport):
    name = "PCA ROC-AUC"
    description = "PCA scatter plot and ROC/AUC curves colored by comparison group"
    icon = Icons.SCATTER_PLOT
    parameters = None

    async def _fetch_quant_df(
        self, lfq_type: str, selected_subsets: list[str],
        exclude_outliers: bool = True,
    ) -> pd.DataFrame:
        """
        Fetch raw long-format quantification DataFrame.

        Returns the DataFrame from ``project.get_protein_quantification_data``
        filtered by LFQ method, subsets and outlier flag — with no pivoting.
        """
        df = await self.project.get_protein_quantification_data(
            method=lfq_type,
            subsets=selected_subsets if selected_subsets else None,
            exclude_outliers=exclude_outliers,
        )
        if df.empty:
            raise ValueError(
                f"No quantification data found for method '{lfq_type}'. "
                "Run protein identification and LFQ calculation first."
            )
        return df

    async def _get_quant_matrix(
        self, lfq_type: str, lfq_measure: str, selected_subsets: list[str],
        exclude_outliers: bool = True,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Build wide sample × protein matrix and return (wide_df, meta_df).

        meta_df has columns [sample, subset] indexed by sample name.
        wide_df rows = sample names, columns = protein_id, values = lfq_measure.
        """
        df = await self._fetch_quant_df(
            lfq_type, selected_subsets, exclude_outliers=exclude_outliers
        )

        # Pivot to wide format
        wide = df.pivot_table(
            index="sample",
            columns="protein_id",
            values=lfq_measure,
            aggfunc="mean",
        )
        meta = (
            df[["sample", "subset"]]
            .drop_duplicates("sample")
            .set_index("sample")
        )
        return wide, meta

    async def _generate_impl(
        self,
        params: dict,
    ) -> tuple[list[tuple[str, go.Figure]], list[tuple[str, pd.DataFrame, bool]]]:
        selected_subsets: list[str] = params.get("subsets", [])
        if isinstance(selected_subsets, str):
            selected_subsets = [s.strip() for s in selected_subsets.split(",") if s.strip()]

        lfq_value = params.get("lfq", ("emPAI", "rel_value"))
        if not isinstance(lfq_value, (tuple, list)):
            lfq_value = (lfq_value, "rel_value")
        lfq_type = lfq_value[0]
        lfq_measure = lfq_value[1]
        show_labels = params.get("show_labels", False)
        include_outliers = bool(params.get("include_outliers", False))
        exclude_outliers = not include_outliers
        group_by = params.get("group_by", "Sample")
        top_n_proteins = int(params.get("top_n_proteins", 100))

        if group_by == "Protein":
            # --- Protein × Group mode ---
            df = await self._fetch_quant_df(
                lfq_type, selected_subsets, exclude_outliers=exclude_outliers
            )
            wide, meta = _build_protein_group_matrix(
                df, lfq_measure, top_n_proteins=top_n_proteins
            )
            point_labels = meta["label"]
            group_labels = meta["subset"]
            entity_name = "Proteins"
            scores_table_id_col = "Protein ID"
            scores_table_label_col = "Gene"
            scores_table_ids = meta["protein_id"].values
            scores_table_name = "Protein PC Scores"
        else:
            # --- Sample mode (original behaviour) ---
            wide, meta = await self._get_quant_matrix(
                lfq_type, lfq_measure, selected_subsets, exclude_outliers=exclude_outliers
            )

            # Align meta to wide rows (some samples might have no quant data)
            meta = meta.reindex(wide.index)

            # Drop samples with unknown subset
            valid_mask = meta["subset"].notna()
            wide = wide.loc[valid_mask]
            meta = meta.loc[valid_mask]

            # Drop samples with no quantification value across any protein — they
            # cannot be positioned in PCA space.
            row_mask = ~wide.isna().all(axis=1)
            wide = wide.loc[row_mask]
            meta = meta.reindex(wide.index)

            if len(wide) < 2:
                raise ValueError(
                    "At least 2 samples with quantification data are required for PCA."
                )

            point_labels = pd.Series(wide.index, index=wide.index)
            group_labels = meta["subset"]
            entity_name = "Samples"
            scores_table_id_col = "Sample"
            scores_table_label_col = "Subset"
            scores_table_ids = wide.index
            scores_table_name = "Sample PC Scores"

        # Build color map from DB
        subsets_obj = await self.project.get_subsets()
        color_map: dict[str, str | None] = {s.name: s.display_color for s in subsets_obj}
        unique_subsets = list(group_labels.unique())
        colors = _assign_colors(unique_subsets, color_map)

        # PCA
        n_components = min(len(wide), len(wide.columns), 10)
        scores_df, pca_obj = _compute_pca(wide, n_components=n_components)
        explained = pca_obj.explained_variance_ratio_

        pca_fig = _build_pca_figure(
            scores_df, point_labels, group_labels, colors, explained,
            show_labels=show_labels, entity_name=entity_name,
        )

        # ROC/AUC
        roc_data = _compute_roc(scores_df, group_labels)
        roc_fig = _build_roc_figure(roc_data, colors, entity_name=entity_name)

        # --- Tables ---

        # Components table
        n_show = min(len(explained), 10)
        components_df = pd.DataFrame({
            "Component": [f"PC{i+1}" for i in range(n_show)],
            "Explained variance (%)": [round(explained[i] * 100, 2) for i in range(n_show)],
            "Cumulative (%)": [round(sum(explained[:i+1]) * 100, 2) for i in range(n_show)],
        })

        # AUC table
        if roc_data:
            auc_df = pd.DataFrame([
                {"Subset": r["subset"], "AUC (PC1, one-vs-rest)": round(r["auc"], 4)}
                for r in roc_data
            ])
        else:
            auc_df = pd.DataFrame(columns=["Subset", "AUC (PC1, one-vs-rest)"])

        # Scores table
        scores_export = scores_df.copy()
        scores_export.insert(0, scores_table_id_col, list(scores_table_ids))
        scores_export.insert(1, scores_table_label_col, list(group_labels.values))

        return (
            [("PCA", pca_fig), ("ROC / AUC", roc_fig)],
            [
                ("PCA Components", components_df, True),
                ("AUC by Subset", auc_df, True),
                (scores_table_name, scores_export, False),
            ],
        )


from ..registry import registry

registry.register(PCAReport)
