# Command-Line Interface (CLI)

In addition to the graphical desktop application, DASMixer provides a full-featured command-line interface: **`dasmixer-cli`**.

The CLI allows you to automate project creation, batch imports, peptide and protein calculations, project merging, and database maintenance in shell scripts, HPC cluster jobs, or Snakemake/Nextflow workflows without requiring a graphical display.

---

## Overview and Installation

If you installed the full `dasmixer` package (or the Windows installer), `dasmixer-cli` is already available in your environment. On headless Linux servers where GUI libraries are not needed, you can install the lightweight CLI package alone:

```bash
pip install dasmixer-cli
```

Check the installed version and view available subcommands at any time:

```bash
dasmixer-cli --version
dasmixer-cli --help
```

### Command Structure

`dasmixer-cli` commands are grouped by domain:

| Command / Group | Purpose |
|---|---|
| `create` / `configure` | Create a new `.dasmix` project or view/modify project settings |
| `subset` | Add, list, or delete comparison groups (subsets) |
| `tool` | Add, list, or configure identification tools |
| `import` | Import MGF spectra, identification files, FASTA databases, MaxQuant projects, or PRIDE datasets |
| `calculate` | Run ion coverage, preferred selection, protein mapping, protein inference, and LFQ |
| `import-project` | Merge another `.dasmix` project into a target project |
| `checkpoint` / `vacuum` | Flush SQLite WAL journals and compact project file size |
| `update-ptm-list` | Initialize or update the PTM configuration CSV files |

---

## 1. Creating and Configuring a Project

### Create a new project

Creates a new `.dasmix` file initialized with a default `Control` comparison group:

```bash
dasmixer-cli create /path/to/study.dasmix
```

### View or modify project settings

List all stored settings in `project_settings`:

```bash
dasmixer-cli configure /path/to/study.dasmix --list
```

Set a specific project setting key:

```bash
dasmixer-cli configure /path/to/study.dasmix --key ion_ppm_threshold --value 15
```

---

## 2. Managing Comparison Groups (`subset`)

```bash
# Add a new comparison group
dasmixer-cli subset add /path/to/study.dasmix \
    --name "Treatment" \
    --details "Drug-treated cohort" \
    --color "#EF4444"

# List all comparison groups
dasmixer-cli subset list /path/to/study.dasmix

# Delete an empty comparison group
dasmixer-cli subset delete /path/to/study.dasmix --name "OldGroup"
```

---

## 3. Managing Identification Tools (`tool`)

Register each search engine or *de novo* tool before importing its identification files:

```bash
# Add a De Novo tool
dasmixer-cli tool add /path/to/study.dasmix \
    --name "PowerNovo2" \
    --parser "PowerNovo2" \
    --type "De Novo" \
    --color "#10B981"

# Add a Library search tool
dasmixer-cli tool add /path/to/study.dasmix \
    --name "MaxQuant" \
    --parser "MaxQuant" \
    --type "Library"

# List registered tools
dasmixer-cli tool list /path/to/study.dasmix

# View tool-specific settings (thresholds, PTM rules, etc.)
dasmixer-cli tool param-list /path/to/study.dasmix --name "PowerNovo2"

# Update a tool setting
dasmixer-cli tool configure /path/to/study.dasmix \
    --name "PowerNovo2" \
    --key max_ppm \
    --value 30
```

Supported built-in `--parser` names for identifications:
`PowerNovo2`, `MaxQuant`, `PLGS`, `PeptideShaker XLS`, `mzTab`, `CasaNovo`, `Pi-PrimeNovo`.

---

## 4. Importing Data (`import`)

### Import MGF Spectra

Import a single MGF file into a sample:

```bash
dasmixer-cli import mgf-file /path/to/study.dasmix \
    --file /data/spectra/S01.mgf \
    --sample-id "S01" \
    --group "Control" \
    --parser "MGF" \
    --on-duplicates skip
```

Batch-import MGF files from a directory using glob and `{id}` patterns:

```bash
dasmixer-cli import mgf-pattern /path/to/study.dasmix \
    --folder /data/spectra/ \
    --pattern "*.mgf" \
    --id-pattern "{}_{id}_DDA.mgf" \
    --group "Treatment" \
    --parser "MGF"
```

### Import Identifications

Import a single identification file for a sample and tool:

```bash
dasmixer-cli import ident-file /path/to/study.dasmix \
    --file /data/pn2/S01_denovo.csv \
    --sample-id "S01" \
    --tool "PowerNovo2" \
    --parser "PowerNovo2"
```

Batch-import identification files by pattern:

```bash
dasmixer-cli import ident-pattern /path/to/study.dasmix \
    --folder /data/pn2/ \
    --pattern "*_denovo.csv" \
    --id-pattern "{id}_denovo.csv" \
    --tool "PowerNovo2" \
    --parser "PowerNovo2"
```

If the identification files contain protein IDs (e.g., `PLGS` or `MaxQuant`), add `--collect-proteins` (and `--is-uniprot-proteins` if accessions are UniProt IDs).

### Import a FASTA Protein Database

```bash
dasmixer-cli import fasta /path/to/study.dasmix \
    --file /data/uniprot_human.fasta
```

### Import a MaxQuant or PRIDE Dataset

Full one-command imports are also available for MaxQuant (`mqpar.xml`) and PRIDE (`PXD...`):

```bash
# MaxQuant project import
dasmixer-cli import maxquant /path/to/study.dasmix /data/mq/mqpar.xml \
    --subset-name "MaxQuant_Cohort"

# PRIDE dataset import
dasmixer-cli import pride /path/to/study.dasmix PXD012345 \
    --subset-name "PRIDE_Cohort"
```

See [MaxQuant Import](MaxQuant.md#cli-import) and [PRIDE Dataset Import](pride_import.md#cli-import) for all available flags.

---

## 5. Running Calculations (`calculate`)

You can run the entire peptide pipeline in one command or execute each calculation stage individually.

### Full Peptide Pipeline (`calculate peptides`)

Runs ion coverage calculation, BLAST protein mapping, and preferred identification selection sequentially:

```bash
dasmixer-cli calculate peptides /path/to/study.dasmix \
    --fasta /data/uniprot_human.fasta \
    --criterion intensity
```

### Individual Calculation Steps

```bash
# 1. Calculate ion coverage and PPM refinement
dasmixer-cli calculate ion-coverage /path/to/study.dasmix \
    --tolerance 20.0 \
    --ions "b,y"

# 2. Map peptides to proteins (BLAST via npysearch)
dasmixer-cli calculate peptide-match /path/to/study.dasmix \
    --fasta /data/uniprot_human.fasta

# 3. Select preferred identifications per spectrum
dasmixer-cli calculate preferred /path/to/study.dasmix \
    --criterion intensity

# 4. Compute protein identifications per sample
dasmixer-cli calculate protein-idents /path/to/study.dasmix \
    --min-peptides 2 \
    --min-unique 1

# 5. Calculate Label-Free Quantification (LFQ)
dasmixer-cli calculate lfq /path/to/study.dasmix \
    --empai --ibaq --nsaf --top3 \
    --enzyme trypsin
```

All `calculate` subcommands also accept `--sample-id <ID>` if you want to restrict computation to a single sample.

---

## 6. Merging Projects (`import-project`)

Combines all data from a `SOURCE` `.dasmix` project into a `TARGET` `.dasmix` project in a single atomic transaction:

```bash
dasmixer-cli import-project /path/to/target.dasmix /path/to/source.dasmix \
    --tool-match parser \
    --conflict-suffix "_1"
```

### Merge Options

| Option | Default | Description |
|---|---|---|
| `--tool-match` | `parser` | How to match tools between projects: `parser` (match by parser type), `name` (match by display name), or `none` (keep separate with suffix) |
| `--no-subset-match` | off | Do not merge comparison groups with identical names; insert source groups with `--conflict-suffix` |
| `--no-sample-match` | off | Do not merge samples with identical names; insert source samples with `--conflict-suffix` |
| `--update-settings` | off | Overwrite target `project_settings` with values from the source project |
| `--conflict-suffix` | `"_1"` | Suffix appended to duplicate names when not merging |

---

## 7. Database Maintenance (`checkpoint`, `vacuum`, `update-ptm-list`)

Because DASMixer projects use SQLite in Write-Ahead Logging (**WAL**) mode, temporary `.dasmix-wal` and `.dasmix-shm` files may exist alongside an open project.

### Flush WAL journal (`checkpoint`)

Before copying or sharing a project file that may not have been cleanly closed, flush all WAL changes into the main `.dasmix` file:

```bash
dasmixer-cli checkpoint /path/to/study.dasmix
```

### Compact project file (`vacuum`)

If you have deleted large numbers of spectra, samples, or identifications, run `vacuum` to reclaim unused disk space inside the `.dasmix` database:

```bash
dasmixer-cli vacuum /path/to/study.dasmix
```

### Refresh PTM configuration files (`update-ptm-list`)

Regenerates or updates the user PTM configuration CSV files (`all_ptm_config.csv` and `import_ptm_renames.csv` — see [PTM Configuration](ptm_configuration.md)):

```bash
dasmixer-cli update-ptm-list
```
