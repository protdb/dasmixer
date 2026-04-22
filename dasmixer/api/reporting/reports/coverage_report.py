"""Tool Coverage Comparison report.

For each protein in protein_identification_result, calculates:
- Per-tool sequence coverage (unique matched_sequence from peptide_match, all samples)
- Combined coverage (all tools together)
- Theoretical maximum coverage (using the same DigestionParams as LFQ)

Output:
- Histogram of coverage distributions per tool + combined (one figure)
- Detail table: protein × tool coverage + combined + theoretical
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from flet import Icons

from ..base import BaseReport
from dasmixer.gui.components.report_form import ReportForm
# No extra form parameters needed — the report uses all identified proteins
# and the project LFQ settings (enzyme, min/max length, missed cleavages).


# ---------------------------------------------------------------------------
# Coverage helpers (pure functions, no project dependency)
# ---------------------------------------------------------------------------

def _sequence_coverage(protein_sequence: str, peptides: list[str]) -> float:
    """
    Calculate sequence coverage (%) for a protein given a list of
    observed peptide sequences.  Uses simple find() — first occurrence only.
    Returns 0.0 if the sequence is empty.
    """
    if not protein_sequence:
        return 0.0
    covered: set[int] = set()
    for pep in peptides:
        pos = protein_sequence.find(pep)
        if pos != -1:
            for i in range(pos, pos + len(pep)):
                covered.add(i)
    return len(covered) / len(protein_sequence) * 100.0


def _theoretical_coverage(protein_sequence: str, dp) -> float:
    """
    Theoretical maximum coverage using DigestionParams *dp*.
    Delegates to the semPAI Protein class to avoid duplicating logic.
    Returns 0.0 on any error.
    """
    if not protein_sequence:
        return 0.0
    try:
        from dasmixer.api.calculations.proteins.sempai import Protein
        prot = Protein(
            accession="tmp",
            sequence=protein_sequence,
            peptides=[],
            is_uniprot=False,
            observable_parameters=dp,
        )
        _, pct = prot.get_theoretical_coverage()
        return float(pct)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Data retrieval
# ---------------------------------------------------------------------------

async def _fetch_coverage_data(project) -> pd.DataFrame:
    """
    Return a DataFrame with columns:
        protein_id, tool, matched_sequence

    Joins peptide_match → identification → tool.
    All samples, all peptides (preferred and non-preferred).
    """
    query = """
        SELECT
            pm.protein_id,
            t.name          AS tool,
            pm.matched_sequence
        FROM peptide_match pm
        JOIN identification i ON pm.identification_id = i.id
        JOIN tool            t ON i.tool_id            = t.id
        WHERE pm.protein_id IS NOT NULL
    """
    return await project.execute_query_df(query)


# ---------------------------------------------------------------------------
# Coverage calculation
# ---------------------------------------------------------------------------

def _compute_coverage_table(
    peptide_df: pd.DataFrame,
    sequences: dict[str, str],
    dp,
) -> pd.DataFrame:
    """
    Given raw peptide/tool data and protein sequences, build the summary table.

    Returns DataFrame with columns:
        protein_id, <tool1>, <tool2>, ..., combined, theoretical
    All coverage values in %.
    """
    if peptide_df.empty:
        return pd.DataFrame()

    tools = sorted(peptide_df["tool"].unique().tolist())
    proteins = list(sequences.keys())

    records = []
    for protein_id in proteins:
        seq = sequences.get(protein_id, "")
        prot_data = peptide_df[peptide_df["protein_id"] == protein_id]
        if prot_data.empty:
            continue

        row: dict[str, object] = {"protein_id": protein_id}

        # Per-tool coverage
        all_tool_peptides: list[str] = []
        for tool in tools:
            tool_peps = prot_data[prot_data["tool"] == tool]["matched_sequence"].dropna().unique().tolist()
            cov = _sequence_coverage(seq, tool_peps)
            row[tool] = round(cov, 2)
            all_tool_peptides.extend(tool_peps)

        # Combined coverage
        combined_peps = list(set(all_tool_peptides))
        row["combined"] = round(_sequence_coverage(seq, combined_peps), 2)

        # Theoretical coverage
        row["theoretical"] = round(_theoretical_coverage(seq, dp), 2)

        records.append(row)

    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------

def _build_coverage_histogram(
    coverage_df: pd.DataFrame,
    tools: list[str],
) -> go.Figure:
    """
    Build a histogram of coverage distributions.

    One trace per tool + 'combined' + 'theoretical' (if present).
    Uses overlaid semi-transparent bars with 10%-wide bins.
    """
    series_to_plot: list[tuple[str, pd.Series]] = []
    for tool in tools:
        if tool in coverage_df.columns:
            series_to_plot.append((tool, coverage_df[tool].dropna()))
    if "combined" in coverage_df.columns:
        series_to_plot.append(("Combined", coverage_df["combined"].dropna()))
    if "theoretical" in coverage_df.columns:
        series_to_plot.append(("Theoretical", coverage_df["theoretical"].dropna()))

    fig = go.Figure()
    bin_settings = dict(start=0, end=100, size=5)

    for label, series in series_to_plot:
        fig.add_trace(go.Histogram(
            x=series.tolist(),
            name=label,
            xbins=bin_settings,
            opacity=0.6,
            histnorm="percent",
        ))

    fig.update_layout(
        barmode="overlay",
        title="Protein Sequence Coverage Distribution by Tool",
        xaxis_title="Coverage (%)",
        yaxis_title="Proteins (%)",
        xaxis=dict(range=[0, 100]),
        legend_title="Tool / Coverage type",
        template="plotly_white",
    )
    return fig


# ---------------------------------------------------------------------------
# Report class
# ---------------------------------------------------------------------------

class ToolCoverageReportForm(ReportForm):
    # No parameters needed — uses project LFQ settings
    pass


class ToolCoverageReport(BaseReport):
    name = "Tool Coverage Comparison"
    description = (
        "Per-tool and combined sequence coverage for identified proteins, "
        "including theoretical maximum coverage"
    )
    icon = Icons.AREA_CHART
    parameters = ToolCoverageReportForm

    async def _generate_impl(
        self,
        params: dict,
    ) -> tuple[list[tuple[str, go.Figure]], list[tuple[str, pd.DataFrame, bool]]]:
        # --- Load project LFQ settings (same as used in LFQ calculation) ---
        enzyme = await self.project.get_setting("lfq_enzyme", "trypsin")
        min_len = int(await self.project.get_setting("lfq_min_peptide_length", "7"))
        max_len = int(await self.project.get_setting("lfq_max_peptide_length", "30"))
        max_mc = int(await self.project.get_setting("lfq_max_missed_cleavages", "2"))

        from dasmixer.api.calculations.proteins.sempai import DigestionParams
        dp = DigestionParams(
            enzyme=enzyme or "trypsin",
            min_peptide_length=min_len,
            max_peptide_length=max_len,
            max_cleavage_sites=max_mc,
        )

        # --- Fetch data ---
        peptide_df = await _fetch_coverage_data(self.project)

        if peptide_df.empty:
            raise ValueError(
                "No peptide match data found. "
                "Run protein identification first."
            )

        # Restrict to proteins that have identification results
        pir_df = await self.project.get_protein_identifications()
        if pir_df.empty:
            raise ValueError("No protein identification results found.")

        # Only proteins that appear in protein_identification_result
        identified_proteins = pir_df["protein_id"].unique().tolist()
        peptide_df = peptide_df[peptide_df["protein_id"].isin(identified_proteins)]

        # Protein sequences
        sequences_full = await self.project.get_protein_db_to_search()
        sequences = {pid: sequences_full[pid] for pid in identified_proteins if pid in sequences_full}

        if not sequences:
            raise ValueError("No protein sequences found. Load a FASTA file first.")

        # --- Compute coverage table ---
        tools = sorted(peptide_df["tool"].unique().tolist())
        coverage_df = _compute_coverage_table(peptide_df, sequences, dp)

        if coverage_df.empty:
            raise ValueError("Coverage calculation returned no results.")

        # --- Plot ---
        fig = _build_coverage_histogram(coverage_df, tools)

        # --- Summary stats table ---
        stat_rows = []
        for col in tools + ["combined", "theoretical"]:
            if col not in coverage_df.columns:
                continue
            s = coverage_df[col].dropna()
            stat_rows.append({
                "Tool / Coverage": col,
                "Mean (%)": round(float(s.mean()), 2) if len(s) else None,
                "Median (%)": round(float(s.median()), 2) if len(s) else None,
                "Std (%)": round(float(s.std()), 2) if len(s) else None,
                "Min (%)": round(float(s.min()), 2) if len(s) else None,
                "Max (%)": round(float(s.max()), 2) if len(s) else None,
                "N proteins": int(len(s)),
            })
        stats_df = pd.DataFrame(stat_rows)

        # Rename detail table columns for readability
        detail_df = coverage_df.rename(columns={t: f"{t} (%)" for t in tools})
        if "combined" in detail_df.columns:
            detail_df = detail_df.rename(columns={"combined": "Combined (%)"})
        if "theoretical" in detail_df.columns:
            detail_df = detail_df.rename(columns={"theoretical": "Theoretical (%)"})

        return (
            [("Coverage Distribution", fig)],
            [
                ("Coverage Summary", stats_df, True),
                ("Per-Protein Coverage", detail_df, False),
            ],
        )


from ..registry import registry
registry.register(ToolCoverageReport)
