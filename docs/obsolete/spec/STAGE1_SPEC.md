# 📐 **PLAN - Спецификация первого этапа разработки**

## 🎯 **Цели первого этапа**

1. Создать базовую структуру проекта
2. Реализовать класс `Project` с асинхронным API для работы с SQLite
3. Разработать абстрактные классы для импортеров
4. Создать абстрактный класс для отчетов
5. Реализовать dataclasses для внешнего интерфейса

---

## 📁 **Структура файлов и модулей**

```
dasmixer/
├── api/
│   ├── __init__.py
│   ├── project/
│   │   ├── __init__.py
│   │   ├── project.py              # Основной класс Project
│   │   ├── schema.py                # SQL-схема для создания БД
│   │   └── dataclasses.py           # Dataclasses: Sample, Protein, Tool, Subset
│   ├── inputs/
│   │   ├── __init__.py
│   │   ├── base.py                  # Абстрактные классы для импортеров
│   │   ├── spectra/
│   │   │   ├── __init__.py
│   │   │   └── base.py              # Абстрактный SpectralDataParser
│   │   └── peptides/
│   │       ├── __init__.py
│   │       └── base.py              # Абстрактный IdentificationParser
│   └── reporting/
│       ├── __init__.py
│       └── base.py                  # Абстрактный класс Report
├── gui/
│   └── __init__.py
├── cli/
│   └── __init__.py
└── utils/
    ├── __init__.py
    └── logger.py                    # Настройка логирования
```

---

## 🗄️ **1. Обновление схемы БД**

### Изменения в `docs/PROJECT_ER.mermaid`

Добавляем поле `charge_array_common_value` в таблицу `SPECTRE`:

```mermaid
SPECTRE {
    int id PK
    int spectre_file_id FK
    int seq_no
    string title
    int scans
    int charge
    float rt
    float pepmass
    blob intensity
    blob mz_array
    blob intensity_array
    blob charge_array
    int charge_array_common_value  # NEW!
    json all_params
}
```

### SQL-схема (`api/project/schema.py`)

```sql
-- Все таблицы из ER-диаграммы
-- Особенности:
-- 1. BLOB поля для numpy arrays (сжатые через savez_compressed)
-- 2. SQLite не поддерживает JSON, т.о. используем поля text где указано JSON
-- 3. Индексы на внешние ключи для производительности
-- 4. Уникальные ограничения где необходимо
```

---

## 🔧 **2. Dataclasses (`api/project/dataclasses.py`)**

### 2.1 `Subset`

```python
@dataclass
class Subset:
    id: int | None = None
    name: str
    details: str | None = None
    display_color: str | None = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary for database operations"""
        
    @classmethod
    def from_dict(cls, data: dict) -> 'Subset':
        """Create from database row"""
```

### 2.2 `Tool`

```python
@dataclass
class Tool:
    id: int | None = None
    name: str
    type: str  # "library", "denovo", etc.
    settings: dict | None = None
    display_color: str | None = None
    
    def to_dict(self) -> dict:
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Tool':
```

### 2.3 `Sample`

```python
@dataclass
class Sample:
    id: int | None = None
    name: str
    subset_id: int | None = None
    additions: dict | None = None  # albumin, total_protein, etc.
    
    # Computed fields (не хранятся в БД, заполняются при загрузке)
    subset_name: str | None = None
    spectra_files_count: int = 0
    
    def to_dict(self) -> dict:
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Sample':
```

### 2.4 `Protein`

```python
@dataclass
class Protein:
    id: str  # Uniprot ID или custom
    is_uniprot: bool = False
    fasta_name: str | None = None
    sequence: str | None = None
    gene: str | None = None
    
    # Enrichment data (загружается опционально)
    uniprot_data: dict | None = None
    protein_atlas_data: dict | None = None
    
    def to_dict(self) -> dict:
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Protein':
```

---

## 🏗️ **3. Класс Project (`api/project/project.py`)**

### 3.1 Сигнатура класса

```python
class Project:
    """
    Main class for managing DASMixer project data.
    
    Project is stored as a single SQLite database file.
    All methods are async to prevent UI blocking.
    
    Usage:
        # Create or open
        project = Project(path="my_project.dasmix", create_if_not_exists=True)
        await project.initialize()
        
        # Use as context manager
        async with Project(path="my_project.dasmix") as project:
            await project.add_sample(...)
    """
    
    def __init__(
        self, 
        path: Path | str | None = None,
        create_if_not_exists: bool = True
    ):
        """
        Initialize project.
        
        Args:
            path: Path to project file (.dasmix). If None, creates in-memory project.
            create_if_not_exists: If True and path doesn't exist, creates new project.
                                  If False and path doesn't exist, raises FileNotFoundError.
        """
    
    async def initialize(self) -> None:
        """Initialize database connection and create schema if needed."""
    
    async def close(self) -> None:
        """Close database connection."""
    
    async def __aenter__(self) -> 'Project':
        """Context manager entry."""
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - auto-saves and closes."""
```

### 3.2 Основные методы управления

```python
    async def save(self) -> None:
        """Save current state (commit transaction)."""
    
    async def save_as(self, path: Path | str) -> None:
        """
        Save project to a new file.
        
        Args:
            path: New file path
        """
    
    async def get_metadata(self) -> dict:
        """
        Get project metadata.
        
        Returns:
            dict: Project metadata including creation date, version, etc.
        """
    
    async def set_setting(self, key: str, value: str) -> None:
        """Set a project setting."""
    
    async def get_setting(self, key: str, default: str | None = None) -> str | None:
        """Get a project setting."""
```

### 3.3 Работа с Subsets

```python
    async def add_subset(
        self, 
        name: str, 
        details: str | None = None,
        display_color: str | None = None
    ) -> Subset:
        """
        Add a new comparison group.
        
        Args:
            name: Unique subset name
            details: Optional description
            display_color: Hex color for visualization
            
        Returns:
            Created Subset object
            
        Raises:
            ValueError: If subset with this name already exists
        """
    
    async def get_subsets(self) -> list[Subset]:
        """Get all subsets."""
    
    async def get_subset(self, subset_id: int) -> Subset | None:
        """Get subset by ID."""
    
    async def update_subset(self, subset: Subset) -> None:
        """Update existing subset."""
    
    async def delete_subset(self, subset_id: int) -> None:
        """
        Delete subset.
        
        Raises:
            ValueError: If subset has associated samples
        """
```

### 3.4 Работа с Tools

```python
    async def add_tool(
        self,
        name: str,
        type: str,
        settings: dict | None = None,
        display_color: str | None = None
    ) -> Tool:
        """Add a new identification tool."""
    
    async def get_tools(self) -> list[Tool]:
        """Get all tools."""
    
    async def get_tool(self, tool_id: int) -> Tool | None:
        """Get tool by ID."""
    
    async def update_tool(self, tool: Tool) -> None:
        """Update existing tool."""
    
    async def delete_tool(self, tool_id: int) -> None:
        """Delete tool (if no identifications associated)."""
```

### 3.5 Работа с Samples

```python
    async def add_sample(
        self,
        name: str,
        subset_id: int | None = None,
        additions: dict | None = None
    ) -> Sample:
        """
        Add a new sample.
        
        Args:
            name: Unique sample name
            subset_id: FK to subset (comparison group)
            additions: Additional metadata (albumin, total_protein, etc.)
            
        Returns:
            Created Sample object
        """
    
    async def get_samples(self, subset_id: int | None = None) -> list[Sample]:
        """
        Get samples, optionally filtered by subset.
        
        Args:
            subset_id: If provided, return only samples from this subset
        """
    
    async def get_sample(self, sample_id: int) -> Sample | None:
        """Get sample by ID."""
    
    async def get_sample_by_name(self, name: str) -> Sample | None:
        """Get sample by name."""
    
    async def update_sample(self, sample: Sample) -> None:
        """Update existing sample."""
    
    async def delete_sample(self, sample_id: int) -> None:
        """Delete sample (cascades to spectra files)."""
```

### 3.6 Работа с Spectra Files

```python
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
    
    async def get_spectra_files(
        self, 
        sample_id: int | None = None
    ) -> pd.DataFrame:
        """
        Get spectra files as DataFrame.
        
        Columns: id, sample_id, format, path, sample_name
        """
```

### 3.7 Работа с Spectra (пакетная обработка)

```python
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
    
    async def get_spectrum_full(self, spectrum_id: int) -> dict:
        """
        Get full spectrum data including arrays.
        
        Returns:
            dict with all fields including decompressed numpy arrays
        """
```

### 3.8 Работа с Identification Files

```python
    async def add_identification_file(
        self,
        spectra_file_id: int,
        tool_id: int,
        file_path: str
    ) -> int:
        """Add identification file record."""
    
    async def get_identification_files(
        self,
        spectra_file_id: int | None = None,
        tool_id: int | None = None
    ) -> pd.DataFrame:
        """Get identification files as DataFrame."""
```

### 3.9 Работа с Identifications (пакетная обработка)

```python
    async def add_identifications_batch(
        self,
        identifications_df: pd.DataFrame
    ) -> None:
        """
        Add batch of identifications.
        
        Args:
            identifications_df: DataFrame with columns:
                - spectre_id: int
                - tool_id: int
                - ident_file_id: int
                - is_preferred: bool
                - sequence: str
                - canonical_sequence: str
                - ppm: float | None
                - theor_mass: float | None
                - score: float | None
                - positional_scores: dict | None
        """
    
    async def get_identifications(
        self,
        spectra_file_id: int | None = None,
        tool_id: int | None = None,
        sample_id: int | None = None
    ) -> pd.DataFrame:
        """Get identifications as DataFrame with joined metadata."""
```

### 3.10 Работа с Proteins

```python
    async def add_protein(self, protein: Protein) -> None:
        """Add or update protein."""
    
    async def add_proteins_batch(self, proteins_df: pd.DataFrame) -> None:
        """Add batch of proteins from DataFrame."""
    
    async def get_protein(self, protein_id: str) -> Protein | None:
        """Get protein by ID."""
    
    async def get_proteins(
        self,
        is_uniprot: bool | None = None
    ) -> list[Protein]:
        """Get proteins, optionally filtered."""
```

### 3.11 Low-level SQL API

```python
    async def execute_query(
        self,
        query: str,
        params: tuple | dict | None = None
    ) -> list[dict]:
        """
        Execute raw SQL query.
        
        For complex reports and custom operations.
        
        Returns:
            List of rows as dictionaries
        """
    
    async def execute_query_df(
        self,
        query: str,
        params: tuple | dict | None = None
    ) -> pd.DataFrame:
        """Execute query and return as DataFrame."""
```

---

## 🔌 **4. Абстрактные классы для импортеров**

### 4.1 Base Importer (`api/inputs/base.py`)

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import AsyncIterator
import pandas as pd

class BaseImporter(ABC):
    """Base class for all data importers."""
    
    def __init__(self, file_path: Path | str):
        """
        Initialize importer.
        
        Args:
            file_path: Path to file to import
        """
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

### 4.2 Spectral Data Parser (`api/inputs/spectra/base.py`)

```python
class SpectralDataParser(BaseImporter):
    """
    Base class for spectral data parsers (MGF, MZML, etc.).
    
    Supports batch processing for large files.
    """
    
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
        """
        Get total number of spectra in file.
        
        Default implementation calls get_metadata().
        Override for efficiency if format allows direct counting.
        """
        metadata = await self.get_metadata()
        return metadata.get('spectra_count', 0)
```

### 4.3 Identification Parser (`api/inputs/peptides/base.py`)

```python
class IdentificationParser(BaseImporter):
    """
    Base class for identification data parsers.
    
    Supports various tabular formats (CSV, XLSX, tool-specific).
    """
    
    def __init__(
        self,
        file_path: Path | str,
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
                - is_preferred: bool (False by default, set by selection logic)
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

---

## 📊 **5. Абстрактный класс для отчетов (`api/reporting/base.py`)**

```python
from abc import ABC, abstractmethod
from typing import Any
import pandas as pd
import plotly.graph_objects as go
from pydantic import BaseModel

class ReportParameters(BaseModel):
    """Base class for report parameters (for validation)."""
    pass

class BaseReport(ABC):
    """
    Base class for all report modules.
    
    Each report can produce:
    - Data table (DataFrame)
    - Visualization (Plotly Figure)
    - Or both
    """
    
    # Report metadata
    name: str = "Base Report"
    description: str = "Base report class"
    version: str = "1.0.0"
    
    @abstractmethod
    def get_parameters_schema(self) -> type[ReportParameters]:
        """
        Get Pydantic model for report parameters.
        
        Used for:
        - GUI form generation
        - CLI argument validation
        - API parameter validation
        
        Returns:
            Pydantic BaseModel subclass
        """
        pass
    
    @abstractmethod
    async def generate(
        self,
        project: 'Project',
        params: ReportParameters
    ) -> tuple[pd.DataFrame | None, go.Figure | None]:
        """
        Generate report.
        
        Args:
            project: Project instance
            params: Validated parameters
            
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
        """
        Export data table to file.
        
        Args:
            data: DataFrame to export
            output_path: Output file path
            format: Export format (xlsx, csv, tsv)
        """
        # Default implementation
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
        """
        Export figure to file.
        
        Args:
            figure: Plotly figure
            output_path: Output file path
            format: Export format (png, svg, html, json)
            width: Image width in pixels
            height: Image height in pixels
        """
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

---

## 🪵 **6. Утилиты: Логирование (`utils/logger.py`)**

```python
import logging
import sys
from pathlib import Path

def setup_logger(
    name: str = "dasmixer",
    level: int = logging.INFO,
    log_file: Path | str | None = None
) -> logging.Logger:
    """
    Setup application logger.
    
    Args:
        name: Logger name
        level: Logging level
        log_file: Optional log file path
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

# Default logger
logger = setup_logger()
```

---

## 📦 **7. Вспомогательные функции**

### 7.1 Работа с numpy arrays (`api/project/array_utils.py`)

```python
import numpy as np
import io

def compress_array(arr: np.ndarray) -> bytes:
    """
    Compress numpy array using savez_compressed.
    
    Args:
        arr: Numpy array
        
    Returns:
        Compressed bytes
    """
    buffer = io.BytesIO()
    np.savez_compressed(buffer, data=arr)
    return buffer.getvalue()

def decompress_array(data: bytes) -> np.ndarray:
    """
    Decompress numpy array.
    
    Args:
        data: Compressed bytes
        
    Returns:
        Numpy array
    """
    buffer = io.BytesIO(data)
    loaded = np.load(buffer)
    return loaded['data']
```

---

## ✅ **8. Чеклист файлов для создания**

### Обязательные файлы:

- [ ] `api/__init__.py`
- [ ] `api/project/__init__.py`
- [ ] `api/project/project.py` - Основной класс Project
- [ ] `api/project/schema.py` - SQL схема БД
- [ ] `api/project/dataclasses.py` - Dataclasses (Subset, Tool, Sample, Protein)
- [ ] `api/project/array_utils.py` - Утилиты для numpy arrays
- [ ] `api/inputs/__init__.py`
- [ ] `api/inputs/base.py` - BaseImporter
- [ ] `api/inputs/spectra/__init__.py`
- [ ] `api/inputs/spectra/base.py` - SpectralDataParser
- [ ] `api/inputs/peptides/__init__.py`
- [ ] `api/inputs/peptides/base.py` - IdentificationParser
- [ ] `api/reporting/__init__.py`
- [ ] `api/reporting/base.py` - BaseReport
- [ ] `utils/__init__.py`
- [ ] `utils/logger.py` - Настройка логирования
- [ ] `docs/PROJECT_ER.mermaid` - Обновить схему (добавить charge_array_common_value)

### Опциональные (для тестирования):

- [ ] `tests/__init__.py`
- [ ] `tests/test_project.py` - Тесты для Project (создадим позже)

---

## 🔄 **9. Порядок реализации**

1. **Обновление документации** - `PROJECT_ER.mermaid`
2. **Утилиты** - `logger.py`, `array_utils.py`
3. **Dataclasses** - `api/project/dataclasses.py`
4. **SQL схема** - `api/project/schema.py`
5. **Класс Project** - `api/project/project.py` (основной)
6. **Абстрактные импортеры**:
   - `api/inputs/base.py`
   - `api/inputs/spectra/base.py`
   - `api/inputs/peptides/base.py`
7. **Абстрактный отчет** - `api/reporting/base.py`
8. **Инициализация пакетов** - `__init__.py` файлы

---

## 📝 **10. Особенности реализации**

### 10.1 Асинхронность
- Все методы `Project` - async
- Используем `aiosqlite` для неблокирующих операций
- Пакетная обработка через `AsyncIterator`

### 10.2 Сериализация
- **Numpy arrays**: `savez_compressed` → BLOB
- **JSON поля**: `json.dumps/loads`
- **Pickle для отчетов**: `pickle.dumps` + `gzip.compress`

### 10.3 Обработка ошибок
- Все исключения прокидываются наверх
- Логирование с traceback
- Валидация через Pydantic где возможно

### 10.4 Производительность
- Индексы на FK и часто запрашиваемые поля
- Пакетная обработка (batch_size=1000 по умолчанию)
- Ленивая загрузка массивов (только по запросу)

