# DASMixer 0.4.0 — Спецификация доработок

**Версия:** 0.4.0  
**Дата:** май 2026  
**Источник требований:** `docs/project/spec/040_REQUIREMENTS.md`

---

## Содержание

1. [Рефакторинг `manage_samples_view`](#1-рефакторинг-manage_samples_view)
2. [Массовые операции с образцами](#2-массовые-операции-с-образцами)
3. [Улучшения процесса импорта — режим On duplicates](#3-улучшения-процесса-импорта--режим-on-duplicates)
4. [Повышение версии](#4-повышение-версии)
5. [Декомпозиция задач](#5-декомпозиция-задач)

---

## 1. Рефакторинг `manage_samples_view`

### 1.1 Цель

Текущий файл `dasmixer/gui/views/manage_samples_view.py` содержит >800 строк и совмещает несколько несвязанных ответственностей. Необходимо превратить его в Python-пакет, разбив на файлы по принципу единственной ответственности.

### 1.2 Новая структура пакета

```
dasmixer/gui/views/manage_samples_view/
├── __init__.py                  # реэкспорт ManageSamplesView
├── manage_samples_view.py       # класс ManageSamplesView (ft.View)
├── sample_panel.py              # класс SampleViewPanel (ft.Container)
├── update_row.py                # класс UpdateRow — строка Update/loader/поля порогов
└── data_manager.py              # класс SampleDataManager — логика кэша и обновлений
```

`__init__.py` содержит только:
```python
from .manage_samples_view import ManageSamplesView
__all__ = ["ManageSamplesView"]
```

Все остальные части проекта, импортирующие `ManageSamplesView`, продолжают работать без изменений — интерфейс класса не меняется.

### 1.3 `data_manager.py` — `SampleDataManager`

Инкапсулирует все операции с кэшем статистики образцов, которые ранее были разбросаны по `ManageSamplesView`.

**Конструктор:**
```python
class SampleDataManager:
    def __init__(self, project: Project):
        self.project = project
```

**Методы:**

| Метод | Описание |
|---|---|
| `async load_all() -> tuple[list[Sample], dict[int, dict], int]` | Загружает образцы, весь кэш статистики, количество инструментов. Возвращает `(samples, cached_stats, tools_count)` |
| `async refresh_single(sample_id: int, save_cache: bool = True) -> tuple[Sample \| None, dict]` | Пересчитывает статистику одного образца, записывает в кэш. Возвращает `(sample, stats)` |
| `async refresh_all_fresh() -> tuple[list[Sample], dict[int, dict], int]` | Полный пересчёт статистики всех образцов (режим Update). Вызывает `get_sample_stats` для каждого, апсёртит кэш, сохраняет проект |
| `async drop_empty_files() -> tuple[int, int]` | Удаляет пустые spectra- и identification-файлы. Возвращает `(deleted_spectra, deleted_idents)` |
| `async get_sample_detail(sample_id: int) -> list[dict]` | Делегирует `project.get_sample_detail(sample_id)` |

**Логика `drop_empty_files`:**
1. `SELECT id FROM identification_file WHERE NOT EXISTS (SELECT 1 FROM identification WHERE ident_file_id = identification_file.id)` → удалить через `project.delete_identification_file` для каждого
2. `SELECT id FROM spectre_file WHERE NOT EXISTS (SELECT 1 FROM spectre WHERE spectre_file_id = spectre_file.id)` → удалить через `project.delete_spectra_file` для каждого
3. Возвратить счётчики удалённых

### 1.4 `update_row.py` — `UpdateRow`

Отдельный Flet-компонент для верхней строки управления (аналогично секциям в `samples_tab`).

```python
class UpdateRow(ft.Container):
    def __init__(self, on_update_clicked: Callable[[], Awaitable[None]]):
        ...

    # Публичные свойства/методы:
    def set_loading(self, visible: bool) -> None
    def get_thresholds(self) -> tuple[int, int]  # (min_proteins, min_idents)
```

Содержит: кнопку Update, ProgressRing, поля `min_proteins` / `min_idents`.

### 1.5 `sample_panel.py` — `SampleViewPanel`

Инкапсулирует построение одной панели образца (`ft.ExpansionPanel`).

```python
class SampleViewPanel(ft.Container):
    def __init__(
        self,
        sample: Sample,
        stats: dict,
        tools_count: int,
        min_proteins: int,
        min_idents: int,
        on_action: Callable,   # callback для действий над образцом
    ):
        ...

    async def build(self) -> ft.ExpansionPanel
    def update_stats(self, stats: dict, min_proteins: int, min_idents: int) -> None
    
    # Чекбокс выбора образца:
    @property
    def is_selected(self) -> bool
    def set_selected(self, value: bool) -> None
```

Содержит:
- чекбокс в заголовке панели (слева от статус-иконки)
- весь текущий header (`_build_sample_header`)
- весь текущий body (`_build_sample_body`)

Вспомогательные module-level функции `_build_sample_header` и `_empty_stats` переезжают в этот файл.

### 1.6 `manage_samples_view.py` — `ManageSamplesView`

После рефакторинга `ManageSamplesView` становится тонким оркестратором:
- хранит ссылки на `SampleDataManager`, `UpdateRow`, `MassOperationsRow`
- делегирует построение панелей в `SampleViewPanel`
- делегирует загрузку/кэширование данных в `SampleDataManager`
- обрабатывает навигацию и коллбэки

---

## 2. Массовые операции с образцами

### 2.1 Чекбокс в заголовке панели

В `SampleViewPanel` чекбокс выбора (`ft.Checkbox`) добавляется **в самое начало** строки заголовка — левее иконки статуса. Виден всегда, независимо от состояния (свёрнута/развёрнута панель).

При изменении состояния чекбокса вызывается коллбэк `on_selection_changed(sample_id: int, selected: bool)`, передаваемый в `SampleViewPanel`. `ManageSamplesView` ведёт множество `_selected_ids: set[int]`.

### 2.2 Строка `MassOperationsRow`

Новый файл: `dasmixer/gui/views/manage_samples_view/mass_operations_row.py`

```python
class MassOperationsRow(ft.Container):
    def __init__(
        self,
        on_select_all: Callable,
        on_deselect_all: Callable,
        on_outlier: Callable,
        on_drop_file: Callable,
        on_assign_subset: Callable,
        on_delete: Callable,
        on_drop_empty: Callable,
    ):
```

Располагается в `ManageSamplesView._build_body()` **между** `UpdateRow` и `ExpansionPanelList`.

**Внешний вид строки:**

```
[ Select All ] [ Deselect All ] | [ Outlier ] [ Drop file ] [ Assign group ] [ Delete ] | [ Drop empty files ]
```

- Разделитель `|` между группами — `ft.VerticalDivider`
- `[ Drop empty files ]` отделён вторым `VerticalDivider` и визуально обособлен (иной цвет иконки или фона кнопки — на усмотрение разработчика)
- Все кнопки всегда видны; кнопки, требующие выбора образцов (Outlier, Drop file, Assign group, Delete), не блокируются — при нажатии без выбора показывают snack "No samples selected"

### 2.3 Действие «Select All» / «Deselect All»

- `Select All`: устанавливает чекбоксы всех видимых панелей в `True`, добавляет все `sample_id` в `_selected_ids`
- `Deselect All`: сбрасывает все чекбоксы, очищает `_selected_ids`
- После изменения: обновить все панели через `.update()`

### 2.4 Действие «Outlier»

**Логика определения нового состояния:**
```python
selected_samples = [s for s in self._samples if s.id in self._selected_ids]
all_outliers = all(s.outlier for s in selected_samples)
new_outlier = not all_outliers  # если все аутлаеры — сбросить; иначе — присвоить
```

**Выполнение:**
1. Для каждого выбранного образца: `sample.outlier = new_outlier`, вызов `project.update_sample(sample)`
2. Обновить панели затронутых образцов (перестроить header)
3. Показать snack: `"Outlier set for N sample(s)"` или `"Outlier cleared for N sample(s)"`

Диалог подтверждения **не требуется** (действие обратимо).

### 2.5 Действие «Drop file»

Открывает диалог `DropFileDialog` из отдельного файла:

**Файл:** `dasmixer/gui/views/manage_samples_view/dialogs/drop_file_dialog.py`

#### 2.5.1 Первый диалог — выбор типа удаления

```
┌─────────────────────────────────────────┐
│  Drop files — select type               │
│                                         │
│  ○ Spectra files (all)                  │
│  ○ Spectra files (keep first)           │
│  ○ Spectra files (keep last)            │
│  ○ Identification files (all)           │
│  ○ Identification files by tool:        │
│    [ Dropdown: Tool name ▼ ]            │
│                                         │
│              [ Cancel ]  [ Confirm ]    │
└─────────────────────────────────────────┘
```

- RadioGroup с 5 вариантами (значения: `spectra_all`, `spectra_keep_first`, `spectra_keep_last`, `ident_all`, `ident_by_tool`)
- Dropdown инструментов **всегда виден**, но активен (enabled) только при выборе `ident_by_tool`; заполняется из `project.get_tools()`
- При нажатии Confirm — переход ко второму диалогу

#### 2.5.2 Второй диалог — список файлов и предупреждение

Перед показом — вычислить список файлов для удаления:

| Режим | Запрос |
|---|---|
| `spectra_all` | все `spectre_file` у выбранных образцов |
| `spectra_keep_first` | все `spectre_file` кроме с минимальным `id` |
| `spectra_keep_last` | все `spectre_file` кроме с максимальным `id` |
| `ident_all` | все `identification_file` у выбранных образцов |
| `ident_by_tool` | все `identification_file` с `tool_id = <выбранный>` у выбранных образцов |

```
┌──────────────────────────────────────────────────────────┐
│  Confirm deletion                                         │
│                                                           │
│  ⚠ This action cannot be undone. Source files on disk    │
│    are not affected — only project data will be removed.  │
│                                                           │
│  Files to be deleted:                                     │
│  ┌────────────────────────────────────────────────────┐  │
│  │ [type]  ID=12  /home/.../sample1/file.mgf (short)  │  │
│  │ [type]  ID=13  /home/.../sample2/ids.csv (short)   │  │
│  │ ...                                                 │  │
│  └────────────────────────────────────────────────────┘  │
│  (прокручиваемый список, высота ~200px)                   │
│                                                           │
│                        [ Cancel ]  [ Delete ]             │
└──────────────────────────────────────────────────────────┘
```

Поля в строке: тип файла (Spectra / Identification), ID, сокращённый путь (последние 2 компонента пути через `Path(...).parts[-2:]`).

Список отображается в `ft.ListView` с `height=200`, прокрутка встроенная.

**Выполнение после подтверждения:**
1. Для `spectra_*` — вызов `project.delete_spectra_file(id)` для каждого
2. Для `ident_*` — вызов `project.delete_identification_file(id)` для каждого
3. Обновить кэш затронутых образцов через `SampleDataManager.refresh_single(sample_id)`
4. Перестроить панели
5. Snack: `"Deleted N file(s)"`

**Класс диалога:**

```python
class DropFileDialog:
    def __init__(
        self,
        project: Project,
        page: ft.Page,
        selected_sample_ids: list[int],
        on_complete: Callable[[], Awaitable[None]],
    ):
        ...
    
    async def show(self) -> None
```

### 2.6 Действие «Assign subset»

**Файл:** `dasmixer/gui/views/manage_samples_view/dialogs/assign_subset_dialog.py`

```
┌────────────────────────────────────────┐
│  Assign comparison group               │
│                                        │
│  Group: [ Dropdown: группы ▼ ]        │
│                                        │
│             [ Cancel ]  [ Assign ]     │
└────────────────────────────────────────┘
```

**Выполнение:**
1. Получить выбранный `subset_id` из dropdown
2. Для каждого `sample_id` из `_selected_ids`:
   - получить `sample = await project.get_sample(sample_id)`
   - `sample.subset_id = new_subset_id`
   - `await project.update_sample(sample)`
3. Обновить `_samples` в памяти (список в `ManageSamplesView`)
4. Перестроить заголовки панелей (там отображается `subset_name`)
5. Snack: `"Group assigned for N sample(s)"`

**Класс диалога:**

```python
class AssignSubsetDialog:
    def __init__(
        self,
        project: Project,
        page: ft.Page,
        selected_sample_ids: list[int],
        on_complete: Callable[[], Awaitable[None]],
    ):
        ...
    
    async def show(self) -> None
```

### 2.7 Действие «Delete» (массовое)

**Диалог подтверждения** — использует существующий `_confirm`-паттерн, но расширенный до списка:

```
┌────────────────────────────────────────────┐
│  Delete samples?                            │
│                                             │
│  The following samples will be deleted:     │
│  ┌─────────────────────────────────────┐   │
│  │ • Sample A                          │   │
│  │ • Sample B                          │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  All spectra, identifications and peptide   │
│  matches will be permanently removed.       │
│                                             │
│              [ Cancel ]  [ Delete ]         │
└────────────────────────────────────────────┘
```

**Выполнение:**
1. `await project.delete_sample(sample_id)` для каждого
2. Удалить из `_samples`
3. Перестроить `ExpansionPanelList`
4. Очистить `_selected_ids`
5. Snack: `"Deleted N sample(s)"`

Диалог реализован inline в `ManageSamplesView` (не отдельный файл — достаточно простой).

### 2.8 Действие «Drop empty files»

Нажатие кнопки **без диалога** выполняет:
1. Вызов `SampleDataManager.drop_empty_files()`
2. Обновление кэша всех образцов (полный `load_all` + перестройка панелей)
3. Snack: `"Removed X spectra file(s) and Y identification file(s)"` или `"No empty files found"`

---

## 3. Улучшения процесса импорта — режим «On duplicates»

### 3.1 Область применения

RadioGroup "On duplicates" добавляется **только** в диалог `ImportPatternDialog` (`import_pattern_dialog.py`).

`ImportSingleDialog` и `ImportStackedDialog` — **не затрагиваются**.

### 3.2 Расположение в диалоге

Новый блок `on_duplicates_group` добавляется в `ImportPatternDialog.show()` сразу после `dropdown_row` (строка с parser/group) и до блока protein options:

```
[ parser dropdown / group dropdown ]
─────────────────────────────────────
On duplicates:
  ● Skip (default)
  ○ Reload
  ○ Add as new
─────────────────────────────────────
[ protein import options, если применимо ]
[ Preview Files ]
[ список файлов ]
```

Визуально — в `ft.Container` с рамкой, аналогично существующим секциям диалога.

```python
on_duplicates_group = ft.RadioGroup(
    value="skip",
    content=ft.Column([
        ft.Radio(value="skip", label="Skip"),
        ft.Radio(value="reload", label="Reload"),
        ft.Radio(value="add_as_new", label="Add as new"),
    ], spacing=2),
)
```

Состояние хранится только в переменной диалога (сессионное, не сохраняется в config).

### 3.3 Передача режима в `ImportHandlers`

При нажатии Import в `ImportPatternDialog._start_import`:
```python
on_duplicates = on_duplicates_group.value  # "skip" | "reload" | "add_as_new"
await self.on_import_callback(
    included_files,
    ...,
    on_duplicates=on_duplicates,
)
```

Сигнатуры `ImportHandlers.import_spectra_files` и `ImportHandlers.import_identification_files` расширяются параметром `on_duplicates: str = "skip"`.

### 3.4 Логика дедупликации в `ImportHandlers`

Дубликат определяется по **полному пути к файлу** (сравнение `str(file_path)` с полем `path` в `spectre_file` или `file_path` в `identification_file`).

#### 3.4.1 Для spectra (`import_spectra_files`)

Перед созданием `spectra_file` записи:

```python
existing_sf = await project.get_spectra_file_by_path(str(file_path))
# get_spectra_file_by_path — новый метод в SpectraMixin (см. п. 3.5)

if existing_sf is not None:
    if on_duplicates == "skip":
        skipped_count += 1
        continue
    elif on_duplicates == "reload":
        await project.delete_spectra_file(existing_sf['id'])
        # каскадно удаляет spectra + identification_files + identifications
        # затем продолжаем создание нового spectra_file как обычно
    # "add_as_new": ничего не делаем, просто создаём новый spectra_file
```

После завершения цикла по файлам, если `skipped_count > 0`:
```python
show_snack(page, f"{skipped_count} file(s) skipped (already imported)", Colors.ORANGE_400)
```

#### 3.4.2 Для identifications (`import_identification_files`)

Перед созданием `identification_file` записи:

```python
existing_if = await project.get_identification_file_by_path(str(file_path))
# get_identification_file_by_path — новый метод в IdentificationMixin (см. п. 3.5)

if existing_if is not None:
    if on_duplicates == "skip":
        skipped_count += 1
        continue
    elif on_duplicates == "reload":
        await project.delete_identification_file(existing_if['id'])
        # каскадно удаляет identifications + peptide_matches
        # затем продолжаем создание нового identification_file как обычно
    # "add_as_new": ничего не делаем
```

### 3.5 Новые методы API

#### `SpectraMixin.get_spectra_file_by_path`

```python
async def get_spectra_file_by_path(self, path: str) -> dict | None:
    """
    Find spectra file by exact file path.
    Returns dict with spectra_file fields, or None if not found.
    """
    row = await self._fetchone(
        "SELECT * FROM spectre_file WHERE path = ?",
        (path,)
    )
    return dict(row) if row else None
```

#### `IdentificationMixin.get_identification_file_by_path`

```python
async def get_identification_file_by_path(self, file_path: str) -> dict | None:
    """
    Find identification file by exact file path.
    Returns dict with identification_file fields, or None if not found.
    """
    row = await self._fetchone(
        "SELECT * FROM identification_file WHERE file_path = ?",
        (file_path,)
    )
    return dict(row) if row else None
```

---

## 4. Повышение версии

### 4.1 Файлы для обновления

| Файл | Поле | Старое | Новое |
|---|---|---|---|
| `pyproject.toml` | `version` | `0.3.*` | `0.4.0` |
| `dasmixer/version.py` | `__version__` | `"0.3.*"` | `"0.4.0"` |

`docs/project/MASTER_SPEC_NEW.md` и остальная документация — **не трогать** в рамках данной задачи, обновляются отдельно.

Версия файла проекта (`.dasmix`) остаётся `0.3.0` — схема БД не меняется.

---

## 5. Декомпозиция задач

### Задача 1 — Рефакторинг модуля `manage_samples_view`

**Файлы, создаваемые/изменяемые:**

```
# Создать директорию:
dasmixer/gui/views/manage_samples_view/

# Новые файлы:
dasmixer/gui/views/manage_samples_view/__init__.py
dasmixer/gui/views/manage_samples_view/data_manager.py
dasmixer/gui/views/manage_samples_view/update_row.py
dasmixer/gui/views/manage_samples_view/sample_panel.py
dasmixer/gui/views/manage_samples_view/manage_samples_view.py

# Удалить:
dasmixer/gui/views/manage_samples_view.py  (старый файл → заменён пакетом)
```

**Подзадачи:**

| # | Подзадача |
|---|---|
| 1.1 | Создать `data_manager.py` — перенести методы загрузки/кэширования, добавить `drop_empty_files` |
| 1.2 | Создать `update_row.py` — компонент для верхней строки (Update, лоадер, поля порогов) |
| 1.3 | Создать `sample_panel.py` — перенести `_build_sample_header`, `_build_sample_body`, `_empty_stats`, добавить чекбокс |
| 1.4 | Создать `manage_samples_view.py` — оркестратор; убрать уже делегированный код |
| 1.5 | Создать `__init__.py` с реэкспортом |
| 1.6 | Удалить старый `manage_samples_view.py`, убедиться что импорты работают |

---

### Задача 2 — Массовые операции

**Файлы, создаваемые/изменяемые:**

```
# Новые файлы:
dasmixer/gui/views/manage_samples_view/mass_operations_row.py
dasmixer/gui/views/manage_samples_view/dialogs/__init__.py
dasmixer/gui/views/manage_samples_view/dialogs/drop_file_dialog.py
dasmixer/gui/views/manage_samples_view/dialogs/assign_subset_dialog.py

# Изменяемые файлы:
dasmixer/gui/views/manage_samples_view/manage_samples_view.py
dasmixer/gui/views/manage_samples_view/sample_panel.py
dasmixer/gui/views/manage_samples_view/data_manager.py
```

**Подзадачи:**

| # | Подзадача |
|---|---|
| 2.1 | `sample_panel.py`: добавить чекбокс в header, свойства `is_selected` / `set_selected`, коллбэк `on_selection_changed` |
| 2.2 | `manage_samples_view.py`: добавить `_selected_ids: set[int]`, метод `_on_selection_changed`, логику `select_all` / `deselect_all` |
| 2.3 | Создать `mass_operations_row.py` — компонент MassOperationsRow со всеми кнопками и разделителями |
| 2.4 | `manage_samples_view.py`: встроить `MassOperationsRow` между `UpdateRow` и панелями |
| 2.5 | Реализовать действие Outlier в `ManageSamplesView` |
| 2.6 | Создать `dialogs/drop_file_dialog.py` — `DropFileDialog` (2 этапа: выбор типа → подтверждение со списком) |
| 2.7 | Подключить `DropFileDialog` к кнопке Drop file в `MassOperationsRow` |
| 2.8 | Создать `dialogs/assign_subset_dialog.py` — `AssignSubsetDialog` |
| 2.9 | Подключить `AssignSubsetDialog` к кнопке Assign group |
| 2.10 | Реализовать массовое Delete (inline диалог в `ManageSamplesView`) |
| 2.11 | Реализовать Drop empty files (вызов `SampleDataManager.drop_empty_files`, обновление UI) |

---

### Задача 3 — On duplicates в импорте

**Файлы, создаваемые/изменяемые:**

```
# Изменяемые файлы:
dasmixer/gui/views/tabs/samples/dialogs/import_pattern_dialog.py
dasmixer/gui/views/tabs/samples/import_handlers.py
dasmixer/api/project/mixins/spectra_mixin.py
dasmixer/api/project/mixins/identification_mixin.py
```

**Подзадачи:**

| # | Подзадача |
|---|---|
| 3.1 | `spectra_mixin.py`: добавить метод `get_spectra_file_by_path` |
| 3.2 | `identification_mixin.py`: добавить метод `get_identification_file_by_path` |
| 3.3 | `import_pattern_dialog.py`: добавить RadioGroup "On duplicates" в форму; передавать значение в коллбэк |
| 3.4 | `import_handlers.py` → `import_spectra_files`: добавить параметр `on_duplicates`, реализовать логику skip/reload/add_as_new, snack при skip |
| 3.5 | `import_handlers.py` → `import_identification_files`: добавить параметр `on_duplicates`, реализовать логику, snack при skip |

---

### Задача 4 — Повышение версии

**Файлы, изменяемые:**

```
pyproject.toml
dasmixer/version.py
```

**Подзадачи:**

| # | Подзадача |
|---|---|
| 4.1 | Обновить `version` в `pyproject.toml` до `"0.4.0"` |
| 4.2 | Обновить `__version__` в `dasmixer/version.py` до `"0.4.0"` |

---

## Приложение — Сводная таблица новых/изменяемых файлов

| Файл | Статус | Задача |
|---|---|---|
| `dasmixer/gui/views/manage_samples_view/__init__.py` | создать | 1 |
| `dasmixer/gui/views/manage_samples_view/manage_samples_view.py` | создать | 1 |
| `dasmixer/gui/views/manage_samples_view/data_manager.py` | создать | 1 |
| `dasmixer/gui/views/manage_samples_view/update_row.py` | создать | 1 |
| `dasmixer/gui/views/manage_samples_view/sample_panel.py` | создать | 1, 2 |
| `dasmixer/gui/views/manage_samples_view/mass_operations_row.py` | создать | 2 |
| `dasmixer/gui/views/manage_samples_view/dialogs/__init__.py` | создать | 2 |
| `dasmixer/gui/views/manage_samples_view/dialogs/drop_file_dialog.py` | создать | 2 |
| `dasmixer/gui/views/manage_samples_view/dialogs/assign_subset_dialog.py` | создать | 2 |
| `dasmixer/gui/views/manage_samples_view.py` | **удалить** | 1 |
| `dasmixer/gui/views/tabs/samples/dialogs/import_pattern_dialog.py` | изменить | 3 |
| `dasmixer/gui/views/tabs/samples/import_handlers.py` | изменить | 3 |
| `dasmixer/api/project/mixins/spectra_mixin.py` | изменить | 3 |
| `dasmixer/api/project/mixins/identification_mixin.py` | изменить | 3 |
| `pyproject.toml` | изменить | 4 |
| `dasmixer/version.py` | изменить | 4 |
