# STAGE 15 — Детальная спецификация

**Версия приложения:** 0.1.0 → **0.2.0**  
**Версия проекта (схема БД):** 0.1.0 → **0.2.0**  
**Дата:** Апрель 2026

---

## Оглавление

1. [Управление версиями (`versions.py`)](#1-управление-версиями-versionspy)
2. [MigrationMixin — система миграций проекта](#2-migrationmixin--система-миграций-проекта)
3. [UI диалога миграции в `app.py`](#3-ui-диалога-миграции-в-apppy)
4. [Расширение модели данных: поля `taxon_id` / `organism_name`](#4-расширение-модели-данных-поля-taxon_id--organism_name)
5. [Исправление `update_protein` в `ProteinMixin`](#5-исправление-update_protein-в-proteinmixin)
6. [Связывание обогащения белков: `EnrichmentSection`](#6-связывание-обогащения-белков-enrichmentsection)
7. [Улучшения таблиц белков](#7-улучшения-таблиц-белков)
8. [MzTab экспорт: taxon\_id / organism\_name](#8-mztab-экспорт-taxon_id--organism_name)
9. [Декомпозиция задач по файлам](#9-декомпозиция-задач-по-файлам)

---

## 1. Управление версиями (`versions.py`)

### 1.1 Цель

Централизовать все версионные константы в одном месте, избавиться от захардкоженных строк в `main.py` и `schema.py`.

### 1.2 Создаваемый файл

**`dasmixer/versions.py`**

```python
# Версия приложения DASMixer
APP_VERSION = "0.2.0"

# Версия схемы файла проекта (.dasmix).
# Поднимается только тогда, когда меняется схема БД.
# Может отставать от APP_VERSION.
PROJECT_VERSION = "0.2.0"

# Минимальная версия проекта, для которой возможна миграция.
# Проекты ниже этой версии не открываются с миграцией.
MIN_SUPPORTED_PROJECT_VERSION = "0.1.0"
```

Пакет `dasmixer` должен реэкспортировать версию приложения как `__version__`:

**`dasmixer/__init__.py`** — добавить строку:
```python
from dasmixer.versions import APP_VERSION as __version__
```

### 1.3 Изменения в существующих файлах

| Файл | Что менять |
|---|---|
| `pyproject.toml` | `version = "0.2.0"` (поле `[project]`) |
| `dasmixer/main.py` | `typer.echo(f"DASMixer version {APP_VERSION}")` — импортировать `APP_VERSION` из `dasmixer.versions` |
| `dasmixer/api/project/schema.py` | `DEFAULT_METADATA['version']` → заменить строку `'0.1.0'` на `PROJECT_VERSION` из `dasmixer.versions` |

---

## 2. MigrationMixin — система миграций проекта

### 2.1 Создаваемый файл

**`dasmixer/api/project/migrations.py`**

Модуль содержит:
- Список миграций `MIGRATIONS`
- Класс `MigrationMixin` с методом `apply_migrations()`

### 2.2 Структура списка миграций

```python
MIGRATIONS: list[dict] = [
    {
        "version": "0.2.0",
        "sql": """
            ALTER TABLE protein ADD COLUMN taxon_id INTEGER;
            ALTER TABLE protein ADD COLUMN organism_name TEXT;
        """
    },
    # В будущем: {"version": "0.4.0", "sql": "..."}
]
```

> **Примечание:** SQLite не поддерживает несколько `ALTER TABLE` в одном `executescript` через точку с запятой при добавлении колонок с разными именами атомарно, но `executescript` выполняет SQL-блок целиком. Каждый `ALTER TABLE ADD COLUMN` — отдельный statement; они идут последовательно в одном скрипте. При ошибке любого из них выполняется `rollback`.

### 2.3 Сигнатура класса и метода

```python
from packaging.version import Version   # или простое строковое сравнение

class MigrationMixin:
    """
    Mixin для системы миграций схемы проекта.
    Подмешивается в Project между ProjectLifecycle и остальными миксинами.
    """

    async def apply_migrations(self) -> None:
        """
        Проверяет версию открытого проекта и применяет необходимые миграции.

        Алгоритм:
        1. Читает project_metadata.version
        2. Если version == PROJECT_VERSION — ничего не делает
        3. Если version < MIN_SUPPORTED_PROJECT_VERSION — поднимает MigrationError
        4. Итерирует MIGRATIONS, пропуская версии <= текущей версии проекта
        5. Применяет подходящие миграции через executescript внутри транзакции
        6. При ошибке — rollback, логирует logger.exception, поднимает MigrationError
        7. При успехе — обновляет project_metadata.version = PROJECT_VERSION и сохраняет

        Raises:
            MigrationError: при неподдерживаемой версии или ошибке выполнения SQL
        """
        ...

    async def get_project_version(self) -> str:
        """Возвращает строку версии из project_metadata."""
        row = await self._fetchone(
            "SELECT value FROM project_metadata WHERE key = 'version'"
        )
        return row['value'] if row else "0.1.0"

    async def needs_migration(self) -> bool:
        """True, если версия проекта ниже PROJECT_VERSION."""
        ...

    async def is_version_too_new(self) -> bool:
        """True, если версия проекта выше PROJECT_VERSION."""
        ...
```

### 2.4 Класс исключения

```python
class MigrationError(Exception):
    """Ошибка при применении миграций проекта."""
    pass
```

Размещается в том же файле `migrations.py`.

### 2.5 Детальная логика `apply_migrations`

```
project_version = await self.get_project_version()

if project_version == PROJECT_VERSION:
    return  # уже актуальная версия

if _version_lt(project_version, MIN_SUPPORTED_PROJECT_VERSION):
    raise MigrationError(
        f"Project version {project_version} is below minimum supported "
        f"{MIN_SUPPORTED_PROJECT_VERSION}. Migration is not possible."
    )

# Фильтруем: берём только миграции, чья версия > project_version
pending = [m for m in MIGRATIONS if _version_gt(m['version'], project_version)]

if not pending:
    # Нечего применять, но версии не совпадают — обновляем метадату
    await _update_version()
    return

# Применяем последовательно, каждую в своей транзакции
for migration in pending:
    try:
        await self._db.executescript(migration['sql'])
        await self._db.commit()
    except Exception as e:
        await self._db.rollback()
        logger.exception(f"Migration to {migration['version']} failed: {e}")
        raise MigrationError(
            f"Migration to version {migration['version']} failed: {e}"
        ) from e

# Все миграции применены — обновляем версию
await self._execute(
    "INSERT OR REPLACE INTO project_metadata (key, value) VALUES ('version', ?)",
    (PROJECT_VERSION,)
)
await self._db.commit()
```

**Вспомогательные функции (приватные, в том же файле):**

```python
def _version_lt(a: str, b: str) -> bool:
    """Возвращает True если версия a строго меньше b."""
    return tuple(int(x) for x in a.split('.')) < tuple(int(x) for x in b.split('.'))

def _version_gt(a: str, b: str) -> bool:
    """Возвращает True если версия a строго больше b."""
    return tuple(int(x) for x in a.split('.')) > tuple(int(x) for x in b.split('.'))
```

> Зависимость `packaging` не нужна — достаточно сравнения кортежей из семантических версий.

### 2.6 Встраивание в `Project`

**`dasmixer/api/project/project.py`** — добавить `MigrationMixin` в MRO:

```python
from .migrations import MigrationMixin

class Project(
    ProjectLifecycle,
    MigrationMixin,       # <-- добавить после ProjectLifecycle
    SubsetMixin,
    ToolMixin,
    ...
):
    pass
```

**`dasmixer/api/project/mixins/__init__.py`** — импорт не нужен (migrations — отдельный модуль, не в папке mixins).

---

## 3. UI диалога миграции в `app.py`

### 3.1 Точка вызова

В методе `open_project` класса `DASMixerApp` (`dasmixer/gui/app.py`), сразу после `await self.current_project.initialize()` и до `self.show_project_view()`:

```python
await self.current_project.initialize()

# Проверка версии проекта
await self._check_project_version()

config.add_recent_project(str(project_path))
self.show_project_view()
```

То же самое — в `new_project` версия всегда будет актуальной, проверку там не делать.

### 3.2 Метод `_check_project_version`

```python
async def _check_project_version(self):
    """
    Проверяет версию открытого проекта и предлагает миграцию или предупреждает
    о несовместимости.
    """
    from dasmixer.api.project.migrations import MigrationError

    needs_migration = await self.current_project.needs_migration()
    is_too_new = await self.current_project.is_version_too_new()
    project_version = await self.current_project.get_project_version()

    if is_too_new:
        # Версия проекта новее, чем текущий DASMixer — предупреждение без действия
        await self._show_version_warning_dialog(project_version)
        return

    if needs_migration:
        # Предлагаем обновление
        user_confirmed = await self._show_migration_dialog(project_version)
        if user_confirmed:
            await self._run_migration()
```

### 3.3 Диалог предупреждения (версия проекта слишком новая)

`_show_version_warning_dialog(project_version: str)` — показывает `ft.AlertDialog` с одной кнопкой "OK":

```
Заголовок: "Incompatible Project Version"

Текст:
"This project was created with a newer version of DASMixer 
(project version: {project_version}, current: {PROJECT_VERSION}).

You may encounter errors or unexpected behavior.
It is strongly recommended to update DASMixer before using this project."

Кнопки: [OK]
```

### 3.4 Диалог предложения миграции

`_show_migration_dialog(project_version: str) -> bool` — возвращает `True`, если пользователь нажал "Update":

```
Заголовок: "Project Update Required"

Текст:
"This project uses an older format (version {project_version}).
Current DASMixer requires version {PROJECT_VERSION}.

Without updating, you may encounter errors.
After updating, the project may not open correctly in older versions of DASMixer.

⚠ Note: project files can be large (several GB). 
We recommend making a backup copy before proceeding."

Кнопки: [Skip] [Update]
```

Реализация через `asyncio.Event` или `asyncio.Future` для ожидания выбора пользователя в async-контексте (паттерн, уже используемый в других диалогах проекта).

### 3.5 Метод `_run_migration`

```python
async def _run_migration(self):
    """Запускает миграцию с отображением прогресса."""
    from dasmixer.api.project.migrations import MigrationError
    from dasmixer.gui.components.progress_dialog import ProgressDialog

    dialog = ProgressDialog("Updating project...")
    self.page.overlay.append(dialog)
    dialog.open = True
    self.page.update()

    try:
        dialog.update_progress(0.1, "Applying migrations...")
        await self.current_project.apply_migrations()
        dialog.update_progress(1.0, "Done")
    except MigrationError as e:
        dialog.open = False
        self.page.update()
        self._show_error(f"Migration failed: {e}")
        return
    finally:
        dialog.open = False
        self.page.update()

    show_snack(self.page, f"Project updated to {PROJECT_VERSION}", ft.Colors.GREEN_400)
```

---

## 4. Расширение модели данных: поля `taxon_id` / `organism_name`

### 4.1 Миграция SQL (включена в MIGRATIONS)

```sql
ALTER TABLE protein ADD COLUMN taxon_id INTEGER;
ALTER TABLE protein ADD COLUMN organism_name TEXT;
```

Оба поля `NULL` по умолчанию. SQLite автоматически проставляет `NULL` для существующих строк при `ALTER TABLE ADD COLUMN`.

### 4.2 Изменения в `schema.py`

В `CREATE_SCHEMA_SQL` — в секции таблицы `protein` добавить строки:

```sql
CREATE TABLE IF NOT EXISTS protein (
    id TEXT PRIMARY KEY,
    is_uniprot INTEGER NOT NULL DEFAULT 0,
    fasta_name TEXT,
    sequence TEXT,
    gene TEXT,
    name TEXT,
    uniprot_data BLOB,
    taxon_id INTEGER,        -- NCBI Taxonomy ID (nullable)
    organism_name TEXT       -- Organism display name (nullable)
);
```

> Изменение `CREATE_SCHEMA_SQL` нужно для новых проектов. Существующие проекты получают поля через `ALTER TABLE` в миграции.

### 4.3 Изменения в `dataclasses.py`

**Класс `Protein`** — добавить два поля:

```python
@dataclass
class Protein:
    id: str = ""
    is_uniprot: bool = False
    fasta_name: str | None = None
    sequence: str | None = None
    gene: str | None = None
    name: str | None = None
    uniprot_data: 'UniprotData | None' = field(default=None, repr=False)
    taxon_id: int | None = None           # НОВОЕ: NCBI Taxonomy ID
    organism_name: str | None = None      # НОВОЕ: название организма
    protein_atlas_data: dict | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'is_uniprot': self.is_uniprot,
            'fasta_name': self.fasta_name,
            'sequence': self.sequence,
            'gene': self.gene,
            'name': self.name,
            'taxon_id': self.taxon_id,           # НОВОЕ
            'organism_name': self.organism_name,  # НОВОЕ
            # uniprot_data — сериализуется отдельно как BLOB
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Protein':
        return cls(
            id=data.get('id', ''),
            is_uniprot=bool(data.get('is_uniprot', False)),
            fasta_name=data.get('fasta_name'),
            sequence=data.get('sequence'),
            gene=data.get('gene'),
            name=data.get('name'),
            taxon_id=data.get('taxon_id'),             # НОВОЕ
            organism_name=data.get('organism_name'),   # НОВОЕ
            uniprot_data=None,
            protein_atlas_data=None
        )
```

---

## 5. Исправление `update_protein` в `ProteinMixin`

### 5.1 Текущая проблема

В `dasmixer/api/project/mixins/protein_mixin.py` метод `update_protein` содержит:
1. Синтаксическую ошибку SQL: пропущена запятая перед `uniprot_data = ?`
2. Отсутствующий `protein_id` в параметрах `params`
3. Новые поля `taxon_id` и `organism_name` не обновляются

### 5.2 Корректный SQL и реализация

```python
async def update_protein(self, protein: Protein) -> None:
    """
    Обновляет все поля белка в БД.
    
    Args:
        protein: Protein dataclass с обновлёнными полями
    """
    query = """
        UPDATE protein
        SET
            is_uniprot    = ?,
            fasta_name    = ?,
            sequence      = ?,
            gene          = ?,
            name          = ?,
            uniprot_data  = ?,
            taxon_id      = ?,
            organism_name = ?
        WHERE id = ?
    """
    params = (
        1 if protein.is_uniprot else 0,
        protein.fasta_name,
        protein.sequence,
        protein.gene,
        protein.name,
        self._serialize_pickle_gzip(protein.uniprot_data),
        protein.taxon_id,
        protein.organism_name,
        protein.id,
    )
    await self._execute(query, params)
    await self.save()
```

### 5.3 Обновление методов `add_protein` и `add_proteins_batch`

Метод `add_protein` и `add_proteins_batch` также должны включать новые поля.

**`add_protein` — полный SQL:**

```sql
INSERT OR REPLACE INTO protein
    (id, is_uniprot, fasta_name, sequence, gene, name, uniprot_data, taxon_id, organism_name)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
```

Параметры в порядке: `(protein_id, is_uniprot, fasta_name, sequence, gene, name, uniprot_blob, taxon_id, organism_name)`

**`add_proteins_batch` — аналогично**, добавить в кортеж `rows_to_insert`:
```python
rows_to_insert.append((
    row['id'],
    1 if row.get('is_uniprot', False) else 0,
    row.get('fasta_name'),
    row.get('sequence'),
    row.get('gene'),
    row.get('name'),
    uniprot_blob,
    row.get('taxon_id'),       # НОВОЕ
    row.get('organism_name'),  # НОВОЕ
))
```

**`get_protein` и `get_proteins`** — добавить в `Protein(...)` конструктор:
```python
taxon_id=row.get('taxon_id'),
organism_name=row.get('organism_name'),
```

---

## 6. Связывание обогащения белков: `EnrichmentSection`

### 6.1 Текущее состояние

`dasmixer/gui/views/tabs/proteins/enrichment_section.py` — кнопка "Enrich proteins data from UniProt" делает `print("NOT IMPLEMENTED")`.

### 6.2 Реализация

Заменить `on_click` кнопки на вызов `self.page.run_task(self._run_enrich)`.

**Метод `_run_enrich`:**

```python
async def _run_enrich(self, e=None):
    force_update = self.force_update_checkbox.value
    overwrite_fasta = self.update_fasta_checkbox.value

    from dasmixer.gui.components.progress_dialog import ProgressDialog
    from dasmixer.api.calculations.proteins.enrich import enrich_proteins
    from dasmixer.gui.utils import show_snack

    dialog = ProgressDialog("Enriching proteins from UniProt...")
    self.page.overlay.append(dialog)
    dialog.open = True
    self.page.update()

    processed = 0
    total = 0
    try:
        async for protein_id, total in enrich_proteins(
            self.project,
            force_update=force_update,
            overwrite_fasta=overwrite_fasta
        ):
            processed += 1
            progress_value = processed / total if total > 0 else 0
            dialog.update_progress(
                progress_value,
                f"Processing {processed}/{total}: {protein_id}"
            )

    except Exception as ex:
        from dasmixer.utils import logger
        logger.exception(ex)
        dialog.open = False
        self.page.update()
        show_snack(self.page, f"Enrichment error: {ex}", ft.Colors.RED_400)
        self.page.update()
        return

    dialog.open = False
    self.page.update()
    show_snack(
        self.page,
        f"Enrichment complete: {processed} proteins processed",
        ft.Colors.GREEN_400
    )
    self.page.update()
```

### 6.3 Блокировка кнопки во время работы

Перед запуском: `self.calculate_btn.disabled = True; self.calculate_btn.update()`  
После завершения (в `finally`): `self.calculate_btn.disabled = False; self.calculate_btn.update()`

---

## 7. Улучшения таблиц белков

### 7.1 Общие изменения для обеих таблиц

#### 7.1.1 Добавление `taxon_id` и `organism_name` как скрытых колонок

Поля добавляются в `header_name_mapping` обеих таблиц:

```python
header_name_mapping = {
    ...
    'taxon_id': 'Taxon ID',
    'organism_name': 'Organism',
}
```

Они не добавляются в `default_columns` (появятся как скрытые, доступные через шестерёнку).

#### 7.1.2 Добавление `protein_name`

В `header_name_mapping` обеих таблиц добавить:

```python
'name': 'Protein Name',
```

### 7.2 Изменения в `ProteinMixin` — метод `get_protein_results_joined`

Добавить в SELECT:
- `p.name` (уже есть в таблице)
- `p.taxon_id`
- `p.organism_name`

**Полный обновлённый SELECT:**

```sql
SELECT
    pir.id,
    pir.protein_id,
    pir.sample_id,
    s.name          AS sample,
    sub.name        AS subset,
    p.gene,
    p.name          AS name,
    p.sequence,
    p.taxon_id,
    p.organism_name,
    pir.peptide_count,
    pir.uq_evidence_count   AS unique_evidence_count,
    pir.coverage            AS coverage_percent,
    pir.intensity_sum,
    pqr_empai.rel_value     AS EmPAI,
    pqr_ibaq.rel_value      AS iBAQ,
    pqr_nsaf.rel_value      AS NSAF,
    pqr_top3.rel_value      AS Top3
FROM protein_identification_result pir
JOIN sample s ON pir.sample_id = s.id
LEFT JOIN subset sub ON s.subset_id = sub.id
LEFT JOIN protein p ON pir.protein_id = p.id
LEFT JOIN protein_quantification_result pqr_empai
    ON pir.id = pqr_empai.protein_identification_id AND pqr_empai.algorithm = 'emPAI'
LEFT JOIN protein_quantification_result pqr_ibaq
    ON pir.id = pqr_ibaq.protein_identification_id AND pqr_ibaq.algorithm = 'iBAQ'
LEFT JOIN protein_quantification_result pqr_nsaf
    ON pir.id = pqr_nsaf.protein_identification_id AND pqr_nsaf.algorithm = 'NSAF'
LEFT JOIN protein_quantification_result pqr_top3
    ON pir.id = pqr_top3.protein_identification_id AND pqr_top3.algorithm = 'Top3'
WHERE 1=1
```

В конце метода, при обработке DataFrame, убрать `'id'` и `'sample_id'` из `drop()`, оставив `'sequence'` (т.к. weight считается из sequence):

```python
df = df.drop(columns=['sequence', 'id', 'sample_id'])
```

> Никаких других изменений в `count_protein_results_joined` не нужно — счётчик считает строки по `pir`, а не по `protein`.

### 7.3 Изменения в `ProteinMixin` — метод `get_protein_statistics`

#### 7.3.1 Добавление `taxon_id`, `organism_name`, `name` в SQL

**Обновлённый CTE `protein_stats`:**

```sql
WITH protein_stats AS (
    SELECT
        p.id            AS protein_id,
        p.name          AS name,
        p.gene,
        p.fasta_name,
        p.taxon_id,
        p.organism_name,
        COUNT(DISTINCT pir.sample_id)           AS samples,
        COUNT(DISTINCT s.subset_id)             AS subsets,
        SUM(pir.peptide_count)                  AS PSMs,
        CAST(ROUND(AVG(pir.peptide_count)) AS INTEGER)    AS mean_psm,
        SUM(pir.uq_evidence_count)              AS unique_evidence,
        CAST(ROUND(AVG(pir.uq_evidence_count)) AS INTEGER) AS mean_unique
    FROM (
        SELECT DISTINCT protein_id FROM protein_identification_result
    ) AS pl
    LEFT JOIN protein p ON p.id = pl.protein_id
    LEFT JOIN protein_identification_result pir ON p.id = pir.protein_id
    LEFT JOIN sample s ON pir.sample_id = s.id
    GROUP BY p.id, p.gene, p.fasta_name, p.name, p.taxon_id, p.organism_name
)
SELECT * FROM protein_stats
WHERE samples >= ? AND subsets >= ?
ORDER BY samples DESC, protein_id
LIMIT ? OFFSET ?
```

#### 7.3.2 Загрузка `uniprot_data` в DataFrame

После выполнения SQL-запроса в `get_protein_statistics` — добавить загрузку `uniprot_data` для каждой строки:

```python
# Добавляем uniprot_data как колонку для виртуальных полей
if not df.empty:
    uniprot_list = []
    for protein_id in df['protein_id']:
        protein = await self.get_protein(protein_id)
        uniprot_list.append(protein.uniprot_data if protein else None)
    df['uniprot_data'] = uniprot_list
```

> `uniprot_data` — служебная колонка, не отображается в таблице. Она скрыта через логику `default_columns` или явным исключением при рендеринге.

### 7.4 Изменения в `ProteinStatisticsTableView`

#### 7.4.1 Обновление `header_name_mapping`

```python
header_name_mapping = {
    'protein_id': 'Protein ID',
    'gene': 'Gene',
    'name': 'Protein Name',       # НОВОЕ
    'fasta_name': 'FASTA Name',
    'taxon_id': 'Taxon ID',       # НОВОЕ
    'organism_name': 'Organism',  # НОВОЕ
    'samples': 'Samples',
    'subsets': 'Groups',
    'PSMs': 'PSMs',
    'unique_evidence': 'Unique Evidence',
    # Виртуальные поля:
    'pathways': 'Pathways',
    'mol_functions': 'Molecular Functions',
    'bio_processes': 'Biological Processes',
    'subcellular_locations': 'Subcellular Locations',
}
```

#### 7.4.2 `default_columns`

Чтобы `uniprot_data` не показывалась в таблице и не попадала в экспорт, нужно явно исключить её при рендеринге:

```python
# В методе get_data() после формирования df:
# убираем служебную колонку из видимых данных,
# но сохраняем её отдельно для вычисления виртуальных полей
```

Логика исключения:

```python
async def get_data(self, limit: int = 100, offset: int = 0) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    kwargs = self._build_filter_kwargs()
    try:
        if limit == -1:
            df = await self.project.get_protein_statistics(**kwargs, limit=-1, offset=0)
        else:
            df = await self.project.get_protein_statistics(**kwargs, limit=limit, offset=offset)
    except Exception:
        import traceback
        traceback.print_exc()
        return pd.DataFrame(columns=list(self.header_name_mapping.keys())), None

    # Вычисляем виртуальные поля из uniprot_data
    tooltip_data = {}
    for vfield, func in VIRTUAL_FIELD_FUNCS.items():
        display_vals = []
        tooltip_vals = []
        for uniprot_obj in df.get('uniprot_data', pd.Series(dtype=object)):
            if uniprot_obj is not None:
                disp, tip = func(uniprot_obj)
            else:
                disp, tip = None, None
            display_vals.append(disp)
            tooltip_vals.append(tip)
        df[vfield] = display_vals
        tooltip_data[vfield] = tooltip_vals

    # Убираем служебную колонку перед отображением
    if 'uniprot_data' in df.columns:
        df = df.drop(columns=['uniprot_data'])

    # Строим tooltip_df для виртуальных полей
    if tooltip_data:
        tooltip_df = pd.DataFrame(tooltip_data, index=df.index)
    else:
        tooltip_df = None

    return df, tooltip_df
```

**Константа маппинга виртуальных полей** (в начале файла `protein_statistics_table_view.py`):

```python
from dasmixer.utils.show_pathways import (
    get_pathways_from_uniprot,
    get_mol_functions_from_uniprot,
    get_biological_processes_from_uniprot,
    get_locations_from_uniprot,
)

VIRTUAL_FIELD_FUNCS: dict[str, callable] = {
    'pathways':             get_pathways_from_uniprot,
    'mol_functions':        get_mol_functions_from_uniprot,
    'bio_processes':        get_biological_processes_from_uniprot,
    'subcellular_locations': get_locations_from_uniprot,
}
```

#### 7.4.3 Виртуальные поля — не добавляются в фильтр

`column_filter_mapping` для виртуальных полей **не расширяется**. Они только отображаются и экспортируются.

#### 7.4.4 `get_total_count` — без изменений

Счётчик строк не зависит от виртуальных полей.

### 7.5 Изменения в `ProteinIdentificationsTableView`

Добавить в `header_name_mapping`:
```python
'name': 'Protein Name',
'taxon_id': 'Taxon ID',
'organism_name': 'Organism',
```

Обновить `get_data()` — убрать truncation `fasta_name` из отдельного шага (или оставить), **добавить** поля `name`, `taxon_id`, `organism_name` в `tooltip_df`:

```python
async def get_data(self, limit: int = 100, offset: int = 0) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    kwargs = self._build_filter_kwargs()
    if limit == -1:
        df = await self.project.get_protein_results_joined(**kwargs, limit=999999, offset=0)
    else:
        df = await self.project.get_protein_results_joined(**kwargs, limit=limit, offset=offset)

    # tooltip для длинных строк
    tooltip_df = df[['fasta_name']].copy()
    df['fasta_name'] = df['fasta_name'].apply(
        lambda x: x if pd.isna(x) or len(str(x)) <= 32 else str(x)[:30] + '…'
    )
    return df, tooltip_df
```

---

## 8. MzTab экспорт: `taxon_id` / `organism_name`

### 8.1 Изменение в `mztab_export.py`

В блоке построения PRT-строк функция `doc.add_protein()` вызывается с параметрами. В `mztabwriter` у объекта `ProteinRow` есть поля `taxid: int | None` и `species: str | None`.

**Обновлённый вызов `doc.add_protein()`:**

Перед вызовом получаем `taxon_id` и `organism_name` из `first_row` (они будут в DataFrame после обновления запроса в `get_protein_results_joined`):

```python
taxid_val = first_row.get("taxon_id")
species_val = first_row.get("organism_name")

doc.add_protein(
    accession=str(protein_id),
    description=first_row.get("name") or None,      # protein_name → name
    database="FASTA",
    search_engine=DASMIXER_SOFTWARE,
    best_search_engine_score=best_score,
    search_engine_scores=dict(all_ms_run_keys),
    num_psms=dict(all_ms_run_keys),
    num_peptides_distinct=num_distinct,
    protein_coverage=first_row.get("coverage") or None,
    protein_abundance_assay=protein_abundance_assay or None,
    protein_abundance_study_variable=abundance_sv or None,
    protein_abundance_stdev_study_variable=stdev_sv or None,
    protein_abundance_std_error_study_variable=stderr_sv or None,
    taxid=int(taxid_val) if taxid_val is not None else None,     # НОВОЕ
    species=species_val or None,                                   # НОВОЕ
)
```

> **Примечание:** поле `description` было `first_row.get("protein_name")`, но в обновлённом запросе поле называется `name` (алиас `p.name AS name`). Обновить соответственно.

### 8.2 SQL запроса в `export_mztab`

В `export_mztab` есть прямой SQL-запрос для фильтрации белков. Добавить в него `p.taxon_id`, `p.organism_name`, `p.name`:

```sql
SELECT
    pir.protein_id,
    pir.sample_id,
    pir.peptide_count,
    pir.coverage,
    pir.intensity_sum,
    p.gene,
    p.name           AS name,
    p.taxon_id,
    p.organism_name
FROM protein_identification_result pir
LEFT JOIN protein p ON pir.protein_id = p.id
WHERE pir.sample_id IN ({placeholders})
ORDER BY pir.protein_id
```

---

## 9. Декомпозиция задач по файлам

### Задача 1 — Управление версиями

**Файлы:**
- `dasmixer/versions.py` — **создать**
- `dasmixer/__init__.py` — добавить `from dasmixer.versions import APP_VERSION as __version__`
- `pyproject.toml` — `version = "0.2.0"`
- `dasmixer/main.py` — заменить `"DASMixer version 0.1.0"` → `f"DASMixer version {APP_VERSION}"`
- `dasmixer/api/project/schema.py` — `DEFAULT_METADATA['version']` → использовать `PROJECT_VERSION`

**Описание:** Создать `versions.py` с тремя константами. Заменить все захардкоженные версии на ссылки на константы.

---

### Задача 2 — MigrationMixin

**Файлы:**
- `dasmixer/api/project/migrations.py` — **создать**
- `dasmixer/api/project/project.py` — добавить `MigrationMixin` в MRO

**Описание:** Реализовать `MigrationError`, `MigrationMixin` с методами `apply_migrations()`, `get_project_version()`, `needs_migration()`, `is_version_too_new()`. Добавить список `MIGRATIONS` с первой миграцией (ALTER TABLE protein ADD COLUMN taxon_id / organism_name).

---

### Задача 3 — UI диалога миграции

**Файлы:**
- `dasmixer/gui/app.py` — добавить методы `_check_project_version()`, `_show_version_warning_dialog()`, `_show_migration_dialog()`, `_run_migration()`; вставить вызов в `open_project()`

**Описание:** Реализовать async-диалоги предупреждения и предложения миграции. Диалог с прогрессом для самой миграции. Вывод snack_bar по результату.

---

### Задача 4 — Расширение схемы и dataclass Protein

**Файлы:**
- `dasmixer/api/project/schema.py` — добавить `taxon_id INTEGER`, `organism_name TEXT` в `CREATE TABLE protein`
- `dasmixer/api/project/dataclasses.py` — добавить поля в `Protein`, обновить `to_dict()` / `from_dict()`

**Описание:** Чисто модельные изменения. SQL миграция уже описана в Задаче 2.

---

### Задача 5 — Обновление `ProteinMixin`

**Файлы:**
- `dasmixer/api/project/mixins/protein_mixin.py`

**Описание:**
1. Исправить `update_protein` (ошибка SQL + добавить новые поля)
2. Обновить `add_protein` — добавить `taxon_id`, `organism_name` в INSERT
3. Обновить `add_proteins_batch` — добавить новые поля в кортеж
4. Обновить `get_protein` / `get_proteins` — читать `taxon_id`, `organism_name` из строки
5. Обновить `get_protein_results_joined` — добавить `p.name AS name`, `p.taxon_id`, `p.organism_name` в SELECT
6. Обновить `get_protein_statistics` — добавить `p.name`, `p.taxon_id`, `p.organism_name` в CTE; добавить загрузку `uniprot_data` в DataFrame после запроса

**SQL запросы:**

`add_protein` / `add_proteins_batch`:
```sql
INSERT OR REPLACE INTO protein
    (id, is_uniprot, fasta_name, sequence, gene, name, uniprot_data, taxon_id, organism_name)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
```

`update_protein`:
```sql
UPDATE protein
SET
    is_uniprot    = ?,
    fasta_name    = ?,
    sequence      = ?,
    gene          = ?,
    name          = ?,
    uniprot_data  = ?,
    taxon_id      = ?,
    organism_name = ?
WHERE id = ?
```

`get_protein` / `get_proteins` — `SELECT *` уже включает новые поля после миграции; достаточно передать `taxon_id` / `organism_name` в конструктор `Protein(...)`.

`get_protein_results_joined` — полный SELECT указан в [разделе 7.2](#72-изменения-в-proteinmixin--метод-get_protein_results_joined).

`get_protein_statistics` — полный CTE указан в [разделе 7.3.1](#731-добавление-taxon_id-organism_name-name-в-sql).

---

### Задача 6 — EnrichmentSection: подключение логики

**Файлы:**
- `dasmixer/gui/views/tabs/proteins/enrichment_section.py`

**Описание:** Заменить `print("NOT IMPLEMENTED")` на `self.page.run_task(self._run_enrich)`. Реализовать `_run_enrich()` с `ProgressDialog`, итерацией по async generator `enrich_proteins()`, блокировкой/разблокировкой кнопки.

---

### Задача 7 — ProteinIdentificationsTableView: новые колонки

**Файлы:**
- `dasmixer/gui/views/tabs/proteins/protein_identifications_table_view.py`

**Описание:**
- Добавить `'name': 'Protein Name'`, `'taxon_id': 'Taxon ID'`, `'organism_name': 'Organism'` в `header_name_mapping`
- Обновить `get_data()`: tooltip_df теперь включает `fasta_name` (уже есть) — убедиться, что новые поля корректно попадают в DataFrame (они приходят из обновлённого `get_protein_results_joined`)

---

### Задача 8 — ProteinStatisticsTableView: новые колонки + виртуальные поля

**Файлы:**
- `dasmixer/gui/views/tabs/proteins/protein_statistics_table_view.py`

**Описание:**
- Добавить `'name'`, `'taxon_id'`, `'organism_name'`, `'pathways'`, `'mol_functions'`, `'bio_processes'`, `'subcellular_locations'` в `header_name_mapping`
- Добавить константу `VIRTUAL_FIELD_FUNCS` с маппингом на функции из `show_pathways.py`
- Переписать `get_data()`: вычислять виртуальные поля из `uniprot_data`, удалять служебную колонку из DataFrame перед возвратом, формировать `tooltip_df` для виртуальных полей

---

### Задача 9 — MzTab экспорт

**Файлы:**
- `dasmixer/api/export/mztab_export.py`

**Описание:**
- Обновить inline SQL-запрос для фильтрации белков: добавить `p.name AS name`, `p.taxon_id`, `p.organism_name`
- В вызове `doc.add_protein()`: `description` → `first_row.get("name")`, добавить `taxid` и `species`

---

## Итоговая таблица изменяемых файлов

| № | Файл | Статус | Задача |
|---|---|---|---|
| 1 | `dasmixer/versions.py` | Создать | 1 |
| 2 | `dasmixer/__init__.py` | Изменить | 1 |
| 3 | `pyproject.toml` | Изменить | 1 |
| 4 | `dasmixer/main.py` | Изменить | 1 |
| 5 | `dasmixer/api/project/schema.py` | Изменить | 1, 4 |
| 6 | `dasmixer/api/project/migrations.py` | Создать | 2 |
| 7 | `dasmixer/api/project/project.py` | Изменить | 2 |
| 8 | `dasmixer/gui/app.py` | Изменить | 3 |
| 9 | `dasmixer/api/project/dataclasses.py` | Изменить | 4 |
| 10 | `dasmixer/api/project/mixins/protein_mixin.py` | Изменить | 5 |
| 11 | `dasmixer/gui/views/tabs/proteins/enrichment_section.py` | Изменить | 6 |
| 12 | `dasmixer/gui/views/tabs/proteins/protein_identifications_table_view.py` | Изменить | 7 |
| 13 | `dasmixer/gui/views/tabs/proteins/protein_statistics_table_view.py` | Изменить | 8 |
| 14 | `dasmixer/api/export/mztab_export.py` | Изменить | 9 |

**Итого:** 2 новых файла, 12 изменяемых.
