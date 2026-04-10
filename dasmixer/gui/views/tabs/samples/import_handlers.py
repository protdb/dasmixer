"""Import handlers for spectra and identifications."""

import flet as ft
import pandas as pd
from pathlib import Path
from dasmixer.api.project.project import Project
from dasmixer.api.inputs.registry import registry


class ImportHandlers:
    """Handles import operations for spectra and identifications."""
    
    def __init__(self, project: Project, page: ft.Page, on_complete_callback=None):
        """
        Initialize import handlers.
        
        Args:
            project: Project instance
            page: Flet page
            on_complete_callback: Callback to execute after import completes
        """
        self.project = project
        self.page = page
        self.on_complete_callback = on_complete_callback
    
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
            
            # Show success
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Successfully imported {total_spectra} spectra from {total_files} file(s)"),
                bgcolor=ft.Colors.GREEN_400
            )
            self.page.snack_bar.open = True
            self.page.update()
            
            # Call completion callback
            if self.on_complete_callback:
                await self.on_complete_callback()
            
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
            
            # Get parser class from registry (using tool.parser as parser name)
            parser_class = registry.get_parser(tool.parser, "identification")
            
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
                
                # Add identification file record
                ident_file_id = await self.project.add_identification_file(
                    spectra_file_id=int(spectra_file_id),
                    tool_id=tool.id,
                    file_path=str(file_path)
                )
                
                # Parse and import identifications
                parser = parser_class(str(file_path))
                print(f'Parser {type(parser)} init for {file_path}')
                
                # Validate file
                is_valid = await parser.validate()
                print(f'validation result: {is_valid}')
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
                print(spectra_mapping)
                
                # Import identifications in batches
                batch_count = 0
                file_ident_count = 0
                async for batch_tuple in parser.parse_batch(batch_size=1000):
                    print(batch_tuple)
                    print(spectra_mapping)
                    batch = pd.merge(
                        batch_tuple[0],
                        pd.json_normalize(spectra_mapping),
                        on=parser.spectra_id_field,
                        how='inner'
                    )
                    # Add tool_id, ident_file_id
                    batch['tool_id'] = tool.id
                    batch['ident_file_id'] = ident_file_id
                    print(batch)
                    print(batch.columns)
                    
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
            
            # Show success
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Successfully imported {total_identifications} identifications from {total_files} file(s)"),
                bgcolor=ft.Colors.GREEN_400
            )
            self.page.snack_bar.open = True
            self.page.update()
            
            # Call completion callback
            if self.on_complete_callback:
                await self.on_complete_callback()
            
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
