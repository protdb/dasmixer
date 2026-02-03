"""
semPAI: Smart quantitative proteomics library for protein analysis.

This library implements multiple quantitative proteomics methods (emPAI, NSAF, iBAQ, Top3)
with object-oriented design and flexible parameter handling. Supports both individual 
protein analysis and sample-level quantification.
"""

__version__ = "0.3.0"
__author__ = "semPAI Team"
__email__ = "contact@sempai.dev"

# Main OOP API
from .protein import Protein
from .sample import ProteomicSample

# Parameters and configuration
from .utils import DigestionParams

# Parameter prediction functionality
from .prediction import (
    predict_parameters,
    predict_parameters_from_observations,
    predict_parameters_from_protein,
    apply_parameters_to_protein,
    predict_and_apply_parameters,
    get_prediction_summary,
    PredictionParameters,  # Deprecated, but kept for compatibility
)

# Utility functions
from .utils import (
    digest_protein,
    calculate_peptide_features,
    get_supported_enzymes,
    save_parameters,
    load_parameters,
)

# Algorithm functions for direct use
from .algorithms import (
    calculate_empai_value,
    calculate_nsaf_value,
    calculate_saf_value,
    calculate_nsaf_normalized,
    calculate_ibaq_value,
    calculate_top3_value,
    normalize_values,
    calculate_absolute_concentrations_total_protein,
    calculate_absolute_concentrations_albumin_standard,
    calculate_combined_absolute_concentrations,
    convert_concentrations_to_molar,
    convert_concentrations_to_mass,
    validate_mass_balance,
)

__all__ = [
    # Main OOP API
    "Protein",
    "ProteomicSample",
    
    # Parameters
    "DigestionParams",
    
    # Parameter prediction
    "predict_parameters",
    "predict_parameters_from_observations",
    "predict_parameters_from_protein", 
    "apply_parameters_to_protein",
    "predict_and_apply_parameters",
    "get_prediction_summary",
    "PredictionParameters",  # Deprecated
    
    # Utility functions
    "digest_protein",
    "calculate_peptide_features",
    "get_supported_enzymes",
    "save_parameters",
    "load_parameters",
    
    # Algorithm functions
    "calculate_empai_value",
    "calculate_nsaf_value", 
    "calculate_saf_value",
    "calculate_nsaf_normalized",
    "calculate_ibaq_value",
    "calculate_top3_value",
    "normalize_values",
    "calculate_absolute_concentrations_total_protein",
    "calculate_absolute_concentrations_albumin_standard",
    "calculate_combined_absolute_concentrations",
    "convert_concentrations_to_molar",
    "convert_concentrations_to_mass",
    "validate_mass_balance",
]