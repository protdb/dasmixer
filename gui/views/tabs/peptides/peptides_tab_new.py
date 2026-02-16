"""Main Peptides Tab - composition of sections."""

import flet as ft

from api.project.project import Project
from gui.components.base_table_and_plot_view import BaseTableAndPlotView
from .shared_state import PeptidesTabState
from .fasta_section import FastaSection
from .tool_settings_section import ToolSettingsSection
from .ion_settings_section import IonSettingsSection
from .actions_section import ActionsSection
from .matching_section import MatchingSection
from .peptide_ion_table_view import PeptideIonTableView
from .peptide_ion_plot_view import PeptideIonPlotView
from .ion_calculations import IonCalculations


class PeptidesTab(ft.Container):
    """
    Peptides tab - comprehensive peptide identification management.
    
    Composed of multiple sections, each responsible for specific functionality.
    Sections share state via PeptidesTabState object.
    """
    
    def __init__(self, project: Project):
        super().__init__()
        print("PeptidesTab init...")
        self.project = project
        self.expand = True
        self.padding = 0
        
        # Create shared state
        self.state = PeptidesTabState()
        
        # Create ion calculations service (singleton, no UI)
        self.ion_calculations = IonCalculations(self.project, self.state)
        
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
        sections = {'fasta': FastaSection(self.project, self.state),
                    'tool_settings': ToolSettingsSection(self.project, self.state),
                    'ion_settings': IonSettingsSection(self.project, self.state),
                    'matching': MatchingSection(self.project, self.state),
                    'actions': ActionsSection(self.project, self.state, self)}
        
        # FASTA section - protein library loading

        # Tool settings section

        # Ion settings section

        # Matching section

        # Actions section (needs reference to tab for accessing other sections)

        print('old sections created...')

        # Search section - REPLACED with BaseTableAndPlotView
        table_view = PeptideIonTableView(self.project)

        print('table view created...')

        plot_view = PeptideIonPlotView(self.project, ion_settings_section=sections['ion_settings'])
        
        sections['search'] = BaseTableAndPlotView(
            project=self.project,
            table_view=table_view,
            plot_view=plot_view,
            title="Search and View Identifications"
        )
        print('Sections created...')
        
        return sections
    
    def _build_content(self) -> ft.Control:
        """Build tab layout."""
        return ft.Column([
            # FASTA loading
            self.sections['fasta'],
            ft.Container(height=10),
            
            # Tool settings
            self.sections['tool_settings'],
            ft.Container(height=10),
            
            # Ion settings
            self.sections['ion_settings'],
            ft.Container(height=10),
            
            # Actions - NEW unified workflow
            self.sections['actions'],
            ft.Container(height=10),
            
            # Matching
            self.sections['matching'],
            ft.Container(height=10),
            
            # Search and view - NOW BaseTableAndPlotView
            self.sections['search']
        ],
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        expand=True
        )
    
    def did_mount(self):
        """Load initial data when tab is mounted."""
        print("PeptidesTab did_mount called")
        
        # Store reference to self in page for sections to access
        if self.page:
            self.page.peptides_tab = self
        
        self.page.run_task(self._load_initial_data)
    
    async def _load_initial_data(self):
        """Load all initial data for sections."""
        print("Loading peptides tab initial data...")
        try:
            # Load data for each section that has load_data method
            for section_name, section in self.sections.items():
                print(f"Loading data for {section_name}...")
                if hasattr(section, 'load_data'):
                    await section.load_data()
            
            # Update protein count in shared state
            self.state.protein_count = await self.project.get_protein_count()
            
            print("Peptides tab initial data loaded successfully")
            
        except Exception as ex:
            print(f"Error loading initial data: {ex}")
            import traceback
            traceback.print_exc()
    
    async def refresh_all(self):
        """Refresh all sections."""
        for section in self.sections.values():
            if hasattr(section, 'load_data'):
                await section.load_data()
