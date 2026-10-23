# Creating Custom Reports

## Overview

DASMixer reports are Python modules that produce analytical outputs (interactive Plotly plots and Pandas tables) from project data. Custom reports can be installed as **plugins** (`.py` files or `.zip` packages placed in `{app_dir}/plugins/reports/` or installed via **Options → Plugins**) or developed directly in the source tree.

Each report consists of up to four components (which can live in a multi-file package or a single `.py` file):

| Component | Purpose |
|---|---|
| `params.py` | Typed parameter dataclass inheriting from `ReportParams` |
| `form.py` | GUI parameter form (optional — only loaded when `dasmixer-gui` is installed) |
| `report.py` | Report calculation and plotting logic — `BaseReport` subclass |
| `__init__.py` | Re-exports the report class (for multi-file packages) |

---

## Single-File Report Plugin (Quick Start)

For a standalone plugin file in `{app_dir}/plugins/reports/`, place all components in one `.py` file and call `registry.register()` at the bottom:

```python
# my_plugin_report.py
from __future__ import annotations

from dataclasses import dataclass, field
import pandas as pd
import plotly.graph_objects as go

from dasmixer.api.reporting.report_params import ReportParams
from dasmixer.api.reporting.base import BaseReport
from dasmixer.api.reporting.registry import registry
from dasmixer.api.reporting._icons import Icons


# 1. Typed Parameters Dataclass
@dataclass
class MyPluginParams(ReportParams):
    threshold: float = 0.5
    show_details: bool = True
    name_template: str = field(default="{date} {time}")


# 2. Optional GUI Form (guarded for headless / CLI compatibility)
try:
    from dasmixer.gui.components.report_form import (
        ReportForm,
        FloatSelector,
        BoolSelector,
    )

    class MyPluginForm(ReportForm):
        params_class = MyPluginParams
        threshold = FloatSelector(default=0.5, label="Threshold")
        show_details = BoolSelector(default=True, label="Show details")

    _parameters = MyPluginForm
except ImportError:
    _parameters = None


# 3. Report Implementation
class MyPluginReport(BaseReport):
    name = "My Custom Report"
    description = "An example custom report with configurable threshold"
    icon = Icons.REPORT
    params_class = MyPluginParams
    parameters = _parameters
    name_template = "{threshold} {date} {time}"

    async def _generate_impl(
        self, params: MyPluginParams
    ) -> tuple[list[tuple[str, go.Figure]], list[tuple[str, pd.DataFrame, bool]]]:
        threshold = params.threshold
        show_details = params.show_details

        # Fetch data from the project
        samples = await self.project.get_samples()
        df = pd.DataFrame([{"Sample": s.name, "ID": s.id} for s in samples])

        # Build Plotly figure
        fig = go.Figure(data=[go.Bar(x=df["Sample"], y=df["ID"])])
        fig.update_layout(
            title=f"My Report (threshold={threshold})",
            template="plotly_white",
        )

        plots = [("Sample Chart", fig)]
        tables = []
        if show_details:
            # Tuple format: (table_title, dataframe, show_in_ui)
            tables.append(("Samples Summary", df, True))

        return plots, tables


# 4. Auto-register with DASMixer
registry.register(MyPluginReport)
```

---

## Step-by-Step Reference

### 1. Defining Parameters (`ReportParams`)

Always inherit from `ReportParams` and include `name_template: str = field(default="{date} {time}")`:

- Use `field(default_factory=list)` for mutable defaults (`list[str]`).
- Standard supported field types: `int`, `float`, `bool`, `str`, `list[str]`, `tuple[str, str]`.

### 2. Building the GUI Form (`ReportForm`)

Available GUI selector controls from `dasmixer.gui.components.report_form`:

| Selector | Python Type | Description |
|---|---|---|
| `IntSelector(default=..., label=...)` | `int` | Integer input field |
| `FloatSelector(default=..., label=...)` | `float` | Floating-point input field |
| `BoolSelector(default=..., label=...)` | `bool` | Checkbox |
| `StringSelector(default=..., label=...)` | `str` | Text input field |
| `EnumSelector(values=[...], default=..., label=...)` | `str` | Dropdown with fixed options |
| `SubsetSelector(default=..., label=...)` | `str` | Dropdown populated with project subsets |
| `MultiSubsetSelector(default=[], label=...)` | `list[str]` | Checkboxes for selecting multiple subsets |
| `ToolSelector(default=..., label=...)` | `str` | Dropdown populated with project tools |
| `LFQSelector(default_method=..., default_value_type=..., label=...)` | `tuple[str, str]` | Combined LFQ method and measure selector, e.g., `("emPAI", "rel_value")` |

> **Important:** Do **not** declare a `name_template` selector inside `ReportForm` — DASMixer renders the **Name format** field directly on the report card in the Reports tab.

### 3. Implementing `_generate_impl`

`_generate_impl(self, params)` must be an `async` method returning `(plots, tables)`:

- **`plots`**: `list[tuple[str, go.Figure]]` — list of `(plot_title, plotly_figure)` pairs. DASMixer automatically applies the user's global plot font size, width, and height settings to each figure after `_generate_impl` returns.
- **`tables`**: `list[tuple[str, pd.DataFrame, bool]]` — list of `(table_title, dataframe, show_in_ui)` tuples:
  - `show_in_ui = True`: Displayed in the interactive HTML report preview, DOCX export, and XLSX export. Use this for compact summary tables.
  - `show_in_ui = False`: Hidden from the HTML/DOCX report text to keep it readable, but exported as a sheet in the XLSX workbook. Use this for full protein/peptide data matrices.

### 4. Querying Project Data (`self.project`)

Inside `_generate_impl`, `self.project` gives you full async access to the `Project` API:

```python
# Metadata & entities
samples = await self.project.get_samples()
subsets = await self.project.get_subsets()
tools = await self.project.get_tools()

# Long-format protein quantification data
quant_df = await self.project.get_protein_quantification_data(
    method="emPAI",
    subsets=["Control", "Treatment"],
    exclude_outliers=True,
)

# Joined peptide-level data
peptides_df = await self.project.get_joined_peptide_data(
    is_preferred=True,
    protein_identified=True,
)

# Custom SQL query returning a DataFrame
custom_df = await self.project.execute_query_df(
    "SELECT protein_id, COUNT(*) AS n FROM peptide_match GROUP BY protein_id"
)
```

---

## Icons (`dasmixer.api.reporting._icons.Icons`)

Always import `Icons` from `dasmixer.api.reporting._icons` rather than `flet` so your report works when `dasmixer-gui` is not installed:

- `Icons.REPORT`
- `Icons.AREA_CHART`
- `Icons.BAR_CHART`
- `Icons.SCATTER_PLOT`
- `Icons.PIE_CHART`
- `Icons.VOLCANO`
- `Icons.INSERT_CHART_ROUNDED`

---

## Name Templates

The display name of each generated report run is formatted using `params.name_template`:

- `{date}` — current date (`YYMMDD`)
- `{time}` — current time (`HH:MM`)
- `{<field_name>}` — any attribute from your `ReportParams` dataclass (e.g., `{threshold}`, `{subsets}`, `{lfq}`)
