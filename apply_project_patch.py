"""
Script to apply patch to api/project/project.py
Adds get_spectra_idlist method to Project class
"""

import re

# Read the file
with open('api/project/project.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Method to insert
method_code = '''
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

# Find the place to insert (before "# Identification file operations")
pattern = r'(\n    # Identification file operations\n)'

if re.search(pattern, content):
    # Insert before the comment
    new_content = re.sub(
        pattern,
        method_code + r'\1',
        content
    )
    
    # Write back
    with open('api/project/project.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✓ Successfully added get_spectra_idlist method to Project class")
else:
    print("✗ Could not find insertion point. Please add manually.")
    print("\nInsert this code before '# Identification file operations':")
    print(method_code)
