"""SamplesFilterRow — filter controls for Manage Samples View."""

from typing import Callable, Awaitable

import flet as ft

from dasmixer.api.project.dataclasses import Subset


class SamplesFilterRow(ft.Container):
    """Filter controls row — name search, status, subset, outlier, Apply button."""

    def __init__(
        self,
        subsets: list[Subset],
        on_apply: Callable[[], Awaitable[None]],
    ):
        super().__init__(padding=ft.padding.symmetric(horizontal=16, vertical=4))
        self._on_apply = on_apply

        self.name_field = ft.TextField(
            label="Search by name",
            width=200,
            dense=True,
        )

        self.status_dropdown = ft.Dropdown(
            label="Status",
            options=[
                ft.DropdownOption(key="all", text="All"),
                ft.DropdownOption(key="OK", text="OK"),
                ft.DropdownOption(key="WARNING", text="Warning"),
                ft.DropdownOption(key="ERROR", text="Error"),
            ],
            value="all",
            width=150,
            dense=True,
        )

        self.subset_dropdown = ft.Dropdown(
            label="Subset",
            options=[ft.DropdownOption(key="all", text="All Subsets")] + [
                ft.DropdownOption(key=str(s.id), text=s.name) for s in subsets
            ],
            value="all",
            width=200,
            dense=True,
        )

        self.outlier_dropdown = ft.Dropdown(
            label="Outlier",
            options=[
                ft.DropdownOption(key="all", text="All"),
                ft.DropdownOption(key="yes", text="Yes"),
                ft.DropdownOption(key="no", text="No"),
            ],
            value="all",
            width=120,
            dense=True,
        )

        self.apply_btn = ft.ElevatedButton(
            content=ft.Text("Apply Filters"),
            icon=ft.Icons.FILTER_ALT,
            on_click=lambda e: e.page.run_task(self._on_apply),
        )

        self.content = ft.Row(
            [
                self.name_field,
                self.status_dropdown,
                self.subset_dropdown,
                self.outlier_dropdown,
                self.apply_btn,
            ],
            spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
        )

    def get_filters(self) -> dict:
        """Return current filter values as a plain dict for in-memory filtering."""
        return {
            'name': (self.name_field.value or '').strip(),
            'status': self.status_dropdown.value or 'all',
            'subset_id': self.subset_dropdown.value or 'all',
            'outlier': self.outlier_dropdown.value or 'all',
        }

    def set_filters(self, filters: dict) -> None:
        """Restore UI state from a persisted filters dict (does not trigger apply)."""
        self.name_field.value = filters.get('name', '')
        self.status_dropdown.value = filters.get('status', 'all')
        self.subset_dropdown.value = filters.get('subset_id', 'all')
        self.outlier_dropdown.value = filters.get('outlier', 'all')