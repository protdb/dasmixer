"""CLI command for importing/merging another project."""

import typer
from pathlib import Path
from typing import Annotated
import asyncio
from dasmixer.api.project.project import Project

app = typer.Typer(help="Merge another project into this one")


@app.command()
def import_project(
    project_path: Annotated[str, typer.Argument(help="Target project (.dasmix)")],
    source_path: Annotated[str, typer.Argument(help="Source project to import from (.dasmix)")],
    tool_match: Annotated[str, typer.Option(help="Tool merge strategy: 'parser'|'name'|'none'")] = "parser",
    no_subset_match: Annotated[bool, typer.Option("--no-subset-match", help="Do not merge subsets by name")] = False,
    no_sample_match: Annotated[bool, typer.Option("--no-sample-match", help="Do not merge samples by name")] = False,
    update_settings: Annotated[bool, typer.Option("--update-settings", help="Replace target settings with source")] = False,
    conflict_suffix: Annotated[str, typer.Option(help="Suffix for conflicting names")] = "_1",
):
    """Merge another project into target project."""
    tgt = Path(project_path)
    src = Path(source_path)
    
    if not tgt.exists():
        typer.echo(f"Error: target project not found: {tgt}", err=True)
        raise typer.Exit(1)
    
    if not src.exists():
        typer.echo(f"Error: source project not found: {src}", err=True)
        raise typer.Exit(1)
    
    # Convert tool_match
    if tool_match == "none":
        tool_match_value = None
    elif tool_match == "name":
        tool_match_value = "name"
    else:
        tool_match_value = "parser"
    
    # Show summary
    typer.echo(f"Target: {tgt}")
    typer.echo(f"Source: {src}")
    typer.echo(f"Tool match: {tool_match_value}")
    typer.echo(f"Merge subsets: {not no_subset_match}")
    typer.echo(f"Merge samples: {not no_sample_match}")
    typer.echo(f"Update settings: {update_settings}")
    typer.echo(f"Conflict suffix: {conflict_suffix}")
    
    if not typer.confirm("Proceed with merge?"):
        typer.echo("Cancelled")
        raise typer.Exit(0)
    
    async def _run():
        async with Project(path=tgt, create_if_not_exists=False) as project:
            def status_callback(table: str, fraction: float):
                typer.echo(f"  [{fraction*100:3.0f}%] Importing {table}...")
            
            await project.import_project(
                source_path=src,
                tool_match=tool_match_value,
                subset_match=not no_subset_match,
                sample_match=not no_sample_match,
                project_settings_match=update_settings,
                conflict_suffix=conflict_suffix,
                status_callback=status_callback,
            )
    
    try:
        asyncio.run(_run())
        typer.echo("✓ Import complete")
    except Exception as e:
        typer.echo(f"Error during import: {e}", err=True)
        raise typer.Exit(1)
