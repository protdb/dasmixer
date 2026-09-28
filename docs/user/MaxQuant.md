# MaxQuant Import

DASMixer can import full MaxQuant search results directly into an existing project.
The importer reads `mqpar.xml` (configuration), `msms.txt` / `msmsScans.txt` (identification
metadata), and `.apl` peak-list files, then converts them into regular spectra and
identifications inside your `.dasmix` project.

---

## Prerequisites

Your MaxQuant output must include:

| File / folder | Expected location (relative to `mqpar.xml`) | Purpose |
|---|---|---|
| `mqpar.xml` | anywhere (you select it) | Paths and RAW file list |
| `msms.txt` | `<txt_folder>/msms.txt` | Peptide identifications |
| `msmsScans.txt` | `<txt_folder>/msmsScans.txt` | Scan metadata |
| `{raw_name}/p0/*.apl` | `<raw_parent>/{raw_name}/p0/*.apl` | Peak lists (one per sample) |
| `.fasta` | `<fasta_file>` (optional) | Protein sequences |

`<txt_folder>`, `<raw_parent>`, and `<fasta_file>` are parsed automatically from
`mqpar.xml`. You can override them in the GUI or via CLI options.

> **Note:** only per-sample `.apl` files (`<raw_name>/p0/*.apl`) are supported.
> `combined/andromeda/*.apl` files (mixed spectra without sample assignment) are
> not imported.

If `mqpar.xml` references multiple RAW-file parent directories, only the **first**
one is used. Put all RAW samples in a single directory for best results.

---

## GUI Import

### 1. Open the dialog

Switch to the **Samples** tab. You will see a new **Import From MaxQuant** section
next to the existing Import Spectra block. Click **Import From MaxQuant…**.

### 2. Select mqpar.xml

Click **Browse**, choose your `mqpar.xml` file, then click **Parse**. The
importer will extract all paths and RAW-file names from the XML.

### 3. Configure paths

The dialog shows three path fields with status icons:

- **RAW files path** — folder containing `{raw_name}/p0/` subdirectories.
- **Custom TXT folder** — folder containing `msms.txt` and `msmsScans.txt`.
- **FASTA file** — protein database (optional).

Click the **folder icon** next to each field to browse. The icon turns green
when the path is valid, red otherwise.

The **Import** button stays disabled until all validations pass.

### 4. Choose options

| Option | Default | Description |
|---|---|---|
| Tool name | `MaxQuant` | Name of the identification tool in your project |
| Subset name | `MaxQuant Import` | Comparison group for imported samples |
| Import proteins from FASTA file | on | If enabled, protein sequences are imported |
| Sequences are in UniProt format | on | Parses UniProt-style headers `>sp\|...\|...` |
| Delete temporary files after import | on | Removes intermediate MGF/CSV files |
| Skip contaminant identifications | on | Filters out `Potential contaminant` rows |
| On duplicates | `Skip` | What to do if a file was already imported |

Decoy identifications (`Decoy = +`) are **always** excluded, regardless of the
contaminant checkbox.

### 5. Select RAW files

The list at the bottom shows every RAW file from `mqpar.xml`. Uncheck any
samples you want to skip. Use **Select All** / **Deselect All** for quick
control.

### 6. Run import

Click **Import**. The dialog switches to a progress screen showing:

```
Processing CRC_Rep1 (1/10)
████████░░░░░░░░░░░░  10%
Stage: spectra
```

Import cannot be cancelled once started (this ensures data consistency).

When finished, the dialog closes and a green snack-bar summarizes the results:

```
MaxQuant import complete: 10 sample(s), 50 000 spectra, 12 340 identifications
```

The new samples, files, and identifications appear immediately in the Samples
tab and are ready for downstream analysis.

---

## CLI Import

```bash
dasmixer-cli import maxquant PROJECT_PATH MQPAR_PATH [OPTIONS]
```

If `PROJECT_PATH` does not exist, a new project is created automatically.

### Required arguments

| Argument | Description |
|---|---|
| `PROJECT_PATH` | Path to `.dasmix` file (created if missing) |
| `MQPAR_PATH` | Path to `mqpar.xml` |

### Options

| Option | Default | Description |
|---|---|---|
| `--fasta-path` | from `mqpar.xml` | Override FASTA file path |
| `--raw-path` | from `mqpar.xml` | Override RAW files parent directory |
| `--txt-path` | from `mqpar.xml` | Override txt results folder path |
| `--tool-name` | `MaxQuant` | Tool name |
| `--subset-name` | `MaxQuant Import` | Subset (group) name |
| `--keep-contaminants` | off | Keep `Potential contaminant` identifications |
| `--import-fasta` / `--no-import-fasta` | `--import-fasta` | Import proteins from FASTA |
| `--fasta-uniprot` / `--fasta-generic` | `--fasta-uniprot` | FASTA headers are UniProt-formatted |
| `--delete-temporary-files` / `--keep-temporary-files` | `--delete-temporary-files` | Remove intermediate MGF/CSV files |
| `--on-duplicates` | `skip` | `skip` \| `reload` \| `add_as_new` |

### Example

```bash
dasmixer-cli import maxquant /data/my_project.dasmix /data/mq/mqpar.xml \
    --tool-name MaxQuant --subset-name "MaxQuant Import"
```

CLI output shows per-stage progress:

```
  [metadata] Reading metadata...
  [converting] Converting CRC_Rep1.HCD.FTMS.peak.apl...
  [converting] Converting CRC_Rep2.HCD.FTMS.peak.apl...
  [creating_tool_subset] Setting up subset and tool...
  [spectra] Processing CRC_Rep1 (1/10)
  [spectra] Processing CRC_Rep2 (2/10)
  ...
  [done] Saving project...
  ...
Import complete: 10 sample(s), 50000 spectra, 12340 identifications
```

---

## What Happens During Import

1. **Read metadata** — `msms.txt` and `msmsScans.txt` are loaded into memory.
2. **Convert APL → MGF** — each `.apl` file is parsed and written as a
   temporary `.mgf` file enriched with sequence, charge, and retention-time
   annotations from the metadata. A companion `.csv` identification file is
   generated in the same temp directory.

   Temporary files are stored under
   `~/.cache/dasmixer/tmp/maxquant_import/<timestamp>/` and deleted when the
   import finishes (unless you uncheck "Delete temporary files").

3. **Create tool and subset** — a `MaxQuant` tool (type Library, parser
   MaxQuant) and a `MaxQuant Import` comparison group are created in your
   project if they don't already exist.

   > **Important:** if a tool named `MaxQuant` already exists but has a
   > different parser, the import is blocked (GUI: button stays grey;
   > CLI: hard error). Rename the existing tool before retrying.

4. **Import proteins** (optional) — the FASTA file is parsed and protein
   entries are added to the database.

5. **Import spectra and identifications per sample** — for each RAW file:
   - A sample is created (or reused if the name already exists).
   - Each `.mgf` file is imported as spectra.
   - Each companion `.csv` is imported as identifications linked to the
     `MaxQuant` tool.

6. **Save** — the project is checkpointed.

---

## Re-importing / Duplicates

You can run the same import multiple times. The behaviour depends on the
**On duplicates** setting:

| Setting | Behaviour |
|---|---|
| `Skip` (default) | Existing spectra/identification files are skipped |
| `Reload` | Existing files are deleted and re-imported |
| `Add as new` | New records are created alongside old ones |

Samples with matching names are **always reused** — a second sample with the
same name is never created.

---

## After Import

Imported data is immediately available:

- **Samples** appear in the Samples tab under the chosen subset.
- **Spectra** are linked to the sample's `spectre_file` records.
- **Identifications** are linked to the `MaxQuant` tool and can be used for
  preferred-identification selection, protein mapping, and quantification.

The regular DASMixer analysis pipeline (ion coverage, preferred
identifications, protein mapping, LFQ, reports) works on MaxQuant-imported
data exactly as on data imported through standard spectra/identification
imports.

---

## Limitations (Current Version)

- Only per-sample `.apl` files (`{raw_name}/p0/`) are supported.
  Shared `combined/andromeda/*.apl` files are not importable.
- If `.apl` files are spread across multiple RAW-parent directories, only the
  first one listed in `mqpar.xml` is used.
- Import cannot be cancelled once started.
- `proteinGroups.txt`, `summary.xml`, and other MaxQuant output files are not
  imported (future enhancement).
- Debug option `--limit` from the old `mq2dasmix` utility is not available.