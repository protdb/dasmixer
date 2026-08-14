# DASMixer

**DASMixer** is a cross-platform desktop application for integrating and comparing peptide identification data from mass spectrometry experiments. It merges de novo sequencing results with library search identifications, performs full comparative proteomics workflows, and produces publication-ready reports.

Developed at the **Laboratory of Structural Proteomics, IBMC, Moscow**.

---

## Key Features

### Data Loading
- Import spectra in **MGF** format
- Import peptide identifications from **PowerNovo 2**, **MaxQuant**, **PLGS**
- Manage multiple spectra files and identification files per project
- Assign samples to comparison groups (subsets) for differential analysis
- Multi-file batch import via file-pattern matching (CLI & GUI)

### Peptide-Level Processing
- Merge and evaluate identifications across tools
- Set thresholds: PPM error, score, intensity coverage, sequence length, peak counts
- Calculate **ion coverage** (a, b, c, x, y, z ion types) with water/ammonia loss ions
- Automatic **best-charge and isotope-offset correction** for de novo sequences (SeqFixer)
- Select preferred identification per spectrum (by PPM or intensity coverage)
- Interactive **ion annotation plots** via Plotly + PyWebView

### Protein-Level Processing
- Map peptides to proteins via **npysearch BLAST-like search** (FASTA)
- Support for partial sequence matches (de novo identifications)
- Compute **sequence coverage** per protein per sample
- **LFQ quantification**: emPAI, iBAQ, NSAF, Top3 (via semPAI)
- UniProt data enrichment (via uniprot-meta-tool)

### Reports and Export
- Built-in reports: PCA, Volcano, UpSet, Coverage, Tool Match, Sample Summary
- Interactive preview in PyWebView
- Export to **HTML**, **DOCX**, **XLSX** formats
- Saved plots with configurable dimensions and font sizes
- Report history stored in project file

### Plugin System
- Install custom identification parsers (`.py` or `.zip`)
- Install custom report modules
- Manage plugins via GUI Plugins panel

---

## Packages

The project is split into four PyPI packages:

| Package | Contents | PyPI |
|---|---|---|
| `dasmixer-core` | API, calculations, data import (`dasmixer.api`, `dasmixer.utils`) | `dasmixer-core` |
| `dasmixer-gui` | Flet GUI (`dasmixer.gui`) | `dasmixer-gui` |
| `dasmixer-cli` | CLI tools (`dasmixer.cli`) | `dasmixer-cli` |
| `dasmixer` | Metapackage (all three above) | `dasmixer` |

## Installation

### Windows installer:

[**Download windows installer here**](https://github.com/protdb/dasmixer/releases/download/v0.6.0/DASMixer0.6.0-setup.exe)

See latest 0.6.0 changelog [here](https://github.com/protdb/dasmixer/releases/tag/v0.6.0)

### Full install via pip

```bash
pip install dasmixer
```

### Partial install

```bash
pip install dasmixer-cli               # CLI only
pip install dasmixer-gui               # GUI only
pip install dasmixer-core              # Library only
pip install "dasmixer-core[plotly]"    # Core + Plotly/Kaleido
pip install "dasmixer-core[proteins]"  # Core + npysearch
pip install "dasmixer-core[all]"       # Core + all optional extras
```

### Development

```bash
git clone git@github.com:protdb/dasmixer.git
cd dasmixer
make dev-install
```

**Requirements:** Python ≥ 3.11

---

## Usage

### GUI

```bash
dasmixer                          # Start with empty screen
dasmixer project.dasmix           # Open existing project in GUI
```

### CLI

```bash
dasmixer-cli create path/to/project.dasmix
dasmixer-cli subset list path/to/project.dasmix
dasmixer-cli subset add path/to/project.dasmix --name "Treatment"
dasmixer-cli import mgf-file path/to/project.dasmix --sample "S1" --file spectra.mgf
dasmixer-cli import mgf-pattern path/to/project.dasmix --sample "S1" --folder ./ --pattern "*.mgf"
dasmixer-cli import ident-file path/to/project.dasmix --tool "PowerNovo2" --file data.csv
dasmixer-cli import ident-pattern path/to/project.dasmix --tool "PowerNovo2" --folder ./ --pattern "*.csv"
```

### Python API

```python
from dasmixer.api.project.project import Project

async with Project(path="study.dasmix", create_if_not_exists=True) as project:
    samples = await project.get_samples()
    ...
```

[User guide](docs/user/Instruction_DasMixer.pdf) — [Workflow guide](docs/user/workflow.md)

---

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
| Build | Poetry |

## Project File Format

Projects are stored as **single SQLite files** (`.dasmix`). The database contains metadata, spectra (compressed NumPy arrays), identifications, protein sequences, LFQ results, and generated reports.

---

## Documentation

| Document | Description |
|---|---|
| [docs/project/MASTER_SPEC_NEW.md](docs/project/MASTER_SPEC_NEW.md) | Full project specification |
| [docs/project/spec/0.5.0_REQUIREMENTS.md](docs/project/spec/0.5.0_REQUIREMENTS.md) | 0.5.0 requirements |
| [docs/project/spec/0.5.0_SPEC.md](docs/project/spec/0.5.0_SPEC.md) | 0.5.0 implementation spec |
| [docs/project/changes/v0.5.0.md](docs/project/changes/v0.5.0.md) | 0.5.0 changelog |
| [docs/user/](docs/user/) | User guides |
| [AGENTS.md](AGENTS.md) | AI agent development guide |

---

## License

Copyright © Laboratory of Structural Proteomics, IBMC, Moscow. All rights reserved.