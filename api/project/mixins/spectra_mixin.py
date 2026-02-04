"""Mixin for spectra file and spectra operations."""

import json
import numpy as np
import pandas as pd

from ..array_utils import compress_array, decompress_array
from utils.logger import logger


class SpectraMixin:
    """
    Mixin providing spectra file and spectra management methods.
    
    Requires ProjectBase functionality and SampleMixin (get_sample).
    """
    
    # Spectra file operations
    
    async def add_spectra_file(
        self,
        sample_id: int,
        format: str,
        path: str
    ) -> int:
        """
        Add spectra file record.
        
        Args:
            sample_id: FK to sample
            format: File format (MGF, MZML, etc.)
            path: Original file path
            
        Returns:
            Created spectra_file ID
        """
        # Validate sample exists
        sample = await self.get_sample(sample_id)
        if sample is None:
            raise ValueError(f"Sample with id={sample_id} does not exist")
        
        cursor = await self._execute(
            "INSERT INTO spectre_file (sample_id, format, path) VALUES (?, ?, ?)",
            (sample_id, format, path)
        )
        
        spectra_file_id = cursor.lastrowid
        await self.save()
        
        logger.info(f"Added spectra file: {path} (id={spectra_file_id}, sample_id={sample_id})")
        
        return spectra_file_id
    
    async def get_spectra_files(self, sample_id: int | None = None) -> pd.DataFrame:
        """
        Get spectra files as DataFrame.
        
        Columns: id, sample_id, format, path, sample_name
        """
        if sample_id is not None:
            query = """
                SELECT sf.*, s.name as sample_name
                FROM spectre_file sf
                JOIN sample s ON sf.sample_id = s.id
                WHERE sf.sample_id = ?
                ORDER BY sf.id
            """
            rows = await self._fetchall(query, (sample_id,))
        else:
            query = """
                SELECT sf.*, s.name as sample_name
                FROM spectre_file sf
                JOIN sample s ON sf.sample_id = s.id
                ORDER BY sf.id
            """
            rows = await self._fetchall(query)
        
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    
    # Spectra operations (batch processing)
    
    async def add_spectra_batch(
        self,
        spectra_file_id: int,
        spectra_df: pd.DataFrame
    ) -> None:
        """
        Add batch of spectra to database.
        
        Args:
            spectra_file_id: FK to spectra_file
            spectra_df: DataFrame with columns:
                - seq_no: int
                - title: str
                - scans: int | None
                - charge: int | None
                - rt: float | None
                - pepmass: float
                - mz_array: np.ndarray
                - intensity_array: np.ndarray
                - charge_array: np.ndarray | None
                - charge_array_common_value: int | None
                - all_params: dict | None
        """
        rows_to_insert = []
        
        for _, row in spectra_df.iterrows():
            # Compress arrays
            mz_compressed = compress_array(row['mz_array']) if 'mz_array' in row and row['mz_array'] is not None else None
            intensity_compressed = compress_array(row['intensity_array']) if 'intensity_array' in row and row['intensity_array'] is not None else None
            charge_compressed = compress_array(row['charge_array']) if 'charge_array' in row and row['charge_array'] is not None else None
            
            # Serialize all_params
            all_params_json = json.dumps(row.get('all_params')) if row.get('all_params') else None
            
            # Calculate intensity if not provided
            intensity = row.get('intensity')
            if intensity is None and 'intensity_array' in row and row['intensity_array'] is not None:
                intensity = float(np.sum(row['intensity_array']))
            
            rows_to_insert.append((
                spectra_file_id,
                int(row['seq_no']),
                row.get('title'),
                int(row['scans']) if row.get('scans') is not None else None,
                int(row['charge']) if row.get('charge') is not None and not np.isnan(row.get('charge')) else None,
                float(row['rt']) if row.get('rt') is not None else None,
                float(row['pepmass']),
                intensity,
                mz_compressed,
                intensity_compressed,
                charge_compressed,
                int(row['charge_array_common_value']) if row.get('charge_array_common_value') is not None else None,
                all_params_json
            ))
        
        if rows_to_insert:
            await self._executemany(
                """INSERT INTO spectre 
                   (spectre_file_id, seq_no, title, scans, charge, rt, pepmass, intensity,
                    mz_array, intensity_array, charge_array, charge_array_common_value, all_params)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows_to_insert
            )
            await self.save()
            logger.info(f"Added {len(rows_to_insert)} spectra to file_id={spectra_file_id}")
    
    async def get_spectra(
        self,
        spectra_file_id: int | None = None,
        sample_id: int | None = None,
        limit: int | None = None,
        offset: int = 0
    ) -> pd.DataFrame:
        """
        Get spectra as DataFrame (without arrays for efficiency).
        
        Returns DataFrame with metadata only (no mz/intensity arrays).
        """
        query_parts = ["""
            SELECT s.id, s.spectre_file_id, s.seq_no, s.title, s.scans,
                   s.charge, s.rt, s.pepmass, s.intensity, s.charge_array_common_value,
                   sf.sample_id, sam.name as sample_name
            FROM spectre s
            JOIN spectre_file sf ON s.spectre_file_id = sf.id
            JOIN sample sam ON sf.sample_id = sam.id
        """]
        
        conditions = []
        params = []
        
        if spectra_file_id is not None:
            conditions.append("s.spectre_file_id = ?")
            params.append(spectra_file_id)
        
        if sample_id is not None:
            conditions.append("sf.sample_id = ?")
            params.append(sample_id)
        
        if conditions:
            query_parts.append("WHERE " + " AND ".join(conditions))
        
        query_parts.append("ORDER BY s.id")
        
        if limit is not None:
            query_parts.append(f"LIMIT {limit} OFFSET {offset}")
        
        query = " ".join(query_parts)
        rows = await self._fetchall(query, tuple(params) if params else None)
        
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    
    async def get_spectrum_full(self, spectrum_id: int) -> dict:
        """
        Get full spectrum data including arrays.
        
        Returns:
            dict with all fields including decompressed numpy arrays
        """
        row = await self._fetchone(
            "SELECT * FROM spectre WHERE id = ?",
            (int(spectrum_id),)
        )
        
        if not row:
            raise ValueError(f"Spectrum with id={spectrum_id} not found")
        
        result = dict(row)
        
        # Decompress arrays
        if result.get('mz_array'):
            result['mz_array'] = decompress_array(result['mz_array'])
        
        if result.get('intensity_array'):
            result['intensity_array'] = decompress_array(result['intensity_array'])
        
        if result.get('charge_array'):
            result['charge_array'] = decompress_array(result['charge_array'])
        
        # Deserialize all_params
        if result.get('all_params'):
            result['all_params'] = json.loads(result['all_params'])
        
        return result
    
    async def get_spectra_idlist(
        self,
        spectra_file_id: int,
        by: str = "seq_no"
    ) -> list[dict[str, int]]:
        """
        Get mapping from seq_no or scans to spectrum database IDs.
        
        This method is essential for identification import workflow:
        1. Parse identification file (contains seq_no or scans references)
        2. Get mapping: seq_no/scans -> spectrum DB ID
        3. Enrich identification DataFrame with spectre_id
        4. Add identifications to database
        
        Args:
            spectra_file_id: Spectra file ID to get mapping for
            by: Field to use as key - "seq_no" or "scans"
            
        Returns:
            Dict mapping seq_no/scans value to spectrum database ID
            
        Raises:
            ValueError: If 'by' parameter is invalid
        """
        print(f'getting idlist: by {by} for id: {spectra_file_id}')
        if by not in ("seq_no", "scans"):
            raise ValueError(
                f"Invalid 'by' parameter: {by}. Must be 'seq_no' or 'scans'"
            )
        
        query = f"""
            SELECT id, {by}
            FROM spectre
            WHERE spectre_file_id = ?
            AND {by} IS NOT NULL
        """
        
        rows = await self._fetchall(query, (int(spectra_file_id),))
        
        return [{by: row[by], 'spectre_id': row['id']} for row in rows]
