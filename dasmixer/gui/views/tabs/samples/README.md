# Samples Tab - Structure and Components

This document describes the organization of the Samples tab, which has been refactored into a modular structure.

## Overview

The Samples tab manages:
- **Comparison Groups (Subsets)**: Define groups for comparative analysis
- **Identification Tools**: Configure tools used for peptide identification
- **Samples**: Manage individual samples and their properties
- **Data Import**: Import spectra and identification files

## File Structure

```
gui/views/tabs/samples/
├── __init__.py                 # Package initialization, exports SamplesTab
├── samples_tab.py              # Main tab container, coordinates all sections
├── shared_state.py             # Shared state between sections (counts, flags)
├── base_section.py             # Base class for all sections
├── constants.py                # Constants (default colors for groups/tools)
├── groups_section.py           # Groups management section
├── tools_section.py            # Tools management section
├── import_section.py           # Import spectra section
├── samples_section.py          # Samples list section
├── import_handlers.py          # Import processing logic
└── dialogs/                    # Dialog components
    ├── __init__.py
    ├── group_dialog.py         # Create/edit group dialog
    ├── tool_dialog.py          # Create/edit tool dialog
    ├── sample_dialog.py        # Edit sample dialog
    ├── import_mode_dialog.py   # Select import mode dialog
    ├── import_pattern_dialog.py # Pattern-based import dialog
    └── import_single_dialog.py # Single file import dialog
```

## Architecture

### Main Components

#### `SamplesTab` (samples_tab.py)
- Main container for the entire tab
- Coordinates all sections
- Handles import dialog chains
- Manages refresh cycles

#### Sections (inheriting from `BaseSection`)
- **GroupsSection**: Displays and manages comparison groups
- **ToolsSection**: Displays and manages identification tools  
- **ImportSection**: Button to trigger spectra import
- **SamplesSection**: Displays sample list with edit capability

#### Dialogs
All dialogs are self-contained components that:
- Take project, page, and callbacks as constructor parameters
- Handle their own UI and validation
- Call callbacks on success
- Show appropriate error/success messages

#### Import Handlers
`ImportHandlers` class encapsulates the complex import logic:
- Progress dialog display
- File parsing and validation
- Batch processing
- Database updates
- Error handling

### Shared State

`SamplesTabState` dataclass holds:
- Counts (groups, tools, samples, etc.)
- Refresh flags for coordination between sections

### Constants

`constants.py` defines:
- **DEFAULT_COLORS**: List of 10 colors for groups/tools
- **get_default_color(index)**: Function to get color by index (cycles through list)

## Key Features

### Edit Functionality
- Groups: Add, edit (name, description, color), delete
- Tools: Add, edit (name, type, parser, color), delete
- Samples: Edit (name, group, additions JSON)

### Default Colors
When creating new groups or tools, a color is automatically selected from a predefined list:
```python
DEFAULT_COLORS = [
    "#0000FF",  # Blue
    "#FF0000",  # Red
    "#008000",  # Green
    "#FF00FF",  # Magenta
    "#00FFFF",  # Cyan
    "#FFD700",  # Gold
    "#FF8000",  # Orange
    "#8000FF",  # Purple
    "#FF0080",  # Pink
    "#00FF80"   # Spring Green
]
```
The color is selected by index = (count of existing items) % 10.

### Sample Editing
Samples can now be edited via a dialog (no more inline dropdowns for groups):
- **Name**: Text field
- **Group**: Dropdown selector
- **Additions**: JSON text field for LFQ parameters (e.g., `{"albumin": 45.5, "total_protein": 70.0}`)

### Import Workflow
1. User clicks "Import Spectra" or "Import Identifications" button
2. ImportModeDialog shows: "Select individual files" or "Pattern matching from folder"
3. Based on selection:
   - **Single files**: ImportSingleDialog opens file picker, then shows config dialog
   - **Pattern matching**: ImportPatternDialog allows folder selection and pattern configuration
4. ImportHandlers processes files with progress indication
5. On completion, all sections refresh

## Migration Notes

The old monolithic `samples_tab.py` has been refactored into this modular structure:
- Better separation of concerns
- Easier testing and maintenance
- Reusable dialog components
- Cleaner state management

## Usage

From other modules:
```python
from gui.views.tabs.samples import SamplesTab

# Create tab
samples_tab = SamplesTab(project)

# Tab will automatically load data on mount
```

## Future Enhancements

Possible improvements:
- Bulk edit for samples
- Drag-and-drop file import
- Export/import of groups and tools configuration
- Sample filtering and search
- More detailed sample statistics
