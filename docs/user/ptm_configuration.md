# PTM Configuration

DASMixer maintains its PTM (post-translational modification) definitions
in two plain-text CSV files located in the application configuration
directory. You can inspect and edit these files to add new modifications
or to teach DASMixer how to recognise PTM notation from third-party
software.

---

## Location

All PTM configuration files live in:

| OS      | Path                                        |
|---------|---------------------------------------------|
| Linux   | `~/.config/dasmixer/ptm/`                   |
| Windows | `%APPDATA%/dasmixer/ptm/`                   |
| macOS   | `~/Library/Application Support/dasmixer/ptm/` |

The folder is created automatically on the first DASMixer launch. You can
open it quickly from the application:

> **Settings** → click **Open configuration folder**.

This opens the entire `dasmixer` config directory in your system file
manager; the `ptm/` subfolder is inside it.

---

## Files

### `all_ptm_config.csv` — PTM definitions

This file lists all modifications that DASMixer can try when searching
for fixed PTMs on peptide sequences. Each row defines one modification.

**Columns:**

| Column       | Type    | Description |
|------------- |---------|-------------|
| `name`       | text    | PTM identifier shown in the UI (e.g. `Oxidation`, `Deamidated`) |
| `attach_to`  | text    | Amino-acid codes the PTM can attach to, separated by `;` (e.g. `S;T;Y`). Leave empty for terminal-only or unrestricted PTMs. |
| `mono_mass`  | number  | Monoisotopic mass shift (Da). Leave empty to look up the mass from the built-in Unimod database automatically. |
| `n_term`     | `Y`/`N` | Whether this PTM can appear at the protein N-terminus. |
| `c_term`     | `Y`/`N` | Whether this PTM can appear at the protein C-terminus. |
| `default`    | `Y`/`N` | If `Y`, this PTM is pre-selected in the tool settings dialog when no explicit PTM list has been saved. |

**Default set:** 43 common PTMs are shipped with DASMixer. Three of them
have `default=Y`: **Amidated**, **Deamidated**, **Pyridylethyl**. These
are the modifications enabled by default for new tools.

### `import_ptm_renames.csv` — parser aliases

Identification files from third-party software (MaxQuant, PLGS,
PeptideShaker) use their own notation for modifications. This file maps
those vendor-specific names to the standard DASMixer PTM codes used in
`all_ptm_config.csv`.

**Columns:**

| Column        | Type  | Description |
|-------------- |-------|-------------|
| `source`      | text  | Substring in the identification file that should be replaced (e.g. `(Deamidation (NQ))`, `S-pyridylethyl`) |
| `proforma`    | text  | Target PTM code (must match a `name` in `all_ptm_config.csv`) or a ProForma string (e.g. `[Deamidated]`, `[-89.029920]-` for N-terminal acetylation). |
| `parser`      | text  | Which parser this rule applies to: `MaxQuant`, `PLGS`, or `PeptideShaker XLS`. |
| `is_terminal` | `Y`/`N` | Whether this substitution represents a terminal modification (N-term or C-term). `Y` only for positional PTMs like `NH2` → `Amidated`. |

**Default set:** 18 entries covering all three supported parsers.

---

## Editing the files

### Important rules

1. **CSV format only.** Both files must remain valid CSV with the header
   row intact. All columns are required; empty cells are allowed where
   noted above.

2. **Encoding.** Files use UTF-8 encoding without BOM. Most text editors
   handle this automatically.

3. **Changes take effect on restart.** DASMixer reads these files once at
   startup. After editing, restart the application.

4. **PTM codes are case-sensitive.** `Oxidation` and `oxidation` are
   different identifiers. Always match the exact spelling.

### Recommended editors

| Editor           | Notes |
|----------------- |-------|
| **LibreOffice Calc** | File → Open → choose `all_ptm_config.csv`. In the import dialog set **Separator: Comma**, **Text delimiter: "**. After editing, File → Save As → choose **CSV format**, check **Edit filter settings**, make sure **Field delimiter: `,`**, **String delimiter: `"`**, **Quote all text cells: No**. |
| **OpenOffice Calc** | Same procedure as LibreOffice. |
| **Microsoft Excel** | File → Open → choose the CSV file. **Important:** Excel may interpret values like `Methylthio` or `Glu->pyro-Glu` incorrectly. After editing, use File → Save As → **CSV UTF-8 (Comma delimited) (*.csv)**. The `attach_to` column with `;` separators will be quoted automatically — that is correct. |
| **VS Code / Notepad++ / any text editor** | Simplest option: edit as plain text. Install a CSV syntax-highlighting extension for readability. |

### Adding a new PTM

1. Open `all_ptm_config.csv`.
2. Append a new row at the bottom (or insert anywhere). Example:
   ```
   MyNewPTM,K,16.0,Y,N,N
   ```
   This defines a PTM called `MyNewPTM` that attaches to lysine (`K`),
   has mass +16.0 Da, can be N-terminal, not C-terminal, and is not a
   default PTM.
3. Save the file and restart DASMixer.
4. The new PTM will appear in the **Select PTMs** dialog (Peptides tab →
   Tool Settings → PTM → Select PTMs…).

### Adding a parser alias

1. Open `import_ptm_renames.csv`.
2. Append a new row. Example for MaxQuant:
   ```
   (MyCustomMod),MyNewPTM,MaxQuant,N
   ```
   This tells DASMixer: when importing MaxQuant evidence files, replace
   the substring `(MyCustomMod)` in the Modified Sequence column with
   `MyNewPTM`.
3. Save and restart. The alias is picked up on the next identification
   import.

### Resetting to defaults

If you ever need to restore the original configuration, simply **delete**
the `ptm/` folder (or the specific CSV file) and restart DASMixer. The
application will regenerate the files from built-in defaults on the next
startup.

---

## How PTMs are used

### In peptide matching

When DASMixer performs ion-coverage calculation and PTM fixing
(`seqfixer`), it uses the `PTMS` list loaded from `all_ptm_config.csv`.
For each peptide sequence it tries all enabled PTMs in the configured
combinations (up to `max_ptm` simultaneous modifications) to find a match
within the PPM tolerance.

The set of *enabled* PTMs is configured per tool in the GUI:

> **Peptides** tab → **Tool Settings** → **PTM** → **Select PTMs…**

The dialog shows all 43 PTMs with their sites and mass. Three are
pre-selected by default. You can enable or disable any combination.

### In identification import

When importing identification files, DASMixer uses `import_ptm_renames.csv`
to convert vendor-specific modification notation to standard ProForma
format. This happens automatically — no user action required beyond
keeping the renames file up to date if you use custom PTM notation in
your source files.

---

## See also

- [Workflow guide](workflow.md) — step-by-step project workflow.
- [MaxQuant import](MaxQuant.md) — importing MaxQuant projects.