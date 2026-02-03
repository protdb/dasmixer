# Peptides Tab - Modular Structure

## Overview

Peptides tab has been refactored into modular components for better maintainability.
Each section is responsible for specific functionality and shares state via `PeptidesTabState`.

## Structure

```
peptides/
├── __init__.py                    # Exports PeptidesTab
├── peptides_tab_new.py            # Main tab - composes all sections
├── shared_state.py                # Shared state object
├── base_section.py                # Base class for all UI sections
│
├── ion_calculations.py            # ✅ Backend service for ion calculations (NO UI)
├── tool_settings_section.py       # ✅ Tool configuration (with min/max length)
├── ion_settings_section.py        # ✅ Ion matching parameters
├── actions_section.py             # ✅ Calculate Peptides workflow
│
├── fasta_section.py               # 🔄 TODO: FASTA loading & protein mapping
├── matching_section.py            # 🔄 TODO: Identification matching
├── search_section.py              # 🔄 TODO: Search & view identifications
│
└── dialogs/
    ├── __init__.py
    └── progress_dialog.py         # ✅ Universal progress dialog
```

## Architecture

### NEW: Service vs Section Pattern

**Sections** (inherit from `BaseSection`):
- Have UI components
- Added to page layout
- Can access `self.page`

**Services** (plain classes):
- NO UI components  
- Accessed via `PeptidesTab` properties
- Use `ft.context.page` for page access

### IonCalculations Service

`IonCalculations` is a **singleton service** (not a section):

```python
# In PeptidesTab
self.ion_calculations = IonCalculations(self.project, self.state)

# In other sections
await self.parent_tab.ion_calculations.run_coverage_calc(recalc_all=False)
```

### Base Section Pattern

UI sections inherit from `BaseSection`:

```python
class MySection(BaseSection):
    def __init__(self, project, state):
        super().__init__(project, state)
    
    def _build_content(self) -> ft.Control:
        # Build UI
        return ft.Column([...])
    
    async def load_data(self):
        # Load initial data
        pass
    
    async def save_settings(self):
        # Save settings to project
        pass
```

### Shared State

`PeptidesTabState` holds:
- Tools list and controls
- Ion settings
- Protein count
- Search results
- Flags for UI updates

### Communication Between Sections

Sections communicate via:
1. **Shared State** - read/write common data
2. **Parent Tab Reference** - access other sections via `parent_tab.sections['name']`
3. **Services** - access singleton services via `parent_tab.ion_calculations`
4. **Direct Method Calls** - call `await other_section.method()`

### Using ft.context.page

All components use `ft.context.page` instead of `self.page` for safety:

```python
def show_error(self, message: str):
    """Show error snackbar using context."""
    try:
        page = ft.context.page  # ← Safe access from anywhere
        page.snack_bar = ft.SnackBar(...)
        page.update()
    except RuntimeError:
        print(f"ERROR: {message}")  # ← Fallback
```

This allows:
- ✅ Services to show messages without being added to page
- ✅ Safe access even if control not mounted
- ✅ Consistent API across sections and services

## Completed Sections

### IonCalculations Service ✅
- **NOT a section** - pure backend service
- Accessible via `peptides_tab.ion_calculations`
- Methods:
  - `run_coverage_calc(recalc_all)` - Calculate ion coverage
  - `calculate_protein_metrics_internal()` - Calculate protein metrics
  - `calculate_ion_coverage_dialog(e)` - Show dialog
- Uses `ft.context.page` for UI interactions

### ToolSettingsSection ✅
- Displays tool configurations
- **NEW:** Min/Max peptide length controls
- Validation and saving
- Provides `get_tool_settings_for_matching()` for other sections

### IonSettingsSection ✅
- Ion type selection (a,b,c,x,y,z)
- Loss options (H2O, NH3)
- PPM threshold and fragment charges
- Provides `get_ion_match_parameters()` for calculations

### ActionsSection ✅
- Main "Calculate Peptides" button
- Runs 4-step workflow:
  1. Match proteins
  2. Calculate ion coverage (via `ion_calculations` service)
  3. Calculate protein metrics (via `ion_calculations` service)
  4. Run identification matching
- Advanced options panel with direct access to:
  - Ion coverage calculations
  - Protein metrics
  - Matching
  - Protein mapping

## TODO Sections

### FastaSection
- FASTA file loading with progress
- Protein count display (NEW)
- BLAST settings
- Match proteins to identifications

### MatchingSection
- Preferred identification selection
- Criterion selection (PPM/Intensity)

### SearchSection
- Search identifications by various criteria
- Results table
- View spectrum plot with PlotlyViewer (NEW)

## Migration Plan

1. ✅ Create base structure (base_section, shared_state)
2. ✅ Create reusable components (ProgressDialog)
3. ✅ Implement simple sections (ToolSettings, IonSettings, Actions)
4. ✅ **Refactor IonCalculations to service pattern**
5. ✅ **Update all sections to use ft.context.page**
6. 🔄 Implement FASTA section
7. 🔄 Implement Matching section
8. 🔄 Implement Search section (with new PlotlyViewer integration)
9. 🔄 Update peptides_tab_new.py to include all sections
10. 🔄 Replace old peptides_tab.py with new version
11. 🔄 Test complete workflow

## Benefits

- **Modularity:** Each section ~100-200 lines vs 1000+ monolith
- **Testability:** Sections can be tested independently
- **Reusability:** Common components (ProgressDialog) shared
- **Maintainability:** Clear separation of concerns
- **Extensibility:** Easy to add new sections
- **NEW: Service Pattern:** Backend logic separated from UI
- **NEW: Safe Page Access:** Using `ft.context.page` everywhere

## Stage 4.1 Integration

All Stage 4.1 requirements are being integrated:
- ✅ Min/Max peptide length in ToolSettingsSection
- ✅ Actions section with Calculate Peptides workflow
- ✅ IonCalculations refactored to service pattern
- 🔄 Protein count display in FastaSection
- 🔄 PlotlyViewer integration in SearchSection
- 🔄 get_joined_peptide_data() usage in SearchSection
- 🔄 get_spectrum_plot_data() + make_full_spectrum_plot() in SearchSection
