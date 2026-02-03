# Спецификация этапа 4.1 - ASC (Analytical Sample Calculation)

**Дата:** 2026-02-03  
**Версия:** 1.0  
**Статус:** Планирование

---

## 1. Обзор

Этап 4.1 включает доработки функционала работы с пептидными идентификациями, необходимые для дальнейшей интеграции белковой идентификации и построения отчетов. Основные задачи:

1. Создание универсального метода получения объединенных данных пептидов с фильтрацией
2. Финализация просмотра графиков спектров с интерактивным режимом  
3. Упрощение логики кнопок на вкладке Peptides
4. Расширенное управление параметрами инструментов (мин/макс длина пептида)
5. Расширение структуры БД для белков (name, uniprot_data)
6. Изменение структуры таблицы tool (разделение type и parser)

---

## 2. Универсальное представление данных

### 2.1 Метод `Project.get_joined_peptide_data()`

**Назначение:** Получение объединенных данных спектров, идентификаций и матчей белков с возможностью фильтрации.

**Сигнатура:**
```python
async def get_joined_peptide_data(
    self,
    is_preferred: bool | None = None,
    sequence_identified: bool | None = None,
    protein_identified: bool | None = None,
    sample: str | None = None,
    subset: str | None = None,
    sample_id: int | None = None,
    subset_id: int | None = None,
    sequence: str | None = None,
    canonical_sequence: str | None = None,
    matched_sequence: str | None = None,
    seq_no: int | None = None,
    scans: int | None = None,
    tool: str | None = None,
    tool_id: int | None = None
) -> pd.DataFrame
```

**SQL запрос (базовый):**
```sql
SELECT
    sb.sample, sb.subset, sb.sample_id, sb.subset_id,
    s.seq_no, s.scans, s.charge, s.rt, s.pepmass, s.intensity,
    id.tool, id.tool_id, id.identification_id, id.sequence, 
    id.canonical_sequence, id.ppm, id.is_preferred,
    mp.matched_sequence, mp.matched_ppm, mp.protein_id, 
    mp.unique_evidence, mp.gene
FROM
    spectre AS s
LEFT JOIN
    (SELECT 
        sm.id AS sample_id, 
        f.id AS spectre_file_id, 
        sm.name AS sample, 
        sb.name AS subset, 
        sb.id AS subset_id 
     FROM sample sm, subset sb, spectre_file f 
     WHERE sm.subset_id = sb.id AND f.sample_id = sm.id) AS sb
    ON sb.spectre_file_id = s.spectre_file_id
LEFT JOIN
    (SELECT 
        i.spectre_id, 
        t.name AS tool, 
        t.id AS tool_id, 
        i.id AS identification_id, 
        i.sequence, 
        i.canonical_sequence, 
        i.ppm, 
        i.is_preferred 
     FROM identification i, tool t 
     WHERE t.id = i.tool_id) AS id 
    ON id.spectre_id = s.id
LEFT JOIN
    (SELECT 
        m.matched_sequence, 
        m.matched_ppm, 
        m.protein_id, 
        m.identification_id, 
        m.unique_evidence, 
        p.gene
     FROM peptide_match m, protein p 
     WHERE p.id = m.protein_id) AS mp 
    ON mp.identification_id = id.identification_id
WHERE 1=1
```

**Фильтры (динамически добавляются в WHERE):**
- `is_preferred` → `AND id.is_preferred = 1`
- `sequence_identified` → `AND id.sequence IS NOT NULL`
- `protein_identified` → `AND mp.protein_id IS NOT NULL`
- `sample` → `AND sb.sample = ?`
- `sequence` → `AND id.sequence LIKE ?` (с `%value%`)
- `seq_no` → `AND s.seq_no = ?`
- И т.д.

**Местоположение:** `api/project/project.py`

---

## 3. Финализация просмотра графиков спектров

### 3.1 Новый метод `Project.get_spectrum_plot_data()`

**Назначение:** Получение всех данных для отрисовки графика спектра со всеми идентификациями.

**Сигнатура:**
```python
async def get_spectrum_plot_data(self, spectrum_id: int) -> dict:
    """
    Returns dict with keys:
        - mz: list[float]
        - intensity: list[float]
        - charges: list[int] | int
        - sequences: list[str]
        - headers: list[str]
        - spectrum_info: dict (seq_no, scans, rt, pepmass, charge)
    """
```

**Логика:**
1. Получить спектр (mz_array, intensity_array, charge_array/charge)
2. Получить все идентификации для спектра (JOIN с tool)
3. Сформировать headers: `"{tool_name} | Score: {score:.2f} | PPM: {ppm:.2f}"`
4. Вернуть словарь для распаковки через `**`

**Местоположение:** `api/project/project.py`

### 3.2 Интеграция в GUI

**Изменения в `view_identification()`:**

```python
async def view_identification(self, e, ident_row: dict):
    # 1. Get spectrum data
    plot_data = await self.project.get_spectrum_plot_data(ident_row['spectre_id'])
    
    # 2. Get ion matching parameters from settings
    params = IonMatchParameters(
        ions=ion_types,  # from project_settings
        tolerance=ppm_threshold,
        mode='largest',
        water_loss=water_loss,
        ammonia_loss=nh3_loss
    )
    
    # 3. Create plot
    fig = make_full_spectrum_plot(
        params=params,
        **plot_data
    )
    
    # 4. Display with PlotlyViewer
    viewer = PlotlyViewer(
        figure=fig,
        width=1000,
        height=600,
        title=f"Spectrum {plot_data['spectrum_info']['seq_no']}",
        show_interactive_button=True
    )
    
    self.plot_container.content = viewer
    self.plot_container.update()
```

**Местоположение:** `gui/views/tabs/peptides_tab.py`

---

## 4. Изменения в логике работы кнопок

### 4.1 Новый блок "Actions"

**Структура:**
- Кнопка "Calculate Peptides" (основная)
- `ft.ExpansionPanel` с заголовком "Advanced Options" (свернут)
  - Calculate Ion Coverage
  - Calculate PPM and Coverage for Proteins
  - Run Identification Matching
  - Match Proteins to Identifications

### 4.2 Кнопка "Load Sequences"

**Дополнение:** Показывать количество белков в БД

```python
self.protein_count_text = ft.Text("", size=11, color=ft.Colors.GREY_600)

# Сразу после инициализации проекта
protein_count = await self.project.get_protein_count()
self.protein_count_text.value = f"({protein_count:,} proteins in database)"
# и не забыть про update()
```

**Метод в Project:**
```python
async def get_protein_count(self) -> int:
    query = "SELECT COUNT(*) as count FROM protein"
    result = await self.execute_query_df(query)
    return int(result.iloc[0]['count'])
```

### 4.3 Последовательность "Calculate Peptides"

```python
async def calculate_peptides(self, e):
    # 1. Match proteins to identifications
    await self.match_proteins_to_identifications(None)
    
    # 2. Calculate Ion coverage (only missing)
    await self._run_coverage_calc(recalc_all=False)
    
    # 3. Calculate PPM and coverage for protein identifications
    await self.calculate_protein_match_metrics(None)
    
    # 4. Run identification matching
    await self.run_identification_matching(None)
```

---

## 5. Расширенное управление инструментами

### 5.1 Новые параметры в Tool Settings

**Для каждого инструмента:**

```python
'min_peptide_length': ft.TextField(
    label="Min Peptide Length",
    value=str(settings.get('min_peptide_length', 7)),
    width=150
)
'max_peptide_length': ft.TextField(
    label="Max Peptide Length",
    value=str(settings.get('max_peptide_length', 30)),
    width=150
)
```

**Сохранение в `tool.settings` (JSON):**
```json
{
  "min_peptide_length": 7,
  "max_peptide_length": 30,
  ...
}
```

### 5.2 Интеграция в `select_preferred_identifications()`

**В `api/peptides/matching.py`:**

```python
min_len = tool_params.get("min_peptide_length", 7)
max_len = tool_params.get("max_peptide_length", 30)

idents['canonical_length'] = idents['canonical_sequence'].str.len()

query = (
    "ppm <= @max_ppm and "
    "score >= @min_score and "
    "intensity_coverage >= @min_ion_intensity_coverage and "
    "canonical_length >= @min_len and "
    "canonical_length <= @max_len"
)
```

---

## 6. Расширение данных о белках

### 6.1 Миграция схемы БД

!!!!! БД в Project - это файл проекта. Она не является постоянной, миграции не нужны. Нужно чтобы при инициализации нового проекта создавалась таблица с новыми полями. Никаких ALTER нигде

**Описание:**
- `name`: Краткое название белка (заполнение - позже)
- `uniprot_data`: pickle + gzip объекта `UniprotData`

### 6.2 Обновление моделей

**В `api/project/models.py`:**

```python
from dataclasses import dataclass
import pickle
import gzip
from uniprot_meta_tool import UniprotData

@dataclass
class Protein:
    id: str
    is_uniprot: bool
    fasta_name: str
    sequence: str
    gene: str | None = None
    name: str | None = None  # NEW
    uniprot_data: UniprotData | None = None  # NEW

```
!!!!!!! Запаковка/распаковка должна происходить в Project при чтении/записи из БД, не надо эту логику тянуть в dataclass.

---

## 7. Изменение структуры таблицы tool

### 7.1 Миграция схемы БД

**Текущая структура:**
- `type` → имя парсера

**Новая структура:**
- `type` → "Library" или "De Novo"
- `parser` → имя парсера (было `type`)

Миграции не требуются, БД после правок для тестирования будет пересоздана. Проследи чтобы везде, где используется tool.type использовался tool.parser
```

### 7.2 Обновление моделей

```python
@dataclass
class Tool:
    id: int
    name: str
    type: Literal['Library', 'De Novo']  # NEW
    parser: str  # RENAMED from 'type'
    settings: dict | None = None
    display_color: str | None = None
```

### 7.3 Обновление GUI

**Диалог создания tool:**

```python
# Type selector
self.tool_type_group = ft.RadioGroup(
    content=ft.Column([
        ft.Radio(value="Library", label="Library Search"),
        ft.Radio(value="De Novo", label="De Novo Sequencing")
    ]),
    value="Library"
)

# Parser dropdown
self.tool_parser_dropdown = ft.Dropdown(
    label="Parser",
    options=[
        ft.dropdown.Option(key="PowerNovo2", text="PowerNovo 2"),
        ft.dropdown.Option(key="MaxQuant", text="MaxQuant"),
        # ...
    ]
)
```

---

## 8. План реализации

### 8.1 Последовательность задач

**1. Миграция БД и обновление моделей**
- Добавить поля в `protein` и `tool`
- Обновить dataclasses
- Обновить методы CRUD

**2. Универсальное представление данных**
- Реализовать `get_joined_peptide_data()`

**3. Метод получения данных спектра**
- Реализовать `get_spectrum_plot_data()`

**4. Расширенное управление инструментами**
- Добавить min/max length в UI
- Интегрировать в matching

**5. Изменения в логике кнопок**
- Создать блок Actions
- Реализовать `calculate_peptides()`

**6. Финализация просмотра графиков**
- Обновить search и view методы
- Интегрировать PlotlyViewer

**7. Обновление UI создания инструментов**
- Добавить Type/Parser селекторы

### 8.2 Тестирование

!!! Вручную после полной реализации

---

## 9. Зависимости

**Новые импорты:**

`api/project/models.py`:
```python
import pickle
import gzip
from typing import Literal
```

`gui/views/tabs/peptides_tab.py`:
```python
from api.spectra.plot_flow import make_full_spectrum_plot
from api.spectra.ion_match import IonMatchParameters
from gui.components.plotly_viewer import PlotlyViewer
```

---

## 10. Риски

1. **Производительность** `get_joined_peptide_data()` - сложный JOIN
   - Митигация: индексы на ключевые поля
!!! Должны быть индексы на foreign key, в целом должно хватить.

2. **Размер графиков** при множественных идентификациях
   - Митигация: ограничить топ-5
Пока игнорируем 

3. **Обратная совместимость** после миграции БД
   - Митигация: версионирование схемы
!!!!!!СЕЙЧАС ОБРАТНАЯ СОВМЕСТИМОСТЬ НЕ ВАЖНА, ПРОЕКТ ЕЩЁ НА РАННЕЙ СТАДИИ РАЗРАБОТКИ!!!!!!!

---

**Конец спецификации**
