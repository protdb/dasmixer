"""Plot view for protein concentrations (boxplot/violin)."""

import flet as ft
import plotly.graph_objects as go
import numpy as np
import pandas as pd

from dasmixer.gui.components.base_plot_view import BasePlotView
from dasmixer.api.project.project import Project
from dasmixer.gui.utils import show_snack


class ProteinConcentrationPlotView(BasePlotView):
    """Plot view for protein concentration (LFQ) across subsets."""
    
    plot_type_name = "protein_concentration"
    
    def __init__(self, project: Project):
        super().__init__(project, title="Protein Concentration Plot")
        self.available_subsets = []
    
    def get_default_settings(self) -> dict:
        """Get default plot settings."""
        return {
            'algorithm': 'emPAI',
            'plot_type': 'boxplot',
            'include_title': True,
            'remove_outliers': False,
            'outlier_range': 3.0,
            'show_all_dots': False,
            'selected_subsets': [],
            'value_type': 'rel',
            'multiplier': 'x1'
        }
    
    def _build_plot_settings_view(self) -> ft.Control:
        """Build settings UI."""
        # Algorithm dropdown
        self.algorithm_dropdown = ft.Dropdown(
            label="Algorithm",
            options=[
                ft.DropdownOption(key="emPAI", text="emPAI"),
                ft.DropdownOption(key="iBAQ", text="iBAQ"),
                ft.DropdownOption(key="NSAF", text="NSAF"),
                ft.DropdownOption(key="Top3", text="Top3")
            ],
            value=self.plot_settings.get('algorithm', 'emPAI'),
            width=200
        )
        
        # Plot type dropdown
        self.plot_type_dropdown = ft.Dropdown(
            label="Plot Type",
            options=[
                ft.DropdownOption(key="boxplot", text="Boxplot"),
                ft.DropdownOption(key="violin", text="Violin Plot")
            ],
            value=self.plot_settings.get('plot_type', 'boxplot'),
            width=200
        )
        
        # Checkboxes
        self.include_title_checkbox = ft.Checkbox(
            label="Include title",
            value=self.plot_settings.get('include_title', True)
        )
        
        self.remove_outliers_checkbox = ft.Checkbox(
            label="Remove outliers",
            value=self.plot_settings.get('remove_outliers', False)
        )
        
        self.outlier_range_field = ft.TextField(
            label="Outlier range (MAD multiplier)",
            value=str(self.plot_settings.get('outlier_range', 3.0)),
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        self.show_all_dots_checkbox = ft.Checkbox(
            label="Show all data points",
            value=self.plot_settings.get('show_all_dots', False)
        )
        
        # Value type radio
        self.value_type_radio = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value="rel", label="rel"),
                ft.Radio(value="gl", label="g/l"),
                ft.Radio(value="mol", label="mol/l"),
            ]),
            value=self.plot_settings.get('value_type', 'rel'),
            on_change=self._on_value_type_changed,
        )

        # Multiplier dropdown
        self.multiplier_dropdown = ft.Dropdown(
            label="Multiplier",
            options=[
                ft.DropdownOption(key="x1", text="×1"),
                ft.DropdownOption(key="x1e3", text="×10³ (milli)"),
                ft.DropdownOption(key="x1e6", text="×10⁶ (micro)"),
                ft.DropdownOption(key="x1e9", text="×10⁹ (nano)"),
                ft.DropdownOption(key="x1e12", text="×10¹² (femto)"),
            ],
            value=self.plot_settings.get('multiplier', 'x1'),
            width=200,
            disabled=(self.plot_settings.get('value_type', 'rel') == 'rel'),
        )
        
        # Subsets selection (will be populated on load)
        self.subset_checkboxes = []
        self.subsets_column = ft.Column([], spacing=5)
        
        refresh_subsets_btn = ft.ElevatedButton(
            content=ft.Text("Load Subsets"),
            icon=ft.Icons.REFRESH,
            on_click=lambda e: self.page.run_task(self._load_subsets)
        )
        
        return ft.Column([
            ft.Text("Algorithm & Plot Type:", weight=ft.FontWeight.BOLD, size=13),
            ft.Row([self.algorithm_dropdown, self.plot_type_dropdown], spacing=10),
            ft.Container(height=10),
            
            ft.Text("Display Options:", weight=ft.FontWeight.BOLD, size=13),
            self.include_title_checkbox,
            self.show_all_dots_checkbox,
            ft.Container(height=10),
            
            ft.Text("Value Type:", weight=ft.FontWeight.BOLD, size=13),
            self.value_type_radio,
            ft.Container(height=4),
            self.multiplier_dropdown,
            ft.Container(height=10),
            
            ft.Text("Outlier Removal:", weight=ft.FontWeight.BOLD, size=13),
            self.remove_outliers_checkbox,
            self.outlier_range_field,
            ft.Container(height=10),
            
            ft.Text("Subset Selection:", weight=ft.FontWeight.BOLD, size=13),
            refresh_subsets_btn,
            self.subsets_column
        ], spacing=5)
    
    async def _load_subsets(self, e=None):
        """Load available subsets and create checkboxes."""
        try:
            subsets = await self.project.get_subsets()
            self.available_subsets = [s.name for s in subsets]
            
            # Create checkboxes
            self.subset_checkboxes = []
            self.subsets_column.controls.clear()
            
            for subset_name in self.available_subsets:
                checkbox = ft.Checkbox(
                    label=subset_name,
                    value=(subset_name in self.plot_settings.get('selected_subsets', []))
                )
                self.subset_checkboxes.append(checkbox)
                self.subsets_column.controls.append(checkbox)
            
            if self.page:
                self.page.update()
            
        except Exception as ex:
            if self.page:
                show_snack(self.page, f"Error loading subsets: {ex}", ft.Colors.RED_400)
                self.page.update()
    
    def _on_value_type_changed(self, e):
        """Handle value type radio change."""
        value_type = e.control.value
        self.multiplier_dropdown.disabled = (value_type == 'rel')
        if self.page:
            self.page.update()
    
    async def _update_settings_from_ui(self):
        """Update settings from UI controls."""
        self.plot_settings['algorithm'] = self.algorithm_dropdown.value
        self.plot_settings['plot_type'] = self.plot_type_dropdown.value
        self.plot_settings['include_title'] = self.include_title_checkbox.value
        self.plot_settings['remove_outliers'] = self.remove_outliers_checkbox.value
        self.plot_settings['outlier_range'] = float(self.outlier_range_field.value or 3.0)
        self.plot_settings['show_all_dots'] = self.show_all_dots_checkbox.value
        self.plot_settings['value_type'] = self.value_type_radio.value
        self.plot_settings['multiplier'] = self.multiplier_dropdown.value
        
        # Get selected subsets
        selected_subsets = []
        for checkbox in self.subset_checkboxes:
            if checkbox.value:
                selected_subsets.append(checkbox.label)
        self.plot_settings['selected_subsets'] = selected_subsets
    
    async def generate_plot(self, entity_id: str) -> go.Figure:
        """
        Generate concentration plot for protein.
        
        Args:
            entity_id: protein_id
        
        Returns:
            go.Figure: Concentration plot
        """
        protein_id = entity_id
        algorithm = self.plot_settings.get('algorithm', 'emPAI')
        
        # Multiplier map
        multiplier_map = {
            "x1":    (1.0,   ""),
            "x1e3":  (1e3,   "m"),
            "x1e6":  (1e6,   "μ"),
            "x1e9":  (1e9,   "n"),
            "x1e12": (1e12,  "f"),
        }
        value_type = self.plot_settings.get('value_type', 'rel')
        multiplier_key = self.plot_settings.get('multiplier', 'x1')
        mult_factor, mult_prefix = multiplier_map.get(multiplier_key, (1.0, ""))
        
        # Determine data column based on value type
        if value_type == 'rel' or value_type not in ('gl', 'mol'):
            data_column = 'rel_value'
            y_label = algorithm
        else:
            column_name = 'abs_value_gl' if value_type == 'gl' else 'abs_value_mol'
            data_column = column_name
            unit = 'g/l' if value_type == 'gl' else 'mol/l'
            y_label = f"{algorithm}, {mult_prefix}{unit}"
        
        # Get quantification data
        df = await self.project.get_protein_quantification_data(
            method=algorithm,
            protein_id=protein_id
        )
        
        if len(df) == 0:
            raise ValueError(f"No quantification data for {protein_id}")
        
        # Filter by selected subsets
        selected_subsets = self.plot_settings.get('selected_subsets', [])
        if selected_subsets:
            df = df[df['subset'].isin(selected_subsets)]
        
        if len(df) == 0:
            raise ValueError("No data after subset filtering")
        
        # Remove outliers if needed
        if self.plot_settings.get('remove_outliers', False):
            outlier_range = self.plot_settings.get('outlier_range', 3.0)
            df = self._remove_outliers(df, data_column, outlier_range)
        
        # Get subset colors
        subset_colors = await self._get_subset_colors()
        
        # Create figure
        fig = go.Figure()
        plot_type = self.plot_settings.get('plot_type', 'boxplot')
        
        for subset_name in df['subset'].unique():
            subset_df = df[df['subset'] == subset_name]
            color = subset_colors.get(subset_name, '#888888')
            
            if plot_type == 'boxplot':
                fig.add_trace(go.Box(
                    y=subset_df[data_column].apply(lambda x: x * mult_factor if x is not None and not (isinstance(x, float) and pd.isna(x)) else None),
                    name=subset_name,
                    marker_color=color,
                    boxmean='sd'
                ))
            else:  # violin
                fig.add_trace(go.Violin(
                    y=subset_df[data_column].apply(lambda x: x * mult_factor if x is not None and not (isinstance(x, float) and pd.isna(x)) else None),
                    name=subset_name,
                    marker_color=color,
                    box_visible=True,
                    meanline_visible=True
                ))
        
        # Add individual points if requested
        if self.plot_settings.get('show_all_dots', False):
            for subset_name in df['subset'].unique():
                subset_df = df[df['subset'] == subset_name]
                color = subset_colors.get(subset_name, '#888888')
                
                fig.add_trace(go.Scatter(
                    y=subset_df[data_column].apply(lambda x: x * mult_factor if x is not None and not (isinstance(x, float) and pd.isna(x)) else None),
                    x=[subset_name] * len(subset_df),
                    mode='markers',
                    marker=dict(size=4, color=color, opacity=0.5),
                    showlegend=False,
                    hoverinfo='y'
                ))
        
        # Layout
        title = f"Protein {protein_id} - {algorithm}" if self.plot_settings.get('include_title', True) else None
        fig.update_layout(
            title=title,
            yaxis_title=y_label,
            xaxis_title="Subset",
            template='plotly_white'
        )
        
        return fig
    
    def _remove_outliers(self, df, column, mad_multiplier):
        """Remove outliers using MAD method."""
        values = df[column].values
        median = np.median(values)
        mad = np.median(np.abs(values - median))
        
        if mad == 0:
            return df  # No variation, can't remove outliers
        
        lower_bound = median - mad_multiplier * mad
        upper_bound = median + mad_multiplier * mad
        
        return df[(df[column] >= lower_bound) & (df[column] <= upper_bound)]
    
    async def _get_subset_colors(self) -> dict:
        """Get subset colors from database."""
        subsets = await self.project.get_subsets()
        return {s.name: s.display_color or '#888888' for s in subsets}
    
    async def load_data(self):
        """Load data (subsets and settings)."""
        await super().load_data()
        await self._load_subsets()
