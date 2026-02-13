"""Peptide identification matching and selection."""
from typing import AsyncIterator, Literal

import pandas as pd
import npysearch as npy

from api.project.project import Project
from utils.logger import logger
from pyteomics.mass import calculate_mass
from pyteomics.auxiliary import PyteomicsError

canonical_aa = 'ARNDCQEGHILKMFPSTWYV'
avg_mass = calculate_mass(canonical_aa) / len(canonical_aa)

def safe_canon_calculate_mass(sequence: str) -> float:
    """

    :param sequence:
    :return:
    """
    try:
        return calculate_mass(proforma=sequence)
    except PyteomicsError:
        cn_seq = ''
        nc_seq = ''
        for letter in sequence:
            if letter.upper() in canonical_aa:
                cn_seq += letter
            else:
                nc_seq += letter
        return calculate_mass(cn_seq) + len(nc_seq) * avg_mass



async def select_preferred_identifications(
    project: Project,
    criterion: str,
    tool_settings: dict[int, dict]
) -> int:
    """
    Select preferred identifications for all spectra based on criterion.
    
    This function performs the following:
    1. Load all identifications from the database
    2. For each spectrum with multiple identifications:
       - Apply tool-specific filters (max_ppm, min_score, min_ion_intensity_coverage)
       - Calculate ion match coverage based on ion_settings
       - Select best identification based on criterion
       - Mark as preferred (is_preferred=1)
    3. Update database with preferred selections
    
    Args:
        project: Project instance
        criterion: Selection criterion
            - "ppm": Select identification with lowest PPM error
            - "intensity": Select identification with highest ion intensity coverage
        tool_settings: Tool-specific settings, mapping tool_id to:
            - max_ppm: Maximum allowed PPM error (float)
            - min_score: Minimum identification score (float)
            - min_ion_intensity_coverage: Minimum % intensity coverage (float)
            - use_protein_from_file: Use protein IDs from file (bool)
            - min_protein_identity: Minimum protein sequence identity (float)
            - denovo_correction: Apply de novo correction (bool)
            - min_peptide_length: Minimum peptide length (int, default 7) - NEW
            - max_peptide_length: Maximum peptide length (int, default 30) - NEW
    
    Returns:
        Number of spectra processed
    
    Raises:
        ValueError: If invalid criterion or settings provided

    - Ion fragment generation
    - PPM-based matching
    - Intensity coverage calculation
    - Database updates
    
    Example:
        >>> tool_settings = {
        ...     1: {
        ...         'max_ppm': 50.0,
        ...         'min_score': 0.8,
        ...         'min_ion_intensity_coverage': 25.0,
        ...         'min_peptide_length': 7,
        ...         'max_peptide_length': 30
        ...     }
        ... }
        >>> async def your_function():
        >>>     count = await select_preferred_identifications(
        ...         project, "intensity", tool_settings
        ...     )
        >>>     print(f"Processed {count} spectra")
    """
    logger.info(f"Starting preferred identification selection (criterion: {criterion})")
    logger.debug(f"Tool settings: {tool_settings}")
    counter = 0
    # Validate criterion
    if criterion not in ("ppm", "intensity"):
        raise ValueError(f"Invalid criterion: {criterion}. Must be 'ppm' or 'intensity'")
    spectra_files = await project.get_spectra_files()
    for _, spectra_file in spectra_files.iterrows():
        idents_not_merged = []
        for tool_id, tool_params in tool_settings.items():
            max_ppm = tool_params.get("max_ppm", 50000)
            min_ppm = max_ppm * -1
            min_score = tool_params.get("min_score", 0)
            min_ion_intensity_coverage = tool_params["min_ion_intensity_coverage"]
            min_len = tool_params.get("min_peptide_length", 7)  # NEW
            max_len = tool_params.get("max_peptide_length", 30)  # NEW
            
            idents = await project.get_identifications(
                spectra_file['id'], tool_id
            )
            
            # Add length filtering - NEW
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
        best_ids = []
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
            best_ids.append(str(best_id))
            await project.set_preferred_identification(spectra_id, best_id)

    return counter


async def map_proteins(
        project: Project,
        tool_settings: dict[int, dict],
        only_prefered: bool = False,
        batch_size = 5000
) -> AsyncIterator[tuple[pd.DataFrame, int, int]]:
    """
    Performs protein mapping in batches
    :param project:
    :param tool_settings:
    :param only_prefered:
    :param batch_size:
    :return:
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
            dumb_search_results = []
            query = {}
            for _, row in batch_data[['id', 'canonical_sequence']].iterrows():
                dumb_found = False
                # for p_id, seq in fasta.items():
                #     if row['canonical_sequence'] in seq:
                #         dumb_found = True
                #         dumb_search_results.append({
                #             'QueryId': str(row['id']),
                #             'TargetId': p_id,
                #             'TargetMatchSeq': row['canonical_sequence'],
                #             'Identity': 1.0
                #         })
                if not dumb_found:
                    query[str(row['id'])] = row['canonical_sequence']
            blast = pd.DataFrame(npy.blast(
                query,
                fasta,
                maxAccepts=max_acc,
                maxRejects=max_rej,
                alphabet='protein',
                minIdentity=tool_params['min_protein_identity'],
            ))
            print(blast)
            blast = blast[['QueryId', 'TargetId', 'TargetMatchSeq', 'Identity']]
            # blast = pd.concat(
            #     [blast, pd.json_normalize(dumb_search_results)],
            # )
            uq_evidences = set(blast['QueryId'].value_counts().reset_index(name='cnt').query('cnt==1')['QueryId'])
            all_res = []
            for _, row in blast.iterrows():
                all_res.append({
                    'protein_id': row['TargetId'],
                    'identification_id': int(row['QueryId']),
                    'matched_sequence': row['TargetMatchSeq'],
                    'identity': row['Identity'],
                    'unique_evidence': row['QueryId'] in uq_evidences,
                    'matched_ppm': None,
                    'matched_theor_mass': safe_canon_calculate_mass(sequence=row['TargetMatchSeq'])
                })
            yield pd.json_normalize(all_res), len(all_res), tool_id
            counter += batch_size


async def calculate_preferred_identifications_for_file(
    project: Project,
    spectra_file_id: int,
    criterion: Literal['ppm', 'intensity'],
    tool_settings: dict[int, dict]
) -> list[int]:
    if criterion not in ("ppm", "intensity"):
        raise ValueError(f"Invalid criterion: {criterion}. Must be 'ppm' or 'intensity'")
    idents_not_merged = []
    for tool_id, tool_params in tool_settings.items():
        max_ppm = tool_params.get("max_ppm", 50)
        min_score = tool_params.get("min_score", 0)
        min_ion_intensity_coverage = tool_params["min_ion_intensity_coverage"]
        min_len = tool_params.get("min_peptide_length", 7)  # NEW
        max_len = tool_params.get("max_peptide_length", 30)  # NEW
        denovo_correction = tool_params.get("denovo_correction", False)
        denovo_correction_ppm = tool_params.get("denovo_correction_ppm", 50000)
        idents = await project.get_idents_for_preferred(
            spectra_file_id=spectra_file_id,
            tool_id=tool_id,
            min_score=min_score,
            max_abs_ppm=max_ppm if not denovo_correction else denovo_correction_ppm,
            intensity_coverage=min_ion_intensity_coverage,
            canonical_length=(min_len, max_len),
        )
        if denovo_correction:
            idents['min_ppm'] = idents.apply(
                lambda row: min(abs(row['ppm']), abs(row('matched_ppm'))), axis=1
            )
            idents = idents.query('min_ppm <= @max_ppm')
        idents_not_merged.append(idents.copy())
    df = pd.concat(idents_not_merged, ignore_index=True)
    idx = df.groupby('spectre_id')['ppm'].idxmin()
    return [int(x) for x in df.loc[idx, ['id']]['id']]

    # spectras = await project.get_spectra(spectra_file_id)
    # best_ids = []
    # for _, spectrum in spectras.iterrows():
    #     spectra_id = spectrum['id']
    #     spectra_idents = all_idents.query("spectre_id == @spectra_id")
    #     if len(spectra_idents) == 0:
    #         continue
    #     if criterion == "ppm":
    #         crit = 'ppm'
    #         asc = True
    #     else:
    #         crit = 'intensity_coverage'
    #         asc = False
    #     best_id = spectra_idents.sort_values(crit, ascending=asc).iloc[0]['id']
    #     best_ids.append(best_id)
