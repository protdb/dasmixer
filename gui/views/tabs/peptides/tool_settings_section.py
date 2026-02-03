"""Tool settings section for peptides tab."""

import flet as ft

from .base_section import BaseSection


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
                        color=ft.Colors.GREY_600
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
        Create control widgets for tool settings.
        
        Includes NEW min/max peptide length controls.
        """
        settings = tool.settings or {}
        
        return {
            'max_ppm': ft.TextField(
                label="Max PPM",
                value=str(settings.get('max_ppm', 50)),
                width=150,
                keyboard_type=ft.KeyboardType.NUMBER
            ),
            'min_score': ft.TextField(
                label="Min Score",
                value=str(settings.get('min_score', 0.8)),
                width=150,
                keyboard_type=ft.KeyboardType.NUMBER
            ),
            'min_ion_intensity_coverage': ft.TextField(
                label="Min Ion Coverage (%)",
                value=str(settings.get('min_ion_intensity_coverage', 25)),
                width=200,
                keyboard_type=ft.KeyboardType.NUMBER
            ),
            'use_protein_from_file': ft.Checkbox(
                label="Use protein ID from file",
                value=settings.get('use_protein_from_file', False)
            ),
            'min_protein_identity': ft.TextField(
                label="Min Protein Identity",
                value=str(settings.get('min_protein_identity', 0.75)),
                width=180,
                keyboard_type=ft.KeyboardType.NUMBER
            ),
            'denovo_correction': ft.Checkbox(
                label="De novo correction",
                value=settings.get('denovo_correction', False)
            ),
            # NEW: Peptide length controls
            'min_peptide_length': ft.TextField(
                label="Min Peptide Length",
                value=str(settings.get('min_peptide_length', 7)),
                width=150,
                keyboard_type=ft.KeyboardType.NUMBER
            ),
            'max_peptide_length': ft.TextField(
                label="Max Peptide Length",
                value=str(settings.get('max_peptide_length', 30)),
                width=150,
                keyboard_type=ft.KeyboardType.NUMBER
            )
        }
    
    def _build_tool_card(self, tool, controls: dict) -> ft.Container:
        """Build tool settings card."""
        return ft.Container(
            content=ft.Column([
                ft.Text(f"{tool.name} ({tool.type})", size=16, weight=ft.FontWeight.BOLD),
                ft.Row([
                    controls['max_ppm'],
                    controls['min_score'],
                    controls['min_ion_intensity_coverage']
                ], spacing=10),
                ft.Row([
                    controls['min_peptide_length'],
                    controls['max_peptide_length']
                ], spacing=10),
                controls['use_protein_from_file'],
                ft.Row([
                    controls['min_protein_identity'],
                    controls['denovo_correction']
                ], spacing=10)
            ], spacing=10),
            padding=15,
            border=ft.border.all(1, ft.Colors.BLUE_200),
            border_radius=8,
            bgcolor=ft.Colors.BLUE_50
        )
    
    def validate_tool_settings(self, tool_id: int) -> tuple[bool, str | None]:
        """
        Validate tool settings.
        
        Returns:
            (is_valid, error_message)
        """
        controls = self.state.tool_settings_controls.get(tool_id)
        if not controls:
            return False, "Tool controls not found"
        
        try:
            # Validate max_ppm
            if float(controls['max_ppm'].value) < 0:
                return False, "Max PPM must be > 0"
            
            # Validate min_score
            if not (0 <= float(controls['min_score'].value) <= 1):
                return False, "Min Score must be 0-1"
            
            # Validate coverage
            if not (0 <= float(controls['min_ion_intensity_coverage'].value) <= 100):
                return False, "Coverage must be 0-100"
            
            # Validate protein identity
            if not (0 <= float(controls['min_protein_identity'].value) <= 1):
                return False, "Identity must be 0-1"
            
            # NEW: Validate peptide lengths
            min_len = int(controls['min_peptide_length'].value)
            max_len = int(controls['max_peptide_length'].value)
            
            if min_len < 1:
                return False, "Min length must be >= 1"
            
            if max_len < min_len:
                return False, "Max length must be >= Min length"
            
            return True, None
            
        except ValueError as e:
            return False, f"Invalid number: {str(e)}"
    
    async def save_tool_settings(self, tool_id: int):
        """Save tool settings to project."""
        controls = self.state.tool_settings_controls.get(tool_id)
        if not controls:
            raise ValueError(f"No controls for tool {tool_id}")
        
        # Validate first
        is_valid, error_msg = self.validate_tool_settings(tool_id)
        if not is_valid:
            raise ValueError(error_msg)
        
        # Get tool
        tool = await self.project.get_tool(tool_id)
        if not tool:
            raise ValueError(f"Tool {tool_id} not found")
        
        # Update settings
        tool.settings = {
            'max_ppm': float(controls['max_ppm'].value),
            'min_score': float(controls['min_score'].value),
            'min_ion_intensity_coverage': float(controls['min_ion_intensity_coverage'].value),
            'use_protein_from_file': controls['use_protein_from_file'].value,
            'min_protein_identity': float(controls['min_protein_identity'].value),
            'denovo_correction': controls['denovo_correction'].value,
            # NEW: Save peptide lengths
            'min_peptide_length': int(controls['min_peptide_length'].value),
            'max_peptide_length': int(controls['max_peptide_length'].value)
        }
        
        await self.project.update_tool(tool)
    
    async def save_all_tool_settings(self):
        """Save all tool settings."""
        for tool_id in self.state.tool_settings_controls.keys():
            await self.save_tool_settings(tool_id)
    
    def get_tool_settings_for_matching(self) -> dict[int, dict]:
        """
        Get tool settings formatted for matching functions.
        
        Returns:
            dict mapping tool_id to settings dict
        """
        tool_settings = {}
        
        for tool_id, controls in self.state.tool_settings_controls.items():
            tool_settings[tool_id] = {
                'max_ppm': float(controls['max_ppm'].value),
                'min_score': float(controls['min_score'].value),
                'min_ion_intensity_coverage': float(controls['min_ion_intensity_coverage'].value),
                'min_protein_identity': float(controls['min_protein_identity'].value),
                'denovo_correction': controls['denovo_correction'].value,
                # NEW: Include peptide lengths
                'min_peptide_length': int(controls['min_peptide_length'].value),
                'max_peptide_length': int(controls['max_peptide_length'].value)
            }
        
        return tool_settings
