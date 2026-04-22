"""Universal Plotly chart viewer with interactive mode support."""

import asyncio
import base64
import multiprocessing
from functools import partial

import flet as ft
import plotly.graph_objects as go

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


def _render_png_sync(fig: go.Figure, width: int, height: int) -> bytes:
    """Synchronous PNG render — runs in thread pool to avoid blocking the event loop."""
    return fig.to_image(format='png', width=width, height=height)


async def render_png_async(fig: go.Figure, width: int, height: int) -> bytes:
    """
    Render a Plotly figure to PNG bytes without blocking the asyncio event loop.

    Uses run_in_executor so that Kaleido's subprocess communication and CPU work
    happen in a thread pool thread, leaving the event loop free.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(_render_png_sync, fig, width, height))


class PlotlyViewer(ft.Container):
    """
    Universal Plotly chart viewer.

    Renders a static PNG preview of a Plotly figure.
    The PNG is rendered asynchronously (via run_in_executor) so the event loop
    is never blocked.  Pass ``img_bytes`` if you already have a cached render —
    the viewer will use it directly without calling Kaleido again.

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
        show_interactive_button: bool = True,
        img_bytes: bytes | None = None,
    ):
        super().__init__()
        self.figure = figure
        self.width = width
        self.height = height
        self.title = title
        self.show_interactive_button = show_interactive_button
        # Pre-rendered bytes (may be None — caller can populate later)
        self._img_bytes: bytes | None = img_bytes

        self.content = self._build_content_from_bytes(img_bytes)
        self.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    # ------------------------------------------------------------------
    # Internal builders
    # ------------------------------------------------------------------

    def _build_content_from_bytes(self, img_bytes: bytes | None) -> ft.Control:
        """Build UI from already-rendered bytes (or a spinner if None)."""
        if img_bytes is None:
            image: ft.Control = ft.Column(
                [ft.ProgressRing(width=32, height=32, stroke_width=3)],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            )
        else:
            try:
                img_base64 = base64.b64encode(img_bytes).decode()
                image = ft.Image(
                    src=img_base64,
                    width=self.width,
                    height=self.height,
                    fit=ft.BoxFit.CONTAIN,
                )
            except Exception as e:
                image = ft.Container(
                    content=ft.Text(f"Error rendering chart: {e}", color=ft.Colors.RED),
                    width=self.width,
                    height=self.height,
                    bgcolor=ft.Colors.GREY_200,
                    alignment=ft.Alignment.CENTER,
                )

        components: list[ft.Control] = [image]

        if self.show_interactive_button:
            button = ft.ElevatedButton(
                content=ft.Text("Interactive Mode"),
                icon=ft.Icons.OPEN_IN_NEW,
                on_click=self.launch_interactive,
                tooltip="Open in interactive viewer",
            )
            components.append(ft.Container(content=button, padding=10))

        return ft.Column(components, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    # ------------------------------------------------------------------
    # Public: async render (call after mounting if img_bytes was None)
    # ------------------------------------------------------------------

    async def render_async(self):
        """
        Render PNG in a thread pool, then update own content.
        Safe to call after did_mount.
        """
        try:
            img_bytes = await render_png_async(self.figure, self.width, self.height)
            self._img_bytes = img_bytes
            self.content = self._build_content_from_bytes(img_bytes)
            if self.page:
                self.update()
        except Exception as e:
            self.content = ft.Container(
                content=ft.Text(f"Error rendering chart: {e}", color=ft.Colors.RED),
                width=self.width,
                height=self.height,
                bgcolor=ft.Colors.GREY_200,
                alignment=ft.Alignment.CENTER,
            )
            if self.page:
                self.update()

    # ------------------------------------------------------------------
    # Interactive launch
    # ------------------------------------------------------------------

    def launch_interactive(self, e):
        try:
            process = multiprocessing.Process(
                target=show_webview,
                args=(self.figure, self.title),
            )
            process.start()
        except Exception as ex:
            if self.page:
                show_snack(self.page, f"Error launching interactive mode: {ex}", ft.Colors.RED_400)
                self.page.update()
