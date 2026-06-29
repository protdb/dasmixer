# DASMixer GUI

Cross-platform desktop graphical interface for comparative proteomics, built with Flet.

## Features

- **Project management** — create, open, configure projects
- **Sample management** — import spectra (MGF), identifications (PowerNovo2, MaxQuant, PLGS), proteins (FASTA)
- **Peptide analysis** — ion spectra visualization, PPM/coverage validation, cross-tool comparison
- **Protein analysis** — detection, quantification (LFQ), UniProt enrichment
- **Reports** — interactive PCA, Volcano, UpSet, Coverage, Sample Summary with HTML/DOCX/XLSX export
- **Plugins** — extend parsers and reports via `.py` files

## Installation

```bash
pip install dasmixer-gui
# or the full metapackage:
pip install dasmixer
```

## Launch

```bash
dasmixer                    # Open GUI
dasmixer path/to/project.dasmix  # Open specific project
```

## Requirements

- Python ≥ 3.11
- Linux (GTK), Windows
- For Kaleido export: Chrome (downloaded automatically on first run)

Documentation: https://github.com/protdb/dasmixer