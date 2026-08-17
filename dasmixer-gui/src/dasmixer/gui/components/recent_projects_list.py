"""Reusable component for displaying the recent projects list."""

import flet as ft
from pathlib import Path


class RecentProjectsList(ft.Column):
    """
    Display list of recent projects with clickable tiles.

    Filters out non-existent files automatically.
    Reused both on the start screen and in the "Open Recent" modal dialog.
    """

    def __init__(self, recent_projects: list[str], on_click_project):
        """
        Args:
            recent_projects: List of project file paths (most recent first).
            on_click_project: Callback invoked with a single str path argument
                when a project tile is clicked.
        """
        super().__init__(spacing=5, scroll=ft.ScrollMode.AUTO)
        self.recent_projects = recent_projects
        self.on_click_project = on_click_project
        self.controls = self._build_list()

    def _build_list(self) -> list[ft.Control]:
        """Build list of tiles for existing projects."""
        items = []
        for project_path in self.recent_projects:
            path = Path(project_path)
            if path.exists():
                items.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.DESCRIPTION),
                        title=ft.Text(path.name, weight=ft.FontWeight.BOLD),
                        subtitle=ft.Text(str(path.parent), size=12),
                        on_click=lambda e, p=project_path: self.on_click_project(p),
                    )
                )

        if not items:
            items.append(
                ft.Text(
                    "No recent projects",
                    size=14,
                    italic=True,
                    color=ft.Colors.GREY_600,
                )
            )

        return items
