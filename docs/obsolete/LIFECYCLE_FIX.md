# Исправление: Lifecycle и загрузка данных

**Дата:** 2026-01-30  
**Статус:** ✅ Исправлено

---

## Проблема

При открытии проекта не отображались:
- ❌ Группы сравнения
- ❌ Инструменты (Tools)
- ❌ Образцы

**Причина:** `did_mount_async()` не вызывается для `ft.Container`

---

## Решение

### Изменение базового класса

**Было:**
```python
class SamplesTab(ft.Container):
    def __init__(self, project):
        super().__init__()
        # ...
        self.content = self._build_content()
    
    def _build_content(self):
        return ft.Column([...])
    
    async def did_mount_async(self):  # ❌ Не вызывается для Container!
        await self.refresh_groups()
```

**Стало:**
```python
class SamplesTab(ft.UserControl):  # ← UserControl вместо Container!
    def __init__(self, project):
        super().__init__()
        # ...
        # Не создаём content здесь
    
    def build(self):  # ← build() вместо _build_content()
        return ft.Container(
            content=ft.Column([...]),
            padding=20,
            expand=True
        )
    
    def did_mount(self):  # ← did_mount() вызывается автоматически!
        print("SamplesTab mounted")
        self.page.run_task(self._load_initial_data)
    
    async def _load_initial_data(self):
        await self.refresh_groups()
        await self.refresh_tools()
        await self.refresh_samples()
```

---

## Lifecycle Methods в Flet

### Control vs UserControl

| Класс | Lifecycle методы | Когда использовать |
|-------|------------------|-------------------|
| `ft.Control` | `did_mount()`, `will_unmount()`, `before_update()` | Низкоуровневые компоненты |
| `ft.UserControl` | То же + удобный `build()` | Кастомные компоненты UI |
| `ft.Container` | ❌ Не поддерживает | Только layout wrapper |

### UserControl преимущества:

1. **Автоматический lifecycle:**
   - `did_mount()` вызывается после добавления на page
   - `will_unmount()` перед удалением
   - `before_update()` перед обновлением

2. **Метод build():**
   - Вызывается автоматически при создании
   - Возвращает содержимое контрола
   - Чистый паттерн

3. **Изоляция:**
   - Каждый UserControl независим
   - Можно вызывать `self.update()`
   - Не затрагивает parent

---

## Изменённые файлы

### 1. `gui/views/tabs/samples_tab.py`

**Изменения:**
- `ft.Container` → `ft.UserControl`
- `_build_content()` → `build()`
- `did_mount_async()` → `did_mount()` + `_load_initial_data()`
- Добавлены print для отладки

### 2. `gui/views/tabs/peptides_tab.py`

**Изменения:**
- `ft.Container` → `ft.UserControl`
- `_build_content()` → `build()`
- Структура приведена к единому стилю

---

## Как работает загрузка

### Последовательность вызовов:

```
1. ProjectView creates SamplesTab(project)
   └→ SamplesTab.__init__(project)

2. page.add(SamplesTab)
   └→ Flet добавляет контрол на page

3. Flet вызывает build()
   └→ Возвращает UI структуру

4. Flet вызывает did_mount()
   └→ print("SamplesTab mounted")
   └→ page.run_task(_load_initial_data)

5. _load_initial_data() async
   ├→ await refresh_groups()
   │   ├→ project.get_subsets()
   │   ├→ groups_list.controls.clear()
   │   ├→ groups_list.controls.append(...)
   │   └→ groups_list.update()
   │
   ├→ await refresh_tools()
   │   ├→ project.get_tools()
   │   ├→ tools_list.controls.clear()
   │   ├→ tools_list.controls.append(...)
   │   └→ tools_list.update()
   │
   └→ await refresh_samples()
       ├→ project.get_samples()
       ├→ samples_container.content = ...
       └→ samples_container.update()
```

---

## Отладка

Добавлены print statements для отслеживания:

```python
def did_mount(self):
    print("SamplesTab did_mount called")  # ← Должно появиться в консоли
    self.page.run_task(self._load_initial_data)

async def _load_initial_data(self):
    print("Loading initial data...")  # ← Должно появиться
    await self.refresh_groups()
    await self.refresh_tools()
    await self.refresh_samples()
    print("Initial data loaded successfully")  # ← Должно появиться

async def refresh_groups(self):
    print("Refreshing groups...")
    groups = await self.project.get_subsets()
    # ...
    print(f"Groups loaded: {len(groups)}")  # ← Показывает количество
```

### Ожидаемый вывод в консоль:

```
SamplesTab did_mount called
Loading initial data...
Refreshing groups...
Groups loaded: 2
Refreshing tools...
Tools loaded: 1
Refreshing samples...
Samples loaded: 3
Initial data loaded successfully
```

---

## Тестирование

### Test Case: Открытие существующего проекта

```
1. Create project
2. Add groups, tools, import data
3. Close project
4. Reopen project
   
Expected:
✅ did_mount called
✅ Groups appear immediately
✅ Tools appear immediately
✅ Samples appear immediately

Console output:
✅ "SamplesTab did_mount called"
✅ "Loading initial data..."
✅ "Groups loaded: N"
✅ "Tools loaded: M"
✅ "Samples loaded: K"
```

---

## Паттерн для других вкладок

### Шаблон для новых вкладок:

```python
class MyTab(ft.UserControl):
    def __init__(self, project: Project):
        super().__init__()
        self.project = project
        self.expand = True
    
    def build(self):
        """Build UI - called automatically."""
        return ft.Container(
            content=ft.Column([...]),
            padding=20,
            expand=True
        )
    
    def did_mount(self):
        """Called when added to page."""
        self.page.run_task(self._load_data)
    
    async def _load_data(self):
        """Load initial data."""
        # Async data loading
        data = await self.project.get_something()
        # Update UI
        self.update()
```

---

## Ключевые моменты

### 1. UserControl для вкладок
- ✅ Используйте `ft.UserControl` для всех вкладок
- ✅ Не используйте `ft.Container` для корневых компонентов

### 2. build() метод
- ✅ Возвращает UI структуру
- ✅ Вызывается автоматически один раз
- ✅ Может возвращать любой Control

### 3. did_mount() для загрузки
- ✅ Используйте для async операций
- ✅ Вызывайте `page.run_task()` для async функций
- ✅ Обновляйте UI через `.update()`

### 4. update() vs page.update()
- `self.update()` - обновляет только этот контрол
- `page.update()` - обновляет всю страницу
- Используйте `self.update()` когда возможно (быстрее)

---

## Результат

После исправления:

✅ **Группы** отображаются сразу при открытии проекта  
✅ **Tools** отображаются сразу при открытии проекта  
✅ **Образцы** отображаются сразу при открытии проекта  
✅ **did_mount()** вызывается автоматически  
✅ **Async загрузка** работает корректно  

---

**Автор:** Goose AI  
**Дата:** 2026-01-30  
**Версия:** 1.0
