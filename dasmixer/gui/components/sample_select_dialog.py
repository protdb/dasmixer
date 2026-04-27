"""Reusable sample selection dialog for export and other operations."""

import asyncio

import flet as ft

from dasmixer.api.project.project import Project


class SampleSelectDialog:
    def __init__(self, page: ft.Page, project: Project):
        self.page = page
        self.project = project
        self._checkboxes: dict[int, ft.Checkbox] = {}

    async def show(self, pre_selected: list[int]) -> list[int] | None:
        samples = await self.project.get_samples()

        self._checkboxes.clear()
        controls = []

        for sample in samples:
            label = sample.name
            if sample.subset_name:
                label = f"{label} ({sample.subset_name})"
            if sample.outlier:
                label += " [outlier]"
            cb = ft.Checkbox(
                label=label,
                value=sample.id in pre_selected,
            )
            if sample.id is not None:
                self._checkboxes[sample.id] = cb
            controls.append(cb)

        select_all_btn = ft.ElevatedButton(
            content=ft.Text("Select All"),
            on_click=self._on_select_all,
            icon=ft.Icons.CHECK,
        )
        deselect_all_btn = ft.ElevatedButton(
            content=ft.Text("Deselect All"),
            on_click=self._on_deselect_all,
            icon=ft.Icons.CLOSE,
        )

        def _on_ok(e):
            dlg_did.data = True
            dlg_did.open = False
            self.page.update()

        def _on_cancel(e):
            dlg_did.data = None
            dlg_did.open = False
            self.page.update()

        ok_btn = ft.ElevatedButton(
            content=ft.Text("OK"),
            on_click=_on_ok,
            icon=ft.Icons.CHECK,
        )
        cancel_btn = ft.ElevatedButton(
            content=ft.Text("Cancel"),
            on_click=_on_cancel,
        )

        dlg_did = ft.AlertDialog(
            title=ft.Text("Select Samples", size=18, weight=ft.FontWeight.BOLD),
            content=ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Row([select_all_btn, deselect_all_btn], spacing=8),
                        ft.ListView(controls=controls, expand=True, spacing=4, height=300),
                    ],
                    tight=True,
                ),
                padding=ft.padding.only(top=10),
            ),
            actions=[ok_btn, cancel_btn],
            actions_alignment=ft.MainAxisAlignment.END,
            modal=True,
        )
        dlg_did.data = None

        self.page.show_dialog(dlg_did)

        await self._wait_for_dialog(dlg_did)

        if dlg_did.data is True:
            return [sid for sid, cb in self._checkboxes.items() if cb.value]
        return None

    def _on_select_all(self, e):
        for cb in self._checkboxes.values():
            cb.value = True
        self.page.update()

    def _on_deselect_all(self, e):
        for cb in self._checkboxes.values():
            cb.value = False
        self.page.update()

    async def _wait_for_dialog(self, dialog):
        try:
            while dialog.open:
                await asyncio.sleep(0.1)
        except Exception:
            pass

    def get_selected_text(self, sample_ids: list[int], samples: list) -> str:
        name_map = {s.id: s.name for s in samples}
        selected_names = [name_map.get(sid, str(sid)) for sid in sample_ids if sid in name_map]
        if not selected_names:
            return "None"
        return ", ".join(selected_names)
