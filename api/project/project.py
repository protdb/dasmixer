"""Main Project class for DASMixer."""

import aiosqlite
import json
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator
import pandas as pd
import numpy as np

from .schema import CREATE_SCHEMA_SQL, DEFAULT_METADATA
from .dataclasses import Subset, Tool, Sample, Protein
from .array_utils import compress_array, decompress_array
from utils.logger import logger


class Project:
    """
    Main class for managing DASMixer project data.
    
    Project is stored as a single SQLite database file.
    All methods are async to prevent UI blocking.
    
    Usage:
        # Create or open
        project = Project(path="my_project.dasmix", create_if_not_exists=True)
        await project.initialize()
        
        # Use as context manager
        async with Project(path="my_project.dasmix") as project:
            await project.add_sample(...)
    """
    
    def __init__(
        self,
        path: Path | str | None = None,
        create_if_not_exists: bool = True
    ):
        """
        Initialize project.
        
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
    
    async def __aenter__(self) -> 'Project':
        """Context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - auto-saves and closes."""
        await self.close()
    
    # Helper methods for database operations
    
    async def _execute(self, query: str, params: tuple | dict | None = None) -> aiosqlite.Cursor:
        """Execute a query."""
        if not self._db:
            raise RuntimeError("Project not initialized")
        print(query)
        print(params)
        return await self._db.execute(query, params or ())
    
    async def _executemany(self, query: str, params_list: list) -> aiosqlite.Cursor:
        """Execute a query with multiple parameter sets."""
        if not self._db:
            raise RuntimeError("Project not initialized")
        return await self._db.executemany(query, params_list)
    
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
    
    # Project management methods
    
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
    
    # Subset operations
    
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
    
    # Tool operations
    
    async def add_tool(
        self,
        name: str,
        type: str,
        settings: dict | None = None,
        display_color: str | None = None
    ) -> Tool:
        """Add a new identification tool."""
        # Check if exists
        existing = await self._fetchone(
            "SELECT id FROM tool WHERE name = ?",
            (name,)
        )
        if existing:
            raise ValueError(f"Tool with name '{name}' already exists")
        
        settings_json = json.dumps(settings) if settings else None
        
        cursor = await self._execute(
            "INSERT INTO tool (name, type, settings, display_color) VALUES (?, ?, ?, ?)",
            (name, type, settings_json, display_color)
        )
        
        tool_id = cursor.lastrowid
        await self.save()
        
        logger.info(f"Added tool: {name} (id={tool_id}, type={type})")
        
        return Tool(
            id=tool_id,
            name=name,
            type=type,
            settings=settings,
            display_color=display_color
        )
    
    async def get_tools(self) -> list[Tool]:
        """Get all tools."""
        rows = await self._fetchall("SELECT * FROM tool ORDER BY name")
        return [Tool.from_dict(row) for row in rows]
    
    async def get_tool(self, tool_id: int) -> Tool | None:
        """Get tool by ID."""
        row = await self._fetchone(
            "SELECT * FROM tool WHERE id = ?",
            (tool_id,)
        )
        return Tool.from_dict(row) if row else None
    
    async def update_tool(self, tool: Tool) -> None:
        """Update existing tool."""
        if tool.id is None:
            raise ValueError("Cannot update tool without ID")
        
        settings_json = json.dumps(tool.settings) if tool.settings else None
        
        await self._execute(
            "UPDATE tool SET name = ?, type = ?, settings = ?, display_color = ? WHERE id = ?",
            (tool.name, tool.type, settings_json, tool.display_color, tool.id)
        )
        await self.save()
        logger.debug(f"Updated tool: {tool.name}")
    
    async def delete_tool(self, tool_id: int) -> None:
        """Delete tool (if no identifications associated)."""
        # Check for associated identifications
        count_row = await self._fetchone(
            "SELECT COUNT(*) as cnt FROM identification WHERE tool_id = ?",
            (tool_id,)
        )
        
        if count_row and count_row['cnt'] > 0:
            raise ValueError(
                f"Cannot delete tool: {count_row['cnt']} identifications are associated with it"
            )
        
        await self._execute("DELETE FROM tool WHERE id = ?", (tool_id,))
        await self.save()
        logger.info(f"Deleted tool id={tool_id}")
    
    # Sample operations
    
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
        
        additions_json = json.dumps(additions) if additions else None
        
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
        
        additions_json = json.dumps(sample.additions) if sample.additions else None
        
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
    
    # Spectra file operations
    
    async def add_spectra_file(
        self,
        sample_id: int,
        format: str,
        path: str
    ) -> int:
        """
        Add spectra file record.
        
        Args:
            sample_id: FK to sample
            format: File format (MGF, MZML, etc.)
            path: Original file path
            
        Returns:
            Created spectra_file ID
        """
        # Validate sample exists
        sample = await self.get_sample(sample_id)
        if sample is None:
            raise ValueError(f"Sample with id={sample_id} does not exist")
        
        cursor = await self._execute(
            "INSERT INTO spectre_file (sample_id, format, path) VALUES (?, ?, ?)",
            (sample_id, format, path)
        )
        
        spectra_file_id = cursor.lastrowid
        await self.save()
        
        logger.info(f"Added spectra file: {path} (id={spectra_file_id}, sample_id={sample_id})")
        
        return spectra_file_id
    
    async def get_spectra_files(self, sample_id: int | None = None) -> pd.DataFrame:
        """
        Get spectra files as DataFrame.
        
        Columns: id, sample_id, format, path, sample_name
        """
        if sample_id is not None:
            query = """
                SELECT sf.*, s.name as sample_name
                FROM spectre_file sf
                JOIN sample s ON sf.sample_id = s.id
                WHERE sf.sample_id = ?
                ORDER BY sf.id
            """
            rows = await self._fetchall(query, (sample_id,))
        else:
            query = """
                SELECT sf.*, s.name as sample_name
                FROM spectre_file sf
                JOIN sample s ON sf.sample_id = s.id
                ORDER BY sf.id
            """
            rows = await self._fetchall(query)
        
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    
    # Spectra operations (batch processing)
    
    async def add_spectra_batch(
        self,
        spectra_file_id: int,
        spectra_df: pd.DataFrame
    ) -> None:
        """
        Add batch of spectra to database.
        
        Args:
            spectra_file_id: FK to spectra_file
            spectra_df: DataFrame with columns:
                - seq_no: int
                - title: str
                - scans: int | None
                - charge: int | None
                - rt: float | None
                - pepmass: float
                - mz_array: np.ndarray
                - intensity_array: np.ndarray
                - charge_array: np.ndarray | None
                - charge_array_common_value: int | None
                - all_params: dict | None
        """
        rows_to_insert = []
        
        for _, row in spectra_df.iterrows():
            # Compress arrays
            mz_compressed = compress_array(row['mz_array']) if 'mz_array' in row and row['mz_array'] is not None else None
            intensity_compressed = compress_array(row['intensity_array']) if 'intensity_array' in row and row['intensity_array'] is not None else None
            charge_compressed = compress_array(row['charge_array']) if 'charge_array' in row and row['charge_array'] is not None else None
            
            # Serialize all_params
            all_params_json = json.dumps(row.get('all_params')) if row.get('all_params') else None
            
            # Calculate intensity if not provided
            intensity = row.get('intensity')
            if intensity is None and 'intensity_array' in row and row['intensity_array'] is not None:
                intensity = float(np.sum(row['intensity_array']))
            
            rows_to_insert.append((
                spectra_file_id,
                int(row['seq_no']),
                row.get('title'),
                int(row['scans']) if row.get('scans') is not None else None,
                int(row['charge']) if row.get('charge') is not None else None,
                float(row['rt']) if row.get('rt') is not None else None,
                float(row['pepmass']),
                intensity,
                mz_compressed,
                intensity_compressed,
                charge_compressed,
                int(row['charge_array_common_value']) if row.get('charge_array_common_value') is not None else None,
                all_params_json
            ))
        
        if rows_to_insert:
            await self._executemany(
                """INSERT INTO spectre 
                   (spectre_file_id, seq_no, title, scans, charge, rt, pepmass, intensity,
                    mz_array, intensity_array, charge_array, charge_array_common_value, all_params)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows_to_insert
            )
            await self.save()
            logger.info(f"Added {len(rows_to_insert)} spectra to file_id={spectra_file_id}")
    
    async def get_spectra(
        self,
        spectra_file_id: int | None = None,
        sample_id: int | None = None,
        limit: int | None = None,
        offset: int = 0
    ) -> pd.DataFrame:
        """
        Get spectra as DataFrame (without arrays for efficiency).
        
        Returns DataFrame with metadata only (no mz/intensity arrays).
        """
        query_parts = ["""
            SELECT s.id, s.spectre_file_id, s.seq_no, s.title, s.scans,
                   s.charge, s.rt, s.pepmass, s.intensity, s.charge_array_common_value,
                   sf.sample_id, sam.name as sample_name
            FROM spectre s
            JOIN spectre_file sf ON s.spectre_file_id = sf.id
            JOIN sample sam ON sf.sample_id = sam.id
        """]
        
        conditions = []
        params = []
        
        if spectra_file_id is not None:
            conditions.append("s.spectre_file_id = ?")
            params.append(spectra_file_id)
        
        if sample_id is not None:
            conditions.append("sf.sample_id = ?")
            params.append(sample_id)
        
        if conditions:
            query_parts.append("WHERE " + " AND ".join(conditions))
        
        query_parts.append("ORDER BY s.id")
        
        if limit is not None:
            query_parts.append(f"LIMIT {limit} OFFSET {offset}")
        
        query = " ".join(query_parts)
        rows = await self._fetchall(query, tuple(params) if params else None)
        
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    
    async def get_spectrum_full(self, spectrum_id: int) -> dict:
        """
        Get full spectrum data including arrays.
        
        Returns:
            dict with all fields including decompressed numpy arrays
        """
        row = await self._fetchone(
            "SELECT * FROM spectre WHERE id = ?",
            (spectrum_id,)
        )
        
        if not row:
            raise ValueError(f"Spectrum with id={spectrum_id} not found")
        
        result = dict(row)
        
        # Decompress arrays
        if result.get('mz_array'):
            result['mz_array'] = decompress_array(result['mz_array'])
        
        if result.get('intensity_array'):
            result['intensity_array'] = decompress_array(result['intensity_array'])
        
        if result.get('charge_array'):
            result['charge_array'] = decompress_array(result['charge_array'])
        
        # Deserialize all_params
        if result.get('all_params'):
            result['all_params'] = json.loads(result['all_params'])
        
        return result
    
    async def get_spectra_idlist(
        self,
        spectra_file_id: int,
        by: str = "seq_no"
    ) -> dict[int | str, int]:
        """
        Get mapping from seq_no or scans to spectrum database IDs.
        
        This method is essential for identification import workflow:
        1. Parse identification file (contains seq_no or scans references)
        2. Get mapping: seq_no/scans -> spectrum DB ID
        3. Enrich identification DataFrame with spectre_id
        4. Add identifications to database
        
        Args:
            spectra_file_id: Spectra file ID to get mapping for
            by: Field to use as key - "seq_no" or "scans"
            
        Returns:
            Dict mapping seq_no/scans value to spectrum database ID
            
        Raises:
            ValueError: If 'by' parameter is invalid
            
        Example:
            >>>async def your_function():
            >>>     # After importing spectra file
            >>>     mapping = await project.get_spectra_idlist(file_id, by="scans")
            >>>     # mapping = {1234: 5, 1235: 6, ...}  scans -> spectrum_id
            >>>
            >>>     # Use in identification import
            >>>     ident_df['spectre_id'] = ident_df['scans'].map(mapping)
            >>>     await project.add_identifications_batch(ident_df)
        """
        if by not in ("seq_no", "scans"):
            raise ValueError(
                f"Invalid 'by' parameter: {by}. Must be 'seq_no' or 'scans'"
            )
        
        query = f"""
            SELECT id, {by}
            FROM spectre
            WHERE spectre_file_id = ?
            AND {by} IS NOT NULL
        """
        
        rows = await self._fetchall(query, (spectra_file_id,))
        
        # Create mapping: seq_no/scans -> spectrum_id
        return {row[by]: row['id'] for row in rows}
    

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
            SELECT if.*, t.name as tool_name, t.type as tool_type
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
                positional_scores_json
            ))
        
        if rows_to_insert:
            await self._executemany(
                """INSERT INTO identification 
                   (spectre_id, tool_id, ident_file_id, is_preferred, sequence, canonical_sequence,
                    ppm, theor_mass, score, positional_scores)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows_to_insert
            )
            await self.save()
            logger.info(f"Added {len(rows_to_insert)} identifications")
    
    async def get_identifications(
        self,
        spectra_file_id: int | None = None,
        tool_id: int | None = None,
        sample_id: int | None = None
    ) -> pd.DataFrame:
        """Get identifications as DataFrame with joined metadata."""
        query_parts = ["""
            SELECT i.*, s.title as spectrum_title, s.pepmass, s.rt,
                   t.name as tool_name, t.type as tool_type,
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
        
        if conditions:
            query_parts.append("WHERE " + " AND ".join(conditions))
        
        query_parts.append("ORDER BY i.id")
        
        query = " ".join(query_parts)
        rows = await self._fetchall(query, tuple(params) if params else None)
        
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    
    # Protein operations
    
    async def add_protein(self, protein: Protein) -> None:
        """Add or update protein."""
        await self._execute(
            """INSERT OR REPLACE INTO protein (id, is_uniprot, fasta_name, sequence, gene)
               VALUES (?, ?, ?, ?, ?)""",
            (protein.id, 1 if protein.is_uniprot else 0, protein.fasta_name,
             protein.sequence, protein.gene)
        )
        await self.save()
        logger.debug(f"Added/updated protein: {protein.id}")
    
    async def add_proteins_batch(self, proteins_df: pd.DataFrame) -> None:
        """Add batch of proteins from DataFrame."""
        rows_to_insert = []
        
        for _, row in proteins_df.iterrows():
            rows_to_insert.append((
                row['id'],
                1 if row.get('is_uniprot', False) else 0,
                row.get('fasta_name'),
                row.get('sequence'),
                row.get('gene')
            ))
        
        if rows_to_insert:
            await self._executemany(
                """INSERT OR REPLACE INTO protein (id, is_uniprot, fasta_name, sequence, gene)
                   VALUES (?, ?, ?, ?, ?)""",
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
        return Protein.from_dict(row) if row else None
    
    async def get_proteins(self, is_uniprot: bool | None = None) -> list[Protein]:
        """Get proteins, optionally filtered."""
        if is_uniprot is not None:
            rows = await self._fetchall(
                "SELECT * FROM protein WHERE is_uniprot = ? ORDER BY id",
                (1 if is_uniprot else 0,)
            )
        else:
            rows = await self._fetchall("SELECT * FROM protein ORDER BY id")
        
        return [Protein.from_dict(row) for row in rows]
    
    # Low-level SQL API
    
    async def execute_query(
        self,
        query: str,
        params: tuple | dict | None = None
    ) -> list[dict]:
        """
        Execute raw SQL query.
        
        For complex reports and custom operations.
        
        Returns:
            List of rows as dictionaries
        """
        return await self._fetchall(query, params)
    
    async def execute_query_df(
        self,
        query: str,
        params: tuple | dict | None = None
    ) -> pd.DataFrame:
        """Execute query and return as DataFrame."""
        rows = await self._fetchall(query, params)
        return pd.DataFrame(rows) if rows else pd.DataFrame()
