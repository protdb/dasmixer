"""
Utility functions for semPAI library.
"""

import pickle
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional
import logging

import numpy as np
from pyteomics import parser, mass
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from .exceptions import ValidationError
from api.proteins.map_identifications import get_coverage
logger = logging.getLogger(__name__)

# Supported enzymes from pyteomics
SUPPORTED_ENZYMES = {
    'trypsin': 'trypsin',
    'chymotrypsin': 'chymotrypsin',
    'pepsin': 'pepsin',
    'lysc': 'lysc',
    'lysn': 'lysn',
    'argc': 'argc',
    'aspn': 'aspn',
    'gluc': 'gluc',
    'gluc_bicarb': 'gluc bicarb',
    'thermolysin': 'thermolysin',
    'cnbr': 'CNBr',
    'bnps_skatole': 'BNPS-Skatole',
    'iodosobenzoic_acid': 'iodosobenzoic acid',
    'ntcb': 'NTCB',
    'formic_acid': 'formic acid',
    'hydroxylamine': 'hydroxylamine',
}


@dataclass
class DigestionParams:
    """
    Parameters for protein digestion and peptide filtering.
    
    Attributes:
        enzyme: Digestion enzyme (default: 'trypsin')
                Supported enzymes: trypsin, chymotrypsin, pepsin, lysc, lysn,
                argc, aspn, gluc, gluc_bicarb, thermolysin, cnbr, etc.
        min_peptide_length: Minimum peptide length for inclusion
        max_peptide_length: Maximum peptide length for inclusion 
        min_peptide_mass: Minimum peptide mass (Da) for inclusion (optional)
        max_peptide_mass: Maximum peptide mass (Da) for inclusion (optional)
        min_intensity_threshold: Minimum intensity threshold (optional)
        max_cleavage_sites: Maximum number of missed cleavages allowed
        detection_model: Trained logistic regression model (optional)
        feature_scaler: Fitted standard scaler for features (optional)
        calibration_protein: Accession or name of calibration protein (optional)
        calibration_stats: Statistics about calibration quality (optional)
    """
    enzyme: str = 'trypsin'
    min_peptide_length: int = 6
    max_peptide_length: int = 30
    min_peptide_mass: Optional[float] = None
    max_peptide_mass: Optional[float] = None
    min_intensity_threshold: Optional[float] = None
    max_cleavage_sites: int = 0
    detection_model: Optional[LogisticRegression] = None
    feature_scaler: Optional[StandardScaler] = None
    calibration_protein: Optional[str] = None
    calibration_stats: Optional[Dict[str, float]] = None
    
    def __post_init__(self):
        """Validate enzyme after initialization."""
        self.validate_enzyme()
    
    def validate_enzyme(self) -> None:
        """Validate that enzyme is supported."""
        enzyme_lower = self.enzyme.lower().replace(' ', '_').replace('-', '_')
        if enzyme_lower not in SUPPORTED_ENZYMES:
            raise ValidationError(
                f"Unsupported enzyme '{self.enzyme}'. "
                f"Supported enzymes: {', '.join(SUPPORTED_ENZYMES.keys())}"
            )
    
    def get_pyteomics_enzyme_name(self) -> str:
        """Get the enzyme name in pyteomics format."""
        enzyme_lower = self.enzyme.lower().replace(' ', '_').replace('-', '_')
        return SUPPORTED_ENZYMES.get(enzyme_lower, 'trypsin')


def get_supported_enzymes() -> Dict[str, str]:
    """
    Get dictionary of supported enzymes.
    
    Returns:
        Dictionary mapping enzyme names to pyteomics format
    """
    return SUPPORTED_ENZYMES.copy()


def remove_modifications(peptide_sequence: str) -> str:
    """
    Remove common peptide modifications from sequence.
    
    Args:
        peptide_sequence: Peptide sequence with potential modifications
        
    Returns:
        Clean peptide sequence
    """
    # Remove common modifications like oxidation (M), carbamidomethylation (C), etc.
    # This regex removes content in parentheses and common modification symbols
    clean_seq = re.sub(r'\([^)]*\)', '', peptide_sequence)
    clean_seq = re.sub(r'[^ACDEFGHIKLMNPQRSTVWY]', '', clean_seq.upper())
    return clean_seq


def digest_protein(
    sequence: str, 
    enzyme: str = "trypsin", 
    max_cleavage_sites: int = 0
) -> List[Dict[str, Any]]:
    """
    Perform theoretical protein digestion using pyteomics.
    
    Args:
        sequence: Protein sequence
        enzyme: Digestion enzyme (trypsin, chymotrypsin, pepsin, lysc, etc.)
                See get_supported_enzymes() for full list
        max_cleavage_sites: Maximum number of missed cleavages allowed
        
    Returns:
        List of peptide dictionaries with sequence and missed cleavages
        
    Raises:
        ValidationError: If enzyme is not supported
    """
    # Validate enzyme
    enzyme_lower = enzyme.lower().replace(' ', '_').replace('-', '_')
    if enzyme_lower not in SUPPORTED_ENZYMES:
        raise ValidationError(
            f"Unsupported enzyme '{enzyme}'. "
            f"Supported enzymes: {', '.join(SUPPORTED_ENZYMES.keys())}"
        )
    
    # Get pyteomics enzyme name
    pyteomics_enzyme = SUPPORTED_ENZYMES[enzyme_lower]
    
    peptides = []
    
    try:
        # Generate peptides with 0 to max_cleavage_sites missed cleavages
        for missed_cleavages in range(max_cleavage_sites + 1):
            cleaved_peptides = parser.cleave(
                sequence, 
                rule=pyteomics_enzyme, 
                missed_cleavages=missed_cleavages
            )
            
            for peptide_seq in cleaved_peptides:
                if len(peptide_seq) >= 2:  # Skip very short peptides
                    peptides.append({
                        'sequence': peptide_seq,
                        'missed_cleavages': missed_cleavages,
                        'enzyme': enzyme,
                    })
    except Exception as e:
        logger.error(f"Digestion failed with enzyme '{enzyme}': {e}")
        raise ValidationError(f"Digestion failed: {e}")
    
    # Deduplicate by sequence, keeping minimum missed_cleavages count
    peptides_map = {}
    for pep in peptides:
        seq = pep['sequence']
        missed = pep['missed_cleavages']
        if seq not in peptides_map or peptides_map[seq]['missed_cleavages'] > missed:
            peptides_map[seq] = pep
    
    return list(peptides_map.values())


def calculate_peptide_features(sequence: str) -> Dict[str, float]:
    """
    Calculate features for a peptide sequence using pyteomics.
    
    Args:
        sequence: Peptide sequence
        
    Returns:
        Dictionary with calculated features
    """
    try:
        # Calculate molecular weight using pyteomics
        molecular_weight = mass.calculate_mass(sequence=sequence)
        
        # Calculate GRAVY (hydrophobicity) - simple implementation
        # Using Kyte-Doolittle scale
        kd_scale = {
            'A': 1.8, 'C': 2.5, 'D': -3.5, 'E': -3.5, 'F': 2.8,
            'G': -0.4, 'H': -3.2, 'I': 4.5, 'K': -3.9, 'L': 3.8,
            'M': 1.9, 'N': -3.5, 'P': -1.6, 'Q': -3.5, 'R': -4.5,
            'S': -0.8, 'T': -0.7, 'V': 4.2, 'W': -0.9, 'Y': -1.3
        }
        
        gravy = sum(kd_scale.get(aa, 0) for aa in sequence) / len(sequence)
        
        # Count basic residues
        basic_residues = sum(1 for aa in sequence if aa in ['K', 'R', 'H'])
        
        # Simple charge calculation at pH 7 (basic approximation)
        # K, R = +1; D, E = -1; H = +0.1 (partially protonated)
        charge = (sequence.count('K') + sequence.count('R') + 
                 0.1 * sequence.count('H') - sequence.count('D') - 
                 sequence.count('E'))
        
        return {
            'mass': molecular_weight,
            'length': len(sequence),
            'gravy': gravy,
            'basic_residues': basic_residues,
            'charge': charge,
        }
    except Exception as e:
        logger.warning(f"Error calculating features for {sequence}: {e}")
        # Return default values if calculation fails
        return {
            'mass': len(sequence) * 110.0,  # Average AA molecular weight
            'length': len(sequence),
            'gravy': 0.0,
            'basic_residues': sum(1 for aa in sequence if aa in ['K', 'R', 'H']),
            'charge': 0.0,
        }


def match_observed_peptides(
    observed_peptides: List[str],
    intensities: List[float],
    theoretical_peptides: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Match observed peptides with theoretical peptides.
    
    Args:
        observed_peptides: List of observed peptide sequences
        intensities: List of peptide intensities
        theoretical_peptides: List of theoretical peptide data
        
    Returns:
        List of matched peptide data with detection status
    """
    # Create mapping of observed peptides to max intensity
    observed_map = {}
    for peptide, intensity in zip(observed_peptides, intensities):
        if peptide in observed_map:
            observed_map[peptide] = max(observed_map[peptide], intensity)
        else:
            observed_map[peptide] = intensity
    
    matched_data = []
    for pep_data in theoretical_peptides:
        sequence = pep_data['sequence']
        
        data = {
            'sequence': sequence,
            'missed_cleavages': pep_data['missed_cleavages'],
            'detected': sequence in observed_map,
            'intensity': observed_map.get(sequence, 0.0),
        }
        matched_data.append(data)
    
    return matched_data


def save_parameters(parameters, filepath: str) -> None:
    """
    Save DigestionParams to file.
    
    Args:
        parameters: DigestionParams object
        filepath: Path to save file
    """
    try:
        with open(filepath, 'wb') as f:
            pickle.dump(parameters, f)
        logger.info(f"Parameters saved to {filepath}")
    except Exception as e:
        logger.error(f"Failed to save parameters: {e}")
        raise


def load_parameters(filepath: str):
    """
    Load DigestionParams from file.
    
    Args:
        filepath: Path to saved parameters file
        
    Returns:
        DigestionParams object
    """
    try:
        with open(filepath, 'rb') as f:
            parameters = pickle.load(f)
        logger.info(f"Parameters loaded from {filepath}")
        return parameters
    except Exception as e:
        logger.error(f"Failed to load parameters: {e}")
        raise


def validate_peptide_sequence(sequence: str) -> bool:
    """
    Validate peptide sequence.
    
    Args:
        sequence: Peptide sequence to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not sequence:
        return False
    
    # Check if contains only valid amino acid letters
    valid_chars = set('ACDEFGHIKLMNPQRSTVWY')
    return all(c in valid_chars for c in sequence.upper())


def calculate_detection_coverage(
    observed_peptides: List[str],
    theoretical_peptides: List[Dict[str, Any]]
) -> Dict[str, float]:
    """
    Calculate sequence coverage metrics.
    
    Args:
        observed_peptides: List of observed peptide sequences
        theoretical_peptides: Theoretical peptides
        
    Returns:
        Dictionary with coverage statistics
    """
    theoretical_sequences = {p['sequence'] for p in theoretical_peptides}
    observed_set = set(observed_peptides)
    
    matched = observed_set.intersection(theoretical_sequences)
    
    return {
        'sequence_coverage': len(matched) / len(theoretical_sequences) if theoretical_sequences else 0.0,
        'detection_efficiency': len(matched) / len(observed_set) if observed_set else 0.0,
        'total_theoretical': len(theoretical_sequences),
        'total_observed': len(observed_set),
        'matched': len(matched),
    }