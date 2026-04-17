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
    
    async def run_matching_internal(self, sample_id: int | None = None):
        """Run identification matching (internal, no event). Delegates to SelectPreferredAction."""
        try:
            from dasmixer.gui.actions.ion_actions import SelectPreferredAction
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

            criterion = self.selection_criterion_group.value or 'intensity'
            tool_settings = tool_settings_section.get_tool_settings_for_matching()

            action = SelectPreferredAction(self.project, self.page)
            await action.run(
                tool_settings=tool_settings,
                criterion=criterion,
                sample_id=sample_id,
            )

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
