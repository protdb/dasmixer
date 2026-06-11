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

    idents_not_merged = []
    for tool_id, tool_params in tool_settings.items():
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
        logger.debug(idents)
        logger.debug(f"{tool_id} {spectra_file_id}")
        if denovo_correction:
            idents['min_ppm'] = idents.apply(
                lambda row: min(abs(row['ppm']), abs(row['matched_ppm'])), axis=1
            )
            idents = idents.query('min_ppm <= @max_ppm')
        else:
            try:
                idents['min_ppm'] = idents['ppm'].abs()
            except KeyError:
                idents['min_ppm'] = None
        idents_not_merged.append(idents.copy())

    df = pd.concat(idents_not_merged, ignore_index=True)
    if df.empty:
        return []
    idx = df.groupby('spectre_id')['min_ppm'].idxmin()
    return [int(x) for x in df.loc[idx, 'id']]
