# User Guide — Reports

## Overview

Reports in DASMixer are modules that produce analytical outputs from project data. Each report can generate:
- **Plots** — interactive Plotly figures
- **Tables** — DataFrames with analysis results

Reports are stored in the project file and can be viewed interactively, exported, or regenerated.

---

## Working with Reports (Reports Tab)

### Report List

The Reports tab shows all registered reports (built-in + plugins). Each report card contains:
- Report name and description
- Parameters form (if the report has configurable options)
- **Generate** button — runs the report and saves results
- **Preview** button — opens the most recent generated result in interactive mode
- History list — previous runs with timestamps; click to load, delete unwanted runs

### Generating a Report

1. Open the **Reports** tab
2. Configure parameters in the report's form (if present)
3. Click **Generate**
4. A progress indicator shows while the report runs
5. On completion, the result is saved to the project and shown in the preview

### Loading a Previous Report

Click on a timestamp in the report's history list to load that run. The preview updates to show the loaded result.

### Deleting a Report Run

Click the delete (trash) icon next to a history entry. Only the saved results are deleted; the report module itself remains available.

---

## Interactive Preview

Clicking **Preview** opens a PyWebView window showing the report's Plotly figures. In this window:
- Zoom, pan, hover for data points
- Toggle trace visibility in the legend
- Reset axes with double-click

The preview does not save any changes back to the project.

---

## Export

Each generated report can be exported to:

| Format | Content |
|---|---|
| **HTML** | Interactive Plotly plots + tables (self-contained, embeds Plotly.js) |
| **DOCX** | Static plots (PNG) + tables in Word format |
| **XLSX** | One Excel sheet per table |

To export: select a report run from history, then click **Export**. Choose output folder.

Export is also available via Python API:
```python
await report.export("/path/to/output/")
# creates: Report Name-20260101_120000.html, .docx, .xlsx
```

---

## Built-in Reports

### PCA Analysis

Principal component analysis on protein quantification data.

**Parameters:**
- LFQ method: algorithm to use for protein abundance values
- Subsets: which comparison groups to include

**Output:**
- PCA biplot (samples as points, protein loadings as vectors)
- Variance explained table
- Sample coordinates table

**Interpretation:** Samples from the same biological group should cluster together. Outliers visible in PCA may indicate technical problems.

### Volcano Plot

Differential expression analysis between two comparison groups.

**Parameters:**
- Group 1 / Group 2: the two groups to compare
- LFQ method: quantification values to use
- p-value threshold and fold change threshold
- Multiple testing correction method (Bonferroni, BH)

**Output:**
- Volcano plot (log2 FC on X, -log10 p-value on Y)
- Significantly up/down-regulated proteins table

**Interpretation:**
- Proteins in upper-right quadrant: upregulated in Group 2
- Proteins in upper-left quadrant: upregulated in Group 1
- Dashed lines: significance thresholds

### UpSet Plot

Visualizes the overlap of protein identifications between samples or groups.

**Parameters:**
- Grouping: by sample or by subset
- Minimum samples/subsets for inclusion

**Output:**
- UpSet diagram showing set intersections
- Counts for each intersection

### Coverage Report

Sequence coverage analysis for proteins across samples.

**Output:**
- Coverage heatmap (proteins × samples)
- Coverage distribution histogram

### Sample Summary

Per-sample statistics report.

**Output:**
- Table with spectra count, identification count, preferred count, coverage metrics
- Bar chart comparing samples

### Tool Match Report

Cross-tool comparison: how many spectra are identified by each tool and their overlap.

**Output:**
- Venn/UpSet diagram of tool identifications
- Per-tool statistics table
- Matched vs. unique identifications per tool

---

## Settings Affecting Reports

**Project Settings (Proteins tab):**
- Plot font size
- Plot width/height

These are applied globally to all generated figures.

**Saving plot settings** takes effect on the next report generation. Previously generated reports retain the settings from the time of generation.

---

## CLI Export

Reports can be generated and exported via CLI (planned feature). Currently, all report operations are GUI-only.

---

## Plugin Reports

Custom report modules can be installed via the Plugins panel. They appear in the same Reports tab alongside built-in reports. See [API Reference: Modules → Reporting](../api/modules.md#reporting-dasmixerapireporting) for plugin development details.
