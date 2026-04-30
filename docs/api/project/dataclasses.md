# Project API — Dataclasses

**File:** `dasmixer/api/project/dataclasses.py`

Dataclasses serve as data transfer objects (DTOs) between the database and application logic. They provide a typed interface instead of raw dicts.

All dataclasses implement:
- `to_dict()` → `dict` — for DB insert/update operations
- `from_dict(data: dict)` → instance — create from a DB row

---

## Subset

Represents a comparison group used to organize samples for differential analysis.

```python
@dataclass
class Subset:
    id: int | None = None
    name: str = ""
    details: str | None = None
    display_color: str | None = None  # Hex color string, e.g. "#3B82F6"
```

| Field | Type | Notes |
|---|---|---|
| `id` | `int\|None` | Auto-assigned by DB; `None` before insert |
| `name` | `str` | Unique name (UNIQUE constraint in DB) |
| `details` | `str\|None` | Optional description |
| `display_color` | `str\|None` | Hex color for UI visualization |

---

## Tool

Represents an identification tool (library or de novo sequencer).

```python
@dataclass
class Tool:
    id: int | None = None
    name: str = ""
    type: Literal['Library', 'De Novo'] = "Library"
    parser: str = "library"          # Parser name in InputTypesRegistry
    settings: dict | None = None     # Tool-specific settings (JSON in DB)
    display_color: str | None = None
```

| Field | Type | Notes |
|---|---|---|
| `id` | `int\|None` | Auto-assigned |
| `name` | `str` | Unique tool name |
| `type` | `"Library"\|"De Novo"` | Tool category |
| `parser` | `str` | Must match a registered parser name (e.g. `"PowerNovo2"`, `"MGF"`) |
| `settings` | `dict\|None` | Arbitrary tool settings; stored as JSON TEXT in DB |
| `display_color` | `str\|None` | Hex color |

**Serialization note:** `settings` is serialized via `json.dumps` on `to_dict()` and deserialized on `from_dict()`.

---

## Sample

Represents a mass spectrometry sample (one biological replicate).

```python
@dataclass
class Sample:
    id: int | None = None
    name: str = ""
    subset_id: int | None = None    # FK to subset.id
    additions: dict | None = None   # Extra metadata (albumin, total_protein, etc.)
    outlier: bool = False           # True = excluded from group analysis

    # Computed fields (not in DB, filled on load)
    subset_name: str | None = field(default=None, repr=False)
    spectra_files_count: int = field(default=0, repr=False)
```

| Field | Type | Notes |
|---|---|---|
| `id` | `int\|None` | Auto-assigned |
| `name` | `str` | Unique sample name |
| `subset_id` | `int\|None` | FK to `subset.id`; `None` = no group assigned |
| `additions` | `dict\|None` | Example: `{"albumin": 0.5, "total_protein": 2.3}` |
| `outlier` | `bool` | Stored as INTEGER 0/1 in DB |
| `subset_name` | `str\|None` | Populated by `get_samples()` via JOIN |
| `spectra_files_count` | `int` | Populated by `get_samples()` via subquery |

---

## Protein

Represents a protein sequence entry from a FASTA database or UniProt.

```python
@dataclass
class Protein:
    id: str = ""                    # UniProt accession or custom ID
    is_uniprot: bool = False
    fasta_name: str | None = None   # Full name from FASTA header
    sequence: str | None = None     # Amino acid sequence
    gene: str | None = None         # Gene name
    name: str | None = None         # Short protein name
    uniprot_data: UniprotData | None = field(default=None, repr=False)

    # Not stored in main table
    protein_atlas_data: dict | None = field(default=None, repr=False)
```

| Field | Type | Notes |
|---|---|---|
| `id` | `str` | Primary key (TEXT in SQLite) |
| `is_uniprot` | `bool` | Stored as INTEGER 0/1 |
| `fasta_name` | `str\|None` | Full FASTA header name |
| `sequence` | `str\|None` | Amino acid sequence (one-letter code) |
| `gene` | `str\|None` | Gene name for display and filtering |
| `name` | `str\|None` | Short name |
| `uniprot_data` | `UniprotData\|None` | Serialized as pickle+gzip BLOB in DB |
| `protein_atlas_data` | `dict\|None` | Not stored in DB; reserved for future enrichment |

**Important:** `to_dict()` does NOT include `uniprot_data` (stored separately). `from_dict()` leaves it as `None` — load explicitly if needed.

---

## IdentificationWithSpectrum

Combined dataclass for ion coverage calculation pipeline. Carries both identification metadata and spectrum arrays without additional DB round-trips.

```python
@dataclass
class IdentificationWithSpectrum:
    id: int                          # identification.id
    spectre_id: int
    pepmass: float                   # Precursor m/z
    mz_array: ndarray                # Experimental m/z peaks
    intensity_array: ndarray         # Experimental intensities
    tool_id: int
    sequence: str                    # Peptide sequence (possibly with mods)
    canonical_sequence: str          # Sequence without modifications
    charge: int | None               # Precursor charge from spectrum
    peaks_count: int | None          # Number of peaks
```

**`from_dict(data)`** — creates from DB row; decompresses `mz_array` and `intensity_array` from BLOB via `decompress_array()`.

**`to_worker_dict()`** — serializes arrays to Python lists for safe multiprocessing pickling (across `ProcessPoolExecutor` workers).

---

## Usage Example

```python
from dasmixer.api.project.project import Project

async with Project("study.dasmix") as project:
    # Add subset
    subset = await project.add_subset("Control", display_color="#3B82F6")
    print(subset.id, subset.name)

    # Add tool
    tool = await project.add_tool(
        name="PowerNovo2",
        type="De Novo",
        parser="PowerNovo2",
        settings={"version": "2.0"},
        display_color="#10B981"
    )

    # Add sample
    sample = await project.add_sample("S01", subset_id=subset.id)

    # Retrieve
    subsets = await project.get_subsets()
    for s in subsets:
        print(s.name, s.display_color)

    # Get single protein
    protein = await project.get_protein("P12345")
    if protein:
        print(protein.gene, protein.sequence[:10])
```
