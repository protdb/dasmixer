import pandas as pd
from typing import Literal
from ..project import Project
from .sempai import Protein, ProteomicSample, DigestionParams

async def calculate_lfq(
        project: Project,
        sample_id: int,
        methods: list[Literal['NSAF', 'iBAQ', 'emPAI', 'top3']],
        enzyme: str = 'trypsin',
        min_length: int = 7,
        max_length: int = 30,
        max_clevage_sites: int = 2,
        empai_base: float = 10.0
) -> pd.DataFrame:
    dp = DigestionParams(
        enzyme=enzyme,
        min_peptide_length=min_length,
        max_peptide_length=max_length,
        max_cleavage_sites=max_clevage_sites,
    )
    idents = pd.json_normalize(await project._fetchall(
        "select id, protein_id from protein_identification_result where sample_id = ?", (sample_id,)
    )) #TODO: Заменить на вызов, который вернет результаты идентификацй
    all_peptides = await project.get_joined_peptide_data(
        is_preferred=True,
        protein_identified=True,
        sample_id=sample_id,
    )
    fasta = await project.get_protein_db_to_search()
    proteins = []
    for protein in idents['protein_id']:
        peptides = all_peptides[all_peptides['protein_id'] == protein]

        proteins.append(
            Protein(
                accession=protein,
                sequence=fasta[protein],
                peptides=list(peptides['matched_sequence']),
                intensities=list(peptides['intensity']),
                empai_base=empai_base,
                observable_parameters=dp
            )
        )
    sample_data = ProteomicSample(
        proteins=proteins,
    )
    result_df = sample_data.get_results(
        all_protein_details=False,
        quantification_methods=methods,
        calculate_coverage=False,
        absolute_concentrations='none'
    )
    all_res = pd.merge(
        result_df,
        idents,
        left_on='accession',
        right_on='protein_id',
        how='inner',
    )
    final = []
    for method in methods:
        cur_subset = all_res[['id', f'{method}_norm']]
        cur_subset['algorithm'] = method
        cur_subset = cur_subset[['id', 'algorithm' f'{method}_norm']]
        cur_subset.columns = ['protein_identification_id', 'algorithm', 'rel_value']
        final.append(cur_subset)
    return pd.concat(final, ignore_index=True)
