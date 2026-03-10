"""Peptide identification matching and selection."""
from typing import AsyncIterator, Literal

import pandas as pd
import npysearch as npy

from api.project.project import Project
from utils.logger import logger
from utils.lic import get_leucine_combinations
from utils.ppm import calculate_ppm, calculate_theor_mass, calculate_ppm_and_charge


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
            max_ppm = tool_params.get("max_ppm", 50000)
            min_score = tool_params.get("min_score", 0)
            min_ion_intensity_coverage = tool_params["min_ion_intensity_coverage"]
            min_len = tool_params.get("min_peptide_length", 7)
            max_len = tool_params.get("max_peptide_length", 30)

            idents = await project.get_identifications(spectra_file['id'], tool_id)

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


async def map_proteins(
        project: Project,
        tool_settings: dict[int, dict],
        only_prefered: bool = False,
        batch_size: int = 5000
) -> AsyncIterator[tuple[pd.DataFrame, int, int]]:
    """
    Performs protein mapping in batches.

    Args:
        project: Project instance
        tool_settings: Tool-specific settings
        only_prefered: Process only preferred identifications
        batch_size: Number of identifications per batch
    """
    fasta = await project.get_protein_db_to_search()
    max_acc = int(await project.get_setting('max_blast_accept', '5'))
    max_rej = int(await project.get_setting('max_blast_reject', '16'))

    for tool_id, tool_params in tool_settings.items():
        counter = 0
        has_batch_data = True
        max_ppm = tool_params.get("ppm", 50)
        denovo_correction = tool_params.get("denovo_correction", False)
        denovo_correction_ppm = tool_params.get("denovo_correction_ppm", 50000)
        leucine_combinatorics = tool_params.get("leucine_combinatorics", False)

        while has_batch_data:
            batch_data = await project.get_identifications(
                tool_id=tool_id,
                only_prefered=only_prefered,
                max_abs_ppm=max_ppm if not denovo_correction else denovo_correction_ppm,
                offset=counter,
                limit=batch_size,
            )
            if len(batch_data) == 0:
                has_batch_data = False
                break

            query = {}
            for _, row in batch_data[['id', 'canonical_sequence', 'pepmass']].iterrows():
                if leucine_combinatorics:
                    if 'I' in row['canonical_sequence'] or 'L' in row['canonical_sequence']:
                        for idx, variant in get_leucine_combinations(row['canonical_sequence']):
                            query[f"{row['id']}_{idx + 1}"] = variant
                    else:
                        query[str(row['id'])] = row['canonical_sequence']
                else:
                    query[str(row['id'])] = row['canonical_sequence']

            blast = pd.DataFrame(npy.blast(
                query,
                fasta,
                maxAccepts=max_acc,
                maxRejects=max_rej,
                alphabet='protein',
                minIdentity=tool_params['min_protein_identity'],
            ))
            blast['id'] = blast['QueryId'].apply(lambda x: int(x.split('_')[0]))
            blast = pd.merge(
                blast[['id', 'TargetId', 'TargetMatchSeq', 'Identity']],
                batch_data[['id', 'pepmass', 'ppm', 'charge', 'override_charge']],
                on='id',
                how='left'
            )

            uq_evidences = set(
                blast['id'].value_counts().reset_index(name='cnt').query('cnt==1')['id']
            )
            all_res = []
            for _, row in blast.iterrows():
                identity = row['Identity']
                pepmass = row['pepmass']
                matched_seq = row['TargetMatchSeq']

                # Use override_charge if available, fall back to spectrum charge,
                # otherwise scan charge range with calculate_ppm_and_charge
                eff_charge = row.get('override_charge') or row.get('charge')
                if eff_charge is not None and not pd.isna(eff_charge):
                    match_ppm = calculate_ppm(matched_seq, pepmass, int(eff_charge))
                    match_theor_mass = calculate_theor_mass(matched_seq)
                else:
                    match_ppm, _, match_theor_mass = calculate_ppm_and_charge(
                        matched_seq, pepmass
                    )

                if identity < 1.0:
                    if abs(match_ppm) >= abs(max_ppm):
                        continue
                all_res.append({
                    'protein_id': row['TargetId'],
                    'identification_id': int(row['id']),
                    'matched_sequence': matched_seq,
                    'identity': row['Identity'],
                    'unique_evidence': row['id'] in uq_evidences,
                    'matched_ppm': match_ppm,
                    'matched_theor_mass': match_theor_mass,
                })

            yield pd.json_normalize(all_res), len(all_res), tool_id
            counter += batch_size


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
        print(idents)
        if denovo_correction:
            idents['min_ppm'] = idents.apply(
                lambda row: min(abs(row['ppm']), abs(row['matched_ppm'])), axis=1
            )
            idents = idents.query('min_ppm <= @max_ppm')
        else:
            idents['min_ppm'] = idents['ppm'].abs()
        idents_not_merged.append(idents.copy())

    df = pd.concat(idents_not_merged, ignore_index=True)
    if df.empty:
        return []
    idx = df.groupby('spectre_id')['min_ppm'].idxmin()
    return [int(x) for x in df.loc[idx, 'id']]
