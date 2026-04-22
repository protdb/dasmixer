"""Main Proteins Tab - composition of sections."""

import flet as ft

from dasmixer.api.project.project import Project
from .shared_state import ProteinsTabState
from .detection_section import DetectionSection
from .lfq_section import LFQSection
from .protein_identifications_table_view import ProteinIdentificationsTableView
from .protein_statistics_table_view import ProteinStatisticsTableView
from .protein_concentration_plot_view import ProteinConcentrationPlotView


class ProteinsTab(ft.Container):
    """
    Proteins tab - protein identification and quantification management.
    
    Composed of multiple sections:
    - DetectionSection: protein identification calculation
    - LFQSection: label-free quantification
    - Table & Plot section: results display with mode switching
    
    Sections share state via ProteinsTabState object.
    """
    
    def __init__(self, project: Project):
        super().__init__()
        print("ProteinsTab init...")
        self.project = project
        self.expand = True
        self.padding = 0
        
        # Create shared state
        self.state = ProteinsTabState()
        
        # Create sections (order matters for dependencies)
        self.sections = self._create_sections()
        
        # Build content
        self.content = self._build_content()
    
    def _create_sections(self) -> dict:
        """
        Create all tab sections.
        
        Returns:
            dict mapping section name to section instance
        """
        sections = {}
        print("ProteinsTab create sections...")
        
        # Detection section
        sections['detection'] = DetectionSection(self.project, self.state, self)
        print("detection...")
        
        # LFQ section
        sections['lfq'] = LFQSection(self.project, self.state, self)
        print("lfq...")
        
        # Table and Plot section (replaces TableSection)
        sections['table_and_plot'] = self._create_table_and_plot_section()
        print("table_and_plot...")
        
        return sections
    
    def _create_table_and_plot_section(self) -> ft.Container:
        """Create table and plot section with mode switching."""
        # Create both table views
        self.identifications_table = ProteinIdentificationsTableView(self.project)
        self.statistics_table = ProteinStatisticsTableView(self.project)
        
        # Create plot view
        self.protein_plot = ProteinConcentrationPlotView(self.project)
        
        # Connect plot callbacks
        self.identifications_table.plot_callback = self.protein_plot.on_plot_requested
        self.statistics_table.plot_callback = self.protein_plot.on_plot_requested
        
        # Mode selector
        self.table_mode_selector = ft.SegmentedButton(
            segments=[
                ft.Segment(
                    value="identifications",
                    label=ft.Text("Identifications"),
                    icon=ft.Icon(ft.Icons.LIST)
                ),
                ft.Segment(
                    value="statistics",
                    label=ft.Text("Statistics"),
                    icon=ft.Icon(ft.Icons.ANALYTICS)
                )
            ],
            selected=["identifications"],  # FIXED: was set, now list
            on_change=self._on_table_mode_change
        )
        
        # Container for active table
        self.active_table_container = ft.Container(
            content=self.identifications_table,
            expand=True
        )
        
        # Layout
        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("Protein Results", size=18, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    self.table_mode_selector
                ]),
                ft.Container(height=10),
                
                self.active_table_container,
                
                ft.Container(height=20),
                ft.Divider(height=2, color=ft.Colors.GREY_400),
                ft.Container(height=20),
                
                self.protein_plot
            ], spacing=0, expand=True, scroll=ft.ScrollMode.AUTO),
            expand=True,
            padding=10
        )
    
    def _on_table_mode_change(self, e):
        """Handle table mode switching."""
        selected_mode = list(e.control.selected)[0]
        
        if selected_mode == "identifications":
            self.active_table_container.content = self.identifications_table
        else:
            self.active_table_container.content = self.statistics_table
        
        if self.page:
            self.page.update()
            
            # Load data for new mode
            self.page.run_task(self.active_table_container.content.load_data)
    
    def _build_content(self) -> ft.Control:
        """Build tab layout."""
        return ft.Column([
            # Detection
            self.sections['detection'],
            ft.Container(height=10),
            
            # LFQ
            self.sections['lfq'],
            ft.Container(height=10),
            
            # Table and Plot
            self.sections['table_and_plot']
        ],
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        expand=True
        )
    
    def did_mount(self):
        """Load initial data when tab is mounted."""
        print("ProteinsTab did_mount called")
        
        # Store reference to self in page for sections to access
        if self.page:
            self.page.proteins_tab = self
        
        self.page.run_task(self._load_initial_data)
    
    async def _load_initial_data(self):
        """Load all initial data for sections in parallel."""
        import asyncio
        print("Loading proteins tab initial data...")
        try:
            tasks = []
            for section_name, section in self.sections.items():
                if section_name == 'table_and_plot':
                    tasks.append(self.identifications_table.load_data())
                    tasks.append(self.protein_plot.load_data())
                elif hasattr(section, 'load_data'):
                    tasks.append(section.load_data())

            # Counts run in parallel with section loads
            tasks.append(self._update_counts())

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for i, r in enumerate(results):
                    if isinstance(r, Exception):
                        print(f"[ProteinsTab] load_data task {i} failed: {r}")

            print(f"Proteins tab initial data loaded. "
                  f"IDs: {self.state.protein_identification_count}, "
                  f"Quant: {self.state.protein_quantification_count}")

        except Exception as ex:
            print(f"Error loading initial data: {ex}")
            import traceback
            traceback.print_exc()

    async def _update_counts(self):
        self.state.protein_identification_count = await self.project.get_protein_identification_count()
        self.state.protein_quantification_count = await self.project.get_protein_quantification_count()
    
    async def refresh_all(self):
        """Refresh all sections."""
        for section in self.sections.values():
            if hasattr(section, 'load_data'):
                await section.load_data()
