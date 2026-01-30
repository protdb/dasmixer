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
    - Data import (spectra and identifications)
    """
    
    def __init__(self, project: Project):
        super().__init__()
        self.project = project
        self.groups_list = ft.Column(spacing=5)
        self.samples_table = None
        
        # Build content
        self.content = self._build_content()
        self.padding = 20
        self.expand = True
    
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
                        content="Add Group",
                        icon=ft.Icons.ADD,
                        on_click=lambda e: self.page.run_task(self.show_add_group_dialog, e)
                    ),
                    ft.OutlinedButton(
                        content="Delete Selected",
                        icon=ft.Icons.DELETE,
                        on_click=self.delete_selected_group
                    )
                ], spacing=10)
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY),
            border_radius=10
        )
        
        # Import buttons section
        import_section = ft.Container(
            content=ft.Column([
                ft.Text("Import Data", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.ElevatedButton(
                        content="Import Spectra (MGF)",
                        icon=ft.Icons.UPLOAD_FILE,
                        on_click=lambda e: self.page.run_task(self.show_import_mode_dialog, e)
                    ),
                    ft.ElevatedButton(
                        content="Import Identifications",
                        icon=ft.Icons.UPLOAD_FILE,
                        on_click=lambda e: self.page.run_task(self.show_import_identifications_dialog, e)
                    )
                ], spacing=10)
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY),
            border_radius=10
        )
        
        # Samples table section
        samples_section = ft.Container(
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
                samples_section
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )
    
    async def did_mount_async(self):
        """Load data when tab is mounted."""
        await self.refresh_groups()
        await self.refresh_samples()
    
    async def refresh_groups(self):
        """Refresh groups list."""
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
        
        self.update()
    
    async def refresh_samples(self):
        """Refresh samples table."""
        # Will be implemented with DataTable
        # For now, just placeholder
        pass
    
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
                    content="Add", 
                    on_click=lambda e: self.page.run_task(save_group, e)
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
    
    async def show_import_mode_dialog(self, e):
        """Show dialog to select import mode: single files or pattern matching."""
        
        async def import_single_files(e):
            dialog.open = False
            self.page.update()
            await self.show_import_single_files()
        
        async def import_with_pattern(e):
            dialog.open = False
            self.page.update()
            await self.show_import_pattern_dialog()
        
        dialog = ft.AlertDialog(
            title=ft.Text("Import Spectra (MGF)"),
            content=ft.Column([
                ft.Text("Choose import mode:", size=16),
                ft.Container(height=10),
                ft.ElevatedButton(
                    content="Select individual files",
                    icon=ft.Icons.INSERT_DRIVE_FILE,
                    on_click=lambda e: self.page.run_task(import_single_files, e),
                    width=300
                ),
                ft.Container(height=5),
                ft.ElevatedButton(
                    content="Pattern matching from folder",
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
    
    async def show_import_pattern_dialog(self, e=None):
        """Show dialog for pattern-based import."""
        from utils.seek_files import seek_files

        # Get available groups
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
        
        # Get available spectra parsers
        spectra_parsers = registry.get_spectra_parsers()
        parser_options = [
            ft.dropdown.Option(key=name, text=f"{name} - {parser_class.__doc__.split('.')[0].strip() if parser_class.__doc__ else name}")
            for name, parser_class in spectra_parsers.items()
        ]
        
        if not parser_options:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text("No spectra parsers available"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
            return
        
        folder_field = ft.TextField(
            label="Folder path",
            hint_text="/path/to/mgf/files",
            expand=True
        )
        
        file_pattern_field = ft.TextField(
            label="File pattern",
            value="*.mgf",
            hint_text="e.g., *.mgf or *_raw.mgf",
            width=200
        )
        
        id_pattern_field = ft.TextField(
            label="Sample ID pattern",
            value="{id}*.mgf",
            hint_text="e.g., {id}*.mgf or sample_{id}_*.mgf",
            expand=True
        )
        
        parser_dropdown = ft.Dropdown(
            label="File format / Parser",
            options=parser_options,
            value=parser_options[0].key,
            width=300
        )
        
        group_dropdown = ft.Dropdown(
            label="Assign to group",
            options=group_options,
            value=group_options[0].key,
            width=200
        )
        
        files_list = ft.Column(spacing=5)
        
        async def browse_folder(e):
            """Browse for folder using FilePicker."""
            try:
                folder_path = await ft.FilePicker().get_directory_path(
                    dialog_title="Select Folder with Spectra Files"
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
                await self.import_spectra_files(
                    found_files,
                    int(group_dropdown.value),
                    parser_dropdown.value
                )
                
            except Exception as ex:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Error: {ex}"),
                    bgcolor=ft.Colors.RED_400
                )
                self.page.snack_bar.open = True
                self.page.update()
        
        pattern_dialog = ft.AlertDialog(
            title=ft.Text("Import Spectra Files - Pattern Matching"),
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
                ft.Row([
                    parser_dropdown,
                    group_dropdown
                ], spacing=10),
                ft.Container(height=5),
                ft.ElevatedButton(
                    content="Preview Files",
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
                    content="Import",
                    icon=ft.Icons.DOWNLOAD,
                    on_click=lambda e: self.page.run_task(start_import, e)
                )
            ]
        )
        
        self.page.overlay.append(pattern_dialog)
        pattern_dialog.open = True
        self.page.update()
    
    async def show_import_single_files(self):
        """Show dialog for importing individual files."""
        try:
            # Use new async FilePicker API to select files
            files = await ft.FilePicker().pick_files(
                dialog_title="Select Spectra Files",
                allow_multiple=True
            )
            
            if not files or len(files) == 0:
                return  # User cancelled
            
            # Convert to format expected by import function
            file_list = [(Path(f.path), Path(f.name).stem) for f in files]
            
            # Show configuration dialog
            await self.show_single_files_config(file_list)
            
        except Exception as ex:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Error opening file picker: {ex}"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    async def show_single_files_config(self, file_list):
        """Show configuration dialog for individually selected files."""
        # Get available groups for dropdown
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
        
        # Get available spectra parsers
        spectra_parsers = registry.get_spectra_parsers()
        parser_options = [
            ft.dropdown.Option(key=name, text=name)
            for name in spectra_parsers.keys()
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
            label="File Format / Parser",
            options=parser_options,
            value=parser_options[0].key,
            width=200
        )
        
        # Create UI for each file
        file_configs = []
        for file_path, sample_id in file_list:
            sample_name = ft.TextField(
                label="Sample Name",
                value=sample_id,
                width=300
            )
            group_dropdown = ft.Dropdown(
                label="Comparison Group",
                options=group_options,
                value=group_options[0].key,
                width=200
            )
            
            file_configs.append({
                'file_path': file_path,
                'sample_name': sample_name,
                'group_dropdown': group_dropdown
            })
        
        # Build dialog content
        config_controls = [
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
        ]
        
        for cfg in file_configs:
            config_controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"File: {cfg['file_path'].name}", weight=ft.FontWeight.BOLD, size=12),
                        ft.Row([
                            cfg['sample_name'],
                            cfg['group_dropdown']
                        ], spacing=10)
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
                
                # Prepare file list with updated sample IDs and groups
                files_to_import = []
                subset_id = None
                
                for cfg in file_configs:
                    sample_id = cfg['sample_name'].value
                    subset_id = int(cfg['group_dropdown'].value)
                    files_to_import.append((cfg['file_path'], sample_id))
                
                # All files go to same group for simplicity
                # (can be enhanced later for per-file groups)
                subset_id = int(file_configs[0]['group_dropdown'].value)
                
                await self.import_spectra_files(
                    files_to_import,
                    subset_id,
                    parser_dropdown.value
                )
                
            except Exception as ex:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Import error: {ex}"),
                    bgcolor=ft.Colors.RED_400
                )
                self.page.snack_bar.open = True
                self.page.update()
        
        config_dialog = ft.AlertDialog(
            title=ft.Text("Configure Spectra Import"),
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
                    content="Import",
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
    
    async def show_import_identifications_dialog(self, e):
        """Show import identifications dialog."""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("Import identifications coming soon"),
            bgcolor=ft.Colors.BLUE_400
        )
        self.page.snack_bar.open = True
        self.page.update()
