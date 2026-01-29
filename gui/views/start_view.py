"""Start view - project selection screen."""

import flet as ft
from pathlib import Path


class StartView(ft.UserControl):
    """
    Startup screen for creating/opening projects.
    
    Displays:
    - Application title and description
    - Create New Project button
    - Open Project button  
    - List of recent projects
    """
    
    def __init__(
        self,
        on_create_project,
        on_open_project,
        recent_projects: list[str]
    ):
        """
        Initialize start view.
        
        Args:
            on_create_project: Callback for creating new project
            on_open_project: Callback for opening project (receives path)
            recent_projects: List of recent project paths
        """
        super().__init__()
        self.on_create_project = on_create_project
        self.on_open_project = on_open_project
        self.recent_projects = recent_projects
    
    def build(self):
        """Build the view."""
        # Header
        header = ft.Container(
            content=ft.Column([
                ft.Text(
                    "DASMixer",
                    size=48,
                    weight=ft.FontWeight.BOLD,
                    color=ft.colors.PRIMARY
                ),
                ft.Text(
                    "Mass Spectrometry Data Integration Tool",
                    size=20,
                    color=ft.colors.ON_SURFACE_VARIANT
                )
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10
            ),
            padding=40
        )
        
        # Action buttons
        create_btn = ft.ElevatedButton(
            text="Create New Project",
            icon=ft.icons.CREATE_NEW_FOLDER,
            on_click=self.on_create_project,
            style=ft.ButtonStyle(
                padding=20,
                text_style=ft.TextStyle(size=16)
            ),
            width=300,
            height=60
        )
        
        open_btn = ft.ElevatedButton(
            text="Open Project",
            icon=ft.icons.FOLDER_OPEN,
            on_click=lambda _: None,  # Handled by file picker in app
            style=ft.ButtonStyle(
                padding=20,
                text_style=ft.TextStyle(size=16)
            ),
            width=300,
            height=60
        )
        
        # This will trigger the file picker from parent app
        # We need to connect it properly
        open_btn.on_click = self._handle_open_click
        
        buttons = ft.Column([
            create_btn,
            open_btn
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=15
        )
        
        # Recent projects
        recent_items = []
        for project_path in self.recent_projects:
            path = Path(project_path)
            if path.exists():
                recent_items.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.icons.DESCRIPTION),
                        title=ft.Text(path.name, weight=ft.FontWeight.BOLD),
                        subtitle=ft.Text(str(path.parent), size=12),
                        on_click=lambda e, p=project_path: self.on_open_project(p),
                        hover_color=ft.colors.SURFACE_VARIANT
                    )
                )
        
        recent_section = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Recent Projects",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=ft.colors.PRIMARY
                ),
                ft.Container(height=10),
                ft.Column(
                    recent_items if recent_items else [
                        ft.Text(
                            "No recent projects",
                            size=14,
                            italic=True,
                            color=ft.colors.ON_SURFACE_VARIANT
                        )
                    ],
                    spacing=5
                )
            ]),
            padding=20,
            width=600
        )
        
        # Main layout
        return ft.Container(
            content=ft.Column([
                header,
                ft.Container(height=20),
                buttons,
                ft.Container(height=40),
                recent_section
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            scroll=ft.ScrollMode.AUTO
            ),
            alignment=ft.alignment.top_center,
            expand=True,
            bgcolor=ft.colors.BACKGROUND
        )
    
    def _handle_open_click(self, e):
        """Handle open button click - delegates to parent."""
        # Parent app handles file picker
        # This is a placeholder
        pass
