# Proteins Tab Architecture

**Version:** 1.0  
**Date:** 2026-02-04

## Overview

The Proteins tab provides protein identification and label-free quantification functionality. It follows a modular architecture similar to the Peptides tab.

## Structure

```
gui/views/tabs/proteins/
├── __init__.py              # Export ProteinsTab
├── proteins_tab.py          # Main tab container
├── shared_state.py          # Shared state between sections
├── base_section.py          # Base class for sections
├── detection_section.py     # Protein identification calculation
├── lfq_section.py           # Label-free quantification
├── table_section.py         # Results display
└── README.md               # This file
```

## Components

### ProteinsTab (proteins_tab.py)

Main container that composes all sections. Handles:
- Section creation and lifecycle
- Initial data loading
- Global refresh operations

### ProteinsTabState (shared_state.py)

Centralized state management with:
- Detection parameters (min peptides, min unique evidence)
- LFQ parameters (methods, enzyme, peptide length, cleavage sites)
- Table state (selected sample filter)
- Cached data and counts

### BaseSection (base_section.py)

Abstract base class providing:
- Standard container styling
- Snackbar helpers (success, error, warning, info)
- Abstract `_build_content()` method
- Optional `load_data()` method

### DetectionSection (detection_section.py)

Protein identification calculation:
- Input fields for min peptides and unique evidence
- Settings persistence via project_settings
- Progress dialog during calculation
- Calls `find_protein_identifications()` from API
- Auto-refresh table after completion

### LFQSection (lfq_section.py)

Label-free quantification:
- Method checkboxes (emPAI, iBAQ, NSAF, Top3)
- Enzyme dropdown with all supported enzymes
- Peptide length and cleavage parameters
- Settings persistence via project_settings
- Progress dialog during calculation
- Iterates over all samples
- Auto-refresh table after completion

### TableSection (table_section.py)

Results display:
- 13-column DataTable with protein results
- Sample filter dropdown
- Joined protein identification and quantification data
- Formatted display (coverage %, scientific notation)

## Data Flow

```
User Input → Section Handler → Project API → Database
                                              ↓
UI Update ← State Update ← Data Transform ← Query Result
```

## Settings Persistence

All parameters are saved to `project_settings`:
- `proteins_min_peptides`
- `proteins_min_unique_evidence`
- `lfq_method_emPAI`, `lfq_method_iBAQ`, `lfq_method_NSAF`, `lfq_method_Top3`
- `lfq_empai_base`
- `lfq_enzyme`
- `lfq_min_peptide_length`
- `lfq_max_peptide_length`
- `lfq_max_cleavage_sites`

## API Methods Used

### From Project:
- `get_setting()` / `set_setting()`
- `clear_protein_identifications()`
- `add_protein_identifications_batch()`
- `get_protein_identification_count()`
- `clear_protein_quantifications()`
- `add_protein_quantifications_batch()`
- `get_protein_quantification_count()`
- `get_protein_results_joined()`
- `get_joined_peptide_data()`
- `get_protein_db_to_search()`

### From api.proteins:
- `find_protein_identifications()` - async iterator returning (DataFrame, sample_id)
- `calculate_lfq()` - calculates LFQ for one sample

## Progress Dialogs

All long-running operations show progress:
- Detection: "Processing sample X of Y"
- LFQ: "Processing sample X of Y"

Uses `ProgressDialog` from peptides dialogs.

## Error Handling

- Input validation before API calls
- Try-catch around async operations
- Informative user messages via snackbars
- Console logging for debugging

## Future Enhancements

- Sortable table columns
- Export to Excel
- Protein-level filtering
- UniProt enrichment integration
- Volcano plots
