# Code Review — Observations and Notes

This document captures observations made during code analysis, including architectural notes, potential problem areas, obsolete files, and improvement suggestions.

---

## Obsolete / Redundant Files

### `dasmixer/api/inputs/registry_new.py`

**Status:** Obsolete — exact duplicate of `registry.py`.

Both files contain the identical `InputTypesRegistry` class and `registry` singleton. `registry_new.py` is never imported anywhere in the codebase. Should be deleted.

**Action:** Delete `dasmixer/api/inputs/registry_new.py`.

### `dasmixer/api/project/project_spectra_mapping.py`

**Status:** Obsolete — dead code.

Contains a standalone `get_spectra_idlist` function that was intended to be "added to Project class". The actual method already exists in `SpectraMixin` with a different (better) implementation. This file is never imported.

**Action:** Delete `dasmixer/api/project/project_spectra_mapping.py`.

### `dasmixer/gui/views/tabs/proteins_tab_old.py`

**Status:** Obsolete — old version of the proteins tab.

The current proteins tab is in `tabs/proteins/`. This file is not imported. Contains an old monolithic implementation.

**Action:** Delete `dasmixer/gui/views/tabs/proteins_tab_old.py`.

### `dasmixer/gui/views/tabs/samples_tab_old.py` and `samples_tab_patch.txt`

**Status:** Obsolete — old sample tab version + patch file.

Current samples tab is in `tabs/samples/`. Neither file is imported.

**Action:** Delete both files.

### `dasmixer/api/project/mixins/fast_ident_match_mixin.py`

**Status:** Unclear — not included in `Project` composition in `project.py`.

The mixin exists but is not imported in `mixins/__init__.py` and not composed into `Project`. Either it's work-in-progress or abandoned.

**Action:** Investigate — include in `Project` if needed, or delete.

### `apply_project_patch.py` (root)

**Status:** One-time migration script, should not be in project root.

**Action:** Delete or move to `docs/obsolete/`.

### `check_ppm.py`, `temp_set_pref.py`, `processed_spectra_files.txt`, `best_ids.txt` (root)

**Status:** Temporary debug/testing files. Should not be in project root.

**Action:** Delete these files.

---

## Architectural Observations

### Debug `print()` Statements Throughout Codebase

Multiple locations have `print()` calls left from development:
- `identification_mixin.py:28` — `print(f"spectra_file_id: ...")`
- `peptide_mixin.py:439, 596` — `print(query)`, `print(params)`
- `sample_mixin.py` — various print statements in stats methods
- `spectra_mixin.py:259` — `print(f'getting idlist: ...')`
- `protein_mixin.py` — multiple print statements
- `lfq.py` — multiple print statements in calculate_lfq
- `matching.py:143` — print statements

**Recommendation:** Replace all debug prints with logger calls (`from dasmixer.utils.logger import logger`). The logger infrastructure already exists.

### `lifecycle.py` — Unused Import

`from flet.controls.core import row` in `lifecycle.py:8` — this is an unused import that doesn't belong in a database lifecycle module. Likely a leftover from copy-paste.

**Action:** Remove the import.

### `save_as` Implementation

`ProjectLifecycle.save_as()` works by file copy for file-based projects. For in-memory databases, it uses SQLite's backup API. The file-copy approach has a race condition: if the app crashes between `close()` and `shutil.copy2()`, the current project is lost. Consider using SQLite backup API for both cases.

### `IdentificationMixin.set_preferred_identifications_for_file`

This method uses f-string SQL construction for IN clauses:
```python
f"UPDATE identification SET is_preferred = 0 WHERE id IN ({', '.join([str(x) for x in ids])})"
```

This is vulnerable to SQL injection if `ids` contains non-integer values. Should use SQLite's parameterized query with `?` placeholders. The list size could also be very large (tens of thousands).

**Recommendation:** Use `executemany` or chunked parameterized queries.

### `get_joined_peptide_data` — Large Query Performance

The central peptide query uses multiple subqueries as derived tables joined via LEFT JOIN. For very large projects (>1M identifications), this may become slow without additional indexing. Current indexes cover the individual table columns but not the join conditions in derived tables.

**Observation:** Consider materialized views or additional indexes if performance becomes an issue.

### `calculate_lfq` Debug Output

`calculations/proteins/lfq.py` contains multiple `print()` statements in production code that print large DataFrames to stdout. This is significant noise during actual runs.

### `process_identificatons_batch` — Typo in Function Name

The function name has a typo: `process_identificatons_batch` (missing 'i' in 'identifications'). Since it's a module-level function used via reflection/direct import, renaming requires care. But it should be fixed.

### `SampleMixin.get_sample_status_summary` — Inconsistent Threshold Logic

The method uses `min_proteins=30` and `min_idents=1000` as default thresholds for OK/WARNING, but these are hardcoded defaults that differ from the GUI's configurable settings in `SamplesSection`. The GUI-level thresholds and these API defaults may diverge.

**Recommendation:** Either pass these as parameters always (no defaults), or remove them from the API and compute status purely in the GUI layer.

---

## Potential Bugs

### `BaseReport._apply_settings_to_figure` — KeyError

```python
height=int(self._project_settings.get('plot_height')),
```

If `plot_height` is not set (returns `None`), `int(None)` raises `TypeError`. The `plot_width` call correctly uses a default but `plot_height` doesn't.

**Fix:** Add default: `self._project_settings.get('plot_height', 800)`.

### `IdentificationWithSpectrum` — Non-nullable Fields on `from_dict`

The dataclass declares `id: int`, `spectre_id: int`, etc. as non-nullable, but `from_dict` passes `data.get(...)` which can return `None`. This causes type errors at runtime when DB rows have NULL values (rare but possible with corrupted data).

**Observation:** Add defensive handling or mark fields as nullable.

### `matching.py:select_preferred_identifications` — Old Implementation

This is an older version that calls `get_identifications()` for each file/tool combination, which is N+1 queries. The newer `calculate_preferred_identifications_for_file()` uses `get_idents_for_preferred()` which is much more efficient. The old function may still be called in some code paths.

**Check:** Ensure all GUI actions use `calculate_preferred_identifications_for_file`.

---

## Improvement Suggestions

### Type Annotations for Mixin Methods

Mixin classes currently don't declare protocol/type stubs for the methods they consume from other mixins (`_execute`, `_fetchone`, etc.). This causes IDE type checking errors (LSP errors visible throughout). Options:
1. Use `Protocol` to declare the required interface
2. Add `if TYPE_CHECKING:` imports
3. Use `# type: ignore` comments selectively

This is a code quality / developer experience issue, not a runtime bug.

### Configuration for Plot Defaults

`_apply_settings_to_figure` fetches settings from `project_settings` table. But `plot_height` is not set during project creation and has no default in `DEFAULT_METADATA`. Consider adding plot settings to `DEFAULT_METADATA` or always providing fallbacks.

### Batch Import for Identification Files (CLI)

`import ident-file` and `import ident-pattern` commands are stubbed out ("Coming in next development phase"). These are important for batch automation workflows.

### Worker Logging Location

Worker logs go to `~/.cache/dasmixer/worker_logs/`. On Windows, `Path.home() / ".cache"` may not be the conventional location (should be `%LOCALAPPDATA%` or `%TEMP%`). Consider using `typer.get_app_dir("dasmixer")` for cross-platform consistency.

### `calculate_lfq` — Missing Error Handling

If `fasta[protein_id]` raises `KeyError` (protein in identification results but not in FASTA), the whole LFQ calculation fails. Should add defensive lookup and log warnings for missing proteins.

### Report Parameters Persistence

`ReportMixin.get_report_parameters` / `save_report_parameters` store parameters as a string (`key=value\n...` format). This is a legacy format from before typed ReportForm. If all reports migrate to `ReportForm`, these methods could be removed or replaced with JSON storage.

---

## Summary

### Files to Delete
- `dasmixer/api/inputs/registry_new.py`
- `dasmixer/api/project/project_spectra_mapping.py`
- `dasmixer/gui/views/tabs/proteins_tab_old.py`
- `dasmixer/gui/views/tabs/samples_tab_old.py`
- `dasmixer/gui/views/tabs/samples_tab_patch.txt`
- `apply_project_patch.py` (root)
- `check_ppm.py`, `temp_set_pref.py`, `processed_spectra_files.txt`, `best_ids.txt` (root)

### Files to Fix (Critical)
- `lifecycle.py` — remove unused `flet` import
- `base_report.py` — fix `plot_height` missing default
- `identification_mixin.py` — fix SQL injection in `set_preferred_identifications_for_file`

### Files to Fix (Non-critical)
- All files with `print()` → replace with `logger.*`
- Rename `process_identificatons_batch` → `process_identifications_batch`
- `fast_ident_match_mixin.py` — determine if needed or delete
