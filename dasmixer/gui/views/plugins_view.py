"""Plugins management view."""

import os
import sys
import subprocess
import flet as ft
from pathlib import Path

from dasmixer.api.config import config
from dasmixer.api.plugin_loader import (
    get_identification_plugins_dir,
    get_reports_plugins_dir,
    install_plugin_file,
    delete_plugin,
)

# Import registries to enumerate built-ins
from dasmixer.api.inputs.registry import registry as inputs_registry
from dasmixer.api.reporting.registry import registry as reports_registry


def _get_plugin_load_results() -> list[dict]:
    """Get plugin load results stored in main module, or empty list."""
    main_module = sys.modules.get("dasmixer.main")
    if main_module and hasattr(main_module, "_plugin_load_results"):
        return main_module._plugin_load_results
    return []


def _get_builtin_identification_names() -> set[str]:
    """Return names of all registered identification parsers."""
    return set(inputs_registry.get_identification_parsers().keys())


def _get_builtin_report_names() -> set[str]:
    """Return names of all registered reports."""
    return set(reports_registry.get_all().keys())


def _get_external_plugin_ids() -> set[str]:
    """Return plugin IDs that were loaded from external files."""
    return set(config.plugin_paths.keys())


class PluginsView(ft.View):
    """
    Plugin management screen.

    Accessible via Options → Plugins menu.
    Shows two sections: Identification Parsers and Reports.

    Each section lists:
    - Built-in modules (always enabled, non-deletable)
    - External plugins (with enable/disable and delete controls)
    """

    def __init__(self):
        super().__init__(
            route="/plugins",
            appbar=ft.AppBar(
                title=ft.Text("Plugins"),
                leading=ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    on_click=lambda _: self._go_back(),
                ),
            ),
            scroll=ft.ScrollMode.AUTO,
        )

        self._load_results: list[dict] = _get_plugin_load_results()
        self._ident_list_col = ft.Column(spacing=4)
        self._reports_list_col = ft.Column(spacing=4)
        self._build_controls()

    def _go_back(self):
        if len(self.page.views) > 1:
            self.page.views.pop()
        self.page.update()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_controls(self):
        """Build full view content."""
        self._refresh_lists()

        external_ids = _get_external_plugin_ids()

        # Identification Parsers section
        ident_section = self._build_section(
            title="Identification Parsers",
            list_col=self._ident_list_col,
            plugin_type="identification",
            plugins_dir=get_identification_plugins_dir(),
        )

        # Reports section
        reports_section = self._build_section(
            title="Reports",
            list_col=self._reports_list_col,
            plugin_type="report",
            plugins_dir=get_reports_plugins_dir(),
        )

        self.controls = [
            ft.Container(
                content=ft.Column(
                    [
                        ident_section,
                        ft.Divider(height=24),
                        reports_section,
                        ft.Container(height=20),
                    ],
                    spacing=16,
                ),
                padding=ft.padding.all(24),
                expand=True,
            )
        ]

    def _build_section(
        self,
        title: str,
        list_col: ft.Column,
        plugin_type: str,
        plugins_dir: Path,
    ) -> ft.Column:
        """Build a plugin section with header, list, and action buttons."""
        install_btn = ft.ElevatedButton(
            text="Install from file...",
            icon=ft.Icons.UPLOAD_FILE,
            on_click=lambda _, pt=plugin_type: self.page.run_task(
                self._pick_plugin_file, pt
            ),
        )
        open_dir_btn = ft.OutlinedButton(
            text="Open plugins folder",
            icon=ft.Icons.FOLDER_OPEN,
            on_click=lambda _, d=plugins_dir: self._open_directory(d),
        )

        return ft.Column(
            [
                ft.Text(title, size=18, weight=ft.FontWeight.BOLD),
                ft.Container(height=4),
                list_col,
                ft.Container(height=8),
                ft.Row([install_btn, open_dir_btn], spacing=10),
            ],
            spacing=4,
        )

    def _refresh_lists(self):
        """Rebuild both plugin list columns from current state."""
        self._ident_list_col.controls.clear()
        self._reports_list_col.controls.clear()

        external_ids = _get_external_plugin_ids()
        load_results_by_id = {r["id"]: r for r in self._load_results}

        # Built-in identification parsers
        for name in sorted(_get_builtin_identification_names()):
            if name not in external_ids:
                self._ident_list_col.controls.append(
                    self._build_plugin_tile(
                        plugin_id=name,
                        display_name=name,
                        path_str="(built-in)",
                        error=None,
                        builtin=True,
                        enabled=True,
                    )
                )

        # External identification parsers
        for pid, path_str in config.plugin_paths.items():
            result = load_results_by_id.get(pid, {})
            plugin_type = result.get("plugin_type", "identification")
            if plugin_type != "identification":
                continue
            self._ident_list_col.controls.append(
                self._build_plugin_tile(
                    plugin_id=pid,
                    display_name=pid,
                    path_str=path_str,
                    error=result.get("error"),
                    builtin=False,
                    enabled=config.plugin_states.get(pid, True),
                )
            )

        # Built-in reports
        for name in sorted(_get_builtin_report_names()):
            if name not in external_ids:
                self._reports_list_col.controls.append(
                    self._build_plugin_tile(
                        plugin_id=name,
                        display_name=name,
                        path_str="(built-in)",
                        error=None,
                        builtin=True,
                        enabled=True,
                    )
                )

        # External reports
        for pid, path_str in config.plugin_paths.items():
            result = load_results_by_id.get(pid, {})
            plugin_type = result.get("plugin_type", "report")
            if plugin_type != "report":
                continue
            self._reports_list_col.controls.append(
                self._build_plugin_tile(
                    plugin_id=pid,
                    display_name=pid,
                    path_str=path_str,
                    error=result.get("error"),
                    builtin=False,
                    enabled=config.plugin_states.get(pid, True),
                )
            )

    def _build_plugin_tile(
        self,
        plugin_id: str,
        display_name: str,
        path_str: str,
        error: str | None,
        builtin: bool,
        enabled: bool,
    ) -> ft.ListTile:
        """Build a single plugin entry row."""
        subtitle_text = path_str
        subtitle_color = ft.Colors.GREY_600
        if error:
            subtitle_text = f"ERROR: {error[:120]}{'...' if len(error) > 120 else ''}"
            subtitle_color = ft.Colors.RED_400

        checkbox = ft.Checkbox(
            value=enabled,
            disabled=builtin,
            on_change=(
                None if builtin
                else lambda e, pid=plugin_id: self._toggle_plugin(pid, e.control.value)
            ),
        )

        trailing_controls = []
        if not builtin:
            trailing_controls.append(
                ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    tooltip="Delete plugin",
                    icon_color=ft.Colors.RED_400,
                    on_click=lambda _, pid=plugin_id, dn=display_name: self.page.run_task(
                        self._confirm_delete, pid, dn
                    ),
                )
            )

        return ft.ListTile(
            leading=checkbox,
            title=ft.Text(display_name, weight=ft.FontWeight.W_500),
            subtitle=ft.Text(subtitle_text, size=11, color=subtitle_color),
            trailing=ft.Row(trailing_controls, tight=True) if trailing_controls else None,
            content_padding=ft.padding.symmetric(horizontal=4),
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _toggle_plugin(self, plugin_id: str, enabled: bool):
        """Enable or disable a plugin."""
        config.set_plugin_state(plugin_id, enabled)

    async def _pick_plugin_file(self, plugin_type: str):
        """Open file picker to select a plugin file (.py or .zip)."""
        file_picker = ft.FilePicker()
        self.page.overlay.append(file_picker)
        self.page.update()

        files = await file_picker.pick_files(
            dialog_title="Select plugin file",
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["py", "zip"],
            allow_multiple=False,
        )

        self.page.overlay.remove(file_picker)
        self.page.update()

        if not files:
            return

        src_path = Path(files[0].path)
        success, plugin_id, error = install_plugin_file(src_path, plugin_type)

        if not success:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Failed to install plugin: {error}"),
                bgcolor=ft.Colors.RED_400,
                open=True,
            )
            self.page.update()
            return

        self.page.snack_bar = ft.SnackBar(
            content=ft.Text(
                f"Plugin '{plugin_id}' installed. "
                "Restart the application to load it."
            ),
            bgcolor=ft.Colors.GREEN_400,
            open=True,
        )
        self.page.update()

        # Show restart dialog
        await self._show_restart_dialog(plugin_id)
        self._refresh_lists()
        self.page.update()

    async def _confirm_delete(self, plugin_id: str, display_name: str):
        """Show confirmation dialog before deleting a plugin."""
        result: list[bool] = [False]

        def on_confirm(_):
            result[0] = True
            dlg.open = False
            self.page.update()

        def on_cancel(_):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Delete Plugin"),
            content=ft.Text(
                f"Delete plugin '{display_name}'? "
                "The file will be permanently removed from disk."
            ),
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel),
                ft.ElevatedButton(
                    "Delete",
                    style=ft.ButtonStyle(bgcolor=ft.Colors.RED_400),
                    on_click=on_confirm,
                ),
            ],
        )

        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

        import asyncio
        while dlg.open:
            await asyncio.sleep(0.05)

        self.page.overlay.remove(dlg)
        self.page.update()

        if not result[0]:
            return

        success, error = delete_plugin(plugin_id)
        if success:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Plugin '{display_name}' deleted."),
                bgcolor=ft.Colors.BLUE_400,
                open=True,
            )
            self._refresh_lists()
            self.page.update()
        else:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Failed to delete plugin: {error}"),
                bgcolor=ft.Colors.RED_400,
                open=True,
            )
            self.page.update()

    async def _show_restart_dialog(self, plugin_id: str):
        """Inform user that restart is required to load the installed plugin."""
        def on_ok(_):
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Plugin Installed"),
            content=ft.Text(
                f"Plugin '{plugin_id}' has been installed.\n"
                "Restart the application to load it."
            ),
            actions=[ft.ElevatedButton("OK", on_click=on_ok)],
        )

        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

        import asyncio
        while dlg.open:
            await asyncio.sleep(0.05)

        self.page.overlay.remove(dlg)
        self.page.update()

    @staticmethod
    def _open_directory(directory: Path):
        """Open directory in system file manager."""
        directory.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(directory))
        elif sys.platform == "darwin":
            subprocess.run(["open", str(directory)], check=False)
        else:
            subprocess.run(["xdg-open", str(directory)], check=False)
