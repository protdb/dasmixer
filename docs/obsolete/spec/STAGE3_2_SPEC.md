# Спецификация этапа 3.2: Базовый функционал GUI и CLI

## Обзор

Этап 3.2 реализует базовый функционал приложения DASMixer для работы с проектами через GUI и CLI:
- Создание и открытие проектов
- Управление группами сравнения (subsets)
- Импорт спектральных данных (MGF)
- Импорт идентификаций пептидов
- Просмотр и навигация по данным
- Визуализация графиков разметки ионов

## Архитектура решения

### 1. Точка входа: `main.py`

Единая точка входа для GUI и CLI режимов.

**Файл:** `main.py` (корень проекта)

**Формат запуска:**
```bash
# GUI режим (по умолчанию)
python main.py

# Открытие проекта в GUI
python main.py path/to/project.dasmix

# CLI режим с командами
python main.py path/to/project.dasmix create
python main.py path/to/project.dasmix subset add --name "Treatment"
python main.py path/to/project.dasmix import-mgf [OPTIONS]
```

**Логика:**
```python
import typer
from typing import Annotated

app = typer.Typer()

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context, 
    file_path: Annotated[str | None, typer.Argument()] = None
):
    """
    DASMixer - Mass Spectrometry Data Integration Tool
    
    Run without arguments to launch GUI.
    Provide project path to open it in GUI.
    Add command to execute CLI operations.
    """
    # Если нет подкоманды - запускаем GUI
    if ctx.invoked_subcommand is None:
        from gui.app import run_gui
        run_gui(file_path)
    # Иначе команда будет обработана typer

# Регистрация CLI команд
from cli.commands import subset, import_data

app.add_typer(subset.app, name="subset")
app.add_typer(import_data.app, name="import")

if __name__ == '__main__':
    app()
```

---

## 2. Модуль настроек приложения

Системные настройки для сохранения пользовательских предпочтений.

**Файл:** `api/config.py`

**Функционал:**
- Хранение последних использованных путей (для файлов/папок)
- Настройки UI (размеры окон, темы - в будущем)
- Использование системной папки через `typer.get_app_dir()`

**Реализация:**
```python
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
import typer
import json

class AppConfig(BaseSettings):
    """Application configuration stored in system folder."""
    
    # Paths
    last_project_path: str | None = None
    last_import_folder: str | None = None
    last_export_folder: str | None = None
    
    # Recent projects (list of paths)
    recent_projects: list[str] = []
    
    # UI settings (future)
    theme: str = "light"
    
    model_config = SettingsConfigDict(
        env_prefix="DASMIXER_",
        env_file=".env",
        env_file_encoding="utf-8"
    )
    
    @classmethod
    def get_config_path(cls) -> Path:
        """Get path to config file in system folder."""
        app_dir = Path(typer.get_app_dir("dasmixer"))
        app_dir.mkdir(parents=True, exist_ok=True)
        return app_dir / "config.json"
    
    @classmethod
    def load(cls) -> 'AppConfig':
        """Load config from file or create default."""
        config_path = cls.get_config_path()
        if config_path.exists():
            with open(config_path, 'r') as f:
                data = json.load(f)
            return cls(**data)
        return cls()
    
    def save(self) -> None:
        """Save config to file."""
        config_path = self.get_config_path()
        with open(config_path, 'w') as f:
            json.dump(self.model_dump(), f, indent=2)
    
    def add_recent_project(self, path: str) -> None:
        """Add project to recent list (max 10)."""
        if path in self.recent_projects:
            self.recent_projects.remove(path)
        self.recent_projects.insert(0, path)
        self.recent_projects = self.recent_projects[:10]
        self.save()

# Global config instance
config = AppConfig.load()
```

---

## 3. GUI архитектура

### 3.1. Основное приложение

**Файл:** `gui/app.py`

**Структура:**
```python
import flet as ft
from api.config import config
from gui.views.start_view import StartView
from gui.views.project_view import ProjectView

class DASMixerApp:
    """Main GUI application."""
    
    def __init__(self, page: ft.Page, initial_project_path: str | None = None):
        self.page = page
        self.initial_project_path = initial_project_path
        self.current_project = None
        
        # Configure page
        self.page.title = "DASMixer"
        self.page.window.width = 1200
        self.page.window.height = 800
        
        # Menu bar
        self.setup_menu()
        
        # Initial view
        if initial_project_path:
            self.open_project(initial_project_path)
        else:
            self.show_start_view()
    
    def setup_menu(self):
        """Create application menu."""
        self.page.appbar = ft.AppBar(
            title=ft.Text("DASMixer"),
            actions=[
                ft.PopupMenuButton(
                    items=[
                        ft.PopupMenuItem(text="New Project", on_click=self.new_project),
                        ft.PopupMenuItem(text="Open Project", on_click=self.open_project_dialog),
                        ft.PopupMenuItem(text="Close Project", on_click=self.close_project),
                        ft.PopupMenuItem(),  # Divider
                        ft.PopupMenuItem(text="Exit", on_click=lambda _: self.page.window.close()),
                    ]
                )
            ]
        )
    
    def show_start_view(self):
        """Show startup screen."""
        self.page.clean()
        view = StartView(
            on_create_project=self.new_project,
            on_open_project=self.open_project,
            recent_projects=config.recent_projects
        )
        self.page.add(view)
        self.page.update()
    
    def show_project_view(self):
        """Show project workspace."""
        self.page.clean()
        view = ProjectView(
            project=self.current_project,
            on_close=self.close_project
        )
        self.page.add(view)
        self.page.update()
    
    async def new_project(self, e=None):
        """Create new project."""
        # Show file picker for save location
        # Create project
        # Update config
        # Show project view
        pass
    
    async def open_project(self, path: str | None = None, e=None):
        """Open existing project."""
        # If path not provided, show file picker
        # Open project
        # Update config
        # Show project view
        pass
    
    async def close_project(self, e=None):
        """Close current project."""
        if self.current_project:
            await self.current_project.close()
            self.current_project = None
        self.show_start_view()

def run_gui(project_path: str | None = None):
    """Entry point for GUI mode."""
    def main(page: ft.Page):
        app = DASMixerApp(page, project_path)
    
    ft.app(target=main)
```

### 3.2. Стартовое представление

**Файл:** `gui/views/start_view.py`

**Компоненты:**
- Заголовок приложения
- Кнопка "Create New Project"
- Кнопка "Open Project"
- Список последних проектов (Recent Projects)
  - Кликабельные элементы для быстрого открытия
  - Полный путь виден при наведении

**Layout:**
```
┌─────────────────────────────────────┐
│         DASMixer                     │
│  Mass Spectrometry Data Integration  │
├─────────────────────────────────────┤
│                                      │
│   [  Create New Project  ]          │
│   [  Open Project...     ]          │
│                                      │
│   Recent Projects:                   │
│   • project1.dasmix                  │
│   • project2.dasmix                  │
│   • ...                              │
│                                      │
└─────────────────────────────────────┘
```

### 3.3. Представление проекта

**Файл:** `gui/views/project_view.py`

**Структура:** Вкладки (Tabs)

#### Вкладка 1: Samples (Образцы)

**Файл:** `gui/views/tabs/samples_tab.py`

**Секции:**

1. **Управление группами (Subsets Management)**
   - Список групп с возможностью добавления/удаления
   - Показывает: название, цвет, количество образцов
   - Кнопки: "Add Group", "Delete Selected"
   - Модальное окно для создания группы:
     - Поле: Group Name (required)
     - Поле: Description (optional)
     - Выбор цвета (color picker)

2. **Импорт данных (Data Import)**
   - Кнопка "Import Spectra (MGF)" → открывает диалог импорта
   - Кнопка "Import Identifications" → открывает диалог импорта

3. **Список образцов (Samples List)**
   - Таблица (DataTable):
     - Sample Name
     - MGF File (с копированием полного пути по клику)
     - Tools (список инструментов: ✓/✗)
     - Group (выпадающий список для изменения)
   - Кнопки массовых операций:
     - "Assign to Group" (для выбранных)
     - "Delete Selected"

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│ Groups                                               │
│ ┌─────────────────────────────────────────────────┐ │
│ │ Control (5 samples)   [Delete]                  │ │
│ │ Treatment (3 samples) [Delete]                  │ │
│ │                       [+ Add Group]             │ │
│ └─────────────────────────────────────────────────┘ │
│                                                      │
│ Import Data                                          │
│ [Import Spectra (MGF)]  [Import Identifications]    │
│                                                      │
│ Samples                                              │
│ ┌────────────────────────────────────────────────┐  │
│ │Name    │ MGF File      │Tools      │ Group    │  │
│ │────────┼───────────────┼───────────┼──────────│  │
│ │Sample1 │ data1.mgf     │PN2:✓ MQ:✗│ Control ▼│  │
│ │Sample2 │ data2.mgf     │PN2:✓ MQ:✓│ Treatm. ▼│  │
│ └────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

#### Вкладка 2: Peptides (Пептиды)

**Файл:** `gui/views/tabs/peptides_tab.py`

**Секции:**

1. **Поиск идентификаций (Identification Search)**
   - Dropdown: Search by (seq_no / scans / canonical_sequence)
   - TextField: Search value
   - Dropdown: Filter by Sample
   - Button: "Search"

2. **Результаты поиска (Search Results)**
   - Таблица идентификаций:
     - Spectrum ID
     - Sample
     - Tool
     - Sequence
     - Score
     - PPM
   - Кнопка "View Ion Match" для выбранной строки

3. **График разметки ионов (Ion Match Viewer)**
   - Отображение спектра с аннотациями
   - Кнопка "Interactive Mode" → pywebview

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│ Search Identifications                               │
│ [seq_no ▼] [________] [All Samples ▼] [Search]      │
│                                                      │
│ Results                                              │
│ ┌────────────────────────────────────────────────┐  │
│ │ID │Sample│Tool    │Sequence    │Score│PPM    │  │
│ │───┼──────┼────────┼────────────┼─────┼───────│  │
│ │1  │S1    │PN2     │PEPTIDE     │0.95 │5.2    │  │
│ │2  │S1    │MaxQuant│PEPTIDE     │     │3.1    │  │
│ └────────────────────────────────────────────────┘  │
│ [View Ion Match]                                     │
│                                                      │
│ Ion Match Visualization                              │
│ ┌────────────────────────────────────────────────┐  │
│ │         [Spectrum plot rendered here]          │  │
│ │                                                │  │
│ └────────────────────────────────────────────────┘  │
│ [Interactive Mode]                                   │
└─────────────────────────────────────────────────────┘
```

#### Вкладки 3-4: Заглушки

**Файлы:** 
- `gui/views/tabs/proteins_tab.py`
- `gui/views/tabs/analysis_tab.py`

**Содержимое:** Простой Text("Coming soon...")

---

### 3.4. Диалоги

#### Диалог импорта данных (универсальный)

**Файл:** `gui/dialogs/import_dialog.py`

**Параметры:**
- `parser_type`: "spectra" или "identification"
- Автоматически загружает список доступных парсеров из registry

**Компоненты:**

1. **Вкладка: Pattern-based Import**
   - TextField: Folder Path (с file picker)
   - TextField: File Pattern (например, `*.mgf`)
   - TextField: Sample ID Pattern (например, `{id}_run*.mgf`)
   - Dropdown: Parser
   - Button: "Find Files"
   - DataTable: Preview найденных файлов
     - Path
     - Detected Sample ID (editable)
   - Button: "Import"

2. **Вкладка: Single File Import**
   - TextField: File Path (с file picker)
   - TextField: Sample ID (manual input)
   - Dropdown: Parser
   - Dropdown: Assign to Group (для spectra)
   - Button: "Import"

**Процесс импорта:**
- Показывает прогресс-бар
- Использует asyncio + ProcessPoolExecutor
- После завершения обновляет таблицу образцов

**Логика работы:**
```python
from utils.seek_files import seek_files

async def find_files(folder: str, pattern: str, id_template: str):
    """Find files using pattern matching."""
    files = seek_files(folder, pattern, id_template)
    # Returns: list[tuple[Path, str]] - (path, sample_id)
    return files

async def import_files(files: list[tuple[Path, str]], parser_class, ...):
    """Import files with progress tracking."""
    # Use ProcessPoolExecutor for parallel parsing
    # Update progress bar
    # Save to project
    pass
```

---

### 3.5. Универсальный компонент для графиков

**Файл:** `gui/components/plotly_viewer.py`

**Класс:** `PlotlyViewer`

**Функционал:**
- Принимает `plotly.graph_objects.Figure`
- Отображает статичное изображение (PNG через `fig.to_image()`)
- Кнопка "Interactive Mode" → запуск pywebview в отдельном процессе

**Реализация:**
```python
import flet as ft
import multiprocessing
import webview
import plotly.graph_objects as go

class PlotlyViewer(ft.Container):
    """Universal Plotly chart viewer with interactive mode."""
    
    def __init__(
        self,
        figure: go.Figure,
        width: int = 1000,
        height: int = 500,
        title: str = "Chart"
    ):
        super().__init__()
        self.figure = figure
        self.width = width
        self.height = height
        self.title = title
    
    def build(self):
        # Render static image
        img_bytes = self.figure.to_image(
            format='png',
            width=self.width,
            height=self.height
        )
        
        image = ft.Image(src_base64=img_bytes)
        
        button = ft.ElevatedButton(
            text="Interactive Mode",
            on_click=self.launch_interactive
        )
        
        return ft.Column([
            image,
            button
        ])
    
    def launch_interactive(self, e):
        """Launch interactive viewer in separate process."""
        process = multiprocessing.Process(
            target=show_webview,
            args=(self.figure, self.title)
        )
        process.start()

def show_webview(fig: go.Figure, title: str):
    """Show plotly figure in webview window."""
    html = fig.to_html(include_plotlyjs='cdn')
    window = webview.create_window(title, html=html)
    webview.start()
```

**Использование:**

```python
from api.calculations.spectra.plot_matches import generate_spectrum_plot
from gui.components.plotly_viewer import PlotlyViewer

# Create figure
fig = generate_spectrum_plot("Sample", data)

# Display with interactive mode
viewer = PlotlyViewer(fig, title="Ion Match Spectrum")
page.add(viewer)
```

---

## 4. CLI архитектура

### 4.1. Команды для управления проектом

**Файл:** `cli/commands/project.py`

**Команда: create**
```bash
python main.py path/to/project.dasmix create
```

Создаёт новый пустой проект с группой "Control" по умолчанию.

**Реализация:**
```python
import typer
from pathlib import Path
from api.project.project import Project

app = typer.Typer()

@app.command()
async def create(ctx: typer.Context):
    """Create new empty project."""
    project_path = ctx.parent.params.get('file_path')
    if not project_path:
        typer.echo("Error: Project path required")
        raise typer.Exit(1)
    
    project_path = Path(project_path)
    
    if project_path.exists():
        if not typer.confirm(f"File {project_path} exists. Overwrite?"):
            raise typer.Exit(0)
    
    async with Project(path=project_path, create_if_not_exists=True) as project:
        # Create default Control group
        await project.add_subset("Control", details="Default control group")
        typer.echo(f"Created project: {project_path}")
```

### 4.2. Команды для групп

**Файл:** `cli/commands/subset.py`

**Команды:**
```bash
# Добавить группу
python main.py project.dasmix subset add --name "Treatment" --color "#FF5733"

# Удалить группу
python main.py project.dasmix subset delete --name "Treatment"

# Список групп
python main.py project.dasmix subset list
```

**Реализация:**
```python
import typer
from api.project.project import Project

app = typer.Typer()

@app.command()
async def add(
    ctx: typer.Context,
    name: str = typer.Option(..., help="Group name"),
    details: str = typer.Option(None, help="Description"),
    color: str = typer.Option(None, help="Display color (hex)")
):
    """Add new comparison group."""
    project_path = ctx.parent.parent.params.get('file_path')
    
    async with Project(path=project_path) as project:
        subset = await project.add_subset(name, details, color)
        typer.echo(f"Added group: {subset.name} (id={subset.id})")

@app.command()
async def delete(
    ctx: typer.Context,
    name: str = typer.Option(..., help="Group name to delete")
):
    """Delete comparison group."""
    project_path = ctx.parent.parent.params.get('file_path')
    
    async with Project(path=project_path) as project:
        # Find subset by name
        subsets = await project.get_subsets()
        subset = next((s for s in subsets if s.name == name), None)
        
        if not subset:
            typer.echo(f"Error: Group '{name}' not found")
            raise typer.Exit(1)
        
        await project.delete_subset(subset.id)
        typer.echo(f"Deleted group: {name}")

@app.command()
async def list(ctx: typer.Context):
    """List all comparison groups."""
    project_path = ctx.parent.parent.params.get('file_path')
    
    async with Project(path=project_path) as project:
        subsets = await project.get_subsets()
        
        if not subsets:
            typer.echo("No groups found")
            return
        
        typer.echo("\nComparison Groups:")
        typer.echo("-" * 50)
        for subset in subsets:
            typer.echo(f"  {subset.name}")
            if subset.details:
                typer.echo(f"    Description: {subset.details}")
            if subset.display_color:
                typer.echo(f"    Color: {subset.display_color}")
```

### 4.3. Команды для импорта данных

**Файл:** `cli/commands/import_data.py`

**Два режима:**

#### Режим 1: Импорт по шаблону (pattern-based)

```bash
python main.py project.dasmix import mgf-pattern \
    --folder /path/to/data \
    --file-pattern "*.mgf" \
    --id-pattern "{id}_run*.mgf" \
    --parser MGF \
    --group Control
```

#### Режим 2: Импорт одного файла

```bash
python main.py project.dasmix import mgf-file \
    --file /path/to/sample1.mgf \
    --sample-id "Sample1" \
    --parser MGF \
    --group Control
```

**Аналогично для идентификаций:**

```bash
python main.py project.dasmix import ident-pattern \
    --folder /path/to/results \
    --file-pattern "*.csv" \
    --id-pattern "{id}_powernovo.csv" \
    --parser PowerNovo2 \
    --tool PowerNovo2

python main.py project.dasmix import ident-file \
    --file /path/to/results.csv \
    --sample-id "Sample1" \
    --parser PowerNovo2 \
    --tool PowerNovo2
```

**Реализация:**
```python
import typer
from pathlib import Path
from api.project.project import Project
from api.inputs.registry import registry
from utils.seek_files import seek_files
import asyncio

app = typer.Typer()

@app.command()
async def mgf_pattern(
    ctx: typer.Context,
    folder: str = typer.Option(..., help="Folder to search"),
    file_pattern: str = typer.Option(..., help="File pattern (e.g., *.mgf)"),
    id_pattern: str = typer.Option(..., help="Sample ID pattern"),
    parser: str = typer.Option("MGF", help="Parser name"),
    group: str = typer.Option("Control", help="Group to assign samples")
):
    """Import MGF files using pattern matching."""
    project_path = ctx.parent.parent.params.get('file_path')
    
    # Find files
    files = seek_files(folder, file_pattern, id_pattern)
    
    if not files:
        typer.echo("No files found matching pattern")
        raise typer.Exit(1)
    
    typer.echo(f"Found {len(files)} files:")
    for path, sample_id in files:
        typer.echo(f"  {path.name} -> Sample ID: {sample_id or 'UNKNOWN'}")
    
    if not typer.confirm("Proceed with import?"):
        raise typer.Exit(0)
    
    # Get parser
    parser_class = registry.get_parser(parser, "spectra")
    
    # Import
    async with Project(path=project_path) as project:
        # Get or create group
        subsets = await project.get_subsets()
        subset = next((s for s in subsets if s.name == group), None)
        
        if not subset:
            subset = await project.add_subset(group)
        
        with typer.progressbar(files, label="Importing") as progress:
            for file_path, sample_id in progress:
                if not sample_id:
                    sample_id = file_path.stem
                
                # Parse file
                parser_instance = parser_class(str(file_path))
                spectra_df = await parser_instance.parse_batch()
                
                # Add to project
                sample = await project.get_sample_by_name(sample_id)
                if not sample:
                    sample = await project.add_sample(
                        sample_id,
                        subset_id=subset.id
                    )
                
                spectra_file_id = await project.add_spectra_file(
                    sample.id,
                    parser,
                    str(file_path)
                )
                
                await project.add_spectra_batch(spectra_file_id, spectra_df)
        
        typer.echo(f"Imported {len(files)} files successfully")

# Аналогичные команды для mgf-file, ident-pattern, ident-file
```

---

## 5. Доработки API

### 5.1. Метод get_spectra_idlist в Project

**Файл:** `api/project/project.py`

**Добавить метод:**
```python
async def get_spectra_idlist(
    self,
    spectra_file_id: int,
    by: str = "seq_no"
) -> dict[int | str, int]:
    """
    Get mapping from seq_no or scans to spectrum database IDs.
    
    Args:
        spectra_file_id: Spectra file ID
        by: "seq_no" or "scans" - field to use as key
        
    Returns:
        Dict mapping seq_no/scans to spectrum ID in database
        
    Example:
        >>> mapping = await project.get_spectra_idlist(file_id, by="scans")
        >>> spectrum_id = mapping[1234]  # scans=1234 -> id in DB
    """
    if by not in ("seq_no", "scans"):
        raise ValueError(f"Invalid 'by' parameter: {by}. Must be 'seq_no' or 'scans'")
    
    query = f"""
        SELECT id, {by}
        FROM spectre
        WHERE spectre_file_id = ?
        AND {by} IS NOT NULL
    """
    
    rows = await self._fetchall(query, (spectra_file_id,))
    
    return {row[by]: row['id'] for row in rows}
```

**Использование в парсерах:**
- Парсеры идентификаций возвращают данные с `seq_no` или `scans`
- В логике импорта (GUI/CLI) после получения данных из парсера:
  1. Получаем маппинг через `get_spectra_idlist`
  2. Обогащаем DataFrame идентификаций полем `spectre_id`
  3. Добавляем `tool_id` и `ident_file_id`
  4. Передаём в `add_identifications_batch`

---

## 6. Регистрация парсеров

### 6.1. Система регистрации

**Файл:** `api/inputs/__init__.py`

**Логика:**
- При импорте модуля `api.inputs` автоматически регистрируются все парсеры
- Используется глобальный объект `registry`

**Реализация:**
```python
"""Input parsers package with automatic registration."""

from .registry import registry
from .base import SpectralDataParser, IdentificationParser

# Import and register all parsers
def register_parsers():
    """Register all available parsers."""
    # Spectra parsers
    try:
        from .spectra.mgf import MGFParser
        registry.add_spectra_parser("MGF", MGFParser)
    except ImportError:
        pass
    
    # Add more parsers as they are implemented
    # try:
    #     from .spectra.mzml import MZMLParser
    #     registry.add_spectra_parser("MZML", MZMLParser)
    # except ImportError:
    #     pass
    
    # Identification parsers
    # try:
    #     from .peptides.powernovo2 import PowerNovo2Parser
    #     registry.add_identification_parser("PowerNovo2", PowerNovo2Parser)
    # except ImportError:
    #     pass

# Auto-register on import
register_parsers()

__all__ = [
    'registry',
    'SpectralDataParser',
    'IdentificationParser'
]
```

**Будущие плагины:**
- Структура готова для добавления внешних парсеров
- В будущем: сканирование папки `plugins/` и автоматическая регистрация
- Формат плагина: Python-модуль с функцией `register(registry)`

---

## 7. Прогресс-бары и асинхронность

### 7.1. В GUI

**Компонент прогресса:** `gui/components/progress_dialog.py`

```python
import flet as ft
import asyncio

class ProgressDialog(ft.AlertDialog):
    """Modal dialog with progress bar."""
    
    def __init__(self, title: str = "Processing..."):
        self.progress_bar = ft.ProgressBar(width=400, value=0)
        self.status_text = ft.Text("")
        
        super().__init__(
            title=ft.Text(title),
            content=ft.Column([
                self.progress_bar,
                self.status_text
            ]),
            modal=True
        )
    
    def update_progress(self, value: float, status: str = ""):
        """Update progress (0.0 to 1.0)."""
        self.progress_bar.value = value
        self.status_text.value = status
        self.update()
```

**Использование:**
```python
async def import_files_async(files, ...):
    """Import files with progress tracking."""
    dialog = ProgressDialog("Importing files...")
    page.dialog = dialog
    dialog.open = True
    page.update()
    
    total = len(files)
    for i, (file_path, sample_id) in enumerate(files):
        # Parse and import
        ...
        
        # Update progress
        dialog.update_progress(
            (i + 1) / total,
            f"Imported {i + 1}/{total}: {file_path.name}"
        )
    
    dialog.open = False
    page.update()
```

### 7.2. В CLI

Использование встроенного `typer.progressbar`:

```python
with typer.progressbar(files, label="Importing") as progress:
    for file_path, sample_id in progress:
        # Process file
        pass
```

---

## 8. План реализации (последовательность)

### Шаг 1: Настройки и конфигурация
- [x] `api/config.py` - системные настройки

### Шаг 2: Точка входа
- [ ] `main.py` - единая точка входа с Typer

### Шаг 3: GUI базовая структура
- [ ] `gui/app.py` - главное приложение
- [ ] `gui/views/start_view.py` - стартовый экран
- [ ] `gui/views/project_view.py` - контейнер проекта с вкладками

### Шаг 4: GUI компоненты
- [ ] `gui/components/plotly_viewer.py` - универсальный просмотрщик графиков
- [ ] `gui/components/progress_dialog.py` - диалог прогресса

### Шаг 5: GUI вкладки
- [ ] `gui/views/tabs/samples_tab.py` - управление образцами и группами
- [ ] `gui/views/tabs/peptides_tab.py` - просмотр идентификаций и графиков
- [ ] `gui/views/tabs/proteins_tab.py` - заглушка
- [ ] `gui/views/tabs/analysis_tab.py` - заглушка

### Шаг 6: GUI диалоги
- [ ] `gui/dialogs/import_dialog.py` - универсальный диалог импорта

### Шаг 7: CLI команды
- [ ] `cli/commands/project.py` - создание проекта
- [ ] `cli/commands/subset.py` - управление группами
- [ ] `cli/commands/import_data.py` - импорт данных

### Шаг 8: Доработки API
- [ ] `api/project/project.py` - метод `get_spectra_idlist`
- [ ] `api/inputs/__init__.py` - автоматическая регистрация парсеров

### Шаг 9: Интеграция и тестирование
- [ ] Интеграционные тесты для CLI
- [ ] Проверка работы GUI
- [ ] Тестирование на реальных данных

---

## 9. Файловая структура

```
dasmixer/
├── main.py                          # Точка входа
├── api/
│   ├── config.py                    # Настройки приложения
│   ├── inputs/
│   │   ├── __init__.py             # Автоматическая регистрация парсеров
│   │   └── registry.py             # Реестр парсеров
│   └── project/
│       └── project.py              # + метод get_spectra_idlist
├── gui/
│   ├── app.py                      # Главное приложение
│   ├── components/
│   │   ├── plotly_viewer.py        # Просмотр графиков
│   │   └── progress_dialog.py      # Диалог прогресса
│   ├── dialogs/
│   │   └── import_dialog.py        # Диалог импорта
│   └── views/
│       ├── start_view.py           # Стартовый экран
│       ├── project_view.py         # Контейнер проекта
│       └── tabs/
│           ├── samples_tab.py      # Вкладка образцов
│           ├── peptides_tab.py     # Вкладка пептидов
│           ├── proteins_tab.py     # Заглушка
│           └── analysis_tab.py     # Заглушка
└── cli/
    └── commands/
        ├── project.py              # Команды проекта
        ├── subset.py               # Команды групп
        └── import_data.py          # Команды импорта
```

---

## 10. Зависимости

Все необходимые зависимости уже установлены в `pyproject.toml`:
- `flet` - GUI
- `typer` - CLI
- `plotly` + `kaleido` - графики
- `pywebview` - интерактивный режим
- `pydantic-settings` - конфигурация
- `aiosqlite` - асинхронная работа с БД

---

## 11. Особенности реализации

### 11.1. Асинхронность в Flet

Flet поддерживает `async/await`, но требует правильного оформления:

```python
import flet as ft

async def button_click(e):
    # Async operation
    result = await some_async_function()
    # Update UI
    e.control.text = result
    e.control.update()

button = ft.ElevatedButton("Click", on_click=button_click)
```

### 11.2. Использование ProcessPoolExecutor для тяжелых операций

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

async def parse_files_parallel(files):
    """Parse multiple files in parallel."""
    loop = asyncio.get_running_loop()
    executor = ProcessPoolExecutor(max_workers=4)
    
    tasks = [
        loop.run_in_executor(executor, parse_single_file, file)
        for file in files
    ]
    
    results = await asyncio.gather(*tasks)
    return results
```

### 11.3. Multiprocessing для pywebview

**Важно:** `if __name__ == '__main__'` guard обязателен для multiprocessing!

```python
import multiprocessing

def show_webview(fig, title):
    """Must be top-level function for pickling."""
    import webview
    html = fig.to_html(include_plotlyjs='cdn')
    window = webview.create_window(title, html=html)
    webview.start()

# In component
def launch_interactive(self, e):
    process = multiprocessing.Process(
        target=show_webview,
        args=(self.figure, self.title)
    )
    process.start()
```

---

## 12. Тестирование

### 12.1. Интеграционные тесты CLI

**Файл:** `tests/test_cli_stage3_2.py`

```python
import pytest
from typer.testing import CliRunner
from main import app
from pathlib import Path
import tempfile

runner = CliRunner()

def test_create_project():
    """Test project creation via CLI."""
    with tempfile.NamedTemporaryFile(suffix='.dasmix', delete=False) as f:
        project_path = f.name
    
    result = runner.invoke(app, [project_path, 'create'])
    assert result.exit_code == 0
    assert Path(project_path).exists()

def test_subset_operations():
    """Test subset add/list/delete."""
    # Create project
    with tempfile.NamedTemporaryFile(suffix='.dasmix', delete=False) as f:
        project_path = f.name
    
    runner.invoke(app, [project_path, 'create'])
    
    # Add subset
    result = runner.invoke(app, [
        project_path, 'subset', 'add',
        '--name', 'Treatment'
    ])
    assert result.exit_code == 0
    
    # List subsets
    result = runner.invoke(app, [project_path, 'subset', 'list'])
    assert 'Control' in result.stdout
    assert 'Treatment' in result.stdout
    
    # Delete subset
    result = runner.invoke(app, [
        project_path, 'subset', 'delete',
        '--name', 'Treatment'
    ])
    assert result.exit_code == 0
```

### 12.2. Тестирование GUI

Ручное тестирование с реальными данными:
- Создание/открытие проекта
- Управление группами
- Импорт спектров
- Импорт идентификаций
- Просмотр идентификаций
- Отображение графиков

---

## 13. Документация

После реализации этапа создать:
- `docs/user/CLI.md` - руководство по CLI
- `docs/user/GUI.md` - руководство по GUI
- `docs/technical/STAGE3_2_IMPLEMENTATION.md` - детали реализации

---

## Контрольный список (Checklist)

### API
- [ ] Метод `get_spectra_idlist` в Project
- [ ] Автоматическая регистрация парсеров
- [ ] Конфигурация приложения (AppConfig)

### CLI
- [ ] main.py с Typer
- [ ] Команда create
- [ ] Команды subset (add/delete/list)
- [ ] Команды import (mgf-pattern/mgf-file/ident-pattern/ident-file)
- [ ] Прогресс-бары

### GUI
- [ ] Главное приложение (app.py)
- [ ] Стартовое представление
- [ ] Меню приложения
- [ ] Вкладка Samples
  - [ ] Управление группами
  - [ ] Список образцов
  - [ ] Диалог импорта
- [ ] Вкладка Peptides
  - [ ] Поиск идентификаций
  - [ ] Просмотр результатов
  - [ ] График разметки ионов
- [ ] Заглушки вкладок (Proteins, Analysis)
- [ ] Универсальный PlotlyViewer
- [ ] Диалог прогресса
- [ ] Интерактивный режим через pywebview

### Интеграция
- [ ] Импорт спектров (GUI + CLI)
- [ ] Импорт идентификаций (GUI + CLI)
- [ ] Обогащение данных (file_id, tool_id, spectre_id)
- [ ] Сохранение последних путей

### Тестирование
- [ ] Интеграционные тесты CLI
- [ ] Ручное тестирование GUI
- [ ] Проверка на реальных данных

---

## Примечания

1. **Создание проекта по умолчанию:** Всегда создаётся группа "Control"
2. **Маппинг спектров:** Используется либо `seq_no`, либо `scans` - определяется автоматически
3. **Парсеры:** Регистрируются автоматически при импорте модуля
4. **Графики:** Всегда PNG + опциональный интерактивный режим
5. **Конфигурация:** Сохраняется в системной папке пользователя
6. **Асинхронность:** Все операции с БД и парсинг - асинхронные
7. **CLI:** Асинхронные команды требуют обёртки (см. примеры)

---

## Следующие этапы (после 3.2)

- Этап 4: Поиск белковых идентификаций и отчёты (API)
- Этап 5: Интеграция этапа 4 в GUI, финализация
