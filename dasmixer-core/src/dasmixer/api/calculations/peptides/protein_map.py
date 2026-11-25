"""
Protein mapping pipeline (v2).

Maps peptide identifications to proteins via BLAST (npysearch) in four stages:

* Stage 0 — preparation: the protein database is exported to FASTA files
  (``proteins.fasta`` and optionally ``proteins_lic.fasta`` for I/L
  combinatorics). One work directory is created per ``map_proteins`` call.
* Stage 1 — simple search (``minIdentity = 1.0``): full-coverage hits are
  written directly with ``identity = 1.0``; the matched subsequence is taken
  from the original protein (not ``TargetMatchSeq``), and ``correction`` is
  set to ``'ilc'`` only when I/L substitution was actually needed.
* Stage 2 — correction search (``minIdentity = min_protein_identity < 1.0``):
  for the query sequences that did not produce a full-coverage hit, a second
  BLAST run with reduced identity is performed and the surviving
  ``(ident_id, protein_id)`` pairs become :class:`Candidate` objects.
* Stage 3 — processing: spectra are loaded and the CPU-bound PPM / ion
  coverage recalculation is offloaded to worker processes via
  :func:`process_protein_map_row` (``ProcessPoolExecutor``). Match
  Correction Criteria are applied to decide whether the match is accepted;
  rejected partial matches may still be saved as AA-substitution candidates.

Results are written directly into the project database in batches.

Known limitation (§1.1 of the spec): npysearch performs **local** alignment,
so partial / local BLAST hits occupy ``maxAccepts`` slots. For short query
sequences that occur in many proteins a full-length exact match may be
crowded out. This is accepted as a known limitation in this version.
"""

import asyncio
import math
import os
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

try:
    import npysearch as npy
except ImportError:  # pragma: no cover
    npy = None  # type: ignore[assignment]

import pandas as pd
from dasmixer.api.calculations.peptides.blast_parse import (
    build_stage1_rows,
    build_stage2_candidates,
    filter_full_coverage,
    filter_stage2_hits,
    read_blast_csv,
)
from dasmixer.api.calculations.peptides.blast_runner import run_blast
from dasmixer.api.calculations.peptides.fasta_export import (
    make_work_dir,
    write_proteins_fasta,
    write_queries_fasta,
)
from dasmixer.api.calculations.peptides.protein_map_worker import process_protein_map_row
from dasmixer.api.calculations.peptides.types import (
    Candidate,
    ProteinMapProgress,
    SearchSequence,
)
from dasmixer.api.config import config as _config
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
    progress_callback: Callable[[ProteinMapProgress], None] | None = None,
    stop_check: Callable[[], bool] | None = None,
) -> None:
    """
    Perform protein mapping (v2) and write results into the project database.

    The pipeline runs four stages per tool (see the module docstring for a
    high-level overview). Results are written directly into the project
    database in batches via ``project.add_peptide_matches_batch_fast``; a
    final ``project.save()`` is performed after all tools are processed.
    Callers must NOT call ``add_peptide_matches_batch`` themselves.

    The CPU-bound per-row recalculation (Stage 3, identity < 1.0) is
    parallelized across worker processes
    (``ProcessPoolExecutor(max_workers=worker_count)``); each row is handled
    by
    ``dasmixer.api.calculations.peptides.protein_map_worker.process_protein_map_row``.
    The BLAST runs (npysearch) are executed in a separate single-worker
    ``ProcessPoolExecutor`` because the native call is blocking and writes
    its output CSV into the current working directory.

    Known limitation: npysearch performs **local** alignment, so partial /
    local BLAST hits occupy ``maxAccepts`` slots (§1.1 of the 0.7.5a2 spec).
    For short query sequences that occur in many proteins a full-length
    exact match may be crowded out. This is accepted as a known limitation
    in this version; project defaults (``max_blast_accept`` / 5,
    ``max_blast_reject`` / 16) are not changed.

    Args:
        project: Project instance.
        tool_settings: Per-tool settings keyed by tool_id. Each dict should
            contain at minimum: min_protein_identity, max_ppm, ptm_list,
            max_ptm, leucine_combinatorics, denovo_correction,
            match_correction_criteria, save_aa_substitutions, min_score,
            min_ion_intensity_coverage, min_peptide_length,
            max_peptide_length.
        ion_params: Dict representation of IonMatchParameters
            (ions, tolerance, mode, water_loss, ammonia_loss).
        fragment_charges: Fragment charge states for match_predictions.
        seqfixer_params: Common SeqFixer parameters:
            target_ppm, min_charge, max_charge, max_isotope_offset,
            force_isotope_offset (bool).
        batch_size: Identifications per page in the src-protein branch.
        sample_id: If provided, only process identifications for this sample.
        use_src_protein_ids: If True, identifications that carry a
            src_file_protein_id are turned into exact-match peptide_match
            records directly (bypassing BLAST) and excluded from the search.
        progress_callback: Optional callable invoked with a single
            :class:`ProteinMapProgress` argument. The ``fraction`` field is
            normalised to ``0..1`` across the whole run (all tools);
            ``processed`` / ``total`` are only set during the ``processing``
            stage.
        stop_check: Optional callable invoked after Stage 1 save, after each
            save flush, and after each Stage 3 chunk; if it returns True the
            current tool is finalised (flushed + saved) and the tool loop
            is broken — remaining tools are skipped.

    Returns:
        None. Results are written into the project database internally.
    """
    if npy is None:
        raise ImportError(
            "npysearch is not installed. Install dasmixer-core with the 'proteins' extra: "
            "pip install 'dasmixer-core[proteins]'"
        )

    proteins: dict[str, str] = await project.get_protein_db_to_search()
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

    # Protein databases (shared across all tools)
    work_dir: Path = make_work_dir(project.path)
    ilc_any = any(bool(p.get('leucine_combinatorics', False)) for p in tool_settings.values())
    write_proteins_fasta(proteins, work_dir / 'proteins.fasta', il_combinatorics=False)
    if ilc_any:
        write_proteins_fasta(proteins, work_dir / 'proteins_lic.fasta', il_combinatorics=True)

    protein_keys = set(proteins.keys())
    pm_batch = int(_config.protein_mapping_batch_size)
    ident_batch_size = int(_config.identification_processing_batch_size)

    # Progress plumbing -----------------------------------------------------
    tool_count = max(1, len(tool_settings))
    tool_index = 0

    def _emit(stage: str, message: str, local_fraction: float,
               processed: int | None = None, total: int | None = None) -> None:
        if progress_callback is None:
            return
        frac = (tool_index + min(max(local_fraction, 0.0), 1.0)) / tool_count
        progress_callback(ProteinMapProgress(
            tool_index=tool_index, tool_count=tool_count, stage=stage,
            message=message, fraction=min(max(frac, 0.0), 1.0),
            processed=processed, total=total,
        ))

    with ProcessPoolExecutor(max_workers=1) as blast_executor, \
         ProcessPoolExecutor(max_workers=worker_count) as worker_executor:
        for tool_index, (tool_id, tool_params) in enumerate(tool_settings.items()):
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

            # Per-tool settings
            max_ppm: float = tool_params.get('max_ppm', 50.0)
            denovo_correction: bool = tool_params.get('denovo_correction', False)
            leucine_combinatorics: bool = tool_params.get('leucine_combinatorics', False)
            match_correction_criteria: list[str] = tool_params.get(
                'match_correction_criteria', ['ppm', 'intensity_coverage'])
            save_aa_substitutions: bool = tool_params.get('save_aa_substitutions', False)
            min_identity: float = float(tool_params.get('min_protein_identity', 1.0))
            min_len: int = int(tool_params.get('min_peptide_length', 1))

            need_stage2 = bool(denovo_correction or save_aa_substitutions) and min_identity < 1.0

            # Stage fractions
            if need_stage2:
                f_prepare, f_simple, f_save_simple, f_correction = 0.00, 0.15, 0.30, 0.45
            else:
                f_prepare, f_simple, f_save_simple = 0.0, 1.0 / 3.0, 2.0 / 3.0

            stopped = False

            # Stage 0 — prepare --------------------------------------------------
            _emit('prepare', 'Create sequence databases...', f_prepare)

            # src-protein branch: identifications that carry src_file_protein_id
            # are turned into exact-match peptide_match rows directly.
            if use_src_protein_ids:
                src_offset = 0
                while True:
                    src_batch = await project.get_idents_with_src_protein(
                        tool_id, sample_id, offset=src_offset, limit=batch_size,
                    )
                    if src_batch.empty:
                        break
                    src_rows: list[dict] = []
                    for _, row in src_batch.iterrows():
                        ident_id = int(row['id'])
                        raw_ids = str(row['src_file_protein_id'])
                        protein_ids = [pid.strip() for pid in raw_ids.split(';') if pid.strip()]
                        canon = str(row['canonical_sequence'])
                        for protein_id in protein_ids:
                            if protein_id not in proteins:
                                continue
                            src_rows.append({
                                'protein_id': protein_id,
                                'identification_id': ident_id,
                                'matched_sequence': canon,
                                'identity': 1.0,
                                'unique_evidence': 1 if len(protein_ids) == 1 else 0,
                                'matched_ppm': _safe_float(row.get('ppm')),
                                'matched_theor_mass': _safe_float(row.get('theor_mass')),
                                'matched_coverage_percent': _safe_float(row.get('intensity_coverage')),
                                'matched_peaks': _safe_int(row.get('ions_matched')),
                                'matched_top_peaks': _safe_int(row.get('top_peaks_covered')),
                                'matched_ion_type': _nan_to_none(row.get('ion_match_type')),
                                'matched_sequence_modified': None,
                                'substitution': False,
                                'lcrr': None,
                                'unconfirmed_ptms': None,
                                'quality': None,
                                'fasta_start': None,
                                'correction': None,
                            })
                    if src_rows:
                        await project.add_peptide_matches_batch_fast(pd.DataFrame(src_rows))
                    src_offset += len(src_batch)

            # Stage 0b — unique search sequences ---------------------------------
            seqs: list[SearchSequence] = await project.get_unique_sequences_for_search(
                tool_id, min_len, leucine_combinatorics,
                sample_id=sample_id,
                exclude_with_src_protein=use_src_protein_ids,
            )

            if not seqs:
                # No sequences to search — emit save_simple with 0 and skip
                _emit('save_simple',
                      'Saving simple search results (0 unique sequences)...',
                      f_save_simple)
                await project.save(checkpoint=True)
                if stop_check is not None and stop_check():
                    stopped = True
                if stopped:
                    break
                if not need_stage2:
                    _emit('save_simple',
                          'Saving simple search results (0 unique sequences)...',
                          1.0)
                continue

            write_queries_fasta(seqs, work_dir / f'st1_plain_{tool_id}.fasta')

            # Stage 1 — simple search (identity = 1.0) --------------------------
            _emit('simple', 'Simple search (identity=1.0)...', f_simple)
            db_path = work_dir / ('proteins_lic.fasta' if leucine_combinatorics else 'proteins.fasta')
            res1: Path = await run_blast(
                blast_executor,
                work_dir / f'st1_plain_{tool_id}.fasta',
                db_path,
                work_dir,
                max_acc, max_rej, 1.0,
                f'st1_result_{tool_id}.csv',
            )
            df1 = filter_full_coverage(read_blast_csv(res1), seqs)
            rows1, found_indexes = build_stage1_rows(
                df1, seqs, proteins, leucine_combinatorics,
            )

            # save_simple — flush Stage 1 rows in slices
            _emit('save_simple',
                  f'Saving simple search results ({len(seqs)} unique sequences)...',
                  f_save_simple)
            for i in range(0, len(rows1), pm_batch):
                slice_rows = rows1[i:i + pm_batch]
                # FK safety: drop rows whose protein_id is not in proteins
                slice_rows = [r for r in slice_rows if r['protein_id'] in protein_keys]
                if slice_rows:
                    await project.add_peptide_matches_batch_fast(pd.DataFrame(slice_rows))
                await project.save(checkpoint=True)

            if not need_stage2:
                _emit('save_simple',
                      f'Saving simple search results ({len(seqs)} unique sequences)...',
                      1.0)

            if stop_check is not None and stop_check():
                stopped = True
            if not stopped and need_stage2:
                # Stage 2 — correction search -----------------------------------
                _emit('correction',
                      f'Correction search (identity={min_identity})...',
                      f_correction)
                remaining = [s for s in seqs if s.index not in found_indexes]
                if remaining:
                    write_queries_fasta(remaining, work_dir / f'st2_{tool_id}.fasta')
                    res2: Path = await run_blast(
                        blast_executor,
                        work_dir / f'st2_{tool_id}.fasta',
                        db_path,
                        work_dir,
                        max_acc, max_rej, min_identity,
                        f'st2_result_{tool_id}.csv',
                    )
                    df2 = filter_stage2_hits(
                        read_blast_csv(res2), seqs, min_identity,
                    )
                    candidates, uq_evidence = build_stage2_candidates(df2, seqs)
                else:
                    candidates, uq_evidence = [], {}

                # Stage 3 — processing with spectra ------------------------------
                if candidates:
                    cand_by_ident: dict[int, list[Candidate]] = {}
                    for c in candidates:
                        cand_by_ident.setdefault(c.ident_id, []).append(c)
                    total = len(candidates)
                    processed = 0
                    stage3_rows: list[dict] = []
                    ident_ids = list(cand_by_ident.keys())

                    for ci in range(0, len(ident_ids), ident_batch_size):
                        chunk = ident_ids[ci:ci + ident_batch_size]
                        placeholders = ",".join("?" * len(chunk))
                        query = (
                            "SELECT i.id, i.sequence, i.canonical_sequence, "
                            "i.ppm, i.intensity_coverage, i.ions_matched, "
                            "i.top_peaks_covered, i.ion_match_type, "
                            "i.isotope_offset, i.override_charge, i.score, "
                            "i.lcrr, i.quality, s.charge "
                            "FROM identification i "
                            "JOIN spectre s ON s.id = i.spectre_id "
                            f"WHERE i.id IN ({placeholders})"
                        )
                        ident_df = await project.execute_query_df(query, tuple(chunk))
                        spectra = await project.get_spectra_for_identification_ids(chunk)

                        futures: list = []
                        for _, ident_row in ident_df.iterrows():
                            ident_id = int(ident_row['id'])
                            cands = cand_by_ident.get(ident_id, [])
                            spectrum = spectra.get(ident_id)
                            for cand in cands:
                                if spectrum is None:
                                    processed += 1
                                    _emit('processing',
                                          f'Processing corrected sequences ({processed} of {total})...',
                                          0.60 + 0.40 * processed / max(total, 1),
                                          processed=processed, total=total)
                                    continue
                                eff_charge = _get_effective_charge({
                                    'override_charge': ident_row.get('override_charge'),
                                    'charge': spectrum.get('charge'),
                                })
                                if eff_charge is None:
                                    processed += 1
                                    _emit('processing',
                                          f'Processing corrected sequences ({processed} of {total})...',
                                          0.60 + 0.40 * processed / max(total, 1),
                                          processed=processed, total=total)
                                    continue
                                pepmass = _safe_float(spectrum.get('pepmass'))
                                if pepmass is None:
                                    processed += 1
                                    _emit('processing',
                                          f'Processing corrected sequences ({processed} of {total})...',
                                          0.60 + 0.40 * processed / max(total, 1),
                                          processed=processed, total=total)
                                    continue

                                row_dict = {
                                    'id': ident_id,
                                    'sequence': ident_row.get('sequence'),
                                    'canonical_sequence': ident_row.get('canonical_sequence'),
                                    'ppm': ident_row.get('ppm'),
                                    'intensity_coverage': ident_row.get('intensity_coverage'),
                                    'ions_matched': ident_row.get('ions_matched'),
                                    'top_peaks_covered': ident_row.get('top_peaks_covered'),
                                    'ion_match_type': ident_row.get('ion_match_type'),
                                    'isotope_offset': ident_row.get('isotope_offset'),
                                    'override_charge': ident_row.get('override_charge'),
                                    'score': ident_row.get('score'),
                                    'ident_lcrr': ident_row.get('lcrr'),
                                    'ident_quality': ident_row.get('quality'),
                                    'fasta_start': cand.fasta_start,
                                    'matched_sequence': cand.target_match_seq,
                                    'protein_id': cand.protein_id,
                                    'identity': cand.eff_identity,
                                    'unique_evidence': bool(uq_evidence.get(ident_id, 0)),
                                    'denovo_correction': denovo_correction,
                                    'match_correction_criteria': match_correction_criteria,
                                    'save_aa_substitutions': save_aa_substitutions,
                                    'max_ppm': max_ppm,
                                    'min_score': tool_params.get('min_score', 0.0),
                                    'min_ion_intensity_coverage': tool_params.get('min_ion_intensity_coverage', 0.0),
                                    'min_peptide_length': tool_params.get('min_peptide_length', 1),
                                    'max_peptide_length': tool_params.get('max_peptide_length', 999),
                                }

                                futures.append(loop.run_in_executor(
                                    worker_executor, process_protein_map_row,
                                    row_dict,
                                    spectrum['mz_array'],
                                    spectrum['intensity_array'],
                                    pepmass, eff_charge,
                                    fixer, ion_params, fragment_charges,
                                ))

                        for fut in asyncio.as_completed(futures):
                            res = await fut
                            processed += 1
                            if res is not None:
                                stage3_rows.append(res)
                            _emit('processing',
                                  f'Processing corrected sequences ({processed} of {total})...',
                                  0.60 + 0.40 * processed / max(total, 1),
                                  processed=processed, total=total)

                        # Flush accumulated Stage 3 rows after each chunk
                        if stage3_rows:
                            df3 = pd.DataFrame(stage3_rows)
                            # Stage 3 dedup (§3.7): per identification_id keep
                            # max identity (denovo > substitution priority),
                            # then deduplicate by (identification_id, protein_id).
                            df3['_prio'] = (df3['correction'] == 'denovo').astype(int)
                            df3 = df3.sort_values(
                                ['identification_id', 'identity', '_prio'],
                                ascending=[True, False, False],
                            )
                            df3 = df3[
                                df3['identity']
                                == df3.groupby('identification_id')['identity'].transform('max')
                            ]
                            df3 = df3.drop_duplicates(
                                ['identification_id', 'protein_id'], keep='first',
                            ).drop(columns=['_prio'])
                            # FK safety: drop rows whose protein_id is not in proteins
                            df3 = df3[df3['protein_id'].isin(protein_keys)]
                            for fi in range(0, len(df3), pm_batch):
                                slice_df = df3.iloc[fi:fi + pm_batch]
                                if len(slice_df) > 0:
                                    await project.add_peptide_matches_batch_fast(slice_df)
                            await project.save()
                        stage3_rows = []

                        if stop_check is not None and stop_check():
                            stopped = True
                            break

            # End of tool — checkpoint save
            await project.save(checkpoint=True)
            if stopped:
                break

    # After all tools — final save
    await project.save()