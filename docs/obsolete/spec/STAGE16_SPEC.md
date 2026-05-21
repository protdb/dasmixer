# STAGE 16 — Спецификация: Доработки импорта данных

**Дата:** Апрель 2026  
**Версия приложения:** 0.2.0 → **0.3.0**  
**Версия схемы проекта:** 0.2.0 → **0.3.0**  
**min_supported:** 0.1.0 (не меняется)

---

## Содержание

1. [Обзор изменений](#1-обзор-изменений)
2. [Задача 1 — Версионирование (0.3.0)](#2-задача-1--версионирование-030)
3. [Задача 2 — Миграция БД 0.3.0](#3-задача-2--миграция-бд-030)
4. [Задача 3 — Поле `src_file_protein_id` в `identification`](#4-задача-3--поле-src_file_protein_id-в-identification)
5. [Задача 4 — Рефакторинг `IdentificationParser`](#5-задача-4--рефакторинг-identificationparser)
6. [Задача 5 — Рефакторинг `SimpleTableImporter`](#6-задача-5--рефакторинг-simpletableimporter)
7. [Задача 6 — Обновление `IdentificationMixin`](#7-задача-6--обновление-identificationmixin)
8. [Задача 7 — Обновление `import_handlers.py`](#8-задача-7--обновление-import_handlerspy)
9. [Задача 8 — Поддержка stacked-файлов в `identification_file`](#9-задача-8--поддержка-stacked-файлов-в-identification_file)
10. [Задача 9 — Stacked-парсер: `IdentificationParser`](#10-задача-9--stacked-парсер-identificationparser)
11. [Задача 10 — Stacked MaxQuant: `MQ_Evidences.py`](#11-задача-10--stacked-maxquant-mq_evidencespy)
12. [Задача 11 — UI: флаги белков в `ImportSingleDialog` / `ImportPatternDialog`](#12-задача-11--ui-флаги-белков-в-importsingledialogiport_patterndialogpy)
13. [Задача 12 — UI: `ImportModeDialog` — кнопка stacked](#13-задача-12--ui-importmodedialog--кнопка-stacked)
14. [Задача 13 — UI: `ImportStackedDialog` (новый файл)](#14-задача-13--ui-importstackeddialog-новый-файл)
15. [Задача 14 — UI: `samples_tab.py` — подключение stacked](#15-задача-14--ui-samples_tabpy--подключение-stacked)
16. [Задача 15 — Логика белков в `protein_map.py`](#16-задача-15--логика-белков-в-protein_mappy)
17. [Итоговая таблица файлов](#17-итоговая-таблица-файлов)
18. [Зависимости и порядок выполнения](#18-зависимости-и-порядок-выполнения)

---

## 1. Обзор изменений

Этап включает три независимые функциональные ветки:

| Ветка | Задачи | Суть |
|---|---|---|
| **Белки из файла идентификаций** | 1–8, 11, 15 | Парсер собирает `Protein`-объекты; при сохранении в БД белки записываются с `ON CONFLICT DO NOTHING`; добавлено поле `src_file_protein_id`; флаги в UI-диалогах |
| **Stacked-файлы** | 1–2, 8–10, 12–14 | Один файл идентификаций на несколько образцов; новые поля в `identification_file`; новый диалог; поддержка MaxQuant |
| **Версионирование и миграция** | 1–2 | `APP_VERSION` и `PROJECT_VERSION` → 0.3.0; SQL-миграция |

---

## 2. Задача 1 — Версионирование (0.3.0)

### Файлы

| Файл | Изменение |
|---|---|
| `dasmixer/versions.py` | `APP_VERSION = "0.3.0"`, `PROJECT_VERSION = "0.3.0"` |
| `pyproject.toml` | `version = "0.3.0"` |

### Детали

```python
# dasmixer/versions.py
APP_VERSION = "0.3.0"
PROJECT_VERSION = "0.3.0"
MIN_SUPPORTED_PROJECT_VERSION = "0.1.0"  # не меняется
```

`pyproject.toml`: обновить строку `version = "0.2.0"` → `version = "0.3.0"`.

> **Важно:** `MIN_SUPPORTED_PROJECT_VERSION` остаётся `"0.1.0"`. Все три существующие версии (0.1.0, 0.2.0) мигрируют цепочкой.

---

## 3. Задача 2 — Миграция БД 0.3.0

### Файлы

| Файл | Изменение |
|---|---|
| `dasmixer/api/project/migrations.py` | Добавить новую запись в `MIGRATIONS` |
| `dasmixer/api/project/schema.py` | Добавить новые поля в `CREATE TABLE identification` и `CREATE TABLE identification_file` |

### SQL миграции (добавить в `MIGRATIONS`)

```python
{
    "version": "0.3.0",
    "sql": """
        ALTER TABLE identification ADD COLUMN src_file_protein_id TEXT;
        ALTER TABLE identification_file ADD COLUMN selection_field TEXT;
        ALTER TABLE identification_file ADD COLUMN selection_field_value TEXT;
    """,
},
```

### Обновление `schema.py`

**Таблица `identification`** — добавить поле после `isotope_offset`:

```sql
src_file_protein_id TEXT,  -- protein ID from source identification file (nullable)
```

Полный DDL таблицы `identification` после изменения:

```sql
CREATE TABLE IF NOT EXISTS identification (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spectre_id INTEGER NOT NULL,
    tool_id INTEGER NOT NULL,
    ident_file_id INTEGER NOT NULL,
    is_preferred INTEGER NOT NULL DEFAULT 0,
    sequence TEXT NOT NULL,
    canonical_sequence TEXT NOT NULL,
    ppm REAL,
    theor_mass REAL,
    score REAL,
    positional_scores TEXT,
    intensity_coverage REAL,
    ions_matched INTEGER,
    ion_match_type TEXT,
    top_peaks_covered INTEGER,
    override_charge INTEGER,
    source_sequence TEXT,
    isotope_offset INTEGER,
    src_file_protein_id TEXT,  -- protein ID from source file; may contain multiple IDs separated by ";"
    FOREIGN KEY (spectre_id) REFERENCES spectre(id) ON DELETE CASCADE,
    FOREIGN KEY (tool_id) REFERENCES tool(id) ON DELETE CASCADE,
    FOREIGN KEY (ident_file_id) REFERENCES identification_file(id) ON DELETE CASCADE
);
```

**Таблица `identification_file`** — добавить поля после `file_path`:

```sql
selection_field TEXT,        -- column name used to filter stacked file (nullable)
selection_field_value TEXT,  -- value of selection_field for this record (nullable)
```

Полный DDL таблицы `identification_file` после изменения:

```sql
CREATE TABLE IF NOT EXISTS identification_file (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    spectre_file_id INTEGER NOT NULL,
    tool_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    selection_field TEXT,        -- column name used to filter stacked file (nullable)
    selection_field_value TEXT,  -- value of selection_field for this record (nullable)
    FOREIGN KEY (spectre_file_id) REFERENCES spectre_file(id) ON DELETE CASCADE,
    FOREIGN KEY (tool_id) REFERENCES tool(id) ON DELETE CASCADE
);
```

> **Примечание:** `CREATE TABLE IF NOT EXISTS` в `schema.py` не требует отдельного `ALTER TABLE` при создании нового проекта — новые поля уже будут в DDL. Миграция нужна только для существующих проектов версий 0.1.0 и 0.2.0.

---

## 4. Задача 3 — Поле `src_file_protein_id` в `identification`

### Файлы

| Файл | Изменение |
|---|---|
| `dasmixer/api/project/mixins/identification_mixin.py` | Обновить `add_identifications_batch`, `get_identifications` |

### 4.1 `add_identifications_batch`

Добавить поддержку нового столбца `src_file_protein_id`. Он **опционален** — если колонка отсутствует в DataFrame, пишем `NULL`.

```python
# В rows_to_insert изменить кортеж:
rows_to_insert.append((
    int(row['spectre_id']),
    int(row['tool_id']),
    int(row['ident_file_id']),
    1 if row.get('is_preferred', False) else 0,
    row['sequence'],
    row['canonical_sequence'],
    float(row['ppm']) if row.get('ppm') is not None else None,
    float(row['theor_mass']) if row.get('theor_mass') is not None else None,
    float(row['score']) if row.get('score') is not None else None,
    positional_scores_json,
    float(row['intensity_coverage']) if row.get('intensity_coverage') is not None else None,
    str(row['src_file_protein_id']) if row.get('src_file_protein_id') is not None else None,  # NEW
))
```

SQL INSERT обновить:

```sql
INSERT INTO identification 
   (spectre_id, tool_id, ident_file_id, is_preferred, sequence, canonical_sequence,
    ppm, theor_mass, score, positional_scores, intensity_coverage, src_file_protein_id)
   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

### 4.2 `get_identifications`

Добавить `i.src_file_protein_id` в SELECT:

```sql
SELECT
    i.id, i.spectre_id, i.tool_id, i.ident_file_id, i.is_preferred,
    i.sequence, i.canonical_sequence,
    i.ppm, i.theor_mass, i.score, i.positional_scores,
    i.intensity_coverage, i.ions_matched, i.ion_match_type,
    i.top_peaks_covered, i.override_charge, i.source_sequence,
    i.isotope_offset, i.src_file_protein_id,       -- NEW
    s.title as spectrum_title, s.pepmass, s.rt, s.charge,
    t.name as tool_name, t.parser as tool_parser,
    sf.sample_id, sam.name as sample_name
FROM identification i
...
```

### 4.3 `add_identification_file` — расширение для stacked

Метод `add_identification_file` должен принять новые опциональные параметры:

```python
async def add_identification_file(
    self,
    spectra_file_id: int,
    tool_id: int,
    file_path: str,
    selection_field: str | None = None,      # NEW
    selection_field_value: str | None = None, # NEW
) -> int:
```

SQL INSERT обновить:

```sql
INSERT INTO identification_file 
    (spectre_file_id, tool_id, file_path, selection_field, selection_field_value)
    VALUES (?, ?, ?, ?, ?)
```

---

## 5. Задача 4 — Рефакторинг `IdentificationParser`

### Файл

`dasmixer/api/inputs/peptides/base.py`

### 5.1 Новые атрибуты класса

```python
class IdentificationParser(BaseImporter):
    """..."""
    
    # Existing
    spectra_id_field: str = 'seq_no'
    
    # NEW: Whether this parser can collect protein data from the identification file.
    # Subclasses that can provide protein IDs must set this to True.
    contain_proteins: bool = False
    
    # NEW: Whether this parser supports stacked files (one file — multiple samples).
    # Subclasses that support stacked import must set this to True.
    can_import_stacked: bool = False
    
    # NEW: Column name used to split stacked file by sample.
    # Set in subclass if can_import_stacked = True.
    sample_id_column: str | None = None
```

### 5.2 Новые параметры `__init__`

```python
def __init__(
    self,
    file_path: str,
    collect_proteins: bool = False,
    is_uniprot_proteins: bool = False,
):
    """
    Initialize identification parser.
    
    Args:
        file_path: Path to identification file.
        collect_proteins: If True and contain_proteins is True,
            proteins collected during parsing will be saved to the DB
            by the calling code (import_handlers). Has no effect if
            contain_proteins is False.
        is_uniprot_proteins: If True, all Protein objects collected during
            parsing will have is_uniprot=True set. Used when the
            identification file comes from a UniProt-based library search.
    """
    super().__init__(file_path)
    self.collect_proteins = collect_proteins
    self.is_uniprot_proteins = is_uniprot_proteins
    self._proteins: dict[str, Protein] = {}
```

Необходим импорт `Protein` из `dasmixer.api.project.dataclasses`:

```python
from dasmixer.api.project.dataclasses import Protein
```

### 5.3 Метод `get_sample_ids`

```python
async def get_sample_ids(self, override_column: str | None = None) -> list[str]:
    """
    Return the list of unique sample IDs present in the file.
    
    Used to populate the sample list in the stacked import dialog.
    The column to read from is determined by override_column (if provided),
    or self.sample_id_column.
    
    Args:
        override_column: If provided, overrides self.sample_id_column.
        
    Returns:
        Sorted list of unique sample ID strings.
        
    Raises:
        NotImplementedError: If can_import_stacked is False.
        ValueError: If the column is not found in the file.
    """
    raise NotImplementedError(
        "get_sample_ids() is only available for parsers with can_import_stacked=True"
    )
```

### 5.4 Сигнатура `parse_batch` — упрощение

Убрать второй элемент кортежа из `yield`. Новая сигнатура:

```python
@abstractmethod
async def parse_batch(
    self,
    batch_size: int = 1000
) -> AsyncIterator[pd.DataFrame]:
    """
    Parse identifications in batches.
    
    Yields:
        DataFrame with columns:
            - scans: int | None
            - seq_no: int | None  (at least one of scans/seq_no must be present)
            - sequence: str
            - canonical_sequence: str
            - ppm: float | None
            - theor_mass: float | None
            - score: float | None
            - positional_scores: dict | None
            - src_file_protein_id: str | None  (if contain_proteins=True)
            - sample_id: str | None  (if can_import_stacked=True)
        
    Note:
        Protein data is NOT yielded directly. Instead, subclasses accumulate
        Protein objects in self._proteins during iteration. After parse_batch
        completes, the caller reads self._proteins to persist proteins to DB.
        
        sample_id column is ignored by the calling code unless
        can_import_stacked=True is set on the parser.
        
    Raises:
        ValueError: If neither scans nor seq_no columns are present.
    """
    pass
```

### 5.5 Свойство `proteins`

```python
@property
def proteins(self) -> dict[str, 'Protein']:
    """
    Return collected proteins dict (protein_id -> Protein).
    
    Available after parse_batch iteration is complete.
    Contains data only if contain_proteins=True and the file had protein data.
    """
    return self._proteins
```

---

## 6. Задача 5 — Рефакторинг `SimpleTableImporter`

### Файл

`dasmixer/api/inputs/peptides/table_importer.py`

### 6.1 `ColumnRenames` — новое поле

```python
@dataclass
class ColumnRenames:
    scans: str | None = None
    seq_no: str | None = None
    sequence: str = ''
    canonical_sequence: str | None = None
    score: str | None = None
    positional_scores: str | None = None
    ppm: str | None = None
    theor_mass: str | None = None
    src_file_protein_id: str | None = None  # NEW: source column for protein ID
```

### 6.2 `SimpleTableImporter` — новый метод `get_proteins`

```python
def get_proteins(self, df: pd.DataFrame) -> dict[str, 'Protein'] | None:
    """
    Extract protein objects from a batch DataFrame.
    
    Called for each batch during parse_batch. If this importer's
    ColumnRenames does not define src_file_protein_id, returns None
    (meaning: this importer cannot provide protein data at all).
    
    If src_file_protein_id is defined but the batch contains no non-null
    values in that column, returns an empty dict (proteins could be
    present in theory, but weren't in this batch).
    
    Subclasses may override this to provide richer Protein objects
    (e.g., with sequence, gene, name fields populated from additional
    columns in the source file).
    
    Args:
        df: Batch DataFrame with already-remapped column names
            (i.e., after remap_columns was applied).
            
    Returns:
        None  — if src_file_protein_id is not configured (contain_proteins=False scenario)
        {}    — if configured but no protein IDs found in this batch
        dict[str, Protein]  — mapping protein_id -> Protein for each unique ID found
    """
    if self.renames.src_file_protein_id is None:
        return None
    
    if 'src_file_protein_id' not in df.columns:
        return {}
    
    result: dict[str, Protein] = {}
    for raw_val in df['src_file_protein_id'].dropna().unique():
        raw_str = str(raw_val).strip()
        if not raw_str:
            continue
        # protein IDs may be semicolon-separated (e.g. "P12345;P67890")
        for pid in raw_str.split(';'):
            pid = pid.strip()
            if pid and pid not in result:
                result[pid] = Protein(
                    id=pid,
                    is_uniprot=self.is_uniprot_proteins,
                )
    return result
```

### 6.3 `SimpleTableImporter.parse_batch` — обновление

```python
async def parse_batch(
    self,
    batch_size: int = 1000
) -> AsyncIterator[pd.DataFrame]:
    """
    Parse table file in batches.
    
    Yields:
        DataFrame with standard column names (after remap_columns).
        If src_file_protein_id is configured, the DataFrame will contain
        that column. Protein objects are accumulated in self._proteins.
    """
    if self.sheets is None:
        self._read_table()
    
    if self.peptide_sheet_selector is None:
        sheet_df = self.get_sheet()
    else:
        sheet_df = self.get_sheet(**self.peptide_sheet_selector)
    
    data = self.remap_columns(self.transform_df(sheet_df))
    
    cursor = 0
    while cursor < len(data):
        batch = data[cursor:cursor + batch_size]
        
        # Collect proteins from this batch
        if self.contain_proteins:
            batch_proteins = self.get_proteins(batch)
            if batch_proteins is not None:
                self._proteins.update(batch_proteins)
        
        yield batch
        cursor += batch_size
```

### 6.4 `LargeCSVImporter.parse_batch` — обновление

Аналогичное изменение: убрать второй элемент из `yield`:

```python
# Было:
yield pd.DataFrame(lines), None

# Стало:
yield pd.DataFrame(lines)
```

И при финальном yield:

```python
# Было:
yield pd.DataFrame(lines), None

# Стало:
yield pd.DataFrame(lines)
```

> **Примечание:** В `LargeCSVImporter` поддержка `get_proteins` и `_proteins` не добавляется в рамках этого этапа. Парсеры на базе `LargeCSVImporter` могут переопределить `parse_batch` самостоятельно.

---

## 7. Задача 6 — Обновление `IdentificationMixin`

### Файл

`dasmixer/api/project/mixins/identification_mixin.py`

### Изменения

Метод `add_all_identifications` не используется в производственном коде (вся логика в `import_handlers.py`). Его **не трогаем**.

Единственное изменение — метод `add_identification_file` (уже описан в Задаче 3, §4.3).

---

## 8. Задача 7 — Обновление `import_handlers.py`

### Файл

`dasmixer/gui/views/tabs/samples/import_handlers.py`

Это **ключевое место** интеграции всей логики белков.

### 8.1 Обновление сигнатуры `import_identification_files`

```python
async def import_identification_files(
    self,
    file_list,
    tool_id: int,
    fixed_spectra_file_id: int = None,
    collect_proteins: bool = False,      # NEW
    is_uniprot_proteins: bool = False,   # NEW
):
```

### 8.2 Инициализация парсера с флагами

```python
# Было:
parser = parser_class(str(file_path))

# Стало:
parser = parser_class(
    str(file_path),
    collect_proteins=collect_proteins,
    is_uniprot_proteins=is_uniprot_proteins,
)
```

### 8.3 Обновление цикла парсинга (убрать tuple-распаковку)

```python
# Было:
async for batch_tuple in parser.parse_batch(batch_size=batch_size):
    batch = pd.merge(
        batch_tuple[0],   # <-- tuple
        ...
    )

# Стало:
async for batch in parser.parse_batch(batch_size=batch_size):
    batch = pd.merge(
        batch,            # <-- plain DataFrame
        pd.json_normalize(spectra_mapping),
        on=parser.spectra_id_field,
        how='inner'
    )
    batch['tool_id'] = tool.id
    batch['ident_file_id'] = ident_file_id
    
    if len(batch) > 0:
        await self.project.add_identifications_batch(batch)
        ...
```

### 8.4 Сохранение белков после завершения итерации

После завершения цикла `async for batch in parser.parse_batch(...)` добавить блок:

```python
# Save proteins collected during parsing
if collect_proteins and parser.contain_proteins and parser.proteins:
    proteins_df = pd.DataFrame([
        p.to_dict() for p in parser.proteins.values()
    ])
    # Применяем is_uniprot флаг (уже установлен в Protein при сборке,
    # но на всякий случай форсируем через флаг парсера)
    proteins_df['is_uniprot'] = 1 if is_uniprot_proteins else 0
    await self._save_proteins_batch(proteins_df)
    logger.info(f"Saved {len(parser.proteins)} proteins from identification file")
```

### 8.5 Новый приватный метод `_save_proteins_batch`

```python
async def _save_proteins_batch(self, proteins_df: pd.DataFrame) -> None:
    """
    Save proteins to DB using ON CONFLICT(id) DO NOTHING semantics.
    
    Unlike project.add_proteins_batch() which uses INSERT OR REPLACE,
    here we must NOT overwrite existing proteins (they may have richer
    data from FASTA import or UniProt enrichment).
    
    Args:
        proteins_df: DataFrame with columns matching Protein.to_dict() keys:
            id, is_uniprot, fasta_name, sequence, gene, name,
            taxon_id, organism_name
    """
    rows = []
    for _, row in proteins_df.iterrows():
        rows.append((
            str(row['id']),
            1 if row.get('is_uniprot', False) else 0,
            row.get('fasta_name'),
            row.get('sequence'),
            row.get('gene'),
            row.get('name'),
            row.get('taxon_id'),
            row.get('organism_name'),
        ))
    
    if rows:
        await self.project._executemany(
            """INSERT INTO protein
               (id, is_uniprot, fasta_name, sequence, gene, name, taxon_id, organism_name)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO NOTHING""",
            rows
        )
        await self.project.save()
```

> **Примечание по SQL:** `ON CONFLICT(id) DO NOTHING` гарантирует, что белки, уже загруженные из FASTA или обогащённые через UniProt, не будут перезаписаны бедными данными из файла идентификаций.

---

## 9. Задача 8 — Поддержка stacked-файлов в `identification_file`

Эта задача охватывает только изменения **схемы БД** и **`add_identification_file`**, которые уже полностью описаны в Задаче 2 (§3) и Задаче 3 (§4.3).

Повторно указывается здесь для ясности зависимостей: Задачи 9–14 зависят от этой задачи.

---

## 10. Задача 9 — Stacked-парсер: `IdentificationParser`

### Файл

`dasmixer/api/inputs/peptides/base.py`

Дополнительные изменения сверх Задачи 4 не требуются — атрибуты `can_import_stacked`, `sample_id_column` и метод-заглушка `get_sample_ids()` уже добавлены в Задаче 4.

Конкретная реализация `get_sample_ids()` создаётся только в `SimpleTableImporter`.

### `SimpleTableImporter.get_sample_ids`

```python
async def get_sample_ids(self, override_column: str | None = None) -> list[str]:
    """
    Return sorted list of unique sample IDs from the stacked file.
    
    Reads the column determined by override_column or self.sample_id_column,
    returns all unique non-null string values sorted alphabetically.
    
    Requires validate() to have been called (or at least _read_table()).
    Calls validate() internally if sheets are not yet loaded.
    
    Args:
        override_column: If provided, use this column name instead of
                        self.sample_id_column.
    
    Returns:
        Sorted list of unique sample ID strings.
        
    Raises:
        NotImplementedError: If can_import_stacked is False.
        ValueError: If the resolved column is not found in the file.
    """
    if not self.can_import_stacked:
        raise NotImplementedError(
            f"{self.__class__.__name__} does not support stacked import"
        )
    
    column = override_column or self.sample_id_column
    if column is None:
        raise ValueError("sample_id_column is not defined for this parser")
    
    if self.sheets is None:
        await self.validate()
    
    if self.peptide_sheet_selector is None:
        sheet_df = self.get_sheet()
    else:
        sheet_df = self.get_sheet(**self.peptide_sheet_selector)
    
    if column not in sheet_df.columns:
        raise ValueError(
            f"Column '{column}' not found in file. "
            f"Available columns: {list(sheet_df.columns)}"
        )
    
    unique_ids = sorted(
        str(v) for v in sheet_df[column].dropna().unique()
        if str(v).strip()
    )
    return unique_ids
```

---

## 11. Задача 10 — Stacked MaxQuant: `MQ_Evidences.py`

### Файл

`dasmixer/api/inputs/peptides/MQ_Evidences.py`

### Изменения в классе `MaxQuantEvidenceParser`

```python
class MaxQuantEvidenceParser(SimpleTableImporter):
    """
    Parser for MaxQuant evidence.txt files.
    ...
    Stacked import:
        MaxQuant evidence.txt typically covers multiple raw files (samples)
        in a single file. Use can_import_stacked=True and the "Raw file"
        column to split by sample.
    """
    
    separator = '\t'
    renames = renames
    spectra_id_field = 'scans'
    
    # NEW: stacked support
    can_import_stacked: bool = True
    sample_id_column: str = 'Raw file'
```

**Примечание:** MaxQuant не предоставляет белковые данные в `evidence.txt` (белки — в `proteinGroups.txt`), поэтому `contain_proteins` остаётся `False` (значение по умолчанию из базового класса).

---

## 12. Задача 11 — UI: флаги белков в `ImportSingleDialog` / `ImportPatternDialog`

### 12.1 Файл: `import_single_dialog.py`

Изменения в методе `_show_config_dialog`.

**Где добавлять:** В блок `else` (ветка `import_type == "identifications"`), после строки `tool = await self.project.get_tool(self.tool_id)`.

**Логика отображения чекбоксов:**
- Создаём экземпляр парсера только для проверки `contain_proteins` (без `file_path`, используем фиктивный или проверяем атрибут класса через `registry`).
- Проще: получить класс парсера из `registry` и проверить `parser_class.contain_proteins`.

```python
# В блоке else (identifications):
tool = await self.project.get_tool(self.tool_id)
parser_type_label = f"Format: {tool.parser}"
parser_dropdown = None
group_options = []

# NEW: check if parser supports proteins
from dasmixer.api.inputs.registry import registry as _registry
parser_class = _registry.get_parser(tool.parser, "identification")
parser_supports_proteins = getattr(parser_class, 'contain_proteins', False)

# Create protein checkboxes (only if parser supports proteins)
cb_collect_proteins = None
cb_is_uniprot = None
if parser_supports_proteins:
    cb_collect_proteins = ft.Checkbox(
        label="Import protein IDs from file",
        value=False,
    )
    cb_is_uniprot = ft.Checkbox(
        label="Proteins are UniProt IDs",
        value=False,
    )
```

**Добавление в `config_controls`:** После блока с `parser_type_label`, до файлов:

```python
if parser_supports_proteins:
    protein_section = ft.Container(
        content=ft.Column([
            ft.Text("Protein import options:", weight=ft.FontWeight.BOLD, size=12),
            cb_collect_proteins,
            cb_is_uniprot,
        ], spacing=5),
        padding=10,
        border=ft.border.all(1, ft.Colors.GREEN_300),
        border_radius=5,
        bgcolor=ft.Colors.GREEN_50,
    )
    config_controls.append(protein_section)
```

**Передача флагов в callback** — обновить `start_import`:

```python
async def start_import(e):
    config_dialog.open = False
    self.page.update()
    
    files_to_import = [(cfg['file_path'], cfg['sample_name'].value) for cfg in file_configs]
    
    if self.on_import_callback:
        if self.import_type == "spectra":
            ...
        else:
            collect = cb_collect_proteins.value if cb_collect_proteins else False
            is_uniprot = cb_is_uniprot.value if cb_is_uniprot else False
            await self.on_import_callback(
                files_to_import,
                self.tool_id,
                fixed_spectra_file_id=self.fixed_spectra_file_id,
                collect_proteins=collect,        # NEW
                is_uniprot_proteins=is_uniprot,  # NEW
            )
```

### 12.2 Файл: `import_pattern_dialog.py`

Аналогичное изменение: в метод `show()`, в блок `else` (identifications), добавить чекбоксы по той же логике.

**В `show()`** после строки `tool = await self.project.get_tool(self.tool_id) if self.tool_id else None`:

```python
# NEW: check if parser supports proteins
from dasmixer.api.inputs.registry import registry as _registry
_parser_class = _registry.get_parser(tool.parser, "identification") if tool else None
_parser_supports_proteins = getattr(_parser_class, 'contain_proteins', False)

cb_collect_proteins = None
cb_is_uniprot = None
if _parser_supports_proteins:
    cb_collect_proteins = ft.Checkbox(
        label="Import protein IDs from file",
        value=False,
    )
    cb_is_uniprot = ft.Checkbox(
        label="Proteins are UniProt IDs",
        value=False,
    )
```

**В контент диалога** добавить `protein_section` аналогично `ImportSingleDialog` — перед `ft.ElevatedButton("Preview Files", ...)`.

**В `_start_import`** обновить вызов `on_import_callback`:

```python
else:
    collect = cb_collect_proteins.value if cb_collect_proteins else False
    is_uniprot = cb_is_uniprot.value if cb_is_uniprot else False
    await self.on_import_callback(
        included_files,
        self.tool_id,
        collect_proteins=collect,        # NEW
        is_uniprot_proteins=is_uniprot,  # NEW
    )
```

---

## 13. Задача 12 — UI: `ImportModeDialog` — кнопка stacked

### Файл

`dasmixer/gui/views/tabs/samples/dialogs/import_mode_dialog.py`

### 13.1 Новый параметр `__init__`

```python
def __init__(
    self,
    project: Project,
    page: ft.Page,
    import_type: str,
    tool_id: int = None,
    on_single_files_callback=None,
    on_pattern_callback=None,
    on_stacked_callback=None,  # NEW
):
    ...
    self.on_stacked_callback = on_stacked_callback  # NEW
```

### 13.2 Отображение кнопки stacked

Кнопка «Import stacked file» показывается **только** при `import_type == "identifications"` и только если парсер инструмента поддерживает `can_import_stacked=True`.

В методе `show()`, после формирования `desc` и загрузки `tool`:

```python
# Check stacked support
show_stacked_btn = False
if self.import_type == "identifications" and self.tool_id:
    from dasmixer.api.inputs.registry import registry as _registry
    _tool = await self.project.get_tool(self.tool_id)
    if _tool:
        _parser_class = _registry.get_parser(_tool.parser, "identification")
        show_stacked_btn = getattr(_parser_class, 'can_import_stacked', False)
```

**Обновить `_content_col.controls`:**

```python
controls = [
    ft.Text("Choose import mode:", size=16, weight=ft.FontWeight.BOLD),
    ft.Text(desc, size=11, italic=True, color=ft.Colors.GREY_600),
    ft.Container(height=10),
    ft.ElevatedButton(
        content=ft.Text("Select individual files"),
        icon=ft.Icons.INSERT_DRIVE_FILE,
        on_click=lambda e: self.page.run_task(self._on_single_files, e),
        width=300,
    ),
    ft.Container(height=5),
    ft.ElevatedButton(
        content=ft.Text("Pattern matching from folder"),
        icon=ft.Icons.FOLDER_OPEN,
        on_click=lambda e: self.page.run_task(self._on_pattern, e),
        width=300,
    ),
]

if show_stacked_btn:
    controls += [
        ft.Container(height=5),
        ft.ElevatedButton(
            content=ft.Text("Import stacked file"),
            icon=ft.Icons.TABLE_VIEW,
            on_click=lambda e: self.page.run_task(self._on_stacked, e),
            width=300,
        ),
        ft.Container(height=5),
        ft.Text(
            "Stacked file contains identifications for multiple samples",
            size=11,
            italic=True,
            color=ft.Colors.GREY_600,
        ),
    ]

controls += [
    ft.Container(height=10),
    ft.Text(
        "Pattern matching allows automatic sample ID extraction from filenames",
        size=11,
        italic=True,
        color=ft.Colors.GREY_600,
    ),
]

self._content_col.controls = controls
```

### 13.3 Новый обработчик `_on_stacked`

```python
async def _on_stacked(self, e):
    """Handle stacked file import mode selection."""
    self._close()
    if self.on_stacked_callback:
        await self.on_stacked_callback()
```

---

## 14. Задача 13 — UI: `ImportStackedDialog` (новый файл)

### Файл

`dasmixer/gui/views/tabs/samples/dialogs/import_stacked_dialog.py`

### Полное описание класса

```python
"""Dialog for importing a stacked identification file (one file — multiple samples)."""

import flet as ft
from pathlib import Path
from typing import Optional
from dasmixer.api.project.project import Project
from dasmixer.api.inputs.registry import registry
from dasmixer.gui.utils import show_snack
from dasmixer.utils import logger


class ImportStackedDialog:
    """
    Dialog for importing a stacked identification file.
    
    Flow:
    1. User selects a file via FilePicker.
    2. User optionally overrides the "Sample field" (column name).
    3. User clicks "Get samples list" — dialog calls parser.get_sample_ids()
       and populates the sample list with sample_name <-> existing_sample mapping.
    4. User reviews and optionally edits sample name overrides.
    5. User clicks "Import" — for each matched sample, a separate
       identification_file record is created and identifications are imported
       with filtering by sample value.
    """
```

### 14.1 Конструктор

```python
def __init__(
    self,
    project: Project,
    page: ft.Page,
    tool_id: int,
    on_import_callback=None,
):
    self.project = project
    self.page = page
    self.tool_id = tool_id
    self.on_import_callback = on_import_callback
    
    self._file_path: Path | None = None
    self._parser_class = None
    self._tool = None
    self._sample_field_override: str | None = None
    
    # Controls
    self.dialog: ft.AlertDialog | None = None
    self._file_path_text: ft.Text | None = None
    self._sample_field_tf: ft.TextField | None = None
    self._samples_list: ft.ListView | None = None
    self._import_btn: ft.ElevatedButton | None = None
    
    # Sample entries: list of {'file_id': str, 'sample_name': ft.TextField, 'include': ft.Checkbox}
    self._sample_entries: list[dict] = []
```

### 14.2 Метод `show()`

```python
async def show(self):
    """Show the stacked import dialog."""
    # Step 1: FilePicker
    result = await ft.FilePicker().pick_files(
        dialog_title="Select Stacked Identification File",
        allow_multiple=False,
    )
    if not result or not result[0].path:
        return
    
    self._file_path = Path(result[0].path)
    
    # Load tool and parser class
    self._tool = await self.project.get_tool(self.tool_id)
    if not self._tool:
        show_snack(self.page, "Tool not found", ft.Colors.RED_400)
        self.page.update()
        return
    
    self._parser_class = registry.get_parser(self._tool.parser, "identification")
    
    # Default sample field
    default_field = getattr(self._parser_class, 'sample_id_column', '') or ''
    
    # Build dialog UI
    self._file_path_text = ft.Text(
        f"File: {self._file_path.name}",
        weight=ft.FontWeight.BOLD,
        size=12,
    )
    self._sample_field_tf = ft.TextField(
        label="Sample field (column name)",
        value=default_field,
        hint_text="e.g. Raw file",
        width=300,
    )
    self._samples_list = ft.ListView(spacing=3, height=260)
    self._import_btn = ft.ElevatedButton(
        content=ft.Text("Import"),
        icon=ft.Icons.DOWNLOAD,
        disabled=True,
        on_click=lambda e: self.page.run_task(self._start_import, e),
    )
    
    self.dialog = ft.AlertDialog(
        title=ft.Text(f"Import Stacked File — {self._tool.name}"),
        content=ft.Column(
            [
                self._file_path_text,
                ft.Container(height=8),
                ft.Row(
                    [
                        self._sample_field_tf,
                        ft.ElevatedButton(
                            content=ft.Text("Get samples list"),
                            icon=ft.Icons.REFRESH,
                            on_click=lambda e: self.page.run_task(self._load_samples, e),
                        ),
                    ],
                    spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.END,
                ),
                ft.Container(height=8),
                ft.Text("Match file sample IDs to project samples:", size=13),
                ft.Text(
                    "Values must match existing sample names exactly. "
                    "Edit manually if needed.",
                    size=11,
                    italic=True,
                    color=ft.Colors.GREY_600,
                ),
                ft.Container(
                    content=self._samples_list,
                    border=ft.border.all(1, ft.Colors.GREY_300),
                    border_radius=5,
                    padding=10,
                ),
            ],
            tight=True,
            width=650,
            scroll=ft.ScrollMode.AUTO,
        ),
        actions=[
            ft.TextButton("Cancel", on_click=self._close),
            self._import_btn,
        ],
    )
    self.page.overlay.append(self.dialog)
    self.dialog.open = True
    self.page.update()
```

### 14.3 Метод `_load_samples`

```python
async def _load_samples(self, e):
    """Load sample IDs from file and populate the matching list."""
    self._samples_list.controls.clear()
    self._samples_list.controls.append(
        ft.ProgressRing(width=24, height=24, stroke_width=3)
    )
    self._samples_list.update()
    
    try:
        override_col = self._sample_field_tf.value.strip() or None
        
        # Instantiate parser and get sample IDs
        parser = self._parser_class(str(self._file_path))
        sample_ids_in_file = await parser.get_sample_ids(override_column=override_col)
        
        if not sample_ids_in_file:
            self._samples_list.controls = [
                ft.Text("No samples found in file", italic=True, color=ft.Colors.GREY_600)
            ]
            self._samples_list.update()
            return
        
        # Get existing DB samples for comparison
        db_samples = await self.project.get_samples()
        db_sample_names = {s.name for s in db_samples}
        
        self._sample_entries.clear()
        self._samples_list.controls.clear()
        
        # Header row
        self._samples_list.controls.append(
            ft.Row(
                [
                    ft.Text("Include", size=11, width=60),
                    ft.Text("ID in file", size=11, width=200, weight=ft.FontWeight.BOLD),
                    ft.Text("Sample name in project", size=11, expand=True, weight=ft.FontWeight.BOLD),
                ],
                spacing=5,
            )
        )
        
        for file_sample_id in sample_ids_in_file:
            # Auto-match: exact name match
            matched = file_sample_id if file_sample_id in db_sample_names else ""
            
            include_cb = ft.Checkbox(value=bool(matched))
            sample_tf = ft.TextField(
                value=matched,
                hint_text="Project sample name",
                expand=True,
                border_color=ft.Colors.RED if not matched else None,
                on_change=lambda e, sid=file_sample_id: self._on_sample_name_change(sid, e),
            )
            
            entry = {
                'file_id': file_sample_id,
                'include': include_cb,
                'sample_name_tf': sample_tf,
            }
            self._sample_entries.append(entry)
            
            self._samples_list.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            include_cb,
                            ft.Text(file_sample_id, size=12, width=200),
                            sample_tf,
                        ],
                        spacing=5,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.padding.symmetric(vertical=2),
                )
            )
        
        self._update_import_btn_state()
        self._samples_list.update()
        
    except Exception as ex:
        logger.exception(ex)
        self._samples_list.controls = [
            ft.Text(f"Error: {ex}", color=ft.Colors.RED_400)
        ]
        self._samples_list.update()
        show_snack(self.page, f"Error loading samples: {ex}", ft.Colors.RED_400)
        self.page.update()
```

### 14.4 Вспомогательные методы

```python
def _on_sample_name_change(self, file_sample_id: str, e):
    for entry in self._sample_entries:
        if entry['file_id'] == file_sample_id:
            val = e.control.value or ""
            e.control.border_color = ft.Colors.RED if not val.strip() else None
            if e.control.page:
                e.control.update()
    self._update_import_btn_state()

def _update_import_btn_state(self):
    if self._import_btn is None:
        return
    has_valid = any(
        entry['include'].value and bool(entry['sample_name_tf'].value.strip())
        for entry in self._sample_entries
    )
    self._import_btn.disabled = not has_valid
    if self._import_btn.page:
        self._import_btn.update()

def _close(self, e=None):
    if self.dialog:
        self.dialog.open = False
    self.page.update()
```

### 14.5 Метод `_start_import`

```python
async def _start_import(self, e):
    """
    Start stacked import.
    
    For each included sample entry:
    1. Find the Sample in DB by name.
    2. Get its spectra files.
    3. Create a separate identification_file record with selection_field and
       selection_field_value.
    4. Import only rows matching that sample's file_id value.
    """
    self._close()
    
    if not self.on_import_callback:
        return
    
    override_col = self._sample_field_tf.value.strip() or None
    effective_field = override_col or getattr(self._parser_class, 'sample_id_column', None)
    
    # Build list of (file_path, project_sample_name, file_sample_id, selection_field)
    entries_to_import = [
        {
            'file_path': self._file_path,
            'project_sample_name': entry['sample_name_tf'].value.strip(),
            'file_sample_id': entry['file_id'],
            'selection_field': effective_field,
        }
        for entry in self._sample_entries
        if entry['include'].value and entry['sample_name_tf'].value.strip()
    ]
    
    await self.on_import_callback(
        entries_to_import,
        self.tool_id,
    )
```

---

## 15. Задача 14 — UI: `samples_tab.py` — подключение stacked

### Файл

`dasmixer/gui/views/tabs/samples/samples_tab.py`

### 15.1 Обновление `_show_import_identifications_dialog`

```python
async def _show_import_identifications_dialog(self, tool_id: int):
    """Show import mode selection for identifications."""
    dialog = ImportModeDialog(
        self.project,
        self.page,
        "identifications",
        tool_id=tool_id,
        on_single_files_callback=lambda: self._on_import_identifications_single(tool_id),
        on_pattern_callback=lambda: self._on_import_identifications_pattern(tool_id),
        on_stacked_callback=lambda: self._on_import_identifications_stacked(tool_id),  # NEW
    )
    await dialog.show()
```

### 15.2 Новый метод `_on_import_identifications_stacked`

```python
async def _on_import_identifications_stacked(self, tool_id: int):
    """Handle stacked file import for identifications."""
    from .dialogs.import_stacked_dialog import ImportStackedDialog
    dialog = ImportStackedDialog(
        self.project,
        self.page,
        tool_id=tool_id,
        on_import_callback=self.import_handlers.import_identification_files_stacked,
    )
    await dialog.show()
```

### 15.3 Новый метод в `ImportHandlers`

В `import_handlers.py` добавить метод `import_identification_files_stacked`:

```python
async def import_identification_files_stacked(
    self,
    entries: list[dict],
    tool_id: int,
):
    """
    Import identifications from a stacked file for multiple samples.
    
    Args:
        entries: list of dicts, each with:
            - file_path: Path
            - project_sample_name: str  (name of existing Sample in DB)
            - file_sample_id: str       (value in selection_field column)
            - selection_field: str | None
        tool_id: Tool ID
    """
    # Show progress dialog
    progress_text = ft.Text("Preparing stacked import...")
    progress_bar = ft.ProgressBar(value=0)
    progress_details = ft.Text("", size=11, color=ft.Colors.GREY_600)
    
    progress_dialog = ft.AlertDialog(
        title=ft.Text("Importing Stacked Identifications"),
        content=ft.Column([
            progress_text, progress_bar,
            ft.Container(height=5), progress_details
        ], tight=True, width=400),
        modal=True
    )
    self.page.overlay.append(progress_dialog)
    progress_dialog.open = True
    self.page.update()
    
    try:
        tool = await self.project.get_tool(tool_id)
        if not tool:
            raise ValueError(f"Tool id={tool_id} not found")
        
        parser_class = registry.get_parser(tool.parser, "identification")
        total = len(entries)
        total_identifications = 0
        
        for i, entry in enumerate(entries):
            file_path = entry['file_path']
            project_sample_name = entry['project_sample_name']
            file_sample_id = entry['file_sample_id']
            selection_field = entry['selection_field']
            
            progress_text.value = f"Processing {project_sample_name} ({i+1}/{total})..."
            progress_bar.value = i / total
            progress_text.update()
            progress_bar.update()
            
            # Find sample by name
            sample = await self.project.get_sample_by_name(project_sample_name)
            if not sample:
                raise ValueError(f"Sample '{project_sample_name}' not found in project")
            
            # Get spectra files for sample
            spectra_files = await self.project.get_spectra_files(sample_id=sample.id)
            if len(spectra_files) == 0:
                raise ValueError(f"No spectra files for sample '{project_sample_name}'")
            
            spectra_file_id = spectra_files.iloc[0]['id']
            
            # Create identification_file record with stacked metadata
            ident_file_id = await self.project.add_identification_file(
                spectra_file_id=int(spectra_file_id),
                tool_id=tool.id,
                file_path=str(file_path),
                selection_field=selection_field,
                selection_field_value=file_sample_id,
            )
            
            # Parse file, filter by file_sample_id
            parser = parser_class(str(file_path))
            is_valid = await parser.validate()
            if not is_valid:
                raise ValueError(f"Invalid file format: {file_path.name}")
            
            # Get spectra mapping
            spectra_mapping = await self.project.get_spectra_idlist(
                spectra_file_id, by=parser.spectra_id_field
            )
            
            effective_field = selection_field or getattr(parser_class, 'sample_id_column', None)
            
            batch_size = _config.identification_batch_size
            file_ident_count = 0
            
            async for batch in parser.parse_batch(batch_size=batch_size):
                # Filter: keep only rows matching this sample
                if effective_field and effective_field in batch.columns:
                    batch = batch[batch[effective_field].astype(str) == str(file_sample_id)]
                
                if len(batch) == 0:
                    continue
                
                # Drop sample_id column before merge (not needed in DB)
                if effective_field and effective_field in batch.columns:
                    batch = batch.drop(columns=[effective_field])
                
                merged = pd.merge(
                    batch,
                    pd.json_normalize(spectra_mapping),
                    on=parser.spectra_id_field,
                    how='inner',
                )
                merged['tool_id'] = tool.id
                merged['ident_file_id'] = ident_file_id
                
                if len(merged) > 0:
                    await self.project.add_identifications_batch(merged)
                    file_ident_count += len(merged)
                    total_identifications += len(merged)
                
                progress_details.value = f"{project_sample_name}: {file_ident_count} identifications..."
                progress_details.update()
        
        # Complete
        progress_bar.value = 1.0
        progress_text.value = "Import complete!"
        progress_details.value = f"Total: {total_identifications} identifications from {total} sample(s)"
        progress_text.update()
        progress_bar.update()
        progress_details.update()
        
        import asyncio
        await asyncio.sleep(1)
        progress_dialog.open = False
        self.page.update()
        
        show_snack(
            self.page,
            f"Successfully imported {total_identifications} identifications for {total} sample(s)",
            ft.Colors.GREEN_400
        )
        self.page.update()
        
        if self.on_complete_callback:
            await self.on_complete_callback()
    
    except Exception as ex:
        logger.exception(ex)
        progress_dialog.open = False
        self.page.update()
        show_snack(self.page, f"Import error: {str(ex)}", ft.Colors.RED_400)
        self.page.update()
```

---

## 16. Задача 15 — Логика белков в `protein_map.py`

### Файл

`dasmixer/api/calculations/peptides/protein_map.py`

### Новый параметр `use_src_protein_ids`

```python
async def map_proteins(
    project: Project,
    tool_settings: dict[int, dict],
    ion_params: dict,
    fragment_charges: list[int],
    seqfixer_params: dict,
    batch_size: int = 5000,
    sample_id: int | None = None,
    use_src_protein_ids: bool = False,   # NEW
) -> AsyncIterator[tuple[pd.DataFrame, int, int]]:
    """
    ...
    Args:
        use_src_protein_ids: If True, for identifications that have
            src_file_protein_id set, create exact-match peptide_match
            records directly (bypassing BLAST). BLAST is then only run
            for identifications without src_file_protein_id.
    ...
    """
```

### Логика при `use_src_protein_ids=True`

В начале каждого батча, **перед** формированием BLAST-запроса, выполнить предобработку:

```python
if use_src_protein_ids:
    # --- Step 1: handle identifications with src_file_protein_id ---
    has_src_protein = batch_data['src_file_protein_id'].notna() & \
                      (batch_data['src_file_protein_id'] != '')
    
    src_protein_rows = batch_data[has_src_protein]
    blast_rows = batch_data[~has_src_protein]  # Only these go to BLAST
    
    # Build exact-match results for src_protein rows
    for _, row in src_protein_rows.iterrows():
        ident_id = int(row['id'])
        raw_ids = str(row['src_file_protein_id'])
        protein_ids = [pid.strip() for pid in raw_ids.split(';') if pid.strip()]
        
        canon = str(row['canonical_sequence'])
        
        for protein_id in protein_ids:
            all_res.append({
                'protein_id': protein_id,
                'identification_id': ident_id,
                'matched_sequence': canon,
                'identity': 1.0,
                'unique_evidence': False,  # will be recomputed below
                'matched_ppm': _safe_float(row.get('ppm')),
                'matched_theor_mass': _safe_float(row.get('theor_mass')),
                'matched_coverage_percent': _safe_float(row.get('intensity_coverage')),
                'matched_peaks': _safe_int(row.get('ions_matched')),
                'matched_top_peaks': _safe_int(row.get('top_peaks_covered')),
                'matched_ion_type': _nan_to_none(row.get('ion_match_type')),
                'matched_sequence_modified': None,
                'substitution': False,
            })
    
    # Override batch_data to only include rows without src_file_protein_id
    batch_data = blast_rows
    
    if len(batch_data) == 0 and all_res:
        yield pd.json_normalize(all_res), len(all_res), tool_id
        all_res = []
        counter += batch_size
        continue
    # --- end Step 1 ---
```

> **Примечание:** `unique_evidence` для src_protein записей вычисляется не на этапе создания (неизвестно, сколько белков будет у данной идентификации в итоге), а проставляется `False`. При необходимости точного значения можно добавить пост-обработку, но в текущей архитектуре `unique_evidence` вычисляется как `value_counts == 1` по `id` в рамках батча, что будет корректно для BLAST-части. Для src_protein-части можно принять `False` как консервативное значение — это не влияет на основной пайплайн.

### Откуда передаётся `use_src_protein_ids`

Флаг должен передаваться из GUI action `protein_map_action.py` (или аналогичного action) на основе настройки в UI (существующая панель настроек protein mapping). Конкретная UI-кнопка/чекбокс для этого флага находится в пределах существующих настроек protein mapping — уточнить расположение на стороне разработчика. В рамках текущей спецификации фиксируется только API.

---

## 17. Итоговая таблица файлов

| № | Файл | Статус | Задачи |
|---|---|---|---|
| 1 | `dasmixer/versions.py` | Изменён | 1 |
| 2 | `pyproject.toml` | Изменён | 1 |
| 3 | `dasmixer/api/project/migrations.py` | Изменён | 2 |
| 4 | `dasmixer/api/project/schema.py` | Изменён | 2 |
| 5 | `dasmixer/api/project/mixins/identification_mixin.py` | Изменён | 3 |
| 6 | `dasmixer/api/inputs/peptides/base.py` | Изменён | 4, 9 |
| 7 | `dasmixer/api/inputs/peptides/table_importer.py` | Изменён | 5 |
| 8 | `dasmixer/api/inputs/peptides/MQ_Evidences.py` | Изменён | 10 |
| 9 | `dasmixer/gui/views/tabs/samples/import_handlers.py` | Изменён | 7, 14 |
| 10 | `dasmixer/gui/views/tabs/samples/dialogs/import_single_dialog.py` | Изменён | 11 |
| 11 | `dasmixer/gui/views/tabs/samples/dialogs/import_pattern_dialog.py` | Изменён | 11 |
| 12 | `dasmixer/gui/views/tabs/samples/dialogs/import_mode_dialog.py` | Изменён | 12 |
| 13 | `dasmixer/gui/views/tabs/samples/dialogs/import_stacked_dialog.py` | **Создан** | 13 |
| 14 | `dasmixer/gui/views/tabs/samples/samples_tab.py` | Изменён | 14 |
| 15 | `dasmixer/api/calculations/peptides/protein_map.py` | Изменён | 15 |

**Итого:** 1 новый файл, 14 изменяемых.

---

## 18. Зависимости и порядок выполнения

### Граф зависимостей

```
Задача 1 (versions)
    └── Задача 2 (migration SQL + schema)
            ├── Задача 3 (identification_mixin: новые поля)
            │       └── Задача 7 (import_handlers: основной pipeline белков)
            │               ├── Задача 11 (UI флаги белков в диалогах)
            │               └── Задача 14 (import_handlers: stacked method)
            │                       └── Задача 14-UI (samples_tab: подключение)
            └── Задача 8 (identification_file stacked fields) ← уже в Задаче 3
                    └── Задача 13 (ImportStackedDialog)
                            └── Задача 14-UI (samples_tab)

Задача 4 (base.py: IdentificationParser рефакторинг)
    ├── Задача 5 (table_importer: ColumnRenames + get_proteins)
    │       ├── Задача 7 (import_handlers: iterate без tuple)
    │       └── Задача 10 (MQ_Evidences: stacked attrs)
    └── Задача 9 (get_sample_ids в SimpleTableImporter)
            └── Задача 10 (MQ_Evidences: stacked attrs)
                    └── Задача 12 (ImportModeDialog: show stacked btn)
                            └── Задача 13 (ImportStackedDialog)

Задача 15 (protein_map: use_src_protein_ids)
    └── Задача 3 (нужен src_file_protein_id в get_identifications)
```

### Рекомендуемый порядок реализации

| Шаг | Задачи | Описание | Файлы |
|---|---|---|---|
| **1** | 1 | Поднять версии | `versions.py`, `pyproject.toml` |
| **2** | 2 | Миграция + схема | `migrations.py`, `schema.py` |
| **3** | 3 | `identification_mixin` — новые поля | `identification_mixin.py` |
| **4** | 4 | `IdentificationParser` рефакторинг | `base.py` |
| **5** | 5 | `SimpleTableImporter` — ColumnRenames, get_proteins, parse_batch | `table_importer.py` |
| **6** | 10 | MaxQuant stacked attrs | `MQ_Evidences.py` |
| **7** | 9 | `get_sample_ids` в `SimpleTableImporter` | `table_importer.py` ← тот же файл, что шаг 5 |
| **8** | 7 | `import_handlers` — основной pipeline | `import_handlers.py` |
| **9** | 11 | UI флаги белков в `ImportSingleDialog`, `ImportPatternDialog` | `import_single_dialog.py`, `import_pattern_dialog.py` |
| **10** | 12 | `ImportModeDialog` — кнопка stacked | `import_mode_dialog.py` |
| **11** | 13 | `ImportStackedDialog` (новый файл) | `import_stacked_dialog.py` |
| **12** | 14 | `import_handlers` stacked method + `samples_tab` подключение | `import_handlers.py` ← тот же файл, что шаг 8; `samples_tab.py` |
| **13** | 15 | `protein_map` — `use_src_protein_ids` | `protein_map.py` |

### Конфликты при параллельной работе над одним файлом

Следующие файлы затрагиваются в нескольких задачах — их нужно обрабатывать **последовательно**:

| Файл | Задачи | Правило |
|---|---|---|
| `base.py` | 4, 9 | Реализовать в одной итерации: сначала §4 (атрибуты + сигнатура), затем §9 (get_sample_ids в SimpleTableImporter) |
| `table_importer.py` | 5, 9 | Реализовать последовательно: сначала §5 (ColumnRenames, get_proteins, упрощение parse_batch), затем §9 (get_sample_ids метод) |
| `import_handlers.py` | 7, 14 | Реализовать последовательно: сначала §7 (основной pipeline с белками), затем §14 (stacked метод) |

---

## Приложение: SQL-запросы этапа

### A. Миграция 0.3.0

```sql
-- Файл: migrations.py, версия "0.3.0"
ALTER TABLE identification ADD COLUMN src_file_protein_id TEXT;
ALTER TABLE identification_file ADD COLUMN selection_field TEXT;
ALTER TABLE identification_file ADD COLUMN selection_field_value TEXT;
```

### B. Добавление идентификации с `src_file_protein_id`

```sql
-- Файл: identification_mixin.py, add_identifications_batch
INSERT INTO identification 
   (spectre_id, tool_id, ident_file_id, is_preferred, sequence, canonical_sequence,
    ppm, theor_mass, score, positional_scores, intensity_coverage, src_file_protein_id)
   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

### C. Добавление `identification_file` с stacked-полями

```sql
-- Файл: identification_mixin.py, add_identification_file
INSERT INTO identification_file 
    (spectre_file_id, tool_id, file_path, selection_field, selection_field_value)
    VALUES (?, ?, ?, ?, ?)
```

### D. Получение идентификаций с `src_file_protein_id`

```sql
-- Файл: identification_mixin.py, get_identifications
SELECT
    i.id, i.spectre_id, i.tool_id, i.ident_file_id, i.is_preferred,
    i.sequence, i.canonical_sequence,
    i.ppm, i.theor_mass, i.score, i.positional_scores,
    i.intensity_coverage, i.ions_matched, i.ion_match_type,
    i.top_peaks_covered, i.override_charge, i.source_sequence,
    i.isotope_offset, i.src_file_protein_id,
    s.title as spectrum_title, s.pepmass, s.rt, s.charge,
    t.name as tool_name, t.parser as tool_parser,
    sf.sample_id, sam.name as sample_name
FROM identification i
JOIN spectre s ON i.spectre_id = s.id
JOIN tool t ON i.tool_id = t.id
JOIN spectre_file sf ON s.spectre_file_id = sf.id
JOIN sample sam ON sf.sample_id = sam.id
-- [WHERE conditions as before]
```

### E. Сохранение белков из файла идентификаций (ON CONFLICT DO NOTHING)

```sql
-- Файл: import_handlers.py, _save_proteins_batch
INSERT INTO protein
   (id, is_uniprot, fasta_name, sequence, gene, name, taxon_id, organism_name)
   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO NOTHING
```

---

**Автор спецификации:** Requirements Agent  
**Дата:** Апрель 2026  
**На основе требований:** `docs/project/spec/STAGE16_Requirements.md`
