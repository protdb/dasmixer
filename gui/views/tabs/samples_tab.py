"""Samples tab - manage samples, groups, and import data."""

import flet as ft
from api.project.project import Project
from api.inputs.registry import registry
from pathlib import Path


class SamplesTab(ft.Container):
    """
    Samples tab for managing:
    - Comparison groups (subsets)
    - Samples and their group assignments
    - Tools (identification methods)
    - Data import (spectra and identifications)
    """
    
    def __init__(self, project: Project):
        super().__init__()
        print("init samples tab...")
        self.project = project
        self.groups_list = ft.Column(spacing=5)
        self.tools_list = ft.Column(spacing=5)
        self.samples_container = None
        self.expand = True
        self.padding = 0
        
        # Build content immediately
        self.content = self._build_content()
    
    def _build_content(self):
        """Build the tab content."""
        # Groups management section
        groups_section = ft.Container(
            content=ft.Column([
                ft.Text("Comparison Groups", size=18, weight=ft.FontWeight.BOLD),
                self.groups_list,
                ft.Container(height=10),
                ft.Row([
                    ft.ElevatedButton(
                        content=ft.Text("Add Group"),
                        icon=ft.Icons.ADD,
                        on_click=lambda e: self.page.run_task(self.show_add_group_dialog, e)
                    ),
                    ft.OutlinedButton(
                        content=ft.Text("Delete Selected"),
                        icon=ft.Icons.DELETE,
                        on_click=self.delete_selected_group
                    )
                ], spacing=10)
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY),
            border_radius=10
        )
        
        # Import spectra section
        import_section = ft.Container(
            content=ft.Column([
                ft.Text("Import Spectra", size=18, weight=ft.FontWeight.BOLD),
                ft.ElevatedButton(
                    content=ft.Text("Import Spectra Files"),
                    icon=ft.Icons.UPLOAD_FILE,
                    on_click=lambda e: self.page.run_task(self.show_import_mode_dialog, e, "spectra")
                )
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY),
            border_radius=10
        )
        
        # Tools management section
        tools_section = ft.Container(
            content=ft.Column([
                ft.Text("Identification Tools", size=18, weight=ft.FontWeight.BOLD),
                self.tools_list,
                ft.Container(height=10),
                ft.ElevatedButton(
                    content=ft.Text("Add Tool"),
                    icon=ft.Icons.ADD,
                    on_click=lambda e: self.page.run_task(self.show_add_tool_dialog, e)
                )
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY),
            border_radius=10
        )
        
        # Samples table section
        self.samples_container = ft.Container(
            content=ft.Column([
                ft.Text("Samples", size=18, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=ft.Text("No samples yet. Import spectra to add samples."),
                    padding=20
                )
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY),
            border_radius=10,
            expand=True
        )
        
        # Main layout
        return ft.Column([
                groups_section,
                ft.Container(height=10),
                import_section,
                ft.Container(height=10),
                tools_section,
                ft.Container(height=10),
                self.samples_container
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )
    
    def did_mount(self):
        """Called when control is added to page - load initial data."""
        print("SamplesTab did_mount called")
        # Run async loading
        self.page.run_task(self._load_initial_data)
    
    async def _load_initial_data(self):
        """Load all initial data."""
        print("Loading initial data...")
        try:
            await self.refresh_groups()
            await self.refresh_tools()
            await self.refresh_samples()
            print("Initial data loaded successfully")
        except Exception as ex:
            print(f"Error loading initial data: {ex}")
            import traceback
            traceback.print_exc()
    
    async def refresh_groups(self):
        """Refresh groups list."""
        print("Refreshing groups...")
        groups = await self.project.get_subsets()
        
        self.groups_list.controls.clear()
        
        for group in groups:
            # Count samples in group
            samples = await self.project.get_samples(subset_id=group.id)
            
            self.groups_list.controls.append(
                ft.ListTile(
                    leading=ft.Container(
                        content=ft.Icon(ft.Icons.FOLDER, color=group.display_color or ft.Colors.PRIMARY),
                        width=40
                    ),
                    title=ft.Text(group.name, weight=ft.FontWeight.BOLD),
                    subtitle=ft.Text(f"{len(samples)} samples" + (f" • {group.details}" if group.details else "")),
                    data=group.id
                )
            )
        
        if not groups:
            self.groups_list.controls.append(
                ft.Text("No groups. Click 'Add Group' to create one.", italic=True)
            )
        
        print(f"Groups loaded: {len(groups)}")
        self.groups_list.update()
    
    async def refresh_tools(self):
        """Refresh tools list."""
        print("Refreshing tools...")
        tools = await self.project.get_tools()
        
        self.tools_list.controls.clear()
        
        for tool in tools:
            # Count identification files for this tool
            ident_files = await self.project.get_identification_files(tool_id=tool.id)
            
            self.tools_list.controls.append(
                ft.ListTile(
                    leading=ft.Container(
                        content=ft.Icon(ft.Icons.BIOTECH, color=tool.display_color or ft.Colors.SECONDARY),
                        width=40
                    ),
                    title=ft.Text(tool.name, weight=ft.FontWeight.BOLD),
                    subtitle=ft.Text(f"{len(ident_files)} identification file(s)" + (f" • Type: {tool.type}" if tool.type else "")),
                    trailing=ft.ElevatedButton(
                        content=ft.Text("Import Identifications"),
                        icon=ft.Icons.UPLOAD_FILE,
                        on_click=lambda e, t=tool: self.page.run_task(self.show_import_mode_dialog, e, "identifications", t.id)
                    ),
                    data=tool.id
                )
            )
        
        if not tools:
            self.tools_list.controls.append(
                ft.Text("No tools. Click 'Add Tool' to create one.", italic=True)
            )
        
        print(f"Tools loaded: {len(tools)}")
        self.tools_list.update()
    
    async def refresh_samples(self):
        """Refresh samples table."""
        print("Refreshing samples...")
        samples = await self.project.get_samples()
        
        if not samples:
            self.samples_container.content = ft.Column([
                ft.Text("Samples", size=18, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=ft.Text("No samples yet. Import spectra to add samples."),
                    padding=20
                )
            ], spacing=10)
        else:
            # Build samples list
            samples_list = ft.Column(spacing=5)
            
            for sample in samples:
                # Get tools for this sample
                spectra_files = await self.project.get_spectra_files(sample_id=sample.id)
                tools_info = []
                
                for _, sf in spectra_files.iterrows():
                    # Check for identifications
                    ident_files = await self.project.get_identification_files(spectra_file_id=sf['id'])
                    if len(ident_files) > 0:
                        for _, ident_file in ident_files.iterrows():
                            tools_info.append(f"✓ {ident_file['tool_name']}")
                
                tools_display = ", ".join(tools_info) if tools_info else "No identifications"
                
                samples_list.controls.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.SCIENCE, size=16),
                        title=ft.Text(sample.name, weight=ft.FontWeight.BOLD, size=14),
                        subtitle=ft.Text(
                            f"Group: {sample.subset_name or 'None'} • Files: {sample.spectra_files_count} • {tools_display}",
                            size=11
                        ),
                        dense=True
                    )
                )
            
            self.samples_container.content = ft.Column([
                ft.Text("Samples", size=18, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=samples_list,
                    padding=10,
                    border=ft.border.all(1, ft.Colors.GREY_300),
                    border_radius=5
                )
            ], spacing=10)
        
        print(f"Samples loaded: {len(samples)}")
        self.samples_container.update()
    
    async def show_add_group_dialog(self, e):
        """Show dialog for adding new group."""
        name_field = ft.TextField(label="Group Name", autofocus=True)
        details_field = ft.TextField(label="Description (optional)", multiline=True)
        color_field = ft.TextField(
            label="Color (hex)",
            value="3B82F6",
        )
        
        async def save_group(e):
            if not name_field.value:
                name_field.error_text = "Name is required"
                name_field.update()
                return
            
            try:
                color = color_field.value
                if not color.startswith('#'):
                    color = '#' + color
                
                await self.project.add_subset(
                    name=name_field.value,
                    details=details_field.value or None,
                    display_color=color
                )
                
                # Close dialog
                dialog.open = False
                self.page.update()
                
                # Refresh groups list
                await self.refresh_groups()
                
                # Show success
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Added group: {name_field.value}"),
                    bgcolor=ft.Colors.GREEN_400
                )
                self.page.snack_bar.open = True
                self.page.update()
                
            except Exception as ex:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Error: {ex}"),
                    bgcolor=ft.Colors.RED_400
                )
                self.page.snack_bar.open = True
                self.page.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text("Add Comparison Group"),
            content=ft.Column([
                name_field,
                details_field,
                color_field
            ], tight=True, width=400),
            actions=[
                ft.TextButton(
                    content="Cancel", 
                    on_click=lambda e: self._close_dialog(dialog)
                ),
                ft.ElevatedButton(
                    content=ft.Text("Add"),
                    on_click=lambda e: self.page.run_task(save_group, e)
                )
            ]
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    async def show_add_tool_dialog(self, e):
        """Show dialog for adding new tool."""
        # Get available identification parsers
        parsers = registry.get_identification_parsers()
        parser_options = [
            ft.DropdownOption(key=name, text=name)
            for name in parsers.keys()
        ]
        
        if not parser_options:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text("No identification parsers available"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
            return
        
        name_field = ft.TextField(
            label="Tool Name",
            hint_text="e.g., PowerNovo2, MaxQuant",
            autofocus=True
        )
        
        parser_dropdown = ft.Dropdown(
            label="Parser / Format",
            options=parser_options,
            value=parser_options[0].key,
            width=300
        )
        
        color_field = ft.TextField(
            label="Color (hex)",
            value="9333EA",
        )
        
        async def save_tool(e):
            if not name_field.value:
                name_field.error_text = "Name is required"
                name_field.update()
                return
            
            try:
                color = color_field.value
                if not color.startswith('#'):
                    color = '#' + color
                
                await self.project.add_tool(
                    name=name_field.value,
                    type=parser_dropdown.value,
                    display_color=color
                )
                
                # Close dialog
                dialog.open = False
                self.page.update()
                
                # Refresh tools list
                await self.refresh_tools()
                
                # Show success
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Added tool: {name_field.value}"),
                    bgcolor=ft.Colors.GREEN_400
                )
                self.page.snack_bar.open = True
                self.page.update()
                
            except Exception as ex:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Error: {ex}"),
                    bgcolor=ft.Colors.RED_400
                )
                self.page.snack_bar.open = True
                self.page.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text("Add Identification Tool"),
            content=ft.Column([
                name_field,
                parser_dropdown,
                color_field,
                ft.Container(height=5),
                ft.Text(
                    "Tool represents an identification method (e.g., de novo, database search)",
                    size=11,
                    italic=True,
                    color=ft.Colors.GREY_600
                )
            ], tight=True, width=400),
            actions=[
                ft.TextButton(
                    content="Cancel", 
                    on_click=lambda e: self._close_dialog(dialog)
                ),
                ft.ElevatedButton(
                    content=ft.Text("Add"),
                    on_click=lambda e: self.page.run_task(save_tool, e)
                )
            ]
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    def _close_dialog(self, dialog):
        """Helper to close dialog."""
        dialog.open = False
        self.page.update()
    
    def delete_selected_group(self, e):
        """Delete selected group (placeholder)."""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("Select a group from the list first (feature coming soon)"),
            bgcolor=ft.Colors.BLUE_400
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    async def show_import_mode_dialog(self, e, import_type: str, tool_id: int | None = None):
        """
        Show dialog to select import mode: single files or pattern matching.
        
        Args:
            import_type: "spectra" or "identifications"
            tool_id: Tool ID (required for identifications)
        """
        # Configure dialog text based on import type
        if import_type == "spectra":
            title = "Import Spectra"
            desc = "Import mass spectrometry spectra data files"
        else:
            # Get tool name
            tool = await self.project.get_tool(tool_id)
            title = f"Import Identifications - {tool.name}"
            desc = f"Import identification files for {tool.name}"
        
        async def import_single_files(e):
            dialog.open = False
            self.page.update()
            await self.show_import_single_files(import_type, tool_id)
        
        async def import_with_pattern(e):
            dialog.open = False
            self.page.update()
            await self.show_import_pattern_dialog(import_type, tool_id)
        
        dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Column([
                ft.Text("Choose import mode:", size=16),
                ft.Text(desc, size=11, italic=True, color=ft.Colors.GREY_600),
                ft.Container(height=10),
                ft.ElevatedButton(
                    content=ft.Text("Select individual files"),
                    icon=ft.Icons.INSERT_DRIVE_FILE,
                    on_click=lambda e: self.page.run_task(import_single_files, e),
                    width=300
                ),
                ft.Container(height=5),
                ft.ElevatedButton(
                    content=ft.Text("Pattern matching from folder"),
                    icon=ft.Icons.FOLDER_OPEN,
                    on_click=lambda e: self.page.run_task(import_with_pattern, e),
                    width=300
                ),
                ft.Container(height=10),
                ft.Text(
                    "Pattern matching allows automatic sample ID extraction from filenames",
                    size=11,
                    italic=True,
                    color=ft.Colors.GREY_600
                )
            ], tight=True, width=400),
            actions=[
                ft.TextButton(
                    content="Cancel",
                    on_click=lambda e: self._close_dialog(dialog)
                )
            ]
        )
        
        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()
    
    async def show_import_pattern_dialog(self, import_type: str, tool_id: int | None = None, e=None):
        """Show dialog for pattern-based import."""
        from utils.seek_files import seek_files

        # Get available groups (only needed for spectra)
        if import_type == "spectra":
            groups = await self.project.get_subsets()
            group_options = [ft.DropdownOption(key=str(g.id), text=g.name) for g in groups]
            
            if not group_options:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text("Please create at least one comparison group first"),
                    bgcolor=ft.Colors.ORANGE_400
                )
                self.page.snack_bar.open = True
                self.page.update()
                return
        else:
            # For identifications, check samples exist
            samples = await self.project.get_samples()
            if not samples:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text("Please import spectra first"),
                    bgcolor=ft.Colors.ORANGE_400
                )
                self.page.snack_bar.open = True
                self.page.update()
                return
        
        # Get parser format based on tool or get all parsers for spectra
        if import_type == "spectra":
            parsers = registry.get_spectra_parsers()
            parser_type_label = "Spectra Format"
            default_pattern = "*.mgf"
            default_id_pattern = "{id}*.mgf"
            
            parser_options = [
                ft.DropdownOption(key=name, text=f"{name} - {parser_class.__doc__.split('.')[0].strip() if parser_class.__doc__ else name}")
                for name, parser_class in parsers.items()
            ]
        else:
            # For identifications, get parser from tool
            tool = await self.project.get_tool(tool_id)
            parser_name = tool.type
            parser_type_label = f"Format: {parser_name}"
            default_pattern = "*.csv"
            default_id_pattern = "{id}*.csv"
            parser_options = None  # Parser is fixed by tool
        
        if import_type == "spectra" and not parser_options:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text("No spectra parsers available"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
            return
        
        folder_field = ft.TextField(
            label="Folder path",
            hint_text="/path/to/files",
            expand=True
        )
        
        file_pattern_field = ft.TextField(
            label="File pattern",
            value=default_pattern,
            hint_text=f"e.g., {default_pattern}",
            width=200
        )
        
        id_pattern_field = ft.TextField(
            label="Sample ID pattern",
            value=default_id_pattern,
            hint_text=f"e.g., {default_id_pattern}",
            expand=True
        )
        
        # Build controls row
        dropdown_controls = []
        
        if import_type == "spectra":
            parser_dropdown = ft.Dropdown(
                label=parser_type_label,
                options=parser_options,
                value=parser_options[0].key,
                width=300
            )
            dropdown_controls.append(parser_dropdown)
            
            group_dropdown = ft.Dropdown(
                label="Assign to group",
                options=group_options,
                value=group_options[0].key,
                width=200
            )
            dropdown_controls.append(group_dropdown)
        else:
            # For identifications, parser is fixed, no group needed
            parser_dropdown = None
            group_dropdown = None
            dropdown_controls.append(
                ft.Text(parser_type_label, weight=ft.FontWeight.BOLD, size=14)
            )
        
        files_list = ft.Column(spacing=5)
        
        async def browse_folder(e):
            """Browse for folder using FilePicker."""
            try:
                folder_path = await ft.FilePicker().get_directory_path(
                    dialog_title=f"Select Folder with {import_type.title()} Files"
                )
                if folder_path:
                    folder_field.value = folder_path
                    folder_field.update()
            except Exception as ex:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Error selecting folder: {ex}"),
                    bgcolor=ft.Colors.RED_400
                )
                self.page.snack_bar.open = True
                self.page.update()
        
        async def preview_files(e):
            if not folder_field.value:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text("Please select a folder first"),
                    bgcolor=ft.Colors.ORANGE_400
                )
                self.page.snack_bar.open = True
                self.page.update()
                return
            
            try:
                folder_path = Path(folder_field.value)
                if not folder_path.exists():
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text("Folder does not exist"),
                        bgcolor=ft.Colors.RED_400
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
                    return
                
                # Find files using pattern
                found_files = seek_files(
                    folder_path,
                    file_pattern_field.value,
                    id_pattern_field.value
                )
                
                files_list.controls.clear()
                
                if not found_files:
                    files_list.controls.append(
                        ft.Text("No files found", italic=True, color=ft.Colors.GREY_600)
                    )
                else:
                    files_list.controls.append(
                        ft.Text(f"Found {len(found_files)} file(s):", weight=ft.FontWeight.BOLD)
                    )
                    for file_path, sample_id in found_files[:20]:  # Show max 20 for preview
                        files_list.controls.append(
                            ft.ListTile(
                                leading=ft.Icon(ft.Icons.DESCRIPTION, size=16),
                                title=ft.Text(file_path.name, size=12),
                                subtitle=ft.Text(f"Sample ID: {sample_id or 'UNKNOWN'}", size=10),
                                dense=True
                            )
                        )
                    if len(found_files) > 20:
                        files_list.controls.append(
                            ft.Text(f"... and {len(found_files) - 20} more", italic=True, size=11)
                        )
                
                files_list.update()
                
            except Exception as ex:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Error: {ex}"),
                    bgcolor=ft.Colors.RED_400
                )
                self.page.snack_bar.open = True
                self.page.update()
        
        async def start_import(e):
            if not folder_field.value:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text("Please select a folder first"),
                    bgcolor=ft.Colors.ORANGE_400
                )
                self.page.snack_bar.open = True
                self.page.update()
                return
            
            try:
                folder_path = Path(folder_field.value)
                found_files = seek_files(
                    folder_path,
                    file_pattern_field.value,
                    id_pattern_field.value
                )
                
                if not found_files:
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text("No files found"),
                        bgcolor=ft.Colors.ORANGE_400
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
                    return
                
                # Close pattern dialog
                pattern_dialog.open = False
                self.page.update()
                
                # Start import
                if import_type == "spectra":
                    await self.import_spectra_files(
                        found_files,
                        int(group_dropdown.value),
                        parser_dropdown.value
                    )
                else:
                    await self.import_identification_files(
                        found_files,
                        tool_id
                    )
                
            except Exception as ex:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Error: {ex}"),
                    bgcolor=ft.Colors.RED_400
                )
                self.page.snack_bar.open = True
                self.page.update()
        
        # Build row with dropdowns
        dropdown_row = ft.Row(dropdown_controls, spacing=10) if dropdown_controls else ft.Container()
        
        pattern_dialog = ft.AlertDialog(
            title=ft.Text(f"Import {import_type.title()} - Pattern Matching"),
            content=ft.Column([
                ft.Row([
                    folder_field,
                    ft.IconButton(
                        icon=ft.Icons.FOLDER_OPEN,
                        on_click=lambda e: self.page.run_task(browse_folder, e)
                    )
                ], spacing=5),
                ft.Row([
                    file_pattern_field,
                    id_pattern_field
                ], spacing=10),
                dropdown_row,
                ft.Container(height=5),
                ft.ElevatedButton(
                    content=ft.Text("Preview Files"),
                    icon=ft.Icons.PREVIEW,
                    on_click=lambda e: self.page.run_task(preview_files, e)
                ),
                ft.Container(height=5),
                ft.Container(
                    content=files_list,
                    height=200,
                    border=ft.border.all(1, ft.Colors.GREY_300),
                    border_radius=5,
                    padding=10
                )
            ], tight=True, width=700, scroll=ft.ScrollMode.AUTO),
            actions=[
                ft.TextButton(
                    content="Cancel",
                    on_click=lambda e: self._close_dialog(pattern_dialog)
                ),
                ft.ElevatedButton(
                    content=ft.Text("Import"),
                    icon=ft.Icons.DOWNLOAD,
                    on_click=lambda e: self.page.run_task(start_import, e)
                )
            ]
        )
        
        self.page.overlay.append(pattern_dialog)
        pattern_dialog.open = True
        self.page.update()
    
    async def show_import_single_files(self, import_type: str, tool_id: int | None = None):
        """Show dialog for importing individual files."""
        try:
            # Use new async FilePicker API to select files
            files = await ft.FilePicker().pick_files(
                dialog_title=f"Select {import_type.title()} Files",
                allow_multiple=True
            )
            
            if not files or len(files) == 0:
                return  # User cancelled
            
            # Convert to format expected by import function
            file_list = [(Path(f.path), Path(f.name).stem) for f in files]
            
            # Show configuration dialog
            await self.show_single_files_config(file_list, import_type, tool_id)
            
        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Error opening file picker: {ex}"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    async def show_single_files_config(self, file_list, import_type: str, tool_id: int | None = None):
        """Show configuration dialog for individually selected files."""
        if import_type == "spectra":
            # Get available parsers
            parsers = registry.get_spectra_parsers()
            parser_type_label = "Spectra Format / Parser"
            
            # Get groups
            groups = await self.project.get_subsets()
            group_options = [ft.DropdownOption(key=str(g.id), text=g.name) for g in groups]
            
            if not group_options:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text("Please create at least one comparison group first"),
                    bgcolor=ft.Colors.ORANGE_400
                )
                self.page.snack_bar.open = True
                self.page.update()
                return
            
            parser_options = [
                ft.DropdownOption(key=name, text=name)
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
            tool = await self.project.get_tool(tool_id)
            parser_type_label = f"Format: {tool.type}"
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
            if import_type == "spectra":
                groups = await self.project.get_subsets()
                group_options = [ft.DropdownOption(key=str(g.id), text=g.name) for g in groups]
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
                
                # Start import
                if import_type == "spectra":
                    # All files go to same group for simplicity
                    subset_id = int(file_configs[0]['group_dropdown'].value)
                    await self.import_spectra_files(
                        files_to_import,
                        subset_id,
                        parser_dropdown.value
                    )
                else:
                    await self.import_identification_files(
                        files_to_import,
                        tool_id
                    )
                
            except Exception as ex:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Import error: {ex}"),
                    bgcolor=ft.Colors.RED_400
                )
                self.page.snack_bar.open = True
                self.page.update()
        
        config_dialog = ft.AlertDialog(
            title=ft.Text(f"Configure {import_type.title()} Import"),
            content=ft.Column(
                config_controls,
                scroll=ft.ScrollMode.AUTO,
                tight=True,
                width=600,
                height=min(450, len(config_controls) * 100 + 80)
            ),
            actions=[
                ft.TextButton(
                    content="Cancel",
                    on_click=lambda e: self._close_dialog(config_dialog)
                ),
                ft.ElevatedButton(
                    content=ft.Text("Import"),
                    on_click=lambda e: self.page.run_task(start_import, e)
                )
            ]
        )
        
        self.page.overlay.append(config_dialog)
        config_dialog.open = True
        self.page.update()
    
    async def import_spectra_files(self, file_list, subset_id, parser_name):
        """
        Import spectra files with progress indication.
        
        Args:
            file_list: List of (file_path, sample_id) tuples
            subset_id: Group ID to assign samples
            parser_name: Name of parser to use (from registry)
        """
        # Show progress dialog
        progress_text = ft.Text("Preparing import...")
        progress_bar = ft.ProgressBar(value=0)
        progress_details = ft.Text("", size=11, color=ft.Colors.GREY_600)
        
        progress_dialog = ft.AlertDialog(
            title=ft.Text("Importing Spectra"),
            content=ft.Column([
                progress_text,
                progress_bar,
                ft.Container(height=5),
                progress_details
            ], tight=True, width=400),
            modal=True
        )
        
        self.page.overlay.append(progress_dialog)
        progress_dialog.open = True
        self.page.update()
        
        try:
            # Get parser class from registry
            parser_class = registry.get_parser(parser_name, "spectra")
            
            total_files = len(file_list)
            total_spectra = 0
            
            for i, (file_path, sample_id) in enumerate(file_list):
                progress_text.value = f"Importing {file_path.name} ({i+1}/{total_files})..."
                progress_bar.value = i / total_files
                progress_details.value = f"Processing file..."
                progress_text.update()
                progress_bar.update()
                progress_details.update()
                
                # Get or create sample
                sample = await self.project.get_sample_by_name(sample_id)
                if not sample:
                    sample = await self.project.add_sample(
                        name=sample_id,
                        subset_id=subset_id
                    )
                
                # Add spectra file record
                spectra_file_id = await self.project.add_spectra_file(
                    sample_id=sample.id,
                    format=parser_name,
                    path=str(file_path)
                )
                
                # Parse and import spectra
                parser = parser_class(str(file_path))
                
                # Validate file
                is_valid = await parser.validate()
                if not is_valid:
                    progress_dialog.open = False
                    self.page.update()
                    
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"Invalid file format: {file_path.name}"),
                        bgcolor=ft.Colors.RED_400
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
                    return
                
                # Import spectra in batches
                batch_count = 0
                file_spectra_count = 0
                async for batch in parser.parse_batch(batch_size=1000):
                    await self.project.add_spectra_batch(spectra_file_id, batch)
                    batch_count += 1
                    file_spectra_count += len(batch)
                    total_spectra += len(batch)
                    
                    progress_details.value = f"Imported {file_spectra_count} spectra (batch {batch_count})..."
                    progress_details.update()
            
            # Complete
            progress_bar.value = 1.0
            progress_text.value = "Import complete!"
            progress_details.value = f"Total: {total_spectra} spectra from {total_files} file(s)"
            progress_text.update()
            progress_bar.update()
            progress_details.update()
            
            # Close progress dialog after a moment
            import asyncio
            await asyncio.sleep(1)
            progress_dialog.open = False
            self.page.update()
            
            # Refresh samples view
            await self.refresh_samples()
            await self.refresh_groups()
            
            # Show success
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Successfully imported {total_spectra} spectra from {total_files} file(s)"),
                bgcolor=ft.Colors.GREEN_400
            )
            self.page.snack_bar.open = True
            self.page.update()
            
        except Exception as ex:
            import traceback
            error_details = traceback.format_exc()
            print(f"Import error: {error_details}")
            
            progress_dialog.open = False
            self.page.update()
            
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Import error: {str(ex)}"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    async def import_identification_files(self, file_list, tool_id: int):
        """
        Import identification files with progress indication.
        
        Args:
            file_list: List of (file_path, sample_id) tuples
            tool_id: Tool ID to use for identifications
        """
        # Show progress dialog
        progress_text = ft.Text("Preparing import...")
        progress_bar = ft.ProgressBar(value=0)
        progress_details = ft.Text("", size=11, color=ft.Colors.GREY_600)
        
        progress_dialog = ft.AlertDialog(
            title=ft.Text("Importing Identifications"),
            content=ft.Column([
                progress_text,
                progress_bar,
                ft.Container(height=5),
                progress_details
            ], tight=True, width=400),
            modal=True
        )
        
        self.page.overlay.append(progress_dialog)
        progress_dialog.open = True
        self.page.update()
        
        try:
            # Get tool
            tool = await self.project.get_tool(tool_id)
            if not tool:
                raise ValueError(f"Tool with id={tool_id} not found")
            
            # Get parser class from registry (using tool.type as parser name)
            parser_class = registry.get_parser(tool.type, "identification")
            
            total_files = len(file_list)
            total_identifications = 0
            
            for i, (file_path, sample_id) in enumerate(file_list):
                progress_text.value = f"Importing {file_path.name} ({i+1}/{total_files})..."
                progress_bar.value = i / total_files
                progress_details.value = f"Processing file..."
                progress_text.update()
                progress_bar.update()
                progress_details.update()
                
                # Get sample by name
                sample = await self.project.get_sample_by_name(sample_id)
                if not sample:
                    progress_dialog.open = False
                    self.page.update()
                    
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"Sample '{sample_id}' not found. Import spectra first."),
                        bgcolor=ft.Colors.RED_400
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
                    return
                
                # Get spectra files for this sample
                spectra_files = await self.project.get_spectra_files(sample_id=sample.id)
                if len(spectra_files) == 0:
                    progress_dialog.open = False
                    self.page.update()
                    
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"No spectra files for sample '{sample_id}'"),
                        bgcolor=ft.Colors.RED_400
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
                    return
                
                # Use first spectra file
                spectra_file_id = spectra_files.iloc[0]['id']
                print(f'getting ids...')
                print(sample_id, spectra_file_id)
                
                # Add identification file record
                ident_file_id = await self.project.add_identification_file(
                    spectra_file_id=int(spectra_file_id),
                    tool_id=tool.id,
                    file_path=str(file_path)
                )
                
                # Parse and import identifications
                parser = parser_class(str(file_path))
                
                # Validate file
                is_valid = await parser.validate()
                if not is_valid:
                    progress_dialog.open = False
                    self.page.update()
                    
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"Invalid file format: {file_path.name}"),
                        bgcolor=ft.Colors.RED_400
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
                    return
                
                # Get spectra ID mapping
                spectra_mapping = await self.project.get_spectra_idlist(
                    spectra_file_id,
                    by=parser.spectra_id_field
                )
                
                # Import identifications in batches
                batch_count = 0
                file_ident_count = 0
                async for batch in parser.parse_batch(batch_size=1000):
                    # Add spectre_id, tool_id, ident_file_id
                    batch['spectre_id'] = batch[parser.spectra_id_field].map(spectra_mapping)
                    batch['tool_id'] = tool.id
                    batch['ident_file_id'] = ident_file_id
                    
                    # Filter out rows without matching spectrum
                    batch = batch[batch['spectre_id'].notna()]
                    
                    if len(batch) > 0:
                        await self.project.add_identifications_batch(batch)
                        batch_count += 1
                        file_ident_count += len(batch)
                        total_identifications += len(batch)
                    
                    progress_details.value = f"Imported {file_ident_count} identifications (batch {batch_count})..."
                    progress_details.update()
            
            # Complete
            progress_bar.value = 1.0
            progress_text.value = "Import complete!"
            progress_details.value = f"Total: {total_identifications} identifications from {total_files} file(s)"
            progress_text.update()
            progress_bar.update()
            progress_details.update()
            
            # Close progress dialog after a moment
            import asyncio
            await asyncio.sleep(1)
            progress_dialog.open = False
            self.page.update()
            
            # Refresh samples view
            await self.refresh_samples()
            await self.refresh_tools()
            await self.refresh_groups()
            
            # Show success
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Successfully imported {total_identifications} identifications from {total_files} file(s)"),
                bgcolor=ft.Colors.GREEN_400
            )
            self.page.snack_bar.open = True
            self.page.update()
            
        except Exception as ex:
            import traceback
            error_details = traceback.format_exc()
            print(f"Import error: {error_details}")
            
            progress_dialog.open = False
            self.page.update()
            
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Import error: {str(ex)}"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
