"""Mixin for peptide match operations (CRUD and metrics)."""

import pandas as pd
from dasmixer.api.calculations.peptides.types import SearchMember, SearchSequence
from dasmixer.utils.exceptions import DasmixerException
from dasmixer.utils.logger import logger


class PeptideMixin:
    """
    Mixin providing peptide_match table management.

    Covers batch insertion, retrieval, and metric updates for peptide match
    records. Complex joined queries over spectre/identification/peptide_match
    live in :class:`JoinedPeptideDataMixin`.

    Requires ProjectBase functionality (_execute/_fetchall/_executemany).
    """

    # Peptide match operations
    
    async def clear_peptide_matches(self) -> None:
        """Clear all peptide matches (for re-mapping)."""
        await self._execute("DELETE FROM peptide_match")
        await self.save()
        logger.info("Cleared all peptide matches")
    
    async def add_peptide_matches_batch(self, matches_df: pd.DataFrame) -> None:
        """
        Add batch of peptide matches.

        Args:
            matches_df: DataFrame with columns:
                - protein_id: str
                - identification_id: int
                - matched_sequence: str
                - identity: float
                - matched_ppm: float | None
                - matched_theor_mass: float | None
                - unique_evidence: bool | None
                - matched_coverage_percent: float | None
                - matched_peaks: int | None
                - matched_top_peaks: int | None
                - matched_ion_type: str | None
                - matched_sequence_modified: str | None
                - substitution: bool
                - lcrr: float | None
                - unconfirmed_ptms: int | None
                - quality: float | None
                - fasta_start: int | None
                - correction: str | None  ('ilc' or 'denovo', None if not corrected)
        """
        rows_to_insert = []

        def _float(val):
            try:
                import math
                v = float(val)
                return None if math.isnan(v) else v
            except (TypeError, ValueError):
                return None

        def _int(val):
            try:
                import math
                v = float(val)
                if math.isnan(v):
                    return None
                return int(v)
            except (TypeError, ValueError):
                return None

        for _, row in matches_df.iterrows():
            rows_to_insert.append((
                row['protein_id'],
                int(row['identification_id']),
                row['matched_sequence'],
                float(row['identity']),
                _float(row.get('matched_ppm')),
                _float(row.get('matched_theor_mass')),
                1 if row.get('unique_evidence', False) else 0,
                _float(row.get('matched_coverage_percent')),
                _int(row.get('matched_peaks')),
                _int(row.get('matched_top_peaks')),
                row.get('matched_ion_type') or None,
                row.get('matched_sequence_modified') or None,
                1 if row.get('substitution', False) else 0,
                _float(row.get('lcrr')),
                _int(row.get('unconfirmed_ptms')),
                _float(row.get('quality')),
                _int(row.get('fasta_start')),
                row.get('correction') or None,
            ))

        if rows_to_insert:
            query = """INSERT INTO peptide_match
                   (protein_id, identification_id, matched_sequence, identity,
                    matched_ppm, matched_theor_mass, unique_evidence, matched_coverage_percent,
                    matched_peaks, matched_top_peaks, matched_ion_type,
                    matched_sequence_modified, substitution,
                    lcrr, unconfirmed_ptms, quality, fasta_start, correction)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
            # await self._executemany(
            #     query,
            #     rows_to_insert
            # )
            skipped = 0
            for r in rows_to_insert:
                try:
                    await self._execute(query, r)
                except Exception as e:
                    logger.debug("peptide_match insert failed: query=%s row=%s", query, r)
                    logger.exception(e)
                    skipped += 1
            # Note: No auto-save for batch efficiency
            logger.debug(f"Added {len(rows_to_insert)} peptide matches, skipped: {skipped}")
            if skipped > (len(rows_to_insert) / 2):
                raise DasmixerException("Too many bad proteins in data, check if library were loaded!")

    async def add_peptide_matches_batch_fast(self, matches_df: pd.DataFrame) -> None:
        """
        Fast bulk insert of peptide matches using a single executemany call.

        Identical column set to :meth:`add_peptide_matches_batch` (including
        lcrr, unconfirmed_ptms, quality, fasta_start, correction), but performs
        NO per-row fallback: every row is expected to reference an existing
        protein and identification. Callers must pre-filter unknown protein ids
        (foreign-key errors abort the whole batch).

        Does not call save() — the caller must save the project.
        """
        def _float(val):
            try:
                import math
                v = float(val)
                return None if math.isnan(v) else v
            except (TypeError, ValueError):
                return None

        def _int(val):
            try:
                import math
                v = float(val)
                if math.isnan(v):
                    return None
                return int(v)
            except (TypeError, ValueError):
                return None

        rows_to_insert = []
        for _, row in matches_df.iterrows():
            rows_to_insert.append((
                row['protein_id'],
                int(row['identification_id']),
                row['matched_sequence'],
                float(row['identity']),
                _float(row.get('matched_ppm')),
                _float(row.get('matched_theor_mass')),
                1 if row.get('unique_evidence', False) else 0,
                _float(row.get('matched_coverage_percent')),
                _int(row.get('matched_peaks')),
                _int(row.get('matched_top_peaks')),
                row.get('matched_ion_type') or None,
                row.get('matched_sequence_modified') or None,
                1 if row.get('substitution', False) else 0,
                _float(row.get('lcrr')),
                _int(row.get('unconfirmed_ptms')),
                _float(row.get('quality')),
                _int(row.get('fasta_start')),
                row.get('correction') or None,
            ))

        if rows_to_insert:
            query = """INSERT INTO peptide_match
                   (protein_id, identification_id, matched_sequence, identity,
                    matched_ppm, matched_theor_mass, unique_evidence, matched_coverage_percent,
                    matched_peaks, matched_top_peaks, matched_ion_type,
                    matched_sequence_modified, substitution,
                    lcrr, unconfirmed_ptms, quality, fasta_start, correction)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
            await self._executemany(query, rows_to_insert)
            logger.debug(f"Fast-inserted {len(rows_to_insert)} peptide matches")

    async def get_unique_sequences_for_search(
        self,
        tool_id: int,
        min_peptide_length: int,
        il_combinatorics: bool,
        sample_id: int | None = None,
        exclude_with_src_protein: bool = False,
    ) -> list[SearchSequence]:
        """
        Collect unique canonical sequences of a tool's identifications for
        the protein match search.

        Sequences are grouped by canonical sequence in SQL (all identification
        ids of a sequence are collected via group_concat). Post-processing:

        - Homopolymers (single distinct amino acid, e.g. GGGGGGGG) and
          empty/None sequences are skipped.
        - Length filter is applied in SQL with a floor of 4:
          ``length(canonical_sequence) >= max(min_peptide_length, 4)``.
        - With ``il_combinatorics`` enabled, isoleucine (I) is replaced by
          leucine (L) to build the search sequence; sequences that become
          identical after the I->L transformation are merged into a single
          :class:`SearchSequence` with several :class:`SearchMember` entries
          (each member keeps its original canonical sequence and its
          identification ids). Otherwise each canonical sequence maps to its
          own SearchSequence.
        - Search sequences are sorted and assigned contiguous indexes
          starting from 0 (the index equals the QueryId used in the query
          FASTA for npysearch).

        Args:
            tool_id: Tool whose identifications are searched.
            min_peptide_length: Minimum sequence length; values below 4 are
                raised to 4.
            il_combinatorics: Merge I/L sequences into single search queries.
            sample_id: If given, restrict to identifications of this sample
                (JOIN over spectre / spectre_file).
            exclude_with_src_protein: If True, exclude identifications that
                already carry a src_file_protein_id.

        Returns:
            List of :class:`SearchSequence`, ordered by search sequence with
            indexes 0..n-1; empty list when nothing matches.
        """
        min_len = max(int(min_peptide_length), 4)

        query_parts = [
            "SELECT i.canonical_sequence,",
            "group_concat(i.id) AS idlist",
            "FROM identification i",
        ]
        params: list = [int(tool_id), min_len]

        if sample_id is not None:
            query_parts.append(
                "JOIN spectre s ON s.id = i.spectre_id\n"
                "JOIN spectre_file sf ON sf.id = s.spectre_file_id"
            )

        query_parts.append(
            "WHERE i.tool_id = ?\n"
            "AND length(i.canonical_sequence) >= ?"
        )

        if sample_id is not None:
            query_parts.append("AND sf.sample_id = ?")
            params.append(int(sample_id))

        if exclude_with_src_protein:
            query_parts.append(
                "AND (i.src_file_protein_id IS NULL OR i.src_file_protein_id = '')"
            )

        query_parts.append(
            "GROUP BY i.canonical_sequence\n"
            "ORDER BY i.canonical_sequence"
        )

        query = " ".join(query_parts)
        rows = await self._fetchall(query, tuple(params))

        if not rows:
            return []

        grouped: dict[str, list[tuple[str, list[int]]]] = {}
        for row in rows:
            seq = row['canonical_sequence']
            if not seq or len(set(seq)) == 1:
                # Skip empty and homopolymer sequences (e.g. GGGGGGGG)
                continue
            search_seq = seq.replace('I', 'L') if il_combinatorics else seq
            idlist = row.get('idlist')
            ids = [int(x) for x in idlist.split(',') if x] if idlist else []
            grouped.setdefault(search_seq, []).append((seq, ids))

        result: list[SearchSequence] = []
        for idx, key in enumerate(sorted(grouped.keys())):
            members = grouped[key]
            result.append(SearchSequence(
                index=idx,
                search_sequence=key,
                members=[
                    SearchMember(canonical_sequence=s, ident_ids=ids)
                    for s, ids in members
                ],
            ))
        return result
    
    async def get_peptide_matches(
        self,
        protein_id: str | None = None,
        identification_id: int | None = None
    ) -> pd.DataFrame:
        """Get peptide matches as DataFrame."""
        query_parts = ["SELECT * FROM peptide_match"]
        
        conditions = []
        params = []
        
        if protein_id is not None:
            conditions.append("protein_id = ?")
            params.append(protein_id)
        
        if identification_id is not None:
            conditions.append("identification_id = ?")
            params.append(identification_id)
        
        if conditions:
            query_parts.append("WHERE " + " AND ".join(conditions))
        
        query_parts.append("ORDER BY id")
        
        query = " ".join(query_parts)
        rows = await self._fetchall(query, tuple(params) if params else None)
        
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    async def get_peptide_matches_with_spectra(self) -> list[dict]:
        """
        Fetch all peptide_match records joined with spectrum arrays and
        identification.override_charge.  Used by the protein metrics
        calculation pipeline.

        Returns:
            List of plain dicts (pickle-safe) with keys:
                id, matched_sequence, pepmass, override_charge,
                mz_array (list[float]), intensity_array (list[float])
        """
        from dasmixer.api.project.array_utils import decompress_array

        query = """
            SELECT
                pm.id,
                pm.matched_sequence,
                s.pepmass,
                s.mz_array,
                s.intensity_array,
                i.override_charge
            FROM peptide_match pm
            JOIN identification i ON pm.identification_id = i.id
            JOIN spectre s ON i.spectre_id = s.id
            ORDER BY pm.id
        """
        rows = await self._fetchall(query)
        result = []
        for row in rows:
            mz = decompress_array(row['mz_array']).tolist() if row['mz_array'] else []
            intensity = decompress_array(row['intensity_array']).tolist() if row['intensity_array'] else []
            result.append({
                'id': row['id'],
                'matched_sequence': row['matched_sequence'],
                'pepmass': row['pepmass'],
                'override_charge': row['override_charge'],
                'mz_array': mz,
                'intensity_array': intensity,
            })
        return result

    async def put_peptide_match_data_batch(self, data_rows: list[dict]) -> None:
        """
        Batch-update PPM and coverage metrics for peptide_match records.

        Keys recognised per dict:
            id, matched_ppm, matched_theor_mass, matched_coverage_percent
        """
        query = """
            UPDATE peptide_match
            SET
                matched_ppm = ?,
                matched_theor_mass = ?,
                matched_coverage_percent = ?
            WHERE id = ?
        """
        params = [
            (
                row.get('matched_ppm'),
                row.get('matched_theor_mass'),
                row.get('matched_coverage_percent'),
                row['id'],
            )
            for row in data_rows
        ]
        await self._executemany(query, params)

    async def update_peptide_match_metrics(
        self,
        match_id: int,
        matched_ppm: float | None = None,
        matched_coverage_percent: float | None = None
    ) -> None:
        """
        Update metrics for a peptide match.
        
        Args:
            match_id: Peptide match ID
            matched_ppm: PPM error for matched sequence
            matched_coverage_percent: Ion coverage for matched sequence
        """
        updates = []
        params = []
        
        if matched_ppm is not None:
            updates.append("matched_ppm = ?")
            params.append(float(matched_ppm))
        
        if matched_coverage_percent is not None:
            updates.append("matched_coverage_percent = ?")
            params.append(float(matched_coverage_percent))
        
        if not updates:
            return
        
        params.append(int(match_id))
        
        query = f"UPDATE peptide_match SET {', '.join(updates)} WHERE id = ?"
        await self._execute(query, tuple(params))
        # Note: No auto-save for batch efficiency

    async def clear_peptide_matches_for_sample(self, sample_id: int) -> None:
        """
        Delete peptide_match records for all identifications of a given sample.
        Used when re-running protein mapping for a single sample.
        """
        await self._execute("""
            DELETE FROM peptide_match WHERE identification_id IN (
                SELECT i.id FROM identification i
                JOIN spectre s ON i.spectre_id = s.id
                JOIN spectre_file sf ON s.spectre_file_id = sf.id
                WHERE sf.sample_id = ?
            )
        """, (int(sample_id),))
        await self.save()
        logger.debug(f"Cleared peptide matches for sample_id={sample_id}")
