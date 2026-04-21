"""GUI utility helpers."""

from __future__ import annotations

import flet as ft
from flet.controls.base_page import BasePage


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
