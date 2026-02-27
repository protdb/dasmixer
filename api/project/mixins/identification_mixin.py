"""Mixin for identification file and identification operations."""

import json
import pandas as pd

from utils.logger import logger


class IdentificationMixin:
    """
    Mixin providing identification file and identification management methods.
    
    Requires ProjectBase functionality and SpectraMixin (get_spectra_idlist).
    """
    
    # Identification file operations
    
    async def add_identification_file(
        self,
        spectra_file_id: int,
        tool_id: int,
        file_path: str
    ) -> int:
        """Add identification file record."""
        print(f"spectra_file_id: {spectra_file_id}, tool_id: {tool_id} file_path: {file_path}")
        cursor = await self._execute(
            "INSERT INTO identification_file (spectre_file_id, tool_id, file_path) VALUES (?, ?, ?)",
            (spectra_file_id, tool_id, file_path)
        )
        
        ident_file_id = cursor.lastrowid
        await self.save()
        
        logger.info(f"Added identification file: {file_path} (id={ident_file_id})")
        
        return ident_file_id
    
    async def get_identification_files(
        self,
        spectra_file_id: int | None = None,
        tool_id: int | None = None
    ) -> pd.DataFrame:
        """Get identification files as DataFrame."""
        query_parts = ["""
            SELECT if.*, t.name as tool_name, t.parser as tool_parser
            FROM identification_file if
            JOIN tool t ON if.tool_id = t.id
        """]
        
        conditions = []
        params = []
        
        if spectra_file_id is not None:
            conditions.append("if.spectre_file_id = ?")
            params.append(spectra_file_id)
        
        if tool_id is not None:
            conditions.append("if.tool_id = ?")
            params.append(tool_id)
        
        if conditions:
            query_parts.append("WHERE " + " AND ".join(conditions))
        
        query_parts.append("ORDER BY if.id")
        
        query = " ".join(query_parts)
        rows = await self._fetchall(query, tuple(params) if params else None)
        
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    
    # Identification operations (batch processing)
    
    async def add_identifications_batch(
        self,
        identifications_df: pd.DataFrame
    ) -> None:
        """
        Add batch of identifications.
        
        Args:
            identifications_df: DataFrame with columns:
                - spectre_id: int
                - tool_id: int
                - ident_file_id: int
                - is_preferred: bool
                - sequence: str
                - canonical_sequence: str
                - ppm: float | None
                - theor_mass: float | None
                - score: float | None
                - positional_scores: dict | None
                - intensity_coverage: float | None
        """
        rows_to_insert = []
        
        for _, row in identifications_df.iterrows():
            positional_scores_json = json.dumps(row.get('positional_scores')) if row.get('positional_scores') else None
            
            rows_to_insert.append((
                int(row['spectre_id']),
                int(row['tool_id']),
                int(row['ident_file_id']),
                1 if row.get('is_preferred', False) else 0,
                row['sequence'],
                row['canonical_sequence'],
                float(row['ppm']) if row.get('ppm') is not None else None,
                float(row['theor_mass']) if row.get('theor_mass') is not None else None,
                float(row['score']) if row.get('score') is not None else None,
                positional_scores_json,
                float(row['intensity_coverage']) if row.get('intensity_coverage') is not None else None
            ))
        
        if rows_to_insert:
            await self._executemany(
                """INSERT INTO identification 
                   (spectre_id, tool_id, ident_file_id, is_preferred, sequence, canonical_sequence,
                    ppm, theor_mass, score, positional_scores, intensity_coverage)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows_to_insert
            )
            await self.save()
            logger.info(f"Added {len(rows_to_insert)} identifications")

    async def add_all_identifications(self, file_id, parser, batch_size=1000):
        """
        Add all identifications from parser in batches.
        
        Args:
            file_id: Spectra file ID
            parser: Parser instance with parse_batch() method
            batch_size: Batch size for processing
        """
        spectra_ids = await self.get_spectra_idlist(file_id, parser.spectra_id_field)
        async for data, _ in parser.parse_batch(batch_size=batch_size):
            res = pd.merge(spectra_ids, data, on=parser.spectra_id_field)
            await self.add_identifications_batch(res)
    
    async def get_identifications(
        self,
        spectra_file_id: int | None = None,
        tool_id: int | None = None,
        sample_id: int | None = None,
        only_prefered: bool = False,
        max_abs_ppm: float | None = None,
        offset: int = 0,
        limit: int | None = None
    ) -> pd.DataFrame:
        """Get identifications as DataFrame with joined metadata."""
        query_parts = ["""
            SELECT i.*, s.title as spectrum_title, s.pepmass, s.rt, s.charge,
                   t.name as tool_name, t.parser as tool_parser,
                   sf.sample_id, sam.name as sample_name
            FROM identification i
            JOIN spectre s ON i.spectre_id = s.id
            JOIN tool t ON i.tool_id = t.id
            JOIN spectre_file sf ON s.spectre_file_id = sf.id
            JOIN sample sam ON sf.sample_id = sam.id
        """]
        
        conditions = []
        params = []
        
        if spectra_file_id is not None:
            conditions.append("s.spectre_file_id = ?")
            params.append(spectra_file_id)
        
        if tool_id is not None:
            conditions.append("i.tool_id = ?")
            params.append(tool_id)
        
        if sample_id is not None:
            conditions.append("sf.sample_id = ?")
            params.append(sample_id)
        
        if only_prefered:
            conditions.append("i.is_preferred = 1")

        if max_abs_ppm is not None:
            conditions.append("abs(i.ppm) <= ?")
            params.append(max_abs_ppm)
        
        if conditions:
            query_parts.append("WHERE " + " AND ".join(conditions))
        
        query_parts.append("ORDER BY i.id")
        
        if limit is not None:
            query_parts.append(f"LIMIT {limit} OFFSET {offset}")
        
        query = " ".join(query_parts)
        rows = await self._fetchall(query, tuple(params) if params else None)
        
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    async def get_idents_for_preferred(
            self,
            spectra_file_id: int,
            tool_id: int,
            min_score: float,
            max_abs_ppm: float,
            intensity_coverage: float,
            canonical_length: tuple[int, int]
    ):
        """
        special method for identification processing
        :param tool_id:
        :param spectra_file_id:
        :param min_score:
        :param max_abs_ppm:
        :param intensity_coverage:
        :param canonical_length:
        :return:
        """
        query = """
            SELECT
                i.id, i.spectre_id, i.tool_id, i.ppm, i.intensity_coverage, i.score,
                s.spectre_file_id,
                m.matched_ppm, m.matched_coverage_percent
            FROM identification i
            LEFT JOIN spectre s ON i.spectre_id = s.id
            LEFT JOIN (
                select
                    identification_id,
                    matched_coverage_percent,
                    min(matched_coverage_percent) as matched_coverage_percent,
                    min(abs(matched_ppm)) as matched_ppm
                from peptide_match
                GROUP by identification_id
                ) m on i.id = m.identification_id
            WHERE
            s.spectre_file_id = ? and
            i.tool_id = ? and
            i.score >= ? and
            abs(i.ppm) <= ? and
            i.intensity_coverage >= ? and
            ? <= length(i.canonical_sequence) <= ?
        """

        params = (
            int(spectra_file_id),
            int(tool_id),
            float(min_score),
            float(max_abs_ppm),
            float(intensity_coverage),
            float(canonical_length[0]),
            float(canonical_length[1])
        )

        rows = await self._fetchall(query, params)
        return pd.DataFrame(rows) if rows else pd.DataFrame()

    async def update_identification_coverage(
        self,
        identification_id: int,
        intensity_coverage: float
    ) -> None:
        """
        Update intensity coverage for an identification.
        
        Args:
            identification_id: Identification ID
            intensity_coverage: Percentage of spectrum intensity matched by ions
        """
        await self._execute(
            "UPDATE identification SET intensity_coverage = ? WHERE id = ?",
            (float(intensity_coverage), int(identification_id))
        )
        # Note: No auto-save here for batch operations efficiency
        # Caller should call save() after batch updates

    async def update_identification_coverage_batch(
            self,
            parameters: list[tuple[float, int]]
    ):
        query = """
        UPDATE identification SET intensity_coverage = ? WHERE id = ?
        """
        await self._executemany(query, parameters)
    
    async def set_preferred_identification(
        self,
        spectre_id: int,
        identification_id: int
    ) -> None:
        """
        Set preferred identification for a spectrum.
        
        Resets is_preferred to False for all identifications of this spectrum,
        then sets it to True for the specified identification.
        
        Args:
            spectre_id: Spectrum ID
            identification_id: Identification ID to mark as preferred
        """
        # Reset all for this spectrum
        await self._execute(
            "UPDATE identification SET is_preferred = 0 WHERE spectre_id = ?",
            (int(spectre_id),)
        )
        
        # Set preferred
        await self._execute(
            "UPDATE identification SET is_preferred = 1 WHERE id = ?",
            (int(identification_id),)
        )
        
        await self.save()
        logger.debug(f"Set preferred identification {identification_id} for spectrum {spectre_id}")

    async def set_preferred_identifications_for_file(
        self, 
        spectra_file_id: int, 
        preferred_ids: list[int]
    ) -> None:
        """
        Set preferred identifications for all spectra in a file.
        
        Args:
            spectra_file_id: Spectra file ID
            preferred_ids: List of identification IDs to mark as preferred
        """
        ids_df = await self.get_identifications(spectra_file_id)
        ids = list(ids_df["id"])
        
        await self._execute(
            f"UPDATE identification SET is_preferred = 0 WHERE id in ({', '.join([str(x) for x in ids])})",
        )
        await self._execute(
            f"UPDATE identification SET is_preferred = 1 WHERE id in ({', '.join([str(x) for x in preferred_ids])})",
        )
        await self.save()

    async def get_identifications_with_spectra_batch(
            self,
            tool_id: int,
            offset: int = 0,
            limit: int = 1000
    ) -> :
