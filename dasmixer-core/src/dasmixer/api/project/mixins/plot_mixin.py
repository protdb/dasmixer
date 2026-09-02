"""Mixin for plot data preparation and saved plots management."""

from __future__ import annotations

import json
import gzip
import pickle
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import plotly.graph_objects as go


# Available checkbox options for the ion-plot subplot header (0.7.2a3).
# Each entry is (key, label, default_enabled). Order defines display order.
# GUI code (peptide_ion_plot_view.py) builds its checkboxes from this list
# so the two files stay in sync without duplicating the field/label/default
# definitions.
HEADER_FIELD_OPTIONS: list[tuple[str, str, bool]] = [
    ('preferred', 'Preferred', True),
    ('tool', 'Tool', True),
    ('sequence', 'Sequence', True),
    ('protein_id', 'Protein ID', False),
    ('gene', 'Gene', False),
    ('identity', 'Identity', True),
    ('ppm', 'PPM', False),
    ('score', 'Score', False),
    ('intensity_coverage', 'Intensity Coverage', False),
    ('quality', 'Quality', False),
    ('lcrr', 'LCRR', False),
]

# Keys of fields enabled by default (subset of HEADER_FIELD_OPTIONS).
DEFAULT_HEADER_FIELDS: list[str] = [key for key, _, default in HEADER_FIELD_OPTIONS if default]


def _format_spectrum_plot_header(plot: dict, header_fields: list[str]) -> str:
    """
    Build a single subplot header string from the enabled ``header_fields``.

    Null/missing values are skipped even if the corresponding field is
    enabled (e.g. quality/lcrr are not calculated for a partial protein
    match).
    """
    prefix = ""
    if 'preferred' in header_fields and plot.get('is_preferred'):
        prefix = "★ "

    parts: list[str] = []

    if 'tool' in header_fields and plot.get('tool') is not None:
        parts.append(str(plot['tool']))

    if 'sequence' in header_fields and plot.get('sequence') is not None:
        parts.append(str(plot['sequence']))

    if 'protein_id' in header_fields and plot.get('protein_id') is not None:
        parts.append(str(plot['protein_id']))

    if 'gene' in header_fields and plot.get('gene') is not None:
        parts.append(f"Gene: {plot['gene']}")

    if 'identity' in header_fields and plot.get('identity') is not None:
        parts.append(f"Identity: {plot['identity']:.2f}")

    if 'ppm' in header_fields and plot.get('ppm') is not None:
        parts.append(f"PPM: {plot['ppm']:.2f}")

    if 'score' in header_fields and plot.get('score') is not None:
        parts.append(f"Score: {plot['score']}")

    if 'intensity_coverage' in header_fields and plot.get('intensity_coverage') is not None:
        parts.append(f"iC: {plot['intensity_coverage']:.2f}")

    if 'quality' in header_fields and plot.get('quality') is not None:
        parts.append(f"Q: {plot['quality']:.2f}")

    if 'lcrr' in header_fields and plot.get('lcrr') is not None:
        parts.append(f"LCRR: {plot['lcrr']:.2f}")

    return prefix + " | ".join(parts)


class PlotMixin:
    """
    Mixin providing data preparation methods for plotting and saved plots management.
    
    Requires SpectraMixin (get_spectrum_full) functionality.
    """
    
    async def get_spectrum_plot_data(
        self,
        spectrum_id: int,
        get_matched: bool = False,
        header_fields: Optional[list[str]] = None,
    ) -> dict:
        """
        Get all data needed to plot spectrum with all identifications.

        Args:
            spectrum_id: Spectrum ID
            get_matched: If True, also fetch matched_sequence from peptide_match
                         via LEFT JOIN. Each identification may have a matched_sequence
                         different from its canonical_sequence.
            header_fields: List of enabled header field keys (see
                ``HEADER_FIELD_OPTIONS`` for the full list of supported keys
                and their default state). Fields whose value is null/missing
                for a given subplot are skipped even when enabled. Defaults
                to ``DEFAULT_HEADER_FIELDS`` when not provided.

        Returns:
            Dictionary with keys:
                - mz: list[float]
                - intensity: list[float]
                - charges: list[int] | int
                - sequences: list[str] - identification sequences
                - headers: list[str] - formatted headers per sequence,
                    built from the enabled header_fields
                - matched_sequences: list[str | None] - matched_sequence or None
                    (only populated when get_matched=True)
                - spectrum_info: dict
        """
        if header_fields is None:
            header_fields = DEFAULT_HEADER_FIELDS

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
            i.quality,
            i.lcrr,
            i.intensity_coverage,
            coalesce(m.matched_sequence_modified, matched_sequence) as matched_sequence_modified,
            m.matched_ppm,
            m.matched_coverage_percent,
            m.protein_id,
            m.identity,
            p.gene
            from identification i
            left join peptide_match m on i.id == m.identification_id
            left join tool as t on t.id = i.tool_id
            left join protein as p on p.id = m.protein_id
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
            i.quality,
            i.lcrr,
            i.intensity_coverage,
            null as matched_sequence_modified,
            null as matched_ppm,
            null as matched_coverage_percent,
            null as protein_id,
            null as identity,
            null as gene
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
                    'gene': None,
                    'is_preferred': row['is_preferred'],
                    'ppm': row['ppm'],
                    'score': row['score'],
                    'intensity_coverage': row['intensity_coverage'],
                    'quality': row['quality'],
                    'lcrr': row['lcrr'],
                    'matched': False,
                    'identity': None
                })
                tool_seqs.add(tool_seq)
            if get_matched and row.get('protein_id', None) is not None:
                if row['matched_sequence_modified'] != row['sequence']:
                    tool_seq_protein = f'{row["tool"]}:{row["matched_sequence_modified"]}'
                    if tool_seq_protein not in tool_seqs:
                        tool_seqs.add(tool_seq_protein)
                        plots.append({
                            'tool': row['tool'],
                            'sequence': row['matched_sequence_modified'],
                            'protein_id': row['protein_id'],
                            'gene': row['gene'],
                            'is_preferred': row['is_preferred'],
                            'ppm': row['matched_ppm'],
                            'score': row['score'],
                            'intensity_coverage': row['matched_coverage_percent'],
                            # Quality/LCRR are not (re)calculated for matched
                            # sequences on a partial protein match.
                            'quality': None,
                            'lcrr': None,
                            'matched': True,
                            'identity': row['identity']
                        })
        headers = []
        sequences = []

        for plot in plots:
            headers.append(_format_spectrum_plot_header(plot, header_fields))
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
