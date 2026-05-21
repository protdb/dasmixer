# Спецификация Stage 6: Универсальные модули отображения таблиц и графиков

**Дата:** 2026-02-16  
**Этап:** Stage 6  
**Статус:** Спецификация  

---

## Оглавление

1. [Обзор](#обзор)
2. [Цели и задачи](#цели-и-задачи)
3. [Архитектура базовых классов](#архитектура-базовых-классов)
4. [Таблица saved_plots в БД](#таблица-saved_plots-в-бд)
5. [Вкладка Plots](#вкладка-plots)
6. [Реализация для вкладки Peptides](#реализация-для-вкладки-peptides)
7. [Реализация для вкладки Proteins](#реализация-для-вкладки-proteins)
8. [Интеграция с приложением](#интеграция-с-приложением)
9. [План разработки](#план-разработки)
10. [Файловая структура](#файловая-структура)
11. [Критерии приёмки](#критерии-приёмки)

---

## Обзор

На данном этапе реализуется универсальная система отображения таблиц и графиков в пользовательском интерфейсе DASMixer.

### Ключевые особенности

- **Базовые классы** для таблиц, графиков и их комбинации
- **Паджинация** таблиц с фильтрацией на уровне SQL
- **Сохранение графиков** в проекте с возможностью управления
- **Экспорт** графиков в PNG/SVG и Word
- **Новая вкладка Plots** для управления сохранёнными графиками
- **Переработка существующих представлений** на вкладках Peptides и Proteins

Система должна быть универсальной и легко расширяемой для добавления новых типов таблиц и графиков.

---

## Цели и задачи

### Основные цели

1. Создать универсальные базовые классы для таблиц и графиков
2. Реализовать паджинацию и фильтрацию таблиц
3. Добавить функционал сохранения графиков в проект
4. Создать вкладку для управления сохранёнными графиками
5. Переработать существующие представления Peptides и Proteins
6. Реализовать экспорт графиков

### Функциональные требования

- Таблицы отображаются постранично с настраиваемым размером страницы (25/50/100/200)
- Фильтрация выполняется на уровне SQL запросов с использованием LIMIT и OFFSET
- Графики строятся по данным из таблицы (передаётся только entity_id)
- Графики можно сохранять в проект и экспортировать
- Настройки графиков и фильтры таблиц сохраняются в настройках проекта
- Все операции неблокирующие (async)
- Применение настроек и построение графиков только по кнопке (не реактивно)

---

## Архитектура базовых классов

### 1. BasePlotView

**Расположение:** `gui/components/base_plot_view.py`

**Назначение:** Базовый класс для всех представлений графиков.

**Структура:**
- Container с заголовком и ExpansionPanelList внутри
- Два ExpansionPanel: "Plot Settings" и "Plot Preview"
- Кнопки: "Save to Project" и "Export..."

**Атрибуты класса для переопределения:**
```python
plot_type_name: str = "base_plot"  # Уникальный идентификатор типа графика
```

**Методы для переопределения в наследниках:**
```python
def get_default_settings(self) -> dict:
    """Возвращает словарь настроек по умолчанию"""
    pass

def _build_plot_settings_view(self) -> ft.Control:
    """Строит UI для настроек графика"""
    pass

async def generate_plot(self, entity_id: str) -> go.Figure:
    """Генерирует график по ID сущности"""
    pass
```

**Публичный интерфейс:**
```python
async def on_plot_requested(self, entity_id: str):
    """Колбэк из таблицы для построения графика"""
    pass

async def load_data(self):
    """Загружает настройки из проекта"""
    pass
```

**Внутренние методы:**
```python
async def _update_settings_from_ui(self):
    """Читает значения из UI и обновляет self.plot_settings"""
    pass

async def _save_settings_to_project(self):
    """Сохраняет настройки в project settings"""
    # Ключи: plot_view_{plot_type_name}_{parameter_name}
    pass

async def _load_settings_from_project(self):
    """Загружает настройки из project settings"""
    pass

async def _apply_global_settings(self, fig: go.Figure) -> go.Figure:
    """Применяет глобальные настройки (font_size, width, height)"""
    pass

async def _display_plot(self, fig: go.Figure):
    """Отображает график через PlotlyViewer"""
    pass

async def _save_to_project(self, e):
    """Сохраняет график в таблицу saved_plots"""
    pass

async def _export_dialog(self, e):
    """Показывает диалог экспорта с настройками"""
    pass
```

**Формат plot_settings:**
```python
self.plot_settings: dict = {
    'parameter1': value1,
    'parameter2': value2,
    # ... определяется в get_default_settings()
}
```

---

### 2. BaseTableView

**Расположение:** `gui/components/base_table_view.py`

**Назначение:** Базовый класс для всех табличных представлений с паджинацией и фильтрацией.

**Структура:**
- Container с заголовком и ExpansionPanelList
- Два ExpansionPanel: "Filters" и "Data"
- Кнопка "Apply Filters" в панели фильтров
- DataTable с паджинацией внизу

**Атрибуты класса для переопределения:**
```python
table_view_name: str = "base_table"  # Уникальный идентификатор таблицы
plot_id_field: Optional[str] = None  # Название колонки с ID для графика (если None - нет кнопки графика)
```

**Методы для переопределения в наследниках:**
```python
def get_default_filters(self) -> dict:
    """Возвращает словарь фильтров по умолчанию"""
    pass

def _build_filter_view(self) -> ft.Control:
    """Строит UI для фильтров"""
    pass

async def get_data(self, limit: int = 100, offset: int = 0) -> pd.DataFrame:
    """Получает отфильтрованные данные из БД"""
    # Должен читать self.filter и применять в SQL
    pass

async def get_total_count(self) -> int:
    """Возвращает общее количество строк с учётом фильтров"""
    pass
```

**Публичный интерфейс:**
```python
def __init__(
    self,
    project: Project,
    title: str = "Table",
    plot_callback: Optional[Callable[[str], None]] = None
):
    """
    Args:
        plot_callback: async def callback(entity_id: str) для построения графика
    """
    pass

async def load_data(self):
    """Загружает данные и обновляет таблицу"""
    pass
```

**Паджинация:**
- Элементы управления:
  - Text: "Showing X-Y of Z rows (Page N of M)"
  - Dropdown: размер страницы (25/50/100/200)
  - IconButton: Prev (arrow_back)
  - IconButton: Next (arrow_forward)
- Состояние:
  ```python
  self.current_page = 0
  self.page_size = 50
  self.total_rows = 0
  ```

**Формат filter:**
```python
self.filter: dict = {
    'filter_param1': value1,
    'filter_param2': value2,
    # ... определяется в get_default_filters()
}
```

---

### 3. BaseTableAndPlotView

**Расположение:** `gui/components/base_table_and_plot_view.py`

**Назначение:** Объединяет таблицу и график в одном представлении.

**Структура:**
```python
class BaseTableAndPlotView(ft.Container):
    def __init__(
        self,
        project: Project,
        table_view: BaseTableView,
        plot_view: BasePlotView,
        title: str = "Data & Plot"
    ):
        # Устанавливает table_view.plot_callback = plot_view.on_plot_requested
        # Компонует layout: title, table, divider, plot
        pass
    
    async def load_data(self):
        """Загружает данные для таблицы и графика"""
        await self.table_view.load_data()
        await self.plot_view.load_data()
```

**Layout:**
```
Column:
  - Title (Text)
  - Container (spacing)
  - table_view
  - Container (spacing)
  - Divider
  - Container (spacing)
  - plot_view
```

---

## Таблица saved_plots в БД

### Схема таблицы

**SQL:**
```sql
CREATE TABLE IF NOT EXISTS saved_plots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    plot_type TEXT NOT NULL,
    settings TEXT,
    plot BLOB
);
```

**Поля:**
- `id` - автоинкрементный первичный ключ
- `created_at` - ISO timestamp (datetime.now().isoformat())
- `plot_type` - тип графика (значение из plot_type_name)
- `settings` - JSON строка с параметрами:
  ```json
  {
    "entity_id": "protein_123",
    "plot_settings": {
      "algorithm": "emPAI",
      "plot_type": "boxplot",
      "show_title": true
    }
  }
  ```
- `plot` - gzipped pickle сериализованного go.Figure

### Методы в PlotMixin

**Расположение:** `api/project/mixins/plot_mixin.py`

```python
import json
import gzip
import pickle
import pandas as pd
from datetime import datetime


class PlotMixin:
    """Mixin для работы с сохранёнными графиками."""
    
    async def get_saved_plots(self) -> list[dict]:
        """
        Получить список всех сохранённых графиков.
        
        Returns:
            list[dict]: [
                {
                    'id': int,
                    'created_at': str,
                    'plot_type': str,
                    'settings': dict
                },
                ...
            ]
        """
        rows = await self._fetchall(
            "SELECT id, created_at, plot_type, settings FROM saved_plots ORDER BY created_at DESC"
        )
        
        result = []
        for row in rows:
            settings = json.loads(row['settings']) if row['settings'] else {}
            result.append({
                'id': row['id'],
                'created_at': row['created_at'],
                'plot_type': row['plot_type'],
                'settings': settings
            })
        
        return result
    
    async def load_saved_plot(self, plot_id: int):
        """
        Загрузить график из БД.
        
        Args:
            plot_id: ID в таблице saved_plots
            
        Returns:
            go.Figure: Десериализованный график
            
        Raises:
            ValueError: Если график не найден
        """
        row = await self._fetchone("SELECT plot FROM saved_plots WHERE id = ?", (plot_id,))
        
        if not row or not row['plot']:
            raise ValueError(f"Plot with id={plot_id} not found")
        
        fig = pickle.loads(gzip.decompress(row['plot']))
        return fig
    
    async def delete_saved_plot(self, plot_id: int):
        """
        Удалить сохранённый график.
        
        Args:
            plot_id: ID в таблице saved_plots
        """
        await self._execute("DELETE FROM saved_plots WHERE id = ?", (plot_id,))
        await self.save()
```

### Миграция БД

**Расположение:** `api/project/models.py`

Добавить в список таблиц для создания:

```python
TABLES = {
    # ... existing tables ...
    
    'saved_plots': """
        CREATE TABLE IF NOT EXISTS saved_plots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            plot_type TEXT NOT NULL,
            settings TEXT,
            plot BLOB
        )
    """
}
```

---

## Вкладка Plots

### PlotsTab

**Расположение:** `gui/views/tabs/plots/plots_tab.py`

**Назначение:** Управление сохранёнными графиками.

**Функциональность:**
- Отображение списка сохранённых графиков
- Просмотр графика в диалоге
- Удаление графика (с подтверждением)
- Экспорт выделенных графиков в Word

**Компоненты:**

```python
class PlotItemCard(ft.Container):
    """Карточка одного сохранённого графика."""
    
    def __init__(self, plot_info: dict, on_view, on_delete, on_select):
        # plot_info: {'id': int, 'created_at': str, 'plot_type': str, 'settings': dict}
        # Layout: Row[Checkbox, Column[Title, Info], IconButton(View), IconButton(Delete)]
        pass


class PlotsTab(ft.Container):
    """Вкладка управления графиками."""
    
    def __init__(self, project: Project):
        # Header: Row[Title, Spacer, Button(Export Selected), Button(Refresh)]
        # Body: ListView с PlotItemCard
        pass
    
    async def load_data(self, e=None):
        """Загрузить список графиков из проекта"""
        self.plot_items = await self.project.get_saved_plots()
        # Создать PlotItemCard для каждого
        pass
    
    async def _view_plot(self, plot_id: int):
        """Просмотр графика в диалоге с PlotlyViewer"""
        fig = await self.project.load_saved_plot(plot_id)
        # Показать AlertDialog с PlotlyViewer
        pass
    
    async def _delete_plot(self, plot_id: int):
        """Удалить график (с подтверждением)"""
        # Показать AlertDialog с подтверждением
        # При подтверждении: await self.project.delete_saved_plot(plot_id)
        pass
    
    async def _export_selected(self, e):
        """Экспорт выделенных графиков в Word"""
        # Получить selected plot_ids
        # Выбрать директорию через FilePicker
        # Вызвать _export_plots_to_word()
        pass
    
    async def _export_plots_to_word(self, plot_ids: list[int], output_dir: Path):
        """Экспорт в Word через html4docx"""
        # Загрузить фигуры и метаданные
        # Рендерить HTML через Jinja2
        # Создать Word документ
        # Resize images
        pass
```

### HTML Template для экспорта

**Расположение:** `gui/views/tabs/plots/templates/plots_export.html.j2`

```jinja2
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>DASMixer - Saved Plots Export</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        .plot-section { page-break-after: always; margin-bottom: 30px; }
        .plot-header { background-color: #f0f0f0; padding: 10px; margin-bottom: 10px; }
        .plot-header h2 { margin: 0; color: #555; }
        .plot-info { font-size: 12px; color: #777; }
        .plot-image { text-align: center; margin: 20px 0; }
        .plot-image img { max-width: 100%; border: 1px solid #ddd; }
        .plot-settings { margin-top: 15px; }
        .plot-settings h3 { font-size: 14px; color: #555; margin-bottom: 5px; }
        table { width: 100%; border-collapse: collapse; font-size: 11px; }
        table th, table td { border: 1px solid #ddd; padding: 6px; text-align: left; }
        table th { background-color: #f5f5f5; font-weight: bold; }
    </style>
</head>
<body>
    <h1>DASMixer - Saved Plots</h1>
    
    {% for plot in plots %}
    <div class="plot-section">
        <div class="plot-header">
            <h2>Plot #{{ plot.id }}: {{ plot.plot_type }}</h2>
            <div class="plot-info">Created: {{ plot.created_at }}</div>
        </div>
        
        <div class="plot-image">
            <img src="data:image/png;base64,{{ plot.png_base64 }}" alt="Plot {{ plot.id }}">
        </div>
        
        <div class="plot-settings">
            <h3>Plot Settings</h3>
            <table>
                <tr><th>Parameter</th><th>Value</th></tr>
                {% for key, value in plot.settings.items() %}
                <tr><td>{{ key }}</td><td>{{ value }}</td></tr>
                {% endfor %}
            </table>
        </div>
    </div>
    {% endfor %}
</body>
</html>
```

---

## Реализация для вкладки Peptides

### 1. PeptideIonPlotView

**Расположение:** `gui/views/tabs/peptides/peptide_ion_plot_view.py`

**Назначение:** График покрытия b/y ионами для пептида.

**Реализация:**

```python
"""Plot view for peptide ion coverage (b/y ions)."""

import flet as ft
import plotly.graph_objects as go

from gui.components.base_plot_view import BasePlotView
from api.project.project import Project
from api.calculations.spectra.plot_flow import make_full_spectrum_plot
from api.calculations.spectra.ion_match import IonMatchParameters


class PeptideIonPlotView(BasePlotView):
    """График покрытия b/y ионами."""

    plot_type_name = "peptide_ion_coverage"

    def __init__(self, project: Project, ion_settings_section):
        """
        Args:
            ion_settings_section: Ссылка на IonSettingsSection для получения параметров
        """
        self.ion_settings_section = ion_settings_section
        super().__init__(project, title="Ion Match Plot")

    def get_default_settings(self) -> dict:
        return {
            'show_title': True,
            'show_legend': True
        }

    def _build_plot_settings_view(self) -> ft.Control:
        self.show_title_checkbox = ft.Checkbox(
            label="Show title",
            value=self.plot_settings.get('show_title', True)
        )

        self.show_legend_checkbox = ft.Checkbox(
            label="Show legend",
            value=self.plot_settings.get('show_legend', True)
        )

        return ft.Column([
            ft.Text("Plot Display Options:", weight=ft.FontWeight.BOLD),
            self.show_title_checkbox,
            self.show_legend_checkbox,
            ft.Container(height=5),
            ft.Text(
                "Note: Ion matching parameters are controlled in Ion Settings section.",
                size=11,
                italic=True,
                color=ft.Colors.GREY_600
            )
        ], spacing=5)

    async def _update_settings_from_ui(self):
        self.plot_settings['show_title'] = self.show_title_checkbox.value
        self.plot_settings['show_legend'] = self.show_legend_checkbox.value

    async def generate_plot(self, entity_id: str) -> go.Figure:
        """
        Args:
            entity_id: spectrum_id (строка)
        """
        spectrum_id = int(entity_id)

        # Получить данные спектра
        plot_data = await self.project.get_spectrum_plot_data(spectrum_id)

        # Получить параметры из IonSettingsSection
        params = self.ion_settings_section.get_ion_match_parameters()

        # Построить график
        fig = make_full_spectrum_plot(params=params, **plot_data)

        # Применить настройки
        if not self.plot_settings.get('show_title', True):
            fig.update_layout(title=None)

        if not self.plot_settings.get('show_legend', True):
            fig.update_layout(showlegend=False)

        return fig
```

---

### 2. PeptideIonTableView

**Расположение:** `gui/views/tabs/peptides/peptide_ion_table_view.py`

**Назначение:** Таблица идентификаций пептидов с фильтрацией.

**Фильтры:**
- Sample (dropdown)
- Tool (dropdown)
- Min Score (number)
- Max PPM (number)
- Sequence contains (text)
- Canonical sequence contains (text)

**Реализация:**

```python
"""Table view for peptide identifications."""

import flet as ft
import pandas as pd

from gui.components.base_table_view import BaseTableView
from api.project.project import Project


class PeptideIonTableView(BaseTableView):
    """Таблица идентификаций пептидов."""
    
    table_view_name = "peptide_identifications"
    plot_id_field = "spectre_id"
    
    def __init__(self, project: Project, plot_callback=None):
        super().__init__(project, title="Peptide Identifications", plot_callback=plot_callback)
    
    def get_default_filters(self) -> dict:
        return {
            'sample_id': 'all',
            'tool_id': 'all',
            'min_score': 0.0,
            'max_ppm': 1000.0,
            'sequence': '',
            'canonical_sequence': ''
        }
    
    def _build_filter_view(self) -> ft.Control:
        self.sample_dropdown = ft.Dropdown(
            label="Sample",
            options=[ft.dropdown.Option(key="all", text="All Samples")],
            value="all",
            width=200
        )
        
        self.tool_dropdown = ft.Dropdown(
            label="Tool",
            options=[ft.dropdown.Option(key="all", text="All Tools")],
            value="all",
            width=200
        )
        
        self.min_score_field = ft.TextField(
            label="Min Score",
            value="0",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        self.max_ppm_field = ft.TextField(
            label="Max PPM",
            value="1000",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        self.sequence_field = ft.TextField(
            label="Sequence contains",
            value="",
            width=200
        )
        
        self.canonical_sequence_field = ft.TextField(
            label="Canonical sequence contains",
            value="",
            width=200
        )
        
        return ft.Column([
            ft.Row([self.sample_dropdown, self.tool_dropdown], spacing=10),
            ft.Row([self.min_score_field, self.max_ppm_field], spacing=10),
            ft.Row([self.sequence_field, self.canonical_sequence_field], spacing=10)
        ], spacing=10)
    
    async def _update_filters_from_ui(self):
        self.filter['sample_id'] = self.sample_dropdown.value
        self.filter['tool_id'] = self.tool_dropdown.value
        self.filter['min_score'] = float(self.min_score_field.value or 0)
        self.filter['max_ppm'] = float(self.max_ppm_field.value or 1000)
        self.filter['sequence'] = self.sequence_field.value
        self.filter['canonical_sequence'] = self.canonical_sequence_field.value
    
    async def load_data(self):
        await self._load_filter_options()
        await super().load_data()
    
    async def _load_filter_options(self):
        """Загрузить опции для dropdown'ов"""
        samples = await self.project.get_samples()
        self.sample_dropdown.options = [
            ft.dropdown.Option(key="all", text="All Samples")
        ] + [
            ft.dropdown.Option(key=str(s.id), text=s.name)
            for s in samples
        ]
        
        tools = await self.project.get_tools()
        self.tool_dropdown.options = [
            ft.dropdown.Option(key="all", text="All Tools")
        ] + [
            ft.dropdown.Option(key=str(t.id), text=t.name)
            for t in tools
        ]
        
        if self.page:
            self.sample_dropdown.update()
            self.tool_dropdown.update()
    
    async def get_data(self, limit: int = 100, offset: int = 0) -> pd.DataFrame:
        """Получить данные с фильтрацией"""
        filter_params = {}
        
        if self.filter['sample_id'] != 'all':
            filter_params['sample_id'] = int(self.filter['sample_id'])
        
        if self.filter['tool_id'] != 'all':
            filter_params['tool_id'] = int(self.filter['tool_id'])
        
        if self.filter['min_score'] > 0:
            filter_params['min_score'] = self.filter['min_score']
        
        if self.filter['max_ppm'] < 1000:
            filter_params['max_ppm'] = self.filter['max_ppm']
        
        if self.filter['sequence']:
            filter_params['sequence'] = self.filter['sequence']
        
        if self.filter['canonical_sequence']:
            filter_params['canonical_sequence'] = self.filter['canonical_sequence']
        
        filter_params['limit'] = limit
        filter_params['offset'] = offset
        
        df = await self.project.get_joined_peptide_data(**filter_params)
        
        # Выбрать колонки для отображения
        display_columns = ['seq_no', 'sample', 'tool', 'sequence', 'score', 'ppm', 'is_preferred', 'spectre_id']
        display_columns = [col for col in display_columns if col in df.columns]
        
        return df[display_columns]
    
    async def get_total_count(self) -> int:
        """Получить общее количество строк"""
        # Построить WHERE clause
        where_parts = []
        params = []
        
        if self.filter['sample_id'] != 'all':
            where_parts.append("s.id = ?")
            params.append(int(self.filter['sample_id']))
        
        if self.filter['tool_id'] != 'all':
            where_parts.append("t.id = ?")
            params.append(int(self.filter['tool_id']))
        
        if self.filter['min_score'] > 0:
            where_parts.append("pi.score >= ?")
            params.append(self.filter['min_score'])
        
        if self.filter['max_ppm'] < 1000:
            where_parts.append("ABS(pm.ppm) <= ?")
            params.append(self.filter['max_ppm'])
        
        if self.filter['sequence']:
            where_parts.append("pi.sequence LIKE ?")
            params.append(f"%{self.filter['sequence']}%")
        
        if self.filter['canonical_sequence']:
            where_parts.append("pm.canonical_sequence LIKE ?")
            params.append(f"%{self.filter['canonical_sequence']}%")
        
        where_clause = " AND ".join(where_parts) if where_parts else "1=1"
        
        query = f"""
        SELECT COUNT(*) as cnt
        FROM peptide_identification pi
        JOIN spectre sp ON pi.spectre_id = sp.id
        JOIN sample s ON sp.sample_id = s.id
        JOIN tool t ON pi.tool_id = t.id
        LEFT JOIN peptide_match pm ON pi.id = pm.peptide_identification_id
        WHERE {where_clause}
        """
        
        row = await self.project._fetchone(query, tuple(params))
        return row['cnt'] if row else 0
```

---

### 3. Интеграция в PeptidesTab

**Изменения в:** `gui/views/tabs/peptides/peptides_tab_new.py`

```python
from gui.components.base_table_and_plot_view import BaseTableAndPlotView
from .peptide_ion_table_view import PeptideIonTableView
from .peptide_ion_plot_view import PeptideIonPlotView

class PeptidesTab(ft.Container):
    def _create_sections(self) -> dict:
        sections = {}
        
        # ... existing sections (fasta, tool_settings, ion_settings, actions, matching) ...
        
        # ЗАМЕНИТЬ SearchSection на BaseTableAndPlotView
        table_view = PeptideIonTableView(self.project)
        plot_view = PeptideIonPlotView(self.project, ion_settings_section=sections['ion_settings'])
        
        sections['search'] = BaseTableAndPlotView(
            project=self.project,
            table_view=table_view,
            plot_view=plot_view,
            title="Search and View Identifications"
        )
        
        return sections
```

---

## Реализация для вкладки Proteins

### 1. ProteinConcentrationPlotView

**Расположение:** `gui/views/tabs/proteins/protein_concentration_plot_view.py`

**Назначение:** Boxplot/Violin plot концентраций белка по группам.

**Настройки:**
- Algorithm: emPAI/iBAQ/NSAF/Top3
- Plot Type: Boxplot/Violin
- Include Title: checkbox
- Remove Outliers: checkbox
- Outlier Range: number (MAD multiplier)
- Show All Dots: checkbox
- Subsets: checkboxes для выбора групп

**Реализация (укороченная):**

```python
"""Plot view for protein concentrations."""

import flet as ft
import plotly.graph_objects as go
import numpy as np

from gui.components.base_plot_view import BasePlotView
from api.project.project import Project


class ProteinConcentrationPlotView(BasePlotView):
    """График концентраций белка."""
    
    plot_type_name = "protein_concentration"
    
    def __init__(self, project: Project):
        super().__init__(project, title="Protein Concentration Plot")
        self.available_subsets = []
    
    def get_default_settings(self) -> dict:
        return {
            'algorithm': 'emPAI',
            'plot_type': 'boxplot',
            'include_title': True,
            'remove_outliers': False,
            'outlier_range': 3.0,
            'show_all_dots': False,
            'selected_subsets': []
        }
    
    def _build_plot_settings_view(self) -> ft.Control:
        # Dropdowns, checkboxes, text fields
        # Кнопка "Refresh Subsets" для загрузки списка групп
        pass
    
    async def _load_subsets(self, e=None):
        """Загрузить доступные группы и построить checkboxes"""
        subsets = await self.project.get_subsets()
        self.available_subsets = [s.name for s in subsets]
        # Создать checkboxes
        pass
    
    async def generate_plot(self, entity_id: str) -> go.Figure:
        """
        Args:
            entity_id: protein_id
        """
        protein_id = entity_id
        algorithm = self.plot_settings.get('algorithm', 'emPAI')
        
        # Получить данные квантификации
        df = await self.project.get_protein_quantification_data(protein_id=protein_id)
        
        if len(df) == 0:
            raise ValueError(f"No quantification data for {protein_id}")
        
        # Фильтровать по выбранным группам
        selected_subsets = self.plot_settings.get('selected_subsets', [])
        if selected_subsets:
            df = df[df['subset'].isin(selected_subsets)]
        
        # Удалить аутлаеры если нужно
        if self.plot_settings.get('remove_outliers', False):
            outlier_range = self.plot_settings.get('outlier_range', 3.0)
            df = self._remove_outliers(df, algorithm, outlier_range)
        
        # Получить цвета групп
        subset_colors = await self._get_subset_colors()
        
        # Построить график
        fig = go.Figure()
        plot_type = self.plot_settings.get('plot_type', 'boxplot')
        
        for subset_name in df['subset'].unique():
            subset_df = df[df['subset'] == subset_name]
            color = subset_colors.get(subset_name, '#888888')
            
            if plot_type == 'boxplot':
                fig.add_trace(go.Box(
                    y=subset_df[algorithm],
                    name=subset_name,
                    marker_color=color,
                    boxmean='sd'
                ))
            else:  # violin
                fig.add_trace(go.Violin(
                    y=subset_df[algorithm],
                    name=subset_name,
                    marker_color=color,
                    box_visible=True,
                    meanline_visible=True
                ))
        
        # Добавить точки если нужно
        if self.plot_settings.get('show_all_dots', False):
            for subset_name in df['subset'].unique():
                subset_df = df[df['subset'] == subset_name]
                color = subset_colors.get(subset_name, '#888888')
                
                fig.add_trace(go.Scatter(
                    y=subset_df[algorithm],
                    x=[subset_name] * len(subset_df),
                    mode='markers',
                    marker=dict(size=4, color=color, opacity=0.5),
                    showlegend=False,
                    hoverinfo='y'
                ))
        
        # Layout
        title = f"Protein {protein_id} - {algorithm}" if self.plot_settings.get('include_title', True) else None
        fig.update_layout(
            title=title,
            yaxis_title=f"{algorithm} Concentration",
            xaxis_title="Subset"
        )
        
        return fig
    
    def _remove_outliers(self, df, column, mad_multiplier):
        """Удалить аутлаеры методом MAD"""
        values = df[column].values
        median = np.median(values)
        mad = np.median(np.abs(values - median))
        
        lower_bound = median - mad_multiplier * mad
        upper_bound = median + mad_multiplier * mad
        
        return df[(df[column] >= lower_bound) & (df[column] <= upper_bound)]
    
    async def _get_subset_colors(self) -> dict:
        """Получить цвета групп из БД"""
        subsets = await self.project.get_subsets()
        return {s.name: s.color or '#888888' for s in subsets}
```

---

### 2. ProteinStatisticsTableView и ProteinIdentificationsTableView

**Два режима таблицы:**

1. **Identifications** - детальный режим (существующий функционал)
2. **Statistics** - агрегированный режим (новый)

**Структура Statistics:**

Колонки:
- protein_id
- gene
- fasta_name (урезано до 30 символов)
- samples (количество образцов)
- subsets (количество групп)
- PSMs (количество идентификаций пептидов)
- unique (количество уникальных)

Фильтры:
- Protein ID contains
- Gene contains
- FASTA name contains
- Min Samples (число)
- Min Subsets (число)

**Реализация ProteinStatisticsTableView:**

```python
"""Table view for protein statistics (aggregated)."""

import flet as ft
import pandas as pd

from gui.components.base_table_view import BaseTableView
from api.project.project import Project


class ProteinStatisticsTableView(BaseTableView):
    """Агрегированная статистика по белкам."""
    
    table_view_name = "protein_statistics"
    plot_id_field = "protein_id"
    
    def get_default_filters(self) -> dict:
        return {
            'protein_id': '',
            'gene': '',
            'fasta_name': '',
            'min_samples': 0,
            'min_subsets': 0
        }
    
    def _build_filter_view(self) -> ft.Control:
        # Text fields для protein_id, gene, fasta_name
        # Number fields для min_samples, min_subsets
        pass
    
    async def get_data(self, limit: int = 100, offset: int = 0) -> pd.DataFrame:
        # Использовать новый метод get_protein_statistics()
        df = await self.project.get_protein_statistics(
            protein_id=self.filter['protein_id'],
            gene=self.filter['gene'],
            fasta_name=self.filter['fasta_name'],
            min_samples=self.filter['min_samples'],
            min_subsets=self.filter['min_subsets'],
            limit=limit,
            offset=offset
        )
        return df
    
    async def get_total_count(self) -> int:
        # Получить без limit
        df = await self.project.get_protein_statistics(
            protein_id=self.filter['protein_id'],
            gene=self.filter['gene'],
            fasta_name=self.filter['fasta_name'],
            min_samples=self.filter['min_samples'],
            min_subsets=self.filter['min_subsets'],
            limit=999999,
            offset=0
        )
        return len(df)
```

**Реализация ProteinIdentificationsTableView:**

Аналогично, но использует `get_protein_results_joined()` с фильтрацией.

---

### 3. Новые методы в Project

**В `api/project/mixins/protein_mixin.py`:**

#### get_protein_statistics()

```python
async def get_protein_statistics(
    self,
    protein_id: str = '',
    gene: str = '',
    fasta_name: str = '',
    min_samples: int = 0,
    min_subsets: int = 0,
    limit: int = 100,
    offset: int = 0
) -> pd.DataFrame:
    """
    Получить агрегированную статистику по белкам.
    
    Returns:
        DataFrame с колонками: protein_id, gene, fasta_name, samples, subsets, PSMs, unique
    """
    where_parts = ["1=1"]
    params = []
    
    if protein_id:
        where_parts.append("p.protein_id LIKE ?")
        params.append(f"%{protein_id}%")
    
    if gene:
        where_parts.append("p.gene LIKE ?")
        params.append(f"%{gene}%")
    
    if fasta_name:
        where_parts.append("p.fasta_name LIKE ?")
        params.append(f"%{fasta_name}%")
    
    where_clause = " AND ".join(where_parts)
    
    query = f"""
    WITH protein_stats AS (
        SELECT
            p.protein_id,
            p.gene,
            SUBSTR(p.fasta_name, 1, 30) as fasta_name,
            COUNT(DISTINCT s.id) as samples,
            COUNT(DISTINCT ss.id) as subsets,
            COUNT(pm.id) as PSMs,
            SUM(CASE WHEN pm.unique_evidence = 1 THEN 1 ELSE 0 END) as unique
        FROM protein p
        LEFT JOIN protein_identification_result pir ON p.id = pir.protein_id
        LEFT JOIN sample s ON pir.sample_id = s.id
        LEFT JOIN subset ss ON s.subset_id = ss.id
        LEFT JOIN peptide_match pm ON p.id = pm.protein_id
        WHERE {where_clause}
        GROUP BY p.id, p.protein_id, p.gene, p.fasta_name
    )
    SELECT * FROM protein_stats
    WHERE samples >= ? AND subsets >= ?
    ORDER BY protein_id
    LIMIT ? OFFSET ?
    """
    
    params.extend([min_samples, min_subsets, limit, offset])
    
    df = await self.execute_query_df(query, tuple(params))
    return df
```

#### Расширение get_protein_quantification_data()

Добавить параметр `protein_id`:

```python
async def get_protein_quantification_data(
    self,
    sample_id: Optional[int] = None,
    protein_id: Optional[str] = None  # НОВЫЙ ПАРАМЕТР
) -> pd.DataFrame:
    """
    Получить данные квантификации белков.
    
    Args:
        sample_id: Фильтр по образцу (опционально)
        protein_id: Фильтр по белку (опционально)  # НОВЫЙ
    """
    where_parts = ["1=1"]
    params = []
    
    if sample_id:
        where_parts.append("s.id = ?")
        params.append(sample_id)
    
    if protein_id:  # НОВЫЙ
        where_parts.append("p.protein_id = ?")
        params.append(protein_id)
    
    where_clause = " AND ".join(where_parts)
    
    query = f"""
    SELECT
        s.name as sample,
        ss.name as subset,
        p.protein_id,
        pqr.EmPAI,
        pqr.iBAQ,
        pqr.NSAF,
        pqr.Top3
    FROM protein_quantification_result pqr
    JOIN protein p ON pqr.protein_id = p.id
    JOIN sample s ON pqr.sample_id = s.id
    LEFT JOIN subset ss ON s.subset_id = ss.id
    WHERE {where_clause}
    ORDER BY p.protein_id, s.name
    """
    
    df = await self.execute_query_df(query, tuple(params))
    return df
```

---

### 4. Интеграция в ProteinsTab с переключением

**В `gui/views/tabs/proteins/proteins_tab.py`:**

```python
from gui.components.base_table_and_plot_view import BaseTableAndPlotView
from .protein_identifications_table_view import ProteinIdentificationsTableView
from .protein_statistics_table_view import ProteinStatisticsTableView
from .protein_concentration_plot_view import ProteinConcentrationPlotView

class ProteinsTab(ft.Container):
    def _create_sections(self) -> dict:
        sections = {}
        
        # ... existing sections (detection, lfq) ...
        
        # НОВАЯ СЕКЦИЯ с переключением режимов
        sections['table_and_plot'] = self._create_table_and_plot_section()
        
        return sections
    
    def _create_table_and_plot_section(self) -> ft.Container:
        """Создать секцию таблицы и графика с переключением режимов."""
        
        # Создать оба представления таблицы
        self.identifications_table = ProteinIdentificationsTableView(self.project)
        self.statistics_table = ProteinStatisticsTableView(self.project)
        
        # Создать представление графика
        self.protein_plot = ProteinConcentrationPlotView(self.project)
        
        # Подключить callbacks
        self.identifications_table.plot_callback = self.protein_plot.on_plot_requested
        self.statistics_table.plot_callback = self.protein_plot.on_plot_requested
        
        # SegmentedButton для переключения режимов
        self.table_mode_selector = ft.SegmentedButton(
            segments=[
                ft.Segment(
                    value="identifications",
                    label=ft.Text("Identifications"),
                    icon=ft.Icon(ft.Icons.LIST)
                ),
                ft.Segment(
                    value="statistics",
                    label=ft.Text("Statistics"),
                    icon=ft.Icon(ft.Icons.ANALYTICS)
                )
            ],
            selected={"identifications"},
            on_change=self._on_table_mode_change
        )
        
        # Контейнер для активной таблицы
        self.active_table_container = ft.Container(
            content=self.identifications_table,
            expand=True
        )
        
        # Layout
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Protein Results", size=18, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    self.table_mode_selector
                ]),
                ft.Container(height=10),
                self.active_table_container,
                ft.Container(height=20),
                ft.Divider(),
                ft.Container(height=20),
                self.protein_plot
            ], spacing=0, expand=True, scroll=ft.ScrollMode.AUTO),
            expand=True,
            padding=10
        )
    
    def _on_table_mode_change(self, e):
        """Обработка переключения режима таблицы."""
        selected_mode = list(e.control.selected)[0]
        
        if selected_mode == "identifications":
            self.active_table_container.content = self.identifications_table
        else:
            self.active_table_container.content = self.statistics_table
        
        self.page.update()
        
        # Загрузить данные для нового режима
        self.page.run_task(self.active_table_container.content.load_data)
```

---

## Интеграция с приложением

### 1. Добавление вкладки Plots в главное меню

**В `gui/app.py`:**

```python
from gui.views.tabs.plots.plots_tab import PlotsTab

class DASMixerApp:
    def _build_project_view(self):
        """Построить представление проекта с вкладками."""
        
        # ... existing tabs ...
        
        # НОВАЯ ВКЛАДКА
        plots_tab = PlotsTab(self.project)
        
        tabs = ft.Tabs(
            selected_index=0,
            tabs=[
                ft.Tab(text="Samples", icon=ft.Icons.DATASET, content=samples_tab),
                ft.Tab(text="Peptides", icon=ft.Icons.BIOTECH, content=peptides_tab),
                ft.Tab(text="Proteins", icon=ft.Icons.SCIENCE, content=proteins_tab),
                ft.Tab(text="Reports", icon=ft.Icons.ASSESSMENT, content=reports_tab),
                ft.Tab(text="Plots", icon=ft.Icons.SHOW_CHART, content=plots_tab),  # НОВАЯ
            ],
            expand=True
        )
        
        return tabs
```

### 2. Миграция БД при запуске

Таблица `saved_plots` создаётся автоматически через `models.py` при инициализации проекта.

---

## План разработки

### Фаза 1: Базовые компоненты (2-3 дня)

**День 1:**
1. Создать `gui/components/base_plot_view.py`
2. Создать `gui/components/base_table_view.py`
3. Создать `gui/components/base_table_and_plot_view.py`

**День 2:**
4. Добавить таблицу `saved_plots` в `api/project/models.py`
5. Создать `api/project/mixins/plot_mixin.py`
6. Добавить PlotMixin в Project

**День 3:**
7. Тестирование базовых компонентов
8. Исправление багов

### Фаза 2: Вкладка Plots (1 день)

**День 4:**
1. Создать `gui/views/tabs/plots/plots_tab.py`
2. Создать `gui/views/tabs/plots/templates/plots_export.html.j2`
3. Интегрировать в главное меню приложения
4. Тестирование

### Фаза 3: Вкладка Peptides (2 дня)

**День 5:**
1. Создать `gui/views/tabs/peptides/peptide_ion_plot_view.py`
2. Создать `gui/views/tabs/peptides/peptide_ion_table_view.py`

**День 6:**
3. Интегрировать в `PeptidesTab`
4. Тестирование
5. Исправление багов

### Фаза 4: Вкладка Proteins (2-3 дня)

**День 7:**
1. Создать `gui/views/tabs/proteins/protein_concentration_plot_view.py`
2. Создать `gui/views/tabs/proteins/protein_statistics_table_view.py`

**День 8:**
3. Создать `gui/views/tabs/proteins/protein_identifications_table_view.py`
4. Добавить `get_protein_statistics()` в `ProteinMixin`
5. Расширить `get_protein_quantification_data()`

**День 9:**
6. Интегрировать в `ProteinsTab` с SegmentedButton
7. Тестирование
8. Исправление багов

### Фаза 5: Документация (1 день)

**День 10:**
1. Обновить пользовательскую документацию
2. Обновить техническую документацию
3. Создать changelog
4. Финальное тестирование

**Общая оценка: 8-10 дней разработки**

---

## Файловая структура

```
gui/
  components/
    base_plot_view.py              # Базовый класс для графиков
    base_table_view.py             # Базовый класс для таблиц
    base_table_and_plot_view.py    # Комбинированный класс
    plotly_viewer.py               # Существующий (без изменений)
  
  views/tabs/
    plots/
      __init__.py
      plots_tab.py                 # Вкладка управления графиками
      templates/
        plots_export.html.j2       # Jinja2 template для экспорта
    
    peptides/
      __init__.py
      peptide_ion_plot_view.py     # График b/y ионов
      peptide_ion_table_view.py    # Таблица идентификаций
      # ... остальные файлы без изменений
    
    proteins/
      __init__.py
      protein_concentration_plot_view.py      # График концентраций
      protein_identifications_table_view.py   # Таблица идентификаций
      protein_statistics_table_view.py        # Таблица статистики
      # ... остальные файлы без изменений

api/
  project/
    mixins/
      plot_mixin.py                # Методы для работы с saved_plots
      protein_mixin.py             # Расширенные методы
    
    models.py                      # Схема таблицы saved_plots
```

---

## Критерии приёмки

### Базовые компоненты
- [ ] `BasePlotView` работает, можно создать наследника
- [ ] `BaseTableView` работает с паджинацией
- [ ] `BaseTableAndPlotView` связывает таблицу и график
- [ ] Таблица `saved_plots` создана в БД
- [ ] Методы в `PlotMixin` работают корректно

### Вкладка Plots
- [ ] Отображает список сохранённых графиков
- [ ] Можно просмотреть график
- [ ] Можно удалить график
- [ ] Можно выбрать несколько и экспортировать в Word

### Вкладка Peptides
- [ ] Таблица идентификаций работает с фильтрами
- [ ] Паджинация работает корректно
- [ ] График b/y ионов строится корректно
- [ ] Можно сохранить график в проект
- [ ] Можно экспортировать график (PNG/SVG)
- [ ] Настройки сохраняются в проект

### Вкладка Proteins
- [ ] Переключение между режимами Identifications/Statistics работает
- [ ] Таблица Statistics показывает агрегированные данные
- [ ] Фильтры Statistics работают
- [ ] График концентраций строится как boxplot/violin
- [ ] Фильтрация по группам работает
- [ ] Удаление аутлаеров работает корректно
- [ ] Цвета групп применяются из БД
- [ ] Можно сохранить график в проект

### Общие требования
- [ ] Все async операции не блокируют UI
- [ ] Настройки сохраняются и загружаются из проекта
- [ ] Ошибки обрабатываются с отображением SnackBar
- [ ] Код соответствует архитектуре проекта
- [ ] Используется актуальный Flet API (ft.dropdown.Option, dialog.open, etc.)
- [ ] Документация обновлена

---

## Примечания по реализации

### Flet API

**Важно:** Используется актуальная версия Flet. Обязательно применять следующие паттерны:

1. **Dropdown options:**
   ```python
   ft.dropdown.Option(key="value", text="Display Text")
   ```

2. **FilePicker (async):**
   ```python
   files = await ft.FilePicker().pick_files(...)
   path = await ft.FilePicker().save_file(...)
   dir_path = await ft.FilePicker().get_directory_path(...)
   ```

3. **AlertDialog:**
   ```python
   dialog = ft.AlertDialog(...)
   page.overlay.append(dialog)
   dialog.open = True
   page.update()
   
   # Закрытие:
   dialog.open = False
   page.update()
   ```

4. **SnackBar:**
   ```python
   page.snack_bar = ft.SnackBar(content=ft.Text("Message"))
   page.snack_bar.open = True
   page.update()
   ```

5. **Buttons:**
   ```python
   ft.ElevatedButton(
       content="Button Text",  # НЕ text=
       icon=ft.Icons.ICON_NAME,
       on_click=handler
   )
   ```

### Цветовая схема

- Использовать цвета групп (subsets) из БД (поле `color`)
- Тема графиков: всегда `plotly_white`
- Не предоставлять пользователю выбор темы

### Асинхронность

- Все методы загрузки данных - async
- Обработчики событий:
  ```python
  async def handler(e):
      # async code
  
  # В кнопке:
  on_click=lambda e: page.run_task(handler, e)
  # или напрямую:
  on_click=handler
  ```

### Сохранение настроек

- Ключи в project settings:
  - Графики: `plot_view_{plot_type_name}_{parameter}`
  - Таблицы: `table_view_{table_view_name}_{parameter}`
- Сохранение только по кнопке (не реактивно)

### Паджинация

- SQL с `LIMIT` и `OFFSET`
- Размеры страниц: 25, 50, 100, 200 (dropdown)
- Информация: "Showing X-Y of Z rows (Page N of M)"
- Кнопки Prev/Next отключаются когда не применимы

### Экспорт

- PNG/SVG через kaleido: `fig.write_image(path, format=format)`
- Word через html4docx:
  ```python
  from docx import Document
  from html4docx import HtmlToDocx
  
  doc = Document()
  html_converter = HtmlToDocx()
  html_converter.add_html_to_document(html, doc)
  doc.save(path)
  ```
- HTML через Jinja2 templates

---

**Конец спецификации**
