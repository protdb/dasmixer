"""Plot view for peptide ion coverage (b/y ions)."""

import flet as ft
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from dasmixer.gui.components.base_plot_view import BasePlotView
from dasmixer.api.project.project import Project
from dasmixer.api.project.mixins.plot_mixin import HEADER_FIELD_OPTIONS, DEFAULT_HEADER_FIELDS
from dasmixer.api.calculations.spectra.plot_flow import make_full_spectrum_plot
from dasmixer.utils import logger


class PeptideIonPlotView(BasePlotView):
    """Plot view for peptide ion coverage with b/y ions."""

    plot_type_name = "peptide_ion_coverage"

    def __init__(self, project: Project, ion_settings_section):
        self.ion_settings_section = ion_settings_section
        self._header_field_checkboxes: dict[str, ft.Checkbox] = {}
        super().__init__(project, title="Ion Match Plot")

    def get_default_settings(self) -> dict:
        return {
            'show_title': True,
            'show_legend': False,
            'show_protein_sequences': False,
            'header_fields': list(DEFAULT_HEADER_FIELDS),
        }

    def _build_plot_settings_view(self) -> ft.Control:
        self.show_title_checkbox = ft.Checkbox(
            label="Show title",
            value=self.plot_settings.get('show_title', True)
        )
        self.show_legend_checkbox = ft.Checkbox(
            label="Show legend",
            value=self.plot_settings.get('show_legend', True)
        )
        self.show_protein_sequences_cb = ft.Checkbox(
            label="Show sequences in proteins",
            value=self.plot_settings.get('show_protein_sequences', False)
        )

        selected_header_fields = self.plot_settings.get('header_fields', DEFAULT_HEADER_FIELDS)
        self._header_field_checkboxes = {}
        header_field_row_items = []
        for key, label, _default in HEADER_FIELD_OPTIONS:
            checkbox = ft.Checkbox(
                label=label,
                value=key in selected_header_fields,
            )
            container = ft.Container(
                content=checkbox,
                width=170
            )
            self._header_field_checkboxes[key] = checkbox
            header_field_row_items.append(container)

        return ft.Column([
            ft.Text("Plot Display Options:", weight=ft.FontWeight.BOLD, size=13),
            ft.Container(height=5),
            self.show_title_checkbox,
            self.show_legend_checkbox,
            self.show_protein_sequences_cb,
            ft.Container(height=10),
            ft.Text("Subplot Header Fields:", weight=ft.FontWeight.BOLD, size=13),
            ft.Row(header_field_row_items, wrap=True, spacing=15, run_spacing=5),
            ft.Container(height=10),
            ft.Text(
                "Note: Ion matching parameters are controlled in Ion Settings section.",
                size=11, italic=True, color=ft.Colors.GREY_600
            )
        ], spacing=5)

    async def _update_settings_from_ui(self):
        self.plot_settings['show_title'] = self.show_title_checkbox.value
        self.plot_settings['show_legend'] = self.show_legend_checkbox.value
        self.plot_settings['show_protein_sequences'] = self.show_protein_sequences_cb.value
        self.plot_settings['header_fields'] = [
            key for key, checkbox in self._header_field_checkboxes.items() if checkbox.value
        ]

    async def generate_plot(self, entity_id: str) -> go.Figure:
        """Generate ion coverage plot for a spectrum."""
        spectrum_id = int(entity_id)
        show_protein_sequences = self.plot_settings.get('show_protein_sequences', False)
        header_fields = self.plot_settings.get('header_fields', DEFAULT_HEADER_FIELDS)

        plot_data = await self.project.get_spectrum_plot_data(
            spectrum_id,
            get_matched=show_protein_sequences,
            header_fields=header_fields,
        )

        logger.debug(f"plot_data: {plot_data}")

        params = self.ion_settings_section.get_ion_match_parameters()

        sequences = plot_data['sequences']
        headers = plot_data['headers']

        if len(headers) > 1:
            self.height_multiplier = 0.65 * len(sequences)
        else:
            self.height_multiplier = 1.0

        fig = make_full_spectrum_plot(
            params=params,
            mz=plot_data['mz'],
            intensity=plot_data['intensity'],
            charges=plot_data['charges'],
            sequences=sequences,
            headers=headers,
            spectrum_info=plot_data['spectrum_info']
        )

        fig.update_layout(
            template='plotly_white',
            showlegend=False #self.plot_settings.get('show_legend', True)

        )



        if self.plot_settings.get('show_title', True):
            fig.update_layout(
                title=f"Fragments (scans={plot_data['spectrum_info']['scans']}, pepmass={plot_data['spectrum_info']['pepmass']}, rt={plot_data['spectrum_info']['rt']})",
            )
        else:
            fig.update_layout(
                title=None
            )

        return fig
