"""Samples section - manage sample list."""

import flet as ft
from dasmixer.api.project.project import Project
from .base_section import BaseSection
from .shared_state import SamplesTabState
from .dialogs.sample_dialog import SampleDialog


class SamplesSection(BaseSection):
    """Section for managing samples list."""
    
    def __init__(self, project: Project, state: SamplesTabState, parent_tab):
        """Initialize samples section."""
        self.samples_container = None
        super().__init__(project, state, parent_tab)
    
    def _build_content(self) -> ft.Control:
        """Build section content."""
        self.samples_container = ft.Column([
            ft.Text("Samples", size=18, weight=ft.FontWeight.BOLD),
            ft.Container(
                content=ft.Text("No samples yet. Import spectra to add samples."),
                padding=20
            )
        ], spacing=10)
        
        return self.samples_container
    
    async def load_data(self):
        """Load samples list."""
        print("Loading samples...")
        samples = await self.project.get_samples()
        
        self.samples_container.controls.clear()
        self.samples_container.controls.append(
            ft.Text("Samples", size=18, weight=ft.FontWeight.BOLD)
        )
        
        if not samples:
            self.samples_container.controls.append(
                ft.Container(
                    content=ft.Text("No samples yet. Import spectra to add samples."),
                    padding=20
                )
            )
        else:
            # Build samples list
            samples_list = ft.Column(spacing=5)
            
            for sample in samples:
                # Get tools for this sample
                spectra_files = await self.project.get_spectra_files(sample_id=sample.id)
                tools_info = []
                
                for _, sf in spectra_files.iterrows():
                    # Check for identifications
                    ident_files = await self.project.get_identification_files(spectra_file_id=sf['id'])
                    if len(ident_files) > 0:
                        for _, ident_file in ident_files.iterrows():
                            tools_info.append(f"✓ {ident_file['tool_name']}")
                
                tools_display = ", ".join(tools_info) if tools_info else "No identifications"
                
                # Get group name
                group_name = "None"
                if sample.subset_id:
                    groups = await self.project.get_subsets()
                    matching_groups = [g for g in groups if g.id == sample.subset_id]
                    if matching_groups:
                        group_name = matching_groups[0].name
                
                samples_list.controls.append(
                    ft.ListTile(
                        leading=ft.Icon(ft.Icons.SCIENCE, size=16),
                        title=ft.Text(sample.name, weight=ft.FontWeight.BOLD, size=14),
                        subtitle=ft.Text(
                            f"Files: {sample.spectra_files_count} • {tools_display} • Group: {group_name}",
                            size=11
                        ),
                        trailing=ft.IconButton(
                            icon=ft.Icons.EDIT_OUTLINED,
                            icon_color=ft.Colors.BLUE_400,
                            tooltip="Edit sample",
                            on_click=lambda e, s=sample: self.page.run_task(self._show_edit_sample_dialog, e, s)
                        ),
                        dense=True
                    )
                )
            
            self.samples_container.controls.append(
                ft.Container(
                    content=samples_list,
                    padding=10,
                    border=ft.border.all(1, ft.Colors.GREY_300),
                    border_radius=5
                )
            )
        
        print(f"Samples loaded: {len(samples)}")
        self.state.samples_count = len(samples)
        
        if self.samples_container.page:
            self.samples_container.update()
    
    async def _show_edit_sample_dialog(self, e, sample):
        """Show dialog for editing sample."""
        dialog = SampleDialog(
            self.project,
            self.page,
            sample,
            on_success_callback=self._on_sample_saved
        )
        await dialog.show()
    
    async def _on_sample_saved(self):
        """Callback after sample is saved."""
        await self.load_data()
        # Notify other sections to refresh (groups need to update counts)
        self.state.needs_refresh_groups = True
