"""Ion coverage calculations - backend service (no UI).

Delegates to IonCoverageAction for the heavy lifting.
"""

import math
import os
import flet as ft
import asyncio
from concurrent.futures import ProcessPoolExecutor
from typing import Literal, cast

from dasmixer.api.calculations.spectra.ion_match import IonMatchParameters
from dasmixer.api.calculations.spectra.coverage_worker import process_peptide_match_batch
from dasmixer.api.calculations.spectra.identification_processor import process_identificatons_batch
from dasmixer.api.project.project import Project
from dasmixer.api.config import config as _config
from .shared_state import PeptidesTabState
from .dialogs.progress_dialog import ProgressDialog
from dasmixer.gui.utils import show_snack


class IonCalculations:
    """
    Ion coverage and PPM calculations backend service.

    NOT a UI component — thin facade that delegates to IonCoverageAction.
    """

    def __init__(self, project: Project, state: PeptidesTabState):
        self.project = project
        self.state = state

    def _get_page(self):
        try:
            return ft.context.page
        except RuntimeError:
            return None

    def show_error(self, message: str):
        page = self._get_page()
        if page:
            show_snack(page, message, ft.Colors.RED_400)
            page.update()
        else:
            print(f"ERROR: {message}")

    def show_success(self, message: str):
        page = self._get_page()
        if page:
            show_snack(page, message, ft.Colors.GREEN_400)
            page.update()
        else:
            print(f"SUCCESS: {message}")

    def show_info(self, message: str):
        page = self._get_page()
        if page:
            show_snack(page, message, ft.Colors.BLUE_400)
            page.update()
        else:
            print(f"INFO: {message}")

    def show_warning(self, message: str):
        page = self._get_page()
        if page:
            show_snack(page, message, ft.Colors.ORANGE_400)
            page.update()
        else:
            print(f"WARNING: {message}")

    # ------------------------------------------------------------------
    # Dialog trigger
    # ------------------------------------------------------------------

    async def calculate_ion_coverage_dialog(self, e=None):
        """Show dialog to choose coverage calculation mode."""
        page = ft.context.page

        async def on_all(e):
            dlg.open = False
            page.update()
            await self.run_coverage_calc(recalc_all=True)

        async def on_missing(e):
            dlg.open = False
            page.update()
            await self.run_coverage_calc(recalc_all=False)

        dlg = ft.AlertDialog(
            title=ft.Text("Calculate Ion Coverage"),
            content=ft.Column([
                ft.Text("Calculate for:"),
                ft.Text(
                    "Using current ion settings",
                    size=11, italic=True, color=ft.Colors.GREY_600,
                ),
            ], tight=True, width=400),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=lambda e: setattr(dlg, 'open', False) or page.update(),
                ),
                ft.ElevatedButton(
                    content=ft.Text("Only Missing"),
                    icon=ft.Icons.PLAYLIST_ADD,
                    on_click=lambda e: page.run_task(on_missing, e),
                ),
                ft.ElevatedButton(
                    content=ft.Text("All"),
                    icon=ft.Icons.REFRESH,
                    on_click=lambda e: page.run_task(on_all, e),
                ),
            ],
        )

        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # ------------------------------------------------------------------
    # Main coverage calculation — delegates to IonCoverageAction
    # ------------------------------------------------------------------

    async def run_coverage_calc(self, recalc_all: bool, sample_id: int | None = None):
        """
        Calculate ion coverage + PPM + theor_mass + override_charge.

        Delegates to IonCoverageAction.
        """
        from dasmixer.gui.actions.ion_actions import IonCoverageAction
        page = ft.context.page
        action = IonCoverageAction(self.project, page)
        await action.run(
            state=self.state,
            recalc_all=recalc_all,
            sample_id=sample_id,
        )

    # ------------------------------------------------------------------
    # Protein match metrics (batch, via coverage_worker — unchanged)
    # ------------------------------------------------------------------

    async def calculate_protein_metrics_internal(self):
        """
        Calculate PPM and ion coverage for protein peptide matches.

        Uses process_peptide_match_batch from coverage_worker (multiprocessing).
        """
        page = ft.context.page

        if hasattr(page, 'peptides_tab'):
            ion_section = page.peptides_tab.sections.get('ion_settings')
            if ion_section and hasattr(ion_section, 'save_settings'):
                await ion_section.save_settings()

        params = self._get_ion_match_params()
        params_dict = {
            'ions': params.ions,
            'tolerance': params.tolerance,
            'mode': params.mode,
            'water_loss': params.water_loss,
            'ammonia_loss': params.ammonia_loss,
        }
        fragment_charges = list(self.state.fragment_charges)

        matches_with_spectra = await self.project.get_peptide_matches_with_spectra()

        if not matches_with_spectra:
            self.show_warning("No matches found. Run protein mapping first.")
            return

        dialog = ProgressDialog(page, "Calculating Protein Match Metrics")
        dialog.show()

        total = len(matches_with_spectra)
        total_processed = 0

        # Get batch size and worker count from config
        batch_size = _config.identification_processing_batch_size
        worker_count = _config.max_cpu_threads or max(1, (os.cpu_count() or 2) - 1)

        try:
            loop = asyncio.get_event_loop()

            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                for batch_start in range(0, total, batch_size):
                    batch = matches_with_spectra[batch_start: batch_start + batch_size]

                    results = await loop.run_in_executor(
                        executor,
                        process_peptide_match_batch,
                        batch,
                        params_dict,
                        fragment_charges,
                    )

                    await self.project.put_peptide_match_data_batch(results)

                    total_processed += len(results)
                    dialog.update_progress(
                        total_processed / total,
                        "Calculating...",
                        f"{total_processed}/{total}...",
                    )

            await self.project.save()
            dialog.complete(f"Processed {total_processed}")
            await asyncio.sleep(1)
            dialog.close()

            self.show_success(f"Calculated metrics for {total_processed} matches")

        except Exception as exc:
            import traceback
            print(f"Error in calculate_protein_metrics_internal: {traceback.format_exc()}")
            try:
                dialog.close()
            except Exception:
                pass
            self.show_error(f"Error: {exc}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_ion_match_params(self) -> IonMatchParameters:
        return IonMatchParameters(
            ions=self.state.ion_types,
            tolerance=self.state.ion_ppm_threshold,
            mode='largest',
            water_loss=self.state.water_loss,
            ammonia_loss=self.state.nh3_loss,
            charges=self.state.fragment_charges
        )
