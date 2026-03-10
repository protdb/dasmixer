"""Mixin for peptide match operations and joined peptide queries."""

import pandas as pd

from utils.logger import logger


class PeptideMixin:
    """
    Mixin providing peptide match management and complex joined queries.
    
    Requires ProjectBase functionality and QueryMixin (execute_query_df).
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
        """
        rows_to_insert = []
        
        for _, row in matches_df.iterrows():
            rows_to_insert.append((
                row['protein_id'],
                int(row['identification_id']),
                row['matched_sequence'],
                float(row['identity']),
                float(row['matched_ppm']) if row.get('matched_ppm') is not None else None,
                float(row['matched_theor_mass']) if row.get('matched_theor_mass') is not None else None,
                1 if row.get('unique_evidence', False) else 0,
                float(row['matched_coverage_percent']) if row.get('matched_coverage_percent') is not None else None
            ))
        
        if rows_to_insert:
            await self._executemany(
                """INSERT INTO peptide_match 
                   (protein_id, identification_id, matched_sequence, identity,
                    matched_ppm, matched_theor_mass, unique_evidence, matched_coverage_percent)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                rows_to_insert
            )
            # Note: No auto-save for batch efficiency
            logger.debug(f"Added {len(rows_to_insert)} peptide matches")
    
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
        from api.project.array_utils import decompress_array

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
    
    # Complex joined peptide queries

    @staticmethod
    def _build_peptide_filter_conditions(
        is_preferred: bool | None = None,
        sequence_identified: bool | None = None,
        protein_identified: bool | None = None,
        sample: str | None = None,
        subset: str | None = None,
        sample_id: int | None = None,
        subset_id: int | None = None,
        sequence: str | None = None,
        canonical_sequence: str | None = None,
        matched_sequence: str | None = None,
        seq_no: int | None = None,
        scans: int | None = None,
        tool: str | None = None,
        tool_id: int | None = None,
        identification_id: int | None = None,
        max_ppm: float | None = None,
        min_score: float | None = None
    ) -> tuple[list[str], list]:
        """
        Build WHERE conditions and parameters for peptide queries.
        
        Returns:
            Tuple of (conditions list, parameters list)
        """
        conditions = []
        params = []
        
        if is_preferred is not None:
            conditions.append("id.is_preferred = ?")
            params.append(1 if is_preferred else 0)
        
        if sequence_identified is not None:
            if sequence_identified:
                conditions.append("id.sequence IS NOT NULL")
            else:
                conditions.append("id.sequence IS NULL")
        
        if protein_identified is not None:
            if protein_identified:
                conditions.append("mp.protein_id IS NOT NULL")
            else:
                conditions.append("mp.protein_id IS NULL")
        
        if sample is not None:
            conditions.append("sb.sample = ?")
            params.append(sample)
        
        if subset is not None:
            conditions.append("sb.subset = ?")
            params.append(subset)
        
        if sample_id is not None:
            conditions.append("sb.sample_id = ?")
            params.append(sample_id)
        
        if subset_id is not None:
            conditions.append("sb.subset_id = ?")
            params.append(subset_id)
        
        if sequence is not None:
            conditions.append("id.sequence LIKE ?")
            params.append(f"%{sequence}%")
        
        if canonical_sequence is not None:
            conditions.append("id.canonical_sequence LIKE ?")
            params.append(f"%{canonical_sequence}%")
        
        if matched_sequence is not None:
            conditions.append("mp.matched_sequence LIKE ?")
            params.append(f"%{matched_sequence}%")
        
        if seq_no is not None:
            conditions.append("s.seq_no = ?")
            params.append(seq_no)
        
        if scans is not None:
            conditions.append("s.scans = ?")
            params.append(scans)
        
        if tool is not None:
            conditions.append("id.tool = ?")
            params.append(tool)
        
        if tool_id is not None:
            conditions.append("id.tool_id = ?")
            params.append(tool_id)

        if identification_id is not None:
            conditions.append("id.identification_id = ?")
            params.append(identification_id)

        if max_ppm is not None:
            conditions.append("abs(id.ppm) <= ?")
            params.append(max_ppm)

        if min_score is not None:
            conditions.append("id.score >= ?")
            params.append(min_score)
        
        return conditions, params
    
    async def count_joined_peptide_data(
        self,
        is_preferred: bool | None = None,
        sequence_identified: bool | None = None,
        protein_identified: bool | None = None,
        sample: str | None = None,
        subset: str | None = None,
        sample_id: int | None = None,
        subset_id: int | None = None,
        sequence: str | None = None,
        canonical_sequence: str | None = None,
        matched_sequence: str | None = None,
        identification_id: int | None = None,
        max_ppm: float | None = None,
        min_score: float | None = None,
        seq_no: int | None = None,
        scans: int | None = None,
        tool: str | None = None,
        tool_id: int | None = None
    ) -> int:
        """
        Count joined peptide data with optional filtering.
        
        Same filter parameters as get_joined_peptide_data.
        
        Returns:
            Total count of rows matching filters
        """
        # Base query - COUNT instead of SELECT columns
        query = """
            SELECT COUNT(*) as count
            FROM
                spectre AS s
            LEFT JOIN
                (SELECT 
                    sm.id AS sample_id, 
                    f.id AS spectre_file_id, 
                    sm.name AS sample, 
                    sb.name AS subset, 
                    sb.id AS subset_id 
                 FROM sample sm, subset sb, spectre_file f 
                 WHERE sm.subset_id = sb.id AND f.sample_id = sm.id) AS sb
                ON sb.spectre_file_id = s.spectre_file_id
            LEFT JOIN
                (SELECT 
                    i.spectre_id, 
                    t.name AS tool, 
                    t.id AS tool_id, 
                    i.id AS identification_id, 
                    i.sequence, 
                    i.canonical_sequence, 
                    i.ppm,
                    i.score,
                    i.is_preferred 
                 FROM identification i, tool t 
                 WHERE t.id = i.tool_id) AS id 
                ON id.spectre_id = s.id
            LEFT JOIN
                (SELECT 
                    m.matched_sequence, 
                    m.matched_ppm, 
                    m.protein_id, 
                    m.identification_id, 
                    m.unique_evidence,
                    m.identity,
                    p.gene
                 FROM peptide_match m, protein p 
                 WHERE p.id = m.protein_id) AS mp 
                ON mp.identification_id = id.identification_id
            WHERE 1=1
        """
        
        # Build filter conditions
        conditions, params = self._build_peptide_filter_conditions(
            is_preferred=is_preferred,
            sequence_identified=sequence_identified,
            protein_identified=protein_identified,
            sample=sample,
            subset=subset,
            sample_id=sample_id,
            subset_id=subset_id,
            sequence=sequence,
            canonical_sequence=canonical_sequence,
            matched_sequence=matched_sequence,
            seq_no=seq_no,
            scans=scans,
            tool=tool,
            tool_id=tool_id,
            identification_id=identification_id,
            min_score=min_score,
            max_ppm=max_ppm
        )
        
        # Add conditions to query
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        # Execute query
        row = await self._fetchone(query, tuple(params) if params else None)
        return row['count'] if row else 0
    
    async def get_joined_peptide_data(
        self,
        is_preferred: bool | None = None,
        sequence_identified: bool | None = None,
        protein_identified: bool | None = None,
        sample: str | None = None,
        subset: str | None = None,
        sample_id: int | None = None,
        subset_id: int | None = None,
        sequence: str | None = None,
        canonical_sequence: str | None = None,
        matched_sequence: str | None = None,
        seq_no: int | None = None,
        scans: int | None = None,
        tool: str | None = None,
        tool_id: int | None = None,
        identification_id: int | None = None,
        limit: int | None = None,
        offset: int = 0
    ) -> pd.DataFrame:
        """
        Get joined peptide data with optional filtering and pagination.
        
        Joins spectre, identification, and peptide_match tables with
        sample/subset/tool information. Applies filters via SQL WHERE clauses.
        
        Args:
            is_preferred: Filter by is_preferred = true
            sequence_identified: Filter by sequence IS NOT NULL
            protein_identified: Filter by protein_id IS NOT NULL
            sample: Filter by sample name (exact match)
            subset: Filter by subset name (exact match)
            sample_id: Filter by sample ID
            subset_id: Filter by subset ID
            sequence: Filter by sequence (LIKE %value%)
            canonical_sequence: Filter by canonical_sequence (LIKE %value%)
            matched_sequence: Filter by matched_sequence (LIKE %value%)
            seq_no: Filter by spectrum sequence number (exact)
            scans: Filter by scans value (exact)
            tool: Filter by tool name (exact match)
            tool_id: Filter by tool ID
            limit: Maximum rows to return (None = all rows)
            offset: Number of rows to skip (for pagination)
        
        Returns:
            DataFrame with columns:
                - sample, subset, sample_id, subset_id
                - seq_no, scans, charge, rt, pepmass, intensity
                - tool, tool_id, identification_id
                - sequence, canonical_sequence, ppm, is_preferred
                - matched_sequence, matched_ppm, protein_id, unique_evidence, gene
        """
        # Base query
        query = """
             SELECT
                sb.sample, sb.subset, sb.sample_id, sb.subset_id,
                s.id as spectre_id, s.seq_no, s.scans, s.charge, s.rt, s.pepmass, s.intensity,
                id.tool, id.tool_id, id.identification_id, id.sequence, 
                id.canonical_sequence, id.ppm, id.score, id.is_preferred,
				id.ions_matched, id.ion_match_type, id.top_peaks_covered,
				id.intensity_coverage,
                mp.matched_sequence, mp.matched_ppm, mp.protein_id, mp.identity,
                mp.unique_evidence, mp.gene
            FROM
                spectre AS s
            LEFT JOIN
                (SELECT 
                    sm.id AS sample_id, 
                    f.id AS spectre_file_id, 
                    sm.name AS sample, 
                    sb.name AS subset, 
                    sb.id AS subset_id 
                 FROM sample sm, subset sb, spectre_file f 
                 WHERE sm.subset_id = sb.id AND f.sample_id = sm.id) AS sb
                ON sb.spectre_file_id = s.spectre_file_id
            LEFT JOIN
                (SELECT 
                    i.spectre_id, 
                    t.name AS tool, 
                    t.id AS tool_id, 
                    i.id AS identification_id, 
                    i.sequence, 
                    i.canonical_sequence, 
                    i.ppm, 
                    i.score,
                    i.is_preferred, 
					i.intensity_coverage,
					i.ions_matched,
					i.ion_match_type,
					i.top_peaks_covered
                 FROM identification i, tool t 
                 WHERE t.id = i.tool_id) AS id 
                ON id.spectre_id = s.id
            LEFT JOIN
                (SELECT 
                    m.matched_sequence, 
                    m.matched_ppm, 
                    m.protein_id, 
                    m.identification_id, 
                    m.unique_evidence,
                    m.identity,
                    p.gene
                 FROM peptide_match m, protein p 
                 WHERE p.id = m.protein_id) AS mp 
                ON mp.identification_id = id.identification_id
            WHERE 1=1
        """
        
        # Build filter conditions
        conditions, params = self._build_peptide_filter_conditions(
            is_preferred=is_preferred,
            sequence_identified=sequence_identified,
            protein_identified=protein_identified,
            sample=sample,
            subset=subset,
            sample_id=sample_id,
            subset_id=subset_id,
            sequence=sequence,
            canonical_sequence=canonical_sequence,
            matched_sequence=matched_sequence,
            seq_no=seq_no,
            scans=scans,
            tool=tool,
            tool_id=tool_id,
            identification_id=identification_id
        )
        
        # Add conditions to query
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        # Add LIMIT/OFFSET if specified; limit=-1 means no pagination
        if limit is not None and limit != -1:
            query += " LIMIT ? OFFSET ?"
            params.append(limit)
            params.append(offset)

        # Execute query
        return await self.execute_query_df(query, tuple(params) if params else None)
