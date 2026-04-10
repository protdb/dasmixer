"""Individual report item component."""

import flet as ft
from datetime import datetime
from pathlib import Path

from dasmixer.api.project.project import Project
from dasmixer.api.reporting.base import BaseReport
from dasmixer.api.reporting.viewer import ReportViewer
from .shared_state import ReportsTabState


class ReportItem(ft.Container):
    """
    Component for one report in the list.
    
    Contains:
    - Name and description
    - "Include in batch" checkbox
    - Parameters field
    - Control buttons
    """
    
    def __init__(
        self,
        report_class: type[BaseReport],
        project: Project,
        state: ReportsTabState
    ):
        super().__init__()
        print('report items init...')
        self.report_class = report_class
        self.project = project
        self.state = state
        print(f'Report {report_class.__name__}.')
        
        # Controls
        self.include_checkbox = ft.Checkbox(
            label="Generate with all",
            value=True,
            on_change=self._on_include_changed
        )
        print('checkbox Generate_all init...')
        
        # Default parameters
        defaults = report_class.get_parameter_defaults()
        default_params_text = "\n".join([
            f"{key}={value}"
            for key, (_, value) in defaults.items()
        ])
        
        self.params_field = ft.TextField(
            label="Parameters",
            value=default_params_text,
            multiline=True,
            min_lines=3,
            max_lines=6,
            expand=True
        )
        print('params_field init...')
        
        # Saved reports dropdown
        self.saved_reports_dropdown = ft.Dropdown(
            label="Saved Reports",
            hint_text="Select a saved report to view",
            width=300,
            options=[ft.DropdownOption('New', 'New report')],
            on_text_change=self._on_saved_report_selected
        )
        print('saved_reports_dropdown init...')
        
        # Buttons
        self.generate_btn = ft.ElevatedButton(
            content="Generate",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._on_generate
        )
        print('generate_btn...')
        
        self.view_btn = ft.ElevatedButton(
            content="View",
            icon=ft.Icons.VISIBILITY,
            on_click=self._on_view,
            disabled=True
        )
        print('view_btn...')
        self.export_btn = ft.ElevatedButton(
            content="Export",
            icon=ft.Icons.FILE_DOWNLOAD,
            on_click=self._on_export,
            disabled=True
        )
        print('export_btn...')
        
        # Current selected report_id
        self.current_report_id: int | None = None
        
        # Build UI
        self.content = self._build_content()
        print('content built...')
        self.padding = 15
        self.border = ft.border.all(1, ft.Colors.BLUE_200)
        self.border_radius = 8
        self.margin = ft.margin.only(bottom=10)
    
    def _build_content(self) -> ft.Control:
        """Build content."""
        print('Building content...')
        res = ft.Column([
            # Header
            ft.Row([
                ft.Icon(self.report_class.icon, size=30),
                ft.Column([
                    ft.Text(
                        self.report_class.name,
                        size=18,
                        weight=ft.FontWeight.BOLD
                    ),
                    ft.Text(
                        self.report_class.description,
                        size=12,
                        color=ft.Colors.GREY_700
                    )
                ], spacing=0, expand=True),
                self.include_checkbox
            ]),
            
            ft.Divider(),

            # Parameters
            self.params_field,

            ft.Container(height=10),

            # Controls
            ft.Row([
                self.generate_btn,
                self.saved_reports_dropdown,
                self.view_btn,
                self.export_btn
            ], spacing=10)
        ])
        print('content inits...')
        return res
    
    async def load_data(self):
        """Load data (parameters and saved reports list)."""
        # Load saved parameters
        saved_params = await self.project.get_report_parameters(self.report_class.name)
        if saved_params:
            self.params_field.value = saved_params
        
        # Load saved reports list
        await self._load_saved_reports()
        
        if self.page:
            self.update()
    
    async def _load_saved_reports(self):
        """Load saved reports list."""
        reports = await self.project.get_generated_reports(self.report_class.name)
        
        options = []
        for report in reports:
            created_at = report['created_at']
            # Format date
            try:
                dt = datetime.fromisoformat(created_at)
                formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                formatted = created_at
            
            options.append(
                ft.DropdownOption(
                    key=str(report['id']),
                    text=formatted
                )
            )
        
        self.saved_reports_dropdown.options = options
    
    def _on_include_changed(self, e):
        """Handle checkbox change."""
        if self.include_checkbox.value:
            self.state.selected_reports.add(self.report_class.name)
        else:
            self.state.selected_reports.discard(self.report_class.name)
    
    async def _on_generate(self, e):
        """Generate report."""
        # Show loading dialog
        loading_dialog = self._show_loading("Generating report...")
        
        try:
            # Parse parameters
            params = self._parse_parameters()
            
            # Save parameters
            await self.project.save_report_parameters(
                self.report_class.name,
                self.params_field.value
            )
            
            # Create report instance
            report = self.report_class(self.project)
            
            # Generate
            await report.generate(params)
            
            # Reload saved reports list
            await self._load_saved_reports()
            
            self._close_loading(loading_dialog)
            self._show_success("Report generated successfully")
            
            if self.page:
                self.update()
            
        except Exception as ex:
            self._close_loading(loading_dialog)
            self._show_error(f"Generation failed: {ex}")
            import traceback
            traceback.print_exc()
    
    def _parse_parameters(self) -> dict:
        """
        Parse parameters from text field.
        
        Returns:
            dict: {param_name: value_as_string}
        """
        params = {}
        text = self.params_field.value or ""
        
        for line in text.split('\n'):
            line = line.strip()
            if '=' in line:
                key, value = line.split('=', 1)
                params[key.strip()] = value.strip()
        
        return params
    
    async def _on_saved_report_selected(self, e):
        """Saved report selected."""
        if self.saved_reports_dropdown.value:
            self.current_report_id = int(self.saved_reports_dropdown.value)
            self.view_btn.disabled = False
            self.export_btn.disabled = False
            if self.page:
                self.update()
    
    async def _on_view(self, e):
        """View report."""
        if not self.current_report_id:
            return
        
        try:
            # Load report from DB
            report = await self.report_class.load_from_db(
                self.project,
                self.current_report_id
            )
            
            # Render HTML
            html = report._render_html()
            
            # Show in pywebview
            ReportViewer.show_report(html, title=f"{self.report_class.name}")
            
        except Exception as ex:
            self._show_error(f"Failed to view report: {ex}")
            import traceback
            traceback.print_exc()
    
    async def _on_export(self, e):
        """Export report."""
        if not self.current_report_id:
            return
        
        # Show loading dialog first
        loading_dialog = self._show_loading("Exporting report...")
        
        try:
            # Use async FilePicker to get directory
            folder_path = await ft.FilePicker().get_directory_path(
                dialog_title="Select Export Folder"
            )
            
            if folder_path:
                # Load report
                report = await self.report_class.load_from_db(
                    self.project,
                    self.current_report_id
                )
                
                # Export
                created_files = await report.export(Path(folder_path))
                
                self._close_loading(loading_dialog)
                
                # Show success with file list
                files_list = "\n".join([f"- {path.name}" for path in created_files.values()])
                self._show_success(f"Report exported:\n{files_list}")
            else:
                self._close_loading(loading_dialog)
                
        except Exception as ex:
            self._close_loading(loading_dialog)
            self._show_error(f"Export failed: {ex}")
            import traceback
            traceback.print_exc()
    
    def _show_loading(self, message: str):
        """Show loading dialog."""
        if not self.page:
            return None
        
        loading_dialog = ft.AlertDialog(
            modal=True,
            content=ft.Column([
                ft.ProgressRing(),
                ft.Text(message)
            ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        )
        
        self.page.overlay.append(loading_dialog)
        loading_dialog.open = True
        self.page.update()
        
        return loading_dialog
    
    def _close_loading(self, dialog):
        """Close loading dialog."""
        if self.page and dialog:
            dialog.open = False
            self.page.update()
    
    def _show_error(self, message: str):
        """Show error."""
        if self.page:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    def _show_success(self, message: str):
        """Show success."""
        if self.page:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=ft.Colors.GREEN_400
            )
            self.page.snack_bar.open = True
            self.page.update()
