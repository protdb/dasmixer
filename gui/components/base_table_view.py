"""Base class for all table views with pagination and filtering."""

import flet as ft
import pandas as pd
from typing import Optional, Callable


class BaseTableView(ft.Container):
    """
    Base class for all table views.
    
    Provides:
    - Filters panel (expandable)
    - Data table with pagination
    - Optional plot button per row
    - Filter persistence in project settings
    
    Subclasses must implement:
    - table_view_name: str - unique identifier
    - plot_id_field: Optional[str] - column name for plot ID (None = no plot button)
    - get_default_filters() -> dict
    - _build_filter_view() -> ft.Control
    - get_data(limit, offset) -> pd.DataFrame
    - get_total_count() -> int
    """
    
    table_view_name: str = "base_table"
    plot_id_field: Optional[str] = None
    
    def __init__(
        self,
        project,
        title: str = "Table",
        plot_callback: Optional[Callable[[str], None]] = None
    ):
        super().__init__()
        self.project = project
        self.title = title
        self.plot_callback = plot_callback
        
        # Filter state
        self.filter = self.get_default_filters()
        
        # Pagination state
        self.current_page = 0
        self.page_size = 50
        self.total_rows = 0
        
        # UI references
        self.filters_panel: Optional[ft.ExpansionPanel] = None
        self.data_panel: Optional[ft.ExpansionPanel] = None
        self.data_table: Optional[ft.DataTable] = None
        self.pagination_text: Optional[ft.Text] = None
        self.page_size_dropdown: Optional[ft.Dropdown] = None
        self.prev_button: Optional[ft.IconButton] = None
        self.next_button: Optional[ft.IconButton] = None
        
        # Build UI
        self.content = self._build_ui()
        self.padding = 10
        self.expand = True
    
    def get_default_filters(self) -> dict:
        """
        Get default filters for this table.
        
        Returns:
            dict: Default filters
        
        Note: Override in subclass
        """
        return {}
    
    def _build_filter_view(self) -> ft.Control:
        """
        Build UI for filters.
        
        Returns:
            ft.Control: Filters UI
        
        Note: Override in subclass
        """
        return ft.Text("No filters available")
    
    async def get_data(self, limit: int = 100, offset: int = 0) -> pd.DataFrame:
        """
        Get filtered data from database.
        
        Args:
            limit: Max rows to return
            offset: Number of rows to skip
        
        Returns:
            pd.DataFrame: Data
        
        Note: Override in subclass
        """
        raise NotImplementedError("Subclass must implement get_data()")
    
    async def get_total_count(self) -> int:
        """
        Get total count of rows with current filters.
        
        Returns:
            int: Total rows
        
        Note: Override in subclass
        """
        raise NotImplementedError("Subclass must implement get_total_count()")
    
    def _build_ui(self) -> ft.Control:
        """Build the complete UI."""
        # Filters panel
        print('building ui...')
        filter_content = ft.Column([
            self._build_filter_view(),
            ft.Container(height=10),
            ft.ElevatedButton(
                content=ft.Text("Apply Filters"),
                icon=ft.Icons.FILTER_ALT,
                on_click=self._on_apply_filters
            )
        ], spacing=5)
        print('building filters panel...')
        self.filters_panel = ft.ExpansionPanel(
            header=ft.ListTile(
                title=ft.Text("Filters", weight=ft.FontWeight.BOLD)
            ),
            content=ft.Container(content=filter_content, padding=10),
            can_tap_header=True
        )
        print('building data panel...')
        # Data table
        self.data_table = ft.DataTable(
            columns=[],
            rows=[],
            border=ft.border.all(1, ft.Colors.GREY_400),
            border_radius=5,
            vertical_lines=ft.BorderSide(1, ft.Colors.GREY_300),
            horizontal_lines=ft.BorderSide(1, ft.Colors.GREY_300),
            heading_row_color=ft.Colors.GREY_200,
            heading_row_height=40,
            data_row_min_height=35,
            data_row_max_height=100,
            column_spacing=20
        )
        print('building pagination...')
        # Pagination controls
        self.pagination_text = ft.Text("No data", size=12, color=ft.Colors.GREY_600)
        
        self.page_size_dropdown = ft.Dropdown(
            label="Rows per page",
            options=[
                ft.DropdownOption(key="25", text="25"),
                ft.DropdownOption(key="50", text="50"),
                ft.DropdownOption(key="100", text="100"),
                ft.DropdownOption(key="200", text="200")
            ],
            value="50",
            width=150,
            on_text_change=self._on_page_size_change
        )
        
        self.prev_button = ft.IconButton(
            icon=ft.Icons.ARROW_BACK,
            tooltip="Previous page",
            on_click=self._on_prev_page,
            disabled=True
        )
        
        self.next_button = ft.IconButton(
            icon=ft.Icons.ARROW_FORWARD,
            tooltip="Next page",
            on_click=self._on_next_page,
            disabled=True
        )
        
        pagination_row = ft.Row([
            self.pagination_text,
            ft.Container(expand=True),
            self.page_size_dropdown,
            self.prev_button,
            self.next_button
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        
        # Data panel
        data_content = ft.Column([
            ft.Container(
                content=self.data_table,
                border=ft.border.all(1, ft.Colors.GREY_300),
                border_radius=5,
                padding=5
            ),
            ft.Container(height=10),
            pagination_row
        ], spacing=5)
        
        self.data_panel = ft.ExpansionPanel(
            header=ft.ListTile(
                title=ft.Text("Data", weight=ft.FontWeight.BOLD)
            ),
            content=ft.Container(content=data_content, padding=10),
            can_tap_header=True,
            expanded=True
        )
        
        expansion_panel_list = ft.ExpansionPanelList(
            controls=[self.filters_panel, self.data_panel],
            expand_icon_color=ft.Colors.BLUE,
            elevation=2
        )
        
        return ft.Column([
            ft.Text(self.title, size=16, weight=ft.FontWeight.BOLD),
            ft.Container(height=5),
            expansion_panel_list
        ], expand=True, scroll=ft.ScrollMode.AUTO)
    
    async def _on_apply_filters(self, e):
        """Apply filters and reload data."""
        await self._update_filters_from_ui()
        await self._save_filters_to_project()
        
        self.current_page = 0
        await self._load_table_data()
        
        if self.page:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text("Filters applied"),
                bgcolor=ft.Colors.GREEN_400
            )
            self.page.snack_bar.open = True
            self.page.update()
    
    async def _update_filters_from_ui(self):
        """
        Read values from UI controls and update self.filter.
        
        Note: Override in subclass
        """
        pass
    
    async def _save_filters_to_project(self):
        """Save filters to project settings."""
        for key, value in self.filter.items():
            setting_key = f"table_view_{self.table_view_name}_filter_{key}"
            await self.project.set_setting(setting_key, str(value))
    
    async def _load_filters_from_project(self):
        """Load filters from project settings."""
        for key in self.filter.keys():
            setting_key = f"table_view_{self.table_view_name}_filter_{key}"
            value = await self.project.get_setting(setting_key)
            if value is not None:
                # Try to parse value
                default_value = self.filter[key]
                if isinstance(default_value, bool):
                    self.filter[key] = value.lower() in ('true', '1', 'yes')
                elif isinstance(default_value, int):
                    self.filter[key] = int(value)
                elif isinstance(default_value, float):
                    self.filter[key] = float(value)
                else:
                    self.filter[key] = value
    
    async def _load_table_data(self):
        """Load data and update table."""
        print('!!!!Loading table data...')
        try:
            # Get total count
            self.total_rows = await self.get_total_count()
            
            # Calculate offset
            offset = self.current_page * self.page_size
            
            # Get data
            df = await self.get_data(limit=self.page_size, offset=offset)
            
            # Update table
            self._update_table_from_dataframe(df)
            
            # Update pagination
            self._update_pagination_controls()
            
            if self.page:
                self.page.update()
            
        except Exception as ex:
            if self.page:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Error loading data: {ex}"),
                    bgcolor=ft.Colors.RED_400
                )
                self.page.snack_bar.open = True
                self.page.update()
    
    def _update_table_from_dataframe(self, df: pd.DataFrame):
        """Update DataTable from DataFrame."""
        if df.empty:
            self.data_table.columns = []
            self.data_table.rows = []
            return
        
        # Build columns
        columns = []
        for col in df.columns:
            columns.append(ft.DataColumn(ft.Text(str(col), weight=ft.FontWeight.BOLD)))
        
        # Add plot button column if needed
        if self.plot_id_field and self.plot_callback:
            columns.append(ft.DataColumn(ft.Text("Plot", weight=ft.FontWeight.BOLD)))
        
        self.data_table.columns = columns
        
        # Build rows
        rows = []
        for idx, row in df.iterrows():
            cells = []
            plot_id_value = None
            
            for col in df.columns:
                value = row[col]
                
                # Store plot ID if this is the plot ID field
                if col == self.plot_id_field:
                    plot_id_value = str(value)
                
                # Format value
                if pd.isna(value):
                    display_value = ""
                elif isinstance(value, float):
                    display_value = f"{value:.4f}"
                else:
                    display_value = str(value)
                
                cells.append(ft.DataCell(ft.Text(display_value)))
            
            # Add plot button if needed
            if self.plot_id_field and self.plot_callback and plot_id_value:
                plot_button = ft.IconButton(
                    icon=ft.Icons.SHOW_CHART,
                    tooltip="Show plot",
                    # on_click=lambda e, pid=plot_id_value: self.page.run_task(
                    #     self.plot_callback, pid
                    # )
                )
                cells.append(ft.DataCell(plot_button))
            
            rows.append(ft.DataRow(cells=cells))
        
        self.data_table.rows = rows
    
    def _update_pagination_controls(self):
        """Update pagination text and buttons."""
        if self.total_rows == 0:
            self.pagination_text.value = "No data"
            self.prev_button.disabled = True
            self.next_button.disabled = True
            return
        
        # Calculate display range
        start = self.current_page * self.page_size + 1
        end = min((self.current_page + 1) * self.page_size, self.total_rows)
        total_pages = (self.total_rows + self.page_size - 1) // self.page_size
        
        self.pagination_text.value = (
            f"Showing {start}-{end} of {self.total_rows} rows "
            f"(Page {self.current_page + 1} of {total_pages})"
        )
        
        # Update buttons
        self.prev_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= total_pages - 1)
    
    async def _on_page_size_change(self, e):
        """Handle page size change."""
        self.page_size = int(e.control.value)
        self.current_page = 0
        await self._load_table_data()
    
    async def _on_prev_page(self, e):
        """Go to previous page."""
        if self.current_page > 0:
            self.current_page -= 1
            await self._load_table_data()
    
    async def _on_next_page(self, e):
        """Go to next page."""
        total_pages = (self.total_rows + self.page_size - 1) // self.page_size
        if self.current_page < total_pages - 1:
            self.current_page += 1
            await self._load_table_data()
    
    async def load_data(self):
        """Load data (filters and table data)."""
        await self._load_filters_from_project()
        await self._load_table_data()
