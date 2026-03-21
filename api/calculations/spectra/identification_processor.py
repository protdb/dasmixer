from api.calculations.ppm import SeqFixer, SeqMatchParams
from dataclasses import asdict
from typing import Literal
from utils.seqfixer_utils import PTMS, FixedPTM
from api.calculations.spectra.ion_match import IonMatchParameters, match_predictions, MatchResult

def _get_best_override(overrides: list[tuple[SeqMatchParams, MatchResult]], criteria: str) -> tuple[SeqMatchParams, MatchResult]:
    # Выбираем наилучшее покрытие по критерию, второй критерий - ppm
    overrides.sort(
        key=lambda row: (-getattr(row[1], criteria), row[0].abs_ppm),
    )
    return overrides[0]

def process_single_ident(
    fixer: SeqFixer,
    params: IonMatchParameters,
    fragment_charges: list[int],
    sequence: str,
    pepmass: float,
    mz_array,
    intensity_array,
    mgf_charge: int | None = None,
    selection_criteria: Literal['peaks', 'top_peaks', 'coverage'] = 'coverage'
) -> dict:
    seq_results = fixer.get_ppm(
        sequence,
        pepmass,
        mgf_charge
    )
    if not seq_results.override:
        ppm_result = seq_results.original,
        match_result = match_predictions(
                params=params,
                mz=mz_array,
                intensity=intensity_array,
                charges=fragment_charges,
                sequence=sequence,
        )
    else:
        all_matches = []
        for override in seq_results.override:
            match_res = match_predictions(
                params=params,
                mz=mz_array,
                intensity=intensity_array,
                charges=fragment_charges,
                sequence=override.sequence,
            )
            all_matches.append((override, match_res))
        ppm_result, match_result = _get_best_override(
            all_matches,
            criteria=selection_criteria
        )
    return {
        'sequence': ppm_result.sequence,
        'ppm': ppm_result.ppm,
        'theor_mass': ppm_result.seq_neutral_mass,
        'override_charge': ppm_result.charge,
        'isotope_offset': ppm_result.isotope_offset,
        'intensity_coverage': match_result.intensity_percent,
        'ions_matched': match_result.max_ion_matches,
        'ion_match_type': match_result.top_matched_ion_type,
        'top_peaks_covered': match_result.top10_intensity_matches,
    }




def process_identificatons_batch(
    batch: list[dict],
    params_dict: dict,
    fragment_charges: list[int],
    target_ppm: float,
    min_charge: int = 1,
    max_charge: int = 4,
    max_isotope_offset: int = 2,
    force_isotope_offset_lookover: bool = True,
    ptm_names_list: list[str] | None = None,
    max_ptm: int = 5,
    seq_criteria: Literal['peaks', 'top_peaks', 'coverage'] = 'coverage'
) -> list[dict]:
    params = IonMatchParameters(
        ions=params_dict.get('ions', ['b', 'y']),
        tolerance=params_dict.get('tolerance', 20.0),
        mode=params_dict.get('mode', 'largest'),
        water_loss=params_dict.get('water_loss', False),
        ammonia_loss=params_dict.get('ammonia_loss', False),
    )
    if ptm_names_list is None:
        ptms = PTMS
    else:
        ptms = [x for x in PTMS if x.code in ptm_names_list]
    fixer = SeqFixer(
        ptm_list=ptms,
        max_ptm=max_ptm,
        target_ppm=target_ppm,
        override_charges=(min_charge, max_charge),
        max_isotope_offset=max_isotope_offset,
        force_isotope_offset_lookover=force_isotope_offset_lookover,
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
            result = process_single_ident(
                fixer,
                params,
                fragment_charges,
                sequence,
                pepmass,
                mz_array,
                intensity_array,
                mgf_charge=charge,
                selection_criteria=seq_criteria
            )
            result['id'] = ident_id
            result['source_sequence'] = sequence
            results.append(result)
        except Exception as exc:
            print(f"[ident processor] Error on id={ident_id}: {exc}")
            results.append({
                'id': ident_id,
                'sequence': sequence,
                'ppm': None,
                'theor_mass': None,
                'override_charge': None,
                'intensity_coverage': None,
                'ions_matched': None,
                'ion_match_type': None,
                'top_peaks_covered': None,
                'isotope_offset': None,
                'source_sequence': sequence,
            })
    return results