"""Base class for peptides tab sections."""

import flet as ft
from abc import ABC, abstractmethod

from api.project.project import Project
from .shared_state import PeptidesTabState


class BaseSection(ft.Container, ABC):
    """
    Base class for peptides tab sections.
    
    All sections inherit from ft.Container and must implement _build_content().
    State is shared via PeptidesTabState instance.
    """
    
    def __init__(self, project: Project, state: PeptidesTabState):
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
        """Show error snackbar."""
        if self.page:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    def show_success(self, message: str):
        """Show success snackbar."""
        if self.page:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=ft.Colors.GREEN_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    def show_info(self, message: str):
        """Show info snackbar."""
        if self.page:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=ft.Colors.BLUE_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    def show_warning(self, message: str):
        """Show warning snackbar."""
        if self.page:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=ft.Colors.ORANGE_400
            )
            self.page.snack_bar.open = True
            self.page.update()
