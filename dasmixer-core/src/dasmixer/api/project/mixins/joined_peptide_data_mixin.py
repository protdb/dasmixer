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

        Returns:
            Tuple ``(conditions, params)`` — list of SQL fragments (to be
            AND-joined) and the corresponding bound parameters.
        """
        conditions = []
        params = []

        if is_preferred is not None:
            conditions.append("id.is_preferred = ?")
            params.append(1 if is_preferred else 0)

        if spectre_id is not None:
            conditions.append("s.id = ?")
            params.append(spectre_id)

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

        if protein_id is not None:
            conditions.append('mp.protein_id = ?')
            params.append(protein_id)

        if gene is not None:
            conditions.append("mp.gene LIKE ?")
            params.append(f"%{gene}%")

        # Min Quality (NULL quality is treated as not meeting the threshold)
        mq = min_quality
        if mq is not None:
            conditions.append("(id.quality IS NOT NULL AND id.quality >= ?)")
            params.append(float(mq))

        # Has PTM (values: 'Yes' | 'No'; anything else → no filter)
        if has_ptm == 'Yes':
            conditions.append("id.has_ptm = 1")
        elif has_ptm == 'No':
            # no PTM = NULL (not computed) or 0
            conditions.append("(id.has_ptm IS NULL OR id.has_ptm = 0)")

        # Has AA Substitution (peptide_match.substitution)
        if has_substitution == 'Yes':
            conditions.append("mp.substitution = 1")
        elif has_substitution == 'No':
            conditions.append("mp.substitution = 0")

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
                      i.quality,
                      i.lcrr,
                      i.unconfirmed_ptms,
                      i.has_ptm
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
                    m.substitution,
                    p.gene
                 FROM peptide_match m, protein p
                 WHERE p.id = m.protein_id) AS mp
                ON mp.identification_id = id.identification_id
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
                  unconfirmed_ptms, override_pepmass, has_ptm
                - matched_sequence, matched_ppm, protein_id, identity,
                  unique_evidence, gene, matched_peaks, matched_top_peaks,
                  matched_ion_type, matched_sequence_modified, substitution
        """
        query = """
             SELECT
                sb.sample, sb.subset, sb.sample_id, sb.subset_id,
                s.id as spectre_id, s.seq_no, s.scans, s.charge, s.rt, s.pepmass, s.intensity, s.peaks_count AS peaks_count,
                id.tool, id.tool_id, id.identification_id, id.sequence,
                id.canonical_sequence, id.ppm, id.score, id.is_preferred,
                id.ions_matched, id.ion_match_type, id.top_peaks_covered,
                id.intensity_coverage,
                id.override_charge, id.source_sequence, id.isotope_offset,
                 id.theor_mass, id.quality, id.lcrr, id.unconfirmed_ptms, id.override_pepmass, id.has_ptm,
                mp.matched_sequence, mp.matched_ppm, mp.protein_id, mp.identity,
                mp.unique_evidence, mp.gene,
                mp.matched_peaks, mp.matched_top_peaks, mp.matched_ion_type,
                mp.matched_sequence_modified, mp.substitution
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
                    i.top_peaks_covered,
                    i.override_charge,
                    i.source_sequence,
                    i.isotope_offset,
                    i.theor_mass,
                      i.quality,
                      i.lcrr,
                      i.unconfirmed_ptms,
                      i.override_pepmass,
                      i.has_ptm
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
                    m.matched_peaks,
                    m.matched_top_peaks,
                    m.matched_ion_type,
                    m.matched_sequence_modified,
                    m.substitution,
                    p.gene
                 FROM peptide_match m, protein p
                 WHERE p.id = m.protein_id) AS mp
                ON mp.identification_id = id.identification_id
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
