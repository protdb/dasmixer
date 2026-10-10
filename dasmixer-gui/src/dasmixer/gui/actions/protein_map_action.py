"""Protein mapping action."""

import asyncio

import flet as ft
from dasmixer.api.calculations.peptides.protein_map import map_proteins
from dasmixer.api.config import config as _config
from dasmixer.api.project.project import Project
from dasmixer.gui.views.tabs.peptides.shared_state import PeptidesTabState

from dasmixer.utils import logger

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

        from dasmixer.gui.views.tabs.peptides.dialogs.progress_dialog import (
            ProgressDialog,
        )
        dialog = ProgressDialog(self.page, "Matching Proteins", stoppable=True)
        dialog.show()
        dialog.update_progress(0, "Mapping...")

        try:
            batch_size = _config.protein_mapping_batch_size
            # use_src_protein_ids = True if ANY tool has "Use protein ID from file" checked
            use_src_protein_ids = any(
                s.get('use_protein_from_file', False) for s in tool_settings.values()
            )

            def _on_progress(processed: int, total: int) -> None:
                # total is always -1 (unknown) from map_proteins — show indeterminate bar
                dialog.update_progress(
                    None,
                    "Mapping...",
                    f"Processed {processed} identifications",
                )

            stop_check = lambda: dialog.stop_requested

            await map_proteins(
                self.project,
                tool_settings,
                ion_params=ion_params,
                fragment_charges=fragment_charges,
                seqfixer_params=seqfixer_params,
                batch_size=batch_size,
                sample_id=sample_id,
                use_src_protein_ids=use_src_protein_ids,
                progress_callback=_on_progress,
                stop_check=stop_check,
            )

            if dialog.stop_requested:
                dialog.complete("Stopped")
            else:
                dialog.complete("Mapping complete")
            await asyncio.sleep(1)
            dialog.close()

            self.show_success("Protein mapping completed")

        except Exception as ex:
            logger.exception(ex)
            try:
                dialog.close()
            except Exception:
                logger.debug("Failed to close progress dialog", exc_info=True)
            self.show_error(f"Error: {ex!s}")
