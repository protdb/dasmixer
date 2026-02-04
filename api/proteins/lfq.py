import pandas as pd
from typing import Literal
from ..project import Project
from .sempai import Protein, ProteomicSample, DigestionParams

async def calculate_lfq(
        project: Project,
        sample_id: int,
        methods: list[Literal['NSAF', 'iBAQ', 'emPAI', 'Top3']],
        enzyme: str = 'trypsin',
        min_length: int = 7,
        max_length: int = 30,
        max_cleavage_sites: int = 2,
        empai_base: float = 10.0
) -> pd.DataFrame:
    """
    Calculate label-free quantification for proteins in a sample.
    
    Args:
        project: Project instance
        sample_id: Sample ID to calculate LFQ for
        methods: List of LFQ methods to calculate
        enzyme: Digestion enzyme
        min_length: Minimum theoretical peptide length
        max_length: Maximum theoretical peptide length
        max_cleavage_sites: Maximum missed cleavages
        empai_base: Base value for emPAI calculation
    
    Returns:
        DataFrame with columns: protein_identification_id, algorithm, rel_value
    """
    print(f'Calculating LFQ for sample {sample_id}')
    dp = DigestionParams(
        enzyme=enzyme,
        min_peptide_length=min_length,
        max_peptide_length=max_length,
        max_cleavage_sites=max_cleavage_sites,
    )
    
    # Get protein identifications for this sample
    idents = await project.get_protein_identifications(sample_id=sample_id)
    print('collected idents...')
    print(idents)
    if len(idents) == 0:
        # Return empty DataFrame with correct structure
        return pd.DataFrame(columns=['protein_identification_id', 'algorithm', 'rel_value'])
    
    # Get peptide data
    all_peptides = await project.get_joined_peptide_data(
        is_preferred=True,
        protein_identified=True,
        sample_id=int(sample_id),
    )
    print(all_peptides)
    # Get protein sequences
    fasta = await project.get_protein_db_to_search()
    
    # Build Protein objects for sempai
    proteins = []
    for _, row in idents.iterrows():
        protein_id = row['protein_id']
        peptides = all_peptides[all_peptides['protein_id'] == protein_id]
        
        if len(peptides) == 0:
            continue
        
        proteins.append(
            Protein(
                accession=protein_id,
                sequence=fasta[protein_id],
                peptides=list(peptides['matched_sequence']),
                intensities=list(peptides['intensity']),
                empai_base=empai_base,
                observable_parameters=dp
            )
        )
    print(proteins)
    if len(proteins) == 0:
        return pd.DataFrame(columns=['protein_identification_id', 'algorithm', 'rel_value'])
    
    # Calculate quantification
    sample_data = ProteomicSample(
        proteins=proteins,
    )
    result_df = sample_data.get_results(
        all_protein_details=False,
        quantification_methods=methods,
        calculate_coverage=False,
        absolute_concentrations='none'
    )
    print('!!!!!! RESULT_DF:')
    print(result_df)
    
    # Merge with identification IDs
    all_res = pd.merge(
        result_df,
        idents,
        left_on='accession',
        right_on='protein_id',
        how='inner',
    )
    print(all_res)
    print('!!!!!! ALL_RES:')
    print(all_res.columns)
    # Pivot results to long format
    final = []
    for method in methods:
        cur_subset = all_res[['id', f'{method}_normalized']]
        cur_subset['algorithm'] = method
        cur_subset = cur_subset[['id', 'algorithm', f'{method}_normalized']]
        cur_subset.columns = ['protein_identification_id', 'algorithm', 'rel_value']
        final.append(cur_subset)
    
    return pd.concat(final, ignore_index=True)
