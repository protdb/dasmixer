"""Ion coverage and preferred identification selection actions."""

import asyncio
import os
from concurrent.futures import ProcessPoolExecutor

import flet as ft
from dasmixer.api.calculations.peptides.matching import (
    calculate_preferred_identifications_for_file,
)
from dasmixer.api.calculations.spectra.identification_processor import (
    process_identifications_batch,
)
from dasmixer.api.calculations.spectra.ion_match import IonMatchParameters
from dasmixer.api.calculations.spectra.queue_runner import (
    run_identification_queue,
)
from dasmixer.api.config import config as _config
from dasmixer.api.project.project import Project
from dasmixer.gui.views.tabs.peptides.shared_state import PeptidesTabState

from dasmixer.utils import logger

from .base import BaseAction


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
        # Get batch size and worker count from config
        batch_size = _config.identification_processing_batch_size
        worker_count = _config.max_cpu_threads or max(1, (os.cpu_count() or 2) - 1)
        
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
            from dasmixer.utils.seqfixer_utils import DEFAULT_PTM_CODES
            ptm_list = None if set(ptm_selected) == DEFAULT_PTM_CODES else ptm_selected
            max_ptm_ctrl = controls.get('max_ptm')
            try:
                max_ptm = int(max_ptm_ctrl.value) if max_ptm_ctrl else 5
            except (ValueError, AttributeError):
                max_ptm = 5
            min_quality_ctrl = controls.get('min_quality')
            try:
                quality_threshold = float(min_quality_ctrl.value) if min_quality_ctrl else 0.25
            except (ValueError, AttributeError):
                quality_threshold = 0.25
            trust_ppm = bool(controls.get('trust_ppm').value) if controls.get('trust_ppm') else False
            recalculate_ptms = bool(controls.get('recalculate_ptms').value) if controls.get('recalculate_ptms') else True
            unallocated_only = not recalculate_ptms
            tool_settings_map[tid] = {
                'ptm_list': ptm_list,
                'max_ptm': max_ptm,
                'quality_threshold': quality_threshold,
                'trust_ppm': trust_ppm,
                'unallocated_only': unallocated_only,
            }

        only_missing = not recalc_all

        # Resolve spectra_file_ids for sample filter
        spectra_file_ids: list[int] | None = None
        if sample_id is not None:
            sf_df = await self.project.get_spectra_files(sample_id=sample_id)
            if sf_df.empty:
                self.show_warning(f"No spectra files for sample id={sample_id}")
                return
            spectra_file_ids = list(sf_df['id'].astype(int))

        from dasmixer.gui.views.tabs.peptides.dialogs.progress_dialog import (
            ProgressDialog,
        )
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
        chunk_size = max(1, int(batch_size / worker_count))
        flush_every = worker_count
        stopped_early = False

        async def _flush_to_db(results: list) -> None:
            """Write a computed batch to DB and commit without touching modified_at."""
            await self.project.put_identification_data_batch(results)
            await self.project._commit()

        stop_check = lambda: dialog.stop_requested

        try:
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                for tool_id in tool_ids:
                    if stopped_early:
                        break
                    t_settings = tool_settings_map.get(tool_id, {})
                    ptm_list = t_settings.get('ptm_list', None)
                    max_ptm = t_settings.get('max_ptm', 5)

                    process_fn_kwargs = {
                        'params_dict': params_dict,
                        'fragment_charges': fragment_charges,
                        'target_ppm': target_ppm,
                        'min_charge': min_charge,
                        'max_charge': max_charge,
                        'max_isotope_offset': max_isotope_offset,
                        'force_isotope_offset_lookover': force_isotope_offset,
                        'ptm_names_list': ptm_list,
                        'max_ptm': max_ptm,
                        'seq_criteria': seq_criteria,
                        'max_ptm_sites': max_ptm_sites,
                        'trust_ppm': t_settings.get('trust_ppm', False),
                        'unallocated_only': t_settings.get('unallocated_only', False),
                        'quality_threshold': t_settings.get('quality_threshold', 0.25),
                    }

                    offset = 0

                    while True:
                        batch_objects = await self.project.get_identifications_with_spectra_batch(
                            tool_id=tool_id,
                            offset=0 if only_missing else offset,
                            limit=batch_size,
                            only_missing=only_missing,
                            spectra_file_ids=spectra_file_ids,
                        )
                        if not batch_objects:
                            break

                        worker_dicts = [obj.to_worker_dict() for obj in batch_objects]
                        del batch_objects  # free spectrum arrays

                        batch_start = total_processed

                        def _on_progress(cum: int, _batch_start: int = batch_start) -> None:
                            done = _batch_start + cum
                            value = (done / total_count) if total_count > 0 else None
                            dialog.update_progress(
                                value,
                                "Calculating...",
                                f"Processed {done} / {total_count}",
                                processed=done,
                                total=total_count,
                            )

                        processed_n = await run_identification_queue(
                            worker_dicts,
                            executor,
                            chunk_size,
                            flush_every,
                            process_identifications_batch,
                            process_fn_kwargs,
                            _flush_to_db,
                            progress_callback=_on_progress,
                            stop_check=stop_check,
                        )
                        del worker_dicts
                        total_processed += processed_n

                        if not only_missing:
                            offset += batch_size

                        dialog.update_progress(
                            (total_processed / total_count) if total_count > 0 else None,
                            "Calculating...",
                            f"Processed {total_processed} / {total_count}",
                            processed=total_processed,
                            total=total_count,
                        )

                        if dialog.stop_requested:
                            stopped_early = True
                            break

            await self.project.save()

            if stopped_early:
                dialog.complete(f"Stopped: {total_processed} / {total_count} processed")
            else:
                dialog.complete(f"Done: {total_processed} identifications")
            await asyncio.sleep(1)
            dialog.close()

            self.show_success(f"Ion coverage calculated for {total_processed} identifications")

        except Exception as exc:
            logger.exception(exc)
            try:
                dialog.close()
            except Exception:
                logger.debug("Failed to close progress dialog", exc_info=True)
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

        from pathlib import Path

        from dasmixer.gui.views.tabs.peptides.dialogs.progress_dialog import (
            ProgressDialog,
        )

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
            logger.exception(ex)
            try:
                dialog.close()
            except Exception:
                logger.debug("Failed to close progress dialog", exc_info=True)
            self.show_error(f"Error: {ex!s}")
