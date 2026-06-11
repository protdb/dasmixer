"""
Algorithms for quantitative proteomics calculations.
"""

from typing import List, Optional
import logging

import numpy as np

from .utils import digest_protein, calculate_peptide_features, remove_modifications, DigestionParams

logger = logging.getLogger(__name__)


def calculate_empai_value(
    peptides: List[str],
    intensities: List[float],
    protein_sequence: str,
    observable_parameters: Optional[DigestionParams] = None,
    empai_base: float = 10.0,
) -> float:
    """
    Calculate emPAI value for a protein.
    
    emPAI = empai_base^(N_obs/N_observ) - 1
    
    Uses only unique peptide sequences (deduplicates input).
    
    Args:
        peptides: List of observed peptide sequences (may contain duplicates)
        intensities: List of peptide intensities (can be empty)
        protein_sequence: Target protein sequence
        observable_parameters: Parameters for digestion and filtering
        empai_base: Base for exponential calculation (default 10.0)
                   Some researchers prefer other values (doi:10.1371/journal.pone.0032339)
        
    Returns:
        emPAI value
    """
    if not peptides:
        return 0.0
    
    # Use default parameters if none provided
    if observable_parameters is None:
        observable_parameters = DigestionParams()
    
    # Clean peptides and deduplicate - emPAI uses unique sequences only
    clean_peptides = [remove_modifications(p) for p in peptides]
    unique_peptides = list(set(clean_peptides))  # Remove duplicates
    
    # Theoretical digestion with enzyme from parameters
    theoretical_peptides = digest_protein(
        protein_sequence,
        enzyme=observable_parameters.get_pyteomics_enzyme_name(),
        max_cleavage_sites=observable_parameters.max_cleavage_sites
    )
    
    # Apply filters and count observable peptides
    filtered_theoretical = []
    for pep_data in theoretical_peptides:
        sequence = pep_data['sequence']
        features = calculate_peptide_features(sequence)
        
        # Apply standard filters (always applied if set)
        # Length filter (required parameters)
        if (features['length'] < observable_parameters.min_peptide_length or
            features['length'] > observable_parameters.max_peptide_length):
            continue
        
        # Mass filter (optional parameters)
        if (observable_parameters.min_peptide_mass is not None and 
            features['mass'] < observable_parameters.min_peptide_mass):
            continue
        if (observable_parameters.max_peptide_mass is not None and 
            features['mass'] > observable_parameters.max_peptide_mass):
            continue
        
        # Cleavage filter (required parameter)
        if pep_data['missed_cleavages'] > observable_parameters.max_cleavage_sites:
            continue
        
        filtered_theoretical.append(pep_data)
    
    if len(filtered_theoretical) == 0:
        logger.warning("No theoretical peptides passed filters")
        return 0.0
    
    # Calculate observable peptides using ML model if available
    use_ml_model = (observable_parameters.detection_model is not None and 
                   observable_parameters.feature_scaler is not None)
    
    if use_ml_model:
        try:
            # Use ML model for detection probabilities
            total_observable = 0.0
            ml_failed = False
            
            for pep_data in filtered_theoretical:
                features = calculate_peptide_features(pep_data['sequence'])
                
                # Get the expected features from calibration stats if available
                expected_features = None
                if (hasattr(observable_parameters, 'calibration_stats') and 
                    observable_parameters.calibration_stats and 
                    'model_features' in observable_parameters.calibration_stats):
                    expected_features = observable_parameters.calibration_stats['model_features']
                
                # Create feature vector - try to match what model expects
                if expected_features:
                    # Use the same features as the model was trained on
                    feature_vector = []
                    for feat_name in expected_features:
                        if feat_name == 'missed_cleavages':
                            feature_vector.append(pep_data['missed_cleavages'])
                        else:
                            feature_vector.append(features[feat_name])
                    feature_vector = np.array([feature_vector])
                else:
                    # Default: all 6 features in standard order
                    feature_vector = np.array([[
                        features['mass'],
                        features['length'],
                        features['gravy'],
                        features['basic_residues'],
                        features['charge'],
                        pep_data['missed_cleavages']
                    ]])
                
                try:
                    feature_vector_scaled = observable_parameters.feature_scaler.transform(feature_vector)
                    prob = observable_parameters.detection_model.predict_proba(feature_vector_scaled)[0, 1]
                    total_observable += prob
                except (ValueError, IndexError) as e:
                    # If model expects different number of features, mark as failed
                    logger.debug(f"ML model prediction failed for peptide: {e}")
                    ml_failed = True
                    break
            
            if ml_failed:
                logger.warning("ML model feature mismatch, falling back to simple count")
                total_observable = float(len(filtered_theoretical))
            
        except Exception as e:
            logger.warning(f"ML model prediction failed: {e}. Using simple count.")
            total_observable = float(len(filtered_theoretical))
    else:
        # Use simple count of filtered theoretical peptides
        total_observable = float(len(filtered_theoretical))
    
    # Count observed unique peptides (no filtering - assume input is already filtered)
    observed_count = float(len(unique_peptides))
    
    # Calculate emPAI with custom base
    if total_observable == 0:
        return 0.0
    
    empai = (empai_base ** (observed_count / total_observable)) - 1
    return empai


def calculate_saf_value(spectral_counts: int, sequence_length: int) -> float:
    """
    Calculate SAF (Spectral Abundance Factor) for a protein.
    
    SAF = SpC / L_i, where SpC is total PSM count and L_i is sequence length.
    
    Args:
        spectral_counts: Total PSM count (sum of all PSM counts for this protein)
        sequence_length: Protein sequence length in amino acids
        
    Returns:
        SAF value (before normalization to NSAF)
    """
    if sequence_length <= 0:
        return 0.0
    
    return spectral_counts / sequence_length


def calculate_nsaf_value(spectral_counts: int, molecular_mass_kda: float) -> float:
    """
    Calculate SAF (Spectral Abundance Factor) for a protein using molecular weight.
    
    Note: This calculates SAF only. Normalization to NSAF happens at sample level.
    SAF = SpC / MW, where SpC is total PSM count.
    
    DEPRECATED: Use calculate_saf_value() instead for correct NSAF calculation.
    
    Args:
        spectral_counts: Total PSM count (sum of all PSM counts for this protein)
        molecular_mass_kda: Molecular mass in kDa
        
    Returns:
        SAF value (before normalization to NSAF)
    """
    if molecular_mass_kda <= 0:
        return 0.0
    
    return spectral_counts / molecular_mass_kda


def calculate_ibaq_value(intensities: List[float], observable_peptides: int) -> float:
    """
    Calculate iBAQ (intensity-Based Absolute Quantification) for a protein.
    
    iBAQ = Σ(all intensities) / N_observ
    Uses ALL intensities including duplicates (no deduplication).
    
    Args:
        intensities: List of ALL peptide intensities (including duplicates)
        observable_peptides: Number of theoretically observable peptides
        
    Returns:
        iBAQ value
    """
    if not intensities or observable_peptides <= 0:
        return 0.0
    
    # Use ALL intensities - no deduplication for iBAQ
    total_intensity = sum(intensities)
    return total_intensity / observable_peptides


def calculate_top3_value(intensities: List[float]) -> float:
    """
    Calculate Top3 value (average of top 3 peptide intensities).
    
    Args:
        intensities: List of peptide intensities
        
    Returns:
        Top3 value (average of top 3, or all if less than 3)
    """
    if not intensities:
        return 0.0
    
    # Sort intensities in descending order
    sorted_intensities = sorted(intensities, reverse=True)
    
    # Take top 3 (or all if less than 3)
    top_intensities = sorted_intensities[:3]
    
    # Calculate average
    return sum(top_intensities) / len(top_intensities)


def normalize_values(values: List[float]) -> List[float]:
    """
    Normalize values to sum to 1.0.
    
    Args:
        values: List of values to normalize
        
    Returns:
        List of normalized values
    """
    total = sum(values)
    if total <= 0:
        return [0.0] * len(values)
    
    return [v / total for v in values]


def calculate_nsaf_normalized(saf_values: List[float]) -> List[float]:
    """
    Calculate NSAF from SAF values according to formula:
    NSAF_i = SAF_i / Σ(SAF_j)
    
    Args:
        saf_values: List of SAF values for all proteins in sample
        
    Returns:
        List of NSAF values (normalized to sum to 1.0)
    """
    return normalize_values(saf_values)


def calculate_absolute_concentrations_total_protein(
    relative_values: List[float],
    total_protein_gl: float
) -> List[float]:
    """
    Calculate absolute concentrations using total protein concentration.
    
    Formula: C_{i,mass} = relative_value_i * C_{total}
    
    Args:
        relative_values: Normalized relative abundance values
        total_protein_gl: Total protein concentration in g/L
        
    Returns:
        Absolute concentrations in g/L
    """
    return [rv * total_protein_gl for rv in relative_values]


def calculate_absolute_concentrations_albumin_standard(
    relative_values: List[float],
    albumin_relative: float,
    albumin_gl: float
) -> List[float]:
    """
    Calculate absolute concentrations using albumin as internal standard.
    
    Formula: C_{i,mass} = C_{reference,mass} * (relative_value_i / relative_value_reference)
    
    Args:
        relative_values: Normalized relative abundance values
        albumin_relative: Relative abundance of albumin
        albumin_gl: Known albumin concentration in g/L
        
    Returns:
        Absolute concentrations in g/L
    """
    if albumin_relative <= 0:
        return [0.0] * len(relative_values)
    
    scaling_factor = albumin_gl / albumin_relative
    return [rv * scaling_factor for rv in relative_values]


def calculate_combined_absolute_concentrations(
    relative_values: List[float],
    albumin_relative: float,
    albumin_gl: float,
    total_protein_gl: float,
    alpha: float = 0.5
) -> List[float]:
    """
    Calculate absolute concentrations using combined approach.
    
    Args:
        relative_values: Normalized relative abundance values
        albumin_relative: Relative abundance of albumin
        albumin_gl: Known albumin concentration in g/L
        total_protein_gl: Total protein concentration in g/L
        alpha: Weight factor (0 ≤ α ≤ 1)
        
    Returns:
        Absolute concentrations in g/L
    """
    # Albumin-based concentrations
    albumin_based = calculate_absolute_concentrations_albumin_standard(
        relative_values, albumin_relative, albumin_gl
    )
    
    # Total protein-based concentrations
    total_based = calculate_absolute_concentrations_total_protein(
        relative_values, total_protein_gl
    )
    
    # Combined approach
    combined = []
    for alb, tot in zip(albumin_based, total_based):
        combined.append(alpha * alb + (1 - alpha) * tot)
    
    return combined


def convert_concentrations_to_molar(
    concentrations_gl: List[float],
    molecular_masses_kda: List[float]
) -> List[float]:
    """
    Convert mass concentrations (g/L) to molar concentrations (mol/L).
    
    Formula: C_{i,molar} = C_{i,mass} / MW_i
    where MW_i is converted from kDa to g/mol (multiply by 1000)
    
    Args:
        concentrations_gl: Concentrations in g/L
        molecular_masses_kda: Molecular masses in kDa
        
    Returns:
        Concentrations in mol/L
    """
    molar_concentrations = []
    for conc, mw in zip(concentrations_gl, molecular_masses_kda):
        if mw > 0:
            # Convert kDa to g/mol (multiply by 1000)
            molar_conc = conc / (mw * 1000)
            molar_concentrations.append(molar_conc)
        else:
            molar_concentrations.append(0.0)
    
    return molar_concentrations


def convert_concentrations_to_mass(
    concentrations_mol: List[float],
    molecular_masses_kda: List[float]
) -> List[float]:
    """
    Convert molar concentrations (mol/L) to mass concentrations (g/L).
    
    Args:
        concentrations_mol: Concentrations in mol/L
        molecular_masses_kda: Molecular masses in kDa
        
    Returns:
        Concentrations in g/L
    """
    mass_concentrations = []
    for conc, mw in zip(concentrations_mol, molecular_masses_kda):
        # Convert kDa to g/mol (multiply by 1000)
        mass_conc = conc * (mw * 1000)
        mass_concentrations.append(mass_conc)
    
    return mass_concentrations


def validate_mass_balance(
    absolute_concentrations: List[float],
    total_protein_gl: float,
    tolerance: float = 0.1
) -> bool:
    """
    Validate that sum of absolute concentrations matches total protein.
    
    Args:
        absolute_concentrations: List of protein concentrations in g/L
        total_protein_gl: Expected total protein concentration in g/L
        tolerance: Allowed relative error
        
    Returns:
        True if mass balance is satisfied
    """
    calculated_total = sum(absolute_concentrations)
    if total_protein_gl <= 0:
        return calculated_total <= tolerance
    
    relative_error = abs(calculated_total - total_protein_gl) / total_protein_gl
    return relative_error <= tolerance
