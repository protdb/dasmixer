"""Universal Plotly chart viewer with interactive mode support."""

import flet as ft
import multiprocessing
import plotly.graph_objects as go
import base64


def show_webview(fig: go.Figure, title: str):
    """
    Show plotly figure in webview window.
    
    Must be top-level function for multiprocessing pickling.
    
    Args:
        fig: Plotly Figure object
        title: Window title
    """
    import webview
    html = fig.to_html(include_plotlyjs='cdn')
    window = webview.create_window(title, html=html)
    webview.start()


class PlotlyViewer(ft.Container):
    """
    Universal Plotly chart viewer with interactive mode.
    
    Displays static PNG image in main UI with button to launch
    interactive mode in separate webview window.
    
    Example:
        >>> import plotly.express as px
        >>> fig = px.scatter(x=[1, 2, 3], y=[4, 5, 6])
        >>> viewer = PlotlyViewer(fig, title="My Chart")
        >>> page.add(viewer)
    """
    
    def __init__(
        self,
        figure: go.Figure,
        width: int = 1000,
        height: int = 500,
        title: str = "Chart",
        show_interactive_button: bool = True
    ):
        """
        Initialize viewer.
        
        Args:
            figure: Plotly Figure object to display
            width: Image width in pixels
            height: Image height in pixels
            title: Chart title (used for interactive window)
            show_interactive_button: Show "Interactive Mode" button
        """
        super().__init__()
        self.figure = figure
        self.width = width
        self.height = height
        self.title = title
        self.show_interactive_button = show_interactive_button
        
        # Build content
        self.content = self._build_content()
        self.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    
    def _build_content(self):
        """Build the UI control."""
        # Render static image
        try:
            img_bytes = self.figure.to_image(
                format='png',
                width=self.width,
                height=self.height
            )
            
            # Convert to base64 for Flet
            img_base64 = base64.b64encode(img_bytes).decode()
            
            image = ft.Image(
                src=img_base64,
                width=self.width,
                height=self.height,
                fit=ft.BoxFit.CONTAIN
            )
        except Exception as e:
            # Fallback if rendering fails
            image = ft.Container(
                content=ft.Text(
                    f"Error rendering chart: {e}",
                    color=ft.Colors.RED
                ),
                width=self.width,
                height=self.height,
                bgcolor=ft.Colors.GREY_200,
                alignment=ft.Alignment.CENTER
            )
        
        components = [image]
        
        # Add interactive button if enabled
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
        """
        Launch interactive viewer in separate process.
        
        Args:
            e: Click event
        """
        try:
            process = multiprocessing.Process(
                target=show_webview,
                args=(self.figure, self.title)
            )
            process.start()
            # Don't join - let it run independently
        except Exception as ex:
            # Show error in main UI if launch fails
            if self.page:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Error launching interactive mode: {ex}"),
                    bgcolor=ft.Colors.RED_400
                )
                self.page.snack_bar.open = True
                self.page.update()
