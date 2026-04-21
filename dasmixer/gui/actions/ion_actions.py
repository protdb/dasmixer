"""Ion coverage and preferred identification selection actions."""

import asyncio
import math
import os
from concurrent.futures import ProcessPoolExecutor

import flet as ft

from dasmixer.api.project.project import Project
from dasmixer.api.calculations.spectra.ion_match import IonMatchParameters
from dasmixer.api.calculations.spectra.coverage_worker import process_peptide_match_batch
from dasmixer.api.calculations.spectra.identification_processor import process_identificatons_batch
from dasmixer.api.calculations.peptides.matching import calculate_preferred_identifications_for_file
from dasmixer.gui.views.tabs.peptides.shared_state import PeptidesTabState
from .base import BaseAction

_WORKER_COUNT = max(1, (os.cpu_count() or 2) - 1)
_BATCH_SIZE = 20000


class IonCoverageAction(BaseAction):
    """
    Calculate ion coverage + PPM + theor_mass + override_charge for identifications.

    Extracted from IonCalculations.run_coverage_calc().
    Supports optional per-sample filtering via spectra_file_ids.
    """

    def __init__(self, project: Project, page: ft.Page):
        super().__init__(project, page)

    async def run(
        self,
        state: PeptidesTabState,
        recalc_all: bool = False,
        sample_id: int | None = None,
    ) -> None:
        """
        Run ion coverage calculation.

        Args:
            state: PeptidesTabState with ion settings.
            recalc_all: If True, recalculate all; otherwise only missing.
            sample_id: If provided, only process identifications for this sample.
        """
        # Persist current ion settings
        if self.page and hasattr(self.page, 'peptides_tab'):
            ion_section = self.page.peptides_tab.sections.get('ion_settings')
            if ion_section and hasattr(ion_section, 'save_settings'):
                await ion_section.save_settings()

        params = IonMatchParameters(
            ions=state.ion_types,
            tolerance=state.ion_ppm_threshold,
            mode='largest',
            water_loss=state.water_loss,
            ammonia_loss=state.nh3_loss,
            charges=state.fragment_charges
        )
        params_dict = {
            'ions': params.ions,
            'tolerance': params.tolerance,
            'mode': params.mode,
            'water_loss': params.water_loss,
            'ammonia_loss': params.ammonia_loss,
        }
        fragment_charges = list(state.fragment_charges)
        target_ppm = state.ion_ppm_threshold
        min_charge = state.min_precursor_charge
        max_charge = state.max_precursor_charge
        force_isotope_offset = state.force_isotope_offset
        max_isotope_offset = state.max_isotope_offset
        seq_criteria = state.seq_criteria

        tool_ids = list(state.tool_settings_controls.keys())
        if not tool_ids:
            self.show_warning("No tools configured")
            return

        # Per-tool PTM settings
        max_ptm_sites = state.max_ptm_sites

        tool_settings_map = {}
        for tid, controls in state.tool_settings_controls.items():
            ptm_selected: list[str] = controls.get('ptm_selected', [])
            from dasmixer.utils.seqfixer_utils import PTMS as _ALL_PTMS
            all_codes = {p.code for p in _ALL_PTMS}
            ptm_list = None if set(ptm_selected) == all_codes else ptm_selected
            max_ptm_ctrl = controls.get('max_ptm')
            try:
                max_ptm = int(max_ptm_ctrl.value) if max_ptm_ctrl else 5
            except (ValueError, AttributeError):
                max_ptm = 5
            tool_settings_map[tid] = {'ptm_list': ptm_list, 'max_ptm': max_ptm}

        only_missing = not recalc_all

        # Resolve spectra_file_ids for sample filter
        spectra_file_ids: list[int] | None = None
        if sample_id is not None:
            sf_df = await self.project.get_spectra_files(sample_id=sample_id)
            if sf_df.empty:
                self.show_warning(f"No spectra files for sample id={sample_id}")
                return
            spectra_file_ids = list(sf_df['id'].astype(int))

        from dasmixer.gui.views.tabs.peptides.dialogs.progress_dialog import ProgressDialog
        dialog = ProgressDialog(self.page, "Calculating Ion Coverage", stoppable=True)
        dialog.show()
        dialog.update_progress(None, "Preparing...", "Counting identifications...")

        # Count after dialog is visible so the UI doesn't appear frozen
        total_count = 0
        for tool_id in tool_ids:
            total_count += await self.project.get_identifications_count(
                tool_id=tool_id,
                only_missing=only_missing,
                spectra_file_ids=spectra_file_ids,
            )

        total_processed = 0
        chunk_size = max(1, math.ceil(_BATCH_SIZE / _WORKER_COUNT))
        stopped_early = False

        async def _compute_batch(
            loop, executor, worker_batch, ptm_list, max_ptm
        ) -> list:
            """Submit worker_batch to the process pool and gather results."""
            sub_batches = [
                worker_batch[i:i + chunk_size]
                for i in range(0, len(worker_batch), chunk_size)
            ]
            futures = [
                loop.run_in_executor(
                    executor,
                    process_identificatons_batch,
                    sub_batch,
                    params_dict,
                    fragment_charges,
                    target_ppm,
                    min_charge,
                    max_charge,
                    max_isotope_offset,
                    force_isotope_offset,
                    ptm_list,
                    max_ptm,
                    seq_criteria,
                    max_ptm_sites,
                )
                for sub_batch in sub_batches
            ]
            sub_results = await asyncio.gather(*futures)
            return [item for sub in sub_results for item in sub]

        async def _write_and_commit(results: list) -> None:
            """Write a computed batch to DB and commit without touching modified_at."""
            await self.project.put_identification_data_batch(results)
            await self.project._commit()

        try:
            loop = asyncio.get_event_loop()
            with ProcessPoolExecutor(max_workers=_WORKER_COUNT) as executor:
                for tool_id in tool_ids:
                    if stopped_early:
                        break
                    t_settings = tool_settings_map.get(tool_id, {})
                    ptm_list = t_settings.get('ptm_list', None)
                    max_ptm = t_settings.get('max_ptm', 5)

                    offset = 0

                    # --- Prime the pipeline: read and compute the first batch ---
                    dialog.update_progress(None, "Loading...", "Reading first batch...")
                    batch_objects = await self.project.get_identifications_with_spectra_batch(
                        tool_id=tool_id,
                        offset=offset,
                        limit=_BATCH_SIZE,
                        only_missing=only_missing,
                        spectra_file_ids=spectra_file_ids,
                    )

                    if not batch_objects:
                        continue

                    worker_batch = [obj.to_worker_dict() for obj in batch_objects]
                    del batch_objects  # free spectrum arrays from memory
                    offset += _BATCH_SIZE

                    pending_results = await _compute_batch(
                        loop, executor, worker_batch, ptm_list, max_ptm
                    )
                    del worker_batch

                    while True:
                        # --- Overlap: write previous results AND read next batch in parallel ---
                        next_read_task = asyncio.create_task(
                            self.project.get_identifications_with_spectra_batch(
                                tool_id=tool_id,
                                offset=offset,
                                limit=_BATCH_SIZE,
                                only_missing=only_missing,
                                spectra_file_ids=spectra_file_ids,
                            )
                        )
                        write_task = asyncio.create_task(
                            _write_and_commit(pending_results)
                        )
                        next_batch_objects, _ = await asyncio.gather(
                            next_read_task, write_task
                        )

                        total_processed += len(pending_results)
                        del pending_results
                        offset += _BATCH_SIZE

                        progress_value = (total_processed / total_count) if total_count > 0 else None
                        dialog.update_progress(
                            progress_value,
                            "Calculating...",
                            f"Processed {total_processed} / {total_count}",
                            processed=total_processed,
                            total=total_count,
                        )

                        if dialog.stop_requested:
                            stopped_early = True
                            break

                        if not next_batch_objects:
                            break

                        # --- Compute next batch while loop iterates ---
                        next_worker_batch = [obj.to_worker_dict() for obj in next_batch_objects]
                        del next_batch_objects  # free spectrum arrays from memory
                        pending_results = await _compute_batch(
                            loop, executor, next_worker_batch, ptm_list, max_ptm
                        )
                        del next_worker_batch

            await self.project.save()

            if stopped_early:
                dialog.complete(f"Stopped: {total_processed} / {total_count} processed")
            else:
                dialog.complete(f"Done: {total_processed} identifications")
            await asyncio.sleep(1)
            dialog.close()

            self.show_success(f"Ion coverage calculated for {total_processed} identifications")

        except Exception as exc:
            import traceback
            print(f"Error in IonCoverageAction.run: {traceback.format_exc()}")
            try:
                dialog.close()
            except Exception:
                pass
            self.show_error(f"Error: {exc}")


class SelectPreferredAction(BaseAction):
    """
    Select preferred identifications for spectra files.

    Extracted from MatchingSection.run_matching_internal().
    Supports optional per-sample filtering.
    """

    def __init__(self, project: Project, page: ft.Page):
        super().__init__(project, page)

    async def run(
        self,
        tool_settings: dict,
        criterion: str = 'intensity',
        sample_id: int | None = None,
    ) -> None:
        """
        Run preferred identification selection.

        Args:
            tool_settings: Tool-specific settings dict (from ToolSettingsSection).
            criterion: 'ppm' or 'intensity'.
            sample_id: If provided, only process files of this sample.
        """
        if not tool_settings:
            self.show_warning("No tools configured")
            return

        from dasmixer.gui.views.tabs.peptides.dialogs.progress_dialog import ProgressDialog
        from pathlib import Path

        dialog = ProgressDialog(self.page, "Running Identification Matching")
        dialog.show()

        try:
            spectre_files = await self.project.get_spectra_files(
                sample_id=sample_id if sample_id is not None else None
            )
            progress = 0.0
            processed_files = 0
            total_files = len(spectre_files)
            progress_step = round(1 / total_files, 3) if total_files > 0 else 1.0

            for _, spectra_file in spectre_files.iterrows():
                file_name = Path(spectra_file['path']).name
                dialog.update_progress(
                    progress,
                    f"Processing {file_name} ({processed_files + 1}/{total_files})..."
                )
                idents = await calculate_preferred_identifications_for_file(
                    self.project,
                    spectra_file['id'],
                    criterion,
                    tool_settings,
                )
                dialog.update_progress(
                    progress,
                    f"Saving {file_name} ({processed_files + 1}/{total_files})..."
                )
                await self.project.set_preferred_identifications_for_file(
                    spectra_file['id'],
                    idents,
                )
                progress += progress_step
                processed_files += 1

            dialog.complete(f"Completed {processed_files}/{total_files}!")
            await asyncio.sleep(0.5)
            dialog.close()

            self.show_success(f"Processed {processed_files} spectra files!")

        except Exception as ex:
            import traceback
            print(f"Error in SelectPreferredAction.run: {traceback.format_exc()}")
            try:
                dialog.close()
            except Exception:
                pass
            self.show_error(f"Error: {str(ex)}")
