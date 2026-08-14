"""Peptide identification matching and selection."""
from typing import Literal

import pandas as pd

from dasmixer.api.project.project import Project
from dasmixer.utils.logger import logger


async def select_preferred_identifications(
    project: Project,
    criterion: str,
    tool_settings: dict[int, dict]
) -> int:
    """
    Select preferred identifications for all spectra based on criterion.

    Args:
        project: Project instance
        criterion: Selection criterion — "ppm" or "intensity"
        tool_settings: Tool-specific settings, mapping tool_id to:
            - max_ppm: Maximum allowed PPM error (float)
            - min_score: Minimum identification score (float)
            - min_ion_intensity_coverage: Minimum % intensity coverage (float)
            - use_protein_from_file: Use protein IDs from file (bool)
            - min_protein_identity: Minimum protein sequence identity (float)
            - denovo_correction: Apply de novo correction (bool)
            - min_peptide_length: Minimum peptide length (int, default 7)
            - max_peptide_length: Maximum peptide length (int, default 30)

    Returns:
        Number of spectra processed
    """
    logger.info(f"Starting preferred identification selection (criterion: {criterion})")
    logger.debug(f"Tool settings: {tool_settings}")
    counter = 0

    if criterion not in ("ppm", "intensity"):
        raise ValueError(f"Invalid criterion: {criterion}. Must be 'ppm' or 'intensity'")

    spectra_files = await project.get_spectra_files()
    for _, spectra_file in spectra_files.iterrows():
        idents_not_merged = []
        for tool_id, tool_params in tool_settings.items():
            idents = await project.get_identifications(spectra_file['id'], tool_id)
            if tool_params.get("ignore_criteria", False):
                idents_not_merged.append(idents.copy())
                continue
            max_ppm = tool_params.get("max_ppm", 50000)
            min_score = tool_params.get("min_score", 0)
            min_ion_intensity_coverage = tool_params["min_ion_intensity_coverage"]
            min_len = tool_params.get("min_peptide_length", 7)
            max_len = tool_params.get("max_peptide_length", 30)



            idents['canonical_length'] = idents['canonical_sequence'].str.len()
            idents['ppm'] = idents['ppm'].abs()
            if not tool_params.get("denovo_correction", False):
                query = (
                    "ppm <= @max_ppm and "
                    "score >= @min_score and "
                    "intensity_coverage >= @min_ion_intensity_coverage and "
                    "canonical_length >= @min_len and "
                    "canonical_length <= @max_len"
                )
            else:
                query = (
                    "ppm <= 50000 and "
                    "score >= @min_score and "
                    "intensity_coverage >= @min_ion_intensity_coverage and "
                    "canonical_length >= @min_len and "
                    "canonical_length <= @max_len"
                )
            idents_not_merged.append(idents.query(query).copy())

        all_idents = pd.concat(idents_not_merged, ignore_index=True)
        spectras = await project.get_spectra(spectra_file['id'])

        for _, spectrum in spectras.iterrows():
            spectra_id = spectrum['id']
            spectra_idents = all_idents.query("spectre_id == @spectra_id")
            if len(spectra_idents) == 0:
                continue
            if criterion == "ppm":
                crit = 'ppm'
                asc = True
            else:
                crit = 'intensity_coverage'
                asc = False
            best_id = spectra_idents.sort_values(crit, ascending=asc).iloc[0]['id']
            await project.set_preferred_identification(spectra_id, best_id)
            counter += 1

    return counter


async def calculate_preferred_identifications_for_file(
    project: Project,
    spectra_file_id: int,
    criterion: Literal['ppm', 'intensity'],
    tool_settings: dict[int, dict]
) -> list[int]:
    """
    Calculate preferred identification IDs for a single spectra file.

    Selection logic:
    1. For each tool fetch candidate identifications:
       - ``ignore_criteria=True``  → all identifications without quality filters
         (flagged as *trusted*).
       - ``ignore_criteria=False`` → identifications that pass quality thresholds.
    2. Build two pools: *trusted* (from ignore_criteria tools) and *normal*.
    3. Per spectrum:
       - If trusted candidates exist → pick the best among trusted by criterion.
       - Otherwise → pick the best among normal candidates by criterion.
    4. Within each pool the selection criterion is:
       - ``criterion="ppm"``       → lowest |PPM|
       - ``criterion="intensity"`` → highest intensity_coverage

    Args:
        project: Project instance
        spectra_file_id: ID of spectra file to process
        criterion: "ppm" or "intensity"
        tool_settings: Tool-specific settings dict

    Returns:
        List of identification IDs that should be marked as preferred
    """
    if criterion not in ("ppm", "intensity"):
        raise ValueError(f"Invalid criterion: {criterion}. Must be 'ppm' or 'intensity'")

    trusted_frames: list[pd.DataFrame] = []
    normal_frames: list[pd.DataFrame] = []

    for tool_id, tool_params in tool_settings.items():
        ignore_criteria = tool_params.get("ignore_criteria", False)

        if ignore_criteria:
            # No quality filtering — trust every identification from this tool
            idents = await project.get_all_idents_for_preferred(
                spectra_file_id=spectra_file_id,
                tool_id=tool_id,
            )
            logger.debug(f"tool_id={tool_id} spectra_file_id={spectra_file_id} ignore_criteria=True rows={len(idents)}")
            if not idents.empty:
                # Compute sort key
                if criterion == "ppm":
                    idents['_sort_key'] = idents['ppm'].abs()
                else:
                    idents['_sort_key'] = idents['intensity_coverage']
                trusted_frames.append(idents.copy())
        else:
            max_ppm = tool_params.get("max_ppm", 50)
            min_score = tool_params.get("min_score", 0)
            min_ion_intensity_coverage = tool_params["min_ion_intensity_coverage"]
            min_len = tool_params.get("min_peptide_length", 7)
            max_len = tool_params.get("max_peptide_length", 30)
            min_peaks = tool_params.get("min_spectre_peaks", 1)
            top_peaks_count = tool_params.get("min_top_peaks", 1)
            min_ions = tool_params.get("min_ions_covered", 1)
            denovo_correction = tool_params.get("denovo_correction", False)
            denovo_correction_ppm = tool_params.get("denovo_correction_ppm", 50000)

            idents = await project.get_idents_for_preferred(
                spectra_file_id=spectra_file_id,
                tool_id=tool_id,
                min_score=min_score,
                max_abs_ppm=max_ppm if not denovo_correction else denovo_correction_ppm,
                intensity_coverage=min_ion_intensity_coverage,
                canonical_length=(min_len, max_len),
                spectre_peaks_count=min_peaks,
                ions_matched=min_ions,
                top_peaks_covered=top_peaks_count,
            )
            logger.debug(f"tool_id={tool_id} spectra_file_id={spectra_file_id} rows={len(idents)}")
            if not idents.empty:
                if denovo_correction:
                    idents['_sort_key'] = idents.apply(
                        lambda row: min(abs(row['ppm']), abs(row['matched_ppm'])), axis=1
                    )
                    idents = idents[idents['_sort_key'] <= max_ppm]
                else:
                    if criterion == "ppm":
                        idents['_sort_key'] = idents['ppm'].abs()
                    else:
                        idents['_sort_key'] = idents['intensity_coverage']
                if not idents.empty:
                    normal_frames.append(idents.copy())

    # --- Build per-spectrum best identification ---
    # Trusted pool takes priority; normal pool is used only where trusted is empty.
    result_ids: list[int] = []

    trusted_df = pd.concat(trusted_frames, ignore_index=True) if trusted_frames else pd.DataFrame()
    normal_df = pd.concat(normal_frames, ignore_index=True) if normal_frames else pd.DataFrame()

    # Collect all spectre_ids that have any candidate
    all_spectre_ids: set[int] = set()
    if not trusted_df.empty:
        all_spectre_ids |= set(trusted_df['spectre_id'].astype(int))
    if not normal_df.empty:
        all_spectre_ids |= set(normal_df['spectre_id'].astype(int))

    ascending = (criterion == "ppm")  # ppm → ascending (lower is better); intensity → descending

    for spectre_id in all_spectre_ids:
        # First try trusted pool
        if not trusted_df.empty:
            candidates = trusted_df[trusted_df['spectre_id'] == spectre_id]
            if not candidates.empty:
                sort_key = candidates['_sort_key'].dropna()
                if not sort_key.empty:
                    if ascending:
                        best_id = int(candidates.loc[sort_key.idxmin(), 'id'])
                    else:
                        best_id = int(candidates.loc[sort_key.idxmax(), 'id'])
                    result_ids.append(best_id)
                    continue

        # Fall back to normal pool
        if not normal_df.empty:
            candidates = normal_df[normal_df['spectre_id'] == spectre_id]
            if not candidates.empty:
                sort_key = candidates['_sort_key'].dropna()
                if not sort_key.empty:
                    if ascending:
                        best_id = int(candidates.loc[sort_key.idxmin(), 'id'])
                    else:
                        best_id = int(candidates.loc[sort_key.idxmax(), 'id'])
                    result_ids.append(best_id)

    return result_ids
