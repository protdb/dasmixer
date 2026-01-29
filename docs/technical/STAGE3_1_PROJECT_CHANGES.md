# Changes to api/project/project.py for Stage 3.1

## 1. Fix intensity calculation in add_spectra_batch()

### Location
Line ~560-565 in method `add_spectra_batch()`

### Change
Replace:
```python
            # Calculate intensity if not provided
            intensity = row.get('intensity')
            if intensity is None and 'intensity_array' in row and row['intensity_array'] is not None:
                intensity = float(np.sum(row['intensity_array']))
```

With:
```python
            # Get intensity from explicit value only - DO NOT calculate from intensity_array
            # intensity and intensity_array are different values that cannot be derived from each other
            intensity = float(row['intensity']) if row.get('intensity') is not None else None
```

---

## 2. Add get_spectra_mapping() method

### Location
Insert after `get_spectra()` method (around line ~610)

### New method
```python
    async def get_spectra_mapping(
        self,
        spectra_file_id: int,
        mapping_type: Literal['auto', 'seq_no', 'scans'] = 'auto'
    ) -> pd.DataFrame:
        """
        Get spectra mapping for identification file processing.
        
        Returns DataFrame that can be merged with identification results
        to resolve spectrum IDs.
        
        Args:
            spectra_file_id: FK to spectra file
            mapping_type: How to map identifications to spectra:
                - 'auto': return all columns, let caller decide
                - 'seq_no': map by sequential number in file
                - 'scans': map by scan number (filters out NULL scans)
                
        Returns:
            DataFrame with columns:
                - id: int - spectrum database ID
                - scans: int | None - scan number (if available and not filtered)
                - seq_no: int - sequential number in file
                
        Usage:
            # Get mapping
            mapping = await project.get_spectra_mapping(spectra_file_id)
            
            # Merge with parsed identifications (auto-detect merge column)
            if 'scans' in ident_df.columns and ident_df['scans'].notna().any():
                merge_on = 'scans'
            else:
                merge_on = 'seq_no'
            merged = pd.merge(ident_df, mapping, on=merge_on, how='inner')
            
            # Now 'id' column in merged contains spectrum database IDs
            # Rename to 'spectre_id' for database insertion
            merged = merged.rename(columns={'id': 'spectre_id'})
            
        Raises:
            ValueError: If mapping_type='scans' but no scans available
        """
        from typing import Literal  # Import at method level if not at top
        
        query = """
            SELECT id, scans, seq_no
            FROM spectre
            WHERE spectre_file_id = ?
            ORDER BY seq_no
        """
        
        df = await self.execute_query_df(query, (spectra_file_id,))
        
        if df.empty:
            raise ValueError(f"No spectra found for spectra_file_id={spectra_file_id}")
        
        if mapping_type == 'auto':
            # Return full mapping, caller decides how to merge
            return df
        elif mapping_type == 'seq_no':
            # Only seq_no mapping
            return df[['id', 'seq_no']]
        elif mapping_type == 'scans':
            # Only scans mapping, filter out NULL scans
            result = df[df['scans'].notna()][['id', 'scans']]
            if result.empty:
                raise ValueError(
                    f"No scans available for spectra_file_id={spectra_file_id}. "
                    "Use mapping_type='seq_no' instead."
                )
            return result
        else:
            raise ValueError(
                f"Invalid mapping_type: {mapping_type}. "
                "Must be 'auto', 'seq_no', or 'scans'"
            )
```

### Import addition
Add at top of file after existing imports:
```python
from typing import Literal  # If not already imported
```
