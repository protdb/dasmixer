# Project API Documentation

## Overview

The `Project` class is the core component of DASMixer for managing proteomics data. It provides an asynchronous interface to work with SQLite-based project files containing spectra, identifications, proteins, and analysis results.

## Quick Start

```python
import asyncio
from api import Project

async def main():
    # Create or open a project
    async with Project("my_project.dasmix") as project:
        # Add a comparison group
        control = await project.add_subset("Control", color="#FF0000")
        
        # Add a tool
        plgs = await project.add_tool("PLGS", "library")
        
        # Add a sample
        sample = await project.add_sample("Sample_01", control.id)
        
        print(f"Project created with {len(await project.get_samples())} samples")

asyncio.run(main())
```

## Class: Project

### Constructor

```python
Project(path: Path | str | None = None, create_if_not_exists: bool = True)
```

**Parameters:**
- `path`: Path to project file (.dasmix). If `None`, creates an in-memory project.
- `create_if_not_exists`: If `True` and path doesn't exist, creates new project. If `False` and path doesn't exist, raises `FileNotFoundError`.

**Examples:**

```python
# Create new project
project = Project("new_project.dasmix")
await project.initialize()

# Open existing project (fail if doesn't exist)
project = Project("existing.dasmix", create_if_not_exists=False)
await project.initialize()

# In-memory project (for testing)
project = Project()
await project.initialize()

# Context manager (recommended)
async with Project("my_project.dasmix") as project:
    # Work with project
    pass  # Automatically saves and closes
```

---

## Project Management

### initialize()

```python
async def initialize() -> None
```

Initialize database connection and create schema if needed. Must be called before using the project (unless using context manager).

**Example:**
```python
project = Project("my_project.dasmix")
await project.initialize()
# ... work with project ...
await project.close()
```

### close()

```python
async def close() -> None
```

Close database connection and commit any pending changes.

### save()

```python
async def save() -> None
```

Explicitly save current state (commit transaction). Automatically called by most modification methods.

### save_as()

```python
async def save_as(path: Path | str) -> None
```

Save project to a new file.

**Parameters:**
- `path`: New file path

**Example:**
```python
await project.save_as("backup_project.dasmix")
```

### get_metadata()

```python
async def get_metadata() -> dict
```

Get project metadata including creation date, version, etc.

**Returns:**
Dictionary with keys: `version`, `created_at`, `modified_at`

**Example:**
```python
metadata = await project.get_metadata()
print(f"Project created: {metadata['created_at']}")
print(f"Version: {metadata['version']}")
```

### Settings

```python
async def set_setting(key: str, value: str) -> None
async def get_setting(key: str, default: str | None = None) -> str | None
```

Store and retrieve project-specific settings.

**Example:**
```python
await project.set_setting("last_export_path", "/data/exports")
path = await project.get_setting("last_export_path")
```

---

## Subsets (Comparison Groups)

### add_subset()

```python
async def add_subset(
    name: str,
    details: str | None = None,
    display_color: str | None = None
) -> Subset
```

Add a new comparison group.

**Parameters:**
- `name`: Unique subset name
- `details`: Optional description
- `display_color`: Hex color for visualization (e.g., "#FF0000")

**Returns:**
Created `Subset` object

**Raises:**
- `ValueError`: If subset with this name already exists

**Example:**
```python
control = await project.add_subset(
    "Control",
    details="Control group samples",
    display_color="#3498db"
)
treatment = await project.add_subset("Treatment", color="#e74c3c")
```

### get_subsets()

```python
async def get_subsets() -> list[Subset]
```

Get all subsets ordered by name.

**Example:**
```python
subsets = await project.get_subsets()
for subset in subsets:
    print(f"{subset.name}: {subset.details}")
```

### get_subset()

```python
async def get_subset(subset_id: int) -> Subset | None
```

Get subset by ID.

**Returns:**
`Subset` object or `None` if not found

### update_subset()

```python
async def update_subset(subset: Subset) -> None
```

Update existing subset.

**Example:**
```python
subset = await project.get_subset(1)
subset.details = "Updated description"
await project.update_subset(subset)
```

### delete_subset()

```python
async def delete_subset(subset_id: int) -> None
```

Delete subset.

**Raises:**
- `ValueError`: If subset has associated samples

---

## Tools (Identification Tools)

### add_tool()

```python
async def add_tool(
    name: str,
    type: str,
    settings: dict | None = None,
    display_color: str | None = None
) -> Tool
```

Add a new identification tool.

**Parameters:**
- `name`: Unique tool name
- `type`: Tool type ("library" or "denovo")
- `settings`: Optional tool settings as dictionary
- `display_color`: Hex color for visualization

**Returns:**
Created `Tool` object

**Example:**
```python
plgs = await project.add_tool(
    "PLGS",
    "library",
    settings={"version": "3.0.2", "fdr": 0.01}
)

powernovo = await project.add_tool(
    "PowerNovo2",
    "denovo",
    settings={"model": "HCD", "beam_size": 5}
)
```

### get_tools()

```python
async def get_tools() -> list[Tool]
```

Get all tools ordered by name.

### get_tool()

```python
async def get_tool(tool_id: int) -> Tool | None
```

Get tool by ID.

### update_tool()

```python
async def update_tool(tool: Tool) -> None
```

Update existing tool.

### delete_tool()

```python
async def delete_tool(tool_id: int) -> None
```

Delete tool (if no identifications associated).

**Raises:**
- `ValueError`: If tool has associated identifications

---

## Samples

### add_sample()

```python
async def add_sample(
    name: str,
    subset_id: int | None = None,
    additions: dict | None = None
) -> Sample
```

Add a new sample.

**Parameters:**
- `name`: Unique sample name
- `subset_id`: FK to subset (comparison group)
- `additions`: Additional metadata (e.g., `{"albumin": 45.5, "total_protein": 7.2}`)

**Returns:**
Created `Sample` object

**Example:**
```python
sample1 = await project.add_sample(
    "Patient_001",
    subset_id=control.id,
    additions={"albumin": 45.5, "age": 35, "gender": "M"}
)
```

### get_samples()

```python
async def get_samples(subset_id: int | None = None) -> list[Sample]
```

Get samples, optionally filtered by subset.

**Parameters:**
- `subset_id`: If provided, return only samples from this subset

**Example:**
```python
# All samples
all_samples = await project.get_samples()

# Samples in specific subset
control_samples = await project.get_samples(subset_id=control.id)

for sample in all_samples:
    print(f"{sample.name} - Subset: {sample.subset_name}, Files: {sample.spectra_files_count}")
```

### get_sample()

```python
async def get_sample(sample_id: int) -> Sample | None
```

Get sample by ID.

### get_sample_by_name()

```python
async def get_sample_by_name(name: str) -> Sample | None
```

Get sample by name.

**Example:**
```python
sample = await project.get_sample_by_name("Patient_001")
if sample:
    print(f"Sample ID: {sample.id}")
```

### update_sample()

```python
async def update_sample(sample: Sample) -> None
```

Update existing sample.

### delete_sample()

```python
async def delete_sample(sample_id: int) -> None
```

Delete sample (cascades to spectra files).

---

## Spectra Files

### add_spectra_file()

```python
async def add_spectra_file(
    sample_id: int,
    format: str,
    path: str
) -> int
```

Add spectra file record.

**Parameters:**
- `sample_id`: FK to sample
- `format`: File format ("MGF", "MZML", etc.)
- `path`: Original file path

**Returns:**
Created spectra_file ID

**Example:**
```python
file_id = await project.add_spectra_file(
    sample1.id,
    "MGF",
    "/data/spectra/sample_001.mgf"
)
```

### get_spectra_files()

```python
async def get_spectra_files(sample_id: int | None = None) -> pd.DataFrame
```

Get spectra files as DataFrame.

**Returns:**
DataFrame with columns: `id`, `sample_id`, `format`, `path`, `sample_name`

**Example:**
```python
files = await project.get_spectra_files(sample_id=sample1.id)
print(files[['id', 'format', 'path']])
```

---

## Spectra (Batch Processing)

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

```python
async def add_spectra_batch(
    spectra_file_id: int,
    spectra_df: pd.DataFrame
) -> None
```

Add batch of spectra to database.

**Parameters:**
- `spectra_file_id`: FK to spectra_file
- `spectra_df`: DataFrame with columns:
  - `seq_no`: int - Sequential number in file
  - `title`: str - Spectrum title
  - `scans`: int | None - Scan number(s)
  - `charge`: int | None - Precursor charge
  - `rt`: float | None - Retention time
  - `pepmass`: float - Precursor m/z
  - `intensity`: float | None - precursor intensity (e.g., from PEPMASS in MGF)
  - `mz_array`: np.ndarray - M/Z values
  - `intensity_array`: np.ndarray - Intensity values
  - `charge_array`: np.ndarray | None - Charge states for each peak
  - `charge_array_common_value`: int | None - Common charge if all peaks have same charge
  - `all_params`: dict | None - Additional parameters

**Note:**
`intensity` and `intensity_array` are different values that cannot be derived from each other:
- `intensity`: Precursor/parent ion intensity (single value, e.g., from PEPMASS in MGF)
- `intensity_array`: Peak intensities in the MS/MS spectrum (array of values)

`intensity` must be explicitly provided if needed; it is NOT automatically calculated from `intensity_array`.

**Example:**
```python
import numpy as np
import pandas as pd

spectra_data = []
for i in range(1000):
    spectra_data.append({
        'seq_no': i + 1,
        'title': f'Scan_{i+1}',
        'scans': i + 1,
        'charge': 2,
        'rt': 10.0 + i * 0.5,
        'pepmass': 500.0 + i * 0.1,
        'mz_array': np.random.rand(100) * 1000,
        'intensity_array': np.random.rand(100) * 10000,
        'charge_array_common_value': 1
    })

df = pd.DataFrame(spectra_data)
await project.add_spectra_batch(file_id, df)
```

### get_spectra()

```python
async def get_spectra(
    spectra_file_id: int | None = None,
    sample_id: int | None = None,
    limit: int | None = None,
    offset: int = 0
) -> pd.DataFrame
```

Get spectra as DataFrame (without arrays for efficiency).

**Parameters:**
- `spectra_file_id`: Filter by spectra file
- `sample_id`: Filter by sample
- `limit`: Maximum number of rows to return
- `offset`: Offset for pagination

**Returns:**
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

**Example:**
```python
# Get first 100 spectra from a sample
spectra = await project.get_spectra(sample_id=sample1.id, limit=100)

# Pagination
page1 = await project.get_spectra(sample_id=sample1.id, limit=50, offset=0)
page2 = await project.get_spectra(sample_id=sample1.id, limit=50, offset=50)

print(f"Total: {len(spectra)} spectra")
print(spectra[['id', 'title', 'pepmass', 'rt', 'charge']])
```

### get_spectrum_full()

```python
async def get_spectrum_full(spectrum_id: int) -> dict
```

Get full spectrum data including arrays.

**Returns:**
Dictionary with all fields including decompressed numpy arrays

**Example:**
```python
spectrum = await project.get_spectrum_full(123)

print(f"Title: {spectrum['title']}")
print(f"Precursor m/z: {spectrum['pepmass']}")
print(f"Number of peaks: {len(spectrum['mz_array'])}")
print(f"M/Z range: {spectrum['mz_array'].min():.2f} - {spectrum['mz_array'].max():.2f}")

# Plot spectrum
import matplotlib.pyplot as plt
plt.stem(spectrum['mz_array'], spectrum['intensity_array'])
plt.xlabel('m/z')
plt.ylabel('Intensity')
plt.show()
```

### get_spectra_mapping()

```python
async def get_spectra_mapping(
    spectra_file_id: int,
    mapping_type: str = 'auto'
) -> pd.DataFrame
```

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
```python
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
```

**Usage with different mapping types:**
```python
# Auto mode - returns all columns
mapping_auto = await project.get_spectra_mapping(file_id, 'auto')
# Result: id, scans, seq_no columns

# Scans only - filters NULL scans
mapping_scans = await project.get_spectra_mapping(file_id, 'scans')
# Result: id, scans columns (no NULL scans)

# Sequential only
mapping_seq = await project.get_spectra_mapping(file_id, 'seq_no')
# Result: id, seq_no columns
```

**See also:**
- [Data Importers Documentation](IMPORTERS.md#integration-with-project)
- [Stage 3.1 Changes](../technical/STAGE3_1_CHANGES.md#new-features)
```

---

## Identification Files

### add_identification_file()

```python
async def add_identification_file(
    spectra_file_id: int,
    tool_id: int,
    file_path: str
) -> int
```

Add identification file record.

**Returns:**
Created identification_file ID

**Example:**
```python
ident_file_id = await project.add_identification_file(
    spectra_file_id=file_id,
    tool_id=plgs.id,
    file_path="/data/identifications/sample_001_plgs.csv"
)
```

### get_identification_files()

```python
async def get_identification_files(
    spectra_file_id: int | None = None,
    tool_id: int | None = None
) -> pd.DataFrame
```

Get identification files as DataFrame.

---

## Identifications (Batch Processing)

### add_identifications_batch()

```python
async def add_identifications_batch(identifications_df: pd.DataFrame) -> None
```

Add batch of identifications.

**Parameters:**
- `identifications_df`: DataFrame with columns:
  - `spectre_id`: int - FK to spectrum
  - `tool_id`: int - FK to tool
  - `ident_file_id`: int - FK to identification file
  - `is_preferred`: bool - Whether this is the preferred identification
  - `sequence`: str - Peptide sequence with modifications
  - `canonical_sequence`: str - Canonical sequence without modifications
  - `ppm`: float | None - Mass error in ppm
  - `theor_mass`: float | None - Theoretical mass
  - `score`: float | None - Identification score
  - `positional_scores`: dict | None - Per-position scores

**Example:**
```python
# Get spectra
spectra = await project.get_spectra(sample_id=sample1.id)

# Create identifications
ident_data = []
for _, spectrum in spectra.iterrows():
    ident_data.append({
        'spectre_id': spectrum['id'],
        'tool_id': plgs.id,
        'ident_file_id': ident_file_id,
        'is_preferred': True,
        'sequence': 'PEPTIDEK',
        'canonical_sequence': 'PEPTIDEK',
        'ppm': 5.2,
        'theor_mass': 500.3,
        'score': 95.0,
        'positional_scores': {'pos_1': 0.9, 'pos_2': 0.95}
    })

ident_df = pd.DataFrame(ident_data)
await project.add_identifications_batch(ident_df)
```

### get_identifications()

```python
async def get_identifications(
    spectra_file_id: int | None = None,
    tool_id: int | None = None,
    sample_id: int | None = None
) -> pd.DataFrame
```

Get identifications as DataFrame with joined metadata.

**Returns:**
DataFrame with columns including spectrum and tool information

**Example:**
```python
# Get all identifications from PLGS
plgs_idents = await project.get_identifications(tool_id=plgs.id)

# Get identifications for specific sample
sample_idents = await project.get_identifications(sample_id=sample1.id)

print(sample_idents[['sequence', 'ppm', 'score', 'tool_name']])
```

---

## Proteins

### add_protein()

```python
async def add_protein(protein: Protein) -> None
```

Add or update protein.

**Example:**
```python
from api.project.dataclasses import Protein

protein = Protein(
    id="P12345",
    is_uniprot=True,
    gene="ALBU",
    sequence="MKWVTFISLLFLFSSAYS..."
)
await project.add_protein(protein)
```

### add_proteins_batch()

```python
async def add_proteins_batch(proteins_df: pd.DataFrame) -> None
```

Add batch of proteins from DataFrame.

**Example:**
```python
proteins_df = pd.DataFrame([
    {'id': 'P12345', 'is_uniprot': True, 'gene': 'ALBU', 'sequence': 'MKWVT...'},
    {'id': 'P67890', 'is_uniprot': True, 'gene': 'HBB', 'sequence': 'MVHLT...'}
])
await project.add_proteins_batch(proteins_df)
```

### get_protein()

```python
async def get_protein(protein_id: str) -> Protein | None
```

Get protein by ID.

### get_proteins()

```python
async def get_proteins(is_uniprot: bool | None = None) -> list[Protein]
```

Get proteins, optionally filtered by UniProt status.

**Example:**
```python
# All proteins
all_proteins = await project.get_proteins()

# Only UniProt proteins
uniprot_proteins = await project.get_proteins(is_uniprot=True)

for protein in all_proteins:
    print(f"{protein.id} - Gene: {protein.gene}, UniProt: {protein.is_uniprot}")
```

---

## Low-Level SQL API

### execute_query()

```python
async def execute_query(
    query: str,
    params: tuple | dict | None = None
) -> list[dict]
```

Execute raw SQL query for complex operations.

**Returns:**
List of rows as dictionaries

**Example:**
```python
# Custom query
results = await project.execute_query(
    """
    SELECT s.name, COUNT(sf.id) as file_count
    FROM sample s
    LEFT JOIN spectre_file sf ON s.id = sf.sample_id
    GROUP BY s.id
    """,
)

for row in results:
    print(f"{row['name']}: {row['file_count']} files")
```

### execute_query_df()

```python
async def execute_query_df(
    query: str,
    params: tuple | dict | None = None
) -> pd.DataFrame
```

Execute query and return as DataFrame.

**Example:**
```python
df = await project.execute_query_df(
    """
    SELECT i.sequence, i.score, s.pepmass, sam.name as sample_name
    FROM identification i
    JOIN spectre s ON i.spectre_id = s.id
    JOIN spectre_file sf ON s.spectre_file_id = sf.id
    JOIN sample sam ON sf.sample_id = sam.id
    WHERE i.score > ?
    """,
    (90.0,)
)

print(df.describe())
```

---

## Complete Workflow Example

```python
import asyncio
import numpy as np
import pandas as pd
from api import Project

async def complete_workflow():
    """Complete workflow example."""
    
    async with Project("proteomics_study.dasmix") as project:
        # 1. Setup project structure
        control = await project.add_subset("Control", color="#3498db")
        treatment = await project.add_subset("Treatment", color="#e74c3c")
        
        plgs = await project.add_tool("PLGS", "library")
        denovo = await project.add_tool("PowerNovo2", "denovo")
        
        # 2. Add samples
        samples = []
        for i in range(1, 4):
            subset = control if i <= 2 else treatment
            sample = await project.add_sample(
                f"Sample_{i:02d}",
                subset_id=subset.id,
                additions={"albumin": 40.0 + i}
            )
            samples.append(sample)
        
        # 3. Import spectra (simplified)
        for sample in samples:
            file_id = await project.add_spectra_file(
                sample.id,
                "MGF",
                f"/data/{sample.name}.mgf"
            )
            
            # Create dummy spectra
            spectra_data = []
            for j in range(100):
                spectra_data.append({
                    'seq_no': j + 1,
                    'title': f'Scan_{j+1}',
                    'pepmass': 500.0 + j,
                    'rt': 10.0 + j * 0.5,
                    'charge': 2,
                    'mz_array': np.random.rand(50) * 1000,
                    'intensity_array': np.random.rand(50) * 10000,
                    'charge_array_common_value': 1
                })
            
            await project.add_spectra_batch(file_id, pd.DataFrame(spectra_data))
        
        # 4. Query and analyze
        all_samples = await project.get_samples()
        print(f"Total samples: {len(all_samples)}")
        
        for sample in all_samples:
            spectra = await project.get_spectra(sample_id=sample.id)
            print(f"{sample.name}: {len(spectra)} spectra")
        
        # 5. Export statistics
        stats = await project.execute_query_df(
            """
            SELECT 
                sam.name,
                sub.name as subset,
                COUNT(DISTINCT sf.id) as files,
                COUNT(s.id) as spectra
            FROM sample sam
            LEFT JOIN subset sub ON sam.subset_id = sub.id
            LEFT JOIN spectre_file sf ON sam.id = sf.sample_id
            LEFT JOIN spectre s ON sf.id = s.spectre_file_id
            GROUP BY sam.id
            """
        )
        
        print("\nProject Statistics:")
        print(stats)

asyncio.run(complete_workflow())
```

---

## Best Practices

### 1. Always Use Context Manager

```python
# ✅ Good - automatic cleanup
async with Project("my_project.dasmix") as project:
    await project.add_sample(...)

# ❌ Bad - manual cleanup required
project = Project("my_project.dasmix")
await project.initialize()
await project.add_sample(...)
await project.close()  # Easy to forget!
```

### 2. Batch Processing for Large Datasets

```python
# ✅ Good - efficient batch insert
await project.add_spectra_batch(file_id, large_df)

# ❌ Bad - individual inserts (slow)
for _, row in large_df.iterrows():
    # Don't do this in a loop!
    pass
```

### 3. Use Pagination for Large Queries

```python
# ✅ Good - paginated access
page_size = 1000
offset = 0
while True:
    spectra = await project.get_spectra(limit=page_size, offset=offset)
    if spectra.empty:
        break
    process_spectra(spectra)
    offset += page_size
```

### 4. Explicit Saves Only When Needed

```python
# Most methods auto-save
await project.add_sample(...)  # Automatically commits

# Manual save only for custom SQL
await project.execute_query("UPDATE ...")
await project.save()  # Explicit commit needed
```

---

## Error Handling

```python
from pathlib import Path

async def safe_project_operations():
    try:
        # This will fail if file doesn't exist
        project = Project("nonexistent.dasmix", create_if_not_exists=False)
        await project.initialize()
    except FileNotFoundError as e:
        print(f"Project file not found: {e}")
    
    async with Project("my_project.dasmix") as project:
        try:
            # This will fail if name already exists
            await project.add_subset("Duplicate")
            await project.add_subset("Duplicate")
        except ValueError as e:
            print(f"Subset already exists: {e}")
        
        try:
            # This will fail if subset has samples
            await project.delete_subset(1)
        except ValueError as e:
            print(f"Cannot delete: {e}")
```

---

## Performance Considerations

### Array Compression

Arrays are automatically compressed using `numpy.savez_compressed`:
- Significantly reduces database size
- Decompression only on explicit request via `get_spectrum_full()`
- Use `get_spectra()` for metadata queries (faster, no decompression)

### Indexing

All foreign keys and frequently queried fields are indexed:
- Fast JOIN operations
- Efficient filtering by sample, tool, subset
- Quick lookups by name or ID

### Transaction Management

- Each modification method commits automatically
- Use `execute_query()` for batch SQL operations
- Manual `save()` after custom operations

---

## See Also

- [Dataclasses Documentation](DATACLASSES.md)
- [Importer Base Classes](IMPORTERS.md)
- [Report Base Classes](REPORTS.md)
- [Database Schema](../project/spec/DATABASE_SCHEMA.md)
