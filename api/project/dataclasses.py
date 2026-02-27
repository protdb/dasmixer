"""Dataclasses for external interface to project entities."""

from dataclasses import dataclass, field
import json
import pickle
import gzip
from typing import Any, Literal

# Import for type hints only
try:
    from uniprot_meta_tool import UniprotData
except ImportError:
    UniprotData = None


@dataclass
class Subset:
    """Comparison group/subset."""
    
    id: int | None = None
    name: str = ""
    details: str | None = None
    display_color: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database operations."""
        return {
            'id': self.id,
            'name': self.name,
            'details': self.details,
            'display_color': self.display_color
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Subset':
        """Create from database row."""
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            details=data.get('details'),
            display_color=data.get('display_color')
        )


@dataclass
class Tool:
    """Identification tool (library or de novo)."""
    
    id: int | None = None
    name: str = ""
    type: Literal['Library', 'De Novo'] = "Library"  # NEW: Type of tool
    parser: str = "library"  # RENAMED: Parser name (was 'type')
    settings: dict | None = None
    display_color: str | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database operations."""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'parser': self.parser,
            'settings': json.dumps(self.settings) if self.settings else None,
            'display_color': self.display_color
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Tool':
        """Create from database row."""
        settings = data.get('settings')
        if settings and isinstance(settings, str):
            settings = json.loads(settings)
        
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            type=data.get('type', 'Library'),
            parser=data.get('parser', 'library'),
            settings=settings,
            display_color=data.get('display_color')
        )


@dataclass
class Sample:
    """Sample with associated spectra files."""
    
    id: int | None = None
    name: str = ""
    subset_id: int | None = None
    additions: dict | None = None  # albumin, total_protein, etc.
    
    # Computed fields (not stored in DB, filled on load)
    subset_name: str | None = field(default=None, repr=False)
    spectra_files_count: int = field(default=0, repr=False)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database operations."""
        return {
            'id': self.id,
            'name': self.name,
            'subset_id': self.subset_id,
            'additions': json.dumps(self.additions) if self.additions else None
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Sample':
        """Create from database row."""
        additions = data.get('additions')
        if additions and isinstance(additions, str):
            additions = json.loads(additions)
        
        return cls(
            id=data.get('id'),
            name=data.get('name', ''),
            subset_id=data.get('subset_id'),
            additions=additions,
            subset_name=data.get('subset_name'),
            spectra_files_count=data.get('spectra_files_count', 0)
        )


@dataclass
class Protein:
    """Protein entry (Uniprot or custom)."""
    
    id: str = ""  # Uniprot ID or custom
    is_uniprot: bool = False
    fasta_name: str | None = None
    sequence: str | None = None
    gene: str | None = None
    name: str | None = None  # NEW: Short protein name
    uniprot_data: 'UniprotData | None' = field(default=None, repr=False)  # NEW: UniprotData object
    
    # Enrichment data (loaded optionally) - kept for future use
    protein_atlas_data: dict | None = field(default=None, repr=False)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database operations."""
        return {
            'id': self.id,
            'is_uniprot': self.is_uniprot,
            'fasta_name': self.fasta_name,
            'sequence': self.sequence,
            'gene': self.gene,
            'name': self.name
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Protein':
        """Create from database row."""
        return cls(
            id=data.get('id', ''),
            is_uniprot=bool(data.get('is_uniprot', False)),
            fasta_name=data.get('fasta_name'),
            sequence=data.get('sequence'),
            gene=data.get('gene'),
            name=data.get('name'),
            uniprot_data=None,  # Will be loaded separately if needed
            protein_atlas_data=None  # Not stored in main table
        )

@dataclass
class IdentificationWithSpectre:
