"""
Per-row protein mapping worker (process-pool safe).

Contains the CPU-bound part of the ``identity < 1.0`` branch of
``map_proteins`` (see ``protein_map.py``): recalculation of PPM and ion
coverage for a BLAST partial match, application of Match Correction
Criteria, and the optional AA-substitution fallback.

This module is fully self-contained:

- It does NOT touch the database.
- It does NOT import anything from ``dasmixer.gui.*``.
- It does NOT import from ``protein_map.py`` (avoids a circular import —
  the caller imports this module, not the other way around).

``process_protein_map_row`` is a pure top-level function, picklable for
``ProcessPoolExecutor``.
"""

from __future__ import annotations

import logging
import math

from dasmixer.api.calculations.ppm import SeqFixer, SeqMatchParams
from dasmixer.api.calculations.spectra.ion_match import (
    IonMatchParameters,
    MatchResult,
    match_predictions,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Private helpers (self-contained copies; do not import from protein_map.py)
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

    Empty criteria — always accept.
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
    return not (seq_len < min_len or seq_len > max_len)


# ---------------------------------------------------------------------------
# Main worker (picklable, pure, per-row)
# ---------------------------------------------------------------------------

def process_protein_map_row(
    row_dict: dict,
    mz_array: list[float],
    intensity_array: list[float],
    pepmass: float,
    charge: int,
    seqfixer: SeqFixer,
    ion_match_params_dict: dict,
    fragment_charges: list[int],
) -> dict | None:
    """
    Recalculate PPM + ion coverage for a single BLAST partial match
    (identity < 1.0) and decide whether the match is accepted.

    Args:
        row_dict: Identification + BLAST metadata (see keys below). Must
            contain at least ``id``, ``sequence``, ``matched_sequence``,
            ``protein_id``, ``identity``.
        mz_array: Spectrum m/z values.
        intensity_array: Spectrum intensity values.
        pepmass: Identification pepmass.
        charge: EFFECTIVE charge (override_charge if set, else spectrum
            charge). Precomputed by the caller — NOT recomputed here.
        seqfixer: Configured SeqFixer instance.
        ion_match_params_dict: Dict representation of IonMatchParameters
            (ions, tolerance, mode, water_loss, ammonia_loss).
        fragment_charges: Fragment charge states for match_predictions.

    Returns:
        A single result row dict for the peptide matches DataFrame with
        ``substitution`` set to False/True, or None if the match is rejected.

    Notes:
        A fresh ``IonMatchParameters`` is built on every call — sharing a
        single instance across processes/threads races on
        ``params.charges`` / ``params.ions``.
    """
    # Step 1: fresh IonMatchParameters copy per call
    ion_params = IonMatchParameters(
        ions=ion_match_params_dict.get('ions', ['b', 'y']),
        tolerance=ion_match_params_dict.get('tolerance', 20.0),
        mode=ion_match_params_dict.get('mode', 'largest'),
        water_loss=ion_match_params_dict.get('water_loss', False),
        ammonia_loss=ion_match_params_dict.get('ammonia_loss', False),
    )

    ident_id = int(row_dict['id'])
    protein_id = str(row_dict['protein_id'])
    matched_seq = str(row_dict['matched_sequence'])
    identity = float(row_dict['identity'])
    unique_evidence = bool(row_dict.get('unique_evidence'))

    # Step 2: isotope offset (0 if absent/NaN)
    isotope_offset = _safe_int(row_dict.get('isotope_offset')) or 0

    # Step 3: SeqFixer recalculation
    try:
        seq_results = seqfixer.get_matched_ppm(
            sequence=str(row_dict['sequence']),
            matched_sequence=matched_seq,
            pepmass=float(pepmass),
            charge=charge,
            isotope_offset=isotope_offset,
        )
    except Exception as exc:
        logger.debug("[protein_map_worker] SeqFixer error ident_id=%s: %s", ident_id, exc)
        return None

    # Step 4: choose best candidate + compute ion coverage
    if seq_results.override:
        chosen_params, match_result = _pick_best_override(
            overrides=seq_results.override,
            ion_params=ion_params,
            fragment_charges=fragment_charges,
            mz_array=mz_array,
            intensity_array=intensity_array,
        )
    else:
        chosen_params = seq_results.original
        match_result = match_predictions(
            params=ion_params,
            mz=mz_array,
            intensity=intensity_array,
            charges=fragment_charges,
            sequence=chosen_params.sequence,
        )

    # Step 5: recalculated absolute PPM
    match_abs_ppm = chosen_params.abs_ppm

    # Step 6: matched_sequence_modified
    matched_sequence_modified = (
        chosen_params.sequence
        if chosen_params.sequence != matched_seq
        else None
    )

    # Step 7: match correction criteria
    criteria_passed = _check_correction_criteria(
        criteria=row_dict.get('match_correction_criteria', []),
        ident_ppm=_safe_float(row_dict.get('ppm')),
        ident_intensity_coverage=_safe_float(row_dict.get('intensity_coverage')),
        ident_ions_matched=_safe_int(row_dict.get('ions_matched')),
        ident_top_peaks_covered=_safe_int(row_dict.get('top_peaks_covered')),
        match_abs_ppm=match_abs_ppm,
        match_result=match_result,
    )

    # Step 8: build result dict
    result = {
        'protein_id': protein_id,
        'identification_id': ident_id,
        'matched_sequence': matched_seq,
        'identity': identity,
        'unique_evidence': unique_evidence,
        'matched_ppm': match_abs_ppm,
        'matched_theor_mass': chosen_params.seq_neutral_mass,
        'matched_coverage_percent': match_result.intensity_percent,
        'matched_peaks': match_result.max_ion_matches,
        'matched_top_peaks': match_result.top10_intensity_matches,
        'matched_ion_type': match_result.top_matched_ion_type,
        'matched_sequence_modified': matched_sequence_modified,
    }

    # Step 9: decision
    if criteria_passed:
        result['substitution'] = False
        return result

    if row_dict.get('save_aa_substitutions'):
        tool_params_dict = {
            'max_ppm': row_dict.get('max_ppm', 50.0),
            'min_score': row_dict.get('min_score', 0.0),
            'min_ion_intensity_coverage': row_dict.get('min_ion_intensity_coverage', 0.0),
            'min_peptide_length': row_dict.get('min_peptide_length', 1),
            'max_peptide_length': row_dict.get('max_peptide_length', 999),
        }
        if _ident_passes_tool_thresholds(row_dict, tool_params_dict):
            result['substitution'] = True
            return result

    return None
