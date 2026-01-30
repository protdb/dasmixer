# FilePicker API - Исправления

## Дата: 2026-01-29, 22:00

---

## Проблема

FilePicker API полностью изменился в новых версиях Flet:

**Старый API (не работает):**
```python
# Create file picker with callback
save_picker = ft.FilePicker(on_result=callback)
page.overlay.append(save_picker)
page.update()

# Call method
save_picker.save_file(...)
```

**Новый API (работает):**
```python
# Direct async call without callbacks
file_path = await ft.FilePicker().save_file(...)

# Or for pick_files:
files = await ft.FilePicker().pick_files(...)
```

---

## Решение

### Изменения в `gui/app.py`

#### 1. save_file() - теперь async и возвращает путь

**Было:**
```python
def save_file_result(e: ft.FilePickerResultEvent):
    if e.path:
        # ...

save_picker = ft.FilePicker(on_result=save_file_result)
page.overlay.append(save_picker)
save_picker.save_file(...)
```

**Стало:**
```python
async def new_project(self, e=None):
    file_path = await ft.FilePicker().save_file(
        dialog_title="Create New Project",
        file_name="project.dasmix",
        file_type=ft.FilePickerFileType.CUSTOM,
        allowed_extensions=["dasmix"]
    )
    
    if not file_path:
        return  # User cancelled
    
    # Use file_path directly
    project_path = Path(file_path)
    # ...
```

#### 2. pick_files() - теперь async и возвращает список файлов

**Было:**
```python
def pick_file_result(e: ft.FilePickerResultEvent):
    if e.files:
        file_path = e.files[0].path
        # ...

pick_files = ft.FilePicker(on_result=pick_file_result)
page.overlay.append(pick_files)
pick_files.pick_files(...)
```

**Стало:**
```python
async def open_project_dialog(self, e=None):
    files = await ft.FilePicker().pick_files(
        dialog_title="Open Project",
        file_type=ft.FilePickerFileType.CUSTOM,
        allowed_extensions=["dasmix"],
        allow_multiple=False
    )
    
    if files:
        await self.open_project(files[0].path)
```

---

## Ключевые отличия

| Старый API | Новый API |
|-----------|-----------|
| `FilePicker(on_result=callback)` | `FilePicker()` без колбэков |
| `picker.save_file()` | `await picker.save_file()` |
| `picker.pick_files()` | `await picker.pick_files()` |
| Результат в `e.path` | Возвращается напрямую |
| Результат в `e.files` | Возвращается `list[FilePickerFile]` |
| Нужен `overlay.append()` | НЕ нужен overlay |

---

## Типы возвращаемых значений

### save_file()
```python
file_path: str | None = await ft.FilePicker().save_file(...)
# Returns: путь к файлу или None если отменено
```

### pick_files()
```python
files: list[FilePickerFile] = await ft.FilePicker().pick_files(...)
# Returns: список файлов (пустой если отменено)

# FilePickerFile имеет атрибуты:
# - name: str
# - path: str
# - size: int
```

### get_directory_path()
```python
dir_path: str | None = await ft.FilePicker().get_directory_path(...)
# Returns: путь к папке или None
```

---

## Использование в обработчиках событий

### Важно: обработчик должен быть async

**Неправильно:**
```python
def handle_click(e):  # НЕ async
    file_path = await ft.FilePicker().save_file()  # ОШИБКА!
```

**Правильно:**
```python
async def handle_click(e):  # async!
    file_path = await ft.FilePicker().save_file()  # ОК
```

### Запуск async обработчика из кнопки

```python
ft.Button(
    content=ft.Text("Save"),
    on_click=lambda _: page.run_task(handle_save)
)

# Или напрямую:
ft.Button(
    content=ft.Text("Save"),
    on_click=handle_save  # Если handle_save async
)
```

---

## Примеры из документации

### Простой pick files
```python
async def handle_pick_files(e):
    files = await ft.FilePicker().pick_files(allow_multiple=True)
    
    if files:
        for f in files:
            print(f"Picked: {f.name}")
```

### Save file
```python
async def handle_save_file(e):
    save_path = await ft.FilePicker().save_file(
        dialog_title="Save As",
        file_name="document.txt"
    )
    
    if save_path:
        print(f"Saving to: {save_path}")
```

### Get directory
```python
async def handle_get_directory(e):
    dir_path = await ft.FilePicker().get_directory_path(
        dialog_title="Select Folder"
    )
    
    if dir_path:
        print(f"Selected: {dir_path}")
```

---

## Исправленные файлы

| Файл | Изменения |
|------|-----------|
| `gui/app.py` | Переписаны `new_project()` и `open_project_dialog()` |

---

## Статус

✅ **FilePicker полностью работает**

Протестировано:
- ✅ Создание проекта (save_file)
- ✅ Открытие проекта (pick_files)
- ✅ GUI запускается без ошибок

---

## Дополнительно: PopupMenuItem

В меню также исправлено:

**Было:** `content="Text"`  
**Стало:** `text="Text"`

PopupMenuItem использует атрибут `text`, а не `content`.

---

**Дата:** 2026-01-29 22:00  
**Автор:** Goose  
**Статус:** ✅ Исправлено и протестировано
