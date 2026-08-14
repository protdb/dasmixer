# Project Merge Example

This document demonstrates how to **merge two `.dasmix` projects** into one using
only `dasmixer-core` (no GUI). The second project's data is imported into the first
one, with configurable deduplication strategies for subsets, tools, and samples.

---

## Table of Contents

1. [Overview](#overview)
2. [The `import_project` Method](#the-import_project-method)
3. [Deduplication Strategies](#deduplication-strategies)
4. [Complete Script](#complete-script)

---

## Overview

The merge operation accepts two paths to `.dasmix` project files:

| Input | Role |
|-------|------|
| `target_path` | The project that will receive the data (modified in place) |
| `source_path` | The project whose data is imported (read-only, never modified) |

After a successful call, `target_path` contains all of its own data **plus** all data
from `source_path`, with foreign keys remapped according to the chosen matching
strategies. The source file is left untouched.

A backup of the target file is created automatically before the merge runs, so the
operation is safe to retry.

---

## The `import_project` Method

The merge is performed by a single method on the `Project` class:

```python
await project.import_project(
    source_path: str | Path,
    tool_match: Literal['name', 'parser'] | None = 'parser',
    subset_match: bool = True,
    project_settings_match: bool = False,
    sample_match: bool = True,
    conflict_suffix: str = "_1",
    status_callback: Callable[[str, float], None] | None = None,
) -> None
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `source_path` | `str \| Path` | — | Path to the `.dasmix` file to import from |
| `tool_match` | `'name' \| 'parser' \| None` | `'parser'` | How to match tools between projects |
| `subset_match` | `bool` | `True` | If `True`, merge subsets by name; if `False`, add all with suffix |
| `project_settings_match` | `bool` | `False` | If `True`, overwrite target settings with source; if `False`, only add new keys |
| `sample_match` | `bool` | `True` | If `True`, merge samples by name; if `False`, add all with suffix |
| `conflict_suffix` | `str` | `"_1"` | Suffix appended to duplicate names when not merging |
| `status_callback` | `Callable \| None` | `None` | Optional `(table_name, fraction)` progress callback |

**What happens under the hood:**

1. The source database is opened in **read-only mode** (`PRAGMA query_only = ON`).
2. The target database is tuned for bulk insert (`synchronous = NORMAL`,
   `cache_size = -65536`).
3. A single transaction (`BEGIN` … `COMMIT`) wraps the entire operation. On any
   exception, the transaction is rolled back — the target file is left unchanged.
4. ID mappings for `subset`, `tool`, and `sample` are built row-by-row.
5. The source database is `ATTACH`-ed and the remaining tables are bulk-copied via
   SQL `INSERT ... SELECT` with offset ID arithmetic.
6. Autoincrement sequences are reset to `MAX(id)` for every affected table.
7. A final `save(checkpoint=True)` flushes the WAL for portability.

**Tables copied in bulk** (with remapped foreign keys):

| Table | Foreign keys remapped |
|---|---|
| `protein` | — (deduplicated by primary key via `INSERT OR IGNORE`) |
| `spectre_file` | `sample_id` |
| `spectre` | `spectre_file_id` |
| `identification_file` | `spectre_file_id`, `tool_id` |
| `identification` | `spectre_id`, `tool_id`, `ident_file_id` |
| `peptide_match` | `protein_id`, `identification_id` |
| `protein_identification_result` | `protein_id`, `sample_id` |
| `protein_quantification_result` | `protein_identification_id` |
| `generated_reports` | — |
| `saved_plots` | — |
| `project_settings` | — (merged by key) |

---

## Deduplication Strategies

### Subsets

- **`subset_match=True`** (default): subsets with the same `name` in both projects
  are merged into a single row. All samples and results from the source are
  re-linked to the existing target subset.
- **`subset_match=False`**: every source subset is inserted as a new row. If a name
  conflicts, `conflict_suffix` is appended repeatedly until unique.

### Tools

- **`tool_match='parser'`** (default): tools are matched by their `parser` field
  (e.g. `"PowerNovo2"`). This is the recommended option — two projects produced by
  the same engine share one tool row.
- **`tool_match='name'`**: match by the user-visible tool name.
- **`tool_match=None`**: never match — every source tool is inserted as a new row
  (with suffix on name conflict). Use this when you want to keep results from two
  runs of the same engine side by side.

### Samples

- **`sample_match=True`** (default): samples with the same `name` are merged into a
  single row. Spectra and identifications from the source are appended to the
  existing sample. **Note:** the merged sample keeps the target's `subset_id`,
  `additions`, and `outlier` values — the source's values for these fields are
  discarded for matched samples.
- **`sample_match=False`**: every source sample is inserted as a new row (with
  suffix on name conflict). The source's `subset_id` is remapped via the subset
  mapping.

### Project Settings

- **`project_settings_match=False`** (default): only settings with **new keys**
  are added; existing target settings are preserved (`INSERT OR IGNORE`).
- **`project_settings_match=True`**: source settings **overwrite** target settings
  with the same key (`INSERT OR REPLACE`).

---

## Complete Script

The function `merge_projects(target_path, source_path, **kwargs)` opens the target
project, creates a `.bak` backup, runs `import_project`, and verifies the result by
printing row counts before and after.

**Command-line usage:**

```bash
python merge_projects.py target.dasmix source.dasmix
```

**As a library:**

```python
import asyncio
from merge_projects import merge_projects

asyncio.run(merge_projects(
    target_path="target.dasmix",
    source_path="source.dasmix",
    tool_match="parser",
    subset_match=True,
    sample_match=True,
))
```

---

```python
#!/usr/bin/env python3
"""
Merge two .dasmix projects into one.

The target project receives all data from the source project. The source file is
opened in read-only mode and never modified. A backup of the target file is
created automatically before the merge.
"""

import argparse
import asyncio
import shutil
from pathlib import Path

from dasmixer.api.project.project import Project


TABLES = [
    "subset",
    "tool",
    "sample",
    "spectre_file",
    "spectre",
    "identification_file",
    "identification",
    "peptide_match",
    "protein",
    "protein_identification_result",
    "protein_quantification_result",
    "generated_reports",
    "saved_plots",
]


async def _row_counts(project: Project) -> dict[str, int]:
    """Return {table_name: row_count} for all merge-related tables."""
    counts: dict[str, int] = {}
    for table in TABLES:
        row = await project._fetchone(f"SELECT COUNT(*) AS n FROM {table}")
        counts[table] = row["n"] if row else 0
    return counts


def _print_counts(label: str, counts: dict[str, int]) -> None:
    print(f"\n[{label}]")
    for table in TABLES:
        print(f"  {table:<35} {counts.get(table, 0):>10}")


async def merge_projects(
    target_path: str | Path,
    source_path: str | Path,
    tool_match: str | None = "parser",
    subset_match: bool = True,
    project_settings_match: bool = False,
    sample_match: bool = True,
    conflict_suffix: str = "_1",
) -> None:
    """
    Import all data from ``source_path`` into ``target_path``.

    Parameters
    ----------
    target_path : str | Path
        Path to the target ``.dasmix`` file. Modified in place.
    source_path : str | Path
        Path to the source ``.dasmix`` file. Read-only.
    tool_match : {'name', 'parser', None}
        Strategy for matching tools between projects. Default: 'parser'.
    subset_match : bool
        Merge subsets by name if True, otherwise add all with suffix.
    project_settings_match : bool
        Overwrite target project_settings with source if True.
    sample_match : bool
        Merge samples by name if True, otherwise add all with suffix.
    conflict_suffix : str
        Suffix appended to duplicate names when not merging. Default: '_1'.
    """
    target_path = Path(target_path)
    source_path = Path(source_path)

    if not target_path.exists():
        raise FileNotFoundError(f"Target project not found: {target_path}")
    if not source_path.exists():
        raise FileNotFoundError(f"Source project not found: {source_path}")

    # ------------------------------------------------------------------
    # 1. Create a backup of the target file
    # ------------------------------------------------------------------
    backup_path = target_path.with_suffix(target_path.suffix + ".bak")
    shutil.copy2(target_path, backup_path)
    print(f"[OK] Backup created: {backup_path}")

    # ------------------------------------------------------------------
    # 2. Open target project and print "before" counts
    # ------------------------------------------------------------------
    async with Project(path=str(target_path), create_if_not_exists=False) as project:
        before = await _row_counts(project)
        _print_counts("Before merge — target", before)

        # --------------------------------------------------------------
        # 3. Run the merge (single transaction inside import_project)
        # --------------------------------------------------------------
        def on_progress(table_name: str, fraction: float) -> None:
            print(f"  ... {table_name:<25} {fraction * 100:5.1f}%")

        print("\n[Merging]")
        await project.import_project(
            source_path=source_path,
            tool_match=tool_match,
            subset_match=subset_match,
            project_settings_match=project_settings_match,
            sample_match=sample_match,
            conflict_suffix=conflict_suffix,
            status_callback=on_progress,
        )

        # --------------------------------------------------------------
        # 4. Print "after" counts and a delta summary
        # --------------------------------------------------------------
        after = await _row_counts(project)
        _print_counts("After merge — target", after)

        print("\n[Delta]")
        for table in TABLES:
            delta = after.get(table, 0) - before.get(table, 0)
            sign = "+" if delta >= 0 else ""
            print(f"  {table:<35} {sign}{delta:>9}")

        # save(checkpoint=True) is called by the context manager on exit,
        # but import_project already calls it internally — kept for safety.
        await project.save(checkpoint=True)

    print(f"\n[DONE] Merge complete. Target: {target_path}")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Merge two .dasmix projects into one."
    )
    parser.add_argument("target", help="Path to the target .dasmix file")
    parser.add_argument("source", help="Path to the source .dasmix file")
    parser.add_argument(
        "--tool-match",
        choices=["name", "parser", "none"],
        default="parser",
        help="Tool matching strategy (default: parser)",
    )
    parser.add_argument(
        "--no-subset-match",
        action="store_true",
        help="Do not merge subsets by name (add all with suffix)",
    )
    parser.add_argument(
        "--no-sample-match",
        action="store_true",
        help="Do not merge samples by name (add all with suffix)",
    )
    parser.add_argument(
        "--overwrite-settings",
        action="store_true",
        help="Overwrite target project_settings with source values",
    )
    parser.add_argument(
        "--conflict-suffix",
        default="_1",
        help="Suffix for duplicate names when not merging (default: _1)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()

    tool_match: str | None
    if args.tool_match == "none":
        tool_match = None
    else:
        tool_match = args.tool_match

    asyncio.run(
        merge_projects(
            target_path=args.target,
            source_path=args.source,
            tool_match=tool_match,
            subset_match=not args.no_subset_match,
            project_settings_match=args.overwrite_settings,
            sample_match=not args.no_sample_match,
            conflict_suffix=args.conflict_suffix,
        )
    )
```
