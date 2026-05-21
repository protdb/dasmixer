# Спецификация: Настройки, структура проекта, плагины

## Обзор

Этап включает четыре независимых направления:

1. **Системные настройки** — новый view "Settings" с batch-лимитами и цветовой схемой
2. **Структура проекта** — рефакторинг в пакет `dasmixer/`
3. **Механизм плагинов** — динамическая загрузка парсеров идентификаций и модулей отчётов
4. **Логотип** — генерация версий нужных размеров и интеграция в GUI

---

## 1. Системные настройки

### 1.1 Расширение `AppConfig` (`api/config.py`)

Добавить в класс `AppConfig` новые поля:

```python
# Batch operation limits
spectra_batch_size: int = 5000
identification_batch_size: int = 5000
identification_processing_batch_size: int = 5000
protein_mapping_batch_size: int = 5000

# Default color palette (единый пул для tool и subset)
default_colors: list[str] = [
    "#3B82F6",  # blue
    "#10B981",  # green
    "#F59E0B",  # amber
    "#EF4444",  # red
    "#8B5CF6",  # violet
    "#06B6D4",  # cyan
    "#F97316",  # orange
    "#EC4899",  # pink
]

# Plugin status (enabled/disabled by plugin id)
plugin_states: dict[str, bool] = {}
```

Метод `get_next_color(existing_colors: list[str]) -> str` возвращает первый цвет из `default_colors`, которого нет в `existing_colors`; если все использованы — возвращает `default_colors[0]`.

### 1.2 Новый файл `gui/views/settings_view.py`

Класс `SettingsView(ft.View)` — отдельное view, открывается через `page.go("/settings")`, возврат через `page.go("/")` или `page.go("/project")`.

**Структура страницы:**

```
AppBar:
    title: "Settings"
    leading: IconButton(Icons.ARROW_BACK, on_click → page.views.pop(); page.update())

Content (scrollable Column):
    Section: "Batch Operation Limits"
    Section: "Default Color Palette"
```

#### Секция "Batch Operation Limits"

Заголовок секции + подсказка:

```
Text("Batch Operation Limits", size=18, weight=BOLD)
Text(
    "Increasing batch size improves performance by reducing read/write overhead, "
    "but increases RAM usage during processing. Use with caution.",
    size=12, italic=True, color=Colors.GREY_600
)
```

Четыре числовых поля `ft.TextField` с `keyboard_type=ft.KeyboardType.NUMBER`:

| Метка | Поле в AppConfig | Значение по умолчанию |
|---|---|---|
| "Spectra file batch size" | `spectra_batch_size` | 5000 |
| "Identification file batch size" | `identification_batch_size` | 5000 |
| "Identification processing batch size" | `identification_processing_batch_size` | 5000 |
| "Protein mapping batch size" | `protein_mapping_batch_size` | 5000 |

Каждое поле — ширина 200px. Расположение: `ft.Column` с `spacing=10`.

#### Секция "Default Color Palette"

Заголовок:
```
Text("Default Color Palette", size=18, weight=BOLD)
Text(
    "Colors used by default when creating new tools and subsets.",
    size=12, italic=True, color=Colors.GREY_600
)
```

Список редактируемых строк цветов. Каждая строка — `ft.Row`:

```
[
    ft.Container(width=36, height=36, bgcolor=<hex>, border_radius=4),  # превью
    ft.TextField(value=<hex>, width=120, hint_text="#rrggbb",
                 on_change=→ обновить превью),  # hex-поле
    ft.IconButton(Icons.DELETE_OUTLINE, on_click=→ удалить строку),
]
```

Под списком — кнопка "Add color" (`ft.TextButton` с иконкой `Icons.ADD`). При нажатии добавляет строку с `#888888` и пустым превью.

Валидация hex: при потере фокуса TextField проверять regex `^#[0-9a-fA-F]{6}$`. При некорректном значении — подсвечивать поле красной рамкой (`border_color=Colors.RED`), не сохранять.

#### Кнопка "Save Settings"

`ft.ElevatedButton("Save", icon=Icons.SAVE)` — зафиксирована внизу content (не floating):
- Читает значения из всех TextField
- Валидирует batch sizes (> 0, целое) и цвета
- Вызывает `config.save()`
- Показывает `ft.SnackBar("Settings saved")`

### 1.3 Навигация

В `gui/app.py`, метод `setup_menu`:

Добавить пункт меню в секцию "Параметры" (рядом с будущим "Project Settings"):

```python
ft.PopupMenuItem(
    content=ft.Text("Settings"),
    icon=ft.Icons.SETTINGS,
    on_click=lambda _: self.page.go("/settings")
)
```

В `app.py` зарегистрировать обработчик `on_route_change` и добавить view для `/settings`:

```python
def route_change(self, e):
    self.page.views.clear()
    # всегда базовый view (start или project)
    if self.current_project:
        self.page.views.append(self._build_project_view())
    else:
        self.page.views.append(self._build_start_view())
    
    if self.page.route == "/settings":
        self.page.views.append(
            SettingsView(on_back=lambda: self.page.go("/"))
        )
    elif self.page.route == "/plugins":
        self.page.views.append(
            PluginsView(on_back=lambda: self.page.go("/"))
        )
    self.page.update()
```

**Важно:** `SettingsView` и `PluginsView` — полноценные `ft.View`, используют `page.views` stack (стандартный механизм Flet-роутинга), а не замену content страницы.

---

## 2. Рефакторинг структуры проекта

### 2.1 Новая структура

```
dasmixer/                  ← новый Python-пакет (корневая директория)
    __init__.py
    main.py                ← перенесён из корня
    api/                   ← перенесено
    gui/                   ← перенесено
    cli/                   ← перенесено
```

В корне проекта остаётся:
```
pyproject.toml
poetry.lock
docs/
assets/
tests/
```

В `pyproject.toml` изменить точку входа:
```toml
[project.scripts]
dasmixer = "dasmixer.main:app"
```

### 2.2 Изменения импортов

Все внутренние импорты вида `from api.xxx import ...` → `from dasmixer.api.xxx import ...`.  
Все `from gui.xxx import ...` → `from dasmixer.gui.xxx import ...`.  
Все `from cli.xxx import ...` → `from dasmixer.cli.xxx import ...`.

**Затронутые файлы (неполный список, нужно пройти все):**

- `dasmixer/main.py` — импорты `cli.commands`, `gui.app`
- `dasmixer/gui/app.py` — `from api.config`, `from api.project`
- `dasmixer/gui/views/*.py` — все imports из api/gui
- `dasmixer/gui/views/tabs/**/*.py` — все imports
- `dasmixer/api/reporting/base.py` — `from ..project`
- `dasmixer/api/inputs/registry.py` — `from .peptides`, `from .spectra`
- `dasmixer/cli/commands/*.py` — все imports

### 2.3 Порядок выполнения

1. Создать директорию `dasmixer/` с `__init__.py`
2. Переместить `main.py`, `api/`, `gui/`, `cli/` в `dasmixer/`
3. Исправить все внутренние импорты (`from api.` → `from dasmixer.api.` и т.д.)
4. Обновить `pyproject.toml` — точку входа скрипта
5. Проверить запуск: `python -m dasmixer.main`

---

## 3. Механизм плагинов

### 3.1 Структура директорий плагинов

В системной папке приложения (путь через `typer.get_app_dir("dasmixer")`):

```
~/.config/dasmixer/        (Linux) / %APPDATA%/dasmixer/  (Windows)
    config.json
    plugins/
        inputs/
            identifications/   ← .py-файлы плагинов парсеров
        reports/               ← .py-файлы плагинов отчётов
```

### 3.2 Новый модуль `dasmixer/api/plugin_loader.py`

```python
"""Dynamic plugin loading for identification parsers and report modules."""

import importlib.util
import sys
import traceback
from pathlib import Path
import typer


def get_plugins_dir() -> Path:
    """Return path to plugins directory in app data folder."""
    return Path(typer.get_app_dir("dasmixer")) / "plugins"


def load_identification_plugins(registry) -> list[dict]:
    """
    Load identification parser plugins from plugins/inputs/identifications/.
    
    Each plugin file must import and call:
        from dasmixer.api.inputs.registry import registry as _registry
        _registry.add_identification_parser("PluginName", MyParserClass)
    
    Returns:
        list of dicts: [{
            'id': str,           # имя файла без расширения
            'path': Path,
            'name': str,         # имя как зарегистрировано в registry
            'error': str | None, # текст ошибки если загрузка не удалась
            'builtin': bool,     # False для плагинов
        }]
    """
    ...


def load_report_plugins(registry) -> list[dict]:
    """
    Load report module plugins from plugins/reports/.
    
    Each plugin file must import and call:
        from dasmixer.api.reporting.registry import registry as _registry
        _registry.register(MyReportClass)
    
    Returns:
        list of dicts: аналогично load_identification_plugins
    """
    ...


def load_single_plugin(path: Path) -> tuple[bool, str | None]:
    """
    Load single plugin file.
    
    Returns:
        (success: bool, error_message: str | None)
    """
    try:
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = module
        spec.loader.exec_module(module)
        return True, None
    except Exception:
        return False, traceback.format_exc()
```

**Логика загрузки плагина:**

1. Проверить в `config.plugin_states` — если `plugin_id: False`, пропустить
2. Попытаться загрузить через `importlib.util`
3. При успехе — плагин сам вызывает `registry.add_identification_parser()` или `registry.register()`
4. При исключении — сохранить текст ошибки, продолжить загрузку остальных плагинов
5. Возвращать список с результатами (включая ошибки) для отображения в UI

### 3.3 Инициализация в `dasmixer/main.py`

При старте приложения (до запуска GUI или CLI) вызывать:

```python
from dasmixer.api.plugin_loader import load_identification_plugins, load_report_plugins
from dasmixer.api.inputs.registry import registry as inputs_registry
from dasmixer.api.reporting.registry import registry as reports_registry

_plugin_load_results = (
    load_identification_plugins(inputs_registry) +
    load_report_plugins(reports_registry)
)
```

Результаты загрузки хранить как модульную переменную для доступа из `PluginsView`.

### 3.4 Формат плагина — `IdentificationParser`

Файл плагина `my_parser.py` в `plugins/inputs/identifications/`:

```python
"""
DASMixer Identification Parser Plugin.

Plugin name: MyTool
Version: 1.0.0
Author: Example Author
"""

from dasmixer.api.inputs.peptides.base import IdentificationParser
from dasmixer.api.inputs.registry import registry
import pandas as pd
from typing import AsyncIterator


class MyToolParser(IdentificationParser):
    """Parser for MyTool identification files."""

    spectra_id_field = 'seq_no'

    async def validate(self) -> bool:
        # Проверить что файл подходит
        ...

    async def parse_batch(
        self,
        batch_size: int = 1000
    ) -> AsyncIterator[tuple[pd.DataFrame, pd.DataFrame | None]]:
        # Парсить файл батчами
        ...
        yield peptide_df, None


# Регистрация плагина
registry.add_identification_parser("MyTool", MyToolParser)
```

### 3.5 Формат плагина — `BaseReport`

Файл плагина `my_report.py` в `plugins/reports/`:

```python
"""
DASMixer Report Plugin.

Plugin name: My Custom Report
Version: 1.0.0
Author: Example Author
"""

import flet as ft
import pandas as pd
import plotly.graph_objects as go
from dasmixer.api.reporting.base import BaseReport
from dasmixer.api.reporting.registry import registry


class MyCustomReport(BaseReport):
    name = "My Custom Report"
    description = "Description of what this report does"
    icon = ft.Icons.ASSESSMENT

    async def _generate_impl(self, params: dict):
        # Реализация генерации отчёта
        ...
        return [], []  # (plots, tables)


# Регистрация плагина
registry.register(MyCustomReport)
```

### 3.6 Установка плагина: копирование файла

При выборе файла плагина (`.py` или `.zip`) через `FilePicker`:

- `.py` — копируется в соответствующую директорию
- `.zip` — распаковывается в соответствующую директорию (все `.py` файлы из архива)

> !!! Уточнение. Не завязываемся на "все .py файлы". Подразумеваем, что в архиве есть одна папка, являющаяся модулем python, т.е. содержащая __init__.py. Делаем проверку: либо init.py в корне (тогда копируем содержимое архива в новую папку с именем как имя архива без расширения), либо в единственной папке в архиве (тогда распаковываем as is).

Соответствие: диалог открыт на вкладке "Identification Parsers" → `plugins/inputs/identifications/`, на вкладке "Reports" → `plugins/reports/`.

После копирования/распаковки предложить перезапустить приложение (`ft.AlertDialog` с текстом "Plugin installed. Restart the application to load it.").

### 3.7 Удаление плагина

При нажатии кнопки удаления — открыть `ft.AlertDialog` с подтверждением:

```
"Delete plugin '{name}'? The file will be permanently removed."
[Cancel]  [Delete]
```

При подтверждении — физически удалить файл `.py` из директории плагинов. Обновить список в UI.
> !!! Либо модуль. Можно хранить пути к плагинам в config.json

### 3.8 Новый файл `gui/views/plugins_view.py`

Класс `PluginsView(ft.View)`.

**Структура:**

```
AppBar:
    title: "Plugins"
    leading: IconButton(Icons.ARROW_BACK)

Content:
    ft.Tabs:
        Tab "Identification Parsers"
        Tab "Reports"
```
> !!! Без Tab, просто блоки с заголовками один под другим.

**Каждая вкладка** содержит:

1. `ft.ListView` — список плагинов (встроенных и внешних)
2. Строка кнопок внизу: "Install from file...", "Open plugins folder"

**Строка в списке** (для каждого плагина):

```
ft.ListTile:
    leading: ft.Checkbox(value=<enabled>, on_change=→ toggle plugin state)
    title: ft.Text("<plugin_name>")
    subtitle: ft.Text("<path> | <error_text если есть>", color=RED если ошибка)
    trailing: ft.Row([
        ft.IconButton(Icons.DELETE_OUTLINE,  # только для не-builtin
                      on_click=→ confirm_delete),
    ])
```

Встроенные плагины (builtin=True): чекбокс disabled (всегда включены), нет кнопки удаления.

Плагины с ошибкой загрузки: subtitle показывает текст ошибки красным цветом.

**Кнопка "Install from file...":** открывает `ft.FilePicker.pick_files()` с фильтром `.py, .zip`.

**Кнопка "Open plugins folder":** открывает директорию плагинов через `os.startfile()` (Windows) или `subprocess.run(['xdg-open', path])` (Linux).

### 3.9 Встроенные плагины в списке

При формировании списка — добавить builtin-плагины (из `api.inputs.peptides` и `api.reporting.reports`) как записи с `builtin=True`. Их имена берутся из зарегистрированных ключей registry на момент старта, отсекая те, что были загружены из файлов плагинов.

Порядок в списке: сначала встроенные, затем внешние плагины.

---

## 4. Логотип

### 4.1 Генерация файлов

Исходные файлы:
- `assets/logo.png` — вертикальный, 1892×2576, чёрный на прозрачном фоне
- `assets/logo_square.png` — квадратный, 2576×2576

Необходимо сгенерировать (командой `convert` из ImageMagick):

| Файл | Размер | Назначение |
|---|---|---|
| `assets/icons/icon_32.png` | 32×32 | иконка меню, мелкие элементы |
| `assets/icons/icon_64.png` | 64×64 | иконка в заголовках |
| `assets/icons/icon_128.png` | 128×128 | иконка приложения (средний) |
| `assets/icons/icon_256.png` | 256×256 | иконка приложения (крупный) |
| `assets/logo_header.png` | высота 80px (ширина пропорционально) | header стартового экрана |

Генерировать из `logo_square.png` (квадратный вариант — для иконок).  
`logo_header.png` — из вертикального `logo.png`, resize по высоте 80px.

Цвет фона иконок: прозрачный (сохранить PNG с alpha-каналом).

**Команды convert:**
```bash
convert assets/logo_square.png -resize 32x32 assets/icons/icon_32.png
convert assets/logo_square.png -resize 64x64 assets/icons/icon_64.png
convert assets/logo_square.png -resize 128x128 assets/icons/icon_128.png
convert assets/logo_square.png -resize 256x256 assets/icons/icon_256.png
convert assets/logo.png -resize x80 assets/logo_header.png
```

### 4.2 Интеграция в GUI

**Иконка приложения (`gui/app.py`):**

```python
self.page.window.icon = "assets/icons/icon_256.png"
```

**Стартовый экран (`gui/views/start_view.py`):**

Заменить текстовый заголовок "DASMixer" на изображение:

```python
ft.Image(
    src="assets/logo_header.png",
    fit=ft.ImageFit.CONTAIN,
    height=80,
)
```

> !!! Не заменить, дополнить. надпись должна оставаться, т.к. её нет на лого. 

Подзаголовок "Mass Spectrometry Data Integration Tool" — оставить как есть.

---

## 5. Затронутые файлы — итого

| Файл | Тип изменений |
|---|---|
| `api/config.py` → `dasmixer/api/config.py` | Новые поля: batch sizes, default_colors, plugin_states |
| `dasmixer/api/plugin_loader.py` | Новый файл: загрузка плагинов |
| `dasmixer/main.py` | Инициализация загрузки плагинов при старте |
| `dasmixer/gui/app.py` | Роутинг через `page.views`, пункт меню Settings/Plugins, иконка |
| `dasmixer/gui/views/settings_view.py` | Новый файл: view настроек |
| `dasmixer/gui/views/plugins_view.py` | Новый файл: view плагинов |
| `dasmixer/gui/views/start_view.py` | Замена текстового заголовка на логотип |
| `assets/icons/` | Новая директория с иконками |
| `assets/logo_header.png` | Новый файл: логотип для header |
| Все файлы с `from api.` / `from gui.` / `from cli.` | Исправление импортов на `from dasmixer.api.` и т.д. |

---

## 6. Открытые вопросы

### 6.1 Перезапуск плагинов без рестарта

Текущая спецификация требует перезапуска после установки плагина. Стоит ли в будущем реализовать горячую перезагрузку (повторный вызов `load_identification_plugins`)? Это сложнее из-за возможных коллизий в registry.

> !!! Давай оставим сейчас и до релиза без горячей перезагрузки. Установка плагинов - задача редкая, можно и перезапустить.

### 6.2 Конфликты имён плагинов

Если плагин пытается зарегистрировать имя, уже занятое встроенным модулем, `registry.add_identification_parser` выбрасывает `KeyError`. Нужно ли перехватывать это отдельно и показывать специфическое сообщение об ошибке ("Plugin name conflicts with built-in parser")?

> !!! Да, давай кидаться ошибками

### 6.3 Тема приложения

В `AppConfig` уже есть поле `theme: str = "light"`. Нужно ли добавить переключатель темы в `SettingsView` сейчас или оставить на будущее?

> !!! Да, давай добавим

### 6.4 Валидация batch sizes

При сохранении — проверять только `> 0`? Или задать верхний предел (например, 50000), чтобы предотвратить случайно введённые значения типа 999999999?

> !!! Давай не делать жесткую валидацию. НО: при batch_sie > 100000 выдавать предупреждение, что указан очень большой размер Batch, который может вызвать ошибку в работе при переполнении RAM. Вы точно уверены?
