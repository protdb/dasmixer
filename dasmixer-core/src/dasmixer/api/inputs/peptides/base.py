"""Base class for identification data parsers."""

from abc import abstractmethod
from typing import AsyncIterator
import pandas as pd

from dasmixer.api.project.dataclasses import Protein
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
    
    # NEW: Whether this parser can collect protein data from the identification file.
    # Subclasses that can provide protein IDs must set this to True.
    contain_proteins: bool = False

    # NEW: Whether this parser supports stacked files (one file — multiple samples).
    # Subclasses that support stacked import must set this to True.
    can_import_stacked: bool = False

    # NEW: Column name used to split stacked file by sample.
    # Set in subclass if can_import_stacked = True.
    sample_id_column: str | None = None
    
    def __init__(
        self,
        file_path: str,
        collect_proteins: bool = False,
        is_uniprot_proteins: bool = False,
    ):
        """
        Initialize identification parser.
        
        Args:
            file_path: Path to identification file
        """
        super().__init__(file_path)
        self.collect_proteins = collect_proteins
        self.is_uniprot_proteins = is_uniprot_proteins
        self._proteins: dict[str, Protein] = {}

    async def get_sample_ids(self, override_column: str | None = None) -> list[str]:
        """
        Return the list of unique sample IDs present in the file.
        
        Used to populate the sample list in the stacked import dialog.
        The column to read from is determined by override_column (if provided),
        or self.sample_id_column.
        
        Args:
            override_column: If provided, overrides self.sample_id_column.
            
        Returns:
            Sorted list of unique sample ID strings.
            
        Raises:
            NotImplementedError: If can_import_stacked is False.
            ValueError: If the column is not found in the file.
        """
        raise NotImplementedError(
            "get_sample_ids() is only available for parsers with can_import_stacked=True"
        )

    @abstractmethod
    async def parse_batch(
        self,
        batch_size: int = 1000
    ) -> AsyncIterator[pd.DataFrame]:
        """
        Parse identifications in batches.
        
        Yields:
            DataFrame with columns:
                - scans: int | None
                - seq_no: int | None  (at least one of scans/seq_no must be present)
                - sequence: str
                - canonical_sequence: str
                - ppm: float | None
                - theor_mass: float | None
                - score: float | None
                - positional_scores: dict | None
                - src_file_protein_id: str | None  (if contain_proteins=True)
                - sample_id: str | None  (if can_import_stacked=True)
            
        Note:
            Protein data is NOT yielded directly. Instead, subclasses accumulate
            Protein objects in self._proteins during iteration. After parse_batch
            completes, the caller reads self._proteins to persist proteins to DB.
            
            sample_id column is ignored by the calling code unless
            can_import_stacked=True is set on the parser.
            
        Raises:
            ValueError: If neither scans nor seq_no columns are present.
        """
        pass

    @property
    def proteins(self) -> dict[str, 'Protein']:
        """
        Return collected proteins dict (protein_id -> Protein).
        
        Available after parse_batch iteration is complete.
        Contains data only if contain_proteins=True and the file had protein data.
        """
        return self._proteins
