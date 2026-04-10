"""Shared state for Proteins tab."""

from dataclasses import dataclass, field
import pandas as pd


@dataclass
class ProteinsTabState:
    """
    Shared state for Proteins tab sections.
    
    Stores parameters, UI state, and cached data.
    """
    
    # Detection parameters
    min_peptides: int = 2
    min_unique_evidence: int = 1
    
    # LFQ parameters
    lfq_methods: dict[str, bool] = field(default_factory=lambda: {
        'emPAI': False,
        'iBAQ': False,
        'NSAF': False,
        'Top3': False
    })
    empai_base_value: float = 10.0
    enzyme: str = 'trypsin'
    min_peptide_length: int = 7
    max_peptide_length: int = 30
    max_cleavage_sites: int = 2
    
    # Table state
    selected_sample: str | None = None  # For filtering table
    table_data: pd.DataFrame | None = None
    
    # Counts
    protein_identification_count: int = 0
    protein_quantification_count: int = 0
    
    def get_selected_lfq_methods(self) -> list[str]:
        """
        Get list of selected LFQ methods.
        
        Returns:
            List of method names that are enabled
        """
        return [k for k, v in self.lfq_methods.items() if v]
    
    def reset_lfq_methods(self):
        """Reset all LFQ method checkboxes to False."""
        for key in self.lfq_methods:
            self.lfq_methods[key] = False
