"""Search and view identifications section."""

import flet as ft
import pandas as pd

from dasmixer.api.calculations.spectra.plot_flow import make_full_spectrum_plot
from dasmixer.api.calculations.spectra.ion_match import IonMatchParameters
from dasmixer.gui.components.plotly_viewer import PlotlyViewer
from .base_section import BaseSection
from dasmixer.utils import logger


class SearchSection(BaseSection):
    """
    Search identifications and view spectrum plots.
    
    NEW: Uses get_joined_peptide_data() for filtering
    NEW: Uses PlotlyViewer with make_full_spectrum_plot() for visualization
    """
    
    def _build_content(self) -> ft.Control:
        """Build search section UI."""
        # Search filters
        self.search_sample_dropdown = ft.Dropdown(
            label="Sample",
            options=[ft.DropdownOption(key="all", text="All Samples")],
            value="all",
            width=200
        )
        
        self.search_tool_dropdown = ft.Dropdown(
            label="Tool",
            options=[ft.DropdownOption(key="all", text="All Tools")],
            value="all",
            width=200
        )
        
        self.search_by_dropdown = ft.Dropdown(
            label="Search by",
            options=[
                ft.DropdownOption(key="seq_no", text="Sequence Number"),
                ft.DropdownOption(key="scans", text="Scans"),
                ft.DropdownOption(key="sequence", text="Sequence"),
                ft.DropdownOption(key="canonical_sequence", text="Canonical Sequence")
            ],
            value="seq_no",
            width=200
        )
        
        self.search_value_field = ft.TextField(
            label="Search value",
            hint_text="Enter value...",
            expand=True,
            on_submit=lambda e: self.page.run_task(self.search_identifications, e)
        )
        
        self.search_btn = ft.ElevatedButton(
            content=ft.Text("Search"),
            icon=ft.Icons.SEARCH,
            on_click=lambda e: self.page.run_task(self.search_identifications, e)
        )
        
        # Results table
        self.results_container = ft.Container(
            content=ft.Column([
                ft.Text("No search yet", italic=True, color=ft.Colors.GREY_600)
            ]),
            padding=10,
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=5,
            height=300
        )
        
        # Plot container
        self.plot_container = ft.Container(
            content=ft.Column([
                ft.Text("Select identification to view", italic=True, color=ft.Colors.GREY_600)
            ]),
            padding=10,
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=5,
            height=600
        )
        
        return ft.Column([
            ft.Text("Search and View Identifications", size=18, weight=ft.FontWeight.BOLD),
            ft.Row([self.search_sample_dropdown, self.search_tool_dropdown], spacing=10),
            ft.Row([self.search_by_dropdown, self.search_value_field, self.search_btn], spacing=10),
            ft.Container(height=10),
            ft.Text("Results:", weight=ft.FontWeight.BOLD),
            self.results_container,
            ft.Container(height=10),
            ft.Text("Ion Match Viewer:", weight=ft.FontWeight.BOLD),
            self.plot_container
        ], spacing=10)
    
    async def load_data(self):
        """Load initial data for search filters."""
        await self.refresh_filters()
    
    async def refresh_filters(self):
        """Refresh sample and tool dropdown options."""
        try:
            samples = await self.project.get_samples()
            tools = await self.project.get_tools()
            
            self.search_sample_dropdown.options = [
                ft.DropdownOption(key="all", text="All Samples")
            ] + [
                ft.DropdownOption(key=str(s.id), text=s.name)
                for s in samples
            ]
            
            self.search_tool_dropdown.options = [
                ft.DropdownOption(key="all", text="All Tools")
            ] + [
                ft.DropdownOption(key=str(t.id), text=t.name)
                for t in tools
            ]
            
            self.search_sample_dropdown.update()
            self.search_tool_dropdown.update()
            
            self.state.needs_filter_refresh = False
            
        except Exception as ex:
            logger.exception("Error refreshing filters")
    
    async def search_identifications(self, e):
        """
        Search identifications using new get_joined_peptide_data() method.
        
        NEW: Uses Project.get_joined_peptide_data() instead of manual SQL
        """
        try:
            # Build filter parameters
            filter_params = {}
            
            # Sample filter
            if self.search_sample_dropdown.value != "all":
                filter_params['sample_id'] = int(self.search_sample_dropdown.value)
            
            # Tool filter
            if self.search_tool_dropdown.value != "all":
                filter_params['tool_id'] = int(self.search_tool_dropdown.value)
            
            # Search value filter
            search_by = self.search_by_dropdown.value
            search_value = self.search_value_field.value
            
            if search_value:
                if search_by == "seq_no":
                    filter_params['seq_no'] = int(search_value)
                elif search_by == "scans":
                    filter_params['scans'] = int(search_value)
                elif search_by == "sequence":
                    filter_params['sequence'] = search_value
                elif search_by == "canonical_sequence":
                    filter_params['canonical_sequence'] = search_value
            
            # NEW: Use get_joined_peptide_data()
            results_df = await self.project.get_joined_peptide_data(**filter_params)
            
            # Limit results for UI performance
            if len(results_df) > 100:
                results_df = results_df.head(100)
            
            # Update results table
            self._display_results(results_df)
            
            # Auto-select first result
            if len(results_df) > 0:
                first_row = results_df.iloc[0].to_dict()
                await self.view_identification(None, first_row)
            
        except Exception as ex:
            logger.exception("Error in search")
            self.show_error(f"Error: {str(ex)}")
    
    def _display_results(self, results_df: pd.DataFrame):
        """Display search results in table."""
        if len(results_df) == 0:
            self.results_container.content = ft.Column([
                ft.Text("No results", italic=True, color=ft.Colors.GREY_600)
            ])
            self.results_container.update()
            return
        
        # Build table rows
        rows = []
        for idx, row in results_df.iterrows():
            pref_icon = ft.Icon(
                ft.Icons.STAR,
                color=ft.Colors.AMBER,
                size=16
            ) if row.get('is_preferred') else ft.Container(width=16)
            
            seq_display = str(row.get('sequence', ''))[:20]
            if len(str(row.get('sequence', ''))) > 20:
                seq_display += "..."
            
            rows.append(
                ft.Container(
                    content=ft.Row([
                        ft.Container(ft.Text(str(row.get('seq_no', '')), size=12), width=60),
                        ft.Container(ft.Text(str(row.get('sample', '')), size=12), width=100),
                        ft.Container(ft.Text(str(row.get('tool', '')), size=12), width=120),
                        ft.Container(ft.Text(seq_display, size=12), width=200),
                        ft.Container(
                            ft.Text(
                                f"{row['score']:.2f}" if pd.notna(row.get('score')) else "N/A",
                                size=12
                            ),
                            width=60
                        ),
                        ft.Container(
                            ft.Text(
                                f"{row['ppm']:.2f}" if pd.notna(row.get('ppm')) else "N/A",
                                size=12
                            ),
                            width=60
                        ),
                        pref_icon,
                        ft.IconButton(
                            icon=ft.Icons.VISIBILITY,
                            tooltip="View spectrum",
                            icon_size=16,
                            on_click=lambda e, r=row.to_dict(): self.page.run_task(
                                self.view_identification, e, r
                            )
                        )
                    ], spacing=5),
                    padding=5,
                    border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.GREY_200))
                )
            )
        
        # Table header
        header = ft.Container(
            content=ft.Row([
                ft.Container(ft.Text("Seq#", weight=ft.FontWeight.BOLD, size=12), width=60),
                ft.Container(ft.Text("Sample", weight=ft.FontWeight.BOLD, size=12), width=100),
                ft.Container(ft.Text("Tool", weight=ft.FontWeight.BOLD, size=12), width=120),
                ft.Container(ft.Text("Sequence", weight=ft.FontWeight.BOLD, size=12), width=200),
                ft.Container(ft.Text("Score", weight=ft.FontWeight.BOLD, size=12), width=60),
                ft.Container(ft.Text("PPM", weight=ft.FontWeight.BOLD, size=12), width=60),
                ft.Container(ft.Text("Pref", weight=ft.FontWeight.BOLD, size=12), width=40),
                ft.Container(ft.Text("View", weight=ft.FontWeight.BOLD, size=12), width=40)
            ], spacing=5),
            padding=5,
            bgcolor=ft.Colors.GREY_100,
            border=ft.border.only(bottom=ft.BorderSide(2, ft.Colors.GREY_400))
        )
        
        # Update container
        self.results_container.content = ft.Column([
            ft.Text(f"Results ({len(results_df)}):", weight=ft.FontWeight.BOLD),
            ft.Column(
                [header] + rows,
                spacing=0,
                scroll=ft.ScrollMode.AUTO,
                height=250
            )
        ], spacing=5)
        
        self.results_container.update()
    
    async def view_identification(self, e, ident_row: dict):
        """
        View identification with spectrum plot.
        
        NEW: Uses get_spectrum_plot_data() and PlotlyViewer
        """
        try:
            # Get spectrum ID
            spectrum_id = ident_row.get('spectre_id')
            if not spectrum_id:
                self.show_error("Spectrum ID not found")
                return
            
            # NEW: Get plot data using new method
            plot_data = await self.project.get_spectrum_plot_data(spectrum_id)
            
            # Get ion match parameters from ion_settings section
            ion_settings_section = None
            if hasattr(self, 'page') and hasattr(self.page, 'peptides_tab'):
                ion_settings_section = self.page.peptides_tab.sections.get('ion_settings')
            
            if ion_settings_section:
                params = ion_settings_section.get_ion_match_parameters()
            else:
                # Fallback to default params
                params = IonMatchParameters(
                    ions=self.state.ion_types,
                    tolerance=self.state.ion_ppm_threshold,
                    mode='largest',
                    water_loss=self.state.water_loss,
                    ammonia_loss=self.state.nh3_loss
                )
            
            # NEW: Create plot using make_full_spectrum_plot
            fig = make_full_spectrum_plot(
                params=params,
                **plot_data  # Unpack: mz, intensity, charges, sequences, headers
            )
            
            # NEW: Display with PlotlyViewer
            viewer = PlotlyViewer(
                figure=fig,
                width=1000,
                height=600,
                title=f"Spectrum {plot_data['spectrum_info']['seq_no']}",
                show_interactive_button=True
            )
            
            self.plot_container.content = viewer
            self.plot_container.update()
            
            # Update state
            self.state.selected_spectrum_id = spectrum_id
            
        except Exception as ex:
            logger.exception("Error viewing identification")
            
            self.plot_container.content = ft.Column([
                ft.Text("Error loading spectrum", color=ft.Colors.RED_600, weight=ft.FontWeight.BOLD),
                ft.Text(str(ex), size=11, color=ft.Colors.RED_400)
            ])
            self.plot_container.update()
