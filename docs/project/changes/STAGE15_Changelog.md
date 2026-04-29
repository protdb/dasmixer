# STAGE 15 — Версия 0.2.0: Миграции, обогащение белков, улучшения таблиц

**Дата:** Апрель 2026  
**Версия приложения:** 0.1.0 → **0.2.0**  
**Версия схемы проекта:** 0.1.0 → **0.2.0**  
**Статус:** ✅ Завершено

---

## Обзор

Этап включает централизацию управления версиями, добавление системы миграций проекта для обновления схемы БД без потери данных, расширение модели белков полями таксономии (taxon_id, organism_name), интеграцию обогащения белков из UniProt с прогресс-диалогом, улучшение таблиц белков (новые колонки + виртуальные поля из UniProt), и поддержку новых полей в экспорте MzTab.

---

## Задача 1 — Централизация управления версиями

### Создаваемые файлы

| Файл | Описание |
|---|---|
| `dasmixer/versions.py` | **Создан** — три константы: `APP_VERSION`, `PROJECT_VERSION`, `MIN_SUPPORTED_PROJECT_VERSION` |

### Изменения в существующих файлах

| Файл | Изменение |
|---|---|
| `dasmixer/__init__.py` | Добавлен реэкспорт `__version__` из `versions.py` |
| `pyproject.toml` | `version = "0.1.0"` → `version = "0.2.0"` |
| `dasmixer/main.py` | Заменён захардкоженный `typer.echo("DASMixer version 0.1.0")` на `typer.echo(f"DASMixer version {APP_VERSION}")` |
| `dasmixer/api/project/schema.py` | Импорт `PROJECT_VERSION` из `versions.py`, замена хардкода в `DEFAULT_METADATA['version']` |

### Детали

```python
# dasmixer/versions.py
APP_VERSION = "0.2.0"
PROJECT_VERSION = "0.2.0"
MIN_SUPPORTED_PROJECT_VERSION = "0.1.0"
```

---

## Задача 2 — MigrationMixin: система миграций проекта

### Создаваемые файлы

| Файл | Описание |
|---|---|
| `dasmixer/api/project/migrations.py` | **Создан** — `MigrationError`, `MIGRATIONS`, `MigrationMixin` |

### Изменения в существующих файлах

| Файл | Изменение |
|---|---|
| `dasmixer/api/project/project.py` | `MigrationMixin` добавлен в MRO после `ProjectLifecycle` |

### Класс `MigrationMixin`

```python
class MigrationMixin:
    async def get_project_version(self) -> str
    async def needs_migration(self) -> bool
    async def is_version_too_new(self) -> bool
    async def apply_migrations(self) -> None
```

### Алгоритм `apply_migrations`

1. Читает `project_metadata.version`
2. Если `version == PROJECT_VERSION` — ничего не делает
3. Если `version < MIN_SUPPORTED_PROJECT_VERSION` — `MigrationError`
4. Итерирует `MIGRATIONS`, пропускает версии <= текущей
5. Применяет миграции через `executescript` в транзакции
6. При ошибке — `rollback`, `logger.exception`, `MigrationError`
7. При успехе — обновляет `project_metadata.version = PROJECT_VERSION`

### Первая миграция (`0.1.0 → 0.2.0`)

```sql
ALTER TABLE protein ADD COLUMN taxon_id INTEGER;
ALTER TABLE protein ADD COLUMN organism_name TEXT;
```

---

## Задача 3 — UI диалога миграции

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/gui/app.py` | Добавлены методы: `_check_project_version`, `_show_version_warning_dialog`, `_show_migration_dialog`, `_run_migration`. Вызов вставлен в `open_project`. Добавлен `import asyncio` |

### Диалог предупреждения (версия проекта слишком новая)

- **Заголовок:** "Incompatible Project Version"
- **Содержание:** Предупреждение о том, что проект создан в более новой версии DASMixer
- **Кнопки:** `[OK]`

### Диалог предложения миграции

- **Заголовок:** "Project Update Required"
- **Содержание:** Объяснение необходимости обновления + предупреждение о бэкапе
- **Кнопки:** `[Skip]` `[Update]`

### Миграция с прогрессом

- Используется `ProgressDialog` через `page.overlay`
- Показывает прогресс "Applying migrations..." → "Done"
- При ошибке — закрывает диалог и показывает `_show_error()`
- При успехе — snack_bar: "Project updated to {PROJECT_VERSION}"

### Flet 0.80.5 API

- `ft.ElevatedButton(content=ft.Text("..."))` для кнопок
- `ft.Colors.RED_400` / `ft.Colors.GREEN_400` для цветов
- `page.overlay.append(dialog)` + `dialog.open = True` для показа

---

## Задача 4 — Расширение модели данных белков

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/api/project/schema.py` | `CREATE TABLE protein` — добавлены `taxon_id INTEGER`, `organism_name TEXT` |
| `dasmixer/api/project/dataclasses.py` | Класс `Protein` — добавлены `taxon_id: int | None`, `organism_name: str | None`; обновлены `to_dict()` и `from_dict()` |

### Новые поля

| Поле | Тип | Описание |
|---|---|---|
| `taxon_id` | `int | None` | NCBI Taxonomy ID |
| `organism_name` | `str | None` | Название организма |

---

## Задача 5 — Обновление ProteinMixin

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/api/project/mixins/protein_mixin.py` | Исправлены и расширены все методы работы с белками |

### Исправления

| Метод | Изменение |
|---|---|
| `update_protein` | 🔧 Исправлена синтаксическая ошибка SQL (пропущена запятая), добавлены `taxon_id`, `organism_name`, добавлен `protein.id` в params |
| `add_protein` | Добавлены поля `taxon_id`, `organism_name` в INSERT |
| `add_proteins_batch` | Добавлены поля в кортеж `rows_to_insert` и в SQL INSERT |
| `get_protein` | `taxon_id` / `organism_name` переданы в конструктор `Protein(...)` |
| `get_proteins` | Аналогично — новые поля в конструктор |
| `get_protein_results_joined` | Добавлены `p.name AS name`, `p.taxon_id`, `p.organism_name` в SELECT |
| `get_protein_statistics` | Добавлены поля `p.name`, `p.taxon_id`, `p.organism_name` в CTE и GROUP BY; добавлена загрузка `uniprot_data` в DataFrame после запроса |

### Обновлённый SQL `get_protein_results_joined`

```sql
SELECT
    pir.id, pir.protein_id, pir.sample_id,
    s.name AS sample, sub.name AS subset,
    p.gene, p.name AS name, p.sequence,
    p.taxon_id, p.organism_name,
    pir.peptide_count, pir.uq_evidence_count AS unique_evidence_count,
    pir.coverage AS coverage_percent, pir.intensity_sum,
    pqr_empai.rel_value AS EmPAI, pqr_ibaq.rel_value AS iBAQ,
    pqr_nsaf.rel_value AS NSAF, pqr_top3.rel_value AS Top3
FROM protein_identification_result pir
JOIN sample s ON pir.sample_id = s.id
LEFT JOIN subset sub ON s.subset_id = sub.id
LEFT JOIN protein p ON pir.protein_id = p.id
...
```

### Обновлённый CTE `get_protein_statistics`

```sql
WITH protein_stats AS (
    SELECT
        p.id AS protein_id, p.name AS name, p.gene, p.fasta_name,
        p.taxon_id, p.organism_name,
        COUNT(DISTINCT pir.sample_id) AS samples,
        COUNT(DISTINCT s.subset_id) AS subsets,
        SUM(pir.peptide_count) AS PSMs,
        CAST(ROUND(AVG(pir.peptide_count)) AS INTEGER) AS mean_psm,
        SUM(pir.uq_evidence_count) AS unique_evidence,
        CAST(ROUND(AVG(pir.uq_evidence_count)) AS INTEGER) AS mean_unique
    FROM ...
    GROUP BY p.id, p.name, p.gene, p.fasta_name, p.taxon_id, p.organism_name
)
SELECT * FROM protein_stats WHERE samples >= ? AND subsets >= ? ...
```

---

## Задача 6 — EnrichmentSection: подключение логики обогащения

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/gui/views/tabs/proteins/enrichment_section.py` | `print("NOT IMPLEMENTED")` → `_run_enrich` с `ProgressDialog` |

### Метод `_run_enrich`

1. Читает состояние чекбоксов (`force_update`, `overwrite_fasta`)
2. Открывает `ProgressDialog` через `page.overlay`
3. Итерирует async generator `enrich_proteins(project, force_update, overwrite_fasta)`
4. Обновляет прогресс: `f"Processing {processed}/{total}: {protein_id}"`
5. При ошибке — `logger.exception`, `show_snack` с `ft.Colors.RED_400`
6. При успехе — `show_snack`: "Enrichment complete: {processed} proteins processed"

---

## Задача 7 — ProteinIdentificationsTableView: новые колонки

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/gui/views/tabs/proteins/protein_identifications_table_view.py` | Добавлены 3 записи в `header_name_mapping` |

### Новые колонки в `header_name_mapping`

| Ключ | Заголовок |
|---|---|
| `name` | Protein Name |
| `taxon_id` | Taxon ID |
| `organism_name` | Organism |

`taxon_id` и `organism_name` не включены в `default_columns` (скрытые, доступны через шестерёнку).

---

## Задача 8 — ProteinStatisticsTableView: новые колонки + виртуальные поля

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/gui/views/tabs/proteins/protein_statistics_table_view.py` | Новые колонки, `VIRTUAL_FIELD_FUNCS`, переписан `get_data()` |

### Новые колонки в `header_name_mapping`

| Ключ | Заголовок |
|---|---|
| `name` | Protein Name |
| `taxon_id` | Taxon ID |
| `organism_name` | Organism |
| `pathways` | Pathways |
| `mol_functions` | Molecular Functions |
| `bio_processes` | Biological Processes |
| `subcellular_locations` | Subcellular Locations |

### Константа `VIRTUAL_FIELD_FUNCS`

```python
from dasmixer.utils.show_pathways import (
    get_pathways_from_uniprot,
    get_mol_functions_from_uniprot,
    get_biological_processes_from_uniprot,
    get_locations_from_uniprot,
)

VIRTUAL_FIELD_FUNCS: dict[str, callable] = {
    'pathways': get_pathways_from_uniprot,
    'mol_functions': get_mol_functions_from_uniprot,
    'bio_processes': get_biological_processes_from_uniprot,
    'subcellular_locations': get_locations_from_uniprot,
}
```

### Переписанный `get_data()`

1. Получает DataFrame из `project.get_protein_statistics(...)`
2. Для каждого виртуального поля вызывает соответствующую функцию из `VIRTUAL_FIELD_FUNCS` на каждом `uniprot_data` объекте
3. Заполняет DataFrame display-значениями, формирует `tooltip_df` с полными значениями
4. Удаляет служебную колонку `uniprot_data` перед возвратом
5. Возвращает `(df, tooltip_df)`

**Примечание:** Виртуальные поля НЕ добавлены в `column_filter_mapping` — они только для отображения и экспорта, не для фильтрации.

---

## Задача 9 — MzTab экспорт: taxon_id / organism_name

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/api/export/mztab_export.py` | Обновлён SQL-запрос и вызов `doc.add_protein()` |

### SQL запрос

Добавлены в SELECT:
```sql
    p.name           AS name,
    p.taxon_id,
    p.organism_name
```

### Вызов `doc.add_protein()`

- `description` → `first_row.get("name") or None` (было `first_row.get("protein_name")`)
- Добавлены новые параметры:
  - `taxid=int(taxid_val) if taxid_val is not None else None`
  - `species=species_val or None`

---

## Итоговая таблица изменяемых файлов

| № | Файл | Статус | Задача |
|---|---|---|---|
| 1 | `dasmixer/versions.py` | **Создан** | 1 |
| 2 | `dasmixer/__init__.py` | Изменён | 1 |
| 3 | `pyproject.toml` | Изменён | 1 |
| 4 | `dasmixer/main.py` | Изменён | 1 |
| 5 | `dasmixer/api/project/schema.py` | Изменён | 1, 4 |
| 6 | `dasmixer/api/project/migrations.py` | **Создан** | 2 |
| 7 | `dasmixer/api/project/project.py` | Изменён | 2 |
| 8 | `dasmixer/gui/app.py` | Изменён | 3 |
| 9 | `dasmixer/api/project/dataclasses.py` | Изменён | 4 |
| 10 | `dasmixer/api/project/mixins/protein_mixin.py` | Изменён | 5 |
| 11 | `dasmixer/gui/views/tabs/proteins/enrichment_section.py` | Изменён | 6 |
| 12 | `dasmixer/gui/views/tabs/proteins/protein_identifications_table_view.py` | Изменён | 7 |
| 13 | `dasmixer/gui/views/tabs/proteins/protein_statistics_table_view.py` | Изменён | 8 |
| 14 | `dasmixer/api/export/mztab_export.py` | Изменён | 9 |

**Итого:** 2 новых файла, 12 изменяемых.

---

## Критические изменения для разработчиков

### Версионирование

Все версии теперь централизованы в `dasmixer/versions.py`. Не используйте захардкоженные строки версий в коде.

### Миграции

При изменении схемы БД:
1. Добавьте новую запись в `MIGRATIONS` в `migrations.py`
2. Обновите `CREATE_SCHEMA_SQL` в `schema.py`
3. Поднимите `PROJECT_VERSION` в `versions.py`

### Новые поля белка

`taxon_id` и `organism_name` — nullable. При миграции существующие строки получают `NULL`. Для новых проектов поля создаются в `CREATE TABLE`.

### Виртуальные поля таблиц

Виртуальные поля (`pathways`, `mol_functions`, `bio_processes`, `subcellular_locations`) вычисляются из `uniprot_data` в `get_data()` table view. Они НЕ хранятся в БД и НЕ добавляются в фильтр.

---

**Автор:** Goose AI  
**Дата:** Апрель 2026  
**Версия документа:** 1.0
