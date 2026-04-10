"""Mixin for subset (comparison group) operations."""

from ..dataclasses import Subset
from dasmixer.utils.logger import logger


class SubsetMixin:
    """
    Mixin providing subset (comparison group) management methods.
    
    Requires ProjectBase functionality (_execute, _fetchone, _fetchall, save).
    """
    
    async def add_subset(
        self,
        name: str,
        details: str | None = None,
        display_color: str | None = None
    ) -> Subset:
        """
        Add a new comparison group.
        
        Args:
            name: Unique subset name
            details: Optional description
            display_color: Hex color for visualization
            
        Returns:
            Created Subset object
            
        Raises:
            ValueError: If subset with this name already exists
        """
        # Check if exists
        existing = await self._fetchone(
            "SELECT id FROM subset WHERE name = ?",
            (name,)
        )
        if existing:
            raise ValueError(f"Subset with name '{name}' already exists")
        
        cursor = await self._execute(
            "INSERT INTO subset (name, details, display_color) VALUES (?, ?, ?)",
            (name, details, display_color)
        )
        
        subset_id = cursor.lastrowid
        await self.save()
        
        logger.info(f"Added subset: {name} (id={subset_id})")
        
        return Subset(
            id=subset_id,
            name=name,
            details=details,
            display_color=display_color
        )
    
    async def get_subsets(self) -> list[Subset]:
        """Get all subsets."""
        rows = await self._fetchall("SELECT * FROM subset ORDER BY name")
        return [Subset.from_dict(row) for row in rows]
    
    async def get_subset(self, subset_id: int) -> Subset | None:
        """Get subset by ID."""
        row = await self._fetchone(
            "SELECT * FROM subset WHERE id = ?",
            (subset_id,)
        )
        return Subset.from_dict(row) if row else None
    
    async def update_subset(self, subset: Subset) -> None:
        """Update existing subset."""
        if subset.id is None:
            raise ValueError("Cannot update subset without ID")
        
        await self._execute(
            "UPDATE subset SET name = ?, details = ?, display_color = ? WHERE id = ?",
            (subset.name, subset.details, subset.display_color, subset.id)
        )
        await self.save()
        logger.debug(f"Updated subset: {subset.name}")
    
    async def delete_subset(self, subset_id: int) -> None:
        """
        Delete subset.
        
        Raises:
            ValueError: If subset has associated samples
        """
        # Check for associated samples
        count_row = await self._fetchone(
            "SELECT COUNT(*) as cnt FROM sample WHERE subset_id = ?",
            (subset_id,)
        )
        
        if count_row and count_row['cnt'] > 0:
            raise ValueError(
                f"Cannot delete subset: {count_row['cnt']} samples are associated with it"
            )
        
        await self._execute("DELETE FROM subset WHERE id = ?", (subset_id,))
        await self.save()
        logger.info(f"Deleted subset id={subset_id}")
