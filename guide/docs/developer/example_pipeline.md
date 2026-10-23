# Example: Running an Automated Pipeline

This guide walks through a complete, non-interactive DASMixer pipeline using only `dasmixer-core` (without the GUI). Everything is automated: provide an MGF file, a peptide identification CSV, and a FASTA file to produce a `.dasmix` project and exported CSV tables.

---

## Overview

| Input | Format | Content |
|---|---|---|
| `mgf_path` | `.mgf` | Tandem mass spectra |
| `ident_csv_path` | `.csv` | PowerNovo2 de novo identifications |
| `fasta_path` | `.fasta` | UniProt protein sequences |

**Outputs:**

- `project_path` (`.dasmix`) — complete project with spectra, identifications, ion coverage metrics, preferred identifications, BLAST protein matches, protein identifications, and LFQ values.
- `<name>_joined_data.csv` — peptide-level joined table (preferred, protein-identified).
- `<name>_protein_results.csv` — protein-level table with coverage and LFQ values (`EmPAI`, `iBAQ`, `NSAF`, `Top3`).

---

## Step-by-Step Breakdown

### 1. Create Project, Subset, Sample, and Tool

Open or create the project with the async context manager, then register the comparison group, sample, and identification tool:

```python
async with Project(path=str(project_path), create_if_not_exists=True) as project:
    subset = await project.add_subset(name="Default", details="Auto-generated subset")
    sample = await project.add_sample(name="Sample", subset_id=subset.id)
    tool = await project.add_tool(
        name="PowerNovo2",
        type="De Novo",
        parser="PowerNovo2",
        settings={"max_ppm": 20},
    )
```

### 2. Import MGF Spectra

Register the spectra file and stream batches from `MGFParser`:

```python
spectra_file_id = await project.add_spectra_file(
    sample_id=sample.id, format="MGF", path=str(mgf_path)
)

parser = MGFParser(str(mgf_path))
if not await parser.validate():
    raise ValueError(f"MGF validation failed: {mgf_path}")

async for batch_df in parser.parse_batch(batch_size=1000):
    await project.add_spectra_batch(spectra_file_id, batch_df)
```

### 3. Import Identifications

Fetch the spectrum ID lookup table (`seq_no` → `spectre_id`), parse the identification file in batches, merge on `seq_no`, and insert:

```python
id_list = await project.get_spectra_idlist(spectra_file_id, by="seq_no")
id_map = pd.DataFrame(id_list)

ident_file_id = await project.add_identification_file(
    spectra_file_id=spectra_file_id,
    tool_id=tool.id,
    file_path=str(ident_csv_path),
)

ident_parser = PowerNovo2Importer(str(ident_csv_path))
async for ident_df in ident_parser.parse_batch(batch_size=1000):
    merged = pd.merge(id_map, ident_df, on="seq_no")
    merged["tool_id"] = tool.id
    merged["ident_file_id"] = ident_file_id
    merged["is_preferred"] = False
    await project.add_identifications_batch(merged)
```

### 4. Import FASTA Database

```python
fasta_parser = FastaParser(str(fasta_path), is_uniprot=True)
if not await fasta_parser.validate():
    raise ValueError(f"FASTA validation failed: {fasta_path}")

async for batch_df in fasta_parser.parse_batch(batch_size=100):
    await project.add_proteins_batch(batch_df)
```

### 5. Calculate Ion Coverage

Use `process_identifications_batch` to compute precursor PPM, SeqFixer overrides, fragment ion coverage, quality, and LCRR:

```python
from dasmixer.api.calculations.spectra.identification_processor import (
    process_identifications_batch,
)

offset = 0
while True:
    batch = await project.get_identifications_with_spectra_batch(
        tool_id=tool.id,
        offset=offset,
        limit=1000,
        only_missing=True,
    )
    if not batch:
        break

    worker_dicts = [item.to_worker_dict() for item in batch]
    results = process_identifications_batch(
        batch=worker_dicts,
        params_dict={"ions": ["b", "y"], "tolerance": 20.0, "mode": "largest"},
        fragment_charges=[1, 2],
        target_ppm=50.0,
    )
    await project.put_identification_data_batch(results)
    offset += len(batch)

await project.save()
```

### 6. Select Preferred Identifications

```python
candidates = await project.get_idents_for_preferred(
    spectra_file_id=spectra_file_id,
    tool_id=tool.id,
    min_score=0.5,
    max_abs_ppm=20.0,
    intensity_coverage=10.0,
    spectre_peaks_count=5,
    ions_matched=3,
    top_peaks_covered=2,
    canonical_length=(7, 30),
)

if not candidates.empty:
    best_per_spectrum = candidates.loc[
        candidates.groupby("spectre_id")["score"].idxmax()
    ]
    await project.set_preferred_identifications_for_file(
        spectra_file_id, best_per_spectrum["id"].tolist()
    )
```

### 7. Map Peptides to Proteins (BLAST)

```python
await map_proteins(
    project=project,
    tool_settings={tool.id: TOOL_MAP_SETTINGS},
    ion_params=ION_PARAMS,
    fragment_charges=FRAGMENT_CHARGES,
    seqfixer_params=SEQFIXER_PARAMS,
    batch_size=5000,
)
await project.save()
```

### 8. Compute Protein Identifications and LFQ

```python
await project.clear_protein_identifications()
joined_data = await project.get_joined_peptide_data(
    is_preferred=True, protein_identified=True
)

if not joined_data.empty:
    sequences_db = await project.get_protein_db_to_search(null_sequence=True)
    async for result_df, _s_id in find_protein_identifications(
        joined_data=joined_data,
        sequences_db=sequences_db,
        min_peptides=1,
        min_uq_evidence=1,
    ):
        if not result_df.empty:
            await project.add_protein_identifications_batch(result_df)

lfq_df = await calculate_lfq(
    project=project,
    sample_id=sample.id,
    methods=["emPAI", "iBAQ"],
)
if not lfq_df.empty:
    await project.add_protein_quantifications_batch(lfq_df)
```

---

## Complete Script

```python
#!/usr/bin/env python3
"""
Non-interactive DASMixer pipeline example.
Usage:
    python pipeline.py <mgf_path> <ident_csv_path> <fasta_path> <project_path>
"""

import asyncio
import sys
from pathlib import Path
import pandas as pd

from dasmixer.api.project.project import Project
from dasmixer.api.inputs.spectra.mgf import MGFParser
from dasmixer.api.inputs.peptides.PowerNovo2 import PowerNovo2Importer
from dasmixer.api.inputs.proteins.fasta import FastaParser
from dasmixer.api.calculations.spectra.identification_processor import (
    process_identifications_batch,
)
from dasmixer.api.calculations.peptides.protein_map import map_proteins
from dasmixer.api.calculations.proteins.map_identifications import (
    find_protein_identifications,
)
from dasmixer.api.calculations.proteins.lfq import calculate_lfq

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


async def run_pipeline(
    mgf_path: str | Path,
    ident_csv_path: str | Path,
    fasta_path: str | Path,
    project_path: str | Path,
) -> None:
    mgf_path = Path(mgf_path)
    ident_csv_path = Path(ident_csv_path)
    fasta_path = Path(fasta_path)
    project_path = Path(project_path)

    async with Project(path=str(project_path), create_if_not_exists=True) as project:
        subset = await project.add_subset(name="Default", details="Auto-generated subset")
        sample = await project.add_sample(name="Sample", subset_id=subset.id)
        tool = await project.add_tool(
            name="PowerNovo2",
            type="De Novo",
            parser="PowerNovo2",
            settings={"max_ppm": 20},
        )

        # Import MGF
        spectra_file_id = await project.add_spectra_file(
            sample_id=sample.id, format="MGF", path=str(mgf_path)
        )
        parser = MGFParser(str(mgf_path))
        if not await parser.validate():
            raise ValueError(f"MGF validation failed: {mgf_path}")
        async for batch_df in parser.parse_batch(batch_size=BATCH_SIZE):
            await project.add_spectra_batch(spectra_file_id, batch_df)

        # Import Identifications
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

        # Import FASTA
        fasta_parser = FastaParser(str(fasta_path), is_uniprot=True)
        if not await fasta_parser.validate():
            raise ValueError(f"FASTA validation failed: {fasta_path}")
        async for batch_df in fasta_parser.parse_batch(batch_size=FASTA_BATCH_SIZE):
            await project.add_proteins_batch(batch_df)

        # Ion Coverage
        offset = 0
        while True:
            batch = await project.get_identifications_with_spectra_batch(
                tool_id=tool.id, offset=offset, limit=BATCH_SIZE, only_missing=True
            )
            if not batch:
                break
            worker_dicts = [item.to_worker_dict() for item in batch]
            results = process_identifications_batch(
                batch=worker_dicts,
                params_dict=ION_PARAMS,
                fragment_charges=FRAGMENT_CHARGES,
                target_ppm=SEQFIXER_PARAMS["target_ppm"],
            )
            await project.put_identification_data_batch(results)
            offset += len(batch)
        await project.save()

        # Preferred Selection
        candidates = await project.get_idents_for_preferred(
            spectra_file_id=spectra_file_id,
            tool_id=tool.id,
            **PREFERRED_THRESHOLDS,
        )
        if not candidates.empty:
            best_per_spectrum = candidates.loc[
                candidates.groupby("spectre_id")["score"].idxmax()
            ]
            await project.set_preferred_identifications_for_file(
                spectra_file_id, best_per_spectrum["id"].tolist()
            )

        # Protein Mapping
        await map_proteins(
            project=project,
            tool_settings={tool.id: TOOL_MAP_SETTINGS},
            ion_params=ION_PARAMS,
            fragment_charges=FRAGMENT_CHARGES,
            seqfixer_params=SEQFIXER_PARAMS,
            batch_size=5000,
        )
        await project.save()

        # Protein Identifications
        await project.clear_protein_identifications()
        joined_data = await project.get_joined_peptide_data(
            is_preferred=True, protein_identified=True
        )
        if not joined_data.empty:
            sequences_db = await project.get_protein_db_to_search(null_sequence=True)
            async for result_df, _s_id in find_protein_identifications(
                joined_data=joined_data,
                sequences_db=sequences_db,
                min_peptides=1,
                min_uq_evidence=1,
            ):
                if not result_df.empty:
                    await project.add_protein_identifications_batch(result_df)

        # LFQ
        lfq_df = await calculate_lfq(
            project=project, sample_id=sample.id, methods=["emPAI", "iBAQ"]
        )
        if not lfq_df.empty:
            await project.add_protein_quantifications_batch(lfq_df)

        # Export CSVs
        project_dir = project_path.parent
        joined_data = await project.get_joined_peptide_data(
            is_preferred=True, protein_identified=True
        )
        if not joined_data.empty:
            joined_data.to_csv(project_dir / f"{project_path.stem}_joined_data.csv", index=False)

        protein_results = await project.get_protein_results_joined(limit=-1)
        if not protein_results.empty:
            protein_results.to_csv(project_dir / f"{project_path.stem}_protein_results.csv", index=False)

        await project.save(checkpoint=True)


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print("Usage: python pipeline.py <mgf> <ident_csv> <fasta> <project.dasmix>")
        sys.exit(1)
    asyncio.run(run_pipeline(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]))
```
