# STAGE3_1_SPEC.md - Спецификация доработок этапа 3.1

## Обзор

Этап 3.1 включает важные доработки архитектуры парсеров и класса Project, выявленные в процессе разработки этапа 2. Изменения НЕ обратно совместимы с предыдущей версией.

---

## 1. Исправление поля `intensity` в таблице `spectre`

### 1.1 Изменения в `Project.add_spectra_batch()`

**Файл:** `api/project/project.py`

**Текущая реализация:**
```python
# Автоматический расчет intensity из intensity_array
intensity = row.get('intensity')
if intensity is None and 'intensity_array' in row and row['intensity_array'] is not None:
    intensity = float(np.sum(row['intensity_array']))
```

**Новая реализация:**
```python
# intensity берется только из явно переданного значения
intensity = float(row['intensity']) if row.get('intensity') is not None else None
```

**Обоснование:** `intensity` и `intensity_array` - разные величины, которые нельзя выводить друг из друга. `intensity` может быть, например, интенсивностью прекурсора из MGF (второе значение PEPMASS), а `intensity_array` - массив интенсивностей всех пиков спектра.

### 1.2 Обновление документации

**Файл:** `docs/api/PROJECT_API.md`

В разделе `add_spectra_batch()` уточнить описание параметров:
- `intensity`: float | None - интенсивность прекурсора (например, из PEPMASS в MGF) или другая метрика уровня спектра. НЕ вычисляется автоматически из intensity_array
- `intensity_array`: np.ndarray - массив интенсивностей пиков спектра

В разделе `get_spectra()` добавить в описание возвращаемого DataFrame колонку `intensity`.

---

## 2. Упрощение metadata в парсерах спектров

### 2.1 Изменения в `SpectralDataParser`

**Файл:** `api/inputs/spectra/base.py`

#### Удаление метода `get_total_spectra_count()`

```python
# УДАЛИТЬ:
async def get_total_spectra_count(self) -> int:
    """Get total number of spectra in file."""
    metadata = await self.get_metadata()
    return metadata.get('spectra_count', 0)
```

#### Реализация `get_metadata()` на уровне базового класса

```python
async def get_metadata(self) -> dict:
    """
    Get file metadata.
    
    Returns base metadata from file system:
        - file_size: int - размер файла в байтах
        - created_at: str - дата создания (ISO format)
        - modified_at: str - дата изменения (ISO format)
        - file_path: str - полный путь к файлу
    
    Additional metadata from add_metadata() is merged into result.
    
    Returns:
        dict with metadata
    """
    from datetime import datetime
    import os
    
    stat = os.stat(self.file_path)
    metadata = {
        'file_size': stat.st_size,
        'created_at': datetime.fromtimestamp(stat.st_ctime).isoformat(),
        'modified_at': datetime.fromtimestamp(stat.st_mtime).isoformat(),
        'file_path': str(self.file_path.absolute())
    }
    
    # Добавляем специфичные для формата метаданные
    additional = await self.add_metadata()
    metadata.update(additional)
    
    return metadata

async def add_metadata(self) -> dict:
    """
    Add format-specific metadata.
    
    Override in subclasses to provide additional metadata
    (format version, instrument info, etc.).
    
    Returns:
        dict with additional metadata (empty by default)
    """
    return {}
```

### 2.2 Изменения в `BaseImporter`

**Файл:** `api/inputs/base.py`

#### Изменение сигнатуры `get_metadata()`

Убрать декоратор `@abstractmethod`, сделать метод опциональным:

```python
async def get_metadata(self) -> dict:
    """
    Get file metadata.
    
    Base implementation returns empty dict.
    Override in subclasses if metadata is needed.
    
    Returns:
        dict with metadata
    """
    return {}
```

### 2.3 Обновление `MGFParser`

**Файл:** `api/inputs/spectra/mgf.py`

```python
async def add_metadata(self) -> dict:
    """
    Add MGF-specific metadata.
    
    Currently returns empty dict, can be extended to parse
    MGF header comments if needed.
    """
    return {}
```

### 2.4 Обновление документации

**Файл:** `docs/api/IMPORTERS.md` (создать новый)

Документировать изменения в базовых классах парсеров.

---

## 3. Поддержка белковых идентификаций из пептидных файлов

### 3.1 Обновление сигнатуры `parse_batch()`

**Файл:** `api/inputs/peptides/base.py`

#### Уточнение docstring

```python
async def parse_batch(
    self,
    batch_size: int = 1000
) -> AsyncIterator[tuple[pd.DataFrame, pd.DataFrame | None]]:
    """
    Parse identifications in batches.
    
    Some identification files (e.g., from library search tools) may contain
    both peptide and protein identifications in one file.
    
    Yields:
        Tuple of (peptide_df, protein_df):
        
        peptide_df: DataFrame with columns:
            - scans: int | None - scan number(s) for mapping to spectra
            - seq_no: int | None - sequential number for mapping to spectra
              (at least one of scans/seq_no must be present)
            - sequence: str - peptide sequence with modifications
            - canonical_sequence: str - canonical sequence without modifications
            - ppm: float | None - mass error in ppm
            - theor_mass: float | None - theoretical mass
            - score: float | None - identification score
            - positional_scores: dict | None - per-position scores
            
        protein_df: DataFrame | None with columns (if proteins present):
            - scans: int | None - scan number for mapping
            - seq_no: int | None - sequential number for mapping
            - sequence: str - peptide sequence
            - protein_id: str - protein identifier
            - protein_sequence: str | None - full protein sequence
            - gene: str | None - gene name
            
        Note: Protein identifications are collected but not processed
        in current implementation. Will be used in Stage 4.
    """
    pass
```

### 3.2 Обновление конкретных парсеров

Все существующие парсеры продолжают возвращать `(peptide_df, None)`, так как белковые идентификации пока не обрабатываются.

**Файлы:** 
- `api/inputs/peptides/table_importer.py`
- `api/inputs/peptides/PowerNovo2.py`
- `api/inputs/peptides/MQ_Evidences.py`

Изменений не требуется, только проверить что везде возвращается tuple.

---

## 4. Удаление зависимости парсеров от контекста проекта

### 4.1 Изменения в `IdentificationParser`

**Файл:** `api/inputs/peptides/base.py`

#### Удаление параметров из конструктора

```python
class IdentificationParser(BaseImporter):
    """
    Base class for identification data parsers.
    
    Parsers are independent of project context and should only
    parse files, returning standard DataFrames.
    Mapping to spectra IDs is handled externally.
    """
    
    def __init__(self, file_path: str):
        """
        Initialize identification parser.
        
        Args:
            file_path: Path to identification file
        """
        super().__init__(file_path)
    
    # УДАЛИТЬ:
    # tool_id: int
    # spectra_file_id: int
    # ident_file_id: int
    # project: Project | None
```

#### Удаление метода `resolve_spectrum_id()`

```python
# УДАЛИТЬ ПОЛНОСТЬЮ:
@abstractmethod
async def resolve_spectrum_id(
    self,
    row_data: dict,
) -> int | None:
    """Resolve spectrum ID from file-specific identifier."""
    pass
```

#### Обновление docstring `parse_batch()`

Убрать упоминания о полях `spectre_id`, `tool_id`, `ident_file_id` - парсер их не возвращает.

### 4.2 Обновление `TableImporter` и `SimpleTableImporter`

**Файл:** `api/inputs/peptides/table_importer.py`

#### Изменения в `ColumnRenames`

```python
@dataclass
class ColumnRenames:
    """
    Column mapping configuration for table importers.
    
    Maps source column names to standard output names.
    spectra_id is removed - mapping happens externally.
    """
    # УДАЛИТЬ: spectra_id: str | None
    scans: str | None = None  # ДОБАВИТЬ
    seq_no: str | None = None  # ДОБАВИТЬ
    sequence: str
    canonical_sequence: str | None = None
    score: str | None = None
    positional_scores: str | None = None
    ppm: str | None = None
    theor_mass: str | None = None
```

#### Изменения в `SimpleTableImporter`

```python
def remap_columns(self, df: pd.DataFrame) -> pd.DataFrame:
    """
    Remap columns according to ColumnRenames configuration.
    
    Returns DataFrame with standard column names.
    At least one of scans/seq_no must be present after remapping.
    """
    r = asdict(self.renames)
    rename_cols = {v: k for k, v in r.items() if v is not None}
    result = df.rename(columns=rename_cols)
    
    # Validate that at least one mapping column exists
    if 'scans' not in result.columns and 'seq_no' not in result.columns:
        raise ValueError(
            "Parser must provide at least one of 'scans' or 'seq_no' columns "
            "for spectrum mapping"
        )
    
    # Return only standard columns
    available_cols = [col for col in r.keys() if col in result.columns]
    return result[available_cols]

# УДАЛИТЬ метод resolve_spectrum_id()
```

### 4.3 Обновление конкретных парсеров

#### PowerNovo2Importer

**Файл:** `api/inputs/peptides/PowerNovo2.py`

```python
from api.inputs.peptides.table_importer import SimpleTableImporter, ColumnRenames

renames = ColumnRenames(
    seq_no='SEQ_NO',  # или как называется колонка в PowerNovo2
    sequence='PEPTIDE',
    canonical_sequence='CANONICAL SEQ.',
    ppm='PPM DIFFERENCE',
    score='SCORE',
    positional_scores='POSITIONAL SCORES'
)

class PowerNovo2Importer(SimpleTableImporter):
    separator = ','
    renames = renames
    
    def transform_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform PowerNovo2-specific data."""
        df['POSITIONAL SCORES'] = df['POSITIONAL SCORES'].apply(
            lambda r: [float(x) for x in r.split(' ')] if pd.notna(r) else None
        )
        return df
    
    # УДАЛИТЬ:
    # - id_map
    # - resolve_spectrum_id()
```

#### MaxQuantEvidenceParser

**Файл:** `api/inputs/peptides/MQ_Evidences.py`

```python
from .table_importer import SimpleTableImporter, ColumnRenames

renames = ColumnRenames(
    scans='MS/MS scan number',  # MaxQuant использует scans
    sequence='Modified sequence',
    canonical_sequence='Sequence',
    score='Score',
    ppm='Mass error [ppm]'
)

ptm_replacements = [
    ('(Deamidation (NQ))', '[Deamidation]'),
    ('(de)', '[Deamidation]'),
    ('_', ''),
    ('(Pyridylethyl)', '[Pyridylethyl]'),
    ('(Oxidation (M))', '[Oxidation]'),
]

class MaxQuantEvidenceParser(SimpleTableImporter):
    separator = '\t'
    renames = renames
    
    @staticmethod
    def _fix_sequence(mod_seq: str) -> str:
        """Convert MaxQuant PTM notation to ProForma-like notation."""
        for src, repl in ptm_replacements:
            mod_seq = mod_seq.replace(src, repl)
        return mod_seq
    
    def transform_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform MaxQuant-specific data."""
        df['Modified sequence'] = df['Modified sequence'].apply(self._fix_sequence)
        return df
    
    # УДАЛИТЬ:
    # - id_map
    # - resolve_spectrum_id()
```

---

## 5. Добавление метода маппинга спектров в Project

### 5.1 Новый метод `get_spectra_mapping()`

**Файл:** `api/project/project.py`

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
            - 'auto': use 'scans' if available, else 'seq_no'
            - 'seq_no': map by sequential number in file
            - 'scans': map by scan number
            
    Returns:
        DataFrame with columns:
            - id: int - spectrum database ID
            - scans: int | None - scan number (if available)
            - seq_no: int - sequential number in file
            
    Usage:
        # In identification import logic:
        mapping = await project.get_spectra_mapping(spectra_file_id)
        
        # Merge with parsed identifications
        # If identifications have 'scans':
        merged = pd.merge(ident_df, mapping, on='scans', how='inner')
        # If identifications have 'seq_no':
        merged = pd.merge(ident_df, mapping, on='seq_no', how='inner')
        # Auto-detection:
        merge_on = 'scans' if 'scans' in ident_df.columns and ident_df['scans'].notna().any() else 'seq_no'
        merged = pd.merge(ident_df, mapping, on=merge_on, how='inner')
        
        # Now 'id' column contains spectrum database IDs
    """
    query = """
        SELECT id, scans, seq_no
        FROM spectre
        WHERE spectre_file_id = ?
        ORDER BY seq_no
    """
    
    df = await self.execute_query_df(query, (spectra_file_id,))
    
    if mapping_type == 'auto':
        # Return full mapping, let caller decide
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
        raise ValueError(f"Invalid mapping_type: {mapping_type}")
```

### 5.2 Обновление документации

**Файл:** `docs/api/PROJECT_API.md`

Добавить раздел с описанием нового метода в секцию "Spectra operations".

---

## 6. Реализация системы регистрации парсеров

### 6.1 Улучшение `InputTypesRegistry`

**Файл:** `api/inputs/registry.py`

```python
"""Registry for data parsers."""

from typing import Type
from .peptides import IdentificationParser
from .spectra import SpectralDataParser


class InputTypesRegistry:
    """
    Registry for data parsers available in the application.
    
    Parsers are registered at module import time.
    Future: plugin system will register parsers dynamically.
    """
    
    def __init__(self):
        self._spectra_parsers: dict[str, Type[SpectralDataParser]] = {}
        self._identification_parsers: dict[str, Type[IdentificationParser]] = {}
    
    def add_spectra_parser(
        self,
        name: str,
        parser_class: Type[SpectralDataParser]
    ) -> None:
        """
        Register a spectral data parser.
        
        Args:
            name: Unique parser name (e.g., "MGF", "MZML")
            parser_class: Parser class (not instance)
            
        Raises:
            KeyError: If parser with this name already exists
        """
        if name in self._spectra_parsers:
            raise KeyError(f'Spectral parser "{name}" already registered')
        self._spectra_parsers[name] = parser_class
    
    def add_identification_parser(
        self,
        name: str,
        parser_class: Type[IdentificationParser]
    ) -> None:
        """
        Register an identification parser.
        
        Args:
            name: Unique parser name (e.g., "PowerNovo2", "MaxQuant")
            parser_class: Parser class (not instance)
            
        Raises:
            KeyError: If parser with this name already exists
        """
        if name in self._identification_parsers:
            raise KeyError(f'Identification parser "{name}" already registered')
        self._identification_parsers[name] = parser_class
    
    def get_spectra_parsers(self) -> dict[str, Type[SpectralDataParser]]:
        """
        Get all registered spectral parsers.
        
        Returns:
            Dict mapping parser names to parser classes
        """
        return self._spectra_parsers.copy()
    
    def get_identification_parsers(self) -> dict[str, Type[IdentificationParser]]:
        """
        Get all registered identification parsers.
        
        Returns:
            Dict mapping parser names to parser classes
        """
        return self._identification_parsers.copy()
    
    def get_parser(
        self,
        name: str,
        parser_type: str
    ) -> Type[SpectralDataParser] | Type[IdentificationParser]:
        """
        Get parser class by name and type.
        
        Args:
            name: Parser name
            parser_type: "spectra" or "identification"
            
        Returns:
            Parser class
            
        Raises:
            ValueError: If parser type is invalid
            KeyError: If parser not found
        """
        if parser_type == "spectra":
            if name not in self._spectra_parsers:
                raise KeyError(f'Spectral parser "{name}" not found')
            return self._spectra_parsers[name]
        elif parser_type == "identification":
            if name not in self._identification_parsers:
                raise KeyError(f'Identification parser "{name}" not found')
            return self._identification_parsers[name]
        else:
            raise ValueError(
                f'Invalid parser_type: {parser_type}. '
                'Must be "spectra" or "identification"'
            )


# Global registry instance
registry = InputTypesRegistry()
```

### 6.2 Регистрация парсеров в модулях

#### Регистрация MGF парсера

**Файл:** `api/inputs/spectra/__init__.py`

```python
"""Spectral data parsers."""

from .base import SpectralDataParser
from .mgf import MGFParser
from ..registry import registry

# Register parsers
registry.add_spectra_parser("MGF", MGFParser)

__all__ = ['SpectralDataParser', 'MGFParser']
```

#### Регистрация пептидных парсеров

**Файл:** `api/inputs/peptides/__init__.py`

```python
"""Peptide identification parsers."""

from .base import IdentificationParser
from .table_importer import (
    TableImporter,
    SimpleTableImporter,
    LargeCSVImporter,
    ColumnRenames
)
from .PowerNovo2 import PowerNovo2Importer
from .MQ_Evidences import MaxQuantEvidenceParser
from ..registry import registry

# Register parsers
registry.add_identification_parser("PowerNovo2", PowerNovo2Importer)
registry.add_identification_parser("MaxQuant", MaxQuantEvidenceParser)

__all__ = [
    'IdentificationParser',
    'TableImporter',
    'SimpleTableImporter',
    'LargeCSVImporter',
    'ColumnRenames',
    'PowerNovo2Importer',
    'MaxQuantEvidenceParser'
]
```

### 6.3 Инициализация registry в точке входа

**Примечание:** Файл `main.py` будет создан в этапе 3.2, но здесь показываем как будет использоваться registry:

```python
# main.py (пример использования)
import api.inputs.spectra  # Triggers parser registration
import api.inputs.peptides  # Triggers parser registration
from api.inputs.registry import registry

# Now registry is populated with all available parsers
print("Available spectral parsers:", list(registry.get_spectra_parsers().keys()))
print("Available identification parsers:", list(registry.get_identification_parsers().keys()))
```

---

## 7. Исправление ошибок в коде

### 7.1 Исправление `api/spectra/plot_matches.py`

**Файл:** `api/spectra/plot_matches.py`

```python
from dataclasses import dataclass
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def get_ion_type_color(ion_type: str) -> str:
    """
    Get color for ion type.
    
    Args:
        ion_type: Ion type ('a', 'b', 'c', 'x', 'y', 'z')
        
    Returns:
        Color name or hex code
    """
    color_map = {
        'a': 'green',
        'b': 'blue',
        'c': 'cyan',
        'x': 'orange',
        'y': 'red',
        'z': 'purple'
    }
    return color_map.get(ion_type, 'gray')


def generate_spectrum_plot(
    headers: str | list[str],
    data: pd.DataFrame | list[pd.DataFrame],
    font_size: int = 25
) -> go.Figure:
    """
    Generate spectrum plot with ion annotations.
    
    Args:
        headers: Title(s) for subplot(s)
        data: DataFrame(s) with columns:
            - mz: float
            - intensity: float
            - ion_type: str | None
            - label: str | None (annotation text)
        font_size: Font size for labels
        
    Returns:
        Plotly Figure object
    """
    # Normalize inputs to lists
    if isinstance(headers, str):
        headers = [headers]
    if isinstance(data, pd.DataFrame):
        data = [data]
    
    num_plots = len(data)
    
    # Pad headers if needed
    if len(headers) < num_plots:
        headers = headers + [''] * (num_plots - len(headers))
    
    # Create subplots
    fig = make_subplots(
        rows=num_plots,
        cols=1,
        subplot_titles=headers,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[1.0 / num_plots] * num_plots
    )
    
    # Plot each spectrum
    for row_no, df, header in zip(range(1, num_plots + 1), data, headers):
        # Add bars for each peak
        for _, row in df.iterrows():
            # Determine color based on ion match
            if pd.notna(row.get('ion_type')):
                color = get_ion_type_color(row['ion_type'])
            else:
                color = 'lightgray'
            
            # Add bar trace
            fig.add_trace(
                go.Bar(
                    x=[row['mz']],
                    y=[row['intensity']],
                    marker=dict(
                        color='lightgray',
                        line=dict(color=color, width=2)
                    ),
                    showlegend=False,
                    hovertemplate=(
                        f"m/z: {row['mz']:.2f}<br>"
                        f"Intensity: {row['intensity']:.0f}"
                        "<extra></extra>"
                    )
                ),
                row=row_no,
                col=1
            )
        
        # Add annotations for matched ions
        matched_ions = df[df['ion_type'].notna()]
        for _, row in matched_ions.iterrows():
            fig.add_annotation(
                x=row['mz'],
                y=row['intensity'],
                text=row.get('label', ''),
                showarrow=False,
                yshift=10,
                font=dict(color=get_ion_type_color(row['ion_type'])),
                row=row_no,
                col=1
            )
    
    # Update axes
    fig.update_xaxes(
        title_text='m/z',
        row=num_plots,
        col=1,
        title_font=dict(size=font_size),
        tickfont=dict(size=font_size)
    )
    
    for i in range(1, num_plots + 1):
        fig.update_yaxes(
            title_text='Intensity',
            row=i,
            col=1,
            title_font=dict(size=font_size),
            tickfont=dict(size=font_size)
        )
    
    return fig
```

### 7.2 Исправление `api/spectra/ion_match.py`

**Файл:** `api/spectra/ion_match.py`

```python
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd
from peptacular.fragmentation import Fragmenter, Fragment
from peptacular.score import (
    get_fragment_matches,
    FragmentMatch,
    get_matched_intensity_percentage
)


@dataclass
class IonMatchParameters:
    """
    Parameters for global ion matching.
    
    Attributes:
        ions: Ion types to match (e.g., ['b', 'y'])
        tolerance: Tolerance for m/z matching (in Th)
        mode: Match selection mode
        water_loss: Include water loss ions
        ammonia_loss: Include ammonia loss ions
    """
    ions: list[Literal['a', 'b', 'c', 'x', 'y', 'z']] | None = None
    tolerance: float = 0.05  # Th tolerance
    mode: Literal['all', 'closest', 'largest'] = 'largest'
    water_loss: bool = True
    ammonia_loss: bool = True


@dataclass
class MatchResult:
    """
    Result of ion matching.
    
    Attributes:
        parameters: Parameters used for matching
        fragments: Generated theoretical fragments
        fragment_matches: Matched fragments with experimental peaks
        intensity_percent: Percentage of total intensity matched
    """
    parameters: IonMatchParameters
    fragments: list[Fragment]
    fragment_matches: list[FragmentMatch]
    intensity_percent: float


def match_predictions(
    params: IonMatchParameters,
    mz: list[float],
    intensity: list[float],
    charges: list[int] | int,
    sequence: str
) -> MatchResult:
    """
    Match theoretical fragments to experimental spectrum.
    
    Args:
        params: Ion matching parameters
        mz: List of experimental m/z values
        intensity: List of experimental intensities
        charges: Charge state(s) for fragment calculation
        sequence: Peptide sequence (ProForma notation)
        
    Returns:
        MatchResult with matched fragments and statistics
    """
    if params.ions is None:
        params.ions = ['b', 'y']
    
    # Generate theoretical fragments
    frags = Fragmenter(sequence).fragment(
        params.ions,
        charges,
        water_loss=params.water_loss,
        ammonia_loss=params.ammonia_loss,
    )
    
    # Match experimental peaks to theoretical fragments
    matches = get_fragment_matches(
        frags,
        mz,
        intensity,
        tolerance_type='th',
        tolerance_value=params.tolerance,
        mode=params.mode,
    )
    
    # Calculate coverage
    coverage = get_matched_intensity_percentage(
        fragment_matches=matches,
        intensities=intensity
    )
    
    return MatchResult(
        parameters=params,
        fragments=frags,
        fragment_matches=matches,
        intensity_percent=coverage,
    )


def get_matches_dataframe(
    match_result: MatchResult,
    mz: list[float],
    intensity: list[float]
) -> pd.DataFrame:
    """
    Create DataFrame from match result for plotting.
    
    Joins experimental spectrum data with matched fragments.
    
    Args:
        match_result: Result from match_predictions()
        mz: List of experimental m/z values
        intensity: List of experimental intensities
        
    Returns:
        DataFrame with columns:
            - mz: float
            - intensity: float
            - ion_type: str | None (e.g., 'b', 'y')
            - label: str | None (e.g., 'b5-H2O')
            - frag_seq: str | None (fragment sequence)
            - theor_mz: float | None (theoretical m/z)
    """
    # Create experimental data frame
    exp_df = pd.DataFrame({
        'mz': mz,
        'intensity': intensity
    })
    
    if not match_result.fragment_matches:
        # No matches - return experimental data with empty match columns
        exp_df['ion_type'] = None
        exp_df['label'] = None
        exp_df['frag_seq'] = None
        exp_df['theor_mz'] = None
        return exp_df
    
    # Build match data
    match_data = []
    for match in match_result.fragment_matches:
        # Format charge
        charge_str = f'+{match.fragment.charge}' if match.fragment.charge > 1 else ''
        
        # Ion position
        ion_pos = match.fragment.end - match.fragment.start
        
        # Loss label
        loss_value = match.fragment.loss
        if abs(loss_value) < 0.01:
            loss_label = ''
        elif abs(loss_value - (-17.02655)) < 0.01:
            loss_label = '-NH3'
        elif abs(loss_value - (-18.01056)) < 0.01:
            loss_label = '-H2O'
        else:
            loss_label = f'{loss_value:+.2f}'
        
        match_data.append({
            'mz': match.mz,
            'ion_type': match.fragment.ion_type,
            'label': f'{match.fragment.ion_type}{ion_pos}{loss_label}{charge_str}',
            'frag_seq': match.fragment.sequence,
            'theor_mz': match.fragment.mz,
        })
    
    # Create matches DataFrame and merge with experimental data
    matches_df = pd.DataFrame(match_data)
    result = pd.merge(
        exp_df,
        matches_df,
        how='left',
        on='mz'
    )
    
    return result
```

### 7.3 Завершение `PowerNovo2.py`

**Файл:** `api/inputs/peptides/PowerNovo2.py`

```python
"""PowerNovo2 identification parser."""

import pandas as pd
from .table_importer import SimpleTableImporter, ColumnRenames


# Column mapping for PowerNovo2 output
renames = ColumnRenames(
    seq_no='SPECTRUM_ID',  # или другое название колонки с номером спектра
    sequence='PEPTIDE',
    canonical_sequence='CANONICAL SEQ.',
    ppm='PPM DIFFERENCE',
    score='SCORE',
    positional_scores='POSITIONAL SCORES'
)


class PowerNovo2Importer(SimpleTableImporter):
    """
    Parser for PowerNovo2 identification files.
    
    PowerNovo2 outputs CSV files with de novo sequencing results.
    """
    
    separator = ','
    renames = renames
    
    def transform_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform PowerNovo2-specific data.
        
        Converts positional scores from space-separated string to list.
        """
        if 'POSITIONAL SCORES' in df.columns:
            df['POSITIONAL SCORES'] = df['POSITIONAL SCORES'].apply(
                lambda x: [float(s) for s in x.split()] if pd.notna(x) else None
            )
        return df
```

**Примечание:** Необходимо уточнить у разработчика точные названия колонок в выходном файле PowerNovo2.

_Ответ разработчика:_ Колонки и их мэппинг указаны в renames, это общая логика работы SimpleTableImporter, реализованная в базовом классе после transform_df

---

## 8. Документация

### 8.1 Структура документации

Создать следующие файлы документации:

1. **`docs/api/IMPORTERS.md`** - документация по парсерам
   - Базовые классы (`BaseImporter`, `SpectralDataParser`, `IdentificationParser`)
   - Система регистрации (`InputTypesRegistry`)
   - Создание собственных парсеров
   - Примеры использования

2. **`docs/api/SPECTRA_PROCESSING.md`** - документация по обработке спектров
   - `api/spectra/ion_match.py` - сопоставление ионов
   - `api/spectra/plot_matches.py` - визуализация
   - Примеры использования
   - Описание параметров и результатов

3. **`docs/technical/STAGE3_1_CHANGES.md`** - техническое описание изменений
   - Обоснование изменений
   - Миграция с предыдущей версии
   - Breaking changes
   - Новые возможности

### 8.2 Обновление существующей документации

Обновить следующие файлы:

1. **`docs/api/PROJECT_API.md`**
   - Уточнить описание `intensity` vs `intensity_array`
   - Добавить `get_spectra_mapping()`
   - Обновить примеры использования

2. **`docs/MASTER_SPEC.md`**
   - Отметить выполнение этапа 3.1

---

## 9. Порядок выполнения (Act Phase)

### Шаг 1: Исправление багов (высокий приоритет)
1. ✅ Исправить `api/spectra/plot_matches.py`
2. ✅ Исправить `api/spectra/ion_match.py`
3. ✅ Завершить `api/inputs/peptides/PowerNovo2.py`

### Шаг 2: Изменения в базовых классах
1. ✅ Обновить `api/inputs/base.py` - опциональная metadata
2. ✅ Обновить `api/inputs/spectra/base.py` - реализация metadata
3. ✅ Обновить `api/inputs/spectra/mgf.py` - add_metadata()
4. ✅ Обновить `api/inputs/peptides/base.py` - удалить resolve_spectrum_id
5. ✅ Обновить `api/inputs/peptides/table_importer.py` - новый ColumnRenames

### Шаг 3: Обновление конкретных парсеров
1. ✅ Обновить `api/inputs/peptides/PowerNovo2.py`
2. ✅ Обновить `api/inputs/peptides/MQ_Evidences.py`

### Шаг 4: Изменения в Project
1. ✅ Исправить `Project.add_spectra_batch()` - убрать расчет intensity
2. ✅ Добавить `Project.get_spectra_mapping()`

### Шаг 5: Система регистрации
1. ✅ Обновить `api/inputs/registry.py`
2. ✅ Добавить регистрацию в `api/inputs/spectra/__init__.py`
3. ✅ Добавить регистрацию в `api/inputs/peptides/__init__.py`

### Шаг 6: Документация
1. ✅ Создать `docs/api/IMPORTERS.md`
2. ✅ Создать `docs/api/SPECTRA_PROCESSING.md`
3. ✅ Создать `docs/technical/STAGE3_1_CHANGES.md`
4. ✅ Обновить `docs/api/PROJECT_API.md`

---

## 10. Тестирование

После внесения изменений необходимо:

1. Проверить что существующий тест `test_stage1.py` проходит (могут потребоваться минорные правки)
2. Вручную протестировать:
   - Парсинг MGF файла
   - Парсинг файлов идентификации
   - Маппинг спектров через `get_spectra_mapping()`
   - Регистрацию парсеров
3. Тестовые данные предоставит разработчик

---

## 11. Breaking Changes

### Для пользователей API:

1. **`SpectralDataParser.get_total_spectra_count()`** - удален
   - **Миграция:** Использовать `len(list(await parser.parse_batch()))` если нужно узнать количество

2. **`IdentificationParser.__init__()`** - изменена сигнатура
   - **Было:** `__init__(file_path, tool_id, spectra_file_id, ident_file_id, project)`
   - **Стало:** `__init__(file_path)`
   - **Миграция:** Маппинг спектров выполняется вручную через `Project.get_spectra_mapping()`

3. **`IdentificationParser.resolve_spectrum_id()`** - удален
   - **Миграция:** Использовать `Project.get_spectra_mapping()` и `pd.merge()`

4. **`ColumnRenames.spectra_id`** - удален
   - **Миграция:** Использовать `scans` или `seq_no`

5. **`Project.add_spectra_batch()`** - не вычисляет intensity автоматически
   - **Миграция:** Явно передавать значение `intensity` в DataFrame если нужно

---

## 12. Новые возможности

1. ✅ Автоматическая metadata для всех файлов (размер, даты)
2. ✅ Гибкая система маппинга спектров через `get_spectra_mapping()`
3. ✅ Независимые от проекта парсеры (проще тестировать)
4. ✅ Централизованная регистрация парсеров
5. ✅ Подготовка к системе плагинов
6. ✅ Поддержка белковых идентификаций в одном файле (заложена)