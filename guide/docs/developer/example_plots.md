# Example: Generating Spectrum Ion Coverage Plots

This guide demonstrates how to render an annotated MS/MS fragmentation spectrum plot (identical to the plot view in the **Peptides** tab) using `dasmixer-core` without launching the GUI, and save it as an interactive HTML file, a static PNG image, or a portable Plotly JSON file.

---

## Overview

To generate a spectrum plot from an existing `.dasmix` project, you need:

1. `project.get_spectrum_plot_data(spectrum_id, get_matched=True)` — fetches the decompressed `mz` and `intensity` arrays along with all identifications (and optionally protein-matched sequences) for that spectrum.
2. `IonMatchParameters` — configures ion series (`b`, `y`, etc.), PPM tolerance, neutral losses, and fragment charge states.
3. `make_full_spectrum_plot(...)` — matches theoretical fragment ions for each identification and builds a multi-panel `plotly.graph_objects.Figure`.

---

## Reading Ion Match Settings from the Project

If your project was configured in the GUI, its ion-matching parameters are stored in the `project_settings` table. Reading those keys ensures your script produces the exact same plot as the UI:

```python
from dasmixer.api.project.project import Project
from dasmixer.api.calculations.spectra.ion_match import IonMatchParameters

_SETTING_DEFAULTS = {
    "ion_types": "b,y",
    "ion_ppm_threshold": "20",
    "fragment_charges": "1,2",
    "water_loss": "0",
    "nh3_loss": "0",
}

async def get_ion_match_parameters_from_project(project: Project) -> IonMatchParameters:
    async def _get(key: str) -> str:
        return await project.get_setting(key, _SETTING_DEFAULTS[key])

    ion_types = [s for s in (await _get("ion_types")).split(",") if s]
    tolerance = float(await _get("ion_ppm_threshold"))
    charges = [int(c.strip()) for c in (await _get("fragment_charges")).split(",") if c.strip()]
    water_loss = (await _get("water_loss")) == "1"
    ammonia_loss = (await _get("nh3_loss")) == "1"

    return IonMatchParameters(
        ions=ion_types or ["b", "y"],
        tolerance=tolerance,
        mode="largest",
        water_loss=water_loss,
        ammonia_loss=ammonia_loss,
        charges=charges or [1, 2],
    )
```

---

## Exporting the Plotly Figure

Once `fig` is created by `make_full_spectrum_plot`, you can export it in three ways:

- **Interactive HTML** (no extra dependencies):
  ```python
  fig.write_html("spectrum_42.html")
  ```
- **Static PNG / SVG** (requires `kaleido`: `pip install kaleido`):
  ```python
  fig.write_image("spectrum_42.png", format="png", scale=2)
  ```
- **Plotly JSON** (use `plotly.io.to_json(fig)` so NumPy scalar types are serialized cleanly):
  ```python
  import plotly.io as pio
  json_str = pio.to_json(fig)
  ```

---

## Complete Script

```python
#!/usr/bin/env python3
"""
Render a peptide ion coverage plot for a spectrum ID in a .dasmix project.
Usage:
    python render_ion_plot.py <project.dasmix> <spectrum_id>
"""

import asyncio
import sys
from pathlib import Path
import plotly.io as pio

from dasmixer.api.project.project import Project
from dasmixer.api.calculations.spectra.ion_match import IonMatchParameters
from dasmixer.api.calculations.spectra.plot_flow import make_full_spectrum_plot


async def render_ion_plot(
    project_path: str | Path,
    spectrum_id: int,
    out_dir: str | Path = ".",
    show_protein_sequences: bool = True,
) -> None:
    project_path = Path(project_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    async with Project(path=str(project_path), create_if_not_exists=False) as project:
        plot_data = await project.get_spectrum_plot_data(
            spectrum_id,
            get_matched=show_protein_sequences,
        )
        if not plot_data["sequences"]:
            raise ValueError(f"Spectrum id={spectrum_id} has no identifications.")

        params = IonMatchParameters(
            ions=["b", "y"],
            tolerance=20.0,
            mode="largest",
            water_loss=True,
            ammonia_loss=True,
            charges=[1, 2],
        )

        fig = make_full_spectrum_plot(
            params=params,
            mz=plot_data["mz"],
            intensity=plot_data["intensity"],
            charges=plot_data["charges"],
            sequences=plot_data["sequences"],
            headers=plot_data["headers"],
            spectrum_info=plot_data["spectrum_info"],
        )

        info = plot_data["spectrum_info"]
        fig.update_layout(
            height=500 * len(plot_data["headers"]),
            width=1100,
            template="plotly_white",
            showlegend=False,
            title=f"Fragments (scans={info['scans']}, pepmass={info['pepmass']}, rt={info['rt']})",
        )

        # Save HTML
        html_path = out_dir / f"spectrum_{spectrum_id}_ion_coverage.html"
        fig.write_html(str(html_path))
        print(f"[OK] HTML saved: {html_path}")

        # Save Plotly JSON
        json_path = out_dir / f"spectrum_{spectrum_id}_ion_coverage.json"
        json_path.write_text(pio.to_json(fig), encoding="utf-8")
        print(f"[OK] JSON saved: {json_path}")

        # Save PNG (if kaleido is installed)
        png_path = out_dir / f"spectrum_{spectrum_id}_ion_coverage.png"
        try:
            fig.write_image(str(png_path), format="png", scale=2)
            print(f"[OK] PNG saved: {png_path}")
        except ValueError as exc:
            print(f"[WARN] PNG export skipped (install kaleido for static export): {exc}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python render_ion_plot.py <project.dasmix> <spectrum_id>")
        sys.exit(1)
    asyncio.run(render_ion_plot(sys.argv[1], int(sys.argv[2])))
```
