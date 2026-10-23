# Working with Proteins (Proteins Tab)

The **Proteins** tab provides controls for protein inference, metadata enrichment from UniProtKB, and Label-Free Quantification (LFQ), followed by interactive tables and protein abundance plots similar to those on the [Peptides tab](peptides_table.md).

![Proteins tab header](img/proteins_tab_head.png){data-description="Proteins tab header — Protein Detection, LFQ, and UniProt enrichment configuration cards."}

## Controls and Settings

The top of the **Proteins** tab is divided into three configuration and action cards:

### 1. Protein Detection

- **Minimum peptides:** The minimum number of distinct preferred peptide identifications mapped to a protein in a sample required to consider that protein present (default: `2`).
- **Minimum unique peptides:** The minimum number of preferred identifications in a sample that map *exclusively* to this protein (default: `1`).
- **Calculate protein identifications:** Aggregates preferred peptide matches per sample and builds the list of identified proteins along with peptide counts, unique evidence counts, sequence coverage, and summed peptide intensities.

### 2. Label-Free Quantification (LFQ)

- **Methods:** Select one or more [LFQ algorithms](../lfq.md) to compute for each sample:
  - **emPAI** (Exponentially Modified Protein Abundance Index)
  - **iBAQ** (Intensity-Based Absolute Quantification)
  - **NSAF** (Normalized Spectral Abundance Factor)
  - **Top3** (Mean intensity of the top 3 most intense peptides)
- **emPAI base value:** The exponential base used in the emPAI formula (default: `10.0`).
- **Enzyme, Min/Max peptide length, Max cleavage sites:** Because **emPAI** and **iBAQ** normalize by the number of theoretically observable peptides ($N_{\text{observ}}$), DASMixer performs an *in silico* enzymatic digestion of each protein sequence. Set these parameters to match your experimental sample preparation (default: `Trypsin`, length `7–30` AA, max `2` missed cleavages).
- **Abs. concentrations / Set references:** Enable conversion of relative LFQ values into absolute mass ($\text{g/L}$) and molar ($\text{mol/L}$) concentrations using total protein or internal standard references. See [Absolute Concentrations Settings](advanced/abs_concentrations.md) for a step-by-step configuration guide.
- **Calculate LFQ:** Runs the selected quantification algorithms across all samples.

### 3. Enrich Protein Metadata from UniProtKB

- **Overwrite names from FASTA:** Replace protein names and gene symbols parsed from the local FASTA file with current canonical entries from UniProtKB.
- **Force update:** Re-fetch UniProtKB records even for proteins that have already been enriched.
- **Enrich protein data from UniProt:** Queries the online UniProtKB API for all identified proteins to retrieve gene names, protein descriptions, molecular weights, functional annotations, subcellular locations, and pathways.

## Recommended Processing Order

Always run the protein-level steps in the following sequence:

1. **Verify preferred identifications:** Ensure you have completed the pipeline on the **Peptides** tab and have a reasonable number of preferred identifications mapped to proteins.
2. **Run "Calculate protein identifications":** Identifies proteins per sample based on your minimum peptide and unique evidence thresholds.
3. **Run "Enrich protein metadata from UniProtKB" *(optional)*:** Particularly important if you imported protein accessions directly from search engine files without loading a full `.fasta` sequence database, as LFQ methods require protein sequences and molecular weights.
4. **Run "Calculate LFQ":** Computes relative (and optional absolute) protein abundances for all identified proteins.

## Important Notes

1. **Preferred identifications only:** Protein inference and LFQ use **only** preferred identifications. Competing non-preferred PSMs are ignored so each spectrum contributes at most once.
2. **Tool-agnostic aggregation:** Preferred identifications from all tools (database search and *de novo*) are pooled together when inferring proteins and computing LFQ.
3. **Dependency order:** You must re-run **Calculate protein identifications** before **Calculate LFQ** whenever peptide matches or detection thresholds change.
4. **Internet connection:** UniProtKB enrichment requires an active internet connection.
5. **Scope of UniProt enrichment:** Only proteins that pass the current **Protein Detection** thresholds are queried against UniProtKB. If you later relax the minimum peptide thresholds and detect additional proteins, run the enrichment step again.
6. **When enrichment can be skipped:** If you already imported a complete UniProt `.fasta` file on the Peptides tab and do not need extra functional annotations, you can proceed directly from protein detection to LFQ.

## Viewing Protein Data

> **Important:** After running protein calculations, expand the **Filters** block above the table and click **Apply filters** to load or refresh the table rows.

The **Proteins** tab provides two table modes, which you can switch between using the segmented toggle button:

![Table switcher](img/table_switch.png){data-description="Segmented toggle to switch between Identifications and Statistics table views."}

- **Identifications table:** Displays one row per **protein per sample**, showing the sample name, comparison group, peptide count, unique evidence count, sequence coverage (%), summed intensity, and calculated LFQ values (`emPAI`, `iBAQ`, `NSAF`, `Top3`).
- **Statistics table:** Aggregates data to one row per **unique protein across the entire project**, summarizing how many samples and comparison groups contain the protein alongside its gene name and description.

![Protein Identifications table](img/protein_ids_table.png){data-description="Protein Identifications table — one row per protein per sample with peptide counts, coverage, and LFQ values."}

![Protein Statistics table](img/protein_stats_table.png){data-description="Protein Statistics table — one row per unique protein across the project with occurrence counts."}

Just like on the Peptides tab, you can filter rows, customize visible columns via the **⚙️** button, and export the filtered table to **CSV** or **XLSX**.

## Protein Abundance Plots

Clicking the plot icon (**📈**) on any row in either the **Identifications** or **Statistics** table generates a comparative abundance chart for that protein across your comparison groups:

![Protein concentration plot](img/proteins_plot.png){data-description="Protein abundance box plot comparing LFQ values across comparison groups."}

Expanding the **Plot settings** panel above the figure allows you to customize the chart:

- **LFQ method:** Choose which quantification algorithm (`emPAI`, `iBAQ`, `NSAF`, or `Top3`) to plot.
- **Plot type:** Switch between a **Box plot** and a **Violin plot**.
- **Appearance:** Customize the plot title and toggle whether individual sample data points are overlaid on the distributions.
- **Value type:** Choose between **Relative** abundance, **Absolute (g/L)** mass concentration, or **Absolute (mol/L)** molar concentration (when [Absolute Concentrations](advanced/abs_concentrations.md) have been calculated).
- **Unit multiplier:** When plotting absolute concentrations, scale units automatically (e.g., from $\text{g/L}$ to $\text{mg/L}$, $\mu\text{g/L}$, $\text{ng/L}$, or $\text{nmol/L}$).
- **Outlier filtering:** Automatically exclude extreme sample values that deviate from the group median by more than a specified factor.
- **Subset selection:** Check or uncheck which comparison groups are included in the figure.

![Protein plot settings](img/protein_plot_settings.png){data-description="Protein plot settings panel — LFQ method, plot type, value type, unit multiplier, and subset selection."}

Click **Apply settings** after modifying any option to redraw the plot. Like peptide spectrum plots, protein plots can be copied to the clipboard, saved to the project (**Save to project**), exported as **SVG/PNG**, or inspected in the **Interactive** viewer.

## Next Steps

The **Proteins** tab gives you a comprehensive view of sample-level protein identifications, cross-group occurrence, and individual protein abundance distributions. Once protein identification and LFQ calculations are complete, proceed to the [Reports tab](reports.md) to run project-wide statistical analyses, tool comparisons, PCA, UpSet intersections, and Volcano plots.
