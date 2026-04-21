"""Base class for Project with low-level database operations."""

import aiosqlite
import json
import pickle
import gzip
from pathlib import Path
from typing import Any

from dasmixer.utils.logger import logger


class ProjectBase:
    """
    Base class providing low-level database operations.
    
    All mixins inherit from this class to access database connection
    and common utility methods.
    """
    
    def __init__(
        self,
        path: Path | str | None = None,
        create_if_not_exists: bool = True
    ):
        """
        Initialize project base.
        
        Args:
            path: Path to project file (.dasmix). If None, creates in-memory project.
            create_if_not_exists: If True and path doesn't exist, creates new project.
                                  If False and path doesn't exist, raises FileNotFoundError.
        """
        if path is None:
            self.path = None
            self._db_path = ":memory:"
        else:
            self.path = Path(path)
            self._db_path = str(self.path)
            
            if not create_if_not_exists and not self.path.exists():
                raise FileNotFoundError(f"Project file not found: {self.path}")
        
        self._db: aiosqlite.Connection | None = None
        self._initialized = False
    
    # Low-level database operations
    
    async def _execute(self, query: str, params: tuple | dict | None = None) -> aiosqlite.Cursor:
        """Execute a query."""
        if not self._db:
            raise RuntimeError("Project not initialized")
        return await self._db.execute(query, params or ())
    
    async def _executemany(self, query: str, params_list: list) -> aiosqlite.Cursor:
        """Execute a query with multiple parameter sets."""
        if not self._db:
            raise RuntimeError("Project not initialized")
        return await self._db.executemany(query, params_list)

    async def _commit(self) -> None:
        """
        Lightweight commit for hot-path batch loops.

        Unlike save(), this does NOT update project_metadata.modified_at.
        Use it inside tight batch loops where every fsync matters.
        Call save() once at the end of the full operation to persist
        the modified_at timestamp.
        """
        if not self._db:
            raise RuntimeError("Project not initialized")
        await self._db.commit()
    
    async def _fetchone(self, query: str, params: tuple | dict | None = None) -> dict | None:
        """Fetch one row as dictionary."""
        cursor = await self._execute(query, params)
        row = await cursor.fetchone()
        return dict(row) if row else None
    
    async def _fetchall(self, query: str, params: tuple | dict | None = None) -> list[dict]:
        """Fetch all rows as list of dictionaries."""
        cursor = await self._execute(query, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    
    # Common utility methods
    
    @staticmethod
    def _serialize_json(data: Any) -> str | None:
        """Serialize data to JSON string."""
        if data is None:
            return None
        return json.dumps(data)
    
    @staticmethod
    def _deserialize_json(json_str: str | None) -> Any:
        """Deserialize JSON string to Python object."""
        if json_str is None:
            return None
        return json.loads(json_str)
    
    @staticmethod
    def _serialize_pickle_gzip(obj: Any) -> bytes | None:
        """Serialize object using pickle + gzip compression."""
        if obj is None:
            return None
        try:
            pickled = pickle.dumps(obj)
            return gzip.compress(pickled)
        except Exception as e:
            logger.error(f"Error serializing object: {e}")
            return None
    
    @staticmethod
    def _deserialize_pickle_gzip(blob: bytes | None) -> Any:
        """Deserialize pickle + gzip compressed object."""
        if blob is None:
            return None
        try:
            decompressed = gzip.decompress(blob)
            return pickle.loads(decompressed)
        except Exception as e:
            logger.error(f"Error deserializing object: {e}")
            return None
