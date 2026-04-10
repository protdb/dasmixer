"""CLI commands for managing comparison groups (subsets)."""

import typer
from pathlib import Path
import asyncio
from dasmixer.api.project.project import Project
from typing import Annotated

app = typer.Typer(help="Manage comparison groups")


@app.command()
def add(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Group name")] = ...,
    details: Annotated[
        str | None,
        typer.Option("--details", "-d", help="Group description")
    ] = None,
    color: Annotated[
        str | None,
        typer.Option("--color", "-c", help="Display color (hex, e.g., #FF5733)")
    ] = None
):
    """Add new comparison group to project."""
    project_path = ctx.parent.parent.params.get('file_path')
    
    if not project_path:
        typer.echo("Error: Project path required", err=True)
        raise typer.Exit(1)
    
    project_path = Path(project_path)
    
    if not project_path.exists():
        typer.echo(f"Error: Project file not found: {project_path}", err=True)
        raise typer.Exit(1)
    
    async def _add():
        async with Project(path=project_path, create_if_not_exists=False) as project:
            subset = await project.add_subset(name, details, color)
            typer.echo(f"✓ Added group: {subset.name} (id={subset.id})")
            if details:
                typer.echo(f"  Description: {details}")
            if color:
                typer.echo(f"  Color: {color}")
    
    try:
        asyncio.run(_add())
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error adding group: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def delete(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="Group name to delete")] = ...
):
    """Delete comparison group from project."""
    project_path = ctx.parent.parent.params.get('file_path')
    
    if not project_path:
        typer.echo("Error: Project path required", err=True)
        raise typer.Exit(1)
    
    project_path = Path(project_path)
    
    if not project_path.exists():
        typer.echo(f"Error: Project file not found: {project_path}", err=True)
        raise typer.Exit(1)
    
    async def _delete():
        async with Project(path=project_path, create_if_not_exists=False) as project:
            # Find subset by name
            subsets = await project.get_subsets()
            subset = next((s for s in subsets if s.name == name), None)
            
            if not subset:
                typer.echo(f"Error: Group '{name}' not found", err=True)
                raise typer.Exit(1)
            
            # Confirm deletion
            if not typer.confirm(f"Delete group '{name}'?"):
                typer.echo("Cancelled")
                raise typer.Exit(0)
            
            await project.delete_subset(subset.id)
            typer.echo(f"✓ Deleted group: {name}")
    
    try:
        asyncio.run(_delete())
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error deleting group: {e}", err=True)
        raise typer.Exit(1)


@app.command("list")
def list_subsets(ctx: typer.Context):
    """List all comparison groups in project."""
    project_path = ctx.parent.parent.params.get('file_path')
    
    if not project_path:
        typer.echo("Error: Project path required", err=True)
        raise typer.Exit(1)
    
    project_path = Path(project_path)
    
    if not project_path.exists():
        typer.echo(f"Error: Project file not found: {project_path}", err=True)
        raise typer.Exit(1)
    
    async def _list():
        async with Project(path=project_path, create_if_not_exists=False) as project:
            subsets = await project.get_subsets()
            
            if not subsets:
                typer.echo("No groups found in project")
                return
            
            typer.echo("\nComparison Groups:")
            typer.echo("=" * 60)
            
            for subset in subsets:
                typer.echo(f"\n{subset.name} (ID: {subset.id})")
                if subset.details:
                    typer.echo(f"  Description: {subset.details}")
                if subset.display_color:
                    typer.echo(f"  Color: {subset.display_color}")
                
                # Count samples in this group
                samples = await project.get_samples(subset_id=subset.id)
                typer.echo(f"  Samples: {len(samples)}")
    
    try:
        asyncio.run(_list())
    except Exception as e:
        typer.echo(f"Error listing groups: {e}", err=True)
        raise typer.Exit(1)
