# Spectrum Ion Coverage Plot Example

This document demonstrates how to **render a peptide ion coverage plot** (the same
b/y-ion annotated MS/MS spectrum view used in the GUI's *Peptides* tab) using only
`dasmixer-core` (no GUI) and save it to:

- a) a **PNG** raster image, and
- b) a **Plotly JSON** file that can be re-opened later in a browser or in Plotly
  Python/JS.

The plot parameters (ion types, PPM tolerance, fragment charges, water/NH₃ loss
toggles) are read from the project's own `project_settings` table — exactly as the
GUI does — so the output matches what the user sees in the UI. There is no need to
pass these parameters explicitly.

---

## Table of Contents

1. [Overview](#overview)
2. [Project Settings for Ion Matching](#project-settings-for-ion-matching)
3. [Why Plotly JSON Needs Special Handling](#why-plotly-json-needs-special-handling)
4. [Complete Script](#complete-script)

---

## Overview

The pipeline accepts two inputs:

| Input | Content |
|-------|---------|
| `project_path` | An existing `.dasmix` project file |
| `spectrum_id`  | Primary key of a row in the `spectre` table |

**Output:**

| File | Content |
|------|---------|
| `<name>_ion_coverage.png`  | Static PNG of the annotated MS/MS spectrum |
| `<name>_ion_coverage.json` | Plotly figure JSON (re-usable, portable) |

The plot is generated for one spectrum and **all of its identifications** — one
subplot per identification, just like in the GUI. Preferred identifications are
marked with a ★ in the subplot title.

---

## Project Settings for Ion Matching

The GUI stores ion-matching parameters in the `project_settings` table as
key/value strings (see `dasmixer-gui/.../ion_settings_section.py:load_data`).
The example script reads these same keys, with the same defaults the GUI uses
when a project has never been saved with explicit settings:

| Key (`project_settings`) | Type stored | Default | Used for |
|---|---|---|---|
| `ion_types` | comma-joined string | `"b,y"` | `IonMatchParameters.ions` |
| `ion_ppm_threshold` | string float | `"20"` | `IonMatchParameters.tolerance` |
| `fragment_charges` | comma-joined string | `"1,2"` | `IonMatchParameters.charges` |
| `water_loss` | `"1"` / `"0"` | `"0"` | `IonMatchParameters.water_loss` |
| `nh3_loss` | `"1"` / `"0"` | `"0"` | `IonMatchParameters.ammonia_loss` |

`IonMatchParameters.mode` is always `'largest'` in the GUI (hard-coded in
`ion_settings_section.py:get_ion_match_parameters`), so the script does the same.

The helper `get_ion_match_parameters_from_project()` mirrors the GUI's
`IonSettingsSection.get_ion_match_parameters()` one-to-one — any project that was
opened and saved through the GUI will produce the **same** plot as the UI.

---

## Why Plotly JSON Needs Special Handling

Plotly's `fig.to_json()` works fine for plain Python types, but in this pipeline
the figure is built from a `pd.DataFrame` produced by `get_matches_dataframe()`.
Even though `generate_spectrum_plot()` extracts scalar values from each row and
passes them into `go.Bar` / `go.Annotation` individually, three categories of
"non-JSON-native" objects can leak into the resulting figure:

| Source | Type | Why `json.dumps` fails |
|--------|------|------------------------|
| `df['mz']` / `df['intensity']` cells | `numpy.float64` | Not a `json.JSONEncoder` subclass by default |
| Custom hover templates with array refs | numpy arrays in `customdata` | Become `{"type": "ndarray", ...}` blobs in plain `to_json()` |
| `pd.Timestamp` values from spectrum metadata | `pd.Timestamp` | `datetime` subclass, serialised differently by stdlib vs. plotly |

There are two safe ways to handle this:

### Option A — `plotly.io.to_json` (recommended)

```python
import plotly.io as pio
json_str = pio.to_json(fig)        # plotly's own encoder, handles numpy
```

`plotly.io.to_json` uses Plotly's internal encoder which converts `numpy.float64`,
`numpy.int32`, and `numpy.ndarray` to plain JSON floats / lists. This is the same
encoder used internally by `fig.show()` and by `dash`.

### Option B — round-trip via `fig.to_dict()` + custom stdlib encoder

If you want a plain dict (e.g. to embed inside a larger JSON document), do:

```python
import json
import numpy as np
import pandas as pd

def _default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (pd.Timestamp,)):
        return o.isoformat()
    raise TypeError(f"Unserialisable: {type(o)}")

fig_dict = fig.to_dict()              # plain Python dict
json_str = json.dumps(fig_dict, default=_default)
```

`fig.to_dict()` strips Plotly's wrapper objects but keeps numpy values inside
`customdata` etc., so the custom `default=` handler is mandatory.

### Why not just `json.dumps(fig.to_dict())`?

It will raise `TypeError: Object of type float64 is not JSON serializable` for
any figure whose traces were built from pandas rows — which is exactly the case
here.

This example uses **Option A** (the most robust, no custom encoder needed), but
includes Option B as a helper for completeness.

---

## Complete Script

The function `render_ion_plot(project_path, spectrum_id, out_dir, **kwargs)`
opens an existing project, reads ion-matching settings from `project_settings`,
fetches plot data for one spectrum, builds the figure, and writes both a PNG
(via `kaleido`) and a Plotly JSON file.

CLI overrides are optional — when omitted, the value from `project_settings`
(or its built-in default) is used.

**Command-line usage:**

```bash
python render_ion_plot.py project.dasmix 42
```

**As a library:**

```python
import asyncio
from render_ion_plot import render_ion_plot

asyncio.run(render_ion_plot(
    project_path="project.dasmix",
    spectrum_id=42,
    out_dir=".",
))
```

> **Requirements:** the PNG export uses `kaleido` (install with
> `pip install kaleido`). The Plotly JSON export needs only `plotly` itself.

---

```python
#!/usr/bin/env python3
"""
Render a peptide ion coverage plot (b/y-ion annotated MS/MS spectrum) and save it
as both PNG and Plotly JSON. Mirrors the GUI view in
dasmixer-gui/src/dasmixer/gui/views/tabs/peptides/peptide_ion_plot_view.py.

Ion-matching parameters are read from the project's ``project_settings`` table
(the same keys the GUI uses), so output matches the UI for any project that has
been opened and saved through the GUI.
"""

import argparse
import asyncio
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

from dasmixer.api.project.project import Project
from dasmixer.api.calculations.spectra.ion_match import IonMatchParameters
from dasmixer.api.calculations.spectra.plot_flow import make_full_spectrum_plot


# ---------------------------------------------------------------------------
# JSON serialisation helpers (see "Why Plotly JSON Needs Special Handling")
# ---------------------------------------------------------------------------

def figure_to_plotly_json(fig: go.Figure) -> str:
    """
    Convert a Plotly Figure to a JSON string using Plotly's own encoder.

    Handles numpy.float64 / numpy.int32 / numpy.ndarray natively, which
    ``json.dumps(fig.to_dict())`` does not. This is the recommended path.
    """
    return pio.to_json(fig)


def figure_to_json_stdlib(fig: go.Figure) -> str:
    """
    Convert a Plotly Figure to a JSON string using the stdlib ``json`` module
    with a custom ``default`` handler for numpy/pandas types.

    Useful when you want to embed the figure inside a larger JSON document
    (e.g. an API response) rather than writing a standalone .json file.
    """
    def _default(obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (pd.Timestamp,)):
            return obj.isoformat()
        if pd.isna(obj):  # NaN / NaT -> null
            return None
        raise TypeError(f"Unserialisable: {type(obj)}")

    return json.dumps(fig.to_dict(), default=_default, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Reading ion-match settings from project_settings (mirrors the GUI)
# ---------------------------------------------------------------------------

# Defaults are exactly those used by the GUI's IonSettingsSection.load_data()
# (dasmixer-gui/.../ion_settings_section.py:97-134) when a key is missing.
_SETTING_DEFAULTS = {
    "ion_types": "b,y",
    "ion_ppm_threshold": "20",
    "fragment_charges": "1,2",
    "water_loss": "0",
    "nh3_loss": "0",
}


async def get_ion_match_parameters_from_project(project: Project) -> IonMatchParameters:
    """
    Build an ``IonMatchParameters`` from the project's ``project_settings`` table.

    Mirrors ``IonSettingsSection.get_ion_match_parameters()`` in the GUI:
    reads the same keys, applies the same defaults, and hard-codes
    ``mode='largest'`` (as the GUI does).
    """
    async def _get(key: str) -> str:
        return await project.get_setting(key, _SETTING_DEFAULTS[key])

    ion_types_str = await _get("ion_types")
    ion_types = [s for s in ion_types_str.split(",") if s] if ion_types_str else []

    tolerance = float(await _get("ion_ppm_threshold"))

    charges_str = await _get("fragment_charges")
    charges = [int(c.strip()) for c in charges_str.split(",") if c.strip()]

    water_loss = (await _get("water_loss")) == "1"
    ammonia_loss = (await _get("nh3_loss")) == "1"

    return IonMatchParameters(
        ions=ion_types or ["b", "y"],
        tolerance=tolerance,
        mode="largest",          # GUI hard-codes this
        water_loss=water_loss,
        ammonia_loss=ammonia_loss,
        charges=charges or [1, 2],
    )


# ---------------------------------------------------------------------------
# Core rendering
# ---------------------------------------------------------------------------

async def render_ion_plot(
    project_path: str | Path,
    spectrum_id: int,
    out_dir: str | Path = ".",
    show_protein_sequences: bool = False,
    show_title: bool = True,
    # Optional CLI overrides — when None, the value from project_settings is used.
    ion_types: list[str] | None = None,
    tolerance: float | None = None,
    fragment_charges: list[int] | None = None,
    water_loss: bool | None = None,
    ammonia_loss: bool | None = None,
) -> tuple[Path, Path]:
    """
    Build the ion coverage plot for one spectrum and save PNG + JSON.

    Ion-matching parameters are read from ``project_settings`` (same keys as
    the GUI). Any non-None override argument takes precedence over the stored
    setting.

    Parameters
    ----------
    project_path : str | Path
        Path to an existing ``.dasmix`` project file.
    spectrum_id : int
        Primary key of a row in the ``spectre`` table.
    out_dir : str | Path
        Directory where the output files are written. Default: current dir.
    show_protein_sequences : bool
        If True, fetch ``matched_sequence`` from ``peptide_match`` (shows
        protein-mapped sequences in addition to identification sequences).
    show_title : bool
        If True, add a title with scans / pepmass / RT to the figure.
    ion_types, tolerance, fragment_charges, water_loss, ammonia_loss
        Optional overrides. When None, the value from ``project_settings``
        (or its built-in default) is used — matching the GUI behaviour.

    Returns
    -------
    tuple[Path, Path]
        Paths to the saved PNG and JSON files.
    """
    project_path = Path(project_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Open project (read-only is enough — no save needed)
    # ------------------------------------------------------------------
    async with Project(path=str(project_path), create_if_not_exists=False) as project:

        # --------------------------------------------------------------
        # 2. Fetch spectrum + identifications in one call.
        #    get_spectrum_plot_data returns:
        #      mz        : list[float]
        #      intensity  : list[float]
        #      charges    : list[int] | int
        #      sequences  : list[str]   (identification sequences)
        #      headers    : list[str]   (subplot titles)
        #      spectrum_info : dict(seq_no, scans, rt, pepmass, charge)
        # --------------------------------------------------------------
        plot_data = await project.get_spectrum_plot_data(
            spectrum_id,
            get_matched=show_protein_sequences,
        )

        if not plot_data["sequences"]:
            raise ValueError(
                f"Spectrum id={spectrum_id} has no identifications; "
                "nothing to plot."
            )

        # --------------------------------------------------------------
        # 3. Build IonMatchParameters from project_settings, applying
        #    any explicit overrides passed by the caller.
        # --------------------------------------------------------------
        params = await get_ion_match_parameters_from_project(project)

        if ion_types is not None:
            params.ions = ion_types
        if tolerance is not None:
            params.tolerance = tolerance
        if fragment_charges is not None:
            params.charges = fragment_charges
        if water_loss is not None:
            params.water_loss = water_loss
        if ammonia_loss is not None:
            params.ammonia_loss = ammonia_loss

        print(
            f"[OK] Ion params: ions={params.ions} tolerance={params.tolerance} "
            f"charges={params.charges} water_loss={params.water_loss} "
            f"nh3_loss={params.ammonia_loss}"
        )

        # --------------------------------------------------------------
        # 4. Build the figure: one subplot per identification.
        #    make_full_spectrum_plot() runs match_predictions() for each
        #    sequence and builds a multi-panel go.Figure.
        # --------------------------------------------------------------
        fig = make_full_spectrum_plot(
            params=params,
            mz=plot_data["mz"],
            intensity=plot_data["intensity"],
            charges=plot_data["charges"],
            sequences=plot_data["sequences"],
            headers=plot_data["headers"],
            spectrum_info=plot_data["spectrum_info"],
        )

        # --------------------------------------------------------------
        # 5. Layout — match the GUI's styling
        # --------------------------------------------------------------
        fig.update_layout(
            height=500 * len(plot_data["headers"]),
            width=1100,
            template="plotly_white",
            showlegend=False,
        )

        if show_title:
            info = plot_data["spectrum_info"]
            fig.update_layout(
                title=(
                    f"Fragments (scans={info['scans']}, "
                    f"pepmass={info['pepmass']}, rt={info['rt']})"
                ),
            )
        else:
            fig.update_layout(title=None)

        # --------------------------------------------------------------
        # 6a. Save PNG  (requires kaleido)
        # --------------------------------------------------------------
        png_path = out_dir / f"spectrum_{spectrum_id}_ion_coverage.png"
        fig.write_image(str(png_path), format="png", scale=2)
        print(f"[OK] PNG saved: {png_path}")

        # --------------------------------------------------------------
        # 6b. Save Plotly JSON.
        #     Use plotly.io.to_json — see "Why Plotly JSON Needs Special
        #     Handling" above. The figure contains numpy.float64 values
        #     (from the per-peak go.Bar traces built by
        #     generate_spectrum_plot), which json.dumps(fig.to_dict())
        #     cannot serialise on its own.
        # --------------------------------------------------------------
        json_path = out_dir / f"spectrum_{spectrum_id}_ion_coverage.json"
        json_str = figure_to_plotly_json(fig)
        json_path.write_text(json_str, encoding="utf-8")
        print(f"[OK] Plotly JSON saved: {json_path}")

        # Optional sanity check: load it back and verify it round-trips
        # into a Figure object with the same number of traces.
        reloaded = pio.from_json(json_str)
        assert len(reloaded.data) == len(fig.data), (
            f"JSON round-trip mismatch: {len(reloaded.data)} vs {len(fig.data)}"
        )
        print(f"[OK] JSON round-trip verified ({len(fig.data)} traces)")

    return png_path, json_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render a peptide ion coverage plot from a .dasmix project."
    )
    parser.add_argument("project", help="Path to the .dasmix project file")
    parser.add_argument("spectrum_id", type=int, help="ID in the spectre table")
    parser.add_argument(
        "-o", "--out-dir", default=".", help="Output directory (default: .)"
    )
    parser.add_argument(
        "--ions", nargs="+", default=None,
        help="Override ion types (default: from project_settings, e.g. b y)",
    )
    parser.add_argument(
        "--tolerance", type=float, default=None,
        help="Override PPM tolerance (default: from project_settings)",
    )
    parser.add_argument(
        "--charges", nargs="+", type=int, default=None,
        help="Override fragment charge states (default: from project_settings)",
    )
    parser.add_argument(
        "--water-loss", action="store_true", default=None,
        help="Include -H2O fragment ions (default: from project_settings)",
    )
    parser.add_argument(
        "--no-water-loss", action="store_true", default=None,
        help="Exclude -H2O fragment ions (overrides project_settings)",
    )
    parser.add_argument(
        "--ammonia-loss", action="store_true", default=None,
        help="Include -NH3 fragment ions (default: from project_settings)",
    )
    parser.add_argument(
        "--no-ammonia-loss", action="store_true", default=None,
        help="Exclude -NH3 fragment ions (overrides project_settings)",
    )
    parser.add_argument(
        "--show-protein-sequences", action="store_true",
        help="Also show matched_sequence from peptide_match (protein-mapped)",
    )
    parser.add_argument(
        "--no-title", action="store_true",
        help="Do not add a title with scans / pepmass / RT",
    )

    args = parser.parse_args()

    # Resolve mutually-exclusive boolean overrides into True/False/None.
    if args.water_loss and args.no_water_loss:
        parser.error("--water-loss and --no-water-loss are mutually exclusive")
    if args.water_loss:
        args.water_loss = True
    elif args.no_water_loss:
        args.water_loss = False
    else:
        args.water_loss = None

    if args.ammonia_loss and args.no_ammonia_loss:
        parser.error("--ammonia-loss and --no-ammonia-loss are mutually exclusive")
    if args.ammonia_loss:
        args.ammonia_loss = True
    elif args.no_ammonia_loss:
        args.ammonia_loss = False
    else:
        args.ammonia_loss = None

    return args


if __name__ == "__main__":
    args = _parse_args()

    asyncio.run(
        render_ion_plot(
            project_path=args.project,
            spectrum_id=args.spectrum_id,
            out_dir=args.out_dir,
            show_protein_sequences=args.show_protein_sequences,
            show_title=not args.no_title,
            ion_types=args.ions,
            tolerance=args.tolerance,
            fragment_charges=args.charges,
            water_loss=args.water_loss,
            ammonia_loss=args.ammonia_loss,
        )
    )
```
