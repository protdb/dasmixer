# STAGE 11 SPEC: Доработка представления образцов, операции над образцами

## Резюме задачи

Переработка секции образцов на вкладке Samples: переход от плоского списка к раскрывающимся панелям (`ft.ExpansionPanelList`), добавление статусных маркеров, детализированного представления файлов, кнопок операций над отдельным образцом. Параллельно — рефакторинг: вынос всех процессов расчётов и диалогов прогресса в модуль `dasmixer/gui/actions`. Добавление нового столбца `outlier` в таблицу `sample`. Модификация расчётных пайплайнов для поддержки выборки по образцу.

---

## 1. Изменения в схеме данных

### 1.1 Новый столбец `outlier` в таблице `sample`

Добавить в `api/project/schema.py` в CREATE TABLE `sample`:

```sql
outlier INTEGER NOT NULL DEFAULT 0  -- BOOLEAN: 1 if sample is marked as outlier
```

Миграция не требуется — новые проекты получат поле автоматически, старые несовместимы.

### 1.2 Изменения в `api/project/dataclasses.py`

В датакласс `Sample` добавить поле:

```python
outlier: bool = False
```

В `to_dict()`:
```python
'outlier': 1 if self.outlier else 0
```

В `from_dict()`:
```python
outlier=bool(data.get('outlier', False))
```

### 1.3 Изменения в `api/project/mixins/sample_mixin.py`

- В `add_sample`: добавить параметр `outlier: bool = False`, передавать в INSERT.
- В `update_sample`: добавить `outlier` в UPDATE.
- В `get_samples` / `get_sample` / `get_sample_by_name`: поле `outlier` уже будет доступно через `SELECT s.*`.

---

## 2. Новые методы в API Project

### 2.1 Метод `get_sample_stats(sample_id: int) -> dict`

Добавить в `SampleMixin`. Возвращает агрегированную статистику образца для отображения в заголовке панели. Выполняется одним SQL-запросом (несколько подзапросов).

```python
async def get_sample_stats(self, sample_id: int) -> dict:
    """
    Returns aggregated statistics for a sample panel header.

    Returns dict with keys:
        spectra_files_count: int       -- COUNT(*) FROM spectre_file WHERE sample_id
        ident_files_count: int         -- COUNT(*) FROM identification_file via spectre_file
        identifications_count: int     -- COUNT(*) FROM identification via spectre
        preferred_count: int           -- COUNT WHERE is_preferred = 1
        coverage_known_count: int      -- COUNT WHERE intensity_coverage IS NOT NULL
        protein_ids_count: int         -- COUNT(*) FROM protein_identification_result WHERE sample_id
    """
```

SQL (один запрос с подзапросами):

```sql
SELECT
    (SELECT COUNT(*) FROM spectre_file WHERE sample_id = ?) AS spectra_files_count,
    (SELECT COUNT(*) FROM identification_file if2
     JOIN spectre_file sf2 ON if2.spectre_file_id = sf2.id
     WHERE sf2.sample_id = ?) AS ident_files_count,
    (SELECT COUNT(*) FROM identification i2
     JOIN spectre s2 ON i2.spectre_id = s2.id
     JOIN spectre_file sf3 ON s2.spectre_file_id = sf3.id
     WHERE sf3.sample_id = ?) AS identifications_count,
    (SELECT COUNT(*) FROM identification i3
     JOIN spectre s3 ON i3.spectre_id = s3.id
     JOIN spectre_file sf4 ON s3.spectre_file_id = sf4.id
     WHERE sf4.sample_id = ? AND i3.is_preferred = 1) AS preferred_count,
    (SELECT COUNT(*) FROM identification i4
     JOIN spectre s4 ON i4.spectre_id = s4.id
     JOIN spectre_file sf5 ON s4.spectre_file_id = sf5.id
     WHERE sf5.sample_id = ? AND i4.intensity_coverage IS NOT NULL) AS coverage_known_count,
    (SELECT COUNT(*) FROM protein_identification_result WHERE sample_id = ?) AS protein_ids_count
```

### 2.2 Метод `get_sample_detail(sample_id: int) -> dict`

Добавить в `SampleMixin`. Возвращает детализированные данные для раскрытой панели: список `spectre_file` с вложенными `identification_file` и счётчиком идентификаций для каждого.

```python
async def get_sample_detail(self, sample_id: int) -> list[dict]:
    """
    Returns list of spectre_file dicts, each with key 'ident_files':
        list of dicts with keys:
            id, tool_id, tool_name, file_path,
            ident_count: int  -- COUNT(*) FROM identification WHERE ident_file_id
    """
```

Структура возвращаемых данных:
```python
[
    {
        'id': int,           # spectre_file.id
        'path': str,
        'format': str,
        'ident_files': [
            {
                'id': int,       # identification_file.id
                'tool_id': int,
                'tool_name': str,
                'file_path': str,
                'ident_count': int,
            },
            ...
        ]
    },
    ...
]
```

### 2.3 Метод `get_tools_count() -> int`

Добавить в `ToolMixin` (или использовать `get_tools()` и взять `len()`). Нужен для вычисления условия зелёного маркера.

```python
async def get_tools_count(self) -> int:
    row = await self._fetchone("SELECT COUNT(*) as count FROM tool")
    return int(row['count']) if row else 0
```

---

## 3. Рефакторинг: модуль `dasmixer/gui/actions`

Создать пакет `dasmixer/gui/actions/` с разделением по доменам. Цель — вынести всю логику запуска расчётов и обёртки прогресс-диалогов из секций вкладок, сделав их доступными как для вкладок, так и для кнопок действий в панели образца.

### 3.1 Структура пакета

```
dasmixer/gui/actions/
    __init__.py
    base.py              # BaseAction — базовый класс с методами show_error/show_success, run_with_progress
    ion_actions.py       # IonCoverageAction, SelectPreferredAction
    protein_map_action.py  # MatchProteinsAction
    protein_ident_action.py  # ProteinIdentificationsAction
    lfq_action.py        # LFQAction
```

### 3.2 `base.py` — `BaseAction`

```python
class BaseAction:
    """
    Base class for all calculation actions.
    Provides helpers for progress dialogs and snackbar messages.
    """
    def __init__(self, project: Project, page: ft.Page):
        self.project = project
        self.page = page

    def show_error(self, message: str): ...
    def show_success(self, message: str): ...
    def show_warning(self, message: str): ...

    async def run_with_progress(
        self,
        title: str,
        coro,          # coroutine to run
        stoppable: bool = False
    ): ...
```

### 3.3 `ion_actions.py`

#### `IonCoverageAction`

Извлечь логику из `IonCalculations.run_coverage_calc()`.

```python
class IonCoverageAction(BaseAction):
    async def run(
        self,
        state: PeptidesTabState,
        recalc_all: bool = False,
        sample_id: int | None = None      # NEW: если задан — фильтруем по образцу
    ): ...
```

Если `sample_id` задан: получаем список `spectre_file_id` для образца, фильтруем выборку идентификаций через `get_identifications_with_spectra_batch` добавив параметр `spectra_file_ids: list[int] | None = None`.

**Изменение в `IdentificationMixin.get_identifications_with_spectra_batch`:** добавить опциональный параметр:
```python
spectra_file_ids: list[int] | None = None
```
Если передан — добавить в WHERE `s.spectre_file_id IN (...)`.

#### `SelectPreferredAction`

Извлечь логику из `MatchingSection.run_matching_internal()`.

```python
class SelectPreferredAction(BaseAction):
    async def run(
        self,
        tool_settings: dict,
        criterion: str,
        sample_id: int | None = None      # NEW: если задан — только файлы спектров образца
    ): ...
```

Если `sample_id` задан: получить `spectre_files` с фильтром `sample_id=sample_id` вместо всех файлов.

### 3.4 `protein_map_action.py` — `MatchProteinsAction`

Извлечь логику из `FastaSection.match_proteins_internal()`.

```python
class MatchProteinsAction(BaseAction):
    async def run(
        self,
        state: PeptidesTabState,
        sample_id: int | None = None      # NEW
    ): ...
```

Если `sample_id` задан: **не** вызываем `project.clear_peptide_matches()` глобально. Вместо этого:
1. Получаем список `ident_file_id` для образца.
2. Через новый метод `project.clear_peptide_matches_for_sample(sample_id)` удаляем только матчи для идентификаций данного образца.
3. Передаём в `map_proteins` параметр `sample_id` для фильтрации `get_identifications`.

**Добавить в `PeptideMixin`:**
```python
async def clear_peptide_matches_for_sample(self, sample_id: int) -> None:
    """Delete peptide_match records for all identifications of a given sample."""
    await self._execute("""
        DELETE FROM peptide_match WHERE identification_id IN (
            SELECT i.id FROM identification i
            JOIN spectre s ON i.spectre_id = s.id
            JOIN spectre_file sf ON s.spectre_file_id = sf.id
            WHERE sf.sample_id = ?
        )
    """, (int(sample_id),))
    await self.save()
```

**Добавить параметр `sample_id: int | None = None` в `map_proteins()`** в `protein_map.py`. Если задан — передавать в `project.get_identifications(sample_id=sample_id, ...)`.

### 3.5 `protein_ident_action.py` — `ProteinIdentificationsAction`

Извлечь логику из `DetectionSection.calculate_identifications()`.

```python
class ProteinIdentificationsAction(BaseAction):
    async def run(
        self,
        min_peptides: int,
        min_uq_evidence: int,
        sample_id: int | None = None      # NEW: если задан — только этот образец
    ): ...
```

Если `sample_id` задан:
- Не вызываем `project.clear_protein_identifications()` глобально.
- Добавляем в `ProteinMixin` метод:
  ```python
  async def clear_protein_identifications_for_sample(self, sample_id: int) -> None:
      await self._execute(
          "DELETE FROM protein_identification_result WHERE sample_id = ?",
          (int(sample_id),)
      )
      await self.save()
  ```
- `find_protein_identifications` уже работает по образцам (итерирует `samples = joined_data['sample_id'].unique()`), поэтому достаточно передать `joined_data` отфильтрованный по `sample_id`.
- В `get_joined_peptide_data` уже есть параметр `sample_id` — использовать его.

### 3.6 `lfq_action.py` — `LFQAction`

Извлечь логику из `LFQSection.calculate_lfq()`. Функция `calculate_lfq` в API уже принимает `sample_id` поштучно — достаточно обернуть.

```python
class LFQAction(BaseAction):
    async def run(
        self,
        state: ProteinsTabState,
        sample_id: int | None = None      # NEW: если задан — только этот образец
    ): ...
```

Если `sample_id` задан: запускаем `calculate_lfq` только для него, без `clear_protein_quantifications()` глобально. Добавить:
```python
async def clear_protein_quantifications_for_sample(self, sample_id: int) -> None:
    """Delete LFQ records for a given sample via protein_identification_result FK."""
    await self._execute("""
        DELETE FROM protein_quantification_result
        WHERE protein_identification_id IN (
            SELECT id FROM protein_identification_result WHERE sample_id = ?
        )
    """, (int(sample_id),))
    await self.save()
```

### 3.7 Обновление существующих секций

После создания `gui/actions/` существующие секции переключаются на использование Action-классов вместо inline-логики:

- `peptides/actions_section.py` → использует `IonCoverageAction`, `SelectPreferredAction`, `MatchProteinsAction`
- `peptides/fasta_section.py` → использует `MatchProteinsAction`
- `peptides/matching_section.py` → использует `SelectPreferredAction`
- `peptides/ion_calculations.py` → остаётся как фасад (держит state), делегирует в `IonCoverageAction`
- `proteins/detection_section.py` → использует `ProteinIdentificationsAction`
- `proteins/lfq_section.py` → использует `LFQAction`

Логика UI (получение настроек из контролов, получение `state`) остаётся в секциях — в Action-классы передаются уже готовые параметры.

---

## 4. Переработка `SamplesSection`

### 4.1 Файл: `dasmixer/gui/views/tabs/samples/samples_section.py`

Полная переработка. Новая структура:

```
SamplesSection (BaseSection)
├── _build_content()
│   ├── Row: [Update btn, min_proteins field, min_identifications field]
│   └── ft.ExpansionPanelList (self.panels_list)
└── load_data()    — загружает все образцы, строит панели
```

### 4.2 Контролы верхней панели

```python
self.update_btn = ft.ElevatedButton(
    content=ft.Text("Update"),
    icon=ft.Icons.REFRESH,
    on_click=lambda e: self.page.run_task(self.load_data)
)

self.min_proteins_field = ft.TextField(
    label="Min proteins",
    value="30",
    width=120,
    keyboard_type=ft.KeyboardType.NUMBER
)

self.min_identifications_field = ft.TextField(
    label="Min identifications",
    value="1000",
    width=160,
    keyboard_type=ft.KeyboardType.NUMBER
)
```

Верхняя строка:
```python
ft.Row([
    self.update_btn,
    self.min_proteins_field,
    self.min_identifications_field,
], spacing=10)
```

### 4.3 `ft.ExpansionPanelList`

```python
self.panels_list = ft.ExpansionPanelList(
    expand_icon_color=ft.Colors.BLUE_400,
    elevation=2,
    divider_color=ft.Colors.GREY_300,
    controls=[]
)
```

По умолчанию все панели свёрнуты (`expanded=False`).

### 4.4 Логика `load_data()`

```python
async def load_data(self):
    samples = await self.project.get_samples()
    tools_count = await self.project.get_tools_count()
    min_proteins = int(self.min_proteins_field.value or 30)
    min_idents = int(self.min_identifications_field.value or 1000)

    self.panels_list.controls.clear()

    for sample in samples:
        stats = await self.project.get_sample_stats(sample.id)
        panel = await self._build_sample_panel(sample, stats, tools_count, min_proteins, min_idents)
        self.panels_list.controls.append(panel)

    if self.panels_list.page:
        self.panels_list.update()
```

### 4.5 Построение заголовка панели `_build_sample_header()`

```python
def _build_sample_header(
    self,
    sample: Sample,
    stats: dict,
    tools_count: int,
    min_proteins: int,
    min_idents: int
) -> ft.Control:
```

**Логика определения маркера:**

Вспомогательные переменные:
```python
has_spectra = stats['spectra_files_count'] > 0
has_ident_files = stats['ident_files_count'] > 0
expected_ident_files = tools_count * stats['spectra_files_count']
ident_files_ok = stats['ident_files_count'] == expected_ident_files
idents_ok = stats['identifications_count'] >= min_idents
preferred_ok = stats['preferred_count'] == 0 or stats['preferred_count'] >= min_idents
proteins_ok = stats['protein_ids_count'] == 0 or stats['protein_ids_count'] >= min_proteins
has_empty_ident_files = <см. ниже>
```

`has_empty_ident_files` требует отдельного запроса или включается в `get_sample_stats`. Добавить в `get_sample_stats`:
```sql
(SELECT COUNT(*) FROM identification_file if5
 JOIN spectre_file sf6 ON if5.spectre_file_id = sf6.id
 WHERE sf6.sample_id = ?
 AND NOT EXISTS (
     SELECT 1 FROM identification WHERE ident_file_id = if5.id
 )) AS empty_ident_files_count
```

**Правила маркера:**

| Условие | Маркер |
|---|---|
| `not has_spectra or not has_ident_files` | `ft.Icons.ERROR_OUTLINE_OUTLINED`, `ft.Colors.RED_600` |
| все условия выполнены и `has_empty_ident_files == 0` | `ft.Icons.CHECK_CIRCLE_OUTLINE_OUTLINED`, `ft.Colors.GREEN_600` |
| иначе | `ft.Icons.WARNING_AMBER_OUTLINED`, `ft.Colors.AMBER_600` |

Проверка "все условия выполнены":
```python
all_ok = (
    has_spectra and
    has_ident_files and
    ident_files_ok and
    idents_ok and
    preferred_ok and
    proteins_ok and
    stats['empty_ident_files_count'] == 0
)
```

**Компоновка заголовка** (горизонтальная строка):
```
[Маркер] [Название] · [Группа] · Files: N · ID Files: N · Idents: N · Coverage: N · Preferred: N · Proteins: N
```

Реализация:
```python
ft.Row([
    ft.Icon(marker_icon, color=marker_color, size=20),
    ft.Text(sample.name, weight=ft.FontWeight.BOLD, size=14),
    ft.Text("·", color=ft.Colors.GREY_500),
    ft.Text(sample.subset_name or "No group", color=ft.Colors.GREY_700, size=13),
    ft.Text("·", color=ft.Colors.GREY_500),
    ft.Text(f"Files: {stats['spectra_files_count']}", size=12),
    ft.Text(f"ID files: {stats['ident_files_count']}", size=12),
    ft.Text(f"Idents: {stats['identifications_count']}", size=12),
    ft.Text(f"Coverage: {stats['coverage_known_count']}", size=12),
    ft.Text(f"Preferred: {stats['preferred_count']}", size=12),
    ft.Text(f"Proteins: {stats['protein_ids_count']}", size=12),
], spacing=8, wrap=False)
```

### 4.6 Построение тела панели `_build_sample_body()`

```python
async def _build_sample_body(self, sample: Sample, min_idents: int) -> ft.Control:
```

Возвращает `ft.Column` со следующими элементами:

#### 4.6.1 Список файлов спектров с вложенными файлами идентификаций

```python
detail = await self.project.get_sample_detail(sample.id)

for sf in detail:
    # Заголовок файла спектров
    spectra_header = ft.Row([
        ft.Icon(ft.Icons.GRAPHIC_EQ, size=16, color=ft.Colors.BLUE_600),
        ft.Text(Path(sf['path']).name, weight=ft.FontWeight.BOLD, size=13),
        ft.Text(f"({sf['format']})", size=11, color=ft.Colors.GREY_600),
        ft.Container(expand=True),
        ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            icon_color=ft.Colors.RED_400,
            tooltip="Delete spectra file",
            on_click=lambda e, sf_id=sf['id']: self.page.run_task(
                self._delete_spectra_file, sf_id, sample
            )
        ),
        ft.IconButton(
            icon=ft.Icons.ADD_CIRCLE_OUTLINE,
            tooltip="Add identification file",
            on_click=lambda e, sf_id=sf['id']: self.page.run_task(
                self._add_identification_file, sf_id, sample
            )
        )
    ])

    # Список ident-файлов
    for ident_file in sf['ident_files']:
        count = ident_file['ident_count']
        is_below = count < min_idents
        row_border = ft.border.all(1, ft.Colors.RED_400) if is_below else None

        ident_row = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=14),
                ft.Text(ident_file['tool_name'], size=12, weight=ft.FontWeight.W_500),
                ft.Text(Path(ident_file['file_path']).name, size=12),
                ft.Text(f"({count} idents)", size=11, color=ft.Colors.GREY_600),
                ft.Container(expand=True),
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_color=ft.Colors.RED_400,
                    tooltip="Delete identification file",
                    on_click=lambda e, if_id=ident_file['id']: self.page.run_task(
                        self._delete_ident_file, if_id, sample
                    )
                )
            ]),
            border=row_border,
            border_radius=4,
            padding=ft.padding.symmetric(horizontal=4)
        )
        # добавить в список
```

Кнопка "Add spectra file" для образца:
```python
ft.TextButton(
    content=ft.Row([
        ft.Icon(ft.Icons.ADD),
        ft.Text("Add spectra file")
    ]),
    on_click=lambda e: self.page.run_task(self._add_spectra_file, sample)
)
```

#### 4.6.2 Значение параметра additions

```python
if sample.additions:
    import json
    additions_text = json.dumps(sample.additions, indent=2, ensure_ascii=False)
    ft.Text(f"Additions: {additions_text}", size=11, color=ft.Colors.GREY_600)
```

#### 4.6.3 Кнопки действий (одна строка)

Кнопки слева (с иконками и текстом):
```python
left_buttons = ft.Row([
    ft.ElevatedButton(
        content=ft.Text("Calculate ions"),
        icon=ft.Icons.BOLT,
        on_click=lambda e: self.page.run_task(self._action_calculate_ions, sample)
    ),
    ft.ElevatedButton(
        content=ft.Text("Select preferred"),
        icon=ft.Icons.STAR_OUTLINE,
        on_click=lambda e: self.page.run_task(self._action_select_preferred, sample)
    ),
    ft.ElevatedButton(
        content=ft.Text("Match proteins"),
        icon=ft.Icons.LINK,
        on_click=lambda e: self.page.run_task(self._action_match_proteins, sample)
    ),
    ft.ElevatedButton(
        content=ft.Text("Protein Identifications"),
        icon=ft.Icons.BIOTECH,
        on_click=lambda e: self.page.run_task(self._action_protein_identifications, sample)
    ),
    ft.ElevatedButton(
        content=ft.Text("LFQ"),
        icon=ft.Icons.ANALYTICS,
        on_click=lambda e: self.page.run_task(self._action_lfq, sample)
    ),
], spacing=8, wrap=True)

right_buttons = ft.Row([
    ft.ElevatedButton(
        content=ft.Row([ft.Icon(ft.Icons.EDIT_OUTLINED), ft.Text("Edit")]),
        tooltip="Edit sample properties",
        on_click=lambda e, s=sample: self.page.run_task(self._show_edit_dialog, s)
    ),
    ft.ElevatedButton(
        content=ft.Row([ft.Icon(ft.Icons.FLAG_OUTLINED), ft.Text("Outlier")]),
        tooltip="Mark as outlier",
        on_click=lambda e, s=sample: self.page.run_task(self._toggle_outlier, s)
    ),
    ft.ElevatedButton(
        content=ft.Row([ft.Icon(ft.Icons.DELETE_OUTLINED), ft.Text("Delete")]),
        tooltip="Delete sample",
        style=ft.ButtonStyle(color=ft.Colors.RED_600),
        on_click=lambda e, s=sample: self.page.run_task(self._delete_sample, s)
    ),
], spacing=8)

actions_row = ft.Row([
    left_buttons,
    ft.Container(expand=True),
    right_buttons
])
```

### 4.7 Построение `ft.ExpansionPanel`

```python
ft.ExpansionPanel(
    header=ft.ListTile(
        title=self._build_sample_header(sample, stats, tools_count, min_proteins, min_idents)
    ),
    content=ft.Container(
        content=await self._build_sample_body(sample, min_idents),
        padding=ft.padding.only(left=16, right=16, bottom=16)
    ),
    expanded=False,
    can_tap_header=True
)
```

---

## 5. Операции из панели образца

### 5.1 Удаление файла спектров `_delete_spectra_file(sf_id, sample)`

```python
async def _delete_spectra_file(self, sf_id: int, sample: Sample):
```

Алгоритм:
1. Показать диалог подтверждения: "Delete spectra file and all linked identifications, identifications data, peptide matches? This cannot be undone."
2. При подтверждении: `await self.project.delete_spectra_file(sf_id)` — каскадное удаление через FK (spectre → identification → peptide_match).
3. Перезагрузить панель: `await self.load_data()`.

**Добавить в `SpectraMixin`:**
```python
async def delete_spectra_file(self, spectra_file_id: int) -> None:
    await self._execute("DELETE FROM spectre_file WHERE id = ?", (int(spectra_file_id),))
    await self.save()
```

### 5.2 Удаление файла идентификаций `_delete_ident_file(if_id, sample)`

```python
async def _delete_ident_file(self, if_id: int, sample: Sample):
```

Алгоритм:
1. Показать диалог подтверждения: "Delete identification file and all linked identifications and peptide matches?"
2. При подтверждении: `await self.project.delete_identification_file(if_id)`.
3. Перезагрузить панель.

**Добавить в `IdentificationMixin`:**
```python
async def delete_identification_file(self, ident_file_id: int) -> None:
    await self._execute("DELETE FROM identification_file WHERE id = ?", (int(ident_file_id),))
    await self.save()
```

Каскадное удаление `identification` → `peptide_match` через FK в схеме БД уже настроено.

### 5.3 Добавление файла спектров `_add_spectra_file(sample)`

```python
async def _add_spectra_file(self, sample: Sample):
```

Алгоритм:
1. Показать `ImportSingleDialog` в режиме "spectra" с зафиксированным образцом и заблокированной группой.
2. Доработка `ImportSingleDialog` (см. п.6).
3. После импорта: `await self.load_data()`.

### 5.4 Добавление файла идентификаций `_add_identification_file(sf_id, sample)`

```python
async def _add_identification_file(self, sf_id: int, sample: Sample):
```

Алгоритм:
1. Показать доработанный `ImportSingleDialog` в режиме "identifications" с зафиксированным именем образца и конкретным `spectra_file_id`.
2. После импорта: `await self.load_data()`.

### 5.5 Редактирование образца `_show_edit_dialog(sample)`

Использовать существующий `SampleDialog`. После сохранения: `await self.load_data()`.

### 5.6 Пометка как outlier `_toggle_outlier(sample)`

```python
async def _toggle_outlier(self, sample: Sample):
    sample.outlier = not sample.outlier
    await self.project.update_sample(sample)
    await self.load_data()
```

Визуальная индикация outlier-статуса в заголовке панели: добавить иконку `ft.Icons.FLAG` (красная) рядом с маркером если `sample.outlier == True`.

### 5.7 Удаление образца `_delete_sample(sample)`

```python
async def _delete_sample(self, sample: Sample):
```

Алгоритм:
1. Диалог подтверждения: "Delete sample '{name}' and all its data? This cannot be undone."
2. `await self.project.delete_sample(sample.id)` — каскадное удаление через FK.
3. `await self.load_data()`.

---

## 6. Действия расчётов из панели образца

### 6.1 `_action_calculate_ions(sample)`

```python
async def _action_calculate_ions(self, sample: Sample):
    from dasmixer.gui.actions.ion_actions import IonCoverageAction
    state = self._get_peptides_state()
    if state is None:
        self.show_warning("Open Peptides tab first to configure ion settings")
        return
    action = IonCoverageAction(self.project, self.page)
    await action.run(state=state, recalc_all=False, sample_id=sample.id)
    await self.load_data()
```

### 6.2 `_action_select_preferred(sample)`

```python
async def _action_select_preferred(self, sample: Sample):
    from dasmixer.gui.actions.ion_actions import SelectPreferredAction
    tool_settings = self._get_tool_settings()
    criterion = self._get_matching_criterion()
    action = SelectPreferredAction(self.project, self.page)
    await action.run(tool_settings=tool_settings, criterion=criterion, sample_id=sample.id)
    await self.load_data()
```

### 6.3 `_action_match_proteins(sample)`

```python
async def _action_match_proteins(self, sample: Sample):
    from dasmixer.gui.actions.protein_map_action import MatchProteinsAction
    state = self._get_peptides_state()
    action = MatchProteinsAction(self.project, self.page)
    await action.run(state=state, sample_id=sample.id)
    await self.load_data()
```

### 6.4 `_action_protein_identifications(sample)`

```python
async def _action_protein_identifications(self, sample: Sample):
    from dasmixer.gui.actions.protein_ident_action import ProteinIdentificationsAction
    min_pep, min_uq = self._get_protein_detection_params()
    action = ProteinIdentificationsAction(self.project, self.page)
    await action.run(min_peptides=min_pep, min_uq_evidence=min_uq, sample_id=sample.id)
    await self.load_data()
```

### 6.5 `_action_lfq(sample)`

```python
async def _action_lfq(self, sample: Sample):
    from dasmixer.gui.actions.lfq_action import LFQAction
    state = self._get_proteins_state()
    action = LFQAction(self.project, self.page)
    await action.run(state=state, sample_id=sample.id)
    await self.load_data()
```

### 6.6 Вспомогательные геттеры настроек

```python
def _get_peptides_state(self) -> PeptidesTabState | None:
    """Get shared state from PeptidesTab via page reference."""
    if hasattr(self.page, 'peptides_tab'):
        return self.page.peptides_tab.state
    return None

def _get_tool_settings(self) -> dict:
    if hasattr(self.page, 'peptides_tab'):
        ts = self.page.peptides_tab.sections.get('tool_settings')
        if ts:
            return ts.get_tool_settings_for_matching()
    return {}

def _get_matching_criterion(self) -> str:
    if hasattr(self.page, 'peptides_tab'):
        ms = self.page.peptides_tab.sections.get('matching')
        if ms and hasattr(ms, 'selection_criterion_group'):
            return ms.selection_criterion_group.value
    return 'intensity'

def _get_protein_detection_params(self) -> tuple[int, int]:
    if hasattr(self.page, 'proteins_tab'):
        ds = self.page.proteins_tab.sections.get('detection')
        if ds:
            return int(ds.min_peptides_field.value), int(ds.min_unique_field.value)
    return 2, 1

def _get_proteins_state(self):
    if hasattr(self.page, 'proteins_tab'):
        return self.page.proteins_tab.state
    return None
```

---

## 7. Доработка `ImportSingleDialog`

### 7.1 Новые параметры конструктора

```python
def __init__(
    self,
    project: Project,
    page: ft.Page,
    import_type: str,
    tool_id: int = None,
    on_import_callback=None,
    # NEW параметры для вызова из панели образца:
    fixed_sample_name: str | None = None,    # если задан — поле заблокировано
    fixed_spectra_file_id: int | None = None, # если задан — не создаём новый sf, используем этот
    lock_group: bool = False,                  # заблокировать поле группы
):
```

### 7.2 Логика изменений в `_show_config_dialog()`

- Если `fixed_sample_name` задан:
  - `sample_name.value = fixed_sample_name`
  - `sample_name.read_only = True`
- Если `lock_group` задан:
  - `group_dropdown` не отображается (или `disabled=True`)
- Если `fixed_spectra_file_id` задан:
  - в `start_import` не ищем файл спектров по имени образца, а используем `fixed_spectra_file_id` напрямую при создании записи идентификаций.

---

## 8. Обновление `SamplesTab`

### 8.1 `did_mount` / `_load_initial_data`

Загрузка `SamplesSection` переносится в конец `_load_initial_data` — после загрузки остальных секций:

```python
async def _load_initial_data(self):
    # 1. Загрузить groups, import, tools секции
    for section_name in ['groups', 'import', 'tools']:
        section = self.sections[section_name]
        if hasattr(section, 'load_data'):
            await section.load_data()
    # 2. Загрузить samples секцию последней (асинхронно, UI уже отрисован)
    await self.sections['samples'].load_data()
```

### 8.2 Триггеры обновления `SamplesSection`

`SamplesSection.load_data()` вызывается:
1. По кнопке Update (вручную).
2. После открытия проекта — в конце `_load_initial_data`.
3. После импорта спектров или идентификаций — через `refresh_all()` в `_on_import_complete`.
4. После каждого действия из панели образца (описано выше в каждом `_action_*`).
5. **НЕ** вызывается автоматически в иных случаях.

---

## 9. Обновление `SamplesTabState`

Добавить поля:

```python
@dataclass
class SamplesTabState:
    ...
    min_proteins: int = 30
    min_identifications: int = 1000
```

---

## 10. Затрагиваемые файлы

| Файл | Тип изменения |
|---|---|
| `api/project/schema.py` | Добавить `outlier` в `sample` |
| `api/project/dataclasses.py` | `Sample` — добавить `outlier` |
| `api/project/mixins/sample_mixin.py` | `add_sample`, `update_sample` + `get_sample_stats`, `get_sample_detail`, `get_tools_count` (или в tool_mixin) |
| `api/project/mixins/spectra_mixin.py` | `delete_spectra_file` |
| `api/project/mixins/identification_mixin.py` | `delete_identification_file`, `get_identifications_with_spectra_batch` (+ `spectra_file_ids`) |
| `api/project/mixins/peptide_mixin.py` | `clear_peptide_matches_for_sample` |
| `api/project/mixins/protein_mixin.py` | `clear_protein_identifications_for_sample`, `clear_protein_quantifications_for_sample` |
| `api/calculations/peptides/protein_map.py` | Добавить `sample_id` в `map_proteins` |
| `gui/actions/__init__.py` | Новый пакет |
| `gui/actions/base.py` | `BaseAction` |
| `gui/actions/ion_actions.py` | `IonCoverageAction`, `SelectPreferredAction` |
| `gui/actions/protein_map_action.py` | `MatchProteinsAction` |
| `gui/actions/protein_ident_action.py` | `ProteinIdentificationsAction` |
| `gui/actions/lfq_action.py` | `LFQAction` |
| `gui/views/tabs/samples/samples_section.py` | Полная переработка |
| `gui/views/tabs/samples/samples_tab.py` | Порядок загрузки в `_load_initial_data` |
| `gui/views/tabs/samples/shared_state.py` | `min_proteins`, `min_identifications` |
| `gui/views/tabs/samples/dialogs/import_single_dialog.py` | `fixed_sample_name`, `fixed_spectra_file_id`, `lock_group` |
| `gui/views/tabs/peptides/actions_section.py` | Переключение на Action-классы |
| `gui/views/tabs/peptides/fasta_section.py` | Переключение на `MatchProteinsAction` |
| `gui/views/tabs/peptides/matching_section.py` | Переключение на `SelectPreferredAction` |
| `gui/views/tabs/peptides/ion_calculations.py` | Делегирование в `IonCoverageAction` |
| `gui/views/tabs/proteins/detection_section.py` | Переключение на `ProteinIdentificationsAction` |
| `gui/views/tabs/proteins/lfq_section.py` | Переключение на `LFQAction` |

---

## 11. Порядок реализации

1. **Схема данных и API:** `schema.py` → `dataclasses.py` → миксины (новые методы и столбцы).
2. **`gui/actions/`:** создать пакет, реализовать все Action-классы с нуля.
3. **Рефакторинг секций:** переключить `actions_section`, `fasta_section`, `matching_section`, `ion_calculations`, `detection_section`, `lfq_section` на Action-классы.
4. **`ImportSingleDialog`:** добавить новые параметры.
5. **`SamplesSection`:** полная переработка.
6. **`SamplesTab`:** обновить порядок загрузки.
7. **Тестирование:** проверить глобальные расчёты (не сломались), проверить расчёты по одному образцу, проверить маркеры в панелях.
