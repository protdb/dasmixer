"""Label-Free Quantification action."""

import asyncio

import flet as ft

from dasmixer.api.project.project import Project
from dasmixer.api.calculations.proteins.lfq import calculate_lfq
from dasmixer.gui.views.tabs.proteins.shared_state import ProteinsTabState
from .base import BaseAction


class LFQAction(BaseAction):
    """
    Calculate Label-Free Quantification for protein identifications.

    Extracted from LFQSection.calculate_lfq().
    Supports optional per-sample calculation.
    """

    def __init__(self, project: Project, page: ft.Page):
        super().__init__(project, page)

    async def run(
        self,
        state: ProteinsTabState,
        sample_id: int | None = None,
    ) -> int:
        """
        Run LFQ calculation.

        Args:
            state: ProteinsTabState with LFQ parameters.
            sample_id: If provided, only calculate for this sample.

        Returns:
            Total number of quantification records saved.
        """
        selected_methods = state.get_selected_lfq_methods()
        if not selected_methods:
            self.show_warning("No LFQ methods selected. Configure in Proteins tab.")
            return 0

        from dasmixer.gui.views.tabs.peptides.dialogs.progress_dialog import ProgressDialog

        dialog = ProgressDialog(self.page, "Calculating LFQ")
        dialog.show()

        try:
            # Clear old results (per sample or globally)
            dialog.update_progress(None, "Clearing old quantifications...")
            if sample_id is not None:
                await self.project.clear_protein_quantifications_for_sample(sample_id)
            else:
                await self.project.clear_protein_quantifications()

            # Determine which samples to process
            dialog.update_progress(None, "Loading samples...")
            if sample_id is not None:
                samples_df = await self.project.execute_query_df(
                    "SELECT id FROM sample WHERE id = ?",
                    (int(sample_id),)
                )
            else:
                samples_df = await self.project.execute_query_df(
                    "SELECT DISTINCT id FROM sample ORDER BY id"
                )

            if len(samples_df) == 0:
                dialog.close()
                self.show_warning("No samples found")
                return 0

            total_samples = len(samples_df)
            total_saved = 0

            for idx, row in samples_df.iterrows():
                s_id = row['id']
                dialog.update_progress(
                    (idx + 1) / total_samples,
                    f"Processing sample {idx + 1} of {total_samples}"
                )
                result_df = await calculate_lfq(
                    project=self.project,
                    sample_id=s_id,
                    methods=selected_methods,
                    enzyme=state.enzyme,
                    min_length=state.min_peptide_length,
                    max_length=state.max_peptide_length,
                    max_cleavage_sites=state.max_cleavage_sites,
                    empai_base=state.empai_base_value,
                )
                if len(result_df) > 0:
                    await self.project.add_protein_quantifications_batch(result_df)
                    total_saved += len(result_df)

            dialog.complete()
            await asyncio.sleep(1)
            dialog.close()

            self.show_success(f"LFQ calculated: {total_saved} quantifications")
            return total_saved

        except Exception as ex:
            import traceback
            traceback.print_exc()
            try:
                dialog.close()
            except Exception:
                pass
            self.show_error(f"Error: {str(ex)}")
            return 0
