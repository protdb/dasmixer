"""Peptide identification matching and selection."""
from typing import AsyncIterator

import pandas as pd
import npysearch as npy
from click.core import batch

from api.project.project import Project
from utils.logger import logger
from utils.ppm import calculate_ppm
from pyteomics.mass import calculate_mass


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
    
    Returns:
        Number of spectra processed
    
    Raises:
        ValueError: If invalid criterion or settings provided
    
    TODO: Implement the full logic
    - Ion fragment generation
    - PPM-based matching
    - Intensity coverage calculation
    - Database updates
    
    Example:
        >>> ion_settings = {
        ...     'ion_types': ['b', 'y'],
        ...     'water_loss': False,
        ...     'nh3_loss': False,
        ...     'ppm_threshold': 20.0
        ... }
        >>> tool_settings = {
        ...     1: {
        ...         'max_ppm': 50.0,
        ...         'min_score': 0.8,
        ...         'min_ion_intensity_coverage': 25.0
        ...     }
        ... }
        >>> async def your_function():
        >>>     count = await select_preferred_identifications(
        ...         project, "intensity", ion_settings, tool_settings
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
            min_score = tool_params.get("min_score", 0)
            min_ion_intensity_coverage = tool_params["min_ion_intensity_coverage"]
            idents = await project.get_identifications(
                spectra_file['id'], tool_id
            )
            if not tool_params.get("denovo_correction", False):
                query = "ppm <= @max_ppm and score >= @min_score and intensity_coverage >= @min_ion_intensity_coverage"
            else:
                query = "ppm <= 50000 and score >= @min_score and intensity_coverage >= @min_ion_intensity_coverage"
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
        batch_size = 1000
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
    counter = 0
    max_acc = int(await project.get_setting('max_blast_accept', '5'))
    max_rej = int(await project.get_setting('max_blast_reject', '16'))
    for tool_id, tool_setting in tool_settings.items():
        batch_data = await project.get_identifications(
            tool_id=tool_id,
            only_prefered=only_prefered,
            offset=counter,
            limit=batch_size,
        )
        query = {}

        for _, row in batch_data[['id', 'canonical_sequence']].iterrows():
            query[row['id']] = row['canonical_sequence']
        blast = pd.DataFrame(npy.blast(
            query,
            fasta,
            maxAccepts=max_acc,
            maxRejects=max_rej,
            minIdentity=tool_setting['min_protein_identity'],
        ))
        uq_evidences = set(blast['QueryId'].value_counts().reset_index(name='cnt').query('cnt==1')['QueryId'])
        all_res = []
        for _, row in blast.iterrows():
            all_res.append({
                'protein_id': row['TargetId'],
                'identification_id': int(row['QueryId']),
                'matched_sequence': row['TargetMatchSeq'],
                'identity': row['Identity'],
                'uq_evidence': row['QueryId'] in uq_evidences,
                'matched_ppm': None,
                'matched_theor_mass': calculate_mass(sequence=row['TargetMatchSeq'])
            })
        yield pd.json_normalize(all_res), len(all_res), tool_id