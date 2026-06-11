"""Base class for samples tab sections."""

import flet as ft
from abc import ABC, abstractmethod

from dasmixer.api.project.project import Project
from .shared_state import SamplesTabState
from dasmixer.gui.utils import show_snack


class BaseSection(ft.Container, ABC):
    """
    Base class for samples tab sections.
    
    All sections inherit from ft.Container and must implement _build_content().
    State is shared via SamplesTabState instance.
    """
    
    def __init__(self, project: Project, state: SamplesTabState, parent_tab):
        """
        Initialize section.
        
        Args:
            project: Project instance
            state: Shared state object
            parent_tab: Parent SamplesTab instance
        """
        super().__init__()
        self.project = project
        self.state = state
        self.parent_tab = parent_tab
        
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
    
    def show_error(self, message: str):
        """Show error snackbar."""
        if self.page:
            show_snack(self.page, message, ft.Colors.RED_400)
            self.page.update()
    
    def show_success(self, message: str):
        """Show success snackbar."""
        if self.page:
            show_snack(self.page, message, ft.Colors.GREEN_400)
            self.page.update()
    
    def show_info(self, message: str):
        """Show info snackbar."""
        if self.page:
            show_snack(self.page, message, ft.Colors.BLUE_400)
            self.page.update()
    
    def show_warning(self, message: str):
        """Show warning snackbar."""
        if self.page:
            show_snack(self.page, message, ft.Colors.ORANGE_400)
            self.page.update()
