"""Base class for spectral data parsers."""

from abc import abstractmethod
from typing import AsyncIterator
from datetime import datetime
import os
import pandas as pd

from ..base import BaseImporter


class SpectralDataParser(BaseImporter):
    """
    Base class for spectral data parsers (MGF, MZML, etc.).
    
    Supports batch processing for large files and automatic metadata extraction.
    """
    
    @abstractmethod
    async def parse_batch(
        self,
        batch_size: int = 1000
    ) -> AsyncIterator[pd.DataFrame]:
        """
        Parse spectra in batches.
        
        Yields DataFrames containing spectrum metadata and peak data.
        Arrays are kept as numpy arrays for efficient storage.
        
        Args:
            batch_size: Number of spectra per batch
            
        Yields:
            DataFrame batches with columns:
                - seq_no: int - sequential number in file (starting from 0 or 1)
                - title: str - spectrum title
                - scans: int | None - scan number(s) from instrument
                - charge: int | None - precursor charge state
                - rt: float | None - retention time (seconds)
                - pepmass: float - precursor m/z
                - intensity: float | None - precursor intensity (e.g., from PEPMASS in MGF)
                - mz_array: np.ndarray - m/z values of peaks
                - intensity_array: np.ndarray - intensity values of peaks
                - charge_array: np.ndarray | None - charge states for each peak
                - charge_array_common_value: int | None - common charge if all peaks have same charge
                - all_params: dict | None - additional parameters from file
                
        Note:
            - intensity and intensity_array are different values and cannot be derived from each other
            - intensity is typically precursor/parent ion intensity
            - intensity_array contains peak intensities in the spectrum
        """
        pass
    
    async def get_metadata(self) -> dict:
        """
        Get file metadata.
        
        Returns base metadata from file system plus format-specific metadata
        from add_metadata().
        
        Returns:
            dict with metadata:
                - file_size: int - file size in bytes
                - created_at: str - creation timestamp (ISO format)
                - modified_at: str - modification timestamp (ISO format)
                - file_path: str - absolute file path
                - plus any additional metadata from add_metadata()
        """
        stat = os.stat(self.file_path)
        metadata = {
            'file_size': stat.st_size,
            'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
            'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            'file_path': str(self.file_path.absolute())
        }
        
        # Add format-specific metadata
        additional = await self.add_metadata()
        metadata.update(additional)
        
        return metadata
    
    async def add_metadata(self) -> dict:
        """
        Add format-specific metadata.
        
        Override in subclasses to provide additional metadata such as:
        - Format version
        - Instrument information
        - Acquisition parameters
        - File-specific headers
        
        Note: Do NOT include total spectrum count here, as determining it
        often requires reading the entire file.
        
        Returns:
            dict with additional metadata (empty by default)
        """
        return {}
