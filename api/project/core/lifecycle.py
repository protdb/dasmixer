"""Project lifecycle management - initialization, save, close."""

import aiosqlite
from datetime import datetime
from pathlib import Path

from flet.controls.core import row

from .base import ProjectBase
from ..schema import CREATE_SCHEMA_SQL, DEFAULT_METADATA
from utils.logger import logger


class ProjectLifecycle(ProjectBase):
    """
    Extends ProjectBase with lifecycle management methods.
    
    Handles database initialization, saving, closing, and context manager protocol.
    """
    
    async def initialize(self) -> None:
        """Initialize database connection and create schema if needed."""
        if self._initialized:
            logger.warning("Project already initialized")
            return
        
        try:
            self._db = await aiosqlite.connect(self._db_path)
            self._db.row_factory = aiosqlite.Row
            
            # Enable foreign keys
            await self._db.execute("PRAGMA foreign_keys = ON")
            
            # Create schema
            await self._db.executescript(CREATE_SCHEMA_SQL)
            await self._db.commit()
            
            # Initialize metadata if new database
            metadata = await self.get_metadata()
            if 'version' not in metadata:
                now = datetime.now().isoformat()
                for key, value in DEFAULT_METADATA.items():
                    if value is None:
                        value = now
                    await self._execute(
                        "INSERT OR REPLACE INTO project_metadata (key, value) VALUES (?, ?)",
                        (key, value)
                    )
                await self._db.commit()
                logger.info(f"Created new project: {self._db_path}")
            else:
                logger.info(f"Opened existing project: {self._db_path}")
            
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize project: {e}", exc_info=True)
            if self._db:
                await self._db.close()
            raise
    
    async def close(self) -> None:
        """Close database connection."""
        if self._db:
            await self._db.commit()
            await self._db.close()
            self._db = None
            self._initialized = False
            logger.info("Project closed")
    
    async def __aenter__(self) -> 'ProjectLifecycle':
        """Context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - auto-saves and closes."""
        await self.close()
    
    async def save(self) -> None:
        """Save current state (commit transaction)."""
        if not self._db:
            raise RuntimeError("Project not initialized")
        
        # Update modified_at
        now = datetime.now().isoformat()
        await self._execute(
            "INSERT OR REPLACE INTO project_metadata (key, value) VALUES (?, ?)",
            ('modified_at', now)
        )
        
        await self._db.commit()
        logger.debug("Project saved")
    
    async def save_as(self, path: Path | str) -> None:
        """
        Save project to a new file.
        
        Args:
            path: New file path
        """
        if not self._db:
            raise RuntimeError("Project not initialized")
        
        new_path = Path(path)
        
        # Use SQLite backup API
        if self.path:
            # Close current connection
            await self.save()
            await self._db.close()
            
            # Copy file
            import shutil
            shutil.copy2(self.path, new_path)
            
            # Reopen with new path
            self.path = new_path
            self._db_path = str(self.path)
            self._initialized = False
            await self.initialize()
        else:
            # In-memory database - use backup
            new_db = await aiosqlite.connect(str(new_path))
            await self._db.backup(new_db)
            await new_db.close()
            
            # Update paths
            self.path = new_path
            self._db_path = str(self.path)
        
        logger.info(f"Project saved as: {new_path}")
    
    async def get_metadata(self) -> dict:
        """
        Get project metadata.
        
        Returns:
            dict: Project metadata including creation date, version, etc.
        """
        rows = await self._fetchall("SELECT key, value FROM project_metadata")
        return {row['key']: row['value'] for row in rows}
    
    async def set_setting(self, key: str, value: str) -> None:
        """Set a project setting."""
        await self._execute(
            "INSERT OR REPLACE INTO project_settings (key, value) VALUES (?, ?)",
            (key, value)
        )
        await self.save()
    
    async def get_setting(self, key: str, default: str | None = None) -> str | None:
        """Get a project setting."""
        row = await self._fetchone(
            "SELECT value FROM project_settings WHERE key = ?",
            (key,)
        )
        return row['value'] if row else default

    async def get_all_settings(self) -> dict:
        res = await self._fetchall("SELECT key, value FROM project_settings")
        return {r['key']: r['value'] for r in res}
