# DASMixer — Project Master Specification

**Version:** 0.1.0  
**Date:** April 2026  
**Lab:** Laboratory of Structural Proteomics, IBMC, Moscow  
**Repo:** `git@github.com:protdb/dasmixer.git`

---

## 1. Purpose and Scope

DASMixer is a cross-platform desktop application for comparative proteomics analysis. Its primary workflow:

1. Import mass spectra (MGF) and peptide identification results from one or more tools
2. Validate and score identifications using ion coverage and PPM error analysis
3. Select the best identification per spectrum across multiple tools
4. Map peptides to protein sequences (FASTA), compute sequence coverage and LFQ metrics
5. Generate comparative reports (PCA, Volcano, UpSet, Coverage) and export them

The application targets proteomics researchers who combine de novo sequencing (PowerNovo2) with library search (MaxQuant, PLGS) and need an integrated pipeline for result merging and differential analysis.

---

## 2. Key Functional Areas

### 2.1 Data Management
- Project files (`.dasmix`) store all experimental data in a single SQLite database
- Multiple spectra files (MGF) per sample; multiple identification files per spectra file
- Samples organized into comparison groups (subsets) for statistical analysis
- Tools registered with type (`Library` / `De Novo`) and associated parser

### 2.2 Peptide-Level Processing
- Ion matching: generate theoretical b/y/a/c/x/z ions (+ losses), match to experimental spectrum peaks (PPM-based tolerance)
- De novo sequence correction: charge state determination, isotope offset correction, PTM hypothesis generation
- Identification selection: filter by score, PPM, coverage, peak counts; choose preferred per spectrum
- Protein mapping: BLAST-like search via npysearch against FASTA database

### 2.3 Protein-Level Processing
- Protein identification: count peptides, unique evidence, compute sequence coverage
- LFQ quantification: emPAI, iBAQ, NSAF, Top3 (via semPAI library)
- UniProt enrichment (via uniprot-meta-tool)

### 2.4 Reports and Export
- Built-in reports: PCA, Volcano plot, UpSet, Coverage, Tool Match, Sample Summary
- Interactive preview (PyWebView + Plotly)
- Export: HTML, XLSX, DOCX
- Saved plots with project-level settings (size, font)

### 2.5 Plugin System
- Extend identification parsers and report modules without modifying core code
- Install `.py` files or `.zip` packages via GUI Plugins panel

---

## 3. Technology Stack

| Component | Choice | Notes |
|---|---|---|
| GUI | Flet 0.80.5 | Cross-platform, Python-native |
| CLI | Typer | Auto-generates `--help` |
| Plots | Plotly + PyWebView 6.x | Interactive in desktop window |
| Data | Pandas + NumPy | DataFrames as primary data format |
| Proteomics | Pyteomics, Peptacular, Npysearch | Fragment generation, ion matching, BLAST |
| Storage | SQLite + aiosqlite | Async, WAL mode |
| Config | Pydantic-settings | JSON-backed, env overridable |
| Export | openpyxl, html-for-docx, Kaleido | Excel, Word, PNG/SVG |
| Packaging | Poetry | pyproject.toml |

---

## 4. Source Code Structure

```
dasmixer/                     # Python package root
├── main.py                   # Typer CLI + GUI launcher
├── utils/                    # Shared utilities (logger, seek_files, seqfixer_utils)
├── api/
│   ├── config.py             # AppConfig singleton
│   ├── plugin_loader.py      # Dynamic plugin import
│   ├── project/              # Project data access object
│   │   ├── project.py        # Project class (mixin composition)
│   │   ├── schema.py         # Full SQLite DDL
│   │   ├── dataclasses.py    # Subset, Tool, Sample, Protein, IdentificationWithSpectrum
│   │   ├── array_utils.py    # NumPy array ↔ bytes (savez_compressed)
│   │   ├── core/
│   │   │   ├── base.py       # ProjectBase: low-level DB ops
│   │   │   └── lifecycle.py  # ProjectLifecycle: init, save, close
│   │   └── mixins/           # Domain-specific mixins (10 files)
│   ├── inputs/               # Data importers
│   │   ├── base.py           # BaseImporter ABC
│   │   ├── registry.py       # InputTypesRegistry (global `registry`)
│   │   ├── spectra/          # SpectralDataParser ABC + MGFParser
│   │   ├── peptides/         # IdentificationParser ABC + PowerNovo2, MQ, PLGS
│   │   └── proteins/         # FASTAImporter
│   ├── calculations/
│   │   ├── spectra/          # ion_match, identification_processor, plot_matches
│   │   ├── peptides/         # matching (preferred selection), protein_map (BLAST)
│   │   ├── proteins/         # lfq, map_identifications, sempai/
│   │   └── ppm/              # SeqFixer (de novo charge/isotope correction)
│   └── reporting/
│       ├── base.py           # BaseReport ABC
│       ├── registry.py       # ReportRegistry (global `registry`)
│       ├── viewer.py         # PyWebView interactive viewer
│       └── reports/          # PCA, Volcano, UpSet, Coverage, Sample, ToolMatch
├── gui/
│   ├── app.py                # DASMixerApp: routing, project lifecycle
│   ├── utils.py              # show_snack
│   ├── components/           # Reusable Flet components
│   ├── actions/              # Async action handlers (GUI → API bridge)
│   └── views/                # Views and tabs
│       ├── start_view.py
│       ├── project_view.py   # Lazy-loaded tabs + suspend/resume
│       ├── settings_view.py
│       ├── plugins_view.py
│       ├── manage_samples_view.py
│       └── tabs/             # samples/, peptides/, proteins/, reports/, plots/
└── cli/
    └── commands/             # project.py, subset.py, import_data.py
```

---

## 5. Database Schema

The project file (`.dasmix`) is a SQLite database with WAL journal mode. Schema defined in `dasmixer/api/project/schema.py`.

### Entity Relationship

```
subset ←── sample ←── spectre_file ←── spectre
                              ↓
                    identification_file ←── identification
                                                   ↓
                                            peptide_match ──→ protein
                                                   ↓
                                       protein_identification_result
                                                   ↓
                                      protein_quantification_result
```

### Tables Summary

| Table | Key Fields |
|---|---|
| `project_metadata` | key, value (version, created_at, modified_at) |
| `project_settings` | key, value (plot settings, etc.) |
| `subset` | id, name, details, display_color |
| `tool` | id, name, type, parser, settings (JSON), display_color |
| `sample` | id, name, subset_id FK, additions (JSON), outlier |
| `spectre_file` | id, sample_id FK, format, path |
| `spectre` | id, spectre_file_id FK, seq_no, title, charge, pepmass, mz_array (BLOB), intensity_array (BLOB), peaks_count |
| `identification_file` | id, spectre_file_id FK, tool_id FK, file_path |
| `identification` | id, spectre_id FK, tool_id FK, ident_file_id FK, is_preferred, sequence, canonical_sequence, ppm, score, intensity_coverage, ions_matched, ion_match_type, top_peaks_covered, override_charge, source_sequence, isotope_offset |
| `peptide_match` | id, protein_id FK, identification_id FK, matched_sequence, identity, matched_ppm, unique_evidence, matched_coverage_percent, substitution |
| `protein` | id (TEXT), is_uniprot, fasta_name, sequence, gene, name, uniprot_data (BLOB) |
| `protein_identification_result` | id, protein_id FK, sample_id FK, peptide_count, uq_evidence_count, coverage, intensity_sum |
| `protein_quantification_result` | id, protein_identification_id FK, algorithm, rel_value, abs_value |
| `sample_status_cache` | sample_id PK, spectra_files_count, ident_files_count, identifications_count, preferred_count, coverage_known_count, protein_ids_count, updated_at |
| `generated_reports` | id, report_name, created_at, plots (BLOB), tables (BLOB), project_settings (JSON), tools_settings (JSON), report_settings (JSON) |
| `saved_plots` | id, created_at, plot_type, settings (JSON), plot (BLOB) |

### Binary Storage
- **Spectra arrays** (mz_array, intensity_array, charge_array): `np.savez_compressed` → bytes BLOB
- **Report plots and tables**: `pickle + gzip` BLOB
- **UniProt data**: `pickle + gzip` BLOB

---

## 6. Project API

### Initialization
```python
from dasmixer.api.project.project import Project

project = Project(path="study.dasmix", create_if_not_exists=True)
await project.initialize()

# Context manager (auto-close without explicit save)
async with Project(path="study.dasmix") as p:
    subsets = await p.get_subsets()
```

### Class Composition (MRO)
```
Project
├── ProjectLifecycle (→ ProjectBase)   # DB lifecycle
├── SubsetMixin                         # Comparison groups
├── ToolMixin                           # Identification tools
├── SampleMixin                         # Samples
├── SpectraMixin                        # Spectra files and data
├── IdentificationMixin                 # Identification files and data
├── PeptideMixin                        # Peptide matches + joined queries
├── ProteinMixin                        # Proteins, results, quantification
├── PlotMixin                           # Plot data preparation
├── QueryMixin                          # Raw SQL access
└── ReportMixin                         # Report storage
```

### Batch vs. Save Policy
Batch insert methods (`add_spectra_batch`, `add_identifications_batch`, `add_peptide_matches_batch`, etc.) do **not** call `save()` internally. The caller is responsible for calling `save()` once after all batch operations.

`_commit()` is a lightweight DB commit for hot-path loops that skips `modified_at` update. Use `save()` to finalize.

---

## 7. Input Parsers

### Registration
At module level, parsers self-register into the global `registry`:
```python
from dasmixer.api.inputs.registry import registry
registry.add_spectra_parser("MGF", MGFParser)
registry.add_identification_parser("PowerNovo2", PowerNovo2Importer)
```

### Built-in Parsers

| Name | Class | Format |
|---|---|---|
| `MGF` | `MGFParser` | Mascot Generic Format |
| `PowerNovo2` | `PowerNovo2Importer` | CSV (de novo sequencing) |
| `MQ_Evidences` | `MQEvidencesImporter` | MaxQuant evidence.txt |
| `PLGS` | `PLGSImporter` | Waters PLGS CSV |

### Identification Import Workflow
1. Parse identification file → get DataFrame with `seq_no` or `scans`
2. `project.get_spectra_idlist(file_id, by="seq_no")` → mapping list
3. Merge on `seq_no`/`scans` to get `spectre_id` column
4. `project.add_identifications_batch(merged_df)`

---

## 8. Calculations Pipeline

### 8.1 PPM + Ion Coverage (Identification Processor)

Entry point: `dasmixer.api.calculations.spectra.identification_processor.process_identificatons_batch`

Runs in separate processes via `ProcessPoolExecutor`. Each worker:
1. Creates `SeqFixer` with PTM list, charge range, isotope offset settings
2. For each identification: calls `SeqFixer.get_ppm()` to determine best charge/isotope/PTM combination
3. Calls `match_predictions()` (from `ion_match.py`) to get ion coverage metrics
4. Returns result dict with: `sequence, ppm, theor_mass, override_charge, isotope_offset, intensity_coverage, ions_matched, ion_match_type, top_peaks_covered`

Results written back via `project.put_identification_data_batch()`.

### 8.2 Ion Matching Core (`ion_match.py`)

```python
params = IonMatchParameters(
    ions=['b', 'y'],         # ion types
    tolerance=20.0,           # PPM
    mode='largest',           # 'all' | 'closest' | 'largest'
    water_loss=True,
    ammonia_loss=True
)
result = match_predictions(params, mz_list, intensity_list, charge, sequence)
# result.intensity_percent  — % of total intensity matched
# result.max_ion_matches    — max consecutive matched ions (per type)
# result.top10_intensity_matches — matched peaks among top-10 by intensity
```

### 8.3 De Novo Correction (`ppm/seqfixer.py`)

`SeqFixer` handles de novo-specific issues:
- **Charge correction**: try charges from `min_charge` to `max_charge`
- **Isotope offset**: try offsets 0..max_isotope_offset (precursor mass ±n×1.003)
- **PTM hypothesis**: apply combinations of known PTMs (from `utils/seqfixer_utils.py`) up to `max_ptm` per sequence and `max_ptm_sites` sites

### 8.4 Preferred Identification Selection (`peptides/matching.py`)

`select_preferred_identifications()` — per-spectrum cross-tool best identification:
- Apply quality filters per tool (score, PPM, coverage, length, peak counts)
- For de novo: optionally use corrected PPM (`matched_ppm` from peptide_match)
- Select by minimum PPM (default) or maximum coverage

### 8.5 Protein Mapping (`peptides/protein_map.py` + npysearch)

Uses npysearch BLAST-like engine to map canonical peptide sequences to protein database. Returns identity score; exact matches (1.0) and partial matches accepted based on configured threshold.

### 8.6 LFQ Quantification (`proteins/lfq.py`)

`calculate_lfq(project, sample_id, methods, ...)` wraps the semPAI library:
- `emPAI`: exponentially modified protein abundance index
- `iBAQ`: intensity-based absolute quantification
- `NSAF`: normalized spectral abundance factor
- `Top3`: average intensity of 3 most abundant peptides

Results stored in `protein_quantification_result` table.

---

## 9. Reporting System

### BaseReport Interface
```python
class MyReport(BaseReport):
    name = "My Report"
    description = "Description shown in UI"
    icon = ft.Icons.ASSESSMENT
    parameters = MyReportForm  # Optional: typed form class

    async def _generate_impl(self, params: dict):
        plots = [("Plot Name", go.Figure(...))]
        tables = [("Table Name", df, True)]  # True = show in UI
        return plots, tables
```

### Storage
Generated reports are stored as pickle+gzip blobs in `generated_reports` table, along with:
- Project settings at generation time (plot dimensions, font size)
- Tool settings at generation time
- Report parameters

### Export
`BaseReport.export(output_path)` creates:
- `{report_name}-{timestamp}.html` — interactive Plotly
- `{report_name}-{timestamp}.docx` — via html-for-docx
- `{report_name}-{timestamp}.xlsx` — one sheet per DataFrame table

---

## 10. GUI Architecture

### Views
```
DASMixerApp (app.py)
├── StartView           — recent projects, create/open buttons
├── ProjectView         — lazy-loaded tab container
│   ├── SamplesTab      — sample management, import, stats
│   ├── PeptidesTab     — identification review, ion plots, settings
│   ├── ProteinsTab     — protein results, LFQ settings, mapping
│   ├── ReportsTab      — report generation and management
│   └── PlotsTab        — saved plots gallery
├── SettingsView        — app settings
└── PluginsView         — plugin management
```

### Key Patterns
- **Lazy tab loading**: Only SamplesTab is built on project open. Other tabs are built on first selection.
- **Suspend/resume**: Heavy tabs (Peptides, Proteins) suspend their `BaseTableView`/`BasePlotView` components when switching away, replacing rendered rows with placeholders. On return, they resume from cached data without DB queries.
- **FilePicker**: Used directly via `await ft.FilePicker().pick_files(...)` — no page overlay needed in Flet 0.80.5.
- **Routing**: Manual `_route_change()` call instead of `page.go()` (async in 0.80.5, not safe from `__init__`).

---

## 11. CLI

```
dasmixer [file_path] [COMMAND]
```

| Command | Description |
|---|---|
| *(no command)* | Launch GUI (optionally open project) |
| `create` | Create new project (GUI) |
| `subset add/list/delete` | Manage comparison groups |
| `import mgf-file` | Import single MGF file |
| `import mgf-pattern` | Batch import MGF files by pattern |
| `import ident-file` | Import single identification file (planned) |
| `import ident-pattern` | Batch import identification files (planned) |

---

## 12. Plugin Development

### Identification Parser Plugin
Create a `.py` file or package with `__init__.py`:

```python
# my_parser.py
from dasmixer.api.inputs.peptides.base import IdentificationParser
from dasmixer.api.inputs.registry import registry
import pandas as pd

class MyParser(IdentificationParser):
    spectra_id_field = 'seq_no'

    async def validate(self) -> bool:
        # Quick format check
        return True

    async def parse_batch(self, batch_size=1000):
        df = pd.read_csv(self.file_path)
        # yield in batches
        for i in range(0, len(df), batch_size):
            yield df.iloc[i:i+batch_size], None

registry.add_identification_parser("MyParser", MyParser)
```

Install: place in `~/.config/dasmixer/plugins/inputs/identifications/` or install via GUI.

### Report Plugin
```python
# my_report.py
import flet as ft
import plotly.graph_objects as go
from dasmixer.api.reporting.base import BaseReport
from dasmixer.api.reporting.registry import registry

class MyReport(BaseReport):
    name = "My Custom Report"
    description = "Example custom report"
    icon = ft.Icons.ANALYTICS

    async def _generate_impl(self, params):
        fig = go.Figure()
        # ... build figure from project data
        return [("My Plot", fig)], []

registry.register(MyReport)
```

Install: place in `~/.config/dasmixer/plugins/reports/` or install via GUI.

---

## 13. Configuration

`AppConfig` (pydantic-settings) loaded from `{app_dir}/config.json`. Supports env override via `DASMIXER_` prefix.

| Field | Type | Default | Description |
|---|---|---|---|
| `recent_projects` | `list[str]` | `[]` | Up to 10 recent project paths |
| `last_import_folder` | `str\|None` | `None` | Last used import directory |
| `last_export_folder` | `str\|None` | `None` | Last used export directory |
| `theme` | `str` | `"light"` | `"light"` or `"dark"` |
| `window_width` | `int` | `1200` | Initial window width |
| `window_height` | `int` | `800` | Initial window height |
| `spectra_batch_size` | `int` | `5000` | Spectra import batch size |
| `identification_batch_size` | `int` | `5000` | Identification import batch size |
| `identification_processing_batch_size` | `int` | `5000` | PPM/coverage worker batch size |
| `protein_mapping_batch_size` | `int` | `5000` | Protein mapping batch size |
| `default_colors` | `list[str]` | 8 hex colors | Color palette for tools/subsets |
| `plugin_states` | `dict[str,bool]` | `{}` | Plugin enabled/disabled state |
| `plugin_paths` | `dict[str,str]` | `{}` | Plugin file paths (for deletion) |

---

## 14. Key Documentation Links

| Document | Location |
|---|---|
| API Reference: Project | `docs/api/project/` |
| API Reference: Inputs, Calculations, Reporting | `docs/api/modules.md` |
| GUI Architecture | `docs/gui/architecture.md` |
| User Guide | `docs/user/` |
| Code Review Notes | `docs/review/code_review.md` |
| ER Diagram | `docs/PROJECT_ER.mermaid` |
| Development Specifications (historical) | `docs/project/spec/` |
