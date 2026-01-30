"""Main GUI application entry point."""

import flet as ft
from pathlib import Path
from api.config import config
from api.project.project import Project


def run_gui(project_path: str | None = None):
    """
    Entry point for GUI mode.
    
    Args:
        project_path: Optional path to project file to open immediately
    """
    def main(page: ft.Page):
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
        
        # Configure page
        self.page.title = "DASMixer - Mass Spectrometry Data Integration"
        self.page.window.width = config.window_width
        self.page.window.height = config.window_height
        self.page.padding = 0
        
        # Setup menu
        self.setup_menu()
        
        # Show initial view
        if initial_project_path:
            # Open project asynchronously
            self.page.run_task(self.open_project, initial_project_path)
        else:
            self.show_start_view()
    
    def setup_menu(self):
        """Create application menu bar."""
        self.page.appbar = ft.AppBar(
            title=ft.Text("DASMixer", size=20, weight=ft.FontWeight.BOLD),
            actions=[
                ft.PopupMenuButton(
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
                            disabled=self.current_project is None
                        ),
                        ft.PopupMenuItem(),  # Divider
                        ft.PopupMenuItem(
                            content=ft.Text("Exit"),
                            icon=ft.Icons.EXIT_TO_APP,
                            on_click=lambda _: self.page.window_close()
                        ),
                    ]
                )
            ]
        )
    
    def show_start_view(self):
        """Show startup screen."""
        from gui.views.start_view import StartView
        
        self.page.clean()
        view = StartView(
            on_create_project=lambda _: self.page.run_task(self.new_project),
            on_open_project=lambda path: self.page.run_task(self.open_project, path),
            recent_projects=config.recent_projects
        )
        self.page.add(view)
        self.page.update()
    
    def show_project_view(self):
        """Show project workspace."""
        from gui.views.project_view import ProjectView
        
        self.page.clean()
        view = ProjectView(
            project=self.current_project,
            on_close=lambda _: self.page.run_task(self.close_project)
        )
        self.page.add(view)
        self.page.update()
        
        # Update menu
        self.setup_menu()
    
    async def new_project(self, e=None):
        """Create new project."""
        try:
            # Use new async FilePicker API
            file_path = await ft.FilePicker().save_file(
                dialog_title="Create New Project",
                file_name="project.dasmix",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["dasmix"]
            )
            
            if not file_path:
                return  # User cancelled
            
            project_path = Path(file_path)
            
            # Ensure .dasmix extension
            if project_path.suffix != '.dasmix':
                project_path = project_path.with_suffix('.dasmix')
            
            # Create project
            self.current_project = Project(path=project_path, create_if_not_exists=True)
            await self.current_project.initialize()
            
            # Create default Control group
            await self.current_project.add_subset(
                "Control",
                details="Default control group",
                display_color="#3B82F6"
            )
            
            # Update config
            config.add_recent_project(str(project_path))
            
            # Show project view
            self.show_project_view()
            
            # Show success message
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Created project: {project_path.name}"),
                bgcolor=ft.Colors.GREEN_400
            )
            self.page.snack_bar.open = True
            self.page.update()
            
        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Error creating project: {ex}"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    async def open_project_dialog(self, e=None):
        """Open project via file picker."""
        try:
            # Use new async FilePicker API
            files = await ft.FilePicker().pick_files(
                dialog_title="Open Project",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["dasmix"],
                allow_multiple=False
            )
            
            if files:
                await self.open_project(files[0].path)
                
        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Error opening file picker: {ex}"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    async def open_project(self, path: str, e=None):
        """
        Open existing project.
        
        Args:
            path: Path to project file
            e: Optional event (for callback compatibility)
        """
        try:
            project_path = Path(path)
            
            if not project_path.exists():
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Project file not found: {path}"),
                    bgcolor=ft.Colors.RED_400
                )
                self.page.snack_bar.open = True
                self.page.update()
                return
            
            # Close current project if any
            if self.current_project:
                await self.current_project.close()
            
            # Open project
            self.current_project = Project(path=project_path, create_if_not_exists=False)
            await self.current_project.initialize()
            
            # Update config
            config.add_recent_project(str(project_path))
            
            # Show project view
            self.show_project_view()
            
            # Show success message
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Opened project: {project_path.name}"),
                bgcolor=ft.Colors.GREEN_400
            )
            self.page.snack_bar.open = True
            self.page.update()
            
        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Error opening project: {ex}"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    async def close_project(self, e=None):
        """Close current project."""
        if self.current_project:
            try:
                await self.current_project.close()
                self.current_project = None
                
                # Return to start view
                self.show_start_view()
                
                # Update menu
                self.setup_menu()
                
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text("Project closed"),
                    bgcolor=ft.Colors.BLUE_400
                )
                self.page.snack_bar.open = True
                self.page.update()
                
            except Exception as ex:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Error closing project: {ex}"),
                    bgcolor=ft.Colors.RED_400
                )
                self.page.snack_bar.open = True
                self.page.update()
