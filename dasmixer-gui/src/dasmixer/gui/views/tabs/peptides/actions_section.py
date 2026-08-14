"""Actions section - main peptide calculation workflow."""

import asyncio
import flet as ft

from .base_section import BaseSection
from dasmixer.utils import logger


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

        self.clear_calculations_btn = ft.ElevatedButton(
            content=ft.Text("Clear Calculations"),
            icon=ft.Icons.DELETE_SWEEP,
            on_click=lambda e: self.page.run_task(self._run_clear_calculations, e),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.RED_700,
                color=ft.Colors.WHITE,
            ),
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
                ft.Row([self.save_settings_btn, self.clear_calculations_btn], spacing=10),
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

    async def _run_clear_calculations(self, e):
        """Open confirmation dialog and clear all calculations globally."""
        try:
            checkbox = ft.Checkbox(label="I am sure", value=False)

            confirm_btn = ft.ElevatedButton(
                content=ft.Text("Confirm"),
                icon=ft.Icons.DELETE_SWEEP,
                disabled=True,
            )

            def on_checkbox_change(event):
                confirm_btn.disabled = not checkbox.value
                dlg.update()

            checkbox.on_change = on_checkbox_change

            async def on_confirm(event):
                dlg.open = False
                self.page.update()
                await self.project.clear_calculations()
                await self.project.save()
                self.show_success("Calculations cleared")
                # Reload the peptide table if available
                search_section = self.parent_tab.sections.get('search')
                if search_section is not None and hasattr(search_section, 'table_view'):
                    table_view = search_section.table_view
                    table_view.current_page = 0
                    await table_view._load_table_data()

            def on_cancel(event):
                dlg.open = False
                self.page.update()

            confirm_btn.on_click = lambda ev: self.page.run_task(on_confirm, ev)

            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("Clear Calculations"),
                content=ft.Column([
                    ft.Text(
                        "This will reset all ion-coverage, PPM correction, quality, and PTM results "
                        "for EVERY identification in the project:\n\n"
                        "- Sequences modified by SEQFixer (PTM/isotope/charge overrides) will be "
                        "restored to their original imported form.\n"
                        "- intensity_coverage, ions_matched, ion_match_type, top_peaks_covered, ppm, "
                        "theor_mass, quality, override_pepmass, has_ptm, isotope_offset, "
                        "override_charge and source_sequence will be cleared (NULL).\n"
                        "- is_preferred flags will be reset to 0 for all spectra.\n\n"
                        "Peptide-protein matches (peptide_match table) are NOT affected, but their "
                        "derived metrics will become inconsistent until coverage is recalculated.\n\n"
                        "This action cannot be undone. Confirm only if you intend to rerun the calculations.",
                        size=12,
                    ),
                    checkbox,
                ], tight=True, scroll=ft.ScrollMode.AUTO, width=480),
                actions=[
                    ft.TextButton("Cancel", on_click=on_cancel),
                    confirm_btn,
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )

            self.page.overlay.append(dlg)
            dlg.open = True
            self.page.update()

        except Exception as ex:
            import traceback
            traceback.print_exc()
            self.show_error(f"Error: {ex}")

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
            logger.debug("Starting Calculate Peptides workflow...")

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
