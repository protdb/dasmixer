---
toc_depth: 3
---

# Core Concepts and Formulas

Understanding the core terminology used in DASMixer is important before starting your analysis, as some terms have specific meanings within the application that may differ slightly from other proteomics software.

## Tool

A **Tool** represents an identification search engine or *de novo* sequencing algorithm used to infer peptide sequences from mass spectra. Tools are created and configured by the user within a project and represent distinct sources of **Identifications** (see below). Each tool uses a designated parser (or "importer") to read external result files and transform them into DASMixer's internal representation.

## Sample

A **Sample** represents a single biological or technical proteomic sample. Samples are typically created automatically when importing spectral files, though a single sample can contain multiple spectral files.

Features and identifications from multiple spectral files within the same Sample are combined directly during protein inference and quantification. Therefore, you should **not** upload separate biological or technical replicates into a single sample. Instead, multi-file samples are intended for fractionated runs or split acquisitions of the same physical sample.

## Spectrum (Spectre)

In DASMixer, a **Spectrum** (internally referred to as `spectre` in database tables) is a single MS/MS fragmentation record consisting of $m/z$ and intensity arrays associated with a precursor ion. Every peptide identification must be linked to a precursor spectrum in order to be evaluated and stored in a DASMixer project.

## Identification

An **Identification** (commonly known as a PSM, or Peptide-Spectrum Match) is a candidate peptide sequence assigned to a spectrum by a search engine or *de novo* tool and imported into DASMixer.

Each identification is characterized by:

- The **Tool** that produced it
- The **Peptide sequence** in two forms:
  - `sequence`: includes post-translational modifications (PTMs) formatted in [HUPO-PSI ProForma notation](https://github.com/HUPO-PSI/ProForma), prioritizing human-readable modification names such as `[Phospho]` or `[Deamidated]` over numerical accession codes like `[UNIMOD:7]`
  - `canonical_sequence`: the unmodified amino acid sequence containing only standard canonical residues
- The original search engine **score** (and per-residue positional scores, if available)
- Physical and spectral matching characteristics calculated by DASMixer

## Identification Properties

DASMixer does not rely solely on target-decoy False Discovery Rate (FDR) statistics — which are unavailable for pure *de novo* sequencing. Instead, it models theoretical peptide fragmentation and evaluates how well the predicted fragment ions explain the experimental MS/MS spectrum.

This evaluation is performed during the **"Calculate ion coverage"** step, which computes several key metrics:

### Intensity Coverage (%)

The percentage of total fragment ion current in the experimental spectrum that is explained by matched theoretical peptide fragments:

$$I_c = \frac{\sum i_{\text{frag}}}{\sum i_{\text{all}}} \times 100$$

### PPM Error

The precursor mass error in parts per million (ppm), measuring the relative difference between the experimental precursor $m/z$ reported in the spectrum and the theoretical $m/z$ of the identified peptide sequence (accounting for PTMs and charge):

$$\text{PPM} = \frac{\text{Pepmass} - MZ_{\text{theor}}}{MZ_{\text{theor}}} \times 10^6$$

where $\text{Pepmass}$ is the experimental precursor $m/z$ and $MZ_{\text{theor}}$ is calculated as:

$$MZ_{\text{theor}} = \frac{\text{Mass}_n + \text{Charge} \times \text{Proton}}{\text{Charge}}$$

Here:

* $\text{Mass}_n$ is the neutral monoisotopic mass of the peptide sequence (including PTMs)
* $\text{Charge}$ is the precursor ion charge state
* $\text{Proton}$ is the mass of a proton ($1.007276\text{ Da}$)

### Peaks Covered and Top Peaks

**Peaks covered** (`ions_matched`) is the total number of experimental spectrum peaks matched to theoretical fragment ions. **Top peaks** (`top_peaks_covered`) counts how many of the 10 most intense peaks in the experimental spectrum are explained by theoretical fragments.

### Quality

**Identification Quality** is an index measuring the completeness of backbone bond cleavage coverage across the selected ion series, based on:

> Bern, M., Goldberg, D., McDonald, W. H., & Yates, J. R. (2004).
> *Automatic Quality Assessment of Peptide Tandem Mass Spectra.*
> **Bioinformatics**, 20(suppl_1), i49–i54.
> https://doi.org/10.1093/bioinformatics/bth947

$$Q = \frac{1}{N_{\text{types}}} \times \frac{N_{\text{match}}}{L - 1}$$

Where:

* $N_{\text{types}}$ is the number of fragment ion series selected (e.g., $2$ if only *b* and *y* ions are enabled; up to $6$ for *a, b, c, x, y,* and *z*)
* $N_{\text{match}}$ is the number of unique backbone cleavage positions matched per ion series. Duplicate matches of the same fragment with different charge states or neutral losses (e.g., `y6`, `y6++`, and `y6-NH3`) are counted as a single matched fragment ion
* $L$ is the amino acid length of the peptide sequence

### Longest Consecutive Run Ratio (LCRR)

**LCRR** measures the longest uninterrupted sequence of consecutive fragment ions of the same series found in the spectrum, normalized by the peptide length.

For example, consider a 10-amino-acid peptide with the following fragments matched to the experimental spectrum:

```
y2, y3, y3++, y4-NH3, y6, y7, y9, b2, b4, b5, b7
```

In this case, the LCRR value is `0.3`, because the longest consecutive run has length 3 (`y2, y3, y4`) and the peptide length is 10. Variants such as `y3` and `y3++` are treated as a single cleavage position (just as in the Quality metric), and `y5` is missing, which breaks the run.

### Unconfirmed PTMs

> **Note:** This metric is subject to further refinement in upcoming versions.

**Unconfirmed PTMs** represents the number of post-translational modifications present in the full peptide sequence that are not directly supported by matched fragment ions.

Because each fragment ion covers only a prefix or suffix of the precursor peptide, a sequence with good overall coverage may still lack fragment ions spanning one or more modified residues:

$$\text{Unconfirmed} = \text{PTM}(\text{peptide}) - \max_{i}\left(\text{PTM}(\text{fragment}_i)\right)$$

where $\text{fragment}_i$ is a matched fragment ion sequence, $\text{peptide}$ is the full precursor sequence, and $\text{PTM}(\cdot)$ counts the number of modifications in a ProForma sequence.

## Spectrum and Identification Correction

Experimental spectra and search engine outputs frequently suffer from annotation inaccuracies that DASMixer attempts to correct automatically during the ion coverage calculation step:

1. Missing or inaccurate precursor charge state in the spectrum metadata
2. Precursor mass shifts caused by C13 isotope peak picking (isotope offset)
3. Fixed or variable PTMs considered by a search engine (or absent in *de novo* output) that are not explicitly annotated in the sequence string
4. Unlocalized PTMs (particularly common in Waters PLGS outputs)

The first two issues cause large discrepancies between theoretical and experimental precursor $m/z$, while the third and fourth degrade fragment ion matching.

To address this, DASMixer's **SeqFixer** algorithm can:

- Minimize precursor PPM error by iterating over allowed precursor charge states and testing isotope offsets ($\pm n \times 1.003\text{ Da}$)
- Generate combinatorial PTM hypotheses on the peptide sequence to achieve an acceptable precursor PPM error while maximizing fragment intensity coverage

These correction steps are enabled in the pipeline by default and can be finely tuned or disabled per tool.

## Preferred Identifications

The **Preferred Identification** is one of the central concepts in the DASMixer workflow.

When integrating multiple tools — especially *de novo* sequencing engines that generate a candidate sequence for nearly every spectrum — not every identification is reliable. Furthermore, because multiple tools may identify the same spectrum, simply pooling all identifications would artificially inflate spectral counts and bias protein quantification. The Preferred Identification step solves both filtering and deduplication:

1. **Quality Filtering:** An identification can only become preferred if **all** of its calculated metrics pass the user-defined thresholds configured for its tool (e.g., maximum PPM error, minimum intensity coverage, minimum quality, minimum score).
2. **Cross-Tool Selection:** If two or more identifications for the same spectrum pass their respective tool thresholds, only the single best identification is marked as preferred, based on the global selection criterion (either highest **Intensity Coverage** or lowest absolute **PPM** error).
3. **Tie-Breaking:** If two tools produce identical sequences that tie on the selection criterion, the preferred flag is assigned to the first tool in project order. (While this does not affect downstream protein inference, tied sequences are counted as found by **"Both"** tools in the Tool Match Report).

**In summary:** A preferred identification is an identification that satisfies all quality thresholds for its tool and explains its spectrum better than any competing identification from other tools.

Only **preferred identifications** are used downstream to infer protein identifications and calculate protein abundance (LFQ). Preferred identifications that do not map to any known database protein can also be investigated as potential novel proteoforms, splice variants, or endogenous peptidome components.

## Protein Mapping

Database search engines naturally link every identified peptide to a protein accession from the search FASTA, whereas *de novo* sequencing tools output only amino acid sequences without protein context. DASMixer bridges this gap by mapping peptide sequences against a user-provided FASTA protein database.

Uploading a FASTA database is also strongly recommended even when working exclusively with database search results, because identification files rarely include full-length protein sequences — which are required to calculate protein sequence coverage and theoretical observable peptides for emPAI and iBAQ quantification.

Protein mapping is powered by the `npysearch` library:

> Schmid S, Jeevannavar A, Julian TR, Tamminen M (2023).
> *Portable BLAST-like algorithm library and its implementations for command line, Python, and R.*
> **PLoS ONE** 18(11): e0289693.
> https://doi.org/10.1371/journal.pone.0289693

### Protein Identity

**Protein Identity** defines the minimum sequence similarity required between an identified peptide's canonical sequence and a candidate region in the protein database. It ranges from `0.0` to `1.0`, where `1.0` requires an exact 100% match.

### De Novo Correction

DASMixer provides a **De Novo Correction** mode designed to rescue *de novo* identifications that contain minor sequencing errors (such as isobaric dipeptide swaps or single-residue inaccuracies). To use this mode, set the tool's **Min protein identity** below `1.0` (typically `0.7`–`0.8`) and enable **De novo correction**.

When a partial match ($1.0 > \text{identity} \ge \text{threshold}$) is found in the FASTA database, the database sequence is called the `matched_sequence`. Because the original canonical sequence and the `matched_sequence` differ, DASMixer re-evaluates the `matched_sequence` against the experimental MS/MS spectrum:

- Recalculates precursor PPM error
- Re-runs fragment ion matching, transferring or re-allocating PTMs from the original sequence if modification sites have changed

If the `matched_sequence` achieves a PPM error and fragment intensity coverage that are as good as or better than the original *de novo* sequence (according to the selected **Match correction criteria**), the protein match is accepted. Moreover, if the original *de novo* sequence failed preferred selection thresholds solely due to precursor PPM error, the corrected match can qualify the identification as preferred during a subsequent Preferred Selection pass.

### Amino Acid Substitutions

Using the same partial-matching mechanism, DASMixer can also flag potential **Amino Acid Substitutions** (SAPs / mutations). However, AA substitution detection looks for the opposite outcome from *de novo* correction.

An amino acid substitution is suspected when:

1. The original *de novo* sequence is high-quality and passes preferred identification criteria,
2. The closest protein database match is inexact ($\text{identity} < 1.0$), **and**
3. Replacing the *de novo* sequence with the canonical database `matched_sequence` results in a **worse** explanation of the experimental spectrum (e.g., significantly higher PPM error and loss of fragment ion coverage).

In other words, the experimental spectrum genuinely supports a sequence that differs from the reference proteome. An example is illustrated below:

![Amino acid substitution example](img/aa_substitution.png)

> **AA substitution ion coverage example.** Top: fragmentation spectrum annotated with the sequence identified by PowerNovo2. Bottom: the same spectrum annotated with the closest reference protein match ($\text{identity} = 0.92$). Switching to the reference sequence causes the loss of nearly the entire *y*-ion series, a large precursor PPM error, and a sharp drop in intensity coverage ($I_c$).

> **Note:** The AA substitution detection algorithm is experimental and will be refined in future versions. Any candidate substitutions flagged by DASMixer should be manually inspected on the fragment spectrum plot before drawing biological conclusions.

### Unique Evidence

If a peptide sequence maps to **one and only one** protein entry in the FASTA database, it is marked as **Unique Evidence** (`unique_evidence = True`) for that protein's presence in the sample.

## Protein Identifications

From the set of preferred identifications mapped to proteins in each sample, DASMixer compiles the list of identified sample proteins. By default, a protein is considered identified in a sample if it is supported by:

- At least **2** preferred peptide identifications (`Min peptides = 2`)
- At least **1** unique peptide identification (`Min unique peptides = 1`)

Both thresholds can be adjusted by the user on the **Proteins** tab.

### Label-Free Quantification

**Label-Free Quantification (LFQ)** estimates the relative (and optionally absolute) abundance of identified proteins within each sample. DASMixer implements four complementary LFQ algorithms (**emPAI**, **iBAQ**, **NSAF**, and **Top3**) along with two calibration strategies for converting relative abundances into absolute mass or molar concentrations. These methods are described in detail on the [LFQ Methods](lfq.md) page.
