# Samples Tab - Modular Structure

## Overview

Samples tab refactored into modular components following the same pattern as Peptides tab.

## Structure

```
samples/
├── __init__.py                # Exports SamplesTab
├── samples_tab.py             # Main composition
├── shared_state.py            # Shared state
├── base_section.py            # Base class
├── groups_section.py          # ✅ Groups management
├── tools_section.py           # ✅ Tools management (with type/parser patch)
├── import_section.py          # 🔄 Import button
├── samples_list_section.py    # 🔄 Samples table
├── import_logic.py            # 🔄 Import workflows (with tool.parser patch)
└── dialogs/
    ├── __init__.py            # ✅
    ├── add_group_dialog.py    # 🔄 Add group
    ├── add_tool_dialog.py     # ✅ Add tool (WITH TYPE/PARSER PATCH!)
    └── import_dialogs.py      # 🔄 Import mode/pattern/config
```

## Key Changes - Stage 4.1 Patch Applied

### AddToolDialog ✅

**Changes applied:**
1. Added `RadioGroup` for tool type selection (Library/De Novo)
2. Renamed "Type" dropdown → "Parser"
3. Pass both `type` and `parser` to `project.add_tool()`:
   ```python
   await project.add_tool(
       name=name_field.value,
       type=tool_type_group.value,    # "Library" or "De Novo"
       parser=parser_dropdown.value,  # Parser name
       display_color=color
   )
   ```

### ToolsSection ✅

**Changes applied:**
1. Display both type and parser in subtitle:
   ```python
   subtitle_text = f"{len(ident_files)} files • {tool.type} ({tool.parser})"
   ```

### Import Logic 🔄

**Needs patching:**
- Line where parser is retrieved from tool:
  ```python
  # OLD: parser_class = registry.get_parser(tool.type, "identification")
  # NEW: parser_class = registry.get_parser(tool.parser, "identification")
  ```

## Status

- ✅ Core structure created
- ✅ Type/Parser patch applied in AddToolDialog
- ✅ Type/Parser patch applied in ToolsSection display
- 🔄 Need to finish import_logic with tool.parser patch
- 🔄 Need to create remaining sections and dialogs
- 🔄 Need to create main samples_tab.py composition
