"""Universal Plotly chart viewer with interactive mode support."""

import flet as ft
import multiprocessing
import plotly.graph_objects as go
import base64
from dasmixer.gui.utils import show_snack


def show_webview(fig: go.Figure, title: str):
    """
    Show plotly figure in webview window.

    Top-level function required for multiprocessing pickling.
    """
    import webview
    html = fig.to_html(include_plotlyjs='cdn')
    window = webview.create_window(title, html=html)
    webview.start()


class PlotlyViewer(ft.Container):
    """
    Universal Plotly chart viewer.

    Renders a static PNG preview of a Plotly figure.
    An "Interactive Mode" button is optionally shown and launches
    a separate webview process.

    Default size: 1100x700 px.
    """

    def __init__(
        self,
        figure: go.Figure,
        width: int = 1100,
        height: int = 700,
        title: str = "Chart",
        show_interactive_button: bool = True
    ):
        super().__init__()
        self.figure = figure
        self.width = width
        self.height = height
        self.title = title
        self.show_interactive_button = show_interactive_button

        self.content = self._build_content()
        self.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    def _build_content(self):
        try:
            img_bytes = self.figure.to_image(
                format='png',
                width=self.width,
                height=self.height
            )
            img_base64 = base64.b64encode(img_bytes).decode()
            image = ft.Image(
                src=img_base64,
                width=self.width,
                height=self.height,
                fit=ft.BoxFit.CONTAIN
            )
        except Exception as e:
            image = ft.Container(
                content=ft.Text(f"Error rendering chart: {e}", color=ft.Colors.RED),
                width=self.width,
                height=self.height,
                bgcolor=ft.Colors.GREY_200,
                alignment=ft.Alignment.CENTER
            )

        components = [image]

        if self.show_interactive_button:
            button = ft.ElevatedButton(
                content=ft.Text("Interactive Mode"),
                icon=ft.Icons.OPEN_IN_NEW,
                on_click=self.launch_interactive,
                tooltip="Open in interactive viewer"
            )
            components.append(ft.Container(content=button, padding=10))

        return ft.Column(
            components,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )

    def launch_interactive(self, e):
        try:
            process = multiprocessing.Process(
                target=show_webview,
                args=(self.figure, self.title)
            )
            process.start()
        except Exception as ex:
            if self.page:
                show_snack(self.page, f"Error launching interactive mode: {ex}", ft.Colors.RED_400)
                self.page.update()
