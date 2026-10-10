"""Main Reports Tab."""

from pathlib import Path

import flet as ft
from dasmixer.api.project.project import Project
from dasmixer.api.reporting.registry import registry

from dasmixer.utils import logger

from .report_item import ReportItem
from .settings_section import SettingsSection
from .shared_state import ReportsTabState


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
        logger.debug('initializing reports tab')
        # Sections
        self.settings_section = SettingsSection(self.project, self.state, self)
        logger.debug('settings initialized')
        # Reports
        self.report_items: list[ReportItem] = []
        self._create_report_items()
        logger.debug('reports items initialized')
        
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
            logger.exception(f"Error loading reports tab data: {ex}")
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
                logger.exception(f"Failed to generate {item.report_class.name}: {ex}")
    
    async def export_selected_reports(self):
        """Export all selected reports using the shared ExportDialog."""
        from .export_dialog import ExportDialog
        
        async def do_export(save_path: str, formats: set[str], xlsx_mode: str) -> None:
            await self._export_all_to_folder(save_path, formats, xlsx_mode)
        
        export_dialog = ExportDialog(self.page, do_export)
        await export_dialog.show()
    
    async def _export_all_to_folder(
        self, folder_path: str, formats: set[str] | None = None, xlsx_mode: str = 'all'
    ):
        from dasmixer.gui.views.tabs.peptides.dialogs.progress_dialog import (
            ProgressDialog,
        )
        
        if formats is None:
            formats = {'html', 'docx', 'xlsx'}
        
        selected = [
            item for item in self.report_items
            if item.report_class.name in self.state.selected_reports
        ]
        
        if not selected:
            return
        
        dialog = ProgressDialog(self.page, "Exporting Reports")
        dialog.show()
        
        total = len(selected)
        for i, item in enumerate(selected):
            if item.current_report_id:
                try:
                    dialog.update_progress(
                        i / total,
                        f"Exporting {item.report_class.name}...",
                        f"{i+1} / {total}"
                    )
                    report = await item.report_class.load_from_db(
                        self.project, item.current_report_id
                    )
                    await report.export(
                        Path(folder_path), formats=formats, xlsx_mode=xlsx_mode
                    )
                except Exception as ex:
                    logger.exception(f"Failed to export {item.report_class.name}: {ex}")
        
        dialog.complete(f"Exported {total} reports")
        import asyncio
        await asyncio.sleep(1)
        dialog.close()
