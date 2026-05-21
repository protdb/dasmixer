# Спецификация реализации фазы 4.2: Вкладка "Protein Identifications"

**Дата:** 2026-02-03  
**Версия:** 1.0  
**Статус:** Утверждено к разработке

---

## Оглавление

1. [Обзор](#обзор)
2. [Архитектура решения](#архитектура-решения)
3. [Структура файлов](#структура-файлов)
4. [Компоненты UI](#компоненты-ui)
5. [Изменения в API (Project)](#изменения-в-api-project)
6. [Изменения в схеме БД](#изменения-в-схеме-бд)
7. [Логика работы](#логика-работы)
8. [Диалоги прогресса](#диалоги-прогресса)
9. [Обработка ошибок](#обработка-ошибок)
10. [План разработки](#план-разработки)

---

## Обзор

Фаза 4.2 реализует функционал идентификации белков и количественной оценки (Label-Free Quantification) на основе данных пептидных идентификаций. Вкладка "Proteins" предоставляет пользователю:

- Расчет достоверных белковых идентификаций с фильтрацией по количеству пептидов
- Количественную оценку белков методами emPAI, iBAQ, NSAF, Top3
- Просмотр результатов в табличном виде с фильтрацией по образцам

**Ключевые требования:**
- Модульная структура аналогичная вкладке Peptides
- Shared state для управления состоянием между секциями
- Автоматическое обновление таблицы после расчётов
- Прогресс-диалоги для всех длительных операций
- Независимость расчёта LFQ от расчёта protein identifications

---

## Архитектура решения

### Принципы проектирования

1. **Модульность**: Разделение на независимые секции с четкими зонами ответственности
2. **Shared State**: Единый объект состояния для координации между секциями
3. **Асинхронность**: Все операции с БД выполняются асинхронно
4. **Прогресс-индикация**: Каждая длительная операция отображает прогресс
5. **Автообновление**: UI обновляется автоматически после изменения данных

### Компонентная структура

```
ProteinsTab (ft.Container)
├── ProteinsTabState (shared state)
├── DetectionSection (protein identification)
├── LFQSection (label-free quantification)
└── TableSection (results display)
```

### Поток данных

```
User Action → Section Handler → Project API → Database → 
→ Update State → Refresh UI → Show Results
```

---

## Структура файлов

### Новые файлы GUI

```
gui/views/tabs/proteins/
├── __init__.py                  # Экспорт ProteinsTab
├── proteins_tab.py              # Главный контейнер вкладки
├── shared_state.py              # Состояние вкладки
├── base_section.py              # Базовый класс для секций
├── detection_section.py         # Секция Protein Detection
├── lfq_section.py               # Секция Label-Free Quantification
├── table_section.py             # Секция отображения таблицы
└── dialogs/
    └── progress_dialog.py       # Диалог прогресса (переиспользуем из peptides)
```

### Изменяемые файлы

- `api/project/project.py` - добавление методов для работы с protein identifications и quantification
- `api/project/schema.py` - добавление поля `intensity_sum` в таблицу `protein_identification_result`
- `gui/views/tabs/proteins_tab.py` - замена заглушки на полноценную реализацию

---

## Компоненты UI

### 1. ProteinsTab (proteins_tab.py)

**Назначение:** Главный контейнер вкладки, композиция секций.

**Структура:**
```python
class ProteinsTab(ft.Container):
    def __init__(self, project: Project)
    async def _load_initial_data()
    async def refresh_all()
```
!!! Для единообразия должен быть метод _build_content(), вызываемый в конструкторе.

**Layout:**
```
Column [
    DetectionSection
    Container(height=10)
    LFQSection
    Container(height=10)
    TableSection
]
```

**Lifecycle:**
- `did_mount()`: загрузка начальных данных для всех секций
- `refresh_all()`: обновление всех секций после изменений

---

### 2. ProteinsTabState (shared_state.py)

**Назначение:** Централизованное хранилище состояния вкладки.

**Поля:**
```python
@dataclass
class ProteinsTabState:
    # Detection parameters
    min_peptides: int = 2
    min_unique_evidence: int = 1
    
    # LFQ parameters
    lfq_methods: dict[str, bool] = field(default_factory=lambda: {
        'emPAI': False,
        'iBAQ': False,
        'NSAF': False,
        'Top3': False
    })
    empai_base_value: float = 10.0
    enzyme: str = 'trypsin'
    min_peptide_length: int = 7
    max_peptide_length: int = 30
    max_cleavage_sites: int = 2
    
    # Table state
    selected_sample: str | None = None  # For filtering table
    table_data: pd.DataFrame | None = None
    
    # Counts
    protein_identification_count: int = 0
    protein_quantification_count: int = 0
```

**Методы:**
```python
def get_selected_lfq_methods() -> list[str]:
    """Возвращает список выбранных методов LFQ"""
    return [k for k, v in self.lfq_methods.items() if v]

def reset_lfq_methods():
    """Сброс всех чекбоксов LFQ"""
    for key in self.lfq_methods:
        self.lfq_methods[key] = False
```

---

### 3. BaseSection (base_section.py)

**Назначение:** Базовый класс для всех секций вкладки Proteins.

Идентичен `gui/views/tabs/peptides/base_section.py`, предоставляет:
- Методы `show_error()`, `show_success()`, `show_info()`, `show_warning()`
- Асбстрактный метод `_build_content()`
- Опциональный метод `load_data()`
- Стандартное оформление контейнера (padding, border, border_radius)

---

### 4. DetectionSection (detection_section.py)

**Назначение:** Управление параметрами и запуск расчёта белковых идентификаций.

**UI компоненты:**

```python
# Заголовок секции
ft.Text("Protein Detection", size=18, weight=ft.FontWeight.BOLD)

# Поля ввода
min_peptides_field = ft.TextField(
    label="Minimum peptides",
    value="2",
    keyboard_type=ft.KeyboardType.NUMBER,
    width=200,
    on_change=self._on_min_peptides_changed
)

min_unique_field = ft.TextField(
    label="Minimum unique peptides",
    value="1",
    keyboard_type=ft.KeyboardType.NUMBER,
    width=200,
    on_change=self._on_min_unique_changed
)

# Кнопка расчёта
calculate_btn = ft.ElevatedButton(
    content=ft.Text("Calculate Protein Identifications"),
    icon=ft.Icons.PLAY_CIRCLE,
    on_click=lambda e: self.page.run_task(self.calculate_identifications, e),
    style=ft.ButtonStyle(
        bgcolor=ft.Colors.BLUE_600,
        color=ft.Colors.WHITE
    )
)
```

**Layout:**
```
Column [
    Text("Protein Detection", bold)
    Row [
        min_peptides_field,
        min_unique_field
    ]
    calculate_btn
]
```

**Методы:**

```python
async def calculate_identifications(self, e):
    """
    Запуск расчёта белковых идентификаций.
    
    Workflow:
    1. Валидация параметров
    2. Очистка старых результатов
    3. Получение данных из project.get_joined_peptide_data()
    4. Получение базы белков project.get_protein_db_to_search()
    5. Вызов find_protein_identifications() с прогрессом
    6. Сохранение результатов через project.add_protein_identifications_batch()
    7. Обновление счётчиков в state
    8. Обновление таблицы
    """

async def _on_min_peptides_changed(self, e):
    """Обновление state при изменении значения"""
    
async def _on_min_unique_changed(self, e):
    """Обновление state при изменении значения"""
```

!!!! Важный момент: указанные пользователем параметры при запуске расчета сохраняются в project_settings. Также при загрузке страницы они берутся оттуда же и только при отсутствии в проекте заполняются значениями по умолчанию !!!!

---

### 5. LFQSection (lfq_section.py)

**Назначение:** Управление параметрами и запуск расчёта LFQ.

**UI компоненты:**

```python
# Заголовок
ft.Text("Label-Free Quantification", size=18, weight=ft.FontWeight.BOLD)

# Чекбоксы методов LFQ
empai_checkbox = ft.Checkbox(
    label="emPAI",
    value=False,
    on_change=self._on_method_changed('emPAI')
)

ibaq_checkbox = ft.Checkbox(
    label="iBAQ",
    value=False,
    on_change=self._on_method_changed('iBAQ')
)

nsaf_checkbox = ft.Checkbox(
    label="NSAF",
    value=False,
    on_change=self._on_method_changed('NSAF')
)

top3_checkbox = ft.Checkbox(
    label="Top3",
    value=False,
    on_change=self._on_method_changed('Top3')
)

# emPAI base value
empai_base_field = ft.TextField(
    label="emPAI base value",
    value="10",
    keyboard_type=ft.KeyboardType.NUMBER,
    width=200,
    on_change=self._on_empai_base_changed
)

# Enzyme dropdown
enzyme_dropdown = ft.Dropdown(
    label="Enzyme",
    value="trypsin",
    width=250,
    options=[
        ft.dropdown.Option(key=key, text=text.title())
        for key, text in SUPPORTED_ENZYMES.items()
    ],
    on_change=self._on_enzyme_changed
)

# Peptide length fields
min_length_field = ft.TextField(
    label="Min peptide length",
    value="7",
    keyboard_type=ft.KeyboardType.NUMBER,
    width=150,
    on_change=self._on_min_length_changed
)

max_length_field = ft.TextField(
    label="Max peptide length",
    value="30",
    keyboard_type=ft.KeyboardType.NUMBER,
    width=150,
    on_change=self._on_max_length_changed
)

# Max cleavage sites
max_cleavage_field = ft.TextField(
    label="Max cleavage sites",
    value="2",
    keyboard_type=ft.KeyboardType.NUMBER,
    width=150,
    on_change=self._on_max_cleavage_changed
)

# Calculate button
calculate_btn = ft.ElevatedButton(
    content=ft.Text("Calculate LFQ"),
    icon=ft.Icons.CALCULATE,
    on_click=lambda e: self.page.run_task(self.calculate_lfq, e),
    style=ft.ButtonStyle(
        bgcolor=ft.Colors.GREEN_600,
        color=ft.Colors.WHITE
    )
)
```

!!!! ЗДесь тоже нужно сохранять параметры в project_settings

**Layout:**
```
Column [
    Text("Label-Free Quantification", bold)
    Container(height=10)
    Text("Methods:", size=14, weight=bold)
    Row [
        empai_checkbox,
        ibaq_checkbox,
        nsaf_checkbox,
        top3_checkbox
    ]
    Container(height=10)
    Row [
        empai_base_field,
        enzyme_dropdown
    ]
    Row [
        min_length_field,
        max_length_field,
        max_cleavage_field
    ]
    Container(height=10)
    calculate_btn
]
```

**Методы:**

```python
async def calculate_lfq(self, e):
    """
    Запуск расчёта LFQ для всех образцов.
    
    Workflow:
    1. Валидация: хотя бы один метод выбран
    2. Очистка старых результатов quantification
    3. Получение списка всех sample_id
    4. Для каждого sample_id:
       a. Вызов calculate_lfq() из api/proteins/lfq.py
       b. Обновление прогресса (dialog.update_progress())
       c. Сохранение результатов через project.add_protein_quantifications_batch()
    5. Обновление счётчиков в state
    6. Обновление таблицы
    """

async def _on_method_changed(self, method: str):
    """Обновление state при изменении чекбокса"""
    
def _on_empai_base_changed(self, e):
    """Обновление state.empai_base_value"""
    
def _on_enzyme_changed(self, e):
    """Обновление state.enzyme"""
    
# Аналогично для остальных полей...
```

**Импорт SUPPORTED_ENZYMES:**

```python
from api.calculations.proteins.sempai import SUPPORTED_ENZYMES
```

---

### 6. TableSection (table_section.py)

**Назначение:** Отображение результатов идентификаций и квантификаций.

**UI компоненты:**

```python
# Заголовок и фильтр
header = ft.Row([
    ft.Text("Results", size=18, weight=ft.FontWeight.BOLD),
    ft.Container(width=20),
    ft.Dropdown(
        label="Filter by sample",
        hint_text="All samples",
        width=300,
        options=[],  # Заполняется при load_data()
        on_change=self._on_sample_filter_changed
    )
], alignment=ft.MainAxisAlignment.START)

# DataTable
data_table = ft.DataTable(
    columns=[
        ft.DataColumn(ft.Text("Sample")),
        ft.DataColumn(ft.Text("Subset")),
        ft.DataColumn(ft.Text("Protein ID")),
        ft.DataColumn(ft.Text("Gene")),
        ft.DataColumn(ft.Text("Weight (Da)")),
        ft.DataColumn(ft.Text("Peptides")),
        ft.DataColumn(ft.Text("Unique")),
        ft.DataColumn(ft.Text("Coverage %")),
        ft.DataColumn(ft.Text("Intensity Sum")),
        ft.DataColumn(ft.Text("emPAI")),
        ft.DataColumn(ft.Text("iBAQ")),
        ft.DataColumn(ft.Text("NSAF")),
        ft.DataColumn(ft.Text("Top3"))
    ],
    rows=[],  # Заполняется при load_data()
    border=ft.border.all(1, ft.Colors.GREY_400),
    border_radius=10,
    vertical_lines=ft.border.BorderSide(1, ft.Colors.GREY_300),
    horizontal_lines=ft.border.BorderSide(1, ft.Colors.GREY_300),
    heading_row_color=ft.Colors.GREY_200,
    heading_row_height=50,
    data_row_max_height=60
)
```

**Layout:**
```
Column [
    header (Row with title and filter)
    Container(height=10)
    Container(
        content=Column([data_table], scroll=ft.ScrollMode.AUTO),
        expand=True
    )
]
```

**Методы:**

```python
async def load_data(self):
    """
    Загрузка данных из БД и заполнение таблицы.
    
    Steps:
    1. Вызов project.get_protein_results_joined(sample=self.state.selected_sample)
    2. Сохранение в self.state.table_data
    3. Формирование DataTable.rows из DataFrame
    4. Заполнение sample dropdown для фильтра
    5. Обновление UI
    """

def _on_sample_filter_changed(self, e):
    """
    Обработчик изменения фильтра по образцу.
    
    Обновляет state.selected_sample и перезагружает данные.
    """

def _format_coverage(self, value: float | None) -> str:
    """Форматирование coverage как XX.X%"""
    if value is None:
        return ""
    return f"{value:.1f}%"

def _format_number(self, value: float | None, decimals: int = 2) -> str:
    """Форматирование числовых значений"""
    if value is None:
        return ""
    return f"{value:.{decimals}f}"
```

**Структура данных таблицы:**

Каждая строка представляет один protein_identification_result с присоединёнными данными quantification.

Если для одного белка есть несколько методов LFQ, они отображаются в соответствующих колонках одной строки.

---

## Изменения в API (Project)

### Новые методы в `api/project/project.py`

#### 1. Работа с protein_identification_result

```python
async def clear_protein_identifications(self) -> None:
    """
    Очистить все результаты белковых идентификаций.
    
    Удаляет записи из protein_identification_result.
    Cascade удаляет связанные quantification results.
    """
    await self._execute("DELETE FROM protein_identification_result")
    await self.save()
    logger.info("Cleared all protein identifications")

async def add_protein_identifications_batch(
    self,
    identifications_df: pd.DataFrame
) -> None:
    """
    Добавить batch результатов белковых идентификаций.
    
    Args:
        identifications_df: DataFrame с колонками:
            - protein_id: str
            - sample_id: int
            - peptide_count: int
            - uq_evidence_count: int
            - coverage: float (percentage)
            - intensity_sum: float
    """
    rows_to_insert = []
    
    for _, row in identifications_df.iterrows():
        rows_to_insert.append((
            row['protein_id'],
            int(row['sample_id']),
            int(row['peptide_count']),
            int(row['uq_evidence_count']),
            float(row['coverage']) if row.get('coverage') is not None else None,
            float(row['intensity_sum']) if row.get('intensity_sum') is not None else None
        ))
    
    if rows_to_insert:
        await self._executemany(
            """INSERT INTO protein_identification_result 
               (protein_id, sample_id, peptide_count, uq_evidence_count, coverage, intensity_sum)
               VALUES (?, ?, ?, ?, ?, ?)""",
            rows_to_insert
        )
        await self.save()
        logger.info(f"Added {len(rows_to_insert)} protein identifications")

async def get_protein_identifications(
    self,
    sample_id: int | None = None
) -> pd.DataFrame:
    """
    Получить результаты белковых идентификаций.
    
    Args:
        sample_id: Опциональный фильтр по образцу
    
    Returns:
        DataFrame с колонками:
            - id, protein_id, sample_id, peptide_count,
              uq_evidence_count, coverage, intensity_sum
    """
    query = "SELECT * FROM protein_identification_result"
    params = None
    
    if sample_id is not None:
        query += " WHERE sample_id = ?"
        params = (sample_id,)
    
    query += " ORDER BY id"
    
    return await self.execute_query_df(query, params)

async def get_protein_identification_count(self) -> int:
    """Получить общее количество белковых идентификаций."""
    query = "SELECT COUNT(*) as count FROM protein_identification_result"
    result = await self.execute_query_df(query)
    if len(result) == 0:
        return 0
    return int(result.iloc[0]['count'])
```

#### 2. Работа с protein_quantification_result

```python
async def clear_protein_quantifications(self) -> None:
    """
    Очистить все результаты квантификации белков.
    """
    await self._execute("DELETE FROM protein_quantification_result")
    await self.save()
    logger.info("Cleared all protein quantifications")

async def add_protein_quantifications_batch(
    self,
    quantifications_df: pd.DataFrame
) -> None:
    """
    Добавить batch результатов квантификации белков.
    
    Args:
        quantifications_df: DataFrame с колонками:
            - protein_identification_id: int
            - algorithm: str ('emPAI', 'iBAQ', 'NSAF', 'Top3')
            - rel_value: float
            - abs_value: float | None
    """
    rows_to_insert = []
    
    for _, row in quantifications_df.iterrows():
        rows_to_insert.append((
            int(row['protein_identification_id']),
            row['algorithm'],
            float(row['rel_value']) if row.get('rel_value') is not None else None,
            float(row['abs_value']) if row.get('abs_value') is not None else None
        ))
    
    if rows_to_insert:
        await self._executemany(
            """INSERT INTO protein_quantification_result 
               (protein_identification_id, algorithm, rel_value, abs_value)
               VALUES (?, ?, ?, ?)""",
            rows_to_insert
        )
        await self.save()
        logger.info(f"Added {len(rows_to_insert)} protein quantifications")

async def get_protein_quantification_count(self) -> int:
    """Получить общее количество результатов квантификации."""
    query = "SELECT COUNT(*) as count FROM protein_quantification_result"
    result = await self.execute_query_df(query)
    if len(result) == 0:
        return 0
    return int(result.iloc[0]['count'])
```

#### 3. Объединённый запрос для таблицы

```python
async def get_protein_results_joined(
    self,
    sample: str | None = None
) -> pd.DataFrame:
    """
    Получить объединённые результаты идентификаций и квантификаций.
    
    Возвращает одну строку на каждый protein_identification_result
    с развёрнутыми колонками для каждого метода LFQ.
    
    Args:
        sample: Опциональный фильтр по имени образца
    
    Returns:
        DataFrame с колонками:
            - sample: str - имя образца
            - subset: str - имя группы
            - protein_id: str
            - gene: str | None
            - weight: float | None - молекулярная масса из sequence
            - peptide_count: int
            - unique_evidence_count: int (переименован из uq_evidence_count)
            - coverage_percent: float - coverage в процентах
            - intensity_sum: float
            - EmPAI: float | None
            - iBAQ: float | None
            - NSAF: float | None
            - Top3: float | None
    """
    # Основной запрос с JOIN
    query = """
        SELECT 
            pir.id,
            pir.protein_id,
            pir.sample_id,
            s.name AS sample,
            sub.name AS subset,
            p.gene,
            p.sequence,
            pir.peptide_count,
            pir.uq_evidence_count AS unique_evidence_count,
            pir.coverage AS coverage_percent,
            pir.intensity_sum,
            pqr_empai.rel_value AS EmPAI,
            pqr_ibaq.rel_value AS iBAQ,
            pqr_nsaf.rel_value AS NSAF,
            pqr_top3.rel_value AS Top3
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
    """
    
    params = None
    
    if sample is not None:
        query += " WHERE s.name = ?"
        params = (sample,)
    
    query += " ORDER BY s.name, pir.protein_id"
    
    df = await self.execute_query_df(query, params)
    
    # Вычислить weight из sequence
    if len(df) > 0 and 'sequence' in df.columns:
        def calc_weight(seq):
            if seq is None or pd.isna(seq):
                return None
            try:
                from pyteomics import mass
                return mass.calculate_mass(sequence=seq)
            except:
                return None
        
        df['weight'] = df['sequence'].apply(calc_weight)
        df = df.drop(columns=['sequence'])
    
    return df
```

---

## Изменения в схеме БД

### Модификация таблицы protein_identification_result

В файле `api/project/schema.py` необходимо добавить поле `intensity_sum`:

```sql
CREATE TABLE IF NOT EXISTS protein_identification_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    protein_id TEXT NOT NULL,
    sample_id INTEGER NOT NULL,
    peptide_count INTEGER NOT NULL,
    uq_evidence_count INTEGER NOT NULL,
    coverage REAL,
    intensity_sum REAL,  -- НОВОЕ ПОЛЕ
    FOREIGN KEY (protein_id) REFERENCES protein(id) ON DELETE CASCADE,
    FOREIGN KEY (sample_id) REFERENCES sample(id) ON DELETE CASCADE
);
```

**Миграция:** Не требуется, так как SQLite позволяет добавлять nullable колонки через ALTER TABLE, но в данном случае мы используем `CREATE TABLE IF NOT EXISTS`, поэтому изменение схемы применится только для новых БД. Для существующих БД поле будет добавлено автоматически при первом сохранении.

**Альтернатива (если требуется строгая миграция):**
```python
# В Project.initialize() после создания схемы
try:
    await self._execute(
        "ALTER TABLE protein_identification_result ADD COLUMN intensity_sum REAL"
    )
except aiosqlite.OperationalError:
    # Column already exists
    pass
```

---

## Логика работы

### Workflow: Calculate Protein Identifications

```
User clicks "Calculate Protein Identifications"
    ↓
DetectionSection.calculate_identifications()
    ↓
1. Validate parameters (min_peptides >= 1, min_unique >= 0)
    ↓
2. Show ProgressDialog
    ↓
3. Clear old results: project.clear_protein_identifications()
    ↓
4. Get data:
   - joined_data = project.get_joined_peptide_data(
         is_preferred=True,
         protein_identified=True
     )
   - sequences_db = project.get_protein_db_to_search()
    ↓
5. Call find_protein_identifications() async iterator
   For each (result_df, sample_id):
       - Update progress: f"Processing sample {current}/{total}"
       - Save: project.add_protein_identifications_batch(result_df)
    ↓
6. Update state.protein_identification_count
    ↓
7. Close dialog, show success message
    ↓
8. Refresh table: parent_tab.sections['table'].load_data()
```

### Workflow: Calculate LFQ

```
User clicks "Calculate LFQ"
    ↓
LFQSection.calculate_lfq()
    ↓
1. Validate: at least one method selected
    ↓
2. Show ProgressDialog
    ↓
3. Clear old results: project.clear_protein_quantifications()
    ↓
4. Get all sample IDs:
   samples = await project.execute_query_df(
       "SELECT DISTINCT id FROM sample ORDER BY id"
   )
    ↓
5. For each sample_id in samples['id']:
   a. Update progress: f"Processing sample {idx+1}/{len(samples)}"
   b. Get selected methods: state.get_selected_lfq_methods()
   c. Call calculate_lfq(
          project=project,
          sample_id=sample_id,
          methods=selected_methods,
          enzyme=state.enzyme,
          min_length=state.min_peptide_length,
          max_length=state.max_peptide_length,
          max_cleavage_sites=state.max_cleavage_sites,
          empai_base=state.empai_base_value
      )
   d. Save: project.add_protein_quantifications_batch(result_df)
    ↓
6. Update state.protein_quantification_count
    ↓
7. Close dialog, show success message
    ↓
8. Refresh table: parent_tab.sections['table'].load_data()
```

---

## Диалоги прогресса

### Переиспользование ProgressDialog

Используем существующий диалог из `gui/views/tabs/peptides/dialogs/progress_dialog.py`.

**Интерфейс:**
```python
class ProgressDialog:
    def __init__(self, page: ft.Page, title: str)
    def show(self)
    def close(self)
    def update_progress(self, progress: float | None, text: str)
    def complete(self)
```

**Использование:**

```python
# В начале операции
dialog = ProgressDialog(self.page, "Calculating Protein Identifications")
dialog.show()

# В процессе
dialog.update_progress(0.5, f"Processing sample 3 of 6")

# По завершению
dialog.complete()
await asyncio.sleep(1)
dialog.close()
```

**Примечание:** Если ProgressDialog отсутствует, создаём копию из peptides или создаём новый с аналогичным интерфейсом.

---

## Обработка ошибок

### Принципы

1. **Валидация входных данных** перед вызовом API
2. **Try-catch блоки** вокруг асинхронных операций
3. **Информативные сообщения** для пользователя
4. **Логирование** всех ошибок в консоль

### Типичные ошибки и обработка

#### 1. Недостаточно данных для расчёта

```python
# В DetectionSection.calculate_identifications()
joined_data = await self.project.get_joined_peptide_data(
    is_preferred=True,
    protein_identified=True
)

if len(joined_data) == 0:
    self.show_warning("No protein-matched identifications found. Please run peptide matching first.")
    return
```

#### 2. Невалидные параметры

```python
# Валидация в начале метода
try:
    min_pep = int(self.min_peptides_field.value)
    min_uq = int(self.min_unique_field.value)
    
    if min_pep < 1:
        self.show_error("Minimum peptides must be at least 1")
        return
    
    if min_uq < 0:
        self.show_error("Minimum unique peptides cannot be negative")
        return
        
except ValueError:
    self.show_error("Please enter valid numbers")
    return
```

#### 3. Ошибки БД или API

```python
try:
    await self.project.clear_protein_identifications()
    # ... остальной код
except Exception as ex:
    import traceback
    traceback.print_exc()
    self.show_error(f"Error: {str(ex)}")
    dialog.close()
```

#### 4. LFQ без выбранных методов

```python
selected_methods = self.state.get_selected_lfq_methods()
if not selected_methods:
    self.show_warning("Please select at least one LFQ method")
    return
```

---

## План разработки

### Этап 1: Подготовка инфраструктуры (30 минут)

- [ ] Создать структуру папок `gui/views/tabs/proteins/`
- [ ] Создать `__init__.py`, `shared_state.py`, `base_section.py`
- [ ] Скопировать/адаптировать `ProgressDialog` если нужно
- [ ] Изменить схему БД: добавить поле `intensity_sum`

### Этап 2: API методы в Project (45 минут)

- [ ] Реализовать `clear_protein_identifications()`
- [ ] Реализовать `add_protein_identifications_batch()`
- [ ] Реализовать `get_protein_identifications()`
- [ ] Реализовать `get_protein_identification_count()`
- [ ] Реализовать `clear_protein_quantifications()`
- [ ] Реализовать `add_protein_quantifications_batch()`
- [ ] Реализовать `get_protein_quantification_count()`
- [ ] Реализовать `get_protein_results_joined()`

### Этап 3: DetectionSection (30 минут)

- [ ] Создать базовый UI (поля, кнопка)
- [ ] Реализовать обработчики изменения полей
- [ ] Реализовать `calculate_identifications()` с прогрессом
- [ ] Протестировать на реальных данных

### Этап 4: LFQSection (45 минут)

- [ ] Создать UI (чекбоксы, поля, dropdown)
- [ ] Импортировать SUPPORTED_ENZYMES
- [ ] Реализовать обработчики изменения параметров
- [ ] Реализовать `calculate_lfq()` с итерацией по образцам
- [ ] Протестировать на реальных данных

### Этап 5: TableSection (45 минут)

- [ ] Создать DataTable с колонками
- [ ] Реализовать `load_data()` с вызовом `get_protein_results_joined()`
- [ ] Реализовать форматирование значений
- [ ] Реализовать фильтр по образцам
- [ ] Протестировать отображение

### Этап 6: ProteinsTab композиция (30 минут)

- [ ] Собрать все секции в главный Tab
- [ ] Реализовать `_load_initial_data()`
- [ ] Реализовать `refresh_all()`
- [ ] Обновить `gui/views/tabs/__init__.py` для экспорта
- [ ] Протестировать навигацию между секциями

### Этап 7: Интеграция и тестирование (30 минут)

- [ ] Полный цикл: загрузка данных → расчёт → LFQ → отображение
- [ ] Проверка обработки ошибок
- [ ] Проверка прогресс-диалогов
- [ ] Проверка фильтрации таблицы
- [ ] Финальная отладка

### Этап 8: Документация (30 минут)

- [ ] Создать `gui/views/tabs/proteins/README.md` с описанием архитектуры
- [ ] Обновить пользовательскую документацию
- [ ] Создать CHANGELOG для фазы 4.2

---

**Общее время разработки:** ~4-5 часов

**Приоритет:** Высокий  
**Блокирующие зависимости:** Фаза 4.1 (завершена)  
**Следующий этап:** Фаза 4.3 (отчёты и визуализация)

---

## Примечания для разработчика

1. **Переиспользование кода:** Максимально использовать паттерны из вкладки Peptides
2. **Консистентность:** Стиль кода, именование, структура должны соответствовать существующему коду
3. **Асинхронность:** Все операции с БД строго асинхронные
4. **Обратная связь:** Прогресс-диалоги обязательны для операций >1 секунды

!!! Тестирование проведем совместно в ручном режиме после разработки, тесты не пишем и не запускаем !!!
---

**Конец спецификации**
