"""Peptides tab - manage peptide identifications and settings."""

import flet as ft
import pandas as pd
import numpy as np
import base64
from pathlib import Path

from api.project.project import Project
from api.inputs.proteins.fasta import FastaParser
from api.peptides.matching import select_preferred_identifications
from api.spectra.plot_matches import plot_ion_match
from api.spectra.ion_match import IonMatchParameters, match_predictions
import plotly.io as pio


class PeptidesTab(ft.Container):
    """
    Peptides tab for:
    - Loading protein sequence libraries (FASTA)
    - Configuring tool-specific identification settings
    - Configuring ion matching settings
    - Calculating ion coverage for identifications
    - Selecting preferred identifications
    - Searching and viewing identifications with ion match plots
    """
    
    def __init__(self, project: Project):
        super().__init__()
        print("PeptidesTab init...")
        self.project = project
        self.expand = True
        self.padding = 0
        
        # UI state
        self._updating = False
        self.tools_list = []  # List of Tool dataclasses
        self.tool_settings_controls = {}  # tool_id -> dict of controls
        
        # Build content immediately
        self.content = self._build_content()
    
    def _build_content(self):
        """Build the tab content."""
        # Section 1: FASTA loading
        fasta_section = self._build_fasta_section()
        
        # Section 2: Tool settings
        tools_section = self._build_tools_settings_section()
        
        # Section 3: Ion settings
        ion_section = self._build_ion_settings_section()
        
        # Section 4: Matching
        matching_section = self._build_matching_section()
        
        # Section 5: Search and view
        search_section = self._build_search_section()
        
        # Main layout
        return ft.Column([
                fasta_section,
                ft.Container(height=10),
                tools_section,
                ft.Container(height=10),
                ion_section,
                ft.Container(height=10),
                matching_section,
                ft.Container(height=10),
                search_section
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )
    
    def did_mount(self):
        """Called when control is added to page - load initial data."""
        print("PeptidesTab did_mount called")
        self.page.run_task(self._load_initial_data)
    
    async def _load_initial_data(self):
        """Load all initial data."""
        print("Loading peptides tab initial data...")
        try:
            await self.refresh_tools()
            await self.load_ion_settings()
            await self.refresh_search_filters()
            print("Peptides tab initial data loaded successfully")
        except Exception as ex:
            print(f"Error loading peptides tab initial data: {ex}")
            import traceback
            traceback.print_exc()
    
    # ========== Section 1: FASTA Loading ==========
    
    def _build_fasta_section(self):
        """Build FASTA loading section."""
        # File selection
        self.fasta_file_field = ft.TextField(
            label="FASTA file path",
            hint_text="Select FASTA file...",
            expand=True,
            read_only=True
        )
        
        self.fasta_browse_btn = ft.ElevatedButton(
            content=ft.Text("Browse"),
            icon=ft.Icons.FOLDER_OPEN,
            on_click=lambda e: self.page.run_task(self.browse_fasta_file, e)
        )
        
        # Options
        self.fasta_is_uniprot_cb = ft.Checkbox(
            label="Sequences in UniProt format",
            value=True
        )
        
        self.fasta_enrich_uniprot_cb = ft.Checkbox(
            label="Enrich data from UniProt",
            value=False
        )
        
        # Load button
        self.fasta_load_btn = ft.ElevatedButton(
            content=ft.Text("Load Sequences"),
            icon=ft.Icons.UPLOAD_FILE,
            on_click=lambda e: self.page.run_task(self.load_fasta_file, e)
        )
        
        # Status
        self.fasta_status_text = ft.Text(
            "No library loaded",
            italic=True,
            color=ft.Colors.GREY_600
        )
        
        return ft.Container(
            content=ft.Column([
                ft.Text("Protein Sequence Library", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([
                    self.fasta_file_field,
                    self.fasta_browse_btn
                ], spacing=10),
                self.fasta_is_uniprot_cb,
                self.fasta_enrich_uniprot_cb,
                ft.Container(height=5),
                self.fasta_load_btn,
                ft.Container(height=5),
                self.fasta_status_text
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY),
            border_radius=10
        )
    
    async def browse_fasta_file(self, e):
        """Open file picker for FASTA file."""
        try:
            result = await ft.FilePicker().pick_files(
                dialog_title="Select FASTA File",
                allowed_extensions=["fasta", "fa"],
                allow_multiple=False
            )
            
            if result and len(result) > 0:
                file_path = result[0].path
                self.fasta_file_field.value = file_path
                self.fasta_file_field.update()
                
        except Exception as ex:
            print(f"Error selecting FASTA file: {ex}")
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Error selecting file: {str(ex)}"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    async def load_fasta_file(self, e):
        """Load and import FASTA file into project."""
        # Validate file selection
        if not self.fasta_file_field.value:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text("Please select a FASTA file first"),
                bgcolor=ft.Colors.ORANGE_400
            )
            self.page.snack_bar.open = True
            self.page.update()
            return
        
        # Show progress dialog
        progress_text = ft.Text("Validating FASTA file...")
        progress_bar = ft.ProgressBar()
        progress_details = ft.Text("", size=11, color=ft.Colors.GREY_600)
        
        progress_dialog = ft.AlertDialog(
            title=ft.Text("Loading Protein Sequences"),
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
            file_path = self.fasta_file_field.value
            
            # Create parser
            parser = FastaParser(
                file_path=file_path,
                is_uniprot=self.fasta_is_uniprot_cb.value,
                enrich_from_uniprot=self.fasta_enrich_uniprot_cb.value
            )
            
            # Validate
            is_valid = await parser.validate()
            if not is_valid:
                progress_dialog.open = False
                self.page.update()
                
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text("Invalid FASTA file format"),
                    bgcolor=ft.Colors.RED_400
                )
                self.page.snack_bar.open = True
                self.page.update()
                return
            
            # Parse and import
            progress_text.value = "Importing protein sequences..."
            progress_bar.value = None  # Indeterminate
            progress_text.update()
            progress_bar.update()
            
            total_proteins = 0
            batch_count = 0
            
            async for batch in parser.parse_batch(batch_size=100):
                # Enrich if requested
                if self.fasta_enrich_uniprot_cb.value:
                    batch = await parser.enrich_with_uniprot(batch)
                
                # Add to project
                await self.project.add_proteins_batch(batch)
                
                batch_count += 1
                total_proteins += len(batch)
                
                progress_details.value = f"Loaded {total_proteins} proteins (batch {batch_count})..."
                progress_details.update()
            
            # Complete
            progress_text.value = "Import complete!"
            progress_bar.value = 1.0
            progress_details.value = f"Total: {total_proteins} proteins"
            progress_text.update()
            progress_bar.update()
            progress_details.update()
            
            # Update status
            file_name = Path(file_path).name
            self.fasta_status_text.value = f"Loaded: {total_proteins:,} proteins from {file_name}"
            self.fasta_status_text.color = ft.Colors.GREEN_700
            self.fasta_status_text.italic = False
            
            # Close dialog after delay
            import asyncio
            await asyncio.sleep(1)
            progress_dialog.open = False
            self.page.update()
            
            # Show success
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Successfully loaded {total_proteins:,} proteins"),
                bgcolor=ft.Colors.GREEN_400
            )
            self.page.snack_bar.open = True
            self.page.update()
            
        except Exception as ex:
            import traceback
            error_details = traceback.format_exc()
            print(f"FASTA import error: {error_details}")
            
            progress_dialog.open = False
            self.page.update()
            
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Import error: {str(ex)}"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    # ========== Section 2: Tool Settings ==========
    
    def _build_tools_settings_section(self):
        """Build tool settings section."""
        self.tools_settings_container = ft.Column(spacing=10)
        
        return ft.Container(
            content=ft.Column([
                ft.Text("Tool Settings", size=18, weight=ft.FontWeight.BOLD),
                self.tools_settings_container
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY),
            border_radius=10
        )
    
    async def refresh_tools(self):
        """Refresh tools list and create settings controls."""
        print("Refreshing tools for peptides tab...")
        
        try:
            tools = await self.project.get_tools()
            self.tools_list = tools
            
            # Clear existing controls
            self.tools_settings_container.controls.clear()
            self.tool_settings_controls.clear()
            
            if not tools:
                self.tools_settings_container.controls.append(
                    ft.Text(
                        "No tools configured. Add tools in the Samples tab.",
                        italic=True,
                        color=ft.Colors.GREY_600
                    )
                )
            else:
                for tool in tools:
                    controls = self._create_tool_settings_controls(tool)
                    self.tool_settings_controls[tool.id] = controls
                    
                    # Create container for this tool
                    tool_container = ft.Container(
                        content=ft.Column([
                            ft.Text(tool.name, size=16, weight=ft.FontWeight.BOLD),
                            ft.Row([
                                controls['max_ppm'],
                                controls['min_score'],
                                controls['min_ion_intensity_coverage']
                            ], spacing=10),
                            controls['use_protein_from_file'],
                            ft.Row([
                                controls['min_protein_identity'],
                                controls['denovo_correction']
                            ], spacing=10)
                        ], spacing=10),
                        padding=15,
                        border=ft.border.all(1, ft.Colors.BLUE_200),
                        border_radius=8,
                        bgcolor=ft.Colors.BLUE_50
                    )
                    
                    self.tools_settings_container.controls.append(tool_container)
            
            print(f"Tools loaded: {len(tools)}")
            self.tools_settings_container.update()
            
        except Exception as ex:
            print(f"Error refreshing tools: {ex}")
            import traceback
            traceback.print_exc()
    
    def _create_tool_settings_controls(self, tool) -> dict:
        """Create settings controls for a tool."""
        # Load existing settings or use defaults
        settings = tool.settings or {}
        
        controls = {
            'max_ppm': ft.TextField(
                label="Max PPM",
                value=str(settings.get('max_ppm', 50)),
                width=150,
                keyboard_type=ft.KeyboardType.NUMBER
            ),
            'min_score': ft.TextField(
                label="Min Score",
                value=str(settings.get('min_score', 0.8)),
                width=150,
                keyboard_type=ft.KeyboardType.NUMBER
            ),
            'min_ion_intensity_coverage': ft.TextField(
                label="Min Ion Intensity Coverage (%)",
                value=str(settings.get('min_ion_intensity_coverage', 25)),
                width=250,
                keyboard_type=ft.KeyboardType.NUMBER
            ),
            'use_protein_from_file': ft.Checkbox(
                label="Use protein identification from file",
                value=settings.get('use_protein_from_file', False)
            ),
            'min_protein_identity': ft.TextField(
                label="Min Protein Identity",
                value=str(settings.get('min_protein_identity', 0.75)),
                width=180,
                keyboard_type=ft.KeyboardType.NUMBER
            ),
            'denovo_correction': ft.Checkbox(
                label="DeNovo seq correction with search",
                value=settings.get('denovo_correction', False)
            )
        }
        
        return controls
    
    def _validate_tool_settings(self, tool_id: int) -> tuple[bool, str | None]:
        """Validate tool settings."""
        controls = self.tool_settings_controls.get(tool_id)
        if not controls:
            return False, "Tool controls not found"
        
        try:
            # Validate max_ppm
            max_ppm = float(controls['max_ppm'].value)
            if max_ppm <= 0:
                return False, "Max PPM must be greater than 0"
            
            # Validate min_score
            min_score = float(controls['min_score'].value)
            if not (0 <= min_score <= 1):
                return False, "Min Score must be between 0 and 1"
            
            # Validate min_ion_intensity_coverage
            min_coverage = float(controls['min_ion_intensity_coverage'].value)
            if not (0 <= min_coverage <= 100):
                return False, "Min Ion Intensity Coverage must be between 0 and 100"
            
            # Validate min_protein_identity
            min_identity = float(controls['min_protein_identity'].value)
            if not (0 <= min_identity <= 100):
                return False, "Min Protein Identity must be between 0 and 100"
            
            return True, None
            
        except ValueError as e:
            return False, f"Invalid numeric value: {str(e)}"
    
    async def save_tool_settings(self, tool_id: int):
        """Save tool settings to database."""
        controls = self.tool_settings_controls.get(tool_id)
        if not controls:
            raise ValueError(f"No controls found for tool {tool_id}")
        
        # Validate
        is_valid, error_msg = self._validate_tool_settings(tool_id)
        if not is_valid:
            raise ValueError(error_msg)
        
        # Get tool
        tool = await self.project.get_tool(tool_id)
        if not tool:
            raise ValueError(f"Tool {tool_id} not found")
        
        # Build settings dict
        settings = {
            'max_ppm': float(controls['max_ppm'].value),
            'min_score': float(controls['min_score'].value),
            'min_ion_intensity_coverage': float(controls['min_ion_intensity_coverage'].value),
            'use_protein_from_file': controls['use_protein_from_file'].value,
            'min_protein_identity': float(controls['min_protein_identity'].value),
            'denovo_correction': controls['denovo_correction'].value
        }
        
        # Update tool
        tool.settings = settings
        await self.project.update_tool(tool)
        
        print(f"Saved settings for tool {tool.name}: {settings}")
    
    # ========== Section 3: Ion Settings ==========
    
    def _build_ion_settings_section(self):
        """Build ion matching settings section."""
        # Ion types checkboxes
        self.ion_type_a_cb = ft.Checkbox(label="a", value=False)
        self.ion_type_b_cb = ft.Checkbox(label="b", value=True)
        self.ion_type_c_cb = ft.Checkbox(label="c", value=False)
        self.ion_type_x_cb = ft.Checkbox(label="x", value=False)
        self.ion_type_y_cb = ft.Checkbox(label="y", value=True)
        self.ion_type_z_cb = ft.Checkbox(label="z", value=False)
        
        # Losses checkboxes
        self.water_loss_cb = ft.Checkbox(
            label="Water loss (H₂O)",
            value=False
        )
        self.nh3_loss_cb = ft.Checkbox(
            label="Ammonia loss (NH₃)",
            value=False
        )
        
        # PPM threshold
        self.ion_ppm_threshold_field = ft.TextField(
            label="PPM Threshold",
            value="20",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        # Fragment charges
        self.fragment_charges_field = ft.TextField(
            label="Fragment Charges (comma-separated)",
            value="1,2",
            hint_text="e.g., 1,2,3",
            width=250
        )
        
        # Calculate coverage button
        self.calc_coverage_btn = ft.ElevatedButton(
            content=ft.Text("Calculate Ion Coverage"),
            icon=ft.Icons.CALCULATE,
            on_click=lambda e: self.page.run_task(self.calculate_ion_coverage, e)
        )
        
        return ft.Container(
            content=ft.Column([
                ft.Text("Ion Matching Settings", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.Text("Ion Types:", weight=ft.FontWeight.W_500),
                    self.ion_type_a_cb,
                    self.ion_type_b_cb,
                    self.ion_type_c_cb,
                    self.ion_type_x_cb,
                    self.ion_type_y_cb,
                    self.ion_type_z_cb
                ], spacing=15),
                ft.Row([
                    ft.Text("Losses:", weight=ft.FontWeight.W_500),
                    self.water_loss_cb,
                    self.nh3_loss_cb
                ], spacing=15),
                ft.Row([
                    self.ion_ppm_threshold_field,
                    self.fragment_charges_field
                ], spacing=10),
                ft.Container(height=5),
                self.calc_coverage_btn
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY),
            border_radius=10
        )
    
    async def load_ion_settings(self):
        """Load ion matching settings from project."""
        print("Loading ion settings...")
        
        try:
            # Load settings
            ion_types_str = await self.project.get_setting('ion_types', 'b,y')
            water_loss = await self.project.get_setting('water_loss', '0')
            nh3_loss = await self.project.get_setting('nh3_loss', '0')
            ppm_threshold = await self.project.get_setting('ion_ppm_threshold', '20')
            fragment_charges = await self.project.get_setting('fragment_charges', '1,2')
            
            # Parse ion types
            ion_types = ion_types_str.split(',') if ion_types_str else []
            
            # Update checkboxes
            self.ion_type_a_cb.value = 'a' in ion_types
            self.ion_type_b_cb.value = 'b' in ion_types
            self.ion_type_c_cb.value = 'c' in ion_types
            self.ion_type_x_cb.value = 'x' in ion_types
            self.ion_type_y_cb.value = 'y' in ion_types
            self.ion_type_z_cb.value = 'z' in ion_types
            
            self.water_loss_cb.value = water_loss == '1'
            self.nh3_loss_cb.value = nh3_loss == '1'
            self.ion_ppm_threshold_field.value = ppm_threshold
            self.fragment_charges_field.value = fragment_charges
            
            print(f"Ion settings loaded: types={ion_types}, water={water_loss}, nh3={nh3_loss}, ppm={ppm_threshold}, charges={fragment_charges}")
            
        except Exception as ex:
            print(f"Error loading ion settings: {ex}")
            import traceback
            traceback.print_exc()
    
    async def save_ion_settings(self):
        """Save ion matching settings to project."""
        # Collect selected ion types
        selected_types = []
        if self.ion_type_a_cb.value:
            selected_types.append('a')
        if self.ion_type_b_cb.value:
            selected_types.append('b')
        if self.ion_type_c_cb.value:
            selected_types.append('c')
        if self.ion_type_x_cb.value:
            selected_types.append('x')
        if self.ion_type_y_cb.value:
            selected_types.append('y')
        if self.ion_type_z_cb.value:
            selected_types.append('z')
        
        # Validate
        if not selected_types:
            raise ValueError("At least one ion type must be selected")
        
        ppm_threshold = float(self.ion_ppm_threshold_field.value)
        if ppm_threshold <= 0:
            raise ValueError("PPM threshold must be greater than 0")
        
        # Validate charges
        charges_str = self.fragment_charges_field.value.strip()
        if not charges_str:
            raise ValueError("Fragment charges cannot be empty")
        
        # Save settings
        ion_types_str = ','.join(selected_types)
        await self.project.set_setting('ion_types', ion_types_str)
        await self.project.set_setting('water_loss', '1' if self.water_loss_cb.value else '0')
        await self.project.set_setting('nh3_loss', '1' if self.nh3_loss_cb.value else '0')
        await self.project.set_setting('ion_ppm_threshold', str(ppm_threshold))
        await self.project.set_setting('fragment_charges', charges_str)
        
        print(f"Saved ion settings: {ion_types_str}, water={self.water_loss_cb.value}, nh3={self.nh3_loss_cb.value}, ppm={ppm_threshold}, charges={charges_str}")
    
    async def calculate_ion_coverage(self, e):
        """Calculate ion coverage for all identifications."""
        # Show confirmation dialog
        async def on_confirm_all(e):
            confirm_dialog.open = False
            self.page.update()
            await self._run_coverage_calculation(recalculate_all=True)
        
        async def on_confirm_missing(e):
            confirm_dialog.open = False
            self.page.update()
            await self._run_coverage_calculation(recalculate_all=False)
        
        def on_cancel(e):
            confirm_dialog.open = False
            self.page.update()
        
        confirm_dialog = ft.AlertDialog(
            title=ft.Text("Calculate Ion Coverage"),
            content=ft.Column([
                ft.Text("Calculate intensity coverage for identifications:"),
                ft.Container(height=10),
                ft.Text("This will use the current ion matching settings.", size=11, italic=True, color=ft.Colors.GREY_600)
            ], tight=True, width=400),
            actions=[
                ft.TextButton(
                    content="Cancel",
                    on_click=on_cancel
                ),
                ft.ElevatedButton(
                    content=ft.Text("Only Missing"),
                    icon=ft.Icons.PLAYLIST_ADD,
                    on_click=lambda e: self.page.run_task(on_confirm_missing, e)
                ),
                ft.ElevatedButton(
                    content=ft.Text("All Identifications"),
                    icon=ft.Icons.REFRESH,
                    on_click=lambda e: self.page.run_task(on_confirm_all, e)
                )
            ]
        )
        
        self.page.overlay.append(confirm_dialog)
        confirm_dialog.open = True
        self.page.update()
    
    async def _run_coverage_calculation(self, recalculate_all: bool):
        """Run the actual coverage calculation."""
        try:
            # Save ion settings first
            await self.save_ion_settings()
            
            # Get ion settings
            selected_types = []
            if self.ion_type_a_cb.value:
                selected_types.append('a')
            if self.ion_type_b_cb.value:
                selected_types.append('b')
            if self.ion_type_c_cb.value:
                selected_types.append('c')
            if self.ion_type_x_cb.value:
                selected_types.append('x')
            if self.ion_type_y_cb.value:
                selected_types.append('y')
            if self.ion_type_z_cb.value:
                selected_types.append('z')
            
            # Parse charges
            charges_str = self.fragment_charges_field.value.strip()
            try:
                charges = [int(c.strip()) for c in charges_str.split(',')]
            except ValueError:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text("Invalid charges format. Use comma-separated integers (e.g., 1,2)"),
                    bgcolor=ft.Colors.ORANGE_400
                )
                self.page.snack_bar.open = True
                self.page.update()
                return
            
            ppm_threshold = float(self.ion_ppm_threshold_field.value)
            
            # Create IonMatchParameters
            params = IonMatchParameters(
                ions=selected_types,
                tolerance=ppm_threshold,
                mode='largest',
                water_loss=self.water_loss_cb.value,
                ammonia_loss=self.nh3_loss_cb.value
            )
            
            # Get identifications to process
            if recalculate_all:
                query = "SELECT * FROM identification ORDER BY id"
            else:
                query = "SELECT * FROM identification WHERE intensity_coverage IS NULL ORDER BY id"
            
            identifications_df = await self.project.execute_query_df(query)
            
            if len(identifications_df) == 0:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text("No identifications to process"),
                    bgcolor=ft.Colors.BLUE_400
                )
                self.page.snack_bar.open = True
                self.page.update()
                return
            
            # Show progress dialog
            progress_text = ft.Text("Calculating coverage...")
            progress_bar = ft.ProgressBar(value=0)
            progress_details = ft.Text("", size=11, color=ft.Colors.GREY_600)
            
            progress_dialog = ft.AlertDialog(
                title=ft.Text("Calculating Ion Coverage"),
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
            
            total = len(identifications_df)
            processed = 0
            
            # Process each identification
            for idx, ident in identifications_df.iterrows():
                try:
                    # Get spectrum
                    spectrum = await self.project.get_spectrum_full(ident['spectre_id'])
                    
                    # Determine charge to use
                    charge_to_use = spectrum.get('charge') if spectrum.get('charge') else charges[0]
                    
                    # Match predictions
                    result = match_predictions(
                        params=params,
                        mz=spectrum['mz_array'].tolist(),
                        intensity=spectrum['intensity_array'].tolist(),
                        charges=charge_to_use,
                        sequence=ident['sequence']
                    )
                    
                    # Update coverage
                    await self.project.update_identification_coverage(
                        ident['id'],
                        result.intensity_percent
                    )
                    
                    processed += 1
                    
                    # Update progress every 10 identifications
                    if processed % 10 == 0 or processed == total:
                        progress_bar.value = processed / total
                        progress_details.value = f"Processed {processed}/{total} identifications..."
                        progress_bar.update()
                        progress_details.update()
                        
                except Exception as ex:
                    print(f"Error processing identification {ident['id']}: {ex}")
                    raise
                    # Continue with next
            
            # Save all updates
            await self.project.save()
            
            # Complete
            progress_text.value = "Calculation complete!"
            progress_bar.value = 1.0
            progress_details.value = f"Processed {processed} identifications"
            progress_text.update()
            progress_bar.update()
            progress_details.update()
            
            # Close after delay
            import asyncio
            await asyncio.sleep(1)
            progress_dialog.open = False
            self.page.update()
            
            # Show success
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Successfully calculated coverage for {processed} identifications"),
                bgcolor=ft.Colors.GREEN_400
            )
            self.page.snack_bar.open = True
            self.page.update()
            
        except Exception as ex:
            import traceback
            error_details = traceback.format_exc()
            print(f"Coverage calculation error: {error_details}")
            
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Error: {str(ex)}"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    # ========== Section 4: Matching ==========
    
    def _build_matching_section(self):
        """Build preferred identification selection section."""
        # Selection criterion radio buttons
        self.selection_criterion_group = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="ppm", label="PPM error"),
                ft.Radio(value="intensity", label="Intensity coverage")
            ]),
            value="intensity"
        )
        
        # Run button
        self.run_matching_btn = ft.ElevatedButton(
            content=ft.Text("Run Identification Matching"),
            icon=ft.Icons.PLAY_ARROW,
            on_click=lambda e: self.page.run_task(self.run_identification_matching, e)
        )
        
        return ft.Container(
            content=ft.Column([
                ft.Text("Preferred Identification Selection", size=18, weight=ft.FontWeight.BOLD),
                ft.Text("Selection Criterion:", weight=ft.FontWeight.W_500),
                self.selection_criterion_group,
                ft.Container(height=10),
                self.run_matching_btn
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY),
            border_radius=10
        )
    
    async def run_identification_matching(self, e):
        """Run identification matching process."""
        try:
            # Validate and save all settings
            print("Validating and saving settings...")
            
            # Validate and save tool settings
            for tool_id in self.tool_settings_controls.keys():
                is_valid, error_msg = self._validate_tool_settings(tool_id)
                if not is_valid:
                    print('not valid!', error_msg)
                    self.page.snack_bar = ft.SnackBar(
                        content=ft.Text(f"Tool settings error: {error_msg}"),
                        bgcolor=ft.Colors.ORANGE_400
                    )
                    self.page.snack_bar.open = True
                    self.page.update()
                    return
                
                await self.save_tool_settings(tool_id)
            
            # Save ion settings
            await self.save_ion_settings()
            
            # Prepare parameters
            criterion = self.selection_criterion_group.value
            
            # Ion settings
            selected_types = []
            if self.ion_type_a_cb.value:
                selected_types.append('a')
            if self.ion_type_b_cb.value:
                selected_types.append('b')
            if self.ion_type_c_cb.value:
                selected_types.append('c')
            if self.ion_type_x_cb.value:
                selected_types.append('x')
            if self.ion_type_y_cb.value:
                selected_types.append('y')
            if self.ion_type_z_cb.value:
                selected_types.append('z')
            
            ion_settings = {
                'ion_types': selected_types,
                'water_loss': self.water_loss_cb.value,
                'nh3_loss': self.nh3_loss_cb.value,
                'ppm_threshold': float(self.ion_ppm_threshold_field.value)
            }
            
            # Tool settings
            tool_settings = {}
            for tool_id, controls in self.tool_settings_controls.items():
                tool_settings[tool_id] = {
                    'max_ppm': float(controls['max_ppm'].value),
                    'min_score': float(controls['min_score'].value),
                    'min_ion_intensity_coverage': float(controls['min_ion_intensity_coverage'].value),
                    'use_protein_from_file': controls['use_protein_from_file'].value,
                    'min_protein_identity': float(controls['min_protein_identity'].value),
                    'denovo_correction': controls['denovo_correction'].value
                }
            
            # Show progress dialog
            progress_text = ft.Text("Processing identifications...")
            progress_bar = ft.ProgressBar()
            
            progress_dialog = ft.AlertDialog(
                title=ft.Text("Running Identification Matching"),
                content=ft.Column([
                    progress_text,
                    progress_bar,
                    ft.Text("This may take a while...", size=11, color=ft.Colors.GREY_600)
                ], tight=True, width=400),
                modal=True
            )
            
            self.page.overlay.append(progress_dialog)
            progress_dialog.open = True
            self.page.update()
            
            # Run matching
            print(f"Running matching with criterion={criterion}")
            count = await select_preferred_identifications(
                self.project,
                criterion,
                tool_settings
            )
            
            # Close progress
            progress_dialog.open = False
            self.page.update()
            
            # Show result
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Successfully processed {count} spectra"),
                bgcolor=ft.Colors.GREEN_400
            )
            self.page.snack_bar.open = True
            self.page.update()
            
        except ValueError as ex:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Validation error: {str(ex)}"),
                bgcolor=ft.Colors.ORANGE_400
            )
            self.page.snack_bar.open = True
            self.page.update()
            
        except Exception as ex:
            import traceback
            error_details = traceback.format_exc()
            print(f"Matching error: {error_details}")
            
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Error: {str(ex)}"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    # ========== Section 5: Search and View ==========
    
    def _build_search_section(self):
        """Build search and view identifications section."""
        # Filters
        self.search_sample_dropdown = ft.Dropdown(
            label="Sample",
            options=[ft.dropdown.Option(key="all", text="All Samples")],
            value="all",
            width=200
        )
        
        self.search_tool_dropdown = ft.Dropdown(
            label="Tool",
            options=[ft.dropdown.Option(key="all", text="All Tools")],
            value="all",
            width=200
        )
        
        self.search_by_dropdown = ft.Dropdown(
            label="Search by",
            options=[
                ft.dropdown.Option(key="seq_no", text="Sequence Number"),
                ft.dropdown.Option(key="scans", text="Scans"),
                ft.dropdown.Option(key="sequence", text="Sequence"),
                ft.dropdown.Option(key="canonical_sequence", text="Canonical Sequence")
            ],
            value="seq_no",
            width=200
        )
        
        self.search_value_field = ft.TextField(
            label="Search value",
            hint_text="Enter value...",
            expand=True,
            on_submit=lambda e: self.page.run_task(self.search_identifications, e)
        )
        
        self.search_btn = ft.ElevatedButton(
            content=ft.Text("Search"),
            icon=ft.Icons.SEARCH,
            on_click=lambda e: self.page.run_task(self.search_identifications, e)
        )
        
        # Results container
        self.results_container = ft.Container(
            content=ft.Column([
                ft.Text("No search performed yet", italic=True, color=ft.Colors.GREY_600)
            ]),
            padding=10,
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=5,
            height=300
        )
        
        # Plot container
        self.plot_container = ft.Container(
            content=ft.Column([
                ft.Text("Select an identification to view ion match", italic=True, color=ft.Colors.GREY_600)
            ]),
            padding=10,
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=5,
            height=450
        )
        
        return ft.Container(
            content=ft.Column([
                ft.Text("Search and View Identifications", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([
                    self.search_sample_dropdown,
                    self.search_tool_dropdown
                ], spacing=10),
                ft.Row([
                    self.search_by_dropdown,
                    self.search_value_field,
                    self.search_btn
                ], spacing=10),
                ft.Container(height=10),
                ft.Text("Results:", weight=ft.FontWeight.BOLD),
                self.results_container,
                ft.Container(height=10),
                ft.Text("Ion Match Visualization:", weight=ft.FontWeight.BOLD),
                self.plot_container
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY),
            border_radius=10
        )
    
    async def refresh_search_filters(self):
        """Refresh search filter dropdowns."""
        print("Refreshing search filters...")
        
        try:
            # Get samples and tools
            samples = await self.project.get_samples()
            tools = await self.project.get_tools()
            
            # Update sample dropdown
            self.search_sample_dropdown.options = [
                ft.dropdown.Option(key="all", text="All Samples")
            ] + [
                ft.dropdown.Option(key=str(s.id), text=s.name)
                for s in samples
            ]
            
            # Update tool dropdown
            self.search_tool_dropdown.options = [
                ft.dropdown.Option(key="all", text="All Tools")
            ] + [
                ft.dropdown.Option(key=str(t.id), text=t.name)
                for t in tools
            ]
            
            print(f"Search filters updated: {len(samples)} samples, {len(tools)} tools")
            
        except Exception as ex:
            print(f"Error refreshing search filters: {ex}")
            import traceback
            traceback.print_exc()
    
    async def search_identifications(self, e):
        """Search for identifications."""
        try:
            # Get parameters
            sample_id = None if self.search_sample_dropdown.value == "all" else int(self.search_sample_dropdown.value)
            tool_id = None if self.search_tool_dropdown.value == "all" else int(self.search_tool_dropdown.value)
            search_by = self.search_by_dropdown.value
            search_value = self.search_value_field.value
            
            # Build query
            query = """
                SELECT i.*, s.seq_no, s.scans, s.pepmass, s.rt, s.charge,
                       sam.name as sample_name, t.name as tool_name
                FROM identification i
                JOIN spectre s ON i.spectre_id = s.id
                JOIN spectre_file sf ON s.spectre_file_id = sf.id
                JOIN sample sam ON sf.sample_id = sam.id
                JOIN tool t ON i.tool_id = t.id
                WHERE 1=1
            """
            
            params = []
            
            # Add filters
            if sample_id:
                query += " AND sam.id = ?"
                params.append(sample_id)
            
            if tool_id:
                query += " AND t.id = ?"
                params.append(tool_id)
            
            if search_value:
                if search_by == "seq_no":
                    try:
                        query += " AND s.seq_no = ?"
                        params.append(int(search_value))
                    except ValueError:
                        self.search_value_field.error_text = "Must be a number"
                        self.search_value_field.update()
                        return
                elif search_by == "scans":
                    try:
                        query += " AND s.scans = ?"
                        params.append(int(search_value))
                    except ValueError:
                        self.search_value_field.error_text = "Must be a number"
                        self.search_value_field.update()
                        return
                elif search_by == "sequence":
                    query += " AND i.sequence LIKE ?"
                    params.append(f"%{search_value}%")
                elif search_by == "canonical_sequence":
                    query += " AND i.canonical_sequence LIKE ?"
                    params.append(f"%{search_value}%")
            
            query += " ORDER BY s.seq_no, i.score DESC LIMIT 100"
            
            # Execute query
            results_df = await self.project.execute_query_df(query, tuple(params))
            
            # Display results
            if len(results_df) == 0:
                self.results_container.content = ft.Column([
                    ft.Text("No results found", italic=True, color=ft.Colors.GREY_600)
                ])
            else:
                # Create table
                rows = []
                for idx, row in results_df.iterrows():
                    # Preferred icon
                    preferred_icon = ft.Icon(
                        ft.Icons.STAR,
                        color=ft.Colors.AMBER,
                        size=16
                    ) if row['is_preferred'] else ft.Container(width=16)
                    
                    # Truncate sequence for display
                    seq_display = row['sequence'][:20] + "..." if len(row['sequence']) > 20 else row['sequence']
                    
                    rows.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Container(
                                    content=ft.Text(str(row['seq_no']), size=12),
                                    width=60
                                ),
                                ft.Container(
                                    content=ft.Text(row['sample_name'], size=12),
                                    width=100
                                ),
                                ft.Container(
                                    content=ft.Text(row['tool_name'], size=12),
                                    width=120
                                ),
                                ft.Container(
                                    content=ft.Text(seq_display, size=12),
                                    width=200
                                ),
                                ft.Container(
                                    content=ft.Text(f"{row['score']:.2f}" if pd.notna(row['score']) else "N/A", size=12),
                                    width=60
                                ),
                                ft.Container(
                                    content=ft.Text(f"{row['ppm']:.2f}" if pd.notna(row['ppm']) else "N/A", size=12),
                                    width=60
                                ),
                                preferred_icon,
                                ft.IconButton(
                                    icon=ft.Icons.VISIBILITY,
                                    tooltip="View ion match",
                                    icon_size=16,
                                    on_click=lambda e, r=row.to_dict(): self.page.run_task(self.view_identification, e, r)
                                )
                            ], spacing=5),
                            padding=5,
                            border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.GREY_200))
                        )
                    )
                
                # Header row
                header = ft.Container(
                    content=ft.Row([
                        ft.Container(ft.Text("Seq#", weight=ft.FontWeight.BOLD, size=12), width=60),
                        ft.Container(ft.Text("Sample", weight=ft.FontWeight.BOLD, size=12), width=100),
                        ft.Container(ft.Text("Tool", weight=ft.FontWeight.BOLD, size=12), width=120),
                        ft.Container(ft.Text("Sequence", weight=ft.FontWeight.BOLD, size=12), width=200),
                        ft.Container(ft.Text("Score", weight=ft.FontWeight.BOLD, size=12), width=60),
                        ft.Container(ft.Text("PPM", weight=ft.FontWeight.BOLD, size=12), width=60),
                        ft.Container(ft.Text("Pref", weight=ft.FontWeight.BOLD, size=12), width=40),
                        ft.Container(ft.Text("View", weight=ft.FontWeight.BOLD, size=12), width=40)
                    ], spacing=5),
                    padding=5,
                    bgcolor=ft.Colors.GREY_100,
                    border=ft.border.only(bottom=ft.BorderSide(2, ft.Colors.GREY_400))
                )
                
                self.results_container.content = ft.Column([
                    ft.Text(f"Results ({len(results_df)} found):", weight=ft.FontWeight.BOLD),
                    ft.Column(
                        [header] + rows,
                        spacing=0,
                        scroll=ft.ScrollMode.AUTO,
                        height=250
                    )
                ], spacing=5)
            
            self.results_container.update()
            
            # Auto-view first result if exists
            if len(results_df) > 0:
                first_result = results_df.iloc[0].to_dict()
                await self.view_identification(None, first_result)
            
        except Exception as ex:
            import traceback
            error_details = traceback.format_exc()
            print(f"Search error: {error_details}")
            
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text(f"Search error: {str(ex)}"),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    async def view_identification(self, e, identification_row: dict):
        """View ion match plot for identification."""
        try:
            print(f"Viewing identification: {identification_row['id']}")
            
            # Get full spectrum data
            spectrum = await self.project.get_spectrum_full(identification_row['spectre_id'])
            
            # Get ion matching settings
            ion_types_str = await self.project.get_setting('ion_types', 'b,y')
            ion_types = ion_types_str.split(',') if ion_types_str else ['b', 'y']
            water_loss = (await self.project.get_setting('water_loss', '0')) == '1'
            nh3_loss = (await self.project.get_setting('nh3_loss', '0')) == '1'
            ppm_threshold = float(await self.project.get_setting('ion_ppm_threshold', '20'))
            
            # Generate plot
            fig = plot_ion_match(
                mz_array=spectrum['mz_array'],
                intensity_array=spectrum['intensity_array'],
                sequence=identification_row['sequence'],
                charge=spectrum.get('charge'),
                ion_types=ion_types,
                water_loss=water_loss,
                nh3_loss=nh3_loss,
                ppm_threshold=ppm_threshold
            )
            
            # Convert to image
            img_bytes = pio.to_image(fig, format='png', width=800, height=400)
            img_base64 = base64.b64encode(img_bytes).decode()
            
            # Update plot container
            self.plot_container.content = ft.Column([
                ft.Text(
                    f"Seq# {identification_row['seq_no']}: {identification_row['sequence']}",
                    weight=ft.FontWeight.BOLD,
                    size=14
                ),
                ft.Text(
                    f"Tool: {identification_row['tool_name']} | Score: {identification_row['score']:.2f} | PPM: {identification_row['ppm']:.2f}" if pd.notna(identification_row.get('score')) else f"Tool: {identification_row['tool_name']}",
                    size=11,
                    color=ft.Colors.GREY_700
                ),
                ft.Image(
                    src_base64=img_base64,
                    width=780,
                    height=400,
                    fit=ft.ImageFit.CONTAIN
                )
            ], spacing=5)
            
            self.plot_container.update()
            
        except Exception as ex:
            import traceback
            error_details = traceback.format_exc()
            print(f"Plot error: {error_details}")
            
            self.plot_container.content = ft.Column([
                ft.Text("Error generating plot", color=ft.Colors.RED_600, weight=ft.FontWeight.BOLD),
                ft.Text(str(ex), size=11, color=ft.Colors.RED_400)
            ])
            self.plot_container.update()
