"""DropFileDialog — two-step dialog for dropping spectra/identification files."""

from pathlib import Path
from typing import Callable, Awaitable

import flet as ft

from dasmixer.api.project.project import Project
from dasmixer.gui.utils import show_snack
from dasmixer.utils import logger


class DropFileDialog:
    """Two-step dialog: select type → confirm with file list."""

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
        """Show the first dialog (type selection)."""
        if not self.selected_sample_ids:
            show_snack(self.page, "No samples selected", ft.Colors.ORANGE_400)
            self.page.update()
            return

        tools = await self.project.get_tools()

        radio_options = ft.Column([
            ft.Radio(value="spectra_all", label="Spectra files (all)"),
            ft.Radio(value="spectra_keep_first", label="Spectra files (keep first)"),
            ft.Radio(value="spectra_keep_last", label="Spectra files (keep last)"),
            ft.Radio(value="ident_all", label="Identification files (all)"),
            ft.Radio(value="ident_by_tool", label="Identification files by tool:"),
        ], spacing=2)

        tool_dropdown = ft.Dropdown(
            label="Tool",
            options=[ft.DropdownOption(key=str(t.id), text=t.name) for t in tools],
            value=str(tools[0].id) if tools else None,
            width=250,
            disabled=True,
        )

        def on_type_change(e):
            tool_dropdown.disabled = (e.control.value != "ident_by_tool")
            if tool_dropdown.page:
                tool_dropdown.update()

        radio_group = ft.RadioGroup(
            value="spectra_all",
            content=radio_options,
            on_change=on_type_change,
        )
        radio_options.controls.append(tool_dropdown)

        async def on_confirm_first(e):
            self._dialog.open = False
            self.page.update()
            await self._show_confirm_second(radio_group.value, int(tool_dropdown.value) if tool_dropdown.value else None)

        self._dialog = ft.AlertDialog(
            title=ft.Text("Drop files — select type"),
            content=ft.Column([
                radio_group,
            ], tight=True, width=450),
            actions=[
                ft.TextButton("Cancel", on_click=self._close),
                ft.ElevatedButton("Confirm", on_click=lambda e: e.page.run_task(on_confirm_first, e)),
            ],
        )
        self.page.overlay.append(self._dialog)
        self._dialog.open = True
        self.page.update()

    async def _show_confirm_second(self, mode: str, tool_id: int | None) -> None:
        """Show second dialog with file list for confirmation."""
        files_to_delete = await self._collect_files(mode, tool_id)

        if not files_to_delete:
            show_snack(self.page, "No files to delete", ft.Colors.ORANGE_400)
            self.page.update()
            return

        file_rows = []
        for f in files_to_delete:
            try:
                short_path = "/".join(Path(f['path']).parts[-2:])
            except Exception:
                short_path = f['path']
            file_rows.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text(f['type'], size=11, weight=ft.FontWeight.BOLD, width=90),
                        ft.Text(f"ID={f['id']}", size=11, width=60),
                        ft.Text(short_path, size=11, expand=True),
                    ], spacing=4),
                    padding=ft.padding.symmetric(vertical=1),
                )
            )

        file_list_view = ft.Container(
            content=ft.ListView(controls=file_rows, spacing=1, height=200),
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=5,
            padding=10,
        )

        async def on_delete(e):
            self._dialog.open = False
            self.page.update()
            await self._execute_delete(files_to_delete)

        self._dialog = ft.AlertDialog(
            title=ft.Text("Confirm deletion"),
            content=ft.Column([
                ft.Text("⚠ This action cannot be undone. Source files on disk are not affected — only project data will be removed.",
                        size=12, color=ft.Colors.ORANGE_700),
                ft.Container(height=8),
                ft.Text("Files to be deleted:", weight=ft.FontWeight.BOLD, size=13),
                file_list_view,
            ], tight=True, width=550),
            actions=[
                ft.TextButton("Cancel", on_click=self._close),
                ft.ElevatedButton(
                    content=ft.Text("Delete"),
                    style=ft.ButtonStyle(bgcolor=ft.Colors.RED_600, color=ft.Colors.WHITE),
                    on_click=lambda e: e.page.run_task(on_delete, e),
                ),
            ],
        )
        self.page.overlay.append(self._dialog)
        self._dialog.open = True
        self.page.update()

    async def _collect_files(self, mode: str, tool_id: int | None) -> list[dict]:
        """Collect files to delete based on mode."""
        files = []
        for sid in self.selected_sample_ids:
            detail = await self.project.get_sample_detail(sid)
            if not detail:
                continue
            for sf in detail:
                if mode == "spectra_all":
                    files.append({'id': int(sf['id']), 'path': sf['path'], 'type': 'Spectra'})
                elif mode == "spectra_keep_first":
                    pass  # handled below
                elif mode == "spectra_keep_last":
                    pass  # handled below
                elif mode in ("ident_all", "ident_by_tool"):
                    for ident_file in sf.get('ident_files', []):
                        if mode == "ident_all" or (tool_id and int(ident_file.get('tool_id', 0)) == tool_id):
                            files.append({
                                'id': int(ident_file['id']),
                                'path': ident_file.get('file_path', ''),
                                'type': 'Identification',
                            })

        # Handle keep_first / keep_last for spectra
        if mode in ("spectra_keep_first", "spectra_keep_last"):
            # Group by sample, keep first/last
            sample_files: dict[int, list[dict]] = {}
            for sid in self.selected_sample_ids:
                detail = await self.project.get_sample_detail(sid)
                for sf in detail or []:
                    sample_files.setdefault(sid, []).append({
                        'id': int(sf['id']), 'path': sf['path'], 'type': 'Spectra',
                    })
            for sid, sfiles in sample_files.items():
                if len(sfiles) <= 1:
                    continue
                sfiles.sort(key=lambda x: x['id'])
                if mode == "spectra_keep_first":
                    files.extend(sfiles[1:])  # remove all except first
                else:
                    files.extend(sfiles[:-1])  # remove all except last

        return files

    async def _execute_delete(self, files: list[dict]) -> None:
        """Execute deletion of files."""
        deleted = 0
        affected_samples: set[int] = set()
        for f in files:
            try:
                if f['type'] == 'Spectra':
                    await self.project.delete_spectra_file(f['id'])
                else:
                    await self.project.delete_identification_file(f['id'])
                deleted += 1
            except Exception as ex:
                logger.exception(f"Error deleting file id={f['id']}: {ex}")

        # Refresh affected samples
        for sid in self.selected_sample_ids:
            try:
                from dasmixer.api.project.dataclasses import Sample
                sample = await self.project.get_sample(sid)
                if sample:
                    await self.project.upsert_sample_status_cache(sid, await self.project.get_sample_stats(sid))
            except Exception:
                pass

        await self.project.save()

        show_snack(self.page, f"Deleted {deleted} file(s)", ft.Colors.GREEN_400)
        self.page.update()
        if self.on_complete:
            await self.on_complete()

    def _close(self, e=None):
        if self._dialog:
            self._dialog.open = False
            self.page.update()
