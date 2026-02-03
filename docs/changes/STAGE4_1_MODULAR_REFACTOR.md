# Stage 4.1 - Modular Refactoring of Peptides Tab

**Date:** 2026-02-03  
**Status:** In Progress

## Overview

Peptides tab has been refactored from a monolithic 800+ line file into modular components for better maintainability and extensibility.

## Changes Made

### 1. Database Schema Updates

**File: `api/project/schema.py`**
- Added `parser` field to `tool` table
- Updated `tool.type` to store "Library" or "De Novo"
- Added `name` field to `protein` table
- Added `uniprot_data` BLOB field to `protein` table

**File: `api/project/dataclasses.py`**
- Updated `Tool` dataclass:
  - `type: Literal['Library', 'De Novo']` - tool category
  - `parser: str` - parser name (renamed from old 'type')
- Updated `Protein` dataclass:
  - `name: str | None` - short protein name
  - `uniprot_data: UniprotData | None` - UniProt enrichment data

### 2. Project API Updates

**File: `api/project/project.py`**

**New Methods:**
- `get_protein_count()` - count total proteins in database
- `get_joined_peptide_data(**filters)` - universal filtered query for peptides
- `get_spectrum_plot_data(spectrum_id)` - get all data for plotting spectrum

**Modified Methods:**
- `add_tool(name, type, parser, ...)` - added `parser` parameter
- `update_tool(tool)` - updated to include `parser`
- `add_protein(..., name, uniprot_data)` - added new fields
- `add_proteins_batch(df)` - handle new fields with serialization
- `get_protein(id)` - deserialize uniprot_data
- `get_proteins()` - deserialize uniprot_data
- `get_identification_files()` - return `tool_parser` instead of `tool_type`
- `get_identifications()` - return `tool_parser` instead of `tool_type`

**Helper Functions:**
- `_serialize_uniprot_data()` - pickle + gzip compression
- `_deserialize_uniprot_data()` - decompress + unpickle

### 3. Matching Logic Updates

**File: `api/peptides/matching.py`**

**Modified:**
- `select_preferred_identifications()` - added peptide length filtering:
  - `min_peptide_length` parameter (default 7)
  - `max_peptide_length` parameter (default 30)
  - Filters by `canonical_sequence` length

### 4. Modular Structure

**New Directory: `gui/views/tabs/peptides/`**

```
peptides/
├── __init__.py                    # Exports PeptidesTab
├── peptides_tab_new.py            # Main tab composition
├── shared_state.py                # Shared state object
├── base_section.py                # Base class for sections
├── fasta_section.py               # FASTA loading + protein count
├── tool_settings_section.py       # Tool config (with min/max length)
├── ion_settings_section.py        # Ion matching parameters
├── actions_section.py             # Calculate Peptides workflow
├── matching_section.py            # Preferred ID selection
├── search_section.py              # Search + PlotlyViewer integration
├── ion_calculations.py            # Ion coverage calculations
├── dialogs/
│   ├── __init__.py
│   └── progress_dialog.py         # Reusable progress dialog
└── README.md                      # Documentation
```

### 5. New Features (Stage 4.1)

**Tool Settings:**
- ✅ Min Peptide Length (default 7)
- ✅ Max Peptide Length (default 30)

**FASTA Section:**
- ✅ Protein count display: "(X proteins in database)"
- ✅ Updates after loading FASTA

**Actions Section (NEW):**
- ✅ "Calculate Peptides" button - runs 4-step workflow:
  1. Match proteins to identifications
  2. Calculate ion coverage (only missing)
  3. Calculate PPM and coverage for protein matches
  4. Run identification matching
- ✅ ExpansionPanel "Advanced Options" with individual step buttons

**Search Section:**
- ✅ Uses `get_joined_peptide_data()` for filtering
- 🔄 Uses `PlotlyViewer` with `make_full_spectrum_plot()` (in progress)
- 🔄 Shows all identifications for spectrum in single plot

### 6. Architecture Benefits

**Before:**
- 1 file, 800+ lines
- Hard to navigate and maintain
- Tightly coupled logic

**After:**
- 13 files, ~100-200 lines each
- Clear separation of concerns
- Shared state pattern for communication
- Reusable components (ProgressDialog)
- Easy to test and extend

### 7. Migration Notes

**Breaking Changes:**
- Tool structure changed: `type` now means "Library/De Novo", parser name moved to `parser` field
- Old project files need schema update (but no backward compatibility required at this stage)

**Import Changes:**
```python
# Old
from gui.views.tabs.peptides_tab import PeptidesTab

# New
from gui.views.tabs.peptides import PeptidesTab
```

### 8. Testing Checklist

- [ ] Create new project
- [ ] Load FASTA - check protein count display
- [ ] Add tool with type selection (Library/De Novo)
- [ ] Configure tool settings (including min/max length)
- [ ] Load MGF files
- [ ] Load identifications
- [ ] Run "Calculate Peptides" workflow
- [ ] Search identifications
- [ ] View spectrum with PlotlyViewer
- [ ] Verify all 4 steps execute correctly
- [ ] Check filtering by peptide length works

### 9. Files Modified

**API:**
- `api/project/schema.py`
- `api/project/dataclasses.py`
- `api/project/project.py`
- `api/peptides/matching.py`

**GUI:**
- `gui/views/project_view.py` - updated import
- `gui/views/tabs/peptides_tab.py` - will be replaced
- `gui/views/tabs/peptides/*` - new modular structure

### 10. Next Steps

- [ ] Test modular structure
- [ ] Update samples_tab.py for new tool creation (type + parser)
- [ ] Update any other files using `tool.type` to use `tool.parser`
- [ ] Complete PlotlyViewer integration in search_section.py
- [ ] Document API changes
