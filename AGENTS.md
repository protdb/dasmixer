# DASMixer — AI Agent Development Guide

This document provides essential context for AI coding agents working on the DASMixer project.

---

## Project Overview

**DASMixer** is a cross-platform desktop proteomics application built with Flet (Python). It integrates de novo peptide sequencing results with library search identifications and performs comparative proteomics analysis.

- **Lab:** Laboratory of Structural Proteomics, IBMC, Moscow
- **Repo:** `git@github.com:protdb/dasmixer.git`
- **Version:** 0.7.3a1 (APP_VERSION) / PROJECT_VERSION 0.7.2

**MOST IMPORTANT DOCUMENT WITH DETAILS:** `docs/project/MASTER_SPEC_NEW.md`

---

## Package Structure (v0.5.0+)

The project is a **monorepo** with four publishable packages using **namespace packages (PEP 420)**:

```
dasmixer/                          # repo root
├── dasmixer-core/                 # core API library
│   ├── pyproject.toml
│   └── src/dasmixer/              # NO __init__.py (namespace package)
│       ├── api/                   # project API, calculations, inputs, reporting
│       ├── utils/                 # logger, seek_files, seqfixer_utils, etc.
│       └── versions.py            # APP_VERSION
│
├── dasmixer-gui/                  # Flet GUI
│   ├── pyproject.toml
│   └── src/dasmixer/              # NO __init__.py
│       ├── gui/                   # app, components, views, actions
│       │   ├── main.py            # entry point: `dasmixer` command
│       │   └── reports/forms.py   # GUI-side report form definitions
│       └── __main__.py            # python -m dasmixer
│
├── dasmixer-cli/                  # CLI tools
│   ├── pyproject.toml
│   └── src/dasmixer/              # NO __init__.py
│       └── cli/                   # commands (project, subset, import_data)
│           └── main.py            # entry point: `dasmixer-cli` command
│
└── metapackage/                   # umbrella package `dasmixer`
    ├── pyproject.toml             # dependencies only, no code
    └── dasmixer/__init__.py       # just __version__
```

All four packages install into `site-packages/dasmixer/` — Python merges them via PEP 420.

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
| Build | Poetry |

---

## Flet 0.81.0 — Critical API Notes

Flet 0.81.0 introduced breaking API changes. Always use the new API:

| Old (broken)                    | New (correct)                                                                 |
|---------------------------------|-------------------------------------------------------------------------------|
| `ft.dropdown.Option(...)`       | `ft.DropdownOption(...)`                                                      |
| `ft.alignment.center`           | `ft.Alignment.CENTER`                                                         |
| `ft.alignment.top_left`         | `ft.Alignment.TOP_LEFT`                                                       |
| `ft.colors.RED`                 | `ft.Colors.RED`                                                               |
| `ft.icons.ADD`                  | `ft.Icons.ADD`                                                                |
| `page.go("/route")`             | Manual `_route_change()` — `page.go()` is async, avoid in `__init__`          |
| `ft.FilePicker` as overlay      | Use `await ft.FilePicker().pick_files(...)` directly (no page overlay needed) |
| `page.window_width`             | `page.window.width`                                                           |
| `ft.ElevatedButton(text="...")` | `ft.ElevatedButton(content=ft.Text("..."))`                                   | 

**FilePicker pattern (correct for 0.81.0):**
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

**Routing in 0.81.0:** `page.on_route_change` handler receives no argument (unlike older versions).
Use the pattern in `dasmixer/gui/app.py:DASMixerApp._route_change`.

---

## Source Layout

### `dasmixer-core/src/dasmixer/api/`

```
api/
├── config.py              # AppConfig (pydantic-settings), global `config` instance
├── plugin_loader.py       # Dynamic plugin loading
├── project/
│   ├── project.py         # Project class (composed from mixins)
│   ├── schema.py          # SQLite schema SQL
│   ├── migrations.py      # MigrationMixin — project version migrations
│   ├── dataclasses.py     # Subset, Tool, Sample, Protein, IdentificationWithSpectrum
│   ├── array_utils.py     # compress_array / decompress_array (numpy ↔ bytes)
│   ├── core/
│   │   ├── base.py            # ProjectBase: _execute, _fetchone, _fetchall, _executemany
│   │   └── lifecycle.py       # ProjectLifecycle: initialize, save, close, context manager
│   └── mixins/
│       ├── subset_mixin.py    ├── tool_mixin.py        ├── sample_mixin.py
│       ├── spectra_mixin.py   ├── identification_mixin.py
│       ├── peptide_mixin.py   ├── protein_mixin.py     ├── plot_mixin.py
│       ├── query_mixin.py     └── report_mixin.py
├── inputs/
│   ├── base.py            # BaseImporter ABC
│   ├── registry.py        # InputTypesRegistry + global `registry`
│   ├── spectra/mgf.py     # MGFParser
│   ├── peptides/          # PowerNovo2, MQ_Evidences, PLGS, table_importer
│   └── proteins/fasta.py  # FASTA importer
├── calculations/
│   ├── spectra/           # ion_match, identification_processor, plot_matches, plot_flow
│   ├── peptides/          # matching (preferred selection), protein_map (npysearch)
│   ├── proteins/          # lfq, map_identifications, sempai/
│   └── ppm/               # seqfixer, dataclasses
└── reporting/
    ├── base.py            # BaseReport ABC
    ├── registry.py        # ReportRegistry
    ├── _icons.py          # Mock Icons (no-flet fallback)
    ├── report_form.py     # Abstract ReportForm (no-flet)
    └── reports/           # PCA, Volcano, UpSet, Coverage, Sample, ToolMatch
```

### `dasmixer-gui/src/dasmixer/gui/`

```
gui/
├── main.py               # Entry point: `dasmixer` command
├── app.py                # DASMixerApp: routing, project lifecycle, AppBar
├── utils.py              # show_snack
├── components/           # base_table_view, base_plot_view, plotly_viewer,
│   │                     # progress_dialog, report_form (GUI-side, flet-based)
│   └── report_form.py    # GUI ReportForm — extends core ReportForm with build()
├── actions/              # ion_actions, lfq_action, protein_ident_action, protein_map_action
├── reports/forms.py      # GUI report form declarations + monkey-patch
├── reporting/viewer.py   # ReportViewer (PyWebView)
└── views/
    ├── start_view.py, project_view.py, settings_view.py, plugins_view.py
    └── tabs/             # samples/, peptides/, proteins/, reports/, plots/, export/
```

### `dasmixer-cli/src/dasmixer/cli/`

```
cli/
├── main.py               # Entry point: `dasmixer-cli` command
└── commands/
    ├── project.py        # create
    ├── subset.py         # add/list/delete
    └── import_data.py    # mgf-file, mgf-pattern, ident-file, ident-pattern
```

---

## Entry Points

| Command | Package | Module |
|---|---|---|
| `dasmixer` | `dasmixer-gui` | `dasmixer.gui.main:app` |
| `dasmixer-cli` | `dasmixer-cli` | `dasmixer.cli.main:app` |
| `python -m dasmixer` | `dasmixer-gui` | `dasmixer/__main__.py` |

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
- `get_sample_stats(id)`, `get_all_samples_stats()` → `dict[int, dict]`
- `get_sample_status_summary(...)`
- `get_sample_counts_by_subset()`, `get_subset_sample_counts()`
- Note: `sample_status_cache` table is **DEPRECATED** (kept in schema for
  backward compat, see v0.7.0a4 changelog). Cache methods were removed;
  always use `get_all_samples_stats()` for fresh stats.

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
- `get_identifications_with_spectra_batch(tool_id, offset, limit, ...)` → `list[IdentificationWithSpectrum]`
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

### In code (API-side)

```python
from dasmixer.api.reporting._icons import Icons
from dasmixer.api.reporting.base import BaseReport

class MyReport(BaseReport):
    name = "My Report"
    description = "..."
    icon = Icons.REPORT           # works without flet installed
    parameters = None             # set by GUI-side monkey-patch

    async def _generate_impl(self, params: dict) -> tuple[list, list]:
        plots = [("Plot name", go.Figure(...))]
        tables = [("Table name", df, True)]
        return plots, tables
```

Register:
```python
from dasmixer.api.reporting.registry import registry
registry.register(MyReport)
```

### In code (GUI-side) — `gui/reports/forms.py`

```python
from dasmixer.gui.components.report_form import ReportForm, BoolSelector, IntSelector

class MyForm(ReportForm):
    threshold = FloatSelector(default=0.05)
    show_labels = BoolSelector(default=True)

MyReport.parameters = MyForm  # monkey-patch at startup
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

## Changelog

Changelogs live in `docs/project/changes/`, one file per version:
`vX.Y.Z(.preN).md` (e.g. `v0.7.3a1.md`, `v0.7.2.md`).

**Changelogs are written or extended only on the developer's explicit
request.** The agent must NOT create or modify changelog files on its own
initiative. When asked, follow the existing format (see recent files like
`v0.7.3a1.md`): a header line `# vX.Y.Z`, a `**Date:** YYYY-MM-DD`, then
`## Summary`, `## Core Changes`, `## GUI Changes`, `## CLI Changes`,
`## Fixes`, etc. with subsections per feature/fix.

---

## Versioning

Version constants live in `dasmixer-core/src/dasmixer/versions.py`:
- `APP_VERSION` — the application (GUI/CLI) version, shown to users.
- `PROJECT_VERSION` — the `.dasmix` project file format version; bumped when
  the DB schema or stored data shape changes. May lag behind `APP_VERSION`.
- `MIN_SUPPORTED_PROJECT_VERSION` — lowest project version the migrator can
  upgrade from.

**The agent must NOT change version numbers in code on its own.** The only
exception is an explicit developer request to bump `PROJECT_VERSION` (when a
schema migration is added). `APP_VERSION` and the `__version__` in
`metapackage/dasmixer/__init__.py`, the `version` fields in all
`pyproject.toml` files, and `dasmixer.iss` are all updated together by the
build script:

```
python build_tools/set_version.py <new_version>
```

That script touches every file that carries a version, so manual edits are
error-prone and must be avoided.

---

## Development Rules

1. **All Project methods must be async** — use `await` everywhere.
2. **Data format from Project:** `pandas.DataFrame` for sets; `dataclasses` for single entities; `dict` for low-level.
3. **Array storage:** NumPy arrays compressed via `np.savez_compressed` → `bytes` BLOB. Use `array_utils.compress_array` / `decompress_array`.
4. **JSON fields in DB:** Serialized as TEXT with `json.dumps`/`json.loads`.
5. **Batch vs save:** Methods doing batch operations do NOT call `save()` internally. The caller must call `save()` after the batch.
6. **No unit tests from agent** — integration tests only, written separately when requested.
7. **Language:** User-facing strings in **English**. Development docs, specs, and agent↔developer communication in **Russian**.
8. **Do not generate test data** — test data is provided by the developer.
9. **Flet 0.80.5 API** — see notes above.
10. **Namespace packages**: directories `src/dasmixer/` in each subpackage must NOT contain `__init__.py`.
11. **Core reports** must not import from `dasmixer.gui.*`. Use `dasmixer.api.reporting._icons` for icons, set `parameters = None`.
12. **pyproject.toml** changes: use path dependencies in `[tool.poetry.dependencies]` for local dev (`{path = "..", develop = true}`), keep `[project.dependencies]` for PyPI versions.
13. **Batch entry point naming:** the public batch function in
    `dasmixer.api.calculations.spectra.identification_processor` is
    `process_identifications_batch`. The old (mis-spelled) name
    `process_identificatons_batch` is kept only as a deprecated alias with a
    `DeprecationWarning`; new code (core, CLI, GUI, plugins) must use the
    correct name.
14. **Logging — named loggers only, never root.** DASMixer uses a single
    named logger `dasmixer` (created in `dasmixer.utils.logger`), with all
    module loggers as children that propagate upward. Runtime configuration
    (level, file handler) is applied from `AppConfig` by
    `dasmixer.gui.views.settings_view._apply_logging_config` to the
    `dasmixer` logger — so child loggers inherit it automatically.

    **Rules:**
    - **Never** call `logging.info(...)`, `logging.debug(...)`, etc.
      directly — these hit the *root* logger, bypassing the `dasmixer`
      hierarchy and the user's level/file settings (Ruff `LOG015`).
    - **Preferred:** import the shared logger:
      ```python
      from dasmixer.utils.logger import logger
      logger.info("message %s", value)
      ```
    - **Alternatively** (when a module-specific logger name is desired):
      ```python
      import logging
      logger = logging.getLogger(__name__)  # e.g. "dasmixer.api.foo"
      ```
      Since all DASMixer modules are under the `dasmixer` namespace, these
      are children of the `dasmixer` logger and inherit its level/handlers.
    - Use **lazy formatting** (`logger.info("x=%s", x)`, not
      `logger.info(f"x={x}")`) — the format string is only evaluated if the
      message passes the level check.
    - Use `logger.exception(exc)` or `logger.debug("...", exc_info=True)`
      inside `except` blocks — never bare `except: pass` (Ruff `S110`).
    - **Bootstrap** (before `AppConfig` loads, e.g. `gui/main.py`): the
      `dasmixer` logger already has a console handler at import time
      (level INFO), so `logger.*` calls work immediately. No `print()` for
      diagnostics — use `logger` from the start.

15. **Schema changes must be synced to `import_project_mixin.py`.** Any
    change to `CREATE_SCHEMA_SQL` in `schema.py` (adding/removing/renaming
    columns, adding new tables with autoincrement `id`) requires a manual
    sync of the SQL statements in
    `dasmixer.api.project.mixins.import_project_mixin.ImportProjectMixin.import_project()`:
    - **Per-table column lists** — for every `INSERT INTO <tbl> (cols...)
      SELECT cols... FROM src.<tbl>`, update both the INSERT-column list and
      the SELECT-column list so they match the current schema exactly.
      Affected bulk tables: `protein`, `spectre_file`, `spectre`,
      `identification_file`, `identification`, `peptide_match`,
      `protein_identification_result`, `protein_quantification_result`,
      `generated_reports`, `saved_plots`.
    - **List-inserted tables** (`subset`, `tool`, `sample`) — update the
      `INSERT INTO ... VALUES (...)` and the source `SELECT ... FROM` in the
      mapping loops if their columns change.
    - **New table** — add it to the `bulk_tables` list (used to compute
      `base_ids`) and to the "Reset autoincrement sequences" loop (Step 6)
      if it has an autoincrement `id`.
    - **Version guard** — import is refused when the source and target
      projects have different `PROJECT_VERSION` (read from
      `project_metadata.version`). `ProjectImportError` is raised with a
      message instructing the user to upgrade the older project to the
      higher version. This guard exists precisely to prevent the column
      drift that occurs when `import_project_mixin.py` falls out of sync
      with `schema.py` — so keep the guard and the column lists in sync.

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
| `dasmixer-gui/src/dasmixer/gui/main.py` | GUI entry point (`dasmixer` command) |
| `dasmixer-cli/src/dasmixer/cli/main.py` | CLI entry point (`dasmixer-cli` command) |
| `dasmixer-core/src/dasmixer/api/project/project.py` | Project class definition (mixin composition) |
| `dasmixer-core/src/dasmixer/api/project/schema.py` | Full SQLite schema |
| `dasmixer-core/src/dasmixer/api/project/dataclasses.py` | Data transfer objects |
| `dasmixer-gui/src/dasmixer/gui/app.py` | GUI app controller, routing, project lifecycle |
| `dasmixer-gui/src/dasmixer/gui/views/project_view.py` | Tab container with lazy loading + suspend/resume |
| `dasmixer-core/src/dasmixer/api/calculations/spectra/ion_match.py` | Ion matching core |
| `dasmixer-core/src/dasmixer/api/calculations/spectra/identification_processor.py` | Batch PPM+coverage worker |
| `dasmixer-core/src/dasmixer/api/calculations/proteins/lfq.py` | LFQ calculation |
| `dasmixer-core/src/dasmixer/api/reporting/base.py` | Report base class |
| `dasmixer-core/src/dasmixer/api/reporting/_icons.py` | Mock Icons (no-flet fallback) |
| `dasmixer-core/src/dasmixer/api/reporting/report_form.py` | Abstract ReportForm (no-flet) |
| `dasmixer-gui/src/dasmixer/gui/reports/forms.py` | GUI report forms + monkey-patch |
| `dasmixer-gui/src/dasmixer/gui/components/report_form.py` | GUI ReportForm (flet-based) |
| `docs/project/MASTER_SPEC_NEW.md` | Full current project specification |