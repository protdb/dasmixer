"""Base class for all plot views with save/export functionality."""

import flet as ft
import plotly.graph_objects as go
from typing import Optional, Callable
from pathlib import Path
import base64

from api.project.project import Project
from gui.components.plotly_viewer import PlotlyViewer


class BasePlotView(ft.Container):
    """
    Base class for all plot views.
    
    Provides:
    - Settings panel (expandable)
    - Plot preview (expandable)
    - Save to project functionality
    - Export to PNG/SVG
    - Settings persistence in project
    
    Subclasses must implement:
    - plot_type_name: str - unique identifier
    - get_default_settings() -> dict
    - _build_plot_settings_view() -> ft.Control
    - generate_plot(entity_id: str) -> go.Figure
    """
    
    plot_type_name: str = "base_plot"
    
    def __init__(
        self,
        project: Project,
        title: str = "Plot",
        show_save_button: bool = True,
        show_export_button: bool = True
    ):
        super().__init__()
        self.project = project
        self.title = title
        self.show_save_button = show_save_button
        self.show_export_button = show_export_button
        
        # Current state
        self.plot_settings = self.get_default_settings()
        self.current_entity_id: Optional[str] = None
        self.current_figure: Optional[go.Figure] = None
        
        # UI references
        self.settings_panel: Optional[ft.ExpansionPanel] = None
        self.preview_panel: Optional[ft.ExpansionPanel] = None
        self.preview_container: Optional[ft.Container] = None
        self.expansion_panel_list: Optional[ft.ExpansionPanelList] = None
        self.save_button: Optional[ft.ElevatedButton] = None
        self.export_button: Optional[ft.ElevatedButton] = None
        
        # Build UI
        self.content = self._build_ui()
        self.padding = 10
        self.expand = True
    
    def get_default_settings(self) -> dict:
        """
        Get default settings for this plot type.
        
        Returns:
            dict: Default settings
        
        Note: Override in subclass
        """
        return {}
    
    def _build_plot_settings_view(self) -> ft.Control:
        """
        Build UI for plot settings.
        
        Returns:
            ft.Control: Settings UI
        
        Note: Override in subclass
        """
        return ft.Text("No settings available")
    
    async def generate_plot(self, entity_id: str) -> go.Figure:
        """
        Generate plot for given entity.
        
        Args:
            entity_id: Entity identifier (e.g., spectrum_id, protein_id)
        
        Returns:
            go.Figure: Generated plot
        
        Note: Override in subclass
        """
        raise NotImplementedError("Subclass must implement generate_plot()")
    
    def _build_ui(self) -> ft.Control:
        """Build the complete UI."""
        # Settings panel content
        settings_content = ft.Column([
            self._build_plot_settings_view(),
            ft.Container(height=10),
            ft.ElevatedButton(
                content=ft.Text("Apply Settings"),
                icon=ft.Icons.CHECK,
                on_click=lambda e: self.page.run_task(self._on_apply_settings, e)
            )
        ], spacing=5)
        
        # Preview panel content
        self.preview_container = ft.Container(
            content=ft.Text("No plot generated yet", color=ft.Colors.GREY_600),
            alignment=ft.Alignment.CENTER,
            height=400
        )
        
        # Build buttons row
        buttons = []
        if self.show_save_button:
            self.save_button = ft.ElevatedButton(
                content=ft.Text("Save to Project"),
                icon=ft.Icons.SAVE,
                on_click=lambda e: self.page.run_task(self._on_save_to_project, e),
                disabled=True  # Enabled after plot generation
            )
            buttons.append(self.save_button)
        
        if self.show_export_button:
            self.export_button = ft.ElevatedButton(
                content=ft.Text("Export..."),
                icon=ft.Icons.DOWNLOAD,
                on_click=lambda e: self.page.run_task(self._on_export, e),
                disabled=True  # Enabled after plot generation
            )
            buttons.append(self.export_button)
        
        preview_content = ft.Column([
            self.preview_container,
            ft.Container(height=10),
            ft.Row(buttons, spacing=10) if buttons else ft.Container()
        ], spacing=5)
        
        # Create expansion panels
        self.settings_panel = ft.ExpansionPanel(
            header=ft.ListTile(
                title=ft.Text("Plot Settings", weight=ft.FontWeight.BOLD)
            ),
            content=ft.Container(content=settings_content, padding=10),
            can_tap_header=True
        )
        
        self.preview_panel = ft.ExpansionPanel(
            header=ft.ListTile(
                title=ft.Text("Plot Preview", weight=ft.FontWeight.BOLD)
            ),
            content=ft.Container(content=preview_content, padding=10),
            can_tap_header=True,
            expanded=True
        )
        
        self.expansion_panel_list = ft.ExpansionPanelList(
            controls=[self.settings_panel, self.preview_panel],
            expand_icon_color=ft.Colors.BLUE,
            elevation=2
        )
        
        return ft.Column([
            ft.Text(self.title, size=16, weight=ft.FontWeight.BOLD),
            ft.Container(height=5),
            self.expansion_panel_list
        ], expand=True, scroll=ft.ScrollMode.AUTO)
    
    async def on_plot_requested(self, entity_id: str):
        """
        Callback when plot is requested from table.
        
        Args:
            entity_id: Entity ID to plot
        """
        self.current_entity_id = entity_id
        await self._generate_and_display_plot()
    
    async def _on_apply_settings(self, e):
        """Apply settings and regenerate plot."""
        await self._update_settings_from_ui()
        await self._save_settings_to_project()
        
        if self.current_entity_id:
            await self._generate_and_display_plot()
        
        if self.page:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text("Settings applied"),
                bgcolor=ft.Colors.GREEN_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    async def _update_settings_from_ui(self):
        """
        Read values from UI controls and update self.plot_settings.
        
        Note: Override in subclass
        """
        pass
    
    async def _save_settings_to_project(self):
        """Save settings to project settings."""
        for key, value in self.plot_settings.items():
            setting_key = f"plot_view_{self.plot_type_name}_{key}"
            await self.project.set_setting(setting_key, str(value))
    
    async def _load_settings_from_project(self):
        """Load settings from project settings."""
        for key in self.plot_settings.keys():
            setting_key = f"plot_view_{self.plot_type_name}_{key}"
            value = await self.project.get_setting(setting_key)
            if value is not None:
                # Try to parse value to appropriate type
                default_value = self.plot_settings[key]
                if isinstance(default_value, bool):
                    self.plot_settings[key] = value.lower() in ('true', '1', 'yes')
                elif isinstance(default_value, int):
                    self.plot_settings[key] = int(value)
                elif isinstance(default_value, float):
                    self.plot_settings[key] = float(value)
                else:
                    self.plot_settings[key] = value
    
    async def _generate_and_display_plot(self):
        """Generate plot and display in preview."""
        if not self.current_entity_id:
            return
        
        try:
            # Show loading
            self.preview_container.content = ft.ProgressRing()
            if self.page:
                self.page.update()
            
            # Generate plot
            fig = await self.generate_plot(self.current_entity_id)
            self.current_figure = fig
            
            # Apply global settings
            fig = await self._apply_global_settings(fig)
            
            # Display
            await self._display_plot(fig)
            
            # Enable buttons
            if self.save_button:
                self.save_button.disabled = False
            if self.export_button:
                self.export_button.disabled = False
            
            if self.page:
                self.page.update()
            
        except Exception as ex:
            self.preview_container.content = ft.Text(
                f"Error generating plot: {ex}",
                color=ft.Colors.RED_400
            )
            if self.page:
                self.page.update()
    
    async def _apply_global_settings(self, fig: go.Figure) -> go.Figure:
        """
        Apply global settings like font size, dimensions.
        
        Args:
            fig: Figure to modify
        
        Returns:
            go.Figure: Modified figure
        """
        # Get global settings from project
        font_size = await self.project.get_setting("global_plot_font_size")
        if font_size:
            fig.update_layout(font=dict(size=int(font_size)))
        
        return fig
    
    async def _display_plot(self, fig: go.Figure):
        """Display plot using PlotlyViewer."""
        viewer = PlotlyViewer(
            figure=fig,
            width=800,
            height=500,
            title=self.title,
            show_interactive_button=True
        )
        self.preview_container.content = viewer
        if self.page:
            self.page.update()
    
    async def _on_save_to_project(self, e):
        """Save current plot to project."""
        if not self.current_figure or not self.current_entity_id:
            return
        
        try:
            settings_to_save = {
                'entity_id': self.current_entity_id,
                'plot_settings': self.plot_settings.copy()
            }
            
            plot_id = await self.project.save_plot(
                plot_type=self.plot_type_name,
                figure=self.current_figure,
                settings=settings_to_save
            )
            
            if self.page:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Plot saved (ID: {plot_id})"),
                    bgcolor=ft.Colors.GREEN_400
                )
                self.page.snack_bar.open = True
                self.page.update()
            
        except Exception as ex:
            if self.page:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Error saving plot: {ex}"),
                    bgcolor=ft.Colors.RED_400
                )
                self.page.snack_bar.open = True
                self.page.update()
    
    async def _on_export(self, e):
        """Show export dialog."""
        if not self.current_figure:
            return
        
        # Create export dialog
        format_dropdown = ft.Dropdown(
            label="Format",
            options=[
                ft.DropdownOption(key="png", text="PNG"),
                ft.DropdownOption(key="svg", text="SVG")
            ],
            value="png",
            width=200
        )
        
        async def on_export_confirm(e):
            try:
                file_picker = ft.FilePicker()
                self.page.overlay.append(file_picker)
                self.page.update()
                
                format_ext = format_dropdown.value
                result = await file_picker.save_file(
                    file_name=f"plot_{self.current_entity_id}.{format_ext}",
                    allowed_extensions=[format_ext]
                )
                
                if result:
                    self.current_figure.write_image(result, format=format_ext)
                    
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"Plot exported to {result}"),
                        bgcolor=ft.Colors.GREEN_400
                    )
                    self.page.snack_bar.open = True
                
                dialog.open = False
                self.page.update()
                
            except Exception as ex:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Error exporting: {ex}"),
                    bgcolor=ft.Colors.RED_400
                )
                self.page.snack_bar.open = True
                dialog.open = False
                self.page.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text("Export Plot"),
            content=ft.Column([
                format_dropdown,
                ft.Text("Select format and location", size=12, color=ft.Colors.GREY_600)
            ], tight=True, spacing=10),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(dialog)),
                ft.ElevatedButton("Export", on_click=lambda e: self.page.run_task(on_export_confirm, e))
            ]
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _close_dialog(self, dialog):
        """Close dialog helper."""
        dialog.open = False
        if self.page:
            self.page.update()
    
    async def load_data(self):
        """Load data (settings from project)."""
        await self._load_settings_from_project()
