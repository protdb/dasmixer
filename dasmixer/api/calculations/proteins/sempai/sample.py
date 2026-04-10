"""
ProteomicSample class for sample-level quantitative analysis.
"""

from typing import List, Optional, Union, Literal, Dict, Any
import logging
import warnings

import pandas as pd
import numpy as np

from .protein import Protein
from .algorithms import (
    normalize_values,
    calculate_nsaf_normalized,
    calculate_absolute_concentrations_total_protein,
    calculate_absolute_concentrations_albumin_standard,
    calculate_combined_absolute_concentrations,
    convert_concentrations_to_molar,
    convert_concentrations_to_mass,
    validate_mass_balance,
)
from .exceptions import ValidationError

logger = logging.getLogger(__name__)


class ProteomicSample:
    """
    Represents a proteomic sample containing multiple proteins.
    
    Provides sample-level normalization and absolute quantification capabilities
    for multiple quantification methods (emPAI, NSAF, iBAQ, Top3).
    """
    
    def __init__(
        self,
        proteins: List[Protein],
        total_protein_gl: Optional[float] = None,
        albumin_gl: Optional[float] = None,
    ):
        """
        Initialize a ProteomicSample.
        
        Args:
            proteins: List of Protein objects in the sample
            total_protein_gl: Total protein concentration in g/L (orthogonal measurement)
            albumin_gl: Albumin concentration in g/L (known standard)
        """
        self._proteins = proteins
        self._total_protein_gl = total_protein_gl
        self._albumin_gl = albumin_gl
        
        # Validate proteins
        if not proteins:
            raise ValidationError("Sample must contain at least one protein")
        
        # Check for duplicate accessions
        accessions = [p.accession for p in proteins]
        if len(set(accessions)) != len(accessions):
            warnings.warn("Duplicate protein accessions found in sample")
    
    @property
    def proteins(self) -> List[Protein]:
        """Get list of proteins in the sample."""
        return self._proteins
    
    @proteins.setter
    def proteins(self, value: List[Protein]) -> None:
        """Set proteins and validate."""
        if not value:
            raise ValidationError("Sample must contain at least one protein")
        self._proteins = value
    
    @property
    def total_protein_gl(self) -> Optional[float]:
        """Get total protein concentration in g/L."""
        return self._total_protein_gl
    
    @total_protein_gl.setter
    def total_protein_gl(self, value: Optional[float]) -> None:
        """Set total protein concentration."""
        if value is not None and value <= 0:
            raise ValidationError("Total protein concentration must be positive")
        self._total_protein_gl = value
    
    @property
    def albumin_gl(self) -> Optional[float]:
        """Get albumin concentration in g/L."""
        return self._albumin_gl
    
    @albumin_gl.setter
    def albumin_gl(self, value: Optional[float]) -> None:
        """Set albumin concentration."""
        if value is not None and value <= 0:
            raise ValidationError("Albumin concentration must be positive")
        self._albumin_gl = value
    
    def _get_albumin_protein(self) -> Optional[Protein]:
        """Find albumin protein in the sample."""
        albumin_accessions = ['P02768', 'ALBU_HUMAN', 'ALB']
        for protein in self._proteins:
            if protein.accession in albumin_accessions:
                return protein
            # Also check if accession contains 'ALB' or 'albumin'
            if 'ALB' in protein.accession.upper() or 'ALBUMIN' in protein.accession.upper():
                return protein
        return None
    
    def get_results(
        self,
        all_protein_details: bool = True,
        quantification_methods: Union[
            Literal['NSAF', 'iBAQ', 'emPAI', 'Top3', 'all'],
            List[Literal['NSAF', 'iBAQ', 'emPAI', 'Top3']]
        ] = 'all',
        calculate_coverage: bool = True,
        absolute_concentrations: Literal['all', 'gramm', 'mol', 'none'] = 'all'
    ) -> pd.DataFrame:
        """
        Get quantification results as pandas DataFrame.
        
        Args:
            all_protein_details: Include protein details (MW, length, etc.)
            quantification_methods: Which quantification methods to include
            calculate_coverage: Include sequence coverage calculations
            absolute_concentrations: Include absolute concentrations ('all', 'gramm', 'mol', 'none')
            
        Returns:
            DataFrame with quantification results
        """
        # Determine which methods to calculate
        if quantification_methods == 'all':
            methods = ['emPAI', 'NSAF', 'iBAQ', 'Top3']
        elif isinstance(quantification_methods, str):
            methods = [quantification_methods]
        else:
            methods = list(quantification_methods)
        
        # Initialize results dictionary
        results = {
            'accession': [p.accession for p in self._proteins]
        }
        
        # Add protein details if requested
        if all_protein_details:
            results.update({
                'molecular_weight_kda': [p.molecular_mass for p in self._proteins],
                'sequence_length': [len(p.sequence) if p.sequence else 0 for p in self._proteins],
                'n_theoretical_peptides': [len(p._get_theoretical_peptides()) for p in self._proteins],
                'n_observed_peptides': [len(p.peptides) for p in self._proteins],
                'n_observable_peptides': [p.observable_peptides for p in self._proteins],
                'sum_intensity': [sum(p.intensities) for p in self._proteins],
            })
        
        # Add coverage information if requested
        if calculate_coverage:
            coverage_data = []
            theoretical_coverage_data = []
            
            for protein in self._proteins:
                try:
                    cov_aa, cov_pct = protein.get_coverage()
                    coverage_data.append({'aa': cov_aa, 'percent': cov_pct})
                    
                    theo_aa, theo_pct = protein.get_theoretical_coverage()
                    theoretical_coverage_data.append({'aa': theo_aa, 'percent': theo_pct})
                except Exception as e:
                    logger.warning(f"Coverage calculation failed for {protein.accession}: {e}")
                    coverage_data.append({'aa': 0, 'percent': 0.0})
                    theoretical_coverage_data.append({'aa': 0, 'percent': 0.0})
            
            results.update({
                'coverage_aa': [d['aa'] for d in coverage_data],
                'coverage_percent': [d['percent'] for d in coverage_data],
                'theoretical_coverage_aa': [d['aa'] for d in theoretical_coverage_data],
                'theoretical_coverage_percent': [d['percent'] for d in theoretical_coverage_data],
            })
        
        # Calculate quantification values
        raw_values = {}
        normalized_values = {}
        
        for method in methods:
            if method == 'emPAI':
                raw_vals = [p.empai for p in self._proteins]
            elif method == 'NSAF':
                # NSAF requires special handling - normalize SAF values
                saf_vals = [p.saf for p in self._proteins]
                raw_vals = saf_vals  # Keep SAF as raw values for debugging
                # Calculate proper NSAF normalization
                normalized_nsaf = calculate_nsaf_normalized(saf_vals)
                normalized_values[method] = normalized_nsaf
            elif method == 'iBAQ':
                raw_vals = [p.ibaq for p in self._proteins]
            elif method == 'Top3':
                raw_vals = [p.top3 for p in self._proteins]
            else:
                raise ValidationError(f"Unknown quantification method: {method}")
            
            raw_values[method] = raw_vals
            
            # For methods other than NSAF, normalize normally
            if method != 'NSAF':
                normalized_values[method] = normalize_values(raw_vals)
            
            # Add to results
            if method == 'NSAF':
                results[f'{method}_saf'] = raw_vals  # SAF values
                results[f'{method}_normalized'] = normalized_values[method]  # NSAF values
            else:
                results[f'{method}_raw'] = raw_vals
                results[f'{method}_normalized'] = normalized_values[method]
        
        # Calculate absolute concentrations if requested
        if absolute_concentrations != 'none':
            self._add_absolute_concentrations(
                results, normalized_values, methods, absolute_concentrations
            )
        
        # Create DataFrame
        df = pd.DataFrame(results)
        
        # Sort by first quantification method (descending)
        if methods:
            sort_column = f'{methods[0]}_normalized'
            df = df.sort_values(sort_column, ascending=False)
        
        return df
    
    def _add_absolute_concentrations(
        self,
        results: Dict[str, List],
        normalized_values: Dict[str, List[float]],
        methods: List[str],
        conc_type: Literal['all', 'gramm', 'mol']
    ) -> None:
        """Add absolute concentration calculations to results."""
        
        # Get albumin protein for albumin-based calculations
        albumin_protein = self._get_albumin_protein()
        
        for method in methods:
            norm_vals = normalized_values[method]
            
            # Total protein-based concentrations
            if self._total_protein_gl is not None:
                abs_conc_total = calculate_absolute_concentrations_total_protein(
                    norm_vals, self._total_protein_gl
                )
                results[f'{method}_abs_total_gl'] = abs_conc_total
                
                if conc_type in ['all', 'mol']:
                    molecular_masses = [p.molecular_mass for p in self._proteins]
                    abs_conc_mol = convert_concentrations_to_molar(abs_conc_total, molecular_masses)
                    results[f'{method}_abs_total_mol'] = abs_conc_mol
            
            # Albumin-based concentrations
            if self._albumin_gl is not None and albumin_protein is not None:
                # Find albumin index
                albumin_idx = None
                for i, protein in enumerate(self._proteins):
                    if protein.accession == albumin_protein.accession:
                        albumin_idx = i
                        break
                
                if albumin_idx is not None:
                    albumin_relative = norm_vals[albumin_idx]
                    abs_conc_albumin = calculate_absolute_concentrations_albumin_standard(
                        norm_vals, albumin_relative, self._albumin_gl
                    )
                    results[f'{method}_abs_albumin_gl'] = abs_conc_albumin
                    
                    if conc_type in ['all', 'mol']:
                        molecular_masses = [p.molecular_mass for p in self._proteins]
                        abs_conc_mol = convert_concentrations_to_molar(abs_conc_albumin, molecular_masses)
                        results[f'{method}_abs_albumin_mol'] = abs_conc_mol
            
            # Combined approach if both total and albumin are available
            if (self._total_protein_gl is not None and 
                self._albumin_gl is not None and 
                albumin_protein is not None):
                
                albumin_idx = None
                for i, protein in enumerate(self._proteins):
                    if protein.accession == albumin_protein.accession:
                        albumin_idx = i
                        break
                
                if albumin_idx is not None:
                    albumin_relative = norm_vals[albumin_idx]
                    abs_conc_combined = calculate_combined_absolute_concentrations(
                        norm_vals, albumin_relative, self._albumin_gl, self._total_protein_gl
                    )
                    results[f'{method}_abs_combined_gl'] = abs_conc_combined
                    
                    if conc_type in ['all', 'mol']:
                        molecular_masses = [p.molecular_mass for p in self._proteins]
                        abs_conc_mol = convert_concentrations_to_molar(abs_conc_combined, molecular_masses)
                        results[f'{method}_abs_combined_mol'] = abs_conc_mol
    
    def validate_mass_balance(self, method: str = 'emPAI', tolerance: float = 0.1) -> bool:
        """
        Validate mass balance for absolute concentrations.
        
        Args:
            method: Quantification method to check
            tolerance: Allowed relative error
            
        Returns:
            True if mass balance is satisfied
        """
        if self._total_protein_gl is None:
            return True  # Can't validate without total protein
        
        # Get absolute concentrations
        df = self.get_results(
            all_protein_details=False,
            quantification_methods=[method],
            calculate_coverage=False,
            absolute_concentrations='gramm'
        )
        
        # Check total protein-based concentrations
        total_col = f'{method}_abs_total_gl'
        if total_col in df.columns:
            abs_concentrations = df[total_col].tolist()
            return validate_mass_balance(abs_concentrations, self._total_protein_gl, tolerance)
        
        return True
    
    def get_summary_statistics(self) -> Dict[str, Any]:
        """
        Get summary statistics for the sample.
        
        Returns:
            Dictionary with summary statistics
        """
        stats = {
            'n_proteins': len(self._proteins),
            'total_peptides': sum(len(p.peptides) for p in self._proteins),
            'proteins_with_intensities': sum(1 for p in self._proteins if p.intensities),
            'total_protein_gl': self._total_protein_gl,
            'albumin_gl': self._albumin_gl,
        }
        
        # Add coverage statistics if possible
        try:
            coverages = [p.get_coverage()[1] for p in self._proteins]  # percentage
            stats.update({
                'mean_coverage_percent': np.mean(coverages),
                'median_coverage_percent': np.median(coverages),
                'min_coverage_percent': np.min(coverages),
                'max_coverage_percent': np.max(coverages),
            })
        except Exception as e:
            logger.warning(f"Could not calculate coverage statistics: {e}")
        
        return stats
    
    def __str__(self) -> str:
        """String representation of sample."""
        return f"ProteomicSample({len(self._proteins)} proteins)"
    
    def __repr__(self) -> str:
        """Detailed representation of sample."""
        return (f"ProteomicSample(proteins={len(self._proteins)}, "
                f"total_protein_gl={self._total_protein_gl}, "
                f"albumin_gl={self._albumin_gl})")