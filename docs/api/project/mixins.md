# Project API — Mixin Reference

Each mixin adds a group of domain-specific methods to the `Project` class. All methods are `async`.

---

## SubsetMixin

**File:** `dasmixer/api/project/mixins/subset_mixin.py`

Manages comparison groups (subsets) used to organize samples for differential analysis.

| Method | Signature | Returns | Notes |
|---|---|---|---|
| `add_subset` | `(name, details?, display_color?)` | `Subset` | Raises `ValueError` if name exists |
| `get_subsets` | `()` | `list[Subset]` | Ordered by name |
| `get_subset` | `(subset_id)` | `Subset\|None` | By ID |
| `update_subset` | `(subset: Subset)` | `None` | Requires `subset.id` |
| `delete_subset` | `(subset_id)` | `None` | Raises `ValueError` if samples are associated |

---

## ToolMixin

**File:** `dasmixer/api/project/mixins/tool_mixin.py`

Manages identification tools. Each tool has a type (`"Library"` or `"De Novo"`) and a parser name.

| Method | Signature | Returns | Notes |
|---|---|---|---|
| `add_tool` | `(name, type, parser, settings?, display_color?)` | `Tool` | `type` must be `"Library"` or `"De Novo"` |
| `get_tools` | `()` | `list[Tool]` | Ordered by name |
| `get_tool` | `(tool_id)` | `Tool\|None` | By ID |
| `update_tool` | `(tool: Tool)` | `None` | |
| `delete_tool` | `(tool_id)` | `None` | Raises `ValueError` if identifications exist |

---

## SampleMixin

**File:** `dasmixer/api/project/mixins/sample_mixin.py`

Manages samples and sample statistics. Samples are the top-level grouping for spectra.

### Basic CRUD

| Method | Signature | Returns | Notes |
|---|---|---|---|
| `add_sample` | `(name, subset_id?, additions?, outlier?)` | `Sample` | |
| `get_samples` | `(subset_id?)` | `list[Sample]` | Includes `subset_name`, `spectra_files_count` |
| `get_sample` | `(sample_id)` | `Sample\|None` | |
| `get_sample_by_name` | `(name)` | `Sample\|None` | |
| `update_sample` | `(sample: Sample)` | `None` | |
| `delete_sample` | `(sample_id)` | `None` | Cascades to spectra files |

### Statistics

| Method | Returns | Notes |
|---|---|---|
| `get_sample_stats(sample_id)` | `dict` | Live aggregated stats: spectra_files_count, ident_files_count, identifications_count, preferred_count, coverage_known_count, protein_ids_count, empty_ident_files_count |
| `get_sample_detail(sample_id)` | `list[dict]` | File tree: spectra files + their identification files + counts |
| `get_tools_count()` | `int` | Total number of tools in project |
| `get_sample_status_summary(min_proteins, min_idents)` | `dict` | OK/WARNING/ERROR counts across all samples |
| `get_sample_counts_by_subset()` | `dict[int, int]` | Sample counts per subset_id |

### Status Cache

The `sample_status_cache` table stores pre-computed stats per sample, avoiding expensive recalculation on every UI refresh.

| Method | Description |
|---|---|
| `get_cached_sample_stats(sample_id)` | Returns cached stats dict or `None` |
| `get_all_cached_sample_stats()` | All samples: `{sample_id: stats_dict}` |
| `upsert_sample_status_cache(sample_id, stats)` | Write to cache (no `save()` called) |
| `invalidate_sample_status_cache(sample_id)` | Remove cache entry |
| `compute_and_cache_sample_stats(sample_id)` | Recalculate and cache, then `save()` |

---

## SpectraMixin

**File:** `dasmixer/api/project/mixins/spectra_mixin.py`

Manages spectra files and individual spectrum records.

### Spectra Files

| Method | Returns | Notes |
|---|---|---|
| `add_spectra_file(sample_id, format, path)` | `int` (file ID) | Validates sample exists |
| `get_spectra_files(sample_id?)` | `DataFrame` | Columns: id, sample_id, format, path, sample_name |
| `delete_spectra_file(spectra_file_id)` | `None` | Cascades: spectra → identifications → peptide_matches |

### Spectra Records

| Method | Returns | Notes |
|---|---|---|
| `add_spectra_batch(spectra_file_id, spectra_df)` | `None` | Batch insert; arrays compressed |
| `get_spectra(spectra_file_id?, sample_id?, limit?, offset?)` | `DataFrame` | No arrays (metadata only) |
| `get_spectrum_full(spectrum_id)` | `dict` | Full data with decompressed NumPy arrays |
| `get_spectra_idlist(spectra_file_id, by="seq_no")` | `list[dict]` | `[{"seq_no": n, "spectre_id": id}, ...]` — for identification import |
| `get_spectra_for_identification_ids(identification_ids)` | `dict[int, dict]` | Arrays for PPM recalculation during protein mapping |

**`spectra_df` columns for `add_spectra_batch`:**

| Column | Type | Notes |
|---|---|---|
| `seq_no` | `int` | Sequential number in file |
| `title` | `str\|None` | MGF TITLE |
| `scans` | `int\|None` | MGF SCANS |
| `charge` | `int\|None` | Precursor charge |
| `rt` | `float\|None` | Retention time |
| `pepmass` | `float` | Precursor m/z |
| `mz_array` | `np.ndarray` | Peak m/z values |
| `intensity_array` | `np.ndarray` | Peak intensities |
| `charge_array` | `np.ndarray\|None` | Per-peak charge (rare) |
| `charge_array_common_value` | `int\|None` | If all peaks have same charge |
| `peaks_count` | `int\|None` | Auto-computed from mz_array if absent |
| `all_params` | `dict\|None` | All raw MGF key-value pairs |

---

## IdentificationMixin

**File:** `dasmixer/api/project/mixins/identification_mixin.py`

Manages identification files and identification records.

### Identification Files

| Method | Returns | Notes |
|---|---|---|
| `add_identification_file(spectra_file_id, tool_id, file_path)` | `int` (file ID) | |
| `get_identification_files(spectra_file_id?, tool_id?)` | `DataFrame` | |
| `delete_identification_file(ident_file_id)` | `None` | Cascades to identifications → peptide_matches |

### Identifications

| Method | Returns | Notes |
|---|---|---|
| `add_identifications_batch(identifications_df)` | `None` | Batch insert |
| `get_identifications(...)` | `DataFrame` | Rich join with spectrum, tool, sample info |
| `get_identifications_count(tool_id, only_missing?, spectra_file_ids?)` | `int` | Count for progress tracking |
| `get_identifications_with_spectra_batch(tool_id, offset, limit, only_missing?, spectra_file_ids?)` | `list[IdentificationWithSpectrum]` | For ion coverage calculation pipeline |
| `get_idents_for_preferred(...)` | `DataFrame` | Filtered candidates for preferred selection |

**`get_identifications` filters:**

| Parameter | Type | Description |
|---|---|---|
| `spectra_file_id` | `int\|None` | Filter by spectra file |
| `tool_id` | `int\|None` | Filter by tool |
| `sample_id` | `int\|None` | Filter by sample |
| `only_prefered` | `bool` | Only `is_preferred = 1` |
| `max_abs_ppm` | `float\|None` | Maximum absolute PPM error |
| `offset`, `limit` | `int` | Pagination |

### Updating Identifications

| Method | Description |
|---|---|
| `put_identification_data_batch(data_rows)` | Batch update PPM, coverage, ion match fields |
| `update_identification_coverage(ident_id, coverage)` | Single update (no auto-save) |
| `update_identification_coverage_batch(params)` | Batch: `[(coverage, id), ...]` |
| `set_preferred_identification(spectre_id, identification_id)` | Mark one as preferred (resets others) |
| `set_preferred_identifications_for_file(spectra_file_id, preferred_ids)` | Bulk set for file |

**`put_identification_data_batch` dict keys:**

`id`, `sequence`, `ppm`, `theor_mass`, `override_charge`, `isotope_offset`, `intensity_coverage`, `ions_matched`, `ion_match_type`, `top_peaks_covered`, `source_sequence`

---

## PeptideMixin

**File:** `dasmixer/api/project/mixins/peptide_mixin.py`

Manages peptide matches (protein→identification links) and provides the central joined peptide query.

### Peptide Matches

| Method | Description |
|---|---|
| `add_peptide_matches_batch(matches_df)` | Batch insert (no auto-save) |
| `get_peptide_matches(protein_id?, identification_id?)` | Basic query |
| `get_peptide_matches_with_spectra()` | Joined with spectrum arrays (for LFQ metrics) |
| `put_peptide_match_data_batch(data_rows)` | Update matched_ppm, matched_theor_mass, matched_coverage_percent |
| `clear_peptide_matches()` | Delete all (for re-mapping) |
| `clear_peptide_matches_for_sample(sample_id)` | Delete for specific sample |

### Main Joined Query

`get_joined_peptide_data(**filters)` is the central read method for the Peptides tab and LFQ calculations. It joins `spectre`, `identification`, `peptide_match`, `protein`, `sample`, `subset` tables.

**Filters:**

| Parameter | Type | Description |
|---|---|---|
| `is_preferred` | `bool\|None` | Only preferred identifications |
| `sequence_identified` | `bool\|None` | Has sequence |
| `protein_identified` | `bool\|None` | Has protein match |
| `sample` / `sample_id` | `str\|int` | Filter by sample |
| `subset` / `subset_id` | `str\|int` | Filter by subset |
| `sequence` | `str` | LIKE filter on sequence |
| `canonical_sequence` | `str` | LIKE filter |
| `matched_sequence` | `str` | LIKE filter |
| `seq_no` / `scans` | `int` | Exact spectrum position |
| `tool` / `tool_id` | `str\|int` | Filter by tool |
| `identification_id` | `int` | Exact identification |
| `protein_id` | `str` | Exact protein |
| `gene` | `str` | LIKE filter |
| `max_ppm` | `float` | Maximum PPM |
| `min_score` | `float` | Minimum score |
| `limit`, `offset` | `int` | Pagination |

**Returned DataFrame columns:**
`sample, subset, sample_id, subset_id, spectre_id, seq_no, scans, charge, rt, pepmass, intensity, tool, tool_id, identification_id, sequence, canonical_sequence, ppm, score, is_preferred, ions_matched, ion_match_type, top_peaks_covered, intensity_coverage, matched_sequence, matched_ppm, protein_id, identity, unique_evidence, gene, matched_peaks, matched_top_peaks, matched_ion_type, matched_sequence_modified, substitution`

`count_joined_peptide_data(**same_filters)` → `int` (count without loading data).

---

## ProteinMixin

**File:** `dasmixer/api/project/mixins/protein_mixin.py`

Manages proteins, identification results, and quantification.

### Proteins

| Method | Returns | Notes |
|---|---|---|
| `add_protein(protein_id, sequence, ...)` | `None` | `INSERT OR REPLACE` |
| `add_proteins_batch(proteins_df)` | `None` | |
| `get_protein(protein_id)` | `Protein\|None` | Deserializes uniprot_data |
| `get_proteins(is_uniprot?)` | `list[Protein]` | |
| `get_protein_db_to_search()` | `dict[str, str]` | `{protein_id: sequence}` for npysearch |
| `get_protein_count()` | `int` | |

### Protein Identification Results

| Method | Description |
|---|---|
| `add_protein_identifications_batch(df)` | Batch insert: protein_id, sample_id, peptide_count, uq_evidence_count, coverage, intensity_sum |
| `get_protein_identifications(sample_id?)` | Returns DataFrame |
| `get_protein_identification_count()` | Count |
| `clear_protein_identifications()` | Delete all |
| `clear_protein_identifications_for_sample(sample_id)` | Delete for sample |

### Quantification

| Method | Description |
|---|---|
| `add_protein_quantifications_batch(df)` | Batch insert: protein_identification_id, algorithm, rel_value, abs_value |
| `get_protein_quantification_count()` | Count |
| `get_protein_quantification_data(method?, subsets?, protein_id?)` | Full quantification data joined with protein and sample info |
| `clear_protein_quantifications()` | Delete all |
| `clear_protein_quantifications_for_sample(sample_id)` | Delete for sample |

### Joined Results View

`get_protein_results_joined(**filters)` — primary view for Proteins tab. Returns one row per `protein_identification_result` with pivoted LFQ columns.

**Filters:** `sample, subset, protein_id, gene, min_peptides, min_unique, min_coverage, max_coverage, min_intensity, max_intensity, limit, offset`

**Returns columns:** `sample, subset, protein_id, gene, weight, peptide_count, unique_evidence_count, coverage_percent, intensity_sum, EmPAI, iBAQ, NSAF, Top3`

`count_protein_results_joined(**same_filters)` → `int`

`get_protein_statistics(protein_id, gene, fasta_name, min_samples, min_subsets, only_identified, limit, offset)` — aggregated cross-sample protein stats.

---

## QueryMixin

**File:** `dasmixer/api/project/mixins/query_mixin.py`

Low-level SQL access for complex report queries.

| Method | Returns |
|---|---|
| `execute_query(query, params?)` | `list[dict]` |
| `execute_query_df(query, params?)` | `pd.DataFrame` |

Use these for custom report logic that can't be expressed through standard domain methods.

---

## ReportMixin

**File:** `dasmixer/api/project/mixins/report_mixin.py`

Manages report storage (complements `BaseReport` from reporting module).

| Method | Returns | Notes |
|---|---|---|
| `get_generated_reports(report_name?)` | `list[dict]` | Metadata only (no blobs) |
| `delete_generated_report(report_id)` | `None` | |
| `save_report_parameters(report_name, parameters)` | `None` | Upsert |
| `get_report_parameters(report_name)` | `str\|None` | |

---

## PlotMixin

**File:** `dasmixer/api/project/mixins/plot_mixin.py`

Data preparation methods for the ion spectrum plot. Retrieves spectrum + identification data in the format required by `plot_matches.py`.

(See source for current method signatures — this mixin is evolving.)

---

## fast_ident_match_mixin

**File:** `dasmixer/api/project/mixins/fast_ident_match_mixin.py`

Optimized identification match lookup for high-performance operations. Not directly exposed in `Project` composition by default — see source for usage.
