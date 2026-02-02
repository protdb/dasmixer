"""Ion matching functionality for peptide identification validation."""

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from peptacular.fragmentation import Fragmenter, Fragment
from peptacular.score import (
    get_fragment_matches,
    FragmentMatch,
)

def get_matched_intensity_percentage(
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


@dataclass
class MatchResult:
    """
    Result of ion matching between theoretical and experimental spectrum.
    
    Attributes:
        parameters: Parameters used for this matching
        fragments: All theoretical fragments generated
        fragment_matches: Experimental peaks matched to theoretical fragments
        intensity_percent: Percentage of total experimental intensity
                          that was matched to theoretical fragments
    """
    parameters: IonMatchParameters
    fragments: list[Fragment]
    fragment_matches: list[FragmentMatch]
    intensity_percent: float


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
    
    # Generate theoretical fragments
    frags = Fragmenter(sequence).fragment(
        params.ions,
        charges,
        water_loss=params.water_loss,
        ammonia_loss=params.ammonia_loss,
    )
    
    # Match experimental peaks to theoretical fragments using PPM tolerance
    matches = get_fragment_matches(
        frags,
        mz,
        intensity,
        tolerance_type='ppm',  # Changed from 'th' to 'ppm'
        tolerance_value=params.tolerance,
        mode=params.mode,
    )
    
    # Calculate intensity coverage
    coverage = get_matched_intensity_percentage(
        fragment_matches=matches,
        intensities=intensity
    )
    
    return MatchResult(
        parameters=params,
        fragments=frags,
        fragment_matches=matches,
        intensity_percent=coverage,
    )


def get_matches_dataframe(
    match_result: MatchResult,
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
            - frag_seq: str | None - fragment sequence
            - theor_mz: float | None - theoretical m/z of matched fragment
            
        Rows without matches have None for ion_type, label, frag_seq, theor_mz.
        
    Example:
        >>> params = IonMatchParameters(ions=['b', 'y'])
        >>> result = match_predictions(params, mz_list, int_list, 2, "PEPTIDE")
        >>> df = get_matches_dataframe(result, mz_list, int_list)
        >>> # Use with plotting
        >>> from api.spectra.plot_matches import generate_spectrum_plot
        >>> fig = generate_spectrum_plot("My Spectrum", df)
    """
    # Create experimental data frame
    exp_df = pd.DataFrame({
        'mz': mz,
        'intensity': intensity
    })
    
    if not match_result.fragment_matches:
        # No matches - return experimental data with empty match columns
        exp_df['ion_type'] = None
        exp_df['label'] = None
        exp_df['frag_seq'] = None
        exp_df['theor_mz'] = None
        return exp_df
    
    # Build match data
    match_data = []
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
        
        match_data.append({
            'mz': match.mz,
            'ion_type': match.fragment.ion_type,
            'label': f'{match.fragment.ion_type}{ion_pos}{loss_label}{charge_str}',
            'frag_seq': match.fragment.sequence,
            'theor_mz': match.fragment.mz,
        })
    
    # Create matches DataFrame and merge with experimental data
    matches_df = pd.DataFrame(match_data)
    result = pd.merge(
        exp_df,
        matches_df,
        how='left',
        on='mz'
    )
    
    return result
