"""CLI commands for project management."""

import typer
from pathlib import Path
from typing import Annotated
import asyncio
from dasmixer.api.project.project import Project
from dasmixer.api.config import config

app = typer.Typer(help="Create new project")


@app.callback(invoke_without_command=True)
def create_project(
    ctx: typer.Context,
    project_path: Annotated[
        str,
        typer.Argument(help="Path to .dasmix project file to create"),
    ],
):
    """
    Create new empty project with default Control group.
    """
    path = Path(project_path)

    # Check if file exists
    if path.exists():
        if not typer.confirm(f"File {path} exists. Overwrite?"):
            typer.echo("Cancelled")
            raise typer.Exit(0)
        path.unlink()

    # Create project
    async def _create():
        async with Project(path=path, create_if_not_exists=True) as project:
            await project.add_subset(
                "Control",
                details="Default control group",
                display_color="#3B82F6",
            )
            typer.echo(f"✓ Created project: {path}")
            typer.echo("✓ Added default group: Control")

    try:
        asyncio.run(_create())
        config.add_recent_project(str(path))
    except Exception as e:
        typer.echo(f"Error creating project: {e}", err=True)
        raise typer.Exit(1)
