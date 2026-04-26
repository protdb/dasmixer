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

import logging
import typer
import multiprocessing
from typing import Annotated
from pathlib import Path

# Configure logging based on saved settings
try:
    from dasmixer.api.config import config as _app_config
    from dasmixer.gui.views.settings_view import _apply_logging_config
    _apply_logging_config(_app_config)
except Exception as _log_init_exc:
    print(f"[Logging] Failed to configure logging: {_log_init_exc}")

# Load external plugins before anything else.
# Results are stored as module-level variable so PluginsView can access them.
try:
    from dasmixer.api.plugin_loader import load_identification_plugins, load_report_plugins
    _plugin_load_results: list[dict] = (
        load_identification_plugins() + load_report_plugins()
    )
    _plugin_errors = [r for r in _plugin_load_results if r.get("error")]
    if _plugin_errors:
        for r in _plugin_errors:
            print(f"[Plugin warning] '{r['id']}': {r['error']}")
except Exception as _plugin_load_exc:
    _plugin_load_results = []
    print(f"[Plugin loader] Failed to initialize plugin loader: {_plugin_load_exc}")

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
        from dasmixer.gui.app import run_gui
        run_gui(file_path)


# Register CLI command modules
from dasmixer.cli.commands import project, subset, import_data

app.add_typer(project.app, name="create", help="Create new project")
app.add_typer(subset.app, name="subset", help="Manage comparison groups")
app.add_typer(import_data.app, name="import", help="Import data files")


if __name__ == '__main__':
    multiprocessing.freeze_support()
    app()
