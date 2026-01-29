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
            bgcolor=ft.colors.SURFACE_VARIANT,
            actions=[
                ft.PopupMenuButton(
                    items=[
                        ft.PopupMenuItem(
                            text="New Project",
                            icon=ft.icons.CREATE_NEW_FOLDER,
                            on_click=self.new_project
                        ),
                        ft.PopupMenuItem(
                            text="Open Project",
                            icon=ft.icons.FOLDER_OPEN,
                            on_click=self.open_project_dialog
                        ),
                        ft.PopupMenuItem(),  # Divider
                        ft.PopupMenuItem(
                            text="Close Project",
                            icon=ft.icons.CLOSE,
                            on_click=self.close_project,
                            disabled=self.current_project is None
                        ),
                        ft.PopupMenuItem(),  # Divider
                        ft.PopupMenuItem(
                            text="Exit",
                            icon=ft.icons.EXIT_TO_APP,
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
            on_create_project=self.new_project,
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
            on_close=self.close_project
        )
        self.page.add(view)
        self.page.update()
        
        # Update menu
        self.setup_menu()
    
    async def new_project(self, e=None):
        """Create new project."""
        # Show file picker for save location
        async def save_file_result(e: ft.FilePickerResultEvent):
            if e.path:
                project_path = Path(e.path)
                
                # Ensure .dasmix extension
                if project_path.suffix != '.dasmix':
                    project_path = project_path.with_suffix('.dasmix')
                
                # Create project
                try:
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
                        bgcolor=ft.colors.GREEN_400
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
                    
                except Exception as ex:
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"Error creating project: {ex}"),
                        bgcolor=ft.colors.RED_400
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
        
        # Create file picker
        save_picker = ft.FilePicker(on_result=save_file_result)
        self.page.overlay.append(save_picker)
        self.page.update()
        
        # Show save dialog
        save_picker.save_file(
            dialog_title="Create New Project",
            file_name="project.dasmix",
            allowed_extensions=["dasmix"],
            file_type=ft.FilePickerFileType.CUSTOM
        )
    
    async def open_project_dialog(self, e=None):
        """Open project via file picker."""
        async def pick_file_result(e: ft.FilePickerResultEvent):
            if e.files:
                file_path = e.files[0].path
                await self.open_project(file_path)
        
        # Create file picker
        pick_files = ft.FilePicker(on_result=pick_file_result)
        self.page.overlay.append(pick_files)
        self.page.update()
        
        # Show open dialog
        pick_files.pick_files(
            dialog_title="Open Project",
            allowed_extensions=["dasmix"],
            file_type=ft.FilePickerFileType.CUSTOM
        )
    
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
                    bgcolor=ft.colors.RED_400
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
                bgcolor=ft.colors.GREEN_400
            )
            self.page.snack_bar.open = True
            self.page.update()
            
        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Error opening project: {ex}"),
                bgcolor=ft.colors.RED_400
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
                    bgcolor=ft.colors.BLUE_400
                )
                self.page.snack_bar.open = True
                self.page.update()
                
            except Exception as ex:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Error closing project: {ex}"),
                    bgcolor=ft.colors.RED_400
                )
                self.page.snack_bar.open = True
                self.page.update()
