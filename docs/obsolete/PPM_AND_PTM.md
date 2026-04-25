# Precursor Mass Validation, Charge Correction, and PTM Assignment

This document describes the logic of precursor mass validation and post-translational modification (PTM) assignment implemented in DASMixer. The algorithm operates on individual peptide identifications produced by de novo sequencing tools and determines: (1) how well the identified sequence explains the observed precursor mass, (2) what charge state the precursor actually carried, and (3) whether a known PTM applied to one or more residues in the sequence would improve the mass agreement.

---

## Background: what is PPM error?

For a peptide of known sequence, the **theoretical neutral monoisotopic mass** $M_{theor}$ can be calculated from residue masses. The instrument measures the **precursor m/z** value ($m/z_{obs}$) at a known charge state $z$:

$$M_{obs} = (m/z_{obs} - m_p) \cdot z$$

where $m_p = 1.007276$ Da is the proton mass.

The mass accuracy is expressed in **parts per million (PPM)**:

$$\text{PPM} = \frac{m/z_{obs} - m/z_{theor}}{m/z_{theor}} \times 10^6$$

where

$$m/z_{theor} = \frac{M_{theor} + z \cdot m_p}{z}$$

A small absolute PPM value (typically $|\text{PPM}| \leq 10$–$20$) indicates good agreement between the identified sequence and the observed precursor.

---

## Overview of the pipeline

For each identification the algorithm executes up to three sequential steps, stopping as soon as an acceptable match is found:

```
Step 1: Direct hit at reported charge
        ↓ (fails if |PPM| > target)
Step 2: Charge override scan
        ↓ (fails if no charge passes)
Step 3: Isotope offset × PTM enumeration
        ↓
Return best matching sequence variant
```

The **target PPM threshold** (default **50 PPM**, configurable per tool in the Tool Settings panel under *Max PPM*) defines what counts as an acceptable match throughout all steps.

---

## Step 1: Direct hit at reported charge

The algorithm first computes PPM using the charge state reported in the MGF file (the `CHARGE` field). If this charge produces $|\text{PPM}| \leq$ target, the sequence is accepted as-is — no modification or charge correction is applied.

**This step is skipped** if the instrument file does not contain a charge value, or if the *Ignore spectre charges* option is enabled (default: **on**).

---

## Step 2: Charge override scan

De novo tools often assign an incorrect charge, especially for low-quality spectra. The algorithm therefore scans a range of precursor charge states $z \in [z_{min},\; z_{max}]$ (default: **1 to 4**, configurable via *Min/Max precursor charge*) and computes PPM for each:

$$\text{PPM}(z) = \frac{m/z_{obs} - \frac{M_{theor} + z \cdot m_p}{z}}{\frac{M_{theor} + z \cdot m_p}{z}} \times 10^6$$

All charge values for which $|\text{PPM}(z)| \leq$ target are retained as valid hits. The charge with the globally minimum $|\text{PPM}|$ across the whole range is also remembered as `best_charge` — it will be used in Step 3 even if no charge alone passed the threshold.

If at least one charge passes, the algorithm returns all passing variants and **does not proceed to Step 3**.

---

## Step 3: Isotope offset and PTM enumeration

This is the most comprehensive and computationally expensive step. It covers two phenomena that are common in high-throughput proteomics:

### 3a. Precursor isotope offset

Mass spectrometers sometimes select and fragment not the monoisotopic peak of a peptide isotope envelope but the first or second **¹³C isotope peak**. Each such shift adds approximately:

$$\Delta m_{isotope} = \frac{k \cdot 1.003355\;\text{Da}}{z}$$

to the observed $m/z$ (where $k = 0, 1, 2, \ldots$ is the isotope offset and $1.003355$ Da $\approx$ ¹³C − ¹²C mass difference). The algorithm corrects the observed precursor mass for each offset:

$$m/z_{corrected}(k) = m/z_{obs} - \frac{k \cdot 1.003355}{z}$$

The range of tested offsets is $k \in [0,\; k_{max}]$, where $k_{max}$ defaults to **2** and is configurable via *Max isotope offset*.

### 3b. PTM combinations

Within each isotope-corrected mass, the algorithm enumerates all combinations of candidate PTMs applied to the peptide. For each combination it builds a ProForma-annotated sequence string, calculates its theoretical mass, and evaluates PPM.

**Candidate PTMs** are drawn from a user-configurable list (configurable per tool via *Select PTMs...*). Each PTM is defined by:
- its **code** (Unimod name, e.g. *Deamidation*, *Oxidation*, *Amidated*)
- the **residues** it may be attached to (e.g., Deamidation → N, Q; Pyridylethyl → C)
- or, for terminal modifications, whether it applies to the N- or C-terminus

**Combinations explored at each isotope offset:**

| Level | What is tried |
|---|---|
| 0 PTMs | Bare sequence with all terminal modification variants |
| 1 PTM | All single-site positions × terminal variants |
| 2 PTMs | All pairs of positions × terminal variants |
| … | … |
| *max_ptm* PTMs | All *max_ptm*-element subsets × terminal variants |

The parameter *max_ptm* (default **5**, configurable per tool) sets the upper limit. Note that complexity grows combinatorially with sequence length and PTM site count — large values may significantly increase processing time.

**Constraint:** two PTMs cannot be applied simultaneously to the same residue position.

A PTM combination is accepted if the resulting $|\text{PPM}|$ falls within the target threshold.

### 3c. Lookover mode

By default (*Force isotope offset lookover* = **on**), the algorithm does **not** stop at the first isotope offset that yields hits. Instead, it scans **all** offsets $k = 0 \ldots k_{max}$ and collects every passing sequence variant, then returns the complete ranked list. This ensures that a better match at $k=2$ is not missed because $k=0$ already produced a marginal hit.

When *Force isotope offset lookover* is **off**, the search stops at the first offset that produces any hit.

---

## Selecting the best sequence variant

If multiple sequence variants pass the PPM threshold (different PTM combinations and/or different charges), they are ranked by the **sequence selection criterion** (configurable via *Sequence selection criteria*, default **Coverage**):

| Criterion | Description |
|---|---|
| **Coverage** | Fraction of total spectrum intensity explained by matched fragment ions (primary sort: highest coverage first; tie-break: lowest $|\text{PPM}|$) |
| **Peaks** | Total number of fragment ion matches (highest count first) |
| **Top Peaks** | Number of the 10 most intense experimental peaks that are matched (highest first) |

The top-ranked variant becomes the **result sequence** stored in the identification. If the result sequence differs from the original input (i.e., a PTM was added), the original is preserved separately as `source_sequence`.

---

## Fragment ion matching

After the best precursor mass variant is determined, the algorithm matches the selected sequence against the experimental MS/MS spectrum to compute ion coverage metrics. Theoretical fragment ions are generated for the ion series specified under *Ion Types* (default: **b** and **y**) at the specified fragment charge states (default: **1, 2**). Optional neutral losses (–H₂O, –NH₃) are included if enabled.

Each theoretical ion is matched to the nearest experimental peak (or the most intense one, depending on *mode*) within the fragment **PPM tolerance** (default: **20 PPM**). The following metrics are computed:

| Metric | Description |
|---|---|
| `intensity_coverage` (%) | $\sum$ intensities of matched peaks / $\sum$ all peak intensities × 100 |
| `ions_matched` | Maximum number of consecutive fragment ions matched for any ion series |
| `top_peaks_covered` | Number of matched peaks among the 10 most intense peaks in the spectrum |
| `ion_match_type` | Ion series (b, y, …) with the most matched ions |

These metrics are stored in the identification record and are used for filtering (per-tool thresholds *Min Ion Coverage*, *Min Ions Covered*, *Min Top-10 Peaks Covered*) and for selecting the preferred identification when multiple tools report the same spectrum.

---

## Configurable parameters — summary

### Ion Matching Settings (global, per project)

| Parameter | Default | Description |
|---|---|---|
| Ion types | b, y | Fragment ion series to generate and match |
| Water loss | off | Include –H₂O neutral loss ions |
| Ammonia loss | off | Include –NH₃ neutral loss ions |
| PPM threshold | 20 | Fragment ion matching tolerance (PPM) |
| Fragment charges | 1, 2 | Charge states for theoretical fragment ions |
| Ignore spectre charges | on | Use charge scan instead of MGF-reported charge |
| Min precursor charge | 1 | Lower bound of charge scan |
| Max precursor charge | 4 | Upper bound of charge scan |
| Force isotope offset lookover | on | Scan all isotope offsets instead of stopping at first hit |
| Max isotope offset | 2 | Maximum ¹³C isotope offset to consider |
| Sequence selection criteria | Coverage | Criterion for choosing best PTM/charge variant |

### Tool Settings (per tool)

| Parameter | Default | Description |
|---|---|---|
| Max PPM | 50 | Precursor mass tolerance for accepting a match |
| Select PTMs | all | PTM candidates to enumerate in Step 3 |
| Max PTM combinations | 5 | Maximum number of simultaneous PTMs per sequence |
| Min Score | 0.8 | Minimum de novo score (tool-reported) |
| Min Ion Coverage | 25% | Minimum intensity coverage to accept an identification |
| Min Ions Covered | 5 | Minimum matched fragment ion count |
| Min Top-10 Peaks Covered | 1 | Minimum matched peaks among top-10 by intensity |
| Min Spectrum Peaks | 10 | Minimum number of peaks for a spectrum to be processed |
| Min Peptide Length | 7 | Minimum canonical sequence length |
| Max Peptide Length | 30 | Maximum canonical sequence length |
