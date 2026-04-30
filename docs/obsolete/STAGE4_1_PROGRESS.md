# Stage 4.1 Implementation Progress

**Date:** 2026-02-03  
**Status:** In Progress - Core components complete, testing needed

---

## Completed ✅

### 1. Database Schema & Models

**Files Modified:**
- ✅ `api/project/schema.py`
- ✅ `api/project/dataclasses.py`
- ✅ `api/project/project.py`

**Changes:**
- Added `tool.type` ("Library"/"De Novo") and `tool.parser` (parser name)
- Added `protein.name` and `protein.uniprot_data` (BLOB)
- Implemented serialization/deserialization for UniprotData
- Added `get_protein_count()` method
- Added `get_joined_peptide_data(**filters)` method
- Added `get_spectrum_plot_data(spectrum_id)` method

### 2. Matching Logic

**Files Modified:**
- ✅ `api/peptides/matching.py`

**Changes:**
- Added peptide length filtering in `select_preferred_identifications()`
- Parameters: `min_peptide_length` (default 7), `max_peptide_length` (default 30)
- Filters identifications by `canonical_sequence` length

### 3. Modular Peptides Tab Structure

**New Files Created:**

```
gui/views/tabs/peptides/
├── __init__.py                    ✅ Exports PeptidesTab
├── peptides_tab_new.py            ✅ Main composition
├── shared_state.py                ✅ Shared state object
├── base_section.py                ✅ Base class
├── fasta_section.py               ✅ FASTA + protein count
├── tool_settings_section.py       ✅ Tool config (with min/max length)
├── ion_settings_section.py        ✅ Ion parameters
├── actions_section.py             ✅ Calculate Peptides workflow
├── matching_section.py            ✅ Preferred ID selection
├── search_section.py              ✅ Search + PlotlyViewer
├── ion_calculations.py            ✅ Coverage calculations
├── dialogs/
│   ├── __init__.py                ✅
│   └── progress_dialog.py         ✅ Reusable dialog
└── README.md                      ✅ Documentation
```

**Files Modified:**
- ✅ `gui/views/project_view.py` - updated import to use peptides package

### 4. Features Implemented

**Tool Settings:**
- ✅ Min Peptide Length field (default 7)
- ✅ Max Peptide Length field (default 30)
- ✅ Validation for length fields
- ✅ Save/load from tool.settings JSON

**FASTA Section:**
- ✅ Protein count display: "(X proteins in database)"
- ✅ Updates after loading FASTA
- ✅ Updates in shared state

**Actions Section (NEW):**
- ✅ "Calculate Peptides" button
- ✅ 4-step workflow implementation
- ✅ ExpansionPanel with "Advanced Options"
- ✅ Individual step buttons in advanced panel

**Search Section:**
- ✅ Uses `get_joined_peptide_data()` for filtering
- ✅ Uses `get_spectrum_plot_data()` for plot data
- ✅ Integrated PlotlyViewer component
- ✅ Shows all identifications for spectrum in single plot

---

## Remaining Work 🔄

### 1. Update samples_tab.py

**File:** `gui/views/tabs/samples_tab.py`

**Changes Needed:**
- Update `show_add_tool_dialog()`:
  - Add RadioGroup for tool type (Library/De Novo)
  - Rename "Type" → "Parser"
  - Pass both `type` and `parser` to `project.add_tool()`
  
- Update `import_identification_files()`:
  - Line ~570: Change `tool.type` → `tool.parser`
  
- Update `refresh_tools()`:
  - Line ~130: Display both type and parser in subtitle

**Patch file created:** `gui/views/tabs/samples_tab_patch.txt`

### 2. Test Complete Workflow

- [ ] Create new project
- [ ] Load FASTA - verify protein count
- [ ] Add tool with type selection
- [ ] Configure tool settings
- [ ] Import MGF files
- [ ] Import identifications
- [ ] Run "Calculate Peptides"
- [ ] Verify all 4 steps execute
- [ ] Search identifications
- [ ] View spectrum with PlotlyViewer

### 3. Fix Any Import Issues

- [ ] Check all imports resolve correctly
- [ ] Verify no circular dependencies
- [ ] Test page.peptides_tab reference works

### 4. Clean Up

- [ ] Remove old `peptides_tab.py` (or rename to `_old`)
- [ ] Remove `project_patch.py` (integrated into project.py)
- [ ] Remove patch files after integration

---

## Known Issues

1. **samples_tab.py not yet updated** - requires manual integration of patch
2. **FilePicker async API** - may need adjustment based on actual Flet API
3. **Section cross-references** - some sections reference others via parent_tab, needs testing

---

## Testing Instructions

### Manual Testing Steps:

1. **Start application**
   ```
   python -m gui.app
   ```

2. **Create new project**

3. **Test Peptides Tab Load:**
   - Switch to Peptides tab
   - Verify no errors in console
   - Verify all sections visible

4. **Test Tool Settings:**
   - Add tool in Samples tab (after updating samples_tab.py)
   - Check that min/max peptide length fields appear
   - Try saving settings

5. **Test FASTA Loading:**
   - Load FASTA file
   - Verify protein count updates

6. **Test Calculate Peptides:**
   - Click "Calculate Peptides" button
   - Verify all 4 steps execute in sequence
   - Check progress dialogs appear

7. **Test Search:**
   - Search for identifications
   - Click "View" on a result
   - Verify PlotlyViewer appears
   - Try interactive mode

---

## Migration from Old to New

The new modular structure is **backward compatible** at the import level:

```python
# This still works (imports from peptides package)
from gui.views.tabs.peptides import PeptidesTab
```

The old monolithic file `gui/views/tabs/peptides_tab.py` can be:
- Kept as `peptides_tab_old.py` for reference
- Or deleted once new version is confirmed working

---

## Next Session Tasks

1. Update samples_tab.py with patch
2. Test complete workflow
3. Fix any bugs found during testing
4. Document user-facing changes
5. Update API documentation

---

**End of Progress Report**
