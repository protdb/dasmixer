"""FASTA loading and protein mapping section."""

import flet as ft
from pathlib import Path

from dasmixer.api.inputs.proteins.fasta import FastaParser
from dasmixer.api.calculations.peptides.protein_map import map_proteins
from .base_section import BaseSection
from .dialogs.progress_dialog import ProgressDialog


class FastaSection(BaseSection):
    """FASTA file loading and protein mapping configuration."""
    
    def _build_content(self) -> ft.Control:
        """Build FASTA section UI."""
        # File selection
        self.fasta_file_field = ft.TextField(
            label="FASTA file path",
            hint_text="Select FASTA file...",
            expand=True,
            read_only=True
        )
        
        self.fasta_browse_btn = ft.ElevatedButton(
            content=ft.Text("Browse"),
            icon=ft.Icons.FOLDER_OPEN,
            on_click=lambda e: self.page.run_task(self.browse_fasta_file, e)
        )
        
        # Options
        self.fasta_is_uniprot_cb = ft.Checkbox(
            label="Sequences in UniProt format",
            value=True
        )
        
        self.fasta_enrich_uniprot_cb = ft.Checkbox(
            label="Enrich data from UniProt",
            value=False
        )
        
        # Load button with protein count - NEW
        self.fasta_load_btn = ft.ElevatedButton(
            content=ft.Text("Load Sequences"),
            icon=ft.Icons.UPLOAD_FILE,
            on_click=lambda e: self.page.run_task(self.load_fasta_file, e)
        )
        
        self.protein_count_text = ft.Text(
            "",
            size=11,
            color=ft.Colors.GREY_600,
            italic=True
        )
        
        self.fasta_status_text = ft.Text(
            "No library loaded",
            italic=True,
            color=ft.Colors.GREY_600
        )
        
        # Protein mapping settings
        self.blast_max_accepts_field = ft.TextField(
            label="BLAST Max Accepts",
            value="16",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        self.blast_max_rejects_field = ft.TextField(
            label="BLAST Max Rejects",
            value="5",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        self.match_proteins_btn = ft.ElevatedButton(
            content=ft.Text("Match Proteins to Identifications"),
            icon=ft.Icons.LINK,
            on_click=lambda e: self.page.run_task(self.match_proteins, e)
        )
        
        return ft.Column([
            ft.Text("Protein Sequence Library", size=18, weight=ft.FontWeight.BOLD),
            ft.Row([self.fasta_file_field, self.fasta_browse_btn], spacing=10),
            self.fasta_is_uniprot_cb,
            self.fasta_enrich_uniprot_cb,
            ft.Container(height=5),
            ft.Row([self.fasta_load_btn, self.protein_count_text], spacing=10),
            ft.Container(height=5),
            self.fasta_status_text,
            ft.Container(height=15),
            ft.Text("Protein Mapping Settings", size=16, weight=ft.FontWeight.BOLD),
            ft.Row([self.blast_max_accepts_field, self.blast_max_rejects_field], spacing=10),
            ft.Container(height=5),
            self.match_proteins_btn
        ], spacing=10)
    
    async def load_data(self):
        """Load initial data."""
        await self.load_blast_settings()
        await self.update_protein_count()
    
    async def update_protein_count(self):
        """Update protein count display."""
        try:
            count = await self.project.get_protein_count()
            self.state.protein_count = count
            
            if count > 0:
                self.protein_count_text.value = f"({count:,} proteins in database)"
                self.protein_count_text.color = ft.Colors.GREEN_700
            else:
                self.protein_count_text.value = "(no proteins loaded)"
                self.protein_count_text.color = ft.Colors.GREY_600
            
            self.protein_count_text.update()
            
        except Exception as ex:
            print(f"Error updating protein count: {ex}")
    
    async def browse_fasta_file(self, e):
        """Open file picker for FASTA selection."""
        try:
            # file_picker = ft.FilePicker(
            #     on_result=lambda result: self._on_file_picked(result)
            # )
            # self.page.overlay.append(file_picker)
            # self.page.update()
            
            res = await ft.FilePicker().pick_files(
                dialog_title="Select FASTA File",
                allowed_extensions=["fasta", "fa"],
                allow_multiple=False
            )
            self._on_file_picked(res)
            
        except Exception as ex:
            print(f"Error: {ex}")
            self.show_error(f"Error: {str(ex)}")
    
    def _on_file_picked(self, result):
        """Handle file picker result."""
        if result and len(result) > 0:
            self.fasta_file_field.value = result[0].path
            self.state.fasta_file_path = result[0].path
            self.fasta_file_field.update()
    
    async def load_fasta_file(self, e):
        """Load FASTA file with progress."""
        if not self.fasta_file_field.value:
            self.show_warning("Please select a FASTA file")
            return
        
        dialog = ProgressDialog(self.page, "Loading Protein Sequences")
        dialog.show()
        
        try:
            # Validate
            dialog.update_progress(None, "Validating...")
            
            parser = FastaParser(
                file_path=self.fasta_file_field.value,
                is_uniprot=self.fasta_is_uniprot_cb.value,
                enrich_from_uniprot=self.fasta_enrich_uniprot_cb.value
            )
            
            if not await parser.validate():
                dialog.close()
                self.show_error("Invalid FASTA format")
                return
            
            # Import
            dialog.update_progress(None, "Importing...")
            
            total = 0
            async for batch in parser.parse_batch(batch_size=100):
                if self.fasta_enrich_uniprot_cb.value:
                    batch = await parser.enrich_with_uniprot(batch)
                
                await self.project.add_proteins_batch(batch)
                total += len(batch)
                dialog.update_progress(None, "Importing...", f"Loaded {total} proteins...")
            
            # Update status
            self.fasta_status_text.value = f"Loaded: {total:,} proteins from {Path(self.fasta_file_field.value).name}"
            self.fasta_status_text.color = ft.Colors.GREEN_700
            self.fasta_status_text.italic = False
            self.fasta_status_text.update()
            
            # Update protein count
            await self.update_protein_count()
            
            dialog.complete(f"Total: {total} proteins")
            
            import asyncio
            await asyncio.sleep(1)
            dialog.close()
            
            self.show_success(f"Loaded {total:,} proteins")
            
        except Exception as ex:
            import traceback
            print(f"Error: {traceback.format_exc()}")
            dialog.close()
            self.show_error(f"Error: {str(ex)}")
    
    async def load_blast_settings(self):
        """Load BLAST settings from project."""
        try:
            max_accepts = await self.project.get_setting('max_blast_accept', '16')
            max_rejects = await self.project.get_setting('max_blast_reject', '5')
            self.blast_max_accepts_field.value = max_accepts
            self.blast_max_rejects_field.value = max_rejects
        except Exception as ex:
            print(f"Error loading BLAST settings: {ex}")
    
    async def save_blast_settings(self):
        """Save BLAST settings to project."""
        await self.project.set_setting('max_blast_accept', self.blast_max_accepts_field.value)
        await self.project.set_setting('max_blast_reject', self.blast_max_rejects_field.value)
    
    async def match_proteins(self, e):
        """Match proteins to identifications (with UI)."""
        await self.match_proteins_internal()
    
    async def match_proteins_internal(self, sample_id: int | None = None):
        """Match proteins to identifications (internal, no event). Delegates to MatchProteinsAction."""
        from dasmixer.gui.actions.protein_map_action import MatchProteinsAction
        action = MatchProteinsAction(self.project, self.page)
        await action.run(state=self.state, sample_id=sample_id)
