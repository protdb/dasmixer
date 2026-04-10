"""CLI commands for importing data files."""

import typer
from pathlib import Path
import asyncio
from typing import Annotated
from dasmixer.api.project.project import Project
from dasmixer.api.inputs.registry import registry
from dasmixer.api.config import config
from dasmixer.utils.seek_files import seek_files

app = typer.Typer(help="Import data files")


@app.command()
def mgf_pattern(
    ctx: typer.Context,
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
    project_path = ctx.parent.parent.params.get('file_path')
    
    if not project_path:
        typer.echo("Error: Project path required", err=True)
        raise typer.Exit(1)
    
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
    ctx: typer.Context,
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
    project_path = ctx.parent.parent.params.get('file_path')
    
    if not project_path:
        typer.echo("Error: Project path required", err=True)
        raise typer.Exit(1)
    
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


# Note: ident-pattern and ident-file commands will be similar but for identifications
# They require knowledge of which tool and spectra file to link to
# Implementation will be added when identification parsers are registered

@app.command()
def ident_pattern(
    ctx: typer.Context,
    folder: Annotated[str, typer.Option("--folder", "-f", help="Folder to search")] = ...,
    file_pattern: Annotated[str, typer.Option("--pattern", "-p", help="File pattern")] = "*.csv",
    id_pattern: Annotated[str, typer.Option("--id-pattern", "-i", help="Sample ID pattern")] = "{id}*.csv",
    parser: Annotated[str, typer.Option("--parser", help="Parser name (e.g., PowerNovo2)")] = ...,
    tool: Annotated[str, typer.Option("--tool", help="Tool name (will be created if not exists)")] = ...
):
    """
    Import identification files using pattern matching.
    
    Note: This command requires that corresponding spectra files
    are already imported for the samples.
    
    Example:
        dasmixer project.dasmix import ident-pattern \\
            --folder /data/results \\
            --pattern "*.csv" \\
            --id-pattern "{id}_powernovo.csv" \\
            --parser PowerNovo2 \\
            --tool PowerNovo2
    """
    typer.echo("This command will be implemented when identification parsers are ready.")
    typer.echo("Coming in next development phase.")
    raise typer.Exit(0)


@app.command()
def ident_file(
    ctx: typer.Context,
    file: Annotated[str, typer.Option("--file", "-f", help="Path to identification file")] = ...,
    sample_id: Annotated[str, typer.Option("--sample-id", "-s", help="Sample ID")] = ...,
    parser: Annotated[str, typer.Option("--parser", help="Parser name")] = ...,
    tool: Annotated[str, typer.Option("--tool", help="Tool name")] = ...
):
    """
    Import single identification file.
    
    Note: This command requires that corresponding spectra file
    is already imported for the sample.
    
    Example:
        dasmixer project.dasmix import ident-file \\
            --file /data/sample1_powernovo.csv \\
            --sample-id "Sample1" \\
            --parser PowerNovo2 \\
            --tool PowerNovo2
    """
    typer.echo("This command will be implemented when identification parsers are ready.")
    typer.echo("Coming in next development phase.")
    raise typer.Exit(0)
