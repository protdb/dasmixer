# Stage 5: Export System Update

## Обзор изменений

Обновлена система экспорта отчетов для использования `html4docx` вместо `docxtpl` и улучшен процесс экспорта.

## Ключевые изменения

### 1. Формирование HTML в базовом классе

**Файл:** `api/reporting/base.py`

Добавлен метод `_render_html()` в базовый класс `BaseReport`:
- Формирует HTML используя Jinja2 шаблон
- Доступен для всех наследников
- Используется как для просмотра, так и для экспорта

```python
def _render_html(self) -> str:
    """Render report to HTML string."""
    from jinja2 import Environment, FileSystemLoader
    
    template_dir = Path(__file__).parent / 'templates'
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template('report.html.j2')
    
    context = self.get_context()
    html = template.render(**context)
    
    return html
```

### 2. Добавлен `<noscript>` с base64 изображениями

**Файл:** `api/reporting/templates/report.html.j2`

В HTML-шаблон добавлена поддержка отображения графиков при отключенном JavaScript:

```html
<div id="plot-{{ loop.index }}"></div>
<script>
    var plotData = {{ figure.json | safe }};
    Plotly.newPlot('plot-{{ loop.index }}', plotData.data, plotData.layout);
</script>
<noscript>
    <img src="data:image/png;base64,{{ figure.png_base64 }}" 
         alt="{{ figure.name }}" 
         class="plot-image">
</noscript>
```

### 3. Обновлен метод `export()`

**Файл:** `api/reporting/base.py`

Метод `export()` теперь:

#### Принимает путь к папке
```python
async def export(self, output_path: Path | str) -> dict[str, Path]:
    """
    Export report to files.
    
    Args:
        output_path: Path to folder for saving
        
    Returns:
        dict: Paths to created files
    """
```

#### Создает файлы с timestamp в имени
Формат имени: `{report_name}-{YYYYMMDD_HHMMSS}.{extension}`

Пример:
- `Sample Report-20260205_152300.html`
- `Sample Report-20260205_152300.docx`
- `Sample Report-20260205_152300.xlsx`

#### Экспорт в Word через html4docx

```python
async def _export_word(self, output_path: Path, base_filename: str) -> Path:
    """Export to Word using html4docx."""
    from docx import Document
    from html4docx import HtmlToDocx
    
    # Render HTML
    html = self._render_html()
    
    # Create Word document
    doc = Document()
    html_converter = HtmlToDocx()
    html_converter.add_html_to_document(html, doc)
    
    # Save
    output_file = output_path / f"{base_filename}.docx"
    doc.save(str(output_file))
    
    return output_file
```

**Преимущества html4docx:**
- Автоматическая конвертация HTML в Word
- Поддержка таблиц, стилей, изображений
- Единый HTML-шаблон для всех форматов
- Не требуется отдельный docx-шаблон

#### Экспорт в Excel с таблицами на листах

```python
async def _export_excel(self, output_path: Path, base_filename: str) -> Path:
    """Export tables to Excel with each table on separate sheet."""
    output_file = output_path / f"{base_filename}.xlsx"
    
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        for name, df, _ in self._tables:
            sheet_name = self._sanitize_sheet_name(name)
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    
    return output_file
```

**Функции:**
- Каждая таблица из отчета на отдельном листе
- Имена листов соответствуют именам таблиц (с санитизацией для Excel)
- Используется `openpyxl` через pandas
- Если таблиц нет - создается пустой файл

#### Санитизация имен листов Excel

```python
@staticmethod
def _sanitize_sheet_name(name: str) -> str:
    """
    Sanitize sheet name for Excel.
    
    Excel sheet names:
    - Max 31 characters
    - Cannot contain: \ / * ? : [ ]
    """
    invalid_chars = ['\\', '/', '*', '?', ':', '[', ']']
    sanitized = name
    for char in invalid_chars:
        sanitized = sanitized.replace(char, '_')
    
    if len(sanitized) > 31:
        sanitized = sanitized[:31]
    
    return sanitized
```

### 4. Обновлен контекст для рендеринга

**Файл:** `api/reporting/base.py`

Метод `_build_figures_context()` теперь добавляет base64-кодированные PNG:

```python
def _build_figures_context(self) -> list[dict]:
    """Build figures for context."""
    figures = []
    if self._plots:
        for name, fig in self._plots:
            # PNG for Word and noscript
            png_bytes = fig.to_image(format='png')
            png_base64 = base64.b64encode(png_bytes).decode('utf-8')
            
            # JSON for HTML
            plotly_json = fig.to_json()
            
            figures.append({
                "name": name,
                "png": png_bytes,           # Для Word
                "png_base64": png_base64,   # Для HTML <noscript>
                "json": plotly_json          # Для интерактивного Plotly
            })
    
    return figures
```

### 5. Обновлен GUI компонент

**Файл:** `gui/views/tabs/reports/report_item.py`

#### Использование _render_html() для просмотра
```python
async def _on_view(self, e):
    """View report."""
    report = await self.report_class.load_from_db(
        self.project,
        self.current_report_id
    )
    
    # Render HTML
    html = report._render_html()
    
    # Show in pywebview
    ReportViewer.show_report(html, title=f"{self.report_class.name}")
```

#### Улучшен FilePicker для экспорта
```python
def __init__(self, ...):
    # File picker for export
    self.file_picker = ft.FilePicker(
        on_result=self._on_folder_selected
    )

async def _on_export(self, e):
    """Export report."""
    self.file_picker.get_directory_path(
        dialog_title="Select Export Folder"
    )

async def _on_folder_selected(self, e: ft.FilePickerResultEvent):
    """Handle folder selection."""
    if e.path:
        report = await self.report_class.load_from_db(...)
        created_files = await report.export(Path(e.path))
        
        # Show success with file list
        files_list = "\n".join([f"- {path.name}" for path in created_files.values()])
        self._show_success(f"Report exported:\n{files_list}")
```

## Архитектура экспорта

```
BaseReport.export(output_folder)
    │
    ├─> _render_html()
    │   └─> Jinja2 template + context
    │       └─> HTML string
    │
    ├─> _export_html(folder, filename)
    │   └─> Сохранение HTML файла
    │
    ├─> _export_word(folder, filename)
    │   ├─> _render_html()
    │   ├─> html4docx конвертация
    │   └─> Сохранение .docx
    │
    └─> _export_excel(folder, filename)
        ├─> Итерация по таблицам
        ├─> Sanitize имен листов
        └─> pandas.to_excel()
```

## Пример использования

### Python API
```python
# Загрузить отчет из БД
report = await SampleReport.load_from_db(project, report_id=1)

# Экспортировать в папку
created_files = await report.export("/path/to/output")

# Результат
# {
#     'html': Path('/path/to/output/Sample Report-20260205_152300.html'),
#     'docx': Path('/path/to/output/Sample Report-20260205_152300.docx'),
#     'xlsx': Path('/path/to/output/Sample Report-20260205_152300.xlsx')
# }
```

### GUI
1. Сгенерировать отчет кнопкой "Generate"
2. Выбрать сохраненный отчет из dropdown
3. Нажать "Export"
4. Выбрать папку для сохранения
5. Получить 3 файла: HTML, DOCX, XLSX

## Зависимости

Все необходимые пакеты уже в `pyproject.toml`:
- `jinja2` - HTML templating
- `html-for-docx` - HTML to Word conversion
- `python-docx` - Word document creation
- `openpyxl` - Excel support for pandas
- `plotly` - Chart generation
- `pandas` - Data handling

## Тестирование

### Проверка экспорта
1. Запустить приложение
2. Открыть проект с данными
3. Перейти на вкладку Reports
4. Сгенерировать Sample Report
5. Экспортировать отчет
6. Проверить созданные файлы:
   - HTML должен открываться в браузере с интерактивными графиками
   - DOCX должен открываться в Word с таблицами и графиками (PNG)
   - XLSX должен содержать таблицы на отдельных листах

### Проверка <noscript>
1. Открыть экспортированный HTML в браузере
2. Отключить JavaScript
3. Обновить страницу
4. Графики должны отображаться как статичные изображения

## Известные ограничения

1. **html4docx** может иметь ограничения в преобразовании сложных CSS стилей
2. Размер Excel файла зависит от количества строк в таблицах
3. PNG графики в Word занимают больше места чем векторная графика

## Будущие улучшения

1. **Векторная графика в Word** - экспорт SVG вместо PNG
2. **Настройки качества PNG** - управление размером изображений
3. **Пакетный экспорт** - экспорт нескольких отчетов в один документ
4. **Кастомизация шаблонов** - пользовательские HTML/Word шаблоны
5. **Прогресс-бар** - отображение прогресса при экспорте больших отчетов

## Файлы изменены

### Модифицированы
- `api/reporting/base.py`
- `api/reporting/templates/report.html.j2`
- `gui/views/tabs/reports/report_item.py`

### Созданы
- `docs/project/STAGE5_EXPORT_UPDATE.md` (этот документ)

## Дата изменений

2026-02-05
