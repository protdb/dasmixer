"""Ion matching functionality for peptide identification validation."""
from dataclasses import dataclass, field
from typing import Literal

import pandas as pd
from dasmixer.utils.logger import logger
from peptacular.fragmentation import Fragment, Fragmenter
from peptacular.score import FragmentMatch, get_fragment_matches, get_match_coverage

from .quality_calculations import (
    calculate_longest_consec_run_ratio,
    calculate_peptide_quality,
    calculate_unconfirmed_ptms,
)


def _get_matched_intensity_percentage(
    fragment_matches: list[FragmentMatch], intensities: list[float]
) -> float:
    """
    Calculates the proportion of matched intensity to total intensity.

    :param fragment_matches: List of fragment matches.
    :type fragment_matches: List[FragmentMatch]
    :param intensities: List of intensities from the experimental spectrum.
    :type intensities: List[float]

    :return: Proportion of matched intensity to total intensity.
    :rtype: float
    """

    # group matches by mz
    matches = {f.mz: f for f in fragment_matches}
    matched_intensity = sum(f.intensity for f in matches.values())
    total_intensity = sum(intensities)

    if total_intensity == 0:
        return 0

    return matched_intensity / total_intensity


def is_precursor_match(match: FragmentMatch, full_sequence: str) -> bool:
    """True if the matched fragment covers the whole peptide sequence.

    ``full_sequence`` must be the normalised ProForma string produced by
    ``Fragmenter(sequence).annotation.serialize()`` *after* ``fragment()``
    (labile modifications already popped).
    """
    return match.fragment.sequence == full_sequence


@dataclass
class IonMatchParameters:
    """
    Parameters for global ion matching.
    
    Controls how theoretical fragment ions are matched to experimental peaks
    in mass spectra.
    
    Attributes:
        ions: List of ion types to generate and match (e.g., ['b', 'y']).
              If None, defaults to ['b', 'y'].
        tolerance: Tolerance for m/z matching in PPM.
                   Default is 20 PPM.
        mode: Match selection mode:
              - 'all': return all matches within tolerance
              - 'closest': return closest match for each theoretical ion
              - 'largest': return highest intensity match for each theoretical ion
        water_loss: Include water loss modifications (-H2O, -18.01056 Da)
        ammonia_loss: Include ammonia loss modifications (-NH3, -17.02655 Da)
    """
    ions: list[Literal['a', 'b', 'c', 'x', 'y', 'z']] | None = None
    tolerance: float = 20.0  # PPM tolerance
    mode: Literal['all', 'closest', 'largest'] = 'largest'
    water_loss: bool = True
    ammonia_loss: bool = True
    charges: int | list[int] | None = None


@dataclass
class MatchResult:
    """
    Result of ion matching between theoretical and experimental spectrum.
    
    Attributes:
        parameters: Parameters used for this matching
        fragments: All theoretical fragments generated
        fragment_matches: Experimental peaks matched to theoretical fragments
        precursor_matches: Matches whose fragment covers the whole peptide
                           sequence (precursor peaks)
        intensity_percent: Percentage of total experimental intensity
                          that was matched to theoretical fragments
    """
    parameters: IonMatchParameters
    fragments: list[Fragment]
    fragment_matches: list[FragmentMatch]
    intensity_percent: float
    top10_intensity_matches: int
    total_peaks: int
    max_ion_matches: int
    top_matched_ion_type: str
    quality: float
    longest_consec_run_rate: float
    unconfirmed_ptms: int
    precursor_matches: list[FragmentMatch] = field(default_factory=list)

def match_predictions(
    params: IonMatchParameters,
    mz: list[float],
    intensity: list[float],
    charges: list[int] | int,
    sequence: str
) -> MatchResult:
    """
    Match theoretical fragments to experimental spectrum.
    
    Generates theoretical fragment ions from the peptide sequence and
    matches them to experimental peaks within the specified tolerance.
    
    Args:
        params: Ion matching parameters (with tolerance in PPM)
        mz: List of experimental m/z values
        intensity: List of experimental intensities (same length as mz)
        charges: Charge state(s) for fragment calculation.
                Can be single int or list of ints.
        sequence: Peptide sequence in ProForma notation
                 (e.g., "PEPTIDE", "PEP[+15.99]TIDE")
        
    Returns:
        MatchResult containing matched fragments and coverage statistics
        
    Example:
        >>> params = IonMatchParameters(ions=['b', 'y'], tolerance=20.0)
        >>> mz = [147.11, 276.15, 405.19]
        >>> intensity = [1000, 2000, 1500]
        >>> result = match_predictions(params, mz, intensity, 1, "PEPTIDE")
        >>> print(f"Matched {len(result.fragment_matches)} ions")
        >>> print(f"Coverage: {result.intensity_percent:.1f}%")
    """
    if params.ions is None:
        params.ions = ['b', 'y']

    if params.charges is None:
        params.charges = charges

    total_peaks = len(mz)

    if total_peaks == 0:
        return MatchResult(
            parameters=params,
            fragments=[],
            fragment_matches=[],
            intensity_percent=0,
            top10_intensity_matches=0,
            total_peaks=total_peaks,
            max_ion_matches=0,
            top_matched_ion_type='',
            quality=0.0,
            longest_consec_run_rate=0.0,
            unconfirmed_ptms=0
        )

    # Generate theoretical fragments
    logger.debug("match_predictions params=%s sequence=%s", params, sequence)
    fragmenter = Fragmenter(sequence)
    frags = fragmenter.fragment(
        params.ions,
        params.charges,
        water_loss=params.water_loss,
        ammonia_loss=params.ammonia_loss,
    )
    # Normalised ProForma sequence *after* fragment() (labile mods popped).
    full_sequence = fragmenter.annotation.serialize()

    # Match experimental peaks to theoretical fragments using PPM tolerance
    matches = get_fragment_matches(
        frags,
        mz,
        intensity,
        tolerance_type='ppm',  # Changed from 'th' to 'ppm'
        tolerance_value=params.tolerance,
        mode=params.mode,
    )

    # Split off precursor (full-length) matches; metrics use the rest.
    precursor_matches = [m for m in matches if is_precursor_match(m, full_sequence)]
    metric_matches = [m for m in matches if not is_precursor_match(m, full_sequence)]

    ion_matches = {k: max(v) for k, v in get_match_coverage(metric_matches).items()}
    max_matches = max(ion_matches.values()) if ion_matches else 0
    try:
        max_matches_type = next(k for k, v in ion_matches.items() if v == max_matches)
    except (StopIteration, IndexError):
        max_matches_type = None

    top_ints = list(intensity)
    top_ints.sort(reverse=True)
    try:
        top10_int = top_ints[9]
    except IndexError:
        top10_int = top_ints[-1]
    top10_intensity_matches = len([x for x in metric_matches if x.intensity >= top10_int])

    quality = calculate_peptide_quality(
        metric_matches,
        sequence,
        params.ions
    )

    # Calculate intensity coverage
    coverage = _get_matched_intensity_percentage(
        fragment_matches=matches,
        intensities=intensity
    )

    lcrr = calculate_longest_consec_run_ratio(
        metric_matches,
        sequence
    )

    unconfirmed_ptms = calculate_unconfirmed_ptms(
        matches,
        sequence,
    )

    
    return MatchResult(
        parameters=params,
        fragments=frags,
        fragment_matches=matches,
        intensity_percent=coverage*100,
        top10_intensity_matches=top10_intensity_matches,
        total_peaks=total_peaks,
        max_ion_matches=max_matches,
        top_matched_ion_type=max_matches_type,
        quality=quality,
        longest_consec_run_rate=lcrr,
        unconfirmed_ptms=unconfirmed_ptms,
        precursor_matches=precursor_matches
    )


def get_matches_dataframe(
    match_result: MatchResult | None,
    mz: list[float],
    intensity: list[float]
) -> pd.DataFrame:
    """
    Create DataFrame from match result for plotting and analysis.
    
    Joins experimental spectrum data with matched fragments, creating
    a DataFrame suitable for visualization with plot_matches.py.
    
    Args:
        match_result: Result from match_predictions()
        mz: List of experimental m/z values (must match what was used in matching)
        intensity: List of experimental intensities (must match what was used)
        
    Returns:
        DataFrame with columns:
            - mz: float - experimental m/z
            - intensity: float - experimental intensity
            - ion_type: str | None - matched ion type (e.g., 'b', 'y', 'a')
            - label: str | None - formatted label for annotation (e.g., 'b5-H2O+2')
            - is_precursor: bool - True if the matched fragment covers the whole peptide (precursor peak)
            - display_label: str | None - annotation text ('P...' for precursor peaks, else same as label)
            - frag_seq: str | None - fragment sequence
            - theor_mz: float | None - theoretical m/z of matched fragment
            
        Rows without matches have None for ion_type, label, frag_seq, theor_mz.
        
    Example:
        >>> params = IonMatchParameters(ions=['b', 'y'])
        >>> result = match_predictions(params, mz_list, int_list, 2, "PEPTIDE")
        >>> df = get_matches_dataframe(result, mz_list, int_list)
        >>> # Use with plotting
        >>> from dasmixer.api.calculations.spectra.plot_matches import generate_spectrum_plot
        >>> fig = generate_spectrum_plot("My Spectrum", df)
    """
    # Create experimental data frame
    exp_df = pd.DataFrame({
        'mz': mz,
        'intensity': intensity
    })
    
    if match_result is None or not match_result.fragment_matches:
        # No matches - return experimental data with empty match columns
        exp_df['ion_type'] = None
        exp_df['ion_pos'] = None
        exp_df['label'] = None
        exp_df['frag_seq'] = None
        exp_df['theor_mz'] = None
        exp_df['is_precursor'] = False
        exp_df['display_label'] = None
        return exp_df
    
    # Build match data
    match_data = []
    precursor_ids = {id(m) for m in match_result.precursor_matches}
    for match in match_result.fragment_matches:
        # Format charge
        charge_str = f'+{match.fragment.charge}' if match.fragment.charge > 1 else ''
        
        # Ion position (number of residues in fragment)
        ion_pos = match.fragment.end - match.fragment.start
        
        # Loss label formatting
        loss_value = match.fragment.loss
        if abs(loss_value) < 0.01:
            loss_label = ''
        elif abs(loss_value - (-17.02655)) < 0.01:
            loss_label = '-NH3'
        elif abs(loss_value - (-18.01056)) < 0.01:
            loss_label = '-H2O'
        else:
            loss_label = f'{loss_value:+.2f}'

        is_precursor = id(match) in precursor_ids
        base_label = f'{match.fragment.ion_type}{ion_pos}{loss_label}{charge_str}'
        display_label = f'P{loss_label}{charge_str}' if is_precursor else base_label

        match_data.append({
            'mz': match.mz,
            'ion_type': match.fragment.ion_type,
            'ion_pos': ion_pos,
            'label': base_label,
            'frag_seq': match.fragment.sequence,
            'theor_mz': match.fragment.mz,
            'is_precursor': is_precursor,
            'display_label': display_label,
        })
    
    # Create matches DataFrame and merge with experimental data
    matches_df = pd.DataFrame(match_data)
    result = pd.merge(
        exp_df,
        matches_df,
        how='left',
        on='mz'
    )

    result['is_precursor'] = result['is_precursor'].fillna(False).astype(bool)

    return result