# STAGE 12 SPEC: ReportForm — типизированные формы параметров отчётов; UpSet Plot отчёт

## Резюме задачи

Два связанных блока:

1. **ReportForm** — замена "костыля" с `TextArea` для ввода параметров. Новый механизм: класс `ReportForm` принимает декларативно описанные виджеты-обёртки, рендерится в `ft.Container` для кнопки "Parameters", сериализует/десериализует значения в JSON для хранения в проекте. `BaseReport` обновляется: `get_parameter_defaults()` заменяется на атрибут `parameters: ReportForm | None`. `ReportItem` в GUI переключается с `TextArea` на кнопку "Parameters" → диалог.

2. **UpsetReport** — реализация отчёта UpSet Plot на основе кода из `volcanizer/create_upset.py`. Источник данных — `protein_identification_result`, джойн с `sample` и `subset`. К графику прилагается таблица белков для каждого пересечения. Параметр отчёта — выбор групп сравнения через `MultiSubsetSelector`. Все существующие отчёты адаптируются под новую `ReportForm`.

---

## 1. Компонент ReportForm

### 1.1 Файл: `dasmixer/gui/components/report_form.py`

#### 1.1.1 Базовый класс параметра `ReportParamBase`

```python
class ReportParamBase:
    """Abstract base for a single report parameter widget."""
    
    def __init__(self, label: str | None = None, default=None):
        self.label = label   # Если None — используется имя атрибута
        self.default = default
        self._attr_name: str | None = None  # Устанавливается ReportFormMeta
        self._control: ft.Control | None = None  # Создаётся в build()
    
    def build(self, project: Project) -> ft.Control:
        """Build flet control. Called once when form is created."""
        raise NotImplementedError
    
    def get_value(self):
        """Return current value in Python native type."""
        raise NotImplementedError
    
    def set_value(self, value):
        """Restore value from stored data."""
        raise NotImplementedError
```

#### 1.1.2 Конкретные классы параметров

| Класс | Виджет Flet | Возвращаемый тип | Особенности |
|---|---|---|---|
| `ToolSelector` | `ft.Dropdown` | `str` (tool.name) | Опции: список `tool.name` из проекта |
| `EnumSelector` | `ft.Dropdown` | `str` | `values: list[str]` передаётся в конструктор |
| `BoolSelector` | `ft.Checkbox` | `bool` | `default: bool = False` |
| `FloatSelector` | `ft.TextField` | `float` | Числовая валидация |
| `IntSelector` | `ft.TextField` | `int` | Числовая валидация |
| `SubsetSelector` | `ft.Dropdown` | `str` (subset.name) | Опции: список `subset.name` из проекта |
| `MultiSubsetSelector` | N `ft.Checkbox` | `list[str]` | По одному чекбоксу на каждую группу; `ft.Column` с чекбоксами |
| `StringSelector` | `ft.TextField` | `str` | Однострочный ввод |

Все классы наследуют `ReportParamBase`.

`ToolSelector`, `SubsetSelector`, `MultiSubsetSelector` требуют доступа к проекту для заполнения опций — получают его через аргумент `build(project)`.

#### 1.1.3 Метакласс и базовый класс `ReportForm`

Используется подход дескриптора/метакласса для сбора всех полей типа `ReportParamBase` при объявлении класса:

```python
class ReportFormMeta(type):
    """Metaclass: collects ReportParamBase fields into _fields dict."""
    def __new__(mcs, name, bases, namespace):
        fields = {}
        for key, val in namespace.items():
            if isinstance(val, ReportParamBase):
                val._attr_name = key
                if val.label is None:
                    val.label = key.replace('_', ' ').title()
                fields[key] = val
        namespace['_fields'] = fields
        return super().__new__(mcs, name, bases, namespace)


class ReportForm(metaclass=ReportFormMeta):
    """
    Base class for typed report parameter forms.
    
    Usage:
        class MyForm(ReportForm):
            tool = ToolSelector()
            threshold = FloatSelector(default=0.05)
            use_correction = BoolSelector(default=True)
    """
    
    _fields: dict[str, ReportParamBase]  # Заполняется метаклассом
    
    def __init__(self, project: Project):
        self.project = project
        self._built = False
    
    async def build(self) -> None:
        """Build all controls (must be called before get_container)."""
        for field in self._fields.values():
            field._control = await field.build(self.project)
        self._built = True
    
    def get_container(self) -> ft.Container:
        """Return ft.Container with all controls laid out vertically."""
        if not self._built:
            raise RuntimeError("Call build() before get_container()")
        controls = []
        for field in self._fields.values():
            controls.append(ft.Text(field.label, size=12, color=ft.Colors.GREY_700))
            controls.append(field._control)
        return ft.Container(
            content=ft.Column(controls, spacing=8),
            padding=10
        )
    
    def get_values(self) -> dict:
        """Return dict of current values keyed by field name."""
        return {name: field.get_value() for name, field in self._fields.items()}
    
    def set_values(self, values: dict) -> None:
        """Restore values from stored dict."""
        for name, val in values.items():
            if name in self._fields:
                self._fields[name].set_value(val)
    
    def to_json(self) -> str:
        """Serialize current values to JSON string."""
        import json
        return json.dumps(self.get_values())
    
    @classmethod
    def from_json(cls, json_str: str, project: Project) -> 'ReportForm':
        """Deserialize values and apply to new form instance."""
        import json
        instance = cls(project)
        instance.set_values(json.loads(json_str))
        return instance
```

### 1.2 Асинхронность build()

`ToolSelector.build()` и `SubsetSelector.build()` и `MultiSubsetSelector.build()` выполняют `await project.get_tools()` / `await project.get_subsets()`. Поэтому `build()` в `ReportForm` — корутина (`async def`).

---

## 2. Изменения в `BaseReport`

### 2.1 Файл: `dasmixer/api/reporting/base.py`

**Изменение 1**: Атрибут класса вместо `get_parameter_defaults()`:

```python
# Было:
@staticmethod
def get_parameter_defaults() -> dict[str, tuple[type, str]]:
    return {}

# Станет:
parameters: type[ReportForm] | None = None  # Класс формы (не экземпляр)
```

**Изменение 2**: Метод `_validate_parameters` остаётся для обратной совместимости, но при наличии `parameters` вызывается `form.get_values()` вместо парсинга текста. `generate()` получает `params: dict` как сейчас — ничего менять в сигнатуре не нужно.

**Изменение 3**: `_generate_impl` не меняется. Параметры по-прежнему передаются как `dict`.

**Совместимость**: `get_parameter_defaults()` остаётся как статический метод с `return {}` по умолчанию. Если `parameters is None`, поведение не меняется. Старый код в `SampleReport`, `ToolMatchReport`, `VolcanoReport` будет заменён формами.

---

## 3. Изменения в `ReportMixin` (Project)

### 3.1 Файл: `dasmixer/api/project/mixins/report_mixin.py`

Изменить сигнатуру `save_report_parameters` и `get_report_parameters` — принимать/возвращать строку (JSON или любую строку). Логика не меняется — просто хранится `TEXT` в SQLite. Форма сама делает `json.dumps` / `json.loads`.

Никаких новых методов в Mixin не добавляется.

---

## 4. Изменения в `ReportItem` (GUI)

### 4.1 Файл: `dasmixer/gui/views/tabs/reports/report_item.py`

**Текущее состояние**: Есть `self.params_field = ft.TextField(multiline=True, ...)` — "костыль".

**Новое поведение**:

- Если `report_class.parameters is not None` (т.е. класс имеет ReportForm):
  - Вместо `params_field` — кнопка `ft.ElevatedButton("Parameters", icon=ft.Icons.SETTINGS, on_click=self._on_open_params)`
  - По клику — открывается `ft.AlertDialog` с `ft.Container` от `form.get_container()`
  - Диалог содержит кнопки "OK" и "Cancel"
  - При "OK" — значения сохраняются в `self._form_values: dict`
  - `_on_generate` вызывает `form.get_values()` как `params`
- Если `report_class.parameters is None` — оставить `params_field` как есть (TextArea)

**Хранение**: При генерации отчёта — `await self.project.save_report_parameters(name, form.to_json())`. При загрузке — `form = cls.from_json(saved_json, project)` перед показом.

**Инициализация формы**: Форма создаётся как экземпляр в `_on_open_params` (lazy) или при `load_data()`:

```python
async def _init_form(self):
    if self.report_class.parameters is not None:
        self._form = self.report_class.parameters(self.project)
        await self._form.build()
        # Восстановить сохранённые значения если есть
        saved = await self.project.get_report_parameters(self.report_class.name)
        if saved:
            try:
                self._form.set_values(json.loads(saved))
            except Exception:
                pass
```

---

## 5. Адаптация существующих отчётов

### 5.1 `SampleReport`

**Файл**: `dasmixer/api/reporting/reports/sample_report.py`

Текущие параметры: `max_samples: int = 10`, `include_table: str = 'Y'`, `chart_type: str = 'bar'`

Новая форма:

```python
class SampleReportForm(ReportForm):
    max_samples = IntSelector(default=10, label="Max samples")
    include_table = BoolSelector(default=True, label="Include table")
    chart_type = EnumSelector(values=["bar", "scatter"], label="Chart type")
```

В `_generate_impl` адаптировать: `params['include_table']` теперь `bool`, `params['chart_type']` — `str`.

Убрать `get_parameter_defaults()`, добавить `parameters = SampleReportForm`.

### 5.2 `ToolMatchReport`

**Файл**: `dasmixer/api/reporting/reports/toolmatch_report.py`

Текущие параметры: `tool1: str = 'Library'`, `tool2: str = 'Denovo'`, `min_psm: int = 1`

Новая форма:

```python
class ToolMatchReportForm(ReportForm):
    tool1 = ToolSelector(label="Tool 1 (Library)")
    tool2 = ToolSelector(label="Tool 2 (De Novo)")
    min_psm = IntSelector(default=1, label="Min PSM count")
```

### 5.3 `VolcanoReport`

**Файл**: `dasmixer/api/reporting/reports/volcano_report.py`

Текущие параметры: `control_subset`, `exptl_subsets`, `lfq_type`, `stats_method`, `fdc`, `percent_to_caculate`, `fc_threshold`, `p_threshold`

Новая форма:

```python
class VolcanoReportForm(ReportForm):
    control_subset = SubsetSelector(label="Control subset")
    exptl_subsets = MultiSubsetSelector(label="Experimental subsets")
    lfq_type = EnumSelector(values=["emPAI", "iBAQ", "NSAF", "Top3"], label="LFQ method")
    stats_method = EnumSelector(values=["Mann-Whitney", "T-test"], label="Statistical method")
    fdc = EnumSelector(values=["BH", "BY", "Bonferroni"], label="FDR correction")
    percent_to_calculate = IntSelector(default=20, label="Min % samples with value")
    fc_threshold = FloatSelector(default=1.5, label="FC threshold")
    p_threshold = FloatSelector(default=0.05, label="p-value threshold")
```

В `_generate_impl` адаптировать: `exptl_subsets` теперь `list[str]` (а не строка через запятую).

---

## 6. UpSet Plot отчёт

### 6.1 Данные

**Источник**: `protein_identification_result` + `sample` + `subset`

Запрос строится через `execute_query_df` в `_generate_impl` UpsetReport. Новых методов в Project/Mixin не добавляется — используется прямой SQL-запрос через `self.project.execute_query_df()`.

SQL-запрос (выполняется внутри `UpsetReport._generate_impl`):

```sql
SELECT
    pir.protein_id AS uniprot_id,
    s.name AS sample,
    sb.name AS subset
FROM protein_identification_result pir
JOIN sample s ON pir.sample_id = s.id
JOIN subset sb ON s.subset_id = sb.id
WHERE sb.name IN (...)   -- фильтр по выбранным subsets
```

Если subsets не выбраны (форма не заполнена) — берутся все.

### 6.2 Логика построения графика

Функции `place_to_groups`, `get_subset_sample_counts`, `plot_upset` переносятся из `volcanizer/create_upset.py` в `dasmixer/api/reporting/reports/upset.py` без принципиальных изменений.

Изменения в `plot_upset`:
- Убрать хардкоденный `range=[0.5, 12.5]` на оси X — заменить на динамический диапазон по количеству комбинаций.
- Убрать шаблон `template` как модульный объект; применить настройки через `_apply_settings_to_figure` в `BaseReport`.

### 6.3 Таблица белков по пересечениям

Функция `place_to_groups` возвращает DataFrame с колонками: `protein`, `<subset1>`, `<subset2>`, ..., `name`, `count`. Это — статистика по пересечениям.

Дополнительно генерируется таблица `intersection_proteins`:

```python
def get_intersection_proteins(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each non-empty intersection, list proteins belonging to it.
    
    Returns DataFrame with columns:
        - intersection: str (e.g. "Control_Treatment")
        - protein_id: str
    """
```

Логика: для каждой строки из `place_to_groups` (где count > 0) — запросить белки, попавшие именно в это пересечение (аналогично `filtered` в `place_to_groups`, но вернуть список белков).

Таблицы в отчёте:
- `("Intersection Summary", summary_df, True)` — статистика пересечений (count по каждой комбинации)
- `("Proteins by Intersection", intersection_proteins_df, True)` — список белков

### 6.4 Форма параметров UpsetReport

```python
class UpsetReportForm(ReportForm):
    subsets = MultiSubsetSelector(label="Subsets to include")
```

### 6.5 Класс UpsetReport

```python
class UpsetReport(BaseReport):
    name = "Upset Plot"
    description = "Upset plot for protein identifications across comparison groups"
    icon = Icons.INSERT_CHART_ROUNDED
    parameters = UpsetReportForm

    async def _generate_impl(
        self,
        params: dict
    ) -> tuple[list[tuple[str, go.Figure]], list[tuple[str, pd.DataFrame, bool]]]:
        selected_subsets = params['subsets']  # list[str]
        
        # SQL-запрос
        df = await self._get_upset_data(selected_subsets)
        
        # Построение графика
        fig = plot_upset(df)
        
        # Таблицы
        summary_df = place_to_groups(df)
        intersection_df = get_intersection_proteins(df)
        
        return (
            [("Upset Plot", fig)],
            [
                ("Intersection Summary", summary_df[['name', 'count']], True),
                ("Proteins by Intersection", intersection_df, True),
            ]
        )
    
    async def _get_upset_data(self, subsets: list[str]) -> pd.DataFrame:
        if subsets:
            placeholders = ','.join('?' * len(subsets))
            query = f"""
                SELECT pir.protein_id AS uniprot_id, s.name AS sample, sb.name AS subset
                FROM protein_identification_result pir
                JOIN sample s ON pir.sample_id = s.id
                JOIN subset sb ON s.subset_id = sb.id
                WHERE sb.name IN ({placeholders})
            """
            return await self.project.execute_query_df(query, tuple(subsets))
        else:
            query = """
                SELECT pir.protein_id AS uniprot_id, s.name AS sample, sb.name AS subset
                FROM protein_identification_result pir
                JOIN sample s ON pir.sample_id = s.id
                JOIN subset sb ON s.subset_id = sb.id
            """
            return await self.project.execute_query_df(query)
```

---

## 7. Итоговый перечень изменяемых файлов

| Файл | Тип изменения | Описание |
|---|---|---|
| `dasmixer/gui/components/report_form.py` | **Новый** | `ReportParamBase`, все классы параметров, `ReportFormMeta`, `ReportForm` |
| `dasmixer/gui/components/__init__.py` | Изменение | Экспорт новых классов |
| `dasmixer/api/reporting/base.py` | Изменение | `parameters: type[ReportForm] | None = None`; совместимость с `get_parameter_defaults()` |
| `dasmixer/api/reporting/reports/sample_report.py` | Изменение | `SampleReportForm` + адаптация `_generate_impl` |
| `dasmixer/api/reporting/reports/toolmatch_report.py` | Изменение | `ToolMatchReportForm` + адаптация `_generate_impl` |
| `dasmixer/api/reporting/reports/volcano_report.py` | Изменение | `VolcanoReportForm` + адаптация `_generate_impl` (exptl_subsets как list) |
| `dasmixer/api/reporting/reports/upset.py` | Изменение (реализация) | Перенос логики из volcanizer; `UpsetReportForm`; `UpsetReport._generate_impl` |
| `dasmixer/gui/views/tabs/reports/report_item.py` | Изменение | Кнопка Parameters + диалог вместо TextArea для отчётов с формой |

Файлы `project.py`, `report_mixin.py`, `schema.py` — **не изменяются**. Новых методов в Mixin и Project не добавляется.

---

## 8. Открытые вопросы / решения

1. **Порядок subsets в MultiSubsetSelector**: отображаются в алфавитном порядке (как возвращает `get_subsets()`).
2. **Пустой UpSet Plot**: если `protein_identification_result` пустой — `_generate_impl` бросает `ValueError` с читаемым сообщением.
3. **Форма для SampleReport**: `SampleReport` — демонстрационный отчёт, тем не менее переводится на форму для полноты.
4. **Сохранение формы при перестройке**: при пересоздании диалога значения восстанавливаются из `self._form_values`, не из проекта (проект используется только при `load_data`).
5. **Имя атрибута vs label**: если `label` не задан — используется `attr_name.replace('_', ' ').title()`.
