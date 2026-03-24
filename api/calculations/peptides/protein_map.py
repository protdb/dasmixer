from typing import AsyncIterator

import npysearch as npy
import pandas as pd

from api import Project
from utils.lic import get_leucine_combinations
from utils.ppm import calculate_ppm, calculate_theor_mass, calculate_ppm_and_charge


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
            for _, row in batch_data[['id', 'canonical_sequence', 'sequence', 'pepmass']].iterrows():
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
