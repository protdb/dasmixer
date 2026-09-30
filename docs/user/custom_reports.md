# User Guide — Creating Custom Reports

## Overview

DASMixer reports are Python modules that produce analytical outputs (plots and tables)
from project data. Custom reports can be added as **plugins** (`.py` files placed in
`{app_dir}/plugins/reports/`) or developed directly in the source tree.

Since v0.7.4a1, each report consists of up to four files:

| File | Purpose |
|------|---------|
| `params.py` | Typed parameter dataclass |
| `form.py` | GUI parameter form (optional — only needed when `dasmixer-gui` is installed) |
| `report.py` | Report logic — `BaseReport` subclass |
| `__init__.py` | Re-exports the report class |

A report **can also be a single `.py` file** (see § Single-file Report below).

---

## Quick Start — Minimal Report

### Step 1: `params.py`

Define a dataclass for report parameters. Minimum: `name_template`.

```python
# my_report/params.py
from dataclasses import dataclass, field
from dasmixer.api.reporting.report_params import ReportParams


@dataclass
class MyReportParams(ReportParams):
    threshold: float = 0.5
    show_details: bool = True
    name_template: str = field(default="{date} {time}")
```

**Rules:**
- Always inherit from `ReportParams`
- Always include `name_template: str = field(default="{date} {time}")`
- Use `field(default=...)` for mutable types (`list`, `tuple`, etc.)
- Type hints are mandatory (`int`, `float`, `bool`, `str`, `list[str]`, `tuple[str, str]`)

### Step 2: `form.py` (GUI only)

Define a form class extending the GUI `ReportForm`. This file is imported only when
`dasmixer-gui` is installed — it must import directly from `dasmixer.gui.components.report_form`.

```python
# my_report/form.py
from dasmixer.gui.components.report_form import (
    ReportForm, FloatSelector, BoolSelector,
)
from .params import MyReportParams


class MyReportForm(ReportForm):
    params_class = MyReportParams
    threshold = FloatSelector(default=0.5, label="Threshold")
    show_details = BoolSelector(default=True, label="Show details")
```

Available selectors:

| Selector | Type | Example |
|----------|------|---------|
| `IntSelector(default=..., label=...)` | `int` | `IntSelector(default=10)` |
| `FloatSelector(default=..., label=...)` | `float` | `FloatSelector(default=1.5)` |
| `BoolSelector(default=..., label=...)` | `bool` | `BoolSelector(default=True)` |
| `StringSelector(default=..., label=...)` | `str` | `StringSelector(default="")` |
| `EnumSelector(values=[...], default=..., label=...)` | `str` | `EnumSelector(["A","B"])` |
| `SubsetSelector(default=..., label=...)` | `str` | Pick one comparison group |
| `MultiSubsetSelector(default=[], label=...)` | `list[str]` | Checkbox per group |
| `ToolSelector(default=..., label=...)` | `str` | Pick one tool by name |
| `LFQSelector(default_method=..., default_value_type=..., label=...)` | `tuple[str,str]` | `("emPAI", "rel_value")` |

**Important:** Do NOT declare a `name_template` selector in your form — it is rendered
automatically as a text field on the report card itself, not inside the parameter dialog.

### Step 3: `report.py`

Implement the report logic by subclassing `BaseReport`.

```python
# my_report/report.py
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from dasmixer.api.reporting._icons import Icons
from dasmixer.api.reporting.base import BaseReport
from dasmixer.api.reporting.registry import registry

from .params import MyReportParams

# Import the GUI form — only when dasmixer-gui is installed
try:
    from .form import MyReportForm
    _parameters = MyReportForm
except ImportError:
    _parameters = None


class MyReport(BaseReport):
    """My custom report."""

    name = "My Custom Report"
    description = "An example custom report with configurable threshold"
    icon = Icons.REPORT

    params_class = MyReportParams
    parameters = _parameters
    name_template = "{date} {time}"

    async def _generate_impl(
        self, params: MyReportParams
    ) -> tuple[list[tuple[str, go.Figure]], list[tuple[str, pd.DataFrame, bool]]]:
        # Access typed parameters directly
        threshold = params.threshold
        show_details = params.show_details

        # 1. Fetch data from project
        samples = await self.project.get_samples()
        df = pd.DataFrame([{'name': s.name, 'id': s.id} for s in samples])

        # 2. Create plots
        fig = go.Figure(data=[go.Bar(x=df['name'], y=df['id'])])
        fig.update_layout(title=f"My Report (threshold={threshold})")

        # 3. Return (plots, tables)
        plots = [("Sample Chart", fig)]
        tables = []
        if show_details:
            tables.append(("Samples", df, True))  # show_in_ui=True

        return plots, tables


# Auto-register
registry.register(MyReport)
```

**Key points:**
- `_generate_impl(self, params: MyReportParams)` — receive your typed dataclass
- `params.threshold` — access fields as attributes (not dict)
- Return `(list[plots], list[tables])` where each plot is `(name, go.Figure)` and each table is `(name, pd.DataFrame, show_in_ui)`
- `show_in_ui=True` — table visible in preview; `False` — «background» table (large, export-only)
- Always call `registry.register(MyReport)` at module level

### Step 4: `__init__.py`

```python
# my_report/__init__.py
from .report import MyReport
__all__ = ["MyReport"]
```

---

## Single-file Report (Plugin)

For a plugin (one `.py` file in `{app_dir}/plugins/reports/`), put everything in one file:

```python
# my_plugin_report.py
from dataclasses import dataclass, field
from dasmixer.api.reporting.report_params import ReportParams
from dasmixer.api.reporting.base import BaseReport
from dasmixer.api.reporting.registry import registry
from dasmixer.api.reporting._icons import Icons


# --- Params ---
@dataclass
class MyPluginParams(ReportParams):
    threshold: float = 0.5
    name_template: str = field(default="{date} {time}")


# --- GUI form (optional) ---
try:
    from dasmixer.gui.components.report_form import ReportForm, FloatSelector

    class MyPluginForm(ReportForm):
        params_class = MyPluginParams
        threshold = FloatSelector(default=0.5)

    _parameters = MyPluginForm
except ImportError:
    _parameters = None


# --- Report ---
class MyPluginReport(BaseReport):
    name = "My Plugin Report"
    description = "Single-file plugin report"
    icon = Icons.REPORT
    params_class = MyPluginParams
    parameters = _parameters
    name_template = "{date} {time}"

    async def _generate_impl(self, params: MyPluginParams):
        import pandas as pd
        import plotly.graph_objects as go

        data = await self.project.get_samples()
        df = pd.DataFrame([{'name': s.name} for s in data])
        fig = go.Figure(data=[go.Bar(x=df['name'], y=[1]*len(df))])

        return [("Chart", fig)], [("Table", df, True)]


registry.register(MyPluginReport)
```

The plugin loader (`dasmixer.api.plugin_loader`) executes this file as a module.
The `registry.register()` call at module level triggers auto-discovery — no further
wiring is needed.

---

## Working with Project Data

Your report has full access to the `Project` API via `self.project`:

```python
# Fetch data
samples = await self.project.get_samples()
subsets = await self.project.get_subsets()
tools = await self.project.get_tools()

# Quantification data
df = await self.project.get_protein_quantification_data(
    method="emPAI",
    subsets=["Control", "Treatment"],
)

# Raw SQL
rows = await self.project.execute_query("SELECT ...")
df = await self.project.execute_query_df("SELECT ...")

# Settings
value = await self.project.get_setting("lfq_enzyme", "trypsin")
```

---

## Icon Reference

Use `Icons` from `dasmixer.api.reporting._icons` (works without flet installed):

```python
from dasmixer.api.reporting._icons import Icons

class MyReport(BaseReport):
    icon = Icons.AREA_CHART       # or Icons.BAR_CHART, Icons.SCATTER_PLOT,
                                  # Icons.PIE_CHART, Icons.VOLCANO,
                                  # Icons.INSERT_CHART_ROUNDED, Icons.REPORT
```

---

## Name Template

The report display name is computed from `name_template` using `str.format()`:

| Placeholder | Meaning | Example |
|-------------|---------|---------|
| `{date}` | Current date (YYMMDD) | `260930` |
| `{time}` | Current time (HH:MM) | `14:05` |
| `{field}` | Any field from your params dataclass | `{threshold}` → `0.5` |

Default: `"{date} {time}"` → `"260930 14:05"`

The template is taken from `params.name_template` (user-editable on the card),
falling back to the class-level `name_template`.

---

## Export File Naming

Exported files are named: `{report_name}_{display_name}.{ext}`

Example for `Volcano Report (independent)` with display name `260930 14:05`:
- `Volcano Report (independent)_260930 14-05.html`

Characters illegal in NTFS (`:`, `\`, `/`, `*`, `?`, `"`, `<`, `>`, `|`) are
replaced: `:` → `-`, others → `_`.

---

## Installing Custom Reports

**As a plugin (recommended):**
1. Place your `.py` file in `{app_dir}/plugins/reports/`
2. Restart DASMixer
3. The report appears in the Reports tab automatically

App directory location:
- **Windows:** `%APPDATA%/dasmixer/plugins/reports/`
- **Linux:** `~/.config/dasmixer/plugins/reports/`

**In the source tree (development):**
1. Create a package under `dasmixer-core/src/dasmixer/reports/<name>/`
2. Add `from .<name> import <YourReport>` to `dasmixer/reports/__init__.py`
3. Rebuild / reinstall the package

---

## Debugging Tips

- Check the log (`AppData/dasmixer/dasmixer.log` or console output)
- Wrap `_generate_impl` body in `try/except` and log exceptions:
  ```python
  from dasmixer.utils.logger import logger
  logger.exception("MyReport failed")
  ```
- If your report doesn't appear, verify `registry.register()` is called at module level
- Use `await self.project.execute_query_df("SELECT ...")` to verify your SQL queries