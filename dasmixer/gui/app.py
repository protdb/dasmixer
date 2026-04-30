"""Main GUI application entry point."""

import asyncio
import os
import flet as ft
from pathlib import Path
from dasmixer.api.config import config
from dasmixer.api.project.project import Project
import traceback
from dasmixer.gui.utils import show_snack
from dasmixer.utils import logger


def run_gui(project_path: str | None = None):
    """
    Entry point for GUI mode.

    Args:
        project_path: Optional path to project file to open immediately
    """
    def main(page: ft.Page):
        logger.debug("[app] main() called, creating DASMixerApp...")
        app = DASMixerApp(page, project_path)

    ft.app(target=main)


class DASMixerApp:
    """Main GUI application controller."""

    def __init__(self, page: ft.Page, initial_project_path: str | None = None):
        """
        Initialize application.

        Args:
            page: Flet page object
            initial_project_path: Optional project file to open on startup
        """
        self.page = page
        self.initial_project_path = initial_project_path
        self.current_project: Project | None = None

        logger.debug("[app] Configuring page...")

        # Configure page
        self.page.title = "DASMixer - Mass Spectrometry Data Integration"
        self.page.window.width = config.window_width
        self.page.window.height = config.window_height
        self.page.padding = 0

        # Set application icon
        icon_path = Path("assets/icons/icon_256.png")
        if icon_path.exists():
            self.page.window.icon = str(icon_path)
            logger.debug(f"[app] Icon set: {icon_path}")

        # Apply theme
        self.page.theme_mode = (
            ft.ThemeMode.DARK if config.theme == "dark" else ft.ThemeMode.LIGHT
        )
        logger.debug(f"[app] Theme: {config.theme}")

        # Setup routing
        self.page.on_route_change = self._route_change
        self.page.on_view_pop = self._view_pop

        # Handle window close: clean up DB + child processes, then force-exit.
        self.page.window.prevent_close = True
        self.page.on_window_event = self._on_window_event

        logger.debug("[app] Route handlers registered.")

        if initial_project_path:
            logger.debug(f"[app] Opening initial project: {initial_project_path}")
            self.page.run_task(self._open_initial_project, initial_project_path)
        else:
            # Call _route_change directly — page.go() is async in Flet 0.80
            # and won't fire synchronously from __init__
            logger.debug("[app] Calling _route_change() directly for initial render.")
            self._route_change()

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _on_window_event(self, e):
        """Handle window lifecycle events."""
        event_type = e.data if hasattr(e, "data") else str(e)
        logger.debug(f"[app] window event: {event_type}")
        if event_type == "close":
            self.page.run_task(self._shutdown)

    async def _shutdown(self):
        """
        Graceful shutdown on window close.

        Order:
        1. Close open project (commits + closes DB connection).
        2. Kill any tracked child processes (webview, etc.).
        3. os._exit(0) — terminates the process unconditionally, bypassing
           asyncio/threading cleanup that would otherwise keep the console
           alive for 10-30 seconds.
        """
        logger.debug("[app] _shutdown started")

        # 1. Close project DB
        if self.current_project:
            try:
                await self.current_project.close()
            except Exception as exc:
                logger.warning(f"[app] _shutdown: project close error: {exc}")
            self.current_project = None

        # 2. Kill child processes (webview windows, etc.)
        from dasmixer.gui.utils import get_child_processes
        for proc in list(get_child_processes()):
            try:
                if proc.is_alive():
                    proc.kill()
            except Exception as exc:
                logger.debug(f"[app] _shutdown: kill proc error: {exc}")
        get_child_processes().clear()

        logger.debug("[app] _shutdown complete — calling os._exit(0)")
        os._exit(0)

    def _route_change(self, e=None):
        """Handle route changes — rebuild view stack.
        
        Called both by page.on_route_change (no-arg in Flet 0.80) and manually.
        """
        logger.debug(f"[route] route_change: {self.page.route}")
        try:
            self.page.views.clear()

            # Base view: start or project
            if self.current_project is not None:
                self.page.views.append(self._build_project_view())
            else:
                self.page.views.append(self._build_start_view())

            # Secondary views
            if self.page.route == "/settings":
                from dasmixer.gui.views.settings_view import SettingsView
                self.page.views.append(SettingsView())
            elif self.page.route == "/plugins":
                from dasmixer.gui.views.plugins_view import PluginsView
                self.page.views.append(PluginsView())

            self.page.update()
            logger.debug(f"[route] view stack size: {len(self.page.views)}")
        except Exception as ex:
            logger.exception(f"[route] ERROR in _route_change: {ex}")
            traceback.print_exc()

    def _view_pop(self, e=None):
        """Handle back navigation (system back button)."""
        logger.debug(f"[route] view_pop triggered")
        if len(self.page.views) > 1:
            self.page.views.pop()
        top_view = self.page.views[-1]
        self.page.route = top_view.route or "/"
        self.page.update()

    # ------------------------------------------------------------------
    # View builders
    # ------------------------------------------------------------------

    def _build_start_view(self) -> ft.View:
        """Build start view as ft.View for routing stack."""
        logger.debug("[app] Building start view...")
        from dasmixer.gui.views.start_view import StartView
        content = StartView(
            on_create_project=lambda _: self.page.run_task(self.new_project),
            on_open_project=lambda path: (
                self.page.run_task(self.open_project_dialog)
                if path is None
                else self.page.run_task(self.open_project, path)
            ),
            recent_projects=config.recent_projects
        )
        return ft.View(
            route="/",
            controls=[content],
            appbar=self._build_appbar(),
            padding=0,
        )

    def _build_project_view(self) -> ft.View:
        """Build project view as ft.View for routing stack."""
        logger.debug("[app] Building project view...")
        from dasmixer.gui.views.project_view import ProjectView
        content = ProjectView(
            project=self.current_project,
            on_close=lambda _: self.page.run_task(self.close_project)
        )
        return ft.View(
            route="/project",
            controls=[content],
            appbar=self._build_appbar(),
            padding=0,
        )

    def _build_appbar(self) -> ft.AppBar:
        """Build application AppBar with menu."""
        close_disabled = self.current_project is None
        return ft.AppBar(
            title=ft.Text("DASMixer", size=20, weight=ft.FontWeight.BOLD),
            actions=[
                # File menu
                ft.PopupMenuButton(
                    tooltip="File",
                    icon=ft.Icons.FOLDER,
                    items=[
                        ft.PopupMenuItem(
                            content=ft.Text("New Project"),
                            icon=ft.Icons.CREATE_NEW_FOLDER,
                            on_click=lambda _: self.page.run_task(self.new_project)
                        ),
                        ft.PopupMenuItem(
                            content=ft.Text("Open Project"),
                            icon=ft.Icons.FOLDER_OPEN,
                            on_click=lambda _: self.page.run_task(self.open_project_dialog)
                        ),
                        ft.PopupMenuItem(),  # Divider
                        ft.PopupMenuItem(
                            content=ft.Text("Close Project"),
                            icon=ft.Icons.CLOSE,
                            on_click=lambda _: self.page.run_task(self.close_project),
                            disabled=close_disabled
                        ),
                        ft.PopupMenuItem(),  # Divider
                        ft.PopupMenuItem(
                            content=ft.Text("Exit"),
                            icon=ft.Icons.EXIT_TO_APP,
                            on_click=lambda _: self.page.window.close()
                        ),
                    ]
                ),
                # Options menu
                ft.PopupMenuButton(
                    tooltip="Options",
                    icon=ft.Icons.SETTINGS,
                    items=[
                        ft.PopupMenuItem(
                            content=ft.Text("Settings"),
                            icon=ft.Icons.TUNE,
                            on_click=lambda _: self._navigate_to("/settings")
                        ),
                        ft.PopupMenuItem(
                            content=ft.Text("Plugins"),
                            icon=ft.Icons.EXTENSION,
                            on_click=lambda _: self._navigate_to("/plugins")
                        ),
                    ]
                ),
            ]
        )

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------

    def _navigate_to(self, route: str):
        """Navigate to a secondary route (settings, plugins) by appending a view."""
        logger.debug(f"[route] _navigate_to: {route}")
        self.page.route = route
        self._route_change()

    # ------------------------------------------------------------------
    # Project migration
    # ------------------------------------------------------------------

    async def _check_project_version(self):
        """
        Проверяет версию открытого проекта и предлагает миграцию или предупреждает
        о несовместимости.
        """
        from dasmixer.api.project.migrations import MigrationError
        from dasmixer.versions import PROJECT_VERSION

        needs_migration = await self.current_project.needs_migration()
        is_too_new = await self.current_project.is_version_too_new()
        project_version = await self.current_project.get_project_version()

        if is_too_new:
            await self._show_version_warning_dialog(project_version)
            return

        if needs_migration:
            user_confirmed = await self._show_migration_dialog(project_version)
            if user_confirmed:
                await self._run_migration()

    async def _show_version_warning_dialog(self, project_version: str):
        """Dialog for project version newer than current DASMixer."""
        from dasmixer.versions import PROJECT_VERSION

        async def on_ok(e):
            dialog.open = False
            event.set()
            self.page.update()

        event = asyncio.Event()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Incompatible Project Version"),
            content=ft.Text(
                f"This project was created with a newer version of DASMixer "
                f"(project version: {project_version}, current: {PROJECT_VERSION}).\n\n"
                f"You may encounter errors or unexpected behavior.\n"
                f"It is strongly recommended to update DASMixer before using this project."
            ),
            actions=[
                ft.ElevatedButton(content=ft.Text("OK"), on_click=on_ok),
            ],
        )
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

        await event.wait()
        dialog.open = False
        try:
            self.page.overlay.remove(dialog)
        except ValueError:
            pass
        self.page.update()

    async def _show_migration_dialog(self, project_version: str) -> bool:
        """Dialog offering project migration. Returns True if user clicked Update."""
        from dasmixer.versions import PROJECT_VERSION

        result = [False]

        def on_update(e):
            result[0] = True
            dialog.open = False
            event.set()
            self.page.update()

        def on_skip(e):
            result[0] = False
            dialog.open = False
            event.set()
            self.page.update()

        event = asyncio.Event()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Project Update Required"),
            content=ft.Container(
                content=ft.Column([
                    ft.Text(
                        f"This project uses an older format (version {project_version}).\n"
                        f"Current DASMixer requires version {PROJECT_VERSION}.\n\n"
                        f"Without updating, you may encounter errors.\n"
                        f"After updating, the project may not open correctly in older versions of DASMixer.\n\n"
                        f"⚠ Note: project files can be large (several GB). \n"
                        f"We recommend making a backup copy before proceeding.",
                    ),
                ], tight=True),
                width=400,
            ),
            actions=[
                ft.ElevatedButton(content=ft.Text("Skip"), on_click=on_skip),
                ft.ElevatedButton(content=ft.Text("Update"), on_click=on_update),
            ],
        )
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

        await event.wait()
        try:
            self.page.overlay.remove(dialog)
        except ValueError:
            pass
        self.page.update()
        return result[0]

    async def _run_migration(self):
        """Запускает миграцию с отображением прогресса."""
        from dasmixer.api.project.migrations import MigrationError
        from dasmixer.gui.components.progress_dialog import ProgressDialog
        from dasmixer.versions import PROJECT_VERSION
        from dasmixer.gui.utils import show_snack

        dialog = ProgressDialog("Updating project...")
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

        try:
            dialog.update_progress(0.1, "Applying migrations...")
            await self.current_project.apply_migrations()
            dialog.update_progress(1.0, "Done")
        except MigrationError as e:
            logger.exception(f"Migration failed: {e}")
            dialog.open = False
            self.page.update()
            self._show_error(f"Migration failed: {e}")
            return
        finally:
            dialog.open = False
            self.page.update()

        show_snack(self.page, f"Project updated to {PROJECT_VERSION}", ft.Colors.GREEN_400)

    def show_start_view(self):
        """Navigate to start screen."""
        self.page.route = "/"
        self._route_change()

    def show_project_view(self):
        """Navigate to project workspace."""
        self.page.route = "/project"
        self._route_change()

    # ------------------------------------------------------------------
    # Snackbar helpers
    # ------------------------------------------------------------------

    def _show_error(self, message: str):
        logger.debug(f"[app] ERROR: {message}")
        show_snack(self.page, message, ft.Colors.RED_400)

    def _show_success(self, message: str):
        logger.debug(f"[app] OK: {message}")
        show_snack(self.page, message, ft.Colors.GREEN_400)

    def _show_info(self, message: str):
        logger.debug(f"[app] INFO: {message}")
        show_snack(self.page, message, ft.Colors.BLUE_400)

    # ------------------------------------------------------------------
    # Project operations
    # ------------------------------------------------------------------

    async def _open_initial_project(self, path: str):
        """Open project passed via CLI on startup."""
        await self.open_project(path)

    async def new_project(self, e=None):
        """Create new project."""
        logger.debug("[app] new_project called")
        try:
            file_path = await ft.FilePicker().save_file(
                dialog_title="Create New Project",
                file_name="project.dasmix",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["dasmix"]
            )

            if not file_path:
                logger.debug("[app] new_project: cancelled")
                return

            project_path = Path(file_path)
            if project_path.suffix != '.dasmix':
                project_path = project_path.with_suffix('.dasmix')

            logger.debug(f"[app] Creating project at: {project_path}")
            self.current_project = Project(path=project_path, create_if_not_exists=True)
            await self.current_project.initialize()

            await self.current_project.add_subset(
                "Control",
                details="Default control group",
                display_color="#3B82F6"
            )

            config.add_recent_project(str(project_path))
            self.show_project_view()
            self._show_success(f"Created project: {project_path.name}")

        except Exception as ex:
            logger.exception(f"[app] new_project ERROR: {ex}")
            self._show_error(f"Error creating project: {ex}")

    async def open_project_dialog(self, e=None):
        """Open project via file picker."""
        logger.debug("[app] open_project_dialog called")
        try:
            files = await ft.FilePicker().pick_files(
                dialog_title="Open Project",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["dasmix"],
                allow_multiple=False
            )

            if files and files[0].path:
                await self.open_project(files[0].path)
            else:
                logger.debug("[app] open_project_dialog: cancelled")

        except Exception as ex:
            logger.exception(f"[app] open_project_dialog ERROR: {ex}")
            self._show_error(f"Error opening file picker: {ex}")

    async def open_project(self, path: str, e=None):
        """
        Open existing project.

        Args:
            path: Path to project file
            e: Optional event (for callback compatibility)
        """
        logger.debug(f"[app] open_project: {path}")
        try:
            project_path = Path(path)

            if not project_path.exists():
                self._show_error(f"Project file not found: {path}")
                return

            if self.current_project:
                await self.current_project.close()

            self.current_project = Project(path=project_path, create_if_not_exists=False)
            await self.current_project.initialize()

            # Check project version for migration
            await self._check_project_version()

            config.add_recent_project(str(project_path))
            self.show_project_view()
            self._show_success(f"Opened project: {project_path.name}")

        except Exception as ex:
            logger.exception(f"[app] open_project ERROR: {ex}")
            self._show_error(f"Error opening project: {ex}")

    async def close_project(self, e=None):
        """Close current project."""
        logger.debug("[app] close_project called")
        if self.current_project:
            try:
                await self.current_project.close()
                self.current_project = None
                self.show_start_view()
                self._show_info("Project closed")
            except Exception as ex:
                logger.exception(f"[app] close_project ERROR: {ex}")
                self._show_error(f"Error closing project: {ex}")
