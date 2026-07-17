"""SampleDataManager — encapsulates sample stats loading and refresh operations."""

from dasmixer.api.project.project import Project
from dasmixer.api.project.dataclasses import Sample


class SampleDataManager:
    """Manages sample data loading and refresh operations.

    Note: sample_status_cache is no longer used for reads or writes by this
    manager — get_all_samples_stats() is fast enough (~0.6s on 2.6M-row
    projects) to compute fresh on every load. The cache table itself is kept
    in the schema for backward compatibility but is not touched here.
    """

    def __init__(self, project: Project):
        self.project = project

    async def load_all(self) -> tuple[list[Sample], dict[int, dict], int]:
        """Load samples, fresh aggregated stats, and tools count.
        Returns (samples, stats_dict, tools_count)."""
        samples = await self.project.get_samples()
        tools_count = await self.project.get_tools_count()
        all_stats = await self.project.get_all_samples_stats()
        return samples, all_stats, tools_count

    async def refresh_single(self, sample_id: int) -> tuple:
        """Recalculate stats for one sample.
        Returns (sample, stats). Does NOT write to sample_status_cache."""
        sample = await self.project.get_sample(sample_id)
        if sample is None:
            return None, {}
        stats = await self.project.get_sample_stats(sample_id)
        return sample, stats

    async def refresh_all_fresh(self) -> tuple[list[Sample], dict[int, dict], int]:
        """Full recalculation of all samples (Update mode).
        Equivalent to load_all() now that the aggregated query is fast
        enough to run on every load.
        Returns (samples, stats_dict, tools_count)."""
        return await self.load_all()

    async def get_sample_detail(self, sample_id: int) -> list[dict]:
        """Delegate to project.get_sample_detail."""
        return await self.project.get_sample_detail(sample_id)

    async def drop_empty_files(self) -> tuple[int, int]:
        """Delete spectra and identification files with no data.
        Returns (deleted_spectra, deleted_idents)."""
        deleted_spectra = 0
        deleted_idents = 0

        # Find empty identification files
        rows = await self.project._fetchall(
            "SELECT id FROM identification_file WHERE NOT EXISTS "
            "(SELECT 1 FROM identification WHERE ident_file_id = identification_file.id)"
        )
        for row in rows:
            await self.project.delete_identification_file(row['id'])
            deleted_idents += 1

        # Find empty spectra files
        rows = await self.project._fetchall(
            "SELECT id FROM spectre_file WHERE NOT EXISTS "
            "(SELECT 1 FROM spectre WHERE spectre_file_id = spectre_file.id)"
        )
        for row in rows:
            await self.project.delete_spectra_file(row['id'])
            deleted_spectra += 1

        return deleted_spectra, deleted_idents
