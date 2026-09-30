"""Reusable export dialog for reports (GUI-side)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Awaitable

import flet as ft

if TYPE_CHECKING:
    pass


class ExportDialog:
    """Modal dialog for choosing export path, formats, and XLSX mode.

    Usage::

        dialog = ExportDialog(self.page, on_export_callback)
        await dialog.show()
    """

    def __init__(
        self,
        page: ft.Page,
        on_export: Callable[[str, set[str], str], Awaitable[None]],
    ):
        self.page = page
        self._on_export = on_export
        self._dialog: ft.AlertDialog | None = None

        # --- Controls ---
        self._path_field = ft.TextField(
            label="Save path",
            read_only=True,
            expand=True,
        )
        self._browse_btn = ft.ElevatedButton(
            content=ft.Text("Browse"),
            icon=ft.Icons.FOLDER_OPEN,
            on_click=self._on_browse,
        )

        self._docx_cb = ft.Checkbox(label="DOCX", value=True)
        self._html_cb = ft.Checkbox(label="HTML", value=True)
        self._xlsx_cb = ft.Checkbox(label="XLSX", value=True)

        self._xlsx_mode_dropdown = ft.Dropdown(
            label="XLSX mode",
            options=[
                ft.DropdownOption(key="all", text="All tables"),
                ft.DropdownOption(key="large_only", text="Large tables only"),
            ],
            value="all",
            visible=True,
        )

        # Show/hide dropdown based on XLSX checkbox
        self._xlsx_cb.on_change = self._on_xlsx_checkbox_changed

        self._save_path: str | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def show(self) -> None:
        """Open the dialog."""
        self._save_path = None
        self._path_field.value = ""

        self._dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Export Report"),
            content=self._build_content(),
            actions=[
                ft.TextButton("Cancel", on_click=self._close),
                ft.ElevatedButton(content=ft.Text("Export"), on_click=self._do_export),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.overlay.append(self._dialog)
        self._dialog.open = True
        self.page.update()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_content(self) -> ft.Control:
        return ft.Column(
            [
                ft.Row(
                    [self._path_field, self._browse_btn],
                    spacing=8,
                ),
                ft.Container(height=10),
                ft.Text("Formats:", weight=ft.FontWeight.BOLD),
                self._docx_cb,
                self._html_cb,
                self._xlsx_cb,
                self._xlsx_mode_dropdown,
            ],
            spacing=8,
            width=450,
        )

    def _on_xlsx_checkbox_changed(self, e) -> None:
        self._xlsx_mode_dropdown.visible = bool(self._xlsx_cb.value)
        if self.page:
            self.page.update()

    async def _on_browse(self, e) -> None:
        folder_path = await ft.FilePicker().get_directory_path(
            dialog_title="Select Export Folder"
        )
        if folder_path:
            self._path_field.value = folder_path
            if self.page:
                self.page.update()

    async def _do_export(self, e) -> None:
        save_path = (self._path_field.value or "").strip()
        if not save_path:
            from dasmixer.gui.utils import show_snack
            show_snack(self.page, "Please select a save path", ft.Colors.RED_400)
            self.page.update()
            return

        formats: set[str] = set()
        if self._docx_cb.value:
            formats.add("docx")
        if self._html_cb.value:
            formats.add("html")
        if self._xlsx_cb.value:
            formats.add("xlsx")

        if not formats:
            from dasmixer.gui.utils import show_snack
            show_snack(self.page, "Please select at least one format", ft.Colors.RED_400)
            self.page.update()
            return

        xlsx_mode = self._xlsx_mode_dropdown.value if self._xlsx_cb.value else "all"

        # Close dialog first
        self._close(None)
        self.page.update()

        # Trigger export
        await self._on_export(save_path, formats, xlsx_mode)

    def _close(self, e) -> None:
        if self._dialog is not None:
            self._dialog.open = False
        self.page.update()
