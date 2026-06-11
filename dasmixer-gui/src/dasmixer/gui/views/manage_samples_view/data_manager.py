"""SampleDataManager — encapsulates sample stats caching and refresh operations."""

from dasmixer.api.project.project import Project
from dasmixer.api.project.dataclasses import Sample


class SampleDataManager:
    """Manages sample data loading, caching, and refresh operations."""

    def __init__(self, project: Project):
        self.project = project

    async def load_all(self) -> tuple[list[Sample], dict[int, dict], int]:
        """Load samples, all cached stats, and tools count.
        Returns (samples, cached_stats_dict, tools_count)."""
        samples = await self.project.get_samples()
        tools_count = await self.project.get_tools_count()
        all_cached = await self.project.get_all_cached_sample_stats()
        return samples, all_cached, tools_count

    async def refresh_single(self, sample_id: int, save_cache: bool = True) -> tuple:
        """Recalculate stats for one sample, update cache.
        Returns (sample, stats)."""
        from dasmixer.api.project.dataclasses import Sample
        sample = await self.project.get_sample(sample_id)
        if sample is None:
            return None, {}
        stats = await self.project.get_sample_stats(sample_id)
        if save_cache:
            await self.project.upsert_sample_status_cache(sample_id, stats)
            await self.project.save()
        return sample, stats

    async def refresh_all_fresh(self) -> tuple[list[Sample], dict[int, dict], int]:
        """Full recalculation of all samples (Update mode).
        Calls get_sample_stats for each, upserts cache, saves project.
        Returns (samples, cached_stats, tools_count)."""
        samples = await self.project.get_samples()
        tools_count = await self.project.get_tools_count()
        all_cached: dict[int, dict] = {}
        for sample in samples:
            sid = int(sample.id or 0)
            stats = await self.project.get_sample_stats(sid)
            await self.project.upsert_sample_status_cache(sid, stats)
            all_cached[sid] = stats
        await self.project.save()
        return samples, all_cached, tools_count

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
