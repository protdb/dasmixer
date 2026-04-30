# Base Classes Technical Documentation

## Overview

DASMixer provides abstract base classes for extending functionality with custom importers and reports. This document describes the architecture and implementation requirements for each base class.

---

## Table of Contents

1. [Importers](#importers)
   - [BaseImporter](#baseimporter)
   - [SpectralDataParser](#spectraldataparser)
   - [IdentificationParser](#identificationparser)
2. [Reports](#reports)
   - [BaseReport](#basereport)
   - [ReportParameters](#reportparameters)
3. [Implementation Examples](#implementation-examples)

---

## Importers

### BaseImporter

**Location:** `api/inputs/base.py`

Base class for all data importers with file validation and metadata extraction.

#### Class Definition

```python
from abc import ABC, abstractmethod
from pathlib import Path

class BaseImporter(ABC):
    """Base class for all data importers."""
    
    def __init__(self, file_path: Path | str):
        """Initialize importer with file validation."""
        self.file_path = Path(file_path)
        self._validate_file()
    
    def _validate_file(self) -> None:
        """Validate that file exists and is readable."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")
        if not self.file_path.is_file():
            raise ValueError(f"Not a file: {self.file_path}")
    
    @abstractmethod
    async def validate(self) -> bool:
        """
        Validate file format.
        
        Returns:
            True if file is valid for this importer
        """
        pass
    
    @abstractmethod
    async def get_metadata(self) -> dict:
        """
        Get file metadata without parsing all data.
        
        Returns:
            dict with metadata (record count, format version, etc.)
        """
        pass
```

#### Implementation Requirements

1. **Constructor:**
   - Call `super().__init__(file_path)` to initialize and validate file
   - Store any parser-specific configuration

2. **validate() method:**
   - Check file format (magic bytes, headers, etc.)
   - Return `True` if file can be parsed by this importer
   - Should be fast (no full file parsing)

3. **get_metadata() method:**
   - Extract metadata without full parsing
   - Return dictionary with keys:
     - `record_count` or `spectra_count`: Number of records
     - `format_version`: Format version if applicable
     - `created_date`: File creation date if available
     - Any other relevant metadata

#### Example: Simple CSV Importer

```python
import aiofiles
import csv
from .base import BaseImporter

class CSVImporter(BaseImporter):
    """Import data from CSV files."""
    
    async def validate(self) -> bool:
        """Check if file is valid CSV."""
        try:
            async with aiofiles.open(self.file_path, 'r') as f:
                first_line = await f.readline()
                # Check if first line looks like CSV
                return ',' in first_line or '\t' in first_line
        except Exception:
            return False
    
    async def get_metadata(self) -> dict:
        """Get CSV metadata."""
        async with aiofiles.open(self.file_path, 'r') as f:
            # Count lines
            line_count = sum(1 async for _ in f)
        
        return {
            'record_count': line_count - 1,  # Exclude header
            'format': 'CSV',
            'file_size': self.file_path.stat().st_size
        }
```

---

### SpectralDataParser

**Location:** `api/inputs/spectra/base.py`

Base class for parsing spectral data files (MGF, MZML, etc.) with batch processing support.

#### Class Definition

```python
from abc import abstractmethod
from typing import AsyncIterator
import pandas as pd
from ..base import BaseImporter

class SpectralDataParser(BaseImporter):
    """Base class for spectral data parsers (MGF, MZML, etc.)."""
    
    @abstractmethod
    async def parse_batch(
        self,
        batch_size: int = 1000
    ) -> AsyncIterator[pd.DataFrame]:
        """
        Parse spectra in batches.
        
        Args:
            batch_size: Number of spectra per batch
            
        Yields:
            DataFrame batches with columns:
                - seq_no: int (sequential number in file)
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
        pass
    
    async def get_total_spectra_count(self) -> int:
        """Get total number of spectra in file."""
        metadata = await self.get_metadata()
        return metadata.get('spectra_count', 0)
```

#### Required DataFrame Columns

Each batch must be a `pandas.DataFrame` with these columns:

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `seq_no` | int | ✅ | Sequential number (1-based) in file |
| `title` | str | ✅ | Spectrum title/identifier |
| `scans` | int | ❌ | Scan number(s) |
| `charge` | int | ❌ | Precursor charge state |
| `rt` | float | ❌ | Retention time (minutes) |
| `pepmass` | float | ✅ | Precursor m/z |
| `mz_array` | np.ndarray | ✅ | Peak m/z values |
| `intensity_array` | np.ndarray | ✅ | Peak intensities |
| `charge_array` | np.ndarray | ❌ | Charge state per peak |
| `charge_array_common_value` | int | ❌ | Common charge if all peaks same |
| `all_params` | dict | ❌ | Additional parameters |

#### Implementation Requirements

1. **Batch Processing:**
   - Yield batches of `batch_size` spectra
   - Use `AsyncIterator` for memory efficiency
   - Last batch may be smaller than `batch_size`

2. **Array Format:**
   - `mz_array` and `intensity_array`: 1D numpy arrays
   - Must have same length
   - Use `dtype=np.float64` for consistency

3. **Performance:**
   - Stream file content (don't load entire file)
   - Yield batches as soon as available
   - Handle large files (GB+) efficiently

#### Example: MGF Parser Skeleton

```python
import numpy as np
import pandas as pd
from typing import AsyncIterator
from .base import SpectralDataParser

class MGFParser(SpectralDataParser):
    """Parse MGF (Mascot Generic Format) files."""
    
    async def validate(self) -> bool:
        """Check if file is valid MGF."""
        async with aiofiles.open(self.file_path, 'r') as f:
            first_lines = [await f.readline() for _ in range(5)]
            return any('BEGIN IONS' in line for line in first_lines)
    
    async def get_metadata(self) -> dict:
        """Count spectra in MGF."""
        count = 0
        async with aiofiles.open(self.file_path, 'r') as f:
            async for line in f:
                if 'BEGIN IONS' in line:
                    count += 1
        
        return {
            'spectra_count': count,
            'format': 'MGF'
        }
    
    async def parse_batch(
        self,
        batch_size: int = 1000
    ) -> AsyncIterator[pd.DataFrame]:
        """Parse MGF in batches."""
        batch = []
        seq_no = 0
        current_spectrum = None
        
        async with aiofiles.open(self.file_path, 'r') as f:
            async for line in f:
                line = line.strip()
                
                if line == 'BEGIN IONS':
                    current_spectrum = {
                        'mz_list': [],
                        'intensity_list': []
                    }
                
                elif line == 'END IONS' and current_spectrum:
                    seq_no += 1
                    
                    # Convert to spectrum record
                    spectrum_data = {
                        'seq_no': seq_no,
                        'title': current_spectrum.get('TITLE', f'Scan_{seq_no}'),
                        'pepmass': float(current_spectrum.get('PEPMASS', 0)),
                        'rt': float(current_spectrum.get('RTINSECONDS', 0)) / 60.0 if 'RTINSECONDS' in current_spectrum else None,
                        'charge': int(current_spectrum.get('CHARGE', '1').rstrip('+')) if 'CHARGE' in current_spectrum else None,
                        'mz_array': np.array(current_spectrum['mz_list'], dtype=np.float64),
                        'intensity_array': np.array(current_spectrum['intensity_list'], dtype=np.float64)
                    }
                    
                    batch.append(spectrum_data)
                    current_spectrum = None
                    
                    # Yield batch if full
                    if len(batch) >= batch_size:
                        yield pd.DataFrame(batch)
                        batch = []
                
                elif current_spectrum is not None:
                    if '=' in line:
                        key, value = line.split('=', 1)
                        current_spectrum[key] = value
                    else:
                        # Peak data: "mz intensity"
                        try:
                            parts = line.split()
                            if len(parts) >= 2:
                                current_spectrum['mz_list'].append(float(parts[0]))
                                current_spectrum['intensity_list'].append(float(parts[1]))
                        except ValueError:
                            pass
        
        # Yield remaining spectra
        if batch:
            yield pd.DataFrame(batch)
```

---

### IdentificationParser

**Location:** `api/inputs/peptides/base.py`

Base class for parsing peptide identification files with spectrum ID resolution.

#### Class Definition

```python
from abc import abstractmethod
from typing import AsyncIterator, TYPE_CHECKING
import pandas as pd
from ..base import BaseImporter

if TYPE_CHECKING:
    from api.project.project import Project

class IdentificationParser(BaseImporter):
    """Base class for identification data parsers."""
    
    def __init__(
        self,
        file_path: str,
        tool_id: int,
        spectra_file_id: int,
        ident_file_id: int
    ):
        """
        Initialize identification parser.
        
        Args:
            file_path: Path to identification file
            tool_id: FK to tool that produced this file
            spectra_file_id: FK to associated spectra file
            ident_file_id: ID of identification_file record
        """
        super().__init__(file_path)
        self.tool_id = tool_id
        self.spectra_file_id = spectra_file_id
        self.ident_file_id = ident_file_id
    
    @abstractmethod
    async def parse_batch(
        self,
        batch_size: int = 1000
    ) -> AsyncIterator[pd.DataFrame]:
        """
        Parse identifications in batches.
        
        Yields:
            DataFrame batches with columns:
                - spectre_id: int (must be resolved from title/scan)
                - tool_id: int
                - ident_file_id: int
                - is_preferred: bool (False by default)
                - sequence: str
                - canonical_sequence: str
                - ppm: float | None
                - theor_mass: float | None
                - score: float | None
                - positional_scores: dict | None
        """
        pass
    
    @abstractmethod
    async def resolve_spectrum_id(
        self,
        project: 'Project',
        spectrum_identifier: str | int
    ) -> int | None:
        """
        Resolve spectrum ID from file-specific identifier.
        
        Args:
            project: Project instance for querying
            spectrum_identifier: Title, scan number, or other identifier
            
        Returns:
            spectrum_id or None if not found
        """
        pass
```

#### Required DataFrame Columns

| Column | Type | Required | Description |
|--------|------|----------|-------------|
| `spectre_id` | int | ✅ | FK to spectrum (resolved from identifier) |
| `tool_id` | int | ✅ | FK to tool (from constructor) |
| `ident_file_id` | int | ✅ | FK to ident file (from constructor) |
| `is_preferred` | bool | ✅ | Preferred identification flag (default False) |
| `sequence` | str | ✅ | Peptide sequence with modifications |
| `canonical_sequence` | str | ✅ | Sequence without modifications |
| `ppm` | float | ❌ | Mass error in ppm |
| `theor_mass` | float | ❌ | Theoretical mass |
| `score` | float | ❌ | Identification score |
| `positional_scores` | dict | ❌ | Per-position confidence scores |

#### Implementation Requirements

1. **Spectrum ID Resolution:**
   - Use `resolve_spectrum_id()` to map file identifiers to DB IDs
   - Cache resolved IDs for performance
   - Handle missing spectra gracefully (log warning, skip)

2. **Sequence Formats:**
   - `sequence`: Keep original notation (e.g., `M(ox)PEPTIDEK`)
   - `canonical_sequence`: Remove modifications (e.g., `MPEPTIDEK`)

3. **Batch Processing:**
   - Similar to `SpectralDataParser`
   - Resolve spectrum IDs within batch before yielding

#### Example: CSV Identification Parser

```python
import pandas as pd
from typing import AsyncIterator
from .base import IdentificationParser

class CSVIdentificationParser(IdentificationParser):
    """Parse CSV identification files."""
    
    def __init__(
        self,
        file_path: str,
        tool_id: int,
        spectra_file_id: int,
        ident_file_id: int,
        column_mapping: dict
    ):
        """
        Initialize with column mapping.
        
        Args:
            column_mapping: Map CSV columns to standard fields
                Example: {
                    'Spectrum': 'spectrum_identifier',
                    'Sequence': 'sequence',
                    'Score': 'score'
                }
        """
        super().__init__(file_path, tool_id, spectra_file_id, ident_file_id)
        self.column_mapping = column_mapping
        self._id_cache = {}
    
    async def validate(self) -> bool:
        """Check if CSV has required columns."""
        try:
            df = pd.read_csv(self.file_path, nrows=1)
            required = set(self.column_mapping.keys())
            return required.issubset(set(df.columns))
        except Exception:
            return False
    
    async def get_metadata(self) -> dict:
        """Get identification count."""
        line_count = sum(1 for _ in open(self.file_path))
        return {
            'identification_count': line_count - 1,
            'format': 'CSV'
        }
    
    async def resolve_spectrum_id(
        self,
        project,
        spectrum_identifier: str | int
    ) -> int | None:
        """Resolve spectrum ID by title."""
        # Check cache
        if spectrum_identifier in self._id_cache:
            return self._id_cache[spectrum_identifier]
        
        # Query database
        result = await project.execute_query(
            """
            SELECT id FROM spectre 
            WHERE spectre_file_id = ? AND title = ?
            """,
            (self.spectra_file_id, str(spectrum_identifier))
        )
        
        if result:
            spectrum_id = result[0]['id']
            self._id_cache[spectrum_identifier] = spectrum_id
            return spectrum_id
        
        return None
    
    async def parse_batch(
        self,
        batch_size: int = 1000
    ) -> AsyncIterator[pd.DataFrame]:
        """Parse CSV in batches."""
        # Read CSV in chunks
        for chunk in pd.read_csv(self.file_path, chunksize=batch_size):
            # Rename columns
            chunk = chunk.rename(columns=self.column_mapping)
            
            # Prepare output batch
            batch_data = []
            
            for _, row in chunk.iterrows():
                # Resolve spectrum ID
                spectrum_id = await self.resolve_spectrum_id(
                    self._project,  # Must be set externally
                    row['spectrum_identifier']
                )
                
                if spectrum_id is None:
                    continue  # Skip unmatched
                
                # Remove modifications for canonical sequence
                canonical = row['sequence'].replace('(ox)', '').replace('[+16]', '')
                
                batch_data.append({
                    'spectre_id': spectrum_id,
                    'tool_id': self.tool_id,
                    'ident_file_id': self.ident_file_id,
                    'is_preferred': False,
                    'sequence': row['sequence'],
                    'canonical_sequence': canonical,
                    'score': row.get('score'),
                    'ppm': row.get('ppm'),
                    'theor_mass': row.get('theor_mass')
                })
            
            if batch_data:
                yield pd.DataFrame(batch_data)
```

---

## Reports

### ReportParameters

**Location:** `api/reporting/base.py`

Base class for report parameters using Pydantic for validation.

```python
from pydantic import BaseModel, Field

class ReportParameters(BaseModel):
    """Base class for report parameters."""
    pass

# Example: Custom report parameters
class VolcanoPlotParameters(ReportParameters):
    """Parameters for volcano plot."""
    
    fc_threshold: float = Field(
        default=2.0,
        gt=0,
        description="Fold change threshold"
    )
    pvalue_threshold: float = Field(
        default=0.05,
        gt=0,
        lt=1,
        description="P-value threshold"
    )
    subset_1: int = Field(
        description="First subset ID for comparison"
    )
    subset_2: int = Field(
        description="Second subset ID for comparison"
    )
```

---

### BaseReport

**Location:** `api/reporting/base.py`

Base class for all report modules with data and visualization generation.

#### Class Definition

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING
import pandas as pd
import plotly.graph_objects as go
from pydantic import BaseModel

if TYPE_CHECKING:
    from api.project.project import Project

class ReportParameters(BaseModel):
    """Base class for report parameters."""
    pass

class BaseReport(ABC):
    """Base class for all report modules."""
    
    # Report metadata
    name: str = "Base Report"
    description: str = "Base report class"
    version: str = "1.0.0"
    
    @abstractmethod
    def get_parameters_schema(self) -> type[ReportParameters]:
        """Get Pydantic model for report parameters."""
        pass
    
    @abstractmethod
    async def generate(
        self,
        project: 'Project',
        params: ReportParameters
    ) -> tuple[pd.DataFrame | None, go.Figure | None]:
        """
        Generate report.
        
        Returns:
            Tuple of (data_table, figure)
            Either can be None if not applicable
        """
        pass
    
    async def export_data(
        self,
        data: pd.DataFrame,
        output_path: Path | str,
        format: str = 'xlsx'
    ) -> None:
        """Export data table to file."""
        output_path = Path(output_path)
        
        if format == 'xlsx':
            data.to_excel(output_path, index=False)
        elif format == 'csv':
            data.to_csv(output_path, index=False)
        elif format == 'tsv':
            data.to_csv(output_path, sep='\t', index=False)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    async def export_figure(
        self,
        figure: go.Figure,
        output_path: Path | str,
        format: str = 'png',
        width: int = 1200,
        height: int = 800
    ) -> None:
        """Export figure to file."""
        output_path = Path(output_path)
        
        if format in ['png', 'svg', 'pdf']:
            figure.write_image(str(output_path), format=format, width=width, height=height)
        elif format == 'html':
            figure.write_html(str(output_path))
        elif format == 'json':
            figure.write_json(str(output_path))
        else:
            raise ValueError(f"Unsupported format: {format}")
```

#### Implementation Requirements

1. **Class Attributes:**
   - `name`: Display name for UI
   - `description`: Brief description
   - `version`: Report version (for compatibility)

2. **Parameter Schema:**
   - Return Pydantic model class
   - Use Field() for validation and descriptions
   - GUI will auto-generate form from schema

3. **Generate Method:**
   - Can return data only, figure only, or both
   - Use None for unused return value
   - Async to allow database queries

#### Example: Sample Summary Report

```python
from typing import TYPE_CHECKING
import pandas as pd
import plotly.graph_objects as go
from pydantic import Field
from .base import BaseReport, ReportParameters

if TYPE_CHECKING:
    from api.project.project import Project

class SampleSummaryParameters(ReportParameters):
    """Parameters for sample summary report."""
    
    include_empty: bool = Field(
        default=False,
        description="Include samples without spectra"
    )

class SampleSummaryReport(BaseReport):
    """Generate summary of samples in project."""
    
    name = "Sample Summary"
    description = "Overview of all samples with spectra counts"
    version = "1.0.0"
    
    def get_parameters_schema(self) -> type[ReportParameters]:
        """Return parameter schema."""
        return SampleSummaryParameters
    
    async def generate(
        self,
        project: 'Project',
        params: SampleSummaryParameters
    ) -> tuple[pd.DataFrame | None, go.Figure | None]:
        """Generate sample summary."""
        
        # Query data
        query = """
            SELECT 
                s.name as sample_name,
                sub.name as subset_name,
                COUNT(DISTINCT sf.id) as file_count,
                COUNT(DISTINCT sp.id) as spectra_count
            FROM sample s
            LEFT JOIN subset sub ON s.subset_id = sub.id
            LEFT JOIN spectre_file sf ON s.id = sf.sample_id
            LEFT JOIN spectre sp ON sf.id = sp.spectre_file_id
            GROUP BY s.id
        """
        
        if not params.include_empty:
            query += " HAVING spectra_count > 0"
        
        data = await project.execute_query_df(query)
        
        # Create bar chart
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=data['sample_name'],
            y=data['spectra_count'],
            text=data['spectra_count'],
            textposition='auto',
            marker_color=data['subset_name'].map({
                'Control': '#3498db',
                'Treatment': '#e74c3c'
            })
        ))
        
        fig.update_layout(
            title='Spectra Count by Sample',
            xaxis_title='Sample',
            yaxis_title='Number of Spectra',
            template='plotly_white'
        )
        
        return data, fig
```

---

## Implementation Examples

### Complete MGF Importer

See [MGF Importer Example](../examples/mgf_importer.md)

### Complete PLGS Identification Parser

See [PLGS Parser Example](../examples/plgs_parser.md)

### Complete Volcano Plot Report

See [Volcano Plot Example](../examples/volcano_report.md)

---

## Testing Custom Classes

### Unit Test Template

```python
import pytest
import asyncio
from pathlib import Path
from your_module import YourParser

@pytest.mark.asyncio
async def test_parser_validation():
    """Test file validation."""
    parser = YourParser("test_data/valid_file.mgf")
    assert await parser.validate() == True

@pytest.mark.asyncio
async def test_parser_metadata():
    """Test metadata extraction."""
    parser = YourParser("test_data/test_file.mgf")
    metadata = await parser.get_metadata()
    
    assert 'spectra_count' in metadata
    assert metadata['spectra_count'] > 0

@pytest.mark.asyncio
async def test_parser_batches():
    """Test batch parsing."""
    parser = YourParser("test_data/test_file.mgf")
    
    total_count = 0
    async for batch in parser.parse_batch(batch_size=100):
        assert not batch.empty
        assert 'seq_no' in batch.columns
        assert 'pepmass' in batch.columns
        total_count += len(batch)
    
    metadata = await parser.get_metadata()
    assert total_count == metadata['spectra_count']
```

### Integration Test with Project

```python
import pytest
from api import Project
from your_module import YourParser

@pytest.mark.asyncio
async def test_import_to_project():
    """Test importing data into project."""
    async with Project() as project:  # In-memory
        # Setup
        subset = await project.add_subset("Test")
        tool = await project.add_tool("TestTool", "library")
        sample = await project.add_sample("Sample1", subset.id)
        
        file_id = await project.add_spectra_file(
            sample.id, "MGF", "test_data/test.mgf"
        )
        
        # Import
        parser = YourParser("test_data/test.mgf")
        async for batch in parser.parse_batch():
            await project.add_spectra_batch(file_id, batch)
        
        # Verify
        spectra = await project.get_spectra(sample_id=sample.id)
        assert len(spectra) > 0
```

---

## Best Practices

### 1. Memory Efficiency

```python
# ✅ Good - streaming with generators
async def parse_batch(self, batch_size):
    batch = []
    async for line in self._read_file():
        # Process line
        batch.append(data)
        if len(batch) >= batch_size:
            yield pd.DataFrame(batch)
            batch = []  # Clear batch

# ❌ Bad - loading entire file
async def parse_batch(self, batch_size):
    all_data = await self._load_all_data()
    for i in range(0, len(all_data), batch_size):
        yield pd.DataFrame(all_data[i:i+batch_size])
```

### 2. Error Handling

```python
async def parse_batch(self, batch_size):
    """Parse with error handling."""
    batch = []
    errors = []
    
    async for line_no, line in self._read_file_with_line_numbers():
        try:
            data = self._parse_line(line)
            batch.append(data)
        except Exception as e:
            errors.append(f"Line {line_no}: {e}")
            continue
        
        if len(batch) >= batch_size:
            yield pd.DataFrame(batch)
            batch = []
    
    if batch:
        yield pd.DataFrame(batch)
    
    if errors:
        logger.warning(f"Parsing errors: {len(errors)}")
        for error in errors[:10]:  # Log first 10
            logger.warning(error)
```

### 3. Validation

```python
async def validate(self) -> bool:
    """Robust validation."""
    try:
        # Check file extension
        if self.file_path.suffix.lower() not in ['.mgf', '.mgf.gz']:
            return False
        
        # Check magic bytes or header
        async with aiofiles.open(self.file_path, 'rb') as f:
            header = await f.read(100)
            if b'BEGIN IONS' not in header:
                return False
        
        # Quick parse test
        async for batch in self.parse_batch(batch_size=1):
            if batch.empty:
                return False
            break
        
        return True
    except Exception:
        return False
```

---

## See Also

- [Project API Documentation](PROJECT_API.md)
- [Dataclasses Documentation](DATACLASSES.md)
- [Database Schema](../project/spec/DATABASE_SCHEMA.md)
- [Example Implementations](../examples/)
