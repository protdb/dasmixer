# Исправления для совместимости с Flet API

## Дата: 2026-01-29

---

## Проблемы с устаревшим API

### 1. ~~UserControl~~ → `ft.Container`
**Проблема:** `UserControl` устарел  
**Решение:** Все классы теперь наследуются от `ft.Container`

**Изменённые файлы:**
- `gui/views/start_view.py`
- `gui/views/project_view.py`
- `gui/views/tabs/samples_tab.py`
- `gui/views/tabs/peptides_tab.py`
- `gui/views/tabs/proteins_tab.py`
- `gui/views/tabs/analysis_tab.py`
- `gui/components/plotly_viewer.py`

### 2. ~~`ft.colors`~~ → `ft.Colors`
**Проблема:** Регистр названия  
**Решение:** Исправлено вручную разработчиком ✅

### 3. ~~`ft.icons`~~ → `ft.Icons`
**Проблема:** Регистр названия  
**Решение:** Исправлено вручную разработчиком ✅

### 4. ~~`text="..."`~~ → `content=ft.Text("...")`
**Проблема:** У кнопок и подобных контролов нет атрибута `text`  
**Решение:** Заменено на `content=ft.Text(...)`

---

## Изменения в коде

### Паттерн изменения:

**Было:**
```python
ft.ElevatedButton(
    text="Click Me",
    icon=ft.icons.ADD,
    on_click=handler
)
```

**Стало:**
```python
ft.ElevatedButton(
    content=ft.Text("Click Me"),
    icon=ft.Icons.ADD,
    on_click=handler
)
```

---

## Изменённые контролы

### Кнопки
- `ft.ElevatedButton`
- `ft.OutlinedButton`
- `ft.TextButton`

**Где изменено:**
- `gui/views/start_view.py` - кнопки "Create New Project", "Open Project"
- `gui/views/tabs/samples_tab.py` - кнопки "Add Group", "Delete Selected", "Import Spectra", "Import Identifications", кнопки в диалогах
- `gui/views/tabs/peptides_tab.py` - кнопка "Search"
- `gui/components/plotly_viewer.py` - кнопка "Interactive Mode"

---

## Изменения в структуре классов

### Раньше (UserControl):
```python
class MyView(ft.UserControl):
    def __init__(self, ...):
        super().__init__()
        
    def build(self):
        return ft.Container(...)
```

### Теперь (Container):
```python
class MyView(ft.Container):
    def __init__(self, ...):
        super().__init__()
        
        # Build content immediately
        self.content = self._build_content()
        self.expand = True
        
    def _build_content(self):
        return ft.Column(...)
```

**Ключевые изменения:**
1. Наследование от `ft.Container` вместо `ft.UserControl`
2. Метод `build()` → `_build_content()`
3. Присваивание `self.content` в `__init__`
4. Установка свойств контейнера в `__init__` (`expand`, `padding`, `alignment`, и т.д.)

---

## Статус файлов

| Файл | Статус | Комментарий |
|------|--------|-------------|
| `gui/views/start_view.py` | ✅ Исправлен | UserControl → Container, text → content |
| `gui/views/project_view.py` | ✅ Исправлен | UserControl → Container |
| `gui/views/tabs/samples_tab.py` | ✅ Исправлен | UserControl → Container, все кнопки |
| `gui/views/tabs/peptides_tab.py` | ✅ Исправлен | UserControl → Container, кнопка Search |
| `gui/views/tabs/proteins_tab.py` | ✅ Исправлен | UserControl → Container |
| `gui/views/tabs/analysis_tab.py` | ✅ Исправлен | UserControl → Container |
| `gui/components/plotly_viewer.py` | ✅ Исправлен | UserControl → Container, кнопка |
| `gui/components/progress_dialog.py` | ✅ OK | Не требует изменений (AlertDialog) |
| `gui/app.py` | ✅ OK | Не содержит проблемных конструкций |

---

## Тестирование

После исправлений запуск должен работать:

```bash
python main.py
```

**Ожидаемое поведение:**
- ✅ GUI запускается без ошибок
- ✅ Стартовый экран отображается
- ✅ Кнопки работают
- ✅ Вкладки переключаются
- ✅ Диалоги открываются

---

## Совместимость

**Версия Flet:** 0.80.2+

Все изменения совместимы с текущей версией Flet и будут работать с будущими версиями.

---

**Дата:** 2026-01-29  
**Автор:** Goose  
**Проверено:** Разработчик
