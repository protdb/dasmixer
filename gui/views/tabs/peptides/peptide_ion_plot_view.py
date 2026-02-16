"""Plot view for peptide ion coverage (b/y ions)."""

import flet as ft
import plotly.graph_objects as go

from gui.components.base_plot_view import BasePlotView
from api.project.project import Project
from api.spectra.plot_flow import make_full_spectrum_plot


class PeptideIonPlotView(BasePlotView):
    """Plot view for peptide ion coverage with b/y ions."""
    
    plot_type_name = "peptide_ion_coverage"
    
    def __init__(self, project: Project, ion_settings_section):
        """
        Initialize plot view.
        
        Args:
            project: Project instance
            ion_settings_section: Reference to IonSettingsSection for ion parameters
        """
        self.ion_settings_section = ion_settings_section
        super().__init__(project, title="Ion Match Plot")
    
    def get_default_settings(self) -> dict:
        """Get default plot display settings."""
        return {
            'show_title': True,
            'show_legend': True
        }
    
    def _build_plot_settings_view(self) -> ft.Control:
        """Build settings UI."""
        self.show_title_checkbox = ft.Checkbox(
            label="Show title",
            value=self.plot_settings.get('show_title', True)
        )
        
        self.show_legend_checkbox = ft.Checkbox(
            label="Show legend",
            value=self.plot_settings.get('show_legend', True)
        )
        
        return ft.Column([
            ft.Text("Plot Display Options:", weight=ft.FontWeight.BOLD, size=13),
            ft.Container(height=5),
            self.show_title_checkbox,
            self.show_legend_checkbox,
            ft.Container(height=10),
            ft.Text(
                "Note: Ion matching parameters are controlled in Ion Settings section.",
                size=11,
                italic=True,
                color=ft.Colors.GREY_600
            )
        ], spacing=5)
    
    async def _update_settings_from_ui(self):
        """Update settings from UI controls."""
        self.plot_settings['show_title'] = self.show_title_checkbox.value
        self.plot_settings['show_legend'] = self.show_legend_checkbox.value
    
    async def generate_plot(self, entity_id: str) -> go.Figure:
        """
        Generate ion coverage plot for spectrum.
        
        Args:
            entity_id: spectrum_id (as string)
        
        Returns:
            go.Figure: Ion coverage plot
        """
        spectrum_id = int(entity_id)
        
        # Get spectrum data
        plot_data = await self.project.get_spectrum_plot_data(spectrum_id)
        
        # Get ion match parameters from ion settings section
        params = self.ion_settings_section.get_ion_match_parameters()
        
        # Generate plot
        fig = make_full_spectrum_plot(params=params, **plot_data)
        
        # Apply display settings
        if not self.plot_settings.get('show_title', True):
            fig.update_layout(title=None)
        
        if not self.plot_settings.get('show_legend', True):
            fig.update_layout(showlegend=False)
        
        return fig
