# Spectra Processing API Documentation

## Overview

DASMixer provides tools for analyzing and validating peptide identifications by matching theoretical fragment ions to experimental MS/MS spectra. This includes ion matching, coverage calculation, and visualization.

## Modules

- **`api/spectra/ion_match.py`** - Ion matching and coverage calculation
- **`api/spectra/plot_matches.py`** - Spectrum visualization with annotations

---

## Ion Matching (`api/spectra/ion_match.py`)

### Overview

The ion matching module uses `peptacular` library to:
1. Generate theoretical fragment ions from peptide sequence
2. Match experimental peaks to theoretical fragments
3. Calculate sequence coverage statistics

### IonMatchParameters

Configuration for ion matching.

```python
@dataclass
class IonMatchParameters:
    ions: list[Literal['a', 'b', 'c', 'x', 'y', 'z']] | None = None
    tolerance: float = 0.05  # Th
    mode: Literal['all', 'closest', 'largest'] = 'largest'
    water_loss: bool = True
    ammonia_loss: bool = True
```

**Attributes:**

- **`ions`**: List of ion types to generate and match
  - Default: `['b', 'y']` if None
  - Supported: `'a'`, `'b'`, `'c'` (N-terminal), `'x'`, `'y'`, `'z'` (C-terminal)

- **`tolerance`**: M/Z tolerance in Thomsons (Th)
  - Default: 0.05 Th
  - Typical values: 0.01-0.1 Th depending on instrument

- **`mode`**: Match selection strategy
  - `'all'`: Return all matches within tolerance
  - `'closest'`: Return closest match for each theoretical ion
  - `'largest'`: Return highest intensity match for each theoretical ion (default)

- **`water_loss`**: Include H₂O loss (-18.01056 Da)
  - Generates additional fragments with water loss

- **`ammonia_loss`**: Include NH₃ loss (-17.02655 Da)
  - Generates additional fragments with ammonia loss

**Example:**
```python
from api.spectra.ion_match import IonMatchParameters

# Standard b/y matching with 0.05 Th tolerance
params = IonMatchParameters(
    ions=['b', 'y'],
    tolerance=0.05,
    mode='largest'
)

# High-resolution matching with a/x ions
params_hr = IonMatchParameters(
    ions=['a', 'x'],
    tolerance=0.01,
    mode='closest',
    water_loss=False,
    ammonia_loss=False
)
```

---

### MatchResult

Result of ion matching operation.

```python
@dataclass
class MatchResult:
    parameters: IonMatchParameters
    fragments: list[Fragment]
    fragment_matches: list[FragmentMatch]
    intensity_percent: float
```

**Attributes:**

- **`parameters`**: Parameters used for matching
- **`fragments`**: All theoretical fragments generated
- **`fragment_matches`**: Experimental peaks matched to theoretical fragments
- **`intensity_percent`**: Percentage of total experimental intensity matched (0-100)

**Example:**
```python
result = match_predictions(params, mz, intensity, 2, "PEPTIDE")

print(f"Total fragments generated: {len(result.fragments)}")
print(f"Matched fragments: {len(result.fragment_matches)}")
print(f"Intensity coverage: {result.intensity_percent:.1f}%")

# Analyze matches
for match in result.fragment_matches:
    print(f"{match.fragment.ion_type}{match.fragment.end - match.fragment.start}: "
          f"theo={match.fragment.mz:.4f}, exp={match.mz:.4f}")
```

---

### match_predictions()

Main function for matching theoretical fragments to experimental spectrum.

```python
def match_predictions(
    params: IonMatchParameters,
    mz: list[float],
    intensity: list[float],
    charges: list[int] | int,
    sequence: str
) -> MatchResult
```

**Parameters:**

- **`params`**: Ion matching parameters
- **`mz`**: List of experimental m/z values
- **`intensity`**: List of experimental intensities (same length as mz)
- **`charges`**: Charge state(s) for fragment calculation
  - Single int: all fragments at this charge
  - List of ints: generate fragments at each charge
- **`sequence`**: Peptide sequence in ProForma notation
  - Examples: `"PEPTIDE"`, `"PEP[+15.99]TIDE"`, `"PEPT[Phospho]IDE"`

**Returns:** `MatchResult` object

**Example:**
```python
from api.spectra.ion_match import IonMatchParameters, match_predictions

# Set up parameters
params = IonMatchParameters(ions=['b', 'y'], tolerance=0.05)

# Experimental data
mz = [147.11, 276.15, 405.19, 534.24]
intensity = [1000, 2000, 1500, 800]

# Match peptide PEPTIDE at charge +2
result = match_predictions(
    params=params,
    mz=mz,
    intensity=intensity,
    charges=2,
    sequence="PEPTIDE"
)

print(f"Coverage: {result.intensity_percent:.1f}%")
print(f"Matched {len(result.fragment_matches)} of {len(result.fragments)} ions")
```

**Multiple charges:**
```python
# Generate fragments at +1, +2, +3
result = match_predictions(
    params=params,
    mz=mz,
    intensity=intensity,
    charges=[1, 2, 3],
    sequence="PEPTIDE"
)
```

---

### get_matches_dataframe()

Convert match result to DataFrame for analysis and plotting.

```python
def get_matches_dataframe(
    match_result: MatchResult,
    mz: list[float],
    intensity: list[float]
) -> pd.DataFrame
```

**Parameters:**

- **`match_result`**: Result from `match_predictions()`
- **`mz`**: Experimental m/z values (must match what was used in matching)
- **`intensity`**: Experimental intensities (must match what was used)

**Returns:** DataFrame with columns:

| Column | Type | Description |
|--------|------|-------------|
| `mz` | float | Experimental m/z |
| `intensity` | float | Experimental intensity |
| `ion_type` | str \| None | Matched ion type (`'b'`, `'y'`, etc.) |
| `label` | str \| None | Formatted label (e.g., `'b5-H2O+2'`) |
| `frag_seq` | str \| None | Fragment sequence |
| `theor_mz` | float \| None | Theoretical m/z of matched fragment |

Rows without matches have `None` for match columns.

**Example:**
```python
from api.spectra.ion_match import match_predictions, get_matches_dataframe

result = match_predictions(params, mz, intensity, 2, "PEPTIDE")
df = get_matches_dataframe(result, mz, intensity)

print(df)
#         mz  intensity ion_type     label  frag_seq  theor_mz
# 0   147.11     1000.0        b    b1      P         147.1128
# 1   276.15     2000.0        y    y2      DE        276.1441
# 2   405.19     1500.0      None  None      None          NaN
# 3   534.24      800.0        b    b5      PEPTI     534.2400

# Filter for matched ions only
matched = df[df['ion_type'].notna()]
print(f"Matched peaks: {len(matched)}")

# Calculate match statistics
match_rate = len(matched) / len(df) * 100
print(f"Match rate: {match_rate:.1f}%")
```

**Label format:**

Labels follow the pattern: `{ion_type}{position}{loss}{charge}`

- `ion_type`: `a`, `b`, `c`, `x`, `y`, `z`
- `position`: Number of residues in fragment
- `loss`: Empty, `-H2O`, `-NH3`, or `+/-X.XX` for custom losses
- `charge`: `+2`, `+3`, etc. (omitted for +1)

Examples:
- `b5` - b-ion with 5 residues, charge +1
- `y3-H2O` - y-ion with 3 residues, water loss, charge +1
- `b7+2` - b-ion with 7 residues, charge +2
- `y4-NH3+2` - y-ion with 4 residues, ammonia loss, charge +2

---

## Visualization (`api/spectra/plot_matches.py`)

### Overview

Generate annotated spectrum plots with matched ions highlighted.

### get_ion_type_color()

Get standard color for ion type.

```python
def get_ion_type_color(ion_type: str) -> str
```

**Color scheme:**
- `'a'` → green
- `'b'` → blue
- `'c'` → cyan
- `'x'` → orange
- `'y'` → red
- `'z'` → purple
- Other → gray

---

### generate_spectrum_plot()

Create annotated spectrum plot.

```python
def generate_spectrum_plot(
    headers: str | list[str],
    data: pd.DataFrame | list[pd.DataFrame],
    font_size: int = 25
) -> go.Figure
```

**Parameters:**

- **`headers`**: Title(s) for subplot(s)
  - Single string for one plot
  - List of strings for multiple plots

- **`data`**: DataFrame(s) with spectrum data
  - Single DataFrame or list of DataFrames
  - Must have columns: `mz`, `intensity`, `ion_type`, `label`
  - Output from `get_matches_dataframe()` is perfect input

- **`font_size`**: Font size for axis labels (annotations are 0.6× this size)

**Returns:** Plotly `Figure` object

**Features:**
- Peaks colored by ion type
- Matched ions annotated with labels
- Multiple panels for comparison
- Interactive hover information
- Publication-quality output

**Example - Single spectrum:**
```python
from api.spectra.ion_match import match_predictions, get_matches_dataframe
from api.spectra.plot_matches import generate_spectrum_plot

# Match ions
params = IonMatchParameters(ions=['b', 'y'])
result = match_predictions(params, mz, intensity, 2, "PEPTIDE")

# Create DataFrame
df = get_matches_dataframe(result, mz, intensity)

# Generate plot
fig = generate_spectrum_plot(
    headers="PEPTIDE Identification",
    data=df,
    font_size=20
)

# Display or save
fig.show()
fig.write_image("spectrum.png", width=1200, height=600)
```

**Example - Compare multiple tools:**
```python
# Match with different parameters
result_by = match_predictions(params_by, mz, intensity, 2, "PEPTIDE")
result_ax = match_predictions(params_ax, mz, intensity, 2, "PEPTIDE")

# Create DataFrames
df_by = get_matches_dataframe(result_by, mz, intensity)
df_ax = get_matches_dataframe(result_ax, mz, intensity)

# Multi-panel plot
fig = generate_spectrum_plot(
    headers=["b/y ions", "a/x ions"],
    data=[df_by, df_ax],
    font_size=18
)

fig.show()
```

---

## Complete Workflow Example

### Validate Identification

```python
import asyncio
from api import Project
from api.spectra.ion_match import IonMatchParameters, match_predictions, get_matches_dataframe
from api.spectra.plot_matches import generate_spectrum_plot

async def validate_identification(
    project: Project,
    spectrum_id: int,
    sequence: str,
    charge: int
):
    """
    Validate peptide identification by matching ions.
    
    Args:
        project: Project instance
        spectrum_id: Database ID of spectrum
        sequence: Identified peptide sequence
        charge: Precursor charge
    
    Returns:
        dict with validation results
    """
    # Get full spectrum data
    spectrum = await project.get_spectrum_full(spectrum_id)
    
    # Set up matching parameters
    params = IonMatchParameters(
        ions=['b', 'y'],
        tolerance=0.05,
        mode='largest',
        water_loss=True,
        ammonia_loss=True
    )
    
    # Match ions
    result = match_predictions(
        params=params,
        mz=spectrum['mz_array'].tolist(),
        intensity=spectrum['intensity_array'].tolist(),
        charges=charge,
        sequence=sequence
    )
    
    # Create DataFrame for plotting
    df = get_matches_dataframe(
        result,
        spectrum['mz_array'].tolist(),
        spectrum['intensity_array'].tolist()
    )
    
    # Generate plot
    title = f"{sequence} | Charge: +{charge} | Coverage: {result.intensity_percent:.1f}%"
    fig = generate_spectrum_plot(title, df)
    
    # Return results
    return {
        'spectrum_id': spectrum_id,
        'sequence': sequence,
        'coverage_percent': result.intensity_percent,
        'matched_ions': len(result.fragment_matches),
        'total_ions': len(result.fragments),
        'dataframe': df,
        'figure': fig
    }

# Usage
async def main():
    async with Project("my_project.dasmix") as project:
        result = await validate_identification(
            project,
            spectrum_id=123,
            sequence="PEPTIDEK",
            charge=2
        )
        
        print(f"Coverage: {result['coverage_percent']:.1f}%")
        print(f"Matched: {result['matched_ions']}/{result['total_ions']} ions")
        
        # Show plot
        result['figure'].show()
        
        # Or save
        result['figure'].write_image("validation.png")

asyncio.run(main())
```

---

### Batch Validation

```python
async def batch_validate(project: Project, sample_id: int, min_coverage: float = 30.0):
    """
    Validate all identifications in a sample.
    
    Args:
        project: Project instance
        sample_id: Sample to validate
        min_coverage: Minimum coverage threshold (%)
    
    Returns:
        DataFrame with validation results
    """
    # Get identifications
    idents = await project.get_identifications(sample_id=sample_id)
    
    results = []
    for _, ident in idents.iterrows():
        # Get spectrum
        spectrum = await project.get_spectrum_full(ident['spectre_id'])
        
        # Match ions
        params = IonMatchParameters(ions=['b', 'y'], tolerance=0.05)
        match_result = match_predictions(
            params,
            spectrum['mz_array'].tolist(),
            spectrum['intensity_array'].tolist(),
            ident['charge'] or 2,
            ident['sequence']
        )
        
        results.append({
            'identification_id': ident['id'],
            'sequence': ident['sequence'],
            'coverage': match_result.intensity_percent,
            'matched_ions': len(match_result.fragment_matches),
            'passed': match_result.intensity_percent >= min_coverage
        })
    
    results_df = pd.DataFrame(results)
    
    # Summary statistics
    print(f"Total identifications: {len(results_df)}")
    print(f"Passed ({min_coverage}% threshold): {results_df['passed'].sum()}")
    print(f"Failed: {(~results_df['passed']).sum()}")
    print(f"Average coverage: {results_df['coverage'].mean():.1f}%")
    
    return results_df

# Usage
async with Project("my_project.dasmix") as project:
    validation_results = await batch_validate(project, sample_id=1, min_coverage=30.0)
    
    # Save results
    validation_results.to_csv("validation_results.csv", index=False)
```

---

## Advanced Usage

### Custom Ion Types

```python
# Match only a/x ions
params_ax = IonMatchParameters(
    ions=['a', 'x'],
    tolerance=0.05,
    mode='largest'
)

# Match all ion types
params_all = IonMatchParameters(
    ions=['a', 'b', 'c', 'x', 'y', 'z'],
    tolerance=0.05,
    mode='all'
)
```

### High-Resolution Matching

```python
# Tight tolerance for high-resolution instruments
params_hr = IonMatchParameters(
    ions=['b', 'y'],
    tolerance=0.01,  # 10 ppm equivalent for ~1000 m/z
    mode='closest',
    water_loss=True,
    ammonia_loss=True
)
```

### Coverage Optimization

```python
# Find best ion types for a peptide
ion_combinations = [
    ['b', 'y'],
    ['a', 'x'],
    ['c', 'z'],
    ['b', 'y', 'a'],
]

best_coverage = 0
best_ions = None

for ions in ion_combinations:
    params = IonMatchParameters(ions=ions, tolerance=0.05)
    result = match_predictions(params, mz, intensity, 2, sequence)
    
    if result.intensity_percent > best_coverage:
        best_coverage = result.intensity_percent
        best_ions = ions

print(f"Best ion types: {best_ions} with {best_coverage:.1f}% coverage")
```

---

## Performance Considerations

### Memory Efficiency

- Use batch processing for large datasets
- Don't store full spectra in memory unnecessarily
- Process and plot one spectrum at a time

### Computation Speed

- Ion matching is fast (~ms per spectrum)
- Plotting is slower (~100ms per spectrum)
- Batch validate without plotting for speed

### Optimization Tips

```python
# Fast: validate without plotting
result = match_predictions(params, mz, intensity, charge, sequence)
coverage = result.intensity_percent

# Slow: full validation with plot generation
df = get_matches_dataframe(result, mz, intensity)
fig = generate_spectrum_plot(title, df)
```

---

## See Also

- [Project API Documentation](PROJECT_API.md)
- [Data Importers](IMPORTERS.md)
- [Peptacular Documentation](https://github.com/pgarrett-scripps/peptacular)
- [Plotly Documentation](https://plotly.com/python/)
