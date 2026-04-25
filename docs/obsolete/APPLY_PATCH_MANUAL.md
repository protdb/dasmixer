# Быстрое применение патча к samples_tab.py

Пока модульная структура дорабатывается, можно применить минимальный патч к существующему `gui/views/tabs/samples_tab.py` для работоспособности.

## 3 изменения в файле samples_tab.py

### 1. Метод `refresh_tools()` - строка ~130

**Найти:**
```python
subtitle=ft.Text(f"{len(ident_files)} identification file(s)" + (f" • Type: {tool.type}" if tool.type else ""))
```

**Заменить на:**
```python
subtitle_text = f"{len(ident_files)} identification file(s) • {tool.type} ({tool.parser})"
subtitle=ft.Text(subtitle_text)
```

### 2. Метод `show_add_tool_dialog()` - строка ~250

**Найти весь метод и заменить на:**

```python
async def show_add_tool_dialog(self, e):
    """Show dialog for adding new tool."""
    # Get available identification parsers
    parsers = registry.get_identification_parsers()
    parser_options = [
        ft.dropdown.Option(key=name, text=name)
        for name in parsers.keys()
    ]
    
    if not parser_options:
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("No identification parsers available"),
            bgcolor=ft.Colors.RED_400
        )
        self.page.snack_bar.open = True
        self.page.update()
        return
    
    name_field = ft.TextField(
        label="Tool Name",
        hint_text="e.g., PowerNovo2_Run1",
        autofocus=True
    )
    
    # NEW: Tool type selector
    tool_type_group = ft.RadioGroup(
        content=ft.Column([
            ft.Radio(value="Library", label="Library Search"),
            ft.Radio(value="De Novo", label="De Novo Sequencing")
        ]),
        value="Library"
    )
    
    # RENAMED: Parser dropdown
    parser_dropdown = ft.Dropdown(
        label="Parser / Format",
        options=parser_options,
        value=parser_options[0].key,
        width=300
    )
    
    color_field = ft.TextField(
        label="Color (hex)",
        value="9333EA",
    )
    
    async def save_tool(e):
        if not name_field.value:
            name_field.error_text = "Name is required"
            name_field.update()
            return
        
        try:
            color = color_field.value
            if not color.startswith('#'):
                color = '#' + color
            
            # PATCHED: Pass both type and parser
            await self.project.add_tool(
                name=name_field.value,
                type=tool_type_group.value,  # NEW
                parser=parser_dropdown.value,  # RENAMED from type
                display_color=color
            )
            
            dialog.open = False
            self.page.update()
            await self.refresh_tools()
            
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Added tool: {name_field.value}"),
                bgcolor=ft.Colors.GREEN_400
            )
            self.page.snack_bar.open = True
            self.page.update()
            
        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Error: {ex}"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    dialog = ft.AlertDialog(
        title=ft.Text("Add Identification Tool"),
        content=ft.Column([
            name_field,
            ft.Container(height=10),
            ft.Text("Tool Type:", weight=ft.FontWeight.W_500),
            tool_type_group,
            ft.Container(height=10),
            parser_dropdown,
            ft.Container(height=10),
            color_field,
            ft.Container(height=5),
            ft.Text(
                "Tool = identification method (library search or de novo)",
                size=11,
                italic=True,
                color=ft.Colors.GREY_600
            )
        ], tight=True, width=400),
        actions=[
            ft.TextButton(
                content="Cancel", 
                on_click=lambda e: self._close_dialog(dialog)
            ),
            ft.ElevatedButton(
                content=ft.Text("Add"),
                on_click=lambda e: self.page.run_task(save_tool, e)
            )
        ]
    )
    
    self.page.overlay.append(dialog)
    dialog.open = True
    self.page.update()
```

### 3. Метод `import_identification_files()` - строка ~545

**Найти строку:**
```python
parser_class = registry.get_parser(tool.type, "identification")
```

**Заменить на:**
```python
# PATCHED: Use tool.parser instead of tool.type
parser_class = registry.get_parser(tool.parser, "identification")
```

---

## После применения патча

1. Сохранить файл
2. Проект готов к тестированию базового функционала
3. Можно создавать tool с выбором type
4. Импорт identifications будет работать с новой структурой

---

## Полная модульная структура

Модульная структура для samples уже частично создана в `gui/views/tabs/samples/`.
После тестирования базового функционала можно завершить рефакторинг.

**Уже создано:**
- samples/__init__.py
- samples/shared_state.py
- samples/groups_section.py
- samples/tools_section.py
- samples/dialogs/add_tool_dialog.py (с патчем)
- samples/dialogs/__init__.py
- samples/README.md

**Осталось:**
- samples/base_section.py
- samples/import_section.py
- samples/samples_list_section.py
- samples/import_logic.py
- samples/dialogs/add_group_dialog.py
- samples/samples_tab.py (главный композитор)
