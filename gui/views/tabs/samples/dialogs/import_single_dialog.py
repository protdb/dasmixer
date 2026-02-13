"""Dialog for importing individual files."""

import flet as ft
from pathlib import Path
from api.project.project import Project
from api.inputs.registry import registry


class ImportSingleDialog:
    """Dialog for importing individually selected files."""
    
    def __init__(
        self,
        project: Project,
        page: ft.Page,
        import_type: str,
        tool_id: int = None,
        on_import_callback=None
    ):
        """
        Initialize single file import dialog.
        
        Args:
            project: Project instance
            page: Flet page
            import_type: "spectra" or "identifications"
            tool_id: Tool ID (required for identifications)
            on_import_callback: Callback(file_list, subset_id, parser_name) or
                               callback(file_list, tool_id) for identifications
        """
        self.project = project
        self.page = page
        self.import_type = import_type
        self.tool_id = tool_id
        self.on_import_callback = on_import_callback
    
    async def show(self):
        """Show file picker and then configuration dialog."""
        try:
            # Use async FilePicker API directly
            result = await ft.FilePicker().pick_files(
                dialog_title=f"Select {self.import_type.title()} Files",
                allow_multiple=True
            )
            
            if not result:
                return  # User cancelled
            
            # Convert to format expected by import function
            file_list = [(Path(f.path), Path(f.name).stem) for f in result]
            
            # Show configuration dialog
            await self._show_config_dialog(file_list)
            
        except Exception as ex:
            import traceback
            traceback.print_exc()
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Error opening file picker: {ex}"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    async def _show_config_dialog(self, file_list):
        """Show configuration dialog for selected files."""
        if self.import_type == "spectra":
            # Get available parsers
            parsers = registry.get_spectra_parsers()
            parser_type_label = "Spectra Format / Parser"
            
            # Get groups
            groups = await self.project.get_subsets()
            group_options = [ft.dropdown.Option(key=str(g.id), text=g.name) for g in groups]
            
            if not group_options:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text("Please create at least one comparison group first"),
                    bgcolor=ft.Colors.ORANGE_400
                )
                self.page.snack_bar.open = True
                self.page.update()
                return
            
            parser_options = [
                ft.dropdown.Option(key=name, text=name)
                for name in parsers.keys()
            ]
            
            if not parser_options:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text("No spectra parsers available"),
                    bgcolor=ft.Colors.RED_400
                )
                self.page.snack_bar.open = True
                self.page.update()
                return
            
            # Parser selection (shared for all files)
            parser_dropdown = ft.Dropdown(
                label=parser_type_label,
                options=parser_options,
                value=parser_options[0].key,
                width=200
            )
        else:
            # For identifications, parser is from tool
            tool = await self.project.get_tool(self.tool_id)
            parser_type_label = f"Format: {tool.parser}"
            parser_dropdown = None
            
            # Check if we have samples
            samples = await self.project.get_samples()
            if not samples:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text("Please import spectra first"),
                    bgcolor=ft.Colors.ORANGE_400
                )
                self.page.snack_bar.open = True
                self.page.update()
                return
        
        # Create UI for each file
        file_configs = []
        for file_path, sample_id in file_list:
            sample_name = ft.TextField(
                label="Sample Name",
                value=sample_id,
                width=300
            )
            
            # Group dropdown only for spectra
            if self.import_type == "spectra":
                groups = await self.project.get_subsets()
                group_options = [ft.dropdown.Option(key=str(g.id), text=g.name) for g in groups]
                group_dropdown = ft.Dropdown(
                    label="Comparison Group",
                    options=group_options,
                    value=group_options[0].key,
                    width=200
                )
            else:
                group_dropdown = None
            
            file_configs.append({
                'file_path': file_path,
                'sample_name': sample_name,
                'group_dropdown': group_dropdown
            })
        
        # Build dialog content
        config_controls = []
        
        # Parser info (only for spectra shows dropdown)
        if parser_dropdown:
            config_controls.append(
                ft.Container(
                    content=ft.Row([
                        ft.Text("Parser:", weight=ft.FontWeight.BOLD),
                        parser_dropdown
                    ]),
                    padding=10,
                    border=ft.border.all(1, ft.Colors.BLUE_300),
                    border_radius=5,
                    bgcolor=ft.Colors.BLUE_50
                )
            )
        else:
            config_controls.append(
                ft.Container(
                    content=ft.Text(parser_type_label, weight=ft.FontWeight.BOLD),
                    padding=10,
                    border=ft.border.all(1, ft.Colors.BLUE_300),
                    border_radius=5,
                    bgcolor=ft.Colors.BLUE_50
                )
            )
        
        for cfg in file_configs:
            row_controls = [cfg['sample_name']]
            if cfg['group_dropdown']:
                row_controls.append(cfg['group_dropdown'])
            
            config_controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"File: {cfg['file_path'].name}", weight=ft.FontWeight.BOLD, size=12),
                        ft.Row(row_controls, spacing=10)
                    ], spacing=5),
                    padding=10,
                    border=ft.border.all(1, ft.Colors.GREY_300),
                    border_radius=5
                )
            )
        
        async def start_import(e):
            try:
                # Close config dialog
                config_dialog.open = False
                self.page.update()
                
                # Prepare file list with updated sample IDs
                files_to_import = []
                
                for cfg in file_configs:
                    sample_id = cfg['sample_name'].value
                    files_to_import.append((cfg['file_path'], sample_id))
                
                # Call import callback
                if self.on_import_callback:
                    if self.import_type == "spectra":
                        # All files go to same group for simplicity
                        subset_id = int(file_configs[0]['group_dropdown'].value)
                        await self.on_import_callback(
                            files_to_import,
                            subset_id,
                            parser_dropdown.value
                        )
                    else:
                        await self.on_import_callback(
                            files_to_import,
                            self.tool_id
                        )
                
            except Exception as ex:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Import error: {ex}"),
                    bgcolor=ft.Colors.RED_400
                )
                self.page.snack_bar.open = True
                self.page.update()
        
        config_dialog = ft.AlertDialog(
            title=ft.Text(f"Configure {self.import_type.title()} Import"),
            content=ft.Column(
                config_controls,
                scroll=ft.ScrollMode.AUTO,
                tight=True,
                width=600,
                height=min(450, len(config_controls) * 100 + 80)
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=lambda e: self._close_dialog(config_dialog)
                ),
                ft.ElevatedButton(
                    "Import",
                    on_click=lambda e: self.page.run_task(start_import, e)
                )
            ]
        )
        
        self.page.overlay.append(config_dialog)
        config_dialog.open = True
        self.page.update()
    
    def _close_dialog(self, dialog):
        """Close a dialog."""
        dialog.open = False
        self.page.update()
