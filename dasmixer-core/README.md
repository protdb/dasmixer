# DASMixer Core

Core library for proteomics data project management, calculations, and data import.

## Features

- **Project management** — create, open, save `.dasmix` files (SQLite)
- **Data import** — MGF (spectra), PowerNovo2 / MaxQuant / PLGS (identifications), FASTA (proteins)
- **Calculations** — ion matching (b/y/a/c/x/z), de novo PPM correction (SeqFixer), coverage calculation
- **Peptide-to-protein mapping** (npysearch BLAST)
- **LFQ quantification** — emPAI, iBAQ, NSAF, Top3 (via semPAI)
- **Reports** — PCA, Volcano, UpSet, Coverage, Sample Summary (Plotly-based)
- **Export** — HTML, DOCX, XLSX, mzTab

## Installation

```bash
pip install dasmixer-core
```

With optional extras:

```bash
pip install "dasmixer-core[plotly]"     # Plotly + Kaleido for charts and export
pip install "dasmixer-core[proteins]"   # npysearch for BLAST-like search
pip install "dasmixer-core[all]"        # Full installation
```

## Usage

```python
from dasmixer.api.project.project import Project

async with Project(path="study.dasmix", create_if_not_exists=True) as project:
    samples = await project.get_samples()
    ...
```

Documentation: https://github.com/protdb/dasmixer