# API Reference — Modules

This document covers the non-project API modules: inputs, calculations, reporting, and plugins.

---

## Inputs (`dasmixer/api/inputs/`)

### InputTypesRegistry

**File:** `dasmixer/api/inputs/registry.py`

Global singleton `registry` that holds all registered parser classes.

```python
from dasmixer.api.inputs.registry import registry

# Get all spectra parsers
parsers = registry.get_spectra_parsers()  # dict[str, Type[SpectralDataParser]]

# Get all identification parsers
parsers = registry.get_identification_parsers()  # dict[str, Type[IdentificationParser]]

# Get specific parser class
MGFParser = registry.get_parser("MGF", "spectra")
parser = MGFParser("/path/to/file.mgf")

# Register new parser
registry.add_spectra_parser("MyFormat", MyParserClass)
registry.add_identification_parser("MyTool", MyParserClass)
```

**Note:** There are two copies of the registry file (`registry.py` and `registry_new.py`) with identical code — `registry_new.py` is obsolete/leftover. Only `registry.py` is imported.

### BaseImporter

**File:** `dasmixer/api/inputs/base.py`

```python
class BaseImporter(ABC):
    file_path: Path

    def __init__(self, file_path: Path | str)  # validates file exists
    async def validate(self) -> bool           # abstract: format check
    async def get_metadata(self) -> dict       # optional: file metadata
```

### SpectralDataParser

**File:** `dasmixer/api/inputs/spectra/base.py`

Extends `BaseImporter`. Must implement `parse_batch()` that yields a `pd.DataFrame` per batch with columns required by `project.add_spectra_batch()`:

`seq_no, title, scans, charge, rt, pepmass, mz_array, intensity_array, charge_array, charge_array_common_value, peaks_count, all_params`

**Built-in:** `MGFParser` (`spectra/mgf.py`) — parses Mascot Generic Format files.

### IdentificationParser

**File:** `dasmixer/api/inputs/peptides/base.py`

Extends `BaseImporter`. Key attribute: `spectra_id_field` (`"seq_no"` or `"scans"`) — tells the importer how to match identifications to spectra.

`parse_batch(batch_size)` yields `(peptide_df, protein_df|None)`:
- `peptide_df` columns: `seq_no|scans, sequence, canonical_sequence, ppm, theor_mass, score, positional_scores`
- `protein_df`: optional, for parsers that include protein identifications

**Built-in parsers:**

| Name | Class | File | Format |
|---|---|---|---|
| `PowerNovo2` | `PowerNovo2Importer` | `peptides/PowerNovo2.py` | CSV de novo results |
| `MQ_Evidences` | `MQEvidencesImporter` | `peptides/MQ_Evidences.py` | MaxQuant evidence.txt |
| `PLGS` | `PLGSImporter` | `peptides/PLGS.py` | Waters PLGS CSV |

### SimpleTableImporter

**File:** `dasmixer/api/inputs/peptides/table_importer.py`

Base class for CSV/Excel tabular identification files. Handles column renaming, batch iteration, and standard transformations. `PowerNovo2`, `MQ_Evidences`, `PLGS` all extend this.

Key attribute: `ColumnRenames` dataclass defines the mapping from tool-specific column names to the standard schema.

### FASTAImporter

**File:** `dasmixer/api/inputs/proteins/fasta.py`

Parses FASTA files and returns a `pd.DataFrame` with columns: `id, fasta_name, sequence, gene, name, is_uniprot`.

---

## Calculations (`dasmixer/api/calculations/`)

### Ion Matching (`calculations/spectra/ion_match.py`)

**`IonMatchParameters`** — dataclass controlling matching behavior:

| Field | Type | Default | Description |
|---|---|---|---|
| `ions` | `list\|None` | `None` → `['b','y']` | Ion types to match |
| `tolerance` | `float` | `20.0` | PPM tolerance |
| `mode` | `str` | `'largest'` | `'all'`, `'closest'`, `'largest'` |
| `water_loss` | `bool` | `True` | Include -H2O ions |
| `ammonia_loss` | `bool` | `True` | Include -NH3 ions |
| `charges` | `int\|list\|None` | `None` | Fragment charge states |

**`match_predictions(params, mz, intensity, charges, sequence)`** → `MatchResult`

Uses `peptacular.fragmentation.Fragmenter` to generate theoretical fragments and `peptacular.score.get_fragment_matches` to match to experimental peaks.

**`MatchResult`** fields:
- `fragment_matches: list[FragmentMatch]`
- `intensity_percent: float` — % of total intensity matched
- `max_ion_matches: int` — max consecutive ions per type
- `top10_intensity_matches: int` — matched peaks among top-10 by intensity
- `top_matched_ion_type: str` — ion type with most matches

**`get_matches_dataframe(match_result, mz, intensity)`** → `pd.DataFrame`

Creates a DataFrame joining experimental spectrum with matched fragment annotations. Columns: `mz, intensity, ion_type, label, frag_seq, theor_mz`. Used by `plot_matches.py` for visualization.

### Identification Processor (`calculations/spectra/identification_processor.py`)

Entry point for batch PPM + coverage calculation. Called from GUI action via `ProcessPoolExecutor`.

**`process_identificatons_batch(batch, params_dict, fragment_charges, target_ppm, ...)`** → `list[dict]`

Each dict in result contains: `id, sequence, ppm, theor_mass, override_charge, isotope_offset, intensity_coverage, ions_matched, ion_match_type, top_peaks_covered, source_sequence`

Per-worker file logger written to `~/.cache/dasmixer/worker_logs/worker_{PID}.log`.

**`process_single_ident(fixer, params, fragment_charges, sequence, pepmass, mz_array, intensity_array, mgf_charge, selection_criteria)`** → `dict`

Core processing for one identification:
1. `SeqFixer.get_ppm()` — find best charge/isotope/PTM combination
2. If overrides found: try all → pick best by `selection_criteria` (`"intensity_percent"`, `"peaks"`, `"top_peaks"`)
3. Run `match_predictions()` on best candidate
4. Return metrics dict

### Coverage Worker (`calculations/spectra/coverage_worker.py`)

Additional worker for computing matched peptide coverage (used during protein mapping PPM recalculation). See source for details.

### Plot Functions (`calculations/spectra/plot_matches.py`, `plot_flow.py`)

- `plot_matches.py` — generates Plotly `go.Figure` for ion spectrum annotation from a `get_matches_dataframe` result
- `plot_flow.py` — orchestrates the full plot pipeline: fetch spectrum → match → build figure

### De Novo Correction (`calculations/ppm/seqfixer.py`)

**`SeqFixer`** — corrects de novo peptide sequences for PPM calculation:

```python
fixer = SeqFixer(
    ptm_list=PTMS,               # list[FixedPTM] from seqfixer_utils.py
    max_ptm=5,                   # max PTMs per sequence hypothesis
    target_ppm=20.0,             # accept hypothesis within this PPM
    override_charges=(1, 4),     # try charge states 1..4
    max_isotope_offset=2,        # try isotope offsets 0..2
    force_isotope_offset_lookover=True,
    max_ptm_sites=10             # limit PTM site combinations
)
result = fixer.get_ppm(sequence, pepmass, mgf_charge)
# result.original: SeqMatchParams (best without override)
# result.override: list[SeqMatchParams] | None (alternative candidates)
```

**`SeqMatchParams`** dataclass fields: `sequence, ppm, seq_neutral_mass, charge, isotope_offset`

**PTMs** are defined in `dasmixer/utils/seqfixer_utils.py` as `list[FixedPTM]`.

### Preferred Identification Selection (`calculations/peptides/matching.py`)

**`select_preferred_identifications(project, criterion, tool_settings)`** → `int` (count)

Iterates all spectra files and selects best identification per spectrum across all tools. Uses quality filters from `tool_settings` dict:

| Key | Type | Description |
|---|---|---|
| `max_ppm` | `float` | Maximum absolute PPM |
| `min_score` | `float` | Minimum score |
| `min_ion_intensity_coverage` | `float` | Minimum coverage % |
| `min_peptide_length` | `int` | Minimum canonical sequence length |
| `max_peptide_length` | `int` | Maximum canonical sequence length |
| `min_spectre_peaks` | `int` | Minimum spectrum peak count |
| `min_top_peaks` | `int` | Minimum top-10 peaks covered |
| `min_ions_covered` | `int` | Minimum matched ions |
| `denovo_correction` | `bool` | Use corrected PPM from peptide_match |
| `denovo_correction_ppm` | `float` | PPM limit when using de novo correction |
| `ignore_criteria` | `bool` | Accept all identifications from this tool |

**`calculate_preferred_identifications_for_file(project, spectra_file_id, criterion, tool_settings)`** → `list[int]`

Faster variant: returns list of identification IDs to mark as preferred for a single spectra file.

### Protein Mapping (`calculations/peptides/protein_map.py`)

Wraps npysearch for BLAST-like protein sequence search. Returns match DataFrame.

### LFQ Quantification (`calculations/proteins/lfq.py`)

**`calculate_lfq(project, sample_id, methods, enzyme, min_length, max_length, max_cleavage_sites, empai_base)`** → `pd.DataFrame`

Returns long-format DataFrame with columns: `protein_identification_id, algorithm, rel_value`.

Uses semPAI library (`calculations/proteins/sempai/`) internally.

Methods: `'emPAI', 'iBAQ', 'NSAF', 'Top3'`

### Protein Identification Builder (`calculations/proteins/map_identifications.py`)

**`find_protein_identifications(joined_data, sequences_db, min_peptides, min_uq_evidence)`** → `AsyncIterator[tuple[pd.DataFrame, int]]`

Yields `(result_df, sample_id)` per sample. Computes:
- peptide_count, uq_evidence_count
- sequence coverage % via `get_coverage(sequence, peptides)`
- intensity_sum

---

## Reporting (`dasmixer/api/reporting/`)

### ReportRegistry

**File:** `dasmixer/api/reporting/registry.py`

Global singleton `registry`:

```python
from dasmixer.api.reporting.registry import registry

registry.register(MyReportClass)          # register by report_class.name
report_class = registry.get("My Report") # get by name
all_reports = registry.get_all()         # dict[str, Type[BaseReport]]
```

### BaseReport

**File:** `dasmixer/api/reporting/base.py`

Abstract base for all reports. Key interface:

```python
class MyReport(BaseReport):
    name = "Report Name"        # used as registry key
    description = "..."
    icon = ft.Icons.ASSESSMENT
    parameters = MyReportForm   # Optional ReportForm subclass

    async def _generate_impl(self, params: dict) -> tuple[
        list[tuple[str, go.Figure]],        # plots
        list[tuple[str, pd.DataFrame, bool]] # tables (name, df, show_in_ui)
    ]:
        ...
```

**Generation flow** (`generate(params)`):
1. `_validate_parameters(params)` — type conversion (legacy) or pass-through (typed form)
2. Collect project settings and tool settings
3. `_generate_impl(params)` — subclass implementation
4. `_apply_settings_to_figure(fig)` — apply global plot style
5. `_save_to_db()` — serialize and store in `generated_reports` table

**Loading:** `BaseReport.load_from_db(project, report_id)` — deserializes from DB.

**Export:** `report.export(output_path)` → `dict[str, Path]`
- `.html` — interactive (Plotly JSON)
- `.docx` — static (embedded PNG images)
- `.xlsx` — one sheet per table

**Context:** `report.get_context()` returns Jinja2 template context dict.

### Built-in Reports

| Class | Name | File | Output |
|---|---|---|---|
| `PCAReport` | "PCA Analysis" | `reports/pca_report.py` | PCA biplot |
| `VolcanoReport` | "Volcano Plot" | `reports/volcano_report.py` | Volcano plot |
| `UpSetReport` | "UpSet Plot" | `reports/upset.py` | UpSet diagram |
| `CoverageReport` | "Coverage Report" | `reports/coverage_report.py` | Coverage table + plots |
| `SampleReport` | "Sample Summary" | `reports/sample_report.py` | Per-sample stats |
| `ToolMatchReport` | "Tool Match Report" | `reports/toolmatch_report.py` | Cross-tool comparison |

### Interactive Viewer (`reporting/viewer.py`)

Opens a PyWebView window displaying Plotly HTML for interactive plot inspection. Used by "Preview" button in reports tab.

---

## Plugin System (`dasmixer/api/plugin_loader.py`)

### Plugin Directories

| Type | Directory |
|---|---|
| Identification parsers | `{app_dir}/plugins/inputs/identifications/` |
| Report modules | `{app_dir}/plugins/reports/` |

### Plugin Formats

- **`.py` file** — single-file plugin; loaded directly
- **`.zip` archive** — Python package (must contain `__init__.py`); extracted to plugin dir

### API

```python
from dasmixer.api.plugin_loader import (
    load_identification_plugins,  # → list[dict]
    load_report_plugins,          # → list[dict]
    install_plugin_file,          # (src_path, plugin_type) → (success, plugin_id, error)
    delete_plugin,                # (plugin_id) → (success, error)
)
```

Result dict keys: `id, path, name, error, builtin, plugin_type, enabled`

### Plugin Loading Flow

At startup (`main.py`), both `load_identification_plugins()` and `load_report_plugins()` are called before GUI/CLI launch. Each plugin file is imported via `importlib.util.spec_from_file_location`. On import, the plugin self-registers into the global `registry`.

Plugin states (enabled/disabled) are stored in `config.plugin_states`. Disabled plugins are listed but not loaded.

### Conflict Protection

If a plugin tries to register a name already occupied by a built-in parser/report, `PluginConflictError` is raised, the plugin is marked as failed, and the error is shown in the Plugins panel.
