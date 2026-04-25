# DASMixer API Documentation

Welcome to the DASMixer API documentation! This guide will help you understand and use the DASMixer Python API for proteomics data analysis.

---

## Quick Links

- **[Project API](PROJECT_API.md)** - Complete guide to the Project class
- **[Base Classes](BASE_CLASSES.md)** - Technical documentation for abstract classes
- **[Dataclasses](DATACLASSES.md)** - Data structures documentation
- **[Examples](../examples/)** - Code examples and tutorials

---

## What is DASMixer?

DASMixer (De novo Assisted Search Mixer) is a Python application for:
- Merging peptide identification data from multiple sources
- Integrating de novo sequencing with database search results
- Performing comprehensive comparative proteomic analysis
- Quantitative proteomics with label-free quantification

---

## Installation

### From PyPI (when available)

```bash
pip install dasmixer
```

### From Source

```bash
git clone git@github.com:protdb/dasmixer.git
cd dasmixer
poetry install
```

---

## Quick Start

### 1. Create a Project

```python
import asyncio
from api import Project

async def main():
    # Create or open a project
    async with Project("my_study.dasmix") as project:
        print("Project created!")
        
        # Get metadata
        metadata = await project.get_metadata()
        print(f"Version: {metadata['version']}")

asyncio.run(main())
```

### 2. Setup Project Structure

```python
async def setup_project():
    async with Project("proteomics_study.dasmix") as project:
        # Add comparison groups
        control = await project.add_subset("Control", color="#3498db")
        treatment = await project.add_subset("Treatment", color="#e74c3c")
        
        # Add identification tools
        plgs = await project.add_tool("PLGS", "library")
        denovo = await project.add_tool("PowerNovo2", "denovo")
        
        # Add samples
        sample1 = await project.add_sample(
            "Patient_001",
            subset_id=control.id,
            additions={"age": 35, "gender": "M"}
        )
        
        print(f"Setup complete: {len(await project.get_samples())} samples")

asyncio.run(setup_project())
```

### 3. Import Spectra Data

```python
import numpy as np
import pandas as pd

async def import_spectra():
    async with Project("my_study.dasmix") as project:
        # Get sample
        sample = await project.get_sample_by_name("Patient_001")
        
        # Add spectra file
        file_id = await project.add_spectra_file(
            sample.id,
            "MGF",
            "/data/patient_001.mgf"
        )
        
        # Prepare spectra data
        spectra_data = []
        for i in range(1000):
            spectra_data.append({
                'seq_no': i + 1,
                'title': f'Scan_{i+1}',
                'pepmass': 500.0 + i * 0.1,
                'rt': 10.0 + i * 0.5,
                'charge': 2,
                'mz_array': np.random.rand(100) * 1000,
                'intensity_array': np.random.rand(100) * 10000,
                'charge_array_common_value': 1
            })
        
        # Import in batch
        df = pd.DataFrame(spectra_data)
        await project.add_spectra_batch(file_id, df)
        
        print(f"Imported {len(df)} spectra")

asyncio.run(import_spectra())
```

### 4. Query Data

```python
async def query_data():
    async with Project("my_study.dasmix") as project:
        # Get all samples
        samples = await project.get_samples()
        
        for sample in samples:
            # Get spectra for each sample
            spectra = await project.get_spectra(sample_id=sample.id, limit=10)
            print(f"{sample.name}: {len(spectra)} spectra")
            
            # Get full spectrum with arrays
            if not spectra.empty:
                full_spectrum = await project.get_spectrum_full(spectra.iloc[0]['id'])
                print(f"  Peaks: {len(full_spectrum['mz_array'])}")

asyncio.run(query_data())
```

---

## Core Concepts

### Projects

A **Project** is a single SQLite file (.dasmix) containing:
- Spectra data (MS/MS spectra with m/z and intensity arrays)
- Identifications (peptide sequences from database search or de novo)
- Proteins (matched to peptide sequences)
- Metadata (samples, comparison groups, tools)
- Analysis results (quantification, statistics)

### Async/Await

All Project methods are asynchronous to prevent UI blocking:

```python
# ✅ Correct - use async/await
async def work_with_project():
    async with Project("file.dasmix") as project:
        await project.add_sample(...)

asyncio.run(work_with_project())

# ❌ Wrong - will not work
project = Project("file.dasmix")
project.add_sample(...)  # Missing 'await' - won't work!
```

### Context Managers

Always use context managers for automatic cleanup:

```python
# ✅ Recommended - automatic save and close
async with Project("file.dasmix") as project:
    await project.add_sample(...)
    # Auto-saves and closes

# ⚠️ Manual management - error-prone
project = Project("file.dasmix")
await project.initialize()
try:
    await project.add_sample(...)
finally:
    await project.close()  # Easy to forget!
```

### Batch Processing

Import large datasets efficiently using batch methods:

```python
# ✅ Efficient - batch insert
await project.add_spectra_batch(file_id, large_dataframe)

# ❌ Inefficient - row by row
for _, row in large_dataframe.iterrows():
    # Don't call add methods in a loop!
    pass
```

---

## Documentation Structure

### For Users

1. **[Project API](PROJECT_API.md)** - Start here!
   - Complete reference for Project class
   - All methods with examples
   - Common workflows
   - Best practices

2. **[Dataclasses](DATACLASSES.md)** - Data structures
   - Subset, Tool, Sample, Protein
   - Usage examples
   - Type information

### For Developers

3. **[Base Classes](BASE_CLASSES.md)** - Extending DASMixer
   - Implement custom importers
   - Create custom reports
   - Technical specifications
   - Examples and patterns

4. **Database Schema** - Low-level details
   - Table structures
   - Relationships
   - Indexing strategy

---

## Common Tasks

### Import MGF File

```python
from api.inputs.spectra import MGFParser  # Stage 2

async def import_mgf():
    async with Project("project.dasmix") as project:
        sample = await project.get_sample_by_name("Sample_01")
        file_id = await project.add_spectra_file(
            sample.id, "MGF", "data.mgf"
        )
        
        parser = MGFParser("data.mgf")
        async for batch in parser.parse_batch(batch_size=1000):
            await project.add_spectra_batch(file_id, batch)
```

### Export Data

```python
async def export_data():
    async with Project("project.dasmix") as project:
        # Get identifications as DataFrame
        idents = await project.get_identifications()
        
        # Export to Excel
        idents.to_excel("identifications.xlsx", index=False)
        
        # Or custom query
        custom_data = await project.execute_query_df("""
            SELECT s.name, COUNT(*) as spectra_count
            FROM sample s
            JOIN spectre_file sf ON s.id = sf.sample_id
            JOIN spectre sp ON sf.id = sp.spectre_file_id
            GROUP BY s.id
        """)
        
        custom_data.to_csv("summary.csv")
```

### Generate Report

```python
from api.reporting import VolcanoPlotReport  # Stage 4

async def generate_report():
    async with Project("project.dasmix") as project:
        report = VolcanoPlotReport()
        
        # Get parameters schema
        ParamsClass = report.get_parameters_schema()
        params = ParamsClass(
            subset_1=1,
            subset_2=2,
            fc_threshold=2.0,
            pvalue_threshold=0.05
        )
        
        # Generate
        data, figure = await report.generate(project, params)
        
        # Export
        if data is not None:
            await report.export_data(data, "volcano_data.xlsx")
        if figure is not None:
            await report.export_figure(figure, "volcano_plot.png")
```

---

## API Stability

### Stage 1 (Current) - ✅ Stable

- Project management
- Subset/Tool/Sample/Protein operations
- Spectra and identification storage
- Basic queries

### Stage 2-5 - 🚧 Under Development

- Specific importers (MGF, PLGS, etc.)
- Advanced analysis functions
- GUI components
- Report modules

The core Project API is stable and backward compatible. Extension APIs may change during development.

---

## Support and Contributing

### Getting Help

- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Email**: Contact maintainers

### Contributing

1. Fork the repository
2. Create feature branch
3. Follow existing code style
4. Add tests for new features
5. Submit pull request

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for details.

---

## Examples

### Complete Workflow

```python
import asyncio
import numpy as np
import pandas as pd
from api import Project

async def complete_workflow():
    """End-to-end example."""
    
    async with Project("complete_study.dasmix") as project:
        # 1. Setup structure
        print("Setting up project...")
        control = await project.add_subset("Control")
        treatment = await project.add_subset("Treatment")
        
        plgs = await project.add_tool("PLGS", "library")
        
        # 2. Add samples
        print("Adding samples...")
        samples_data = [
            ("Sample_01", control.id),
            ("Sample_02", control.id),
            ("Sample_03", treatment.id),
            ("Sample_04", treatment.id)
        ]
        
        for name, subset_id in samples_data:
            sample = await project.add_sample(name, subset_id)
            
            # Add spectra file
            file_id = await project.add_spectra_file(
                sample.id, "MGF", f"/data/{name}.mgf"
            )
            
            # Simulate spectra import
            spectra = []
            for i in range(100):
                spectra.append({
                    'seq_no': i + 1,
                    'title': f'Scan_{i+1}',
                    'pepmass': 500.0 + i,
                    'rt': 10.0 + i * 0.5,
                    'charge': 2,
                    'mz_array': np.random.rand(50) * 1000,
                    'intensity_array': np.random.rand(50) * 10000,
                    'charge_array_common_value': 1
                })
            
            await project.add_spectra_batch(file_id, pd.DataFrame(spectra))
        
        # 3. Query and analyze
        print("\nProject Statistics:")
        stats = await project.execute_query_df("""
            SELECT 
                sub.name as subset,
                COUNT(DISTINCT s.id) as samples,
                COUNT(DISTINCT sf.id) as files,
                COUNT(sp.id) as spectra
            FROM subset sub
            JOIN sample s ON sub.id = s.subset_id
            JOIN spectre_file sf ON s.id = sf.sample_id
            JOIN spectre sp ON sf.id = sp.spectre_file_id
            GROUP BY sub.id
        """)
        
        print(stats)
        
        # 4. Export
        stats.to_excel("project_statistics.xlsx")
        print("\nExported to project_statistics.xlsx")

asyncio.run(complete_workflow())
```

---

## Performance Tips

### 1. Use Batch Operations

```python
# ✅ Fast - batch insert
await project.add_spectra_batch(file_id, df)

# ❌ Slow - individual inserts
for _, row in df.iterrows():
    # Don't do this!
    pass
```

### 2. Limit Query Results

```python
# ✅ Efficient - paginated
for offset in range(0, total, 1000):
    batch = await project.get_spectra(limit=1000, offset=offset)
    process(batch)

# ❌ Memory intensive - load all
all_spectra = await project.get_spectra()  # Huge DataFrame!
```

### 3. Don't Load Arrays Unless Needed

```python
# ✅ Fast - metadata only
spectra_meta = await project.get_spectra(sample_id=1)

# ❌ Slow - loads and decompresses arrays
for id in spectrum_ids:
    full = await project.get_spectrum_full(id)  # Only if needed!
```

---

## Troubleshooting

### AsyncIO Errors

```python
# ❌ Error: "RuntimeError: Event loop is closed"
async def my_function():
    project = Project("file.dasmix")
    await project.initialize()

asyncio.run(my_function())
asyncio.run(my_function())  # Error on second call!

# ✅ Solution: Use new event loop or context manager
async def my_function():
    async with Project("file.dasmix") as project:
        # Work here
        pass

asyncio.run(my_function())  # Works multiple times
```

### Memory Issues

```python
# ❌ Memory problem with large files
async for batch in parser.parse_batch(batch_size=100000):  # Too large!
    await project.add_spectra_batch(file_id, batch)

# ✅ Solution: Smaller batches
async for batch in parser.parse_batch(batch_size=1000):  # Reasonable
    await project.add_spectra_batch(file_id, batch)
```

### Database Locked

```python
# ❌ Multiple simultaneous writes
task1 = asyncio.create_task(project.add_sample(...))
task2 = asyncio.create_task(project.add_sample(...))
await asyncio.gather(task1, task2)  # May cause lock!

# ✅ Solution: Sequential writes
await project.add_sample(...)
await project.add_sample(...)
```

---

## Next Steps

1. Read the **[Project API](PROJECT_API.md)** documentation
2. Try the **Quick Start** examples above
3. Explore **[Dataclasses](DATACLASSES.md)** for data structures
4. For extending: **[Base Classes](BASE_CLASSES.md)**

**Happy analyzing! 🧬🔬**
