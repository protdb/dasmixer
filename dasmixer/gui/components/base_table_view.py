"""Base class for all table views with pagination and filtering."""

import flet as ft
import pandas as pd
from typing import Callable
from dasmixer.utils import logger
from dasmixer.gui.utils import show_snack


class BaseTableView(ft.Container):
    """
    Base class for all table views.

    Provides:
    - Filters panel (expandable)
    - Data table with pagination
    - Optional plot button per row
    - Filter persistence in project settings
    - Column visibility settings (gear button)
    - Human-readable column headers via header_name_mapping
    - Tooltips from tooltips_df
    - Clickable cell values for filter setting via column_filter_mapping
    - Export to CSV/XLSX

    Subclasses must implement:
    - table_view_name: str
    - plot_id_field: str | None
    - header_name_mapping: dict[str, str]
    - column_filter_mapping: dict[str, str]
    - get_default_filters() -> dict
    - _build_filter_view() -> ft.Control
    - get_data(limit, offset) -> tuple[pd.DataFrame, pd.DataFrame | None]
    - get_total_count() -> int
    """

    table_view_name: str = "base_table"
    plot_id_field: str | None = None
    header_name_mapping: dict[str, str] = {}
    column_filter_mapping: dict[str, str] = {}
    # Columns shown by default. Empty set = show all columns.
    # When non-empty, only these columns are visible on first load;
    # the rest are available via the gear dialog.
    default_columns: set[str] = set()

    def __init__(
        self,
        project,
        title: str = "Table",
        plot_callback: Callable[[str], None] | None = None
    ):
        super().__init__()
        self.project = project
        self.title = title
        self.plot_callback = plot_callback

        self.filter = self.get_default_filters()
        self.filter_controls: dict[str, ft.Control] = {}

        self.current_page = 0
        self.page_size = 20
        self.total_rows = 0
        self.has_data = False
        self.is_loading = False

        self._last_df: pd.DataFrame | None = None
        self._last_tooltips_df: pd.DataFrame | None = None
        self._all_columns: list[str] = []
        self._visible_columns: set[str] = set()

        # suspend/resume support
        self._is_suspended: bool = False

        self.filters_panel: ft.ExpansionPanel | None = None
        self.data_panel: ft.ExpansionPanel | None = None
        self.data_container: ft.Container | None = None
        self.data_table: ft.DataTable | None = None
        self.pagination_text: ft.Text | None = None
        self.page_size_dropdown: ft.Dropdown | None = None
        self.prev_button: ft.IconButton | None = None
        self.next_button: ft.IconButton | None = None
        self._column_settings_button: ft.IconButton | None = None

        self.content = self._build_ui()
        self.padding = 10
        self.expand = True

    # ------------------------------------------------------------------
    # Subclass interface
    # ------------------------------------------------------------------

    def get_default_filters(self) -> dict:
        return {}

    def _build_filter_view(self) -> ft.Control:
        return ft.Text("No filters available")

    async def get_data(self, limit: int = 100, offset: int = 0) -> tuple[pd.DataFrame, pd.DataFrame | None]:
        raise NotImplementedError("Subclass must implement get_data()")

    async def get_total_count(self) -> int:
        raise NotImplementedError("Subclass must implement get_total_count()")

    # ------------------------------------------------------------------
    # filter_controls helpers
    # ------------------------------------------------------------------

    def get_filters_from_ui(self):
        for filter_key, control in self.filter_controls.items():
            if hasattr(control, 'value'):
                self.filter[filter_key] = control.value

    async def set_filters_in_ui(self, filter_key: str, value):
        if filter_key in self.filter_controls:
            control = self.filter_controls[filter_key]
            if hasattr(control, 'value'):
                control.value = str(value)
                if self.page:
                    control.update()
        self.filter[filter_key] = value
        self.current_page = 0
        await self._load_table_data()

    # ------------------------------------------------------------------
    # Tooltip helper
    # ------------------------------------------------------------------

    def get_tooltip(self, column_name: str, idx) -> str | None:
        if self._last_tooltips_df is None:
            return None
        if column_name not in self._last_tooltips_df.columns:
            return None
        try:
            val = self._last_tooltips_df.at[idx, column_name]
            if val is None:
                return None
            if isinstance(val, float) and pd.isna(val):
                return None
            return str(val)
        except (KeyError, TypeError):
            return None

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------

    def _build_ui(self) -> ft.Control:
        filter_content = ft.Column([
            self._build_filter_view(),
            ft.Container(height=10),
            ft.ElevatedButton(
                content=ft.Text("Apply Filters"),
                icon=ft.Icons.FILTER_ALT,
                on_click=self._on_apply_filters
            )
        ], spacing=5)

        self.filters_panel = ft.ExpansionPanel(
            header=ft.ListTile(title=ft.Text("Filters", weight=ft.FontWeight.BOLD)),
            content=ft.Container(content=filter_content, padding=10),
            can_tap_header=True
        )

        self._column_settings_button = ft.IconButton(
            icon=ft.Icons.SETTINGS,
            tooltip="Column visibility",
            on_click=lambda e: self.page.run_task(self._show_column_settings_dialog) if self.page else None,
            disabled=True
        )

        self.data_container = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.INFO_OUTLINE, size=48, color=ft.Colors.GREY_400),
                ft.Text("Click 'Apply Filters' to load data", size=14, color=ft.Colors.GREY_600)
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            alignment=ft.Alignment.CENTER,
            height=300
        )

        self.pagination_text = ft.Text("No data", size=12, color=ft.Colors.GREY_600)

        self.page_size_dropdown = ft.Dropdown(
            label="Rows per page",
            options=[
                ft.DropdownOption(key="20", text="20"),
                ft.DropdownOption(key="50", text="50"),
                ft.DropdownOption(key="100", text="100"),
                ft.DropdownOption(key="200", text="200")
            ],
            value="20",
            width=150,
            on_text_change=self._on_page_size_change
        )

        self.prev_button = ft.IconButton(
            icon=ft.Icons.ARROW_BACK, tooltip="Previous page",
            on_click=self._on_prev_page, disabled=True
        )

        self.next_button = ft.IconButton(
            icon=ft.Icons.ARROW_FORWARD, tooltip="Next page",
            on_click=self._on_next_page, disabled=True
        )

        export_button = ft.ElevatedButton(
            content=ft.Text("Export"),
            icon=ft.Icons.DOWNLOAD,
            on_click=lambda e: self.page.run_task(self._on_export, e) if self.page else None
        )

        pagination_row = ft.Row([
            self.pagination_text,
            ft.Container(expand=True),
            export_button,
            self.page_size_dropdown,
            self.prev_button,
            self.next_button
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        data_content = ft.Column([
            ft.Row([ft.Container(expand=True), self._column_settings_button]),
            self.data_container,
            ft.Container(height=10),
            pagination_row
        ], spacing=5)

        self.data_panel = ft.ExpansionPanel(
            header=ft.ListTile(title=ft.Text("Data", weight=ft.FontWeight.BOLD)),
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

    # ------------------------------------------------------------------
    # Filter apply / save / load
    # ------------------------------------------------------------------

    async def _on_apply_filters(self, e):
        await self._update_filters_from_ui()
        await self._save_filters_to_project()
        self.current_page = 0
        await self._load_table_data()
        if self.page:
            show_snack(self.page, "Filters applied", ft.Colors.GREEN_400)
            self.page.update()

    async def _update_filters_from_ui(self):
        pass

    async def _save_filters_to_project(self):
        for key, value in self.filter.items():
            setting_key = f"table_view_{self.table_view_name}_filter_{key}"
            await self.project.set_setting(setting_key, str(value))

    async def _load_filters_from_project(self):
        for key in self.filter.keys():
            setting_key = f"table_view_{self.table_view_name}_filter_{key}"
            value = await self.project.get_setting(setting_key)
            if value is not None:
                default_value = self.filter[key]
                if isinstance(default_value, bool):
                    self.filter[key] = value.lower() in ('true', '1', 'yes')
                elif isinstance(default_value, int):
                    self.filter[key] = int(value)
                elif isinstance(default_value, float):
                    self.filter[key] = float(value)
                else:
                    self.filter[key] = value

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    async def _load_table_data(self):
        try:
            self.is_loading = True
            self._show_loading()

            self.total_rows = await self.get_total_count()

            if self.total_rows == 0:
                self.has_data = False
                self._show_no_data()
                return

            offset = self.current_page * self.page_size
            result = await self.get_data(limit=self.page_size, offset=offset)

            if isinstance(result, tuple):
                df, tooltips_df = result
            else:
                df, tooltips_df = result, None

            self.has_data = True
            self._last_tooltips_df = tooltips_df
            self._update_table_from_dataframe(df)
            self._update_pagination_controls()

            if self.page:
                self.page.update()

        except Exception as ex:
            self.has_data = False
            self._show_error(str(ex))
            if self.page:
                logger.exception(ex)
                show_snack(self.page, f"Error loading data: {ex}", ft.Colors.RED_400)
                self.page.update()
        finally:
            self.is_loading = False

    # ------------------------------------------------------------------
    # State display helpers
    # ------------------------------------------------------------------

    def _show_loading(self):
        self.data_container.content = ft.Column([
            ft.ProgressRing(),
            ft.Text("Loading data...", size=14, color=ft.Colors.GREY_600)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
        self.data_container.alignment = ft.Alignment.CENTER
        self.data_container.height = 300
        if self.page:
            self.data_container.update()

    def _show_no_data(self):
        self.data_container.content = ft.Column([
            ft.Icon(ft.Icons.SEARCH_OFF, size=48, color=ft.Colors.GREY_400),
            ft.Text("Nothing to show", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_600),
            ft.Text("Try adjusting your filters", size=12, color=ft.Colors.GREY_500)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
        self.data_container.alignment = ft.Alignment.CENTER
        self.data_container.height = 300
        self.pagination_text.value = "No data"
        self.prev_button.disabled = True
        self.next_button.disabled = True
        self._column_settings_button.disabled = True
        if self.page:
            self.data_container.update()
            self.pagination_text.update()
            self.prev_button.update()
            self.next_button.update()
            self._column_settings_button.update()

    def _show_error(self, error_message: str):
        self.data_container.content = ft.Column([
            ft.Icon(ft.Icons.ERROR_OUTLINE, size=48, color=ft.Colors.RED_400),
            ft.Text("Error loading data", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_600),
            ft.Text(error_message, size=12, color=ft.Colors.GREY_600)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
        self.data_container.alignment = ft.Alignment.CENTER
        self.data_container.height = 300
        if self.page:
            self.data_container.update()

    # ------------------------------------------------------------------
    # Table rendering
    # ------------------------------------------------------------------

    def _update_table_from_dataframe(self, df: pd.DataFrame):
        if df.empty:
            self._show_no_data()
            return

        self._last_df = df
        new_cols = list(df.columns)

        if not self._all_columns:
            # First load — initialise visible columns.
            # If default_columns is set, use it as the initial visible set
            # (intersected with what the df actually returned).
            # Otherwise show everything.
            self._all_columns = new_cols
            if self.default_columns:
                self._visible_columns = {c for c in new_cols if c in self.default_columns}
                # Safety: if nothing matches, fall back to all columns
                if not self._visible_columns:
                    self._visible_columns = set(new_cols)
            else:
                self._visible_columns = set(new_cols)
        else:
            # Subsequent loads:
            # - columns explicitly hidden by the user stay hidden if they reappear.
            # - new columns (not seen before) are shown by default.
            old_hidden = set(self._all_columns) - self._visible_columns
            self._all_columns = new_cols
            self._visible_columns = {c for c in new_cols if c not in old_hidden}

        self._render_table(df)

        self._column_settings_button.disabled = False
        if self.page:
            self._column_settings_button.update()

    def _render_table(self, df: pd.DataFrame):
        visible_cols = [c for c in df.columns if c in self._visible_columns]

        columns = []
        for col in visible_cols:
            label = self.header_name_mapping.get(col, col)
            columns.append(ft.DataColumn(ft.Text(label, weight=ft.FontWeight.BOLD)))

        has_plot_col = bool(self.plot_id_field and self.plot_callback)
        if has_plot_col:
            columns.append(ft.DataColumn(ft.Text("Plot", weight=ft.FontWeight.BOLD)))

        rows = []
        for idx, row in df.iterrows():
            cells = []
            plot_id_value = None

            for col in visible_cols:
                value = row[col]

                if col == self.plot_id_field:
                    plot_id_value = str(value)

                if value is None:
                    display_value = ""
                elif isinstance(value, float) and pd.isna(value):
                    display_value = ""
                elif isinstance(value, float):
                    display_value = f"{value:.4f}"
                else:
                    display_value = str(value)

                tooltip_text = self.get_tooltip(col, idx)

                if col in self.column_filter_mapping and display_value:
                    filter_key = self.column_filter_mapping[col]
                    cell_text = ft.Text(
                        display_value,
                        color=ft.Colors.BLUE_600,
                        style=ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE),
                        tooltip=ft.Tooltip(message=tooltip_text) if tooltip_text else None,
                    )
                    cells.append(ft.DataCell(
                        cell_text,
                        on_tap=lambda e, fk=filter_key, v=str(value): (
                            self.page.run_task(self.set_filters_in_ui, fk, v) if self.page else None
                        )
                    ))
                else:
                    cell_text = ft.Text(
                        display_value,
                        tooltip=ft.Tooltip(message=tooltip_text) if tooltip_text else None
                    )
                    cells.append(ft.DataCell(cell_text))

            if has_plot_col:
                if plot_id_value:
                    cells.append(ft.DataCell(ft.IconButton(
                        icon=ft.Icons.SHOW_CHART,
                        tooltip="Show plot",
                        on_click=lambda e, pid=plot_id_value: (
                            self.page.run_task(self.plot_callback, pid) if self.page else None
                        )
                    )))
                else:
                    cells.append(ft.DataCell(ft.Text("")))

            rows.append(ft.DataRow(cells=cells))

        # Always create a fresh DataTable — do NOT try to patch an existing one
        # when column count changes, as Flet validates cells==columns before patching.
        self.data_table = ft.DataTable(
            columns=columns,
            rows=rows,
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

        # Replace entire content — full re-render, no incremental patch.
        # Caller is responsible for calling page.update() after this.
        self.data_container.content = ft.Column([ft.Row([self.data_table], scroll=ft.ScrollMode.ADAPTIVE)], scroll=ft.ScrollMode.AUTO)
        self.data_container.alignment = None
        self.data_container.height = None
        # Do NOT call self.data_container.update() here — that triggers an incremental
        # patch that validates cell/column counts against the *old* control tree.

    def _apply_column_visibility(self):
        """Re-render table from cached df with current _visible_columns.

        Must be called after page.update() has already flushed the dialog close,
        so the old DataTable is detached before we replace it.
        """
        if self._last_df is not None and not self._last_df.empty:
            self._render_table(self._last_df)
            if self.page:
                self.page.update()

    # ------------------------------------------------------------------
    # Column settings dialog
    # ------------------------------------------------------------------

    async def _show_column_settings_dialog(self):
        if not self._all_columns:
            return

        checkboxes: dict[str, ft.Checkbox] = {
            col: ft.Checkbox(
                label=self.header_name_mapping.get(col, col),
                value=col in self._visible_columns
            )
            for col in self._all_columns
        }

        async def on_apply(e):
            self._visible_columns = {c for c, cb in checkboxes.items() if cb.value}
            if not self._visible_columns:
                self._visible_columns = set(self._all_columns[:1])
            # Close dialog and flush UI first — the old DataTable must be detached
            # before we replace it, otherwise Flet's patch validator fires.
            dialog.open = False
            if self.page:
                self.page.update()
            # Now re-render with new column set
            self._apply_column_visibility()

        def on_cancel(e):
            dialog.open = False
            if self.page:
                self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Column Visibility"),
            content=ft.Column(
                list(checkboxes.values()),
                scroll=ft.ScrollMode.AUTO,
                height=min(400, len(checkboxes) * 45)
            ),
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel),
                ft.ElevatedButton(
                    "Apply",
                    on_click=lambda e: self.page.run_task(on_apply, e) if self.page else None
                )
            ]
        )

        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    async def _on_export(self, e):
        format_radio = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value="csv", label="CSV"),
                ft.Radio(value="xlsx", label="XLSX"),
            ]),
            value="csv"
        )
        tech_headers_cb = ft.Checkbox(label="Technical headers", value=False)

        async def on_export_confirm(e):
            dialog.open = False
            if self.page:
                self.page.update()

            from dasmixer.gui.views.tabs.peptides.dialogs.progress_dialog import ProgressDialog
            progress = ProgressDialog(self.page, "Exporting Table")
            progress.show()

            fmt = format_radio.value or "csv"
            use_tech = tech_headers_cb.value

            try:
                result = await self.get_data(limit=-1, offset=0)
                df = result[0] if isinstance(result, tuple) else result

                if not use_tech and self.header_name_mapping:
                    df = df.rename(columns=self.header_name_mapping)

                progress.update_progress(None, "Saving file...", "")

                file_result = await ft.FilePicker().save_file(
                    file_name=f"{self.table_view_name}_export.{fmt}",
                    allowed_extensions=[fmt]
                )

                if file_result:
                    if fmt == "csv":
                        df.to_csv(file_result, index=False)
                    else:
                        df.to_excel(file_result, index=False)

                    from pathlib import Path as _Path
                    progress.complete(f"Exported: {_Path(file_result).name}")
                    import asyncio
                    await asyncio.sleep(1)
                    progress.close()
                else:
                    progress.close()

            except Exception as ex:
                progress.close()
                if self.page:
                    logger.exception(ex)
                    show_snack(self.page, f"Export error: {ex}", ft.Colors.RED_400)
                    self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Export Table"),
            content=ft.Column([
                ft.Text("Format:", weight=ft.FontWeight.BOLD),
                format_radio,
                ft.Container(height=8),
                tech_headers_cb,
            ], tight=True, spacing=5, width=300),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(dialog)),
                ft.ElevatedButton(
                    "Export",
                    on_click=lambda e: self.page.run_task(on_export_confirm, e) if self.page else None
                )
            ]
        )

        self.page.overlay.append(dialog)
        dialog.open = True
        self.page.update()

    def _close_dialog(self, dialog):
        dialog.open = False
        if self.page:
            self.page.update()

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def _update_pagination_controls(self):
        if self.total_rows == 0:
            self.pagination_text.value = "No data"
            self.prev_button.disabled = True
            self.next_button.disabled = True
            return

        start = self.current_page * self.page_size + 1
        end = min((self.current_page + 1) * self.page_size, self.total_rows)
        total_pages = (self.total_rows + self.page_size - 1) // self.page_size

        self.pagination_text.value = (
            f"Showing {start}-{end} of {self.total_rows} rows "
            f"(Page {self.current_page + 1} of {total_pages})"
        )
        self.prev_button.disabled = (self.current_page == 0)
        self.next_button.disabled = (self.current_page >= total_pages - 1)

        if self.page:
            self.pagination_text.update()
            self.prev_button.update()
            self.next_button.update()

    async def _on_page_size_change(self, e):
        self.page_size = int(e.control.value)
        self.current_page = 0
        await self._load_table_data()

    async def _on_prev_page(self, e):
        if self.current_page > 0:
            self.current_page -= 1
            await self._load_table_data()

    async def _on_next_page(self, e):
        total_pages = (self.total_rows + self.page_size - 1) // self.page_size
        if self.current_page < total_pages - 1:
            self.current_page += 1
            await self._load_table_data()

    # ------------------------------------------------------------------
    # Suspend / Resume  (called when parent tab becomes inactive/active)
    # ------------------------------------------------------------------

    def suspend(self) -> None:
        """
        Replace the rendered DataTable with a lightweight placeholder.

        The data (self._last_df) is preserved in memory — resume() rebuilds
        the table from it instantly without any DB query.
        """
        if self._is_suspended or not self.has_data:
            return
        self._is_suspended = True

        if self.data_container is not None:
            self.data_container.content = ft.Container(
                content=ft.Text(
                    "Table hidden (switch back to reload)",
                    size=13,
                    color=ft.Colors.GREY_500,
                    italic=True,
                ),
                alignment=ft.Alignment.CENTER,
                height=80,
            )
            # Deliberately do NOT call update() here — caller handles page.update()

    def resume(self) -> None:
        """
        Restore the DataTable from the cached DataFrame without a DB query.
        """
        if not self._is_suspended:
            return
        self._is_suspended = False

        if self._last_df is not None and not self._last_df.empty:
            self._render_table(self._last_df)
        # Caller handles page.update()

    # ------------------------------------------------------------------
    # Public load entry point
    # ------------------------------------------------------------------

    async def load_data(self):
        await self._load_filters_from_project()
