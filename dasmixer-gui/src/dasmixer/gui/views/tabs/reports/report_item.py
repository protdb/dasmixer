"""Individual report item component."""

from datetime import datetime
from pathlib import Path

import flet as ft
from dasmixer.api.project.project import Project
from dasmixer.api.reporting.base import BaseReport
from dasmixer.gui.reporting.viewer import ReportViewer
from dasmixer.gui.utils import show_snack
from dasmixer.utils import logger

from .shared_state import ReportsTabState


class ReportItem(ft.Container):
    """
    Component for one report in the list.
    
    Contains:
    - Name and description
    - "Include in batch" checkbox
    - Parameters button (opens dialog) or TextArea fallback
    - Control buttons
    """
    
    def __init__(
        self,
        report_class: type[BaseReport],
        project: Project,
        state: ReportsTabState
    ):
        super().__init__()
        logger.debug('report items init...')
        self.report_class = report_class
        self.project = project
        self.state = state
        logger.debug(f'Report {report_class.__name__}.')
        
        # Include checkbox
        self.include_checkbox = ft.Checkbox(
            label="Generate with all",
            value=True,
            on_change=self._on_include_changed
        )
        logger.debug('checkbox Generate_all init...')

        # Form instance (for reports with ReportForm)
        self._form = None
        self._params_dialog: ft.AlertDialog | None = None

        # Decide UI mode
        self._has_form = report_class.parameters is not None

        # Name format field (on the card, not in the params dialog)
        self.name_template_field = ft.TextField(
            label="Name format",
            hint_text="{date} {time}",
            value=report_class.name_template if hasattr(report_class, 'name_template') else "{date} {time}",
            width=250,
            tooltip="Template: {date} = YYMMDD, {time} = HH:MM, plus any param field name",
        )

        # Always create params button
        self.params_btn = ft.ElevatedButton(
            content=ft.Text("Parameters"),
            icon=ft.Icons.SETTINGS,
            on_click=self._on_open_params,
        )
        
        # If no form, disable the button
        if not self._has_form:
            self.params_btn.disabled = True
            self.params_btn.tooltip = "This report has no configurable parameters"
        
        self.params_field: ft.TextField | None = None
        logger.debug('params widget init...')
        
        # Saved reports dropdown
        self.saved_reports_dropdown = ft.Dropdown(
            label="Saved Reports",
            hint_text="Select a saved report to view",
            width=300,
            options=[ft.DropdownOption('New', 'New report')],
            on_text_change=self._on_saved_report_selected
        )
        logger.debug('saved_reports_dropdown init...')
        
        # Buttons
        self.generate_btn = ft.ElevatedButton(
            content="Generate",
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._on_generate
        )
        logger.debug('generate_btn...')
        
        self.view_btn = ft.ElevatedButton(
            content="View",
            icon=ft.Icons.VISIBILITY,
            on_click=self._on_view,
            disabled=True
        )
        logger.debug('view_btn...')
        self.export_btn = ft.ElevatedButton(
            content="Export",
            icon=ft.Icons.FILE_DOWNLOAD,
            on_click=self._on_export,
            disabled=True
        )
        logger.debug('export_btn...')
        
        # Current selected report_id
        self.current_report_id: int | None = None
        
        # Build UI
        self.content = self._build_content()
        logger.debug('content built...')
        self.padding = 15
        self.border = ft.border.all(1, ft.Colors.BLUE_200)
        self.border_radius = 8
        self.margin = ft.margin.only(bottom=10)
    
    def _build_content(self) -> ft.Control:
        """Build content."""
        logger.debug('Building content...')

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

            # Parameters area - always show the button
            ft.Row([self.params_btn, self.name_template_field], spacing=10),
            # ft.Row([self.name_template_field], spacing=10),

            ft.Container(height=10),

            # Controls
            ft.Row([
                self.generate_btn,
                self.saved_reports_dropdown,
                self.view_btn,
                self.export_btn
            ], spacing=10)
        ])
        logger.debug('content inits...')
        return res

    # ------------------------------------------------------------------
    # Form helpers
    # ------------------------------------------------------------------

    async def _init_form(self) -> None:
        """Create and populate form instance from saved parameters."""
        if not self._has_form or self.report_class.parameters is None:
            return
        saved = await self.project.get_report_parameters(self.report_class.name)
        if saved:
            import json
            try:
                self._form = self.report_class.parameters.from_json_str(saved, self.project)
                # Also restore name_template from saved JSON
                data = json.loads(saved)
                if 'name_template' in data:
                    self.name_template_field.value = data['name_template']
            except Exception:
                self._form = self.report_class.parameters(self.project)
        else:
            self._form = self.report_class.parameters(self.project)
            self.name_template_field.value = (
                self.report_class.name_template
                if hasattr(self.report_class, 'name_template')
                else "{date} {time}"
            )

    async def _ensure_form_built(self) -> None:
        """Make sure form is initialised and built."""
        if self._form is None:
            await self._init_form()
        if self._form is not None and not self._form._built:
            await self._form.build()

    async def _on_open_params(self, e) -> None:
        """Open parameters dialog."""
        if not self.page:
            return
        await self._ensure_form_built()
        if self._form is None:
            return

        form_ref = self._form  # capture non-None reference

        def _close_dialog(_):
            if self._params_dialog is not None:
                self._params_dialog.open = False
            if self.page:
                self.page.update()

        async def _save_and_close(_):
            try:
                await self.project.save_report_parameters(
                    self.report_class.name,
                    form_ref.to_json()
                )
            except Exception as ex:
                logger.exception(f"Failed to save report parameters: {ex}")
            if self._params_dialog is not None:
                self._params_dialog.open = False
            if self.page:
                self.page.update()

        async def _save_generate_and_close(_):
            try:
                # Save name_template along with form values
                import json
                data = json.loads(form_ref.to_json())
                data['name_template'] = self.name_template_field.value
                await self.project.save_report_parameters(
                    self.report_class.name,
                    json.dumps(data)
                )
            except Exception as ex:
                logger.exception(f"Failed to save report parameters: {ex}")
            if self._params_dialog is not None:
                self._params_dialog.open = False
            if self.page:
                self.page.update()
            await self._on_generate(None)

        container = form_ref.get_container()
        
        # Calculate adaptive dialog height based on number of form fields
        # n_fields = len(form_ref._fields) if hasattr(form_ref, '_fields') else 0
        # if n_fields > 0:
        #     dialog_height = min(80 + n_fields * 80, 550)
        #     container.height = dialog_height
        # else:
        #     # Empty form or no fields
        #     container.height = 120
        
        # Set fixed width for consistency
        container.width = 460

        self._params_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(f"{self.report_class.name} — Parameters"),
            content=container,
            actions=[
                ft.TextButton("Cancel", on_click=_close_dialog),
                ft.ElevatedButton(content=ft.Text("OK"), on_click=_save_and_close),
                ft.ElevatedButton(content=ft.Text("Save and generate"), on_click=_save_generate_and_close),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.overlay.append(self._params_dialog)
        self._params_dialog.open = True
        self.page.update()

    def _get_params_from_form(self):
        """Get typed ReportParams dataclass from form values.

        Builds params via form.get_params(), then sets name_template from
        the card-level Name format field, overriding whatever default the
        dataclass carries.
        """
        if self._form is not None:
            params = self._form.get_params()
            if hasattr(params, 'name_template'):
                params.name_template = self.name_template_field.value or params.name_template
            return params
        return None

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    async def load_data(self):
        """Load data (parameters and saved reports list)."""
        if self._has_form:
            await self._init_form()
        # No need to load legacy parameters anymore
        
        # Load saved reports list
        await self._load_saved_reports()
        
        # Auto-select the most recent report if any exist
        if self.saved_reports_dropdown.options:
            first = self.saved_reports_dropdown.options[0]
            self.saved_reports_dropdown.value = first.key
            self.current_report_id = int(first.key)
            self.view_btn.disabled = False
            self.export_btn.disabled = False
        
        if self.page:
            self.update()
    
    async def _load_saved_reports(self):
        """Load saved reports list. Shows 'name' column when available, created_at otherwise."""
        reports = await self.project.get_generated_reports(self.report_class.name)
        
        options = []
        for report in reports:
            display = report.get('name')
            if not display:
                # Fallback to formatted created_at
                created_at = report['created_at']
                try:
                    dt = datetime.fromisoformat(created_at)
                    display = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    display = created_at
            
            options.append(
                ft.DropdownOption(
                    key=str(report['id']),
                    text=display
                )
            )
        
        # Keep the "New report" option at index 0 if it exists
        self.saved_reports_dropdown.options = options
    
    def _on_include_changed(self, e):
        """Handle checkbox change."""
        if self.include_checkbox.value:
            self.state.selected_reports.add(self.report_class.name)
        else:
            self.state.selected_reports.discard(self.report_class.name)
    
    async def _on_generate(self, e):
        """Generate report."""
        loading_dialog = self._show_loading("Generating report...")
        
        try:
            # Collect parameters
            if self._has_form:
                await self._ensure_form_built()
                params = self._get_params_from_form()
                # Also save current form state (including name_template)
                if self._form is not None:
                    import json
                    data = json.loads(self._form.to_json())
                    data['name_template'] = self.name_template_field.value
                    await self.project.save_report_parameters(
                        self.report_class.name,
                        json.dumps(data)
                    )
            else:
                # No form — instantiate default params from the report's params_class
                if hasattr(self.report_class, 'params_class') and self.report_class.params_class is not None:
                    params = self.report_class.params_class()
                    # Apply name_template from the card field
                    if hasattr(params, 'name_template'):
                        params.name_template = self.name_template_field.value or params.name_template
                else:
                    params = {}
            
            # Create report instance
            report = self.report_class(self.project)
            
            # Generate (returns report_id now)
            report_id = await report.generate(params)
            
            # Reload saved reports list
            await self._load_saved_reports()
            
            # Auto-select the newly generated report
            self.saved_reports_dropdown.value = str(report_id)
            self.current_report_id = report_id
            self.view_btn.disabled = False
            self.export_btn.disabled = False
            
            self._close_loading(loading_dialog)
            self._show_success("Report generated successfully")
            
            if self.page:
                self.update()
            
        except Exception as ex:
            self._close_loading(loading_dialog)
            self._show_error(f"Generation failed: {ex}")
            logger.exception(f"Generation failed: {ex}")
            import traceback
            traceback.print_exc()

    

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
            report = await self.report_class.load_from_db(
                self.project,
                self.current_report_id
            )
            html = report._render_html()
            ReportViewer.show_report(html, title=f"{self.report_class.name}")
            
        except Exception as ex:
            self._show_error(f"Failed to view report: {ex}")
            logger.exception(f"Failed to view report: {ex}")
            import traceback
            traceback.print_exc()
    
    async def _on_export(self, e):
        """Export report using the new ExportDialog."""
        if not self.current_report_id:
            return
        if not self.page:
            return

        from .export_dialog import ExportDialog

        async def do_export(save_path: str, formats: set[str], xlsx_mode: str) -> None:
            from dasmixer.gui.views.tabs.peptides.dialogs.progress_dialog import (
                ProgressDialog,
            )
            dialog = ProgressDialog(self.page, "Exporting Report")
            dialog.show()
            try:
                dialog.update_progress(None, "Loading report...", "")
                report = await self.report_class.load_from_db(
                    self.project,
                    self.current_report_id
                )
                dialog.update_progress(None, "Exporting files...", ", ".join(sorted(formats)))
                created_files = await report.export(
                    Path(save_path),
                    formats=formats,
                    xlsx_mode=xlsx_mode,
                )
                files_list = ", ".join([p.name for p in created_files.values()])
                dialog.complete(f"Done: {files_list}")
                import asyncio
                await asyncio.sleep(1)
                dialog.close()
            except Exception as ex:
                dialog.close()
                self._show_error(f"Export failed: {ex}")
                logger.exception(f"Export failed: {ex}")
                import traceback
                traceback.print_exc()

        export_dialog = ExportDialog(self.page, do_export)
        await export_dialog.show()

    async def _export_to_folder(self, folder_path: str):
        """Export this report to a given folder (used by batch export)."""
        if not self.current_report_id:
            return
        report = await self.report_class.load_from_db(self.project, self.current_report_id)
        await report.export(Path(folder_path), formats={'html', 'docx', 'xlsx'}, xlsx_mode='all')

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------

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
            show_snack(self.page, message, ft.Colors.RED_400)
            self.page.update()
    
    def _show_success(self, message: str):
        """Show success."""
        if self.page:
            show_snack(self.page, message, ft.Colors.GREEN_400)
            self.page.update()
