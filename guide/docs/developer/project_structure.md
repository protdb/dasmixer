# Project File Structure (`.dasmix`)

A DASMixer project file (`.dasmix`) is a self-contained **SQLite 3** database operating in Write-Ahead Logging (**WAL**) mode with foreign key constraints enforced (`PRAGMA foreign_keys = ON`).

Because it is a standard SQLite file, you can inspect or query it directly using `dasmixer-core`, Python's built-in `sqlite3` module, or any database viewer (such as DBeaver or DB Browser for SQLite).

---

## Entity-Relationship Diagram

```mermaid
erDiagram
    PROJECT_METADATA {
        string key PK
        string value
    }

    PROJECT_SETTINGS {
        string key PK
        string value
    }

    SUBSET {
        int id PK
        string name UK
        string details
        string display_color
    }

    TOOL {
        int id PK
        string name UK
        string type
        string parser
        json settings
        string display_color
    }

    SAMPLE {
        int id PK
        string name UK
        int subset_id FK
        json additions
        bool outlier
    }

    SPECTRE_FILE {
        int id PK
        int sample_id FK
        string format
        string path
    }

    SPECTRE {
        int id PK
        int spectre_file_id FK
        int seq_no
        string title
        int scans
        int charge
        float rt
        float pepmass
        float intensity
        blob mz_array
        blob intensity_array
        int peaks_count
        blob charge_array
        int charge_array_common_value
        json all_params
    }

    IDENTIFICATION_FILE {
        int id PK
        int spectre_file_id FK
        int tool_id FK
        string file_path
        string selection_field
        string selection_field_value
    }

    IDENTIFICATION {
        int id PK
        int spectre_id FK
        int tool_id FK
        int ident_file_id FK
        bool is_preferred
        string sequence
        string canonical_sequence
        float ppm
        float theor_mass
        float score
        json positional_scores
        float intensity_coverage
        int ions_matched
        string ion_match_type
        int top_peaks_covered
        int override_charge
        string source_sequence
        int isotope_offset
        float quality
        float override_pepmass
        bool has_ptm
        float lcrr
        int unconfirmed_ptms
        string src_file_protein_id
        float fdr
        float e_value
        float q_value
    }

    PROTEIN {
        string id PK
        bool is_uniprot
        string fasta_name
        string sequence
        string gene
        string name
        blob uniprot_data
        int taxon_id
        string organism_name
    }

    PEPTIDE_MATCH {
        int id PK
        string protein_id FK
        int identification_id FK
        string matched_sequence
        float identity
        float matched_ppm
        float matched_theor_mass
        bool unique_evidence
        float matched_coverage_percent
        int matched_peaks
        int matched_top_peaks
        string matched_ion_type
        string matched_sequence_modified
        bool substitution
    }

    PROTEIN_IDENTIFICATION_RESULT {
        int id PK
        string protein_id FK
        int sample_id FK
        int peptide_count
        int uq_evidence_count
        float coverage
        float intensity_sum
    }

    PROTEIN_QUANTIFICATION_RESULT {
        int id PK
        int protein_identification_id FK
        string algorithm
        float rel_value
        float abs_value_mol
        float abs_value_gl
    }

    GENERATED_REPORTS {
        int id PK
        string report_name
        string name
        datetime created_at
        blob plots
        blob tables
        json project_settings
        json tools_settings
        json report_settings
    }

    REPORT_PARAMETERS {
        int id PK
        string report_name UK
        json parameters
    }

    SAVED_PLOTS {
        int id PK
        datetime created_at
        string plot_type
        json settings
        blob plot
    }

    SUBSET ||--o{ SAMPLE : contains
    SAMPLE ||--o{ SPECTRE_FILE : contains
    SPECTRE_FILE ||--o{ SPECTRE : includes
    SPECTRE ||--o{ IDENTIFICATION : describes
    TOOL ||--o{ IDENTIFICATION_FILE : produces
    IDENTIFICATION_FILE ||--o{ IDENTIFICATION : contains
    TOOL ||--o{ IDENTIFICATION : produces
    IDENTIFICATION ||--o{ PEPTIDE_MATCH : has
    PROTEIN ||--o{ PEPTIDE_MATCH : matched_by
    PROTEIN ||--o{ PROTEIN_IDENTIFICATION_RESULT : describes
    SAMPLE ||--o{ PROTEIN_IDENTIFICATION_RESULT : describes
    PROTEIN_IDENTIFICATION_RESULT ||--o{ PROTEIN_QUANTIFICATION_RESULT : quantified_by
```

---

## Binary and JSON Encoding Conventions

### NumPy Arrays (`spectre` table)

Peak lists (`mz_array`, `intensity_array`, `charge_array`) are compressed into `BLOB` columns using `np.savez_compressed`. To read or write them in Python, use the helper functions in `dasmixer.api.project.array_utils`:

```python
from dasmixer.api.project.array_utils import compress_array, decompress_array

blob: bytes = compress_array(mz_numpy_array)
mz_numpy_array = decompress_array(blob)
```

### Pickled Objects (`protein`, `generated_reports`, `saved_plots`)

Complex Python objects (`uniprot_data`, report `plots` and `tables`, and `saved_plots.plot`) are serialized with `pickle.dumps()` and compressed with `gzip.compress()`.

### JSON Columns

SQLite `TEXT` columns are used for structured dictionaries and lists (`tool.settings`, `sample.additions`, `spectre.all_params`, `identification.positional_scores`, and settings snapshots in `generated_reports`). They are serialized with standard `json.dumps()` and `json.loads()`.

---

## Portability and WAL Files

While a project is open, SQLite creates two companion files alongside `project.dasmix`:

- `project.dasmix-wal` (Write-Ahead Log)
- `project.dasmix-shm` (Shared Memory index)

When `project.close()` or `project.save(checkpoint=True)` is called (or via `dasmixer-cli checkpoint project.dasmix`), all transactions from the `-wal` file are merged into the main `.dasmix` file, making it safe to copy or share as a single file.
