# DASMixer

**DASMixer** is a cross-platform desktop application for integrating and comparing peptide identification data from mass spectrometry experiments. It is designed to merge de novo sequencing results with library search identifications, perform full comparative proteomics workflows, and produce publication-ready reports.

Developed at the **Laboratory of Structural Proteomics, IBMC, Moscow**.

---

## Key Features

### Data Loading
- Import spectra files in **MGF** format (MZML support planned)
- Import peptide identification results from:
  - **PowerNovo 2** (de novo sequencing)
  - **MaxQuant** (Evidence files)
  - **PLGS** (Waters library search)
- Manage multiple spectra files and identification files per project
- Assign samples to comparison groups (subsets) for differential analysis
- Multi-file batch import via file-pattern matching (CLI & GUI)

### Peptide-Level Processing
- Merge and evaluate identifications across tools
- Set thresholds: PPM error, score, intensity coverage, sequence length, peak counts
- Calculate **ion coverage** (a, b, c, x, y, z ion types) with configurable parameters:
  - Water/ammonia loss ions
  - PPM-based matching tolerance
- Automatic **best-charge and isotope-offset correction** for de novo sequences
- Select preferred identification per spectrum (by PPM or intensity coverage)
- Interactive **ion annotation plots** via Plotly + PyWebView

### Protein-Level Processing
- Map peptides to protein sequences using **FASTA files** (via npysearch BLAST-like search)
- Support for partial sequence matches (for de novo identifications)
- Filter protein identifications by peptide count, unique evidence count
- Compute **sequence coverage** per protein per sample
- **LFQ quantification**: emPAI, iBAQ, NSAF, Top3 (via semPAI library)
- UniProt data enrichment (via uniprot-meta-tool)

### Reports and Export
- Built-in reports: PCA, Volcano plot, UpSet plot, Coverage report, Tool comparison, Sample summary
- Interactive preview in PyWebView
- Export to **HTML**, **XLSX**, **DOCX** formats
- Saved plots with configurable dimensions and font sizes
- Report history stored in project file

### Plugin System
- Install custom identification parsers (`.py` or `.zip` packages)
- Install custom report modules
- Manage plugins via GUI Plugins panel.

---

## Installation

### From PyPI
```bash
pip install dasmixer
```

### Development setup (Poetry)
```bash
git clone git@github.com:protdb/dasmixer.git
cd dasmixer
poetry install
poetry run dasmixer
```

### Standalone windows executable:

**[Download latest version](https://github.com/protdb/dasmixer/releases/download/0.3.0/dasmixer0.3.0_Windows_x64.zip)**

Then you should unpack the archive and run dasmixer.exe from unpacking folder

**Requirements:** Python ≥ 3.11

---

## Usage

**[Read the instruction](docs/user/Instruction_DasMixer.pdf)**

Also check out the guide for the process [here](docs/user/workflow.md)

### Launch GUI
```bash
dasmixer                          # Start with empty screen
dasmixer project.dasmix           # Open existing project in GUI
```

## Architecture

| Layer | Technology |
|---|---|
| GUI | Flet 0.80.5 |
| CLI | Typer |
| Interactive plots | Plotly + PyWebView |
| Data processing | Pandas, NumPy |
| Proteomics | Pyteomics, Peptacular, Npysearch |
| Project storage | SQLite (aiosqlite, async) |
| Configuration | Pydantic-settings |
| Export | openpyxl, html-for-docx, Kaleido |

The application exposes three parallel interfaces:
- **GUI** — desktop application window
- **CLI** — command-line tool (`dasmixer`)
- **Python API** — importable package for scripting

---


---

## Project File Format

Projects are stored as **single SQLite files** with the `.dasmix` extension. The database contains:

- Project metadata and settings
- Spectra (MGF data as compressed NumPy arrays)
- All identification data
- Protein sequences and identification results
- LFQ quantification results
- Generated reports and saved plots

---

## Documentation

| Document | Description |
|---|---|
| [docs/project/MASTER_SPEC_NEW.md](docs/project/MASTER_SPEC_NEW.md) | Full project specification and architecture overview |
| [docs/api/](docs/api/) | API reference for the Python package |
| [docs/gui/](docs/gui/) | GUI architecture and components |
| [docs/user/](docs/user/) | User guides (workflow, identification, proteins, reports) |
| [AGENTS.md](AGENTS.md) | AI agent development guide |

---

## License

Copyright © Laboratory of Structural Proteomics, IBMC, Moscow. All rights reserved.
