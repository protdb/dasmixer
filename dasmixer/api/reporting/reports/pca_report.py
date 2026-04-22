"""PCA + ROC/AUC report for sample-level proteomics data."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from flet import Icons
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import label_binarize

from ..base import BaseReport
from dasmixer.gui.components.report_form import (
    ReportForm,
    MultiSubsetSelector,
    EnumSelector,
)


class PCAReportForm(ReportForm):
    subsets = MultiSubsetSelector(label="Subsets to include")
    lfq_type = EnumSelector(
        values=["emPAI", "iBAQ", "NSAF", "Top3"],
        label="LFQ method",
    )


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
    sample_labels: pd.Series,
    subset_labels: pd.Series,
    colors: dict[str, str],
    explained: np.ndarray,
) -> go.Figure:
    """
    Build 2-D PCA scatter plot.

    Args:
        matrix: shape (n_samples, 2) — PC1, PC2 scores.
        sample_labels: sample names (index-aligned with matrix).
        subset_labels: subset names (index-aligned with matrix).
        colors: {subset_name: hex_color}.
        explained: explained variance ratio array (at least 2 elements).
    """
    fig = go.Figure()
    for subset in subset_labels.unique():
        mask = subset_labels == subset
        fig.add_trace(go.Scatter(
            x=matrix.loc[mask, "PC1"],
            y=matrix.loc[mask, "PC2"],
            mode="markers+text",
            name=subset,
            text=sample_labels[mask].tolist(),
            textposition="top center",
            textfont=dict(size=10),
            marker=dict(size=12, color=colors.get(subset, "#888888"), opacity=0.85),
        ))

    pct1 = explained[0] * 100
    pct2 = explained[1] * 100
    fig.update_layout(
        title="PCA — Samples",
        xaxis_title=f"PC1 ({pct1:.1f}% variance)",
        yaxis_title=f"PC2 ({pct2:.1f}% variance)",
        legend_title="Subset",
        template="plotly_white",
    )
    return fig


def _build_roc_figure(
    roc_data: list[dict],
    colors: dict[str, str],
) -> go.Figure:
    """
    Build ROC curves figure.

    Args:
        roc_data: list of {subset, fpr, tpr, auc}.
        colors: {subset_name: hex_color}.
    """
    fig = go.Figure()
    # Diagonal reference line
    fig.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1],
        mode="lines",
        line=dict(dash="dash", color="gray", width=1),
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
            line=dict(color=colors.get(subset, "#888888"), width=2),
        ))
    fig.update_layout(
        title="ROC / AUC — per subset (one-vs-rest)",
        xaxis_title="False Positive Rate",
        yaxis_title="True Positive Rate",
        xaxis=dict(range=[0, 1]),
        yaxis=dict(range=[0, 1.02]),
        legend_title="Subset",
        template="plotly_white",
    )
    return fig


def _compute_pca(wide: pd.DataFrame, n_components: int = 2) -> tuple[pd.DataFrame, PCA]:
    """
    Run PCA on the wide (samples × proteins) matrix.

    Missing values filled with column medians before scaling.
    Returns (scores_df, fitted_pca).
    """
    filled = wide.fillna(wide.median(numeric_only=True))
    scaler = StandardScaler()
    scaled = scaler.fit_transform(filled)
    pca = PCA(n_components=min(n_components, min(scaled.shape)))
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
            continue
        if auc < 0.5:
            pc1 = -pc1
            auc = roc_auc_score(y_true, pc1)

        fpr, tpr, _ = roc_curve(y_true, pc1)
        results.append({
            "subset": subset,
            "fpr": fpr.tolist(),
            "tpr": tpr.tolist(),
            "auc": float(auc),
        })

    return results


# ---------------------------------------------------------------------------
# Report class
# ---------------------------------------------------------------------------

class PCAReport(BaseReport):
    name = "PCA / ROC-AUC"
    description = "PCA scatter plot and ROC/AUC curves colored by comparison group"
    icon = Icons.SCATTER_PLOT
    parameters = PCAReportForm

    async def _get_quant_matrix(
        self, lfq_type: str, selected_subsets: list[str]
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Build wide sample × protein matrix and return (wide_df, meta_df).

        meta_df has columns [sample, subset] indexed by sample name.
        wide_df rows = sample names, columns = protein_id, values = rel_value.
        """
        df = await self.project.get_protein_quantification_data(
            method=lfq_type,
            subsets=selected_subsets if selected_subsets else None,
        )
        if df.empty:
            raise ValueError(
                f"No quantification data found for method '{lfq_type}'. "
                "Run protein identification and LFQ calculation first."
            )

        # Pivot to wide format
        wide = df.pivot_table(
            index="sample",
            columns="protein_id",
            values="rel_value",
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

        lfq_type = str(params.get("lfq_type", "emPAI"))

        wide, meta = await self._get_quant_matrix(lfq_type, selected_subsets)

        # Align meta to wide rows (some samples might have no quant data)
        meta = meta.reindex(wide.index)

        # Drop samples with unknown subset
        valid_mask = meta["subset"].notna()
        wide = wide.loc[valid_mask]
        meta = meta.loc[valid_mask]

        if len(wide) < 2:
            raise ValueError("At least 2 samples with quantification data are required for PCA.")

        # Build color map from DB
        subsets_obj = await self.project.get_subsets()
        color_map: dict[str, str | None] = {s.name: s.display_color for s in subsets_obj}
        unique_subsets = list(meta["subset"].unique())
        colors = _assign_colors(unique_subsets, color_map)

        # PCA
        n_components = min(len(wide), len(wide.columns), 10)
        scores_df, pca_obj = _compute_pca(wide, n_components=n_components)
        explained = pca_obj.explained_variance_ratio_

        sample_labels = pd.Series(wide.index, index=wide.index)
        subset_labels = meta["subset"]

        pca_fig = _build_pca_figure(scores_df, sample_labels, subset_labels, colors, explained)

        # ROC/AUC
        roc_data = _compute_roc(scores_df, subset_labels)
        roc_fig = _build_roc_figure(roc_data, colors)

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

        # Sample scores table
        scores_export = scores_df.copy()
        scores_export.insert(0, "Sample", wide.index)
        scores_export.insert(1, "Subset", subset_labels.values)

        return (
            [("PCA", pca_fig), ("ROC / AUC", roc_fig)],
            [
                ("PCA Components", components_df, True),
                ("AUC by Subset", auc_df, True),
                ("Sample PC Scores", scores_export, False),
            ],
        )


from ..registry import registry
registry.register(PCAReport)
