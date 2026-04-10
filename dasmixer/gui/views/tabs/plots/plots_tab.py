"""Plots tab - manage saved plots."""

import flet as ft
from pathlib import Path
from datetime import datetime
from typing import Optional
import base64
from jinja2 import Template

from dasmixer.api.project.project import Project
from dasmixer.gui.components.plotly_viewer import PlotlyViewer


class PlotItemCard(ft.Container):
    """Card displaying single saved plot info."""
    
    def __init__(
        self,
        plot_info: dict,
        on_view,
        on_delete,
        on_select
    ):
        super().__init__()
        self.plot_info = plot_info
        self.on_view = on_view
        self.on_delete = on_delete
        self.on_select = on_select
        
        # Checkbox for selection
        self.checkbox = ft.Checkbox(
            value=False,
            on_change=lambda e: on_select(plot_info['id'], e.control.value)
        )
        
        # Format created_at
        try:
            created_dt = datetime.fromisoformat(plot_info['created_at'])
            created_str = created_dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            created_str = plot_info['created_at']
        
        # Extract entity_id from settings if available
        entity_id = plot_info['settings'].get('entity_id', 'N/A') if plot_info['settings'] else 'N/A'
        
        # Build info text
        info_text = ft.Column([
            ft.Text(
                f"Plot #{plot_info['id']}: {plot_info['plot_type']}",
                size=14,
                weight=ft.FontWeight.BOLD
            ),
            ft.Text(
                f"Created: {created_str}",
                size=11,
                color=ft.Colors.GREY_600
            ),
            ft.Text(
                f"Entity: {entity_id}",
                size=11,
                color=ft.Colors.GREY_600
            )
        ], spacing=2, tight=True)
        
        # Action buttons
        view_button = ft.IconButton(
            icon=ft.Icons.VISIBILITY,
            tooltip="View plot",
            on_click=lambda e: on_view(plot_info['id'])
        )
        
        delete_button = ft.IconButton(
            icon=ft.Icons.DELETE,
            tooltip="Delete plot",
            icon_color=ft.Colors.RED_400,
            on_click=lambda e: on_delete(plot_info['id'])
        )
        
        # Layout
        self.content = ft.Row([
            self.checkbox,
            info_text,
            ft.Container(expand=True),
            view_button,
            delete_button
        ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        
        self.border = ft.border.all(1, ft.Colors.GREY_300)
        self.border_radius = 5
        self.padding = 10
        self.bgcolor = ft.Colors.WHITE


class PlotsTab(ft.Container):
    """Plots tab - manage saved plots."""
    
    def __init__(self, project: Project):
        super().__init__()
        print("PlotsTab init...")
        self.project = project
        self.expand = True
        self.padding = 10
        
        # State
        self.plot_items = []
        self.selected_ids = set()
        
        # UI references
        self.plots_list: Optional[ft.ListView] = None
        
        # Build UI
        self.content = self._build_ui()
    
    def _build_ui(self) -> ft.Control:
        """Build tab layout."""
        # Header with actions
        header = ft.Row([
            ft.Text("Saved Plots", size=20, weight=ft.FontWeight.BOLD),
            ft.Container(expand=True),
            ft.ElevatedButton(
                content=ft.Text("Export Selected to Word"),
                icon=ft.Icons.DESCRIPTION,
                on_click=lambda e: self.page.run_task(self._on_export_selected, e)
            ),
            ft.IconButton(
                icon=ft.Icons.REFRESH,
                tooltip="Refresh list",
                on_click=lambda e: self.page.run_task(self.load_data)
            )
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        
        # Plots list
        self.plots_list = ft.ListView(
            spacing=10,
            padding=10,
            expand=True
        )
        
        return ft.Column([
            header,
            ft.Container(height=10),
            ft.Divider(),
            ft.Container(height=10),
            self.plots_list
        ], expand=True, scroll=ft.ScrollMode.AUTO)
    
    def did_mount(self):
        """Load data when tab is mounted."""
        print("PlotsTab did_mount called")
        self.page.run_task(self.load_data)
    
    async def load_data(self, e=None):
        """Load list of saved plots."""
        try:
            self.plot_items = await self.project.get_saved_plots()
            
            # Clear list
            self.plots_list.controls.clear()
            
            if not self.plot_items:
                self.plots_list.controls.append(
                    ft.Container(
                        content=ft.Text(
                            "No saved plots yet",
                            size=14,
                            color=ft.Colors.GREY_600
                        ),
                        alignment=ft.Alignment.CENTER,
                        padding=20
                    )
                )
            else:
                # Add cards
                for plot_info in self.plot_items:
                    card = PlotItemCard(
                        plot_info=plot_info,
                        on_view=lambda pid: self.page.run_task(self._view_plot, pid),
                        on_delete=lambda pid: self.page.run_task(self._delete_plot, pid),
                        on_select=self._on_plot_selected
                    )
                    self.plots_list.controls.append(card)
            
            if self.page:
                self.page.update()
            
        except Exception as ex:
            print(f"Error loading plots: {ex}")
            import traceback
            traceback.print_exc()
    
    def _on_plot_selected(self, plot_id: int, selected: bool):
        """Handle plot selection change."""
        if selected:
            self.selected_ids.add(plot_id)
        else:
            self.selected_ids.discard(plot_id)
    
    async def _view_plot(self, plot_id: int):
        """View plot in dialog."""
        try:
            fig = await self.project.load_saved_plot(plot_id)
            
            # Create viewer
            viewer = PlotlyViewer(
                figure=fig,
                width=900,
                height=600,
                title=f"Plot #{plot_id}",
                show_interactive_button=True
            )
            
            # Show in dialog
            dialog = ft.AlertDialog(
                title=ft.Text(f"Plot #{plot_id}"),
                content=ft.Container(
                    content=viewer,
                    width=950,
                    height=650
                ),
                actions=[
                    ft.TextButton("Close", on_click=lambda e: self._close_dialog(dialog))
                ]
            )
            
            self.page.overlay.append(dialog)
            dialog.open = True
            self.page.update()
            
        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Error viewing plot: {ex}"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    async def _delete_plot(self, plot_id: int):
        """Delete plot with confirmation."""
        def on_confirm(e):
            self.page.run_task(self._delete_plot_confirmed, plot_id)
            dialog.open = False
            self.page.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text("Confirm Delete"),
            content=ft.Text(f"Are you sure you want to delete plot #{plot_id}?"),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(dialog)),
                ft.ElevatedButton(
                    "Delete",
                    on_click=on_confirm,
                    bgcolor=ft.Colors.RED_400,
                    color=ft.Colors.WHITE
                )
            ]
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    async def _delete_plot_confirmed(self, plot_id: int):
        """Actually delete the plot."""
        try:
            await self.project.delete_saved_plot(plot_id)
            
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Plot #{plot_id} deleted"),
                bgcolor=ft.Colors.GREEN_400
            )
            self.page.snack_bar.open = True
            
            # Reload list
            await self.load_data()
            
        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Error deleting plot: {ex}"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    async def _on_export_selected(self, e):
        """Export selected plots to Word."""
        if not self.selected_ids:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text("No plots selected"),
                bgcolor=ft.Colors.ORANGE_400
            )
            self.page.snack_bar.open = True
            self.page.update()
            return
        
        try:
            # Pick directory
            file_picker = ft.FilePicker()
            self.page.overlay.append(file_picker)
            self.page.update()
            
            result = await file_picker.get_directory_path()
            if not result:
                return
            
            output_dir = Path(result)
            await self._export_plots_to_word(list(self.selected_ids), output_dir)
            
        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Error exporting: {ex}"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    async def _export_plots_to_word(self, plot_ids: list[int], output_dir: Path):
        """Export plots to Word document."""
        try:
            from docx import Document
            from docx.shared import Inches
            
            # Load template
            template_path = Path(__file__).parent / "templates" / "plots_export.html.j2"
            with open(template_path, 'r', encoding='utf-8') as f:
                template = Template(f.read())
            
            # Collect plot data
            plots_data = []
            for plot_id in plot_ids:
                # Get plot info
                plot_info = next((p for p in self.plot_items if p['id'] == plot_id), None)
                if not plot_info:
                    continue
                
                # Load figure
                fig = await self.project.load_saved_plot(plot_id)
                
                # Convert to PNG base64
                png_bytes = fig.to_image(format='png', width=800, height=500)
                png_base64 = base64.b64encode(png_bytes).decode()
                
                plots_data.append({
                    'id': plot_id,
                    'plot_type': plot_info['plot_type'],
                    'created_at': plot_info['created_at'],
                    'png_base64': png_base64,
                    'settings': plot_info['settings'] or {}
                })
            
            # Render HTML
            html_content = template.render(plots=plots_data)
            
            # Create Word document
            doc = Document()
            
            # Add title
            doc.add_heading('DASMixer - Saved Plots', 0)
            doc.add_paragraph(f'Exported: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
            doc.add_paragraph('')
            
            # Add each plot
            for plot_data in plots_data:
                doc.add_heading(f"Plot #{plot_data['id']}: {plot_data['plot_type']}", 1)
                doc.add_paragraph(f"Created: {plot_data['created_at']}")
                
                # Save image temporarily and add to doc
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    tmp.write(base64.b64decode(plot_data['png_base64']))
                    tmp_path = tmp.name
                
                doc.add_picture(tmp_path, width=Inches(6))
                Path(tmp_path).unlink()  # Clean up
                
                # Add settings table
                if plot_data['settings']:
                    doc.add_heading('Settings', 2)
                    table = doc.add_table(rows=1, cols=2)
                    table.style = 'Light Grid Accent 1'
                    
                    hdr_cells = table.rows[0].cells
                    hdr_cells[0].text = 'Parameter'
                    hdr_cells[1].text = 'Value'
                    
                    for key, value in plot_data['settings'].items():
                        row_cells = table.add_row().cells
                        row_cells[0].text = str(key)
                        row_cells[1].text = str(value)
                
                doc.add_page_break()
            
            # Save document
            output_file = output_dir / f"plots_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
            doc.save(str(output_file))
            
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Exported to {output_file.name}"),
                bgcolor=ft.Colors.GREEN_400
            )
            self.page.snack_bar.open = True
            self.page.update()
            
        except Exception as ex:
            print(f"Error in export: {ex}")
            import traceback
            traceback.print_exc()
            raise
    
    def _close_dialog(self, dialog):
        """Close dialog helper."""
        dialog.open = False
        if self.page:
            self.page.update()
