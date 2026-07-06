# Export & Visualization Workflow

This document demonstrates working with an *already existing* `.dasmix` project — CSV
exports and ion coverage plot generation — using only `dasmixer-core` (no GUI).

---

## Table of Contents

1. [Overview](#overview)
2. [Step 1 — Open Existing Project](#step-1--open-existing-project)
3. [Step 2 — Find the First Sample](#step-2--find-the-first-sample)
4. [Step 3 — Export Joined Peptide Data](#step-3--export-joined-peptide-data)
5. [Step 4 — Export Protein Results](#step-4--export-protein-results)
6. [Step 5 — Find First Preferred Identification](#step-5--find-first-preferred-identification)
7. [Step 6 — Generate Ion Coverage Plot](#step-6--generate-ion-coverage-plot)
8. [Complete Script](#complete-script)

---

## Overview

The workflow accepts one input — a `.dasmix` project file — and produces two CSV exports
plus an interactive ion coverage HTML plot:

| Input | Content |
|-------|---------|
| `project_path` | An existing `.dasmix` project file |

**Output:**

| File | Content |
|------|---------|
| `<name>_joined_data.csv` | Full peptide-level view (preferred only, protein-identified) |
| `<name>_protein_results.csv` | Protein-level view with coverage, peptide counts, LFQ |
| `<name>_ion_coverage.html` | Interactive Plotly ion coverage plot (b/y ions, ± H₂O/NH₃ loss) |

The ion coverage plot is generated for the **first preferred identification** found
in the **first sample** of the project.

---

## Import Map

```python
from pathlib import Path

from dasmixer.api.project.project import Project
from dasmixer.api.calculations.spectra.ion_match import IonMatchParameters
from dasmixer.api.calculations.spectra.plot_flow import make_full_spectrum_plot
```

---

## Shared Constants

```python
ION_TYPES = ["b", "y"]
ION_TOLERANCE = 20.0  # PPM
FRAGMENT_CHARGES = [1, 2]
```

---

## Step 1 — Open Existing Project

Open a `.dasmix` file in read-write mode (no `create_if_not_exists`):

```python
project = Project(path=project_path, create_if_not_exists=False)
await project.initialize()
```

---

## Step 2 — Find the First Sample

Retrieve all samples and pick the first one from the list:

```python
samples = await project.get_samples()
if not samples:
    print("[ERROR] No samples found in the project")
    return

sample = samples[0]
print(f"[OK] Sample: {sample.name} (id={sample.id})")
```

`get_samples()` returns `list[Sample]` — each `Sample` has `.id`, `.name`,
`.subset_id`, `.additions`, `.outlier`, and computed `.spectra_files_count`.

---

## Step 3 — Export Joined Peptide Data

The `get_joined_peptide_data()` method joins spectra, identifications, and
peptide-to-protein matches into a single DataFrame:

```python
joined_data = await project.get_joined_peptide_data(
    is_preferred=True,
    protein_identified=True,
)

if not joined_data.empty:
    csv_path = project_path.parent / f"{project_path.stem}_joined_data.csv"
    joined_data.to_csv(csv_path, index=False)
    print(f"[OK] Joined peptide data: {csv_path} ({len(joined_data)} rows)")
else:
    print("[WARN] No joined peptide data found")
```

**Filters applied:**
- `is_preferred=True` — only preferred identifications per spectrum.
- `protein_identified=True` — only rows where a protein was successfully matched.

**Output DataFrame columns include:** `sample`, `subset`, `seq_no`, `scans`, `pepmass`,
`tool`, `sequence`, `canonical_sequence`, `ppm`, `matched_sequence`, `protein_id`,
`gene`, `unique_evidence`, and more.

---

## Step 4 — Export Protein Results

`get_protein_results_joined()` returns one row per protein identification result,
with pivoted columns for each LFQ method:

```python
protein_results = await project.get_protein_results_joined(limit=-1)

if not protein_results.empty:
    csv_path = project_path.parent / f"{project_path.stem}_protein_results.csv"
    protein_results.to_csv(csv_path, index=False)
    print(f"[OK] Protein results: {csv_path} ({len(protein_results)} rows)")
else:
    print("[WARN] No protein results found")
```

`limit=-1` exports all rows (default pagination is 100 rows).

**Output DataFrame columns:** `sample`, `subset`, `protein_id`, `gene`, `weight`,
`peptide_count`, `unique_evidence_count`, `coverage_percent`, `intensity_sum`,
`EmPAI`, `iBAQ`, `NSAF`, `Top3`.

---

## Step 5 — Find First Preferred Identification

Query the first preferred identification for the chosen sample,
then extract its spectrum ID:

```python
idents_df = await project.get_identifications(
    sample_id=sample.id,
    only_prefered=True,
    limit=1,
)

if idents_df.empty:
    print("[WARN] No preferred identifications found for this sample")
    return

first_ident = idents_df.iloc[0]
spectre_id = int(first_ident["spectre_id"])
sequence = first_ident["sequence"]
tool = first_ident["tool_name"]

print(f"[OK] First preferred: spectre_id={spectre_id} "
      f"tool={tool} sequence={sequence}")
```

---

## Step 6 — Generate Ion Coverage Plot

Use `get_spectrum_plot_data()` to fetch everything needed for plotting,
then call `make_full_spectrum_plot()` to produce an annotated Plotly figure:

```python
plot_data = await project.get_spectrum_plot_data(
    spectre_id, get_matched=True
)

params = IonMatchParameters(
    ions=ION_TYPES,
    tolerance=ION_TOLERANCE,
    mode="largest",
    water_loss=True,
    ammonia_loss=True,
    charges=FRAGMENT_CHARGES,
)

fig = make_full_spectrum_plot(
    params=params,
    mz=plot_data["mz"],
    intensity=plot_data["intensity"],
    charges=plot_data["charges"],
    sequences=plot_data["sequences"],
    headers=plot_data["headers"],
    spectrum_info=plot_data["spectrum_info"],
)
```

**What happens under the hood:**

1. `get_spectrum_plot_data()` decompresses the m/z and intensity arrays from the
   database, fetches all identifications linked to this spectrum, and builds
   formatted headers (tool name, sequence, PPM, score).
2. `IonMatchParameters` configures which ion types to match, PPM tolerance,
   neutral loss ions, and fragment charges — matching the built-in GUI defaults.
3. `make_full_spectrum_plot()` iterates over each identification sequence,
   calls `match_predictions()` for theoretical fragment matching, builds
   per-sequence DataFrames via `get_matches_dataframe()`, and passes them
   to `generate_spectrum_plot()` which creates a multi-panel Plotly figure:
   - **Colored bars** for matched peaks (blue = b-ions, red = y-ions, gray = unmatched).
   - **Annotated labels** above matched peaks (e.g. `b5`, `y3-H₂O`).
   - **Shared x-axis** (m/z), separate y-axes per identification.

### Save to HTML and PNG

```python
html_path = project_path.parent / f"{project_path.stem}_ion_coverage.html"
fig.write_html(str(html_path))
print(f"[OK] Ion coverage plot (HTML): {html_path}")

png_path = project_path.parent / f"{project_path.stem}_ion_coverage.png"
fig.write_image(str(png_path), width=1200, height=800, scale=2)
print(f"[OK] Ion coverage plot (PNG): {png_path}")
```

> **Note:** `fig.write_image()` requires the **Kaleido** package (`pip install kaleido`).
> The HTML export works without any extra dependencies and opens in any browser.

### Cleanup

```python
await project.close()
print("\n[DONE] Export workflow complete")
```

---

## Complete Script

```python
#!/usr/bin/env python3
"""
export_workflow.py — Export & Visualization for an existing DASMixer project.

Usage:
    python export_workflow.py <project_path>

Outputs:
    <name>_joined_data.csv       Peptide-level joined data
    <name>_protein_results.csv   Protein-level results with LFQ
    <name>_ion_coverage.html     Interactive ion coverage plot
    <name>_ion_coverage.png      Static ion coverage plot (requires Kaleido)
"""

import asyncio
from pathlib import Path

from dasmixer.api.project.project import Project
from dasmixer.api.calculations.spectra.ion_match import IonMatchParameters
from dasmixer.api.calculations.spectra.plot_flow import make_full_spectrum_plot

ION_TYPES = ["b", "y"]
ION_TOLERANCE = 20.0
FRAGMENT_CHARGES = [1, 2]


async def run_export_workflow(project_path: Path) -> None:
    project_path = Path(project_path)
    project_dir = project_path.parent
    stem = project_path.stem

    # ---------------------------------------------------------------
    # 1. Open existing project
    # ---------------------------------------------------------------
    project = Project(path=project_path, create_if_not_exists=False)
    await project.initialize()
    print(f"[OK] Project opened: {project_path}")

    # ---------------------------------------------------------------
    # 2. Find the first sample
    # ---------------------------------------------------------------
    samples = await project.get_samples()
    if not samples:
        print("[ERROR] No samples found in the project")
        await project.close()
        return

    sample = samples[0]
    print(f"[OK] Sample: {sample.name} (id={sample.id})")

    # ---------------------------------------------------------------
    # 3. Export joined peptide data
    # ---------------------------------------------------------------
    joined_data = await project.get_joined_peptide_data(
        is_preferred=True,
        protein_identified=True,
    )

    if not joined_data.empty:
        csv_path = project_dir / f"{stem}_joined_data.csv"
        joined_data.to_csv(csv_path, index=False)
        print(f"[OK] Joined peptide data: {csv_path} ({len(joined_data)} rows)")
    else:
        print("[WARN] No joined peptide data found")

    # ---------------------------------------------------------------
    # 4. Export protein results
    # ---------------------------------------------------------------
    protein_results = await project.get_protein_results_joined(limit=-1)

    if not protein_results.empty:
        csv_path = project_dir / f"{stem}_protein_results.csv"
        protein_results.to_csv(csv_path, index=False)
        print(f"[OK] Protein results: {csv_path} ({len(protein_results)} rows)")
    else:
        print("[WARN] No protein results found")

    # ---------------------------------------------------------------
    # 5. Find first preferred identification
    # ---------------------------------------------------------------
    idents_df = await project.get_identifications(
        sample_id=sample.id,
        only_prefered=True,
        limit=1,
    )

    if idents_df.empty:
        print("[WARN] No preferred identifications for this sample — "
              "skipping ion coverage plot")
        await project.close()
        return

    first_ident = idents_df.iloc[0]
    spectre_id = int(first_ident["spectre_id"])
    sequence = first_ident["sequence"]
    tool = first_ident["tool_name"]

    print(f"[OK] First preferred: spectre_id={spectre_id} "
          f"tool={tool} sequence={sequence}")

    # ---------------------------------------------------------------
    # 6. Generate ion coverage plot
    # ---------------------------------------------------------------
    plot_data = await project.get_spectrum_plot_data(
        spectre_id, get_matched=True,
    )

    params = IonMatchParameters(
        ions=ION_TYPES,
        tolerance=ION_TOLERANCE,
        mode="largest",
        water_loss=True,
        ammonia_loss=True,
        charges=FRAGMENT_CHARGES,
    )

    fig = make_full_spectrum_plot(
        params=params,
        mz=plot_data["mz"],
        intensity=plot_data["intensity"],
        charges=plot_data["charges"],
        sequences=plot_data["sequences"],
        headers=plot_data["headers"],
        spectrum_info=plot_data["spectrum_info"],
    )

    html_path = project_dir / f"{stem}_ion_coverage.html"
    fig.write_html(str(html_path))
    print(f"[OK] Ion coverage plot (HTML): {html_path}")

    png_path = project_dir / f"{stem}_ion_coverage.png"
    try:
        fig.write_image(str(png_path), width=1200, height=800, scale=2)
        print(f"[OK] Ion coverage plot (PNG): {png_path}")
    except ValueError as exc:
        print(f"[WARN] PNG export skipped (Kaleido not installed?): {exc}")

    # ---------------------------------------------------------------
    # 7. Cleanup
    # ---------------------------------------------------------------
    await project.close()
    print("\n[DONE] Export workflow complete")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python export_workflow.py <project_path>")
        sys.exit(1)

    asyncio.run(run_export_workflow(Path(sys.argv[1])))
```
