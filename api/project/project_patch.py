"""
ИНСТРУКЦИЯ ПО ПРИМЕНЕНИЮ ПАТЧА

Откройте файл api/project/project.py и найдите строку:
    # Identification file operations

Перед этой строкой вставьте следующий метод:
"""

METHOD_TO_INSERT = '''
    async def get_spectra_idlist(
        self,
        spectra_file_id: int,
        by: str = "seq_no"
    ) -> dict[int | str, int]:
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
            
        Example:
            >>> # After importing spectra file
            >>> mapping = await project.get_spectra_idlist(file_id, by="scans")
            >>> # mapping = {1234: 5, 1235: 6, ...}  scans -> spectrum_id
            >>> 
            >>> # Use in identification import
            >>> ident_df['spectre_id'] = ident_df['scans'].map(mapping)
            >>> await project.add_identifications_batch(ident_df)
        """
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
        
        rows = await self._fetchall(query, (spectra_file_id,))
        
        # Create mapping: seq_no/scans -> spectrum_id
        return {row[by]: row['id'] for row in rows}
    
'''

print(METHOD_TO_INSERT)
