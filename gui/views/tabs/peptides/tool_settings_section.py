"""Tool settings section for peptides tab."""

import flet as ft

from utils.seqfixer_utils import PTMS
from .base_section import BaseSection

# Full list of available PTM codes from PTMS registry
_ALL_PTM_CODES: list[str] = [ptm.code for ptm in PTMS]


class ToolSettingsSection(BaseSection):
    """Tool-specific settings configuration."""

    def _build_content(self) -> ft.Control:
        """Build tool settings UI."""
        self.tools_container = ft.Column(spacing=10)

        return ft.Column([
            ft.Text("Tool Settings", size=18, weight=ft.FontWeight.BOLD),
            self.tools_container
        ], spacing=10)

    async def load_data(self):
        """Load tools and their settings."""
        await self.refresh_tools()

    async def refresh_tools(self):
        """Refresh tools list and controls."""
        try:
            tools = await self.project.get_tools()
            self.state.tools_list = tools
            self.tools_container.controls.clear()
            self.state.tool_settings_controls.clear()

            if not tools:
                self.tools_container.controls.append(
                    ft.Text(
                        "No tools configured. Add tools in Samples tab.",
                        italic=True,
                        color=ft.Colors.GREY_600,
                    )
                )
            else:
                for tool in tools:
                    controls = self._create_tool_controls(tool)
                    self.state.tool_settings_controls[tool.id] = controls
                    self.tools_container.controls.append(
                        self._build_tool_card(tool, controls)
                    )

            self.tools_container.update()
            self.state.needs_tool_refresh = False

        except Exception as ex:
            print(f"Error refreshing tools: {ex}")
            self.show_error(f"Error loading tools: {str(ex)}")

    def _create_tool_controls(self, tool) -> dict:
        """
        Create control widgets for a single tool.

        Includes:
        - Basic quality filters: max_ppm, min_score, min_ion_intensity_coverage
        - Peptide length filters: min_peptide_length, max_peptide_length
        - Quality filters: min_top_peaks, min_ions_covered, min_spectre_peaks
        - Protein matching: use_protein_from_file, min_protein_identity,
          denovo_correction
        - leucine_combinatorics
        - PTM selection (via dialog)
        - max_ptm: maximum simultaneous PTMs to try
        """
        settings = tool.settings or {}

        # Determine initial PTM selection
        saved_ptm_list = settings.get('ptm_list', None)
        # None means "all PTMs"; empty list means "no PTMs"
        if saved_ptm_list is None:
            initial_ptm_selected = list(_ALL_PTM_CODES)
        else:
            initial_ptm_selected = list(saved_ptm_list)

        ptm_display_text = ', '.join(initial_ptm_selected) if initial_ptm_selected else '(none)'

        # Match correction criteria — load from saved settings
        saved_criteria: list[str] = settings.get('match_correction_criteria', ['ppm', 'intensity_coverage'])

        return {
            # ── Basic quality filters ──────────────────────────────────────
            'max_ppm': ft.TextField(
                label="Max PPM",
                value=str(settings.get('max_ppm', 50)),
                width=150,
                keyboard_type=ft.KeyboardType.NUMBER,
            ),
            'min_score': ft.TextField(
                label="Min Score",
                value=str(settings.get('min_score', 0.8)),
                width=150,
                keyboard_type=ft.KeyboardType.NUMBER,
            ),
            'min_ion_intensity_coverage': ft.TextField(
                label="Min Ion Coverage (%)",
                value=str(settings.get('min_ion_intensity_coverage', 25)),
                width=200,
                keyboard_type=ft.KeyboardType.NUMBER,
            ),
            # ── Peptide length ─────────────────────────────────────────────
            'min_peptide_length': ft.TextField(
                label="Min Peptide Length",
                value=str(settings.get('min_peptide_length', 7)),
                width=150,
                keyboard_type=ft.KeyboardType.NUMBER,
            ),
            'max_peptide_length': ft.TextField(
                label="Max Peptide Length",
                value=str(settings.get('max_peptide_length', 30)),
                width=150,
                keyboard_type=ft.KeyboardType.NUMBER,
            ),
            # ── Ion / peak quality thresholds ─────────────────────────────
            'min_top_peaks': ft.TextField(
                label="Min Top-10 Peaks Covered",
                value=str(settings.get('min_top_peaks', 1)),
                width=210,
                keyboard_type=ft.KeyboardType.NUMBER,
            ),
            'min_ions_covered': ft.TextField(
                label="Min Ions Covered",
                value=str(settings.get('min_ions_covered', 5)),
                width=180,
                keyboard_type=ft.KeyboardType.NUMBER,
            ),
            'min_spectre_peaks': ft.TextField(
                label="Min Spectrum Peaks",
                value=str(settings.get('min_spectre_peaks', 10)),
                width=180,
                keyboard_type=ft.KeyboardType.NUMBER,
            ),
            # ── Protein matching ───────────────────────────────────────────
            'use_protein_from_file': ft.Checkbox(
                label="Use protein ID from file",
                value=settings.get('use_protein_from_file', False),
            ),
            'min_protein_identity': ft.TextField(
                label="Min Protein Identity",
                value=str(settings.get('min_protein_identity', 0.75)),
                width=180,
                keyboard_type=ft.KeyboardType.NUMBER,
            ),
            'denovo_correction': ft.Checkbox(
                label="De novo correction",
                value=settings.get('denovo_correction', False),
            ),
            # ── Leucine combinatorics ──────────────────────────────────────
            'leucine_combinatorics': ft.Checkbox(
                label="Use Leucine Combinatorics (I/L)",
                value=settings.get('leucine_combinatorics', False),
            ),
            # ── PTM selection ──────────────────────────────────────────────
            # Internal state: list of selected PTM codes
            'ptm_selected': initial_ptm_selected,
            # Display text showing selected PTMs
            'ptm_display': ft.Text(
                value=ptm_display_text,
                size=12,
                color=ft.Colors.GREY_700,
                expand=True,
            ),
            # ── Max PTM combinations ───────────────────────────────────────
            'max_ptm': ft.TextField(
                label="Max PTM combinations",
                value=str(settings.get('max_ptm', 5)),
                width=180,
                keyboard_type=ft.KeyboardType.NUMBER,
                tooltip="Maximum number of simultaneous PTMs to try per sequence",
            ),
            # ── Match correction criteria ──────────────────────────────────
            'match_correction_ppm': ft.Checkbox(
                label="PPM",
                value='ppm' in saved_criteria,
            ),
            'match_correction_intensity': ft.Checkbox(
                label="Intensity coverage",
                value='intensity_coverage' in saved_criteria,
            ),
            'match_correction_ions': ft.Checkbox(
                label="Ions matched",
                value='ions_matched' in saved_criteria,
            ),
            'match_correction_top10': ft.Checkbox(
                label="Top 10 ions matched",
                value='top10_ions_matched' in saved_criteria,
            ),
            # ── Save AA substitutions ──────────────────────────────────────
            'save_aa_substitutions': ft.Checkbox(
                label="Save AA substitutions",
                value=settings.get('save_aa_substitutions', False),
                tooltip="Save partial matches as amino acid substitution candidates",
            ),
        }

    def _build_tool_card(self, tool, controls: dict) -> ft.Container:
        """Build a visual card for one tool's settings."""
        tool_id = tool.id

        ptm_button = ft.OutlinedButton(
            content=ft.Row([
                ft.Icon(ft.Icons.TUNE, size=16),
                ft.Text("Select PTMs...", size=13),
            ], spacing=4, tight=True),
            on_click=lambda e, tid=tool_id: ft.context.page.run_task(
                self._open_ptm_dialog, tid
            ),
        )

        return ft.Container(
            content=ft.Column([
                ft.Text(
                    f"{tool.name} ({tool.type})",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                ),
                # Row 1: basic quality
                ft.Row([
                    controls['max_ppm'],
                    controls['min_score'],
                    controls['min_ion_intensity_coverage'],
                ], spacing=10),
                # Row 2: peptide length
                ft.Row([
                    controls['min_peptide_length'],
                    controls['max_peptide_length'],
                ], spacing=10),
                # Row 3: ion / peak thresholds
                ft.Row([
                    controls['min_top_peaks'],
                    controls['min_ions_covered'],
                    controls['min_spectre_peaks'],
                ], spacing=10),
                # Row 4: protein matching flags
                controls['use_protein_from_file'],
                ft.Row([
                    controls['min_protein_identity'],
                    controls['denovo_correction'],
                ], spacing=10),
                # Row 5: leucine combinatorics
                controls['leucine_combinatorics'],
                # Row 6: PTM selection + max_ptm
                ft.Row([
                    controls['max_ptm'],
                ], spacing=10),
                ft.Row(
                    controls=[
                        ft.Container(
                            content=controls['ptm_display'],
                            expand=True,
                            border=ft.border.all(1, ft.Colors.GREY_300),
                            border_radius=4,
                            padding=ft.padding.symmetric(horizontal=8, vertical=6),
                        ),
                        ptm_button,
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                # Row 7: Match correction criteria
                ft.Text(
                    "Match Correction Criteria",
                    size=13,
                    weight=ft.FontWeight.W_500,
                    color=ft.Colors.GREY_700,
                ),
                ft.Row([
                    controls['match_correction_ppm'],
                    controls['match_correction_intensity'],
                    controls['match_correction_ions'],
                    controls['match_correction_top10'],
                ], spacing=15),
                # Row 8: Save AA substitutions
                controls['save_aa_substitutions'],
            ], spacing=10),
            padding=15,
            border=ft.border.all(1, ft.Colors.BLUE_200),
            border_radius=8,
            bgcolor=ft.Colors.BLUE_50,
        )

    # ------------------------------------------------------------------
    # PTM dialog
    # ------------------------------------------------------------------

    async def _open_ptm_dialog(self, tool_id: int):
        """Open PTM selection dialog for the given tool."""
        page = ft.context.page
        controls = self.state.tool_settings_controls.get(tool_id)
        if not controls:
            return

        current_selected: list[str] = list(controls['ptm_selected'])

        # Build checkboxes — one per PTM
        checkboxes: dict[str, ft.Checkbox] = {
            code: ft.Checkbox(
                label=code,
                value=(code in current_selected),
            )
            for code in _ALL_PTM_CODES
        }

        async def on_apply(e):
            selected = [code for code, cb in checkboxes.items() if cb.value]
            controls['ptm_selected'] = selected
            display_text = ', '.join(selected) if selected else '(none)'
            controls['ptm_display'].value = display_text
            controls['ptm_display'].update()
            dlg.open = False
            page.update()

        def on_cancel(e):
            dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Select PTMs"),
            content=ft.Column(
                controls=list(checkboxes.values()),
                tight=True,
                scroll=ft.ScrollMode.AUTO,
                width=300,
                height=300,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel),
                ft.ElevatedButton(
                    "Apply",
                    icon=ft.Icons.CHECK,
                    on_click=lambda e: page.run_task(on_apply, e),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_tool_settings(self, tool_id: int) -> tuple[bool, str | None]:
        """
        Validate all settings for a tool.

        Returns:
            (is_valid, error_message)
        """
        controls = self.state.tool_settings_controls.get(tool_id)
        if not controls:
            return False, "Tool controls not found"

        try:
            if float(controls['max_ppm'].value) < 0:
                return False, "Max PPM must be ≥ 0"

            if not (0 <= float(controls['min_score'].value) <= 1):
                return False, "Min Score must be in [0, 1]"

            if not (0 <= float(controls['min_ion_intensity_coverage'].value) <= 100):
                return False, "Min Ion Coverage must be in [0, 100]"

            if not (0 <= float(controls['min_protein_identity'].value) <= 1):
                return False, "Min Protein Identity must be in [0, 1]"

            min_len = int(controls['min_peptide_length'].value)
            max_len = int(controls['max_peptide_length'].value)
            if min_len < 1:
                return False, "Min Peptide Length must be ≥ 1"
            if max_len < min_len:
                return False, "Max Peptide Length must be ≥ Min Peptide Length"

            if int(controls['min_top_peaks'].value) < 0:
                return False, "Min Top-10 Peaks Covered must be ≥ 0"

            if int(controls['min_ions_covered'].value) < 0:
                return False, "Min Ions Covered must be ≥ 0"

            if int(controls['min_spectre_peaks'].value) < 0:
                return False, "Min Spectrum Peaks must be ≥ 0"

            max_ptm_val = int(controls['max_ptm'].value)
            if max_ptm_val < 0:
                return False, "Max PTM combinations must be ≥ 0"

            return True, None

        except ValueError as exc:
            return False, f"Invalid number: {exc}"

    # ------------------------------------------------------------------
    # Save / load
    # ------------------------------------------------------------------

    async def save_tool_settings(self, tool_id: int):
        """Validate and persist settings for one tool."""
        controls = self.state.tool_settings_controls.get(tool_id)
        if not controls:
            raise ValueError(f"No controls for tool {tool_id}")

        is_valid, error_msg = self.validate_tool_settings(tool_id)
        if not is_valid:
            raise ValueError(error_msg)

        tool = await self.project.get_tool(tool_id)
        if not tool:
            raise ValueError(f"Tool {tool_id} not found")

        # PTM list: store None if all PTMs selected (== default), else store list
        ptm_selected: list[str] = controls['ptm_selected']
        ptm_list_to_save = None if set(ptm_selected) == set(_ALL_PTM_CODES) else ptm_selected

        # Build match correction criteria list
        criteria_map = {
            'ppm': controls['match_correction_ppm'],
            'intensity_coverage': controls['match_correction_intensity'],
            'ions_matched': controls['match_correction_ions'],
            'top10_ions_matched': controls['match_correction_top10'],
        }
        match_correction_criteria = [k for k, cb in criteria_map.items() if cb.value]

        tool.settings = {
            'max_ppm': float(controls['max_ppm'].value),
            'min_score': float(controls['min_score'].value),
            'min_ion_intensity_coverage': float(controls['min_ion_intensity_coverage'].value),
            'use_protein_from_file': controls['use_protein_from_file'].value,
            'min_protein_identity': float(controls['min_protein_identity'].value),
            'denovo_correction': controls['denovo_correction'].value,
            'min_peptide_length': int(controls['min_peptide_length'].value),
            'max_peptide_length': int(controls['max_peptide_length'].value),
            'min_top_peaks': int(controls['min_top_peaks'].value),
            'min_ions_covered': int(controls['min_ions_covered'].value),
            'min_spectre_peaks': int(controls['min_spectre_peaks'].value),
            'leucine_combinatorics': controls['leucine_combinatorics'].value,
            'ptm_list': ptm_list_to_save,
            'max_ptm': int(controls['max_ptm'].value),
            'match_correction_criteria': match_correction_criteria,
            'save_aa_substitutions': controls['save_aa_substitutions'].value,
        }

        await self.project.update_tool(tool)

    async def save_all_tool_settings(self):
        """Save settings for all configured tools."""
        for tool_id in self.state.tool_settings_controls.keys():
            await self.save_tool_settings(tool_id)

    # ------------------------------------------------------------------
    # Settings extraction for matching pipeline
    # ------------------------------------------------------------------

    def get_tool_settings_for_matching(self) -> dict[int, dict]:
        """
        Return tool settings formatted for matching / protein-mapping functions.

        Returns:
            Mapping tool_id → settings dict with all keys expected by
            calculate_preferred_identifications_for_file() and map_proteins().
        """
        tool_settings = {}
        for tool_id, controls in self.state.tool_settings_controls.items():
            ptm_selected: list[str] = controls['ptm_selected']
            # Pass None to pipeline if all PTMs selected (use full PTMS list)
            ptm_list = None if set(ptm_selected) == set(_ALL_PTM_CODES) else ptm_selected

            criteria_map = {
                'ppm': controls['match_correction_ppm'],
                'intensity_coverage': controls['match_correction_intensity'],
                'ions_matched': controls['match_correction_ions'],
                'top10_ions_matched': controls['match_correction_top10'],
            }
            match_correction_criteria = [k for k, cb in criteria_map.items() if cb.value]

            tool_settings[tool_id] = {
                'max_ppm': float(controls['max_ppm'].value),
                'min_score': float(controls['min_score'].value),
                'min_ion_intensity_coverage': float(controls['min_ion_intensity_coverage'].value),
                'min_protein_identity': float(controls['min_protein_identity'].value),
                'denovo_correction': controls['denovo_correction'].value,
                'min_peptide_length': int(controls['min_peptide_length'].value),
                'max_peptide_length': int(controls['max_peptide_length'].value),
                'min_top_peaks': int(controls['min_top_peaks'].value),
                'min_ions_covered': int(controls['min_ions_covered'].value),
                'min_spectre_peaks': int(controls['min_spectre_peaks'].value),
                'leucine_combinatorics': controls['leucine_combinatorics'].value,
                'ptm_list': ptm_list,
                'max_ptm': int(controls['max_ptm'].value),
                'match_correction_criteria': match_correction_criteria,
                'save_aa_substitutions': controls['save_aa_substitutions'].value,
            }
        return tool_settings
