"""LFQ section - label-free quantification calculation."""

import flet as ft
import asyncio

from .base_section import BaseSection
from dasmixer.gui.views.tabs.peptides.dialogs.progress_dialog import ProgressDialog
from dasmixer.api.calculations.proteins.sempai import SUPPORTED_ENZYMES
from dasmixer.api.calculations.proteins.lfq import calculate_lfq


class LFQSection(BaseSection):
    """
    Label-Free Quantification section.
    
    Manages parameters and execution of LFQ calculations.
    """
    
    def __init__(self, project, state, parent_tab):
        """
        Initialize LFQ section.
        
        Args:
            project: Project instance
            state: Shared state
            parent_tab: Reference to parent ProteinsTab
        """
        self.parent_tab = parent_tab
        super().__init__(project, state)
    
    def _build_content(self) -> ft.Control:
        """Build LFQ section UI."""
        # Method checkboxes
        self.empai_checkbox = ft.Checkbox(
            label="emPAI",
            value=self.state.lfq_methods['emPAI'],
            on_change=lambda e: self._on_method_changed('emPAI', e)
        )
        print('empai checkbox built...')
        
        self.ibaq_checkbox = ft.Checkbox(
            label="iBAQ",
            value=self.state.lfq_methods['iBAQ'],
            on_change=lambda e: self._on_method_changed('iBAQ', e)
        )
        print('iBAQ checkbox built...')
        
        self.nsaf_checkbox = ft.Checkbox(
            label="NSAF",
            value=self.state.lfq_methods['NSAF'],
            on_change=lambda e: self._on_method_changed('NSAF', e)
        )
        print('NSAF checkbox built...')
        
        self.top3_checkbox = ft.Checkbox(
            label="Top3",
            value=self.state.lfq_methods['Top3'],
            on_change=lambda e: self._on_method_changed('Top3', e)
        )
        print('Top3 checkbox built...')
        # emPAI base value
        self.empai_base_field = ft.TextField(
            label="emPAI base value",
            value=str(self.state.empai_base_value),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=200,
            on_change=self._on_empai_base_changed
        )
        print('empai base field built...')
        
        # Enzyme dropdown
        enzyme_options = [
            ft.DropdownOption(key=key, text=text.title())
            for key, text in SUPPORTED_ENZYMES.items()
        ]
        
        self.enzyme_dropdown = ft.Dropdown(
            label="Enzyme",
            value=self.state.enzyme,
            width=250,
            options=enzyme_options,
            on_text_change=self._on_enzyme_changed
        )
        print('Enzyme dropdown built...')
        # Peptide length fields
        self.min_length_field = ft.TextField(
            label="Min peptide length",
            value=str(self.state.min_peptide_length),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=150,
            on_change=self._on_min_length_changed
        )
        print('Min peptide length field built...')
        
        self.max_length_field = ft.TextField(
            label="Max peptide length",
            value=str(self.state.max_peptide_length),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=150,
            on_change=self._on_max_length_changed
        )
        print('Max peptide length field built...')
        
        # Max cleavage sites
        self.max_cleavage_field = ft.TextField(
            label="Max cleavage sites",
            value=str(self.state.max_cleavage_sites),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=150,
            on_change=self._on_max_cleavage_changed
        )
        print('Max cleavage sites field built...')
        
        # Calculate button
        self.calculate_btn = ft.ElevatedButton(
            content=ft.Text("Calculate LFQ"),
            icon=ft.Icons.CALCULATE,
            on_click=lambda e: self.page.run_task(self.calculate_lfq, e),
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.GREEN_600,
                color=ft.Colors.WHITE
            )
        )
        print('Calculate button built...')
        
        return ft.Column([
            ft.Text("Label-Free Quantification", size=18, weight=ft.FontWeight.BOLD),
            ft.Container(height=10),
            ft.Text("Methods:", size=14, weight=ft.FontWeight.BOLD),
            ft.Row([
                self.empai_checkbox,
                self.ibaq_checkbox,
                self.nsaf_checkbox,
                self.top3_checkbox
            ]),
            ft.Container(height=10),
            ft.Row([
                self.empai_base_field,
                ft.Container(width=10),
                self.enzyme_dropdown
            ]),
            ft.Container(height=5),
            ft.Row([
                self.min_length_field,
                ft.Container(width=10),
                self.max_length_field,
                ft.Container(width=10),
                self.max_cleavage_field
            ]),
            ft.Container(height=10),
            self.calculate_btn
        ], spacing=10)
    
    async def load_data(self):
        """Load settings from project."""
        # Load LFQ methods
        for method in ['emPAI', 'iBAQ', 'NSAF', 'Top3']:
            value = await self.project.get_setting(f'lfq_method_{method}')
            if value is not None:
                self.state.lfq_methods[method] = value == 'True'
        
        # Load emPAI base
        empai_base = await self.project.get_setting('lfq_empai_base')
        if empai_base is not None:
            self.state.empai_base_value = float(empai_base)
            self.empai_base_field.value = empai_base
        
        # Load enzyme
        enzyme = await self.project.get_setting('lfq_enzyme')
        if enzyme is not None:
            self.state.enzyme = enzyme
            self.enzyme_dropdown.value = enzyme
        
        # Load peptide length
        min_len = await self.project.get_setting('lfq_min_peptide_length')
        if min_len is not None:
            self.state.min_peptide_length = int(min_len)
            self.min_length_field.value = min_len
        
        max_len = await self.project.get_setting('lfq_max_peptide_length')
        if max_len is not None:
            self.state.max_peptide_length = int(max_len)
            self.max_length_field.value = max_len
        
        # Load max cleavage
        max_cleav = await self.project.get_setting('lfq_max_cleavage_sites')
        if max_cleav is not None:
            self.state.max_cleavage_sites = int(max_cleav)
            self.max_cleavage_field.value = max_cleav
        
        # Update checkboxes
        self.empai_checkbox.value = self.state.lfq_methods['emPAI']
        self.ibaq_checkbox.value = self.state.lfq_methods['iBAQ']
        self.nsaf_checkbox.value = self.state.lfq_methods['NSAF']
        self.top3_checkbox.value = self.state.lfq_methods['Top3']
        
        if self.page:
            self.update()
    
    def _on_method_changed(self, method: str, e):
        """Update state when method checkbox changes."""
        self.state.lfq_methods[method] = e.control.value
    
    def _on_empai_base_changed(self, e):
        """Update state when emPAI base value changes."""
        try:
            value = float(e.control.value)
            self.state.empai_base_value = value
        except ValueError:
            pass
    
    def _on_enzyme_changed(self, e):
        """Update state when enzyme changes."""
        self.state.enzyme = e.control.value
    
    def _on_min_length_changed(self, e):
        """Update state when min peptide length changes."""
        try:
            value = int(e.control.value)
            self.state.min_peptide_length = value
        except ValueError:
            pass
    
    def _on_max_length_changed(self, e):
        """Update state when max peptide length changes."""
        try:
            value = int(e.control.value)
            self.state.max_peptide_length = value
        except ValueError:
            pass
    
    def _on_max_cleavage_changed(self, e):
        """Update state when max cleavage sites changes."""
        try:
            value = int(e.control.value)
            self.state.max_cleavage_sites = value
        except ValueError:
            pass
    
    async def calculate_lfq(self, e):
        """
        Calculate LFQ for all samples.
        
        Workflow:
        1. Validate at least one method selected
        2. Show progress dialog
        3. Clear old quantifications
        4. Get all sample IDs
        5. For each sample, calculate LFQ
        6. Save results
        7. Update state and refresh table
        """
        # Validate
        selected_methods = self.state.get_selected_lfq_methods()
        if not selected_methods:
            self.show_warning("Please select at least one LFQ method")
            return
        
        # Validate numeric parameters
        try:
            empai_base = float(self.empai_base_field.value)
            min_len = int(self.min_length_field.value)
            max_len = int(self.max_length_field.value)
            max_cleav = int(self.max_cleavage_field.value)
            
            if empai_base <= 0:
                self.show_error("emPAI base value must be positive")
                return
            
            if min_len < 1 or max_len < min_len:
                self.show_error("Invalid peptide length range")
                return
            
            if max_cleav < 0:
                self.show_error("Max cleavage sites cannot be negative")
                return
        except ValueError:
            self.show_error("Please enter valid numbers")
            return
        
        # Update state from current field values
        self.state.empai_base_value = empai_base
        self.state.min_peptide_length = min_len
        self.state.max_peptide_length = max_len
        self.state.max_cleavage_sites = max_cleav

        # Save settings to project
        for method in ['emPAI', 'iBAQ', 'NSAF', 'Top3']:
            await self.project.set_setting(f'lfq_method_{method}', str(self.state.lfq_methods[method]))
        await self.project.set_setting('lfq_empai_base', str(empai_base))
        await self.project.set_setting('lfq_enzyme', self.state.enzyme)
        await self.project.set_setting('lfq_min_peptide_length', str(min_len))
        await self.project.set_setting('lfq_max_peptide_length', str(max_len))
        await self.project.set_setting('lfq_max_cleavage_sites', str(max_cleav))

        from dasmixer.gui.actions.lfq_action import LFQAction
        action = LFQAction(self.project, self.page)
        await action.run(state=self.state)

        # Update counts and refresh table
        self.state.protein_quantification_count = await self.project.get_protein_quantification_count()
        if hasattr(self.parent_tab, 'sections') and 'table' in self.parent_tab.sections:
            await self.parent_tab.sections['table'].load_data()
