"""Mixin for sample operations."""

from ..dataclasses import Sample
from utils.logger import logger


class SampleMixin:
    """
    Mixin providing sample management methods.
    
    Requires ProjectBase functionality and SubsetMixin (get_subset).
    """
    
    async def add_sample(
        self,
        name: str,
        subset_id: int | None = None,
        additions: dict | None = None
    ) -> Sample:
        """
        Add a new sample.
        
        Args:
            name: Unique sample name
            subset_id: FK to subset (comparison group)
            additions: Additional metadata (albumin, total_protein, etc.)
            
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
            "INSERT INTO sample (name, subset_id, additions) VALUES (?, ?, ?)",
            (name, subset_id, additions_json)
        )
        
        sample_id = cursor.lastrowid
        await self.save()
        
        logger.info(f"Added sample: {name} (id={sample_id})")
        
        return Sample(
            id=sample_id,
            name=name,
            subset_id=subset_id,
            additions=additions
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
            "UPDATE sample SET name = ?, subset_id = ?, additions = ? WHERE id = ?",
            (sample.name, sample.subset_id, additions_json, sample.id)
        )
        await self.save()
        logger.debug(f"Updated sample: {sample.name}")
    
    async def delete_sample(self, sample_id: int) -> None:
        """Delete sample (cascades to spectra files)."""
        await self._execute("DELETE FROM sample WHERE id = ?", (sample_id,))
        await self.save()
        logger.info(f"Deleted sample id={sample_id}")
