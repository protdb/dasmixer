"""Protein identifications calculation action."""

import asyncio

import flet as ft

from dasmixer.utils import logger
from dasmixer.api.project.project import Project
from dasmixer.api.calculations.proteins.map_identifications import find_protein_identifications
from .base import BaseAction


class ProteinIdentificationsAction(BaseAction):
    """
    Calculate protein identification results from peptide matches.

    Extracted from DetectionSection.calculate_identifications().
    Supports optional per-sample calculation.
    """

    def __init__(self, project: Project, page: ft.Page):
        super().__init__(project, page)

    async def run(
        self,
        min_peptides: int,
        min_uq_evidence: int,
        sample_id: int | None = None,
    ) -> int:
        """
        Run protein identification calculation.

        Args:
            min_peptides: Minimum peptide count for a protein to be identified.
            min_uq_evidence: Minimum unique peptide count.
            sample_id: If provided, only recalculate for this sample.

        Returns:
            Total number of protein identifications saved.
        """
        from dasmixer.gui.views.tabs.peptides.dialogs.progress_dialog import ProgressDialog

        dialog = ProgressDialog(self.page, "Calculating Protein Identifications")
        dialog.show()

        try:
            # Clear old results (per sample or globally)
            dialog.update_progress(None, "Clearing old results...")
            if sample_id is not None:
                await self.project.clear_protein_identifications_for_sample(sample_id)
            else:
                await self.project.clear_protein_identifications()

            # Get peptide data
            dialog.update_progress(None, "Loading peptide data...")
            joined_data = await self.project.get_joined_peptide_data(
                is_preferred=True,
                protein_identified=True,
                sample_id=sample_id,
            )

            if len(joined_data) == 0:
                dialog.close()
                self.show_warning(
                    "No protein-matched identifications found. "
                    "Please run peptide matching first."
                )
                return 0

            dialog.update_progress(None, "Loading protein database...")
            sequences_db = await self.project.get_protein_db_to_search()

            if len(sequences_db) == 0:
                dialog.close()
                self.show_warning("No proteins loaded. Please load a FASTA file first.")
                return 0

            total_samples = joined_data['sample_id'].nunique()
            current_sample = 0
            total_saved = 0

            async for result_df, s_id in find_protein_identifications(
                joined_data=joined_data,
                sequences_db=sequences_db,
                min_peptides=min_peptides,
                min_uq_evidence=min_uq_evidence,
            ):
                current_sample += 1
                dialog.update_progress(
                    current_sample / total_samples,
                    f"Processing sample {current_sample} of {total_samples}"
                )
                if len(result_df) > 0:
                    await self.project.add_protein_identifications_batch(result_df)
                    total_saved += len(result_df)

            dialog.complete()
            await asyncio.sleep(1)
            dialog.close()

            self.show_success(
                f"Protein identifications calculated: {total_saved} total"
            )
            return total_saved

        except Exception as ex:
            logger.exception(ex)
            try:
                dialog.close()
            except Exception:
                pass
            self.show_error(f"Error: {str(ex)}")
            return 0
