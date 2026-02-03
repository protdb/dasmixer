from typing import AsyncIterator

import pandas as pd


def get_coverage(seq: str, peptides: list[str]) -> tuple[float, float]:
    map_list = ['-' for _ in range(len(seq))]
    for peptide in peptides:
        start_position = seq.find(peptide)
        if start_position == -1:
            print(f'incorrect peptide? {peptide} in {seq}')
            continue
        for idx, letter in enumerate(peptide):
            map_list[idx+start_position] = letter
    aa_match = len([x for x in map_list if x != '-'])
    return aa_match, aa_match/len(map_list) * 100


async def find_protein_identifications(
        joined_data: pd.DataFrame, # project.get_joined_peptide_data(is_preferred==True, protein_identified=True)
        sequences_db: dict[str, str], # project.get_protein_db_to_search()
        min_peptides: int,
        min_uq_evidence: int) -> AsyncIterator[tuple[pd.DataFrame, str]]:
    """

    :param joined_data:
    :param sequences_db:
    :param min_peptides:
    :param min_uq_evidence:
    :return:
    """
    samples = joined_data['sample_id'].unique()
    for sample in samples:
        data = joined_data[joined_data['sample_id'] == sample]
        proteins = data['protein_id'].unique()
        result_proteins = []
        for protein in proteins:
            sequence = sequences_db[protein]
            peptides = data.query('protein_id == @protein')['matched_sequence'].unique()
            uq_evidence = data.query('protein_id == @protein & unique_evidence == 1')['matched_sequence'].unique()
            intensity_sum = data.query('protein_id == @protein')['intensity'].sum()
            if len(peptides) < min_peptides or len(uq_evidence) < min_uq_evidence:
                continue
            coverage = get_coverage(sequence, peptides)
            result_proteins.append({
                'sample_id': sample,
                'protein_id': protein,
                'peptide_count': len(peptides),
                'uq_evidence_count': len(uq_evidence),
                'coverage': coverage,
                'intensity_sum': intensity_sum
            })
        yield pd.DataFrame(result_proteins), sample