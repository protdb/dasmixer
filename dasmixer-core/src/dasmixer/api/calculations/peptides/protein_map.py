"""
Protein mapping pipeline.

Maps peptide identifications to proteins via BLAST (npysearch), then:
- For identity == 1.0: copies PPM / ion-coverage metrics directly from identification.
- For identity < 1.0: recalculates PPM and ion coverage using SeqFixer and
  match_predictions.  The CPU-bound per-row work is offloaded to worker
  processes via ``protein_map_worker.process_protein_map_row``
  (ProcessPoolExecutor).  Match Correction Criteria are then applied to
  decide whether the match is accepted.  Optionally saves rejected partial
  matches as AA substitution candidates.

Results are written directly into the project database in batches.
"""

import asyncio
import math
import os
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor

try:
    import npysearch as npy
except ImportError:  # pragma: no cover
    npy = None  # type: ignore[assignment]

import pandas as pd
from dasmixer.api.calculations.peptides.protein_map_worker import process_protein_map_row
from dasmixer.api.config import config as _config
from dasmixer.utils.exceptions import DasmixerException
from dasmixer.utils.lic import get_leucine_combinations
from dasmixer.utils.logger import logger
from dasmixer.utils.seqfixer_utils import DEFAULT_PTM_CODES, PTMS, FixedPTM

from dasmixer.api import Project
from dasmixer.api.calculations.ppm import SeqFixer

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _nan_to_none(val):
    """Convert NaN / None to None; leave other values unchanged."""
    try:
        if val is None:
            return None
        f = float(val)
        return None if math.isnan(f) else val
    except (TypeError, ValueError):
        return None


def _safe_float(val) -> float | None:
    v = _nan_to_none(val)
    return float(v) if v is not None else None


def _safe_int(val) -> int | None:
    v = _nan_to_none(val)
    return int(float(v)) if v is not None else None


def _get_effective_charge(row: dict) -> int | None:
    """Return override_charge if set, fall back to spectrum charge."""
    ch = _nan_to_none(row.get('override_charge')) or _nan_to_none(row.get('charge'))
    return int(float(ch)) if ch is not None else None


def _filter_worse_idents(df: pd.DataFrame) -> pd.DataFrame:
    res = []
    uq_idents_id = df['identification_id'].unique()
    for ident in uq_idents_id:
        subset = df[df['identification_id'] == ident]
        max_identity = subset['identity'].max()
        subset = subset[subset['identity'] == max_identity]
        subset.drop_duplicates(['protein_id'], inplace=True)
        res.append(subset)
    return pd.concat(res, ignore_index=True)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def map_proteins(
    project: Project,
    tool_settings: dict[int, dict],
    ion_params: dict,
    fragment_charges: list[int],
    seqfixer_params: dict,
    batch_size: int = 5000,
    sample_id: int | None = None,
    use_src_protein_ids: bool = False,
    progress_callback: Callable[[int, int], None] | None = None,
    stop_check: Callable[[], bool] | None = None,
) -> None:
    """
    Perform protein mapping in batches and write the results into the
    project database directly.

    This function returns ``None``: after each processed batch the peptide
    matches are written internally via ``project.add_peptide_matches_batch()``
    followed by ``project._commit()``; a final ``project.save()`` is performed
    after all tools are processed.  Callers must NOT call
    ``add_peptide_matches_batch`` themselves.

    The CPU-bound per-row recalculation (identity < 1.0 branch) is
    parallelized across worker processes (``ProcessPoolExecutor``), one
    executor per tool; each row is handled by
    ``dasmixer.api.calculations.peptides.protein_map_worker.process_protein_map_row``.

    Args:
        project: Project instance.
        tool_settings: Per-tool settings keyed by tool_id.  Each dict should
            contain at minimum: min_protein_identity, max_ppm, ptm_list,
            max_ptm, leucine_combinatorics, denovo_correction,
            denovo_correction_ppm, match_correction_criteria,
            save_aa_substitutions, min_score, min_ion_intensity_coverage,
            min_peptide_length, max_peptide_length.
        ion_params: Dict representation of IonMatchParameters
            (ions, tolerance, mode, water_loss, ammonia_loss).
        fragment_charges: Fragment charge states for match_predictions.
        seqfixer_params: Common SeqFixer parameters:
            target_ppm, min_charge, max_charge, max_isotope_offset,
            force_isotope_offset (bool).
        batch_size: Identifications per DB batch.
        sample_id: If provided, only process identifications for this sample.
        use_src_protein_ids: If True, for identifications that have
            src_file_protein_id set, create exact-match peptide_match
            records directly (bypassing BLAST). BLAST is then only run
            for identifications without src_file_protein_id.
        progress_callback: Optional callable invoked after each processed
            batch as ``progress_callback(processed, total)``, where
            ``processed`` is the cumulative number of identifications
            fetched/consumed so far across all tools/batches, and
            ``total`` is always ``-1`` (the total number of
            identifications to process is unknown in advance).
        stop_check: Optional callable invoked after each processed batch;
            if it returns True, processing stops — the current tool's
            batch loop and all remaining tools are skipped.

    Returns:
        None. Results are written into the project database internally.
    """
    if npy is None:
        raise ImportError(
            "npysearch is not installed. Install dasmixer-core with the 'proteins' extra: "
            "pip install 'dasmixer-core[proteins]'"
        )

    fasta = await project.get_protein_db_to_search()
    max_acc: int = int((await project.get_setting('max_blast_accept')) or 5)
    max_rej: int = int((await project.get_setting('max_blast_reject')) or 16)

    # Common SeqFixer config
    target_ppm: float = seqfixer_params.get('target_ppm', 50.0)
    min_charge: int = seqfixer_params.get('min_charge', 1)
    max_charge: int = seqfixer_params.get('max_charge', 4)
    max_isotope_offset: int = seqfixer_params.get('max_isotope_offset', 2)
    force_isotope: bool = seqfixer_params.get('force_isotope_offset', False)

    worker_count = _config.max_cpu_threads or max(1, (os.cpu_count() or 2) - 1)
    loop = asyncio.get_running_loop()
    total_processed = 0

    for tool_id, tool_params in tool_settings.items():
        # Per-tool PTM list
        ptm_names: list[str] | None = tool_params.get('ptm_list', None)
        if ptm_names is None:
            ptms: list[FixedPTM] = [x for x in PTMS if x.code in DEFAULT_PTM_CODES]
        else:
            ptms = [x for x in PTMS if x.code in ptm_names]

        fixer = SeqFixer(
            ptm_list=ptms,
            max_ptm=tool_params.get('max_ptm', 5),
            target_ppm=target_ppm,
            override_charges=(min_charge, max_charge),
            max_isotope_offset=max_isotope_offset,
            force_isotope_offset_lookover=force_isotope,
        )

        max_ppm: float = tool_params.get('max_ppm', 50.0)
        trust_everyting = tool_params.get('ignore_criteria', False)
        denovo_correction: bool = tool_params.get('denovo_correction', False)
        denovo_correction_ppm: float = tool_params.get('denovo_correction_ppm', 50000.0)
        leucine_combinatorics: bool = tool_params.get('leucine_combinatorics', False)
        match_correction_criteria: list[str] = tool_params.get('match_correction_criteria', [])
        save_aa_substitutions: bool = tool_params.get('save_aa_substitutions', False)
        if not trust_everyting:
            query_ppm = denovo_correction_ppm if denovo_correction else max_ppm
        else:
            query_ppm = None

        counter = 0
        all_res: list[dict] = []
        stopped = False

        async def _flush_matches() -> None:
            """Write accumulated matches into the DB and reset the buffer."""
            nonlocal all_res
            if all_res:
                matches_df = _filter_worse_idents(pd.json_normalize(all_res))
                await project.add_peptide_matches_batch(matches_df)
                await project._commit()
            all_res = []

        # Executor is created PER TOOL so it is torn down when the tool finishes
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            while True:
                logger.debug('retrieving batch data...')
                batch_data = await project.get_identifications(
                    tool_id=tool_id,
                    max_abs_ppm=query_ppm,
                    offset=counter,
                    limit=batch_size,
                    sample_id=sample_id,
                )
                if len(batch_data) == 0:
                    break
                logger.debug('batch data retrieved!')
                # Captured BEFORE any src-protein splitting so progress
                # is reported accurately
                batch_ident_count = len(batch_data)
                # ----------------------------------------------------------------
                # Step: handle identifications with src_file_protein_id (pre-BLAST)
                # ----------------------------------------------------------------
                if use_src_protein_ids and len(batch_data) > 0:
                    has_src_protein = batch_data['src_file_protein_id'].notna() & \
                                      (batch_data['src_file_protein_id'] != '')

                    src_protein_rows = batch_data[has_src_protein]
                    blast_rows = batch_data[~has_src_protein]  # Only these go to BLAST
                    # Build exact-match results for src_protein rows
                    for _, row in src_protein_rows.iterrows():
                        ident_id = int(row['id'])
                        raw_ids = str(row['src_file_protein_id'])
                        protein_ids = [pid.strip() for pid in raw_ids.split(';') if pid.strip()]

                        canon = str(row['canonical_sequence'])

                        for protein_id in protein_ids:
                            all_res.append({
                                'protein_id': protein_id,
                                'identification_id': ident_id,
                                'matched_sequence': canon,
                                'identity': 1.0,
                                'unique_evidence': 1 if len(protein_ids) == 1 else 0,  # will be recomputed below
                                'matched_ppm': _safe_float(row.get('ppm')),
                                'matched_theor_mass': _safe_float(row.get('theor_mass')),
                                'matched_coverage_percent': _safe_float(row.get('intensity_coverage')),
                                'matched_peaks': _safe_int(row.get('ions_matched')),
                                'matched_top_peaks': _safe_int(row.get('top_peaks_covered')),
                                'matched_ion_type': _nan_to_none(row.get('ion_match_type')),
                                'matched_sequence_modified': None,
                                'substitution': False,
                            })

                    # Override batch_data to only include rows without src_file_protein_id
                    batch_data = blast_rows

                    if len(batch_data) == 0:
                        await _flush_matches()
                        counter += batch_size
                        continue
                    # --- end Step: handle src_file_protein_id ---
                # ----------------------------------------------------------------
                # Build BLAST query dict
                # ----------------------------------------------------------------
                query: dict[str, str] = {}
                for _, row in batch_data[
                    ['id', 'canonical_sequence', 'sequence', 'pepmass']
                ].iterrows():
                    canon = str(row['canonical_sequence'])
                    ident_id = int(row['id'])
                    logger.debug(f"{ident_id} {canon}")
                    if leucine_combinatorics and ('I' in canon or 'L' in canon):
                        for idx, variant in enumerate(get_leucine_combinations(canon)):
                            query[f"{ident_id}_{int(idx) + 1}"] = variant
                    else:
                        query[str(ident_id)] = canon
                logger.debug('performing blast...')
                blast_df = pd.DataFrame(npy.blast(
                    query,
                    fasta,
                    maxAccepts=max_acc,
                    maxRejects=max_rej,
                    alphabet='protein',
                    minIdentity=tool_params['min_protein_identity'],
                ))

                if blast_df.empty:
                    await _flush_matches()
                    counter += batch_size
                    continue

                blast_df['id'] = blast_df['QueryId'].apply(lambda x: int(x.split('_')[0]))

                # Join identification metadata onto blast results
                ident_cols = [
                    'id', 'sequence', 'canonical_sequence', 'pepmass',
                    'ppm', 'theor_mass', 'charge', 'override_charge',
                    'isotope_offset', 'intensity_coverage',
                    'ions_matched', 'top_peaks_covered', 'ion_match_type',
                ]
                blast_df = pd.merge(
                    blast_df[['id', 'TargetId', 'TargetMatchSeq', 'Identity']],
                    batch_data[ident_cols],
                    on='id',
                    how='left',
                )

                # ----------------------------------------------------------------
                # Identify which identification IDs need spectra
                # ----------------------------------------------------------------
                partial_ids: list[int] = [int(x) for x in blast_df.loc[blast_df['Identity'] < 1.0, 'id'].unique()]
                logger.debug("partial_ids count=%d", len(partial_ids))
                spectra_map: dict[int, dict] = {}
                if partial_ids:
                    logger.debug(f'reading spectra for {len(partial_ids)}')
                    spectra_map = await project.get_spectra_for_identification_ids(partial_ids)

                # ----------------------------------------------------------------
                # Unique-evidence set (single-protein identifications)
                # ----------------------------------------------------------------
                uq_evidences: set[int] = set(
                    blast_df['id']
                    .value_counts()
                    .reset_index(name='cnt')
                    .query('cnt == 1')['id']
                )

                # ----------------------------------------------------------------
                # Process each BLAST row
                # ----------------------------------------------------------------
                futures: list = []
                for _, row in blast_df.iterrows():
                    identity: float = float(row['Identity'])
                    ident_id: int = int(row['id'])
                    matched_seq: str = str(row['TargetMatchSeq'])
                    protein_id: str = str(row['TargetId'])

                    if identity == 1.0:
                        # Full match — copy metrics from identification
                        # Also copy sequence (ProForma with PTMs) as
                        # matched_sequence_modified per Вопрос 6 answer
                        orig_sequence = row.get('sequence')
                        if orig_sequence and str(orig_sequence) != matched_seq:
                            matched_seq_modified = str(orig_sequence)
                        else:
                            matched_seq_modified = None

                        all_res.append({
                            'protein_id': protein_id,
                            'identification_id': ident_id,
                            'matched_sequence': matched_seq,
                            'identity': 1.0,
                            'unique_evidence': ident_id in uq_evidences,
                            'matched_ppm': _safe_float(row.get('ppm')),
                            'matched_theor_mass': _safe_float(row.get('theor_mass')),
                            'matched_coverage_percent': _safe_float(row.get('intensity_coverage')),
                            'matched_peaks': _safe_int(row.get('ions_matched')),
                            'matched_top_peaks': _safe_int(row.get('top_peaks_covered')),
                            'matched_ion_type': _nan_to_none(row.get('ion_match_type')),
                            'matched_sequence_modified': matched_seq_modified,
                            'substitution': False,
                        })
                        continue

                    # identity < 1.0 — need spectra for recalculation
                    spectrum = spectra_map.get(ident_id)
                    if spectrum is None:
                        # Spectrum data unavailable — skip
                        raise DasmixerException('Spectre Unreachable!')

                    mz_array: list[float] = spectrum['mz_array']
                    intensity_array: list[float] = spectrum['intensity_array']

                    eff_charge = _get_effective_charge({
                        'override_charge': row.get('override_charge'),
                        'charge': spectrum.get('charge'),
                    })

                    if eff_charge is None:
                        # Cannot compute PPM without charge — skip
                        raise DasmixerException('Charge unreachable!')

                    # Offload the CPU-bound recalculation to a worker process
                    row_dict = row.to_dict()
                    row_dict['matched_sequence'] = matched_seq
                    row_dict['protein_id'] = protein_id
                    row_dict['identity'] = identity
                    row_dict['unique_evidence'] = (ident_id in uq_evidences)
                    row_dict['match_correction_criteria'] = match_correction_criteria
                    row_dict['save_aa_substitutions'] = save_aa_substitutions
                    row_dict['max_ppm'] = max_ppm
                    row_dict['min_score'] = tool_params.get('min_score', 0.0)
                    row_dict['min_ion_intensity_coverage'] = tool_params.get('min_ion_intensity_coverage', 0.0)
                    row_dict['min_peptide_length'] = tool_params.get('min_peptide_length', 1)
                    row_dict['max_peptide_length'] = tool_params.get('max_peptide_length', 999)

                    futures.append(loop.run_in_executor(
                        executor, process_protein_map_row,
                        row_dict, mz_array, intensity_array,
                        float(row['pepmass']), eff_charge,
                        fixer, ion_params, fragment_charges,
                    ))

                # Collect worker results
                if futures:
                    for fut in asyncio.as_completed(futures):
                        res = await fut
                        if res is not None:
                            all_res.append(res)

                # Write the batch into the DB
                await _flush_matches()

                counter += batch_size
                total_processed += batch_ident_count
                if progress_callback is not None:
                    progress_callback(total_processed, -1)
                if stop_check is not None and stop_check():
                    stopped = True
                    break

        if stopped:
            break

    await project.save()
