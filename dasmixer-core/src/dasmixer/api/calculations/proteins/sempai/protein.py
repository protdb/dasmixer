"""
Protein class for quantitative proteomics analysis.
"""

import warnings
from typing import List, Optional, Union, Tuple, Dict, Any
import logging

import numpy as np
from uniprot_meta_tool import UniprotData

from .utils import (
    digest_protein,
    calculate_peptide_features,
    remove_modifications,
    match_observed_peptides,
    DigestionParams,
)
from .exceptions import ValidationError, DataError
from .algorithms import (
    calculate_empai_value,
    calculate_nsaf_value,
    calculate_ibaq_value,
    calculate_top3_value,
)

logger = logging.getLogger(__name__)

# Try to import biopython Sequence if available
try:
    from Bio.Seq import Seq as BioPythonSequence
    HAS_BIOPYTHON = True
except ImportError:
    BioPythonSequence = None
    HAS_BIOPYTHON = False

try:
    from Bio.Align import PairwiseAligner
    HAS_BIO_ALIGN = True
except ImportError:
    HAS_BIO_ALIGN = False


class Protein:
    """
    Represents a protein in a proteomic sample with quantification capabilities.
    
    This class provides lazy evaluation of quantification metrics (emPAI, NSAF, iBAQ, Top3)
    and automatic recalculation when sequence or peptides change.
    
    The protein can handle various data formats:
    - Unique peptide sequences with aggregated intensities and PSM counts
    - Repeated peptide sequences (raw spectra data)
    - Mixed data with optional intensity information
    """
    
    def __init__(
        self,
        accession: str,
        sequence: Optional[Union[str, "BioPythonSequence"]] = None,
        peptides: Optional[List[Union[str, "BioPythonSequence"]]] = None,
        is_uniprot: bool = True,
        intensities: Optional[List[float]] = None,
        psm_counts: Optional[List[int]] = None,
        empai_base: float = 10.0,
        observable_parameters: Optional[DigestionParams] = None,
    ):
        """
        Initialize a Protein object.
        
        Args:
            accession: UniProt accession or protein identifier
            sequence: Protein sequence (string or Bio.Seq object)
            peptides: List of observed peptide sequences
            is_uniprot: Whether to fetch sequence from UniProt if sequence is None
            intensities: List of peptide intensities (optional, required for iBAQ/Top3)
            psm_counts: List of PSM (Peptide-Spectrum Match) counts per peptide
                       If None, defaults to [1] * len(peptides)
            empai_base: Base for emPAI exponential calculation (default 10)
                       Some researchers prefer different values (doi:10.1371/journal.pone.0032339)
            observable_parameters: Parameters for determining observable peptides
        """
        self._accession = accession
        self._sequence = None
        self._peptides = []
        self._intensities = intensities or []
        self._psm_counts = None
        self._empai_base = empai_base
        # Always create DigestionParams object, even if empty
        self._observable_parameters = observable_parameters or DigestionParams()
        self._is_uniprot = is_uniprot
        
        # Cached values for lazy evaluation
        self._empai = None
        self._saf = None  # Changed from _nsaf to _saf for clarity
        self._ibaq = None
        self._top3 = None
        self._observable_peptides = None
        self._molecular_mass = None
        self._theoretical_peptides = None
        self._coverage_data = None
        
        # Set sequence first (this will trigger validation and caching reset)
        self.sequence = sequence
        
        # Set peptides and psm_counts together to avoid conflicts
        self._set_peptides_with_psm_counts(peptides or [], psm_counts)
        
    def _set_peptides_with_psm_counts(self, peptides: List[Union[str, "BioPythonSequence"]], psm_counts: Optional[List[int]]) -> None:
        """Set peptides and PSM counts together to maintain consistency."""
        # Convert any BioPython sequences to strings
        clean_peptides = []
        if peptides:
            for peptide in peptides:
                if HAS_BIOPYTHON and isinstance(peptide, BioPythonSequence):
                    clean_peptides.append(str(peptide))
                else:
                    clean_peptides.append(remove_modifications(str(peptide)))
        
        self._peptides = clean_peptides
        
        # Set PSM counts
        if psm_counts is None:
            # Default: assume 1 PSM per peptide
            self._psm_counts = [1] * len(self._peptides)
        else:
            # Validate length match
            if len(psm_counts) != len(self._peptides):
                raise ValidationError(
                    f"PSM counts length ({len(psm_counts)}) must match "
                    f"peptides length ({len(self._peptides)})"
                )
            # Validate PSM counts are positive integers
            if not all(isinstance(count, int) and count > 0 for count in psm_counts):
                raise ValidationError("All PSM counts must be positive integers")
            
            self._psm_counts = list(psm_counts)
        
        # Reset cached values
        self._reset_cache()
        
    def _setup_psm_counts(self) -> None:
        """Setup PSM counts with validation."""
        if self._psm_counts is None:
            # Default: assume 1 PSM per peptide
            self._psm_counts = [1] * len(self._peptides)
        else:
            # Validate length match
            if len(self._psm_counts) != len(self._peptides):
                raise ValidationError(
                    f"PSM counts length ({len(self._psm_counts)}) must match "
                    f"peptides length ({len(self._peptides)})"
                )
            # Validate PSM counts are positive integers
            if not all(isinstance(count, int) and count > 0 for count in self._psm_counts):
                raise ValidationError("All PSM counts must be positive integers")
    
    @property
    def accession(self) -> str:
        """Get protein accession."""
        return self._accession
    
    @property
    def empai_base(self) -> float:
        """Get emPAI base value."""
        return self._empai_base
    
    @empai_base.setter
    def empai_base(self, value: float) -> None:
        """Set emPAI base and reset cached emPAI value."""
        if value <= 0:
            raise ValidationError("emPAI base must be positive")
        self._empai_base = value
        self._empai = None
    
    @property
    def sequence(self) -> Optional[str]:
        """Get protein sequence as string."""
        return self._sequence
    
    @sequence.setter
    def sequence(self, value: Optional[Union[str, "BioPythonSequence"]]) -> None:
        """Set protein sequence and reset cached values."""
        if value is None and self._is_uniprot:
            # Fetch from UniProt
            try:
                logger.info(f"Fetching sequence for {self._accession}")
                uniprot_data = UniprotData(self._accession)
                self._sequence = uniprot_data.sequence
                if not self._sequence:
                    raise DataError(f"No sequence found for accession {self._accession}")
            except Exception as e:
                raise DataError(f"Failed to fetch sequence for {self._accession}: {e}")
        else:
            # Convert BioPython Sequence to string if needed
            if HAS_BIOPYTHON and isinstance(value, BioPythonSequence):
                self._sequence = str(value)
            else:
                self._sequence = value
        
        # Reset cached values
        self._reset_cache()
    
    @property
    def peptides(self) -> List[str]:
        """Get list of observed peptides."""
        return self._peptides
    
    @peptides.setter
    def peptides(self, value: List[Union[str, "BioPythonSequence"]]) -> None:
        """Set peptides and reset cached values."""
        # When setting peptides independently, reset PSM counts to defaults
        self._set_peptides_with_psm_counts(value, None)
    
    @property
    def intensities(self) -> List[float]:
        """Get list of peptide intensities."""
        return self._intensities
    
    @intensities.setter
    def intensities(self, value: Optional[List[float]]) -> None:
        """Set peptide intensities and reset cached values."""
        self._intensities = value or []
        # Validate length if provided
        if self._intensities and len(self._intensities) != len(self._peptides):
            raise ValidationError(
                f"Intensities length ({len(self._intensities)}) must match "
                f"peptides length ({len(self._peptides)})"
            )
        # Reset cached intensity-dependent values
        self._ibaq = None
        self._top3 = None
    
    @property
    def psm_counts(self) -> List[int]:
        """Get list of PSM counts."""
        return self._psm_counts
    
    @psm_counts.setter
    def psm_counts(self, value: Optional[List[int]]) -> None:
        """Set PSM counts and reset cached values."""
        if value is None:
            self._psm_counts = [1] * len(self._peptides)
        else:
            # Validate length match
            if len(value) != len(self._peptides):
                raise ValidationError(
                    f"PSM counts length ({len(value)}) must match "
                    f"peptides length ({len(self._peptides)})"
                )
            # Validate PSM counts are positive integers
            if not all(isinstance(count, int) and count > 0 for count in value):
                raise ValidationError("All PSM counts must be positive integers")
            
            self._psm_counts = list(value)
        
        # Reset SAF (depends on PSM counts)
        self._saf = None
    
    @property
    def observable_parameters(self) -> DigestionParams:
        """Get observable peptide parameters."""
        return self._observable_parameters
    
    @observable_parameters.setter
    def observable_parameters(self, value: Optional[DigestionParams]) -> None:
        """Set observable parameters and reset cached values."""
        # Always ensure we have a DigestionParams object
        self._observable_parameters = value or DigestionParams()
        self._observable_peptides = None
        self._empai = None
        self._saf = None
        self._ibaq = None
    
    def _reset_cache(self) -> None:
        """Reset all cached values."""
        self._empai = None
        self._saf = None
        self._ibaq = None
        self._top3 = None
        self._observable_peptides = None
        self._molecular_mass = None
        self._theoretical_peptides = None
        self._coverage_data = None
    
    def _ensure_sequence(self) -> str:
        """Ensure sequence is available, raise error if not."""
        if not self._sequence:
            raise ValidationError(f"No sequence available for protein {self._accession}")
        return self._sequence
    
    def _get_theoretical_peptides(self) -> List[Dict[str, Any]]:
        """Get theoretical peptides (cached)."""
        if self._theoretical_peptides is None:
            sequence = self._ensure_sequence()
            # Use enzyme from observable_parameters
            enzyme = self._observable_parameters.get_pyteomics_enzyme_name()
            self._theoretical_peptides = digest_protein(
                sequence, 
                enzyme=enzyme,
                max_cleavage_sites=self._observable_parameters.max_cleavage_sites
            )
        return self._theoretical_peptides
    
    @property
    def observable_peptides(self) -> int:
        """Get number of observable peptides (lazy evaluation)."""
        if self._observable_peptides is None:
            theoretical = self._get_theoretical_peptides()
            
            # Apply filters from observable parameters
            count = 0
            for pep_data in theoretical:
                sequence = pep_data['sequence']
                features = calculate_peptide_features(sequence)
                
                # Apply filters only if they are set in parameters
                params = self._observable_parameters
                
                # Length filter
                if features['length'] < params.min_peptide_length:
                    continue
                if features['length'] > params.max_peptide_length:
                    continue
                
                # Mass filter (optional)
                if (params.min_peptide_mass is not None and 
                    features['mass'] < params.min_peptide_mass):
                    continue
                if (params.max_peptide_mass is not None and 
                    features['mass'] > params.max_peptide_mass):
                    continue
                
                # Intensity filter (optional) - not applicable for theoretical
                
                # Cleavage filter
                if pep_data['missed_cleavages'] > params.max_cleavage_sites:
                    continue
                
                count += 1
            
            self._observable_peptides = count
        
        return self._observable_peptides
    
    @property
    def molecular_mass(self) -> float:
        """Get protein molecular mass in kDa (lazy evaluation)."""
        if self._molecular_mass is None:
            sequence = self._ensure_sequence()
            # Simple approximation: average amino acid mass * length
            self._molecular_mass = len(sequence) * 0.11  # kDa
        return self._molecular_mass
    
    @property
    def empai(self) -> float:
        """
        Get emPAI value (lazy evaluation).
        
        emPAI = empai_base^(N_obs/N_observ) - 1
        
        Uses unique peptide sequences only (no duplicates).
        """
        if self._empai is None:
            sequence = self._ensure_sequence()
            self._empai = calculate_empai_value(
                self._peptides,
                self._intensities,
                sequence,
                self._observable_parameters,
                empai_base=self._empai_base
            )
        return self._empai
    
    @property
    def saf(self) -> float:
        """
        Get SAF (Spectral Abundance Factor) value (lazy evaluation).
        
        SAF = SpC / L_i, where SpC is total PSM count and L_i is sequence length in amino acids.
        
        Note: This is SAF, not NSAF. NSAF requires normalization at sample level:
        NSAF_i = SAF_i / Σ(SAF_j)
        """
        if self._saf is None:
            total_spc = sum(self._psm_counts)  # SpC = sum of PSM counts
            sequence_length = len(self._sequence) if self._sequence else 1
            self._saf = total_spc / sequence_length
        return self._saf
    
    @property
    def nsaf(self) -> float:
        """
        Get SAF value for backward compatibility.
        
        WARNING: This returns SAF, not NSAF! NSAF requires normalization at sample level.
        Use sample.get_results() for proper NSAF calculation.
        """
        warnings.warn(
            "protein.nsaf returns SAF, not normalized NSAF. "
            "Use ProteomicSample.get_results() for proper NSAF calculation.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.saf
    
    @property
    def ibaq(self) -> float:
        """
        Get iBAQ value (lazy evaluation).
        
        iBAQ uses ALL intensities, including duplicates.
        Returns 0 if no intensities available.
        """
        if self._ibaq is None:
            if not self._intensities:
                self._ibaq = 0.0
            else:
                self._ibaq = calculate_ibaq_value(
                    self._intensities,  # All intensities, no deduplication
                    self.observable_peptides
                )
        return self._ibaq
    
    @property
    def top3(self) -> float:
        """
        Get Top3 value (lazy evaluation).
        
        Returns 0 if no intensities available.
        """
        if self._top3 is None:
            if not self._intensities:
                self._top3 = 0.0
            else:
                self._top3 = calculate_top3_value(self._intensities)
        return self._top3
    
    @property
    def has_intensities(self) -> bool:
        """Check if protein has intensity data for iBAQ/Top3 calculations."""
        return len(self._intensities) > 0
    
    def get_coverage(self) -> Tuple[int, float]:
        """
        Calculate sequence coverage by observed peptides.
        
        Returns:
            Tuple of (absolute coverage in amino acids, percentage coverage)
        """
        if self._coverage_data is None:
            if not HAS_BIO_ALIGN:
                warnings.warn("Bio.Align not available, using simple coverage calculation")
                self._coverage_data = self._get_simple_coverage()
            else:
                self._coverage_data = self._get_alignment_coverage()
        
        return self._coverage_data
    
    def _get_simple_coverage(self) -> Tuple[int, float]:
        """Simple coverage calculation without alignment."""
        sequence = self._ensure_sequence()
        covered = set()
        
        # Use unique peptides only for coverage
        unique_peptides = list(set(self._peptides))
        
        for peptide in unique_peptides:
            start_pos = sequence.find(peptide)
            if start_pos != -1:
                for i in range(start_pos, start_pos + len(peptide)):
                    covered.add(i)
        
        coverage_aa = len(covered)
        coverage_percent = (coverage_aa / len(sequence)) * 100 if sequence else 0.0
        
        return coverage_aa, coverage_percent
    
    def _get_alignment_coverage(self) -> Tuple[int, float]:
        """Coverage calculation using Bio.Align (more accurate)."""
        sequence = self._ensure_sequence()
        aligner = PairwiseAligner()
        aligner.mode = 'global'
        aligner.internal_gap_score = -1
        
        matched = [False] * len(sequence)
        
        # Use unique peptides only for coverage
        unique_peptides = list(set(self._peptides))
        
        for peptide in unique_peptides:
            try:
                raw_aln = aligner.align(sequence, peptide)
                if raw_aln:
                    aln = list(raw_aln[0])
                    top_gaps = 0
                    for resi, resn in enumerate(aln[1]):
                        if resi < len(aln[0]) and aln[0][resi] == '-':
                            top_gaps += 1
                            continue
                        seq_pos = resi - top_gaps
                        if seq_pos < len(sequence) and sequence[seq_pos] == resn:
                            matched[seq_pos] = True
            except Exception as e:
                logger.warning(f"Alignment failed for peptide {peptide}: {e}")
                # Fallback to simple search
                start_pos = sequence.find(peptide)
                if start_pos != -1:
                    for i in range(start_pos, min(start_pos + len(peptide), len(sequence))):
                        matched[i] = True
        
        coverage_aa = sum(matched)
        coverage_percent = (coverage_aa / len(sequence)) * 100 if sequence else 0.0
        
        return coverage_aa, coverage_percent
    
    def get_theoretical_coverage(self) -> Tuple[int, float]:
        """
        Calculate theoretical maximum sequence coverage.
        
        Returns:
            Tuple of (theoretical coverage in amino acids, theoretical percentage)
        """
        sequence = self._ensure_sequence()
        theoretical_peptides = self._get_theoretical_peptides()
        
        covered = set()
        for pep_data in theoretical_peptides:
            peptide = pep_data['sequence']
            start_pos = sequence.find(peptide)
            if start_pos != -1:
                for i in range(start_pos, start_pos + len(peptide)):
                    covered.add(i)
        
        coverage_aa = len(covered)
        coverage_percent = (coverage_aa / len(sequence)) * 100 if sequence else 0.0
        
        return coverage_aa, coverage_percent
    
    def predict_optimal_parameters(
        self,
        **kwargs
    ) -> DigestionParams:
        """
        Predict optimal digestion parameters for this protein using observation-based analysis.
        
        This method analyzes the observed peptides directly without requiring theoretical
        matching, making it suitable for de novo sequencing and non-tryptic data.
        
        Args:
            **kwargs: Additional arguments passed to predict_parameters_from_protein
                     (e.g., enable_ml_model, enable_length_filter, etc.)
            
        Returns:
            Optimized DigestionParams object
            
        Example:
            >>> protein = Protein("P02768", peptides=["DAHKSEVAHRFK", ...])
            >>> params = protein.predict_optimal_parameters(enable_ml_model=True)
            >>> protein.observable_parameters = params
        """
        # Import here to avoid circular imports
        from .prediction import predict_parameters_from_protein
        
        return predict_parameters_from_protein(
            protein=self,
            **kwargs
        )
    
    def optimize_parameters(
        self,
        **kwargs
    ) -> "Protein":
        """
        Create a new protein object with optimized parameters using observation-based analysis.
        
        This is a convenience method that predicts optimal parameters and
        returns a new protein object with those parameters applied.
        
        Args:
            **kwargs: Additional arguments passed to predict_parameters_from_protein
                     (e.g., enable_ml_model, enable_length_filter, etc.)
            
        Returns:
            New Protein object with optimized parameters
            
        Example:
            >>> protein = Protein("P02768", peptides=["DAHKSEVAHRFK", ...])
            >>> optimized = protein.optimize_parameters(enable_ml_model=True)
            >>> print(f"Original emPAI: {protein.empai:.4f}")
            >>> print(f"Optimized emPAI: {optimized.empai:.4f}")
        """
        # Import here to avoid circular imports
        from .prediction import predict_and_apply_parameters
        
        return predict_and_apply_parameters(
            protein=self,
            **kwargs
        )
    
    def apply_parameters(self, params: DigestionParams) -> "Protein":
        """
        Apply given parameters to create a new protein object.
        
        Args:
            params: DigestionParams to apply
            
        Returns:
            New Protein object with applied parameters
            
        Example:
            >>> params = DigestionParams(min_peptide_length=8, max_peptide_length=25)
            >>> new_protein = protein.apply_parameters(params)
        """
        # Import here to avoid circular imports
        from .prediction import apply_parameters_to_protein
        
        return apply_parameters_to_protein(self, params)
    
    def compare_parameters(
        self,
        other_params: DigestionParams,
        metrics: Optional[List[str]] = None
    ) -> Dict[str, Tuple[float, float]]:
        """
        Compare current parameters with other parameters.
        
        Args:
            other_params: Parameters to compare with
            metrics: List of metrics to compare ('empai', 'saf', 'ibaq', 'top3')
                    If None, compares all available metrics
            
        Returns:
            Dictionary mapping metric names to (current_value, other_value) tuples
            
        Example:
            >>> new_params = DigestionParams(min_peptide_length=8)
            >>> comparison = protein.compare_parameters(new_params)
            >>> print(f"emPAI: {comparison['empai'][0]:.4f} -> {comparison['empai'][1]:.4f}")
        """
        if metrics is None:
            metrics = ['empai', 'observable_peptides']
            if self.has_intensities:
                metrics.extend(['ibaq', 'top3'])
        
        # Get current values
        current_values = {}
        for metric in metrics:
            if hasattr(self, metric):
                current_values[metric] = getattr(self, metric)
        
        # Create temporary protein with other parameters
        temp_protein = Protein(
            accession=self._accession,
            sequence=self._sequence,
            peptides=self._peptides[:],  # Copy
            intensities=self._intensities[:] if self._intensities else None,
            psm_counts=self._psm_counts[:] if self._psm_counts else None,
            empai_base=self._empai_base,
            observable_parameters=other_params,
            is_uniprot=False,  # Don't fetch sequence again
        )
        
        # Get other values
        other_values = {}
        for metric in metrics:
            if hasattr(temp_protein, metric):
                other_values[metric] = getattr(temp_protein, metric)
        
        # Combine results
        comparison = {}
        for metric in metrics:
            if metric in current_values and metric in other_values:
                comparison[metric] = (current_values[metric], other_values[metric])
        
        return comparison
    
    def __str__(self) -> str:
        """String representation of protein."""
        return f"Protein({self._accession}, {len(self._peptides)} peptides)"
    
    def __repr__(self) -> str:
        """Detailed representation of protein."""
        return (f"Protein(accession='{self._accession}', "
                f"peptides={len(self._peptides)}, "
                f"intensities={len(self._intensities)}, "
                f"psm_counts={len(self._psm_counts)}, "
                f"empai_base={self._empai_base})")