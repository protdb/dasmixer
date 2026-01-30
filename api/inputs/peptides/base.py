"""Base class for identification data parsers."""

from abc import abstractmethod
from typing import AsyncIterator
import pandas as pd

from ..base import BaseImporter


class IdentificationParser(BaseImporter):
    """
    Base class for identification data parsers.
    
    Parsers are independent of project context and should only parse files,
    returning standard DataFrames. Mapping to spectra IDs is handled externally
    via Project.get_spectra_mapping().
    
    Supports various tabular formats (CSV, XLSX, tool-specific outputs).
    
    Attributes:
        spectra_id_field: Field name to use for spectrum mapping ('scans' or 'seq_no')
    """
    
    # Default field for spectrum ID mapping - subclasses can override
    spectra_id_field: str = 'seq_no'
    
    def __init__(self, file_path: str):
        """
        Initialize identification parser.
        
        Args:
            file_path: Path to identification file
        """
        super().__init__(file_path)

    @abstractmethod
    async def parse_batch(
        self,
        batch_size: int = 1000
    ) -> AsyncIterator[tuple[pd.DataFrame, pd.DataFrame | None]]:
        """
        Parse identifications in batches.
        
        Some identification files (e.g., from library search tools) may contain
        both peptide and protein identifications in one file.
        
        Yields:
            Tuple of (peptide_df, protein_df):
            
            peptide_df: DataFrame with columns:
                - scans: int | None - scan number(s) for mapping to spectra
                - seq_no: int | None - sequential number for mapping to spectra
                  (at least one of scans/seq_no must be present)
                - sequence: str - peptide sequence with modifications
                - canonical_sequence: str - canonical sequence without modifications
                - ppm: float | None - mass error in ppm
                - theor_mass: float | None - theoretical mass
                - score: float | None - identification score
                - positional_scores: dict | None - per-position scores
                
            protein_df: DataFrame | None with columns (if proteins present):
                - scans: int | None - scan number for mapping
                - seq_no: int | None - sequential number for mapping
                - sequence: str - peptide sequence
                - protein_id: str - protein identifier
                - protein_sequence: str | None - full protein sequence
                - gene: str | None - gene name
                
        Note:
            Protein identifications are collected but not processed in current
            implementation. Will be used in Stage 4.
            
        Raises:
            ValueError: If neither scans nor seq_no columns are present
        """
        pass
