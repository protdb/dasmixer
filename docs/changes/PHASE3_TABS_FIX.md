# Исправление проблемы с вкладками в Phase 3

**Дата:** 2026-01-30  
**Проблема:** Списки образцов, инструментов, групп не заполнялись при открытии проекта автоматически. В процессе исправления был сломан механизм отображения вкладок - вместо содержимого показывался пустой экран.

## Выявленные проблемы

### 1. Несоответствие количества вкладок в `project_view.py`

**Файл:** `gui/views/project_view.py`

**Проблема:**
- В `ft.Tabs(length=4, ...)` указано 4 вкладки
- В `TabBar` только 2 активных вкладки (Samples и Peptides, остальные закомментированы)
- В `TabBarView.controls` тоже только 2 элемента
- Это приводило к ошибке рендеринга, т.к. Flet ожидал 4 вкладки, а получал 2

**Решение:**
- Изменено `length=2` для соответствия количеству активных вкладок
- Использованы правильные параметры для Tab: `text=ft.Text("...")` вместо `label="..."`

### 2. Использование устаревшего UserControl

**Файлы:** `gui/views/tabs/samples_tab.py`, `gui/views/tabs/peptides_tab.py`

**Проблема:**
- Табы наследовались от `ft.UserControl`
- Использовали метод `build()` для построения контента
- `UserControl` устарел в новых версиях Flet и не работает корректно с новым API вкладок

**Решение:**
- Изменено наследование на `ft.Container` (как в `ProjectView`)
- Метод `build()` заменён на `_build_content()`
- Вызов `_build_content()` перемещён в `__init__()` с присвоением `self.content`
- Добавлены `self.padding = 0` для корректного отображения

### 3. Дублирование методов в `samples_tab.py`

**Файл:** `gui/views/tabs/samples_tab.py`

**Проблема:**
- Метод `did_mount()` был определён дважды (на строках ~126 и ~377)
- Метод `_load_initial_data()` также был продублирован
- Первое определение было упрощённым, без обработки ошибок
- Это могло приводить к непредсказуемому поведению при загрузке данных

**Решение:**
- Удалены первые определения методов `did_mount()` и `_load_initial_data()`
- Оставлена только полная версия с обработкой ошибок try-except

### 4. Использование устаревших параметров в кнопках

**Файл:** `gui/views/tabs/samples_tab.py`

**Проблема:**
- В кнопках использовался параметр `content="текст"` вместо `text="текст"`
- Новая версия Flet использует `text` для текстовых кнопок

**Решение:**
- Заменены все `content=` на `text=` в ElevatedButton, TextButton, OutlinedButton

## Архитектура вкладок

### Правильная структура наследования:

**Для ProjectView и всех Tab-контейнеров:**

```python
class MyTab(ft.Container):
    def __init__(self, project: Project):
        super().__init__()
        self.project = project
        self.expand = True
        self.padding = 0
        
        # Build content immediately
        self.content = self._build_content()
    
    def _build_content(self):
        """Build the tab content."""
        return ft.Column([
            # ... content controls
        ], expand=True)
    
    def did_mount(self):
        """Called when control is added to page."""
        # Run async initialization
        self.page.run_task(self._load_data)
    
    async def _load_data(self):
        """Load initial data."""
        # ... async data loading
```

### Структура работы вкладок по новому API Flet

```python
ft.Tabs(
    selected_index=0,
    length=N,  # ДОЛЖНО СОВПАДАТЬ с количеством Tab в TabBar и controls в TabBarView
    expand=True,
    content=ft.Column(
        expand=True,
        controls=[
            ft.TabBar(
                tabs=[
                    ft.Tab(text=ft.Text("Tab 1"), icon=ft.Icons.ICON1),
                    ft.Tab(text=ft.Text("Tab 2"), icon=ft.Icons.ICON2),
                    # ... всего N вкладок
                ]
            ),
            ft.TabBarView(
                expand=True,
                controls=[
                    TabContent1(args),  # ft.Container с _build_content()
                    TabContent2(args),  # ft.Container с _build_content()
                    # ... всего N контролов
                ],
            ),
        ],
    ),
)
```

### Ключевые моменты:

1. **Наследование:** Все табы наследуются от `ft.Container`, НЕ от `ft.UserControl`
2. **Построение контента:** Используется `_build_content()`, вызываемый в `__init__()`
3. **length** в `ft.Tabs` должен точно соответствовать количеству вкладок
4. **TabBar.tabs** и **TabBarView.controls** должны иметь одинаковое количество элементов
5. **Tab.text** принимает `ft.Text()` или строку, но лучше использовать `ft.Text()`
6. **TabBarView.controls** содержит контент для каждой вкладки (ft.Container)
7. Все должно быть обёрнуто в **ft.Column** с `expand=True`

## Механизм загрузки данных в SamplesTab

### Жизненный цикл:

1. **__init__()** - инициализация, создание пустых контейнеров, вызов `_build_content()`
2. **_build_content()** - построение UI-структуры, возврат контента
3. **did_mount()** - вызывается когда контрол добавлен на страницу
4. **_load_initial_data()** - асинхронная загрузка данных из проекта
5. **refresh_groups/tools/samples()** - заполнение списков данными с вызовом `.update()`

### Важно:

- Метод `did_mount()` - это хук Flet, вызываемый автоматически
- Использование `self.page.run_task()` для запуска асинхронных операций
- Каждый метод refresh должен вызывать `.update()` для обновления UI
- Обработка ошибок в try-except для отлавливания проблем загрузки
- `_build_content()` вызывается в `__init__()`, результат присваивается `self.content`

## Отличия от UserControl

### Старый подход (UserControl) - НЕ РАБОТАЕТ:

```python
class MyTab(ft.UserControl):
    def build(self):
        return ft.Column([...])
```

### Новый подход (Container) - ПРАВИЛЬНО:

```python
class MyTab(ft.Container):
    def __init__(self, args):
        super().__init__()
        self.expand = True
        self.padding = 0
        self.content = self._build_content()
    
    def _build_content(self):
        return ft.Column([...])
```

## Результат

После исправлений:
- ✅ Вкладки корректно отображаются
- ✅ При открытии проекта автоматически загружаются и отображаются группы
- ✅ Автоматически загружаются и отображаются инструменты
- ✅ Автоматически загружаются и отображаются образцы
- ✅ Кнопки и диалоги работают корректно
- ✅ Архитектура соответствует новому API Flet

## Файлы изменены

1. `gui/views/project_view.py` - исправлена структура вкладок, использование `text=ft.Text()`
2. `gui/views/tabs/samples_tab.py` - изменено наследование на Container, удалены дубликаты методов, исправлены параметры кнопок
3. `gui/views/tabs/peptides_tab.py` - изменено наследование на Container, использование `_build_content()`
