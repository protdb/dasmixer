"""Actions section - main peptide calculation workflow."""

import flet as ft
import asyncio

from .base_section import BaseSection
from .dialogs.progress_dialog import ProgressDialog


class ActionsSection(BaseSection):
    """
    Main actions section with Calculate Peptides button.
    
    Provides unified workflow that runs all peptide calculations:
    1. Match proteins to identifications
    2. Calculate ion coverage
    3. Calculate PPM and coverage for protein matches
    4. Run identification matching
    """
    def __init__(self, project, state, parent_tab):
        """
        Initialize actions section.
        
        Args:
            project: Project instance
            state: Shared state
            parent_tab: Reference to parent PeptidesTab for accessing other sections
        """
        self.parent_tab = parent_tab
        super().__init__(project, state)
    
    def _build_content(self) -> ft.Control:
        """Build actions UI."""
        # Main Calculate button
        self.calc_peptides_btn = ft.ElevatedButton(
            content=ft.Text("Calculate Peptides"),
            icon=ft.Icons.PLAY_CIRCLE,
            on_click=lambda e: self.page.run_task(self.calculate_peptides, e),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.GREEN_600,
                color=ft.Colors.WHITE
            )
        )

        # Advanced options panel (collapsed by default)
        self.advanced_panel = ft.ExpansionPanelList(
            expand_icon_color=ft.Colors.BLUE,
            elevation=0,
            controls=[
                ft.ExpansionPanel(
                    header=ft.ListTile(
                        title=ft.Text("Advanced Options")
                    ),
                    content=ft.Container(
                        content=ft.Column([
                            ft.ElevatedButton(
                                content=ft.Text("Calculate Ion Coverage"),
                                icon=ft.Icons.CALCULATE,
                                on_click=lambda e: self.page.run_task(
                                    self.parent_tab.ion_calculations.calculate_ion_coverage_dialog, e
                                )
                            ),
                            ft.ElevatedButton(
                                content=ft.Text("Run Identification Matching"),
                                icon=ft.Icons.PLAY_ARROW,
                                on_click=lambda e: self.page.run_task(
                                    self.parent_tab.sections['matching'].run_matching, e
                                ) if hasattr(self.parent_tab.sections.get('matching'), 'run_matching') else None
                            ),
                            ft.ElevatedButton(
                                content=ft.Text("Match Proteins to Identifications"),
                                icon=ft.Icons.LINK,
                                on_click=lambda e: self.page.run_task(
                                    self.parent_tab.sections['fasta'].match_proteins, e
                                ) if hasattr(self.parent_tab.sections.get('fasta'), 'match_proteins') else None
                            )
                        ], spacing=10),
                        padding=15
                    ),
                    can_tap_header=True
                )
            ]
        )

        return ft.Column([
            ft.Text("Actions", size=18, weight=ft.FontWeight.BOLD),
            self.calc_peptides_btn,
            ft.Container(height=10),
            self.advanced_panel
        ], spacing=10)
    
    async def calculate_peptides(self, e):
        """
        Run complete peptide calculation workflow.

        Steps:
        1. Match proteins to identifications (includes PPM/coverage for partial matches)
        2. Calculate ion coverage for identifications
        3. Run identification matching
        """
        try:
            print("Starting Calculate Peptides workflow...")

            # Step 1: Match proteins (PPM/coverage now computed inside mapping)
            await self._run_step(
                "Matching Proteins",
                self._match_proteins_step()
            )

            # Short delay between steps
            await asyncio.sleep(0.5)

            # Step 2: Calculate ion coverage for identifications
            await self._run_step(
                "Calculating Ion Coverage",
                self._calculate_coverage_step()
            )

            await asyncio.sleep(0.5)

            # Step 3: Run identification matching
            await self._run_step(
                "Running Identification Matching",
                self._run_matching_step()
            )

            # Final success message
            self.show_success("Peptide calculations complete!")

        except Exception as ex:
            import traceback
            print(f"Error in calculate_peptides: {traceback.format_exc()}")
            self.show_error(f"Error: {str(ex)}")
    
    async def _run_step(self, title: str, coro):
        """Run a single step with progress dialog."""
        dialog = ProgressDialog(self.page, title)
        dialog.show()
        dialog.update_progress(None, "Processing...")
        
        try:
            await coro
            dialog.complete()
            await asyncio.sleep(1)
            dialog.close()
        except Exception as ex:
            dialog.close()
            raise ex
    
    async def _match_proteins_step(self):
        """Step 1: Match proteins to identifications."""
        # Get reference to fasta section
        fasta_section = self.parent_tab.sections.get('fasta')
        if hasattr(fasta_section, 'match_proteins_internal'):
            await fasta_section.match_proteins_internal()
        else:
            print("Warning: fasta section not found or missing match_proteins_internal method")
    
    async def _calculate_coverage_step(self):
        """Step 2: Calculate ion coverage for identifications (only missing)."""
        # Use ion_calculations service from parent tab
        await self.parent_tab.ion_calculations.run_coverage_calc(recalc_all=False)

    async def _run_matching_step(self):
        """Step 4: Run identification matching."""
        matching_section = self.parent_tab.sections.get('matching')
        if hasattr(matching_section, 'run_matching_internal'):
            await matching_section.run_matching_internal()
        else:
            print("Warning: matching section not found")
