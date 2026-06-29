"""Table section - display protein results."""

import flet as ft
import pandas as pd

from .base_section import BaseSection
from dasmixer.utils import logger


class TableSection(BaseSection):
    """
    Results table section.
    
    Displays joined protein identification and quantification results.
    """
    
    def __init__(self, project, state, parent_tab):
        """
        Initialize table section.
        
        Args:
            project: Project instance
            state: Shared state
            parent_tab: Reference to parent ProteinsTab
        """
        self.parent_tab = parent_tab
        super().__init__(project, state)
    
    def _build_content(self) -> ft.Control:
        """Build table section UI."""
        # Sample filter dropdown
        self.sample_filter = ft.Dropdown(
            label="Filter by sample",
            hint_text="All samples",
            width=300,
            options=[],
            on_text_change=self._on_sample_filter_changed
        )
        
        # Header with filter
        header = ft.Row([
            ft.Text("Results", size=18, weight=ft.FontWeight.BOLD),
            ft.Container(width=20),
            self.sample_filter
        ], alignment=ft.MainAxisAlignment.START)
        
        # DataTable
        self.data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Sample")),
                ft.DataColumn(ft.Text("Subset")),
                ft.DataColumn(ft.Text("Protein ID")),
                ft.DataColumn(ft.Text("Gene")),
                ft.DataColumn(ft.Text("Weight (Da)")),
                ft.DataColumn(ft.Text("Peptides")),
                ft.DataColumn(ft.Text("Unique")),
                ft.DataColumn(ft.Text("Coverage %")),
                ft.DataColumn(ft.Text("Intensity Sum")),
                ft.DataColumn(ft.Text("emPAI")),
                ft.DataColumn(ft.Text("iBAQ")),
                ft.DataColumn(ft.Text("NSAF")),
                ft.DataColumn(ft.Text("Top3"))
            ],
            rows=[],
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=10,
            vertical_lines=ft.border.BorderSide(1, ft.Colors.GREY_300),
            horizontal_lines=ft.border.BorderSide(1, ft.Colors.GREY_300),
            heading_row_color=ft.Colors.GREY_200,
            heading_row_height=50,
            data_row_max_height=60
        )
        
        return ft.Column([
            header,
            ft.Container(height=10),
            ft.Container(
                content=ft.Column([self.data_table], scroll=ft.ScrollMode.AUTO),
                expand=True
            )
        ], spacing=10, expand=True)
    
    async def load_data(self):
        """
        Load data from database and populate table.
        
        Steps:
        1. Get joined protein results
        2. Update sample filter dropdown
        3. Build table rows
        4. Update UI
        """
        try:
            # Get data
            sample_filter = self.state.selected_sample
            df = await self.project.get_protein_results_joined(sample=sample_filter)
            
            # Store in state
            self.state.table_data = df
            
            # Update sample filter options
            all_samples = await self.project.execute_query_df("SELECT DISTINCT name FROM sample ORDER BY name")
            if len(all_samples) > 0:
                self.sample_filter.options = [
                    ft.DropdownOption(key="", text="All samples")
                ] + [
                    ft.DropdownOption(key=row['name'], text=row['name'])
                    for _, row in all_samples.iterrows()
                ]
            
            # Build table rows
            rows = []
            if len(df) > 0:
                for _, row in df.iterrows():
                    logger.debug('appending row to table...')
                    rows.append(
                        ft.DataRow(
                            cells=[
                                ft.DataCell(ft.Text(str(row['sample']) if pd.notna(row['sample']) else "")),
                                ft.DataCell(ft.Text(str(row['subset']) if pd.notna(row['subset']) else "")),
                                ft.DataCell(ft.Text(str(row['protein_id']))),
                                ft.DataCell(ft.Text(str(row['gene']) if pd.notna(row['gene']) else "")),
                                ft.DataCell(ft.Text(self._format_number(row['weight'], 2))),
                                ft.DataCell(ft.Text(str(row['peptide_count']))),
                                ft.DataCell(ft.Text(str(row['unique_evidence_count']))),
                                ft.DataCell(ft.Text(self._format_coverage(row['coverage_percent']))),
                                ft.DataCell(ft.Text(self._format_number(row['intensity_sum'], 2))),
                                ft.DataCell(ft.Text(self._format_number(row['EmPAI'], 4))),
                                ft.DataCell(ft.Text(self._format_number(row['iBAQ'], 2))),
                                ft.DataCell(ft.Text(self._format_number(row['NSAF'], 6))),
                                ft.DataCell(ft.Text(self._format_number(row['Top3'], 2)))
                            ]
                        )
                    )
            
            self.data_table.rows = rows
            
            if self.page:
                self.update()
        
        except Exception:
            logger.exception("Error loading data")
            self.show_error("Error loading data")
    
    def _on_sample_filter_changed(self, e):
        """Handle sample filter change."""
        value = e.control.value
        self.state.selected_sample = value if value else None
        # Reload data
        if self.page:
            self.page.run_task(self.load_data)
    
    def _format_coverage(self, value) -> str:
        """Format coverage as XX.X%."""
        if value is None or pd.isna(value):
            return ""
        return f"{float(value):.1f}%"
    
    def _format_number(self, value, decimals: int = 2) -> str:
        """Format numeric values."""
        if value is None or pd.isna(value):
            return ""
        return f"{float(value):.{decimals}f}"
