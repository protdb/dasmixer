# Flet Container Pattern - Quick Reference

## Базовый шаблон для всех пользовательских контролов

```python
import flet as ft

class MyCustomControl(ft.Container):
    """Описание контрола."""
    
    def __init__(self, arg1, arg2):
        """
        Initialize the control.
        
        Args:
            arg1: Description
            arg2: Description
        """
        super().__init__()
        
        # Store arguments
        self.arg1 = arg1
        self.arg2 = arg2
        
        # Configure container
        self.expand = True      # Fill available space
        self.padding = 0        # No internal padding
        
        # Initialize state
        self.data_container = ft.Column(spacing=5)
        
        # Build content immediately
        self.content = self._build_content()
    
    def _build_content(self):
        """
        Build the control's content structure.
        
        Returns:
            Control: The main content control (usually Column or Row)
        """
        return ft.Column([
            ft.Text("Title", size=20, weight=ft.FontWeight.BOLD),
            self.data_container,
            ft.ElevatedButton(
                text="Action",
                on_click=lambda e: self.page.run_task(self.handle_click, e)
            )
        ], 
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        expand=True
        )
    
    def did_mount(self):
        """
        Lifecycle hook: called when control is added to page.
        Use for initial data loading.
        """
        print(f"{self.__class__.__name__} mounted")
        self.page.run_task(self._load_initial_data)
    
    async def _load_initial_data(self):
        """Load initial data asynchronously."""
        try:
            # Async data loading
            data = await self.fetch_data()
            
            # Update UI
            self.data_container.controls.clear()
            for item in data:
                self.data_container.controls.append(
                    ft.Text(str(item))
                )
            
            # Refresh the control
            self.data_container.update()
            
        except Exception as ex:
            print(f"Error loading data: {ex}")
            import traceback
            traceback.print_exc()
    
    async def fetch_data(self):
        """Fetch data from source."""
        # Your async data fetching logic
        return ["Item 1", "Item 2", "Item 3"]
    
    async def handle_click(self, e):
        """Handle button click."""
        # Your async event handler
        pass
```

## Шаблон для табов

```python
import flet as ft
from api.project.project import Project

class MyTab(ft.Container):
    """Tab content control."""
    
    def __init__(self, project: Project):
        super().__init__()
        self.project = project
        self.expand = True
        self.padding = 0
        
        # Build content
        self.content = self._build_content()
    
    def _build_content(self):
        """Build tab content."""
        return ft.Column([
            ft.Container(
                content=ft.Column([
                    ft.Text("Section Title", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text("Section content")
                ], spacing=10),
                padding=20,
                border=ft.border.all(1, ft.Colors.GREY),
                border_radius=10
            )
        ],
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        expand=True
        )
    
    def did_mount(self):
        """Load data when tab is mounted."""
        self.page.run_task(self._load_data)
    
    async def _load_data(self):
        """Load tab data."""
        # Load data from project
        data = await self.project.get_data()
        # Update UI
        self.update()
```

## Структура Tabs (новый API)

```python
# В ProjectView или главном контейнере:

from gui.views.tabs.tab1 import Tab1
from gui.views.tabs.tab2 import Tab2

tabs = ft.Tabs(
    selected_index=0,
    length=2,  # MUST MATCH number of tabs
    expand=True,
    content=ft.Column(
        expand=True,
        controls=[
            ft.TabBar(
                tabs=[
                    ft.Tab(text=ft.Text("Tab 1"), icon=ft.Icons.ICON1),
                    ft.Tab(text=ft.Text("Tab 2"), icon=ft.Icons.ICON2),
                ]
            ),
            ft.TabBarView(
                expand=True,
                controls=[
                    Tab1(project),  # Must be ft.Container
                    Tab2(project),  # Must be ft.Container
                ],
            ),
        ],
    ),
)
```

## Важные правила

### ✅ DO:

1. **Наследуйте от Container**
   ```python
   class MyControl(ft.Container):
   ```

2. **Вызывайте `_build_content()` в `__init__()`**
   ```python
   self.content = self._build_content()
   ```

3. **Используйте `did_mount()` для загрузки данных**
   ```python
   def did_mount(self):
       self.page.run_task(self._load_data)
   ```

4. **Вызывайте `.update()` после изменений**
   ```python
   self.my_control.value = "new value"
   self.my_control.update()
   ```

5. **Используйте `self.page.run_task()` для async**
   ```python
   on_click=lambda e: self.page.run_task(self.async_handler, e)
   ```

### ❌ DON'T:

1. **НЕ используйте UserControl**
   ```python
   # ❌ WRONG
   class MyControl(ft.UserControl):
       def build(self):
           return ft.Column([...])
   ```

2. **НЕ используйте `build()` метод**
   ```python
   # ❌ WRONG - это для UserControl
   def build(self):
       return ...
   ```

3. **НЕ забывайте set expand и padding**
   ```python
   # ❌ WRONG - контрол может не отображаться
   def __init__(self):
       super().__init__()
       self.content = self._build_content()
   
   # ✅ CORRECT
   def __init__(self):
       super().__init__()
       self.expand = True
       self.padding = 0
       self.content = self._build_content()
   ```

4. **НЕ делайте sync вызовы async методов**
   ```python
   # ❌ WRONG
   def on_click(self, e):
       data = await self.fetch_data()  # SyntaxError!
   
   # ✅ CORRECT
   async def on_click(self, e):
       data = await self.fetch_data()
   
   # Or use run_task:
   def on_click(self, e):
       self.page.run_task(self._handle_click, e)
   
   async def _handle_click(self, e):
       data = await self.fetch_data()
   ```

## Кнопки и параметры

### Новый API (текущий):

```python
ft.ElevatedButton(
    text="Click Me",           # ✅ text, not content
    icon=ft.Icons.ADD,
    on_click=self.handler
)

ft.TextButton(
    text="Cancel",             # ✅ text
    on_click=self.handler
)

ft.OutlinedButton(
    text="Delete",             # ✅ text
    icon=ft.Icons.DELETE,
    on_click=self.handler
)
```

### Старый API (устарел):

```python
ft.ElevatedButton(
    content="Click Me",        # ❌ устарело
    on_click=self.handler
)
```

## Жизненный цикл

1. **`__init__()`** - Конструктор, инициализация
2. **`_build_content()`** - Построение структуры контролов
3. **`did_mount()`** - Когда добавлен на страницу (автоматически)
4. **`_load_initial_data()`** - Загрузка данных (вызывается из did_mount)
5. **`.update()`** - Обновление UI после изменений

## Обработка ошибок

```python
async def _load_data(self):
    """Load data with error handling."""
    try:
        data = await self.source.get_data()
        self.display.controls = [ft.Text(str(d)) for d in data]
        self.display.update()
    except Exception as ex:
        print(f"Error: {ex}")
        import traceback
        traceback.print_exc()
        
        # Show error in UI
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(f"Error loading data: {ex}"),
            bgcolor=ft.Colors.RED_400
        )
        self.page.snack_bar.open = True
        self.page.update()
```

## Проверочный список для нового контрола

- [ ] Наследуется от `ft.Container`
- [ ] `__init__()` вызывает `self.content = self._build_content()`
- [ ] Установлены `self.expand = True` и `self.padding = 0`
- [ ] Метод называется `_build_content()`, не `build()`
- [ ] `_build_content()` возвращает контрол (Column/Row/Container)
- [ ] Если нужна загрузка, реализован `did_mount()`
- [ ] Async операции через `self.page.run_task()`
- [ ] После изменений вызывается `.update()`
- [ ] Обработка ошибок в try-except
- [ ] Кнопки используют `text=`, не `content=`
