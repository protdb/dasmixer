"""
Protein mapping pipeline.

Maps peptide identifications to proteins via BLAST (npysearch), then:
- For identity == 1.0: copies PPM / ion-coverage metrics directly from identification.
- For identity < 1.0: recalculates PPM and ion coverage using SeqFixer and
  match_predictions, then applies Match Correction Criteria to decide whether
  the match is accepted.  Optionally saves rejected partial matches as AA
  substitution candidates.
"""

import math
from typing import AsyncIterator

import npysearch as npy
import pandas as pd

from dasmixer.api import Project
from dasmixer.api.calculations.ppm import SeqFixer, SeqMatchParams
from dasmixer.api.calculations.ppm.dataclasses import SeqResults
from dasmixer.api.calculations.spectra.ion_match import IonMatchParameters, match_predictions, MatchResult
from dasmixer.utils.lic import get_leucine_combinations
from dasmixer.utils.seqfixer_utils import PTMS, FixedPTM


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


def _pick_best_override(
    overrides: list[SeqMatchParams],
    ion_params: IonMatchParameters,
    fragment_charges: list[int],
    mz_array: list[float],
    intensity_array: list[float],
) -> tuple[SeqMatchParams, MatchResult]:
    """
    For a list of SeqMatchParams overrides, compute ion coverage for each and
    return the (SeqMatchParams, MatchResult) pair with the highest
    intensity_percent.
    """
    best_params: SeqMatchParams | None = None
    best_match: MatchResult | None = None
    best_coverage = -1.0

    for sp in overrides:
        mr = match_predictions(
            params=ion_params,
            mz=mz_array,
            intensity=intensity_array,
            charges=fragment_charges,
            sequence=sp.sequence,
        )
        if mr.intensity_percent > best_coverage:
            best_coverage = mr.intensity_percent
            best_params = sp
            best_match = mr

    return best_params, best_match  # type: ignore[return-value]


def _check_correction_criteria(
    criteria: list[str],
    ident_ppm: float | None,
    ident_intensity_coverage: float | None,
    ident_ions_matched: int | None,
    ident_top_peaks_covered: int | None,
    match_abs_ppm: float | None,
    match_result: MatchResult,
) -> bool:
    """
    Return True if at least one of the selected criteria is met.

    For ppm:               match_abs_ppm <= abs(ident_ppm)
    For intensity_coverage: match_result.intensity_percent >= ident_intensity_coverage
    For ions_matched:       match_result.max_ion_matches >= ident_ions_matched
    For top10_ions_matched: match_result.top10_intensity_matches >= ident_top_peaks_covered
    """
    if not criteria:
        # No criteria selected — always accept
        return True

    for c in criteria:
        if c == 'ppm':
            ref = abs(ident_ppm) if ident_ppm is not None and not math.isnan(ident_ppm) else None
            val = match_abs_ppm
            if ref is not None and val is not None and val <= ref:
                return True

        elif c == 'intensity_coverage':
            ref = ident_intensity_coverage if ident_intensity_coverage is not None and not math.isnan(ident_intensity_coverage) else None
            if ref is not None and match_result.intensity_percent >= ref:
                return True

        elif c == 'ions_matched':
            ref = ident_ions_matched if ident_ions_matched is not None else None
            if ref is not None and match_result.max_ion_matches >= ref:
                return True

        elif c == 'top10_ions_matched':
            ref = ident_top_peaks_covered if ident_top_peaks_covered is not None else None
            if ref is not None and match_result.top10_intensity_matches >= ref:
                return True

    return False


def _ident_passes_tool_thresholds(row: dict, tool_params: dict) -> bool:
    """
    Check whether an identification meets all quality thresholds defined in
    tool_params (used as the gate for the AA substitution branch).

    Checks: max_ppm, min_score, min_ion_intensity_coverage,
            min_peptide_length, max_peptide_length.
    """
    max_ppm = tool_params.get('max_ppm', 50.0)
    min_score = tool_params.get('min_score', 0.0)
    min_coverage = tool_params.get('min_ion_intensity_coverage', 0.0)
    min_len = tool_params.get('min_peptide_length', 1)
    max_len = tool_params.get('max_peptide_length', 999)

    ppm_val = _safe_float(row.get('ppm'))
    score_val = _safe_float(row.get('score'))
    cov_val = _safe_float(row.get('intensity_coverage'))
    seq_len = len(row.get('canonical_sequence') or '')

    if ppm_val is not None and abs(ppm_val) > max_ppm:
        return False
    if score_val is not None and score_val < min_score:
        return False
    if cov_val is not None and cov_val < min_coverage:
        return False
    if seq_len < min_len or seq_len > max_len:
        return False
    return True


# ---------------------------------------------------------------------------
# Main async generator
# ---------------------------------------------------------------------------

async def map_proteins(
    project: Project,
    tool_settings: dict[int, dict],
    ion_params: dict,
    fragment_charges: list[int],
    seqfixer_params: dict,
    batch_size: int = 5000,
    sample_id: int | None = None,
) -> AsyncIterator[tuple[pd.DataFrame, int, int]]:
    """
    Perform protein mapping in batches and yield results per batch.

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

    Yields:
        (matches_df, count, tool_id) — DataFrame ready for
        project.add_peptide_matches_batch(), number of rows, tool id.
    """
    fasta = await project.get_protein_db_to_search()
    max_acc: int = int((await project.get_setting('max_blast_accept')) or 5)
    max_rej: int = int((await project.get_setting('max_blast_reject')) or 16)

    # Build shared IonMatchParameters once
    ion_match_params = IonMatchParameters(
        ions=ion_params.get('ions', ['b', 'y']),
        tolerance=ion_params.get('tolerance', 20.0),
        mode=ion_params.get('mode', 'largest'),
        water_loss=ion_params.get('water_loss', False),
        ammonia_loss=ion_params.get('ammonia_loss', False),
    )

    # Common SeqFixer config
    target_ppm: float = seqfixer_params.get('target_ppm', 50.0)
    min_charge: int = seqfixer_params.get('min_charge', 1)
    max_charge: int = seqfixer_params.get('max_charge', 4)
    max_isotope_offset: int = seqfixer_params.get('max_isotope_offset', 2)
    force_isotope: bool = seqfixer_params.get('force_isotope_offset', False)

    for tool_id, tool_params in tool_settings.items():
        # Per-tool PTM list
        ptm_names: list[str] | None = tool_params.get('ptm_list', None)
        if ptm_names is None:
            ptms: list[FixedPTM] = PTMS
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
        while True:
            print('retrieving batch data...')
            batch_data = await project.get_identifications(
                tool_id=tool_id,
                max_abs_ppm=query_ppm,
                offset=counter,
                limit=batch_size,
                sample_id=sample_id,
            )
            if len(batch_data) == 0:
                break
            print('batch data retrieved!')
            # ----------------------------------------------------------------
            # Build BLAST query dict
            # ----------------------------------------------------------------
            query: dict[str, str] = {}
            for _, row in batch_data[
                ['id', 'canonical_sequence', 'sequence', 'pepmass']
            ].iterrows():
                canon = str(row['canonical_sequence'])
                ident_id = int(row['id'])
                print(ident_id, canon)
                if leucine_combinatorics and ('I' in canon or 'L' in canon):
                    for idx, variant in enumerate(get_leucine_combinations(canon)):
                        query[f"{ident_id}_{int(idx) + 1}"] = variant
                else:
                    query[str(ident_id)] = canon
            print('performing blast...')
            blast_df = pd.DataFrame(npy.blast(
                query,
                fasta,
                maxAccepts=max_acc,
                maxRejects=max_rej,
                alphabet='protein',
                minIdentity=tool_params['min_protein_identity'],
            ))

            if blast_df.empty:
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
            partial_ids: list[int] = list(
                blast_df.loc[blast_df['Identity'] < 1.0, 'id'].unique()
            )
            spectra_map: dict[int, dict] = {}
            if partial_ids:
                print('reading spectra for', len(partial_ids))
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
            all_res: list[dict] = []

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
                    continue

                mz_array: list[float] = spectrum['mz_array']
                intensity_array: list[float] = spectrum['intensity_array']

                eff_charge = _get_effective_charge({
                    'override_charge': row.get('override_charge'),
                    'charge': spectrum.get('charge'),
                })

                if eff_charge is None:
                    # Cannot compute PPM without charge — skip
                    continue

                isotope_offset = _safe_int(row.get('isotope_offset')) or 0

                try:
                    seq_results: SeqResults = fixer.get_matched_ppm(
                        sequence=str(row['sequence']),
                        matched_sequence=matched_seq,
                        pepmass=float(row['pepmass']),
                        charge=eff_charge,
                        isotope_offset=isotope_offset,
                    )
                except Exception as exc:
                    print(f"[protein_map] SeqFixer error ident_id={ident_id}: {exc}")
                    continue

                # Choose best SeqMatchParams + compute ion coverage
                if seq_results.override:
                    chosen_params, match_result = _pick_best_override(
                        overrides=seq_results.override,
                        ion_params=ion_match_params,
                        fragment_charges=fragment_charges,
                        mz_array=mz_array,
                        intensity_array=intensity_array,
                    )
                else:
                    chosen_params = seq_results.original
                    match_result = match_predictions(
                        params=ion_match_params,
                        mz=mz_array,
                        intensity=intensity_array,
                        charges=fragment_charges,
                        sequence=chosen_params.sequence,
                    )

                match_abs_ppm = chosen_params.abs_ppm

                # Determine matched_sequence_modified
                if chosen_params.sequence != matched_seq:
                    matched_seq_modified = chosen_params.sequence
                else:
                    matched_seq_modified = None

                # ---- Match correction criteria check ----
                criteria_passed = _check_correction_criteria(
                    criteria=match_correction_criteria,
                    ident_ppm=_safe_float(row.get('ppm')),
                    ident_intensity_coverage=_safe_float(row.get('intensity_coverage')),
                    ident_ions_matched=_safe_int(row.get('ions_matched')),
                    ident_top_peaks_covered=_safe_int(row.get('top_peaks_covered')),
                    match_abs_ppm=match_abs_ppm,
                    match_result=match_result,
                )

                if criteria_passed:
                    all_res.append({
                        'protein_id': protein_id,
                        'identification_id': ident_id,
                        'matched_sequence': matched_seq,
                        'identity': identity,
                        'unique_evidence': ident_id in uq_evidences,
                        'matched_ppm': match_abs_ppm,
                        'matched_theor_mass': chosen_params.seq_neutral_mass,
                        'matched_coverage_percent': match_result.intensity_percent,
                        'matched_peaks': match_result.max_ion_matches,
                        'matched_top_peaks': match_result.top10_intensity_matches,
                        'matched_ion_type': match_result.top_matched_ion_type,
                        'matched_sequence_modified': matched_seq_modified,
                        'substitution': False,
                    })
                elif save_aa_substitutions:
                    # Save as AA substitution candidate if identification
                    # passes all tool quality thresholds
                    ident_row_dict = row.to_dict()
                    if _ident_passes_tool_thresholds(ident_row_dict, tool_params):
                        all_res.append({
                            'protein_id': protein_id,
                            'identification_id': ident_id,
                            'matched_sequence': matched_seq,
                            'identity': identity,
                            'unique_evidence': ident_id in uq_evidences,
                            'matched_ppm': match_abs_ppm,
                            'matched_theor_mass': chosen_params.seq_neutral_mass,
                            'matched_coverage_percent': match_result.intensity_percent,
                            'matched_peaks': match_result.max_ion_matches,
                            'matched_top_peaks': match_result.top10_intensity_matches,
                            'matched_ion_type': match_result.top_matched_ion_type,
                            'matched_sequence_modified': matched_seq_modified,
                            'substitution': True,
                        })

            if all_res:
                yield pd.json_normalize(all_res), len(all_res), tool_id

            counter += batch_size
