"""CLI commands for portable project utilities (checkpoint, vacuum)."""

import typer
from pathlib import Path
from typing import Annotated
import asyncio
from dasmixer.api.project.project import Project

app = typer.Typer(help="Portable project utilities")


@app.command()
def checkpoint(
    project_path: Annotated[str, typer.Argument(help="Path to .dasmix project file")],
):
    """Save uncommitted WAL changes into the main database file."""
    path = Path(project_path)
    if not path.exists():
        typer.echo(f"Error: file not found: {path}", err=True)
        raise typer.Exit(1)

    async def _run():
        async with Project(path=path, create_if_not_exists=False) as project:
            await project.save(checkpoint=True)

    try:
        asyncio.run(_run())
        typer.echo(f"✓ Checkpoint done: {path}")
    except Exception as e:
        typer.echo(f"Error during checkpoint: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def vacuum(
    project_path: Annotated[str, typer.Argument(help="Path to .dasmix project file")],
):
    """Compact the database file by running SQLite VACUUM."""
    path = Path(project_path)
    if not path.exists():
        typer.echo(f"Error: file not found: {path}", err=True)
        raise typer.Exit(1)

    async def _run():
        async with Project(path=path, create_if_not_exists=False) as project:
            await project.save(checkpoint=True)
            await project.vacuum()

    try:
        asyncio.run(_run())
        typer.echo(f"✓ Vacuum complete: {path}")
    except Exception as e:
        typer.echo(f"Error during vacuum: {e}", err=True)
        raise typer.Exit(1)
