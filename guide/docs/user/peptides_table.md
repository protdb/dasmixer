# Preview peptide data

Information about spectre, identification and protein match is shown in the "Search and view identifications" section in the bottom of peptides tab:

![collapsed peptides table](img/peptides_table_collapsed.png)

it consists of four collapsible blocks:

- Peptide identifications:
  - Filters
  - Data
- Ion match plot:
  - Plot settings
  - Plot preview

All the blocks can be extended by clicking on its header. Expanded view of the Filters and Data section shown on the image below:

![expanded peptide data](img/peptides_table_expanded.png)

## Filtering data

You can filter table data by any combination of the controls:

- Identification ID (internal ID in DASMixer project)
- Sample
- Specrte index in file (Spectre Seq #)
- Spectre Scans index
- Spectre internal ID (Spectrum ID)
- by preferred flag (All: ignore preferred in filtering; Yes: show only preferred records; No: show only not preferred records)
- Tool
- Min PPM (absolute PPM error)
- Part of the sequence or canonical sequence (Sequence contains/Canonical sequence contains)
- Min [Quality](../concepts.md#quality) value
- Max per-PSM FDR value
- Protein ID
- Gene
- Protein identified flag
- Sequence identified flag
- Has PTM flag
- Has AA substitution flag

Enter values to filter and press "Apply filters" button. You also need to press this button after calculation is finished to update data in the table.

Some column in the table (Spectrum ID, Scans, ID, Protein) can be clicked to filter by the value in column. Clickable values are shown in hyperlink style with blue color and underline.
Click on such column will add the value to the filter and apply it immediately without cleaning other filters.

## Hidden columns

Some columns in the table are not shown by default but can be useful in some cases. There is a "⚙️" button on the top right corner of the table.
It enables selection of visible fields in the table. You can hide current fields by deselecting them and show hidden fields by selecting

![img.png](img/peptides_table_fields.png)

## Count and export

Below the table, there are useful set of controls:

![peptide table controls](img/peptides_table_controls.png)

- Amount of records with given filters: "Showing 1-20 of XXXXX rows..." where XXXXX is total amount of lines matching filters.
- "Export" button: allows you to export all data from table. 
- "Rows per page" dropdown list let you choose the size of displayed table page.
- To show next or previous page of the table, you can use arrows in the right corner

Important notes about export:

![export dialog](img/export_dialog.png)

- For large projects, export can be slow, even opening the exprot setting window can take some time.
- You can choose the format of exporting table. CSV (values in plain text separated by comma) or XLSX (Microsoft Excel native format).
- If "Technical headers" flag has been checked, the table will contain less human-readable (but better machine-readable) headers row: e.g. protein_id instead of Protein ID.

> **Hint:**
> 
> if you export data to supliment the manuscript or to investigate yourself in Excel, select XLSX format and do not check "technical headers" flag.
> 
> If you need this export to process programmatically, export it as CSV with technical headers.


## Filtering use cases

Some filters combinations are not obvious but may lead to useful insights.
There are a few examples that should help you better understand how to use filtering in peptides table.

### Find fine peptides not matched to the proteins

Set "Preferred" to "Yes" and "Protein identified" to "No".

### Find all phosphorylated peptides

Simply enter "Phospho" to "Sequence contains" field

### Find all AA substitution for specific protein

Fill "Gene" or "Protein ID" field and set "AA substitution" to "Yes"

## Plotting fragments

in the most right column of the table, there is plot icon (📈) for every row. Clicking on this icon will result in fragmentation plot appearance below the table.

First, you will see the loader in the "Plot preview" section:

![peptide plot preview](img/peptide_plot_preview.png)

When ready, the plot will be displayed:

![peptide plot displayed](img/peptide_plot_displayed.png)

Plot displays fragment of each type with separated colors. unmapped peaks remain gray.

> **Note**: plot is generated based on current window size to bi as large as possible while fitting in the app window. 
> To make plot bigger, maximize the window and generate it again.
> 
> And to make smaller plot, you can make DASMixer window smaller and generate it again

If there are more than one identification for a given spectra, all identifications will be displayed in rows on the plot.

Plot can be handled in the following ways:

- Copy (to clipboard). Note that in Linux clipboard requires xclip or wl-clipboard installed in your system.
- Save to project: save plot to export with other plots in future
- Export: save plot as SVG or PNG file on your computer
- Interactive: open in interactive view separate window

> Hint: export plot as SVG if you need high resolution for printing.
> Editorial offices can accept SVG format itself, or you can convert it to PNG/JPG/any other image format using GIMP, Inkscape or just by searching "SVG to PNG converter online" in the internet.

Interactive mode opens your plot in separate window when you can zoom and inspect plot to get more details:

![interactive peptide plot](img/peptide_plot_interactive.png)

> Note: interactive mode may not work properly in some systems. If no window appears in reasonable time, go to settings and change "Plot and report view mode" to "browser (default)" and restart DASMixer.
> 
> Note 2: On Linux systems, you may encounter error "not found"/"not allowed" in browser after changing "Plot and report view mode" 
> to browser if your browser is installed via Snap. Change the "Temporary files directory" to some location having no hidden folders (like .cache) in its path.
> 
> Note 3: There is also "Plot aspect ratio" parameter in the settings changing proportions of the plots generated by system. You can adjust it to get less wide plots.

## Plot configuration

between the table and the plot view, there is also collapsible block called "Plot settings":

![peptide plot settings](img/peptide_plot_settings.png)

Here you can:

- Control whether overall plot title is displayed ("show title")
- Add sequences of protein mapping to the plot (useful for identifications after de novo correction or with amino acid substitutions)
- add parameters to display in subplot title.

After changing any of these parameters, click "Apply settings" button to redraw the plot.

> One more note: Changing the parameters in "Ion mapping settings" applies to the plot too, but without re-calculation of "Ion coverage", values like Ion coverage and quality will not be chenged


## Conclusions to make

Commonly you cannot review all the specra yourself to strictly verify every PSM is good enough.
But you can check limited amount of identifications, both preferred and not preferred to make sure that 
most of the preferred identifications you encounter are satisfying and most of non-preferred are not.
You can also check the amount of preferred identifications by tool and in total to make sure that 
it's enough to preceed with protein identifications.

If you're not agree with the system, you can adjust preferred parameters for tools or even change ion mapping parameters and recalculate the data. Or even make a decision to rerun search or even reinitialize the MS/MS experiment itself.

When you see that identifications are processed well, you can proceed to [proteins tab](proteins_tab.md)