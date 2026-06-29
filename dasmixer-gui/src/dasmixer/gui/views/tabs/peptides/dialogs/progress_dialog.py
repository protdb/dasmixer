"""Universal progress dialog."""

import time
import flet as ft
import asyncio


def _fmt_seconds(seconds: float) -> str:
    """Format seconds as HH:MM."""
    seconds = max(0, int(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    return f"{h:02d}:{m:02d}"


class ProgressDialog:
    """
    Universal progress dialog for long-running operations.

    Usage:
        dialog = ProgressDialog(page, "Loading Data")
        dialog.show()

        dialog.update_progress(0.5, "Processing 50/100...")

        dialog.complete("Done! Processed 100 items")
        await asyncio.sleep(1)
        dialog.close()

    With stop button and ETA:
        dialog = ProgressDialog(page, "Calculating", stoppable=True)
        dialog.show()

        # Pass processed/total for ETA calculation
        dialog.update_progress(processed / total, "Calculating...",
                               f"{processed}/{total}",
                               processed=processed, total=total)

        # Check stop flag after each batch
        if dialog.stop_requested:
            break
    """

    def __init__(
        self,
        page: ft.Page,
        title: str,
        show_details: bool = True,
        width: int = 400,
        stoppable: bool = False,
    ):
        """
        Initialize progress dialog.

        Args:
            page: Flet page
            title: Dialog title
            show_details: Show details text below progress bar
            width: Dialog width
            stoppable: If True, shows Stop button that sets stop_requested flag
        """
        self.page = page
        self.stoppable = stoppable
        self.stop_requested = False
        self._start_time: float | None = None

        self.progress_text = ft.Text("Processing...")
        self.progress_bar = ft.ProgressBar(value=0)
        self.progress_details = ft.Text("", size=11, color=ft.Colors.GREY_600)
        self._time_text = ft.Text(
            "",
            size=11,
            color=ft.Colors.GREY_500,
            font_family="monospace",
        )

        self._stop_button = ft.ElevatedButton(
            "Stop",
            icon=ft.Icons.STOP,
            on_click=self._on_stop_clicked,
            visible=stoppable,
            color=ft.Colors.WHITE,
            bgcolor=ft.Colors.RED_700,
        )

        content_controls = [
            self.progress_text,
            self.progress_bar,
        ]

        if show_details:
            content_controls.append(ft.Container(height=5))
            content_controls.append(self.progress_details)

        # Always add time row (hidden until first update with ETA data)
        content_controls.append(self._time_text)

        if stoppable:
            content_controls.append(ft.Container(height=10))
            content_controls.append(
                ft.Row([self._stop_button], alignment=ft.MainAxisAlignment.CENTER)
            )

        self.dialog = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Column(content_controls, tight=True, width=width),
            modal=True,
        )

    def _on_stop_clicked(self, e):
        """Handle Stop button click — request stop and update UI."""
        self.stop_requested = True
        self._stop_button.disabled = True
        self._stop_button.update()
        self.progress_text.value = "Stopping. Wait..."
        self.progress_text.update()

    def show(self):
        """Show dialog and start the elapsed timer."""
        self._start_time = time.monotonic()
        self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()

    def close(self):
        """Close dialog."""
        self.dialog.open = False
        self.page.update()

    def update_progress(
        self,
        value: float | None,
        status: str = "",
        details: str = "",
        processed: int | None = None,
        total: int | None = None,
    ):
        """
        Update progress.

        Args:
            value: Progress value (0.0-1.0) or None for indeterminate
            status: Status text
            details: Details text (e.g. "1500/20000")
            processed: Number of items processed so far (for ETA)
            total: Total number of items (for ETA)
        """
        # Compute ETA regardless of stop state
        eta_text = self._compute_eta(processed, total)
        if eta_text:
            self._time_text.value = eta_text
            self._time_text.update()

        # Do not overwrite "Stopping. Wait..." message
        if self.stop_requested:
            if value is not None:
                self.progress_bar.value = value
                self.progress_bar.update()
            if details:
                self.progress_details.value = details
                self.progress_details.update()
            return

        if value is not None:
            self.progress_bar.value = value
        else:
            self.progress_bar.value = None

        if status:
            self.progress_text.value = status

        if details:
            self.progress_details.value = details

        self.progress_text.update()
        self.progress_bar.update()
        self.progress_details.update()

    def _compute_eta(self, processed: int | None, total: int | None) -> str:
        """Return 'Elapsed HH:MM  Remains HH:MM' or empty string."""
        if self._start_time is None:
            return ""
        elapsed = time.monotonic() - self._start_time
        elapsed_str = _fmt_seconds(elapsed)

        if processed and total and processed > 0 and total > 0 and elapsed > 0:
            rate = processed / elapsed          # items/sec
            remaining_items = max(0, total - processed)
            remains = remaining_items / rate
            return f"Elapsed {elapsed_str}  |  Remains {_fmt_seconds(remains)}"

        return f"Elapsed {elapsed_str}"

    def complete(self, message: str = "Complete!"):
        """Mark as complete."""
        self.progress_text.value = message
        self.progress_bar.value = 1.0
        self.progress_text.update()
        self.progress_bar.update()
        # Update elapsed to final value
        if self._start_time is not None:
            elapsed = time.monotonic() - self._start_time
            self._time_text.value = f"Elapsed {_fmt_seconds(elapsed)}"
            self._time_text.update()

    async def run_with_progress(
        self,
        coro,
        status: str = "Processing...",
        complete_message: str = "Complete!",
        auto_close_delay: float = 1.0,
    ):
        """
        Run coroutine with progress dialog.

        Args:
            coro: Async coroutine to run
            status: Initial status text
            complete_message: Completion message
            auto_close_delay: Delay before auto-close (seconds)

        Returns:
            Result from coroutine
        """
        self.show()
        self.update_progress(None, status)

        try:
            result = await coro
            self.complete(complete_message)
            await asyncio.sleep(auto_close_delay)
            self.close()
            return result
        except Exception as ex:
            self.close()
            raise ex
