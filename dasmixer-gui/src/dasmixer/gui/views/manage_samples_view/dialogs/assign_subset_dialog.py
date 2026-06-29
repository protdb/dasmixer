"""AssignSubsetDialog — dialog for assigning a comparison group to selected samples."""

from typing import Callable, Awaitable

import flet as ft

from dasmixer.api.project.project import Project
from dasmixer.gui.utils import show_snack


class AssignSubsetDialog:
    """Dialog for assigning a comparison group to selected samples."""

    def __init__(
        self,
        project: Project,
        page: ft.Page,
        selected_sample_ids: list[int],
        on_complete: Callable[[], Awaitable[None]],
    ):
        self.project = project
        self.page = page
        self.selected_sample_ids = selected_sample_ids
        self.on_complete = on_complete
        self._dialog: ft.AlertDialog | None = None

    async def show(self) -> None:
        if not self.selected_sample_ids:
            show_snack(self.page, "No samples selected", ft.Colors.ORANGE_400)
            self.page.update()
            return

        subsets = await self.project.get_subsets()
        if not subsets:
            show_snack(self.page, "No comparison groups available", ft.Colors.ORANGE_400)
            self.page.update()
            return

        subset_options = [ft.DropdownOption(key=str(s.id), text=s.name) for s in subsets]
        subset_dropdown = ft.Dropdown(
            label="Group",
            options=subset_options,
            value=str(subsets[0].id),
            width=300,
        )

        async def on_assign(e):
            self._dialog.open = False
            self.page.update()
            new_subset_id = int(subset_dropdown.value)
            assigned = 0
            for sid in self.selected_sample_ids:
                sample = await self.project.get_sample(sid)
                if sample:
                    sample.subset_id = new_subset_id
                    await self.project.update_sample(sample)
                    assigned += 1
            await self.project.save()
            show_snack(self.page, f"Group assigned for {assigned} sample(s)", ft.Colors.GREEN_400)
            self.page.update()
            if self.on_complete:
                await self.on_complete()

        self._dialog = ft.AlertDialog(
            title=ft.Text("Assign comparison group"),
            content=ft.Column([
                subset_dropdown,
            ], tight=True, width=350),
            actions=[
                ft.TextButton("Cancel", on_click=self._close),
                ft.ElevatedButton("Assign", on_click=lambda e: e.page.run_task(on_assign, e)),
            ],
        )
        self.page.overlay.append(self._dialog)
        self._dialog.open = True
        self.page.update()

    def _close(self, e=None):
        if self._dialog:
            self._dialog.open = False
            self.page.update()
