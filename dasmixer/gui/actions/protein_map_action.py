"""Protein mapping action."""

import asyncio

import flet as ft

from dasmixer.api.project.project import Project
from dasmixer.api.calculations.peptides.protein_map import map_proteins
from dasmixer.gui.views.tabs.peptides.shared_state import PeptidesTabState
from .base import BaseAction


class MatchProteinsAction(BaseAction):
    """
    Map peptide identifications to proteins via BLAST.

    Extracted from FastaSection.match_proteins_internal().
    Supports optional per-sample filtering.
    """

    def __init__(self, project: Project, page: ft.Page):
        super().__init__(project, page)

    async def run(
        self,
        state: PeptidesTabState,
        sample_id: int | None = None,
    ) -> None:
        """
        Run protein mapping.

        Args:
            state: PeptidesTabState with ion and tool settings.
            sample_id: If provided, only process identifications for this sample.
        """
        # Get tool settings from peptides tab if available
        tool_settings = {}
        if self.page and hasattr(self.page, 'peptides_tab'):
            ts = self.page.peptides_tab.sections.get('tool_settings')
            if ts:
                tool_settings = ts.get_tool_settings_for_matching()

        if not tool_settings:
            self.show_warning("No tools configured. Configure tools in Peptides tab first.")
            return

        # Save BLAST settings from peptides tab
        if self.page and hasattr(self.page, 'peptides_tab'):
            fasta_section = self.page.peptides_tab.sections.get('fasta')
            if fasta_section and hasattr(fasta_section, 'save_blast_settings'):
                await fasta_section.save_blast_settings()

        # Build ion_params from state
        ion_params = {
            'ions': state.ion_types,
            'tolerance': state.ion_ppm_threshold,
            'mode': 'largest',
            'water_loss': state.water_loss,
            'ammonia_loss': state.nh3_loss,
        }
        fragment_charges = list(state.fragment_charges)
        seqfixer_params = {
            'target_ppm': state.ion_ppm_threshold,
            'min_charge': state.min_precursor_charge,
            'max_charge': state.max_precursor_charge,
            'max_isotope_offset': state.max_isotope_offset,
            'force_isotope_offset': state.force_isotope_offset,
        }

        # Clear existing matches (for sample or globally)
        if sample_id is not None:
            await self.project.clear_peptide_matches_for_sample(sample_id)
        else:
            await self.project.clear_peptide_matches()

        from dasmixer.gui.views.tabs.peptides.dialogs.progress_dialog import ProgressDialog
        dialog = ProgressDialog(self.page, "Matching Proteins")
        dialog.show()
        dialog.update_progress(0, "Mapping...")

        total_matches = 0

        try:
            async for matches_df, count, tool_id in map_proteins(
                self.project,
                tool_settings,
                ion_params=ion_params,
                fragment_charges=fragment_charges,
                seqfixer_params=seqfixer_params,
                batch_size=5000,
                sample_id=sample_id,
            ):
                await self.project.add_peptide_matches_batch(matches_df)
                total_matches += count
                dialog.update_progress(None, "Mapping...", f"Mapped {total_matches} matches...")

            await self.project.save()
            dialog.complete(f"Total: {total_matches}")
            await asyncio.sleep(1)
            dialog.close()

            self.show_success(f"Mapped {total_matches} matches")

        except Exception as ex:
            import traceback
            print(f"Error in MatchProteinsAction.run: {traceback.format_exc()}")
            try:
                dialog.close()
            except Exception:
                pass
            self.show_error(f"Error: {str(ex)}")
