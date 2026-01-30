"""Samples tab - manage samples, groups, and import data."""

import flet as ft
from api.project.project import Project


class SamplesTab(ft.Container):
    """
    Samples tab for managing:
    - Comparison groups (subsets)
    - Samples and their group assignments
    - Data import (spectra and identifications)
    """
    
    def __init__(self, project: Project):
        super().__init__()
        self.project = project
        self.groups_list = ft.Column(spacing=5)
        self.samples_table = None
        
        # Build content
        self.content = self._build_content()
        self.padding = 20
        self.expand = True
    
    def _build_content(self):
        """Build the tab content."""
        # Groups management section
        groups_section = ft.Container(
            content=ft.Column([
                ft.Text("Comparison Groups", size=18, weight=ft.FontWeight.BOLD),
                self.groups_list,
                ft.Container(height=10),
                ft.Row([
                    ft.ElevatedButton(
                        content=ft.Text("Add Group"),
                        icon=ft.Icons.ADD,
                        on_click=self.show_add_group_dialog
                    ),
                    ft.OutlinedButton(
                        content=ft.Text("Delete Selected"),
                        icon=ft.Icons.DELETE,
                        on_click=self.delete_selected_group
                    )
                ], spacing=10)
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY),
            border_radius=10
        )
        
        # Import buttons section
        import_section = ft.Container(
            content=ft.Column([
                ft.Text("Import Data", size=18, weight=ft.FontWeight.BOLD),
                ft.Row([
                    ft.ElevatedButton(
                        content=ft.Text("Import Spectra (MGF)"),
                        icon=ft.Icons.UPLOAD_FILE,
                        on_click=self.show_import_spectra_dialog
                    ),
                    ft.ElevatedButton(
                        content=ft.Text("Import Identifications"),
                        icon=ft.Icons.UPLOAD_FILE,
                        on_click=self.show_import_identifications_dialog
                    )
                ], spacing=10)
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY),
            border_radius=10
        )
        
        # Samples table section
        samples_section = ft.Container(
            content=ft.Column([
                ft.Text("Samples", size=18, weight=ft.FontWeight.BOLD),
                ft.Container(
                    content=ft.Text("No samples yet. Import spectra to add samples."),
                    padding=20
                )
            ], spacing=10),
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY),
            border_radius=10,
            expand=True
        )
        
        # Main layout
        return ft.Column([
            groups_section,
            ft.Container(height=10),
            import_section,
            ft.Container(height=10),
            samples_section
        ],
        spacing=10,
        scroll=ft.ScrollMode.AUTO,
        expand=True
        )
    
    async def did_mount_async(self):
        """Load data when tab is mounted."""
        await self.refresh_groups()
        await self.refresh_samples()
    
    async def refresh_groups(self):
        """Refresh groups list."""
        groups = await self.project.get_subsets()
        
        self.groups_list.controls.clear()
        
        for group in groups:
            # Count samples in group
            samples = await self.project.get_samples(subset_id=group.id)
            
            self.groups_list.controls.append(
                ft.ListTile(
                    leading=ft.Container(
                        content=ft.Icon(ft.Icons.FOLDER, color=group.display_color or ft.Colors.PRIMARY),
                        width=40
                    ),
                    title=ft.Text(group.name, weight=ft.FontWeight.BOLD),
                    subtitle=ft.Text(f"{len(samples)} samples" + (f" • {group.details}" if group.details else "")),
                    data=group.id
                )
            )
        
        if not groups:
            self.groups_list.controls.append(
                ft.Text("No groups. Click 'Add Group' to create one.", italic=True)
            )
        
        self.update()
    
    async def refresh_samples(self):
        """Refresh samples table."""
        # Will be implemented with DataTable
        # For now, just placeholder
        pass
    
    def show_add_group_dialog(self, e):
        """Show dialog for adding new group."""
        name_field = ft.TextField(label="Group Name", autofocus=True)
        details_field = ft.TextField(label="Description (optional)", multiline=True)
        color_field = ft.TextField(
            label="Color (hex)",
            value="#3B82F6",
            prefix_text="#"
        )
        
        async def save_group(e):
            if not name_field.value:
                name_field.error_text = "Name is required"
                self.page.update()
                return
            
            try:
                color = color_field.value
                if not color.startswith('#'):
                    color = '#' + color
                
                await self.project.add_subset(
                    name=name_field.value,
                    details=details_field.value or None,
                    display_color=color
                )
                
                dialog.open = False
                self.page.update()
                
                await self.refresh_groups()
                
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Added group: {name_field.value}"),
                    bgcolor=ft.Colors.GREEN_400
                )
                self.page.snack_bar.open = True
                self.page.update()
                
            except Exception as ex:
                self.page.snack_bar = ft.SnackBar(
                    content=ft.Text(f"Error: {ex}"),
                    bgcolor=ft.Colors.RED_400
                )
                self.page.snack_bar.open = True
                self.page.update()
        
        dialog = ft.AlertDialog(
            title=ft.Text("Add Comparison Group"),
            content=ft.Column([
                name_field,
                details_field,
                color_field
            ], tight=True, width=400),
            actions=[
                ft.TextButton(content=ft.Text("Cancel"), on_click=lambda _: self.close_dialog(dialog)),
                ft.ElevatedButton(content=ft.Text("Add"), on_click=save_group)
            ]
        )
        
        self.page.dialog = dialog
        dialog.open = True
        self.page.update()
    
    def delete_selected_group(self, e):
        """Delete selected group (placeholder)."""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("Select a group from the list first (feature coming soon)"),
            bgcolor=ft.Colors.BLUE_400
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def show_import_spectra_dialog(self, e):
        """Show import spectra dialog."""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("Import dialog coming soon. Use CLI for now: 'dasmixer project.dasmix import mgf-pattern'"),
            bgcolor=ft.Colors.BLUE_400
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def show_import_identifications_dialog(self, e):
        """Show import identifications dialog."""
        self.page.snack_bar = ft.SnackBar(
            content=ft.Text("Import identifications coming soon"),
            bgcolor=ft.Colors.BLUE_400
        )
        self.page.snack_bar.open = True
        self.page.update()
    
    def close_dialog(self, dialog):
        """Close dialog."""
        dialog.open = False
        self.page.update()
