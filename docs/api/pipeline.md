# End-to-End Pipeline Example

This document walks through a complete, non-interactive DASMixer pipeline using only
`dasmixer-core` (no GUI).  Everything is automated — provide three input files and get
LFQ results for a single sample.

---

## Table of Contents

1. [Overview](#overview)
2. [Step 1 — Create Project](#step-1--create-project)
3. [Step 2 — Add Subset, Sample, and Tool](#step-2--add-subset-sample-and-tool)
4. [Step 3 — Import MGF Spectra](#step-3--import-mgf-spectra)
5. [Step 4 — Import PowerNovo2 Identifications](#step-4--import-powernovo2-identifications)
6. [Step 5 — Import FASTA Proteins](#step-5--import-fasta-proteins)
7. [Step 6 — Calculate Ion Coverage](#step-6--calculate-ion-coverage)
8. [Step 7 — Select Preferred Identifications](#step-7--select-preferred-identifications)
9. [Step 8 — Protein Mapping (BLAST)](#step-8--protein-mapping-blast)
10. [Step 9 — Determine Protein Identifications](#step-9--determine-protein-identifications)
11. [Step 10 — Calculate LFQ (emPAI / iBAQ)](#step-10--calculate-lfq-empa--ibaq)
12. [Step 11 — Export Results to CSV](#step-11--export-results-to-csv)
13. [Complete Script](#complete-script)

---

## Overview

The pipeline accepts three files as input and produces a `.dasmix` project file with
full protein quantification results:

| Input | Format | Content |
|-------|--------|---------|
| `mgf_path` | MGF | Tandem mass spectra |
| `ident_csv_path` | CSV | PowerNovo2 de novo identifications |
| `fasta_path` | FASTA | UniProt protein sequences |

**Output:** `project_path` — a `.dasmix` file containing:
- Spectra with compressed m/z and intensity arrays
- Identifications linked to spectra
- Ion coverage metrics (PPM, intensity coverage, matched ions)
- Preferred identifications per spectrum
- Peptide-to-protein matches via BLAST
- Protein identification results per sample (peptide count, unique evidence, coverage)
- LFQ values (emPAI, iBAQ)

Two CSV files are also written alongside the project:
- `<name>_joined_data.csv` — full peptide-level view (spectra + identifications +
  protein matches, preferred only, protein-identified only).
- `<name>_protein_results.csv` — protein-level view with coverage, peptide counts,
  and LFQ values (emPAI, iBAQ, NSAF, Top3).

All parameters are hard-coded as constants matching the default GUI settings.

---

## Import Map

```python
from pathlib import Path
import pandas as pd

from dasmixer.api.project.project import Project
from dasmixer.api.inputs.spectra.mgf import MGFParser
from dasmixer.api.inputs.peptides.PowerNovo2 import PowerNovo2Importer
from dasmixer.api.inputs.proteins.fasta import FastaParser
from dasmixer.api.calculations.spectra.identification_processor import (
    process_identificatons_batch,
)
from dasmixer.api.calculations.peptides.protein_map import map_proteins
from dasmixer.api.calculations.proteins.map_identifications import (
    find_protein_identifications,
)
from dasmixer.api.calculations.proteins.lfq import calculate_lfq
```

## Shared Constants

These constants define tool configuration, ion matching parameters, and quality
thresholds — identical to the built-in GUI defaults:

```python
BATCH_SIZE = 1000
FASTA_BATCH_SIZE = 100

ION_PARAMS = {"ions": ["b", "y"], "tolerance": 20.0, "mode": "largest"}
FRAGMENT_CHARGES = [1, 2]

SEQFIXER_PARAMS = {
    "target_ppm": 50.0,
    "min_charge": 1,
    "max_charge": 4,
    "max_isotope_offset": 2,
    "force_isotope_offset": False,
}

TOOL_MAP_SETTINGS = {
    "min_protein_identity": 0.9,
    "max_ppm": 50.0,
    "ptm_list": None,
    "max_ptm": 5,
    "leucine_combinatorics": False,
    "denovo_correction": True,
    "denovo_correction_ppm": 50000.0,
    "match_correction_criteria": ["intensity_coverage"],
    "save_aa_substitutions": False,
    "min_score": 0.0,
    "min_ion_intensity_coverage": 0.0,
    "min_peptide_length": 1,
    "max_peptide_length": 999,
    "ignore_criteria": False,
}

PREFERRED_THRESHOLDS = {
    "min_score": 0.5,
    "max_abs_ppm": 20.0,
    "intensity_coverage": 10.0,
    "spectre_peaks_count": 5,
    "ions_matched": 3,
    "top_peaks_covered": 2,
    "canonical_length": (7, 30),
}

PROTEIN_IDENT_THRESHOLDS = {"min_peptides": 1, "min_uq_evidence": 1}

LFQ_METHODS = ["emPAI", "iBAQ"]
```

---

## Step 1 — Create Project

Open (or create) a `.dasmix` project via the async context manager.  The context
manager automatically calls `initialize()` on entry and `save()` + `close()` on exit.

```python
async with Project(path=str(project_path), create_if_not_exists=True) as project:
    # all steps happen inside this block
```

- `path` — a filesystem path ending with `.dasmix`.
- `create_if_not_exists=True` — creates an empty SQLite database if the file doesn't
  exist.

At this point the database has an empty schema (all `CREATE TABLE IF NOT EXISTS`
statements have been executed) and default metadata rows (`version`, `created_at`).

---

## Step 2 — Add Subset, Sample, and Tool

Every project needs at least one **subset** (comparison group), one **sample**, and one
**tool** (the identification engine that produced the input CSV).

```python
subset = await project.add_subset(name="Default", details="Auto-generated subset")
sample = await project.add_sample(name="Sample", subset_id=subset.id)
tool = await project.add_tool(
    name="PowerNovo2",
    type="De Novo",
    parser="PowerNovo2",
    settings={"max_ppm": 20},
)
```

| Method | Returns | Notes |
|--------|---------|-------|
| `add_subset` | `Subset` | Name must be unique; auto-saves |
| `add_sample` | `Sample` | Linked to subset via `subset_id`; auto-saves |
| `add_tool` | `Tool` | `type` must be `"Library"` or `"De Novo"`; `parser` is the parser class name string |

The tool's `settings` dict is serialized as JSON and stored for later reference.

---

## Step 3 — Import MGF Spectra

A two-step process: (a) register the spectra file in the database, then (b) parse and
batch-insert the spectra.

```python
spectra_file_id = await project.add_spectra_file(
    sample_id=sample.id,
    format="MGF",
    path=str(mgf_path),
)

parser = MGFParser(str(mgf_path))
if not await parser.validate():
    raise ValueError(f"MGF validation failed: {mgf_path}")

async for batch_df in parser.parse_batch(batch_size=BATCH_SIZE):
    await project.add_spectra_batch(spectra_file_id, batch_df)
```

**What happens under the hood:**

1. `add_spectra_file` inserts a row into `spectre_file` and returns its `id`.
2. `MGFParser.parse_batch` yields `pd.DataFrame` chunks with columns: `seq_no`, `title`,
   `scans`, `charge`, `rt`, `pepmass`, `mz_array`, `intensity_array`, `peaks_count`, etc.
3. `add_spectra_batch` compresses numpy arrays via `np.savez_compressed` → `bytes` BLOB
   and inserts into the `spectre` table. Each call auto-saves.

The `seq_no` column is the sequential spectrum number — it will be used in the next
step to map identifications to spectra.

---

## Step 4 — Import PowerNovo2 Identifications

PowerNovo2 CSV files are mapped to spectra using the `seq_no` column.  The import
requires merging the identification data with a spectrum ID lookup table.

```python
id_list = await project.get_spectra_idlist(spectra_file_id, by="seq_no")
id_map = pd.DataFrame(id_list)  # columns: seq_no, spectre_id

ident_file_id = await project.add_identification_file(
    spectra_file_id=spectra_file_id,
    tool_id=tool.id,
    file_path=str(ident_csv_path),
)

ident_parser = PowerNovo2Importer(str(ident_csv_path))
async for ident_df in ident_parser.parse_batch(batch_size=BATCH_SIZE):
    merged = pd.merge(id_map, ident_df, on="seq_no")
    merged["tool_id"] = tool.id
    merged["ident_file_id"] = ident_file_id
    merged["is_preferred"] = False
    await project.add_identifications_batch(merged)
```

**Column mapping performed by PowerNovo2Importer:**

| Source CSV column | Standard name | Description |
|-------------------|---------------|-------------|
| `SCAN ID` | `seq_no` | Spectrum sequential number |
| `PEPTIDE` | `sequence` | Peptide with PTM notation |
| `CANONICAL SEQ.` | `canonical_sequence` | Plain sequence |
| `PPM DIFFERENCE` | `ppm` | Mass error |
| `SCORE` | `score` | Confidence score |
| `POSITIONAL SCORES` | `positional_scores` | Per-position scores (list[float]) |

The `pd.merge` on `seq_no` resolves each identification row to the correct `spectre_id`.
`tool_id` and `ident_file_id` are constant across the entire file.  `is_preferred` is
initialized to `False` — it will be updated in step 7.

---

## Step 5 — Import FASTA Proteins

UniProt-formatted FASTA files are parsed and batch-inserted into the `protein` table.

```python
fasta_parser = FastaParser(str(fasta_path), is_uniprot=True)
if not await fasta_parser.validate():
    raise ValueError(f"FASTA validation failed: {fasta_path}")

async for batch_df in fasta_parser.parse_batch(batch_size=FASTA_BATCH_SIZE):
    await project.add_proteins_batch(batch_df)
```

`FastaParser.parse_batch` yields DataFrames with columns: `id`, `is_uniprot`,
`fasta_name`, `sequence`, `gene`.  The `id` is extracted from the UniProt header
pattern `>sp|P12345|...` and becomes the primary key of the `protein` table.

`add_proteins_batch` uses `INSERT OR REPLACE` — safe to call multiple times on the
same file.

---

## Step 6 — Calculate Ion Coverage

This step computes experimental-to-theoretical matching metrics for every
identification:

- **PPM error** — corrected via SeqFixer (PTM-aware charge/isotope optimisation).
- **Intensity coverage** — percentage of total ion current matched to theoretical
  fragments.
- **Ion matches** — count of matched b/y ions and top-10 intensity peaks.

The work is done by `process_identificatons_batch`, which uses `ProcessPoolExecutor`
internally for parallelism.

```python
offset = 0
while True:
    batch = await project.get_identifications_with_spectra_batch(
        tool_id=tool.id,
        offset=offset,
        limit=BATCH_SIZE,
        only_missing=True,  # skip already-processed rows
    )
    if not batch:
        break

    worker_dicts = [item.to_worker_dict() for item in batch]

    results = process_identificatons_batch(
        batch=worker_dicts,
        params_dict=ION_PARAMS,
        fragment_charges=FRAGMENT_CHARGES,
        target_ppm=SEQFIXER_PARAMS["target_ppm"],
    )

    await project.put_identification_data_batch(results)
    offset += len(batch)

await project.save()
```

**Key details:**

- `get_identifications_with_spectra_batch` returns `list[IdentificationWithSpectrum]`.
  Each object contains both the identification metadata and the decompressed spectrum
  arrays (`mz_array`, `intensity_array`).
- `to_worker_dict()` produces a plain dict suitable for multiprocess serialisation.
- `only_missing=True` fetches only identifications where `intensity_coverage IS NULL` —
  safe to resume an interrupted run.
- `put_identification_data_batch` updates `ppm`, `theor_mass`, `override_charge`,
  `intensity_coverage`, `ions_matched`, `ion_match_type`, `top_peaks_covered`, and
  `isotope_offset` for each identification.
- The final `await project.save()` is required because `put_identification_data_batch`
  does **not** auto-save (by design, for batch efficiency).

---

## Step 7 — Select Preferred Identifications

For each spectrum, one identification is marked as **preferred**.  Selection is based
on the highest score among candidates that pass all quality thresholds.

```python
candidates = await project.get_idents_for_preferred(
    spectra_file_id=spectra_file_id,
    tool_id=tool.id,
    **PREFERRED_THRESHOLDS,  # min_score, max_abs_ppm, intensity_coverage, etc.
)

if not candidates.empty:
    best_per_spectrum = candidates.loc[
        candidates.groupby("spectre_id")["score"].idxmax()
    ]
    preferred_ids = best_per_spectrum["id"].tolist()
    await project.set_preferred_identifications_for_file(
        spectra_file_id, preferred_ids
    )
```

`set_preferred_identifications_for_file` performs two operations:
1. Resets `is_preferred = 0` for all identifications in the file.
2. Sets `is_preferred = 1` for the selected IDs.

Only preferred identifications participate in protein mapping and LFQ calculation.

---

## Step 8 — Protein Mapping (BLAST)

Peptide identifications are searched against the protein database using
[npysearch](https://github.com/nickdelgrosso/npysearch) (BLAST-like search on GPU or
NumPy backend).

```python
async for matches_df, count, _tid in map_proteins(
    project=project,
    tool_settings={tool.id: TOOL_MAP_SETTINGS},
    ion_params=ION_PARAMS,
    fragment_charges=FRAGMENT_CHARGES,
    seqfixer_params=SEQFIXER_PARAMS,
    batch_size=5000,
):
    if not matches_df.empty:
        await project.add_peptide_matches_batch(matches_df)

await project.save()
```

**What `map_proteins` does per batch:**

1. Fetches identifications from the database (filtered by `tool_id` and `max_ppm`).
2. Builds a BLAST query from canonical sequences (with optional leucine/I combinatorics).
3. Runs `npy.blast()` against the protein database.
4. For **identity == 1.0** (exact match): copies PPM and ion-coverage metrics directly
   from the identification.
5. For **identity < 1.0** (partial match): recalculates PPM and ion coverage using
   SeqFixer + `match_predictions`, and applies **match correction criteria** to
   decide whether to accept.
6. Yields a `pd.DataFrame` ready for `add_peptide_matches_batch`.

The final `await project.save()` commits the accumulated peptide matches.

---

## Step 9 — Determine Protein Identifications

Peptide matches are aggregated per protein, per sample.  Each protein is considered
**identified** if it meets the minimum peptide and unique-evidence thresholds.

```python
await project.clear_protein_identifications()

joined_data = await project.get_joined_peptide_data(
    is_preferred=True,
    protein_identified=True,
)

if not joined_data.empty:
    sequences_db = await project.get_protein_db_to_search(null_sequence=True)

    async for result_df, _sample_id in find_protein_identifications(
        joined_data=joined_data,
        sequences_db=sequences_db,
        min_peptides=1,
        min_uq_evidence=1,
    ):
        if not result_df.empty:
            await project.add_protein_identifications_batch(result_df)
```

**For each protein, the following metrics are computed:**

| Column | Description |
|--------|-------------|
| `protein_id` | UniProt accession |
| `sample_id` | Sample FK |
| `peptide_count` | Number of distinct matched peptides |
| `uq_evidence_count` | Number of unique peptides (matching only this protein) |
| `coverage` | Sequence coverage percentage (matched AA / total length × 100) |
| `intensity_sum` | Sum of peptide intensities |

`clear_protein_identifications()` deletes all previous results — safe for a fresh
run.  For per-sample recalculation use `clear_protein_identifications_for_sample()`.

---

## Step 10 — Calculate LFQ (emPAI / iBAQ)

Label-free quantification uses the **semPAI** library internally.  It computes the
theoretical observable peptide count (via in-silico digestion) and normalises the
experimental peptide intensities.

```python
lfq_df = await calculate_lfq(
    project=project,
    sample_id=sample.id,
    methods=["emPAI", "iBAQ"],
)

if not lfq_df.empty:
    await project.add_protein_quantifications_batch(lfq_df)
```

**Methods available:**

| Method | Description |
|--------|-------------|
| `emPAI` | Exponentially Modified Protein Abundance Index (`10^(peptide_count / observable) − 1`) |
| `iBAQ` | Intensity-Based Absolute Quantification (summed intensity / observable peptides) |
| `NSAF` | Normalized Spectral Abundance Factor |
| `Top3` | Mean intensity of top-3 peptides |

The method internally:
1. Reads `protein_identification_result` rows for the sample.
2. Joins with preferred peptide matches to get matched sequences and intensities.
3. Builds `Protein` objects with sequences, peptide lists, and intensities.
4. Creates a `ProteomicSample` and calls `get_results()`.
5. Pivots the results to long format: `(protein_identification_id, algorithm, rel_value)`.

---

## Step 11 — Export Results to CSV

After the pipeline completes, two CSV files are written alongside the project file:

### Joined Peptide Data

The **Joined Data** view from the GUI, exported via `get_joined_peptide_data()`.  Each
row is one peptide identification matched to its spectrum and (if mapped) its protein.

```python
project_dir = project_path.parent
joined_csv = project_dir / f"{project_path.stem}_joined_data.csv"

joined_data = await project.get_joined_peptide_data(
    is_preferred=True,
    protein_identified=True,
)
if not joined_data.empty:
    joined_data.to_csv(joined_csv, index=False)
```

**Columns:** `sample`, `subset`, `sample_id`, `subset_id`, `seq_no`, `scans`, `charge`,
`rt`, `pepmass`, `intensity`, `tool`, `tool_id`, `identification_id`, `sequence`,
`canonical_sequence`, `ppm`, `score`, `is_preferred`, `ions_matched`, `ion_match_type`,
`top_peaks_covered`, `intensity_coverage`, `matched_sequence`, `matched_ppm`,
`protein_id`, `identity`, `unique_evidence`, `gene`, `matched_peaks`,
`matched_top_peaks`, `matched_ion_type`, `matched_sequence_modified`, `substitution`.

### Protein Results

The final protein-level view, exported via `get_protein_results_joined()`.  Each row is
one protein identified in one sample, with LFQ values.

```python
protein_csv = project_dir / f"{project_path.stem}_protein_results.csv"

protein_results = await project.get_protein_results_joined(limit=-1)
if not protein_results.empty:
    protein_results.to_csv(protein_csv, index=False)
```

**Columns:** `sample`, `subset`, `protein_id`, `gene`, `weight` (Da), `peptide_count`,
`unique_evidence_count`, `coverage_percent`, `intensity_sum`, `EmPAI`, `iBAQ`, `NSAF`,
`Top3`.

Use `limit=-1` to export all rows (no pagination).

---

## Complete Script

The function `run_pipeline(mgf_path, ident_csv_path, fasta_path, project_path)`
executes all steps sequentially, exports two CSVs alongside the project, and saves the
final `.dasmix` file with a WAL checkpoint for portability.

**Command-line usage:**

```bash
python pipeline.py data.mgf pn2_results.csv uniprot.fasta output.dasmix
```

**As a library:**

```python
import asyncio
from pipeline import run_pipeline

asyncio.run(run_pipeline(
    mgf_path="data.mgf",
    ident_csv_path="pn2_results.csv",
    fasta_path="uniprot.fasta",
    project_path="output.dasmix",
))
```

---

```python
#!/usr/bin/env python3
"""
Non-interactive DASMixer pipeline.

Strictly automated: project → subset → sample → MGF → PowerNovo2 idents → FASTA
→ ion coverage → preferred → protein mapping → protein identifications → LFQ.
"""

import asyncio
from pathlib import Path

import pandas as pd

from dasmixer.api.project.project import Project
from dasmixer.api.inputs.spectra.mgf import MGFParser
from dasmixer.api.inputs.peptides.PowerNovo2 import PowerNovo2Importer
from dasmixer.api.inputs.proteins.fasta import FastaParser
from dasmixer.api.calculations.spectra.identification_processor import (
    process_identificatons_batch,
)
from dasmixer.api.calculations.peptides.protein_map import map_proteins
from dasmixer.api.calculations.proteins.map_identifications import (
    find_protein_identifications,
)
from dasmixer.api.calculations.proteins.lfq import calculate_lfq

# ---------------------------------------------------------------------------
# Constants — matching default GUI settings
# ---------------------------------------------------------------------------
TOOL_NAME = "PowerNovo2"
TOOL_TYPE = "De Novo"
TOOL_PARSER = "PowerNovo2"
SUBSET_NAME = "Default"
SAMPLE_NAME = "Sample"
BATCH_SIZE = 1000
FASTA_BATCH_SIZE = 100

ION_PARAMS = {"ions": ["b", "y"], "tolerance": 20.0, "mode": "largest"}
FRAGMENT_CHARGES = [1, 2]
SEQFIXER_PARAMS = {
    "target_ppm": 50.0,
    "min_charge": 1,
    "max_charge": 4,
    "max_isotope_offset": 2,
    "force_isotope_offset": False,
}
TOOL_MAP_SETTINGS = {
    "min_protein_identity": 0.9,
    "max_ppm": 50.0,
    "ptm_list": None,
    "max_ptm": 5,
    "leucine_combinatorics": False,
    "denovo_correction": True,
    "denovo_correction_ppm": 50000.0,
    "match_correction_criteria": ["intensity_coverage"],
    "save_aa_substitutions": False,
    "min_score": 0.0,
    "min_ion_intensity_coverage": 0.0,
    "min_peptide_length": 1,
    "max_peptide_length": 999,
    "ignore_criteria": False,
}
PREFERRED_THRESHOLDS = {
    "min_score": 0.5,
    "max_abs_ppm": 20.0,
    "intensity_coverage": 10.0,
    "spectre_peaks_count": 5,
    "ions_matched": 3,
    "top_peaks_covered": 2,
    "canonical_length": (7, 30),
}
PROTEIN_IDENT_THRESHOLDS = {"min_peptides": 1, "min_uq_evidence": 1}
LFQ_METHODS = ["emPAI", "iBAQ"]


async def run_pipeline(
    mgf_path: str | Path,
    ident_csv_path: str | Path,
    fasta_path: str | Path,
    project_path: str | Path,
) -> None:
    """
    Execute the full DASMixer pipeline for a single sample.

    Parameters
    ----------
    mgf_path : str | Path
        Path to the MGF spectrum file.
    ident_csv_path : str | Path
        Path to the PowerNovo2 CSV identification file.
    fasta_path : str | Path
        Path to the FASTA protein database (is_uniprot=True).
    project_path : str | Path
        Path where the ``.dasmix`` project file will be saved.
    """
    mgf_path = Path(mgf_path)
    ident_csv_path = Path(ident_csv_path)
    fasta_path = Path(fasta_path)
    project_path = Path(project_path)

    # -------------------------------------------------------------------
    # 1. Create / open project
    # -------------------------------------------------------------------
    async with Project(path=str(project_path), create_if_not_exists=True) as project:

        # ---------------------------------------------------------------
        # 2. Subset
        # ---------------------------------------------------------------
        subset = await project.add_subset(
            name=SUBSET_NAME, details="Auto-generated subset"
        )

        # ---------------------------------------------------------------
        # 3. Sample
        # ---------------------------------------------------------------
        sample = await project.add_sample(name=SAMPLE_NAME, subset_id=subset.id)

        # ---------------------------------------------------------------
        # 4. Tool
        # ---------------------------------------------------------------
        tool = await project.add_tool(
            name=TOOL_NAME,
            type=TOOL_TYPE,
            parser=TOOL_PARSER,
            settings={"max_ppm": 20},
        )

        # ---------------------------------------------------------------
        # 5. Import MGF spectra
        # ---------------------------------------------------------------
        spectra_file_id = await project.add_spectra_file(
            sample_id=sample.id, format="MGF", path=str(mgf_path)
        )
        parser = MGFParser(str(mgf_path))
        if not await parser.validate():
            raise ValueError(f"MGF validation failed: {mgf_path}")
        async for batch_df in parser.parse_batch(batch_size=BATCH_SIZE):
            await project.add_spectra_batch(spectra_file_id, batch_df)
        print(f"[OK] Spectra imported: {mgf_path}")

        # ---------------------------------------------------------------
        # 6. Import PowerNovo2 identifications
        # ---------------------------------------------------------------
        id_list = await project.get_spectra_idlist(spectra_file_id, by="seq_no")
        id_map = pd.DataFrame(id_list)

        ident_file_id = await project.add_identification_file(
            spectra_file_id=spectra_file_id,
            tool_id=tool.id,
            file_path=str(ident_csv_path),
        )
        ident_parser = PowerNovo2Importer(str(ident_csv_path))
        async for ident_df in ident_parser.parse_batch(batch_size=BATCH_SIZE):
            merged = pd.merge(id_map, ident_df, on="seq_no")
            merged["tool_id"] = tool.id
            merged["ident_file_id"] = ident_file_id
            merged["is_preferred"] = False
            await project.add_identifications_batch(merged)
        print(f"[OK] Identifications imported: {ident_csv_path}")

        # ---------------------------------------------------------------
        # 7. Import FASTA proteins
        # ---------------------------------------------------------------
        fasta_parser = FastaParser(str(fasta_path), is_uniprot=True)
        if not await fasta_parser.validate():
            raise ValueError(f"FASTA validation failed: {fasta_path}")
        async for batch_df in fasta_parser.parse_batch(batch_size=FASTA_BATCH_SIZE):
            await project.add_proteins_batch(batch_df)
        print(f"[OK] Proteins imported: {fasta_path}")

        # ---------------------------------------------------------------
        # 8. Calculate ion coverage
        # ---------------------------------------------------------------
        offset = 0
        while True:
            batch = await project.get_identifications_with_spectra_batch(
                tool_id=tool.id,
                offset=offset,
                limit=BATCH_SIZE,
                only_missing=True,
            )
            if not batch:
                break
            worker_dicts = [item.to_worker_dict() for item in batch]
            results = process_identificatons_batch(
                batch=worker_dicts,
                params_dict=ION_PARAMS,
                fragment_charges=FRAGMENT_CHARGES,
                target_ppm=SEQFIXER_PARAMS["target_ppm"],
            )
            await project.put_identification_data_batch(results)
            offset += len(batch)
        await project.save()
        print(f"[OK] Ion coverage calculated ({offset} identifications)")

        # ---------------------------------------------------------------
        # 9. Select preferred identifications
        # ---------------------------------------------------------------
        candidates = await project.get_idents_for_preferred(
            spectra_file_id=spectra_file_id,
            tool_id=tool.id,
            **PREFERRED_THRESHOLDS,
        )
        if not candidates.empty:
            best_per_spectrum = candidates.loc[
                candidates.groupby("spectre_id")["score"].idxmax()
            ]
            preferred_ids = best_per_spectrum["id"].tolist()
            await project.set_preferred_identifications_for_file(
                spectra_file_id, preferred_ids
            )
        print("[OK] Preferred identifications set")

        # ---------------------------------------------------------------
        # 10. Protein mapping (BLAST)
        # ---------------------------------------------------------------
        async for matches_df, count, _tid in map_proteins(
            project=project,
            tool_settings={tool.id: TOOL_MAP_SETTINGS},
            ion_params=ION_PARAMS,
            fragment_charges=FRAGMENT_CHARGES,
            seqfixer_params=SEQFIXER_PARAMS,
            batch_size=5000,
        ):
            if not matches_df.empty:
                await project.add_peptide_matches_batch(matches_df)
        await project.save()
        print("[OK] Protein mapping completed")

        # ---------------------------------------------------------------
        # 11. Determine protein identifications
        # ---------------------------------------------------------------
        await project.clear_protein_identifications()
        joined_data = await project.get_joined_peptide_data(
            is_preferred=True,
            protein_identified=True,
        )
        if not joined_data.empty:
            sequences_db = await project.get_protein_db_to_search(null_sequence=True)
            async for result_df, _s_id in find_protein_identifications(
                joined_data=joined_data,
                sequences_db=sequences_db,
                **PROTEIN_IDENT_THRESHOLDS,
            ):
                if not result_df.empty:
                    await project.add_protein_identifications_batch(result_df)
        print("[OK] Protein identifications determined")

        # ---------------------------------------------------------------
        # 12. Calculate LFQ (emPAI / iBAQ)
        # ---------------------------------------------------------------
        lfq_df = await calculate_lfq(
            project=project,
            sample_id=sample.id,
            methods=LFQ_METHODS,
        )
        if not lfq_df.empty:
            await project.add_protein_quantifications_batch(lfq_df)
        print("[OK] LFQ calculated")

        # ---------------------------------------------------------------
        # 13. Export joined data to CSV
        # ---------------------------------------------------------------
        project_dir = project_path.parent

        joined_csv = project_dir / f"{project_path.stem}_joined_data.csv"
        joined_data = await project.get_joined_peptide_data(
            is_preferred=True,
            protein_identified=True,
        )
        if not joined_data.empty:
            joined_data.to_csv(joined_csv, index=False)
            print(f"[OK] Joined peptide data exported: {joined_csv}")

        protein_csv = project_dir / f"{project_path.stem}_protein_results.csv"
        protein_results = await project.get_protein_results_joined(limit=-1)
        if not protein_results.empty:
            protein_results.to_csv(protein_csv, index=False)
            print(f"[OK] Protein results exported: {protein_csv}")

        # ---------------------------------------------------------------
        # 14. Final save with WAL checkpoint
        # ---------------------------------------------------------------
        await project.save(checkpoint=True)
        print(f"\n[DONE] Pipeline complete. Project saved to {project_path}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 5:
        print(
            "Usage: python pipeline.py <mgf_path> <ident_csv_path>"
            " <fasta_path> <project_path>"
        )
        sys.exit(1)

    asyncio.run(
        run_pipeline(
            mgf_path=sys.argv[1],
            ident_csv_path=sys.argv[2],
            fasta_path=sys.argv[3],
            project_path=sys.argv[4],
        )
    )
```
