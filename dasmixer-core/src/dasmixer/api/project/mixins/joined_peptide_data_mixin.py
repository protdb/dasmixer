"""Mixin for joined peptide data queries (spectre + identification + peptide_match)."""

import pandas as pd
from dasmixer.utils.logger import logger


class JoinedPeptideDataMixin:
    """
    Mixin providing complex joined queries over peptide data.

    Joins the spectre, identification, and peptide_match tables together
    with sample/subset/tool metadata, and exposes filterable, paginated
    access to the resulting view.

    Requires ProjectBase functionality (_fetchone/_fetchall) and QueryMixin
    (execute_query_df).
    """

    @staticmethod
    def _build_peptide_filter_conditions(
        is_preferred: bool | None = None,
        spectre_id: int | None = None,
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
        min_score: float | None = None,
        protein_id: str | None = None,
        gene: str | None = None,
        min_quality: float | None = None,
        has_ptm: str | None = None,
        has_substitution: str | None = None,
        max_fdr: float | None = None,
    ) -> tuple[list[str], list]:
        """
        Build WHERE conditions and bound parameters for joined peptide queries.

        All arguments are optional; ``None`` (or any value other than ``'Yes'``/
        ``'No'`` for the ``has_ptm`` / ``has_substitution`` tri-state filters)
        means "no filter".

        Args:
            is_preferred: Keep only preferred (True) or non-preferred (False)
                identifications.
            spectre_id: Exact spectrum id (``spectre.id``).
            sequence_identified: Keep identifications with a non-null sequence
                (True) or null sequence (False).
            protein_identified: Keep matches with a mapped protein (True) or
                unmapped (False).
            sample: Sample name (exact match).
            subset: Subset name (exact match).
            sample_id: Sample id (exact match).
            subset_id: Subset id (exact match).
            sequence: Identification sequence substring (LIKE %value%).
            canonical_sequence: Canonical sequence substring (LIKE %value%).
            matched_sequence: ``peptide_match.matched_sequence`` substring
                (LIKE %value%).
            seq_no: Spectrum sequence number (exact match).
            scans: Spectrum scans value (exact match).
            tool: Tool name (exact match).
            tool_id: Tool id (exact match).
            identification_id: Identification id (exact match).
            max_ppm: Keep rows with ``|identification.ppm| <= value``.
            min_score: Keep rows with ``identification.score >= value``.
            protein_id: ``peptide_match.protein_id`` (exact match, e.g. UniProt
                accession).
            gene: ``protein.gene`` substring (LIKE %value%).
            min_quality: Keep rows with ``identification.quality >= value``
                (NULL quality is excluded).
            has_ptm: Tri-state ('Yes'/'No'/other = all). 'Yes' keeps
                ``has_ptm = 1``; 'No' keeps NULL or 0.
            has_substitution: Tri-state ('Yes'/'No'/other = all). 'Yes' keeps
                ``peptide_match.substitution = 1``; 'No' keeps 0.
            max_fdr: Keep rows with ``identification.fdr <= value``
                     (NULL fdr is excluded). When None, no FDR filter.

        Returns:
            Tuple ``(conditions, params)`` — list of SQL fragments (to be
            AND-joined) and the corresponding bound parameters.
        """
        conditions = []
        params = []

        if is_preferred is not None:
            conditions.append("i.is_preferred = ?")
            params.append(1 if is_preferred else 0)

        if spectre_id is not None:
            conditions.append("s.id = ?")
            params.append(spectre_id)

        if sequence_identified is not None:
            if sequence_identified:
                conditions.append("i.sequence IS NOT NULL")
            else:
                conditions.append("i.sequence IS NULL")

        if protein_identified is not None:
            if protein_identified:
                conditions.append("m.protein_id IS NOT NULL")
            else:
                conditions.append("m.protein_id IS NULL")

        if sample is not None:
            conditions.append("sm.name = ?")
            params.append(sample)

        if subset is not None:
            conditions.append("sb.name = ?")
            params.append(subset)

        if sample_id is not None:
            conditions.append("sm.id = ?")
            params.append(sample_id)

        if subset_id is not None:
            conditions.append("sb.id = ?")
            params.append(subset_id)

        if sequence is not None:
            conditions.append("i.sequence LIKE ?")
            params.append(f"%{sequence}%")

        if canonical_sequence is not None:
            conditions.append("i.canonical_sequence LIKE ?")
            params.append(f"%{canonical_sequence}%")

        if matched_sequence is not None:
            conditions.append("m.matched_sequence LIKE ?")
            params.append(f"%{matched_sequence}%")

        if seq_no is not None:
            conditions.append("s.seq_no = ?")
            params.append(seq_no)

        if scans is not None:
            conditions.append("s.scans = ?")
            params.append(scans)

        if tool is not None:
            conditions.append("t.name = ?")
            params.append(tool)

        if tool_id is not None:
            conditions.append("t.id = ?")
            params.append(tool_id)

        if identification_id is not None:
            conditions.append("i.id = ?")
            params.append(identification_id)

        if max_ppm is not None:
            conditions.append("abs(i.ppm) <= ?")
            params.append(max_ppm)

        if min_score is not None:
            conditions.append("i.score >= ?")
            params.append(min_score)

        if protein_id is not None:
            conditions.append('m.protein_id = ?')
            params.append(protein_id)

        if gene is not None:
            conditions.append("p.gene LIKE ?")
            params.append(f"%{gene}%")

        # Min Quality (NULL quality is treated as not meeting the threshold)
        mq = min_quality
        if mq is not None:
            conditions.append("(i.quality IS NOT NULL AND i.quality >= ?)")
            params.append(float(mq))

        # Has PTM (values: 'Yes' | 'No'; anything else → no filter)
        if has_ptm == 'Yes':
            conditions.append("i.has_ptm = 1")
        elif has_ptm == 'No':
            # no PTM = NULL (not computed) or 0
            conditions.append("(i.has_ptm IS NULL OR i.has_ptm = 0)")

        # Has AA Substitution (peptide_match.substitution)
        if has_substitution == 'Yes':
            conditions.append("m.substitution = 1")
        elif has_substitution == 'No':
            conditions.append("m.substitution = 0")

        # Max FDR (strict: NULL fdr rows are excluded when threshold is set)
        mf = max_fdr
        if mf is not None:
            conditions.append("(i.fdr IS NOT NULL AND i.fdr <= ?)")
            params.append(float(mf))

        return conditions, params

    async def count_joined_peptide_data(
        self,
        is_preferred: bool | None = None,
        spectre_id: int | None = None,
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
        tool_id: int | None = None,
        protein_id: str | None = None,
        gene: str | None = None,
        min_quality: float | None = None,
        has_ptm: str | None = None,
        has_substitution: str | None = None,
        max_fdr: float | None = None,
    ) -> int:
        """
        Count joined peptide data rows matching the given filters.

        Same filter parameters as :meth:`get_joined_peptide_data` (without
        ``limit``/``offset``).

        Returns:
            Total number of rows matching the filters.
        """
        query = """
            SELECT COUNT(*) as count
            FROM spectre AS s
            LEFT JOIN spectre_file f ON f.id = s.spectre_file_id
            LEFT JOIN sample sm ON sm.id = f.sample_id
            LEFT JOIN subset sb ON sb.id = sm.subset_id
            LEFT JOIN identification i ON i.spectre_id = s.id
            LEFT JOIN tool t ON t.id = i.tool_id
            LEFT JOIN peptide_match m ON m.identification_id = i.id
            LEFT JOIN protein p ON p.id = m.protein_id
            WHERE 1=1
        """

        conditions, params = self._build_peptide_filter_conditions(
            is_preferred=is_preferred,
            spectre_id=spectre_id,
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
            max_ppm=max_ppm,
            protein_id=protein_id,
            gene=gene,
            min_quality=min_quality,
            has_ptm=has_ptm,
            has_substitution=has_substitution,
            max_fdr=max_fdr,
        )

        if conditions:
            query += " AND " + " AND ".join(conditions)
        logger.debug(query)
        logger.debug(params)
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
        spectre_id: int | None = None,
        scans: int | None = None,
        tool: str | None = None,
        tool_id: int | None = None,
        identification_id: int | None = None,
        protein_id: str | None = None,
        gene: str | None = None,
        max_ppm: float | None = None,
        min_quality: float | None = None,
        has_ptm: str | None = None,
        has_substitution: str | None = None,
        max_fdr: float | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> pd.DataFrame:
        """
        Get joined peptide data with optional filtering and pagination.

        Joins spectre, identification, and peptide_match tables with
        sample/subset/tool information. Applies filters via SQL WHERE clauses.

        Args:
            is_preferred: Filter by ``identification.is_preferred`` flag.
            sequence_identified: Keep only rows where the identification
                sequence is present (True) or missing (False).
            protein_identified: Keep only rows where a protein is mapped
                (True) or not (False).
            sample: Filter by sample name (exact match).
            subset: Filter by subset name (exact match).
            sample_id: Filter by sample id (exact match).
            subset_id: Filter by subset id (exact match).
            sequence: Filter by ``identification.sequence`` (LIKE %value%).
            canonical_sequence: Filter by ``identification.canonical_sequence``
                (LIKE %value%).
            matched_sequence: Filter by ``peptide_match.matched_sequence``
                (LIKE %value%).
            seq_no: Filter by spectrum sequence number (exact match).
            spectre_id: Filter by spectrum id (exact match, ``spectre.id``).
            scans: Filter by spectrum scans value (exact match).
            tool: Filter by tool name (exact match).
            tool_id: Filter by tool id (exact match).
            identification_id: Filter by identification id (exact match).
            protein_id: Filter by ``peptide_match.protein_id`` (exact match,
                e.g. UniProt accession).
            gene: Filter by ``protein.gene`` (LIKE %value%).
            max_ppm: Keep rows with ``|identification.ppm| <= value``.
            min_quality: Keep rows with ``identification.quality >= value``
                (NULL quality is excluded).
            has_ptm: Tri-state ('Yes'/'No'/other = all). 'Yes' keeps
                ``has_ptm = 1``; 'No' keeps NULL or 0.
            has_substitution: Tri-state ('Yes'/'No'/other = all). 'Yes' keeps
                ``peptide_match.substitution = 1``; 'No' keeps 0.
            max_fdr: Keep rows with ``identification.fdr <= value``
                (NULL fdr is excluded). When None, no FDR filter.
            limit: Maximum rows to return. ``None`` or ``-1`` disables
                pagination (returns all matching rows).
            offset: Number of rows to skip (for pagination).

        Returns:
            DataFrame with columns:
                - sample, subset, sample_id, subset_id
                - spectre_id, seq_no, scans, charge, rt, pepmass, intensity,
                  peaks_count
                - tool, tool_id, identification_id, sequence,
                  canonical_sequence, ppm, score, is_preferred,
                  ions_matched, ion_match_type, top_peaks_covered,
                  intensity_coverage, override_charge, source_sequence,
                  isotope_offset, theor_mass, quality, lcrr,
                  unconfirmed_ptms, override_pepmass, has_ptm, fdr, e_value,
                  q_value
                - matched_sequence, matched_ppm, protein_id, identity,
                  unique_evidence, gene, matched_peaks, matched_top_peaks,
                  matched_ion_type, matched_sequence_modified, substitution
        """
        query = """
            SELECT
                sm.name AS sample, sb.name AS subset, sm.id AS sample_id,
                sb.id AS subset_id,
                s.id as spectre_id, s.seq_no, s.scans, s.charge, s.rt,
                s.pepmass, s.intensity, s.peaks_count AS peaks_count,
                t.name AS tool, t.id AS tool_id, i.id AS identification_id,
                i.sequence, i.canonical_sequence, i.ppm, i.score,
                i.is_preferred,
                i.ions_matched, i.ion_match_type, i.top_peaks_covered,
                i.intensity_coverage,
                i.override_charge, i.source_sequence, i.isotope_offset,
                i.theor_mass, i.quality, i.lcrr, i.unconfirmed_ptms,
                i.override_pepmass, i.has_ptm,
                i.fdr, i.e_value, i.q_value,
                m.matched_sequence, m.matched_ppm, m.protein_id, m.identity,
                m.unique_evidence, p.gene,
                m.matched_peaks, m.matched_top_peaks, m.matched_ion_type,
                m.matched_sequence_modified, m.substitution
            FROM spectre AS s
            LEFT JOIN spectre_file f ON f.id = s.spectre_file_id
            LEFT JOIN sample sm ON sm.id = f.sample_id
            LEFT JOIN subset sb ON sb.id = sm.subset_id
            LEFT JOIN identification i ON i.spectre_id = s.id
            LEFT JOIN tool t ON t.id = i.tool_id
            LEFT JOIN peptide_match m ON m.identification_id = i.id
            LEFT JOIN protein p ON p.id = m.protein_id
            WHERE 1=1
        """

        conditions, params = self._build_peptide_filter_conditions(
            is_preferred=is_preferred,
            sequence_identified=sequence_identified,
            protein_identified=protein_identified,
            sample=sample,
            subset=subset,
            spectre_id=spectre_id,
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
            protein_id=protein_id,
            gene=gene,
            max_ppm=max_ppm,
            min_quality=min_quality,
            has_ptm=has_ptm,
            has_substitution=has_substitution,
            max_fdr=max_fdr,
        )

        if conditions:
            query += " AND " + " AND ".join(conditions)

        # limit=-1 (and None) means no pagination (export / full fetch)
        if limit is not None and limit != -1:
            query += " LIMIT ? OFFSET ?"
            params.append(limit)
            params.append(offset)

        logger.debug(query)
        logger.debug(params)
        return await self.execute_query_df(query, tuple(params) if params else None)
