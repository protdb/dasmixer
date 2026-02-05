"""Main Reports Tab."""

import flet as ft

from api.project.project import Project
from api.reporting.registry import registry
from .shared_state import ReportsTabState
from .settings_section import SettingsSection
from .report_item import ReportItem


class ReportsTab(ft.Container):
    """
    Reports tab.
    
    Contains:
    - Global settings section
    - List of all available reports
    """
    
    def __init__(self, project: Project):
        super().__init__()
        self.project = project
        self.expand = True
        self.padding = 0
        
        # State
        self.state = ReportsTabState()
        print('initializing reports tab')
        # Sections
        self.settings_section = SettingsSection(self.project, self.state, self)
        print('settings initialized')
        # Reports
        self.report_items: list[ReportItem] = []
        self._create_report_items()
        print('reports items initialized')
        
        # Build UI
        self.content = self._build_content()
    
    def _create_report_items(self):
        """Create components for all registered reports."""
        all_reports = registry.get_all()
        
        for report_name, report_class in all_reports.items():
            item = ReportItem(report_class, self.project, self.state)
            self.report_items.append(item)
            # Add to selected by default
            self.state.selected_reports.add(report_name)
    
    def _build_content(self) -> ft.Control:
        """Build tab content."""
        return ft.Column([
            # Settings
            self.settings_section,
            
            ft.Container(height=20),
            
            # Reports list header
            ft.Text("Available Reports", size=24, weight=ft.FontWeight.BOLD),
            
            ft.Divider(),
            
            # Reports list
            ft.Column(
                self.report_items,
                scroll=ft.ScrollMode.AUTO,
                expand=True
            )
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
        spacing=10
        )
    
    def did_mount(self):
        """Load data when mounted."""
        if self.page:
            self.page.run_task(self._load_initial_data)
    
    async def _load_initial_data(self):
        """Load initial data."""
        try:
            # Load settings
            await self.settings_section.load_settings()
            
            # Load data for each report
            for item in self.report_items:
                await item.load_data()
            
        except Exception as ex:
            print(f"Error loading reports tab data: {ex}")
            import traceback
            traceback.print_exc()
    
    async def generate_selected_reports(self):
        """Generate all selected reports."""
        selected = [
            item for item in self.report_items
            if item.report_class.name in self.state.selected_reports
        ]
        
        if not selected:
            return
        
        # TODO: Show progress
        for item in selected:
            try:
                # Simulate Generate button click
                await item._on_generate(None)
            except Exception as ex:
                print(f"Failed to generate {item.report_class.name}: {ex}")
    
    async def export_selected_reports(self):
        """Export all selected reports."""
        # Select folder using new async API
        try:
            folder_path = await ft.FilePicker().get_directory_path(
                dialog_title="Select Export Folder for All Reports"
            )
            
            if folder_path:
                await self._export_all_to_folder(folder_path)
        except Exception as ex:
            print(f"Failed to select folder: {ex}")
            import traceback
            traceback.print_exc()
    
    async def _export_all_to_folder(self, folder_path: str):
        """
        Export all selected reports to folder.
        
        TODO: Implement combined export (one Word, one Excel)
        """
        # Stub - export each separately for now
        selected = [
            item for item in self.report_items
            if item.report_class.name in self.state.selected_reports
        ]
        
        for item in selected:
            if item.current_report_id:
                try:
                    await item._export_to_folder(folder_path)
                except Exception as ex:
                    print(f"Failed to export {item.report_class.name}: {ex}")
