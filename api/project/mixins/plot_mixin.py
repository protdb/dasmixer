"""Mixin for plot data preparation methods."""


class PlotMixin:
    """
    Mixin providing data preparation methods for plotting.
    
    Requires SpectraMixin (get_spectrum_full) functionality.
    """
    
    async def get_spectrum_plot_data(self, spectrum_id: int) -> dict:
        """
        Get all data needed to plot spectrum with all identifications.
        
        Returns spectrum arrays and all identification sequences for this spectrum,
        ready to be unpacked into make_full_spectrum_plot().
        
        Args:
            spectrum_id: Spectrum ID
        
        Returns:
            Dictionary with keys:
                - mz: list[float] - m/z array
                - intensity: list[float] - intensity array
                - charges: list[int] | int - charge array or single charge
                - sequences: list[str] - all identified sequences for this spectrum
                - headers: list[str] - formatted headers for each sequence
                    Format: "{tool_name} | Score: {score:.2f} | PPM: {ppm:.2f}"
                - spectrum_info: dict - spectrum metadata
                    - seq_no: int
                    - scans: int
                    - rt: float
                    - pepmass: float
                    - charge: int
        
        Example:
            >>> data = await project.get_spectrum_plot_data(123)
            >>> from api.spectra.plot_flow import make_full_spectrum_plot
            >>> from api.spectra.ion_match import IonMatchParameters
            >>> 
            >>> params = IonMatchParameters(ions=['b', 'y'], tolerance=20.0)
            >>> fig = make_full_spectrum_plot(
            ...     params=params,
            ...     **data  # Unpack dict directly
            ... )
        """
        # Get spectrum with arrays
        spectrum = await self.get_spectrum_full(spectrum_id)
        
        # Get all identifications for this spectrum
        query = """
            SELECT 
                i.sequence, i.score, i.ppm, i.is_preferred,
                t.name AS tool_name
            FROM identification i
            JOIN tool t ON i.tool_id = t.id
            WHERE i.spectre_id = ?
            ORDER BY i.is_preferred DESC, i.score DESC
        """
        ident_rows = await self._fetchall(query, (spectrum_id,))
        
        # Build sequences and headers
        sequences = []
        headers = []
        
        for row in ident_rows:
            sequences.append(row['sequence'])
            
            # Format header
            score_str = f"{row['score']:.2f}" if row['score'] is not None else "N/A"
            ppm_str = f"{row['ppm']:.2f}" if row['ppm'] is not None else "N/A"
            pref_marker = "★ " if row['is_preferred'] else ""
            
            header = f"{pref_marker}{row['tool_name']} | Score: {score_str} | PPM: {ppm_str}"
            headers.append(header)
        
        # Determine charges
        if spectrum.get('charge_array') is not None:
            charges = spectrum['charge_array'].tolist()
        elif spectrum.get('charge_array_common_value') is not None:
            charges = int(spectrum['charge_array_common_value'])
        elif spectrum.get('charge') is not None:
            charges = int(spectrum['charge'])
        else:
            charges = 1  # Default fallback
        
        # Return data ready for unpacking
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
