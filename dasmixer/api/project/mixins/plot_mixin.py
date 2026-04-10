"""Mixin for plot data preparation and saved plots management."""

import json
import gzip
import pickle
from datetime import datetime
from typing import Optional
import plotly.graph_objects as go


class PlotMixin:
    """
    Mixin providing data preparation methods for plotting and saved plots management.
    
    Requires SpectraMixin (get_spectrum_full) functionality.
    """
    
    async def get_spectrum_plot_data(self, spectrum_id: int, get_matched: bool = False) -> dict:
        """
        Get all data needed to plot spectrum with all identifications.

        Args:
            spectrum_id: Spectrum ID
            get_matched: If True, also fetch matched_sequence from peptide_match
                         via LEFT JOIN. Each identification may have a matched_sequence
                         different from its canonical_sequence.

        Returns:
            Dictionary with keys:
                - mz: list[float]
                - intensity: list[float]
                - charges: list[int] | int
                - sequences: list[str] - identification sequences
                - headers: list[str] - formatted headers per sequence
                    Format: "★ {tool} | {sequence} [(matched)] | PPM: {ppm}"
                - matched_sequences: list[str | None] - matched_sequence or None
                    (only populated when get_matched=True)
                - spectrum_info: dict
        """
        spectrum = await self.get_spectrum_full(spectrum_id)

        if get_matched:
            query = """
            select 
            i.spectre_id,
            t.name as tool,
            i.sequence,
            i.is_preferred,
            i.canonical_sequence,
            i.score,
            i.ppm,
            i.tool_id,
            m.matched_sequence,
            m.matched_ppm,
            m.protein_id,
            m.identity
            from identification i left join peptide_match m on i.id == m.identification_id left join tool as t on t.id = i.tool_id
            where i.spectre_id = ?
            order by i.tool_id ASC
            """
        else:
            query = """
            select 
            i.spectre_id,
            t.name as tool,
            i.sequence,
            i.is_preferred,
            i.canonical_sequence,
            i.score,
            i.ppm,
            i.tool_id,
            null as matched_sequence,
            null as matched_ppm,
            null as protein_id,
             null as identity
            from identification i left join tool as t on t.id = i.tool_id
            where i.spectre_id = ?
            order by i.is_preferred DESC, t.name DESC
            """

        ident_rows = await self._fetchall(query, (spectrum_id,))

        plots = []
        tool_seqs = set()

        for row in ident_rows:
            tool_seq = f'{row["tool"]}:{row["sequence"]}'
            if tool_seq not in tool_seqs:
                plots.append({
                    'tool': row['tool'],
                    'sequence': row['sequence'],
                    'protein_id': row['protein_id'],
                    'is_preferred': row['is_preferred'],
                    'ppm': row['ppm'],
                    'score': row['score'],
                    'matched': False,
                    'identity': None
                })
                tool_seqs.add(tool_seq)
            if row.get('protein_id', None) is not None:
                if row['matched_sequence'] != row['canonical_sequence']:
                    if tool_seq not in tool_seqs:
                        tool_seqs.add(tool_seq)
                        plots.append({
                            'tool': row['tool'],
                            'sequence': row['matched_sequence'],
                            'protein_id': row['protein_id'],
                            'is_preferred': row['is_preferred'],
                            'ppm': row['matched_ppm'],
                            'score': row['score'],
                            'matched': True,
                            'identity': row['identity']
                        })
        headers = []
        sequences = []

        for plot in plots:
            pref_marker = "★ " if plot['is_preferred'] else ""
            ppm_str = f"{plot['ppm']:.2f}" if plot['ppm'] is not None else "N/A"
            matched = f" (match: {plot['identity']})" if plot['matched'] else ""
            protein = f" | {plot['protein_id']}" if plot['protein_id'] is not None else ""
            header = f"{pref_marker}{plot['tool']} | {plot['sequence']}{matched}{protein} | PPM: {ppm_str} | Score: {plot['score']}"
            headers.append(header)
            sequences.append(plot['sequence'])

        # Determine charges
        if spectrum.get('charge_array') is not None:
            charges = spectrum['charge_array'].tolist()
        elif spectrum.get('charge_array_common_value') is not None:
            charges = int(spectrum['charge_array_common_value'])
        elif spectrum.get('charge') is not None:
            charges = int(spectrum['charge'])
        else:
            charges = 1

        return {
            'mz': spectrum['mz_array'].tolist(),
            'intensity': spectrum['intensity_array'].tolist(),
            'charges': charges,
            'sequences': sequences,
            'headers': headers,
            'spectrum_info': {
                'seq_no': spectrum['seq_no'],
                'scans': spectrum.get('scans'),
                'rt': spectrum.get('rt'),
                'pepmass': spectrum['pepmass'],
                'charge': spectrum.get('charge')
            }
        }
    
    # ===== Saved Plots Management (Stage 6) =====
    
    async def save_plot(
        self,
        plot_type: str,
        figure: go.Figure,
        settings: Optional[dict] = None
    ) -> int:
        """
        Save a plot to the database.
        
        Args:
            plot_type: Type identifier (e.g., "peptide_ion_coverage")
            figure: Plotly Figure object
            settings: Optional settings dict (will be JSON serialized)
        
        Returns:
            int: ID of saved plot
        """
        created_at = datetime.now().isoformat()
        
        # Serialize settings
        settings_json = json.dumps(settings) if settings else None
        
        # Serialize plot
        plot_blob = gzip.compress(pickle.dumps(figure))
        
        # Insert
        query = """
            INSERT INTO saved_plots (created_at, plot_type, settings, plot)
            VALUES (?, ?, ?, ?)
        """
        cursor = await self._execute(query, (created_at, plot_type, settings_json, plot_blob))
        plot_id = cursor.lastrowid
        
        await self.save()
        return plot_id
    
    async def get_saved_plots(self) -> list[dict]:
        """
        Get list of all saved plots (without plot data).
        
        Returns:
            list[dict]: [
                {
                    'id': int,
                    'created_at': str,
                    'plot_type': str,
                    'settings': dict
                },
                ...
            ]
        """
        rows = await self._fetchall(
            "SELECT id, created_at, plot_type, settings FROM saved_plots ORDER BY created_at DESC"
        )
        
        result = []
        for row in rows:
            settings = json.loads(row['settings']) if row['settings'] else {}
            result.append({
                'id': row['id'],
                'created_at': row['created_at'],
                'plot_type': row['plot_type'],
                'settings': settings
            })
        
        return result
    
    async def load_saved_plot(self, plot_id: int) -> go.Figure:
        """
        Load a plot from the database.
        
        Args:
            plot_id: ID in saved_plots table
        
        Returns:
            go.Figure: Deserialized Plotly figure
        
        Raises:
            ValueError: If plot not found
        """
        row = await self._fetchone("SELECT plot FROM saved_plots WHERE id = ?", (plot_id,))
        
        if not row or not row['plot']:
            raise ValueError(f"Plot with id={plot_id} not found")
        
        fig = pickle.loads(gzip.decompress(row['plot']))
        return fig
    
    async def delete_saved_plot(self, plot_id: int):
        """
        Delete a saved plot.
        
        Args:
            plot_id: ID in saved_plots table
        """
        await self._execute("DELETE FROM saved_plots WHERE id = ?", (plot_id,))
        await self.save()
