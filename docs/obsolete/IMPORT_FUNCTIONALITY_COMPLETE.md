# Завершение функциональности импорта спектров

**Дата:** 2026-01-30  
**Статус:** ✅ Завершено

---

## Проблема

После исправления FilePicker API диалоги открывались корректно, но:
- ❌ Импорт файлов не выполнялся
- ❌ Не было выбора парсера (формата файла)
- ❌ Парсер был захардкожен как MGFParser

---

## Решение

### 1. Интеграция с Registry парсеров

Теперь используется `api.inputs.registry` для получения доступных парсеров:

```python
from api.inputs.registry import registry

# Получить все доступные парсеры спектров
spectra_parsers = registry.get_spectra_parsers()
# Возвращает: {'MGF': MGFParser, ...}

# Получить конкретный парсер
parser_class = registry.get_parser("MGF", "spectra")
parser = parser_class("file.mgf")
```

### 2. Dropdown выбора парсера

Добавлен выбор парсера в оба режима импорта:

#### Pattern Matching Dialog:
```python
parser_dropdown = ft.Dropdown(
    label="File format / Parser",
    options=[
        ft.dropdown.Option(key=name, text=f"{name} - {description}")
        for name, parser_class in spectra_parsers.items()
    ],
    value=parser_options[0].key
)
```

#### Single Files Config:
```python
# Общий парсер для всех файлов
parser_dropdown = ft.Dropdown(
    label="File Format / Parser",
    options=[...],
    value=parser_options[0].key
)
```

**Важно:** Используется `ft.dropdown.Option`, а не `ft.DropdownOption` (согласно последней документации Flet).

### 3. Рефакторинг функции импорта

**Было:** `import_mgf_files()` - жестко привязано к MGF

**Стало:** `import_spectra_files()` - универсальная функция

```python
async def import_spectra_files(
    self,
    file_list: list[tuple[Path, str]],
    subset_id: int,
    parser_name: str  # ← Новый параметр!
):
    """
    Import spectra files with any registered parser.
    
    Args:
        file_list: List of (file_path, sample_id) tuples
        subset_id: Group ID to assign samples
        parser_name: Name of parser from registry (e.g., "MGF")
    """
    # Получить класс парсера из registry
    parser_class = registry.get_parser(parser_name, "spectra")
    
    # Создать экземпляр парсера
    parser = parser_class(str(file_path))
    
    # Валидация
    is_valid = await parser.validate()
    if not is_valid:
        # Показать ошибку
        return
    
    # Импорт батчами
    async for batch in parser.parse_batch(batch_size=1000):
        await self.project.add_spectra_batch(spectra_file_id, batch)
```

### 4. Улучшенный Progress Dialog

Добавлены дополнительные детали прогресса:

```python
progress_dialog = ft.AlertDialog(
    title=ft.Text("Importing Spectra"),
    content=ft.Column([
        progress_text,         # Основной текст
        progress_bar,          # Прогресс-бар
        progress_details       # Детали: "Imported 1500 spectra (batch 2)..."
    ])
)
```

Показывает:
- Текущий файл (N из M)
- Число импортированных спектров
- Номер текущего батча

### 5. Обработка ошибок

Добавлена валидация файлов и обработка исключений:

```python
# Валидация формата
is_valid = await parser.validate()
if not is_valid:
    # Показать ошибку и остановить импорт
    return

# Обработка исключений
try:
    # ... импорт
except Exception as ex:
    import traceback
    error_details = traceback.format_exc()
    print(f"Import error: {error_details}")  # В консоль
    
    # Пользователю
    self.page.snack_bar = ft.SnackBar(
        content=ft.Text(f"Import error: {str(ex)}"),
        bgcolor=ft.Colors.RED_400
    )
```

---

## Изменения в коде

### `gui/views/tabs/samples_tab.py`

#### Добавлены импорты:
```python
from api.inputs.registry import registry
```

#### Изменённые методы:

**1. `show_import_pattern_dialog()`**
- ✅ Добавлен `parser_dropdown` с выбором парсера из registry
- ✅ Парсер передаётся в `import_spectra_files()`

**2. `show_single_files_config()`**
- ✅ Добавлен `parser_dropdown` (общий для всех файлов)
- ✅ Парсер передаётся в `import_spectra_files()`

**3. `import_mgf_files()` → `import_spectra_files()`**
- ✅ Переименован для универсальности
- ✅ Добавлен параметр `parser_name: str`
- ✅ Динамическое получение парсера из registry
- ✅ Валидация файла перед импортом
- ✅ Улучшенный progress dialog с деталями
- ✅ Подсчёт общего числа спектров
- ✅ Обработка ошибок с traceback

---

## Тестирование

### Проверено:

✅ **Получение парсеров из registry**
```python
spectra_parsers = registry.get_spectra_parsers()
# {'MGF': <class 'api.inputs.spectra.mgf.MGFParser'>}
```

✅ **Dropdown заполняется корректно**
- Отображает доступные парсеры
- Первый парсер выбран по умолчанию

✅ **Импорт MGF файлов**
- Файлы парсятся корректно
- Спектры сохраняются в БД
- Progress dialog обновляется
- Показывается число спектров

✅ **Валидация файлов**
- Некорректные файлы отклоняются
- Показывается сообщение об ошибке

✅ **Обработка ошибок**
- Исключения логируются в консоль
- Пользователю показывается понятное сообщение

---

## Архитектура решения

### Диаграмма потока данных:

```
User clicks "Import Spectra"
    ↓
Select mode (Single / Pattern)
    ↓
Select files / folder + pattern
    ↓
Choose parser from Dropdown ← registry.get_spectra_parsers()
    ↓
Configure samples + groups
    ↓
Click "Import"
    ↓
import_spectra_files(files, subset_id, parser_name)
    ↓
    ├→ Get parser class: registry.get_parser(parser_name, "spectra")
    ├→ Create parser instance: parser_class(file_path)
    ├→ Validate: parser.validate()
    └→ Import batches: parser.parse_batch()
        ↓
    Save to DB: project.add_spectra_batch()
```

### Преимущества архитектуры:

1. **Расширяемость:** Новые парсеры добавляются только в registry
2. **Универсальность:** Один код для всех форматов
3. **Безопасность:** Валидация перед импортом
4. **UX:** Пользователь видит доступные форматы
5. **Отладка:** Подробные ошибки в консоли

---

## Будущие улучшения

### Рекомендации для развития:

1. **Автоопределение формата**
   - По расширению файла
   - По содержимому (magic bytes)
   - Попытка парсинга всеми парсерами

2. **Предпросмотр спектров**
   - Показать первые N спектров перед импортом
   - График example spectrum

3. **Отмена импорта**
   - Кнопка "Cancel" в progress dialog
   - Использовать asyncio.Task.cancel()

4. **Параллельный импорт**
   - Импорт нескольких файлов одновременно
   - Использовать asyncio.gather()

5. **Кэширование парсеров**
   - Переиспользовать parser instance
   - Улучшить производительность

---

## API для разработчиков

### Добавление нового парсера

1. Создать класс парсера, наследующий `SpectralDataParser`:

```python
# api/inputs/spectra/mzml.py
from .base import SpectralDataParser

class MZMLParser(SpectralDataParser):
    async def validate(self) -> bool:
        # Validate MZML format
        pass
    
    async def parse_batch(self, batch_size=1000):
        # Parse MZML data
        pass
```

2. Зарегистрировать в `api/inputs/__init__.py`:

```python
def register_parsers():
    # ... existing parsers
    
    try:
        from .spectra.mzml import MZMLParser
        registry.add_spectra_parser("MZML", MZMLParser)
    except ImportError:
        pass
```

3. Парсер автоматически появится в UI dropdown! 🎉

---

## Заключение

Функциональность импорта спектров полностью реализована и протестирована:

✅ Интеграция с registry парсеров  
✅ Выбор формата через Dropdown  
✅ Универсальная функция импорта  
✅ Валидация файлов  
✅ Детальный прогресс  
✅ Обработка ошибок  
✅ Расширяемая архитектура  

**Готово к использованию в Production!** 🚀

---

**Автор:** Goose AI  
**Дата:** 2026-01-30  
**Версия:** 1.0
