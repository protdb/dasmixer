"""Mixin for protein operations, identification results, and quantification."""

import pandas as pd

from ..dataclasses import Protein
from dasmixer.utils.logger import logger


class ProteinMixin:
    """
    Mixin providing protein management, identification results, and quantification methods.
    
    Requires ProjectBase functionality and QueryMixin (execute_query_df).
    """
    
    # Protein operations
    
    async def add_protein(
        self,
        protein_id: str,
        sequence: str,
        is_uniprot: bool = False,
        fasta_name: str | None = None,
        gene: str | None = None,
        name: str | None = None,
        uniprot_data=None  # UniprotData object
    ) -> None:
        """
        Add or update protein.
        
        Args:
            protein_id: Protein ID
            sequence: Amino acid sequence
            is_uniprot: Whether ID is from UniProt
            fasta_name: Name from FASTA header
            gene: Gene name
            name: Short protein name
            uniprot_data: UniprotData object
        """
        # Serialize uniprot_data
        uniprot_blob = self._serialize_pickle_gzip(uniprot_data)
        
        await self._execute(
            """INSERT OR REPLACE INTO protein 
               (id, is_uniprot, fasta_name, sequence, gene, name, uniprot_data)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (protein_id, 1 if is_uniprot else 0, fasta_name, sequence, gene, name, uniprot_blob)
        )
        await self.save()
        logger.debug(f"Added/updated protein: {protein_id}")
    
    async def add_proteins_batch(self, proteins_df: pd.DataFrame) -> None:
        """Add batch of proteins from DataFrame."""
        rows_to_insert = []
        
        for _, row in proteins_df.iterrows():
            # Serialize uniprot_data if present
            uniprot_blob = None
            if 'uniprot_data' in row and row['uniprot_data'] is not None:
                uniprot_blob = self._serialize_pickle_gzip(row['uniprot_data'])
            
            rows_to_insert.append((
                row['id'],
                1 if row.get('is_uniprot', False) else 0,
                row.get('fasta_name'),
                row.get('sequence'),
                row.get('gene'),
                row.get('name'),
                uniprot_blob
            ))
        
        if rows_to_insert:
            await self._executemany(
                """INSERT OR REPLACE INTO protein 
                   (id, is_uniprot, fasta_name, sequence, gene, name, uniprot_data)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                rows_to_insert
            )
            await self.save()
            logger.info(f"Added {len(rows_to_insert)} proteins")
    
    async def get_protein(self, protein_id: str) -> Protein | None:
        """Get protein by ID."""
        row = await self._fetchone(
            "SELECT * FROM protein WHERE id = ?",
            (protein_id,)
        )
        
        if not row:
            return None
        
        # Deserialize uniprot_data
        uniprot_data = self._deserialize_pickle_gzip(row.get('uniprot_data'))
        
        return Protein(
            id=row['id'],
            is_uniprot=bool(row.get('is_uniprot', False)),
            fasta_name=row.get('fasta_name'),
            sequence=row.get('sequence'),
            gene=row.get('gene'),
            name=row.get('name'),
            uniprot_data=uniprot_data
        )
    
    async def get_proteins(self, is_uniprot: bool | None = None) -> list[Protein]:
        """Get proteins, optionally filtered."""
        if is_uniprot is not None:
            rows = await self._fetchall(
                "SELECT * FROM protein WHERE is_uniprot = ? ORDER BY id",
                (1 if is_uniprot else 0,)
            )
        else:
            rows = await self._fetchall("SELECT * FROM protein ORDER BY id")
        
        proteins = []
        for row in rows:
            # Deserialize uniprot_data
            uniprot_data = self._deserialize_pickle_gzip(row.get('uniprot_data'))
            
            proteins.append(Protein(
                id=row['id'],
                is_uniprot=bool(row.get('is_uniprot', False)),
                fasta_name=row.get('fasta_name'),
                sequence=row.get('sequence'),
                gene=row.get('gene'),
                name=row.get('name'),
                uniprot_data=uniprot_data
            ))
        
        return proteins

    async def get_protein_db_to_search(self) -> dict[str, str]:
        """
        Special function to get Protein data to apply search with npysearch.
        
        Returns:
            dict {protein_id: sequence} for full protein DB loaded
        """
        rows = await self._fetchall(
            "SELECT id, sequence FROM protein",
        )
        return {row['id']: row['sequence'] for row in rows}
    
    async def get_protein_count(self) -> int:
        """
        Get total number of proteins in database.
        
        Returns:
            int: Total protein count
        """
        query = "SELECT COUNT(*) as count FROM protein"
        result = await self.execute_query_df(query)
        if len(result) == 0:
            return 0
        return int(result.iloc[0]['count'])
    
    # Protein identification results operations
    
    async def clear_protein_identifications(self) -> None:
        """
        Clear all protein identification results.
        
        Deletes all records from protein_identification_result.
        Cascade deletes linked quantification results.
        """
        await self._execute("DELETE FROM protein_identification_result")
        await self.save()
        logger.info("Cleared all protein identifications")
    
    async def add_protein_identifications_batch(
        self,
        identifications_df: pd.DataFrame
    ) -> None:
        """
        Add batch of protein identification results.
        
        Args:
            identifications_df: DataFrame with columns:
                - protein_id: str
                - sample_id: int
                - peptide_count: int
                - uq_evidence_count: int
                - coverage: float (percentage)
                - intensity_sum: float
        """
        rows_to_insert = []
        
        for _, row in identifications_df.iterrows():
            rows_to_insert.append((
                row['protein_id'],
                int(row['sample_id']),
                int(row['peptide_count']),
                int(row['uq_evidence_count']),
                float(row['coverage']) if row.get('coverage') is not None else None,
                float(row['intensity_sum']) if row.get('intensity_sum') is not None else None
            ))
        
        if rows_to_insert:
            await self._executemany(
                """INSERT INTO protein_identification_result 
                   (protein_id, sample_id, peptide_count, uq_evidence_count, coverage, intensity_sum)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                rows_to_insert
            )
            await self.save()
            logger.info(f"Added {len(rows_to_insert)} protein identifications")
    
    async def get_protein_identifications(
        self,
        sample_id: int | None = None
    ) -> pd.DataFrame:
        """
        Get protein identification results.
        
        Args:
            sample_id: Optional filter by sample
        
        Returns:
            DataFrame with columns:
                - id, protein_id, sample_id, peptide_count,
                  uq_evidence_count, coverage, intensity_sum
        """
        query = "SELECT * FROM protein_identification_result"
        params = None
        
        if sample_id is not None:
            query += " WHERE sample_id = ?"
            params = (int(sample_id),)
        
        query += " ORDER BY id"
        print(query, params)
        return await self.execute_query_df(query, params)
    
    async def get_protein_identification_count(self) -> int:
        """Get total number of protein identifications."""
        query = "SELECT COUNT(*) as count FROM protein_identification_result"
        result = await self.execute_query_df(query)
        if len(result) == 0:
            return 0
        return int(result.iloc[0]['count'])
    
    # Protein quantification results operations
    
    async def clear_protein_quantifications(self) -> None:
        """Clear all protein quantification results."""
        await self._execute("DELETE FROM protein_quantification_result")
        await self.save()
        logger.info("Cleared all protein quantifications")
    
    async def add_protein_quantifications_batch(
        self,
        quantifications_df: pd.DataFrame
    ) -> None:
        """
        Add batch of protein quantification results.
        
        Args:
            quantifications_df: DataFrame with columns:
                - protein_identification_id: int
                - algorithm: str ('emPAI', 'iBAQ', 'NSAF', 'Top3')
                - rel_value: float
                - abs_value: float | None
        """
        rows_to_insert = []
        
        for _, row in quantifications_df.iterrows():
            rows_to_insert.append((
                int(row['protein_identification_id']),
                row['algorithm'],
                float(row['rel_value']) if row.get('rel_value') is not None else None,
                float(row['abs_value']) if row.get('abs_value') is not None else None
            ))
        
        if rows_to_insert:
            await self._executemany(
                """INSERT INTO protein_quantification_result 
                   (protein_identification_id, algorithm, rel_value, abs_value)
                   VALUES (?, ?, ?, ?)""",
                rows_to_insert
            )
            await self.save()
            logger.info(f"Added {len(rows_to_insert)} protein quantifications")
    
    async def get_protein_quantification_count(self) -> int:
        """Get total number of protein quantifications."""
        query = "SELECT COUNT(*) as count FROM protein_quantification_result"
        result = await self.execute_query_df(query)
        if len(result) == 0:
            return 0
        return int(result.iloc[0]['count'])

    async def get_protein_quantification_data(
            self,
            method: str = None,
            subsets: list[str] | None = None,
            protein_id: str | None = None
    ) -> pd.DataFrame:
        """
        Get protein quantification data.
        
        Args:
            method: LFQ algorithm ('emPAI', 'iBAQ', 'NSAF', 'Top3')
            subsets: Optional list of subset names to filter
            protein_id: Optional protein ID to filter
        
        Returns:
            DataFrame with quantification data
        """
        query = """
            select
                i.sample_id,
                s.name as sample,
                sb.name as subset,
                i.protein_id,
                p.fasta_name,
                i.peptide_count,
                i.uq_evidence_count,
                i.coverage,
                i.intensity_sum,
                q.algorithm,
                q.rel_value,
                q.abs_value
            from
                protein_quantification_result as q
                left join protein_identification_result as i on q.protein_identification_id = i.id
                left join protein as p on i.protein_id = p.id
                left join sample as s on s.id = i.sample_id
                left join subset as sb on sb.id = s.subset_id
            WHERE 1=1
        """
        params = []
        
        if method:
            query += " AND q.algorithm = ?"
            params.append(method)
        
        if protein_id:
            query += " AND i.protein_id = ?"
            params.append(protein_id)
        
        if subsets:
            placeholders = ','.join('?' * len(subsets))
            query += f" AND sb.name IN ({placeholders})"
            params.extend(subsets)
        
        params_tuple = tuple(params) if params else None
        df = await self.execute_query_df(query, params_tuple)
        return df
    
    async def count_protein_results_joined(
        self,
        sample: str | None = None,
        subset: str | None = None,
        min_peptides: int = 0,
        min_unique: int = 0,
        protein_id: str | None = None,
        gene: str | None = None,
        min_coverage: float | None = None,
        max_coverage: float | None = None,
        min_intensity: float | None = None,
        max_intensity: float | None = None,
    ) -> int:
        """
        Count rows that would be returned by get_protein_results_joined
        (with optional filters).

        Uses a lightweight COUNT(*) query — does NOT load all rows.
        """
        query = """
            SELECT COUNT(*) AS cnt
            FROM protein_identification_result pir
            JOIN sample s ON pir.sample_id = s.id
            LEFT JOIN subset sub ON s.subset_id = sub.id
            LEFT JOIN protein p ON pir.protein_id = p.id
            WHERE 1=1
        """
        params: list = []

        if sample is not None:
            query += " AND s.name = ?"
            params.append(sample)

        if subset is not None:
            query += " AND sub.name = ?"
            params.append(subset)

        if protein_id:
            query += " AND pir.protein_id LIKE ?"
            params.append(f"%{protein_id}%")

        if gene:
            query += " AND p.gene LIKE ?"
            params.append(f"%{gene}%")

        if min_peptides > 0:
            query += " AND pir.peptide_count >= ?"
            params.append(min_peptides)

        if min_unique > 0:
            query += " AND pir.uq_evidence_count >= ?"
            params.append(min_unique)

        if min_coverage is not None:
            query += " AND pir.coverage >= ?"
            params.append(min_coverage)

        if max_coverage is not None:
            query += " AND pir.coverage <= ?"
            params.append(max_coverage)

        if min_intensity is not None:
            query += " AND pir.intensity_sum >= ?"
            params.append(min_intensity)

        if max_intensity is not None:
            query += " AND pir.intensity_sum <= ?"
            params.append(max_intensity)

        row = await self._fetchone(query, tuple(params) if params else None)
        return int(row['cnt']) if row else 0

    async def get_protein_results_joined(
        self,
        sample: str | None = None,
        subset: str | None = None,
        protein_id: str | None = None,
        gene: str | None = None,
        min_peptides: int = 0,
        min_unique: int = 0,
        min_coverage: float | None = None,
        max_coverage: float | None = None,
        min_intensity: float | None = None,
        max_intensity: float | None = None,
        limit: int = 100,
        offset: int = 0
    ) -> pd.DataFrame:
        """
        Get joined protein identification and quantification results.
        
        Returns one row per protein_identification_result with
        pivoted columns for each LFQ method.
        
        Args:
            sample: Optional filter by sample name
            subset: Optional filter by subset/group name
            protein_id: Optional LIKE filter on protein ID
            gene: Optional LIKE filter on gene name
            min_peptides: Minimum peptide count
            min_unique: Minimum unique evidence count
            min_coverage: Minimum sequence coverage (%)
            max_coverage: Maximum sequence coverage (%)
            min_intensity: Minimum intensity sum
            max_intensity: Maximum intensity sum
            limit: Maximum number of rows to return
            offset: Offset for pagination
        
        Returns:
            DataFrame with columns:
                - sample: str - sample name
                - subset: str - subset name
                - protein_id: str
                - gene: str | None
                - weight: float | None - molecular weight from sequence
                - peptide_count: int
                - unique_evidence_count: int (renamed from uq_evidence_count)
                - coverage_percent: float - coverage as percentage
                - intensity_sum: float
                - EmPAI: float | None
                - iBAQ: float | None
                - NSAF: float | None
                - Top3: float | None
        """
        # Main query with JOINs
        query = """
            SELECT 
                pir.id,
                pir.protein_id,
                pir.sample_id,
                s.name AS sample,
                sub.name AS subset,
                p.gene,
                p.sequence,
                pir.peptide_count,
                pir.uq_evidence_count AS unique_evidence_count,
                pir.coverage AS coverage_percent,
                pir.intensity_sum,
                pqr_empai.rel_value AS EmPAI,
                pqr_ibaq.rel_value AS iBAQ,
                pqr_nsaf.rel_value AS NSAF,
                pqr_top3.rel_value AS Top3
            FROM protein_identification_result pir
            JOIN sample s ON pir.sample_id = s.id
            LEFT JOIN subset sub ON s.subset_id = sub.id
            LEFT JOIN protein p ON pir.protein_id = p.id
            LEFT JOIN protein_quantification_result pqr_empai 
                ON pir.id = pqr_empai.protein_identification_id AND pqr_empai.algorithm = 'emPAI'
            LEFT JOIN protein_quantification_result pqr_ibaq 
                ON pir.id = pqr_ibaq.protein_identification_id AND pqr_ibaq.algorithm = 'iBAQ'
            LEFT JOIN protein_quantification_result pqr_nsaf 
                ON pir.id = pqr_nsaf.protein_identification_id AND pqr_nsaf.algorithm = 'NSAF'
            LEFT JOIN protein_quantification_result pqr_top3 
                ON pir.id = pqr_top3.protein_identification_id AND pqr_top3.algorithm = 'Top3'
            WHERE 1=1
        """
        
        params: list = []

        if sample is not None:
            query += " AND s.name = ?"
            params.append(sample)

        if subset is not None:
            query += " AND sub.name = ?"
            params.append(subset)

        if protein_id:
            query += " AND pir.protein_id LIKE ?"
            params.append(f"%{protein_id}%")

        if gene:
            query += " AND p.gene LIKE ?"
            params.append(f"%{gene}%")

        if min_peptides > 0:
            query += " AND pir.peptide_count >= ?"
            params.append(min_peptides)

        if min_unique > 0:
            query += " AND pir.uq_evidence_count >= ?"
            params.append(min_unique)

        if min_coverage is not None:
            query += " AND pir.coverage >= ?"
            params.append(min_coverage)

        if max_coverage is not None:
            query += " AND pir.coverage <= ?"
            params.append(max_coverage)

        if min_intensity is not None:
            query += " AND pir.intensity_sum >= ?"
            params.append(min_intensity)

        if max_intensity is not None:
            query += " AND pir.intensity_sum <= ?"
            params.append(max_intensity)

        query += " ORDER BY s.name, pir.protein_id"
        if limit != -1:
            query += f" LIMIT {limit} OFFSET {offset}"
        
        df = await self.execute_query_df(query, tuple(params) if params else None)
        
        # Calculate weight from sequence
        if len(df) > 0 and 'sequence' in df.columns:
            def calc_weight(seq):
                if seq is None or pd.isna(seq):
                    return None
                try:
                    from pyteomics import mass
                    return mass.calculate_mass(sequence=seq)
                except:
                    return None
            
            df['weight'] = df['sequence'].apply(calc_weight)
            df = df.drop(columns=['sequence', 'id', 'sample_id'])
        
        return df
    
    async def get_protein_statistics(
        self,
        protein_id: str = '',
        gene: str = '',
        fasta_name: str = '',
        min_samples: int = 0,
        min_subsets: int = 0,
        only_identified: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> pd.DataFrame:
        """
        Get aggregated protein statistics.
        
        Args:
            protein_id: Filter protein ID (LIKE)
            gene: Filter gene name (LIKE)
            fasta_name: Filter FASTA name (LIKE)
            min_samples: Minimum number of samples (default 0 = include all identified)
            min_subsets: Minimum number of subsets (default 0)
            only_identified: If True (default), only return proteins with at least 1 sample
            limit: Maximum rows to return (-1 = no limit)
            offset: Pagination offset
        
        Returns:
            DataFrame with columns:
                - protein_id: str
                - gene: str
                - fasta_name: str (truncated to 30 chars)
                - samples: int (count of samples)
                - subsets: int (count of subsets)
                - PSMs: int (count of peptide matches)
                - unique_evidence: int (count of unique evidence)
        """
        # Build WHERE conditions for protein table filter
        where_parts = ["1=1"]
        params: list = []
        
        if protein_id:
            where_parts.append("p.id LIKE ?")
            params.append(f"%{protein_id}%")
        
        if gene:
            where_parts.append("p.gene LIKE ?")
            params.append(f"%{gene}%")
        
        if fasta_name:
            where_parts.append("p.fasta_name LIKE ?")
            params.append(f"%{fasta_name}%")
        
        where_clause = " AND ".join(where_parts)

        # Effective min_samples for HAVING clause
        effective_min_samples = max(min_samples, 1) if only_identified else min_samples
        
        # Main query with aggregation
        query = f"""
        WITH protein_stats AS (
            SELECT
                p.id as protein_id,
                p.gene,
                SUBSTR(COALESCE(p.fasta_name, ''), 1, 30) as fasta_name,
                COUNT(DISTINCT pir.sample_id) as samples,
                COUNT(DISTINCT s.subset_id) as subsets,
                COUNT(DISTINCT pm.id) as PSMs,
                SUM(CASE WHEN pm.unique_evidence = 1 THEN 1 ELSE 0 END) as unique_evidence
            FROM protein p
            LEFT JOIN protein_identification_result pir ON p.id = pir.protein_id
            LEFT JOIN sample s ON pir.sample_id = s.id
            LEFT JOIN peptide_match pm ON p.id = pm.protein_id
            WHERE {where_clause}
            GROUP BY p.id, p.gene, p.fasta_name
        )
        SELECT * FROM protein_stats
        WHERE samples >= ? AND subsets >= ?
        ORDER BY samples DESC, protein_id
        LIMIT ? OFFSET ?
        """
        
        if limit == -1:
            params.extend([effective_min_samples, min_subsets, 999999999, 0])
        else:
            params.extend([effective_min_samples, min_subsets, limit, offset])

        try:
            df = await self.execute_query_df(query, tuple(params))
        except Exception as e:
            logger.error(f"get_protein_statistics query failed: {e}")
            return pd.DataFrame(columns=[
                'protein_id', 'gene', 'fasta_name', 'samples', 'subsets', 'PSMs', 'unique_evidence'
            ])
        return df

    async def count_protein_statistics(
        self,
        protein_id: str = '',
        gene: str = '',
        fasta_name: str = '',
        min_samples: int = 0,
        min_subsets: int = 0,
        only_identified: bool = True,
    ) -> int:
        """
        Count rows for get_protein_statistics without loading all data.
        
        Args:
            protein_id: Filter protein ID (LIKE)
            gene: Filter gene name (LIKE)
            fasta_name: Filter FASTA name (LIKE)
            min_samples: Minimum number of samples
            min_subsets: Minimum number of subsets
            only_identified: If True (default), only count proteins with at least 1 sample
        
        Returns:
            int: Row count
        """
        where_parts = ["1=1"]
        params: list = []

        if protein_id:
            where_parts.append("p.id LIKE ?")
            params.append(f"%{protein_id}%")

        if gene:
            where_parts.append("p.gene LIKE ?")
            params.append(f"%{gene}%")

        if fasta_name:
            where_parts.append("p.fasta_name LIKE ?")
            params.append(f"%{fasta_name}%")

        where_clause = " AND ".join(where_parts)
        effective_min_samples = max(min_samples, 1) if only_identified else min_samples

        query = f"""
        WITH protein_stats AS (
            SELECT
                p.id as protein_id,
                COUNT(DISTINCT pir.sample_id) as samples,
                COUNT(DISTINCT s.subset_id) as subsets
            FROM protein p
            LEFT JOIN protein_identification_result pir ON p.id = pir.protein_id
            LEFT JOIN sample s ON pir.sample_id = s.id
            WHERE {where_clause}
            GROUP BY p.id
        )
        SELECT COUNT(*) AS cnt FROM protein_stats
        WHERE samples >= ? AND subsets >= ?
        """

        params.extend([effective_min_samples, min_subsets])

        try:
            row = await self._fetchone(query, tuple(params))
            return int(row['cnt']) if row else 0
        except Exception as e:
            logger.error(f"count_protein_statistics query failed: {e}")
            return 0

    async def clear_protein_identifications_for_sample(self, sample_id: int) -> None:
        """
        Delete protein identification results for a given sample.
        Cascade-deletes linked protein_quantification_result rows via FK.
        """
        await self._execute(
            "DELETE FROM protein_identification_result WHERE sample_id = ?",
            (int(sample_id),)
        )
        await self.save()
        logger.info(f"Cleared protein identifications for sample_id={sample_id}")

    async def clear_protein_quantifications_for_sample(self, sample_id: int) -> None:
        """
        Delete LFQ quantification records for a given sample.
        """
        await self._execute("""
            DELETE FROM protein_quantification_result
            WHERE protein_identification_id IN (
                SELECT id FROM protein_identification_result WHERE sample_id = ?
            )
        """, (int(sample_id),))
        await self.save()
        logger.info(f"Cleared protein quantifications for sample_id={sample_id}")
