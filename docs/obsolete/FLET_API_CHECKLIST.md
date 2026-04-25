# Чек-лист проверки Flet API

Используйте этот чек-лист для проверки кода на соответствие актуальному API Flet 0.80.4+.

---

## ✅ FilePicker

### Неправильно (старый API):
```python
❌ file_picker = ft.FilePicker(on_result=callback)
❌ page.overlay.append(file_picker)
❌ file_picker.pick_files(...)
```

### Правильно (новый API):
```python
✅ files = await ft.FilePicker().pick_files(...)
✅ file_path = await ft.FilePicker().save_file(...)
✅ dir_path = await ft.FilePicker().get_directory_path(...)
```

---

## ✅ AlertDialog

### Неправильно:
```python
❌ page.show_dialog(dialog)
❌ page.pop_dialog()
```

### Правильно:
```python
✅ page.overlay.append(dialog)
✅ dialog.open = True
✅ page.update()

# Закрытие:
✅ dialog.open = False
✅ page.update()
```

---

## ✅ SnackBar

### Неправильно:
```python
❌ page.show_dialog(ft.SnackBar(...))
```

### Правильно:
```python
✅ page.snack_bar = ft.SnackBar(...)
✅ page.snack_bar.open = True
✅ page.update()
```

---

## ✅ Button Controls

### Неправильно:
```python
❌ ft.ElevatedButton(text="Click", ...)
❌ ft.TextButton(text="Cancel", ...)
```

### Правильно:
```python
✅ ft.ElevatedButton(content="Click", ...)
✅ ft.TextButton(content="Cancel", ...)
```

---

## ✅ Async Handlers

### Неправильно:
```python
❌ def handle_click(e):  # НЕ async
    files = await ft.FilePicker().pick_files()  # ОШИБКА!
```

### Правильно:
```python
✅ async def handle_click(e):  # async!
    files = await ft.FilePicker().pick_files()
```

---

## ✅ PopupMenuItem

### Правильно:
```python
✅ ft.PopupMenuItem(content=ft.Text("Item"), ...)
✅ ft.PopupMenuItem(content="Item", ...)
```

**Примечание:** `content`, НЕ `text`

---

## ✅ Dropdown Options

### Оба варианта правильны:
```python
✅ ft.dropdown.Option(key="val", text="Text")
✅ ft.DropdownOption(key="val", text="Text")
```

---

## Процесс проверки файла

1. [ ] Открыть файл
2. [ ] Найти все использования `FilePicker` (Ctrl+F: "FilePicker")
3. [ ] Проверить соответствие новому API
4. [ ] Найти все `AlertDialog` (Ctrl+F: "AlertDialog")
5. [ ] Проверить метод показа/скрытия
6. [ ] Найти все `SnackBar` (Ctrl+F: "SnackBar")
7. [ ] Проверить метод отображения
8. [ ] Найти все кнопки (Ctrl+F: "Button")
9. [ ] Проверить использование `content=`
10. [ ] Проверить async обработчики
11. [ ] Запустить и протестировать

---

## Файлы для проверки

| Файл | Статус | Примечания |
|------|--------|------------|
| `gui/app.py` | ✅ Проверен | Исправлен |
| `gui/views/start_view.py` | ⚠️ Требует проверки | Кнопки используют `content`, но нет FilePicker |
| `gui/views/project_view.py` | ✅ Вероятно OK | Нет диалогов/FilePicker |
| `gui/views/tabs/samples_tab.py` | ✅ Проверен | Полностью исправлен |
| `gui/views/tabs/peptides_tab.py` | ⚠️ Требует проверки | Кнопки используют `content` |
| `gui/views/tabs/proteins_tab.py` | ⚠️ Требует проверки | Не проверен |
| `gui/views/tabs/analysis_tab.py` | ⚠️ Требует проверки | Не проверен |

---

## Быстрая команда поиска

```bash
# Найти потенциально устаревший код:
grep -r "on_result=" gui/
grep -r "show_dialog" gui/
grep -r "pop_dialog" gui/
grep -r "text=" gui/ | grep Button
```

---

**Последнее обновление:** 2026-01-30
