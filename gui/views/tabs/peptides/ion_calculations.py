"""Ion coverage calculations - backend service (no UI)."""

import os
import flet as ft
import asyncio
from concurrent.futures import ProcessPoolExecutor

from api.calculations.spectra.ion_match import IonMatchParameters
from api.calculations.spectra.coverage_worker import process_identification_batch, process_peptide_match_batch
from api.project.project import Project
from .shared_state import PeptidesTabState
from .dialogs.progress_dialog import ProgressDialog

# Number of worker processes: leave one CPU free for the UI/async loop
_WORKER_COUNT = max(1, (os.cpu_count() or 2) - 1)
_BATCH_SIZE = 1000


class IonCalculations:
    """
    Ion coverage and PPM calculations backend service.

    NOT a UI component — pure calculation service.
    """

    def __init__(self, project: Project, state: PeptidesTabState):
        self.project = project
        self.state = state

    # ------------------------------------------------------------------
    # Snackbar helpers
    # ------------------------------------------------------------------

    def _get_page(self):
        try:
            return ft.context.page
        except RuntimeError:
            return None

    def show_error(self, message: str):
        page = self._get_page()
        if page:
            page.snack_bar = ft.SnackBar(content=ft.Text(message), bgcolor=ft.Colors.RED_400)
            page.snack_bar.open = True
            page.update()
        else:
            print(f"ERROR: {message}")

    def show_success(self, message: str):
        page = self._get_page()
        if page:
            page.snack_bar = ft.SnackBar(content=ft.Text(message), bgcolor=ft.Colors.GREEN_400)
            page.snack_bar.open = True
            page.update()
        else:
            print(f"SUCCESS: {message}")

    def show_info(self, message: str):
        page = self._get_page()
        if page:
            page.snack_bar = ft.SnackBar(content=ft.Text(message), bgcolor=ft.Colors.BLUE_400)
            page.snack_bar.open = True
            page.update()
        else:
            print(f"INFO: {message}")

    def show_warning(self, message: str):
        page = self._get_page()
        if page:
            page.snack_bar = ft.SnackBar(content=ft.Text(message), bgcolor=ft.Colors.ORANGE_400)
            page.snack_bar.open = True
            page.update()
        else:
            print(f"WARNING: {message}")

    # ------------------------------------------------------------------
    # Dialog trigger
    # ------------------------------------------------------------------

    async def calculate_ion_coverage_dialog(self, e):
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
    # Main coverage calculation (batched + multiprocessing)
    # ------------------------------------------------------------------

    async def run_coverage_calc(self, recalc_all: bool):
        """
        Calculate ion coverage + PPM + theor_mass + override_charge for identifications.
        """
        page = ft.context.page

        # Persist current ion settings before reading them
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
        ignore_spectre_charges = self.state.ignore_spectre_charges
        min_charge = self.state.min_precursor_charge
        max_charge = self.state.max_precursor_charge

        tool_ids = list(self.state.tool_settings_controls.keys())
        if not tool_ids:
            self.show_warning("No tools configured")
            return

        dialog = ProgressDialog(page, "Calculating Ion Coverage")
        dialog.show()

        total_processed = 0

        try:
            loop = asyncio.get_event_loop()

            with ProcessPoolExecutor(max_workers=_WORKER_COUNT) as executor:
                for tool_id in tool_ids:
                    offset = 0
                    while True:
                        batch_objects = await self.project.get_identifications_with_spectra_batch(
                            tool_id=tool_id,
                            offset=offset,
                            limit=_BATCH_SIZE,
                            only_missing=not recalc_all,
                        )
                        if not batch_objects:
                            break

                        worker_batch = [obj.to_worker_dict() for obj in batch_objects]

                        results = await loop.run_in_executor(
                            executor,
                            process_identification_batch,
                            worker_batch,
                            params_dict,
                            fragment_charges,
                            ignore_spectre_charges,
                            min_charge,
                            max_charge,
                        )

                        await self.project.put_identification_data_batch(results)

                        total_processed += len(results)
                        offset += _BATCH_SIZE

                        dialog.update_progress(
                            None,
                            "Calculating...",
                            f"Processed {total_processed} identifications...",
                        )

            await self.project.save()
            dialog.complete(f"Done: {total_processed} identifications")
            await asyncio.sleep(1)
            dialog.close()

            self.show_success(f"Ion coverage calculated for {total_processed} identifications")

        except Exception as exc:
            import traceback
            print(f"Error in run_coverage_calc: {traceback.format_exc()}")
            try:
                dialog.close()
            except Exception:
                pass
            self.show_error(f"Error: {exc}")

    # ------------------------------------------------------------------
    # Protein match metrics (batch, via coverage_worker)
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

        # Fetch all peptide matches with spectrum data
        # We join peptide_match with identification to get spectre_id and override_charge,
        # then join spectre for mz/intensity arrays.
        matches_with_spectra = await self.project.get_peptide_matches_with_spectra()

        if not matches_with_spectra:
            self.show_warning("No matches found. Run protein mapping first.")
            return

        dialog = ProgressDialog(page, "Calculating Protein Match Metrics")
        dialog.show()

        total = len(matches_with_spectra)
        total_processed = 0

        try:
            loop = asyncio.get_event_loop()

            with ProcessPoolExecutor(max_workers=_WORKER_COUNT) as executor:
                # Process in batches
                for batch_start in range(0, total, _BATCH_SIZE):
                    batch = matches_with_spectra[batch_start: batch_start + _BATCH_SIZE]

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
