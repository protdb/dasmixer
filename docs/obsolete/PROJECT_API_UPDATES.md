# Updates to PROJECT_API.md for Stage 3.1

## Location 1: add_spectra_batch() section

### Find this section (around line 450-490):

```markdown
### add_spectra_batch()

...
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
```

### Add after `pepmass` line:

```markdown
    - intensity: float | None - precursor intensity (e.g., from PEPMASS in MGF)
```

### Add new "Note" section before the Example:

```markdown
**Note:**
`intensity` and `intensity_array` are different values that cannot be derived from each other:
- `intensity`: Precursor/parent ion intensity (single value, e.g., from PEPMASS in MGF)
- `intensity_array`: Peak intensities in the MS/MS spectrum (array of values)

`intensity` must be explicitly provided if needed; it is NOT automatically calculated from `intensity_array`.
```

---

## Location 2: After get_spectrum_full() section

### Add new section:

```markdown
### get_spectra_mapping()

\```python
async def get_spectra_mapping(
    spectra_file_id: int,
    mapping_type: str = 'auto'
) -> pd.DataFrame
\```

Get spectra mapping for identification file processing.

Returns DataFrame that can be merged with identification results
to resolve spectrum IDs.

**Parameters:**
- `spectra_file_id`: FK to spectra file
- `mapping_type`: How to map identifications to spectra:
  - `'auto'`: Return all columns (id, scans, seq_no), let caller decide
  - `'seq_no'`: Map by sequential number in file
  - `'scans'`: Map by scan number (filters out NULL scans)

**Returns:**
DataFrame with columns:
- `id`: int - spectrum database ID
- `scans`: int | None - scan number (if available and not filtered)
- `seq_no`: int - sequential number in file

**Raises:**
- `ValueError`: If no spectra found or if mapping_type='scans' but no scans available

**Example:**
\```python
from api.inputs.peptides.MQ_Evidences import MaxQuantEvidenceParser

# Parse identifications
parser = MaxQuantEvidenceParser("evidence.txt")

# Get mapping
mapping = await project.get_spectra_mapping(spectra_file_id)

# Process batches
async for ident_df, protein_df in parser.parse_batch():
    # Auto-detect merge column
    if 'scans' in ident_df.columns and ident_df['scans'].notna().any():
        merge_on = 'scans'
    else:
        merge_on = 'seq_no'
    
    # Merge to resolve spectrum IDs
    merged = pd.merge(ident_df, mapping, on=merge_on, how='inner')
    merged = merged.rename(columns={'id': 'spectre_id'})
    
    # Add metadata
    merged['tool_id'] = tool_id
    merged['ident_file_id'] = ident_file_id
    
    # Save to project
    await project.add_identifications_batch(merged)
\```

**Usage with different mapping types:**
\```python
# Auto mode - returns all columns
mapping_auto = await project.get_spectra_mapping(file_id, 'auto')
# Result: id, scans, seq_no columns

# Scans only - filters NULL scans
mapping_scans = await project.get_spectra_mapping(file_id, 'scans')
# Result: id, scans columns (no NULL scans)

# Sequential only
mapping_seq = await project.get_spectra_mapping(file_id, 'seq_no')
# Result: id, seq_no columns
\```

**See also:**
- [Data Importers Documentation](IMPORTERS.md#integration-with-project)
- [Stage 3.1 Changes](../technical/STAGE3_1_CHANGES.md#new-features)
```

---

## Location 3: get_spectra() section

### Find the "Returns" description:

```markdown
**Returns:**
DataFrame with metadata only (no mz/intensity arrays)
```

### Replace with:

```markdown
**Returns:**
DataFrame with columns:
- `id`: int
- `spectre_file_id`: int
- `seq_no`: int
- `title`: str
- `scans`: int | None
- `charge`: int | None
- `rt`: float | None
- `pepmass`: float
- `intensity`: float | None - precursor intensity
- `charge_array_common_value`: int | None
- `sample_id`: int
- `sample_name`: str

Note: mz_array and intensity_array are NOT included for efficiency.
Use `get_spectrum_full()` to retrieve arrays.
```

---

## Apply these updates to docs/api/PROJECT_API.md

The developer should manually apply these changes to maintain consistency with the existing documentation style.
