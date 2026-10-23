# DASMixer User Guide

**DASMixer** is a cross-platform desktop application for integrating and comparing peptide identification data from mass spectrometry experiments. 
It merges *de novo* sequencing results with database search identifications, performs complete comparative proteomics workflows, and produces publication-ready interactive and static reports.

Developed at the **Laboratory of Structural Proteomics, IBMC, Moscow**.

![DASMixer logo](img/logo_big.png)

## Reading the Guide

* [Use cases and publications **TBD**]()
* [Features and capabilities **TBD**]()
* [Core concepts and formulas](concepts.md)
* [Label-Free Quantification (LFQ) methods](lfq.md)
* [Installation](installation.md)
* **User Guide:**
  1. [Projects and samples](user/project_sample.md)
  2. [Processing identifications](user/peptides_tab.md)
  3. [Viewing identification data](user/peptides_table.md)
  4. [Protein processing](user/proteins_tab.md)
  5. [Reports](user/reports.md)
  6. [Saved plots](user/plots_tab.md)
  7. [Data export](user/export_tab.md)
  8. [Settings and plugins](user/configuration.md)
  9. [System menus (File & Options)](user/system_menus.md)
* **Advanced Topics:**
  * [MaxQuant project import](user/advanced/MaxQuant.md)
  * [PRIDE dataset import](user/advanced/pride_import.md)
  * [PTM configuration](user/advanced/ptm_configuration.md)
  * [Absolute concentrations settings](user/advanced/abs_concentrations.md)
  * [Command-line interface (CLI)](user/advanced/cli.md)
* **Programming with DASMixer (Developer Guide):**
  * **API and Architecture:**
    * [Modules and architecture](developer/architecture.md)
    * [dasmixer-core library and API](developer/core_api.md)
    * [Project file structure](developer/project_structure.md)
  * **Examples:**
    * [Running an end-to-end workflow](developer/example_pipeline.md)
    * [Creating a peptide spectrum plot](developer/example_plots.md)
  * **Plugin Guide:**
    * [Creating an identification importer](developer/custom_importers.md)
    * [Creating a custom report](developer/custom_reports.md)
* [Development Roadmap](roadmap.md)
