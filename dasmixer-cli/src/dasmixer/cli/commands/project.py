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


@app.command()
def configure(
    project_path: Annotated[str, typer.Argument(help="Path to .dasmix project file")],
    key: Annotated[str, typer.Option("--key", "-k", help="Setting key")] = None,
    value: Annotated[str, typer.Option("--value", "-v", help="Setting value")] = None,
    list_settings: Annotated[bool, typer.Option("--list", "-l", help="List all settings")] = False,
):
    """
    Configure project settings.
    """
    path = Path(project_path)
    if not path.exists():
        typer.echo(f"Error: Project file not found: {path}", err=True)
        raise typer.Exit(1)

    async def _run():
        async with Project(path=path, create_if_not_exists=False) as project:
            if list_settings:
                rows = await project.execute_query(
                    "SELECT key, value FROM project_settings ORDER BY key"
                )
                if not rows:
                    typer.echo("No settings configured.")
                    return
                typer.echo(f"{'Key':<35} {'Value'}")
                typer.echo("-" * 70)
                for row in rows:
                    typer.echo(f"{row['key']:<35} {row['value']}")
            else:
                if not key or value is None:
                    typer.echo("Error: --key and --value are required (or use --list)", err=True)
                    raise typer.Exit(1)
                await project.set_setting(key, value)
                await project.save()
                typer.echo(f"✓ Setting saved: {key} = {value}")

    try:
        asyncio.run(_run())
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)
