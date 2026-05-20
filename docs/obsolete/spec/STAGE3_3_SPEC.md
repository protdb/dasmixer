# Спецификация STAGE3_3: Разработка вкладки Peptides

## Обзор

Этап 3.3 включает разработку полноценного пользовательского интерфейса для работы с пептидными идентификациями на вкладке **Peptides**. Вкладка позволяет:
- Загружать библиотеки белковых последовательностей (FASTA)
- Настраивать параметры идентификации для каждого инструмента
- Настраивать параметры разметки ионов
- Выбирать оптимальную идентификацию для каждого спектра
- Искать и просматривать идентификации с визуализацией графиков разметки ионов

## Архитектурные решения

### Принципы реализации
- Максимальное соответствие паттернам `samples_tab.py`
- Асинхронная работа с БД через `Project` API
- Использование `ft.Container` для визуального разделения блоков
- Валидация пользовательского ввода
- Информативные уведомления через `SnackBar`

### Структура файлов

```
api/inputs/proteins/
  __init__.py
  fasta.py              # Новый парсер FASTA

gui/views/tabs/
  peptides_tab.py       # Полная переработка существующего файла
```

## 1. Парсер FASTA (`api/inputs/proteins/fasta.py`)

### Класс `FastaParser`

Абстрактный базовый класс уже существует, необходимо создать конкретную реализацию для парсинга FASTA файлов.

#### Параметры конструктора
```python
def __init__(
    self,
    file_path: str,
    is_uniprot: bool = True,
    enrich_from_uniprot: bool = False
)
```

**Параметры:**
- `file_path` (str) - путь к FASTA файлу
- `is_uniprot` (bool) - формат последовательностей UniProt (по умолчанию True)
- `enrich_from_uniprot` (bool) - обогащать данные с UniProt (по умолчанию False)

#### Методы

##### `async def validate() -> bool`
Проверяет корректность формата FASTA файла.

**Возвращает:**
- `True` если файл валидный
- `False` если формат некорректен

**Логика проверки:**
- Файл существует и читается
- Содержит хотя бы одну запись в формате FASTA
- Заголовки начинаются с `>`
- Последовательности содержат только допустимые символы (A-Z)

##### `async def parse_batch(batch_size: int = 100) -> AsyncIterator[pd.DataFrame]`
Парсит FASTA файл батчами.

**Параметры:**
- `batch_size` (int) - размер батча (по умолчанию 100)

**Возвращает:**
- AsyncIterator[pd.DataFrame] с колонками:
  - `id` (str) - идентификатор белка (из заголовка)
  - `is_uniprot` (bool) - флаг UniProt формата
  - `fasta_name` (str) - полный заголовок из FASTA
  - `sequence` (str) - аминокислотная последовательность
  - `gene` (str | None) - название гена (если парсится из заголовка)

**Парсинг заголовка UniProt:**
Формат: `>sp|P12345|PROT_HUMAN Protein name OS=Homo sapiens GN=GENE PE=1 SV=1`

Извлекаемые поля:
- `id` = `P12345` (UniProt accession)
- `gene` = `GENE` (из части `GN=GENE`)
- `fasta_name` = полный заголовок без `>`

**Парсинг обычного заголовка:**
- `id` = всё до первого пробела (без `>`)
- `gene` = None
- `fasta_name` = полный заголовок без `>`

##### `async def enrich_with_uniprot(df: pd.DataFrame) -> pd.DataFrame`
Обогащает данные через UniProt API (опционально).

**Параметры:**
- `df` (pd.DataFrame) - DataFrame с белками

**Возвращает:**
- Обогащённый DataFrame (детали обогащения уточняются на этапе реализации)

**Примечание:** На этом этапе можно оставить заглушку или базовую реализацию.

#### Интеграция с Registry

Парсер **НЕ** регистрируется в `InputTypesRegistry`, так как:
- Не является парсером спектральных данных
- Не является парсером идентификаций пептидов
- Используется напрямую в UI для загрузки библиотеки белков

## 2. Вкладка Peptides (`gui/views/tabs/peptides_tab.py`)

### Общая структура класса `PeptidesTab`

```python
class PeptidesTab(ft.Container):
    def __init__(self, project: Project):
        super().__init__()
        self.project = project
        self.expand = True
        self.padding = 0
        
        # UI state
        self._updating = False
        self.tools_list = []  # List of Tool dataclasses
        self.tool_settings_controls = {}  # tool_id -> dict of controls
        
        # Build content
        self.content = self._build_content()
    
    def did_mount(self):
        """Load initial data when tab is mounted."""
        self.page.run_task(self._load_initial_data)
    
    async def _load_initial_data(self):
        """Load tools and settings."""
        await self.refresh_tools()
        await self.load_ion_settings()
```

### Блок 1: Загрузка файла последовательностей

#### UI компоненты

```
┌─────────────────────────────────────────────────────────────────┐
│ Protein Sequence Library                                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  File: [____________________] [Browse]                           │
│                                                                  │
│  ☑ Sequences in UniProt format                                  │
│  ☐ Enrich data from UniProt                                     │
│                                                                  │
│  [Load Sequences]                                                │
│                                                                  │
│  Status: No library loaded                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Компоненты Flet

```python
# File selection
self.fasta_file_field = ft.TextField(
    label="FASTA file path",
    hint_text="Select FASTA file...",
    expand=True,
    read_only=True
)

self.fasta_browse_btn = ft.ElevatedButton(
    content=ft.Text("Browse"),
    icon=ft.Icons.FOLDER_OPEN,
    on_click=lambda e: self.page.run_task(self.browse_fasta_file, e)
)

# Options
self.fasta_is_uniprot_cb = ft.Checkbox(
    label="Sequences in UniProt format",
    value=True
)

self.fasta_enrich_uniprot_cb = ft.Checkbox(
    label="Enrich data from UniProt",
    value=False
)

# Load button
self.fasta_load_btn = ft.ElevatedButton(
    content=ft.Text("Load Sequences"),
    icon=ft.Icons.UPLOAD_FILE,
    on_click=lambda e: self.page.run_task(self.load_fasta_file, e)
)

# Status
self.fasta_status_text = ft.Text(
    "No library loaded",
    italic=True,
    color=ft.Colors.GREY_600
)
```

#### Методы

##### `async def browse_fasta_file(e)`
Открывает диалог выбора FASTA файла.

**Логика:**
- Использует `ft.FilePicker().pick_files()` с фильтром `*.fasta, *.fa`
- Обновляет `self.fasta_file_field.value`
- Валидирует наличие файла

##### `async def load_fasta_file(e)`
Загружает и импортирует FASTA файл в проект.

**Логика:**
1. Проверить наличие выбранного файла
2. Показать progress dialog
3. Создать `FastaParser` с параметрами из чекбоксов
4. Валидировать файл через `parser.validate()`
5. Парсить батчами через `parser.parse_batch()`
6. Если `enrich_from_uniprot=True`, обогатить данные
7. Сохранить через `project.add_proteins_batch()`
8. Обновить статус (показать количество загруженных белков)
9. Показать SnackBar с результатом

**Progress Dialog:**
- Заголовок: "Loading Protein Sequences"
- Прогресс-бар
- Детали: "Loaded X proteins..."

**Обработка ошибок:**
- Файл не выбран → SnackBar "Please select a FASTA file"
- Невалидный формат → SnackBar "Invalid FASTA format"
- Ошибка импорта → SnackBar с описанием ошибки

**Обновление статуса:**
После успешной загрузки обновить `self.fasta_status_text`:
```
"Loaded: 1,234 proteins from file.fasta"
```

### Блок 2: Настройки инструментов

#### UI компоненты

```
┌─────────────────────────────────────────────────────────────────┐
│ Tool Settings                                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─ PowerNovo2 ────────────────────────────────────────────┐   │
│  │                                                           │   │
│  │  Max PPM: [___50___]                                      │   │
│  │  Min Score: [___0.8___]                                   │   │
│  │  Min Ion Intensity Coverage: [___25___] %                 │   │
│  │  ☐ Use protein identification from file                  │   │
│  │  Min Protein Identity: [___0.75___]                       │   │
│  │  ☐ DeNovo seq correction with search                     │   │
│  │                                                           │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─ MaxQuant ──────────────────────────────────────────────┐   │
│  │  ... (аналогично для каждого tool)                       │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Компоненты Flet

Для каждого инструмента создаётся набор контролов:

```python
def _create_tool_settings_controls(self, tool: Tool) -> dict:
    """Create settings controls for a tool."""
    
    # Load existing settings or use defaults
    settings = tool.settings or {}
    
    controls = {
        'max_ppm': ft.TextField(
            label="Max PPM",
            value=str(settings.get('max_ppm', 50)),
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        ),
        'min_score': ft.TextField(
            label="Min Score",
            value=str(settings.get('min_score', 0.8)),
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        ),
        'min_ion_intensity_coverage': ft.TextField(
            label="Min Ion Intensity Coverage (%)",
            value=str(settings.get('min_ion_intensity_coverage', 25)),
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER
        ),
        'use_protein_from_file': ft.Checkbox(
            label="Use protein identification from file",
            value=settings.get('use_protein_from_file', False)
        ),
        'min_protein_identity': ft.TextField(
            label="Min Protein Identity",
            value=str(settings.get('min_protein_identity', 0.75)),
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        ),
        'denovo_correction': ft.Checkbox(
            label="DeNovo seq correction with search",
            value=settings.get('denovo_correction', False)
        )
    }
    
    return controls
```

Контролы размещаются внутри `ft.Container` с заголовком (имя инструмента):

```python
ft.Container(
    content=ft.Column([
        ft.Text(tool.name, size=16, weight=ft.FontWeight.BOLD),
        ft.Row([
            controls['max_ppm'],
            controls['min_score'],
            controls['min_ion_intensity_coverage']
        ], spacing=10),
        controls['use_protein_from_file'],
        ft.Row([
            controls['min_protein_identity'],
            controls['denovo_correction']
        ], spacing=10)
    ], spacing=10),
    padding=15,
    border=ft.border.all(1, ft.Colors.BLUE_200),
    border_radius=8,
    bgcolor=ft.Colors.BLUE_50
)
```

#### Методы

##### `async def refresh_tools()`
Загружает список инструментов и создаёт для них контролы настроек.

**Логика:**
1. Получить инструменты: `tools = await self.project.get_tools()`
2. Для каждого инструмента создать контролы: `self._create_tool_settings_controls(tool)`
3. Сохранить в `self.tool_settings_controls[tool.id] = controls`
4. Обновить UI

**Примечание:** Если инструментов нет, показать:
```
"No tools configured. Add tools in the Samples tab."
```

##### `def _validate_tool_settings(tool_id: int) -> tuple[bool, str | None]`
Валидирует настройки инструмента.

**Валидация:**
- `max_ppm` > 0
- `0 < min_score <= 1`
- `0 < min_ion_intensity_coverage <= 100`
- `0 < min_protein_identity <= 1`

**Возвращает:**
- `(True, None)` если всё корректно
- `(False, "error message")` если есть ошибки

##### `async def save_tool_settings(tool_id: int)`
Сохраняет настройки инструмента в БД.

**Логика:**
1. Получить контролы: `controls = self.tool_settings_controls[tool_id]`
2. Валидировать значения
3. Собрать в словарь settings
4. Обновить tool: `tool.settings = settings`
5. Сохранить: `await self.project.update_tool(tool)`

**Примечание:** Метод вызывается из функции пересчёта идентификаций, не напрямую из UI.

### Блок 3: Настройки разметки ионов

#### UI компоненты

```
┌─────────────────────────────────────────────────────────────────┐
│ Ion Matching Settings                                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Ion Types:  ☐ a  ☑ b  ☐ c  ☐ x  ☑ y  ☐ z                      │
│                                                                  │
│  Losses:     ☐ Water loss (H₂O)  ☐ Ammonia loss (NH₃)           │
│                                                                  │
│  PPM Threshold: [___20___]                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Компоненты Flet

```python
# Ion types checkboxes
self.ion_type_a_cb = ft.Checkbox(label="a", value=False)
self.ion_type_b_cb = ft.Checkbox(label="b", value=True)
self.ion_type_c_cb = ft.Checkbox(label="c", value=False)
self.ion_type_x_cb = ft.Checkbox(label="x", value=False)
self.ion_type_y_cb = ft.Checkbox(label="y", value=True)
self.ion_type_z_cb = ft.Checkbox(label="z", value=False)

# Losses checkboxes
self.water_loss_cb = ft.Checkbox(
    label="Water loss (H₂O)",
    value=False
)
self.nh3_loss_cb = ft.Checkbox(
    label="Ammonia loss (NH₃)",
    value=False
)

# PPM threshold
self.ion_ppm_threshold_field = ft.TextField(
    label="PPM Threshold",
    value="20",
    width=150,
    keyboard_type=ft.KeyboardType.NUMBER
)
```

Layout:
```python
ft.Container(
    content=ft.Column([
        ft.Text("Ion Matching Settings", size=18, weight=ft.FontWeight.BOLD),
        ft.Row([
            ft.Text("Ion Types:", weight=ft.FontWeight.W_500),
            self.ion_type_a_cb,
            self.ion_type_b_cb,
            self.ion_type_c_cb,
            self.ion_type_x_cb,
            self.ion_type_y_cb,
            self.ion_type_z_cb
        ], spacing=15),
        ft.Row([
            ft.Text("Losses:", weight=ft.FontWeight.W_500),
            self.water_loss_cb,
            self.nh3_loss_cb
        ], spacing=15),
        self.ion_ppm_threshold_field
    ], spacing=10),
    padding=20,
    border=ft.border.all(1, ft.Colors.GREY),
    border_radius=10
)
```

#### Методы

##### `async def load_ion_settings()`
Загружает настройки разметки ионов из `project_settings`.

**Ключи настроек:**
- `ion_types` - строка с типами ионов, разделёнными запятыми (например: "b,y")
- `water_loss` - boolean (0/1 в SQLite)
- `nh3_loss` - boolean
- `ion_ppm_threshold` - число

**Логика:**
1. Получить настройки:
   ```python
   ion_types_str = await self.project.get_setting('ion_types', 'b,y')
   water_loss = await self.project.get_setting('water_loss', '0')
   nh3_loss = await self.project.get_setting('nh3_loss', '0')
   ppm_threshold = await self.project.get_setting('ion_ppm_threshold', '20')
   ```
2. Распарсить `ion_types_str` и обновить чекбоксы
3. Обновить остальные контролы

##### `async def save_ion_settings()`
Сохраняет настройки разметки ионов.

**Логика:**
1. Собрать выбранные типы ионов в строку
   ```python
   selected_types = []
   if self.ion_type_a_cb.value: selected_types.append('a')
   if self.ion_type_b_cb.value: selected_types.append('b')
   # ... и т.д.
   ion_types_str = ','.join(selected_types)
   ```
2. Сохранить через `project.set_setting()`:
   ```python
   await self.project.set_setting('ion_types', ion_types_str)
   await self.project.set_setting('water_loss', '1' if self.water_loss_cb.value else '0')
   await self.project.set_setting('nh3_loss', '1' if self.nh3_loss_cb.value else '0')
   await self.project.set_setting('ion_ppm_threshold', self.ion_ppm_threshold_field.value)
   ```

**Валидация:**
- Проверить, что выбран хотя бы один тип иона
- Проверить, что PPM threshold > 0

**Примечание:** Метод вызывается из функции пересчёта идентификаций.

### Блок 4: Выбор оптимальной идентификации

#### UI компоненты

```
┌─────────────────────────────────────────────────────────────────┐
│ Preferred Identification Selection                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Selection Criterion:                                            │
│    ○ PPM error                                                   │
│    ● Intensity coverage                                          │
│                                                                  │
│  [Run Identification Matching]                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Компоненты Flet

```python
# Selection criterion radio buttons
self.selection_criterion_group = ft.RadioGroup(
    content=ft.Column([
        ft.Radio(value="ppm", label="PPM error"),
        ft.Radio(value="intensity", label="Intensity coverage")
    ]),
    value="intensity"
)

# Run button
self.run_matching_btn = ft.ElevatedButton(
    content=ft.Text("Run Identification Matching"),
    icon=ft.Icons.PLAY_ARROW,
    on_click=lambda e: self.page.run_task(self.run_identification_matching, e)
)
```

Layout:
```python
ft.Container(
    content=ft.Column([
        ft.Text("Preferred Identification Selection", size=18, weight=ft.FontWeight.BOLD),
        ft.Text("Selection Criterion:", weight=ft.FontWeight.W_500),
        self.selection_criterion_group,
        ft.Container(height=10),
        self.run_matching_btn
    ], spacing=10),
    padding=20,
    border=ft.border.all(1, ft.Colors.GREY),
    border_radius=10
)
```

#### Методы

##### `async def run_identification_matching(e)`
Запускает процесс выбора оптимальной идентификации для каждого спектра.

**Сигнатура функции пересчёта (будет реализована разработчиком):**
```python
async def select_preferred_identifications(
    project: Project,
    criterion: str,  # "ppm" or "intensity"
    ion_settings: dict,
    tool_settings: dict[int, dict]
) -> int:
    """
    Select preferred identifications for all spectra.
    
    Args:
        project: Project instance
        criterion: Selection criterion ("ppm" or "intensity")
        ion_settings: Ion matching settings from project_settings
        tool_settings: Dict mapping tool_id to tool settings
    
    Returns:
        Number of spectra processed
    """
    pass
```

**Логика UI метода:**
1. Валидировать настройки всех инструментов
2. Сохранить настройки всех инструментов
3. Сохранить настройки разметки ионов
4. Собрать параметры:
   ```python
   criterion = self.selection_criterion_group.value
   
   # Ion settings
   ion_settings = {
       'ion_types': [тип for тип if соответствующий_checkbox.value],
       'water_loss': self.water_loss_cb.value,
       'nh3_loss': self.nh3_loss_cb.value,
       'ppm_threshold': float(self.ion_ppm_threshold_field.value)
   }
   
   # Tool settings
   tool_settings = {}
   for tool_id, controls in self.tool_settings_controls.items():
       tool_settings[tool_id] = {
           'max_ppm': float(controls['max_ppm'].value),
           'min_score': float(controls['min_score'].value),
           # ... и т.д.
       }
   ```
5. Показать progress dialog
6. Вызвать функцию пересчёта:
   ```python
   from api.calculations.peptides.matching import select_preferred_identifications
   
   count = await select_preferred_identifications(
       self.project,
       criterion,
       ion_settings,
       tool_settings
   )
   ```
7. Обновить прогресс
8. Показать результат в SnackBar

**Progress Dialog:**
- Заголовок: "Running Identification Matching"
- Прогресс-бар (indeterminate или с обновлением из функции)
- Детали: "Processing spectra..."

**Обработка ошибок:**
- Нет инструментов → "No tools configured"
- Ошибка валидации → показать детали
- Ошибка выполнения → показать описание

**Результат:**
```
"Successfully processed 1,234 spectra"
```

**Примечание:** Файл `api/peptides/matching.py` с функцией `select_preferred_identifications` будет создан как заглушка с TODO для разработчика.

### Блок 5: Просмотр идентификаций

#### UI компоненты

```
┌─────────────────────────────────────────────────────────────────┐
│ Search and View Identifications                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Sample: [All Samples ▼]  Tool: [All Tools ▼]                   │
│                                                                  │
│  Search by: [Sequence Number ▼]  Value: [_____]  [Search]       │
│                                                                  │
│  Results (5 found):                                              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ Seq#  Sample    Tool         Sequence      Score  PPM    │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │ 1234  Sample1   PowerNovo2   PEPTIDE...   0.95    2.3  ● │  │
│  │ 1235  Sample1   MaxQuant     ANOTHER...   0.88    1.2    │  │
│  │ ...                                                        │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Ion Match Visualization:                                        │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                                                            │  │
│  │              [График разметки ионов]                       │  │
│  │                                                            │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Компоненты Flet

**Фильтры:**
```python
# Sample filter
self.search_sample_dropdown = ft.Dropdown(
    label="Sample",
    options=[ft.dropdown.Option(key="all", text="All Samples")],
    value="all",
    width=200
)

# Tool filter
self.search_tool_dropdown = ft.Dropdown(
    label="Tool",
    options=[ft.dropdown.Option(key="all", text="All Tools")],
    value="all",
    width=200
)

# Search by dropdown
self.search_by_dropdown = ft.Dropdown(
    label="Search by",
    options=[
        ft.dropdown.Option(key="seq_no", text="Sequence Number"),
        ft.dropdown.Option(key="scans", text="Scans"),
        ft.dropdown.Option(key="sequence", text="Sequence"),
        ft.dropdown.Option(key="canonical_sequence", text="Canonical Sequence")
    ],
    value="seq_no",
    width=200
)

# Search value
self.search_value_field = ft.TextField(
    label="Search value",
    hint_text="Enter value...",
    expand=True,
    on_submit=lambda e: self.page.run_task(self.search_identifications, e)
)

# Search button
self.search_btn = ft.ElevatedButton(
    content=ft.Text("Search"),
    icon=ft.Icons.SEARCH,
    on_click=lambda e: self.page.run_task(self.search_identifications, e)
)
```

**Таблица результатов:**
```python
self.results_table = ft.DataTable(
    columns=[
        ft.DataColumn(ft.Text("Seq#")),
        ft.DataColumn(ft.Text("Sample")),
        ft.DataColumn(ft.Text("Tool")),
        ft.DataColumn(ft.Text("Sequence")),
        ft.DataColumn(ft.Text("Score")),
        ft.DataColumn(ft.Text("PPM")),
        ft.DataColumn(ft.Text("View"))
    ],
    rows=[]
)

self.results_container = ft.Container(
    content=ft.Column([
        ft.Text("No results", italic=True, color=ft.Colors.GREY_600)
    ]),
    padding=10,
    border=ft.border.all(1, ft.Colors.GREY_300),
    border_radius=5,
    height=300
)
```

**График:**
```python
self.plot_container = ft.Container(
    content=ft.Column([
        ft.Text("Select an identification to view ion match", italic=True, color=ft.Colors.GREY_600)
    ]),
    padding=10,
    border=ft.border.all(1, ft.Colors.GREY_300),
    border_radius=5,
    height=400
)
```

#### Методы

##### `async def refresh_search_filters()`
Обновляет списки в выпадающих меню фильтров.

**Логика:**
1. Получить образцы: `samples = await self.project.get_samples()`
2. Получить инструменты: `tools = await self.project.get_tools()`
3. Обновить опции:
   ```python
   self.search_sample_dropdown.options = [
       ft.dropdown.Option(key="all", text="All Samples")
   ] + [
       ft.dropdown.Option(key=str(s.id), text=s.name)
       for s in samples
   ]
   
   self.search_tool_dropdown.options = [
       ft.dropdown.Option(key="all", text="All Tools")
   ] + [
       ft.dropdown.Option(key=str(t.id), text=t.name)
       for t in tools
   ]
   ```

##### `async def search_identifications(e)`
Выполняет поиск идентификаций по заданным критериям.

**Логика:**
1. Получить параметры поиска:
   ```python
   sample_id = None if self.search_sample_dropdown.value == "all" else int(self.search_sample_dropdown.value)
   tool_id = None if self.search_tool_dropdown.value == "all" else int(self.search_tool_dropdown.value)
   search_by = self.search_by_dropdown.value
   search_value = self.search_value_field.value
   ```

2. Валидация:
   - Если `search_by` не "all", проверить что `search_value` не пустой

3. Построить SQL запрос через Project API:
   ```python
   # Базовый запрос
   query = """
       SELECT i.*, s.seq_no, s.scans, s.pepmass, s.rt,
              sam.name as sample_name, t.name as tool_name
       FROM identification i
       JOIN spectre s ON i.spectre_id = s.id
       JOIN spectre_file sf ON s.spectre_file_id = sf.id
       JOIN sample sam ON sf.sample_id = sam.id
       JOIN tool t ON i.tool_id = t.id
       WHERE 1=1
   """
   
   params = []
   
   # Добавить фильтры
   if sample_id:
       query += " AND sam.id = ?"
       params.append(sample_id)
   
   if tool_id:
       query += " AND t.id = ?"
       params.append(tool_id)
   
   if search_value:
       if search_by == "seq_no":
           query += " AND s.seq_no = ?"
           params.append(int(search_value))
       elif search_by == "scans":
           query += " AND s.scans = ?"
           params.append(int(search_value))
       elif search_by == "sequence":
           query += " AND i.sequence LIKE ?"
           params.append(f"%{search_value}%")
       elif search_by == "canonical_sequence":
           query += " AND i.canonical_sequence LIKE ?"
           params.append(f"%{search_value}%")
   
   query += " ORDER BY s.seq_no, i.score DESC"
   
   results_df = await self.project.execute_query_df(query, tuple(params))
   ```

4. Обновить таблицу результатов:
   ```python
   if len(results_df) == 0:
       # Показать "No results"
       self.results_container.content = ft.Column([
           ft.Text("No results found", italic=True, color=ft.Colors.GREY_600)
       ])
   else:
       # Создать строки таблицы
       rows = []
       for idx, row in results_df.iterrows():
           # Иконка preferred
           preferred_icon = ft.Icon(
               ft.Icons.STAR,
               color=ft.Colors.AMBER,
               size=16
           ) if row['is_preferred'] else ft.Container(width=16)
           
           rows.append(
               ft.DataRow(
                   cells=[
                       ft.DataCell(ft.Text(str(row['seq_no']))),
                       ft.DataCell(ft.Text(row['sample_name'])),
                       ft.DataCell(ft.Text(row['tool_name'])),
                       ft.DataCell(ft.Text(row['sequence'][:20] + "..." if len(row['sequence']) > 20 else row['sequence'])),
                       ft.DataCell(ft.Text(f"{row['score']:.2f}" if row['score'] else "N/A")),
                       ft.DataCell(ft.Text(f"{row['ppm']:.2f}" if row['ppm'] else "N/A")),
                       ft.DataCell(
                           ft.Row([
                               preferred_icon,
                               ft.IconButton(
                                   icon=ft.Icons.VISIBILITY,
                                   tooltip="View ion match",
                                   on_click=lambda e, r=row: self.page.run_task(self.view_identification, e, r)
                               )
                           ], spacing=5)
                       )
                   ]
               )
           )
       
       self.results_table.rows = rows
       self.results_container.content = ft.Column([
           ft.Text(f"Results ({len(results_df)} found):", weight=ft.FontWeight.BOLD),
           ft.Container(
               content=self.results_table,
               border=ft.border.all(1, ft.Colors.GREY_300),
               border_radius=5
           )
       ], spacing=10)
   ```

5. Если результат один или выбран первый, автоматически показать график:
   ```python
   if len(results_df) > 0:
       first_result = results_df.iloc[0].to_dict()
       await self.view_identification(None, first_result)
   ```

6. Обновить UI

**Обработка ошибок:**
- Ошибка запроса → SnackBar с описанием
- Невалидное значение поиска → error_text в поле

##### `async def view_identification(e, identification_row: dict)`
Отображает график разметки ионов для выбранной идентификации.

**Параметры:**
- `identification_row` - словарь с данными идентификации из результатов поиска

**Логика:**
1. Получить полные данные спектра:
   ```python
   spectrum = await self.project.get_spectrum_full(identification_row['spectre_id'])
   ```

2. Получить настройки разметки ионов:
   ```python
   ion_types_str = await self.project.get_setting('ion_types', 'b,y')
   ion_types = ion_types_str.split(',')
   water_loss = (await self.project.get_setting('water_loss', '0')) == '1'
   nh3_loss = (await self.project.get_setting('nh3_loss', '0')) == '1'
   ppm_threshold = float(await self.project.get_setting('ion_ppm_threshold', '20'))
   ```

3. Построить график:
   ```python
   from api.calculations.spectra.plot_matches import plot_ion_match
   
   fig = plot_ion_match(
       mz_array=spectrum['mz_array'],
       intensity_array=spectrum['intensity_array'],
       sequence=identification_row['sequence'],
       charge=spectrum['charge'],
       ion_types=ion_types,
       water_loss=water_loss,
       nh3_loss=nh3_loss,
       ppm_threshold=ppm_threshold
   )
   ```

4. Отобразить график в контейнере:
   ```python
   # Конвертировать Plotly figure в изображение или HTML
   # Вариант 1: Через Image (требует конвертации)
   import plotly.io as pio
   img_bytes = pio.to_image(fig, format='png')
   
   self.plot_container.content = ft.Column([
       ft.Text(
           f"Ion Match: {identification_row['sequence']} (Seq# {identification_row['seq_no']})",
           weight=ft.FontWeight.BOLD
       ),
       ft.Image(
           src_base64=base64.b64encode(img_bytes).decode(),
           width=800,
           height=400
       )
   ], spacing=10)
   
   # Вариант 2: Через HTML (если поддерживается)
   # html_str = pio.to_html(fig, include_plotlyjs='cdn')
   # self.plot_container.content = ft.HTML(html_str, width=800, height=400)
   ```

5. Обновить контейнер

**Примечание:** 
- Использовать существующую функцию `plot_ion_match` из `api/spectra/plot_matches.py`
- Если функция требует дополнительные параметры, передать их из настроек
- Рассмотреть интеграцию pywebview для интерактивных графиков (опционально на этом этапе)

**Обработка ошибок:**
- Спектр не найден → показать сообщение
- Ошибка построения графика → показать описание
- Использовать try-except для безопасности

#### Интеграция при монтировании

При монтировании вкладки (`did_mount`):
1. Загрузить инструменты
2. Загрузить настройки ионов
3. Обновить фильтры поиска

При переключении на вкладку:
- Обновить список инструментов (могли добавить на Samples tab)
- Обновить фильтры поиска

### Общая структура layout вкладки

```python
def _build_content(self):
    """Build the tab content."""
    
    # Секция 1: Загрузка FASTA
    fasta_section = self._build_fasta_section()
    
    # Секция 2: Настройки инструментов
    tools_section = self._build_tools_settings_section()
    
    # Секция 3: Настройки ионов
    ion_section = self._build_ion_settings_section()
    
    # Секция 4: Выбор оптимальной идентификации
    matching_section = self._build_matching_section()
    
    # Секция 5: Поиск и просмотр
    search_section = self._build_search_section()
    
    # Главный layout
    return ft.Column([
            fasta_section,
            ft.Container(height=10),
            tools_section,
            ft.Container(height=10),
            ion_section,
            ft.Container(height=10),
            matching_section,
            ft.Container(height=10),
            search_section
        ],
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        expand=True
    )
```

## 3. Заглушка функции пересчёта (`api/peptides/matching.py`)

Создать новый файл с функцией для реализации разработчиком:

```python
"""Peptide identification matching and selection."""

from api.project.project import Project
from utils.logger import logger


async def select_preferred_identifications(
    project: Project,
    criterion: str,
    ion_settings: dict,
    tool_settings: dict[int, dict]
) -> int:
    """
    Select preferred identifications for all spectra based on criterion.
    
    This function performs the following:
    1. Load all identifications from the database
    2. For each spectrum with multiple identifications:
       - Apply tool-specific filters (max_ppm, min_score, min_ion_intensity_coverage)
       - Calculate ion match coverage based on ion_settings
       - Select best identification based on criterion
       - Mark as preferred (is_preferred=1)
    3. Update database with preferred selections
    
    Args:
        project: Project instance
        criterion: Selection criterion
            - "ppm": Select identification with lowest PPM error
            - "intensity": Select identification with highest ion intensity coverage
        ion_settings: Ion matching configuration
            - ion_types: List of ion types to consider (e.g., ['b', 'y'])
            - water_loss: Include water loss ions (bool)
            - nh3_loss: Include ammonia loss ions (bool)
            - ppm_threshold: PPM threshold for ion matching (float)
        tool_settings: Tool-specific settings, mapping tool_id to:
            - max_ppm: Maximum allowed PPM error (float)
            - min_score: Minimum identification score (float)
            - min_ion_intensity_coverage: Minimum % intensity coverage (float)
            - use_protein_from_file: Use protein IDs from file (bool)
            - min_protein_identity: Minimum protein sequence identity (float)
            - denovo_correction: Apply de novo correction (bool)
    
    Returns:
        Number of spectra processed
    
    Raises:
        ValueError: If invalid criterion or settings provided
    
    TODO: Implement the full logic
    - Ion fragment generation
    - PPM-based matching
    - Intensity coverage calculation
    - Database updates
    
    Example:
        >>> ion_settings = {
        ...     'ion_types': ['b', 'y'],
        ...     'water_loss': False,
        ...     'nh3_loss': False,
        ...     'ppm_threshold': 20.0
        ... }
        >>> tool_settings = {
        ...     1: {
        ...         'max_ppm': 50.0,
        ...         'min_score': 0.8,
        ...         'min_ion_intensity_coverage': 25.0
        ...     }
        ... }
        >>> count = await select_preferred_identifications(
        ...     project, "intensity", ion_settings, tool_settings
        ... )
        >>> print(f"Processed {count} spectra")
    """
    logger.info(f"Starting preferred identification selection (criterion: {criterion})")
    logger.debug(f"Ion settings: {ion_settings}")
    logger.debug(f"Tool settings: {tool_settings}")
    
    # TODO: Implement logic
    # For now, return 0 as placeholder
    logger.warning("select_preferred_identifications is not yet implemented")
    return 0
```

Также создать `api/peptides/__init__.py`:
```python
"""Peptide identification and matching."""
```

## 4. Обновления в существующих файлах

### `api/inputs/proteins/__init__.py`
Создать новую директорию и файл:
```python
"""Protein data parsers."""
```

### `api/spectra/plot_matches.py`
Убедиться, что функция `plot_ion_match` существует и имеет правильную сигнатуру. Если функции нет, создать заглушку:

```python
"""Ion match visualization."""

import plotly.graph_objects as go
import numpy as np


def plot_ion_match(
    mz_array: np.ndarray,
    intensity_array: np.ndarray,
    sequence: str,
    charge: int,
    ion_types: list[str],
    water_loss: bool = False,
    nh3_loss: bool = False,
    ppm_threshold: float = 20.0
) -> go.Figure:
    """
    Plot ion match visualization for a spectrum and sequence.
    
    Args:
        mz_array: m/z values
        intensity_array: Intensity values
        sequence: Peptide sequence
        charge: Precursor charge
        ion_types: List of ion types to match (e.g., ['b', 'y'])
        water_loss: Include water loss ions
        nh3_loss: Include ammonia loss ions
        ppm_threshold: PPM threshold for matching
    
    Returns:
        Plotly Figure object
    
    TODO: Implement full visualization with:
    - Spectrum as bar chart
    - Matched ions highlighted
    - Annotations for matched peaks
    - Legend
    """
    # Placeholder implementation
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=mz_array,
        y=intensity_array,
        name='Spectrum',
        marker_color='lightgray'
    ))
    
    fig.update_layout(
        title=f"Ion Match: {sequence}",
        xaxis_title="m/z",
        yaxis_title="Intensity",
        height=400
    )
    
    return fig
```

## 5. План тестирования

### Ручное тестирование

1. **Загрузка FASTA:**
   - Выбрать и загрузить валидный FASTA файл
   - Проверить отображение статуса
   - Проверить запись в БД через SQL запрос
   - Протестировать с UniProt и обычными форматами

2. **Настройки инструментов:**
   - Проверить загрузку существующих настроек
   - Изменить значения и убедиться в валидации
   - Проверить сохранение через функцию пересчёта

3. **Настройки ионов:**
   - Выбрать разные комбинации типов ионов
   - Проверить сохранение в project_settings
   - Проверить загрузку при повторном открытии

4. **Поиск идентификаций:**
   - Поиск по seq_no, scans, sequence
   - Фильтрация по sample и tool
   - Проверить корректность результатов

5. **Просмотр графиков:**
   - Выбрать идентификацию и проверить отображение графика
   - Проверить автоматическое отображение первого результата

6. **Обработка ошибок:**
   - Протестировать все сценарии с ошибками
   - Проверить сообщения в SnackBar

### Интеграционное тестирование

Создать тестовый файл `test_stage3_3.py`:

```python
"""Integration tests for Stage 3.3: Peptides tab."""

import pytest
from pathlib import Path
from api.project.project import Project
from api.inputs.proteins.fasta import FastaParser


@pytest.mark.asyncio
async def test_fasta_parser():
    """Test FASTA parser basic functionality."""
    # Test with sample FASTA file
    test_file = Path("TEST_DATA/test.fasta")
    
    parser = FastaParser(str(test_file), is_uniprot=True)
    
    # Validate
    is_valid = await parser.validate()
    assert is_valid, "FASTA file should be valid"
    
    # Parse
    proteins = []
    async for batch in parser.parse_batch(batch_size=10):
        proteins.extend(batch.to_dict('records'))
    
    assert len(proteins) > 0, "Should parse proteins"
    assert 'id' in proteins[0], "Should have id field"
    assert 'sequence' in proteins[0], "Should have sequence field"


@pytest.mark.asyncio
async def test_project_protein_storage():
    """Test storing proteins in project."""
    async with Project(path=None) as project:
        # Parse FASTA
        test_file = Path("TEST_DATA/test.fasta")
        parser = FastaParser(str(test_file))
        
        # Import to project
        async for batch in parser.parse_batch():
            await project.add_proteins_batch(batch)
        
        # Verify
        proteins = await project.get_proteins()
        assert len(proteins) > 0, "Should store proteins"


@pytest.mark.asyncio
async def test_tool_settings():
    """Test tool settings storage and retrieval."""
    async with Project(path=None) as project:
        # Add tool
        tool = await project.add_tool("TestTool", "test_parser")
        
        # Update settings
        tool.settings = {
            'max_ppm': 50.0,
            'min_score': 0.8,
            'min_ion_intensity_coverage': 25.0
        }
        await project.update_tool(tool)
        
        # Retrieve
        loaded_tool = await project.get_tool(tool.id)
        assert loaded_tool.settings['max_ppm'] == 50.0
        assert loaded_tool.settings['min_score'] == 0.8


@pytest.mark.asyncio
async def test_ion_settings():
    """Test ion matching settings storage."""
    async with Project(path=None) as project:
        # Save settings
        await project.set_setting('ion_types', 'b,y')
        await project.set_setting('water_loss', '1')
        await project.set_setting('ion_ppm_threshold', '20')
        
        # Retrieve
        ion_types = await project.get_setting('ion_types')
        assert ion_types == 'b,y'
        
        water_loss = await project.get_setting('water_loss')
        assert water_loss == '1'
```

## 6. Документация

### Пользовательская документация (обновить после реализации)

Добавить в `docs/USER_GUIDE.md` секцию:

```markdown
## Peptides Tab

The Peptides tab provides tools for managing peptide identifications and selecting optimal matches.

### Loading Protein Sequences

1. Click "Browse" to select a FASTA file
2. Configure options:
   - "Sequences in UniProt format": Check if file contains UniProt-formatted headers
   - "Enrich data from UniProt": Enable to fetch additional data from UniProt
3. Click "Load Sequences"

### Configuring Tool Settings

For each identification tool, configure:
- **Max PPM**: Maximum allowed mass error
- **Min Score**: Minimum identification score threshold
- **Min Ion Intensity Coverage**: Minimum percentage of spectrum covered by matched ions
- **Use protein identification from file**: Use protein assignments from identification file
- **Min Protein Identity**: Minimum sequence identity for protein matching
- **DeNovo seq correction**: Enable de novo sequence correction

### Ion Matching Settings

Configure which ion types to use for matching:
- Select ion types (a, b, c, x, y, z)
- Enable neutral losses (water, ammonia)
- Set PPM threshold for ion matching

### Running Identification Matching

1. Configure all settings
2. Select criterion: PPM error or Intensity coverage
3. Click "Run Identification Matching"

### Searching Identifications

1. Filter by Sample and/or Tool
2. Choose search field (Sequence Number, Scans, Sequence)
3. Enter search value
4. Click "Search" or press Enter
5. View results in table
6. Click "View" icon to see ion match visualization
```

## 7. Итоговый чеклист

### API компоненты
- [ ] `api/inputs/proteins/__init__.py`
- [ ] `api/inputs/proteins/fasta.py` - FastaParser
- [ ] `api/peptides/__init__.py`
- [ ] `api/peptides/matching.py` - select_preferred_identifications (заглушка)
- [ ] `api/spectra/plot_matches.py` - убедиться в наличии plot_ion_match

### GUI компоненты
- [ ] `gui/views/tabs/peptides_tab.py` - полная переработка
  - [ ] Блок загрузки FASTA
  - [ ] Блок настроек инструментов
  - [ ] Блок настроек ионов
  - [ ] Блок выбора оптимальной идентификации
  - [ ] Блок поиска и просмотра идентификаций

### Тестирование
- [ ] `test_stage3_3.py` - интеграционные тесты
- [ ] Ручное тестирование всех компонентов UI
- [ ] Тестирование с реальными данными

### Документация
- [ ] Обновить `docs/USER_GUIDE.md`
- [ ] Обновить технические комментарии в коде

## 8. Зависимости и требования

### Python пакеты
- Все необходимые пакеты уже присутствуют в `pyproject.toml`:
  - flet (UI)
  - pandas (данные)
  - plotly (графики)
  - aiosqlite (БД)

### Тестовые данные
- Создать `TEST_DATA/test.fasta` с примерами белковых последовательностей
- Использовать существующие MGF и идентификационные файлы

## 9. Этапы реализации

1. **Этап 1: Парсер FASTA**
   - Создать структуру директорий
   - Реализовать FastaParser
   - Протестировать парсинг

2. **Этап 2: UI Блоки 1-3**
   - Загрузка FASTA
   - Настройки инструментов
   - Настройки ионов
   - Интеграция с Project API

3. **Этап 3: UI Блок 4**
   - Выбор оптимальной идентификации
   - Создание заглушки функции matching

4. **Этап 4: UI Блок 5**
   - Поиск идентификаций
   - Просмотр графиков
   - Интеграция plot_matches

5. **Этап 5: Тестирование и отладка**
   - Интеграционные тесты
   - Ручное тестирование
   - Исправление багов

6. **Этап 6: Документация**
   - Обновление пользовательской документации
   - Финализация комментариев

## 10. Известные ограничения

1. **Обогащение UniProt**: Базовая заглушка, полная реализация в будущих этапах
2. **Интерактивные графики**: Используем статические изображения, pywebview интеграция в этапе 5
3. **Функция matching**: Заглушка для разработчика, полная логика будет реализована отдельно
4. **Повторная загрузка FASTA**: Не поддерживается на этом этапе

## 11. Примечания для разработчика

- Следовать стилю кода из `samples_tab.py`
- Использовать async/await для всех операций с БД
- Валидировать все пользовательские вводы
- Предоставлять информативные сообщения об ошибках
- Логировать важные операции через `utils.logger`
- Комментировать сложные участки кода
- Использовать type hints
