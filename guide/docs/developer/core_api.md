# Core Library API (`dasmixer-core`)

`dasmixer-core` provides an asynchronous Python API for managing `.dasmix` projects, parsing input files, running analytical calculations, and generating reports.

---

## Project Class (`dasmixer.api.project.project.Project`)

`Project` is the central data access object. It is implemented as a composition of domain-specific mixins and uses **aiosqlite** with WAL mode enabled. All public methods are `async`.

### Lifecycle and Context Manager

```python
from dasmixer.api.project.project import Project

# Open or create a project using the async context manager (recommended)
async with Project(path="study.dasmix", create_if_not_exists=True) as project:
    samples = await project.get_samples()
    # Automatically saves and closes on exit
```

| Method | Signature | Description |
|---|---|---|
| `initialize()` | `() -> None` | Opens connection, configures WAL, creates schema, runs migrations |
| `save(checkpoint=False)` | `(bool) -> None` | Updates `modified_at` and commits transaction (optionally checkpoints WAL) |
| `save_as(path)` | `(Path \| str) -> None` | Copies project to a new path and reopens connection |
| `vacuum()` | `() -> None` | Rebuilds SQLite database file to reclaim unused disk space |
| `close()` | `() -> None` | Commits and closes database connection |
| `get_metadata()` | `() -> dict` | Returns project metadata (`version`, `created_at`, `modified_at`) |
| `set_setting(key, value)` | `(str, str) -> None` | Upserts a key-value pair in `project_settings` |
| `get_setting(key, default=None)` | `(str, Any) -> str \| None` | Reads a setting from `project_settings` |
| `get_all_settings()` | `() -> dict[str, str]` | Returns all settings as a dictionary |

---

### Subsets (`SubsetMixin`)

Manages comparison groups used for differential analysis.

| Method | Signature | Returns | Notes |
|---|---|---|---|
| `add_subset` | `(name, details=None, display_color=None)` | `Subset` | Raises `ValueError` if name exists |
| `get_subsets` | `()` | `list[Subset]` | Ordered by name |
| `get_subset` | `(subset_id: int)` | `Subset \| None` | Lookup by ID |
| `update_subset` | `(subset: Subset)` | `None` | Updates name, details, color |
| `delete_subset` | `(subset_id: int)` | `None` | Raises `ValueError` if samples belong to this subset |

---

### Tools (`ToolMixin`)

Manages identification search engines registered in the project.

| Method | Signature | Returns | Notes |
|---|---|---|---|
| `add_tool` | `(name, type, parser, settings=None, display_color=None)` | `Tool` | `type`: `"Library"` or `"De Novo"`; `parser`: registered parser name |
| `get_tools` | `()` | `list[Tool]` | Ordered by name |
| `get_tool` | `(tool_id: int)` | `Tool \| None` | Lookup by ID |
| `update_tool` | `(tool: Tool)` | `None` | Updates tool metadata and JSON settings |
| `delete_tool` | `(tool_id: int)` | `None` | Cascades or raises if identifications exist |

---

### Samples (`SampleMixin`)

Manages biological samples and their status statistics.

| Method | Signature | Returns | Notes |
|---|---|---|---|
| `add_sample` | `(name, subset_id=None, additions=None, outlier=False)` | `Sample` | `additions` is a `dict` stored as JSON |
| `get_samples` | `(subset_id: int \| None = None)` | `list[Sample]` | Includes computed `subset_name` and `spectra_files_count` |
| `get_sample` | `(sample_id: int)` | `Sample \| None` | Lookup by ID |
| `get_sample_by_name` | `(name: str)` | `Sample \| None` | Lookup by unique name |
| `update_sample` | `(sample: Sample)` | `None` | Updates subset, additions, or outlier flag |
| `delete_sample` | `(sample_id: int)` | `None` | Cascades to spectra files and identifications |
| `get_sample_stats` | `(sample_id: int)` | `dict` | Live stats for a single sample |
| `get_all_samples_stats` | `()` | `dict[int, dict]` | Fresh aggregated stats for all samples |
| `get_subset_sample_counts` | `(exclude_outliers=True, subsets=None)` | `dict[str, int]` | Sample counts per subset name |

---

### Spectra (`SpectraMixin`)

Manages spectral files and individual MS/MS spectra.

| Method | Signature | Returns | Notes |
|---|---|---|---|
| `add_spectra_file` | `(sample_id: int, format: str, path: str)` | `int` | Returns `spectre_file.id` |
| `get_spectra_files` | `(sample_id: int \| None = None)` | `pd.DataFrame` | Columns: `id, sample_id, format, path, sample_name` |
| `delete_spectra_file` | `(spectra_file_id: int)` | `None` | Cascades to spectra and identifications |
| `add_spectra_batch` | `(spectra_file_id: int, spectra_df: pd.DataFrame)` | `None` | Compresses `mz_array` and `intensity_array` into BLOBs |
| `get_spectra` | `(spectra_file_id=None, sample_id=None, limit=None, offset=None)` | `pd.DataFrame` | Metadata only (no binary arrays) |
| `get_spectrum_full` | `(spectrum_id: int)` | `dict` | Includes decompressed NumPy arrays |
| `get_spectra_idlist` | `(spectra_file_id: int, by="seq_no")` | `list[dict]` | Maps `seq_no`, `scans`, or `title` to `spectre_id` |

---

### Identifications (`IdentificationMixin`)

Manages identification files and peptide-spectrum matches (PSMs).

| Method | Signature | Returns | Notes |
|---|---|---|---|
| `add_identification_file` | `(spectra_file_id: int, tool_id: int, file_path: str)` | `int` | Returns `identification_file.id` |
| `add_identifications_batch` | `(identifications_df: pd.DataFrame)` | `None` | Batch insert of PSM records |
| `get_identifications` | `(spectra_file_id=None, tool_id=None, sample_id=None, only_prefered=False, ...)` | `pd.DataFrame` | Joined with spectrum, tool, and sample metadata |
| `get_identifications_with_spectra_batch` | `(tool_id, offset, limit, only_missing=False, spectra_file_ids=None)` | `list[IdentificationWithSpectrum]` | Used by the ion coverage worker pool |
| `put_identification_data_batch` | `(data_rows: list[dict])` | `None` | Batch update of PPM, coverage, quality, LCRR, etc. (does **not** auto-save) |
| `set_preferred_identification` | `(spectre_id: int, identification_id: int)` | `None` | Marks one identification as preferred for a spectrum |
| `set_preferred_identifications_for_file` | `(spectra_file_id: int, preferred_ids: list[int])` | `None` | Bulk update of preferred flags for a spectra file |

---

### Peptide Matches & Joined Queries (`PeptideMixin`)

Manages links between identifications and protein sequences, and provides the main joined peptide query.

| Method | Signature | Returns | Notes |
|---|---|---|---|
| `add_peptide_matches_batch` | `(matches_df: pd.DataFrame)` | `None` | Batch insert into `peptide_match` (does **not** auto-save) |
| `clear_peptide_matches` | `()` | `None` | Deletes all peptide matches |
| `clear_peptide_matches_for_sample` | `(sample_id: int)` | `None` | Deletes matches for one sample |
| `get_joined_peptide_data` | `(**filters)` | `pd.DataFrame` | Full joined view (`spectre` + `identification` + `peptide_match` + `protein` + `sample` + `subset`) |
| `count_joined_peptide_data` | `(**filters)` | `int` | Row count for `get_joined_peptide_data` |

Common filters for `get_joined_peptide_data`:
`is_preferred` (`bool`), `sequence_identified` (`bool`), `protein_identified` (`bool`), `sample` (`str`), `sample_id` (`int`), `subset` (`str`), `tool` (`str`), `protein_id` (`str`), `gene` (`str`), `sequence` (`str`), `canonical_sequence` (`str`), `max_ppm` (`float`), `min_score` (`float`), `limit` (`int`), `offset` (`int`).

---

### Proteins & Quantification (`ProteinMixin`)

Manages the protein sequence database, sample-level protein identifications, and LFQ results.

| Method | Signature | Returns | Notes |
|---|---|---|---|
| `add_proteins_batch` | `(proteins_df: pd.DataFrame)` | `None` | `INSERT OR REPLACE` into `protein` |
| `get_protein` | `(protein_id: str)` | `Protein \| None` | Includes deserialized `uniprot_data` if present |
| `get_proteins` | `(is_uniprot: bool \| None = None)` | `pd.DataFrame` | Returns protein table rows |
| `get_protein_db_to_search` | `(null_sequence: bool = False)` | `dict[str, str]` | `{protein_id: sequence}` map for BLAST search |
| `add_protein_identifications_batch` | `(df: pd.DataFrame)` | `None` | Inserts into `protein_identification_result` |
| `clear_protein_identifications` | `()` | `None` | Clears all protein identification results |
| `add_protein_quantifications_batch` | `(df: pd.DataFrame)` | `None` | Inserts into `protein_quantification_result` |
| `get_protein_results_joined` | `(**filters)` | `pd.DataFrame` | Protein results with pivoted LFQ columns (`EmPAI`, `iBAQ`, `NSAF`, `Top3`) |
| `get_protein_quantification_data` | `(method=None, subsets=None, protein_id=None, exclude_outliers=True)` | `pd.DataFrame` | Long-format quantification table used by reports |
| `get_protein_statistics` | `(**filters)` | `pd.DataFrame` | Cross-sample aggregated protein statistics |

---

### Project Merge (`ImportProjectMixin`)

Merges all data from another `.dasmix` project (with matching `PROJECT_VERSION`) into the current project inside a single transaction:

```python
await project.import_project(
    source_path="other_project.dasmix",
    tool_match="parser",          # "parser", "name", or None
    subset_match=True,            # merge subsets with identical names
    sample_match=True,            # merge samples with identical names
    project_settings_match=False, # False = keep target settings; True = overwrite
    conflict_suffix="_1",
)
```

---

### Raw SQL (`QueryMixin`)

For custom analytical queries (e.g., inside custom report plugins):

```python
rows: list[dict] = await project.execute_query(
    "SELECT id, name FROM sample WHERE subset_id = ?", (1,)
)

df: pd.DataFrame = await project.execute_query_df(
    "SELECT * FROM protein_identification_result WHERE peptide_count >= ?", (2,)
)
```

---

## Data Transfer Objects (`dasmixer.api.project.dataclasses`)

All DTOs implement `.to_dict()` and `Class.from_dict(dict)`:

- **`Subset`**: `id, name, details, display_color`
- **`Tool`**: `id, name, type ("Library" | "De Novo"), parser, settings (dict), display_color`
- **`Sample`**: `id, name, subset_id, additions (dict), outlier (bool), subset_name, spectra_files_count`
- **`Protein`**: `id, is_uniprot, fasta_name, sequence, gene, name, taxon_id, organism_name, uniprot_data`
- **`IdentificationWithSpectrum`**: `id, spectre_id, pepmass, mz_array, intensity_array, tool_id, sequence, canonical_sequence, charge, peaks_count, ppm`

---

## Calculations API (`dasmixer.api.calculations`)

- **Ion Matching (`spectra.ion_match`)**:
  - `IonMatchParameters(ions=['b', 'y'], tolerance=20.0, mode='largest', water_loss=False, ammonia_loss=False, charges=[1, 2])`
  - `match_predictions(params, mz, intensity, charges, sequence) -> MatchResult`
- **Batch Identification Processing (`spectra.identification_processor`)**:
  - `process_identifications_batch(batch, params_dict, fragment_charges, target_ppm, ...)` — computes PPM,SeqFixer PTM/charge/isotope corrections, intensity coverage, quality, LCRR, and unconfirmed PTMs across worker processes.
- **Spectrum Plotting (`spectra.plot_flow`)**:
  - `make_full_spectrum_plot(params, mz, intensity, charges, sequences, headers, spectrum_info) -> go.Figure`
- **Preferred Identification Selection (`peptides.matching`)**:
  - `calculate_preferred_identifications_for_file(project, spectra_file_id, criterion, tool_settings) -> list[int]`
- **Protein Mapping (`peptides.protein_map`)**:
  - `await map_proteins(project, tool_settings, ion_params, fragment_charges, seqfixer_params, batch_size=5000, progress_callback=...)`
- **Protein Identifications (`proteins.map_identifications`)**:
  - `find_protein_identifications(joined_data, sequences_db, min_peptides=2, min_uq_evidence=1)` — async generator yielding `(result_df, sample_id)`.
- **Label-Free Quantification (`proteins.lfq`)**:
  - `await calculate_lfq(project, sample_id, methods=['emPAI', 'iBAQ', 'NSAF', 'Top3'], ...)`
