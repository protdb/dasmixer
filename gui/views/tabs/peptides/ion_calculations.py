"""Ion coverage calculations - backend service (no UI)."""

import flet as ft
import asyncio

from api.spectra.ion_match import IonMatchParameters, match_predictions
from utils.ppm import calculate_ppm
from api.project.project import Project
from .shared_state import PeptidesTabState
from .dialogs.progress_dialog import ProgressDialog


class IonCalculations:
    """
    Ion coverage and PPM calculations backend service.
    
    This is NOT a UI component - it's a pure calculation service.
    Singleton instance accessible via PeptidesTab.ion_calculations
    """
    
    def __init__(self, project: Project, state: PeptidesTabState):
        """
        Initialize ion calculations service.
        
        Args:
            project: Project instance
            state: Shared state
        """
        self.project = project
        self.state = state
    
    def show_error(self, message: str):
        """Show error snackbar using context."""
        try:
            page = ft.context.page
            page.snack_bar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=ft.Colors.RED_400
            )
            page.snack_bar.open = True
            page.update()
        except RuntimeError:
            print(f"ERROR: {message}")
    
    def show_success(self, message: str):
        """Show success snackbar using context."""
        try:
            page = ft.context.page
            page.snack_bar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=ft.Colors.GREEN_400
            )
            page.snack_bar.open = True
            page.update()
        except RuntimeError:
            print(f"SUCCESS: {message}")
    
    def show_info(self, message: str):
        """Show info snackbar using context."""
        try:
            page = ft.context.page
            page.snack_bar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=ft.Colors.BLUE_400
            )
            page.snack_bar.open = True
            page.update()
        except RuntimeError:
            print(f"INFO: {message}")
    
    def show_warning(self, message: str):
        """Show warning snackbar using context."""
        try:
            page = ft.context.page
            page.snack_bar = ft.SnackBar(
                content=ft.Text(message),
                bgcolor=ft.Colors.ORANGE_400
            )
            page.snack_bar.open = True
            page.update()
        except RuntimeError:
            print(f"WARNING: {message}")
    
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
                    size=11,
                    italic=True,
                    color=ft.Colors.GREY_600
                )
            ], tight=True, width=400),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=lambda e: setattr(dlg, 'open', False) or page.update()
                ),
                ft.ElevatedButton(
                    content=ft.Text("Only Missing"),
                    icon=ft.Icons.PLAYLIST_ADD,
                    on_click=lambda e: page.run_task(on_missing, e)
                ),
                ft.ElevatedButton(
                    content=ft.Text("All"),
                    icon=ft.Icons.REFRESH,
                    on_click=lambda e: page.run_task(on_all, e)
                )
            ]
        )
        
        page.overlay.append(dlg)
        dlg.open = True
        page.update()
    
    async def run_coverage_calc(self, recalc_all: bool):
        """
        Calculate ion coverage for identifications.
        
        Args:
            recalc_all: If True, recalculate all. If False, only missing.
        """
        try:
            page = ft.context.page
            
            # Get ion settings from ion_settings section and save them
            if hasattr(page, 'peptides_tab'):
                ion_settings_section = page.peptides_tab.sections.get('ion_settings')
                if ion_settings_section and hasattr(ion_settings_section, 'save_settings'):
                    await ion_settings_section.save_settings()
            
            # Get parameters
            params = self._get_ion_match_params()
            
            # Get identifications to process
            if recalc_all:
                query = "SELECT * FROM identification ORDER BY id"
            else:
                query = "SELECT * FROM identification WHERE intensity_coverage IS NULL ORDER BY id"
            
            idents_df = await self.project.execute_query_df(query)
            
            if len(idents_df) == 0:
                self.show_info("No identifications to process")
                return
            
            # Process with progress
            dialog = ProgressDialog(page, "Calculating Ion Coverage")
            dialog.show()
            
            total = len(idents_df)
            processed = 0
            
            for idx, ident in idents_df.iterrows():
                try:
                    spectrum = await self.project.get_spectrum_full(ident['spectre_id'])
                    charge = spectrum.get('charge') if spectrum.get('charge') else self.state.fragment_charges[0]
                    
                    result = match_predictions(
                        params=params,
                        mz=spectrum['mz_array'].tolist(),
                        intensity=spectrum['intensity_array'].tolist(),
                        charges=charge,
                        sequence=ident['sequence']
                    )
                    
                    await self.project.update_identification_coverage(
                        ident['id'],
                        result.intensity_percent
                    )
                    
                    processed += 1
                    
                    if processed % 10 == 0 or processed == total:
                        dialog.update_progress(
                            processed / total,
                            "Calculating...",
                            f"{processed}/{total}..."
                        )
                        
                except Exception as ex:
                    print(f"Error on identification {ident['id']}: {ex}")
            
            await self.project.save()
            
            dialog.complete(f"Processed {processed}")
            await asyncio.sleep(1)
            dialog.close()
            
            self.show_success(f"Calculated coverage for {processed} identifications")
            
        except Exception as ex:
            import traceback
            print(f"Error: {traceback.format_exc()}")
            self.show_error(f"Error: {str(ex)}")
    
    async def calculate_protein_metrics_internal(self):
        """Calculate PPM and coverage for protein matches."""
        try:
            page = ft.context.page
            
            # Get ion settings
            if hasattr(page, 'peptides_tab'):
                ion_settings_section = page.peptides_tab.sections.get('ion_settings')
                if ion_settings_section and hasattr(ion_settings_section, 'save_settings'):
                    await ion_settings_section.save_settings()
            
            # Get matches
            matches_df = await self.project.get_peptide_matches()
            
            if len(matches_df) == 0:
                self.show_warning("No matches found. Run protein mapping first.")
                return
            
            # Get parameters
            params = self._get_ion_match_params()
            
            # Process with progress
            dialog = ProgressDialog(page, "Calculating Protein Metrics")
            dialog.show()
            
            total = len(matches_df)
            processed = 0
            
            for idx, match in matches_df.iterrows():
                try:
                    # Get identification
                    ident_query = f"SELECT * FROM identification WHERE id = {int(match['identification_id'])}"
                    ident_df = await self.project.execute_query_df(ident_query)
                    
                    if len(ident_df) == 0:
                        continue
                    
                    ident = ident_df.iloc[0]
                    spectrum = await self.project.get_spectrum_full(ident['spectre_id'])
                    charge = spectrum.get('charge') if spectrum.get('charge') else self.state.fragment_charges[0]
                    
                    # Calculate PPM for matched sequence
                    matched_ppm = calculate_ppm(
                        sequence=match['matched_sequence'],
                        pepmass=spectrum['pepmass'],
                        charge=charge
                    )
                    
                    # Calculate coverage for matched sequence
                    result = match_predictions(
                        params=params,
                        mz=spectrum['mz_array'].tolist(),
                        intensity=spectrum['intensity_array'].tolist(),
                        charges=charge,
                        sequence=match['matched_sequence']
                    )
                    
                    # Update database
                    await self.project.update_peptide_match_metrics(
                        match['id'],
                        matched_ppm=matched_ppm,
                        matched_coverage_percent=result.intensity_percent
                    )
                    
                    processed += 1
                    
                    if processed % 10 == 0 or processed == total:
                        dialog.update_progress(
                            processed / total,
                            "Calculating...",
                            f"{processed}/{total}..."
                        )
                        
                except Exception as ex:
                    print(f"Error on match {match['id']}: {ex}")
            
            await self.project.save()
            
            dialog.complete(f"Processed {processed}")
            await asyncio.sleep(1)
            dialog.close()
            
            self.show_success(f"Calculated metrics for {processed} matches")
            
        except Exception as ex:
            import traceback
            print(f"Error: {traceback.format_exc()}")
            self.show_error(f"Error: {str(ex)}")
    
    def _get_ion_match_params(self) -> IonMatchParameters:
        """Get IonMatchParameters from shared state."""
        return IonMatchParameters(
            ions=self.state.ion_types,
            tolerance=self.state.ion_ppm_threshold,
            mode='largest',
            water_loss=self.state.water_loss,
            ammonia_loss=self.state.nh3_loss
        )
