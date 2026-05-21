"""UpdateRow — top-row component with Update button, loader, and threshold fields."""

from typing import Callable, Awaitable

import flet as ft


class UpdateRow(ft.Container):
    """Row with Update button, ProgressRing, min_proteins and min_idents fields."""

    def __init__(
        self,
        on_update_clicked: Callable[[], Awaitable[None]],
    ):
        super().__init__(
            padding=ft.padding.symmetric(horizontal=16, vertical=8),
        )
        self._on_update_clicked = on_update_clicked

        self._min_proteins_field = ft.TextField(
            label="Min proteins",
            value="30",
            width=130,
            keyboard_type=ft.KeyboardType.NUMBER,
            dense=True,
        )
        self._min_idents_field = ft.TextField(
            label="Min identifications",
            value="1000",
            width=170,
            keyboard_type=ft.KeyboardType.NUMBER,
            dense=True,
        )
        self._update_loader = ft.ProgressRing(
            width=20, height=20, stroke_width=2,
            color=ft.Colors.BLUE_400, visible=False,
        )
        self._update_btn = ft.ElevatedButton(
            content=ft.Text("Update"),
            icon=ft.Icons.REFRESH,
            on_click=lambda e: self.page.run_task(self._on_update_clicked) if self.page else None,
        )

        self.content = ft.Row(
            [
                self._update_btn,
                self._update_loader,
                self._min_proteins_field,
                self._min_idents_field,
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def set_loading(self, visible: bool) -> None:
        """Show/hide loader and disable/enable update button."""
        if self._update_loader is None or self._update_btn is None:
            return
        self._update_loader.visible = visible
        self._update_btn.disabled = visible
        if self.page:
            self.update()

    def get_thresholds(self) -> tuple[int, int]:
        """Return (min_proteins, min_idents)."""
        try:
            mp = int(self._min_proteins_field.value or 30)
        except (ValueError, AttributeError):
            mp = 30
        try:
            mi = int(self._min_idents_field.value or 1000)
        except (ValueError, AttributeError):
            mi = 1000
        return mp, mi
