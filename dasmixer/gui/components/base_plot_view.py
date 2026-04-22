"""Base class for all plot views with save/export functionality."""

import flet as ft
import plotly.graph_objects as go
import json
import multiprocessing

from dasmixer.api.project.project import Project
from dasmixer.gui.components.plotly_viewer import PlotlyViewer, show_webview, render_png_async
from dasmixer.gui.utils import show_snack

_PLOT_WIDTH = 1100
_PLOT_HEIGHT = 700


class BasePlotView(ft.Container):
    """
    Base class for all plot views.

    Provides:
    - Settings panel (expandable)
    - Plot preview (expandable) at 1100x700
    - Save to project functionality
    - Export to PNG/SVG (async FilePicker)
    - Preview in WebView
    - Settings persistence in project
    """

    plot_type_name: str = "base_plot"

    def __init__(
        self,
        project: Project,
        title: str = "Plot",
        show_save_button: bool = True,
        show_export_button: bool = True
    ):
        super().__init__()
        self.project = project
        self.title = title
        self.show_save_button = show_save_button
        self.show_export_button = show_export_button

        self.plot_settings = self.get_default_settings()
        self.current_entity_id: str | None = None
        self.current_figure: go.Figure | None = None
        # Cached PNG bytes — avoids re-rendering when suspending/resuming
        self._last_img_bytes: bytes | None = None

        self.settings_panel: ft.ExpansionPanel | None = None
        self.preview_panel: ft.ExpansionPanel | None = None
        self.preview_container: ft.Container | None = None
        self.expansion_panel_list: ft.ExpansionPanelList | None = None
        self.save_button: ft.ElevatedButton | None = None
        self.export_button: ft.ElevatedButton | None = None
        self.webview_button: ft.ElevatedButton | None = None

        # suspend/resume support
        self._is_suspended: bool = False

        self.content = self._build_ui()
        self.padding = 10
        self.expand = True

    def get_default_settings(self) -> dict:
        return {}

    def _build_plot_settings_view(self) -> ft.Control:
        return ft.Text("No settings available")

    async def generate_plot(self, entity_id: str) -> go.Figure:
        raise NotImplementedError("Subclass must implement generate_plot()")

    def _build_ui(self) -> ft.Control:
        settings_content = ft.Column([
            self._build_plot_settings_view(),
            ft.Container(height=10),
            ft.ElevatedButton(
                content=ft.Text("Apply Settings"),
                icon=ft.Icons.CHECK,
                on_click=lambda e: self.page.run_task(self._on_apply_settings, e) if self.page else None
            )
        ], spacing=5)

        self.preview_container = ft.Container(
            content=ft.Text("No plot generated yet", color=ft.Colors.GREY_600),
            alignment=ft.Alignment.CENTER,
            height=_PLOT_HEIGHT + 20
        )

        buttons = []

        if self.show_save_button:
            self.save_button = ft.ElevatedButton(
                content=ft.Text("Save to Project"),
                icon=ft.Icons.SAVE,
                on_click=lambda e: self.page.run_task(self._on_save_to_project, e) if self.page else None,
                disabled=True
            )
            buttons.append(self.save_button)

        if self.show_export_button:
            self.export_button = ft.ElevatedButton(
                content=ft.Text("Export..."),
                icon=ft.Icons.DOWNLOAD,
                on_click=lambda e: self.page.run_task(self._on_export, e) if self.page else None,
                disabled=True
            )
            buttons.append(self.export_button)

        self.webview_button = ft.ElevatedButton(
            content=ft.Text("Interactive"),
            icon=ft.Icons.OPEN_IN_NEW,
            on_click=lambda e: self._launch_webview(),
            disabled=True
        )
        buttons.append(self.webview_button)

        preview_content = ft.Column([
            self.preview_container,
            ft.Container(height=10),
            ft.Row(buttons, spacing=10) if buttons else ft.Container()
        ], spacing=5)

        self.settings_panel = ft.ExpansionPanel(
            header=ft.ListTile(title=ft.Text("Plot Settings", weight=ft.FontWeight.BOLD)),
            content=ft.Container(content=settings_content, padding=10),
            can_tap_header=True
        )

        self.preview_panel = ft.ExpansionPanel(
            header=ft.ListTile(title=ft.Text("Plot Preview", weight=ft.FontWeight.BOLD)),
            content=ft.Container(content=preview_content, padding=10),
            can_tap_header=True,
            expanded=True
        )

        self.expansion_panel_list = ft.ExpansionPanelList(
            controls=[self.settings_panel, self.preview_panel],
            expand_icon_color=ft.Colors.BLUE,
            elevation=2
        )

        return ft.Column([
            ft.Text(self.title, size=16, weight=ft.FontWeight.BOLD),
            ft.Container(height=5),
            self.expansion_panel_list
        ], expand=True, scroll=ft.ScrollMode.AUTO)

    async def on_plot_requested(self, entity_id: str):
        self.current_entity_id = entity_id
        await self._generate_and_display_plot()

    async def _on_apply_settings(self, e):
        await self._update_settings_from_ui()
        await self._save_settings_to_project()

        if self.current_entity_id:
            await self._generate_and_display_plot()

        if self.page:
            show_snack(self.page, "Settings applied", ft.Colors.GREEN_400)
            self.page.update()

    async def _update_settings_from_ui(self):
        pass

    async def _save_settings_to_project(self):
        for key, value in self.plot_settings.items():
            setting_key = f"plot_view_{self.plot_type_name}_{key}"
            value_str = json.dumps(value) if isinstance(value, (list, dict)) else str(value)
            await self.project.set_setting(setting_key, value_str)

    async def _load_settings_from_project(self):
        for key in self.plot_settings.keys():
            setting_key = f"plot_view_{self.plot_type_name}_{key}"
            value = await self.project.get_setting(setting_key)
            if value is not None:
                default_value = self.plot_settings[key]
                if isinstance(default_value, bool):
                    self.plot_settings[key] = value.lower() in ('true', '1', 'yes')
                elif isinstance(default_value, int):
                    self.plot_settings[key] = int(value)
                elif isinstance(default_value, float):
                    self.plot_settings[key] = float(value)
                elif isinstance(default_value, (list, dict)):
                    try:
                        self.plot_settings[key] = json.loads(value)
                    except json.JSONDecodeError:
                        self.plot_settings[key] = default_value
                else:
                    self.plot_settings[key] = value

    async def _generate_and_display_plot(self):
        if not self.current_entity_id:
            return

        try:
            if self.preview_container is not None:
                self.preview_container.content = ft.Column(
                    [ft.ProgressRing(width=32, height=32, stroke_width=3)],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                )
            if self.page:
                self.page.update()

            fig = await self.generate_plot(self.current_entity_id)
            self.current_figure = fig
            # Invalidate cached PNG — figure changed
            self._last_img_bytes = None

            fig = await self._apply_global_settings(fig)
            await self._display_plot(fig)

            # Enable action buttons
            for btn in [self.save_button, self.export_button, self.webview_button]:
                if btn is not None:
                    btn.disabled = False

            if self.page:
                self.page.update()

        except Exception as ex:
            if self.preview_container is not None:
                self.preview_container.content = ft.Text(
                    f"Error generating plot: {ex}", color=ft.Colors.RED_400
                )
            if self.page:
                self.page.update()

    async def _apply_global_settings(self, fig: go.Figure) -> go.Figure:
        font_size = await self.project.get_setting("global_plot_font_size")
        if font_size:
            fig.update_layout(font=dict(size=int(font_size)))
        return fig

    async def _display_plot(self, fig: go.Figure):
        """
        Render the figure to PNG asynchronously (no event-loop blocking),
        cache the bytes, then update the preview container.
        """
        # Render PNG in a thread pool — Kaleido subprocess won't block the loop
        img_bytes = await render_png_async(fig, _PLOT_WIDTH, _PLOT_HEIGHT)
        self._last_img_bytes = img_bytes

        viewer = PlotlyViewer(
            figure=fig,
            width=_PLOT_WIDTH,
            height=_PLOT_HEIGHT,
            title=self.title,
            show_interactive_button=False,  # we have our own button in the button row
            img_bytes=img_bytes,            # pass pre-rendered bytes — no second render
        )
        if self.preview_container is not None:
            self.preview_container.content = viewer
        if self.page:
            self.page.update()

    def _launch_webview(self):
        """Launch interactive WebView in a separate process."""
        if not self.current_figure:
            return
        try:
            p = multiprocessing.Process(
                target=show_webview,
                args=(self.current_figure, self.title)
            )
            p.start()
        except Exception as ex:
            if self.page:
                show_snack(self.page, f"Error launching interactive mode: {ex}", ft.Colors.RED_400)
                self.page.update()

    async def _on_save_to_project(self, e):
        if not self.current_figure or not self.current_entity_id:
            return

        try:
            settings_to_save = {
                'entity_id': self.current_entity_id,
                'plot_settings': self.plot_settings.copy()
            }
            plot_id = await self.project.save_plot(
                plot_type=self.plot_type_name,
                figure=self.current_figure,
                settings=settings_to_save
            )
            if self.page:
                show_snack(self.page, f"Plot saved (ID: {plot_id})", ft.Colors.GREEN_400)
                self.page.update()

        except Exception as ex:
            if self.page:
                show_snack(self.page, f"Error saving plot: {ex}", ft.Colors.RED_400)
                self.page.update()

    async def _on_export(self, e):
        """Show export dialog with format selection."""
        if not self.current_figure:
            return

        format_radio = ft.RadioGroup(
            content=ft.Row([
                ft.Radio(value="png", label="PNG"),
                ft.Radio(value="svg", label="SVG"),
            ]),
            value="png"
        )

        async def on_export_confirm(e):
            dialog.open = False
            if self.page:
                self.page.update()

            fmt = format_radio.value or "png"
            try:
                file_result = await ft.FilePicker().save_file(
                    file_name=f"plot_{self.current_entity_id}.{fmt}",
                    allowed_extensions=[fmt]
                )
                if file_result:
                    self.current_figure.write_image(file_result, format=fmt)
                    if self.page:
                        show_snack(self.page, f"Plot exported to {file_result}", ft.Colors.GREEN_400)
                        self.page.update()

            except Exception as ex:
                if self.page:
                    show_snack(self.page, f"Error exporting: {ex}", ft.Colors.RED_400)
                    self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text("Export Plot"),
            content=ft.Column([
                ft.Text("Format:", weight=ft.FontWeight.BOLD),
                format_radio,
            ], tight=True, spacing=10, width=250),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: self._close_dialog(dialog)),
                ft.ElevatedButton(
                    "Export",
                    on_click=lambda e: self.page.run_task(on_export_confirm, e) if self.page else None
                )
            ]
        )

        if self.page:
            self.page.overlay.append(dialog)
            dialog.open = True
            self.page.update()

    def _close_dialog(self, dialog):
        dialog.open = False
        if self.page:
            self.page.update()

    # ------------------------------------------------------------------
    # Suspend / Resume  (called when parent tab becomes inactive/active)
    # ------------------------------------------------------------------

    def suspend(self) -> None:
        """
        Replace the plot viewer with a lightweight placeholder.

        go.Figure and _last_img_bytes are kept in memory so resume()
        can restore the view instantly without re-rendering.
        """
        if self._is_suspended or self.current_figure is None:
            return
        self._is_suspended = True

        if self.preview_container is not None:
            self.preview_container.content = ft.Container(
                content=ft.Text(
                    "Plot hidden (switch back to reload)",
                    size=13,
                    color=ft.Colors.GREY_500,
                    italic=True,
                ),
                alignment=ft.Alignment.CENTER,
                height=80,
            )
        # Caller handles page.update()

    def resume(self) -> None:
        """
        Restore the plot viewer.

        If _last_img_bytes is available, restores instantly (no Kaleido call).
        Otherwise schedules an async re-render.
        """
        if not self._is_suspended or self.current_figure is None:
            return
        self._is_suspended = False

        if self._last_img_bytes is not None and self.preview_container is not None:
            viewer = PlotlyViewer(
                figure=self.current_figure,
                width=_PLOT_WIDTH,
                height=_PLOT_HEIGHT,
                title=self.title,
                show_interactive_button=False,
                img_bytes=self._last_img_bytes,
            )
            self.preview_container.content = viewer
        elif self.page and self.current_entity_id:
            # No cached bytes — schedule async re-render
            self.page.run_task(self._generate_and_display_plot)
        # Caller handles page.update()

    # ------------------------------------------------------------------

    async def load_data(self):
        await self._load_settings_from_project()
