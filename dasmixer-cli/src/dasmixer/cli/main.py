"""
DASMixer CLI — entry point for the `dasmixer-cli` command.

Provides command-line tools for project management without GUI.
"""

import typer
from typing import Annotated
from pathlib import Path

from dasmixer.versions import APP_VERSION
from dasmixer.cli.commands import project, subset, import_data
from dasmixer.cli.commands import portable
from dasmixer.cli.commands import import_project as import_project_cmd

app = typer.Typer(
    name="dasmixer-cli",
    help="DASMixer CLI — manage projects without GUI",
    add_completion=False,
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option("--version", "-v", help="Show version and exit"),
    ] = False,
):
    """DASMixer CLI — управление проектами без GUI."""
    if version:
        typer.echo(f"DASMixer CLI {APP_VERSION}")
        raise typer.Exit(0)
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


app.add_typer(project.app, name="create", help="Create new project")
app.add_typer(subset.app, name="subset", help="Manage comparison groups")
app.add_typer(import_data.app, name="import", help="Import data files")
app.add_typer(portable.app, name="checkpoint", help="Save WAL to database file")
app.add_typer(portable.app, name="vacuum", help="Compact database file")
app.add_typer(import_project_cmd.app, name="import-project", help="Merge another project into this one")

if __name__ == "__main__":
    app()