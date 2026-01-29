# Dataclasses Documentation

## Overview

DASMixer uses Python dataclasses for structured data exchange between the Project class and application code. These classes provide type-safe, validated data structures for core entities.

---

## Location

All dataclasses are defined in `api/project/dataclasses.py`

---

## Available Dataclasses

1. [Subset](#subset) - Comparison groups
2. [Tool](#tool) - Identification tools
3. [Sample](#sample) - Experimental samples
4. [Protein](#protein) - Protein entries

---

## Subset

Represents a comparison group for differential analysis.

### Definition

```python
@dataclass
class Subset:
    """Comparison group/subset."""
    
    id: int | None = None
    name: str = ""
    details: str | None = None
    display_color: str | None = None
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | int \| None | None | Database ID (auto-assigned) |
| `name` | str | "" | Unique subset name |
| `details` | str \| None | None | Optional description |
| `display_color` | str \| None | None | Hex color for visualization (e.g., "#FF0000") |

### Methods

#### to_dict()

Convert to dictionary for database operations.

```python
def to_dict(self) -> dict[str, Any]
```

**Returns:** Dictionary with all fields

**Example:**
```python
subset = Subset(id=1, name="Control", display_color="#3498db")
data = subset.to_dict()
# {'id': 1, 'name': 'Control', 'details': None, 'display_color': '#3498db'}
```

#### from_dict()

Create Subset instance from database row.

```python
@classmethod
def from_dict(cls, data: dict[str, Any]) -> 'Subset'
```

**Parameters:**
- `data`: Dictionary from database query

**Returns:** Subset instance

**Example:**
```python
row = {'id': 1, 'name': 'Control', 'details': 'Control group', 'display_color': '#3498db'}
subset = Subset.from_dict(row)
print(subset.name)  # "Control"
```

### Usage Examples

```python
from api.project.dataclasses import Subset

# Create new subset
subset = Subset(
    name="Treatment",
    details="Treatment group with compound X",
    display_color="#e74c3c"
)

# Modify subset
subset.details = "Updated description"

# Convert for database
data = subset.to_dict()

# Create from database row
db_row = {'id': 1, 'name': 'Control', 'details': None, 'display_color': '#3498db'}
subset = Subset.from_dict(db_row)
```

---

## Tool

Represents an identification tool (library search or de novo sequencing).

### Definition

```python
@dataclass
class Tool:
    """Identification tool (library or de novo)."""
    
    id: int | None = None
    name: str = ""
    type: str = "library"  # "library", "denovo", etc.
    settings: dict | None = None
    display_color: str | None = None
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | int \| None | None | Database ID (auto-assigned) |
| `name` | str | "" | Unique tool name |
| `type` | str | "library" | Tool type: "library" or "denovo" |
| `settings` | dict \| None | None | Tool-specific settings |
| `display_color` | str \| None | None | Hex color for visualization |

### Methods

#### to_dict()

Convert to dictionary for database operations. Automatically serializes `settings` dict to JSON string.

```python
def to_dict(self) -> dict[str, Any]
```

**Example:**
```python
tool = Tool(
    name="PLGS",
    type="library",
    settings={"version": "3.0.2", "fdr": 0.01}
)
data = tool.to_dict()
# settings is JSON string: '{"version": "3.0.2", "fdr": 0.01}'
```

#### from_dict()

Create Tool instance from database row. Automatically deserializes JSON settings.

```python
@classmethod
def from_dict(cls, data: dict[str, Any]) -> 'Tool'
```

**Example:**
```python
row = {
    'id': 1,
    'name': 'PLGS',
    'type': 'library',
    'settings': '{"version": "3.0.2"}',  # JSON string
    'display_color': '#0000FF'
}
tool = Tool.from_dict(row)
print(tool.settings)  # {'version': '3.0.2'} - dict
```

### Usage Examples

```python
from api.project.dataclasses import Tool

# Library search tool
plgs = Tool(
    name="PLGS",
    type="library",
    settings={
        "version": "3.0.2",
        "fdr": 0.01,
        "database": "SwissProt"
    },
    display_color="#2ecc71"
)

# De novo sequencing tool
powernovo = Tool(
    name="PowerNovo2",
    type="denovo",
    settings={
        "model": "HCD",
        "beam_size": 5,
        "min_score": 80.0
    },
    display_color="#9b59b6"
)

# Access settings
fdr = plgs.settings["fdr"]  # 0.01

# Update settings
plgs.settings["min_peptide_length"] = 6
```

---

## Sample

Represents an experimental sample with associated metadata.

### Definition

```python
@dataclass
class Sample:
    """Sample with associated spectra files."""
    
    id: int | None = None
    name: str = ""
    subset_id: int | None = None
    additions: dict | None = None
    
    # Computed fields (not stored in DB)
    subset_name: str | None = field(default=None, repr=False)
    spectra_files_count: int = field(default=0, repr=False)
```

### Fields

#### Database Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | int \| None | None | Database ID (auto-assigned) |
| `name` | str | "" | Unique sample name |
| `subset_id` | int \| None | None | FK to subset (comparison group) |
| `additions` | dict \| None | None | Additional metadata (albumin, age, etc.) |

#### Computed Fields

These fields are populated when loading from database but not stored:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `subset_name` | str \| None | None | Name of associated subset |
| `spectra_files_count` | int | 0 | Number of associated spectra files |

### Methods

#### to_dict()

Convert to dictionary for database operations. Only includes database fields.

```python
def to_dict(self) -> dict[str, Any]
```

**Example:**
```python
sample = Sample(
    name="Patient_001",
    subset_id=1,
    additions={"albumin": 45.5, "age": 35}
)
data = sample.to_dict()
# {'id': None, 'name': 'Patient_001', 'subset_id': 1, 'additions': '{"albumin": 45.5, "age": 35}'}
```

#### from_dict()

Create Sample instance from database row. Automatically deserializes JSON additions.

```python
@classmethod
def from_dict(cls, data: dict[str, Any]) -> 'Sample'
```

**Example:**
```python
row = {
    'id': 1,
    'name': 'Patient_001',
    'subset_id': 1,
    'additions': '{"albumin": 45.5}',
    'subset_name': 'Control',  # Computed field from JOIN
    'spectra_files_count': 3   # Computed field from COUNT
}
sample = Sample.from_dict(row)
print(sample.name)                  # "Patient_001"
print(sample.additions['albumin'])  # 45.5
print(sample.subset_name)           # "Control"
print(sample.spectra_files_count)   # 3
```

### Usage Examples

```python
from api.project.dataclasses import Sample

# Create sample with metadata
sample = Sample(
    name="Patient_001",
    subset_id=1,
    additions={
        "albumin": 45.5,
        "total_protein": 7.2,
        "age": 35,
        "gender": "M",
        "diagnosis": "Healthy"
    }
)

# Access metadata
albumin = sample.additions["albumin"]  # 45.5

# Update metadata
sample.additions["bmi"] = 24.5

# Create from database (with computed fields)
db_row = {
    'id': 1,
    'name': 'Patient_001',
    'subset_id': 1,
    'additions': '{"albumin": 45.5}',
    'subset_name': 'Control',
    'spectra_files_count': 3
}
sample = Sample.from_dict(db_row)

# Computed fields available
print(f"{sample.name} is in {sample.subset_name} with {sample.spectra_files_count} files")
```

---

## Protein

Represents a protein entry from UniProt or custom database.

### Definition

```python
@dataclass
class Protein:
    """Protein entry (Uniprot or custom)."""
    
    id: str = ""  # Uniprot ID or custom
    is_uniprot: bool = False
    fasta_name: str | None = None
    sequence: str | None = None
    gene: str | None = None
    
    # Enrichment data (loaded optionally)
    uniprot_data: dict | None = field(default=None, repr=False)
    protein_atlas_data: dict | None = field(default=None, repr=False)
```

### Fields

#### Database Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | str | "" | Protein ID (UniProt accession or custom) |
| `is_uniprot` | bool | False | True if from UniProt database |
| `fasta_name` | str \| None | None | FASTA header/name |
| `sequence` | str \| None | None | Amino acid sequence |
| `gene` | str \| None | None | Gene name |

#### Enrichment Fields

These fields are not stored in the main database table:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `uniprot_data` | dict \| None | None | Additional UniProt metadata |
| `protein_atlas_data` | dict \| None | None | Protein Atlas data |

### Methods

#### to_dict()

Convert to dictionary for database operations. Only includes database fields.

```python
def to_dict(self) -> dict[str, Any]
```

**Example:**
```python
protein = Protein(
    id="P12345",
    is_uniprot=True,
    gene="ALBU",
    sequence="MKWVTFISLLFLFSSAYS"
)
data = protein.to_dict()
# Enrichment fields not included
```

#### from_dict()

Create Protein instance from database row.

```python
@classmethod
def from_dict(cls, data: dict[str, Any]) -> 'Protein'
```

**Example:**
```python
row = {
    'id': 'P12345',
    'is_uniprot': 1,  # SQLite boolean
    'fasta_name': 'sp|P12345|ALBU_HUMAN',
    'sequence': 'MKWVTFISLLFLFSSAYS',
    'gene': 'ALB'
}
protein = Protein.from_dict(row)
print(protein.gene)  # "ALB"
```

### Usage Examples

```python
from api.project.dataclasses import Protein

# UniProt protein
albu = Protein(
    id="P02768",
    is_uniprot=True,
    fasta_name="sp|P02768|ALBU_HUMAN Serum albumin",
    sequence="MKWVTFISLLFLFSSAYSRGVFRRDTHKSEIAHRFKDLGEEHFKGLVLIAFSQY...",
    gene="ALB"
)

# Custom protein (from de novo without database match)
custom = Protein(
    id="CUSTOM_001",
    is_uniprot=False,
    fasta_name="Novel protein 1",
    sequence="MPEPTIDEKSEQUENCE"
)

# With enrichment data (loaded separately)
albu.uniprot_data = {
    "function": "Maintains oncotic pressure",
    "subcellular_location": "Secreted",
    "mass": 69367
}

albu.protein_atlas_data = {
    "tissue_specificity": "Blood",
    "expression_level": "High"
}

# Access data
if albu.is_uniprot:
    print(f"UniProt: {albu.id} - {albu.gene}")
    if albu.uniprot_data:
        print(f"Function: {albu.uniprot_data['function']}")
```

---

## Common Patterns

### Working with Project API

```python
from api import Project
from api.project.dataclasses import Subset, Tool, Sample, Protein

async def example():
    async with Project("my_project.dasmix") as project:
        # Create using dataclass
        subset = Subset(
            name="Control",
            display_color="#3498db"
        )
        
        # Add to project (returns updated dataclass with ID)
        subset = await project.add_subset(
            subset.name,
            subset.details,
            subset.display_color
        )
        
        print(f"Created subset with ID: {subset.id}")
        
        # Retrieve as dataclass
        retrieved = await project.get_subset(subset.id)
        print(f"Retrieved: {retrieved.name}")
        
        # Modify and update
        retrieved.details = "Updated description"
        await project.update_subset(retrieved)
        
        # List all (returns list of dataclasses)
        all_subsets = await project.get_subsets()
        for s in all_subsets:
            print(f"- {s.name}: {s.display_color}")
```

### Serialization for Storage

```python
import json
from api.project.dataclasses import Tool

# To JSON
tool = Tool(
    name="PLGS",
    type="library",
    settings={"version": "3.0.2"}
)

tool_dict = tool.to_dict()
tool_json = json.dumps(tool_dict)

# From JSON
loaded_dict = json.loads(tool_json)
loaded_tool = Tool.from_dict(loaded_dict)
```

### Validation

```python
from api.project.dataclasses import Sample

def validate_sample(sample: Sample) -> bool:
    """Validate sample data."""
    if not sample.name:
        return False
    
    if sample.additions:
        # Validate albumin range
        if 'albumin' in sample.additions:
            alb = sample.additions['albumin']
            if alb < 0 or alb > 100:
                return False
    
    return True

# Usage
sample = Sample(name="Test", additions={"albumin": 45.5})
if validate_sample(sample):
    print("Valid sample")
```

### Creating Helper Functions

```python
from api.project.dataclasses import Protein

def create_uniprot_protein(
    accession: str,
    gene: str,
    sequence: str
) -> Protein:
    """Helper to create UniProt protein."""
    return Protein(
        id=accession,
        is_uniprot=True,
        fasta_name=f"sp|{accession}|{gene}_HUMAN",
        gene=gene,
        sequence=sequence
    )

# Usage
albu = create_uniprot_protein(
    "P02768",
    "ALB",
    "MKWVTFISLLFLFSSAYS..."
)
```

---

## Type Hints and IDE Support

All dataclasses are fully typed for excellent IDE support:

```python
from api.project.dataclasses import Sample

# IDE will autocomplete fields
sample = Sample(
    name="Test",  # IDE knows this is str
    subset_id=1,   # IDE knows this is int | None
    additions={"key": "value"}  # IDE knows this is dict | None
)

# Type checking
if sample.additions:  # Type guard
    # IDE knows additions is dict here, not None
    value = sample.additions["key"]

# Computed fields
files_count: int = sample.spectra_files_count  # IDE knows type
```

---

## Best Practices

### 1. Use Type Guards

```python
def process_sample(sample: Sample) -> None:
    """Process sample with type safety."""
    # Type guard for optional field
    if sample.additions:
        albumin = sample.additions.get("albumin")
        if albumin is not None:
            print(f"Albumin: {albumin}")
    
    # Type guard for computed field
    if sample.subset_name:
        print(f"Subset: {sample.subset_name}")
```

### 2. Immutable After Creation

```python
# ✅ Good - modify in-place
sample.additions = {"new": "data"}
sample.name = "Updated_Name"

# ❌ Bad - creating new instance loses ID
sample = Sample(name="New_Name")  # Lost ID!
```

### 3. Use from_dict() for Database Data

```python
# ✅ Good - handles JSON deserialization
row = await project.execute_query("SELECT * FROM sample WHERE id = ?", (1,))
sample = Sample.from_dict(row[0])

# ❌ Bad - manual deserialization
sample = Sample(
    id=row[0]['id'],
    name=row[0]['name'],
    additions=json.loads(row[0]['additions'])  # Manual!
)
```

### 4. Validate Before Database Operations

```python
def validate_protein(protein: Protein) -> None:
    """Validate protein before saving."""
    if not protein.id:
        raise ValueError("Protein ID required")
    
    if protein.sequence:
        # Validate sequence characters
        valid_aa = set("ACDEFGHIKLMNPQRSTVWY")
        if not set(protein.sequence.upper()).issubset(valid_aa):
            raise ValueError("Invalid amino acid sequence")

# Usage
protein = Protein(id="P12345", sequence="MKWVT")
validate_protein(protein)
await project.add_protein(protein)
```

---

## See Also

- [Project API Documentation](PROJECT_API.md)
- [Base Classes Documentation](BASE_CLASSES.md)
- [Database Schema](../project/spec/DATABASE_SCHEMA.md)
