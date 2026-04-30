# STAGE 16 — Версия 0.3.0: Белки из файлов идентификаций + Stacked-файлы

**Дата:** Апрель 2026  
**Версия приложения:** 0.2.0 → **0.3.0**  
**Версия схемы проекта:** 0.2.0 → **0.3.0**  
**Статус:** ✅ Завершено

---

## Обзор

Этап включает три независимые функциональные ветки:

| Ветка | Суть |
|---|---|
| **Белки из файла идентификаций** | Парсер собирает `Protein`-объекты из файлов идентификаций; при сохранении в БД белки записываются с `ON CONFLICT DO NOTHING`; добавлено поле `src_file_protein_id`; UI-флаги импорта белков |
| **Stacked-файлы** | Один файл идентификаций на несколько образцов; новые поля в `identification_file`; новый диалог `ImportStackedDialog`; поддержка MaxQuant evidence.txt |
| **Версионирование и миграция** | `APP_VERSION` и `PROJECT_VERSION` → 0.3.0; SQL-миграция с 3 ALTER TABLE |

---

## 1. Версионирование (0.3.0)

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/versions.py` | `APP_VERSION = "0.3.0"`, `PROJECT_VERSION = "0.3.0"` |
| `pyproject.toml` | `version = "0.2.0"` → `version = "0.3.0"` |

`MIN_SUPPORTED_PROJECT_VERSION = "0.1.0"` **не изменился**.

---

## 2. Миграция БД 0.3.0 + Схема

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/api/project/migrations.py` | Добавлена новая запись в `MIGRATIONS` для версии `"0.3.0"` |
| `dasmixer/api/project/schema.py` | Добавлены новые поля в `CREATE TABLE identification` и `CREATE TABLE identification_file` |

### SQL миграции

```sql
ALTER TABLE identification ADD COLUMN src_file_protein_id TEXT;
ALTER TABLE identification_file ADD COLUMN selection_field TEXT;
ALTER TABLE identification_file ADD COLUMN selection_field_value TEXT;
```

### Новые поля в схеме

**Таблица `identification`** — поле после `isotope_offset`:
```sql
src_file_protein_id TEXT,  -- protein ID from source file; may contain multiple IDs separated by ";"
```

**Таблица `identification_file`** — поля после `file_path`:
```sql
selection_field TEXT,        -- column name used to filter stacked file (nullable)
selection_field_value TEXT,  -- value of selection_field for this record (nullable)
```

---

## 3. IdentificationMixin — новые поля

### Изменённый файл

`dasmixer/api/project/mixins/identification_mixin.py`

### Изменения

| Метод | Изменение |
|---|---|
| `add_identification_file` | Новые параметры `selection_field: str \| None = None`, `selection_field_value: str \| None = None`; SQL INSERT расширен до 5 колонок |
| `add_identifications_batch` | Добавлена 12-я колонка `src_file_protein_id` в кортеж `rows_to_insert` и в SQL INSERT |
| `get_identifications` | Добавлен `i.src_file_protein_id` в SELECT-список |

---

## 4. Рефакторинг IdentificationParser (base.py)

### Изменённый файл

`dasmixer/api/inputs/peptides/base.py`

### Изменения

| Элемент | Изменение |
|---|---|
| Импорты | Добавлен `from dasmixer.api.project.dataclasses import Protein` |
| Классовые атрибуты | Добавлены: `contain_proteins: bool = False`, `can_import_stacked: bool = False`, `sample_id_column: str \| None = None` |
| `__init__` | Добавлены параметры `collect_proteins: bool = False`, `is_uniprot_proteins: bool = False`; инициализирован `self._proteins: dict[str, Protein] = {}` |
| `get_sample_ids` | Добавлен метод-заглушка, выбрасывающий `NotImplementedError` |
| `parse_batch` | Сигнатура изменена с `AsyncIterator[tuple[pd.DataFrame, ...]]` → `AsyncIterator[pd.DataFrame]`; обновлён docstring |
| `proteins` | Добавлено свойство `@property`, возвращающее `self._proteins` |

---

## 5. SimpleTableImporter — ColumnRenames, get_proteins, parse_batch

### Изменённый файл

`dasmixer/api/inputs/peptides/table_importer.py`

### Изменения

| Элемент | Изменение |
|---|---|
| `ColumnRenames` | Добавлено поле `src_file_protein_id: str \| None = None` |
| Импорты | Добавлен `from dasmixer.api.project.dataclasses import Protein` |
| `SimpleTableImporter.get_proteins` | Новый метод — извлекает `Protein`-объекты из батча, поддерживает разделение `;` |
| `SimpleTableImporter.parse_batch` | Возвращает `AsyncIterator[pd.DataFrame]`; добавлен сбор белков через `self.get_proteins()` и `self._proteins.update()` |
| `LargeCSVImporter.parse_batch` | Аналогичное изменение сигнатуры; добавлен сбор белков |

### `get_proteins()` логика

```python
if self.renames.src_file_protein_id is None:
    return None  # parser не предоставляет белки
if 'src_file_protein_id' not in df.columns:
    return {}    # в этом батче нет белков
# иначе: собирает Protein-объекты с is_uniprot=self.is_uniprot_proteins
```

---

## 6. MaxQuant — stacked поддержка

### Изменённый файл

`dasmixer/api/inputs/peptides/MQ_Evidences.py`

### Изменения

Добавлены классовые атрибуты в `MaxQuantEvidenceParser`:
```python
can_import_stacked: bool = True
sample_id_column: str = 'Raw file'
```

---

## 7. import_handlers — основной pipeline белков

### Изменённый файл

`dasmixer/gui/views/tabs/samples/import_handlers.py`

### Изменения

| Элемент | Изменение |
|---|---|
| `import_identification_files` | Добавлены параметры `collect_proteins: bool = False`, `is_uniprot_proteins: bool = False` |
| Парсер instantiation | Передача `collect_proteins` и `is_uniprot_proteins` в конструктор парсера |
| Цикл парсинга | Убрана tuple-распаковка (`batch_tuple[0]` → `batch`); упрощён merge |
| Сохранение белков | После цикла парсинга — если `collect_proteins` и `parser.proteins` — сбор DataFrame и вызов `_save_proteins_batch()` |
| `_save_proteins_batch` | Новый приватный метод — SQL `INSERT ... ON CONFLICT(id) DO NOTHING` |

---

## 8. UI: флаги белков в ImportSingleDialog и ImportPatternDialog

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/gui/views/tabs/samples/dialogs/import_single_dialog.py` | Добавлены чекбоксы «Import protein IDs from file» и «Proteins are UniProt IDs» (только если парсер поддерживает `contain_proteins=True`) |
| `dasmixer/gui/views/tabs/samples/dialogs/import_pattern_dialog.py` | Аналогично — чекбоксы импорта белков в диалоге паттерна |

### UI-представление

```
┌─ Protein import options: ───────────────────┐
│ ☐ Import protein IDs from file              │
│ ☐ Proteins are UniProt IDs                  │
└─────────────────────────────────────────────┘
```

Чекбоксы передаются в callback как `collect_proteins` и `is_uniprot_proteins`.

---

## 9. ImportModeDialog — кнопка stacked

### Изменённый файл

`dasmixer/gui/views/tabs/samples/dialogs/import_mode_dialog.py`

### Изменения

- Добавлен параметр `on_stacked_callback` в `__init__`
- Добавлен обработчик `_on_stacked`
- В `show()`: проверка `parser_class.can_import_stacked` — если True, добавляется кнопка «Import stacked file» (только для identifications)

---

## 10. ImportStackedDialog (новый файл)

### Созданный файл

`dasmixer/gui/views/tabs/samples/dialogs/import_stacked_dialog.py` (292 строки)

### Описание

Диалог для импорта stacked-файла идентификаций (один файл — несколько образцов).

### Flow

1. **FilePicker** — выбор файла
2. **Sample field** — редактируемое поле с названием колонки образца (по умолчанию из `parser.sample_id_column`)
3. **Get samples list** — создаёт экземпляр парсера, вызывает `parser.get_sample_ids()`, возвращает список уникальных ID образцов
4. **Сопоставление** — для каждого ID в файле: чекбокс включения + TextField с автоподстановкой имени образца из проекта (если совпадает точно)
5. **Import** — для каждого включённого образца: создание `identification_file` с `selection_field`/`selection_field_value`, фильтрация батчей при парсинге

### Flet 0.80.5 API

- `ft.ElevatedButton(content=ft.Text(...))`
- `ft.FilePicker().pick_files(...)` — вызов напрямую
- `ft.Colors.*`, `ft.Icons.*`, `ft.FontWeight.*`
- `ft.AlertDialog` через `page.overlay.append()`
- `page.run_task()` для асинхронных обработчиков

---

## 11. Stacked import handler + samples_tab

### Изменённые файлы

| Файл | Изменение |
|---|---|
| `dasmixer/gui/views/tabs/samples/import_handlers.py` | Добавлен метод `import_identification_files_stacked` |
| `dasmixer/gui/views/tabs/samples/samples_tab.py` | Добавлены `on_stacked_callback` в `ImportModeDialog` и метод `_on_import_identifications_stacked` |

### `import_identification_files_stacked` логика

1. Показывает `ProgressDialog` с per-sample прогрессом
2. Для каждого entry: находит sample по имени, получает spectra_file
3. Создаёт `identification_file` с `selection_field`/`selection_field_value`
4. Парсит файл, фильтрует батчи по `file_sample_id`
5. Мержит с spectra_mapping, батчево вставляет идентификации

---

## 12. protein_map — use_src_protein_ids

### Изменённый файл

`dasmixer/api/calculations/peptides/protein_map.py`

### Изменения

| Элемент | Изменение |
|---|---|
| `map_proteins` | Добавлен параметр `use_src_protein_ids: bool = False` с описанием в docstring |
| Pre-BLAST обработка | В основном цикле, после получения `batch_data`: фильтрация строк с `src_file_protein_id`, создание exact-match записей (`identity=1.0`) в `all_res`, bypass BLAST для этих строк |

### Алгоритм

```
batch_data → фильтр по src_file_protein_id
├── has_src_protein → создание exact-match peptide_match (identity=1.0)
└── ~has_src_protein → BLAST (как обычно)

Поддержка множественных ID через ";"
```

---

## Итоговая таблица изменяемых файлов

| № | Файл | Статус | Задача |
|---|---|---|---|
| 1 | `dasmixer/versions.py` | Изменён | 1 |
| 2 | `pyproject.toml` | Изменён | 1 |
| 3 | `dasmixer/api/project/migrations.py` | Изменён | 2 |
| 4 | `dasmixer/api/project/schema.py` | Изменён | 2 |
| 5 | `dasmixer/api/project/mixins/identification_mixin.py` | Изменён | 3 |
| 6 | `dasmixer/api/inputs/peptides/base.py` | Изменён | 4, 9 |
| 7 | `dasmixer/api/inputs/peptides/table_importer.py` | Изменён | 5, 9 |
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

## Критические изменения для разработчиков

### Новые поля в БД

При открытии существующего проекта 0.1.0 / 0.2.0 будет автоматически применена миграция с 3 ALTER TABLE. Для новых проектов поля уже присутствуют в CREATE TABLE.

### parse_batch API breaking change

Сигнатура `parse_batch` изменена с `AsyncIterator[tuple[pd.DataFrame, pd.DataFrame | None]]` на `AsyncIterator[pd.DataFrame]`. Все существующие парсеры и код, вызывающий `parse_batch`, должны быть обновлены.

### Белки из файлов идентификаций

- Парсеры, поддерживающие сбор белков, должны установить `contain_proteins = True` и определить `ColumnRenames.src_file_protein_id`
- `get_proteins()` возвращает `dict[str, Protein]` — белковые объекты сохраняются с `ON CONFLICT(id) DO NOTHING`
- Флаг `use_src_protein_ids` в `protein_map.py` позволяет создавать exact-match peptide_match записи без BLAST

### Stacked-файлы

- Парсеры, поддерживающие stacked, должны установить `can_import_stacked = True` и `sample_id_column`
- `get_sample_ids()` должна быть реализована в конкретном парсере
- Каждый stacked-образец получает отдельную запись `identification_file` с `selection_field`/`selection_field_value`
- Фильтрация батчей происходит на уровне `import_identification_files_stacked` в import_handlers.py

---

**Автор:** Goose AI  
**Дата:** Апрель 2026  
**Версия документа:** 1.0