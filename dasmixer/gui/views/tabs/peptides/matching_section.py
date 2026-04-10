"""Preferred identification matching section."""
from pathlib import Path

import flet as ft

from dasmixer.api.calculations.peptides.matching import calculate_preferred_identifications_for_file
from .base_section import BaseSection
from .dialogs.progress_dialog import ProgressDialog


class MatchingSection(BaseSection):
    """Preferred identification selection based on criterion."""
    
    def _build_content(self) -> ft.Control:
        """Build matching section UI."""
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
            on_click=lambda e: self.page.run_task(self.run_matching, e)
        )
        
        return ft.Column([
            ft.Text("Preferred Identification Selection", size=18, weight=ft.FontWeight.BOLD),
            ft.Text("Selection Criterion:", weight=ft.FontWeight.W_500),
            self.selection_criterion_group,
            ft.Container(height=10),
            self.run_matching_btn
        ], spacing=10)
    
    async def run_matching(self, e):
        """Run identification matching (with UI)."""
        await self.run_matching_internal()
    
    async def run_matching_internal(self):
        """Run identification matching (internal, no event)."""
        try:
            # Get tool settings section
            tool_settings_section = None
            if hasattr(self, 'page') and hasattr(self.page, 'peptides_tab'):
                tool_settings_section = self.page.peptides_tab.sections.get('tool_settings')
            
            if not tool_settings_section:
                self.show_error("Tool settings not available")
                return
            
            # Validate and save all tool settings
            for tool_id in self.state.tool_settings_controls.keys():
                is_valid, error_msg = tool_settings_section.validate_tool_settings(tool_id)
                if not is_valid:
                    self.show_warning(f"Validation error: {error_msg}")
                    return
                await tool_settings_section.save_tool_settings(tool_id)
            
            # Get criterion
            criterion = self.selection_criterion_group.value
            
            # Get tool settings for matching
            tool_settings = tool_settings_section.get_tool_settings_for_matching()
            
            if not tool_settings:
                self.show_warning("No tools configured")
                return
            
            # Run matching with progress
            dialog = ProgressDialog(self.page, "Running Matching")
            dialog.show()


            spectre_files = await self.project.get_spectra_files()
            progres = 0.0
            processed_files = 0
            progres_step = round(1 / len(spectre_files), 3)
            for _, spectra_file in spectre_files.iterrows():
                file_name = Path(spectra_file['path']).name
                dialog.update_progress(
                    progres,
                    f"Processing {file_name} ({processed_files+1}/{len(spectre_files)})..."
                )
                idents = await calculate_preferred_identifications_for_file(
                    self.project,
                    spectra_file['id'],
                    criterion,
                    tool_settings,
                )
                dialog.update_progress(progres, f"Saving {file_name} ({processed_files+1}/{len(spectre_files)})...")
                await self.project.set_preferred_identifications_for_file(
                    spectra_file['id'],
                    idents,
                )
                progres += progres_step
                processed_files += 1
            dialog.complete(f"Completed {processed_files+1}/{len(spectre_files)}!")
            
            import asyncio
            await asyncio.sleep(0.5)
            dialog.close()
            
            self.show_success(f"Processed {processed_files} spectra files!")
            
        except Exception as ex:
            import traceback
            print(f"Error: {traceback.format_exc()}")
            self.show_error(f"Error: {str(ex)}")
    
    def _get_ion_match_params(self):
        """Get IonMatchParameters from shared state."""
        from dasmixer.api.calculations.spectra.ion_match import IonMatchParameters
        
        return IonMatchParameters(
            ions=self.state.ion_types,
            tolerance=self.state.ion_ppm_threshold,
            mode='largest',
            water_loss=self.state.water_loss,
            ammonia_loss=self.state.nh3_loss
        )
