"""Peptides tab - manage peptide identifications and settings."""

import flet as ft
import pandas as pd
import base64
from pathlib import Path

from dasmixer.api.project.project import Project
from dasmixer.api.inputs.proteins.fasta import FastaParser
from dasmixer.api.calculations.peptides.matching import select_preferred_identifications
from dasmixer.api.calculations.peptides.protein_map import map_proteins
from dasmixer.api.calculations.spectra.plot_matches import plot_ion_match
from dasmixer.api.calculations.spectra.ion_match import IonMatchParameters, match_predictions
from dasmixer.api.config import config as _config
from dasmixer.utils.ppm import calculate_ppm
import plotly.io as pio
from dasmixer.gui.utils import show_snack


class PeptidesTab(ft.Container):
    """Peptides tab - comprehensive peptide identification management."""
    
    def __init__(self, project: Project):
        super().__init__()
        print("PeptidesTab init...")
        self.project = project
        self.expand = True
        self.padding = 0
        
        # UI state
        self._updating = False
        self.tools_list = []
        self.tool_settings_controls = {}
        
        # Build content
        self.content = self._build_content()
    
    def _build_content(self):
        """Build the tab content."""
        return ft.Column([
                self._build_fasta_section(),
                ft.Container(height=10),
                self._build_tools_settings_section(),
                ft.Container(height=10),
                self._build_ion_settings_section(),
                ft.Container(height=10),
                self._build_matching_section(),
                ft.Container(height=10),
                self._build_search_section()
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            expand=True
        )
    
    def did_mount(self):
        """Load initial data."""
        print("PeptidesTab did_mount called")
        self.page.run_task(self._load_initial_data)
    
    async def _load_initial_data(self):
        """Load all initial data."""
        print("Loading peptides tab initial data...")
        try:
            await self.refresh_tools()
            await self.load_ion_settings()
            await self.load_blast_settings()
            await self.refresh_search_filters()
            print("Peptides tab initial data loaded")
        except Exception as ex:
            print(f"Error loading initial data: {ex}")
            import traceback
            traceback.print_exc()
    
    # FASTA and Protein Mapping Section
    
    def _build_fasta_section(self):
        """Build FASTA and protein mapping section."""
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
        
        self.fasta_is_uniprot_cb = ft.Checkbox(
            label="Sequences in UniProt format",
            value=True
        )
        
        self.fasta_enrich_uniprot_cb = ft.Checkbox(
            label="Enrich data from UniProt",
            value=False
        )
        
        self.fasta_load_btn = ft.ElevatedButton(
            content=ft.Text("Load Sequences"),
            icon=ft.Icons.UPLOAD_FILE,
            on_click=lambda e: self.page.run_task(self.load_fasta_file, e)
        )
        
        self.fasta_status_text = ft.Text(
            "No library loaded",
            italic=True,
            color=ft.Colors.GREY_600
        )
        
        # Protein mapping controls
        self.match_preferred_only_cb = ft.Checkbox(
            label="Match preferred only",
            value=False
        )
        
        self.blast_max_accepts_field = ft.TextField(
            label="BLAST Max Accepts",
            value="16",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        self.blast_max_rejects_field = ft.TextField(
            label="BLAST Max Rejects",
            value="5",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        self.match_proteins_btn = ft.ElevatedButton(
            content=ft.Text("Match Proteins to Identifications"),
            icon=ft.Icons.LINK,
            on_click=lambda e: self.page.run_task(self.match_proteins_to_identifications, e)
        )
        
        return ft.Container(
            content=ft.Column([
                ft.Text("Protein Sequence Library", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([self.fasta_file_field, self.fasta_browse_btn], spacing=10),
                self.fasta_is_uniprot_cb,
                self.fasta_enrich_uniprot_cb,
                ft.Container(height=5),
                self.fasta_load_btn,
                ft.Container(height=5),
                self.fasta_status_text,
                ft.Container(height=15),
                ft.Text("Protein Mapping Settings", size=16, weight=ft.FontWeight.BOLD),
                self.match_preferred_only_cb,
                ft.Row([self.blast_max_accepts_field, self.blast_max_rejects_field], spacing=10),
                ft.Container(height=5),
                self.match_proteins_btn
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY),
            border_radius=10
        )
    
    async def browse_fasta_file(self, e):
        """Open file picker."""
        try:
            result = await ft.FilePicker().pick_files(
                dialog_title="Select FASTA File",
                allowed_extensions=["fasta", "fa"],
                allow_multiple=False
            )
            
            if result and len(result) > 0:
                self.fasta_file_field.value = result[0].path
                self.fasta_file_field.update()
        except Exception as ex:
            print(f"Error: {ex}")
            show_snack(self.page, f"Error: {str(ex)}", ft.Colors.RED_400)
            self.page.update()
    
    async def load_fasta_file(self, e):
        """Load FASTA file."""
        if not self.fasta_file_field.value:
            show_snack(self.page, "Please select a FASTA file", ft.Colors.ORANGE_400)
            self.page.update()
            return
        
        progress_text = ft.Text("Validating...")
        progress_bar = ft.ProgressBar()
        progress_details = ft.Text("", size=11, color=ft.Colors.GREY_600)
        
        progress_dialog = ft.AlertDialog(
            title=ft.Text("Loading Protein Sequences"),
            content=ft.Column([progress_text, progress_bar, ft.Container(height=5), progress_details], tight=True, width=400),
            modal=True
        )
        
        self.page.overlay.append(progress_dialog)
        progress_dialog.open = True
        self.page.update()
        
        try:
            parser = FastaParser(
                file_path=self.fasta_file_field.value,
                is_uniprot=self.fasta_is_uniprot_cb.value,
                enrich_from_uniprot=self.fasta_enrich_uniprot_cb.value
            )
            
            if not await parser.validate():
                progress_dialog.open = False
                self.page.update()
                show_snack(self.page, "Invalid FASTA format", ft.Colors.RED_400)
                self.page.update()
                return
            
            progress_text.value = "Importing..."
            progress_bar.value = None
            progress_text.update()
            progress_bar.update()
            
            total = 0
            # Get batch size from config
            batch_size = _config.protein_mapping_batch_size
            async for batch in parser.parse_batch(batch_size=batch_size):
                if self.fasta_enrich_uniprot_cb.value:
                    batch = await parser.enrich_with_uniprot(batch)
                await self.project.add_proteins_batch(batch)
                total += len(batch)
                progress_details.value = f"Loaded {total} proteins..."
                progress_details.update()
            
            progress_text.value = "Complete!"
            progress_bar.value = 1.0
            progress_details.value = f"Total: {total} proteins"
            progress_text.update()
            progress_bar.update()
            progress_details.update()
            
            self.fasta_status_text.value = f"Loaded: {total:,} proteins from {Path(self.fasta_file_field.value).name}"
            self.fasta_status_text.color = ft.Colors.GREEN_700
            self.fasta_status_text.italic = False
            
            import asyncio
            await asyncio.sleep(1)
            progress_dialog.open = False
            self.page.update()
            
            show_snack(self.page, f"Loaded {total:,} proteins", ft.Colors.GREEN_400)
            self.page.update()
            
        except Exception as ex:
            import traceback
            print(f"Error: {traceback.format_exc()}")
            progress_dialog.open = False
            self.page.update()
            show_snack(self.page, f"Error: {str(ex)}", ft.Colors.RED_400)
            self.page.update()
    
    async def load_blast_settings(self):
        """Load BLAST settings."""
        try:
            max_accepts = await self.project.get_setting('max_blast_accept', '16')
            max_rejects = await self.project.get_setting('max_blast_reject', '5')
            self.blast_max_accepts_field.value = max_accepts
            self.blast_max_rejects_field.value = max_rejects
        except Exception as ex:
            print(f"Error loading BLAST settings: {ex}")
    
    async def save_blast_settings(self):
        """Save BLAST settings."""
        await self.project.set_setting('max_blast_accept', self.blast_max_accepts_field.value)
        await self.project.set_setting('max_blast_reject', self.blast_max_rejects_field.value)
    
    async def match_proteins_to_identifications(self, e):
        """Match proteins to identifications."""
        try:
            await self.save_blast_settings()
            
            tool_settings = {}
            for tool_id, controls in self.tool_settings_controls.items():
                tool_settings[tool_id] = {
                    'min_protein_identity': float(controls['min_protein_identity'].value)
                }
            
            if not tool_settings:
                show_snack(self.page, "No tools configured", ft.Colors.ORANGE_400)
                self.page.update()
                return
            
            await self.project.clear_peptide_matches()
            
            progress_text = ft.Text("Mapping...")
            progress_bar = ft.ProgressBar(value=0)
            progress_details = ft.Text("", size=11, color=ft.Colors.GREY_600)
            
            progress_dialog = ft.AlertDialog(
                title=ft.Text("Matching Proteins"),
                content=ft.Column([progress_text, progress_bar, ft.Container(height=5), progress_details], tight=True, width=400),
                modal=True
            )
            
            self.page.overlay.append(progress_dialog)
            progress_dialog.open = True
            self.page.update()
            
            total_matches = 0
            
            # Get batch size from config
            batch_size = _config.protein_mapping_batch_size
            async for matches_df, count, tool_id in map_proteins(
                self.project,
                tool_settings,
                only_prefered=self.match_preferred_only_cb.value,
                batch_size=batch_size
            ):
                await self.project.add_peptide_matches_batch(matches_df)
                total_matches += count
                progress_details.value = f"Mapped {total_matches} matches..."
                progress_details.update()
            
            await self.project.save()
            
            progress_text.value = "Complete!"
            progress_bar.value = 1.0
            progress_details.value = f"Total: {total_matches}"
            progress_text.update()
            progress_bar.update()
            progress_details.update()
            
            import asyncio
            await asyncio.sleep(1)
            progress_dialog.open = False
            self.page.update()
            
            show_snack(self.page, f"Mapped {total_matches} matches", ft.Colors.GREEN_400)
            self.page.update()
            
        except Exception as ex:
            import traceback
            print(f"Error: {traceback.format_exc()}")
            show_snack(self.page, f"Error: {str(ex)}", ft.Colors.RED_400)
            self.page.update()
    
    # Tool Settings Section
    
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
        """Refresh tools."""
        try:
            tools = await self.project.get_tools()
            self.tools_list = tools
            self.tools_settings_container.controls.clear()
            self.tool_settings_controls.clear()
            
            if not tools:
                self.tools_settings_container.controls.append(
                    ft.Text("No tools. Add in Samples tab.", italic=True, color=ft.Colors.GREY_600)
                )
            else:
                for tool in tools:
                    controls = self._create_tool_settings_controls(tool)
                    self.tool_settings_controls[tool.id] = controls
                    
                    self.tools_settings_container.controls.append(
                        ft.Container(
                            content=ft.Column([
                                ft.Text(tool.name, size=16, weight=ft.FontWeight.BOLD),
                                ft.Row([controls['max_ppm'], controls['min_score'], controls['min_ion_intensity_coverage']], spacing=10),
                                controls['use_protein_from_file'],
                                ft.Row([controls['min_protein_identity'], controls['denovo_correction']], spacing=10)
                            ], spacing=10),
                            padding=15,
                            border=ft.border.all(1, ft.Colors.BLUE_200),
                            border_radius=8,
                            bgcolor=ft.Colors.BLUE_50
                        )
                    )
            
            self.tools_settings_container.update()
        except Exception as ex:
            print(f"Error refreshing tools: {ex}")
    
    def _create_tool_settings_controls(self, tool) -> dict:
        """Create controls for tool."""
        settings = tool.settings or {}
        return {
            'max_ppm': ft.TextField(label="Max PPM", value=str(settings.get('max_ppm', 50)), width=150, keyboard_type=ft.KeyboardType.NUMBER),
            'min_score': ft.TextField(label="Min Score", value=str(settings.get('min_score', 0.8)), width=150, keyboard_type=ft.KeyboardType.NUMBER),
            'min_ion_intensity_coverage': ft.TextField(label="Min Ion Intensity Coverage (%)", value=str(settings.get('min_ion_intensity_coverage', 25)), width=250, keyboard_type=ft.KeyboardType.NUMBER),
            'use_protein_from_file': ft.Checkbox(label="Use protein identification from file", value=settings.get('use_protein_from_file', False)),
            'min_protein_identity': ft.TextField(label="Min Protein Identity", value=str(settings.get('min_protein_identity', 0.75)), width=180, keyboard_type=ft.KeyboardType.NUMBER),
            'denovo_correction': ft.Checkbox(label="DeNovo seq correction with search", value=settings.get('denovo_correction', False))
        }
    
    def _validate_tool_settings(self, tool_id: int) -> tuple[bool, str | None]:
        """Validate tool settings."""
        controls = self.tool_settings_controls.get(tool_id)
        if not controls:
            return False, "Tool controls not found"
        try:
            if float(controls['max_ppm'].value) < 0:
                return False, "Max PPM > 0"
            if not (0 <= float(controls['min_score'].value) <= 1):
                return False, "Min Score 0-1"
            if not (0 <= float(controls['min_ion_intensity_coverage'].value) <= 100):
                return False, "Coverage 0-100"
            if not (0 <= float(controls['min_protein_identity'].value) <= 1):
                return False, "Identity 0-1"
            return True, None
        except ValueError as e:
            return False, f"Invalid number: {str(e)}"
    
    async def save_tool_settings(self, tool_id: int):
        """Save tool settings."""
        controls = self.tool_settings_controls.get(tool_id)
        if not controls:
            raise ValueError(f"No controls for tool {tool_id}")
        
        is_valid, error_msg = self._validate_tool_settings(tool_id)
        if not is_valid:
            raise ValueError(error_msg)
        
        tool = await self.project.get_tool(tool_id)
        if not tool:
            raise ValueError(f"Tool {tool_id} not found")
        
        tool.settings = {
            'max_ppm': float(controls['max_ppm'].value),
            'min_score': float(controls['min_score'].value),
            'min_ion_intensity_coverage': float(controls['min_ion_intensity_coverage'].value),
            'use_protein_from_file': controls['use_protein_from_file'].value,
            'min_protein_identity': float(controls['min_protein_identity'].value),
            'denovo_correction': controls['denovo_correction'].value
        }
        
        await self.project.update_tool(tool)
    
    # Ion Settings Section
    
    def _build_ion_settings_section(self):
        """Build ion settings section."""
        self.ion_type_a_cb = ft.Checkbox(label="a", value=False)
        self.ion_type_b_cb = ft.Checkbox(label="b", value=True)
        self.ion_type_c_cb = ft.Checkbox(label="c", value=False)
        self.ion_type_x_cb = ft.Checkbox(label="x", value=False)
        self.ion_type_y_cb = ft.Checkbox(label="y", value=True)
        self.ion_type_z_cb = ft.Checkbox(label="z", value=False)
        
        self.water_loss_cb = ft.Checkbox(label="Water loss (H₂O)", value=False)
        self.nh3_loss_cb = ft.Checkbox(label="Ammonia loss (NH₃)", value=False)
        
        self.ion_ppm_threshold_field = ft.TextField(label="PPM Threshold", value="20", width=150, keyboard_type=ft.KeyboardType.NUMBER)
        self.fragment_charges_field = ft.TextField(label="Fragment Charges", value="1,2", hint_text="e.g., 1,2,3", width=250)
        
        self.calc_coverage_btn = ft.ElevatedButton(
            content=ft.Text("Calculate Ion Coverage"),
            icon=ft.Icons.CALCULATE,
            on_click=lambda e: self.page.run_task(self.calculate_ion_coverage, e)
        )
        
        self.calc_protein_metrics_btn = ft.ElevatedButton(
            content=ft.Text("Calculate PPM Error and Ion Coverage for Protein Identifications"),
            icon=ft.Icons.SCIENCE,
            on_click=lambda e: self.page.run_task(self.calculate_protein_match_metrics, e)
        )
        
        return ft.Container(
            content=ft.Column([
                ft.Text("Ion Matching Settings", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([ft.Text("Ion Types:", weight=ft.FontWeight.W_500), self.ion_type_a_cb, self.ion_type_b_cb, self.ion_type_c_cb, self.ion_type_x_cb, self.ion_type_y_cb, self.ion_type_z_cb], spacing=15),
                ft.Row([ft.Text("Losses:", weight=ft.FontWeight.W_500), self.water_loss_cb, self.nh3_loss_cb], spacing=15),
                ft.Row([self.ion_ppm_threshold_field, self.fragment_charges_field], spacing=10),
                ft.Container(height=5),
                self.calc_coverage_btn,
                ft.Container(height=5),
                self.calc_protein_metrics_btn
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY),
            border_radius=10
        )
    
    async def load_ion_settings(self):
        """Load ion settings."""
        try:
            ion_types_str = await self.project.get_setting('ion_types', 'b,y')
            ion_types = ion_types_str.split(',') if ion_types_str else []
            
            self.ion_type_a_cb.value = 'a' in ion_types
            self.ion_type_b_cb.value = 'b' in ion_types
            self.ion_type_c_cb.value = 'c' in ion_types
            self.ion_type_x_cb.value = 'x' in ion_types
            self.ion_type_y_cb.value = 'y' in ion_types
            self.ion_type_z_cb.value = 'z' in ion_types
            
            self.water_loss_cb.value = (await self.project.get_setting('water_loss', '0')) == '1'
            self.nh3_loss_cb.value = (await self.project.get_setting('nh3_loss', '0')) == '1'
            self.ion_ppm_threshold_field.value = await self.project.get_setting('ion_ppm_threshold', '20')
            self.fragment_charges_field.value = await self.project.get_setting('fragment_charges', '1,2')
        except Exception as ex:
            print(f"Error loading ion settings: {ex}")
    
    async def save_ion_settings(self):
        """Save ion settings."""
        selected_types = []
        if self.ion_type_a_cb.value: selected_types.append('a')
        if self.ion_type_b_cb.value: selected_types.append('b')
        if self.ion_type_c_cb.value: selected_types.append('c')
        if self.ion_type_x_cb.value: selected_types.append('x')
        if self.ion_type_y_cb.value: selected_types.append('y')
        if self.ion_type_z_cb.value: selected_types.append('z')
        
        if not selected_types:
            raise ValueError("At least one ion type required")
        if float(self.ion_ppm_threshold_field.value) <= 0:
            raise ValueError("PPM threshold > 0")
        if not self.fragment_charges_field.value.strip():
            raise ValueError("Charges required")
        
        await self.project.set_setting('ion_types', ','.join(selected_types))
        await self.project.set_setting('water_loss', '1' if self.water_loss_cb.value else '0')
        await self.project.set_setting('nh3_loss', '1' if self.nh3_loss_cb.value else '0')
        await self.project.set_setting('ion_ppm_threshold', self.ion_ppm_threshold_field.value)
        await self.project.set_setting('fragment_charges', self.fragment_charges_field.value)
    
    async def calculate_ion_coverage(self, e):
        """Calculate ion coverage."""
        async def on_all(e):
            dlg.open = False
            self.page.update()
            await self._run_coverage_calc(True)
        
        async def on_missing(e):
            dlg.open = False
            self.page.update()
            await self._run_coverage_calc(False)
        
        dlg = ft.AlertDialog(
            title=ft.Text("Calculate Ion Coverage"),
            content=ft.Column([ft.Text("Calculate for:"), ft.Text("Using current ion settings", size=11, italic=True, color=ft.Colors.GREY_600)], tight=True, width=400),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: setattr(dlg, 'open', False) or self.page.update()),
                ft.ElevatedButton(content=ft.Text("Only Missing"), icon=ft.Icons.PLAYLIST_ADD, on_click=lambda e: self.page.run_task(on_missing, e)),
                ft.ElevatedButton(content=ft.Text("All"), icon=ft.Icons.REFRESH, on_click=lambda e: self.page.run_task(on_all, e))
            ]
        )
        
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()
    
    async def _run_coverage_calc(self, recalc_all: bool):
        """Run coverage calculation."""
        try:
            await self.save_ion_settings()
            
            selected_types = []
            if self.ion_type_a_cb.value: selected_types.append('a')
            if self.ion_type_b_cb.value: selected_types.append('b')
            if self.ion_type_c_cb.value: selected_types.append('c')
            if self.ion_type_x_cb.value: selected_types.append('x')
            if self.ion_type_y_cb.value: selected_types.append('y')
            if self.ion_type_z_cb.value: selected_types.append('z')
            
            charges = [int(c.strip()) for c in self.fragment_charges_field.value.split(',')]
            ppm_threshold = float(self.ion_ppm_threshold_field.value)
            
            params = IonMatchParameters(
                ions=selected_types,
                tolerance=ppm_threshold,
                mode='largest',
                water_loss=self.water_loss_cb.value,
                ammonia_loss=self.nh3_loss_cb.value
            )
            
            query = "SELECT * FROM identification ORDER BY id" if recalc_all else "SELECT * FROM identification WHERE intensity_coverage IS NULL ORDER BY id"
            idents_df = await self.project.execute_query_df(query)
            
            if len(idents_df) == 0:
                show_snack(self.page, "No identifications", ft.Colors.BLUE_400)
                self.page.update()
                return
            
            progress_text = ft.Text("Calculating...")
            progress_bar = ft.ProgressBar(value=0)
            progress_details = ft.Text("", size=11, color=ft.Colors.GREY_600)
            
            pdlg = ft.AlertDialog(
                title=ft.Text("Calculating Ion Coverage"),
                content=ft.Column([progress_text, progress_bar, ft.Container(height=5), progress_details], tight=True, width=400),
                modal=True
            )
            
            self.page.overlay.append(pdlg)
            pdlg.open = True
            self.page.update()
            
            total = len(idents_df)
            processed = 0
            
            for idx, ident in idents_df.iterrows():
                try:
                    spectrum = await self.project.get_spectrum_full(ident['spectre_id'])
                    charge = spectrum.get('charge') if spectrum.get('charge') else charges[0]
                    
                    result = match_predictions(
                        params=params,
                        mz=spectrum['mz_array'].tolist(),
                        intensity=spectrum['intensity_array'].tolist(),
                        charges=charge,
                        sequence=ident['sequence']
                    )
                    
                    await self.project.update_identification_coverage(ident['id'], result.intensity_percent)
                    processed += 1
                    
                    if processed % 10 == 0 or processed == total:
                        progress_bar.value = processed / total
                        progress_details.value = f"{processed}/{total}..."
                        progress_bar.update()
                        progress_details.update()
                except Exception as ex:
                    print(f"Error on {ident['id']}: {ex}")
            
            await self.project.save()
            
            progress_text.value = "Complete!"
            progress_bar.value = 1.0
            progress_text.update()
            progress_bar.update()
            
            import asyncio
            await asyncio.sleep(1)
            pdlg.open = False
            self.page.update()
            
            show_snack(self.page, f"Calculated for {processed}", ft.Colors.GREEN_400)
            self.page.update()
        except Exception as ex:
            import traceback
            print(f"Error: {traceback.format_exc()}")
            show_snack(self.page, f"Error: {str(ex)}", ft.Colors.RED_400)
            self.page.update()
    
    async def calculate_protein_match_metrics(self, e):
        """Calculate PPM and coverage for protein matches."""
        try:
            await self.save_ion_settings()
            
            matches_df = await self.project.get_peptide_matches()
            
            if len(matches_df) == 0:
                show_snack(self.page, "No matches. Run mapping first.", ft.Colors.ORANGE_400)
                self.page.update()
                return
            
            selected_types = []
            if self.ion_type_a_cb.value: selected_types.append('a')
            if self.ion_type_b_cb.value: selected_types.append('b')
            if self.ion_type_c_cb.value: selected_types.append('c')
            if self.ion_type_x_cb.value: selected_types.append('x')
            if self.ion_type_y_cb.value: selected_types.append('y')
            if self.ion_type_z_cb.value: selected_types.append('z')
            
            charges = [int(c.strip()) for c in self.fragment_charges_field.value.split(',')]
            ppm_threshold = float(self.ion_ppm_threshold_field.value)
            
            params = IonMatchParameters(
                ions=selected_types,
                tolerance=ppm_threshold,
                mode='largest',
                water_loss=self.water_loss_cb.value,
                ammonia_loss=self.nh3_loss_cb.value
            )
            
            progress_text = ft.Text("Calculating...")
            progress_bar = ft.ProgressBar(value=0)
            progress_details = ft.Text("", size=11, color=ft.Colors.GREY_600)
            
            pdlg = ft.AlertDialog(
                title=ft.Text("Calculating Protein Metrics"),
                content=ft.Column([progress_text, progress_bar, ft.Container(height=5), progress_details], tight=True, width=400),
                modal=True
            )
            
            self.page.overlay.append(pdlg)
            pdlg.open = True
            self.page.update()
            
            total = len(matches_df)
            processed = 0
            
            for idx, match in matches_df.iterrows():
                try:
                    ident_query = f"SELECT * FROM identification WHERE id = {int(match['identification_id'])}"
                    ident_df = await self.project.execute_query_df(ident_query)
                    
                    if len(ident_df) == 0:
                        continue
                    
                    ident = ident_df.iloc[0]
                    spectrum = await self.project.get_spectrum_full(ident['spectre_id'])
                    charge = spectrum.get('charge') if spectrum.get('charge') else charges[0]
                    
                    matched_ppm = calculate_ppm(
                        sequence=match['matched_sequence'],
                        pepmass=spectrum['pepmass'],
                        charge=charge
                    )
                    
                    result = match_predictions(
                        params=params,
                        mz=spectrum['mz_array'].tolist(),
                        intensity=spectrum['intensity_array'].tolist(),
                        charges=charge,
                        sequence=match['matched_sequence']
                    )
                    
                    await self.project.update_peptide_match_metrics(
                        match['id'],
                        matched_ppm=matched_ppm,
                        matched_coverage_percent=result.intensity_percent
                    )
                    
                    processed += 1
                    
                    if processed % 10 == 0 or processed == total:
                        progress_bar.value = processed / total
                        progress_details.value = f"{processed}/{total}..."
                        progress_bar.update()
                        progress_details.update()
                except Exception as ex:
                    print(f"Error on match {match['id']}: {ex}")
            
            await self.project.save()
            
            progress_text.value = "Complete!"
            progress_bar.value = 1.0
            progress_text.update()
            progress_bar.update()
            
            import asyncio
            await asyncio.sleep(1)
            pdlg.open = False
            self.page.update()
            
            show_snack(self.page, f"Calculated for {processed} matches", ft.Colors.GREEN_400)
            self.page.update()
        except Exception as ex:
            import traceback
            print(f"Error: {traceback.format_exc()}")
            show_snack(self.page, f"Error: {str(ex)}", ft.Colors.RED_400)
            self.page.update()
    
    # Matching Section
    
    def _build_matching_section(self):
        """Build matching section."""
        self.selection_criterion_group = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="ppm", label="PPM error"),
                ft.Radio(value="intensity", label="Intensity coverage")
            ]),
            value="intensity"
        )
        
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
        """Run matching."""
        try:
            for tool_id in self.tool_settings_controls.keys():
                is_valid, error_msg = self._validate_tool_settings(tool_id)
                if not is_valid:
                    show_snack(self.page, f"Error: {error_msg}", ft.Colors.ORANGE_400)
                    self.page.update()
                    return
                await self.save_tool_settings(tool_id)
            
            criterion = self.selection_criterion_group.value
            
            tool_settings = {}
            for tool_id, controls in self.tool_settings_controls.items():
                tool_settings[tool_id] = {
                    'max_ppm': float(controls['max_ppm'].value),
                    'min_score': float(controls['min_score'].value),
                    'min_ion_intensity_coverage': float(controls['min_ion_intensity_coverage'].value),
                    'denovo_correction': controls['denovo_correction'].value
                }
            
            progress_text = ft.Text("Processing...")
            progress_bar = ft.ProgressBar()
            
            pdlg = ft.AlertDialog(
                title=ft.Text("Running Matching"),
                content=ft.Column([progress_text, progress_bar], tight=True, width=400),
                modal=True
            )
            
            self.page.overlay.append(pdlg)
            pdlg.open = True
            self.page.update()
            
            count = await select_preferred_identifications(self.project, criterion, tool_settings)
            
            pdlg.open = False
            self.page.update()
            
            show_snack(self.page, f"Processed {count} spectra", ft.Colors.GREEN_400)
            self.page.update()
        except Exception as ex:
            import traceback
            print(f"Error: {traceback.format_exc()}")
            show_snack(self.page, f"Error: {str(ex)}", ft.Colors.RED_400)
            self.page.update()
    
    # Search Section
    
    def _build_search_section(self):
        """Build search section."""
        self.search_sample_dropdown = ft.Dropdown(label="Sample", options=[ft.dropdown.Option(key="all", text="All Samples")], value="all", width=200)
        self.search_tool_dropdown = ft.Dropdown(label="Tool", options=[ft.dropdown.Option(key="all", text="All Tools")], value="all", width=200)
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
        self.search_value_field = ft.TextField(label="Search value", hint_text="Enter value...", expand=True, on_submit=lambda e: self.page.run_task(self.search_identifications, e))
        self.search_btn = ft.ElevatedButton(content=ft.Text("Search"), icon=ft.Icons.SEARCH, on_click=lambda e: self.page.run_task(self.search_identifications, e))
        
        self.results_container = ft.Container(
            content=ft.Column([ft.Text("No search yet", italic=True, color=ft.Colors.GREY_600)]),
            padding=10,
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=5,
            height=300
        )
        
        self.plot_container = ft.Container(
            content=ft.Column([ft.Text("Select identification", italic=True, color=ft.Colors.GREY_600)]),
            padding=10,
            border=ft.border.all(1, ft.Colors.GREY_300),
            border_radius=5,
            height=450
        )
        
        return ft.Container(
            content=ft.Column([
                ft.Text("Search and View Identifications", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([self.search_sample_dropdown, self.search_tool_dropdown], spacing=10),
                ft.Row([self.search_by_dropdown, self.search_value_field, self.search_btn], spacing=10),
                ft.Container(height=10),
                ft.Text("Results:", weight=ft.FontWeight.BOLD),
                self.results_container,
                ft.Container(height=10),
                ft.Text("Ion Match:", weight=ft.FontWeight.BOLD),
                self.plot_container
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY),
            border_radius=10
        )
    
    async def refresh_search_filters(self):
        """Refresh filters."""
        try:
            samples = await self.project.get_samples()
            tools = await self.project.get_tools()
            
            self.search_sample_dropdown.options = [ft.dropdown.Option(key="all", text="All Samples")] + [ft.dropdown.Option(key=str(s.id), text=s.name) for s in samples]
            self.search_tool_dropdown.options = [ft.dropdown.Option(key="all", text="All Tools")] + [ft.dropdown.Option(key=str(t.id), text=t.name) for t in tools]
        except Exception as ex:
            print(f"Error: {ex}")
    
    async def search_identifications(self, e):
        """Search identifications."""
        try:
            sample_id = None if self.search_sample_dropdown.value == "all" else int(self.search_sample_dropdown.value)
            tool_id = None if self.search_tool_dropdown.value == "all" else int(self.search_tool_dropdown.value)
            search_by = self.search_by_dropdown.value
            search_value = self.search_value_field.value
            
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
            
            if sample_id:
                query += " AND sam.id = ?"
                params.append(sample_id)
            if tool_id:
                query += " AND t.id = ?"
                params.append(tool_id)
            
            if search_value:
                if search_by == "seq_no":
                    query += " AND s.seq_no = ?"
                    params.append(int(search_value))
                elif search_by == "scans":
                    query += " AND s.scans = ?"
                    params.append(int(search_value))
                elif search_by == "sequence":
                    query += " AND i.sequence LIKE ?"
                    params.append(f"%{search_value}%")
                elif search_by == "canonical_sequence":
                    query += " AND i.canonical_sequence LIKE ?"
                    params.append(f"%{search_value}%")
            
            query += " ORDER BY s.seq_no, i.score DESC LIMIT 100"
            
            results_df = await self.project.execute_query_df(query, tuple(params))
            
            if len(results_df) == 0:
                self.results_container.content = ft.Column([ft.Text("No results", italic=True, color=ft.Colors.GREY_600)])
            else:
                rows = []
                for idx, row in results_df.iterrows():
                    pref_icon = ft.Icon(ft.Icons.STAR, color=ft.Colors.AMBER, size=16) if row['is_preferred'] else ft.Container(width=16)
                    seq_display = row['sequence'][:20] + "..." if len(row['sequence']) > 20 else row['sequence']
                    
                    rows.append(
                        ft.Container(
                            content=ft.Row([
                                ft.Container(ft.Text(str(row['seq_no']), size=12), width=60),
                                ft.Container(ft.Text(row['sample_name'], size=12), width=100),
                                ft.Container(ft.Text(row['tool_name'], size=12), width=120),
                                ft.Container(ft.Text(seq_display, size=12), width=200),
                                ft.Container(ft.Text(f"{row['score']:.2f}" if pd.notna(row['score']) else "N/A", size=12), width=60),
                                ft.Container(ft.Text(f"{row['ppm']:.2f}" if pd.notna(row['ppm']) else "N/A", size=12), width=60),
                                pref_icon,
                                ft.IconButton(icon=ft.Icons.VISIBILITY, tooltip="View", icon_size=16, on_click=lambda e, r=row.to_dict(): self.page.run_task(self.view_identification, e, r))
                            ], spacing=5),
                            padding=5,
                            border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.GREY_200))
                        )
                    )
                
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
                    ft.Text(f"Results ({len(results_df)}):", weight=ft.FontWeight.BOLD),
                    ft.Column([header] + rows, spacing=0, scroll=ft.ScrollMode.AUTO, height=250)
                ], spacing=5)
            
            self.results_container.update()
            
            if len(results_df) > 0:
                await self.view_identification(None, results_df.iloc[0].to_dict())
        except Exception as ex:
            import traceback
            print(f"Error: {traceback.format_exc()}")
            show_snack(self.page, f"Error: {str(ex)}", ft.Colors.RED_400)
            self.page.update()
    
    async def view_identification(self, e, ident_row: dict):
        """View identification plot."""
        try:
            spectrum = await self.project.get_spectrum_full(ident_row['spectre_id'])
            
            ion_types_str = await self.project.get_setting('ion_types', 'b,y')
            ion_types = ion_types_str.split(',') if ion_types_str else ['b', 'y']
            
            fig = plot_ion_match(
                mz_array=spectrum['mz_array'],
                intensity_array=spectrum['intensity_array'],
                sequence=ident_row['sequence'],
                charge=spectrum.get('charge'),
                ion_types=ion_types,
                water_loss=(await self.project.get_setting('water_loss', '0')) == '1',
                nh3_loss=(await self.project.get_setting('nh3_loss', '0')) == '1',
                ppm_threshold=float(await self.project.get_setting('ion_ppm_threshold', '20'))
            )
            
            img_bytes = pio.to_image(fig, format='png', width=800, height=400)
            img_base64 = base64.b64encode(img_bytes).decode()
            
            self.plot_container.content = ft.Column([
                ft.Text(f"Seq# {ident_row['seq_no']}: {ident_row['sequence']}", weight=ft.FontWeight.BOLD, size=14),
                ft.Text(f"Tool: {ident_row['tool_name']}" + (f" | Score: {ident_row['score']:.2f} | PPM: {ident_row['ppm']:.2f}" if pd.notna(ident_row.get('score')) else ""), size=11, color=ft.Colors.GREY_700),
                ft.Image(src_base64=img_base64, width=780, height=400, fit=ft.BoxFit.CONTAIN)
            ], spacing=5)
            
            self.plot_container.update()
        except Exception as ex:
            import traceback
            print(f"Error: {traceback.format_exc()}")
            self.plot_container.content = ft.Column([
                ft.Text("Error", color=ft.Colors.RED_600, weight=ft.FontWeight.BOLD),
                ft.Text(str(ex), size=11, color=ft.Colors.RED_400)
            ])
            self.plot_container.update()
