"""Shared dataclasses for the protein match v2 pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SearchMember:
    """One original peptide sequence merged into a single search query."""

    canonical_sequence: str
    ident_ids: list[int]


@dataclass
class SearchSequence:
    """A unique sequence sent to npysearch (I/L-merged when enabled)."""

    index: int                  # equals QueryId in the query FASTA
    search_sequence: str        # canonical sequence after I->L transformation
    members: list[SearchMember] = field(default_factory=list)


@dataclass
class Candidate:
    """Stage 2 candidate: one (identification, protein) pair after filtering."""

    index: int                  # SearchSequence.index
    ident_id: int
    protein_id: str
    fasta_start: int            # 1-based position of the match in the protein
    target_match_seq: str
    query_match_seq: str
    eff_identity: float


@dataclass
class ProteinMapProgress:
    """Progress snapshot passed to the protein match callback."""

    tool_index: int             # 0-based
    tool_count: int
    stage: str                  # 'prepare' | 'simple' | 'save_simple' | 'correction' | 'processing'
    message: str
    fraction: float             # 0..1 over the whole run (all tools)
    processed: int | None = None
    total: int | None = None
