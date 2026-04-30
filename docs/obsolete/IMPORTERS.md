# Data Importers API Documentation

## Overview

DASMixer provides a flexible system for importing spectral data and peptide identifications from various file formats. The importer system is built on abstract base classes that can be extended to support new formats.

## Architecture

### Base Classes

All importers inherit from `BaseImporter`, which provides common functionality:
- File path validation
- Metadata extraction
- Format validation

Two specialized base classes extend `BaseImporter`:
- **`SpectralDataParser`** - for MS/MS spectra files (MGF, MZML, etc.)
- **`IdentificationParser`** - for peptide identification files (CSV, XLSX, tool outputs)

### Registry System

The `InputTypesRegistry` maintains a central registry of all available parsers. Parsers register themselves at module import time, making them available throughout the application.

```python
from api.inputs.registry import registry

# Get all available parsers
spectra_parsers = registry.get_spectra_parsers()
ident_parsers = registry.get_identification_parsers()

# Get specific parser
MGFParser = registry.get_parser("MGF", "spectra")
```

---

## BaseImporter

Base class for all data importers.

### Constructor

```python
BaseImporter(file_path: Path | str)
```

**Parameters:**
- `file_path`: Path to file to import

**Raises:**
- `FileNotFoundError`: If file doesn't exist
- `ValueError`: If path is not a file

### Methods

#### validate()

```python
async def validate() -> bool
```

Validate file format. Should perform quick checks (magic numbers, headers) without parsing entire file.

**Returns:** `True` if file is valid for this importer

#### get_metadata()

```python
async def get_metadata() -> dict
```

Get file metadata. Base implementation returns empty dict. Override in subclasses for format-specific metadata.

**Returns:** Dict with metadata

---

## SpectralDataParser

Base class for spectral data parsers (MGF, MZML, etc.).

Inherits from `BaseImporter`.

### Methods

#### parse_batch()

```python
async def parse_batch(batch_size: int = 1000) -> AsyncIterator[pd.DataFrame]
```

Parse spectra in batches for memory efficiency.

**Parameters:**
- `batch_size`: Number of spectra per batch

**Yields:** DataFrame batches with columns:
- `seq_no`: int - sequential number in file
- `title`: str - spectrum title
- `scans`: int | None - scan number from instrument
- `charge`: int | None - precursor charge
- `rt`: float | None - retention time (seconds)
- `pepmass`: float - precursor m/z
- `intensity`: float | None - precursor intensity
- `mz_array`: np.ndarray - m/z values of peaks
- `intensity_array`: np.ndarray - intensity values of peaks
- `charge_array`: np.ndarray | None - charge states per peak
- `charge_array_common_value`: int | None - common charge if all peaks same
- `all_params`: dict | None - additional parameters

**Important:** `intensity` and `intensity_array` are different values:
- `intensity`: precursor/parent ion intensity (e.g., from PEPMASS in MGF)
- `intensity_array`: peak intensities in the spectrum

#### get_metadata()

```python
async def get_metadata() -> dict
```

Get file metadata including file system info and format-specific data.

**Returns:** Dict with:
- `file_size`: int - file size in bytes
- `created_at`: str - creation timestamp (ISO)
- `modified_at`: str - modification timestamp (ISO)
- `file_path`: str - absolute path
- Plus any format-specific metadata from `add_metadata()`

#### add_metadata()

```python
async def add_metadata() -> dict
```

Add format-specific metadata. Override in subclasses to provide:
- Format version
- Instrument information
- Acquisition parameters

**Returns:** Dict with additional metadata (empty by default)

**Note:** Do NOT include total spectrum count - determining it often requires reading entire file.

---

## IdentificationParser

Base class for peptide identification parsers.

Parsers are independent of project context - they only parse files and return standard DataFrames. Mapping to spectrum IDs is handled externally via `Project.get_spectra_mapping()`.

Inherits from `BaseImporter`.

### Methods

#### parse_batch()

```python
async def parse_batch(batch_size: int = 1000) -> AsyncIterator[tuple[pd.DataFrame, pd.DataFrame | None]]
```

Parse identifications in batches.

**Parameters:**
- `batch_size`: Number of identifications per batch

**Yields:** Tuple of `(peptide_df, protein_df)`:

**peptide_df** columns:
- `scans`: int | None - scan number for mapping
- `seq_no`: int | None - sequential number for mapping
  - **At least one of scans/seq_no must be present**
- `sequence`: str - peptide sequence with modifications
- `canonical_sequence`: str - sequence without modifications
- `ppm`: float | None - mass error in ppm
- `theor_mass`: float | None - theoretical mass
- `score`: float | None - identification score
- `positional_scores`: dict | None - per-position scores

**protein_df** columns (optional, for files with protein data):
- `scans`: int | None
- `seq_no`: int | None
- `sequence`: str - peptide sequence
- `protein_id`: str - protein identifier
- `protein_sequence`: str | None - full protein sequence
- `gene`: str | None - gene name

**Note:** Protein identifications collected but not processed in current implementation (will be used in Stage 4).

---

## Concrete Parsers

### MGFParser

Parser for MGF (Mascot Generic Format) files.

**Supported formats:** `.mgf`

**Registration name:** `"MGF"`

**Example:**
```python
from api.inputs.spectra.mgf import MGFParser

parser = MGFParser("data.mgf")
if await parser.validate():
    async for batch in parser.parse_batch(batch_size=1000):
        print(f"Parsed {len(batch)} spectra")
        # Process batch...
```

**Features:**
- Extracts scan numbers from TITLE field if not in params
- Handles charge arrays with automatic common value detection
- Parses PEPMASS for both m/z and intensity

---

### Table-Based Parsers

#### TableImporter

Base class for table-based imports (CSV, XLS, XLSX, ODS).

**Attributes:**
- `separator`: CSV field separator (default `','`)
- `encoding`: Text encoding (default `'utf-8'`)
- `ignore_errors`: Encoding error handling (default `'ignore'`)
- `skiprows`: Rows to skip at file start (default `None`)
- `sheets`: Loaded sheets from workbook

**Methods:**

```python
def get_sheet(*, name: str | None = None, no: int | None = None) -> pd.DataFrame
```

Get sheet by name or number.

```python
def _read_table()
```

Read table file into sheets. Supports `.csv`, `.xls`, `.xlsx`, `.ods`.

---

#### SimpleTableImporter

Simple table importer with column remapping using `ColumnRenames`.

**Attributes:**
- `renames`: ColumnRenames configuration
- `peptide_sheet_selector`: Dict for sheet selection (e.g., `{'name': 'Peptides'}`)

**Methods:**

```python
def remap_columns(df: pd.DataFrame) -> pd.DataFrame
```

Remap columns according to ColumnRenames.

```python
def transform_df(df: pd.DataFrame) -> pd.DataFrame
```

Transform DataFrame before remapping. Override for format-specific transformations.

**Example:**
```python
from api.inputs.peptides.table_importer import SimpleTableImporter, ColumnRenames

renames = ColumnRenames(
    scans='Scan Number',
    sequence='Peptide',
    score='Confidence'
)

class MyParser(SimpleTableImporter):
    separator = '\t'
    renames = renames
    
    def transform_df(self, df):
        # Custom transformations
        df['Confidence'] = df['Confidence'] / 100
        return df
```

---

#### ColumnRenames

Configuration for column mapping.

**Attributes:**
- `scans`: Source column for scan numbers
- `seq_no`: Source column for sequential numbers
- `sequence`: Source column for peptide sequence
- `canonical_sequence`: Source column for canonical sequence
- `score`: Source column for score
- `positional_scores`: Source column for positional scores
- `ppm`: Source column for mass error
- `theor_mass`: Source column for theoretical mass

**At least one of `scans` or `seq_no` must be mapped.**

---

### PowerNovo2Importer

Parser for PowerNovo2 de novo sequencing files.

**Format:** CSV with comma separator

**Registration name:** `"PowerNovo2"`

**Column mapping:**
- `SPECTRUM_ID` → `seq_no`
- `PEPTIDE` → `sequence`
- `CANONICAL SEQ.` → `canonical_sequence`
- `PPM DIFFERENCE` → `ppm`
- `SCORE` → `score`
- `POSITIONAL SCORES` → `positional_scores`

**Features:**
- Converts positional scores from space-separated string to list

**Example:**
```python
from api.inputs.peptides.PowerNovo2 import PowerNovo2Importer

parser = PowerNovo2Importer("results.csv")
async for peptide_df, protein_df in parser.parse_batch():
    print(peptide_df[['seq_no', 'sequence', 'score']])
```

---

### MaxQuantEvidenceParser

Parser for MaxQuant evidence.txt files.

**Format:** Tab-separated values

**Registration name:** `"MaxQuant"`

**Column mapping:**
- `MS/MS scan number` → `scans`
- `Modified sequence` → `sequence`
- `Sequence` → `canonical_sequence`
- `Score` → `score`
- `Mass error [ppm]` → `ppm`

**Features:**
- Converts MaxQuant PTM notation to ProForma-like notation
- Replaces `(Oxidation (M))` → `[Oxidation]`
- Removes underscores and standardizes modifications

**Example:**
```python
from api.inputs.peptides.MQ_Evidences import MaxQuantEvidenceParser

parser = MaxQuantEvidenceParser("evidence.txt")
async for peptide_df, protein_df in parser.parse_batch():
    # Sequences now have standardized PTM notation
    print(peptide_df[['scans', 'sequence', 'ppm']])
```

---

## InputTypesRegistry

Central registry for all available parsers.

### Methods

#### add_spectra_parser()

```python
def add_spectra_parser(name: str, parser_class: Type[SpectralDataParser]) -> None
```

Register spectral parser.

**Raises:** `KeyError` if name already registered

#### add_identification_parser()

```python
def add_identification_parser(name: str, parser_class: Type[IdentificationParser]) -> None
```

Register identification parser.

**Raises:** `KeyError` if name already registered

#### get_spectra_parsers()

```python
def get_spectra_parsers() -> dict[str, Type[SpectralDataParser]]
```

Get all registered spectral parsers.

#### get_identification_parsers()

```python
def get_identification_parsers() -> dict[str, Type[IdentificationParser]]
```

Get all registered identification parsers.

#### get_parser()

```python
def get_parser(name: str, parser_type: str) -> Type[BaseImporter]
```

Get parser by name and type.

**Parameters:**
- `name`: Parser name
- `parser_type`: `"spectra"` or `"identification"`

**Raises:**
- `ValueError`: Invalid parser type
- `KeyError`: Parser not found

---

## Creating Custom Parsers

### Custom Spectral Parser

```python
from api.inputs.spectra import SpectralDataParser
from api.inputs.registry import registry
import pandas as pd

class MyFormatParser(SpectralDataParser):
    async def validate(self) -> bool:
        # Check file format
        with open(self.file_path, 'r') as f:
            header = f.readline()
            return header.startswith("MYFORMAT")
    
    async def parse_batch(self, batch_size=1000):
        # Parse file and yield DataFrames
        batch = []
        with open(self.file_path, 'r') as f:
            for line in f:
                # Parse spectrum...
                spectrum_data = {...}
                batch.append(spectrum_data)
                
                if len(batch) >= batch_size:
                    yield pd.DataFrame(batch)
                    batch = []
        
        if batch:
            yield pd.DataFrame(batch)
    
    async def add_metadata(self) -> dict:
        return {'format_version': '1.0'}

# Register parser
registry.add_spectra_parser("MyFormat", MyFormatParser)
```

### Custom Identification Parser

```python
from api.inputs.peptides.table_importer import SimpleTableImporter, ColumnRenames
from api.inputs.registry import registry

renames = ColumnRenames(
    scans='ScanNum',
    sequence='PeptideSeq',
    score='ConfidenceScore'
)

class MyToolParser(SimpleTableImporter):
    separator = '\t'
    renames = renames
    
    def transform_df(self, df):
        # Custom transformations
        df['ConfidenceScore'] = df['ConfidenceScore'].apply(lambda x: x / 100)
        return df

# Register parser
registry.add_identification_parser("MyTool", MyToolParser)
```

---

## Integration with Project

Parsers work with `Project.get_spectra_mapping()` for spectrum ID resolution:

```python
from api import Project
from api.inputs.registry import registry

async def import_identifications(
    project: Project,
    ident_file: str,
    spectra_file_id: int,
    tool_id: int
):
    # Get parser
    ParserClass = registry.get_parser("MaxQuant", "identification")
    parser = ParserClass(ident_file)
    
    # Get spectrum mapping
    mapping = await project.get_spectra_mapping(spectra_file_id)
    
    # Parse and merge
    async for peptide_df, protein_df in parser.parse_batch():
        # Auto-detect merge column
        if 'scans' in peptide_df.columns and peptide_df['scans'].notna().any():
            merge_on = 'scans'
        else:
            merge_on = 'seq_no'
        
        # Merge to get spectrum IDs
        merged = pd.merge(peptide_df, mapping, on=merge_on, how='inner')
        merged = merged.rename(columns={'id': 'spectre_id'})
        
        # Add tool and file IDs
        merged['tool_id'] = tool_id
        merged['ident_file_id'] = ident_file_id
        
        # Save to project
        await project.add_identifications_batch(merged)
```

---

## Best Practices

1. **Validation:** Always validate files before parsing
2. **Batch processing:** Use batch parsing for large files
3. **Error handling:** Parsers should handle malformed data gracefully
4. **Metadata:** Keep `add_metadata()` fast - avoid full file scans
5. **Registration:** Register parsers in module `__init__.py` for automatic availability
6. **Column mapping:** Use `ColumnRenames` for consistent output
7. **Independence:** Parsers should not depend on Project or database context

---

## See Also

- [Project API Documentation](PROJECT_API.md)
- [Spectra Processing](SPECTRA_PROCESSING.md)
- [Technical Architecture](../technical/STAGE3_1_CHANGES.md)
