"""SamplesPaginationRow — pagination controls for Manage Samples View."""

from typing import Callable, Awaitable

import flet as ft


class SamplesPaginationRow(ft.Container):
    """Pagination controls — operates over in-memory list, no SQL calls."""

    PAGE_SIZES = ["10", "20", "50", "100", "All"]

    def __init__(self, on_page_changed: Callable[[], Awaitable[None]]):
        super().__init__(padding=ft.padding.symmetric(horizontal=16, vertical=4))
        self._on_page_changed = on_page_changed

        self.current_page = 0
        self.page_size: int | None = 20  # None means "All"
        self.total_rows = 0

        self.pagination_text = ft.Text("No data", size=12, color=ft.Colors.GREY_600)
        self.page_size_dropdown = ft.Dropdown(
            label="Rows per page",
            options=[ft.DropdownOption(key=v, text=v) for v in self.PAGE_SIZES],
            value="20",
            width=140,
            dense=True,
            on_text_change=self._on_page_size_change,
        )
        self.prev_button = ft.IconButton(
            icon=ft.Icons.ARROW_BACK,
            on_click=self._on_prev,
            disabled=True,
        )
        self.next_button = ft.IconButton(
            icon=ft.Icons.ARROW_FORWARD,
            on_click=self._on_next,
            disabled=True,
        )

        self.content = ft.Row(
            [
                self.pagination_text,
                ft.Container(expand=True),
                self.page_size_dropdown,
                self.prev_button,
                self.next_button,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    def slice(self, items: list) -> list:
        """Return the current page slice of items (or all items if page_size is None)."""
        self.total_rows = len(items)
        if self.page_size is None:
            self._update_text_all()
            return items
        start = self.current_page * self.page_size
        end = start + self.page_size
        self._update_text_paged()
        return items[start:end]

    def _update_text_paged(self):
        if self.total_rows == 0:
            self.pagination_text.value = "No data"
            self.prev_button.disabled = True
            self.next_button.disabled = True
            return
        start = self.current_page * self.page_size + 1
        end = min((self.current_page + 1) * self.page_size, self.total_rows)
        total_pages = (self.total_rows + self.page_size - 1) // self.page_size
        self.pagination_text.value = (
            f"Showing {start}-{end} of {self.total_rows} "
            f"(Page {self.current_page + 1} of {total_pages})"
        )
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= total_pages - 1

    def _update_text_all(self):
        self.pagination_text.value = f"Showing {self.total_rows} of {self.total_rows}"
        self.prev_button.disabled = True
        self.next_button.disabled = True

    async def _on_page_size_change(self, e):
        value = e.control.value
        self.page_size = None if value == "All" else int(value)
        self.current_page = 0
        await self._on_page_changed()

    async def _on_prev(self, e):
        if self.current_page > 0:
            self.current_page -= 1
            await self._on_page_changed()

    async def _on_next(self, e):
        self.current_page += 1
        await self._on_page_changed()