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
# Algorithm functions for direct use
from .algorithms import (
    calculate_absolute_concentrations_albumin_standard,
    calculate_absolute_concentrations_total_protein,
    calculate_combined_absolute_concentrations,
    calculate_empai_value,
    calculate_ibaq_value,
    calculate_nsaf_normalized,
    calculate_nsaf_value,
    calculate_saf_value,
    calculate_top3_value,
    convert_concentrations_to_mass,
    convert_concentrations_to_molar,
    normalize_values,
    validate_mass_balance,
)

# Parameter prediction functionality
from .prediction import (
    PredictionParameters,  # Deprecated, but kept for compatibility
    apply_parameters_to_protein,
    get_prediction_summary,
    predict_and_apply_parameters,
    predict_parameters,
    predict_parameters_from_observations,
    predict_parameters_from_protein,
)
from .protein import Protein
from .sample import ProteomicSample

# Parameters and configuration
# Utility functions
from .utils import (
    SUPPORTED_ENZYMES,
    DigestionParams,
    calculate_peptide_features,
    digest_protein,
    get_supported_enzymes,
    load_parameters,
    save_parameters,
)

__all__ = [
    "SUPPORTED_ENZYMES",
    # Parameters
    "DigestionParams",
    "PredictionParameters",  # Deprecated
    # Main OOP API
    "Protein",
    "ProteomicSample",
    "apply_parameters_to_protein",
    "calculate_absolute_concentrations_albumin_standard",
    "calculate_absolute_concentrations_total_protein",
    "calculate_combined_absolute_concentrations",
    # Algorithm functions
    "calculate_empai_value",
    "calculate_ibaq_value",
    "calculate_nsaf_normalized",
    "calculate_nsaf_value",
    "calculate_peptide_features",
    "calculate_saf_value",
    "calculate_top3_value",
    "convert_concentrations_to_mass",
    "convert_concentrations_to_molar",
    # Utility functions
    "digest_protein",
    "get_prediction_summary",
    "get_supported_enzymes",
    "load_parameters",
    "normalize_values",
    "predict_and_apply_parameters",
    # Parameter prediction
    "predict_parameters",
    "predict_parameters_from_observations",
    "predict_parameters_from_protein",
    "save_parameters",
    "validate_mass_balance",
]