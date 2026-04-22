"""GUI utility helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import flet as ft
from flet.controls.base_page import BasePage


def get_asset_path(relative: str) -> Path:
    """
    Resolve path to a bundled asset, compatible with both development and
    PyInstaller frozen environments.

    In a PyInstaller bundle (sys.frozen == True) assets are extracted to
    sys._MEIPASS at startup. In development the project root (two levels up
    from this file: dasmixer/gui/utils.py → project root) is used.

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
        # Two parents up: dasmixer/gui/utils.py → dasmixer/ → project root
        base = Path(__file__).resolve().parent.parent.parent
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
