"""Main Samples Tab - composition of sections."""

import flet as ft
from dasmixer.api.project.project import Project
from .shared_state import SamplesTabState
from .groups_section import GroupsSection
from .tools_section import ToolsSection
from .import_section import ImportSection
from .samples_section import SamplesSection
from .import_handlers import ImportHandlers
from .dialogs.import_mode_dialog import ImportModeDialog
from .dialogs.import_pattern_dialog import ImportPatternDialog
from .dialogs.import_single_dialog import ImportSingleDialog


class SamplesTab(ft.Container):
    """
    Samples tab for managing:
    - Comparison groups (subsets)
    - Samples and their group assignments
    - Tools (identification methods)
    - Data import (spectra and identifications)
    
    Composed of multiple sections:
    - GroupsSection: manage comparison groups
    - ImportSection: import spectra files
    - ToolsSection: manage identification tools
    - SamplesSection: view and edit samples
    """
    
    def __init__(self, project: Project):
        super().__init__()
        print("SamplesTab init...")
        self.project = project
        self.expand = True
        self.padding = 0
        
        # Create shared state
        self.state = SamplesTabState()
        
        # Create sections (order matters for dependencies)
        self.sections = self._create_sections()
        
        # Create import handlers
        self.import_handlers = None  # Will be initialized in did_mount
        
        # Build content
        self.content = self._build_content()
    
    def _create_sections(self) -> dict:
        """
        Create all tab sections.
        
        Returns:
            dict mapping section name to section instance
        """
        sections = {}
        print("SamplesTab create sections...")
        
        # Groups section
        sections['groups'] = GroupsSection(self.project, self.state, self)
        print("groups...")
        
        # Import section
        sections['import'] = ImportSection(self.project, self.state, self)
        print("import...")
        
        # Tools section
        sections['tools'] = ToolsSection(self.project, self.state, self)
        print("tools...")
        
        # Samples section
        sections['samples'] = SamplesSection(self.project, self.state, self)
        print("samples...")
        
        return sections
    
    def _build_content(self) -> ft.Control:
        """Build tab layout."""
        print('building samples tab content')
        return ft.Column([
            # Groups
            self.sections['groups'],
            ft.Container(height=10),
            
            # Import
            self.sections['import'],
            ft.Container(height=10),
            
            # Tools
            self.sections['tools'],
            ft.Container(height=10),
            
            # Samples
            self.sections['samples']
        ],
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        expand=True
        )
    
    def did_mount(self):
        """Load initial data when tab is mounted."""
        print("SamplesTab did_mount called")
        
        # Initialize import handlers
        self.import_handlers = ImportHandlers(
            self.project,
            self.page,
            on_complete_callback=self._on_import_complete
        )
        
        # Store reference to self in page for sections to access
        if self.page:
            self.page.samples_tab = self
        
        self.page.run_task(self._load_initial_data)
    
    async def _load_initial_data(self):
        """Load all initial data for sections."""
        print("Loading samples tab initial data...")
        try:
            # Load data for each section that has load_data method
            for section_name, section in self.sections.items():
                print(f"Loading data for {section_name}...")
                if hasattr(section, 'load_data'):
                    await section.load_data()
            
            print("Samples tab initial data loaded successfully.")
            
        except Exception as ex:
            print(f"Error loading initial data: {ex}")
            import traceback
            traceback.print_exc()
    
    async def _on_import_complete(self):
        """Callback after import completes."""
        # Refresh all sections
        await self.refresh_all()
    
    async def refresh_all(self):
        """Refresh all sections."""
        for section in self.sections.values():
            if hasattr(section, 'load_data'):
                await section.load_data()
    
    def show_import_spectra(self):
        """Show import spectra dialog chain."""
        self.page.run_task(self._show_import_spectra_dialog)
    
    async def _show_import_spectra_dialog(self):
        """Show import mode selection for spectra."""
        dialog = ImportModeDialog(
            self.project,
            self.page,
            "spectra",
            on_single_files_callback=self._on_import_spectra_single,
            on_pattern_callback=self._on_import_spectra_pattern
        )
        await dialog.show()
    
    async def _on_import_spectra_single(self):
        """Handle single file import for spectra."""
        dialog = ImportSingleDialog(
            self.project,
            self.page,
            "spectra",
            on_import_callback=self.import_handlers.import_spectra_files
        )
        await dialog.show()
    
    async def _on_import_spectra_pattern(self):
        """Handle pattern import for spectra."""
        dialog = ImportPatternDialog(
            self.project,
            self.page,
            "spectra",
            on_import_callback=self.import_handlers.import_spectra_files
        )
        await dialog.show()
    
    def show_import_identifications(self, tool_id: int):
        """
        Show import identifications dialog chain.
        
        Args:
            tool_id: Tool ID to use for identifications
        """
        self.page.run_task(self._show_import_identifications_dialog, tool_id)
    
    async def _show_import_identifications_dialog(self, tool_id: int):
        """Show import mode selection for identifications."""
        dialog = ImportModeDialog(
            self.project,
            self.page,
            "identifications",
            tool_id=tool_id,
            on_single_files_callback=lambda: self._on_import_identifications_single(tool_id),
            on_pattern_callback=lambda: self._on_import_identifications_pattern(tool_id)
        )
        await dialog.show()
    
    async def _on_import_identifications_single(self, tool_id: int):
        """Handle single file import for identifications."""
        dialog = ImportSingleDialog(
            self.project,
            self.page,
            "identifications",
            tool_id=tool_id,
            on_import_callback=self.import_handlers.import_identification_files
        )
        await dialog.show()
    
    async def _on_import_identifications_pattern(self, tool_id: int):
        """Handle pattern import for identifications."""
        dialog = ImportPatternDialog(
            self.project,
            self.page,
            "identifications",
            tool_id=tool_id,
            on_import_callback=self.import_handlers.import_identification_files
        )
        await dialog.show()
