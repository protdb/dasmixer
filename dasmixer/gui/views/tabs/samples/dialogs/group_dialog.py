"""Dialog for creating and editing comparison groups."""

import flet as ft
from dasmixer.api.project.project import Project
from dasmixer.api.project.dataclasses import Subset
from ..constants import get_default_color
from dasmixer.gui.utils import show_snack


class GroupDialog:
    """Dialog for adding or editing a comparison group."""
    
    def __init__(self, project: Project, page: ft.Page, on_success_callback=None, group: Subset = None):
        """
        Initialize group dialog.
        
        Args:
            project: Project instance
            page: Flet page
            on_success_callback: Callback to execute after successful save
            group: Existing group to edit (None for creating new)
        """
        self.project = project
        self.page = page
        self.on_success_callback = on_success_callback
        self.group = group
        self.is_edit_mode = group is not None
        
        # Dialog controls
        self.name_field = None
        self.details_field = None
        self.color_field = None
        self.dialog = None
    
    async def show(self):
        """Show the dialog immediately, then populate fields."""
        dlg_title = "Edit Group" if self.is_edit_mode else "Add Comparison Group"

        # For edit mode, all data is already available — no await needed.
        # For create mode we need get_subsets() to pick a default color.
        if self.is_edit_mode:
            default_color = self.group.display_color or "#3B82F6"
            await self._show_with_color(dlg_title, default_color)
        else:
            # Show spinner immediately, load color in background
            self._spinner_col = ft.Column(
                [ft.ProgressRing(width=28, height=28, stroke_width=3)],
                tight=True,
                width=400,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            )
            self.dialog = ft.AlertDialog(
                title=ft.Text(dlg_title),
                content=self._spinner_col,
                actions=[ft.TextButton("Cancel", on_click=self._close)],
            )
            self.page.overlay.append(self.dialog)
            self.dialog.open = True
            self.page.update()

            groups = await self.project.get_subsets()
            default_color = get_default_color(len(groups))
            await self._fill_dialog(dlg_title, default_color)

    async def _show_with_color(self, dlg_title: str, default_color: str):
        """Build and open dialog immediately (edit mode — no async needed)."""
        self.dialog = ft.AlertDialog(
            title=ft.Text(dlg_title),
            content=ft.ProgressRing(width=28, height=28, stroke_width=3),
            actions=[ft.TextButton("Cancel", on_click=self._close)],
        )
        self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()
        await self._fill_dialog(dlg_title, default_color)

    async def _fill_dialog(self, dlg_title: str, default_color: str):
        """Replace dialog content with the actual form."""
        if default_color.startswith('#'):
            default_color = default_color[1:]

        self.name_field = ft.TextField(
            label="Group Name",
            value=self.group.name if self.is_edit_mode else "",
            autofocus=True,
        )
        self.details_field = ft.TextField(
            label="Description (optional)",
            value=self.group.details if self.is_edit_mode and self.group.details else "",
            multiline=True,
            min_lines=2,
            max_lines=4,
        )
        self.color_field = ft.TextField(
            label="Color (hex)",
            value=default_color,
            max_length=6,
            hint_text="e.g., FF0000 for red",
        )
        color_preview = ft.Container(
            width=50, height=50, border_radius=5, bgcolor=f"#{default_color}"
        )

        def update_color_preview(e):
            color_value = self.color_field.value
            if color_value:
                if not color_value.startswith('#'):
                    color_value = '#' + color_value
                try:
                    color_preview.bgcolor = color_value
                    color_preview.update()
                except Exception:
                    pass

        self.color_field.on_change = update_color_preview

        self.dialog.content = ft.Column(
            [
                self.name_field,
                self.details_field,
                ft.Row(
                    [self.color_field, color_preview],
                    alignment=ft.MainAxisAlignment.START,
                    spacing=10,
                ),
            ],
            tight=True,
            width=400,
        )
        self.dialog.actions = [
            ft.TextButton("Cancel", on_click=self._close),
            ft.ElevatedButton(
                "Save" if self.is_edit_mode else "Add",
                on_click=lambda e: self.page.run_task(self._save, e),
            ),
        ]
        self.page.update()
    
    def _close(self, e=None):
        """Close the dialog."""
        self.dialog.open = False
        self.page.update()
    
    async def _save(self, e):
        """Save the group."""
        # Validate
        if not self.name_field.value:
            self.name_field.error_text = "Name is required"
            self.name_field.update()
            return
        
        try:
            # Prepare color
            color = self.color_field.value
            if not color.startswith('#'):
                color = '#' + color
            
            if self.is_edit_mode:
                # Update existing group
                self.group.name = self.name_field.value
                self.group.details = self.details_field.value or None
                self.group.display_color = color
                
                await self.project.update_subset(self.group)
                
                success_message = f"Updated group: {self.group.name}"
            else:
                # Create new group
                await self.project.add_subset(
                    name=self.name_field.value,
                    details=self.details_field.value or None,
                    display_color=color
                )
                
                success_message = f"Added group: {self.name_field.value}"
            
            # Close dialog
            self._close()
            
            # Show success
            show_snack(self.page, success_message, ft.Colors.GREEN_400)
            self.page.update()
            
            # Call success callback
            if self.on_success_callback:
                await self.on_success_callback()
        
        except Exception as ex:
            show_snack(self.page, f"Error: {ex}", ft.Colors.RED_400)
            self.page.update()
