"""Start view - project selection screen."""

import flet as ft
from pathlib import Path

from dasmixer.gui.utils import get_asset_path


class StartView(ft.Container):
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
        
        # Build content
        self.content = self._build_content()
        self.alignment = ft.Alignment.TOP_CENTER
        self.expand = True
    
    def _build_content(self):
        """Build the view content."""
        # Header — logo image + title text
        logo_path = get_asset_path("logo_header.png")
        breakpoints = {
            ft.ResponsiveRowBreakpoint.MD: 6,
            ft.ResponsiveRowBreakpoint.SM: 12
        }
        header_controls = []
        if logo_path.exists():
            header_controls.append(
                ft.Image(
                    src=str(logo_path),
                    fit=ft.BoxFit.CONTAIN,
                    height=80,
                )
            )
        header_controls += [
            ft.Text(
                "DASMixer",
                size=48,
                weight=ft.FontWeight.BOLD,
            ),
            ft.Text(
                "Mass Spectrometry Data Integration Tool",
                size=20,
            ),
        ]
        header = ft.Container(
            content=ft.Column(
                header_controls,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
            ),
            padding=40,
            col = breakpoints
        )
        
        # Action buttons
        create_btn = ft.ElevatedButton(
            content=ft.Text("Create New Project"),
            icon=ft.Icons.CREATE_NEW_FOLDER,
            on_click=self.on_create_project,
            width=300,
            height=60
        )
        
        open_btn = ft.ElevatedButton(
            content=ft.Text("Open Project"),
            icon=ft.Icons.FOLDER_OPEN,
            on_click=self._handle_open_click,
            width=300,
            height=60
        )

        buttons = ft.Column([
            create_btn,
            open_btn
        ],
        horizontal_alignment=ft.CrossAxisAlignment.START,
        spacing=15
        )
        
        # Recent projects
        recent_items = []
        for project_path in self.recent_projects:
            path = Path(project_path)
            if path.exists():
                recent_items.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.DESCRIPTION),
                        title=ft.Text(path.name, weight=ft.FontWeight.BOLD),
                        subtitle=ft.Text(str(path.parent), size=12),
                        on_click=lambda e, p=project_path: self.on_open_project(p)
                    )
                )
        
        recent_section = ft.Container(
            content=ft.Column([
                ft.Text(
                    "Recent Projects",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Container(height=10),
                ft.Column(
                    recent_items if recent_items else [
                        ft.Text(
                            "No recent projects",
                            size=14,
                            italic=True,
                        )
                    ],
                    spacing=5
                )
            ]),
            padding=20,
            # width=600
            col=breakpoints
        )

        layout = ft.ResponsiveRow(
            [
                header,
                recent_section,
            ],

        )
        
        # Main layout
        # return ft.Column([
        #     header,
        #     ft.Container(height=20),
        #     buttons,
        #     ft.Container(height=40),
        #     recent_section
        # ],
        # horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        # scroll=ft.ScrollMode.AUTO
        # )
        return layout
    
    def _handle_open_click(self, e):
        """Handle open button click - triggers parent open dialog callback."""
        # on_open_project with no path signals "open dialog"
        self.on_open_project(None)
