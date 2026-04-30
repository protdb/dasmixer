# Project API — Architecture

## Overview

The `Project` class is the central data access object in DASMixer. It provides the complete interface for creating, reading, and updating all project data stored in a SQLite database.

`Project` is implemented as a **composition of mixins** — the class itself contains no logic, only inheriting from a chain of mixin classes. This keeps each domain isolated and testable independently.

---

## Class Hierarchy

```
ProjectBase                      # Low-level DB operations (dasmixer/api/project/core/base.py)
  └─ ProjectLifecycle            # DB lifecycle: initialize, save, close (core/lifecycle.py)
       └─ Project (composed)     # Composed class with all mixins (project.py)
            ├─ SubsetMixin       # Comparison groups (mixins/subset_mixin.py)
            ├─ ToolMixin         # Identification tools (mixins/tool_mixin.py)
            ├─ SampleMixin       # Samples (mixins/sample_mixin.py)
            ├─ SpectraMixin      # Spectra files and data (mixins/spectra_mixin.py)
            ├─ IdentificationMixin  # Identifications (mixins/identification_mixin.py)
            ├─ PeptideMixin      # Peptide matches + joined queries (mixins/peptide_mixin.py)
            ├─ ProteinMixin      # Proteins, results, LFQ (mixins/protein_mixin.py)
            ├─ PlotMixin         # Plot data prep (mixins/plot_mixin.py)
            ├─ QueryMixin        # Raw SQL access (mixins/query_mixin.py)
            └─ ReportMixin       # Report storage (mixins/report_mixin.py)
```

Python MRO ensures that `ProjectLifecycle → ProjectBase` methods are available to all mixins at runtime.

---

## ProjectBase — Low-Level Database Operations

**File:** `dasmixer/api/project/core/base.py`

`ProjectBase` is the root class. It manages the aiosqlite connection and provides low-level DB primitives used by all mixins.

### Constructor

```python
ProjectBase(
    path: Path | str | None = None,
    create_if_not_exists: bool = True
)
```

| Parameter | Description |
|---|---|
| `path` | Path to `.dasmix` file. `None` = in-memory database. |
| `create_if_not_exists` | If `False` and file doesn't exist, raises `FileNotFoundError` |

### Low-Level Methods

| Method | Signature | Description |
|---|---|---|
| `_execute` | `(query, params?) → Cursor` | Execute INSERT/UPDATE/DELETE |
| `_executemany` | `(query, params_list) → Cursor` | Batch execute (for inserts) |
| `_commit` | `() → None` | Lightweight commit without updating `modified_at` |
| `_fetchone` | `(query, params?) → dict\|None` | Fetch single row as dict |
| `_fetchall` | `(query, params?) → list[dict]` | Fetch all rows as list of dicts |

### Serialization Utilities

| Method | Description |
|---|---|
| `_serialize_json(data)` | Convert Python object → JSON string (returns `None` for `None`) |
| `_deserialize_json(json_str)` | JSON string → Python object |
| `_serialize_pickle_gzip(obj)` | Object → pickle+gzip bytes (for BLOBs) |
| `_deserialize_pickle_gzip(blob)` | pickle+gzip bytes → Python object |

---

## ProjectLifecycle — Database Lifecycle

**File:** `dasmixer/api/project/core/lifecycle.py`

Extends `ProjectBase` with connection management and context manager protocol.

### Initialization

```python
async def initialize() -> None
```

1. Opens aiosqlite connection
2. Sets `PRAGMA journal_mode = WAL` and `PRAGMA synchronous = NORMAL`
3. Enables `PRAGMA foreign_keys = ON`
4. Runs `CREATE_SCHEMA_SQL` (creates tables if not exist)
5. Inserts default metadata (`version`, `created_at`, `modified_at`) for new DB
6. Sets `self._initialized = True`

### Persistence Methods

| Method | Description |
|---|---|
| `save()` | Updates `modified_at` and commits transaction |
| `save_as(path)` | Saves project to a new file path (file copy + reopen) |
| `close()` | Commits and closes the connection |
| `__aenter__` / `__aexit__` | Context manager protocol (auto-close on exit) |

### Settings Methods

| Method | Description |
|---|---|
| `get_metadata()` | Returns `dict` with project metadata (version, timestamps) |
| `set_setting(key, value)` | Upsert project setting |
| `get_setting(key, default?)` | Get project setting by key |
| `get_all_settings()` | Returns all project settings as `dict` |

---

## Key Design Decisions

### Async-First
All public methods are `async`. This prevents UI blocking in the Flet event loop. aiosqlite wraps SQLite operations in a background thread.

### WAL Mode
`PRAGMA journal_mode = WAL` allows readers and the single writer to run concurrently. Combined with `synchronous = NORMAL`, this gives good crash safety without major performance penalty.

### Batch vs. Save
High-volume operations use `_executemany` internally. They do **not** call `save()` — this is left to the caller to avoid N intermediate commits. For tight batch loops, `_commit()` can be used to flush data without updating `modified_at`.

### Row Factory
`aiosqlite.Row` is set as row factory, allowing dict-like access by column name. All `_fetchone` and `_fetchall` results are converted to plain `dict` objects for easier downstream use.

### Array Storage
NumPy arrays (mz, intensity, charge) are stored as compressed blobs using `np.savez_compressed`. See `dasmixer/api/project/array_utils.py`.

---

## File Reference

| File | Class | Purpose |
|---|---|---|
| `core/base.py` | `ProjectBase` | Low-level DB operations |
| `core/lifecycle.py` | `ProjectLifecycle` | Init, save, close, context manager |
| `project.py` | `Project` | Mixin composition (no own logic) |
| `schema.py` | — | `CREATE_SCHEMA_SQL`, `DEFAULT_METADATA` |
| `dataclasses.py` | `Subset, Tool, Sample, Protein, IdentificationWithSpectrum` | Data transfer objects |
| `array_utils.py` | — | `compress_array`, `decompress_array` |
| `mixins/*.py` | `*Mixin` | Domain-specific logic |
