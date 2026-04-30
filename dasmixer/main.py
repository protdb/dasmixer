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

from dasmixer.versions import APP_VERSION

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
        typer.echo(f"DASMixer version {APP_VERSION}")
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


def _ensure_chrome() -> None:
    """Download Chrome for Kaleido/choreographer on first run.

    Chrome is stored in {app_dir}/chrome/ (e.g. %APPDATA%/dasmixer/chrome/ on
    Windows) so it survives application updates and works across users/machines.
    The download is skipped if the expected executable already exists.

    After locating (or downloading) Chrome, sets the BROWSER_PATH environment
    variable so choreographer picks it up in the current process without needing
    to write anything into the frozen _internal directory.
    """
    import os
    import platform
    import sys
    import kaleido
    from choreographer.cli._cli_utils import get_google_supported_platform_string

    app_dir = Path(typer.get_app_dir("dasmixer"))
    chrome_dir = app_dir / "chrome"

    # Determine expected exe path for the current platform
    arch, *_ = get_google_supported_platform_string()
    if not arch:
        print("[Kaleido] WARNING: unsupported platform, skipping Chrome setup.", file=sys.stderr)
        return

    if platform.system().startswith("Win"):
        chrome_exe = chrome_dir / f"chrome-{arch}" / "chrome.exe"
    elif platform.system().startswith("Darwin"):
        chrome_exe = (
            chrome_dir
            / f"chrome-{arch}"
            / "Google Chrome for Testing.app"
            / "Contents"
            / "MacOS"
            / "Google Chrome for Testing"
        )
    else:  # Linux
        chrome_exe = chrome_dir / f"chrome-{arch}" / "chrome"

    if not chrome_exe.exists():
        print(f"[Kaleido] Downloading Chrome to {chrome_dir} ...")
        try:
            kaleido.get_chrome_sync(path=chrome_dir)
            print(f"[Kaleido] Chrome installed: {chrome_exe}")
        except Exception as exc:
            print(f"[Kaleido] WARNING: could not install Chrome: {exc}", file=sys.stderr)
            return

    # Tell choreographer where Chrome lives — checked first in get_browser_path()
    os.environ["BROWSER_PATH"] = str(chrome_exe)
    print(f"[Kaleido] Chrome ready: {chrome_exe}")


if __name__ == '__main__':
    # Multiprocessing for builds support
    multiprocessing.freeze_support()
    # Ensure Chrome for Kaleido is available in the user app directory
    _ensure_chrome()
    app()
