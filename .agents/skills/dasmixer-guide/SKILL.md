---
name: dasmixer-guide
description: This skill should be used when writing, extending, updating, or reviewing the DASMixer MkDocs user and developer guide in `guide/`. Activates when the user asks to document new features, GUI tabs, CLI commands, reports, parsers, or API changes in the guide.
---

# DASMixer Guide Extension & Maintenance Skill

Use this skill whenever you create, extend, or update documentation in `guide/` for the DASMixer project.

---

## 1. Overview & Architecture of `guide/`

The official DASMixer manual is built with **MkDocs** (`mkdocs-material` theme) and lives in `guide/`:

- `guide/mkdocs.yml` — Site configuration, navigation (`nav`), Markdown extensions (`pymdownx.arithmatex`, `pymdownx.superfences` with `mermaid`, `mdx_truly_sane_lists`, `attr_list`), and plugins (`glightbox`).
- `guide/docs/` — Markdown documentation sources:
  - `index.md`, `installation.md`, `concepts.md`, `lfq.md`, `roadmap.md`
  - `user/` — End-user GUI and workflow documentation (`project_sample.md`, `peptides_tab.md`, `peptides_table.md`, `proteins_tab.md`, `reports.md`, `plots_tab.md`, `export_tab.md`, `configuration.md`)
  - `user/advanced/` — Advanced user workflows (`MaxQuant.md`, `pride_import.md`, `ptm_configuration.md`, `abs_concentrations.md`, `cli.md`)
  - `developer/` — External developer & plugin author documentation (`architecture.md`, `core_api.md`, `project_file.md`, `examples_workflow.md`, `examples_plots.md`, `custom_importers.md`, `custom_reports.md`)

**Important:** Do **not** touch or move internal development specs, changelogs, or reviews in `docs/project/` (`spec`, `changes`, `review`) or `docs/obsolete/`. Those remain internal to `docs/`.

---

## 2. Target Audience & Tone

1. **Language:** Always write in clear, natural **English**.
2. **User Guide (`user/` and root pages):**
   - **Audience:** Proteomics researchers and domain scientists who are not software engineers.
   - **Style:** Practical, approachable, and well-structured — neither overly casual/frivolous nor dryly academic. Explain *why* a parameter or step matters in terms of mass spectrometry and proteomics, not internal code mechanics.
3. **Developer Guide (`developer/`):**
   - **Audience:** External Python developers who want to automate workflows using `dasmixer-core`, inspect `.dasmix` project files, or write plugins (`IdentificationParser`, `BaseReport`).
   - **Style:** Concise technical prose with complete, runnable, copy-pasteable code examples synchronized with current API signatures.

---

## 3. Workflow for Extending the Guide

### Step 1: Synchronize with the Codebase
Never rely on outdated specs or assumptions. Before writing or updating a page:
- Inspect the relevant GUI view/tab in `dasmixer-gui/src/dasmixer/gui/views/` to verify exact control labels, dropdown options, default values, and dialog flows.
- Inspect the relevant CLI command in `dasmixer-cli/src/dasmixer/cli/commands/` for exact argument and option names.
- Inspect the core API in `dasmixer-core/src/dasmixer/api/` or `dasmixer-core/src/dasmixer/reports/` for method signatures, dataclass fields, and report parameters.

### Step 2: Write / Update Markdown Content
- Follow the formatting conventions configured in `guide/mkdocs.yml`:
  - Nested lists use **2-space indentation** (`mdx_truly_sane_lists: nested_indent: 2`).
  - Math formulas use Arithmatex/MathJax syntax: `$inline$` and `$$block$$`.
  - Diagrams use fenced `mermaid` code blocks.
- When documenting new GUI views or dialogs that do not yet have screenshots in `guide/docs/user/img/`, add a clear placeholder callout especificarion what screenshot is needed, the suggested file path (e.g., `user/img/<name>.png`), and what UI elements should be visible in it.

### Step 3: Update Navigation
If you add a new `.md` file:
1. Add it to the appropriate section in `guide/mkdocs.yml` under `nav:`.
2. Add a corresponding link to the overview table of contents in `guide/docs/index.md`.

### Step 4: Verify the Build
Always run MkDocs in strict mode to verify that all internal links, image paths, and Markdown extensions build cleanly:

```bash
poetry run mkdocs build --strict
```
(Run with `workdir="/home/gluck/PycharmProjects/dasmixer/guide"`). Fix any warnings or broken links before finishing.
