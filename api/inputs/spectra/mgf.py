"""MGF (Mascot Generic Format) spectral data parser."""

from typing import AsyncIterator
import re

import pandas as pd
import numpy as np
from pyteomics.mgf import MGF
from pyteomics.auxiliary.structures import PyteomicsError

from .base import SpectralDataParser


class MGFParser(SpectralDataParser):
    """
    Parser for MGF (Mascot Generic Format) files.
    
    MGF is a text-based format commonly used for MS/MS data exchange.
    Each spectrum is defined by a BEGIN IONS / END IONS block.
    
    Example usage:
        >>> parser = MGFParser("spectra.mgf")
        >>> if await parser.validate():
        ...     async for batch in parser.parse_batch(batch_size=1000):
        ...         print(f"Parsed {len(batch)} spectra")
    """

    mgf_file: MGF | None = None
    _file_position: int = 0
    scan_regexp: re.Pattern

    def __init__(self, file_path: str, **kwargs):
        """
        Initialize MGF parser.
        
        Args:
            file_path: Path to MGF file
            **kwargs: Additional arguments passed to parent
        """
        super().__init__(file_path, **kwargs)
        self.mgf_file = MGF(str(self.file_path))
        # Regex to extract scan number from TITLE field
        self.scan_regexp = re.compile(r'scans?=(\d+)', re.IGNORECASE)
        self._file_position = 0

    async def validate(self) -> bool:
        """
        Validate MGF file format.
        
        Attempts to read first spectrum to verify file is valid MGF.
        
        Returns:
            True if file is valid MGF format
        """
        try:
            MGF(str(self.file_path)).__next__()
            return True
        except (PyteomicsError, StopIteration):
            return False

    async def parse_batch(
        self,
        batch_size: int = 1000
    ) -> AsyncIterator[pd.DataFrame]:
        """
        Parse MGF file in batches.
        
        Yields:
            DataFrame batches with spectrum data, including peaks_count column.
        """
        eof = False
        while not eof:
            batch_data = []
            for i in range(batch_size):
                try:
                    record = self.mgf_file.__next__()
                except StopIteration:
                    eof = True
                    break
                
                mz_array = record.get('m/z array', None)
                intensity_arr = record.get('intensity array', None)

                # peaks_count — length of mz_array (source of truth for number of peaks)
                peaks_count = len(mz_array) if mz_array is not None else 0

                # Process charge array
                charge_array = record.get('charge array', np.array([]))
                charge_array = np.ma.filled(
                    charge_array.astype(float),
                    fill_value=np.nan
                )
                
                # Check if all charges are the same
                unique_charges = np.unique(charge_array)
                if len(unique_charges) == 1:
                    charge_array_data = None
                    common_value = unique_charges[0]
                    if np.isnan(common_value):
                        common_value = None
                    else:
                        common_value = int(common_value)
                else:
                    charge_array_data = charge_array
                    common_value = None
                
                # Extract scan number
                params = record.get('params', {})
                scans = params.get('scans', None)
                title = params.get('title', '')
                
                # Try to extract scan from title if not in params
                if scans is None and title:
                    try:
                        scans = int(self.scan_regexp.findall(title.lower())[0])
                    except (IndexError, ValueError):
                        scans = None
                
                # Extract PEPMASS (can be single value or tuple)
                pepmass_data = params.get('pepmass', (None, None))
                if isinstance(pepmass_data, (list, tuple)):
                    pepmass = pepmass_data[0]
                    intensity = pepmass_data[1] if len(pepmass_data) > 1 else None
                else:
                    pepmass = pepmass_data
                    intensity = None
                
                # Get charge (can be list, take first value)
                charge_data = params.get('charge', [None])
                if isinstance(charge_data, (list, tuple)):
                    charge = charge_data[0] if charge_data else None
                else:
                    charge = charge_data
                
                batch_data.append({
                    'seq_no': self._file_position,
                    'title': title,
                    'scans': scans,
                    'charge': charge,
                    'rt': params.get('rtinseconds', None),
                    'pepmass': pepmass,
                    'intensity': intensity,
                    'mz_array': mz_array,
                    'intensity_array': intensity_arr,
                    'charge_array': charge_array_data,
                    'charge_array_common_value': common_value,
                    'peaks_count': peaks_count,
                    'all_params': params,
                })
                
                self._file_position += 1
            
            if batch_data:
                yield pd.DataFrame(batch_data)

    async def add_metadata(self) -> dict:
        """
        Add MGF-specific metadata.
        
        Currently returns empty dict. Could be extended to parse
        MGF header comments if needed.
        
        Returns:
            Empty dict (MGF files typically don't have rich metadata)
        """
        return {}
