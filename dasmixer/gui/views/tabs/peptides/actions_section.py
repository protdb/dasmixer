"""Actions section - main peptide calculation workflow."""

import asyncio
import flet as ft

from .base_section import BaseSection


class ActionsSection(BaseSection):
    """
    Main actions section.

    Layout:
    - "Calculate Peptides" button (green, full workflow)
    - "Advanced" subtitle
    - "Select Preferred" button (star icon)
    - "Calculate Ion Coverage" button
    - "Match Proteins to Identifications" button
    - Divider
    - "Save settings" button
    """

    def __init__(self, project, state, parent_tab):
        self.parent_tab = parent_tab
        super().__init__(project, state)

    def _build_content(self) -> ft.Control:
        """Build actions UI."""
        # Main workflow button
        self.calc_peptides_btn = ft.ElevatedButton(
            content=ft.Text("Calculate Peptides"),
            icon=ft.Icons.PLAY_CIRCLE,
            on_click=lambda e: self.page.run_task(self.calculate_peptides, e),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.GREEN_600,
                color=ft.Colors.WHITE,
            ),
        )

        # Advanced individual step buttons
        self.select_preferred_btn = ft.ElevatedButton(
            content=ft.Text("Select Preferred"),
            icon=ft.Icons.STAR_OUTLINE,
            on_click=lambda e: self.page.run_task(self._run_select_preferred, e),
        )

        self.calc_coverage_btn = ft.ElevatedButton(
            content=ft.Text("Calculate Ion Coverage"),
            icon=ft.Icons.CALCULATE,
            on_click=lambda e: self.page.run_task(self._run_ion_coverage, e),
        )

        self.match_proteins_btn = ft.ElevatedButton(
            content=ft.Text("Match Proteins to Identifications"),
            icon=ft.Icons.LINK,
            on_click=lambda e: self.page.run_task(self._run_match_proteins, e),
        )

        self.save_settings_btn = ft.ElevatedButton(
            content=ft.Text("Save settings"),
            icon=ft.Icons.SAVE,
            on_click=lambda e: self.page.run_task(self._save_all_settings, e),
        )

        return ft.Column(
            [
                ft.Text("Actions", size=18, weight=ft.FontWeight.BOLD),
                self.calc_peptides_btn,
                ft.Container(height=8),
                ft.Text(
                    "Advanced",
                    size=13,
                    color=ft.Colors.GREY_600,
                    weight=ft.FontWeight.W_500,
                ),
                self.select_preferred_btn,
                self.calc_coverage_btn,
                self.match_proteins_btn,
                ft.Divider(),
                self.save_settings_btn,
            ],
            spacing=8,
        )

    # ------------------------------------------------------------------
    # Individual action handlers
    # ------------------------------------------------------------------

    async def _run_select_preferred(self, e):
        """Run Select Preferred Identifications."""
        try:
            from dasmixer.gui.actions.ion_actions import SelectPreferredAction

            tool_settings_section = self.parent_tab.sections.get('tool_settings')
            if not tool_settings_section:
                self.show_error("Tool settings not available")
                return

            for tool_id in self.state.tool_settings_controls.keys():
                is_valid, error_msg = tool_settings_section.validate_tool_settings(tool_id)
                if not is_valid:
                    self.show_warning(f"Validation error: {error_msg}")
                    return
                await tool_settings_section.save_tool_settings(tool_id)

            criterion = 'intensity'
            ion_section = self.parent_tab.sections.get('ion_settings')
            if ion_section and hasattr(ion_section, 'get_selection_criterion'):
                criterion = ion_section.get_selection_criterion()

            tool_settings = tool_settings_section.get_tool_settings_for_matching()
            action = SelectPreferredAction(self.project, self.page)
            await action.run(tool_settings=tool_settings, criterion=criterion)

        except Exception as ex:
            import traceback
            traceback.print_exc()
            self.show_error(f"Error: {ex}")

    async def _run_ion_coverage(self, e):
        """Run Calculate Ion Coverage."""
        try:
            await self.parent_tab.ion_calculations.run_coverage_calc(recalc_all=False)
        except Exception as ex:
            import traceback
            traceback.print_exc()
            self.show_error(f"Error: {ex}")

    async def _run_match_proteins(self, e):
        """Run Match Proteins to Identifications."""
        try:
            fasta_section = self.parent_tab.sections.get('fasta')
            if fasta_section and hasattr(fasta_section, 'match_proteins_internal'):
                await fasta_section.match_proteins_internal()
        except Exception as ex:
            import traceback
            traceback.print_exc()
            self.show_error(f"Error: {ex}")

    async def _save_all_settings(self, e):
        """Save Ion Matching settings, Tool settings and BLAST settings."""
        try:
            ion_section = self.parent_tab.sections.get('ion_settings')
            if ion_section and hasattr(ion_section, 'save_settings'):
                await ion_section.save_settings()

            tool_section = self.parent_tab.sections.get('tool_settings')
            if tool_section and hasattr(tool_section, 'save_all_tool_settings'):
                await tool_section.save_all_tool_settings()

            fasta_section = self.parent_tab.sections.get('fasta')
            if fasta_section and hasattr(fasta_section, 'save_blast_settings'):
                await fasta_section.save_blast_settings()

            self.show_success("Settings saved")

        except Exception as ex:
            import traceback
            traceback.print_exc()
            self.show_error(f"Error saving settings: {ex}")

    # ------------------------------------------------------------------
    # Full workflow
    # ------------------------------------------------------------------

    async def calculate_peptides(self, e):
        """
        Run complete peptide calculation workflow.

        Steps:
        1. Match proteins to identifications
        2. Calculate ion coverage (only missing)
        3. Select preferred identifications
        """
        try:
            print("Starting Calculate Peptides workflow...")

            fasta_section = self.parent_tab.sections.get('fasta')
            if fasta_section and hasattr(fasta_section, 'match_proteins_internal'):
                await fasta_section.match_proteins_internal()

            await asyncio.sleep(0.5)

            await self.parent_tab.ion_calculations.run_coverage_calc(recalc_all=False)

            await asyncio.sleep(0.5)

            await self._run_select_preferred(None)

            self.show_success("Peptide calculations complete!")

        except Exception as ex:
            import traceback
            traceback.print_exc()
            self.show_error(f"Error: {ex}")
