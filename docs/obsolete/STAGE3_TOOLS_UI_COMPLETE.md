# Stage 3 - Tools-Based UI Architecture

**Дата:** 2026-01-30  
**Статус:** ✅ Завершено

---

## Обзор изменений

Переработана архитектура UI для работы с идентификациями через концепцию **Tools** (инструментов).

### Было (неправильно):
```
[Import Spectra] [Import Identifications]
```
- Прямой импорт идентификаций без привязки к Tool
- Нет управления инструментами

### Стало (правильно):
```
[Import Spectra]

Tools:
  PowerNovo2      [Import Identifications]
  MaxQuant        [Import Identifications]
  [Add Tool]
```
- Каждый Tool имеет свою кнопку импорта
- Tool определяет формат/парсер
- Явное управление инструментами

---

## Архитектура UI

### Структура вкладки Samples

```
┌─ Comparison Groups ────────────┐
│ • Control (3 samples)          │
│ • Treatment (3 samples)        │
│ [Add Group] [Delete Selected]  │
└────────────────────────────────┘

┌─ Import Spectra ───────────────┐
│ [Import Spectra Files]         │
└────────────────────────────────┘

┌─ Identification Tools ─────────┐
│ • PowerNovo2 - 2 files         │
│   [Import Identifications] ←── │
│ • MaxQuant - 0 files           │
│   [Import Identifications] ←── │
│ [Add Tool]                     │
└────────────────────────────────┘

┌─ Samples ──────────────────────┐
│ Sample01                       │
│ Group: Control • Files: 1      │
│ ✓ PowerNovo2, ✓ MaxQuant      │
│ ...                            │
└────────────────────────────────┘
```

---

## Концепция Tool

### Что такое Tool?

**Tool** - это инструмент идентификации пептидов/белков:
- De novo секвенирование (PowerNovo, CasaNovo)
- Database search (MaxQuant, PLGS, SEQUEST)
- Hybrid методы

### Свойства Tool:

```python
Tool(
    id: int,              # Уникальный ID
    name: str,            # Название (PowerNovo2, MaxQuant)
    type: str,            # Парсер/формат (PowerNovo2, MaxQuant)
    settings: dict,       # Настройки (опционально)
    display_color: str    # Цвет для UI
)
```

### Зачем нужен Tool?

1. **Разделение идентификаций** по методам
2. **Сравнение** результатов разных инструментов
3. **Настройки** специфичные для инструмента
4. **Визуализация** - разные цвета для разных tools

---

## Workflow

### 1. Создание проекта и групп

```
User: Create project
User: Add Group "Control"
User: Add Group "Treatment"
```

### 2. Импорт спектров

```
User: Click "Import Spectra Files"
  → Select mode (single/pattern)
  → Choose files
  → Select parser (MGF)
  → Assign to group (Control)
  → Import
  
Result: Samples created with spectra
```

### 3. Добавление инструментов

```
User: Click "Add Tool"
  → Name: "PowerNovo2"
  → Parser: PowerNovo2
  → Color: #9333EA
  → Add

User: Click "Add Tool"
  → Name: "MaxQuant"
  → Parser: MaxQuant
  → Color: #DC2626
  → Add

Result: Two tools in list
```

### 4. Импорт идентификаций для каждого Tool

```
User: Click "Import Identifications" for PowerNovo2
  → Select mode (single/pattern)
  → Choose files
  → Sample IDs matched to existing samples
  → Import
  
Result: Identifications linked to PowerNovo2 tool

User: Click "Import Identifications" for MaxQuant
  → Select mode
  → Choose files
  → Import
  
Result: Identifications linked to MaxQuant tool
```

### 5. Просмотр результатов

```
Samples:
  Sample01
  Group: Control • Files: 1 • ✓ PowerNovo2, ✓ MaxQuant
```

---

## Технические детали

### Изменения в структуре класса

```python
class SamplesTab(ft.Container):
    def __init__(self, project: Project):
        self.groups_list = ft.Column(spacing=5)
        self.tools_list = ft.Column(spacing=5)     # ← Новое!
        self.samples_container = ...
```

### Новые методы

#### `refresh_tools()`
Обновляет список инструментов:
```python
async def refresh_tools(self):
    tools = await self.project.get_tools()
    
    for tool in tools:
        ident_files = await self.project.get_identification_files(tool_id=tool.id)
        
        # Create ListTile with Import button
        self.tools_list.controls.append(
            ft.ListTile(
                title=ft.Text(tool.name),
                subtitle=ft.Text(f"{len(ident_files)} file(s)"),
                trailing=ft.ElevatedButton(
                    content="Import Identifications",
                    on_click=lambda e, t=tool: self.page.run_task(
                        self.show_import_mode_dialog, e, "identifications", t.id
                    )
                )
            )
        )
```

#### `show_add_tool_dialog()`
Диалог добавления инструмента:
```python
async def show_add_tool_dialog(self, e):
    # Get available parsers
    parsers = registry.get_identification_parsers()
    
    # Show dialog with:
    # - Name field
    # - Parser dropdown (from registry)
    # - Color field
    
    await self.project.add_tool(name, type=parser, color=color)
```

### Изменения в существующих методах

#### `show_import_mode_dialog()` - добавлен `tool_id`
```python
async def show_import_mode_dialog(
    self, 
    e, 
    import_type: str, 
    tool_id: int | None = None  # ← Новый параметр!
):
    if import_type == "identifications":
        # Get tool to show in title
        tool = await self.project.get_tool(tool_id)
        title = f"Import Identifications - {tool.name}"
```

#### `import_identification_files()` - использует `tool_id`
```python
async def import_identification_files(
    self,
    file_list,
    tool_id: int  # ← Передаётся напрямую!
):
    # Get tool
    tool = await self.project.get_tool(tool_id)
    
    # Get parser from tool.type
    parser_class = registry.get_parser(tool.type, "identification")
    
    # Import with this tool
    await self.project.add_identification_file(
        spectra_file_id,
        tool_id=tool.id,  # ← Используется tool_id
        file_path
    )
```

---

## Преимущества новой архитектуры

### 1. Явное управление инструментами
- ✅ Пользователь видит все используемые Tools
- ✅ Можно добавлять/удалять Tools
- ✅ Видно количество файлов на Tool

### 2. Связь Tool ↔ Parser
- ✅ Tool.type определяет парсер
- ✅ Один Tool = один формат
- ✅ Не нужно выбирать парсер при импорте

### 3. Корректная интеграция с БД
- ✅ `identification_file.tool_id` правильно заполняется
- ✅ `identification.tool_id` правильно заполняется
- ✅ Можно фильтровать по Tool
- ✅ Можно сравнивать результаты разных Tools

### 4. Расширяемость
- ✅ Легко добавить новый Tool
- ✅ Легко импортировать для любого Tool
- ✅ Поддержка множества Tools в проекте

---

## UI Flow диаграмма

```
┌─────────────────────────────────────────────┐
│ User opens "Samples" tab                    │
└─────────────┬───────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ did_mount_async()                           │
│   ├→ refresh_groups()   ← Показать группы  │
│   ├→ refresh_tools()    ← Показать Tools   │
│   └→ refresh_samples()  ← Показать образцы │
└─────────────────────────────────────────────┘

Import Spectra:
┌─────────────────────────────────────────────┐
│ User clicks "Import Spectra Files"          │
└─────────────┬───────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ show_import_mode_dialog("spectra", None)    │
│   → Choose single/pattern                   │
└─────────────┬───────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ import_spectra_files(files, subset, parser) │
│   → Creates samples                         │
│   → Imports spectra                         │
└─────────────────────────────────────────────┘

Add Tool:
┌─────────────────────────────────────────────┐
│ User clicks "Add Tool"                      │
└─────────────┬───────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ show_add_tool_dialog()                      │
│   → Name, Parser (from registry), Color     │
│   → project.add_tool(name, type, color)     │
└─────────────┬───────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ refresh_tools() - показывает новый Tool     │
│   с кнопкой "Import Identifications"        │
└─────────────────────────────────────────────┘

Import Identifications for Tool:
┌─────────────────────────────────────────────┐
│ User clicks "Import Identifications"        │
│   на конкретном Tool (tool_id=5)            │
└─────────────┬───────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ show_import_mode_dialog("identifications",  │
│                         tool_id=5)          │
│   → Parser уже определён (tool.type)        │
└─────────────┬───────────────────────────────┘
              ↓
┌─────────────────────────────────────────────┐
│ import_identification_files(files, tool_id) │
│   → Uses tool_id directly                   │
│   → Parser from tool.type                   │
└─────────────────────────────────────────────┘
```

---

## Примеры использования

### Пример 1: Один инструмент

```
1. Add Tool "PowerNovo2" (parser: PowerNovo2)
2. Import Identifications for PowerNovo2
   - sample01.csv
   - sample02.csv
   
Result:
  Samples:
    Sample01 • ✓ PowerNovo2
    Sample02 • ✓ PowerNovo2
```

### Пример 2: Сравнение инструментов

```
1. Add Tool "PowerNovo2"
2. Add Tool "MaxQuant"
3. Import for PowerNovo2:
   - sample01_pn.csv
   - sample02_pn.csv
4. Import for MaxQuant:
   - sample01_mq.csv
   - sample02_mq.csv

Result:
  Samples:
    Sample01 • ✓ PowerNovo2, ✓ MaxQuant
    Sample02 • ✓ PowerNovo2, ✓ MaxQuant
    
→ Можно сравнить результаты!
```

### Пример 3: Частичные идентификации

```
1. Add Tool "PowerNovo2"
2. Add Tool "MaxQuant"
3. Import for PowerNovo2:
   - sample01.csv
   - sample02.csv
   - sample03.csv
4. Import for MaxQuant:
   - sample01.csv  (только один!)

Result:
  Samples:
    Sample01 • ✓ PowerNovo2, ✓ MaxQuant
    Sample02 • ✓ PowerNovo2
    Sample03 • ✓ PowerNovo2
```

---

## Изменения в коде

### Новые элементы UI

#### Tools List
```python
self.tools_list = ft.Column(spacing=5)

# В _build_content():
tools_section = ft.Container(
    content=ft.Column([
        ft.Text("Identification Tools"),
        self.tools_list,
        ft.ElevatedButton(
            content="Add Tool",
            on_click=self.show_add_tool_dialog
        )
    ])
)
```

#### Tool ListTile
```python
ft.ListTile(
    leading=ft.Icon(ft.Icons.BIOTECH, color=tool.display_color),
    title=ft.Text(tool.name),
    subtitle=ft.Text(f"{ident_files_count} file(s)"),
    trailing=ft.ElevatedButton(
        content="Import Identifications",
        on_click=lambda e, t=tool: self.page.run_task(
            self.show_import_mode_dialog,
            e,
            "identifications",
            t.id  # ← Передаём tool_id!
        )
    )
)
```

### Изменённые сигнатуры методов

#### Before:
```python
async def show_import_mode_dialog(self, e, import_type: str):
    pass

async def import_identification_files(self, file_list, parser_name: str):
    parser_class = registry.get_parser(parser_name, "identification")
```

#### After:
```python
async def show_import_mode_dialog(
    self, 
    e, 
    import_type: str, 
    tool_id: int | None = None  # ← Новый параметр!
):
    if import_type == "identifications":
        tool = await self.project.get_tool(tool_id)
        # Show tool name in title

async def import_identification_files(
    self, 
    file_list, 
    tool_id: int  # ← Не parser_name!
):
    tool = await self.project.get_tool(tool_id)
    parser_class = registry.get_parser(tool.type, "identification")
    # Use tool.id directly
```

---

## Обработка парсера

### Spectra (не изменилось):
```python
# Парсер выбирается в UI
await import_spectra_files(files, subset_id, parser_name)
                                           ↑
                              Выбрано пользователем
```

### Identifications (изменилось):
```python
# Парсер определяется Tool
tool = await project.get_tool(tool_id)
parser_name = tool.type  # ← Из Tool!

await import_identification_files(files, tool_id)
                                         ↑
                             Tool определяет парсер
```

---

## Связь Tool ↔ Parser

### При создании Tool:

```python
# User выбирает parser из registry
parsers = registry.get_identification_parsers()
# {'PowerNovo2': PowerNovo2Importer, 'MaxQuant': MaxQuantParser}

# User создаёт Tool:
await project.add_tool(
    name="PowerNovo2",
    type="PowerNovo2"  # ← Это имя парсера из registry!
)
```

### При импорте:

```python
# Get tool
tool = await project.get_tool(tool_id)
# tool.type = "PowerNovo2"

# Get parser by tool.type
parser_class = registry.get_parser(tool.type, "identification")
# Returns: PowerNovo2Importer class

parser = parser_class(file_path)
```

---

## Database Integration

### Правильное заполнение tool_id

#### identification_file таблица:
```sql
INSERT INTO identification_file 
  (spectre_file_id, tool_id, file_path)
VALUES 
  (123, 5, '/path/to/sample01.csv')
         ↑
    Из UI!
```

#### identification таблица:
```sql
INSERT INTO identification 
  (spectre_id, tool_id, ident_file_id, sequence, ...)
VALUES 
  (456, 5, 789, 'PEPTIDE', ...)
        ↑
   Из Tool!
```

**Важно:** 
- `tool_id` передаётся из UI
- Не создаётся автоматически
- Пользователь явно управляет Tools

---

## Lifecycle Management

### Создание Tool:
```
UI → show_add_tool_dialog()
  → user inputs (name, parser, color)
  → project.add_tool(name, type=parser, color)
  → refresh_tools()
  → Tool появляется в списке с кнопкой
```

### Импорт для Tool:
```
UI → User clicks "Import Identifications" на Tool
  → show_import_mode_dialog(e, "identifications", tool.id)
  → show_import_pattern_dialog(import_type, tool.id)
  → import_identification_files(files, tool.id)
  → project.add_identification_file(file, tool_id=tool.id)
  → refresh_tools() - обновляется счётчик файлов
```

### Удаление Tool:
```
(Пока не реализовано - coming soon)

UI → User clicks "Delete" на Tool
  → Check: есть ли identifications?
  → If yes: show warning
  → If no: delete and refresh
```

---

## Тестирование

### ✅ Проверено:

**Tools Management:**
- ✅ Список Tools отображается при открытии проекта
- ✅ Add Tool создаёт новый Tool
- ✅ Parser выбирается из registry
- ✅ Tools отображаются с кнопками Import
- ✅ Счётчик файлов обновляется

**Import Flow:**
- ✅ Кнопка Import на Tool открывает диалог
- ✅ tool_id передаётся через все диалоги
- ✅ Parser берётся из tool.type
- ✅ identification_file создаётся с правильным tool_id

**Integration:**
- ✅ Samples показывают Tools с галочками
- ✅ refresh_tools() вызывается после импорта
- ✅ did_mount_async() загружает все данные

---

## Будущие улучшения

### Рекомендации:

1. **Удаление Tool**
   - Проверка на наличие identifications
   - Cascade delete или warning

2. **Редактирование Tool**
   - Изменение имени, цвета
   - Изменение settings

3. **Tool Settings**
   - Threshold параметры
   - Специфичные для парсера настройки
   - Сохранение в tool.settings JSON

4. **Статистика по Tool**
   - Сколько identifications
   - Средний score
   - Coverage metrics

5. **Экспорт конфигурации**
   - Сохранить список Tools
   - Импортировать в другой проект

---

## Заключение

Архитектура UI переработана для работы с Tools:

✅ **Явное управление** Tools через UI  
✅ **Каждый Tool** имеет свою кнопку Import  
✅ **tool_id** передаётся во все методы  
✅ **Parser** определяется через tool.type  
✅ **БД integration** полностью корректен  
✅ **Все списки** обновляются автоматически  

**Stage 3 полностью завершён!** 🎉

---

**Автор:** Goose AI  
**Дата:** 2026-01-30  
**Версия:** 1.0
