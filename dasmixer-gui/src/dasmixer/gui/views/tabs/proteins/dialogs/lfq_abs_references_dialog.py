"""
Dialog for configuring LFQ absolute concentration references.
"""

import asyncio
import flet as ft

from dasmixer.utils import logger
from dasmixer.api.project.project import Project
from dasmixer.gui.utils import show_snack


class LFQAbsReferencesDialog:
    """
    Dialog for setting up absolute concentration references.
    
    Allows user to:
    - Select total protein field from additionals
    - Select reference protein field from additionals
    - Set reference protein ID (default P02768)
    - Configure default concentration values
    """

    def __init__(self, project: Project, page: ft.Page):
        self.project = project
        self.page = page

    async def show(self):
        """Build and show the dialog."""
        # Load current settings
        current_total_field = await self.project.get_setting('lfq_abs_total_protein_field') or ''
        current_ref_field = await self.project.get_setting('lfq_abs_reference_protein_field') or ''
        current_ref_id = await self.project.get_setting('lfq_abs_reference_protein_id') or 'P02768'
        current_use_defaults = (await self.project.get_setting('lfq_abs_use_defaults')) == 'True'
        current_default_ref = await self.project.get_setting('lfq_abs_default_reference_value') or '40.0'
        current_default_total = await self.project.get_setting('lfq_abs_default_total_protein_value') or '75.0'

        # Get additionals keys for dropdowns
        keys = await self.project.get_additionals_keys()
        empty_option = ft.DropdownOption(key="", text="— not used —")
        key_options = [empty_option] + [ft.DropdownOption(key=k, text=k) for k in keys]

        # Total protein field dropdown
        total_field_dd = ft.Dropdown(
            label="Total protein field",
            options=key_options,
            value=current_total_field if current_total_field in keys else "",
            width=350,
        )

        # Reference protein field dropdown
        ref_field_dd = ft.Dropdown(
            label="Reference protein field",
            options=key_options,
            value=current_ref_field if current_ref_field in keys else "",
            width=350,
        )

        # Reference protein ID
        ref_id_field = ft.TextField(
            label="Reference protein ID",
            value=current_ref_id,
            width=350,
        )

        # Use defaults checkbox
        use_defaults_cb = ft.Checkbox(
            label="Use default concentrations",
            value=current_use_defaults,
        )

        # Default values (only enabled when use_defaults is checked)
        default_ref_field = ft.TextField(
            label="Default reference value (g/l)",
            value=current_default_ref,
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER,
            disabled=not current_use_defaults,
        )

        default_total_field = ft.TextField(
            label="Default total protein value (g/l)",
            value=current_default_total,
            width=200,
            keyboard_type=ft.KeyboardType.NUMBER,
            disabled=not current_use_defaults,
        )

        def on_use_defaults_changed(e):
            enabled = use_defaults_cb.value
            default_ref_field.disabled = not enabled
            default_total_field.disabled = not enabled
            if use_defaults_cb.page:
                use_defaults_cb.page.update()

        use_defaults_cb.on_change = on_use_defaults_changed

        note_text = (
            "Concentrations must be provided in g/l. The LFQ method "
            "determines which reference is preferred: for emPAI and NSAF, "
            "total protein concentration is recommended; for iBAQ and Top3, "
            "a reference protein works best. If both values are provided, "
            "the most suitable one is selected automatically."
        )

        # Result handling
        result_event = asyncio.Event()
        saved = False

        async def on_save(e):
            nonlocal saved
            try:
                # Validate numeric fields
                if use_defaults_cb.value:
                    float(default_ref_field.value or 0)
                    float(default_total_field.value or 0)
            except ValueError:
                show_snack(self.page, "Please enter valid numbers for default values", ft.Colors.RED_400)
                self.page.update()
                return

            # Save all settings
            await self.project.set_setting('lfq_abs_total_protein_field', total_field_dd.value or '')
            await self.project.set_setting('lfq_abs_reference_protein_field', ref_field_dd.value or '')
            await self.project.set_setting('lfq_abs_reference_protein_id', ref_id_field.value or 'P02768')
            await self.project.set_setting('lfq_abs_use_defaults', str(use_defaults_cb.value))
            await self.project.set_setting('lfq_abs_default_reference_value', str(default_ref_field.value or '40.0'))
            await self.project.set_setting('lfq_abs_default_total_protein_value', str(default_total_field.value or '75.0'))
            await self.project.save()

            saved = True
            dlg.open = False
            if dlg.page:
                dlg.page.update()
            result_event.set()
            show_snack(self.page, "Reference settings saved", ft.Colors.GREEN_400)

        def on_cancel(e):
            dlg.open = False
            if dlg.page:
                dlg.page.update()
            result_event.set()

        dlg = ft.AlertDialog(
            title=ft.Text("Absolute Concentration References"),
            content=ft.Column([
                total_field_dd,
                ft.Container(height=6),
                ref_field_dd,
                ft.Container(height=6),
                ref_id_field,
                ft.Container(height=10),
                use_defaults_cb,
                ft.Container(height=4),
                ft.Row([default_ref_field, default_total_field], spacing=10),
                ft.Container(height=10),
                ft.Container(
                    content=ft.Text(note_text, size=11, color=ft.Colors.GREY_600, italic=True),
                    padding=ft.padding.all(8),
                    bgcolor=ft.Colors.GREY_100,
                    border_radius=5,
                ),
            ], tight=True, width=500, scroll=ft.ScrollMode.AUTO),
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel),
                ft.ElevatedButton(
                    content=ft.Text("Save"),
                    icon=ft.Icons.SAVE,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_600, color=ft.Colors.WHITE),
                    on_click=lambda e: self.page.run_task(on_save, e) if self.page else None,
                ),
            ],
        )
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()
        await result_event.wait()
