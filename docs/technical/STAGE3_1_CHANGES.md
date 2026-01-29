# Stage 3.1 Technical Changes

## Overview

Stage 3.1 introduces important architectural improvements to the parser system and Project class based on findings from Stage 2 development. These changes are **not backward compatible** but provide better separation of concerns and more flexible data import workflows.

**Date:** 2026-01-29

**Status:** Completed

---

## Breaking Changes

### 1. SpectralDataParser.get_total_spectra_count() Removed

**Reason:** Determining total spectrum count often requires reading the entire file, which defeats the purpose of having this as separate metadata.

**Migration:**
```python
# OLD (removed):
parser = MGFParser("data.mgf")
count = await parser.get_total_spectra_count()

# NEW:
parser = MGFParser("data.mgf")
count = 0
async for batch in parser.parse_batch():
    count += len(batch)
```

---

### 2. IdentificationParser Constructor Changed

**Old signature:**
```python
def __init__(
    self,
    file_path: str,
    tool_id: int,
    spectra_file_id: int,
    ident_file_id: int,
    project: Project | None = None
)
```

**New signature:**
```python
def __init__(self, file_path: str)
```

**Reason:** Parsers should be independent of project context. Spectrum ID mapping is now handled externally through `Project.get_spectra_mapping()`.

**Migration:**
```python
# OLD:
parser = PowerNovo2Importer(
    "results.csv",
    tool_id=1,
    spectra_file_id=10,
    ident_file_id=15,
    project=project
)

# NEW:
parser = PowerNovo2Importer("results.csv")
# Mapping handled separately - see Section 3
```

---

### 3. IdentificationParser.resolve_spectrum_id() Removed

**Reason:** Spectrum ID resolution now happens externally using `Project.get_spectra_mapping()` and `pd.merge()`.

**Migration:**
```python
# OLD (removed):
async def resolve_spectrum_id(self, row_data: dict) -> int | None:
    if self.id_map is None:
        self.id_map = await self.project.get_spectra(...)
    return self.id_map.query(...).iloc[0]['id']

# NEW - done externally:
mapping = await project.get_spectra_mapping(spectra_file_id)
merged = pd.merge(ident_df, mapping, on='scans', how='inner')
merged = merged.rename(columns={'id': 'spectre_id'})
```

---

### 4. ColumnRenames.spectra_id Removed

**Old:**
```python
@dataclass
class ColumnRenames:
    spectra_id: str | None
    sequence: str
    # ...
```

**New:**
```python
@dataclass
class ColumnRenames:
    scans: str | None = None
    seq_no: str | None = None
    sequence: str
    # ...
```

**Reason:** Parsers return `scans` or `seq_no` for external mapping, not database IDs.

---

### 5. Project.add_spectra_batch() No Longer Auto-Calculates intensity

**Old behavior:**
```python
# Automatically calculated intensity from intensity_array
intensity = row.get('intensity')
if intensity is None and 'intensity_array' in row:
    intensity = float(np.sum(row['intensity_array']))
```

**New behavior:**
```python
# Only use explicitly provided value
intensity = float(row['intensity']) if row.get('intensity') is not None else None
```

**Reason:** `intensity` and `intensity_array` are fundamentally different values:
- `intensity`: Precursor/parent ion intensity (e.g., from PEPMASS in MGF)
- `intensity_array`: Peak intensities in the MS/MS spectrum

These cannot be derived from each other.

**Migration:**
```python
# Ensure intensity is explicitly provided in DataFrame
spectra_data.append({
    'pepmass': 500.0,
    'intensity': 1234.5,  # Precursor intensity - must be explicit
    'mz_array': np.array([...]),
    'intensity_array': np.array([...]),  # Peak intensities
    # ...
})
```

---

## New Features

### 1. Automatic File Metadata

All parsers now automatically provide filesystem metadata:

```python
parser = MGFParser("data.mgf")
metadata = await parser.get_metadata()

# Always available:
print(metadata['file_size'])      # bytes
print(metadata['created_at'])     # ISO timestamp
print(metadata['modified_at'])    # ISO timestamp
print(metadata['file_path'])      # absolute path

# Plus format-specific metadata from add_metadata()
```

**Implementation:**

`SpectralDataParser.get_metadata()` now implemented at base class level:
```python
async def get_metadata(self) -> dict:
    stat = os.stat(self.file_path)
    metadata = {
        'file_size': stat.st_size,
        'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
        'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
        'file_path': str(self.file_path.absolute())
    }
    additional = await self.add_metadata()
    metadata.update(additional)
    return metadata
```

Subclasses override `add_metadata()` (not `get_metadata()`) to add format-specific data.

---

### 2. Flexible Spectrum Mapping

New method `Project.get_spectra_mapping()` provides flexible spectrum ID resolution:

```python
async def get_spectra_mapping(
    self,
    spectra_file_id: int,
    mapping_type: str = 'auto'
) -> pd.DataFrame
```

**mapping_type options:**
- `'auto'`: Return all columns (id, scans, seq_no)
- `'scans'`: Only scans mapping (filters NULL)
- `'seq_no'`: Only sequential number mapping

**Returns DataFrame:**
| Column | Type | Description |
|--------|------|-------------|
| id | int | Spectrum database ID |
| scans | int \| None | Scan number |
| seq_no | int | Sequential number |

**Usage example:**
```python
# Parse identifications
parser = MaxQuantEvidenceParser("evidence.txt")
async for ident_df, protein_df in parser.parse_batch():
    # Get mapping
    mapping = await project.get_spectra_mapping(spectra_file_id)
    
    # Auto-detect merge column
    if 'scans' in ident_df.columns and ident_df['scans'].notna().any():
        merge_on = 'scans'
    else:
        merge_on = 'seq_no'
    
    # Merge to resolve spectrum IDs
    merged = pd.merge(ident_df, mapping, on=merge_on, how='inner')
    merged = merged.rename(columns={'id': 'spectre_id'})
    
    # Add metadata and save
    merged['tool_id'] = tool_id
    merged['ident_file_id'] = ident_file_id
    await project.add_identifications_batch(merged)
```

**Benefits:**
- Parsers are simpler and testable without database
- Flexible mapping strategy (scans vs. seq_no)
- Clear separation of parsing and database operations
- Easy to debug mapping issues

---

### 3. Centralized Parser Registry

New `InputTypesRegistry` class manages all available parsers:

```python
from api.inputs.registry import registry

# Get all parsers
spectra_parsers = registry.get_spectra_parsers()
# {'MGF': <class 'MGFParser'>}

ident_parsers = registry.get_identification_parsers()
# {'PowerNovo2': <class 'PowerNovo2Importer'>, 'MaxQuant': <class 'MaxQuantEvidenceParser'>}

# Get specific parser
MGFParser = registry.get_parser("MGF", "spectra")
parser = MGFParser("data.mgf")
```

**Auto-registration:**

Parsers register themselves when their modules are imported:

```python
# api/inputs/spectra/__init__.py
from .mgf import MGFParser
from ..registry import registry

registry.add_spectra_parser("MGF", MGFParser)

# api/inputs/peptides/__init__.py
from .PowerNovo2 import PowerNovo2Importer
from .MQ_Evidences import MaxQuantEvidenceParser
from ..registry import registry

registry.add_identification_parser("PowerNovo2", PowerNovo2Importer)
registry.add_identification_parser("MaxQuant", MaxQuantEvidenceParser)
```

**Benefits:**
- UI can dynamically list available parsers
- Easy to add new parsers
- Foundation for future plugin system
- No hardcoded parser lists

---

### 4. Protein Identifications Support (Prepared)

`IdentificationParser.parse_batch()` can now return protein identifications:

```python
async def parse_batch(self, batch_size=1000) -> AsyncIterator[tuple[pd.DataFrame, pd.DataFrame | None]]:
    # ...
    yield peptide_df, protein_df  # protein_df can contain protein IDs
```

Current implementation collects but doesn't process protein data (will be used in Stage 4).

---

## Implementation Details

### Updated Parse Workflow

**Old workflow:**
1. Create parser with project context
2. Parser resolves spectrum IDs internally
3. Parser returns data with database IDs

**New workflow:**
1. Create parser (no context needed)
2. Parser returns data with scans/seq_no
3. External code gets mapping from project
4. External code merges and resolves IDs
5. External code saves to project

**Code comparison:**

```python
# OLD (Stage 2):
async def import_identifications_old(project, file_path, tool_id, spectra_file_id):
    # Create identification file record
    ident_file_id = await project.add_identification_file(
        spectra_file_id, tool_id, file_path
    )
    
    # Parser knows about project
    parser = PowerNovo2Importer(
        file_path,
        tool_id=tool_id,
        spectra_file_id=spectra_file_id,
        ident_file_id=ident_file_id,
        project=project
    )
    
    # Parser resolves IDs internally
    async for batch, _ in parser.parse_batch():
        # batch already has spectre_id, tool_id, ident_file_id
        await project.add_identifications_batch(batch)

# NEW (Stage 3.1):
async def import_identifications_new(project, file_path, tool_id, spectra_file_id):
    # Create identification file record
    ident_file_id = await project.add_identification_file(
        spectra_file_id, tool_id, file_path
    )
    
    # Parser is independent
    parser = PowerNovo2Importer(file_path)
    
    # Get mapping once
    mapping = await project.get_spectra_mapping(spectra_file_id)
    
    async for batch, _ in parser.parse_batch():
        # Detect merge column
        merge_on = 'scans' if 'scans' in batch.columns and batch['scans'].notna().any() else 'seq_no'
        
        # Merge to resolve IDs
        merged = pd.merge(batch, mapping, on=merge_on, how='inner')
        merged = merged.rename(columns={'id': 'spectre_id'})
        
        # Add metadata
        merged['tool_id'] = tool_id
        merged['ident_file_id'] = ident_file_id
        
        # Save
        await project.add_identifications_batch(merged)
```

---

### Parser Independence Benefits

**Testability:**
```python
# Can test parser without database
parser = PowerNovo2Importer("test_data.csv")
async for batch, _ in parser.parse_batch():
    assert 'sequence' in batch.columns
    assert 'seq_no' in batch.columns or 'scans' in batch.columns
```

**Reusability:**
```python
# Same parser can be used in different contexts
parser = MGFParser("data.mgf")

# Context 1: Import to project
async for batch in parser.parse_batch():
    await project.add_spectra_batch(file_id, batch)

# Context 2: Quick inspection
async for batch in parser.parse_batch():
    print(f"Batch: {len(batch)} spectra")
    print(batch[['title', 'pepmass', 'charge']])
    break  # Just check first batch
```

---

## Database Schema Updates

### spectre Table

Added `intensity` column:

```sql
CREATE TABLE IF NOT EXISTS spectre (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- ... other columns ...
    pepmass REAL NOT NULL,
    intensity REAL,  -- NEW: precursor intensity
    mz_array BLOB,
    intensity_array BLOB,  -- Different from intensity!
    -- ... other columns ...
);
```

**Distinction:**
- `intensity`: Single value, precursor intensity
- `intensity_array`: Array of values, peak intensities in spectrum

---

## Migration Guide

### For Parser Developers

**If you created custom parsers in Stage 2:**

1. **Remove project dependencies:**
   ```python
   # Remove from __init__:
   # - tool_id
   # - spectra_file_id
   # - ident_file_id
   # - project
   
   def __init__(self, file_path: str):
       super().__init__(file_path)
   ```

2. **Remove resolve_spectrum_id():**
   ```python
   # Delete this method entirely
   ```

3. **Update ColumnRenames:**
   ```python
   # Change:
   # spectra_id='SPECTRUM_ID'
   # To:
   seq_no='SPECTRUM_ID'  # or scans='SCAN_NUM'
   ```

4. **Update parse_batch():**
   ```python
   # Return scans or seq_no in DataFrame
   async def parse_batch(self, batch_size=1000):
       # ... parsing logic ...
       df['seq_no'] = ...  # or df['scans'] = ...
       yield df, None
   ```

5. **Register parser:**
   ```python
   # In module __init__.py:
   from .my_parser import MyParser
   from ..registry import registry
   
   registry.add_identification_parser("MyTool", MyParser)
   ```

### For Application Code

**Update import workflows:**

```python
# Add mapping step
mapping = await project.get_spectra_mapping(spectra_file_id)

# Merge after parsing
async for batch, _ in parser.parse_batch():
    merge_on = 'scans' if 'scans' in batch.columns else 'seq_no'
    merged = pd.merge(batch, mapping, on=merge_on, how='inner')
    merged = merged.rename(columns={'id': 'spectre_id'})
    merged['tool_id'] = tool_id
    merged['ident_file_id'] = ident_file_id
    await project.add_identifications_batch(merged)
```

---

## Future Enhancements

### Plugin System (Stage 5+)

Current registry design supports future plugins:

```python
# Future plugin API
class PluginManager:
    def load_plugin(self, plugin_path: str):
        # Load plugin module
        module = importlib.import_module(plugin_path)
        
        # Plugin registers itself
        # registry.add_spectra_parser(...)
        # registry.add_identification_parser(...)
```

### Advanced Mapping (Future)

`mapping_type='mz-rt'` is reserved for future implementation:

```python
# Future: map by m/z and retention time
mapping = await project.get_spectra_mapping(
    spectra_file_id,
    mapping_type='mz-rt'
)
# Would return mapping based on precursor m/z and RT matching
```

---

## Testing Notes

**What was tested:**
- All parsers load and register correctly
- Metadata extraction works
- Column remapping functions correctly
- Project mapping returns correct DataFrames

**What needs testing in Stage 3.2:**
- Full import workflow with real data
- Mapping edge cases (missing scans, duplicate seq_no)
- Error handling for malformed files
- Performance with large files

---

## Documentation Updates

### New Documentation
- `docs/api/IMPORTERS.md` - Complete importer API reference
- `docs/api/SPECTRA_PROCESSING.md` - Ion matching and visualization
- `docs/technical/STAGE3_1_CHANGES.md` - This document

### Updated Documentation
- `docs/api/PROJECT_API.md` - Added `get_spectra_mapping()`, clarified intensity fields

---

## Lessons Learned

### Good Decisions

1. **Parser independence** - Much easier to test and reuse
2. **Centralized mapping** - Single point of truth for ID resolution
3. **Registry pattern** - Clean, extensible architecture
4. **Metadata at base level** - Consistent across all parsers

### Areas for Improvement

1. **Documentation** - Should have been written alongside code
2. **Testing** - Need integration tests with real data
3. **Error messages** - Could be more helpful for mapping failures

---

## See Also

- [IMPORTERS.md](../api/IMPORTERS.md) - Complete importer documentation
- [SPECTRA_PROCESSING.md](../api/SPECTRA_PROCESSING.md) - Ion matching documentation
- [PROJECT_API.md](../api/PROJECT_API.md) - Project class documentation
- [MASTER_SPEC.md](../../MASTER_SPEC.md) - Overall project specification
