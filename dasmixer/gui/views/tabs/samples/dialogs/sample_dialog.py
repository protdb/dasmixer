"""Dialog for editing sample properties."""

import flet as ft
import json
from dasmixer.api.project.project import Project
from dasmixer.api.project.dataclasses import Sample
from dasmixer.gui.utils import show_snack


class SampleDialog:
    """Dialog for editing a sample."""
    
    def __init__(self, project: Project, page: ft.Page, sample: Sample, on_success_callback=None):
        """
        Initialize sample dialog.
        
        Args:
            project: Project instance
            page: Flet page
            sample: Sample to edit
            on_success_callback: Callback to execute after successful save
        """
        self.project = project
        self.page = page
        self.sample = sample
        self.on_success_callback = on_success_callback
        
        # Dialog controls
        self.name_field = None
        self.group_dropdown = None
        self.additions_field = None
        self.dialog = None
    
    async def show(self):
        """Show the dialog."""
        # Get available groups
        groups = await self.project.get_subsets()
        group_options = [ft.dropdown.Option(key="None", text="None")]
        group_options.extend([
            ft.dropdown.Option(key=str(g.id), text=g.name)
            for g in groups
        ])
        
        # Current group value
        current_group_value = str(self.sample.subset_id) if self.sample.subset_id else "None"
        
        # Serialize additions to JSON string for editing
        additions_text = ""
        if self.sample.additions:
            try:
                additions_text = json.dumps(self.sample.additions, indent=2)
            except:
                additions_text = str(self.sample.additions)
        
        # Create fields
        self.name_field = ft.TextField(
            label="Sample Name",
            value=self.sample.name,
            autofocus=True
        )
        
        self.group_dropdown = ft.Dropdown(
            label="Comparison Group",
            options=group_options,
            value=current_group_value,
            width=300
        )
        
        self.additions_field = ft.TextField(
            label="Additions (JSON)",
            value=additions_text,
            multiline=True,
            min_lines=4,
            max_lines=8,
            hint_text='e.g., {"albumin": 45.5, "total_protein": 70.0}'
        )
        
        # Create dialog
        self.dialog = ft.AlertDialog(
            title=ft.Text(f"Edit Sample: {self.sample.name}"),
            content=ft.Column([
                self.name_field,
                self.group_dropdown,
                self.additions_field,
                ft.Container(height=5),
                ft.Text(
                    "Additions should be valid JSON (e.g., for LFQ parameters)",
                    size=11,
                    italic=True,
                    color=ft.Colors.GREY_600
                )
            ], tight=True, width=450, scroll=ft.ScrollMode.AUTO),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=self._close
                ),
                ft.ElevatedButton(
                    "Save",
                    on_click=lambda e: self.page.run_task(self._save, e)
                )
            ]
        )
        
        self.page.overlay.append(self.dialog)
        self.dialog.open = True
        self.page.update()
    
    def _close(self, e=None):
        """Close the dialog."""
        self.dialog.open = False
        self.page.update()
    
    async def _save(self, e):
        """Save the sample."""
        # Validate
        if not self.name_field.value:
            self.name_field.error_text = "Name is required"
            self.name_field.update()
            return
        
        # Parse additions JSON
        additions = None
        if self.additions_field.value and self.additions_field.value.strip():
            try:
                additions = json.loads(self.additions_field.value)
            except json.JSONDecodeError as ex:
                self.additions_field.error_text = f"Invalid JSON: {ex}"
                self.additions_field.update()
                return
        
        try:
            # Update sample
            self.sample.name = self.name_field.value
            
            # Parse group
            if self.group_dropdown.value == "None":
                self.sample.subset_id = None
            else:
                self.sample.subset_id = int(self.group_dropdown.value)
            
            self.sample.additions = additions
            
            # Save to database
            await self.project.update_sample(self.sample)
            
            # Close dialog
            self._close()
            
            # Show success
            show_snack(self.page, f"Updated sample: {self.sample.name}", ft.Colors.GREEN_400)
            self.page.update()
            
            # Call success callback
            if self.on_success_callback:
                await self.on_success_callback()
        
        except Exception as ex:
            import traceback
            traceback.print_exc()
            
            show_snack(self.page, f"Error: {ex}", ft.Colors.RED_400)
            self.page.update()
