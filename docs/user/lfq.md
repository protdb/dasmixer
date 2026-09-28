# User Guide — Label-Free Quantification (LFQ)

## Overview

DASMixer implements four label-free quantification methods at the protein level:
**emPAI**, **NSAF**, **iBAQ**, and **Top3**. Each method estimates protein abundance from
peptide-level data (spectral counts or intensities) without requiring isotopic labels.

LFQ results are calculated **per sample** and stored in the project. Both relative
(normalized) and, optionally, absolute concentrations can be obtained.

---

## Terminology

| Term | Definition |
|---|---|
| **PSM** | Peptide-Spectrum Match — one identification of a peptide from one spectrum |
| **SpC** | Spectral Count — total number of PSMs assigned to a protein |
| **$N_{\text{obs}}$** | Number of unique (distinct) observed peptide sequences for a protein |
| **$N_{\text{observ}}$** | Number of theoretically observable peptides — obtained by *in silico* digestion of the protein sequence and filtering by length, mass, and missed cleavages |
| **Preferred identification** | The best identification per spectrum, selected across all tools |

---

## Quantification Methods

### emPAI — Exponentially Modified Protein Abundance Index

emPAI estimates protein abundance based on the ratio of observed to observable peptides.
It was introduced by Ishihama et al. (2005) and is widely used in shotgun proteomics.

**Formula:**

$$\text{emPAI} = 10^{\,N_{\text{obs}} / N_{\text{observ}}} - 1$$

where the base $10$ is the default; alternative bases (e.g., $e$) can be selected.

Key properties:

- Uses **only unique** peptide sequences (duplicates are removed before counting $N_{\text{obs}}$).
- $N_{\text{observ}}$ is determined by *in silico* digestion of the protein with the chosen enzyme (default: trypsin, no missed cleavages), followed by peptide length filtering (default: 7–30 amino acids).
- The output is a **non-normalized** index — higher emPAI means higher abundance.
- The protein abundance (mol%) is estimated as:

$$\text{Protein content (mol\%)} = \frac{\text{emPAI}_i}{\sum_j \text{emPAI}_j} \times 100\%$$

DASMixer performs this normalization automatically and reports it as the relative value.

---

### NSAF — Normalized Spectral Abundance Factor

NSAF normalizes spectral counts by protein length and across all proteins in the sample.
The underlying assumption is that larger proteins tend to generate more PSMs, so the count
must be adjusted by protein size.

**Step 1: SAF (Spectral Abundance Factor)**

$$\text{SAF}_i = \frac{\text{SpC}_i}{L_i}$$

where $\text{SpC}_i$ is the total PSM count for protein $i$, and $L_i$ is its sequence
length in amino acid residues.

**Step 2: NSAF (Normalized SAF)**

$$\text{NSAF}_i = \frac{\text{SAF}_i}{\sum_j \text{SAF}_j}$$

The sum of all NSAF values in a sample equals 1. NSAF is the **relative value** reported
by DASMixer.

Key properties:

- NSAF uses **spectral counts**, not intensities — it does not require intensity data.
- Normalization by protein length corrects for the bias that longer proteins generate
  more peptides and therefore more PSMs.
- Works well for comparing protein abundances **within a sample**.

---

### iBAQ — Intensity-Based Absolute Quantification

iBAQ normalizes the total peptide intensity by the number of theoretically observable
peptides. It was introduced by Schwanhäusser et al. (2011).

**Formula:**

$$\text{iBAQ}_i = \frac{\sum_k I_{i,k}}{N_{\text{observ}, i}}$$

where $\sum_k I_{i,k}$ is the sum of intensities of **all** observed peptides assigned
to protein $i$ (including duplicates), and $N_{\text{observ}, i}$ is the number of
theoretically observable peptides.

Key properties:

- Uses **all** peptide intensities — duplicates are included.
- Peptides with missing intensity (NaN) are excluded from the sum.
- $N_{\text{observ}}$ is the same value used for emPAI (depends on digestion and
  filtering parameters).
- Raw iBAQ is then normalized across proteins: $\text{iBAQ}_{i,\text{norm}} = \text{iBAQ}_i / \sum_j \text{iBAQ}_j$.

---

### Top3 — Mean of Top 3 Peptide Intensities

Top3 approximates protein abundance as the arithmetic mean of intensities of the three
most intense peptides assigned to the protein.

**Formula:**

$$\text{Top3}_i = \frac{I_{i,(1)} + I_{i,(2)} + I_{i,(3)}}{3}$$

where $I_{i,(1)}, I_{i,(2)}, I_{i,(3)}$ are the three highest peptide intensities for
protein $i$, sorted in descending order.

Key properties:

- Requires **at least 3 peptides** with intensity data. Proteins with fewer peptides
  receive no Top3 value.
- Simple and robust — does not require theoretical digestion or sequence information.
- Relies solely on MS1 intensity data.
- Raw Top3 is then normalized across proteins: $\text{Top3}_{i,\text{norm}} = \text{Top3}_i / \sum_j \text{Top3}_j$.

---

## Normalization (Relative Quantification)

For emPAI, iBAQ, and Top3, raw values are normalized so that they sum to 1 across all
proteins in the sample:

$$v_{i,\text{norm}} = \frac{v_i}{\sum_j v_j}$$

This normalization produces **relative abundance** values, suitable for comparing protein
levels **within a single sample**. NSAF is already normalized by definition (sum of SAF
is 1).

---

## Absolute Quantification

If a known protein concentration is available, DASMixer can convert relative values into
absolute concentrations. Two approaches are supported:

### Total Protein Concentration

When the total protein concentration $C_{\text{total}}$ is known (e.g., from a Bradford
or BCA assay, in g/L):

$$C_{i,\text{mass}} = v_{i,\text{norm}} \times C_{\text{total}}$$

### Reference Protein (Internal Standard)

When the concentration of a specific reference protein $C_{\text{ref}}$ is known:

$$C_{i,\text{mass}} = C_{\text{ref}} \times \frac{v_{i,\text{norm}}}{v_{\text{ref},\text{norm}}}$$

The reference protein is auto-detected by its UniProt accession (default: **P02768**,
serum albumin), or can be specified manually.

### Combined Approach

When both $C_{\text{total}}$ and $C_{\text{ref}}$ are known, DASMixer combines them with
a weighting factor $\alpha$ (default $0.5$):

$$C_{i,\text{mass}} = \alpha \cdot C_{i,\text{mass}}^{\text{ref}} + (1 - \alpha) \cdot C_{i,\text{mass}}^{\text{total}}$$

### Conversion to Molar Concentrations

Mass concentrations (g/L) can be converted to molar units (mol/L):

$$C_{i,\text{molar}} = \frac{C_{i,\text{mass}}}{\text{MW}_i \times 1000}$$

where $\text{MW}_i$ is the molecular weight of protein $i$ in kDa (approximated as
$0.11 \times \text{length}$, i.e. average amino acid residue mass of 110 Da).

---

## Digestion Parameters

The calculation of $N_{\text{observ}}$ (used by emPAI and iBAQ) depends on *in silico*
digestion parameters:

| Parameter | Default | Description |
|---|---|---|
| Enzyme | Trypsin | Cleavage specificity for *in silico* digestion |
| Min peptide length | 7 | Minimum amino acid residues in theoretical peptides |
| Max peptide length | 30 | Maximum amino acid residues in theoretical peptides |
| Missed cleavages | 2 | Maximum allowed missed cleavage sites |

These parameters control which theoretical peptides are considered "observable" and
directly affect emPAI and iBAQ values. Stricter filtering (tighter length range, fewer
missed cleavages) reduces $N_{\text{observ}}$ and increases the abundance index.

---

## Data Requirements

| Method | Requires FASTA | Requires intensities | Notes |
|---|---|---|---|
| **emPAI** | Yes | No | Needs protein sequence for *in silico* digestion |
| **NSAF** | Yes | No | Uses PSM counts and sequence length only |
| **iBAQ** | Yes | **Yes** | Needs both sequence and MS1 intensities |
| **Top3** | No | **Yes** | Needs at least 3 peptide intensities |

Only peptides from **preferred identifications** mapped to proteins are used.
If intensity data is missing, iBAQ and Top3 will return no value for affected proteins.

---

## Running LFQ in DASMixer

LFQ is calculated via the **Proteins tab** in the GUI after:
1. Spectra and identifications have been imported
2. Preferred identifications have been selected
3. A FASTA database has been imported and protein mapping has been performed
4. Protein identification results have been computed

Select a sample, choose one or more LFQ methods, configure digestion parameters,
and optionally enable absolute quantification by providing concentration values.
The results are stored in the `protein_quantification_result` table and can be
exported as CSV.

---

## References

1. Ishihama, Y., et al. (2005). Exponentially Modified Protein Abundance Index (emPAI)
   for Estimation of Absolute Protein Amount in Proteomics by the Number of Sequenced
   Peptides per Protein. *Molecular & Cellular Proteomics*, 4(9), 1265–1272.
   [DOI: 10.1074/mcp.M500061-MCP200](https://doi.org/10.1074/mcp.M500061-MCP200)

2. Zybailov, B., et al. (2006). Statistical Analysis of Membrane Proteome Expression
   Changes in *Saccharomyces cerevisiae*. *Journal of Proteome Research*, 5(9),
   2339–2347.
   [DOI: 10.1021/pr060161n](https://doi.org/10.1021/pr060161n)

3. Schwanhäusser, B., et al. (2011). Global quantification of mammalian gene expression
   control. *Nature*, 473, 337–342.
   [DOI: 10.1038/nature10098](https://doi.org/10.1038/nature10098)

4. Silva, J. C., et al. (2006). Absolute Quantification of Proteins by LCMSE.
   *Molecular & Cellular Proteomics*, 5(1), 144–156.
   [DOI: 10.1074/mcp.M500230-MCP200](https://doi.org/10.1074/mcp.M500230-MCP200)