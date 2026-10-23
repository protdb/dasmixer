# Creating Custom Identification Importers

DASMixer supports pluggable parsers for importing peptide identifications from third-party search engines and de novo sequencing tools. Custom importers can be installed as single `.py` files or `.zip` packages in `{app_dir}/plugins/inputs/identifications/` (or via **Options → Plugins** in the GUI).

---

## Importer Base Classes

All identification parsers inherit from `IdentificationParser` (in `dasmixer.api.inputs.peptides.base`), which itself extends `BaseImporter`. Depending on your input file format, you can subclass one of three classes:

| Base Class | Module | Best For |
|---|---|---|
| `SimpleTableImporter` | `dasmixer.api.inputs.peptides.table_importer` | Standard CSV, TSV, XLS, XLSX, or ODS tables that fit in memory |
| `LargeCSVImporter` | `dasmixer.api.inputs.peptides.table_importer` | Huge CSV/TSV files requiring asynchronous line-by-line streaming (`aiocsv`) |
| `IdentificationParser` | `dasmixer.api.inputs.peptides.base` | Custom non-tabular or complex formats (e.g., XML, mzTab, custom binary) |

---

## Option 1: Using `SimpleTableImporter` (Recommended for CSV/Excel)

Most tools output a flat CSV, TSV, or Excel table. `SimpleTableImporter` handles reading the file, applying PTM alias replacements, remapping columns, and yielding batches automatically.

### Standard Output Columns (`ColumnRenames`)

`ColumnRenames` maps your tool's column names to DASMixer's internal schema. At least one spectrum identifier column (`seq_no`, `scans`, or `title`) and `sequence` must be provided:

| `ColumnRenames` Field | Type | Description |
|---|---|---|
| `seq_no` | `int` | 0-based or 1-based sequential spectrum index in the MGF file |
| `scans` | `int` | Scan number from the MGF `SCANS` field |
| `title` | `str` | Spectrum title from the MGF `TITLE` field |
| `sequence` | `str` | Peptide sequence with modifications in **ProForma** notation |
| `canonical_sequence` | `str` | Unmodified amino acid sequence |
| `score` | `float` | Search engine or de novo confidence score |
| `positional_scores` | `list[float]` | Per-residue confidence scores (optional) |
| `ppm` | `float` | Precursor mass error in ppm (optional) |
| `theor_mass` | `float` | Theoretical neutral peptide mass (optional) |
| `src_file_protein_id` | `str` | Protein accession(s), semicolon-separated if multiple (optional) |
| `fdr` | `float` | Per-PSM False Discovery Rate (optional) |
| `e_value` | `float` | E-value (optional) |
| `q_value` | `float` | Q-value (optional) |

### Minimal Plugin Example (`my_tool_importer.py`)

```python
import pandas as pd
from dasmixer.api.inputs.peptides.table_importer import ColumnRenames, SimpleTableImporter
from dasmixer.api.inputs.registry import registry

# 1. Map source file columns to DASMixer standard columns
renames = ColumnRenames(
    scans="ScanNumber",
    sequence="ModifiedPeptide",
    canonical_sequence="Peptide",
    score="Confidence",
    ppm="DeltaPPM",
    fdr="FDR",
)


class MyToolImporter(SimpleTableImporter):
    """Custom importer for MyTool CSV results."""

    PARSER_ID = "MyTool"
    separator = ","                  # Use "\t" for TSV files
    spectra_id_field = "scans"       # Match spectra by 'scans', 'seq_no', or 'title'
    renames = renames

    # Optional: apply PTM alias replacements from import_ptm_renames.csv
    # before transform_df() and remap_columns()
    field_to_proforma = "ModifiedPeptide"

    def transform_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Optional hook to transform raw columns before column renaming.
        `df` still has the original column names from the file.
        """
        df = df.copy()
        # Example: strip flanking amino acids like "K.PEPTIDE.R" -> "PEPTIDE"
        if "Peptide" in df.columns:
            df["Peptide"] = df["Peptide"].str.replace(r"^[A-Z\-]\.|\.[A-Z\-]$", "", regex=True)
        return df


# 2. Register the parser at module level so DASMixer discovers it on load
registry.add_identification_parser("MyTool", MyToolImporter)
```

---

## Option 2: Subclassing `IdentificationParser` Directly

If your file format is not a simple table, subclass `IdentificationParser` and implement `validate()` and `parse_batch(batch_size)`:

```python
from collections.abc import AsyncIterator
import pandas as pd
from dasmixer.api.inputs.peptides.base import IdentificationParser
from dasmixer.api.inputs.registry import registry


class CustomFormatImporter(IdentificationParser):
    PARSER_ID = "CustomFormat"
    spectra_id_field = "scans"       # 'scans', 'seq_no', or 'title'
    contain_proteins = False         # Set True if self._proteins is populated
    can_import_stacked = False       # Set True if one file holds multiple samples
    can_import_multifile = False     # Set True if one file maps to multiple MGFs

    async def validate(self) -> bool:
        """Return True if self.file_path is a valid file of this format."""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                first_line = f.readline()
            return first_line.startswith("#CustomHeader")
        except Exception:
            return False

    async def parse_batch(self, batch_size: int = 1000) -> AsyncIterator[pd.DataFrame]:
        """Yield DataFrames with standard column names in chunks of batch_size."""
        rows = []
        with open(self.file_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("#") or not line.strip():
                    continue
                parts = line.strip().split("\t")
                rows.append({
                    "scans": int(parts[0]),
                    "sequence": parts[1],
                    "canonical_sequence": parts[2],
                    "score": float(parts[3]),
                })
                if len(rows) >= batch_size:
                    yield pd.DataFrame(rows)
                    rows.clear()
        if rows:
            yield pd.DataFrame(rows)


registry.add_identification_parser("CustomFormat", CustomFormatImporter)
```

---

## Advanced Parser Capabilities

- **Collecting Proteins (`contain_proteins = True`)**:
  - In `SimpleTableImporter`, map `src_file_protein_id` in `ColumnRenames` and set `contain_proteins = True`. Semicolon-separated protein IDs are automatically split and stored in `self._proteins`.
  - In custom parsers, populate `self._proteins[protein_id] = Protein(id=protein_id, is_uniprot=self.is_uniprot_proteins)` while iterating in `parse_batch`.
- **Stacked Files (`can_import_stacked = True`)**:
  - Used when a single identification file contains results for multiple samples (e.g., MaxQuant `evidence.txt`).
  - Set `can_import_stacked = True` and `sample_id_column = "Raw file"`, and include a `sample_id` column in the yielded DataFrame.

---

## Installing and Testing Your Plugin

1. Save your script as `my_tool_importer.py`.
2. Open DASMixer and go to **Options → Plugins**, then click **Install from file...** and select `my_tool_importer.py` (or place it directly in `~/.config/dasmixer/plugins/inputs/identifications/` on Linux or `%APPDATA%\dasmixer\plugins\inputs\identifications\` on Windows).
3. Restart DASMixer.
4. On the **Samples** tab, click **Add Tool** — `"MyTool"` will now appear in the **Parser** dropdown.
