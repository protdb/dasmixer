# Этап 14 — Data Export: детальная спецификация

**Версия:** 1.0  
**Дата:** Апрель 2026  
**Источник требований:** `docs/project/spec/STAGE14_REQUIREMENTS.md`

---

## 0. Краткое описание

Этап добавляет вкладку **Export** в `ProjectView` (последняя вкладка, после Plots). Вкладка содержит четыре независимые секции: **System Data**, **Joined Data**, **Export MGF**, **Export MzTab**. Каждая секция инкапсулирует свою логику и форму выбора параметров. Всё тяжёлое I/O вынесено в `dasmixer/api/export/`.

---

## 1. Зависимости

### 1.1 Добавить в `pyproject.toml`

```toml
mztabwriter = { version = ">=0.1.0,<0.2.0", extras = ["pandas"] }
```

**Пакет:** `mztabwriter` (PyPI: https://pypi.org/project/mztabwriter/)  
**Extras `[pandas]`** нужны для методов `add_proteins_from_dataframe` / `add_psms_from_dataframe`.

### 1.2 Уже присутствующие зависимости (не менять)

| Назначение | Пакет |
|---|---|
| CSV/XLSX экспорт | `pandas` + `openpyxl` |
| MGF запись | `pyteomics` |
| Архивация | stdlib `gzip`, `zipfile` |

---

## 2. Структура файлов

```
dasmixer/
├── api/
│   └── export/
│       ├── __init__.py
│       ├── system_export.py      # System Data → CSV
│       ├── joined_export.py      # Joined Data → CSV / XLSX
│       ├── mgf_export.py         # Export MGF
│       └── mztab_export.py       # Export MzTab (использует mztabwriter)
├── gui/
│   └── views/
│       └── tabs/
│           └── export/
│               ├── __init__.py
│               ├── export_tab.py             # Корневой контейнер вкладки
│               ├── shared_state.py           # ExportTabState (сохранение введённых данных)
│               ├── system_section.py         # Секция System Data
│               ├── joined_section.py         # Секция Joined Data
│               ├── mgf_section.py            # Секция Export MGF
│               └── mztab_section.py          # Секция Export MzTab
```

---

## 3. Регистрация вкладки

В `dasmixer/gui/views/project_view.py`, в список `_TAB_DEFS`, добавить последним:

```python
("Export", ft.Icons.DOWNLOAD, "dasmixer.gui.views.tabs.export", "ExportTab"),
```

Вкладка **не является suspendable** (нет тяжёлых таблиц), поэтому не добавляется в список `_SUSPENDABLE_TABS`. При деактивации вкладки её контент **уничтожается** через механизм lazy loading, при активации — пересоздаётся; значения элементов управления восстанавливаются из `ExportTabState`.

---

## 4. `ExportTabState` (shared_state.py)

Синглтон-объект, хранящий последние введённые значения UI для каждой секции. Реализуется как простой `dataclass` или словарь, доступный через атрибут `_state` в `ExportTab`. Не персистируется между запусками приложения (только на время сессии).

```python
@dataclass
class ExportTabState:
    # System Data
    system_flags: dict[str, bool]  # {table_name: checked}

    # Joined Data
    joined_flags: dict[str, bool]  # {section_name: checked}
    joined_format: str             # "csv" | "xlsx"
    joined_one_per_sample: bool

    # Export MGF
    mgf_sample_ids: list[int]
    mgf_by: str                    # "all" | "all_preferred" | "preferred_by_tool"
    mgf_tool_id: int | None
    mgf_write_offset: bool
    mgf_write_spectra: bool
    mgf_write_seq: bool
    mgf_seq_type: str              # "canonical" | "modified"
    mgf_compression: str           # "gzip" | "zip_all" | "zip_each" | "none"

    # Export MzTab
    mztab_sample_ids: list[int]
    mztab_lfq_method: str          # "emPAI" | "iBAQ" | "NSAF" | "Top3"
    mztab_title: str
    mztab_description: str
```

---

## 5. Секция System Data

### 5.1 UI

```
┌─ System Data ─────────────────────────────────────────────────────┐
│  [Select All]  [Deselect All]                                      │
│  ☑ Samples           ☑ Subsets         ☑ Tools                    │
│  ☑ Spectra metadata  ☑ Identification file  ☑ Spectre file        │
│  ☑ Identification    ☑ Peptide match                               │
│  ☑ Protein identifications  ☑ Protein quantifications             │
│  ☑ Project settings                                               │
│                                                          [Export (CSV)] │
└───────────────────────────────────────────────────────────────────┘
```

**Кнопки Select All / Deselect All** — массово выставляют/снимают все чекбоксы.

### 5.2 Маппинг чекбоксов → таблицы БД

| Флаг UI | Таблица(ы) |
|---|---|
| Samples | `sample` |
| Subsets | `subset` |
| Tools | `tool` |
| Spectra metadata | `spectre` (без BLOB-колонок `mz_array`, `intensity_array`) |
| Identification file | `identification_file` |
| Spectre file | `spectre_file` |
| Identification | `identification` |
| Peptide match | `peptide_match` |
| Protein identifications | `protein_identification_result` |
| Protein quantifications | `protein_quantification_result` |
| Project settings | `project_settings` |

### 5.3 Логика экспорта (`system_export.py`)

```python
async def export_system_data(
    project: Project,
    flags: dict[str, bool],
    output_dir: str,
    timestamp: str,
) -> list[str]:
    """
    Возвращает список созданных файлов.
    Для каждого активного флага:
    1. Читает данные через QueryMixin.execute_query_df(query)
    2. Разворачивает JSON-колонки (tool.settings, sample.additions) через pd.json_normalize
    3. Удаляет BLOB-колонки (mz_array, intensity_array)
    4. Сохраняет как {table_name}_{timestamp}.csv в output_dir
    """
```

**Правила обработки данных:**

- **BLOB-поля** (`mz_array`, `intensity_array`, `uniprot_data`, `plots`, `tables`) из экспорта исключаются.
- **JSON-поля** (`settings`, `additions`, `uniprot_data`): если значение является JSON-объектом (dict) — разворачиваем через `pd.json_normalize` в плоские колонки с префиксом `{field}.`. Если значение — список или невалидный JSON — оставляем как строку.
- Таблица `project_settings` — экспортируется как есть (key, value).

**Именование файлов:** `{table_name}_{YYYYMMDD_HHMMSS}.csv`

### 5.4 UI при экспорте

Показывать `ProgressDialog` в режиме без прогресса (бесконечный loader), так как количество файлов известно заранее — переключать на ProgressBar поштучно. После завершения — показать `show_snack` с результатом.

---

## 6. Секция Joined Data

### 6.1 UI

```
┌─ Joined Data ─────────────────────────────────────────────────────┐
│  [Select All]  [Deselect All]                                      │
│  ☑ Sample details                                                  │
│  ☑ Identifications                                                 │
│  ☑ Protein identifications                                         │
│  ☑ Protein Statistics                                              │
│  ☑ One file per sample                                             │
│                                                                    │
│  Format: ○ CSV  ● XLSX                                             │
│                                                         [Export]   │
└───────────────────────────────────────────────────────────────────┘
```

**Флаг "One file per sample"** логически относится к чекбоксам, но визуально отделён горизонтальным разделителем.

### 6.2 Источники данных

| Флаг | Источник данных | Параметры фильтрации |
|---|---|---|
| Sample details | `project.get_cached_sample_stats(id)` + `project.get_samples()` | Все образцы |
| Identifications | `project.get_joined_peptide_data()` | Без фильтров (все данные) |
| Protein identifications | `project.get_protein_results_joined()` | Без фильтров |
| Protein Statistics | `project.get_protein_statistics()` | Без фильтров |

**Sample details** формируется как DataFrame из данных, аналогичных `manage_samples_view.py`:

```python
{
    "sample_id": int,
    "name": str,
    "subset_name": str,
    "outlier": bool,
    "spectra_files_count": int,
    "ident_files_count": int,
    "identifications_count": int,
    "preferred_count": int,
    "coverage_known_count": int,
    "protein_ids_count": int,
}
```

### 6.3 Флаг "One file per sample"

Когда включён:
- **Identifications** и **Protein identifications** разбиваются по образцам (`sample_id`) — для каждого образца отдельный файл/лист.
- **Sample details** и **Protein Statistics** всегда в одном файле (неделимы по образцам).

### 6.4 Логика экспорта (`joined_export.py`)

**CSV режим:** один файл на тип данных (или на тип × образец). Пример имён:
- `identifications_20260427_153000.csv`
- `identifications_sample_01_20260427_153000.csv` (при one_per_sample)

**XLSX режим:** один файл со всеми данными, каждый тип данных — отдельный лист. При `one_per_sample` — листы именуются `Identifications_{sample_name}`.

Имя XLSX-файла: `dasmixer_export_{YYYYMMDD_HHMMSS}.xlsx`

```python
async def export_joined_data(
    project: Project,
    flags: dict[str, bool],       # {section: bool}
    format_: str,                  # "csv" | "xlsx"
    one_per_sample: bool,
    output_dir: str,
    timestamp: str,
    progress_callback: Callable[[float, str], Awaitable[None]],
) -> list[str]:
    ...
```

**Progress:** для каждой активной секции (и каждого образца при one_per_sample) инкрементируем прогресс.

---

## 7. Секция Export MGF

### 7.1 UI

```
┌─ Export MGF ──────────────────────────────────────────────────────┐
│  Samples: [Sample 1 ✓, Sample 2 ✓, ...]  [Select...]             │
│                                                                    │
│  By identification:                                               │
│  ● All  ○ All preferred  ○ All preferred by tool: [Dropdown Tool] │
│                                                                    │
│  ☐ Write offset from identification                               │
│  ☐ Write spectra from identification                              │
│  ☐ Write SEQ from identification: [canonical ▼]                   │
│                                                                    │
│  Compression:                                                     │
│  ○ GZIP  ○ ZIP (All in one)  ● ZIP (One file per archive)  ○ None │
│                                                                    │
│                                                       [Export]    │
└───────────────────────────────────────────────────────────────────┘
```

**Кнопка [Select...]** — открывает диалог множественного выбора образцов. Рядом с кнопкой отображается краткий список выбранных имён (или "All", "None").

**Dropdown Tool** (`All preferred by tool`) — список Tool из проекта; появляется/скрывается по состоянию radio.

**Write SEQ Dropdown** — `canonical` / `modified`; активен только при включённом чекбоксе Write SEQ.

### 7.2 Логика экспорта (`mgf_export.py`)

#### 7.2.1 Алгоритм на образец

```python
async def export_mgf(
    project: Project,
    sample_ids: list[int],
    by: str,                       # "all" | "all_preferred" | "preferred_by_tool"
    tool_id: int | None,
    write_offset: bool,
    write_spectra_charge: bool,    # "Write spectra from identification"
    write_seq: bool,
    seq_type: str,                 # "canonical" | "modified"
    compression: str,              # "gzip" | "zip_all" | "zip_each" | "none"
    output_dir: str,
    timestamp: str,
    progress_callback: ...,
) -> list[str]:
```

1. Для каждого `sample_id`:
   a. Получить список `spectre_file` через `project.get_spectra(sample_id=sample_id)`.
   b. Для каждого spectre_file: получить спектры и связанные предпочитаемые идентификации.
   c. Фильтр по `by`:
      - `"all"`: все спектры из образца.
      - `"all_preferred"`: только спектры с is_preferred идентификацией любого инструмента.
      - `"preferred_by_tool"`: спектры с is_preferred для конкретного tool_id.
   d. Для каждого спектра формируем MGF-запись.

#### 7.2.2 Формат MGF записи

Базовая MGF-запись строится из полей `spectre` таблицы. Pyteomics используется для записи: `pyteomics.mgf.write(spectra, output)`.

Каждый спектр представляется как dict для pyteomics:

```python
{
    "params": {
        "title": spectrum["title"],
        "pepmass": (spectrum["pepmass"], None),
        "charge": [charge],          # модифицируется если write_spectra_charge
        "seq": seq_value,            # добавляется если write_seq
        "offset": offset_value,      # добавляется если write_offset
    },
    "m/z array": mz_array,          # numpy array из decompress_array
    "intensity array": intensity_array,
}
```

**Модификации из идентификации (при наличии preferred):**
- `write_offset`: добавить `OFFSET={isotope_offset}` в params.
- `write_spectra_charge`: заменить charge в params на `override_charge` из идентификации (если не None).
- `write_seq`: добавить `SEQ={sequence}` или `SEQ={canonical_sequence}` в params в зависимости от `seq_type`.

#### 7.2.3 Именование файлов

Базовое имя: `{sample_name}_{timestamp}.mgf`  
При sanitize имени: заменяем пробелы и спецсимволы на `_`.

#### 7.2.4 Сжатие

| Режим | Реализация |
|---|---|
| `none` | Записываем `.mgf` файлы напрямую |
| `gzip` | `gzip.open(f"{name}.mgf.gz", "wb")` → записываем MGF |
| `zip_all` | Один `ZipFile(f"dasmixer_mgf_{timestamp}.zip")`, добавляем все MGF |
| `zip_each` | Для каждого MGF отдельный `ZipFile(f"{sample_name}_{timestamp}.zip")` с одним файлом внутри |

При `zip_all` — пользователь выбирает папку, создаётся один ZIP-файл.  
При остальных режимах — каждый файл сохраняется в выбранную папку.

### 7.3 Progress

Прогресс по образцам: `N_processed / N_total`. Для каждого образца обновляем статус `"Exporting sample: {sample_name}"`.

---

## 8. Секция Export MzTab

### 8.1 Обзор маппинга данных DASMixer → mzTab

| DASMixer | mzTab |
|---|---|
| `sample` | `assay[N]` (один assay на образец) |
| `spectre_file` | `ms_run[N]` (один ms_run на spectre_file; образец может иметь несколько) |
| `subset` | `study_variable[N]` |
| LFQ method (rel_value) | `protein_abundance_assay[N]`, `protein_abundance_study_variable[N]` |
| `protein.id` / `protein.fasta_name` | PRT `accession` |
| `identification` (preferred) | PSM строки |

### 8.2 UI

```
┌─ Export MzTab ────────────────────────────────────────────────────┐
│  Title: [_______________________________]                         │
│  Description: [_________________________]                         │
│                                                                    │
│  Samples: [Sample 1 ✓, Sample 2 ✓, ...]  [Select...]            │
│                                                                    │
│  LFQ Method: [emPAI ▼]                                           │
│                                                                    │
│                                                       [Export]    │
└───────────────────────────────────────────────────────────────────┘
```

Поля **Title** и **Description** сохраняются в `project_settings` с ключами:
- `mztab_export_title`
- `mztab_export_description`

При открытии формы — подгружаются из project_settings (если есть).

**Выбор образцов** — аналогично MGF, через диалог множественного выбора.

**LFQ Method** — Dropdown: `emPAI`, `iBAQ`, `NSAF`, `Top3`.

### 8.3 Логика экспорта (`mztab_export.py`)

```python
from mztabwriter import MzTabDocument, CvParam, Modification

async def export_mztab(
    project: Project,
    sample_ids: list[int],
    lfq_method: str,               # "emPAI" | "iBAQ" | "NSAF" | "Top3"
    title: str | None,
    description: str | None,
    output_path: str,              # полный путь к выходному файлу .mzTab
    progress_callback: ...,
) -> str:
    """Возвращает путь к созданному файлу."""
```

#### 8.3.1 Шаг 1: Создание документа

```python
doc = MzTabDocument(
    mode="Complete",
    type_="Quantification",
    title=title or "DASMixer Export",
    description=description or "",
)

# Регистрируем DASMixer как software
doc.add_software(CvParam("MS", "MS:1001207", "DASMixer"))

# Регистрируем unlabeled sample как метод квантификации
doc.set_quantification_method(CvParam("MS", "MS:1002038", "unlabeled sample"))
doc.set_protein_quantification_unit(
    CvParam("PRIDE", "PRIDE:0000393", "Relative quantification unit")
)

# Регистрируем тип скора (используем intensity_coverage как прокси-скор)
doc.add_protein_search_engine_score(
    CvParam("MS", "MS:1001171", "DASMixer:intensity_coverage")
)
doc.add_psm_search_engine_score(
    CvParam("MS", "MS:1001171", "DASMixer:score")
)
```

#### 8.3.2 Шаг 2: Построение ms_run, assay, study_variable

```python
# Получить образцы и их spectre_files
samples = await project.get_samples()
samples = [s for s in samples if s.id in sample_ids]

subsets = await project.get_subsets()
subset_map: dict[int, list[Assay]] = {}  # subset_id -> assays

sample_assay_map: dict[int, Assay] = {}   # sample_id -> assay
ms_run_index: dict[int, MsRun] = {}       # spectre_file_id -> MsRun

reagent = CvParam("MS", "MS:1002038", "unlabeled sample")

for sample in samples:
    # Получить spectre_file-ы образца
    spectre_files_df = await project.execute_query_df(
        "SELECT id, path FROM spectre_file WHERE sample_id = ?", [sample.id]
    )

    # Каждый spectre_file -> ms_run
    sample_ms_runs = []
    for _, row in spectre_files_df.iterrows():
        location = f"file://{row['path']}" if row['path'] else "file:///unknown"
        ms_run = doc.add_ms_run(location)
        ms_run_index[row['id']] = ms_run
        sample_ms_runs.append(ms_run)

    # Первый ms_run образца -> assay (или assay на каждый ms_run, если нужно)
    # По договорённости: один assay на образец, привязанный к первому ms_run
    if sample_ms_runs:
        assay = doc.add_assay(sample_ms_runs[0], reagent)
    else:
        # Образец без spectre_file — пропускаем или создаём фиктивный ms_run
        ms_run = doc.add_ms_run("file:///no_data")
        assay = doc.add_assay(ms_run, reagent)

    sample_assay_map[sample.id] = assay
    subset_map.setdefault(sample.subset_id, []).append(assay)

# Создать study_variable на каждый subset
subset_study_variable_map: dict[int, StudyVariable] = {}
for subset in subsets:
    assays_in_subset = subset_map.get(subset.id, [])
    if assays_in_subset:
        sv = doc.add_study_variable(subset.name, assays_in_subset)
        subset_study_variable_map[subset.id] = sv
```

#### 8.3.3 Шаг 3: Заполнение PRT (белки)

Для каждого белка, у которого есть идентификации хотя бы в одном из выбранных образцов:

```python
proteins_df = await project.get_protein_results_joined(limit=None, offset=0)
# Фильтруем по выбранным образцам
proteins_df = proteins_df[proteins_df['sample_id'].isin(sample_ids)]

# Группируем по protein_id
for protein_id, group in proteins_df.groupby('protein_id'):
    # Получаем LFQ данные по образцам
    quant_df = await project.get_protein_quantification_data(
        method=lfq_method,
        protein_id=protein_id,
    )
    # quant_df содержит: sample_id, rel_value

    # Строим abundance_assay dict
    protein_abundance_assay = {}
    for _, qrow in quant_df.iterrows():
        if qrow['sample_id'] in sample_assay_map:
            assay = sample_assay_map[qrow['sample_id']]
            protein_abundance_assay[f"assay[{assay.index}]"] = qrow['rel_value']

    # Строим abundance по study_variables (среднее по образцам subset)
    # ... группировка quant_df по subset_id, mean/std/stderr

    first_row = group.iloc[0]
    doc.add_protein(
        accession=protein_id,
        description=first_row.get('name', None),
        database="FASTA",
        search_engine=CvParam("MS", "MS:1001207", "DASMixer"),
        best_search_engine_score=group['intensity_sum'].max() if 'intensity_sum' in group else None,
        search_engine_scores={
            f"ms_run[{ms_run_index[sf_id].index}]": None  # заполняем null
            for sf_id in ms_run_index
        },
        num_psms={
            f"ms_run[{ms_run_index[sf_id].index}]": None
            for sf_id in ms_run_index
        },
        num_peptides_distinct={
            f"ms_run[{sf_id}]": int(sub['peptide_count'].sum())
            for subset_id, sub in group.groupby('sample_id')
            if sub['sample_id'].iloc[0] in sample_assay_map
            for sf_id in [None]  # упрощение
        },
        protein_coverage=first_row.get('coverage', None),
        protein_abundance_assay=protein_abundance_assay,
        protein_abundance_study_variable=abundance_study_variable,
        protein_abundance_stdev_study_variable=stdev_study_variable,
        protein_abundance_std_error_study_variable=stderr_study_variable,
    )
```

> **Примечание по `num_psms_ms_run`:** В DASMixer нет прямого маппинга спектров конкретного spectre_file на конкретный белок. Поля `num_psms_ms_run[N]`, `num_peptides_distinct_ms_run[N]`, `num_peptides_unique_ms_run[N]` заполняем `null` для всех ms_run, кроме агрегированных счётчиков по образцу. Это допустимо в режиме `Complete` при null-значениях.

#### 8.3.4 Шаг 4: Заполнение PSM

Для каждого выбранного образца — получаем preferred-идентификации:

```python
for sample_id in sample_ids:
    psm_df = await project.get_joined_peptide_data(
        sample_id=sample_id,
        is_preferred=True,
        limit=None,
    )

    # Получить ms_run для образца (используем spectre_file_id)
    # spectre_file_id хранится в psm_df через join

    psm_id_counter = 1
    for _, row in psm_df.iterrows():
        # Определить spectra_ref
        spectre_file_id = row.get('spectre_file_id')
        ms_run = ms_run_index.get(spectre_file_id)
        if ms_run:
            spectra_ref = f"ms_run[{ms_run.index}]:index={row.get('seq_no', 0)}"
        else:
            spectra_ref = None

        doc.add_psm(
            sequence=row.get('canonical_sequence') or row.get('sequence', ''),
            psm_id=psm_id_counter,
            accession=row.get('protein_id', 'null'),
            unique=1 if row.get('unique_evidence') else 0,
            database="FASTA",
            search_engine=CvParam("MS", "MS:1001207", "DASMixer"),
            search_engine_score=row.get('score'),
            spectra_ref=spectra_ref,
            charge=row.get('override_charge') or row.get('charge'),
            exp_mass_to_charge=row.get('pepmass'),
            pre=None,   # Нет в текущей схеме
            post=None,
            start=None, # Нет в текущей схеме (только matched_sequence)
            end=None,
        )
        psm_id_counter += 1
```

#### 8.3.5 Шаг 5: Запись файла

```python
doc.to_file(output_path)
```

### 8.4 Выбор файла для сохранения

Используем `await ft.FilePicker().save_file(...)`:

```python
file_path = await ft.FilePicker().save_file(
    dialog_title="Save MzTab File",
    file_name=f"dasmixer_mztab_{timestamp}.mzTab",
    file_type=ft.FilePickerFileType.CUSTOM,
    allowed_extensions=["mzTab", "txt"],
)
```

### 8.5 Сохранение параметров в project_settings

После успешного экспорта или при изменении полей формы:

```python
await project.set_setting("mztab_export_title", title)
await project.set_setting("mztab_export_description", description)
```

При инициализации формы:

```python
title = await project.get_setting("mztab_export_title", default="")
description = await project.get_setting("mztab_export_description", default="")
```

---

## 9. Диалог выбора образцов (компонент)

Общий компонент `SampleSelectDialog` используется в секциях MGF и MzTab.

```
┌─ Select Samples ──────────────────────────────────────────────────┐
│  ☑ Sample 1 (Subset A)                                            │
│  ☑ Sample 2 (Subset A)                                            │
│  ☐ Sample 3 (Subset B)  [outlier]                                 │
│  ☑ Sample 4 (Subset B)                                            │
│                                                                    │
│  [Select All]  [Deselect All]                    [OK]  [Cancel]  │
└───────────────────────────────────────────────────────────────────┘
```

Реализуется как `ft.AlertDialog` с `ListView` чекбоксов. Возвращает `list[int]` выбранных `sample_id`.

---

## 10. ProgressDialog

Используется существующий `dasmixer/gui/components/progress_dialog.py`.

Поведение:
- **Одиночная операция / неизвестный размер** → показываем `ProgressBar` без значения (бесконечный).
- **Список файлов известен** → `ProgressBar` с `value=N_done/N_total`, обновляемый через `update_progress(value, status)`.
- Диалог блокирующий (modal), закрывается только по завершении операции.

Все экспортные функции принимают `progress_callback: Callable[[float, str], Awaitable[None]]`, вызываемый из async-кода.

---

## 11. Общая логика выбора выходной папки

Для всех экспортов (кроме MzTab, который использует save_file):

```python
folder = await ft.FilePicker().get_directory_path(
    dialog_title="Select Export Directory",
    initial_directory=config.last_export_folder,
)
if folder:
    config.last_export_folder = folder
    config.save()
```

После экспорта — `show_snack(page, f"Exported {N} files to {folder}")`.

---

## 12. Именование файлов (общее правило)

Timestamp: `datetime.now().strftime("%Y%m%d_%H%M%S")`

| Файл | Паттерн |
|---|---|
| System Data CSV | `{table}_{timestamp}.csv` |
| Joined CSV | `{section}_{timestamp}.csv` или `{section}_sample_{name}_{timestamp}.csv` |
| Joined XLSX | `dasmixer_export_{timestamp}.xlsx` |
| MGF (no compression) | `{sample_name}_{timestamp}.mgf` |
| MGF (GZIP) | `{sample_name}_{timestamp}.mgf.gz` |
| MGF (ZIP all) | `dasmixer_mgf_{timestamp}.zip` |
| MGF (ZIP each) | `{sample_name}_{timestamp}.zip` |
| MzTab | `dasmixer_{timestamp}.mzTab` |

Символы, недопустимые в именах файлов (`/ \ : * ? " < > |` и пробелы) — заменяются на `_`.

---

## 13. Suspend/Resume поведения вкладки Export

Вкладка **не участвует** в suspend/resume механизме тяжёлых таблиц (т.к. не содержит `BaseTableView`/`BasePlotView`). Lazy loading работает стандартно через `_TAB_DEFS`:

- При первом выборе вкладки — создаётся `ExportTab`, строится UI, восстанавливаются значения из `ExportTabState`.
- При уходе с вкладки — `ExportTab` уничтожается (контент вкладки = `ft.Column([])`), `ExportTabState` сохраняется.
- При возврате — `ExportTab` пересоздаётся, UI заполняется из `ExportTabState`.

---

## 14. Детальный план файлов и функций

### `dasmixer/api/export/__init__.py`
Пустой, только re-export публичного API.

### `dasmixer/api/export/system_export.py`

```python
TABLE_QUERIES: dict[str, str]   # dict флаг -> SQL-запрос (без BLOB-колонок)
BLOB_COLUMNS: set[str]          # имена BLOB-колонок для исключения
JSON_COLUMNS: set[str]          # имена JSON-колонок для разворачивания

async def export_system_data(
    project: Project,
    flags: dict[str, bool],
    output_dir: str,
    timestamp: str,
    progress_callback: Callable[[float, str], Awaitable[None]],
) -> list[str]: ...
```

### `dasmixer/api/export/joined_export.py`

```python
async def export_joined_data(
    project: Project,
    flags: dict[str, bool],
    format_: str,
    one_per_sample: bool,
    output_dir: str,
    timestamp: str,
    progress_callback: Callable[[float, str], Awaitable[None]],
) -> list[str]: ...

async def _get_sample_details(project: Project) -> pd.DataFrame: ...
```

### `dasmixer/api/export/mgf_export.py`

```python
def _sanitize_filename(name: str) -> str: ...

def _build_mgf_spectrum(
    spectre_row: dict,
    identification: dict | None,
    write_offset: bool,
    write_spectra_charge: bool,
    write_seq: bool,
    seq_type: str,
) -> dict: ...

async def export_mgf(
    project: Project,
    sample_ids: list[int],
    by: str,
    tool_id: int | None,
    write_offset: bool,
    write_spectra_charge: bool,
    write_seq: bool,
    seq_type: str,
    compression: str,
    output_dir: str,
    timestamp: str,
    progress_callback: Callable[[float, str], Awaitable[None]],
) -> list[str]: ...
```

### `dasmixer/api/export/mztab_export.py`

```python
# Константы CV-параметров
UNLABELED_REAGENT = CvParam("MS", "MS:1002038", "unlabeled sample")
DASMIXER_SOFTWARE = CvParam("MS", "MS:1001207", "DASMixer")

async def export_mztab(
    project: Project,
    sample_ids: list[int],
    lfq_method: str,
    title: str | None,
    description: str | None,
    output_path: str,
    progress_callback: Callable[[float, str], Awaitable[None]],
) -> str: ...

async def _build_metadata(
    doc: MzTabDocument,
    project: Project,
    sample_ids: list[int],
) -> tuple[
    dict[int, object],   # sample_id -> Assay
    dict[int, object],   # spectre_file_id -> MsRun
]: ...

async def _fill_proteins(
    doc: MzTabDocument,
    project: Project,
    sample_ids: list[int],
    lfq_method: str,
    sample_assay_map: dict,
    ms_run_index: dict,
) -> None: ...

async def _fill_psms(
    doc: MzTabDocument,
    project: Project,
    sample_ids: list[int],
    ms_run_index: dict,
) -> None: ...
```

---

## 15. GUI-файлы (краткие контракты)

### `export_tab.py` — `ExportTab`

```python
class ExportTab(ft.Column):
    def __init__(self, page: ft.Page, project: Project, state: ExportTabState): ...
    async def _build(self) -> None: ...
```

Содержит четыре `ft.ExpansionTile` или `ft.Card` секции, по одной на каждую подсекцию. Каждая секция реализована в отдельном файле.

### `system_section.py` — `SystemDataSection`

```python
class SystemDataSection(ft.Column):
    def __init__(self, page, project, state): ...
    async def _on_export(self, e): ...
```

### `joined_section.py` — `JoinedDataSection`

```python
class JoinedDataSection(ft.Column):
    def __init__(self, page, project, state): ...
    async def _on_export(self, e): ...
```

### `mgf_section.py` — `MgfExportSection`

```python
class MgfExportSection(ft.Column):
    def __init__(self, page, project, state): ...
    async def _on_select_samples(self, e): ...
    async def _on_export(self, e): ...
    def _update_tool_dropdown_visibility(self): ...
    def _update_seq_type_visibility(self): ...
```

### `mztab_section.py` — `MzTabExportSection`

```python
class MzTabExportSection(ft.Column):
    def __init__(self, page, project, state): ...
    async def _load_saved_meta(self) -> None: ...
    async def _on_select_samples(self, e): ...
    async def _on_export(self, e): ...
```

---

## 16. Ошибки и граничные случаи

| Ситуация | Обработка |
|---|---|
| Не выбран ни один чекбокс (System/Joined) | Кнопка Export недоступна или показать `show_snack` с предупреждением |
| Не выбран ни один образец (MGF/MzTab) | Кнопка Export недоступна |
| У образца нет spectre_file (MzTab) | Создаём фиктивный ms_run `file:///no_data`, assay добавляем |
| У белка нет LFQ-данных для выбранного метода | `protein_abundance_assay = {}` (пустой, mztabwriter запишет null) |
| Нет preferred идентификаций (MGF preferred) | Экспортируем пустой файл с заголовком и 0 спектрами, логируем предупреждение |
| Ошибка записи файла | `try/except`, закрыть ProgressDialog, показать `show_snack` с ошибкой |
| Отмена диалога выбора папки/файла | Просто не выполнять экспорт (нет snack) |

---

## 17. Зависимости между компонентами

```
ExportTab
├── ExportTabState          (инициализируется в ProjectView, передаётся в ExportTab)
├── SystemDataSection       → api/export/system_export.py
├── JoinedDataSection       → api/export/joined_export.py
├── MgfExportSection        → api/export/mgf_export.py
│   └── SampleSelectDialog
└── MzTabExportSection      → api/export/mztab_export.py
    └── SampleSelectDialog
```

`SampleSelectDialog` — переиспользуемый компонент, вынести в `dasmixer/gui/components/sample_select_dialog.py`.

---

## 18. Тестовый сценарий (для ручного QA)

1. Открыть проект с 3+ образцами, 2+ сабсетами, LFQ-рассчитанными данными.
2. **System Data:** выбрать все → Export → проверить наличие CSV для каждой таблицы; убедиться, что в spectre нет BLOB-колонок; убедиться, что tool.settings разворачивается в отдельные колонки.
3. **Joined Data:** XLSX + Sample details + Identifications + One per sample → проверить листы в файле.
4. **Export MGF:** выбрать 2 образца, All preferred, Write SEQ (canonical), GZIP → убедиться, что создаются 2 `.mgf.gz`, MGF содержит SEQ в заголовках.
5. **Export MzTab:** заполнить Title+Description, выбрать образцы, iBAQ → проверить структуру файла: MTD-секция содержит ms_run/assay/study_variable; PRT — белки с abundance; PSM — preferred-идентификации.
