"""Settings view — application settings screen."""

import re
import flet as ft
from dasmixer.api.config import config

_HEX_RE = re.compile(r'^#[0-9a-fA-F]{6}$')

_LARGE_BATCH_THRESHOLD = 100_000
_LARGE_BATCH_WARNING = (
    "Very large batch size specified. This may cause out-of-memory errors "
    "during processing. Are you sure?"
)


class SettingsView(ft.View):
    """
    Application settings screen.

    Accessible via Options → Settings menu.
    Uses page.views routing stack — back button returns to previous view.

    Sections:
    - Theme
    - Batch Operation Limits
    - Default Color Palette
    """

    def __init__(self):
        super().__init__(
            route="/settings",
            appbar=ft.AppBar(
                title=ft.Text("Settings"),
                leading=ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    on_click=lambda _: self._go_back(),
                ),
            ),
            scroll=ft.ScrollMode.AUTO,
        )
        self._color_rows: list[dict] = []  # [{container, field}]
        self._build_controls()

    def _go_back(self):
        if len(self.page.views) > 1:
            self.page.views.pop()
        self.page.update()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_controls(self):
        """Construct all setting controls and populate self.controls."""

        # --- Theme ---
        self._theme_dropdown = ft.Dropdown(
            label="Application theme",
            width=200,
            options=[
                ft.DropdownOption(key="light", text="Light"),
                ft.DropdownOption(key="dark", text="Dark"),
            ],
            value=config.theme,
        )

        theme_section = self._section(
            title="Appearance",
            subtitle=None,
            content=ft.Row([self._theme_dropdown], spacing=10),
        )

        # --- Batch limits ---
        self._spectra_batch = self._number_field(
            "Spectra file batch size",
            str(config.spectra_batch_size),
        )
        self._ident_batch = self._number_field(
            "Identification file batch size",
            str(config.identification_batch_size),
        )
        self._ident_proc_batch = self._number_field(
            "Identification processing batch size",
            str(config.identification_processing_batch_size),
        )
        self._protein_batch = self._number_field(
            "Protein mapping batch size",
            str(config.protein_mapping_batch_size),
        )

        batch_section = self._section(
            title="Batch Operation Limits",
            subtitle=(
                "Increasing batch size improves performance by reducing read/write "
                "overhead, but increases RAM usage during processing. Use with caution."
            ),
            content=ft.Column(
                [
                    self._spectra_batch,
                    self._ident_batch,
                    self._ident_proc_batch,
                    self._protein_batch,
                ],
                spacing=10,
            ),
        )

        # --- Color palette ---
        self._color_rows_column = ft.Column(spacing=6)
        for hex_color in config.default_colors:
            self._add_color_row(hex_color)

        add_color_btn = ft.TextButton(
            text="Add color",
            icon=ft.Icons.ADD,
            on_click=lambda _: self._on_add_color(),
        )

        color_section = self._section(
            title="Default Color Palette",
            subtitle="Colors used by default when creating new tools and subsets.",
            content=ft.Column(
                [self._color_rows_column, add_color_btn],
                spacing=8,
            ),
        )

        # --- Save button ---
        save_btn = ft.ElevatedButton(
            text="Save",
            icon=ft.Icons.SAVE,
            on_click=lambda _: self.page.run_task(self._save_settings),
        )

        self.controls = [
            ft.Container(
                content=ft.Column(
                    [
                        theme_section,
                        ft.Divider(),
                        batch_section,
                        ft.Divider(),
                        color_section,
                        ft.Container(height=20),
                        ft.Row([save_btn]),
                        ft.Container(height=30),
                    ],
                    spacing=16,
                ),
                padding=ft.padding.all(24),
                expand=True,
            )
        ]

    # ------------------------------------------------------------------
    # Helpers for building controls
    # ------------------------------------------------------------------

    @staticmethod
    def _section(title: str, subtitle: str | None, content: ft.Control) -> ft.Column:
        """Build a labeled settings section."""
        rows = [ft.Text(title, size=18, weight=ft.FontWeight.BOLD)]
        if subtitle:
            rows.append(
                ft.Text(subtitle, size=12, italic=True, color=ft.Colors.GREY_600)
            )
        rows.append(ft.Container(height=4))
        rows.append(content)
        return ft.Column(rows, spacing=6)

    @staticmethod
    def _number_field(label: str, value: str) -> ft.TextField:
        return ft.TextField(
            label=label,
            value=value,
            width=280,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

    def _add_color_row(self, hex_color: str = "#888888"):
        """Add one editable color row to the palette list."""
        preview = ft.Container(
            width=36,
            height=36,
            bgcolor=hex_color if _HEX_RE.match(hex_color) else "#888888",
            border_radius=4,
            border=ft.border.all(1, ft.Colors.GREY_400),
        )
        field = ft.TextField(
            value=hex_color,
            width=120,
            hint_text="#rrggbb",
            on_change=lambda e, p=preview, f=None: self._on_color_change(e, p),
            on_blur=lambda e, p=preview: self._on_color_blur(e, p),
        )
        # Fix: bind field reference for on_change
        field.on_change = lambda e, p=preview, tf=field: self._on_color_change(e, p)

        row_data = {"preview": preview, "field": field}
        self._color_rows.append(row_data)

        delete_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE,
            tooltip="Remove color",
            on_click=lambda _, rd=row_data: self._on_delete_color(rd),
        )

        row_container = ft.Container(
            content=ft.Row(
                [preview, field, delete_btn],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        row_data["container"] = row_container
        self._color_rows_column.controls.append(row_container)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_color_change(self, e: ft.ControlEvent, preview: ft.Container):
        """Live-update color preview as user types."""
        value = e.control.value or ""
        if _HEX_RE.match(value):
            preview.bgcolor = value
            e.control.border_color = None  # reset error highlight
        else:
            preview.bgcolor = "#888888"
        if self.page:
            preview.update()
            e.control.update()

    def _on_color_blur(self, e: ft.ControlEvent, preview: ft.Container):
        """Validate color on focus loss — highlight invalid values."""
        value = e.control.value or ""
        if not _HEX_RE.match(value):
            e.control.border_color = ft.Colors.RED
        else:
            e.control.border_color = None
        if self.page:
            e.control.update()

    def _on_add_color(self):
        self._add_color_row("#888888")
        if self.page:
            self._color_rows_column.update()

    def _on_delete_color(self, row_data: dict):
        self._color_rows.remove(row_data)
        self._color_rows_column.controls.remove(row_data["container"])
        if self.page:
            self._color_rows_column.update()

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    async def _save_settings(self):
        """Validate and persist settings to config."""
        errors = []
        warnings = []

        # Theme
        new_theme = self._theme_dropdown.value or "light"

        # Batch sizes
        batch_fields = [
            ("spectra_batch_size", self._spectra_batch),
            ("identification_batch_size", self._ident_batch),
            ("identification_processing_batch_size", self._ident_proc_batch),
            ("protein_mapping_batch_size", self._protein_batch),
        ]
        batch_values: dict[str, int] = {}
        for field_name, tf in batch_fields:
            try:
                val = int(tf.value or "0")
                if val <= 0:
                    raise ValueError("must be > 0")
                batch_values[field_name] = val
                tf.border_color = None
                tf.update()
                if val > _LARGE_BATCH_THRESHOLD:
                    warnings.append(tf.label)
            except ValueError:
                errors.append(f"'{tf.label}': must be a positive integer")
                tf.border_color = ft.Colors.RED
                tf.update()

        # Colors
        new_colors: list[str] = []
        for row_data in self._color_rows:
            val = (row_data["field"].value or "").strip()
            if not _HEX_RE.match(val):
                errors.append(f"Invalid color value: '{val}'")
                row_data["field"].border_color = ft.Colors.RED
                row_data["field"].update()
            else:
                row_data["field"].border_color = None
                row_data["field"].update()
                new_colors.append(val)

        if errors:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text("Fix errors before saving: " + "; ".join(errors)),
                bgcolor=ft.Colors.RED_400,
                open=True,
            )
            self.page.update()
            return

        # Warn about large batch sizes
        if warnings:
            confirmed = await self._confirm_large_batch(warnings)
            if not confirmed:
                return

        # Apply
        config.theme = new_theme
        for field_name, val in batch_values.items():
            setattr(config, field_name, val)
        config.default_colors = new_colors
        config.save()

        # Apply theme immediately
        self.page.theme_mode = (
            ft.ThemeMode.DARK if new_theme == "dark" else ft.ThemeMode.LIGHT
        )
        self.page.update()

        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("Settings saved"),
            bgcolor=ft.Colors.GREEN_400,
            open=True,
        )
        self.page.update()

    async def _confirm_large_batch(self, large_fields: list[str]) -> bool:
        """Show warning dialog for very large batch sizes. Returns True if confirmed."""
        result: list[bool] = [False]
        dialog_closed = ft.Event()

        def on_confirm(_):
            result[0] = True
            dlg.open = False
            self.page.update()

        def on_cancel(_):
            result[0] = False
            dlg.open = False
            self.page.update()

        fields_str = ", ".join(f'"{f}"' for f in large_fields)
        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Large Batch Size Warning"),
            content=ft.Text(
                f"Fields {fields_str} exceed {_LARGE_BATCH_THRESHOLD:,}. "
                f"{_LARGE_BATCH_WARNING}"
            ),
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel),
                ft.ElevatedButton("Yes, save anyway", on_click=on_confirm),
            ],
        )

        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

        # Wait for dialog close
        import asyncio
        while dlg.open:
            await asyncio.sleep(0.05)

        self.page.overlay.remove(dlg)
        self.page.update()
        return result[0]
