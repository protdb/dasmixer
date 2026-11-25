"""Parse npysearch CSV output into peptide_match row dicts (Stage 1) and Stage 2 candidates.

npysearch performs **LOCAL** alignment (not global), so ``Identity == 1.0`` in
the CSV does **not** imply that the whole query sequence was matched — it only
means the aligned segment is identical.  Full-query coverage must be checked
separately via ``NumMatches == qlen``, ``NumGaps == 0`` and
``NumMismatches == 0`` (Stage 1) or via effective identity
``NumMatches / qlen`` (Stage 2).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from dasmixer.api.calculations.peptides.types import Candidate, SearchSequence
from dasmixer.utils.logger import logger

BLAST_COLUMNS = [
    'QueryId', 'TargetId', 'QueryMatchStart', 'QueryMatchEnd',
    'TargetMatchStart', 'TargetMatchEnd', 'QueryMatchSeq', 'TargetMatchSeq',
    'NumColumns', 'NumMatches', 'NumMismatches', 'NumGaps', 'Identity', 'Alignment',
]


def read_blast_csv(path: Path) -> pd.DataFrame:
    """Read an npysearch result CSV into a DataFrame.

    If *path* does not exist or is empty, return an empty DataFrame with the
    expected :data:`BLAST_COLUMNS`.  If the file contains only a header (empty
    result from npysearch), pandas returns an empty frame which is returned
    as is.  The row count is logged at DEBUG level.

    Args:
        path: Path to the npysearch CSV file.

    Returns:
        DataFrame with ``dtype={'QueryId': int, 'TargetId': str}``.
    """
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        logger.debug("read_blast_csv: %s missing or empty -> 0 rows", path)
        return pd.DataFrame(columns=BLAST_COLUMNS)
    df = pd.read_csv(path, dtype={'QueryId': int, 'TargetId': str})
    logger.debug("read_blast_csv: %s -> %d rows", path, len(df))
    return df


def filter_full_coverage(
    df: pd.DataFrame,
    seqs: list[SearchSequence],
) -> pd.DataFrame:
    """Return only rows where the whole query is aligned.

    A row passes when ``NumMatches == qlen`` (where ``qlen`` is the length of
    the search sequence for the row's ``QueryId``), ``NumGaps == 0`` and
    ``NumMismatches == 0``.  Rows with an unknown ``QueryId`` are dropped.

    Args:
        df: Raw BLAST result DataFrame.
        seqs: Search sequences (provides ``QueryId`` → ``qlen`` mapping).

    Returns:
        Filtered copy with integer ``QueryId``.
    """
    qlen: dict[int, int] = {s.index: len(s.search_sequence) for s in seqs}
    df = df.copy()
    df['QueryId'] = df['QueryId'].astype(int)
    df['_qlen'] = df['QueryId'].map(qlen)
    df = df[df['_qlen'].notna()].copy()
    df['_qlen'] = df['_qlen'].astype(int)
    mask = (
        (df['NumMatches'] == df['_qlen'])
        & (df['NumGaps'] == 0)
        & (df['NumMismatches'] == 0)
    )
    result = df[mask].drop(columns=['_qlen']).copy()
    result['QueryId'] = result['QueryId'].astype(int)
    return result


def build_stage1_rows(
    df: pd.DataFrame,
    seqs: list[SearchSequence],
    proteins: dict[str, str],
    ilc: bool,
) -> tuple[list[dict], set[int]]:
    """Build ``peptide_match`` row dicts from full-coverage BLAST hits (Stage 1).

    *df* must already be filtered by :func:`filter_full_coverage`.

    For each BLAST row, the matched subsequence is taken from the **original**
    protein (not ``TargetMatchSeq``, which may contain ``L`` in place of ``I``
    in I/L-combinatorics mode).  The ``correction`` field is set to ``'ilc'``
    **per member** when I/L substitution was actually needed (i.e., the protein
    subsequence differs from the member's ``canonical_sequence``), otherwise
    ``None``.

    Rows are deduplicated by ``(identification_id, protein_id, fasta_start)``.
    ``unique_evidence`` is set to ``1`` per ``identification_id`` when exactly
    one distinct ``protein_id`` remains, otherwise ``0``.

    Args:
        df: Full-coverage BLAST hits.
        seqs: Search sequences (provides ``QueryId`` → members mapping).
        proteins: Mapping ``protein_id`` → protein sequence.
        ilc: Whether I/L combinatorics is active (controls ``correction``).

    Returns:
        Tuple ``(rows, found_indexes)`` — the list of row dicts and the set of
        ``SearchSequence`` indexes that produced at least one row.
    """
    seq_by_index: dict[int, SearchSequence] = {s.index: s for s in seqs}
    rows: list[dict] = []
    found_indexes: set[int] = set()

    for _, row in df.iterrows():
        index = int(row['QueryId'])
        seq = seq_by_index.get(index)
        if seq is None:
            continue
        qlen = len(seq.search_sequence)
        protein_id = str(row['TargetId'])
        if protein_id not in proteins:
            continue
        start = int(row['TargetMatchStart'])
        protein_seq = proteins[protein_id]
        matched = protein_seq[start - 1 : start - 1 + qlen]
        if len(matched) < qlen:
            logger.debug(
                "build_stage1_rows: protein %s too short for query %d "
                "(start=%d, qlen=%d, got len=%d)",
                protein_id, index, start, qlen, len(matched),
            )
            continue
        for member in seq.members:
            correction = 'ilc' if (ilc and matched != member.canonical_sequence) else None
            for ident_id in member.ident_ids:
                rows.append({
                    'protein_id': protein_id,
                    'identification_id': ident_id,
                    'matched_sequence': matched,
                    'identity': 1.0,
                    'unique_evidence': None,
                    'matched_ppm': None,
                    'matched_theor_mass': None,
                    'matched_coverage_percent': None,
                    'matched_peaks': None,
                    'matched_top_peaks': None,
                    'matched_ion_type': None,
                    'matched_sequence_modified': None,
                    'substitution': False,
                    'lcrr': None,
                    'unconfirmed_ptms': None,
                    'quality': None,
                    'fasta_start': start,
                    'correction': correction,
                })
        found_indexes.add(index)

    # Deduplicate by (identification_id, protein_id, fasta_start)
    seen: set[tuple[int, str, int]] = set()
    deduped: list[dict] = []
    for r in rows:
        key = (r['identification_id'], r['protein_id'], r['fasta_start'])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    rows = deduped

    # unique_evidence: per identification_id, 1 if exactly one distinct protein_id, else 0
    ident_proteins: dict[int, set[str]] = {}
    for r in rows:
        ident_proteins.setdefault(r['identification_id'], set()).add(r['protein_id'])
    for r in rows:
        r['unique_evidence'] = 1 if len(ident_proteins[r['identification_id']]) == 1 else 0

    return rows, found_indexes


def filter_stage2_hits(
    df: pd.DataFrame,
    seqs: list[SearchSequence],
    min_identity: float,
) -> pd.DataFrame:
    """Filter Stage 2 BLAST hits by effective identity.

    Effective identity is ``NumMatches / qlen`` (not the ``Identity`` column
    from the CSV, which reflects only the aligned segment).  Keeps rows with
    ``min_identity <= eff_identity < 1.0``.

    Per ``(QueryId, TargetId)`` the row with the maximum ``eff_identity`` is
    kept (tie-break: minimum ``NumGaps``).  Per ``QueryId`` only rows with the
    maximum ``eff_identity`` are kept.

    Args:
        df: Raw Stage 2 BLAST result DataFrame.
        seqs: Search sequences (provides ``QueryId`` → ``qlen`` mapping).
        min_identity: Minimum effective identity threshold.

    Returns:
        Filtered copy with columns including at least ``QueryId``, ``TargetId``,
        ``TargetMatchStart``, ``TargetMatchSeq``, ``QueryMatchSeq``, ``eff_identity``.
    """
    qlen: dict[int, int] = {s.index: len(s.search_sequence) for s in seqs}
    df = df.copy()
    df['QueryId'] = df['QueryId'].astype(int)
    df['_qlen'] = df['QueryId'].map(qlen)
    df = df[df['_qlen'].notna()].copy()
    df['_qlen'] = df['_qlen'].astype(int)
    df['eff_identity'] = df['NumMatches'] / df['_qlen']
    df = df[(df['eff_identity'] >= min_identity) & (df['eff_identity'] < 1.0)]
    # Per (QueryId, TargetId) keep max eff_identity, tie-break min NumGaps
    df = df.sort_values(
        ['QueryId', 'TargetId', 'eff_identity', 'NumGaps'],
        ascending=[True, True, False, True],
    ).drop_duplicates(['QueryId', 'TargetId'])
    # Per QueryId keep only rows with the maximum eff_identity
    max_eff = df.groupby('QueryId')['eff_identity'].transform('max')
    df = df[df['eff_identity'] == max_eff]
    result = df.drop(columns=['_qlen']).copy()
    result['QueryId'] = result['QueryId'].astype(int)
    return result


def build_stage2_candidates(
    df: pd.DataFrame,
    seqs: list[SearchSequence],
) -> tuple[list[Candidate], dict[int, int]]:
    """Build Stage 2 :class:`Candidate` objects from filtered BLAST hits.

    For each BLAST row and each member/``ident_id`` of the corresponding
    :class:`SearchSequence`, a :class:`Candidate` is produced.

    Args:
        df: Stage 2 BLAST hits filtered by :func:`filter_stage2_hits`.
        seqs: Search sequences (provides ``QueryId`` → members mapping).

    Returns:
        Tuple ``(candidates, unique_evidence)`` where
        ``unique_evidence[ident_id]`` is ``1`` if exactly one distinct
        ``protein_id`` remains for that ``ident_id`` across all candidates,
        otherwise ``0``.  The dict contains every ``ident_id`` seen.
    """
    seq_by_index: dict[int, SearchSequence] = {s.index: s for s in seqs}
    candidates: list[Candidate] = []
    ident_proteins: dict[int, set[str]] = {}

    for _, row in df.iterrows():
        index = int(row['QueryId'])
        seq = seq_by_index.get(index)
        if seq is None:
            continue
        protein_id = str(row['TargetId'])
        fasta_start = int(row['TargetMatchStart'])
        target_match_seq = str(row['TargetMatchSeq'])
        query_match_seq = str(row['QueryMatchSeq'])
        eff_identity = float(row['eff_identity'])
        for member in seq.members:
            for ident_id in member.ident_ids:
                candidates.append(Candidate(
                    index=index,
                    ident_id=ident_id,
                    protein_id=protein_id,
                    fasta_start=fasta_start,
                    target_match_seq=target_match_seq,
                    query_match_seq=query_match_seq,
                    eff_identity=eff_identity,
                ))
                ident_proteins.setdefault(ident_id, set()).add(protein_id)

    unique_evidence: dict[int, int] = {}
    for ident_id, protein_set in ident_proteins.items():
        unique_evidence[ident_id] = 1 if len(protein_set) == 1 else 0

    return candidates, unique_evidence