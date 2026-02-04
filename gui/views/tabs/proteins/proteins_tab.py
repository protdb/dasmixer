"""Main Proteins Tab - composition of sections."""

import flet as ft

from api.project.project import Project
from .shared_state import ProteinsTabState
from .detection_section import DetectionSection
from .lfq_section import LFQSection
from .table_section import TableSection


class ProteinsTab(ft.Container):
    """
    Proteins tab - protein identification and quantification management.
    
    Composed of multiple sections:
    - DetectionSection: protein identification calculation
    - LFQSection: label-free quantification
    - TableSection: results display
    
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
        # Table section
        sections['table'] = TableSection(self.project, self.state, self)
        print("table...")
        return sections
    
    def _build_content(self) -> ft.Control:
        print('building protein tab content')
        """Build tab layout."""
        return ft.Column([
            # Detection
            self.sections['detection'],
            ft.Container(height=10),
            
            # LFQ
            self.sections['lfq'],
            ft.Container(height=10),
            
            # Table
            self.sections['table']
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
        """Load all initial data for sections."""
        print("Loading proteins tab initial data...")
        try:
            # Load data for each section that has load_data method
            for section_name, section in self.sections.items():
                print(f"Loading data for {section_name}...")
                if hasattr(section, 'load_data'):
                    await section.load_data()
            
            # Update counts in shared state
            self.state.protein_identification_count = await self.project.get_protein_identification_count()
            self.state.protein_quantification_count = await self.project.get_protein_quantification_count()
            
            print(f"Proteins tab initial data loaded successfully. "
                  f"IDs: {self.state.protein_identification_count}, "
                  f"Quant: {self.state.protein_quantification_count}")
            
        except Exception as ex:
            print(f"Error loading initial data: {ex}")
            import traceback
            traceback.print_exc()
    
    async def refresh_all(self):
        """Refresh all sections."""
        for section in self.sections.values():
            if hasattr(section, 'load_data'):
                await section.load_data()
