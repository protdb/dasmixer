"""Individual report item component."""

import flet as ft
from datetime import datetime
from pathlib import Path

from api.project.project import Project
from api.reporting.base import BaseReport
from api.reporting.viewer import ReportViewer
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
        self.report_class = report_class
        self.project = project
        self.state = state
        
        # Controls
        self.include_checkbox = ft.Checkbox(
            label="Generate with all",
            value=True,
            on_change=self._on_include_changed
        )
        
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
        
        # Saved reports dropdown
        self.saved_reports_dropdown = ft.Dropdown(
            label="Saved Reports",
            hint_text="Select a saved report to view",
            width=300,
            on_change=self._on_saved_report_selected
        )
        
        # Buttons
        self.generate_btn = ft.ElevatedButton(
            "Generate",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._on_generate
        )
        
        self.view_btn = ft.ElevatedButton(
            "View",
            icon=ft.Icons.VISIBILITY,
            on_click=self._on_view,
            disabled=True
        )
        
        self.export_btn = ft.ElevatedButton(
            "Export",
            icon=ft.Icons.FILE_DOWNLOAD,
            on_click=self._on_export,
            disabled=True
        )
        
        # Current selected report_id
        self.current_report_id: int | None = None
        
        # Build UI
        self.content = self._build_content()
        self.padding = 15
        self.border = ft.border.all(1, ft.Colors.BLUE_200)
        self.border_radius = 8
        self.margin = ft.margin.only(bottom=10)
    
    def _build_content(self) -> ft.Control:
        """Build content."""
        return ft.Column([
            # Header
            ft.Row([
                ft.Icon(name=self.report_class.icon, size=30),
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
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            
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
        self._show_loading("Generating report...")
        
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
            
            self._close_loading()
            self._show_success("Report generated successfully")
            
            if self.page:
                self.update()
            
        except Exception as ex:
            self._close_loading()
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
            
            # Get HTML
            context = report.get_context()
            
            # Render via jinja2
            from jinja2 import Environment, FileSystemLoader
            from pathlib import Path
            
            template_dir = Path(__file__).parent.parent.parent.parent / 'api' / 'reporting' / 'templates'
            env = Environment(loader=FileSystemLoader(str(template_dir)))
            template = env.get_template('report.html.j2')
            html = template.render(**context)
            
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
        
        # Select folder
        def on_folder_selected(e: ft.FilePickerResultEvent):
            if e.path:
                self.page.run_task(self._export_to_folder, e.path)
        
        folder_picker = ft.FilePicker(on_result=on_folder_selected)
        self.page.overlay.append(folder_picker)
        self.page.update()
        await folder_picker.get_directory_path(dialog_title="Select Export Folder")
    
    async def _export_to_folder(self, folder_path: str):
        """Export to selected folder."""
        try:
            # Load report
            report = await self.report_class.load_from_db(
                self.project,
                self.current_report_id
            )
            
            # Export
            await report.export(Path(folder_path))
            
            self._show_success(f"Report exported to {folder_path}")
            
        except Exception as ex:
            self._show_error(f"Export failed: {ex}")
            import traceback
            traceback.print_exc()
    
    def _show_loading(self, message: str):
        """Show loading dialog."""
        if self.page:
            self.page.dialog = ft.AlertDialog(
                modal=True,
                content=ft.Column([
                    ft.ProgressRing(),
                    ft.Text(message)
                ], tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            )
            self.page.dialog.open = True
            self.page.update()
    
    def _close_loading(self):
        """Close loading dialog."""
        if self.page and self.page.dialog:
            self.page.dialog.open = False
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
