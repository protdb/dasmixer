"""Mixin for sample operations."""

from ..dataclasses import Sample
from dasmixer.utils.logger import logger


class SampleMixin:
    """
    Mixin providing sample management methods.
    
    Requires ProjectBase functionality and SubsetMixin (get_subset).
    """
    
    async def add_sample(
        self,
        name: str,
        subset_id: int | None = None,
        additions: dict | None = None,
        outlier: bool = False
    ) -> Sample:
        """
        Add a new sample.
        
        Args:
            name: Unique sample name
            subset_id: FK to subset (comparison group)
            additions: Additional metadata (albumin, total_protein, etc.)
            outlier: Whether this sample is an outlier
            
        Returns:
            Created Sample object
        """
        # Check if exists
        existing = await self._fetchone(
            "SELECT id FROM sample WHERE name = ?",
            (name,)
        )
        if existing:
            raise ValueError(f"Sample with name '{name}' already exists")
        
        # Validate subset_id if provided
        if subset_id is not None:
            subset = await self.get_subset(subset_id)
            if subset is None:
                raise ValueError(f"Subset with id={subset_id} does not exist")
        
        additions_json = self._serialize_json(additions)
        
        cursor = await self._execute(
            "INSERT INTO sample (name, subset_id, additions, outlier) VALUES (?, ?, ?, ?)",
            (name, subset_id, additions_json, 1 if outlier else 0)
        )
        
        sample_id = cursor.lastrowid
        await self.save()
        
        logger.info(f"Added sample: {name} (id={sample_id})")
        
        return Sample(
            id=sample_id,
            name=name,
            subset_id=subset_id,
            additions=additions,
            outlier=outlier
        )
    
    async def get_samples(self, subset_id: int | None = None) -> list[Sample]:
        """
        Get samples, optionally filtered by subset.
        
        Args:
            subset_id: If provided, return only samples from this subset
        """
        if subset_id is not None:
            query = """
                SELECT s.*, sub.name as subset_name,
                       (SELECT COUNT(*) FROM spectre_file WHERE sample_id = s.id) as spectra_files_count
                FROM sample s
                LEFT JOIN subset sub ON s.subset_id = sub.id
                WHERE s.subset_id = ?
                ORDER BY s.name
            """
            rows = await self._fetchall(query, (subset_id,))
        else:
            query = """
                SELECT s.*, sub.name as subset_name,
                       (SELECT COUNT(*) FROM spectre_file WHERE sample_id = s.id) as spectra_files_count
                FROM sample s
                LEFT JOIN subset sub ON s.subset_id = sub.id
                ORDER BY s.name
            """
            rows = await self._fetchall(query)
        
        return [Sample.from_dict(row) for row in rows]
    
    async def get_sample(self, sample_id: int) -> Sample | None:
        """Get sample by ID."""
        query = """
            SELECT s.*, sub.name as subset_name,
                   (SELECT COUNT(*) FROM spectre_file WHERE sample_id = s.id) as spectra_files_count
            FROM sample s
            LEFT JOIN subset sub ON s.subset_id = sub.id
            WHERE s.id = ?
        """
        row = await self._fetchone(query, (sample_id,))
        return Sample.from_dict(row) if row else None
    
    async def get_sample_by_name(self, name: str) -> Sample | None:
        """Get sample by name."""
        query = """
            SELECT s.*, sub.name as subset_name,
                   (SELECT COUNT(*) FROM spectre_file WHERE sample_id = s.id) as spectra_files_count
            FROM sample s
            LEFT JOIN subset sub ON s.subset_id = sub.id
            WHERE s.name = ?
        """
        row = await self._fetchone(query, (name,))
        return Sample.from_dict(row) if row else None
    
    async def update_sample(self, sample: Sample) -> None:
        """Update existing sample."""
        if sample.id is None:
            raise ValueError("Cannot update sample without ID")
        
        additions_json = self._serialize_json(sample.additions)
        
        await self._execute(
            "UPDATE sample SET name = ?, subset_id = ?, additions = ?, outlier = ? WHERE id = ?",
            (sample.name, sample.subset_id, additions_json, 1 if sample.outlier else 0, sample.id)
        )
        await self.save()
        logger.debug(f"Updated sample: {sample.name}")
    
    async def delete_sample(self, sample_id: int) -> None:
        """Delete sample (cascades to spectra files)."""
        await self._execute("DELETE FROM sample WHERE id = ?", (sample_id,))
        await self.save()
        logger.info(f"Deleted sample id={sample_id}")

    async def get_sample_stats(self, sample_id: int) -> dict:
        """
        Return aggregated statistics for a sample panel header.
        
        Executes a single SQL query with subqueries for efficiency.
        
        Returns dict with keys:
            spectra_files_count, ident_files_count, identifications_count,
            preferred_count, coverage_known_count, protein_ids_count,
            empty_ident_files_count
        """
        query = """
            SELECT
                (SELECT COUNT(*) FROM spectre_file WHERE sample_id = ?) AS spectra_files_count,
                (SELECT COUNT(*) FROM identification_file if2
                 JOIN spectre_file sf2 ON if2.spectre_file_id = sf2.id
                 WHERE sf2.sample_id = ?) AS ident_files_count,
                (SELECT COUNT(*) FROM identification i2
                 JOIN spectre s2 ON i2.spectre_id = s2.id
                 JOIN spectre_file sf3 ON s2.spectre_file_id = sf3.id
                 WHERE sf3.sample_id = ?) AS identifications_count,
                (SELECT COUNT(*) FROM identification i3
                 JOIN spectre s3 ON i3.spectre_id = s3.id
                 JOIN spectre_file sf4 ON s3.spectre_file_id = sf4.id
                 WHERE sf4.sample_id = ? AND i3.is_preferred = 1) AS preferred_count,
                (SELECT COUNT(*) FROM identification i4
                 JOIN spectre s4 ON i4.spectre_id = s4.id
                 JOIN spectre_file sf5 ON s4.spectre_file_id = sf5.id
                 WHERE sf5.sample_id = ? AND i4.intensity_coverage IS NOT NULL) AS coverage_known_count,
                (SELECT COUNT(*) FROM protein_identification_result WHERE sample_id = ?) AS protein_ids_count,
                (SELECT COUNT(*) FROM identification_file if5
                 JOIN spectre_file sf6 ON if5.spectre_file_id = sf6.id
                 WHERE sf6.sample_id = ?
                 AND NOT EXISTS (
                     SELECT 1 FROM identification WHERE ident_file_id = if5.id
                 )) AS empty_ident_files_count
        """
        sid = int(sample_id)
        row = await self._fetchone(query, (sid, sid, sid, sid, sid, sid, sid))
        if not row:
            return {
                'spectra_files_count': 0,
                'ident_files_count': 0,
                'identifications_count': 0,
                'preferred_count': 0,
                'coverage_known_count': 0,
                'protein_ids_count': 0,
                'empty_ident_files_count': 0,
            }
        return dict(row)

    async def get_sample_detail(self, sample_id: int) -> list[dict]:
        """
        Return detailed file tree for a sample panel body.

        Uses a single JOIN query instead of N+1 queries.

        Returns list of spectre_file dicts, each with 'ident_files' key:
            list of dicts: id, tool_id, tool_name, file_path, ident_count
        """
        # One query: all spectra files + their identification files + counts
        query = """
            SELECT
                sf.id          AS sf_id,
                sf.path        AS sf_path,
                sf.format      AS sf_format,
                if2.id         AS if_id,
                if2.tool_id    AS if_tool_id,
                if2.file_path  AS if_file_path,
                t.name         AS if_tool_name,
                (SELECT COUNT(*) FROM identification WHERE ident_file_id = if2.id) AS ident_count
            FROM spectre_file sf
            LEFT JOIN identification_file if2 ON if2.spectre_file_id = sf.id
            LEFT JOIN tool t ON if2.tool_id = t.id
            WHERE sf.sample_id = ?
            ORDER BY sf.id, if2.id
        """
        rows = await self._fetchall(query, (int(sample_id),))

        # Group by spectra file
        sf_map: dict[int, dict] = {}
        for row in rows:
            sf_id = int(row['sf_id'])
            if sf_id not in sf_map:
                sf_map[sf_id] = {
                    'id': sf_id,
                    'path': row['sf_path'],
                    'format': row['sf_format'],
                    'ident_files': [],
                }
            if row['if_id'] is not None:
                sf_map[sf_id]['ident_files'].append({
                    'id': int(row['if_id']),
                    'tool_id': row['if_tool_id'],
                    'file_path': row['if_file_path'],
                    'tool_name': row['if_tool_name'],
                    'ident_count': int(row['ident_count'] or 0),
                })

        return list(sf_map.values())

    async def get_tools_count(self) -> int:
        """Return total number of tools."""
        row = await self._fetchone("SELECT COUNT(*) AS count FROM tool")
        return int(row['count']) if row else 0

    async def get_sample_status_summary(self, min_proteins: int = 30, min_idents: int = 1000) -> dict:
        """
        Return aggregate sample status counters derived from sample_status_cache.

        Status rules (same as SamplesSection._build_sample_header):
          - ERROR:   no spectra files  OR  has spectra but no ident files
          - OK:      has spectra + ident files + idents >= min_idents
                     + proteins ok (0 or >= min_proteins) + no empty ident files
          - WARNING: everything else (has data but some threshold not met)

        Returns dict:
            total      - total number of samples
            ok         - samples in OK state
            warning    - samples in WARNING state
            error      - samples in ERROR state
            uncached   - samples with no cache entry yet
        """
        # Get all samples count
        row_total = await self._fetchone("SELECT COUNT(*) AS cnt FROM sample")
        total = int(row_total['cnt']) if row_total else 0

        if total == 0:
            return {'total': 0, 'ok': 0, 'warning': 0, 'error': 0, 'uncached': 0}

        # Get tools count (needed for expected ident files check)
        row_tools = await self._fetchone("SELECT COUNT(*) AS cnt FROM tool")
        tools_count = int(row_tools['cnt']) if row_tools else 0

        # Load all cached stats
        rows = await self._fetchall("SELECT * FROM sample_status_cache")
        cached_ids_count = len(rows)
        uncached = total - cached_ids_count

        ok = warning = error = 0
        for row in rows:
            sf = int(row['spectra_files_count'] or 0)
            if_c = int(row['ident_files_count'] or 0)
            idents = int(row['identifications_count'] or 0)
            proteins = int(row['protein_ids_count'] or 0)
            empty_if = int(row['empty_ident_files_count'] or 0)

            has_spectra = sf > 0
            has_ident = if_c > 0
            expected_if = tools_count * sf if sf > 0 else 0
            ident_files_ok = (expected_if == 0) or (if_c == expected_if)
            idents_ok = idents >= min_idents
            proteins_ok = (proteins == 0) or (proteins >= min_proteins)

            if not has_spectra or (has_spectra and not has_ident):
                error += 1
            elif has_spectra and has_ident and ident_files_ok and idents_ok and proteins_ok and empty_if == 0:
                ok += 1
            else:
                warning += 1

        return {
            'total': total,
            'ok': ok,
            'warning': warning,
            'error': error,
            'uncached': uncached,
        }

    async def get_sample_counts_by_subset(self) -> dict[int, int]:
        """
        Return sample counts grouped by subset_id.

        Returns:
            dict mapping subset_id (int) → sample count (int).
            Subsets with no samples are not included.
        """
        rows = await self._fetchall(
            "SELECT subset_id, COUNT(*) AS cnt FROM sample WHERE subset_id IS NOT NULL GROUP BY subset_id"
        )
        return {int(r['subset_id']): int(r['cnt']) for r in rows}

    # ------------------------------------------------------------------
    # sample_status_cache methods
    # ------------------------------------------------------------------

    async def get_cached_sample_stats(self, sample_id: int) -> dict | None:
        """
        Return cached stats for a sample, or None if not cached yet.

        Returns dict with same keys as get_sample_stats() or None.
        """
        row = await self._fetchone(
            "SELECT * FROM sample_status_cache WHERE sample_id = ?",
            (int(sample_id),)
        )
        return dict(row) if row else None

    async def get_all_cached_sample_stats(self) -> dict[int, dict]:
        """
        Return cached stats for ALL samples as {sample_id: stats_dict}.

        Used on project open to avoid N×expensive SQL on all samples.
        """
        rows = await self._fetchall("SELECT * FROM sample_status_cache")
        if not rows:
            return {}
        return {int(row['sample_id']): dict(row) for row in rows}

    async def upsert_sample_status_cache(self, sample_id: int, stats: dict) -> None:
        """
        Insert or replace cached stats for a sample.

        Args:
            sample_id: Sample ID
            stats: Dict with keys matching sample_status_cache columns
                   (spectra_files_count, ident_files_count, identifications_count,
                    preferred_count, coverage_known_count, protein_ids_count,
                    empty_ident_files_count)
        """
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()

        await self._execute(
            """INSERT OR REPLACE INTO sample_status_cache
               (sample_id, spectra_files_count, ident_files_count,
                identifications_count, preferred_count, coverage_known_count,
                protein_ids_count, empty_ident_files_count, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                int(sample_id),
                int(stats.get('spectra_files_count', 0)),
                int(stats.get('ident_files_count', 0)),
                int(stats.get('identifications_count', 0)),
                int(stats.get('preferred_count', 0)),
                int(stats.get('coverage_known_count', 0)),
                int(stats.get('protein_ids_count', 0)),
                int(stats.get('empty_ident_files_count', 0)),
                now,
            )
        )
        # No save() here — caller decides when to save (batch or immediate)

    async def invalidate_sample_status_cache(self, sample_id: int) -> None:
        """Remove cached stats for a single sample (forces recalc on next refresh)."""
        await self._execute(
            "DELETE FROM sample_status_cache WHERE sample_id = ?",
            (int(sample_id),)
        )

    async def compute_and_cache_sample_stats(self, sample_id: int) -> dict:
        """
        Compute fresh stats for one sample and write to cache.

        Returns the computed stats dict.
        """
        stats = await self.get_sample_stats(sample_id)
        await self.upsert_sample_status_cache(sample_id, stats)
        await self.save()
        return stats
