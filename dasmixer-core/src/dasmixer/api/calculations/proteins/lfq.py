import pandas as pd
from typing import Literal, Optional
from dasmixer.api.project import Project
from dasmixer.utils.logger import logger
from .sempai import Protein, ProteomicSample, DigestionParams


async def calculate_lfq(
        project: Project,
        sample_id: int,
        methods: list[Literal['NSAF', 'iBAQ', 'emPAI', 'Top3']],
        enzyme: str = 'trypsin',
        min_length: int = 7,
        max_length: int = 30,
        max_cleavage_sites: int = 2,
        empai_base: float = 10.0,
        abs_enabled: bool = False,
        total_protein_gl: float | None = None,
        reference_protein_gl: float | None = None,
        reference_protein_id: str = "P02768",
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
        abs_enabled: Whether to calculate absolute concentrations
        total_protein_gl: Total protein concentration in g/L for this sample
        reference_protein_gl: Reference protein concentration in g/L for this sample
        reference_protein_id: UniProt ID of the reference protein (default P02768)

    Returns:
        DataFrame with columns: protein_identification_id, algorithm, rel_value
                                (, abs_value_mol, abs_value_gl) if abs_enabled
    """
    logger.debug(f'Calculating LFQ for sample {sample_id}')
    dp = DigestionParams(
        enzyme=enzyme,
        min_peptide_length=min_length,
        max_peptide_length=max_length,
        max_cleavage_sites=max_cleavage_sites,
    )

    # Get protein identifications for this sample
    idents = await project.get_protein_identifications(sample_id=sample_id)
    logger.debug('collected idents...')
    logger.debug(idents)
    if len(idents) == 0:
        cols = ['protein_identification_id', 'algorithm', 'rel_value']
        if abs_enabled:
            cols += ['abs_value_mol', 'abs_value_gl']
        return pd.DataFrame(columns=cols)

    # Get peptide data
    all_peptides = await project.get_joined_peptide_data(
        is_preferred=True,
        protein_identified=True,
        sample_id=int(sample_id),
    )
    logger.debug(all_peptides)
    # Get protein sequences
    fasta = await project.get_protein_db_to_search()

    # Build Protein objects for sempai
    proteins = []
    skipped_no_seq = 0
    for _, row in idents.iterrows():
        protein_id = row['protein_id']
        peptides = all_peptides[all_peptides['protein_id'] == protein_id]

        if len(peptides) == 0:
            continue

        if protein_id not in fasta:
            logger.warning(
                f'No FASTA sequence for protein {protein_id} — skipping LFQ for this protein'
            )
            skipped_no_seq += 1
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
    logger.debug(proteins)
    if len(proteins) == 0:
        if skipped_no_seq > 0:
            raise ValueError(
                f'Cannot calculate LFQ for sample {sample_id}: '
                f'no protein sequences available '
                f'({skipped_no_seq} protein(s) skipped — FASTA sequence missing, '
                f'possibly deprecated UniProt entries)'
            )
        cols = ['protein_identification_id', 'algorithm', 'rel_value']
        if abs_enabled:
            cols += ['abs_value_mol', 'abs_value_gl']
        return pd.DataFrame(columns=cols)

    # Calculate quantification
    if abs_enabled and (total_protein_gl is not None or reference_protein_gl is not None):
        sample_data = ProteomicSample(
            proteins=proteins,
            total_protein_gl=total_protein_gl,
            reference_protein_gl=reference_protein_gl,
            reference_protein_accession=reference_protein_id,
        )
        result_df = sample_data.get_results(
            all_protein_details=False,
            quantification_methods=methods,
            calculate_coverage=False,
            absolute_concentrations='all',
        )
    else:
        sample_data = ProteomicSample(proteins=proteins)
        result_df = sample_data.get_results(
            all_protein_details=False,
            quantification_methods=methods,
            calculate_coverage=False,
            absolute_concentrations='none',
        )
    logger.debug('RESULT_DF:')
    logger.debug(result_df)

    # Merge with identification IDs
    all_res = pd.merge(
        result_df,
        idents,
        left_on='accession',
        right_on='protein_id',
        how='inner',
    )
    logger.debug(all_res)
    logger.debug('ALL_RES:')
    logger.debug(all_res.columns)

    # Pivot results to long format
    final = []
    for method in methods:
        if abs_enabled:
            # Preferred source selection per method
            pref = 'total' if method in ('emPAI', 'NSAF') else 'reference'
            fallback = 'reference' if pref == 'total' else 'total'
            abs_norm_col = f'{method}_normalized'
            abs_gl_col = f'{method}_abs_{pref}_gl'
            abs_mol_col = f'{method}_abs_{pref}_mol'

            # Fallback if preferred is NaN
            fallback_gl = f'{method}_abs_{fallback}_gl'
            fallback_mol = f'{method}_abs_{fallback}_mol'

            # Build rows
            rows = []
            for _, row in all_res.iterrows():
                val_gl = row.get(abs_gl_col)
                val_mol = row.get(abs_mol_col)
                if val_gl is None or (not isinstance(val_gl, str) and pd.isna(val_gl)):
                    val_gl = row.get(fallback_gl)
                if val_mol is None or (not isinstance(val_mol, str) and pd.isna(val_mol)):
                    val_mol = row.get(fallback_mol)
                val_rel = row.get(abs_norm_col, 0.0)
                if val_rel is None or (not isinstance(val_rel, str) and pd.isna(val_rel)):
                    val_rel = 0.0

                rows.append({
                    'protein_identification_id': row['id'],
                    'algorithm': method,
                    'rel_value': float(val_rel) if val_rel is not None else None,
                    'abs_value_mol': float(val_mol) if val_mol is not None and not pd.isna(val_mol) else None,
                    'abs_value_gl': float(val_gl) if val_gl is not None and not pd.isna(val_gl) else None,
                })
            if rows:
                final.append(pd.DataFrame(rows))
        else:
            cur_subset = all_res[['id', f'{method}_normalized']].copy()
            cur_subset['algorithm'] = method
            cur_subset = cur_subset[['id', 'algorithm', f'{method}_normalized']]
            cur_subset.columns = ['protein_identification_id', 'algorithm', 'rel_value']
            final.append(cur_subset)

    if final:
        return pd.concat(final, ignore_index=True)
    else:
        cols = ['protein_identification_id', 'algorithm', 'rel_value']
        if abs_enabled:
            cols += ['abs_value_mol', 'abs_value_gl']
        return pd.DataFrame(columns=cols)
