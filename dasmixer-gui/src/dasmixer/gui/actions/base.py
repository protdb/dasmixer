"""Base class for all GUI action handlers."""

import flet as ft

from dasmixer.api.project.project import Project
from dasmixer.gui.views.tabs.peptides.dialogs.progress_dialog import ProgressDialog
from dasmixer.gui.utils import show_snack


class BaseAction:
    """
    Base class for calculation action handlers.

    Provides helpers for progress dialogs and snackbar messages.
    All concrete action classes inherit from this.
    """

    def __init__(self, project: Project, page: ft.Page):
        self.project = project
        self.page = page

    # ------------------------------------------------------------------
    # Snackbar helpers
    # ------------------------------------------------------------------

    def show_error(self, message: str) -> None:
        show_snack(self.page, message, ft.Colors.RED_400)
        self.page.update()

    def show_success(self, message: str) -> None:
        show_snack(self.page, message, ft.Colors.GREEN_400)
        self.page.update()

    def show_warning(self, message: str) -> None:
        show_snack(self.page, message, ft.Colors.ORANGE_400)
        self.page.update()

    def show_info(self, message: str) -> None:
        show_snack(self.page, message, ft.Colors.BLUE_400)
        self.page.update()

    # ------------------------------------------------------------------
    # Progress dialog helpers
    # ------------------------------------------------------------------

    def make_progress_dialog(self, title: str, stoppable: bool = False) -> ProgressDialog:
        return ProgressDialog(self.page, title, stoppable=stoppable)
