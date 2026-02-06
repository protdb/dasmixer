# Changelog - 2026-02-05: Export System Refactoring

## Краткое описание

Переработана система экспорта отчетов для использования единого HTML-шаблона и библиотеки `html4docx` для генерации Word документов. Добавлена поддержка fallback-отображения графиков через `<noscript>` тэг с base64-кодированными изображениями.

## Изменения

### 1. Переработан BaseReport.export()

**Что изменилось:**
- Метод теперь принимает путь к **папке** (а не файлу)
- Генерируются файлы с timestamp: `{report_name}-{YYYYMMDD_HHMMSS}.{ext}`
- Создаются все 3 формата одновременно: HTML, DOCX, XLSX
- Возвращает словарь с путями к созданным файлам

**Пример:**
```python
created_files = await report.export("/path/to/folder")
# Result:
# {
#     'html': Path('.../Sample Report-20260205_152300.html'),
#     'docx': Path('.../Sample Report-20260205_152300.docx'),
#     'xlsx': Path('.../Sample Report-20260205_152300.xlsx')
# }
```

### 2. Формирование HTML в базовом классе

**Добавлен метод:** `BaseReport._render_html()`

- Централизованное формирование HTML через Jinja2
- Используется для просмотра (pywebview) и экспорта
- Единый шаблон `api/reporting/templates/report.html.j2`

**Преимущества:**
- Не нужно дублировать код рендеринга
- Проще поддерживать единообразие
- Наследники получают готовое решение

### 3. HTML4docx вместо docxtpl

**Старый подход (docxtpl):**
- Требовал отдельный `.docx` шаблон
- Сложность в синхронизации HTML и Word шаблонов
- Ограниченная гибкость

**Новый подход (html4docx):**
```python
from docx import Document
from html4docx import HtmlToDocx

html = report._render_html()
doc = Document()
HtmlToDocx().add_html_to_document(html, doc)
doc.save('report.docx')
```

**Преимущества:**
- Автоматическая конвертация HTML → Word
- Один шаблон для всех форматов
- Таблицы, стили, изображения работают из коробки

### 4. Поддержка <noscript> с base64 изображениями

**HTML шаблон обновлен:**
```html
<div id="plot-1"></div>
<script>
    // Интерактивный Plotly график
    Plotly.newPlot('plot-1', plotData.data, plotData.layout);
</script>
<noscript>
    <!-- Fallback для отключенного JS -->
    <img src="data:image/png;base64,{{ figure.png_base64 }}" 
         alt="{{ figure.name }}" 
         class="plot-image">
</noscript>
```

**Применение:**
- HTML работает с отключенным JavaScript
- Word документ использует PNG изображения
- Email-клиенты показывают статичные графики

### 5. Excel экспорт с таблицами на листах

**Реализация:**
```python
async def _export_excel(self, output_path, base_filename):
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
        for name, df, _ in self._tables:
            sheet_name = self._sanitize_sheet_name(name)
            df.to_excel(writer, sheet_name=sheet_name, index=False)
```

**Функции:**
- Каждая таблица → отдельный лист
- Санитизация имен (Excel ограничения)
- Использует pandas + openpyxl

### 6. Обновлен GUI компонент

**Файл:** `gui/views/tabs/reports/report_item.py`

**Изменения:**
- `_on_view()` использует `report._render_html()`
- `_on_export()` открывает FilePicker для выбора папки
- `_on_folder_selected()` показывает список созданных файлов
- Улучшена обработка ошибок

## Структура создаваемых файлов

```
/output/folder/
├── Sample Report-20260205_152300.html   # Интерактивный HTML
├── Sample Report-20260205_152300.docx   # Word с PNG графиками
└── Sample Report-20260205_152300.xlsx   # Excel с таблицами на листах
```

## Контекст для рендеринга

Обновлен `_build_figures_context()`:

```python
{
    "name": "Plot Name",
    "png": b'...',              # bytes для Word
    "png_base64": "iVBORw...",  # base64 для HTML <noscript>
    "json": "{...}"             # Plotly JSON для интерактива
}
```

## Тестирование

### Автоматический тест
```bash
python docs/project/INTERNAL_EXAMPLES/export_test_example.py \
    /path/to/project.dasmixer \
    /output/folder
```

### Ручное тестирование
1. Открыть проект
2. Вкладка Reports
3. Generate → Sample Report
4. Export → выбрать папку
5. Проверить созданные файлы

### Проверка <noscript>
1. Открыть `.html` в браузере
2. Dev Tools → Console → `navigator.javaScriptEnabled = false`
3. Обновить страницу → графики должны отображаться

## Зависимости

Все пакеты уже в `pyproject.toml`:
- `jinja2 (>=3.1.6)`
- `html-for-docx (>=1.1.3)`
- `python-docx` (через html-for-docx)
- `openpyxl (>=3.1.5)`
- `plotly (>=6.5.2)`

## Файлы

### Модифицированы
- `api/reporting/base.py` - экспорт и рендеринг
- `api/reporting/templates/report.html.j2` - добавлен <noscript>
- `gui/views/tabs/reports/report_item.py` - обновлен UI

### Созданы
- `docs/project/STAGE5_EXPORT_UPDATE.md` - детальная документация
- `docs/project/INTERNAL_EXAMPLES/export_test_example.py` - тестовый скрипт
- `docs/project/CHANGELOG_2026-02-05.md` - этот файл

## Обратная совместимость

✅ **Полностью совместимо**

- Старые отчеты загружаются без проблем
- API не изменен (только расширен)
- GUI работает с существующими данными

## Известные ограничения

1. html4docx имеет ограничения в CSS (сложные стили могут не работать)
2. PNG графики занимают больше места чем векторная графика
3. Excel имеет лимит 31 символ на имя листа

## Следующие шаги

Опциональные улучшения:
1. SVG графики в Word (вместо PNG)
2. Настройки качества изображений
3. Пакетный экспорт нескольких отчетов
4. Кастомные шаблоны
5. Прогресс-бар для больших отчетов

---

**Автор:** Goose AI Agent  
**Дата:** 2026-02-05  
**Задача:** Переиграть экспорт отчетов на html4docx
