"""MassOperationsRow — row of mass-operation buttons between UpdateRow and panels."""

from typing import Callable, Awaitable

import flet as ft


class MassOperationsRow(ft.Container):
    """Row with Select All, Deselect All, Outlier, Drop file, Assign group, Delete, Drop empty files."""

    def __init__(
        self,
        on_select_all: Callable[[], None],
        on_deselect_all: Callable[[], None],
        on_outlier: Callable[[], Awaitable[None]],
        on_drop_file: Callable[[], Awaitable[None]],
        on_assign_subset: Callable[[], Awaitable[None]],
        on_delete: Callable[[], Awaitable[None]],
        on_drop_empty: Callable[[], Awaitable[None]],
    ):
        super().__init__(
            padding=ft.padding.symmetric(horizontal=16, vertical=4),
        )
        btn_style = ft.ButtonStyle(padding=ft.padding.symmetric(horizontal=8, vertical=4))
        small_btn_style = ft.ButtonStyle(padding=ft.padding.symmetric(horizontal=6, vertical=3))

        self.content = ft.Row(
            [
                ft.TextButton("Select All", icon=ft.Icons.CHECK_BOX,
                              style=btn_style, on_click=lambda e: on_select_all()),
                ft.TextButton("Deselect All", icon=ft.Icons.CHECK_BOX_OUTLINE_BLANK,
                              style=btn_style, on_click=lambda e: on_deselect_all()),
                ft.VerticalDivider(width=1, thickness=1),
                ft.TextButton("Outlier", icon=ft.Icons.FLAG,
                              style=btn_style,
                              on_click=lambda e: self.page.run_task(on_outlier) if self.page else None),
                ft.TextButton("Drop file", icon=ft.Icons.FILE_UPLOAD_OFF,
                              style=btn_style,
                              on_click=lambda e: self.page.run_task(on_drop_file) if self.page else None),
                ft.TextButton("Assign group", icon=ft.Icons.GROUP,
                              style=btn_style,
                              on_click=lambda e: self.page.run_task(on_assign_subset) if self.page else None),
                ft.TextButton("Delete", icon=ft.Icons.DELETE_SWEEP,
                              style=btn_style,
                              on_click=lambda e: self.page.run_task(on_delete) if self.page else None),
                ft.VerticalDivider(width=1, thickness=1),
                ft.TextButton("Drop empty files", icon=ft.Icons.CLEANING_SERVICES,
                              style=small_btn_style,
                              on_click=lambda e: self.page.run_task(on_drop_empty) if self.page else None),
            ],
            spacing=2,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
