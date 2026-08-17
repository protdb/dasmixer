"""Interactive report viewer (pywebview window or default browser)."""

import multiprocessing
from pathlib import Path


def _show_html_in_webview(html_content: str, title: str = "Report Viewer"):
    """
    Function to run in separate process.

    Args:
        html_content: HTML content to display
        title: Window title
    """
    from dasmixer.api.config import config

    if config.plot_view_mode == "Browser":
        import tempfile
        import webbrowser

        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.html',
            prefix='dasmixer_report_',
            delete=False,
            encoding='utf-8'
        ) as f:
            f.write(html_content)
            temp_path = f.name

        webbrowser.open(Path(temp_path).as_uri())
    else:
        import webview
        window = webview.create_window(title, html=html_content)
        webview.start()


class ReportViewer:
    """
    Wrapper for interactive report viewing.
    
    Uses pywebview in a separate process to display
    HTML-rendered reports with interactive Plotly charts.
    """
    
    @staticmethod
    def show_report(html_content: str, title: str = "DASMixer Report"):
        """
        Show report in separate window.
        
        Args:
            html_content: HTML content of report
            title: Window title
            
        Note:
            Runs in separate process, does not block UI.
        """
        process = multiprocessing.Process(
            target=_show_html_in_webview,
            args=(html_content, title)
        )
        process.start()
        # Don't call join() - process lives independently
    
    @staticmethod
    def show_report_from_file(html_file: Path | str, title: str = "DASMixer Report"):
        """
        Show report from HTML file.
        
        Args:
            html_file: Path to HTML file
            title: Window title
        """
        html_file = Path(html_file)
        html_content = html_file.read_text(encoding='utf-8')
        ReportViewer.show_report(html_content, title)
