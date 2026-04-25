# GUI Architecture

## Overview

The GUI is built with **Flet 0.80.5** — a Python framework that renders Flutter controls. All GUI code is in `dasmixer/gui/`.

Key architectural points:
- **Event-driven async**: all user actions are async methods, running in the Flet event loop
- **Manual routing**: `DASMixerApp._route_change()` instead of `page.go()` (which is async in 0.80.5 and not safe from `__init__`)
- **Lazy tab loading**: project tabs are built only when first selected
- **Suspend/resume**: heavy tabs are paused when not visible to reduce Flet reconciliation cost

---

## Application Controller (`gui/app.py`)

`DASMixerApp` is instantiated once per application run. It owns:
- `self.page: ft.Page` — root Flet page
- `self.current_project: Project | None` — currently open project

### Initialization Sequence
1. Configure page (title, size, theme, icon)
2. Register `page.on_route_change` and `page.on_view_pop`
3. If `initial_project_path` provided: schedule `_open_initial_project` via `page.run_task`
4. Otherwise: call `_route_change()` directly to render start view

### Routing

Routes are implemented as a **view stack** (`page.views`), not URL routing:

| Route | View | When |
|---|---|---|
| `/` | `StartView` | No project open |
| `/project` | `ProjectView` | Project open |
| `/settings` | `SettingsView` | Pushed onto stack |
| `/plugins` | `PluginsView` | Pushed onto stack |

`_route_change()` clears the view stack, adds the base view (start or project), then appends any secondary view if route matches.

`_navigate_to(route)` — sets `page.route` and calls `_route_change()` manually.

### Project Lifecycle in GUI

| Method | Description |
|---|---|
| `new_project()` | FilePicker save dialog → create Project → add default "Control" subset → show project view |
| `open_project_dialog()` | FilePicker open dialog → `open_project()` |
| `open_project(path)` | Close current if open → open Project → show project view |
| `close_project()` | Close Project → show start view |

**FilePicker usage** (Flet 0.80.5):
```python
file_path = await ft.FilePicker().save_file(...)   # returns str | None
files = await ft.FilePicker().pick_files(...)       # returns list[FilePickerResultFile] | None
```
No overlay registration needed.

### AppBar

Top bar with two popup menus:
- **File**: New Project, Open Project, Close Project, Exit
- **Options**: Settings, Plugins

---

## Views (`gui/views/`)

### StartView (`views/start_view.py`)

Displayed when no project is open. Contains:
- "New Project" button
- "Open Project" button  
- List of recent projects (from `config.recent_projects`)

### ProjectView (`views/project_view.py`)

Main workspace. Wraps a `ft.Tabs` widget with 5 tabs:

| Index | Label | Icon | Module | Class |
|---|---|---|---|---|
| 0 | Samples | `SCIENCE` | `tabs.samples` | `SamplesTab` |
| 1 | Peptides | `BIOTECH` | `tabs.peptides` | `PeptidesTab` |
| 2 | Proteins | `BUBBLE_CHART` | `tabs.proteins` | `ProteinsTab` |
| 3 | Reports | `ASSESSMENT` | `tabs.reports` | `ReportsTab` |
| 4 | Plots | `SHOW_CHART` | `tabs.plots` | `PlotsTab` |

**Lazy loading:** Only tab 0 (Samples) is built on project open. Other tabs are built on first selection via `_build_tab(index)` using `importlib.import_module`.

**Suspend/resume:** Tabs 1 (Peptides) and 2 (Proteins) are "heavy" — they contain `BaseTableView` and `BasePlotView` components. When switching away:
- `_collect_suspendable(control)` recursively finds all such components
- Each calls `.suspend()` — replaces rendered content with lightweight placeholders
- On return: `.resume()` — restores from internal cached data without DB query

### SettingsView (`views/settings_view.py`)

Application settings: theme, window size, batch sizes. Settings saved to `AppConfig`.

### PluginsView (`views/plugins_view.py`)

Plugin management panel. Shows loaded plugins with status (enabled/error). Allows:
- Install plugin from `.py` or `.zip` file
- Enable/disable plugins
- Delete plugins

### ManageSamplesView (`views/manage_samples_view.py`)

Secondary view for sample management: bulk group assignment, outlier marking.

---

## Tab Structure (`gui/views/tabs/`)

### SamplesTab (`tabs/samples/`)

Sections:
- **SubsetsSection** — list of comparison groups with edit/delete; add new group button
- **ToolsSection** — list of identification tools with edit/delete; add new tool button  
- **SamplesSection** — expandable sample panels showing status (spectra files, identification files, counts). Each panel has:
  - Header: sample name, status indicator (OK/WARNING/ERROR), stats
  - Body: tree of spectra files → identification files with counts
  - Actions: import spectra, import identifications, delete

### PeptidesTab (`tabs/peptides/`)

Sections:
- **PeptidesSection** — paginated table of identifications with filters; export button
- **IonMatchSection** — ion match settings (ion types, tolerance, losses) + action button
- **PreferredSection** — preferred identification settings + action button
- **PlotSection** — spectrum ion annotation plot viewer (select spectra file + spectrum number)

### ProteinsTab (`tabs/proteins/`)

Sections:
- **ProteinMappingSection** — FASTA file selection, mapping parameters, action button
- **LFQSection** — LFQ method selection, digestion parameters, action button
- **ProteinResultsSection** — paginated protein results table with filters; statistics table
- **ProteinStatisticsSection** — cross-sample protein statistics

### ReportsTab (`tabs/reports/`)

For each registered report:
- Report name, description, icon
- Parameters form (if report has `parameters = ReportForm subclass`)
- Generate button, Preview button
- List of previously generated report instances with Load and Delete actions

### PlotsTab (`tabs/plots/`)

Gallery of saved plots with preview and export options.

---

## Components (`gui/components/`)

### BaseTableView (`components/base_table_view.py`)

Reusable paginated table component. Features:
- `load_data(data: pd.DataFrame)` — render rows into `ft.DataTable`
- `suspend()` / `resume()` — replace DataTable with placeholder on suspend, restore on resume
- Pagination controls (previous/next, page number)
- Column configuration (width, sortable)

### BasePlotView (`components/base_plot_view.py`)

Reusable plot container. Features:
- `load_figure(fig: go.Figure)` — render Plotly figure via `PlotlyViewer`
- `suspend()` / `resume()` — replace viewer with placeholder

### BaseTableAndPlotView (`components/base_table_and_plot_view.py`)

Combines `BaseTableView` and `BasePlotView` side by side or stacked.

### PlotlyViewer (`components/plotly_viewer.py`)

Embeds Plotly figures in a Flet view using **PyWebView**. Converts `go.Figure` to HTML (with embedded Plotly.js) and displays in a native WebView panel.

Key method: `show_figure(fig: go.Figure)` — renders figure to HTML and loads in WebView.

### ProgressDialog (`components/progress_dialog.py`)

Modal progress dialog for long-running async operations. Shows a progress bar and current status text. Used during spectra import, identification processing, protein mapping.

### ReportForm (`components/report_form.py`)

Base class for typed report parameter forms. Subclasses define fields (typed Python attributes with defaults) that are rendered as Flet form controls and returned as a typed dict.

---

## Actions (`gui/actions/`)

Action classes bridge GUI events to API calls. They handle:
- Progress reporting (via `ProgressDialog`)
- Error handling and user feedback (via `show_snack`)
- Async orchestration across multiple API calls

| Class | File | Purpose |
|---|---|---|
| `IonActions` | `actions/ion_actions.py` | Ion coverage calculation (ProcessPoolExecutor) |
| `LFQAction` | `actions/lfq_action.py` | LFQ quantification |
| `ProteinIdentAction` | `actions/protein_ident_action.py` | Build protein identification results |
| `ProteinMapAction` | `actions/protein_map_action.py` | Run protein mapping (npysearch) |

---

## Utilities (`gui/utils.py`)

```python
show_snack(page, message, color)  # Display snackbar notification
```

---

## Flet 0.80.5 API Compatibility

| Old API (broken) | New API (correct) |
|---|---|
| `ft.DropdownOption(...)` | `ft.Dropdown.Option(...)` |
| `ft.alignment.center` | `ft.Alignment.CENTER` |
| `ft.colors.RED` | `ft.Colors.RED` |
| `ft.icons.ADD` | `ft.Icons.ADD` |
| `page.window_width` | `page.window.width` |
| `page.go("/route")` (in `__init__`) | `self._route_change()` |
| `ft.FilePicker` as page overlay | `await ft.FilePicker().pick_files(...)` |

All Flet code in the project has been updated to 0.80.5 API.
