"""
Parameter prediction and calibration for emPAI calculations.

This module provides functionality to predict optimal parameters for in silico
protein digestion and detection based on observed peptide data.

The algorithm analyzes observed peptides directly without requiring theoretical
matching, making it suitable for de novo sequencing data and non-tryptic peptides.
"""

import warnings
import logging
from typing import Iterable, Optional, List, Dict, Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import accuracy_score, roc_auc_score, precision_score, recall_score

from uniprot_meta_tool import UniprotData

from .exceptions import ValidationError, DataError, CalibrationError
from .utils import (
    DigestionParams,
    calculate_peptide_features,
    remove_modifications,
)
from .protein import Protein

logger = logging.getLogger(__name__)


class PredictionParameters(DigestionParams):
    """
    DEPRECATED: Use DigestionParams instead.
    
    This class is kept for backward compatibility but will be removed in v0.4.0.
    """
    
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "PredictionParameters is deprecated. Use DigestionParams instead.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__(*args, **kwargs)


def analyze_observed_peptides(
    peptides: List[str],
    intensities: List[float],
    enable_ml_model: bool = False
) -> Dict[str, Any]:
    """
    Analyze observed peptides to extract statistical patterns.
    
    This function analyzes observed peptides directly without theoretical matching,
    making it suitable for de novo sequencing and non-tryptic data.
    
    Args:
        peptides: List of observed peptide sequences
        intensities: List of peptide intensities
        enable_ml_model: Whether to build intensity prediction model
        
    Returns:
        Dictionary with analysis results
    """
    # Clean and validate peptides
    clean_peptides = []
    valid_intensities = []
    
    for peptide, intensity in zip(peptides, intensities):
        clean_peptide = remove_modifications(peptide)
        if len(clean_peptide) >= 2:  # Skip very short sequences
            clean_peptides.append(clean_peptide)
            valid_intensities.append(intensity)
    
    if len(clean_peptides) < 2:  # Reduced from 3 to 2 for minimal analysis
        raise CalibrationError(
            f"Insufficient valid peptides ({len(clean_peptides)}) for analysis. "
            "Need at least 2 peptides."
        )
    
    # Calculate features for all peptides
    features_data = []
    for peptide, intensity in zip(clean_peptides, valid_intensities):
        features = calculate_peptide_features(peptide)
        features['intensity'] = intensity
        features['sequence'] = peptide
        features_data.append(features)
    
    df = pd.DataFrame(features_data)
    
    # Detect missed cleavages by analyzing peptide termini
    df['missed_cleavages'] = df['sequence'].apply(_estimate_missed_cleavages)
    
    # Basic statistical analysis
    analysis = {
        'n_peptides': len(df),
        'length_stats': {
            'min': int(df['length'].min()),
            'max': int(df['length'].max()),
            'mean': float(df['length'].mean()),
            'median': float(df['length'].median()),
            'q05': float(df['length'].quantile(0.05)),
            'q95': float(df['length'].quantile(0.95)),
        },
        'mass_stats': {
            'min': float(df['mass'].min()),
            'max': float(df['mass'].max()),
            'mean': float(df['mass'].mean()),
            'median': float(df['mass'].median()),
            'q05': float(df['mass'].quantile(0.05)),
            'q95': float(df['mass'].quantile(0.95)),
        },
        'intensity_stats': {
            'min': float(df['intensity'].min()),
            'max': float(df['intensity'].max()),
            'mean': float(df['intensity'].mean()),
            'median': float(df['intensity'].median()),
            'q05': float(df['intensity'].quantile(0.05)),
            'q95': float(df['intensity'].quantile(0.95)),
        },
        'cleavage_stats': {
            'min': int(df['missed_cleavages'].min()),
            'max': int(df['missed_cleavages'].max()),
            'mean': float(df['missed_cleavages'].mean()),
            'mode': int(df['missed_cleavages'].mode().iloc[0]) if not df['missed_cleavages'].mode().empty else 0,
        },
        'feature_correlations': _calculate_feature_correlations(df),
    }
    
    # Optional ML model for intensity prediction (need more data)
    if enable_ml_model and len(df) >= 10:  # Need more data for ML
        try:
            ml_results = _build_intensity_prediction_model(df)
            analysis['ml_model'] = ml_results
        except Exception as e:
            logger.warning(f"ML model building failed: {e}")
            analysis['ml_model'] = None
    else:
        if enable_ml_model and len(df) < 10:
            logger.info(f"Skipping ML model - insufficient data ({len(df)} < 10 peptides)")
        analysis['ml_model'] = None
    
    return analysis


def _estimate_missed_cleavages(peptide_sequence: str) -> int:
    """
    Estimate number of missed cleavages in a peptide sequence.
    
    This is a heuristic based on trypsin specificity (K, R not followed by P).
    
    Args:
        peptide_sequence: Peptide sequence
        
    Returns:
        Estimated number of missed cleavages
    """
    missed = 0
    for i, aa in enumerate(peptide_sequence[:-1]):  # Exclude last AA
        if aa in ['K', 'R']:
            # Check if followed by proline (trypsin exception)
            if i + 1 < len(peptide_sequence) and peptide_sequence[i + 1] != 'P':
                missed += 1
    return missed


def _calculate_feature_correlations(df: pd.DataFrame) -> Dict[str, float]:
    """Calculate correlations between peptide features."""
    numeric_cols = ['mass', 'length', 'gravy', 'basic_residues', 'charge', 'intensity', 'missed_cleavages']
    available_cols = [col for col in numeric_cols if col in df.columns]
    
    if len(available_cols) < 2:
        return {}
    
    corr_matrix = df[available_cols].corr()
    
    # Extract key correlations
    correlations = {}
    if 'intensity' in corr_matrix.columns:
        for col in available_cols:
            if col != 'intensity':
                corr_val = corr_matrix.loc[col, 'intensity']
                if not np.isnan(corr_val):
                    correlations[f'intensity_vs_{col}'] = float(corr_val)
    
    return correlations


def _build_intensity_prediction_model(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Build a model to predict peptide intensity from features.
    
    Args:
        df: DataFrame with peptide features
        
    Returns:
        Dictionary with model and statistics
    """
    # Define the standard feature set - this order must match what we use in algorithms.py
    standard_features = ['mass', 'length', 'gravy', 'basic_residues', 'charge', 'missed_cleavages']
    available_features = [col for col in standard_features if col in df.columns]
    
    if len(available_features) < 3:
        raise ValueError("Insufficient features for ML model")
    
    X = df[available_features].values
    y = df['intensity'].values
    
    # Use log intensity for better modeling
    y_log = np.log1p(y)  # log(1 + intensity) to handle zeros
    
    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Simple linear regression for intensity prediction
    from sklearn.linear_model import LinearRegression
    from sklearn.model_selection import cross_val_score
    
    model = LinearRegression()
    model.fit(X_scaled, y_log)
    
    # Cross-validation score
    cv_scores = cross_val_score(model, X_scaled, y_log, cv=min(5, len(df) // 2))
    
    # Predictions
    y_pred_log = model.predict(X_scaled)
    y_pred = np.expm1(y_pred_log)  # Convert back from log space
    
    # Calculate R-squared manually
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r2 = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
    
    return {
        'model': model,
        'scaler': scaler,
        'features': available_features,  # Save which features were actually used
        'r2_score': float(r2),
        'cv_mean': float(np.mean(cv_scores)),
        'cv_std': float(np.std(cv_scores)),
        'n_samples': len(df),
        'n_features': len(available_features),  # Save number of features for validation
    }


def predict_parameters_from_observations(
    peptides: Iterable[str],
    intensities: Iterable[float],
    enable_length_filter: bool = True,
    enable_mass_filter: bool = True,
    enable_intensity_filter: bool = True,
    enable_cleavage_filter: bool = True,
    enable_ml_model: bool = True,
    length_percentiles: tuple = (0.05, 0.95),
    mass_percentiles: tuple = (0.05, 0.95),
    intensity_percentile: float = 0.05,
    length_buffer: int = 1,
    mass_buffer: float = 100.0,
    intensity_buffer: float = 1000.0,
) -> DigestionParams:
    """
    Predict optimal parameters from observed peptides without theoretical matching.
    
    This function analyzes observed peptides directly to determine optimal parameters
    for protein digestion and peptide filtering. It's suitable for de novo sequencing
    data and non-tryptic peptides.
    
    Args:
        peptides: Iterable of observed peptide sequences
        intensities: Iterable of peptide intensities
        enable_length_filter: Whether to determine length boundaries
        enable_mass_filter: Whether to determine mass boundaries
        enable_intensity_filter: Whether to determine intensity threshold
        enable_cleavage_filter: Whether to determine cleavage limits
        enable_ml_model: Whether to build intensity prediction model
        length_percentiles: Percentiles for length boundaries (min, max)
        mass_percentiles: Percentiles for mass boundaries (min, max)
        intensity_percentile: Percentile for intensity threshold
        length_buffer: Buffer to add/subtract from length boundaries
        mass_buffer: Buffer to add/subtract from mass boundaries (Da)
        intensity_buffer: Buffer to subtract from intensity threshold
        
    Returns:
        DigestionParams object with optimized parameters
        
    Raises:
        ValidationError: If input data is invalid
        CalibrationError: If analysis fails
    """
    logger.info("Starting parameter prediction from observed peptides")
    
    # Validate inputs
    peptides = list(peptides)
    intensities = list(intensities)
    
    if len(peptides) != len(intensities):
        raise ValidationError("Peptides and intensities must have same length")
    
    if len(peptides) == 0:
        raise ValidationError("No peptides provided")
    
    if not all(isinstance(i, (int, float)) and i >= 0 for i in intensities):
        raise ValidationError("All intensities must be non-negative numbers")
    
    # Analyze observed peptides
    logger.info("Analyzing observed peptide patterns")
    analysis = analyze_observed_peptides(peptides, intensities, enable_ml_model)
    
    # Initialize parameters
    params = DigestionParams()
    params.calibration_protein = "observed_data"
    
    # Set parameters based on analysis
    logger.info("Determining parameter boundaries")
    
    if enable_length_filter:
        length_stats = analysis['length_stats']
        min_pct, max_pct = length_percentiles
        
        # Calculate min length bound
        if min_pct == 0.05:
            min_length_bound = length_stats['q05']
        else:
            min_length_bound = np.percentile([len(remove_modifications(p)) for p in peptides], min_pct * 100)
        
        params.min_peptide_length = max(int(min_length_bound) - length_buffer, 1)
        
        # Calculate max length bound  
        if max_pct == 0.95:
            max_length_bound = length_stats['q95']
        else:
            max_length_bound = np.percentile([len(remove_modifications(p)) for p in peptides], max_pct * 100)
            
        params.max_peptide_length = int(max_length_bound) + length_buffer
        
        logger.info(f"Length filter: {params.min_peptide_length}-{params.max_peptide_length}")
    
    if enable_mass_filter:
        mass_stats = analysis['mass_stats']
        min_pct, max_pct = mass_percentiles
        
        # Calculate min mass bound
        if min_pct == 0.05:
            min_mass_bound = mass_stats['q05']
        else:
            min_mass_bound = np.percentile([calculate_peptide_features(remove_modifications(p))['mass'] for p in peptides], min_pct * 100)
        
        params.min_peptide_mass = max(min_mass_bound - mass_buffer, 0.0)
        
        # Calculate max mass bound
        if max_pct == 0.95:
            max_mass_bound = mass_stats['q95']
        else:
            max_mass_bound = np.percentile([calculate_peptide_features(remove_modifications(p))['mass'] for p in peptides], max_pct * 100)
        
        params.max_peptide_mass = max_mass_bound + mass_buffer
        
        logger.info(f"Mass filter: {params.min_peptide_mass:.1f}-{params.max_peptide_mass:.1f}")
    
    if enable_intensity_filter:
        intensity_stats = analysis['intensity_stats']
        
        # Calculate intensity bound
        if intensity_percentile == 0.05:
            intensity_bound = intensity_stats['q05']
        else:
            intensity_bound = np.percentile(intensities, intensity_percentile * 100)
        
        params.min_intensity_threshold = max(intensity_bound - intensity_buffer, 0.0)
        
        logger.info(f"Intensity filter: {params.min_intensity_threshold:.1f}")
    
    if enable_cleavage_filter:
        cleavage_stats = analysis['cleavage_stats']
        # Use the maximum observed + 1 for safety margin
        params.max_cleavage_sites = max(int(cleavage_stats['max']) + 1, 0)
        logger.info(f"Cleavage filter: {params.max_cleavage_sites}")
    
    # Store ML model if built
    if analysis['ml_model'] is not None:
        ml_results = analysis['ml_model']
        params.detection_model = ml_results['model']  # This is actually intensity prediction model
        params.feature_scaler = ml_results['scaler']
        logger.info(f"ML model built with R² = {ml_results['r2_score']:.3f}")
    
    # Store calibration statistics
    params.calibration_stats = {
        'n_total_peptides': analysis['n_peptides'],
        'n_detected_peptides': analysis['n_peptides'],  # All are "detected" since they're observed
        'detection_rate': 1.0,  # 100% since we only have observed peptides
        'length_diversity': analysis['length_stats']['max'] - analysis['length_stats']['min'],
        'mass_diversity': analysis['mass_stats']['max'] - analysis['mass_stats']['min'],
        'intensity_range': analysis['intensity_stats']['max'] - analysis['intensity_stats']['min'],
        'cleavage_diversity': analysis['cleavage_stats']['max'] - analysis['cleavage_stats']['min'],
    }
    
    if analysis['ml_model'] is not None:
        ml_results = analysis['ml_model']
        params.calibration_stats.update({
            'model_r2': ml_results['r2_score'],
            'model_cv_mean': ml_results['cv_mean'],
            'model_cv_std': ml_results['cv_std'],
            'model_features': ml_results['features'],  # Store which features were used
            'model_n_features': ml_results['n_features'],  # Store number of features
        })
    
    # Quality checks and warnings
    _check_parameter_quality(params, analysis)
    
    logger.info("Parameter prediction completed")
    return params


def _check_parameter_quality(params: DigestionParams, analysis: Dict[str, Any]) -> None:
    """Check parameter quality and issue warnings if needed."""
    
    # Check diversity
    if analysis['length_stats']['max'] - analysis['length_stats']['min'] < 5:
        warnings.warn(
            "Low length diversity in peptides. Parameters may not be robust.",
            UserWarning
        )
    
    # Check sample size
    if analysis['n_peptides'] < 5:  # Reduced warning threshold
        warnings.warn(
            f"Small sample size ({analysis['n_peptides']} peptides). "
            "Consider collecting more data for robust parameters.",
            UserWarning
        )
    
    # Check intensity distribution
    intensity_stats = analysis['intensity_stats']
    if intensity_stats['max'] / intensity_stats['min'] < 2:
        warnings.warn(
            "Low intensity dynamic range. Intensity filtering may not be effective.",
            UserWarning
        )
    
    # Check ML model quality if available
    if analysis['ml_model'] is not None:
        r2 = analysis['ml_model']['r2_score']
        if r2 < 0.3:
            warnings.warn(
                f"Low model performance (R² = {r2:.3f}). "
                "Peptide features may not predict intensity well.",
                UserWarning
            )


def predict_parameters_from_protein(
    protein: "Protein",
    **kwargs
) -> DigestionParams:
    """
    Predict optimal digestion parameters from a Protein object.
    
    This function analyzes observed peptides in a Protein object to determine
    optimal parameters without requiring theoretical matching.
    
    Args:
        protein: Protein object with observed peptides and intensities
        **kwargs: Additional arguments passed to predict_parameters_from_observations
        
    Returns:
        DigestionParams object containing optimized parameters
        
    Raises:
        ValidationError: If protein data is invalid
        CalibrationError: If analysis fails
    """
    logger.info(f"Starting parameter prediction from protein {protein.accession}")
    
    # Get peptides and intensities from protein
    peptides = protein.peptides
    intensities = protein.intensities
    
    # If no intensities, create default ones for analysis
    if not intensities:
        intensities = [1000.0] * len(peptides)
        logger.warning("No intensities found in protein, using default values for analysis")
    
    # Call the new observation-based function
    return predict_parameters_from_observations(
        peptides=peptides,
        intensities=intensities,
        **kwargs
    )


def predict_parameters(
    peptides: Iterable[str],
    intensities: Iterable[float],
    digestion_accession: Optional[str] = None,  # Now optional and ignored
    sequence: Optional[str] = None,  # Now optional and ignored
    **kwargs
) -> DigestionParams:
    """
    Predict parameters from observed peptides (updated approach).
    
    This function now uses direct analysis of observed peptides instead of
    theoretical matching. The digestion_accession and sequence parameters
    are kept for backward compatibility but are ignored.
    
    Args:
        peptides: Iterable of observed peptide sequences
        intensities: Iterable of peptide intensities
        digestion_accession: DEPRECATED - kept for compatibility, ignored
        sequence: DEPRECATED - kept for compatibility, ignored
        **kwargs: Additional arguments passed to predict_parameters_from_observations
        
    Returns:
        DigestionParams object with optimized parameters
    """
    if digestion_accession or sequence:
        warnings.warn(
            "digestion_accession and sequence parameters are deprecated. "
            "The new algorithm analyzes observed peptides directly.",
            DeprecationWarning,
            stacklevel=2
        )
    
    return predict_parameters_from_observations(
        peptides=peptides,
        intensities=intensities,
        **kwargs
    )


def apply_parameters_to_protein(protein: "Protein", params: DigestionParams) -> "Protein":
    """
    Apply predicted parameters to a protein object.
    
    Args:
        protein: Original protein object
        params: Parameters to apply
        
    Returns:
        New protein object with applied parameters
    """
    logger.info(f"Applying predicted parameters to protein {protein.accession}")
    
    # Avoid circular import
    from .protein import Protein
    
    # Create new protein with the same data but new parameters
    new_protein = Protein(
        accession=protein.accession,
        sequence=protein.sequence,
        peptides=protein.peptides[:],  # Copy list
        intensities=protein.intensities[:] if protein.intensities else None,
        psm_counts=protein.psm_counts[:] if protein.psm_counts else None,
        empai_base=protein.empai_base,
        observable_parameters=params,
        is_uniprot=False,  # Don't fetch sequence again
    )
    
    return new_protein


def predict_and_apply_parameters(
    protein: "Protein",
    **kwargs
) -> "Protein":
    """
    Convenience function to predict parameters and apply them to a protein.
    
    Args:
        protein: Input protein object
        **kwargs: Additional arguments passed to predict_parameters_from_protein
        
    Returns:
        New protein object with optimized parameters
    """
    # Predict parameters - remove any old-style arguments that might be passed in
    clean_kwargs = {k: v for k, v in kwargs.items() 
                   if k not in ['calibration_protein_accession', 'calibration_sequence']}
    
    params = predict_parameters_from_protein(
        protein=protein,
        **clean_kwargs
    )
    
    # Apply parameters
    return apply_parameters_to_protein(protein, params)


def get_prediction_summary(params: DigestionParams) -> Dict[str, Any]:
    """
    Get a summary of prediction results.
    
    Args:
        params: DigestionParams object with calibration data
        
    Returns:
        Dictionary with summary statistics
    """
    summary = {
        'calibration_protein': params.calibration_protein,
        'length_range': (params.min_peptide_length, params.max_peptide_length),
        'mass_range': (params.min_peptide_mass, params.max_peptide_mass),
        'intensity_threshold': params.min_intensity_threshold,
        'max_cleavages': params.max_cleavage_sites,
        'has_ml_model': params.detection_model is not None,
    }
    
    if params.calibration_stats:
        summary.update(params.calibration_stats)
    
    return summary