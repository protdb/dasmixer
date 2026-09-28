"""CLI commands for running pipeline calculations."""

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from dasmixer.api.config import config as app_config
from dasmixer.api.project.project import Project

app = typer.Typer(help="Run pipeline calculations")


def _parse_bool(val: str) -> bool:
    return val.lower() in ("true", "1", "yes")


async def _collect_tool_settings(project) -> dict[int, dict]:
    """
    Build tool_settings dict in the format expected by
    ``calculate_preferred_identifications_for_file``.

    Reads each tool's saved ``settings`` (populated by the GUI in the
    canonical format) and fills sensible defaults for any missing keys.
    Shared by both ``preferred`` and ``peptides`` commands.
    """
    tools = await project.get_tools()
    tool_settings: dict[int, dict] = {}
    for t in tools:
        ts = dict(t.settings or {})
        # Ensure keys required by calculate_preferred_identifications_for_file
        ts.setdefault("ignore_criteria", False)
        ts.setdefault("max_ppm", 50.0)
        ts.setdefault("min_score", 0.0)
        ts.setdefault("min_ion_intensity_coverage", 0.0)
        ts.setdefault("min_peptide_length", 7)
        ts.setdefault("max_peptide_length", 30)
        ts.setdefault("min_spectre_peaks", 1)
        ts.setdefault("min_top_peaks", 1)
        ts.setdefault("min_ions_covered", 1)
        ts.setdefault("min_quality", 0.25)
        ts.setdefault("min_lcrr", 0.2)
        ts.setdefault("max_unconfirmed_ptms", 0)
        ts.setdefault("denovo_correction", False)
        ts.setdefault("denovo_correction_ppm", 50000)
        tool_settings[t.id] = ts
    return tool_settings


async def _run_preferred_selection(project, criterion_val: str, sample_id: int | None) -> int:
    """
    Select preferred identifications per spectrum using the per-file
    algorithm (``calculate_preferred_identifications_for_file``),
    mirroring the GUI pipeline in ``ion_actions.py``.

    Returns the number of spectra files processed.
    """
    from dasmixer.api.calculations.peptides.matching import (
        calculate_preferred_identifications_for_file,
    )

    tool_settings = await _collect_tool_settings(project)
    if not tool_settings:
        typer.echo("No tools configured.")
        return 0

    spectre_files = await project.get_spectra_files(
        sample_id=sample_id if sample_id is not None else None
    )
    processed = 0
    total = len(spectre_files)
    for _, spectra_file in spectre_files.iterrows():
        file_name = Path(spectra_file["path"]).name if spectra_file.get("path") else f"#{spectra_file['id']}"
        typer.echo(f"  Processing {file_name} ({processed + 1}/{total})...")
        idents = await calculate_preferred_identifications_for_file(
            project,
            int(spectra_file["id"]),
            criterion_val,
            tool_settings,
        )
        await project.set_preferred_identifications_for_file(
            int(spectra_file["id"]),
            idents,
        )
        processed += 1
    return processed


# ---------------------------------------------------------------------------
# ion-coverage
# ---------------------------------------------------------------------------

@app.command()
def ion_coverage(
    project_path: Annotated[str, typer.Argument(help="Path to .dasmix project file")],
    recalc_all: Annotated[bool, typer.Option("--recalc-all", help="Recalculate all, including already processed")] = False,
    sample_id: Annotated[int | None, typer.Option("--sample-id", help="Limit to one sample ID")] = None,
    tolerance: Annotated[float | None, typer.Option("--tolerance", help="PPM tolerance (overrides project setting)")] = None,
    ions: Annotated[str | None, typer.Option("--ions", help="Ion types, comma-separated (overrides project setting)")] = None,
):
    """
    Calculate ion coverage for identifications.
    
    Reads settings from project_settings, can override with CLI options.
    """
    async def _run():
        async with Project(path=Path(project_path), create_if_not_exists=False) as project:
            # Load settings from project_settings
            ion_match_ions = await project.get_setting("ion_match_ions", "b,y")
            ion_match_tolerance = await project.get_setting("ion_match_tolerance", "20.0")
            ion_match_mode = await project.get_setting("ion_match_mode", "largest")
            ion_match_water_loss = await project.get_setting("ion_match_water_loss", "True")
            ion_match_ammonia_loss = await project.get_setting("ion_match_ammonia_loss", "True")
            ion_fragment_charges = await project.get_setting("ion_fragment_charges", "1,2")
            seqfixer_min_charge = await project.get_setting("seqfixer_min_charge", "1")
            seqfixer_max_charge = await project.get_setting("seqfixer_max_charge", "4")
            seqfixer_max_isotope_offset = await project.get_setting("seqfixer_max_isotope_offset", "3")
            seqfixer_max_ptm = await project.get_setting("seqfixer_max_ptm", "2")
            seqfixer_max_ptm_sites = await project.get_setting("seqfixer_max_ptm_sites", "3")

            # Override with CLI options
            if tolerance is not None:
                ion_match_tolerance = str(tolerance)
            if ions is not None:
                ion_match_ions = ions

            from dasmixer.api.calculations.ppm.seqfixer import SeqfixerParams
            from dasmixer.api.calculations.spectra.identification_processor import (
                process_identifications_batch,
            )
            from dasmixer.api.calculations.spectra.ion_match import IonMatchParameters

            seqfixer_params = SeqfixerParams(
                min_charge=int(seqfixer_min_charge),
                max_charge=int(seqfixer_max_charge),
                max_isotope_offset=int(seqfixer_max_isotope_offset),
                max_ptm=int(seqfixer_max_ptm),
                max_ptm_sites=int(seqfixer_max_ptm_sites),
            )

            ion_params = IonMatchParameters(
                ion_types=ion_match_ions.split(","),
                ppm_tolerance=float(ion_match_tolerance),
                match_mode=ion_match_mode,
                water_loss=_parse_bool(ion_match_water_loss),
                ammonia_loss=_parse_bool(ion_match_ammonia_loss),
                fragment_charges=[int(c) for c in ion_fragment_charges.split(",")],
            )

            # Get identifications without coverage (or all if recalc_all)
            if recalc_all:
                idents_df = await project.get_identifications(sample_id=sample_id)
            else:
                idents_df = await project.get_identifications(sample_id=sample_id)
                if not idents_df.empty and "ppm" in idents_df.columns:
                    idents_df = idents_df[idents_df["ppm"].isna()]

            if idents_df.empty:
                typer.echo("No identifications to process.")
                return

            total = len(idents_df)
            batch_size = getattr(app_config, 'identification_processing_batch_size', 500)
            processed = 0

            with typer.progressbar(length=total, label="Processing") as progress:
                for start in range(0, total, batch_size):
                    batch = idents_df.iloc[start:start + batch_size]
                    data_rows = process_identifications_batch(
                        batch, ion_params, seqfixer_params,
                    )
                    if data_rows:
                        await project.put_identification_data_batch(data_rows)
                    processed += len(batch)
                    progress.update(len(batch))

            await project.save()
            typer.echo(f"✓ Processed {processed} identifications")

    try:
        asyncio.run(_run())
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# preferred
# ---------------------------------------------------------------------------

@app.command()
def preferred(
    project_path: Annotated[str, typer.Argument(help="Path to .dasmix project file")],
    criterion: Annotated[str | None, typer.Option("--criterion", help="Selection criterion: ppm or intensity")] = None,
    sample_id: Annotated[int | None, typer.Option("--sample-id", help="Limit to one sample ID")] = None,
):
    """
    Select preferred identifications per spectrum.
    """
    async def _run():
        async with Project(path=Path(project_path), create_if_not_exists=False) as project:
            criterion_val = criterion
            if criterion_val is None:
                criterion_val = await project.get_setting("preferred_criterion", "intensity")

            processed = await _run_preferred_selection(project, criterion_val, sample_id)
            await project.save()
            typer.echo(f"✓ Processed {processed} spectra files (preferred identifications selected)")

    try:
        asyncio.run(_run())
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# peptide-match
# ---------------------------------------------------------------------------

@app.command()
def peptide_match(
    project_path: Annotated[str, typer.Argument(help="Path to .dasmix project file")],
    fasta: Annotated[str | None, typer.Option("--fasta", help="Path to FASTA file (overrides project setting)")] = None,
    sample_id: Annotated[int | None, typer.Option("--sample-id", help="Limit to one sample ID")] = None,
    threshold: Annotated[float | None, typer.Option("--threshold", help="Identity threshold")] = None,
    batch_size: Annotated[int | None, typer.Option("--batch-size", help="Batch size")] = None,
):
    """
    Match peptide identifications to protein sequences.
    """
    async def _run():
        async with Project(path=Path(project_path), create_if_not_exists=False) as project:
            fasta_path = fasta
            if not fasta_path:
                fasta_path = await project.get_setting("fasta_path", "")
            if not fasta_path:
                typer.echo("Error: No FASTA file specified. Use --fasta or set fasta_path in project settings.", err=True)
                raise typer.Exit(1)

            fasta_path_obj = Path(fasta_path)
            if not fasta_path_obj.exists():
                typer.echo(f"Error: FASTA file not found: {fasta_path}", err=True)
                raise typer.Exit(1)

            ident_threshold = threshold if threshold is not None else float(
                await project.get_setting("blast_identity_threshold", "0.8")
            )
            mapping_batch_size = batch_size or getattr(app_config, 'protein_mapping_batch_size', 1000)

            from dasmixer.api.calculations.peptides.protein_map import map_proteins

            tools = await project.get_tools()
            tool_settings = {}
            for t in tools:
                tid = t.id
                ts = dict(t.settings or {})
                ts.setdefault("score_min", await project.get_setting(f"tool_{tid}_score_min", "0"))
                ts.setdefault("ppm_max", await project.get_setting(f"tool_{tid}_ppm_max", "20"))
                tool_settings[tid] = ts

            await project.set_setting("fasta_path", str(fasta_path_obj))
            total = await map_proteins(
                project, tool_settings,
                fasta_path=str(fasta_path_obj),
                identity_threshold=ident_threshold,
                mapping_batch_size=mapping_batch_size,
                sample_id=sample_id,
            )
            await project.save()
            typer.echo(f"✓ Mapped {total} peptide matches")

    try:
        asyncio.run(_run())
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# protein-idents
# ---------------------------------------------------------------------------

@app.command()
def protein_idents(
    project_path: Annotated[str, typer.Argument(help="Path to .dasmix project file")],
    min_peptides: Annotated[int | None, typer.Option("--min-peptides", help="Minimum peptides per protein")] = None,
    min_unique: Annotated[int | None, typer.Option("--min-unique", help="Minimum unique evidence")] = None,
    sample_id: Annotated[int | None, typer.Option("--sample-id", help="Limit to one sample ID")] = None,
):
    """
    Calculate protein identifications from peptide matches.
    """
    async def _run():
        async with Project(path=Path(project_path), create_if_not_exists=False) as project:
            min_peptides_val = min_peptides
            min_unique_val = min_unique
            if min_peptides_val is None:
                min_peptides_val = int(await project.get_setting("proteins_min_peptides", "2"))
            if min_unique_val is None:
                min_unique_val = int(await project.get_setting("proteins_min_unique_evidence", "1"))

            await project.set_setting("proteins_min_peptides", str(min_peptides_val))
            await project.set_setting("proteins_min_unique_evidence", str(min_unique_val))

            from dasmixer.api.calculations.proteins.map_identifications import (
                find_protein_identifications,
            )

            # Get joined peptide data
            filters = {}
            if sample_id is not None:
                filters['sample_id'] = sample_id
            joined_data = await project.get_joined_peptide_data(**filters)

            if joined_data.empty:
                typer.echo("No peptide data found. Run 'calculate peptide-match' first.")
                return

            # Get all proteins as sequences_db
            proteins_df = await project.get_proteins()
            if proteins_df.empty:
                typer.echo("No proteins in project. Import a FASTA file first.")
                return

            sequences_db = dict(zip(proteins_df['id'], proteins_df['sequence']))

            prot_idents_df = find_protein_identifications(
                joined_data, sequences_db, min_peptides_val, min_unique_val,
            )

            if prot_idents_df.empty:
                typer.echo("No protein identifications found with current thresholds.")
                return

            await project.add_protein_identifications_batch(prot_idents_df)
            await project.save()
            typer.echo(f"✓ Found {len(prot_idents_df)} protein identifications")

    try:
        asyncio.run(_run())
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# lfq
# ---------------------------------------------------------------------------

@app.command()
def lfq(
    project_path: Annotated[str, typer.Argument(help="Path to .dasmix project file")],
    empai: Annotated[bool | None, typer.Option("--empai", help="Enable emPAI")] = None,
    ibaq: Annotated[bool | None, typer.Option("--ibaq", help="Enable iBAQ")] = None,
    nsaf: Annotated[bool | None, typer.Option("--nsaf", help="Enable NSAF")] = None,
    top3: Annotated[bool | None, typer.Option("--top3", help="Enable Top3")] = None,
    enzyme: Annotated[str | None, typer.Option("--enzyme", help="Digestion enzyme")] = None,
    min_length: Annotated[int | None, typer.Option("--min-length", help="Min peptide length")] = None,
    max_length: Annotated[int | None, typer.Option("--max-length", help="Max peptide length")] = None,
    max_cleavage: Annotated[int | None, typer.Option("--max-cleavage", help="Max missed cleavages")] = None,
    empai_base: Annotated[float | None, typer.Option("--empai-base", help="emPAI base value")] = None,
    sample_id: Annotated[int | None, typer.Option("--sample-id", help="Limit to one sample ID")] = None,
):
    """
    Calculate protein quantification (LFQ).
    
    If no method flags (--empai, --ibaq, etc.) are specified,
    methods are read from project_settings.
    """
    async def _run():
        async with Project(path=Path(project_path), create_if_not_exists=False) as project:
            # Determine methods
            cli_methods = []
            if empai is not None:
                cli_methods.append("empai")
            if ibaq is not None:
                cli_methods.append("ibaq")
            if nsaf is not None:
                cli_methods.append("nsaf")
            if top3 is not None:
                cli_methods.append("top3")

            if cli_methods:
                methods = cli_methods
            else:
                methods_str = await project.get_setting("lfq_methods", "empai,ibaq")
                methods = [m.strip() for m in methods_str.split(",") if m.strip()]

            if not methods:
                typer.echo("Error: No LFQ methods selected", err=True)
                raise typer.Exit(1)

            # Load / override parameters
            lfq_enzyme = enzyme or await project.get_setting("lfq_enzyme", "trypsin")
            lfq_min_length = min_length or int(await project.get_setting("lfq_min_peptide_length", "7"))
            lfq_max_length = max_length or int(await project.get_setting("lfq_max_peptide_length", "25"))
            lfq_max_cleavage = max_cleavage or int(await project.get_setting("lfq_max_cleavage_sites", "2"))
            lfq_empai_base = empai_base or float(await project.get_setting("lfq_empai_base", "10.0"))

            # Save settings
            await project.set_setting("lfq_methods", ",".join(methods))
            await project.set_setting("lfq_enzyme", lfq_enzyme)
            await project.set_setting("lfq_min_peptide_length", str(lfq_min_length))
            await project.set_setting("lfq_max_peptide_length", str(lfq_max_length))
            await project.set_setting("lfq_max_cleavage_sites", str(lfq_max_cleavage))
            await project.set_setting("lfq_empai_base", str(lfq_empai_base))

            from dasmixer.api.calculations.proteins.lfq import calculate_lfq

            samples = await project.get_samples()
            if sample_id is not None:
                samples = [s for s in samples if s.id == sample_id]
                if not samples:
                    typer.echo(f"Error: Sample ID {sample_id} not found", err=True)
                    raise typer.Exit(1)

            calculated_count = 0
            for s in samples:
                await calculate_lfq(
                    project,
                    sample_id=s.id,
                    methods=methods,
                    enzyme=lfq_enzyme,
                    min_peptide_length=lfq_min_length,
                    max_peptide_length=lfq_max_length,
                    max_cleavage_sites=lfq_max_cleavage,
                    empai_base=lfq_empai_base,
                )
                calculated_count += 1
                typer.echo(f"  Sample '{s.name}': done")

            await project.save()
            typer.echo(f"✓ LFQ calculated for {calculated_count} samples, methods: {methods}")

    try:
        asyncio.run(_run())
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# peptides (full pipeline)
# ---------------------------------------------------------------------------

@app.command()
def peptides(
    project_path: Annotated[str, typer.Argument(help="Path to .dasmix project file")],
    fasta: Annotated[str | None, typer.Option("--fasta", help="Path to FASTA file")] = None,
    criterion: Annotated[str | None, typer.Option("--criterion", help="Selection criterion: ppm or intensity")] = None,
    sample_id: Annotated[int | None, typer.Option("--sample-id", help="Limit to one sample ID")] = None,
):
    """
    Run full peptide calculation pipeline:
    1. Match proteins
    2. Calculate ion coverage
    3. Select preferred identifications
    """
    async def _run():
        async with Project(path=Path(project_path), create_if_not_exists=False) as project:
            # Step 1: Match proteins
            typer.echo("Step 1/3: Matching proteins...")
            fasta_path = fasta or await project.get_setting("fasta_path", "")
            if not fasta_path:
                typer.echo("Error: No FASTA file specified", err=True)
                raise typer.Exit(1)
            if not Path(fasta_path).exists():
                typer.echo(f"Error: FASTA file not found: {fasta_path}", err=True)
                raise typer.Exit(1)

            tools = await project.get_tools()
            tool_settings = {}
            for t in tools:
                tid = t.id
                ts = dict(t.settings or {})
                ts.setdefault("score_min", await project.get_setting(f"tool_{tid}_score_min", "0"))
                ts.setdefault("ppm_max", await project.get_setting(f"tool_{tid}_ppm_max", "20"))
                tool_settings[tid] = ts

            ident_threshold = float(await project.get_setting("blast_identity_threshold", "0.8"))
            mapping_batch_size = getattr(app_config, 'protein_mapping_batch_size', 1000)

            from dasmixer.api.calculations.peptides.protein_map import map_proteins
            await map_proteins(
                project, tool_settings,
                fasta_path=fasta_path,
                identity_threshold=ident_threshold,
                mapping_batch_size=mapping_batch_size,
                sample_id=sample_id,
            )
            await project.save()

            # Step 2: Ion coverage
            typer.echo("Step 2/3: Calculating ion coverage...")
            from dasmixer.api.calculations.ppm.seqfixer import SeqfixerParams
            from dasmixer.api.calculations.spectra.identification_processor import (
                process_identifications_batch,
            )
            from dasmixer.api.calculations.spectra.ion_match import IonMatchParameters

            ion_match_ions = await project.get_setting("ion_match_ions", "b,y")
            ion_match_tolerance = await project.get_setting("ion_match_tolerance", "20.0")
            ion_match_mode = await project.get_setting("ion_match_mode", "largest")
            ion_match_water_loss = await project.get_setting("ion_match_water_loss", "True")
            ion_match_ammonia_loss = await project.get_setting("ion_match_ammonia_loss", "True")
            ion_fragment_charges = await project.get_setting("ion_fragment_charges", "1,2")

            seqfixer_params = SeqfixerParams(
                min_charge=1, max_charge=4, max_isotope_offset=3, max_ptm=2, max_ptm_sites=3,
            )
            ion_params = IonMatchParameters(
                ion_types=ion_match_ions.split(","),
                ppm_tolerance=float(ion_match_tolerance),
                match_mode=ion_match_mode,
                water_loss=_parse_bool(ion_match_water_loss),
                ammonia_loss=_parse_bool(ion_match_ammonia_loss),
                fragment_charges=[int(c) for c in ion_fragment_charges.split(",")],
            )

            idents_df = await project.get_identifications(sample_id=sample_id)
            if not idents_df.empty:
                batch_size = getattr(app_config, 'identification_processing_batch_size', 500)
                for start in range(0, len(idents_df), batch_size):
                    batch = idents_df.iloc[start:start + batch_size]
                    data_rows = process_identifications_batch(batch, ion_params, seqfixer_params)
                    if data_rows:
                        await project.put_identification_data_batch(data_rows)
                await project.save()

            # Step 3: Select preferred
            typer.echo("Step 3/3: Selecting preferred identifications...")
            criterion_val = criterion
            if criterion_val is None:
                criterion_val = await project.get_setting("preferred_criterion", "intensity")

            await _run_preferred_selection(project, criterion_val, sample_id)
            await project.save()

            typer.echo("✓ Peptide calculations complete!")

    try:
        asyncio.run(_run())
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
