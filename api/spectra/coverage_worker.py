"""
Multiprocessing worker for batch ion-coverage calculation.

This module is intentionally free of any project/DB imports so it can be
safely used inside a multiprocessing.Pool without pickling issues.
"""

from api.spectra.ion_match import IonMatchParameters, match_predictions
from utils.ppm import calculate_ppm, calculate_theor_mass


def process_identification_batch(
    batch: list[dict],
    params_dict: dict,
    fragment_charges: list[int],
) -> list[dict]:
    """
    Calculate ion-coverage metrics for a batch of identifications.

    Designed to run inside a multiprocessing.Pool — all arguments and return
    values must be pickle-serialisable (no numpy arrays, no project objects).
    mz_array / intensity_array in each item should already be plain Python
    lists (use IdentificationWithSpectrum.to_worker_dict() to prepare them).

    Args:
        batch: List of plain dicts, each with keys:
            id, sequence, pepmass, charge, mz_array (list), intensity_array (list)
        params_dict: Dict representation of IonMatchParameters:
            ions, tolerance, mode, water_loss, ammonia_loss
        fragment_charges: Default charge list used when spectrum charge is None.

    Returns:
        List of result dicts, one per input item, suitable for
        Project.put_identification_data_batch().  Keys:
            id, ppm, theor_mass, intensity_coverage,
            ions_matched, ion_match_type, top_peaks_covered
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
        charge = item.get('charge') or (fragment_charges[0] if fragment_charges else 1)
        mz_array = item.get('mz_array', [])
        intensity_array = item.get('intensity_array', [])

        try:
            # PPM and theoretical mass
            theor_mass = calculate_theor_mass(sequence)
            ppm = calculate_ppm(sequence, pepmass, charge) if pepmass is not None else None

            # Ion matching
            match_result = match_predictions(
                params=params,
                mz=mz_array,
                intensity=intensity_array,
                charges=charge,
                sequence=sequence,
            )

            results.append({
                'id': ident_id,
                'ppm': ppm,
                'theor_mass': theor_mass,
                'intensity_coverage': match_result.intensity_percent,
                'ions_matched': match_result.max_ion_matches,
                'ion_match_type': match_result.top_matched_ion_type,
                'top_peaks_covered': match_result.top10_intensity_matches,
            })

        except Exception as exc:
            raise
            # Log and return nulls so one bad record doesn't abort the batch
            print(f"[coverage_worker] Error on id={ident_id}: {exc}")
            results.append({
                'id': ident_id,
                'ppm': None,
                'theor_mass': None,
                'intensity_coverage': None,
                'ions_matched': None,
                'ion_match_type': None,
                'top_peaks_covered': None,
            })

    return results
