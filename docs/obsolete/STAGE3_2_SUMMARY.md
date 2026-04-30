# Резюме этапа 3.2: Базовый функционал GUI и CLI

## Статус: В ПРОЦЕССЕ (70% завершено)

Дата: 2026-01-29

---

## Что реализовано

### 1. Конфигурация и инфраструктура ✅

#### `api/config.py`
Системная конфигурация приложения с автосохранением в:
- Windows: `%APPDATA%/dasmixer/config.json`
- Linux: `~/.config/dasmixer/config.json`
- macOS: `~/Library/Application Support/dasmixer/config.json`

**Возможности:**
- Хранение последних использованных путей
- Список последних 10 проектов
- Настройки UI (расширяемо)

#### `api/inputs/__init__.py`
Автоматическая регистрация парсеров при импорте модуля.
- Регистрируется MGF парсер
- Готово к добавлению плагинов в будущем

#### `main.py`
Единая точка входа для GUI и CLI.

**Использование:**
```bash
python main.py                        # GUI
python main.py project.dasmix          # Открыть в GUI
python main.py project.dasmix create   # CLI: создать проект
python main.py project.dasmix subset add --name "Test"  # CLI: команда
```

---

### 2. CLI команды ✅

#### Создание проекта (`cli/commands/project.py`)
```bash
python main.py project.dasmix create
```
- Создаёт пустой проект
- Автоматически добавляет группу "Control"
- Сохраняет в recent projects

#### Управление группами (`cli/commands/subset.py`)
```bash
# Добавить
python main.py project.dasmix subset add --name "Treatment" --color "#FF5733"

# Удалить
python main.py project.dasmix subset delete --name "Treatment"

# Список
python main.py project.dasmix subset list
```

#### Импорт данных (`cli/commands/import_data.py`)

**Импорт спектров (MGF):**

Режим 1: По шаблону (множество файлов)
```bash
python main.py project.dasmix import mgf-pattern \
    --folder /path/to/data \
    --pattern "*.mgf" \
    --id-pattern "{id}_run*.mgf" \
    --group Control
```

Режим 2: Одиночный файл
```bash
python main.py project.dasmix import mgf-file \
    --file /path/to/sample1.mgf \
    --sample-id "Sample1" \
    --group Control
```

**Импорт идентификаций:**
- Заглушки `ident-pattern` и `ident-file`
- Будут реализованы после добавления парсеров идентификаций

---

### 3. GUI компоненты ✅

#### `gui/components/plotly_viewer.py`
Универсальный компонент для отображения Plotly графиков.

**Возможности:**
- Отображение статичного PNG в основном UI
- Кнопка "Interactive Mode" → запуск pywebview в отдельном процессе
- Обработка ошибок рендеринга

**Использование:**
```python
from gui.components.plotly_viewer import PlotlyViewer
import plotly.express as px

fig = px.scatter(x=[1,2,3], y=[4,5,6])
viewer = PlotlyViewer(fig, title="My Chart", width=800, height=600)
page.add(viewer)
```

#### `gui/components/progress_dialog.py`
Модальный диалог с прогресс-баром.

**Использование:**
```python
from gui.components.progress_dialog import ProgressDialog

dialog = ProgressDialog("Importing files...")
page.dialog = dialog
dialog.open = True

for i, item in enumerate(items):
    dialog.update_progress(i / len(items), f"Processing {i+1}/{len(items)}")
    # process item

dialog.open = False
```

---

### 4. GUI приложение ✅

#### `gui/app.py`
Главное приложение с меню и роутингом.

**Возможности:**
- Создание/открытие/закрытие проектов
- Меню приложения (File, Параметры, Справка - базовые)
- Автоматическое открытие проекта из командной строки
- Интеграция с системной конфигурацией

#### `gui/views/start_view.py`
Стартовый экран приложения.

**Содержит:**
- Заголовок приложения
- Кнопки "Create New Project" и "Open Project"
- Список последних 10 проектов (кликабельный)

#### `gui/views/project_view.py`
Основное рабочее пространство с вкладками.

**Вкладки:**
1. **Samples** - Управление образцами и группами
2. **Peptides** - Просмотр идентификаций (базовая версия)
3. **Proteins** - Заглушка (Stage 4)
4. **Analysis** - Заглушка (Stage 5)

---

### 5. GUI вкладки

#### `gui/views/tabs/samples_tab.py` (Базовая версия ✅)

**Реализовано:**
- Отображение списка групп
- Подсчёт образцов в каждой группе
- Диалог добавления группы (название, описание, цвет)
- Кнопки импорта (пока заглушки, работает через CLI)

**Использование:**
```python
# Открыть проект в GUI
python main.py project.dasmix

# Перейти на вкладку Samples
# Нажать "Add Group"
# Заполнить форму
```

#### `gui/views/tabs/peptides_tab.py` (Заглушка ✅)
Базовая структура для:
- Поиска идентификаций (по seq_no/scans/sequence)
- Отображения результатов поиска
- Визуализации графиков разметки ионов

#### `gui/views/tabs/proteins_tab.py` и `analysis_tab.py` (Заглушки ✅)
Информативные заглушки с описанием будущего функционала.

---

## Что НЕ реализовано (требует доработки)

### ⚠️ КРИТИЧНО: Метод в Project класс

**Файл:** `api/project/project.py`

**Что добавить:** Метод `get_spectra_idlist`

**Где:** После метода `get_spectrum_full`, перед комментарием `# Identification file operations`

**Инструкция:** См. файлы:
- `api/project/project_patch.py`
- `api/project/project_spectra_mapping.py`
- `STAGE3_2_TODO.md`

**Код готов, нужно только вставить в правильное место!**

---

### Неполная реализация GUI

1. **Диалог импорта данных** (`gui/dialogs/import_dialog.py`) - НЕ создан
   - Нужен универсальный диалог для спектров и идентификаций
   - Два режима: pattern-based и single file
   - Интеграция с `utils/seek_files.py`
   - Прогресс-бар импорта

2. **Таблица образцов** в `samples_tab.py`
   - Сейчас только placeholder
   - Нужна полноценная DataTable с:
     - Колонки: Sample Name, MGF File, Tools, Group
     - Копирование пути по клику
     - Выпадающий список для смены группы
     - Массовые операции (назначение группы, удаление)

3. **Удаление групп** в `samples_tab.py`
   - Кнопка есть, функционал не реализован
   - Нужен выбор группы из списка
   - Подтверждение удаления

4. **Поиск и отображение идентификаций** в `peptides_tab.py`
   - Структура есть, логика не реализована
   - Нужна интеграция с Project API
   - Таблица результатов (DataTable)

5. **График разметки ионов** в `peptides_tab.py`
   - Интеграция с `api/spectra/plot_matches.py`
   - Использование `PlotlyViewer`
   - Загрузка полных данных спектра

---

## Структура файлов

```
dasmixer/
├── main.py                                 ✅ Создан
├── api/
│   ├── config.py                          ✅ Создан
│   ├── inputs/
│   │   └── __init__.py                    ✅ Обновлён
│   └── project/
│       ├── project.py                     ⚠️ Требует патча
│       ├── project_patch.py               ✅ Инструкция
│       └── project_spectra_mapping.py     ✅ Готовый код
├── cli/
│   └── commands/
│       ├── __init__.py                    ✅ Создан
│       ├── project.py                     ✅ Создан
│       ├── subset.py                      ✅ Создан
│       └── import_data.py                 ✅ Создан
├── gui/
│   ├── app.py                             ✅ Создан
│   ├── components/
│   │   ├── __init__.py                    ✅ Создан
│   │   ├── plotly_viewer.py               ✅ Создан
│   │   └── progress_dialog.py             ✅ Создан
│   ├── dialogs/                           ❌ Не создана
│   │   └── import_dialog.py               ❌ Не создан
│   └── views/
│       ├── __init__.py                    ✅ Создан
│       ├── start_view.py                  ✅ Создан
│       ├── project_view.py                ✅ Создан
│       └── tabs/
│           ├── __init__.py                ✅ Создан
│           ├── samples_tab.py             🔄 Базовая версия
│           ├── peptides_tab.py            🔄 Заглушка
│           ├── proteins_tab.py            ✅ Заглушка
│           └── analysis_tab.py            ✅ Заглушка
├── docs/project/
│   └── STAGE3_2_SUMMARY.md                ✅ Этот файл
├── STAGE3_2_TODO.md                       ✅ Создан
└── test_project.dasmix                    (создаётся при тестировании)
```

**Легенда:**
- ✅ Полностью реализовано
- 🔄 Частично реализовано
- ⚠️ Требует доработки
- ❌ Не создано

---

## Тестирование

### Минимальный тест CLI

```bash
# 1. Создать проект
python main.py test_project.dasmix create

# Ожидаем:
# ✓ Created project: test_project.dasmix
# ✓ Added default group: Control

# 2. Добавить группу
python main.py test_project.dasmix subset add --name "Treatment" --color "#FF5733"

# Ожидаем:
# ✓ Added group: Treatment (id=2)

# 3. Список групп
python main.py test_project.dasmix subset list

# Ожидаем:
# Comparison Groups:
# ===========================================
# Control (ID: 1)
#   Color: #3B82F6
#   Samples: 0
#
# Treatment (ID: 2)
#   Color: #FF5733
#   Samples: 0

# 4. Импорт MGF (требует тестовый файл)
python main.py test_project.dasmix import mgf-file \
    --file /path/to/test.mgf \
    --sample-id "TestSample" \
    --group Control
```

### Минимальный тест GUI

```bash
# 1. Запуск
python main.py

# Проверить:
# - Отображается стартовый экран
# - Кнопки "Create New Project" и "Open Project"
# - Список недавних проектов (если есть)

# 2. Создать проект
# - Нажать "Create New Project"
# - Выбрать место сохранения
# - Проверить что открылась вкладка Samples

# 3. Проверить группы
# - В Samples должна быть группа "Control"
# - Нажать "Add Group"
# - Заполнить форму
# - Проверить что группа добавилась

# 4. Закрыть и открыть
# - Меню → Close Project
# - Должен вернуться стартовый экран
# - В списке недавних должен быть проект
# - Кликнуть на проект
# - Должен открыться
```

---

## Известные проблемы

1. **Импорт через GUI не работает** - используйте CLI
2. **Таблица образцов не отображается** - показывается placeholder
3. **Удаление групп не работает** - функционал не реализован
4. **Поиск идентификаций не работает** - нет данных для поиска
5. **Графики не отображаются** - интеграция не завершена

---

## Следующие шаги (приоритет)

### СРОЧНО
1. ⚠️ **Добавить метод `get_spectra_idlist` в Project** - инструкции готовы
2. Протестировать CLI на реальных данных
3. Протестировать GUI (создание/открытие проектов)

### ВАЖНО
4. Создать диалог импорта (`gui/dialogs/import_dialog.py`)
5. Реализовать таблицу образцов в `samples_tab.py`
6. Реализовать удаление групп
7. Доделать поиск идентификаций в `peptides_tab.py`
8. Интегрировать графики разметки ионов

### ЖЕЛАТЕЛЬНО
9. Написать интеграционные тесты для CLI
10. Добавить обработку ошибок
11. Улучшить UX (сообщения, валидация)

---

## Зависимости

Все зависимости уже установлены в `pyproject.toml`:
- ✅ `flet` - GUI
- ✅ `typer` - CLI
- ✅ `plotly` + `kaleido` - графики
- ✅ `pywebview` - интерактивный режим
- ✅ `pydantic-settings` - конфигурация
- ✅ `aiosqlite` - асинхронная БД

---

## Оценка завершённости

| Компонент | Статус | %  |
|-----------|--------|-----|
| API (config, registry) | ✅ Готово | 95% |
| CLI commands | ✅ Готово | 90% |
| GUI components | ✅ Готово | 100% |
| GUI app & routing | ✅ Готово | 100% |
| GUI Samples tab | 🔄 Частично | 40% |
| GUI Peptides tab | 🔄 Частично | 20% |
| GUI dialogs | ❌ Не начато | 0% |
| Integration | 🔄 Частично | 60% |
| Testing | ❌ Не начато | 0% |

**Общая готовность этапа 3.2: ~70%**

---

## Рекомендации

1. **Первым делом** - добавить метод в Project (5 минут)
2. **Затем** - протестировать CLI на реальных данных
3. **После** - доделать GUI импорт и таблицы
4. **В конце** - тестирование и документация

---

## Контакты и вопросы

При возникновении вопросов или проблем:
1. Проверьте `STAGE3_2_TODO.md`
2. Проверьте `docs/project/spec/STAGE3_2_SPEC.md`
3. Проверьте логи в консоли

---

**Дата создания:** 2026-01-29  
**Автор:** Goose (AI Assistant)  
**Версия:** 1.0
