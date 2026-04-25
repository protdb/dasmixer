# DASMixer — AI Agent Development Guide

This document provides essential context for AI coding agents working on the DASMixer project.

---

## Project Overview

**DASMixer** is a cross-platform desktop proteomics application built with Flet (Python). It integrates de novo peptide sequencing results with library search identifications and performs comparative proteomics analysis.

- **Lab:** Laboratory of Structural Proteomics, IBMC, Moscow
- **Repo:** `git@github.com:protdb/dasmixer.git`
- **Package name:** `dasmixer`
- **Entry point:** `dasmixer/main.py` → `dasmixer` CLI command


**MOST IMPORTANT DOCUMENT WITH DETAILS:** `docs/project/MASTER_SPEC_NEW.md`
---

## Technology Stack

| Component | Library/Version |
|---|---|
| GUI | **Flet 0.80.5** (flet[all] >=0.80.4,<0.81.0) |
| CLI | Typer >=0.21 |
| Interactive plots | Plotly + PyWebView 6.x |
| Data | Pandas >=2.3, NumPy >=2.4 |
| Proteomics | Pyteomics, Peptacular, Npysearch |
| DB | SQLite via **aiosqlite** (async) |
| Config | pydantic-settings |
| Build | Poetry (pyproject.toml) |

---

## Flet 0.80.5 — Critical API Notes

Flet 0.80.5 introduced breaking API changes. Always use the new API:

| Old (broken) | New (correct) |
|---|---|
| `ft.DropdownOption(...)` | `ft.Dropdown.Option(...)` |
| `ft.alignment.center` | `ft.Alignment.CENTER` |
| `ft.alignment.top_left` | `ft.Alignment.TOP_LEFT` |
| `ft.colors.RED` | `ft.Colors.RED` |
| `ft.icons.ADD` | `ft.Icons.ADD` |
| `page.go("/route")` | Manual `_route_change()` — `page.go()` is async, avoid in `__init__` |
| `ft.FilePicker` as overlay | Use `await ft.FilePicker().pick_files(...)` directly (no page overlay needed) |
| `page.window_width` | `page.window.width` |

**FilePicker pattern (correct for 0.80.5):**
```python
files = await ft.FilePicker().pick_files(
    dialog_title="Open File",
    file_type=ft.FilePickerFileType.CUSTOM,
    allowed_extensions=["dasmix"],
    allow_multiple=False
)
if files and files[0].path:
    path = files[0].path

# For save dialog:
file_path = await ft.FilePicker().save_file(
    dialog_title="Save File",
    file_name="project.dasmix",
    file_type=ft.FilePickerFileType.CUSTOM,
    allowed_extensions=["dasmix"]
)
```

**Routing in 0.80.5:** `page.on_route_change` handler receives no argument (unlike older versions).
Use the pattern in `dasmixer/gui/app.py:DASMixerApp._route_change`.

---

## Source Layout

```
dasmixer/
├── main.py                 # CLI entry point (Typer app + GUI launcher)
├── api/
│   ├── config.py           # AppConfig (pydantic-settings), global `config` instance
│   ├── plugin_loader.py    # Dynamic plugin loading
│   ├── project/
│   │   ├── project.py      # Project class (composed from mixins)
│   │   ├── schema.py       # SQLite schema SQL
│   │   ├── dataclasses.py  # Subset, Tool, Sample, Protein, IdentificationWithSpectrum
│   │   ├── array_utils.py  # compress_array / decompress_array (numpy ↔ bytes)
│   │   ├── core/
│   │   │   ├── base.py         # ProjectBase: _execute, _fetchone, _fetchall, _executemany, etc.
│   │   │   └── lifecycle.py    # ProjectLifecycle: initialize, save, close, context manager
│   │   └── mixins/
│   │       ├── subset_mixin.py
│   │       ├── tool_mixin.py
│   │       ├── sample_mixin.py
│   │       ├── spectra_mixin.py
│   │       ├── identification_mixin.py
│   │       ├── peptide_mixin.py
│   │       ├── protein_mixin.py
│   │       ├── plot_mixin.py
│   │       ├── query_mixin.py
│   │       └── report_mixin.py
│   ├── inputs/
│   │   ├── base.py             # BaseImporter ABC
│   │   ├── registry.py         # InputTypesRegistry + global `registry`
│   │   ├── spectra/
│   │   │   ├── base.py         # SpectralDataParser ABC
│   │   │   └── mgf.py          # MGFParser
│   │   ├── peptides/
│   │   │   ├── base.py         # IdentificationParser ABC
│   │   │   ├── table_importer.py  # SimpleTableImporter base
│   │   │   ├── PowerNovo2.py
│   │   │   ├── MQ_Evidences.py
│   │   │   └── PLGS.py
│   │   └── proteins/
│   │       └── fasta.py        # FASTA importer
│   ├── calculations/
│   │   ├── spectra/
│   │   │   ├── ion_match.py          # IonMatchParameters, match_predictions, get_matches_dataframe
│   │   │   ├── identification_processor.py  # Batch worker for PPM+coverage calculation
│   │   │   ├── coverage_worker.py
│   │   │   ├── plot_flow.py
│   │   │   └── plot_matches.py
│   │   ├── peptides/
│   │   │   ├── matching.py           # select_preferred_identifications
│   │   │   └── protein_map.py        # npysearch BLAST wrapper
│   │   ├── proteins/
│   │   │   ├── lfq.py               # calculate_lfq (emPAI, iBAQ, NSAF, Top3)
│   │   │   ├── map_identifications.py  # find_protein_identifications
│   │   │   └── sempai/              # LFQ computation library
│   │   └── ppm/
│   │       ├── dataclasses.py       # SeqMatchParams, SeqResults
│   │       └── seqfixer.py          # SeqFixer: charge/isotope correction for de novo
│   └── reporting/
│       ├── base.py         # BaseReport ABC
│       ├── registry.py     # ReportRegistry + global `registry`
│       ├── viewer.py       # Interactive report viewer (PyWebView)
│       └── reports/        # Concrete report implementations
│           ├── pca_report.py
│           ├── volcano_report.py
│           ├── upset.py
│           ├── coverage_report.py
│           ├── sample_report.py
│           └── toolmatch_report.py
├── gui/
│   ├── app.py              # DASMixerApp: routing, project lifecycle, AppBar
│   ├── utils.py            # show_snack, other GUI helpers
│   ├── components/         # Reusable UI components
│   │   ├── base_table_view.py
│   │   ├── base_plot_view.py
│   │   ├── base_table_and_plot_view.py
│   │   ├── plotly_viewer.py    # PyWebView integration for Plotly
│   │   ├── progress_dialog.py
│   │   └── report_form.py      # ReportForm base for typed report parameters
│   ├── actions/            # Async action handlers (GUI → API bridge)
│   │   ├── base.py
│   │   ├── ion_actions.py
│   │   ├── lfq_action.py
│   │   ├── protein_ident_action.py
│   │   └── protein_map_action.py
│   └── views/
│       ├── start_view.py
│       ├── project_view.py     # ProjectView: lazy tab loading + suspend/resume
│       ├── settings_view.py
│       ├── plugins_view.py
│       ├── manage_samples_view.py
│       └── tabs/
│           ├── samples/        # Samples tab sections
│           ├── peptides/       # Peptides tab sections
│           ├── proteins/       # Proteins tab sections
│           ├── reports/        # Reports tab
│           └── plots/          # Saved plots tab
└── cli/
    └── commands/
        ├── project.py      # create command
        ├── subset.py       # subset add/list/delete
        └── import_data.py  # mgf-file, mgf-pattern, ident-file, ident-pattern
```

---

## Project Class

`dasmixer.api.project.project.Project` is the central data access object. It is a **Python class composed entirely from mixins** — no logic in `Project` itself.

```python
from dasmixer.api.project.project import Project

# Create new project
project = Project(path="my.dasmix", create_if_not_exists=True)
await project.initialize()

# Open existing
project = Project(path="my.dasmix", create_if_not_exists=False)
await project.initialize()

# As context manager (auto-saves on exit)
async with Project(path="my.dasmix") as project:
    samples = await project.get_samples()
```

All methods are **async**. The database uses WAL mode and has foreign keys enabled.

### Key Project Methods by Domain

**Lifecycle** (`core/lifecycle.py`):
- `initialize()`, `save()`, `save_as(path)`, `close()`
- `get_metadata()`, `set_setting(key, value)`, `get_setting(key, default)`

**Subsets** (`mixins/subset_mixin.py`):
- `add_subset(name, details, display_color)` → `Subset`
- `get_subsets()` → `list[Subset]`
- `update_subset(subset)`, `delete_subset(id)`

**Tools** (`mixins/tool_mixin.py`):
- `add_tool(name, type, parser, settings, display_color)` → `Tool`
  - `type`: `"Library"` or `"De Novo"`
  - `parser`: parser name string (e.g. `"PowerNovo2"`, `"MGF"`)
- `get_tools()` → `list[Tool]`, `get_tool(id)` → `Tool | None`

**Samples** (`mixins/sample_mixin.py`):
- `add_sample(name, subset_id, additions, outlier)` → `Sample`
- `get_samples(subset_id?)` → `list[Sample]`
- `get_sample_stats(id)`, `get_cached_sample_stats(id)`
- `compute_and_cache_sample_stats(id)`

**Spectra** (`mixins/spectra_mixin.py`):
- `add_spectra_file(sample_id, format, path)` → `int`
- `add_spectra_batch(spectra_file_id, spectra_df)` — batch insert
- `get_spectra(spectra_file_id?, sample_id?, limit?, offset?)` → `DataFrame`
- `get_spectrum_full(spectrum_id)` → `dict` (includes decompressed arrays)
- `get_spectra_idlist(spectra_file_id, by="seq_no")` → `list[dict]`

**Identifications** (`mixins/identification_mixin.py`):
- `add_identification_file(spectra_file_id, tool_id, file_path)` → `int`
- `add_identifications_batch(identifications_df)` — batch insert
- `get_identifications(...)` → `DataFrame`
- `get_identifications_with_spectra_batch(tool_id, offset, limit, only_missing?, spectra_file_ids?)` → `list[IdentificationWithSpectrum]`
- `put_identification_data_batch(data_rows)` — update PPM/coverage fields
- `set_preferred_identification(spectre_id, identification_id)`

**Peptide matches** (`mixins/peptide_mixin.py`):
- `add_peptide_matches_batch(matches_df)`
- `get_joined_peptide_data(**filters)` → `DataFrame` (full joined view)
- `count_joined_peptide_data(**filters)` → `int`

**Proteins** (`mixins/protein_mixin.py`):
- `add_proteins_batch(proteins_df)`, `get_protein(id)` → `Protein | None`
- `add_protein_identifications_batch(identifications_df)`
- `get_protein_results_joined(**filters)` → `DataFrame`
- `get_protein_quantification_data(method?, subsets?, protein_id?)` → `DataFrame`
- `calculate_lfq(...)` via `dasmixer.api.calculations.proteins.lfq`

**Raw SQL** (`mixins/query_mixin.py`):
- `execute_query(query, params?)` → `list[dict]`
- `execute_query_df(query, params?)` → `DataFrame`

---

## Dataclasses

All are in `dasmixer/api/project/dataclasses.py`:

| Class | Fields |
|---|---|
| `Subset` | `id, name, details, display_color` |
| `Tool` | `id, name, type ("Library"/"De Novo"), parser, settings (dict), display_color` |
| `Sample` | `id, name, subset_id, additions (dict), outlier (bool)` + computed `subset_name, spectra_files_count` |
| `Protein` | `id, is_uniprot, fasta_name, sequence, gene, name, uniprot_data` |
| `IdentificationWithSpectrum` | `id, spectre_id, pepmass, mz_array, intensity_array, tool_id, sequence, canonical_sequence, charge, peaks_count` |

All dataclasses have `from_dict(data)` and `to_dict()` methods.

---

## Input Parsers

Base classes:
- `BaseImporter` — file validation
- `SpectralDataParser(BaseImporter)` — for spectra files
- `IdentificationParser(BaseImporter)` — for identification files; defines `spectra_id_field`

Register at module level:
```python
from dasmixer.api.inputs.registry import registry
registry.add_identification_parser("MyParser", MyParserClass)
registry.add_spectra_parser("MGF", MGFParser)
```

---

## Reports

Base class: `dasmixer.api.reporting.base.BaseReport`

```python
class MyReport(BaseReport):
    name = "My Report"
    description = "..."
    icon = ft.Icons.REPORT
    parameters = MyReportForm  # optional typed form

    async def _generate_impl(self, params: dict) -> tuple[list, list]:
        plots = [("Plot name", go.Figure(...))]
        tables = [("Table name", df, True)]  # bool = show in UI
        return plots, tables
```

Register:
```python
from dasmixer.api.reporting.registry import registry
registry.register(MyReport)
```

---

## Plugin System

Plugins are `.py` files or Python packages (`.zip`) placed in:
- Identifications: `{app_dir}/plugins/inputs/identifications/`
- Reports: `{app_dir}/plugins/reports/`

App dir location:
- Linux: `~/.config/dasmixer/` (via `typer.get_app_dir("dasmixer")`)
- Windows: `%APPDATA%/dasmixer/`

---

## Development Rules

1. **Never modify `pyproject.toml`** without a strong reason.
2. **All Project methods must be async** — use `await` everywhere.
3. **Data format from Project:** `pandas.DataFrame` for sets; `dataclasses` for single entities; `dict` for low-level.
4. **Array storage:** NumPy arrays compressed via `np.savez_compressed` → `bytes` BLOB. Use `array_utils.compress_array` / `decompress_array`.
5. **JSON fields in DB:** Serialized as TEXT with `json.dumps`/`json.loads`.
6. **Batch vs save:** Methods doing batch operations do NOT call `save()` internally. The caller must call `save()` after the batch.
7. **No unit tests from agent** — integration tests only, written separately when requested.
8. **Language:** User-facing strings in **English**. Development docs, specs, and agent↔developer communication in **Russian**.
9. **Do not generate test data** — test data is provided by the developer.
10. **Flet 0.80.5 API** — see notes above.

---

## Configuration

`dasmixer.api.config.AppConfig` (pydantic-settings) — loaded once as `config` singleton.

Key fields:
- `recent_projects: list[str]` — max 10
- `last_import_folder`, `last_export_folder` — remembered per operation type
- `theme: str` — `"light"` or `"dark"`
- `spectra_batch_size`, `identification_batch_size` etc. — batch sizes
- `plugin_states: dict[str, bool]`, `plugin_paths: dict[str, str]`

Config file: `{app_dir}/config.json`.

---

## Key Files for Quick Navigation

| File | Purpose |
|---|---|
| `dasmixer/main.py` | Entry point, CLI commands registration |
| `dasmixer/api/project/project.py` | Project class definition (mixin composition) |
| `dasmixer/api/project/schema.py` | Full SQLite schema |
| `dasmixer/api/project/dataclasses.py` | Data transfer objects |
| `dasmixer/gui/app.py` | GUI app controller, routing, project lifecycle |
| `dasmixer/gui/views/project_view.py` | Tab container with lazy loading + suspend/resume |
| `dasmixer/api/calculations/spectra/ion_match.py` | Ion matching core |
| `dasmixer/api/calculations/spectra/identification_processor.py` | Batch PPM+coverage worker |
| `dasmixer/api/calculations/proteins/lfq.py` | LFQ calculation |
| `dasmixer/api/reporting/base.py` | Report base class |
| `docs/project/MASTER_SPEC_NEW.md` | Full current project specification |
