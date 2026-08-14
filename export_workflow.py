#!/usr/bin/env python3
"""
export_workflow.py -- Export & Visualization for an existing DASMixer project.

Usage:
    python export_workflow.py <project_path>

Outputs:
    <name>_joined_data.csv       Peptide-level joined data
    <name>_protein_results.csv   Protein-level results with LFQ
    <name>_ion_coverage.html     Interactive ion coverage plot
    <name>_ion_coverage.png      Static ion coverage plot (requires Kaleido)
"""

import asyncio
from pathlib import Path

from dasmixer.api.project.project import Project
from dasmixer.api.calculations.spectra.ion_match import IonMatchParameters
from dasmixer.api.calculations.spectra.plot_flow import make_full_spectrum_plot

ION_TYPES = ["b", "y"]
ION_TOLERANCE = 20.0
FRAGMENT_CHARGES = [1, 2]


async def run_export_workflow(project_path: Path) -> None:
    project_path = Path(project_path)
    project_dir = project_path.parent
    stem = project_path.stem

    # ---------------------------------------------------------------
    # 1. Open existing project
    # ---------------------------------------------------------------
    project = Project(path=project_path, create_if_not_exists=False)
    await project.initialize()
    print(f"[OK] Project opened: {project_path}")

    # ---------------------------------------------------------------
    # 2. Find the first sample
    # ---------------------------------------------------------------
    samples = await project.get_samples()
    if not samples:
        print("[ERROR] No samples found in the project")
        await project.close()
        return

    sample = samples[0]
    print(f"[OK] Sample: {sample.name} (id={sample.id})")

    # ---------------------------------------------------------------
    # 3. Export joined peptide data
    # ---------------------------------------------------------------
    joined_data = await project.get_joined_peptide_data(
        is_preferred=True,
        protein_identified=True,
    )

    if not joined_data.empty:
        csv_path = project_dir / f"{stem}_joined_data.csv"
        joined_data.to_csv(csv_path, index=False)
        print(f"[OK] Joined peptide data: {csv_path} ({len(joined_data)} rows)")
    else:
        print("[WARN] No joined peptide data found")

    # ---------------------------------------------------------------
    # 4. Export protein results
    # ---------------------------------------------------------------
    protein_results = await project.get_protein_results_joined(limit=-1)

    if not protein_results.empty:
        csv_path = project_dir / f"{stem}_protein_results.csv"
        protein_results.to_csv(csv_path, index=False)
        print(f"[OK] Protein results: {csv_path} ({len(protein_results)} rows)")
    else:
        print("[WARN] No protein results found")

    # ---------------------------------------------------------------
    # 5. Find first preferred identification
    # ---------------------------------------------------------------
    idents_df = await project.get_identifications(
        sample_id=sample.id,
        only_prefered=True,
        limit=1,
    )

    if idents_df.empty:
        print("[WARN] No preferred identifications for this sample -- "
              "skipping ion coverage plot")
        await project.close()
        return

    first_ident = idents_df.iloc[0]
    spectre_id = int(first_ident["spectre_id"])
    sequence = first_ident["sequence"]
    tool = first_ident["tool_name"]

    print(f"[OK] First preferred: spectre_id={spectre_id} "
          f"tool={tool} sequence={sequence}")

    # ---------------------------------------------------------------
    # 6. Generate ion coverage plot
    # ---------------------------------------------------------------
    plot_data = await project.get_spectrum_plot_data(
        spectre_id, get_matched=True,
    )

    params = IonMatchParameters(
        ions=ION_TYPES,
        tolerance=ION_TOLERANCE,
        mode="largest",
        water_loss=True,
        ammonia_loss=True,
        charges=FRAGMENT_CHARGES,
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

    html_path = project_dir / f"{stem}_ion_coverage.html"
    fig.write_html(str(html_path))
    print(f"[OK] Ion coverage plot (HTML): {html_path}")

    png_path = project_dir / f"{stem}_ion_coverage.png"
    try:
        fig.write_image(str(png_path), width=1200, height=800, scale=2)
        print(f"[OK] Ion coverage plot (PNG): {png_path}")
    except ValueError as exc:
        print(f"[WARN] PNG export skipped (Kaleido not installed?): {exc}")

    # ---------------------------------------------------------------
    # 7. Cleanup
    # ---------------------------------------------------------------
    await project.close()
    print("\n[DONE] Export workflow complete")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python export_workflow.py <project_path>")
        sys.exit(1)

    asyncio.run(run_export_workflow(Path(sys.argv[1])))
