"""Base class for peptides tab sections."""

import flet as ft
from abc import ABC, abstractmethod

from dasmixer.api.project.project import Project
from .shared_state import PeptidesTabState
from dasmixer.gui.utils import show_snack
from dasmixer.utils import logger


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
        """Show error snackbar using context."""
        try:
            page = ft.context.page
            show_snack(page, message, ft.Colors.RED_400)
            page.update()
        except RuntimeError:
            # Fallback if not in Flet context
            logger.exception(f"ERROR: {message}")
    
    def show_success(self, message: str):
        """Show success snackbar using context."""
        try:
            page = ft.context.page
            show_snack(page, message, ft.Colors.GREEN_400)
            page.update()
        except RuntimeError:
            logger.debug(f"SUCCESS: {message}")
    
    def show_info(self, message: str):
        """Show info snackbar using context."""
        try:
            page = ft.context.page
            show_snack(page, message, ft.Colors.BLUE_400)
            page.update()
        except RuntimeError:
            logger.debug(f"INFO: {message}")
    
    def show_warning(self, message: str):
        """Show warning snackbar using context."""
        try:
            page = ft.context.page
            show_snack(page, message, ft.Colors.ORANGE_400)
            page.update()
        except RuntimeError:
            logger.debug(f"WARNING: {message}")
