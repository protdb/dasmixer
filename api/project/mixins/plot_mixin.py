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
                SELECT
                    i.sequence, i.canonical_sequence, i.ppm, i.is_preferred,
                    t.name AS tool_name,
                    pm.matched_sequence
                FROM identification i
                JOIN tool t ON i.tool_id = t.id
                LEFT JOIN (
                    SELECT identification_id, matched_sequence
                    FROM peptide_match
                    GROUP BY identification_id
                ) pm ON pm.identification_id = i.id
                WHERE i.spectre_id = ?
                ORDER BY i.is_preferred DESC, i.score DESC
            """
        else:
            query = """
                SELECT
                    i.sequence, i.canonical_sequence, i.ppm, i.is_preferred,
                    t.name AS tool_name,
                    NULL AS matched_sequence
                FROM identification i
                JOIN tool t ON i.tool_id = t.id
                WHERE i.spectre_id = ?
                ORDER BY i.is_preferred DESC, i.score DESC
            """

        ident_rows = await self._fetchall(query, (spectrum_id,))

        sequences = []
        headers = []
        matched_sequences = []

        for row in ident_rows:
            seq = row['sequence']
            matched_seq = row['matched_sequence']
            ppm_str = f"{row['ppm']:.2f}" if row['ppm'] is not None else "N/A"
            pref_marker = "★ " if row['is_preferred'] else ""
            matched_marker = " (matched)" if matched_seq else ""

            header = f"{pref_marker}{row['tool_name']} | {seq}{matched_marker} | PPM: {ppm_str}"

            sequences.append(seq)
            headers.append(header)
            matched_sequences.append(matched_seq)

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
            'matched_sequences': matched_sequences,
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
