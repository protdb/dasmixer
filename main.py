"""
DASMixer - Mass Spectrometry Data Integration Tool

Main entry point for both GUI and CLI modes.

Usage:
    # Launch GUI
    python main.py
    
    # Open project in GUI
    python main.py path/to/project.dasmix
    
    # Create new project (CLI)
    python main.py path/to/project.dasmix create
    
    # Other CLI commands
    python main.py path/to/project.dasmix subset add --name "Treatment"
    python main.py path/to/project.dasmix import mgf-pattern --folder ...
"""

import typer
from typing import Annotated
from pathlib import Path

app = typer.Typer(
    name="dasmixer",
    help="DASMixer - Mass Spectrometry Data Integration Tool",
    add_completion=False
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    file_path: Annotated[
        str | None,
        typer.Argument(
            help="Path to project file (.dasmix). Opens in GUI if no command specified."
        )
    ] = None,
    version: Annotated[
        bool,
        typer.Option("--version", "-v", help="Show version and exit")
    ] = False
):
    """
    DASMixer - Mass Spectrometry Data Integration Tool.
    
    Run without arguments to launch GUI.
    Provide project path to open it in GUI.
    Add command to execute CLI operations.
    """
    if version:
        typer.echo("DASMixer version 0.1.0")
        raise typer.Exit(0)
    
    # If no subcommand - launch GUI
    if ctx.invoked_subcommand is None:
        from gui.app import run_gui
        run_gui(file_path)


# Register CLI command modules
from cli.commands import project, subset, import_data

app.add_typer(project.app, name="create", help="Create new project")
app.add_typer(subset.app, name="subset", help="Manage comparison groups")
app.add_typer(import_data.app, name="import", help="Import data files")


if __name__ == '__main__':
    app()
