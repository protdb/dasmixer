"""GUI utility helpers."""

from __future__ import annotations

import multiprocessing
import sys
from pathlib import Path

import flet as ft
from flet.controls.base_page import BasePage


# ---------------------------------------------------------------------------
# Global child-process registry
# ---------------------------------------------------------------------------
# Any component that spawns a subprocess (e.g. PlotlyViewer webview) should
# register it here.  DASMixerApp._shutdown() kills all registered processes
# on window close so they don't keep the console alive.

_child_processes: list[multiprocessing.Process] = []


def register_child_process(proc: multiprocessing.Process) -> None:
    """Register a child process for cleanup on app exit."""
    # Prune already-dead entries while we're here.
    _child_processes[:] = [p for p in _child_processes if p.is_alive()]
    _child_processes.append(proc)


def get_child_processes() -> list[multiprocessing.Process]:
    """Return the live child-process list (shared reference)."""
    return _child_processes


def get_asset_path(relative: str) -> Path:
    """
    Resolve path to a bundled asset, compatible with both development and
    PyInstaller frozen environments.

    In a PyInstaller bundle (sys.frozen == True) assets are extracted to
    sys._MEIPASS at startup. In development the assets directory lives
    alongside this file at ``dasmixer/gui/assets/``.

    Args:
        relative: Asset path relative to the ``assets/`` directory root,
                  e.g. ``"logo_header.png"`` or ``"icons/icon_256.ico"``.

    Returns:
        Resolved absolute :class:`pathlib.Path`.  The file is not guaranteed
        to exist — callers should check ``.exists()`` when required.
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)
    else:
        # Same directory as this file: dasmixer/gui/utils.py → dasmixer/gui/
        base = Path(__file__).resolve().parent
    return base / "assets" / relative


def show_snack(page: ft.Page | BasePage, message: str, color: str) -> None:
    """
    Display a SnackBar notification.

    Compatible with Flet 0.80+ where page.snack_bar has been removed.
    Uses page.show_dialog() which is the correct API for DialogControl subclasses.

    Args:
        page: Flet page instance
        message: Text to display
        color: Background color (e.g. ft.Colors.GREEN_400)
    """
    page.show_dialog(
        ft.SnackBar(
            content=ft.Text(message),
            bgcolor=color,
        )
    )


def cleanup_temp_html_files(max_age_hours: float = 24.0) -> None:
    """
    Remove stale DASMixer temporary HTML files older than ``max_age_hours``.

    Cleans up files created by Browser-mode interactive viewers
    (``dasmixer_plot_*.html`` and ``dasmixer_report_*.html``).
    Called once when the application starts.

    Only files whose modification time is older than ``max_age_hours`` are
    removed, so graphs still open in a browser (including those produced by
    a concurrently running DASMixer instance) are left intact.

    The target directory is platform dependent — see
    :func:`dasmixer.api.config.get_temp_html_dir` (system temp on Windows,
    ``~/.cache/dasmixer/tmp/plots/`` on Linux/macOS).

    Args:
        max_age_hours: Files older than this many hours are removed.
    """
    import time

    from dasmixer.api.config import get_temp_html_dir
    from dasmixer.utils import logger

    temp_dir = get_temp_html_dir()
    cutoff = time.time() - max_age_hours * 3600
    for pattern in ("dasmixer_plot_*.html", "dasmixer_report_*.html"):
        for file_path in temp_dir.glob(pattern):
            try:
                if file_path.stat().st_mtime < cutoff:
                    file_path.unlink()
                    logger.debug(f"[cleanup] Removed stale temp file: {file_path}")
            except Exception as e:
                logger.debug(f"[cleanup] Could not remove {file_path}: {e}")
