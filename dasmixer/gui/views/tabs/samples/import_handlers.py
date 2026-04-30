"""Import handlers for spectra and identifications."""

import flet as ft
import pandas as pd
from pathlib import Path
from dasmixer.api.project.project import Project
from dasmixer.api.inputs.registry import registry
from dasmixer.api.config import config as _config
from dasmixer.gui.utils import show_snack
from dasmixer.utils import logger


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
    
    async def import_spectra_files(self, file_list, subset_id, parser_name, fixed_sample_name=None):
        """
        Import spectra files with progress indication.
        
        Args:
            file_list: List of (file_path, sample_name) tuples
            subset_id: Group ID to assign samples
            parser_name: Name of parser to use (from registry)
            fixed_sample_name: If set, overrides sample names from file_list (used in fixed-sample mode)
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
                effective_name = fixed_sample_name if fixed_sample_name else sample_id
                sample = await self.project.get_sample_by_name(effective_name)
                if not sample:
                    sample = await self.project.add_sample(
                        name=effective_name,
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
                    
                    show_snack(self.page, f"Invalid file format: {file_path.name}", ft.Colors.RED_400)
                    self.page.update()
                    return
                
                # Import spectra in batches
                batch_size = _config.spectra_batch_size
                batch_count = 0
                file_spectra_count = 0
                async for batch in parser.parse_batch(batch_size=batch_size):
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
            show_snack(self.page, f"Successfully imported {total_spectra} spectra from {total_files} file(s)", ft.Colors.GREEN_400)
            self.page.update()
            
            # Call completion callback
            if self.on_complete_callback:
                await self.on_complete_callback()
            
        except Exception as ex:
            logger.exception(ex)
            import traceback
            error_details = traceback.format_exc()
            logger.debug(f"Import error: {error_details}")
            
            progress_dialog.open = False
            self.page.update()
            
            show_snack(self.page, f"Import error: {str(ex)}", ft.Colors.RED_400)
            self.page.update()
    
    async def import_identification_files(
        self,
        file_list,
        tool_id: int,
        fixed_spectra_file_id: int = None,
        collect_proteins: bool = False,
        is_uniprot_proteins: bool = False,
    ):
        """
        Import identification files with progress indication.
        
        Args:
            file_list: List of (file_path, sample_id) tuples
            tool_id: Tool ID to use for identifications
            fixed_spectra_file_id: If set, use this spectra file ID directly (bypasses sample lookup)
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
                
                # Determine spectra_file_id
                if fixed_spectra_file_id is not None:
                    spectra_file_id = fixed_spectra_file_id
                else:
                    # Get sample by name
                    sample = await self.project.get_sample_by_name(sample_id)
                    if not sample:
                        progress_dialog.open = False
                        self.page.update()

                        show_snack(self.page, f"Sample '{sample_id}' not found. Import spectra first.", ft.Colors.RED_400)
                        self.page.update()
                        return

                    # Get spectra files for this sample
                    spectra_files = await self.project.get_spectra_files(sample_id=sample.id)
                    if len(spectra_files) == 0:
                        progress_dialog.open = False
                        self.page.update()

                        show_snack(self.page, f"No spectra files for sample '{sample_id}'", ft.Colors.RED_400)
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
                parser = parser_class(
                    str(file_path),
                    collect_proteins=collect_proteins,
                    is_uniprot_proteins=is_uniprot_proteins,
                )
                logger.debug(f'Parser {type(parser)} init for {file_path}')
                
                # Validate file
                is_valid = await parser.validate()
                logger.debug(f'validation result: {is_valid}')
                if not is_valid:
                    progress_dialog.open = False
                    self.page.update()
                    
                    show_snack(self.page, f"Invalid file format: {file_path.name}", ft.Colors.RED_400)
                    self.page.update()
                    return
                
                # Get spectra ID mapping
                spectra_mapping = await self.project.get_spectra_idlist(
                    spectra_file_id,
                    by=parser.spectra_id_field
                )
                logger.info(f'Matching to spectra_file with id: {spectra_file_id} by {parser.spectra_id_field}')
                logger.debug(spectra_mapping)
                
                # Import identifications in batches
                batch_size = _config.identification_batch_size
                batch_count = 0
                file_ident_count = 0
                async for batch in parser.parse_batch(batch_size=batch_size):
                    logger.warn(batch)
                    logger.warn(spectra_mapping)
                    batch = pd.merge(
                        batch,
                        pd.json_normalize(spectra_mapping),
                        on=parser.spectra_id_field,
                        how='inner'
                    )
                    # Add tool_id, ident_file_id
                    batch['tool_id'] = tool.id
                    batch['ident_file_id'] = ident_file_id
                    logger.debug(batch)
                    logger.debug(batch.columns)

                    if len(batch) > 0:
                        await self.project.add_identifications_batch(batch)
                        batch_count += 1
                        file_ident_count += len(batch)
                        total_identifications += len(batch)

                    progress_details.value = f"Imported {file_ident_count} identifications (batch {batch_count})..."
                    progress_details.update()

                # Save proteins collected during parsing
                if collect_proteins and parser.contain_proteins and parser.proteins:
                    proteins_df = pd.DataFrame([
                        p.to_dict() for p in parser.proteins.values()
                    ])
                    # Apply is_uniprot flag
                    proteins_df['is_uniprot'] = 1 if is_uniprot_proteins else 0
                    await self._save_proteins_batch(proteins_df)
                    logger.info(f"Saved {len(parser.proteins)} proteins from identification file")

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
            show_snack(self.page, f"Successfully imported {total_identifications} identifications from {total_files} file(s)", ft.Colors.GREEN_400)
            self.page.update()

            # Call completion callback
            if self.on_complete_callback:
                await self.on_complete_callback()

        except Exception as ex:
            logger.exception(ex)
            import traceback
            error_details = traceback.format_exc()
            logger.debug(f"Import error: {error_details}")

            progress_dialog.open = False
            self.page.update()

            show_snack(self.page, f"Import error: {str(ex)}", ft.Colors.RED_400)
            self.page.update()

    async def _save_proteins_batch(self, proteins_df: pd.DataFrame) -> None:
        """
        Save proteins to DB using ON CONFLICT(id) DO NOTHING semantics.
        
        Unlike project.add_proteins_batch() which uses INSERT OR REPLACE,
        here we must NOT overwrite existing proteins (they may have richer
        data from FASTA import or UniProt enrichment).
        """
        rows = []
        for _, row in proteins_df.iterrows():
            rows.append((
                str(row['id']),
                1 if row.get('is_uniprot', False) else 0,
                row.get('fasta_name'),
                row.get('sequence'),
                row.get('gene'),
                row.get('name'),
                row.get('taxon_id'),
                row.get('organism_name'),
            ))
        
        if rows:
            await self.project._executemany(
                """INSERT INTO protein
                   (id, is_uniprot, fasta_name, sequence, gene, name, taxon_id, organism_name)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO NOTHING""",
                rows
            )
            await self.project.save()

    async def import_identification_files_stacked(
        self,
        entries: list[dict],
        tool_id: int,
    ):
        """
        Import identifications from a stacked file for multiple samples.
        
        Args:
            entries: list of dicts, each with:
                - file_path: Path
                - project_sample_name: str  (name of existing Sample in DB)
                - file_sample_id: str       (value in selection_field column)
                - selection_field: str | None
            tool_id: Tool ID
        """
        # Show progress dialog
        progress_text = ft.Text("Preparing stacked import...")
        progress_bar = ft.ProgressBar(value=0)
        progress_details = ft.Text("", size=11, color=ft.Colors.GREY_600)
        
        progress_dialog = ft.AlertDialog(
            title=ft.Text("Importing Stacked Identifications"),
            content=ft.Column([
                progress_text, progress_bar,
                ft.Container(height=5), progress_details
            ], tight=True, width=400),
            modal=True
        )
        self.page.overlay.append(progress_dialog)
        progress_dialog.open = True
        self.page.update()
        
        try:
            tool = await self.project.get_tool(tool_id)
            if not tool:
                raise ValueError(f"Tool id={tool_id} not found")
            
            parser_class = registry.get_parser(tool.parser, "identification")
            total = len(entries)
            total_identifications = 0
            
            for i, entry in enumerate(entries):
                file_path = entry['file_path']
                project_sample_name = entry['project_sample_name']
                file_sample_id = entry['file_sample_id']
                selection_field = entry['selection_field']
                
                progress_text.value = f"Processing {project_sample_name} ({i+1}/{total})..."
                progress_bar.value = i / total
                progress_text.update()
                progress_bar.update()
                
                # Find sample by name
                sample = await self.project.get_sample_by_name(project_sample_name)
                if not sample:
                    raise ValueError(f"Sample '{project_sample_name}' not found in project")
                
                # Get spectra files for sample
                spectra_files = await self.project.get_spectra_files(sample_id=sample.id)
                if len(spectra_files) == 0:
                    raise ValueError(f"No spectra files for sample '{project_sample_name}'")
                
                spectra_file_id = spectra_files.iloc[0]['id']
                
                # Create identification_file record with stacked metadata
                ident_file_id = await self.project.add_identification_file(
                    spectra_file_id=int(spectra_file_id),
                    tool_id=tool.id,
                    file_path=str(file_path),
                    selection_field=selection_field,
                    selection_field_value=file_sample_id,
                )
                
                # Parse file, filter by file_sample_id
                parser = parser_class(str(file_path))
                is_valid = await parser.validate()
                if not is_valid:
                    raise ValueError(f"Invalid file format: {file_path.name}")
                
                # Get spectra mapping
                spectra_mapping = await self.project.get_spectra_idlist(
                    spectra_file_id, by=parser.spectra_id_field
                )
                
                effective_field = selection_field or getattr(parser_class, 'sample_id_column', None)
                
                batch_size = _config.identification_batch_size
                file_ident_count = 0
                
                async for batch in parser.parse_batch(batch_size=batch_size):
                    # Filter: keep only rows matching this sample
                    if effective_field and effective_field in batch.columns:
                        batch = batch[batch[effective_field].astype(str) == str(file_sample_id)]
                    
                    if len(batch) == 0:
                        continue
                    
                    # Drop sample_id column before merge (not needed in DB)
                    if effective_field and effective_field in batch.columns:
                        batch = batch.drop(columns=[effective_field])
                    
                    merged = pd.merge(
                        batch,
                        pd.json_normalize(spectra_mapping),
                        on=parser.spectra_id_field,
                        how='inner',
                    )
                    merged['tool_id'] = tool.id
                    merged['ident_file_id'] = ident_file_id
                    
                    if len(merged) > 0:
                        await self.project.add_identifications_batch(merged)
                        file_ident_count += len(merged)
                        total_identifications += len(merged)
                    
                    progress_details.value = f"{project_sample_name}: {file_ident_count} identifications..."
                    progress_details.update()
            
            # Complete
            progress_bar.value = 1.0
            progress_text.value = "Import complete!"
            progress_details.value = f"Total: {total_identifications} identifications from {total} sample(s)"
            progress_text.update()
            progress_bar.update()
            progress_details.update()
            
            import asyncio
            await asyncio.sleep(1)
            progress_dialog.open = False
            self.page.update()
            
            show_snack(
                self.page,
                f"Successfully imported {total_identifications} identifications for {total} sample(s)",
                ft.Colors.GREEN_400
            )
            self.page.update()
            
            if self.on_complete_callback:
                await self.on_complete_callback()
        
        except Exception as ex:
            logger.exception(ex)
            progress_dialog.open = False
            self.page.update()
            show_snack(self.page, f"Import error: {str(ex)}", ft.Colors.RED_400)
            self.page.update()
