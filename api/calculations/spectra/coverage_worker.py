"""
Multiprocessing workers for batch ion-coverage calculation.

This module is intentionally free of any project/DB imports so it can be
safely used inside a multiprocessing.Pool without pickling issues.
"""

from api.calculations.spectra.ion_match import IonMatchParameters, match_predictions
from utils.ppm import calculate_ppm_and_charge, calculate_theor_mass


def process_identification_batch(
    batch: list[dict],
    params_dict: dict,
    fragment_charges: list[int],
    ignore_spectre_charges: bool = True,
    min_charge: int = 1,
    max_charge: int = 4,
) -> list[dict]:
    """
    Calculate ion-coverage metrics for a batch of identifications.

    Designed to run inside a multiprocessing.Pool — all arguments and return
    values must be pickle-serialisable.

    Args:
        batch: List of plain dicts, each with keys:
            id, sequence, pepmass, charge, mz_array (list), intensity_array (list)
        params_dict: Dict representation of IonMatchParameters:
            ions, tolerance, mode, water_loss, ammonia_loss
        fragment_charges: Fragment charge list for ion matching.
        ignore_spectre_charges: If True, ignore spectrum charge for PPM,
            use min_charge..max_charge range instead.
        min_charge: Minimum precursor charge for PPM scan (used when ignoring
            spectrum charge or charge is None).
        max_charge: Maximum precursor charge for PPM scan.

    Returns:
        List of result dicts:
            id, ppm, theor_mass, override_charge,
            intensity_coverage, ions_matched, ion_match_type, top_peaks_covered
    """
    params = IonMatchParameters(
        ions=params_dict.get('ions', ['b', 'y']),
        tolerance=params_dict.get('tolerance', 20.0),
        mode=params_dict.get('mode', 'largest'),
        water_loss=params_dict.get('water_loss', False),
        ammonia_loss=params_dict.get('ammonia_loss', False),
    )

    results = []
    for item in batch:
        ident_id = item['id']
        sequence = item.get('sequence', '')
        pepmass = item.get('pepmass')
        charge = item.get('charge')

        mz_array = item.get('mz_array', [])
        intensity_array = item.get('intensity_array', [])
        try:
            if pepmass is None:
                ppm = None
                override_charge = None
                theor_mass = calculate_theor_mass(sequence)
            else:
                # Determine effective charge range for PPM calculation
                if not ignore_spectre_charges and charge is not None:
                    _min = int(charge)
                    _max = int(charge)
                else:
                    _min = min_charge
                    _max = max_charge

                ppm, override_charge, theor_mass = calculate_ppm_and_charge(
                    sequence=sequence,
                    pepmass=pepmass,
                    min_charge=_min,
                    max_charge=_max,
                )

            # Ion matching
            match_result = match_predictions(
                params=params,
                mz=mz_array,
                intensity=intensity_array,
                charges=fragment_charges,
                sequence=sequence,
            )

            results.append({
                'id': ident_id,
                'ppm': ppm,
                'theor_mass': theor_mass,
                'override_charge': override_charge,
                'intensity_coverage': match_result.intensity_percent,
                'ions_matched': match_result.max_ion_matches,
                'ion_match_type': match_result.top_matched_ion_type,
                'top_peaks_covered': match_result.top10_intensity_matches,
            })

        except Exception as exc:
            print(f"[coverage_worker] Error on id={ident_id}: {exc}")
            results.append({
                'id': ident_id,
                'ppm': None,
                'theor_mass': None,
                'override_charge': None,
                'intensity_coverage': None,
                'ions_matched': None,
                'ion_match_type': None,
                'top_peaks_covered': None,
            })

    return results


def process_peptide_match_batch(
    batch: list[dict],
    params_dict: dict,
    fragment_charges: list[int],
) -> list[dict]:
    """
    Calculate PPM and ion coverage for a batch of peptide_match records.

    Args:
        batch: List of dicts with keys:
            id (match id), matched_sequence, pepmass, override_charge,
            mz_array (list), intensity_array (list)
        params_dict: IonMatchParameters dict (same as process_identification_batch).
        fragment_charges: Fragment charge list for ion matching.

    Returns:
        List of result dicts:
            id, matched_ppm, matched_theor_mass, matched_coverage_percent
    """
    params = IonMatchParameters(
        ions=params_dict.get('ions', ['b', 'y']),
        tolerance=params_dict.get('tolerance', 20.0),
        mode=params_dict.get('mode', 'largest'),
        water_loss=params_dict.get('water_loss', False),
        ammonia_loss=params_dict.get('ammonia_loss', False),
    )

    results = []
    for item in batch:
        match_id = item['id']
        matched_seq = item.get('matched_sequence', '')
        pepmass = item.get('pepmass')
        override_charge = item.get('override_charge')

        mz_array = item.get('mz_array', [])
        intensity_array = item.get('intensity_array', [])

        try:
            if pepmass is None:
                matched_ppm = None
                matched_theor_mass = calculate_theor_mass(matched_seq)
            elif override_charge is not None:
                matched_ppm, _, matched_theor_mass = calculate_ppm_and_charge(
                    sequence=matched_seq,
                    pepmass=pepmass,
                    min_charge=int(override_charge),
                    max_charge=int(override_charge),
                )
            else:
                matched_ppm, _, matched_theor_mass = calculate_ppm_and_charge(
                    sequence=matched_seq,
                    pepmass=pepmass,
                )

            match_result = match_predictions(
                params=params,
                mz=mz_array,
                intensity=intensity_array,
                charges=fragment_charges,
                sequence=matched_seq,
            )

            results.append({
                'id': match_id,
                'matched_ppm': matched_ppm,
                'matched_theor_mass': matched_theor_mass,
                'matched_coverage_percent': match_result.intensity_percent,
            })

        except Exception as exc:
            print(f"[coverage_worker] Error on match_id={match_id}: {exc}")
            results.append({
                'id': match_id,
                'matched_ppm': None,
                'matched_theor_mass': None,
                'matched_coverage_percent': None,
            })

    return results
