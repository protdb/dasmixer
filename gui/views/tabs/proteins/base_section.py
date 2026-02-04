"""Base class for proteins tab sections."""

import flet as ft
from abc import ABC, abstractmethod

from api.project.project import Project
from .shared_state import ProteinsTabState


class BaseSection(ft.Container, ABC):
    """
    Base class for proteins tab sections.
    
    All sections inherit from ft.Container and must implement _build_content().
    State is shared via ProteinsTabState instance.
    """
    
    def __init__(self, project: Project, state: ProteinsTabState):
        """
        Initialize section.
        
        Args:
            project: Project instance
            state: Shared state object
        """
        super().__init__()
        self.project = project
        self.state = state
        
        # Build content
        self.content = self._build_content()
        
        # Configure container
        self.padding = 20
        self.border = ft.border.all(1, ft.Colors.GREY)
        self.border_radius = 10
    
    @abstractmethod
    def _build_content(self) -> ft.Control:
        """
        Build section content.
        
        Must be implemented by subclasses.
        
        Returns:
            Flet control representing section UI
        """
        pass
    
    async def load_data(self):
        """
        Load initial data for section.
        
        Override in subclasses if needed.
        """
        pass
    
    async def save_settings(self):
        """
        Save section settings to project.
        
        Override in subclasses if needed.
        """
        pass
    
    def show_error(self, message: str):
        """Show error snackbar using context."""
        try:
            page = ft.context.page
            page.snack_bar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=ft.Colors.RED_400
            )
            page.snack_bar.open = True
            page.update()
        except RuntimeError:
            # Fallback if not in Flet context
            print(f"ERROR: {message}")
    
    def show_success(self, message: str):
        """Show success snackbar using context."""
        try:
            page = ft.context.page
            page.snack_bar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=ft.Colors.GREEN_400
            )
            page.snack_bar.open = True
            page.update()
        except RuntimeError:
            print(f"SUCCESS: {message}")
    
    def show_info(self, message: str):
        """Show info snackbar using context."""
        try:
            page = ft.context.page
            page.snack_bar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=ft.Colors.BLUE_400
            )
            page.snack_bar.open = True
            page.update()
        except RuntimeError:
            print(f"INFO: {message}")
    
    def show_warning(self, message: str):
        """Show warning snackbar using context."""
        try:
            page = ft.context.page
            page.snack_bar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=ft.Colors.ORANGE_400
            )
            page.snack_bar.open = True
            page.update()
        except RuntimeError:
            print(f"WARNING: {message}")
