# User Guide: Importing Spectra Data

This guide explains how to import mass spectrometry spectra data into DASMixer.

---

## Prerequisites

Before importing spectra:

1. **Create a Project**
   - File → New Project
   - Choose location and name

2. **Create at least one Comparison Group**
   - Go to "Samples" tab
   - Click "Add Group"
   - Enter group name (e.g., "Control", "Treatment")

---

## Import Methods

DASMixer offers two ways to import spectra files:

### 1. Select Individual Files

Best for: Importing specific files with custom settings

**Steps:**
1. Click **"Import Spectra (MGF)"** button
2. Choose **"Select individual files"**
3. Browse and select one or more spectra files
4. Configure each file:
   - **Sample Name:** Unique identifier for this sample
   - **Comparison Group:** Which group this sample belongs to
5. Select **File Format / Parser** (e.g., MGF)
6. Click **"Import"**

### 2. Pattern Matching from Folder

Best for: Batch importing multiple files with automatic sample naming

**Steps:**
1. Click **"Import Spectra (MGF)"** button
2. Choose **"Pattern matching from folder"**
3. Configure pattern matching:
   - **Folder path:** Select folder containing spectra files
   - **File pattern:** e.g., `*.mgf` (all MGF files)
   - **Sample ID pattern:** e.g., `{id}*.mgf` (extract ID from filename)
   - **File Format / Parser:** Select appropriate parser
   - **Assign to group:** Choose comparison group
4. Click **"Preview Files"** to verify file detection
5. Click **"Import"**

---

## File Format / Parser Selection

DASMixer supports multiple spectra file formats through parsers:

| Format | Extension | Description |
|--------|-----------|-------------|
| **MGF** | `.mgf` | Mascot Generic Format - text-based MS/MS data |

**Note:** Additional parsers may be available depending on installed plugins.

### How to choose:
- Select the format that matches your data files
- If unsure, MGF is the most common format for MS/MS data

---

## Sample ID Pattern Examples

Pattern matching extracts sample IDs from filenames:

### Pattern: `{id}*.mgf`
- **File:** `Sample_01_raw.mgf` → **Sample ID:** `Sample_01`
- **File:** `control_A.mgf` → **Sample ID:** `control`

### Pattern: `*_{id}_*.mgf`
- **File:** `exp_Sample01_raw.mgf` → **Sample ID:** `Sample01`
- **File:** `data_ctrl_processed.mgf` → **Sample ID:** `ctrl`

### Pattern: `sample_{id}.mgf`
- **File:** `sample_A1.mgf` → **Sample ID:** `A1`
- **File:** `sample_Control.mgf` → **Sample ID:** `Control`

**Tip:** Use "Preview Files" to verify IDs are extracted correctly before importing.

---

## Import Progress

During import, you'll see:

1. **Progress Bar:** Shows file import progress (1/N files)
2. **Details:** Number of spectra imported per file
3. **Status Messages:**
   - Success: "Successfully imported N spectra from M files"
   - Error: Specific error message if import fails

---

## After Import

Once import completes:

1. **Verify Samples:** Check "Samples" section shows imported samples
2. **Check Groups:** Verify sample counts updated in group list
3. **Next Steps:**
   - Import identifications (peptide/protein data)
   - View spectra in "Peptides" tab
   - Run comparative analysis

---

## Troubleshooting

### "No groups. Click 'Add Group' to create one"
**Solution:** Create at least one comparison group before importing.

### "Invalid file format: filename.mgf"
**Possible causes:**
- File is corrupted or incomplete
- Wrong file format selected (not actually MGF)
- File doesn't follow expected format structure

**Solution:** 
- Verify file can be opened in text editor
- Check file format matches selected parser
- Try with a different file to isolate issue

### "No files found"
**Causes:**
- Folder path incorrect
- File pattern doesn't match any files
- Files have wrong extension

**Solution:**
- Verify folder path is correct
- Check file pattern (e.g., `*.mgf` not `*.MGF` on case-sensitive systems)
- List files in folder to verify they exist

### Import is very slow
**Expected behavior:** Large files take time to process
- MGF files are parsed sequentially
- Each spectrum is validated and stored in database
- 1000 spectra per batch is typical

**Tips:**
- First import may be slower (database initialization)
- Subsequent imports are faster
- Consider using SSD for project file location

---

## Best Practices

### File Organization
```
data/
├── control/
│   ├── ctrl_01.mgf
│   ├── ctrl_02.mgf
│   └── ctrl_03.mgf
└── treatment/
    ├── treat_01.mgf
    ├── treat_02.mgf
    └── treat_03.mgf
```

**Import strategy:**
1. Import `control/` folder → assign to "Control" group
2. Import `treatment/` folder → assign to "Treatment" group

### Sample Naming
- **Use consistent naming:** `prefix_number` format
- **Avoid special characters:** Stick to letters, numbers, underscore, dash
- **Be descriptive:** Include condition/timepoint/replicate info
- **Examples:**
  - ✅ `Control_Day0_Rep1`
  - ✅ `Treatment_High_A`
  - ❌ `Sample #1` (special char)
  - ❌ `s1` (not descriptive)

### Group Organization
- Create groups that represent experimental conditions
- Examples:
  - Control vs Treatment
  - Timepoint_0, Timepoint_24, Timepoint_48
  - Wildtype, Mutant_A, Mutant_B

---

## Advanced Topics

### Custom Parsers

If you need to import a custom file format:

1. Contact developer or check plugin repository
2. Install parser plugin
3. Parser will appear automatically in "File Format / Parser" dropdown

### Validation

DASMixer validates files before import:
- Checks file format is correct
- Verifies required fields are present
- Rejects invalid files with error message

This prevents corrupted data from entering your project.

---

## Summary

**Quick Start:**
1. Create comparison group
2. Click "Import Spectra"
3. Choose import method
4. Select files and parser
5. Configure samples
6. Click "Import"
7. Wait for completion

**Support:** Check documentation or contact development team for assistance.

---

**Last Updated:** 2026-01-30  
**Version:** 1.0
