# DASMixer Quick Start Guide

Get started with DASMixer in 5 minutes!

---

## Step 1: Create Project

1. Launch DASMixer
2. Click **"Create New Project"**
3. Choose location and filename (e.g., `my_experiment.dasmix`)
4. Project opens with default "Control" group

---

## Step 2: Add Comparison Groups

Groups represent experimental conditions (Control, Treatment, etc.)

1. Go to **"Samples"** tab
2. Click **"Add Group"** in "Comparison Groups" section
3. Enter:
   - **Name:** Treatment
   - **Description:** Drug treatment group
   - **Color:** Leave default or customize
4. Click **"Add"**

**Result:** Now you have Control and Treatment groups

---

## Step 3: Import Spectra Data

Import your mass spectrometry spectra files (MGF format).

### Option A: Individual Files

1. Click **"Import Spectra Files"**
2. Choose **"Select individual files"**
3. Browse and select your `.mgf` files
4. For each file, configure:
   - **Sample Name:** e.g., Sample01, Sample02
   - **Comparison Group:** Control or Treatment
5. Select **File Format:** MGF
6. Click **"Import"**
7. Wait for import to complete

### Option B: Pattern Matching (Batch Import)

1. Click **"Import Spectra Files"**
2. Choose **"Pattern matching from folder"**
3. Configure:
   - **Folder path:** Select folder with MGF files
   - **File pattern:** `*.mgf` (all MGF files)
   - **Sample ID pattern:** `{id}*.mgf` (extracts ID from filename)
   - **File Format:** MGF
   - **Assign to group:** Control
4. Click **"Preview Files"** to verify
5. Click **"Import"**

**Result:** Samples appear in "Samples" section

---

## Step 4: Add Identification Tools

Tools represent identification methods (de novo, database search, etc.)

1. In **"Identification Tools"** section, click **"Add Tool"**
2. Enter:
   - **Tool Name:** PowerNovo2 (or your method)
   - **Parser:** Select from available parsers
   - **Color:** Optional customization
3. Click **"Add"**
4. Repeat for other tools (e.g., MaxQuant)

**Result:** Tools appear in list, each with "Import Identifications" button

---

## Step 5: Import Identifications

Import peptide/protein identification results for each tool.

1. Find your tool in **"Identification Tools"** list
2. Click **"Import Identifications"** button on that tool
3. Choose import mode (individual files or pattern matching)
4. Select your identification files (`.csv` or tool-specific format)
5. **Important:** Sample names in files must match your imported samples
6. Click **"Import"**

**Result:** Samples now show "✓ ToolName" next to them

---

## Verify Results

Check the **"Samples"** section:

```
✓ Sample01
  Group: Control • Files: 1 • ✓ PowerNovo2, ✓ MaxQuant

✓ Sample02
  Group: Treatment • Files: 1 • ✓ PowerNovo2
```

---

## Example: Complete Workflow

### Scenario: Compare Control vs Treatment, two identification methods

**Setup:**
```
Data files:
  spectra/
    control_01.mgf
    control_02.mgf
    treatment_01.mgf
    treatment_02.mgf
  
  identifications/
    powernovo/
      control_01.csv
      control_02.csv
      treatment_01.csv
      treatment_02.csv
    
    maxquant/
      control_01_evidence.txt
      control_02_evidence.txt
      treatment_01_evidence.txt
      treatment_02_evidence.txt
```

**Steps:**

1. **Create project** → `experiment.dasmix`

2. **Add groups:**
   - Control
   - Treatment

3. **Import spectra for Control:**
   - Pattern matching: `spectra/` folder
   - Pattern: `control_*.mgf`
   - Sample ID: `control_{id}`
   - Group: Control
   → Creates: control_01, control_02

4. **Import spectra for Treatment:**
   - Pattern matching: `spectra/` folder
   - Pattern: `treatment_*.mgf`
   - Sample ID: `treatment_{id}`
   - Group: Treatment
   → Creates: treatment_01, treatment_02

5. **Add Tool "PowerNovo2"**
   - Parser: PowerNovo2

6. **Import identifications for PowerNovo2:**
   - Pattern matching: `identifications/powernovo/`
   - Pattern: `*.csv`
   - Sample ID: `{id}`
   → Links to samples by name

7. **Add Tool "MaxQuant"**
   - Parser: MaxQuant

8. **Import identifications for MaxQuant:**
   - Pattern matching: `identifications/maxquant/`
   - Pattern: `*_evidence.txt`
   - Sample ID: `{id}`

**Final Result:**
```
Groups:
  📁 Control (2 samples)
  📁 Treatment (2 samples)

Tools:
  🧬 PowerNovo2 (4 files)
  🧬 MaxQuant (4 files)

Samples:
  🧪 control_01    • Control • ✓ PowerNovo2, ✓ MaxQuant
  🧪 control_02    • Control • ✓ PowerNovo2, ✓ MaxQuant
  🧪 treatment_01  • Treatment • ✓ PowerNovo2, ✓ MaxQuant
  🧪 treatment_02  • Treatment • ✓ PowerNovo2, ✓ MaxQuant
```

---

## Tips & Best Practices

### Naming Conventions

✅ **Good:**
- `control_01`, `control_02`
- `Sample_A`, `Sample_B`
- `Day0_Rep1`, `Day1_Rep1`

❌ **Bad:**
- `sample #1` (special characters)
- `s1` (too short, not descriptive)
- `Sample 01` (space, prefer underscore)

### File Organization

Organize files by condition/group:
```
data/
├── control/
│   ├── spectra/
│   └── identifications/
└── treatment/
    ├── spectra/
    └── identifications/
```

### Sample ID Extraction

Pattern: `{id}*.mgf`

| Filename | Extracted ID |
|----------|--------------|
| `Sample01_raw.mgf` | `Sample01` |
| `ctrl_A.mgf` | `ctrl` |
| `exp_2024_01.mgf` | `exp` |

Pattern: `*_{id}_*.mgf`

| Filename | Extracted ID |
|----------|--------------|
| `exp_Sample01_raw.mgf` | `Sample01` |
| `data_ctrl_processed.mgf` | `ctrl` |

---

## Troubleshooting

### "Please create at least one comparison group first"
→ Add a group before importing spectra

### "Please import spectra first"
→ Import spectra before identifications

### "Sample 'SampleX' not found"
→ Check sample name matches between spectra and identification files

### "No spectra files for sample 'SampleX'"
→ Sample exists but no spectra imported

### "Invalid file format"
→ Check file format matches selected parser

---

## What's Next?

After importing data:

1. **Peptides Tab** - View identifications, ion matches
2. **Proteins Tab** - Protein identifications, LFQ
3. **Analysis Tab** - Comparative analysis, volcano plots, PCA

---

## Support

- Check documentation in `docs/` folder
- View examples in project files
- Contact: Laboratory of Structural Proteomics, IBMC, Moscow

---

**Version:** 1.0  
**Last Updated:** 2026-01-30
