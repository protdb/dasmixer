"""Global settings section for reports."""

import flet as ft
from api.project.project import Project
from .shared_state import ReportsTabState


class SettingsSection(ft.Container):
    """
    Section with global settings for all reports.
    
    Contains:
    - Plot font size
    - Image dimensions
    - Batch operation buttons
    """
    
    def __init__(self, project: Project, state: ReportsTabState, parent_tab):
        super().__init__()
        self.project = project
        self.state = state
        self.parent_tab = parent_tab
        
        # Controls
        self.font_size_field = ft.TextField(
            label="Plot Font Size",
            value=str(state.plot_font_size),
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        self.width_field = ft.TextField(
            label="Plot Width (px)",
            value=str(state.plot_width),
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        self.height_field = ft.TextField(
            label="Plot Height (px)",
            value=str(state.plot_height),
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        # Buttons
        self.save_settings_btn = ft.ElevatedButton(
            "Save Settings",
            icon=ft.Icons.SAVE,
            on_click=self._on_save_settings
        )
        
        self.generate_all_btn = ft.ElevatedButton(
            "Generate All Selected",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._on_generate_all
        )
        
        self.export_all_btn = ft.ElevatedButton(
            "Export All Selected",
            icon=ft.Icons.FILE_DOWNLOAD,
            on_click=self._on_export_all
        )
        
        # Build UI
        self.content = self._build_content()
        self.padding = 20
        self.border = ft.border.all(1, ft.Colors.GREY)
        self.border_radius = 10
    
    def _build_content(self) -> ft.Control:
        """Build section content."""
        return ft.Column([
            ft.Text("Global Settings", size=20, weight=ft.FontWeight.BOLD),
            ft.Divider(),
            
            ft.Row([
                self.font_size_field,
                self.width_field,
                self.height_field,
                self.save_settings_btn
            ], spacing=10),
            
            ft.Container(height=10),
            
            ft.Row([
                self.generate_all_btn,
                self.export_all_btn
            ], spacing=10)
        ])
    
    async def load_settings(self):
        """Load settings from project."""
        font_size = await self.project.get_setting('plot_font_size', '12')
        width = await self.project.get_setting('plot_width', '1200')
        height = await self.project.get_setting('plot_height', '800')
        
        self.state.plot_font_size = int(font_size)
        self.state.plot_width = int(width)
        self.state.plot_height = int(height)
        
        self.font_size_field.value = font_size
        self.width_field.value = width
        self.height_field.value = height
        
        if self.page:
            self.update()
    
    async def _on_save_settings(self, e):
        """Save settings."""
        try:
            # Validation
            font_size = int(self.font_size_field.value)
            width = int(self.width_field.value)
            height = int(self.height_field.value)
            
            # Save to project
            await self.project.set_setting('plot_font_size', str(font_size))
            await self.project.set_setting('plot_width', str(width))
            await self.project.set_setting('plot_height', str(height))
            
            # Update state
            self.state.plot_font_size = font_size
            self.state.plot_width = width
            self.state.plot_height = height
            
            self._show_success("Settings saved successfully")
            
        except ValueError as ex:
            self._show_error(f"Invalid input: {ex}")
        except Exception as ex:
            self._show_error(f"Failed to save settings: {ex}")
    
    async def _on_generate_all(self, e):
        """Generate all selected reports."""
        if not self.state.selected_reports:
            self._show_warning("No reports selected")
            return
        
        # Delegate to parent tab
        await self.parent_tab.generate_selected_reports()
    
    async def _on_export_all(self, e):
        """Export all selected reports."""
        if not self.state.selected_reports:
            self._show_warning("No reports selected")
            return
        
        # Delegate to parent tab
        await self.parent_tab.export_selected_reports()
    
    def _show_error(self, message: str):
        """Show error."""
        if self.page:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    def _show_success(self, message: str):
        """Show success."""
        if self.page:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=ft.Colors.GREEN_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    def _show_warning(self, message: str):
        """Show warning."""
        if self.page:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=ft.Colors.ORANGE_400
            )
            self.page.snack_bar.open = True
            self.page.update()
