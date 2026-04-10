"""Spectrum plotting functions with ion annotations."""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def get_ion_type_color(ion_type: str) -> str:
    """
    Get color for ion type.
    
    Args:
        ion_type: Ion type ('a', 'b', 'c', 'x', 'y', 'z')
        
    Returns:
        Color name or hex code
    """
    color_map = {
        'a': 'green',
        'b': 'blue',
        'c': 'cyan',
        'x': 'orange',
        'y': 'red',
        'z': 'purple'
    }
    return color_map.get(ion_type, 'gray')


def plot_ion_match(
    mz_array: np.ndarray,
    intensity_array: np.ndarray,
    sequence: str,
    charge: int | None = None,
    ion_types: list[str] | None = None,
    water_loss: bool = False,
    nh3_loss: bool = False,
    ppm_threshold: float = 20.0
) -> go.Figure:
    """
    Plot ion match visualization for a spectrum and sequence.
    
    This is a simplified function for UI display. For full functionality
    with actual ion matching, use the ion_match module.
    
    Args:
        mz_array: m/z values
        intensity_array: Intensity values
        sequence: Peptide sequence
        charge: Precursor charge (optional)
        ion_types: List of ion types to match (e.g., ['b', 'y'])
        water_loss: Include water loss ions
        nh3_loss: Include ammonia loss ions
        ppm_threshold: PPM threshold for matching
    
    Returns:
        Plotly Figure object
    
    TODO: Implement full ion matching logic
    - Generate theoretical fragments
    - Match peaks with PPM threshold
    - Annotate matched peaks
    
    For now, this creates a simple spectrum visualization.
    """
    # Create simple spectrum plot
    fig = go.Figure()
    
    # Add spectrum as bar chart
    fig.add_trace(go.Bar(
        x=mz_array,
        y=intensity_array,
        name='Spectrum',
        marker_color='lightgray',
        hovertemplate=(
            "m/z: %{x:.2f}<br>"
            "Intensity: %{y:.0f}"
            "<extra></extra>"
        )
    ))
    
    # Update layout
    charge_text = f" (charge: {charge})" if charge else ""
    fig.update_layout(
        title=f"Spectrum: {sequence}{charge_text}",
        xaxis_title="m/z",
        yaxis_title="Intensity",
        height=400,
        showlegend=False,
        hovermode='closest'
    )
    
    return fig


def generate_spectrum_plot(
    headers: str | list[str],
    data: pd.DataFrame | list[pd.DataFrame],
    font_size: int = 25
) -> go.Figure:
    """
    Generate spectrum plot with ion annotations.
    
    Creates multi-panel plot for comparing multiple spectra or showing
    different identification results for the same spectrum.
    
    Args:
        headers: Title(s) for subplot(s). Single string or list.
        data: DataFrame(s) with columns:
            - mz: float - m/z value
            - intensity: float - peak intensity
            - ion_type: str | None - matched ion type ('a', 'b', 'y', etc.)
            - label: str | None - annotation text (e.g., 'b5-H2O')
        font_size: Font size for axis labels and annotations
        
    Returns:
        Plotly Figure object with spectrum plot(s)
        
    Example:
        >>> import pandas as pd
        >>> df = pd.DataFrame({
        ...     'mz': [100.0, 200.0, 300.0],
        ...     'intensity': [1000, 2000, 500],
        ...     'ion_type': ['b', 'y', None],
        ...     'label': ['b1', 'y2', None]
        ... })
        >>> fig = generate_spectrum_plot("Sample Spectrum", df)
        >>> fig.show()
    """
    # Normalize inputs to lists
    if isinstance(headers, str):
        headers = [headers]
    if isinstance(data, pd.DataFrame):
        data = [data]
    
    num_plots = len(data)
    
    # Pad headers if needed
    if len(headers) < num_plots:
        headers = headers + [''] * (num_plots - len(headers))
    
    # Create subplots
    fig = make_subplots(
        rows=num_plots,
        cols=1,
        subplot_titles=headers,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[1.0 / num_plots] * num_plots
    )
    
    # Plot each spectrum
    for row_no, df, header in zip(range(1, num_plots + 1), data, headers):
        # Add bars for each peak
        for _, row in df.iterrows():
            # Determine color based on ion match
            if pd.notna(row.get('ion_type')):
                color = get_ion_type_color(row['ion_type'])
            else:
                color = 'lightgray'
            
            # Add bar trace
            fig.add_trace(
                go.Bar(
                    x=[row['mz']],
                    y=[row['intensity']],
                    marker=dict(
                        color='lightgray',
                        line=dict(color=color, width=2)
                    ),
                    showlegend=False,
                    hovertemplate=(
                        f"m/z: {row['mz']:.2f}<br>"
                        f"Intensity: {row['intensity']:.0f}"
                        "<extra></extra>"
                    )
                ),
                row=row_no,
                col=1
            )
        
        # Add annotations for matched ions
        matched_ions = df[df['ion_type'].notna()]
        for _, row in matched_ions.iterrows():
            fig.add_annotation(
                x=row['mz'],
                y=row['intensity'],
                text=row.get('label', ''),
                showarrow=False,
                yshift=10,
                font=dict(
                    color=get_ion_type_color(row['ion_type']),
                    size=font_size * 0.6  # Slightly smaller for annotations
                ),
                row=row_no,
                col=1
            )
    
    # Update axes
    fig.update_xaxes(
        title_text='m/z',
        row=num_plots,
        col=1,
        title_font=dict(size=font_size),
        tickfont=dict(size=font_size)
    )
    
    for i in range(1, num_plots + 1):
        fig.update_yaxes(
            title_text='Intensity',
            row=i,
            col=1,
            title_font=dict(size=font_size),
            tickfont=dict(size=font_size)
        )
    
    # Update layout
    fig.update_layout(
        showlegend=False,
        height=400 * num_plots,  # Scale height with number of plots
        hovermode='closest'
    )
    
    return fig
