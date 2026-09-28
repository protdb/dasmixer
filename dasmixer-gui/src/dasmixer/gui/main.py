"""
DASMixer GUI — entry point for the `dasmixer` command.

Launches the Flet-based GUI. Optionally opens a project file.
Creates a new project if the file doesn't exist.
"""

import multiprocessing
from pathlib import Path
from typing import Annotated

import typer
from dasmixer.utils.logger import logger
from dasmixer.versions import APP_VERSION

# Configure logging based on saved settings.
# ``logger`` (from dasmixer.utils.logger) is already available with a basic
# console handler, so we can use it for any fallback messages even when the
# full AppConfig-based configuration fails.
try:
    from dasmixer.api.config import config as _app_config
    from dasmixer.gui.views.settings_view import _apply_logging_config
    _apply_logging_config(_app_config)
except Exception as _log_init_exc:
    logger.error("Failed to configure logging from AppConfig: %s", _log_init_exc)

# Load external plugins before anything else.
# Results are stored as module-level variable so PluginsView can access them.
try:
    from dasmixer.api.plugin_loader import (
        load_identification_plugins,
        load_report_plugins,
    )
    _plugin_load_results: list[dict] = (
        load_identification_plugins() + load_report_plugins()
    )
    _plugin_errors = [r for r in _plugin_load_results if r.get("error")]
    if _plugin_errors:
        for r in _plugin_errors:
            logger.warning("Plugin '%s': %s", r['id'], r['error'])
except Exception as _plugin_load_exc:
    _plugin_load_results = []
    logger.error("Failed to initialize plugin loader: %s", _plugin_load_exc)

# Bind GUI-side report forms to report classes (monkey-patch)
import dasmixer.gui.reports.forms  # noqa: F401

app = typer.Typer(
    name="dasmixer",
    help="DASMixer - Mass Spectrometry Data Integration Tool",
    add_completion=False,
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    file_path: Annotated[
        str | None,
        typer.Argument(
            help="Path to project file (.dasmix). Opens in GUI if no command specified."
        ),
    ] = None,
    version: Annotated[
        bool,
        typer.Option("--version", "-v", help="Show version and exit"),
    ] = False,
):
    """
    DASMixer — запустить GUI (опционально с файлом проекта).

    Run without arguments to launch GUI.
    Provide project path to open it in GUI.
    """
    if version:
        typer.echo(f"DASMixer version {APP_VERSION}")
        raise typer.Exit(0)

    # If no subcommand — launch GUI
    if ctx.invoked_subcommand is None:
        from dasmixer.gui.app import run_gui
        run_gui(file_path)


def _find_chrome_exe(chrome_dir: Path) -> Path | None:
    """Scan chrome_dir for the Chrome executable on any platform.

    Kaleido downloads Chrome into a subdirectory whose exact name depends on
    the kaleido/choreographer version (e.g. 'chrome-win64', 'chrome-linux64',
    'chrome-mac-arm64', etc.).  Rather than predicting the name, we glob for
    the executable after download.
    """
    import platform
    system = platform.system()
    if system.startswith("Win"):
        candidates = list(chrome_dir.glob("chrome-*/chrome.exe"))
    elif system.startswith("Darwin"):
        candidates = list(
            chrome_dir.glob(
                "chrome-*/Google Chrome for Testing.app"
                "/Contents/MacOS/Google Chrome for Testing"
            )
        )
    else:  # Linux
        candidates = list(chrome_dir.glob("chrome-*/chrome"))
    return candidates[0] if candidates else None


def _ensure_chrome() -> None:
    """Download Chrome for Kaleido/choreographer on first run.

    Chrome is stored in {app_dir}/chrome/ (e.g. %APPDATA%/dasmixer/chrome/ on
    Windows) so it survives application updates and works across users/machines.
    The download is skipped if the executable is already present.

    After locating (or downloading) Chrome, sets the BROWSER_PATH environment
    variable so choreographer picks it up in the current process without needing
    to write anything into the frozen _internal directory.
    """
    import os

    import kaleido

    app_dir = Path(typer.get_app_dir("dasmixer"))
    chrome_dir = app_dir / "chrome"

    # Check if Chrome is already installed (glob for any matching exe)
    chrome_exe = _find_chrome_exe(chrome_dir)

    if chrome_exe is None:
        logger.info("[Kaleido] Downloading Chrome to %s ...", chrome_dir)
        try:
            kaleido.get_chrome_sync(path=chrome_dir)
        except Exception as exc:
            logger.warning("[Kaleido] could not install Chrome: %s", exc)
            return
        # Locate the actual exe in the directory Kaleido created
        chrome_exe = _find_chrome_exe(chrome_dir)
        if chrome_exe is None:
            logger.warning(
                "[Kaleido] Chrome downloaded but executable not found in %s",
                chrome_dir,
            )
            return
        logger.info("[Kaleido] Chrome installed: %s", chrome_exe)

    # Tell choreographer where Chrome lives — checked first in get_browser_path()
    os.environ["BROWSER_PATH"] = str(chrome_exe)
    logger.info("[Kaleido] Chrome ready: %s", chrome_exe)


if __name__ == "__main__":
    # Multiprocessing for builds support
    multiprocessing.freeze_support()
    # Ensure Chrome for Kaleido is available in the user app directory
    _ensure_chrome()
    app()