"""Main Project class for DASMixer."""

import aiosqlite
import json
import pickle
import gzip
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator
import pandas as pd
import numpy as np

from .schema import CREATE_SCHEMA_SQL, DEFAULT_METADATA
from .dataclasses import Subset, Tool, Sample, Protein
from .array_utils import compress_array, decompress_array
from utils.logger import logger


# Helper functions for uniprot_data serialization/deserialization

def _serialize_uniprot_data(uniprot_data) -> bytes | None:
    """Serialize UniprotData object to compressed blob."""
    if uniprot_data is None:
        return None
    try:
        pickled = pickle.dumps(uniprot_data)
        return gzip.compress(pickled)
    except Exception as e:
        logger.error(f"Error serializing uniprot_data: {e}")
        return None


def _deserialize_uniprot_data(blob: bytes | None):
    """Deserialize compressed blob to UniprotData object."""
    if blob is None:
        return None
    try:
        decompressed = gzip.decompress(blob)
        return pickle.loads(decompressed)
    except Exception as e:
        logger.error(f"Error deserializing uniprot_data: {e}")
        return None


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
        type: str,  # "Library" or "De Novo"
        parser: str,  # Parser name
        settings: dict | None = None,
        display_color: str | None = None
    ) -> Tool:
        """
        Add a new identification tool.
        
        Args:
            name: Tool name (unique)
            type: Tool type - "Library" or "De Novo"
            parser: Parser name (e.g., "PowerNovo2", "MaxQuant")
            settings: Tool-specific settings (JSON)
            display_color: Color for UI display
            
        Returns:
            Created Tool object
        """
        # Check if exists
        existing = await self._fetchone(
            "SELECT id FROM tool WHERE name = ?",
            (name,)
        )
        if existing:
            raise ValueError(f"Tool with name '{name}' already exists")
        
        settings_json = json.dumps(settings) if settings else None
        
        cursor = await self._execute(
            "INSERT INTO tool (name, type, parser, settings, display_color) VALUES (?, ?, ?, ?, ?)",
            (name, type, parser, settings_json, display_color)
        )
        
        tool_id = cursor.lastrowid
        await self.save()
        
        logger.info(f"Added tool: {name} (id={tool_id}, type={type}, parser={parser})")
        
        return Tool(
            id=tool_id,
            name=name,
            type=type,
            parser=parser,
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
            "UPDATE tool SET name = ?, type = ?, parser = ?, settings = ?, display_color = ? WHERE id = ?",
            (tool.name, tool.type, tool.parser, settings_json, tool.display_color, tool.id)
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
                int(row['charge']) if row.get('charge') is not None and not np.isnan(row.get('charge')) else None,
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
            (int(spectrum_id),)
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
    ) -> list[dict[str, int]]:
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
        """
        print(f'getting idlist: by {by} for id: {spectra_file_id}')
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
        
        rows = await self._fetchall(query, (int(spectra_file_id),))
        
        return [{by: row[by], 'spectre_id': row['id']} for row in rows]
    

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
        spectra_ids = self.get_spectra_idlist(file_id, parser.spectra_id_field)
        async for data, _ in parser.parse_batch(batch_size=batch_size):
            res = pd.merge(spectra_ids, data, on=parser.spectra_id_field)
            await self.add_identifications_batch(res)

    
    async def get_identifications(
        self,
        spectra_file_id: int | None = None,
        tool_id: int | None = None,
        sample_id: int | None = None,
        only_prefered: bool = False,
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
        
        if conditions:
            query_parts.append("WHERE " + " AND ".join(conditions))
        
        query_parts.append("ORDER BY i.id")
        
        if limit is not None:
            query_parts.append(f"LIMIT {limit} OFFSET {offset}")
        
        query = " ".join(query_parts)
        rows = await self._fetchall(query, tuple(params) if params else None)
        
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

    async def set_preferred_identifications_for_file(self, spectra_file_id: int, preferred_ids: list[int]) -> None:
        ids_df = await self.get_identifications(spectra_file_id)
        ids = list(ids_df["id"])
        await self._execute(
            f"UPDATE identification SET is_preferred = 0 WHERE id in ({', '.join(ids)})",
        )
        await self._execute(
            f"UPDATE identification SET is_preferred = 1 WHERE id in ({', '.join([str(x) for x in preferred_ids])})",
        )

    # Peptide match operations
    
    async def clear_peptide_matches(self) -> None:
        """Clear all peptide matches (for re-mapping)."""
        await self._execute("DELETE FROM peptide_match")
        await self.save()
        logger.info("Cleared all peptide matches")
    
    async def add_peptide_matches_batch(self, matches_df: pd.DataFrame) -> None:
        """
        Add batch of peptide matches.
        
        Args:
            matches_df: DataFrame with columns:
                - protein_id: str
                - identification_id: int
                - matched_sequence: str
                - identity: float
                - matched_ppm: float | None
                - matched_theor_mass: float | None
                - unique_evidence: bool | None
                - matched_coverage_percent: float | None
        """
        rows_to_insert = []
        
        for _, row in matches_df.iterrows():
            rows_to_insert.append((
                row['protein_id'],
                int(row['identification_id']),
                row['matched_sequence'],
                float(row['identity']),
                float(row['matched_ppm']) if row.get('matched_ppm') is not None else None,
                float(row['matched_theor_mass']) if row.get('matched_theor_mass') is not None else None,
                1 if row.get('unique_evidence', False) else 0,
                float(row['matched_coverage_percent']) if row.get('matched_coverage_percent') is not None else None
            ))
        
        if rows_to_insert:
            await self._executemany(
                """INSERT INTO peptide_match 
                   (protein_id, identification_id, matched_sequence, identity,
                    matched_ppm, matched_theor_mass, unique_evidence, matched_coverage_percent)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                rows_to_insert
            )
            # Note: No auto-save for batch efficiency
            logger.debug(f"Added {len(rows_to_insert)} peptide matches")
    
    async def get_peptide_matches(
        self,
        protein_id: str | None = None,
        identification_id: int | None = None
    ) -> pd.DataFrame:
        """Get peptide matches as DataFrame."""
        query_parts = ["SELECT * FROM peptide_match"]
        
        conditions = []
        params = []
        
        if protein_id is not None:
            conditions.append("protein_id = ?")
            params.append(protein_id)
        
        if identification_id is not None:
            conditions.append("identification_id = ?")
            params.append(identification_id)
        
        if conditions:
            query_parts.append("WHERE " + " AND ".join(conditions))
        
        query_parts.append("ORDER BY id")
        
        query = " ".join(query_parts)
        rows = await self._fetchall(query, tuple(params) if params else None)
        
        return pd.DataFrame(rows) if rows else pd.DataFrame()
    
    async def update_peptide_match_metrics(
        self,
        match_id: int,
        matched_ppm: float | None = None,
        matched_coverage_percent: float | None = None
    ) -> None:
        """
        Update metrics for a peptide match.
        
        Args:
            match_id: Peptide match ID
            matched_ppm: PPM error for matched sequence
            matched_coverage_percent: Ion coverage for matched sequence
        """
        updates = []
        params = []
        
        if matched_ppm is not None:
            updates.append("matched_ppm = ?")
            params.append(float(matched_ppm))
        
        if matched_coverage_percent is not None:
            updates.append("matched_coverage_percent = ?")
            params.append(float(matched_coverage_percent))
        
        if not updates:
            return
        
        params.append(int(match_id))
        
        query = f"UPDATE peptide_match SET {', '.join(updates)} WHERE id = ?"
        await self._execute(query, tuple(params))
        # Note: No auto-save for batch efficiency
    
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
            name: Short protein name (NEW)
            uniprot_data: UniprotData object (NEW)
        """
        # Serialize uniprot_data
        uniprot_blob = _serialize_uniprot_data(uniprot_data)
        
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
                uniprot_blob = _serialize_uniprot_data(row['uniprot_data'])
            
            rows_to_insert.append((
                row['id'],
                1 if row.get('is_uniprot', False) else 0,
                row.get('fasta_name'),
                row.get('sequence'),
                row.get('gene'),
                row.get('name'),  # NEW
                uniprot_blob  # NEW
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
        uniprot_data = _deserialize_uniprot_data(row.get('uniprot_data'))
        
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
            uniprot_data = _deserialize_uniprot_data(row.get('uniprot_data'))
            
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
        Special function to get Protein data to apply search with npysearch
        :return: dict {protein_id: sequence} for full protein DB loaded
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
    
    # NEW: Advanced query methods for peptides
    
    async def get_joined_peptide_data(
        self,
        is_preferred: bool | None = None,
        sequence_identified: bool | None = None,
        protein_identified: bool | None = None,
        sample: str | None = None,
        subset: str | None = None,
        sample_id: int | None = None,
        subset_id: int | None = None,
        sequence: str | None = None,
        canonical_sequence: str | None = None,
        matched_sequence: str | None = None,
        seq_no: int | None = None,
        scans: int | None = None,
        tool: str | None = None,
        tool_id: int | None = None
    ) -> pd.DataFrame:
        """
        Get joined peptide data with optional filtering.
        
        Joins spectre, identification, and peptide_match tables with
        sample/subset/tool information. Applies filters via SQL WHERE clauses.
        
        Args:
            is_preferred: Filter by is_preferred = true
            sequence_identified: Filter by sequence IS NOT NULL
            protein_identified: Filter by protein_id IS NOT NULL
            sample: Filter by sample name (exact match)
            subset: Filter by subset name (exact match)
            sample_id: Filter by sample ID
            subset_id: Filter by subset ID
            sequence: Filter by sequence (LIKE %value%)
            canonical_sequence: Filter by canonical_sequence (LIKE %value%)
            matched_sequence: Filter by matched_sequence (LIKE %value%)
            seq_no: Filter by spectrum sequence number (exact)
            scans: Filter by scans value (exact)
            tool: Filter by tool name (exact match)
            tool_id: Filter by tool ID
        
        Returns:
            DataFrame with columns:
                - sample, subset, sample_id, subset_id
                - seq_no, scans, charge, rt, pepmass, intensity
                - tool, tool_id, identification_id
                - sequence, canonical_sequence, ppm, is_preferred
                - matched_sequence, matched_ppm, protein_id, unique_evidence, gene
        """
        # Base query
        query = """
            SELECT
                sb.sample, sb.subset, sb.sample_id, sb.subset_id,
                s.id as spectre_id, s.seq_no, s.scans, s.charge, s.rt, s.pepmass, s.intensity,
                id.tool, id.tool_id, id.identification_id, id.sequence, 
                id.canonical_sequence, id.ppm, id.is_preferred,
                mp.matched_sequence, mp.matched_ppm, mp.protein_id, 
                mp.unique_evidence, mp.gene
            FROM
                spectre AS s
            LEFT JOIN
                (SELECT 
                    sm.id AS sample_id, 
                    f.id AS spectre_file_id, 
                    sm.name AS sample, 
                    sb.name AS subset, 
                    sb.id AS subset_id 
                 FROM sample sm, subset sb, spectre_file f 
                 WHERE sm.subset_id = sb.id AND f.sample_id = sm.id) AS sb
                ON sb.spectre_file_id = s.spectre_file_id
            LEFT JOIN
                (SELECT 
                    i.spectre_id, 
                    t.name AS tool, 
                    t.id AS tool_id, 
                    i.id AS identification_id, 
                    i.sequence, 
                    i.canonical_sequence, 
                    i.ppm, 
                    i.is_preferred 
                 FROM identification i, tool t 
                 WHERE t.id = i.tool_id) AS id 
                ON id.spectre_id = s.id
            LEFT JOIN
                (SELECT 
                    m.matched_sequence, 
                    m.matched_ppm, 
                    m.protein_id, 
                    m.identification_id, 
                    m.unique_evidence, 
                    p.gene
                 FROM peptide_match m, protein p 
                 WHERE p.id = m.protein_id) AS mp 
                ON mp.identification_id = id.identification_id
            WHERE 1=1
        """
        
        # Build filter conditions and parameters
        conditions = []
        params = []
        
        if is_preferred is not None:
            conditions.append("id.is_preferred = ?")
            params.append(1 if is_preferred else 0)
        
        if sequence_identified is not None:
            if sequence_identified:
                conditions.append("id.sequence IS NOT NULL")
            else:
                conditions.append("id.sequence IS NULL")
        
        if protein_identified is not None:
            if protein_identified:
                conditions.append("mp.protein_id IS NOT NULL")
            else:
                conditions.append("mp.protein_id IS NULL")
        
        if sample is not None:
            conditions.append("sb.sample = ?")
            params.append(sample)
        
        if subset is not None:
            conditions.append("sb.subset = ?")
            params.append(subset)
        
        if sample_id is not None:
            conditions.append("sb.sample_id = ?")
            params.append(sample_id)
        
        if subset_id is not None:
            conditions.append("sb.subset_id = ?")
            params.append(subset_id)
        
        if sequence is not None:
            conditions.append("id.sequence LIKE ?")
            params.append(f"%{sequence}%")
        
        if canonical_sequence is not None:
            conditions.append("id.canonical_sequence LIKE ?")
            params.append(f"%{canonical_sequence}%")
        
        if matched_sequence is not None:
            conditions.append("mp.matched_sequence LIKE ?")
            params.append(f"%{matched_sequence}%")
        
        if seq_no is not None:
            conditions.append("s.seq_no = ?")
            params.append(seq_no)
        
        if scans is not None:
            conditions.append("s.scans = ?")
            params.append(scans)
        
        if tool is not None:
            conditions.append("id.tool = ?")
            params.append(tool)
        
        if tool_id is not None:
            conditions.append("id.tool_id = ?")
            params.append(tool_id)
        
        # Add conditions to query
        if conditions:
            query += " AND " + " AND ".join(conditions)
        
        # Execute query
        return await self.execute_query_df(query, tuple(params) if params else None)
    
    async def get_spectrum_plot_data(self, spectrum_id: int) -> dict:
        """
        Get all data needed to plot spectrum with all identifications.
        
        Returns spectrum arrays and all identification sequences for this spectrum,
        ready to be unpacked into make_full_spectrum_plot().
        
        Args:
            spectrum_id: Spectrum ID
        
        Returns:
            Dictionary with keys:
                - mz: list[float] - m/z array
                - intensity: list[float] - intensity array
                - charges: list[int] | int - charge array or single charge
                - sequences: list[str] - all identified sequences for this spectrum
                - headers: list[str] - formatted headers for each sequence
                    Format: "{tool_name} | Score: {score:.2f} | PPM: {ppm:.2f}"
                - spectrum_info: dict - spectrum metadata
                    - seq_no: int
                    - scans: int
                    - rt: float
                    - pepmass: float
                    - charge: int
        
        Example:
            >>> data = await project.get_spectrum_plot_data(123)
            >>> from api.spectra.plot_flow import make_full_spectrum_plot
            >>> from api.spectra.ion_match import IonMatchParameters
            >>> 
            >>> params = IonMatchParameters(ions=['b', 'y'], tolerance=20.0)
            >>> fig = make_full_spectrum_plot(
            ...     params=params,
            ...     **data  # Unpack dict directly
            ... )
        """
        # Get spectrum with arrays
        spectrum = await self.get_spectrum_full(spectrum_id)
        
        # Get all identifications for this spectrum
        query = """
            SELECT 
                i.sequence, i.score, i.ppm, i.is_preferred,
                t.name AS tool_name
            FROM identification i
            JOIN tool t ON i.tool_id = t.id
            WHERE i.spectre_id = ?
            ORDER BY i.is_preferred DESC, i.score DESC
        """
        ident_rows = await self._fetchall(query, (spectrum_id,))
        
        # Build sequences and headers
        sequences = []
        headers = []
        
        for row in ident_rows:
            sequences.append(row['sequence'])
            
            # Format header
            score_str = f"{row['score']:.2f}" if row['score'] is not None else "N/A"
            ppm_str = f"{row['ppm']:.2f}" if row['ppm'] is not None else "N/A"
            pref_marker = "★ " if row['is_preferred'] else ""
            
            header = f"{pref_marker}{row['tool_name']} | Score: {score_str} | PPM: {ppm_str}"
            headers.append(header)
        
        # Determine charges
        if spectrum.get('charge_array') is not None:
            charges = spectrum['charge_array'].tolist()
        elif spectrum.get('charge_array_common_value') is not None:
            charges = int(spectrum['charge_array_common_value'])
        elif spectrum.get('charge') is not None:
            charges = int(spectrum['charge'])
        else:
            charges = 1  # Default fallback
        
        # Return data ready for unpacking
        return {
            'mz': spectrum['mz_array'].tolist(),
            'intensity': spectrum['intensity_array'].tolist(),
            'charges': charges,
            'sequences': sequences,
            'headers': headers,
            'spectrum_info': {
                'seq_no': spectrum['seq_no'],
                'scans': spectrum.get('scans'),
                'rt': spectrum.get('rt'),
                'pepmass': spectrum['pepmass'],
                'charge': spectrum.get('charge')
            }
        }

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
    
    async def get_protein_results_joined(
        self,
        sample: str | None = None,
        limit=100,
        offset=0
    ) -> pd.DataFrame:
        """
        Get joined protein identification and quantification results.
        
        Returns one row per protein_identification_result with
        pivoted columns for each LFQ method.
        
        Args:
            sample: Optional filter by sample name
        
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
        """
        
        params = None
        
        if sample is not None:
            query += " WHERE s.name = ?"
            params = (sample, )
        
        query += " ORDER BY s.name, pir.protein_id"
        query += f" LIMIT {offset} {limit}"
        
        df = await self.execute_query_df(query, params)
        
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
