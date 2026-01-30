# Миграция на актуальный API Flet

**Дата:** 2026-01-30  
**Версия Flet:** 0.80.4  
**Статус:** ✅ Завершено

---

## Обзор

В рамках этапа 3 разработки проекта DASMixer были выявлены проблемы с использованием устаревшего API Flet, что приводило к неработающим диалогам выбора файлов и другим ошибкам UI. Данный документ описывает все изменения, внесённые для приведения кода в соответствие с актуальным API Flet.

---

## Основные изменения API

### 1. FilePicker - полностью переработан

#### Старый API (не работает)
```python
# Создание FilePicker с callback
file_picker = ft.FilePicker(on_result=callback_function)
page.overlay.append(file_picker)
page.update()

# Вызов метода (неблокирующий)
file_picker.pick_files(...)
```

#### Новый API (работает)
```python
# Прямой async вызов без callbacks
files = await ft.FilePicker().pick_files(
    dialog_title="Select Files",
    file_type=ft.FilePickerFileType.CUSTOM,
    allowed_extensions=["mgf"],
    allow_multiple=True
)

# Результат возвращается напрямую
if files:
    for file in files:
        print(file.path, file.name)
```

**Ключевые отличия:**

| Старый API | Новый API |
|-----------|-----------|
| `FilePicker(on_result=callback)` | `FilePicker()` без колбэков |
| Результат через `event.files` | Возвращает `list[FilePickerFile]` |
| Результат через `event.path` | Возвращает `str \| None` |
| Нужен `overlay.append()` | НЕ нужен overlay |
| Синхронный вызов | `await` async вызов |

---

### 2. FilePicker методы

#### pick_files()
```python
files: list[FilePickerFile] = await ft.FilePicker().pick_files(
    dialog_title="Select MGF Files",
    file_type=ft.FilePickerFileType.CUSTOM,
    allowed_extensions=["mgf"],
    allow_multiple=True
)

# Возвращает:
# - Список FilePickerFile объектов (может быть пустым, если отменено)
# - Каждый объект имеет: name, path, size
```

#### save_file()
```python
file_path: str | None = await ft.FilePicker().save_file(
    dialog_title="Save Project",
    file_name="project.dasmix",
    file_type=ft.FilePickerFileType.CUSTOM,
    allowed_extensions=["dasmix"]
)

# Возвращает:
# - Строку с путём к файлу
# - None если отменено
```

#### get_directory_path()
```python
dir_path: str | None = await ft.FilePicker().get_directory_path(
    dialog_title="Select Folder"
)

# Возвращает:
# - Строку с путём к папке
# - None если отменено
```

---

### 3. AlertDialog - изменён API показа/скрытия

#### Старый API
```python
# Показ диалога
page.show_dialog(dialog)

# Закрытие
page.pop_dialog()
```

#### Новый API
```python
# Создание диалога
dialog = ft.AlertDialog(
    title=ft.Text("Title"),
    content=ft.Text("Content"),
    actions=[...]
)

# Добавление в overlay
page.overlay.append(dialog)

# Показ
dialog.open = True
page.update()

# Закрытие
dialog.open = False
page.update()
```

**Важно:** Теперь диалоги управляются через свойство `open` и требуют `page.update()`.

---

### 4. SnackBar - изменён API показа

#### Старый API
```python
page.show_dialog(ft.SnackBar(...))
```

#### Новый API
```python
page.snack_bar = ft.SnackBar(
    content=ft.Text("Message"),
    bgcolor=ft.Colors.GREEN_400
)
page.snack_bar.open = True
page.update()
```

---

### 5. Button Controls - уточнение атрибутов

Все кнопки (`ElevatedButton`, `TextButton`, `OutlinedButton`, `FilledButton`) используют атрибут `content`, а не `text`:

```python
# Правильно:
ft.ElevatedButton(
    content="Click me",  # или ft.Text("Click me")
    icon=ft.Icons.ADD,
    on_click=handler
)

# Также правильно:
ft.ElevatedButton(
    content=ft.Text("Click me"),
    icon=ft.Icons.ADD
)

# Неправильно:
ft.ElevatedButton(
    text="Click me",  # ❌ Нет такого атрибута
)
```

**Примечание:** `content` может быть:
- Строкой (автоматически оборачивается в `Text`)
- `Text` контролом
- Любым другим Control (например, `Row` с иконками)

---

### 6. Dropdown Option

Поддерживаются оба варианта:

```python
# Вариант 1 (рекомендуемый):
ft.dropdown.Option(key="value", text="Display Text")

# Вариант 2:
ft.DropdownOption(key="value", text="Display Text")
```

---

## Исправленные файлы

### 1. `gui/app.py`
**Статус:** ✅ Исправлен ранее

Изменения:
- `new_project()`: использует `await ft.FilePicker().save_file()`
- `open_project_dialog()`: использует `await ft.FilePicker().pick_files()`
- SnackBar через `page.snack_bar.open = True`

---

### 2. `gui/views/tabs/samples_tab.py`
**Статус:** ✅ Полностью переработан

#### Изменённые методы:

**`show_import_single_files()`:**
```python
async def show_import_single_files(self):
    # Использует новый async API
    files = await ft.FilePicker().pick_files(
        dialog_title="Select MGF Files",
        file_type=ft.FilePickerFileType.CUSTOM,
        allowed_extensions=["mgf"],
        allow_multiple=True
    )
    
    if not files or len(files) == 0:
        return  # User cancelled
    
    # Обработка files
    file_list = [(Path(f.path), Path(f.name).stem) for f in files]
    await self.show_single_files_config(file_list)
```

**`show_import_pattern_dialog()` - browse_folder:**
```python
async def browse_folder(e):
    folder_path = await ft.FilePicker().get_directory_path(
        dialog_title="Select Folder with MGF Files"
    )
    if folder_path:
        folder_field.value = folder_path
        folder_field.update()
```

**Все диалоги:**
```python
# Создание
dialog = ft.AlertDialog(...)

# Показ
self.page.overlay.append(dialog)
dialog.open = True
self.page.update()

# Закрытие
dialog.open = False
self.page.update()
```

**Все SnackBar:**
```python
self.page.snack_bar = ft.SnackBar(
    content=ft.Text("Message"),
    bgcolor=ft.Colors.GREEN_400
)
self.page.snack_bar.open = True
self.page.update()
```

**Все кнопки:**
```python
ft.ElevatedButton(
    content="Button Text",  # не text=
    icon=ft.Icons.ICON_NAME,
    on_click=handler
)

ft.TextButton(
    content="Cancel",  # не text=
    on_click=handler
)
```

---

## Async-обработчики событий

Важное изменение: для использования async FilePicker обработчики событий должны быть async:

```python
# Правильно:
async def handle_click(e):
    files = await ft.FilePicker().pick_files()
    # ...

ft.Button(
    content="Click",
    on_click=handle_click  # Flet автоматически обработает async
)

# Или с lambda:
ft.Button(
    content="Click",
    on_click=lambda e: page.run_task(handle_click, e)
)
```

---

## Проверка совместимости

### Тестирование
Все изменения протестированы с Flet 0.80.4:

✅ Создание проекта (save_file)  
✅ Открытие проекта (pick_files)  
✅ Выбор MGF файлов (pick_files)  
✅ Выбор папки для pattern matching (get_directory_path)  
✅ Отображение диалогов (AlertDialog)  
✅ Отображение уведомлений (SnackBar)  
✅ Кнопки с content атрибутом  

---

## Рекомендации для будущей разработки

1. **FilePicker всегда async** - используйте `await` и делайте обработчики async
2. **Dialog управление** - через `dialog.open = True/False` + `page.update()`
3. **SnackBar** - через `page.snack_bar.open = True`
4. **Кнопки** - используйте `content=`, а не `text=`
5. **Обработчики** - делайте async если используют await внутри

---

## Дополнительные ресурсы

- [Официальная документация Flet FilePicker](https://docs.flet.dev/services/filepicker)
- [Примеры использования FilePicker](https://docs.flet.dev/services/filepicker#examples)
- [Migration guide](https://flet.dev/docs/migration/)

---

**Автор:** Goose AI  
**Дата:** 2026-01-30  
**Версия документа:** 1.0
