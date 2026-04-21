"""Main GUI application entry point."""

import flet as ft
from pathlib import Path
from dasmixer.api.config import config
from dasmixer.api.project.project import Project
import traceback
from dasmixer.gui.utils import show_snack


def run_gui(project_path: str | None = None):
    """
    Entry point for GUI mode.

    Args:
        project_path: Optional path to project file to open immediately
    """
    def main(page: ft.Page):
        print("[app] main() called, creating DASMixerApp...")
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

        print("[app] Configuring page...")

        # Configure page
        self.page.title = "DASMixer - Mass Spectrometry Data Integration"
        self.page.window.width = config.window_width
        self.page.window.height = config.window_height
        self.page.padding = 0

        # Set application icon
        icon_path = Path("assets/icons/icon_256.png")
        if icon_path.exists():
            self.page.window.icon = str(icon_path)
            print(f"[app] Icon set: {icon_path}")

        # Apply theme
        self.page.theme_mode = (
            ft.ThemeMode.DARK if config.theme == "dark" else ft.ThemeMode.LIGHT
        )
        print(f"[app] Theme: {config.theme}")

        # Setup routing
        self.page.on_route_change = self._route_change
        self.page.on_view_pop = self._view_pop
        print("[app] Route handlers registered.")

        if initial_project_path:
            print(f"[app] Opening initial project: {initial_project_path}")
            self.page.run_task(self._open_initial_project, initial_project_path)
        else:
            # Call _route_change directly — page.go() is async in Flet 0.80
            # and won't fire synchronously from __init__
            print("[app] Calling _route_change() directly for initial render.")
            self._route_change()

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def _route_change(self, e=None):
        """Handle route changes — rebuild view stack.
        
        Called both by page.on_route_change (no-arg in Flet 0.80) and manually.
        """
        print(f"[route] route_change: {self.page.route}")
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
            print(f"[route] view stack size: {len(self.page.views)}")
        except Exception as ex:
            print(f"[route] ERROR in _route_change: {ex}")
            traceback.print_exc()

    def _view_pop(self, e=None):
        """Handle back navigation (system back button)."""
        print(f"[route] view_pop triggered")
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
        print("[app] Building start view...")
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
        print("[app] Building project view...")
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
        print(f"[route] _navigate_to: {route}")
        self.page.route = route
        self._route_change()

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
        print(f"[app] ERROR: {message}")
        show_snack(self.page, message, ft.Colors.RED_400)

    def _show_success(self, message: str):
        print(f"[app] OK: {message}")
        show_snack(self.page, message, ft.Colors.GREEN_400)

    def _show_info(self, message: str):
        print(f"[app] INFO: {message}")
        show_snack(self.page, message, ft.Colors.BLUE_400)

    # ------------------------------------------------------------------
    # Project operations
    # ------------------------------------------------------------------

    async def _open_initial_project(self, path: str):
        """Open project passed via CLI on startup."""
        await self.open_project(path)

    async def new_project(self, e=None):
        """Create new project."""
        print("[app] new_project called")
        try:
            file_path = await ft.FilePicker().save_file(
                dialog_title="Create New Project",
                file_name="project.dasmix",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["dasmix"]
            )

            if not file_path:
                print("[app] new_project: cancelled")
                return

            project_path = Path(file_path)
            if project_path.suffix != '.dasmix':
                project_path = project_path.with_suffix('.dasmix')

            print(f"[app] Creating project at: {project_path}")
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
            print(f"[app] new_project ERROR: {ex}")
            traceback.print_exc()
            self._show_error(f"Error creating project: {ex}")

    async def open_project_dialog(self, e=None):
        """Open project via file picker."""
        print("[app] open_project_dialog called")
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
                print("[app] open_project_dialog: cancelled")

        except Exception as ex:
            print(f"[app] open_project_dialog ERROR: {ex}")
            traceback.print_exc()
            self._show_error(f"Error opening file picker: {ex}")

    async def open_project(self, path: str, e=None):
        """
        Open existing project.

        Args:
            path: Path to project file
            e: Optional event (for callback compatibility)
        """
        print(f"[app] open_project: {path}")
        try:
            project_path = Path(path)

            if not project_path.exists():
                self._show_error(f"Project file not found: {path}")
                return

            if self.current_project:
                await self.current_project.close()

            self.current_project = Project(path=project_path, create_if_not_exists=False)
            await self.current_project.initialize()

            config.add_recent_project(str(project_path))
            self.show_project_view()
            self._show_success(f"Opened project: {project_path.name}")

        except Exception as ex:
            print(f"[app] open_project ERROR: {ex}")
            traceback.print_exc()
            self._show_error(f"Error opening project: {ex}")

    async def close_project(self, e=None):
        """Close current project."""
        print("[app] close_project called")
        if self.current_project:
            try:
                await self.current_project.close()
                self.current_project = None
                self.show_start_view()
                self._show_info("Project closed")
            except Exception as ex:
                print(f"[app] close_project ERROR: {ex}")
                traceback.print_exc()
                self._show_error(f"Error closing project: {ex}")
