# User Guide — Workflow Overview

## Project Concept

A **project** is DASMixer's fundamental unit of work. It is a single `.dasmix` file that stores all experimental data:
- Spectra (MGF peak lists)
- Identification results from multiple tools
- Protein matches and quantification
- Generated reports and saved plots

The project is a SQLite database. All data is self-contained — you can share the file between machines or store it for long-term archiving.

---

## Typical Analysis Workflow

```
1. Create project
2. Define comparison groups (subsets)
3. Register identification tools
4. Import spectra (MGF files) → samples created
5. Import identification files → linked to tools
6. Run ion coverage calculation (PPM + coverage per identification)
7. Select preferred identifications (best per spectrum across tools)
8. Import FASTA protein database
9. Run protein mapping (peptide → protein)
10. Compute protein identification results
11. Run LFQ quantification
12. Generate and export reports
```

---

## Starting a New Project

**GUI:** Launch DASMixer → click **New Project** → choose save location.

On project creation, a default "Control" comparison group is created automatically.

**CLI:** Opens GUI with project path:
```bash
dasmixer /path/to/study.dasmix
```

---

## Comparison Groups (Subsets)

Groups organize samples for differential analysis. Each sample belongs to one group.

**GUI (Samples tab → Groups section):**
- Click **+** to add a group
- Enter name, optional description, select color
- Click the color chip to change the display color

**Constraints:**
- Group names must be unique
- A group with associated samples cannot be deleted (reassign samples first)
- You can edit a group name and color at any time

**CLI:**
```bash
dasmixer study.dasmix subset add --name "Treatment"
dasmixer study.dasmix subset list
dasmixer study.dasmix subset delete --name "OldGroup"
```

---

## Identification Tools

Tools represent identification software. Register each tool before importing its result files.

**GUI (Samples tab → Tools section):**
- Click **+** to add a tool
- Enter tool name (e.g., "PowerNovo2", "MaxQuant Run1")
- Select tool type: **Library** (PLGS, MaxQuant) or **De Novo** (PowerNovo2)
- Select parser: matches the file format of this tool's output
- Optionally set display color

**Important:** The parser determines how identification files are parsed. It must match the actual file format.

---

## Importing Spectra (MGF Files)

Each MGF file corresponds to one sample. The import creates a sample record and links the file to it.

**GUI (Samples tab → sample panel → Import Spectra):**
1. Click the spectra import button on a sample panel
2. Select MGF file via file picker
3. The file is parsed and spectra are stored in the project database

**CLI (single file):**
```bash
dasmixer study.dasmix import mgf-file \
    --file /data/run1.mgf \
    --sample-id "Sample_01" \
    --group Control
```

**CLI (batch by pattern):**
```bash
dasmixer study.dasmix import mgf-pattern \
    --folder /data/spectra \
    --pattern "*.mgf" \
    --id-pattern "{id}_*.mgf" \
    --group Treatment
```

The `--id-pattern` uses `{id}` as a placeholder — the text matched by `{id}` becomes the sample name.

---

## Importing Identification Files

Each identification file is linked to:
- A **spectra file** (to map spectra IDs)
- A **tool** (to record which software produced the results)

**GUI (Samples tab → sample panel → Import Identifications):**
1. Expand the sample panel
2. Click "Import Identifications" next to the spectra file
3. Select the tool and identification file
4. The import parser maps scan/sequence numbers to spectrum IDs

**Status indicators:**
- Green check: identification file imported with results
- Red cross: identification file registered but empty (no matched spectra)
- Missing: no identification file for this tool

---

## Ion Coverage Calculation (Peptides Tab)

After importing identifications, calculate PPM error and ion coverage metrics for each identification.

**Peptides tab → Ion Match Settings:**

| Parameter | Description |
|---|---|
| Ion types | Select ion series: b, y, a, c, x, z |
| PPM tolerance | Matching tolerance in parts-per-million |
| Water loss | Include -H2O (-18.01 Da) ions |
| Ammonia loss | Include -NH3 (-17.03 Da) ions |
| Fragment charges | Charge states for fragment ions |

**De Novo correction settings:**

| Parameter | Description |
|---|---|
| Charge range (min/max) | Try alternative charge states for de novo sequences |
| Max isotope offset | Try precursor mass ± n × 1.003 Da |
| PTM list | Known modifications to try as hypotheses |
| Max PTMs | Maximum number of PTMs per sequence |

Click **Run Ion Coverage** to start. A progress dialog shows batch processing.

**What it computes:**
- `ppm`: mass error between experimental and theoretical precursor
- `intensity_coverage`: fraction of spectrum intensity matched by theoretical ions
- `ions_matched`: count of matched ions (for best ion type)
- `top_peaks_covered`: how many of the 10 most intense peaks are matched
- `override_charge`: if a different charge gave better results

---

## Preferred Identification Selection (Peptides Tab)

Each spectrum may have identifications from multiple tools. This step selects the single best identification per spectrum.

**Peptides tab → Preferred Identification Settings:**

| Parameter | Description |
|---|---|
| Criterion | Select by PPM (minimum error) or by coverage (maximum intensity coverage) |
| Min score | Minimum identification score (tool-dependent) |
| Max PPM | Maximum allowed mass error |
| Min coverage | Minimum ion intensity coverage (%) |
| Min/Max length | Canonical sequence length filter |
| Min peaks | Minimum number of peaks in spectrum |
| Min ions covered | Minimum matched ions count |
| Min top-10 peaks | Minimum number of top-10 peaks that must be matched |
| De novo correction | For de novo tools: use corrected PPM (from protein match) when available |

Per-tool settings allow different thresholds for library vs. de novo identifications.

Click **Set Preferred Identifications** to run.

---

## Protein Mapping (Proteins Tab)

Map canonical peptide sequences to protein sequences from a FASTA database.

**Proteins tab → Protein Mapping:**
1. Select FASTA file (or use previously loaded one)
2. Configure mapping:
   - Minimum identity: for exact matches, set 1.0; for de novo partial matches, set e.g. 0.9
   - Protein database limit: max proteins to load
3. Click **Run Protein Mapping**

The mapping uses npysearch BLAST-like alignment.

---

## Protein Identification Results

After mapping, build protein identification results:
- Peptide count per protein per sample
- Unique evidence count (peptides that uniquely identify this protein)
- Sequence coverage (%)
- Intensity sum

**Proteins tab → Protein Results:**
1. Set minimum peptides and unique evidence thresholds
2. Click **Compute Protein Identifications**

---

## LFQ Quantification (Proteins Tab)

Label-free quantification calculates relative protein abundance.

**Proteins tab → LFQ Settings:**

| Algorithm | Description | Best for |
|---|---|---|
| emPAI | Exponentially modified protein abundance index | Discovery experiments |
| iBAQ | Intensity-based absolute quantification | Comparing runs |
| NSAF | Normalized spectral abundance factor | Normalization by sequence length |
| Top3 | Average of 3 most abundant peptide intensities | Absolute quantification |

Digestion parameters (enzyme, peptide length range, missed cleavages) define theoretical observable peptides for emPAI and iBAQ.

Click **Run LFQ** to calculate.

---

## Viewing Results

### Peptide Table (Peptides Tab)
- Filter by sample, group, tool, sequence, protein
- Toggle "preferred only"
- Export table to Excel

### Ion Spectrum Plot (Peptides Tab)
- Select spectra file from dropdown
- Enter spectrum sequence number
- View annotated ion plot with matched peaks highlighted

### Protein Table (Proteins Tab)
- Filter by protein ID, gene, sample, group
- Filter by peptide count, coverage, intensity
- Sort by any column

### Sample Status (Samples Tab)
Each sample panel shows status:
- **OK** (green): spectra + identifications loaded, above thresholds
- **WARNING** (yellow): some files or identifications missing/below threshold
- **ERROR** (red): no spectra files, or spectra without any identifications

---

## Reports

See [reports.md](reports.md) for full details on generating, viewing, and exporting reports.
