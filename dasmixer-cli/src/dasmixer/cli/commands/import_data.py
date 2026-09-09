"""CLI commands for importing data files."""

import asyncio
from collections import defaultdict
from pathlib import Path
from typing import Annotated

import typer
from dasmixer.api.config import config
from dasmixer.api.inputs.registry import registry
from dasmixer.api.project.project import Project
from dasmixer.utils.seek_files import seek_files

app = typer.Typer(help="Import data files")


@app.command()
def mgf_pattern(
    project_path: Annotated[str, typer.Argument(help="Path to .dasmix project file")],
    folder: Annotated[str, typer.Option("--folder", "-f", help="Folder to search")] = ...,
    file_pattern: Annotated[str, typer.Option("--pattern", "-p", help="File pattern (e.g., *.mgf)")] = "*.mgf",
    id_pattern: Annotated[str, typer.Option("--id-pattern", "-i", help="Sample ID pattern (e.g., {id}_*.mgf)")] = "{id}*.mgf",
    parser: Annotated[str, typer.Option("--parser", help="Parser name")] = "MGF",
    group: Annotated[str, typer.Option("--group", "-g", help="Group to assign samples")] = "Control"
):
    """
    Import MGF files using pattern matching.
    
    Example:
        dasmixer project.dasmix import mgf-pattern \\
            --folder /data/spectra \\
            --pattern "*.mgf" \\
            --id-pattern "{id}_run*.mgf" \\
            --group Control
    """
    project_path = Path(project_path)
    
    if not project_path.exists():
        typer.echo(f"Error: Project file not found: {project_path}", err=True)
        raise typer.Exit(1)
    
    folder_path = Path(folder)
    if not folder_path.exists():
        typer.echo(f"Error: Folder not found: {folder}", err=True)
        raise typer.Exit(1)
    
    # Find files
    try:
        files = seek_files(folder_path, file_pattern, id_pattern)
    except Exception as e:
        typer.echo(f"Error searching files: {e}", err=True)
        raise typer.Exit(1)
    
    if not files:
        typer.echo("No files found matching pattern", err=True)
        raise typer.Exit(1)
    
    # Show found files
    typer.echo(f"\nFound {len(files)} file(s):")
    typer.echo("-" * 60)
    for file_path, sample_id in files:
        display_id = sample_id or "UNKNOWN"
        typer.echo(f"  {file_path.name} → Sample ID: {display_id}")
    
    if not typer.confirm("\nProceed with import?"):
        typer.echo("Cancelled")
        raise typer.Exit(0)
    
    # Get parser
    try:
        parser_class = registry.get_parser(parser, "spectra")
    except KeyError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    
    # Import files
    async def _import():
        async with Project(path=project_path, create_if_not_exists=False) as project:
            # Get or create group
            subsets = await project.get_subsets()
            subset = next((s for s in subsets if s.name == group), None)
            
            if not subset:
                subset = await project.add_subset(group)
                typer.echo(f"✓ Created group: {group}")
            
            # Import with progress
            with typer.progressbar(
                files,
                label="Importing",
                show_pos=True
            ) as progress:
                for file_path, sample_id in progress:
                    # Use filename as sample_id if not detected
                    if not sample_id:
                        sample_id = file_path.stem
                    
                    try:
                        # Parse file
                        parser_instance = parser_class(str(file_path))
                        spectra_df = await parser_instance.parse_batch()
                        
                        # Add sample if not exists
                        sample = await project.get_sample_by_name(sample_id)
                        if not sample:
                            sample = await project.add_sample(
                                sample_id,
                                subset_id=subset.id
                            )
                        
                        # Add spectra file
                        spectra_file_id = await project.add_spectra_file(
                            sample.id,
                            parser,
                            str(file_path)
                        )
                        
                        # Add spectra
                        await project.add_spectra_batch(spectra_file_id, spectra_df)
                        
                    except Exception as e:
                        typer.echo(f"\n  Error importing {file_path.name}: {e}", err=True)
            
            typer.echo(f"\n✓ Imported {len(files)} file(s) successfully")
    
    try:
        asyncio.run(_import())
        config.update_last_import_folder(folder)
    except Exception as e:
        typer.echo(f"\nError during import: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def mgf_file(
    project_path: Annotated[str, typer.Argument(help="Path to .dasmix project file")],
    file: Annotated[str, typer.Option("--file", "-f", help="Path to MGF file")] = ...,
    sample_id: Annotated[str, typer.Option("--sample-id", "-s", help="Sample ID")] = ...,
    parser: Annotated[str, typer.Option("--parser", help="Parser name")] = "MGF",
    group: Annotated[str, typer.Option("--group", "-g", help="Group to assign sample")] = "Control"
):
    """
    Import single MGF file.
    
    Example:
        dasmixer project.dasmix import mgf-file \\
            --file /data/sample1.mgf \\
            --sample-id "Sample1" \\
            --group Control
    """
    project_path = Path(project_path)
    file_path = Path(file)
    
    if not project_path.exists():
        typer.echo(f"Error: Project file not found: {project_path}", err=True)
        raise typer.Exit(1)
    
    if not file_path.exists():
        typer.echo(f"Error: File not found: {file}", err=True)
        raise typer.Exit(1)
    
    # Get parser
    try:
        parser_class = registry.get_parser(parser, "spectra")
    except KeyError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    
    # Import file
    async def _import():
        async with Project(path=project_path, create_if_not_exists=False) as project:
            # Get or create group
            subsets = await project.get_subsets()
            subset = next((s for s in subsets if s.name == group), None)
            
            if not subset:
                subset = await project.add_subset(group)
                typer.echo(f"✓ Created group: {group}")
            
            typer.echo(f"Importing {file_path.name}...")
            
            # Parse file
            parser_instance = parser_class(str(file_path))
            spectra_df = await parser_instance.parse_batch()
            
            # Add sample if not exists
            sample = await project.get_sample_by_name(sample_id)
            if not sample:
                sample = await project.add_sample(
                    sample_id,
                    subset_id=subset.id
                )
            
            # Add spectra file
            spectra_file_id = await project.add_spectra_file(
                sample.id,
                parser,
                str(file_path)
            )
            
            # Add spectra
            await project.add_spectra_batch(spectra_file_id, spectra_df)
            
            typer.echo(f"✓ Imported {len(spectra_df)} spectra from {file_path.name}")
            typer.echo(f"  Sample: {sample_id}")
            typer.echo(f"  Group: {group}")
    
    try:
        asyncio.run(_import())
        config.update_last_import_folder(str(file_path.parent))
    except Exception as e:
        typer.echo(f"Error importing file: {e}", err=True)
        raise typer.Exit(1)


@app.command()
async def ident_file(
    project_path: Annotated[str, typer.Argument(help="Path to .dasmix project file")],
    file: Annotated[str, typer.Option("--file", "-f", help="Path to identification file")] = ...,
    sample_id: Annotated[str, typer.Option("--sample-id", "-s", help="Sample name (must exist)")] = ...,
    parser: Annotated[str, typer.Option("--parser", help="Parser name (e.g., PowerNovo2)")] = ...,
    tool: Annotated[str, typer.Option("--tool", help="Tool name (must exist in project)")] = ...,
    spectra_file_id: Annotated[int, typer.Option("--spectra-file-id", help="Spectra file ID (auto-detected if omitted)")] = None,
):
    """
    Import single identification file.
    
    Requires that corresponding spectra file is already imported for the sample
    and the tool has been added to the project.
    
    Example:
        dasmixer project.dasmix import ident-file \\
            --file /data/sample1_powernovo.csv \\
            --sample-id "Sample1" \\
            --parser PowerNovo2 \\
            --tool PowerNovo2
    """
    await _import_ident_file_internal(
        project_path=Path(project_path),
        file_path=Path(file),
        sample_name=sample_id,
        parser_name=parser,
        tool_name=tool,
        spectra_file_id=spectra_file_id,
    )


async def _import_ident_file_internal(
    project_path: Path,
    file_path: Path,
    sample_name: str,
    parser_name: str,
    tool_name: str,
    spectra_file_id: int | None = None,
    quiet: bool = False,
) -> int:
    """Internal helper to import a single identification file."""
    from dasmixer.api.config import config as app_config

    if not project_path.exists():
        typer.echo(f"Error: Project file not found: {project_path}", err=True)
        raise typer.Exit(1)

    if not file_path.exists():
        typer.echo(f"Error: File not found: {file_path}", err=True)
        raise typer.Exit(1)

    async with Project(path=project_path, create_if_not_exists=False) as project:
        # Find sample by name
        samples = await project.get_samples()
        sample = next((s for s in samples if s.name == sample_name), None)
        if not sample:
            typer.echo(f"Error: Sample '{sample_name}' not found", err=True)
            raise typer.Exit(1)

        # Find tool by name
        tools = await project.get_tools()
        tool_obj = next((t for t in tools if t.name == tool_name), None)
        if not tool_obj:
            typer.echo(f"Error: Tool '{tool_name}' not found. Use 'dasmixer-cli tool add' first", err=True)
            raise typer.Exit(1)

        # Determine spectra_file_id
        if spectra_file_id is None:
            sf_df = await project.get_spectra_files(sample_id=sample.id)
            if sf_df.empty:
                typer.echo(f"Error: No spectra files found for sample '{sample_name}'", err=True)
                raise typer.Exit(1)
            sf_sorted = sf_df.iloc[sf_df["path"].apply(lambda p: Path(p).name).argsort()]
            spectra_file_id = int(sf_sorted.iloc[0]["id"])

        # Get parser
        try:
            parser_class = registry.get_parser(parser_name, "identification")
        except KeyError:
            typer.echo(f"Error: Unknown identification parser '{parser_name}'", err=True)
            raise typer.Exit(1)

        # Create identification file entry
        ident_file_id = await project.add_identification_file(
            spectra_file_id=spectra_file_id,
            tool_id=tool_obj.id,
            file_path=str(file_path),
        )

        # Get spectra ID list
        parser_instance = parser_class(str(file_path))
        spectra_id_field = getattr(parser_instance, 'spectra_id_field', 'spectrum_id')
        spectra_list = await project.get_spectra_idlist(spectra_file_id, by=spectra_id_field)

        if not spectra_list:
            typer.echo(f"Warning: No spectra found for spectra file {spectra_file_id}", err=True)
            return 0

        # Build lookup: ID → spectre_id
        spectra_map = {str(s[spectra_id_field]): s['spectre_id'] for s in spectra_list}

        if not quiet:
            typer.echo(f"Importing {file_path.name}...")

        total = 0
        batch_size = getattr(app_config, 'identification_batch_size', 1000)
        async for batch_df, _ in parser_instance.parse_batch(batch_size=batch_size):
            if batch_df.empty:
                continue
            batch_df['ident_file_id'] = ident_file_id
            # Map spectra IDs
            id_col = spectra_id_field
            if id_col in batch_df.columns:
                batch_df['spectre_id'] = batch_df[id_col].astype(str).map(spectra_map)
                matched = batch_df['spectre_id'].notna()
                unmatched_count = (~matched).sum()
                if unmatched_count > 0 and not quiet:
                    typer.echo(f"  Warning: {unmatched_count} identifications unmatched to spectra")
                batch_df = batch_df[matched].copy()
            if not batch_df.empty:
                await project.add_identifications_batch(batch_df)
                total += len(batch_df)

        await project.save()

        if not quiet:
            typer.echo(f"✓ Imported {total} identifications from {file_path.name}")
            typer.echo(f"  Tool: {tool_name}")
            typer.echo(f"  Sample: {sample_name}")
            typer.echo(f"  Spectra file ID: {spectra_file_id}")
        return total


@app.command()
async def ident_pattern(
    project_path: Annotated[str, typer.Argument(help="Path to .dasmix project file")],
    folder: Annotated[str, typer.Option("--folder", "-f", help="Folder to search")] = ...,
    file_pattern: Annotated[str, typer.Option("--pattern", "-p", help="File pattern")] = "*.csv",
    id_pattern: Annotated[str, typer.Option("--id-pattern", "-i", help="Sample ID pattern")] = "{id}*.csv",
    parser: Annotated[str, typer.Option("--parser", help="Parser name (e.g., PowerNovo2)")] = ...,
    tool: Annotated[str, typer.Option("--tool", help="Tool name")] = ...,
):
    """
    Import identification files using pattern matching.
    
    Requires that corresponding spectra files are already imported for the samples
    and the tool has been added to the project.
    
    Example:
        dasmixer project.dasmix import ident-pattern \\
            --folder /data/results \\
            --pattern "*.csv" \\
            --id-pattern "{id}_powernovo.csv" \\
            --parser PowerNovo2 \\
            --tool PowerNovo2
    """
    project_path_obj = Path(project_path)
    folder_path = Path(folder)

    if not project_path_obj.exists():
        typer.echo(f"Error: Project file not found: {project_path}", err=True)
        raise typer.Exit(1)

    if not folder_path.exists():
        typer.echo(f"Error: Folder not found: {folder}", err=True)
        raise typer.Exit(1)

    try:
        files = seek_files(folder_path, file_pattern, id_pattern)
    except Exception as e:
        typer.echo(f"Error searching files: {e}", err=True)
        raise typer.Exit(1)

    if not files:
        typer.echo("No files found matching pattern", err=True)
        raise typer.Exit(1)

    typer.echo(f"\nFound {len(files)} file(s):")
    typer.echo("-" * 60)
    for file_path, sid in files:
        display_id = sid or "UNKNOWN"
        typer.echo(f"  {file_path.name} → Sample ID: {display_id}")

    if not typer.confirm("\nProceed with import?"):
        typer.echo("Cancelled")
        raise typer.Exit(0)

    # --- Pre-pass: pair identification files with spectre_file by basename ---
    from dasmixer.utils.ident_spectra_pairing import resolve_ident_to_spectra_mapping

    # Normalize sid (same logic as main loop)
    normalized: list[tuple[Path, str]] = []
    for fp, sid in files:
        sid = sid or fp.stem
        normalized.append((fp, sid))

    # Group by normalized sid
    groups: dict[str, list[Path]] = defaultdict(list)
    for fp, sid in normalized:
        groups[sid].append(fp)

    spectra_map: dict[str, int] = {}   # str(path) -> spectra_file_id
    unmatched: set[str] = set()

    async with Project(path=project_path_obj, create_if_not_exists=False) as _pre_pass_project:
        for sid, ident_fps in groups.items():
            sample_obj = await _pre_pass_project.get_sample_by_name(sid)
            if sample_obj is None:
                continue  # will be caught by _import_ident_file_internal
            sf_df = await _pre_pass_project.get_spectra_files(sample_id=sample_obj.id)
            if sf_df.empty:
                continue  # will be caught by _import_ident_file_internal
            spectra_files = sf_df[["id", "path"]].to_dict("records")
            mapping, unm = resolve_ident_to_spectra_mapping(
                [str(fp) for fp in ident_fps], spectra_files
            )
            spectra_map.update(mapping)
            for p in unm:
                unmatched.add(p)

    total_imported = 0
    total_files = 0
    errors = []

    for file_path, sid in files:
        if not sid:
            sid = file_path.stem

        fp_str = str(file_path)
        if fp_str in unmatched:
            typer.echo(f"  Warning: {file_path.name} has no matching spectre_file (more identification files than spectre_file in sample), skipped")
            continue

        try:
            result = await _import_ident_file_internal(
                project_path=project_path_obj,
                file_path=file_path,
                sample_name=sid,
                parser_name=parser,
                tool_name=tool,
                spectra_file_id=spectra_map.get(fp_str),
                quiet=True,
            )
            total_imported += result
            total_files += 1
            typer.echo(f"  ✓ {file_path.name}: {result} identifications")
        except typer.Exit:
            raise
        except Exception as e:
            errors.append(f"{file_path.name}: {e}")
            typer.echo(f"  ✗ {file_path.name}: {e}", err=True)

    typer.echo(f"\n✓ Imported {total_files} files, {total_imported} identifications total")
    if errors:
        typer.echo(f"  {len(errors)} file(s) had errors", err=True)


@app.command()
def fasta(
    project_path: Annotated[str, typer.Argument(help="Path to .dasmix project file")],
    file: Annotated[str, typer.Option("--file", "-f", help="Path to FASTA file")] = ...,
    batch_size: Annotated[int, typer.Option("--batch-size", help="Batch size for import")] = 100,
):
    """
    Import proteins from a FASTA file.
    
    Example:
        dasmixer project.dasmix import fasta \\
            --file /data/uniprot.fasta \\
            --batch-size 200
    """
    project_path_obj = Path(project_path)
    file_path = Path(file)

    if not project_path_obj.exists():
        typer.echo(f"Error: Project file not found: {project_path}", err=True)
        raise typer.Exit(1)

    if not file_path.exists():
        typer.echo(f"Error: FASTA file not found: {file}", err=True)
        raise typer.Exit(1)

    from dasmixer.api.inputs.proteins.fasta import FastaParser

    async def _import():
        parser = FastaParser(str(file_path))
        valid = await parser.validate()
        if not valid:
            typer.echo("Error: Invalid FASTA file", err=True)
            raise typer.Exit(1)

        async with Project(path=project_path_obj, create_if_not_exists=False) as project:
            total_imported = 0
            batch_count = 0
            uniprot_count = 0
            generic_count = 0

            async for batch_df in parser.parse_batch(batch_size=batch_size):
                if "is_uniprot" in batch_df.columns:
                    uniprot_count += batch_df["is_uniprot"].sum()
                uniprot_in_batch = batch_df.get("is_uniprot", pd.Series([False] * len(batch_df))).sum()
                generic_count += len(batch_df) - uniprot_in_batch
                await project.add_proteins_batch(batch_df)
                total_imported += len(batch_df)
                batch_count += 1
                typer.echo(f"  Batch {batch_count}: {total_imported} proteins...")

            await project.save()
            typer.echo(f"✓ Imported {total_imported} proteins from {file_path.name}")
            typer.echo(f"  UniProt entries: {int(uniprot_count)}")
            typer.echo(f"  Generic entries: {int(generic_count)}")

    try:
        import asyncio

        import pandas as pd
        asyncio.run(_import())
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error importing FASTA: {e}", err=True)
        raise typer.Exit(1)


@app.command(name="maxquant")
def import_maxquant(
    project_path: str = typer.Argument(..., help="Path to .dasmix project file (created if missing)"),
    mqpar_path: str = typer.Argument(..., help="Path to mqpar.xml"),
    fasta_path: str | None = typer.Option(None, "--fasta-path", help="Override FASTA file path"),
    raw_path: str | None = typer.Option(None, "--raw-path", help="Override RAW files parent directory"),
    txt_path: str | None = typer.Option(None, "--txt-path", help="Override txt results folder path"),
    tool_name: str = typer.Option("MaxQuant", "--tool-name", help="Tool name"),
    subset_name: str = typer.Option("MaxQuant Import", "--subset-name", help="Subset (group) name"),
    keep_contaminants: bool = typer.Option(False, "--keep-contaminants", help="Keep 'Potential contaminant' identifications"),
    delete_temporary_files: bool = typer.Option(True, "--delete-temporary-files/--keep-temporary-files", help="Delete temporary MGF/CSV after import"),
    import_fasta: bool = typer.Option(True, "--import-fasta/--no-import-fasta", help="Import proteins from FASTA"),
    fasta_is_uniprot: bool = typer.Option(True, "--fasta-uniprot/--fasta-generic", help="FASTA headers are UniProt-formatted"),
    on_duplicates: str = typer.Option("skip", "--on-duplicates", help="skip|reload|add_as_new"),
):
    """
    Import a full MaxQuant project (mqpar.xml + txt + apl spectra) into a DASMixer project.

    If PROJECT_PATH does not exist, a new project is created (unlike the GUI flow,
    where import always targets an already-open project).

    Example:
        dasmixer-cli import maxquant project.dasmix /data/mq/mqpar.xml --tool-name MaxQuant
    """
    from dasmixer.api.config import config as app_config
    from dasmixer.api.inputs.complex.MaxQuantProject.importer import (
        MaxQuantImportOptions,
        run_maxquant_import,
    )
    from dasmixer.api.inputs.complex.MaxQuantProject.mqpar_parser import (
        get_paths_from_mqpar,
    )

    async def _run():
        mqpar_paths = get_paths_from_mqpar(mqpar_path)

        effective_fasta = Path(fasta_path) if fasta_path else mqpar_paths.fasta_path.path
        effective_raw = (
            Path(raw_path) if raw_path
            else (mqpar_paths.raw_parents[0].path if mqpar_paths.raw_parents else None)
        )
        effective_txt = Path(txt_path) if txt_path else mqpar_paths.custom_txt_path.path

        if effective_raw is None or not effective_raw.is_dir():
            typer.echo(f"Error: RAW files directory not found: {effective_raw}", err=True)
            raise typer.Exit(1)
        if not effective_txt.is_dir():
            typer.echo(f"Error: txt results folder not found: {effective_txt}", err=True)
            raise typer.Exit(1)
        if import_fasta and not effective_fasta.is_file():
            typer.echo(f"Error: FASTA file not found: {effective_fasta}", err=True)
            raise typer.Exit(1)

        project_file = Path(project_path)
        create_new = not project_file.exists()

        async with Project(path=project_file, create_if_not_exists=create_new) as project:
            # Check tool.parser — hard error, spec section 1 item 10
            tools = await project.get_tools()
            existing_tool = next((t for t in tools if t.name == tool_name), None)
            if existing_tool is not None and existing_tool.parser != "MaxQuant":
                typer.echo(
                    f"Error: Tool '{tool_name}' already exists with parser '{existing_tool.parser}' "
                    f"(expected 'MaxQuant')", err=True
                )
                raise typer.Exit(1)

            options = MaxQuantImportOptions(
                mqpar_path=Path(mqpar_path),
                txt_path=effective_txt,
                raw_parent=effective_raw,
                fasta_path=effective_fasta if import_fasta else None,
                import_fasta=import_fasta,
                fasta_is_uniprot=fasta_is_uniprot,
                tool_name=tool_name,
                subset_name=subset_name,
                delete_temp_files=delete_temporary_files,
                keep_contaminants=keep_contaminants,
                selected_raw_names=[rf.name for rf in mqpar_paths.raw_files],
                on_duplicates=on_duplicates,
            )

            async def _progress(p):
                typer.echo(f"  [{p.stage}] {p.message}")

            summary = await run_maxquant_import(project, options, progress_callback=_progress)

        typer.echo(f"Import complete: {summary['samples_processed']} sample(s), "
                   f"{summary['spectra_imported']} spectra, "
                   f"{summary['identifications_imported']} identifications")
        if summary['proteins_imported']:
            typer.echo(f"  Proteins: {summary['proteins_imported']}")
        if summary['skipped_duplicates']:
            typer.echo(f"  Skipped duplicates: {summary['skipped_duplicates']}")

        if create_new:
            app_config.add_recent_project(str(project_file))

    try:
        asyncio.run(_run())
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error during MaxQuant import: {e}", err=True)
        raise typer.Exit(1)
