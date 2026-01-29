"""Table-based identification parsers for CSV, XLS, XLSX formats."""

import csv
from dataclasses import dataclass, asdict
from abc import ABC
from typing import AsyncIterator
import pandas as pd
import aiofiles
import aiocsv

from .base import IdentificationParser


class TableSheet:
    """
    Represents a single sheet from a workbook.
    
    Attributes:
        no: Sheet number (0-indexed)
        name: Sheet name (None for CSV files)
        data: DataFrame with sheet data
    """
    no: int
    name: str | None
    data: pd.DataFrame
    
    def __str__(self):
        cols_preview = list(self.data.columns)[:5]
        cols_str = ', '.join(cols_preview)
        if len(self.data.columns) > 5:
            cols_str += '...'
        return f'{self.no}: {self.name} ({len(self.data)} rows), cols: {cols_str}'


@dataclass
class ColumnRenames:
    """
    Column mapping configuration for table importers.
    
    Maps source column names to standard output column names.
    At least one of scans/seq_no must be mapped for spectrum matching.
    
    Attributes:
        scans: Source column name for scan numbers
        seq_no: Source column name for sequential spectrum numbers
        sequence: Source column name for peptide sequence with modifications
        canonical_sequence: Source column name for sequence without modifications
        score: Source column name for identification score
        positional_scores: Source column name for per-position confidence scores
        ppm: Source column name for mass error in ppm
        theor_mass: Source column name for theoretical mass
    """
    scans: str | None = None
    seq_no: str | None = None
    sequence: str = ''
    canonical_sequence: str | None = None
    score: str | None = None
    positional_scores: str | None = None
    ppm: str | None = None
    theor_mass: str | None = None


class TableImporter(IdentificationParser, ABC):
    """
    Base class for table imports.
    
    Supports parsing any data in tabular format: CSV, XLS, XLSX, ODS.
    Handles multi-sheet workbooks.
    
    Attributes:
        separator: CSV field separator (default ',')
        encoding: Text encoding (default 'utf-8')
        ignore_errors: How to handle encoding errors (default 'ignore')
        skiprows: Number of rows to skip at file start (default None)
        sheets: Loaded sheets from workbook (None until file is read)
    """
    separator: str = ','
    encoding: str = 'utf-8'
    ignore_errors: str = 'ignore'
    skiprows: int | None = None
    sheets: list[TableSheet] | None = None

    def get_sheet(
        self,
        *,
        name: str | None = None,
        no: int | None = None
    ) -> pd.DataFrame:
        """
        Get sheet data by name or number.
        
        Args:
            name: Sheet name to retrieve
            no: Sheet number (0-indexed) to retrieve
            
        Returns:
            DataFrame with sheet data
            
        Raises:
            ValueError: If sheets not loaded, or sheet not found
        """
        if self.sheets is None or len(self.sheets) == 0:
            raise ValueError("Sheets not loaded. Call _read_table() first.")
        
        if name is not None:
            try:
                return [x for x in self.sheets if x.name == name][0].data
            except IndexError:
                available = [s.name for s in self.sheets]
                raise ValueError(
                    f"No sheet with name '{name}'. Available sheets: {available}"
                )
        
        if no is not None:
            try:
                return [x for x in self.sheets if x.no == no][0].data
            except IndexError:
                raise ValueError(
                    f"No sheet with number {no}. Available: 0-{len(self.sheets)-1}"
                )
        
        # Return first sheet by default
        return self.sheets[0].data

    def _read_table(self):
        """
        Read table file into sheets.
        
        Supports CSV, XLS, XLSX, ODS formats.
        """
        suffix = self.file_path.suffix.lower()
        
        if suffix == '.csv':
            sheet = TableSheet()
            sheet.no = 0
            sheet.name = None
            sheet.data = pd.read_csv(
                self.file_path,
                sep=self.separator,
                encoding=self.encoding,
                encoding_errors=self.ignore_errors,
                skiprows=self.skiprows
            )
            self.sheets = [sheet]
            
        elif suffix in ('.xls', '.xlsx', '.ods'):
            self.sheets = []
            with pd.ExcelFile(self.file_path) as workbook:
                for no, sheet_name in enumerate(workbook.sheet_names):
                    sheet = TableSheet()
                    sheet.no = no
                    sheet.name = sheet_name
                    sheet.data = pd.read_excel(
                        workbook,
                        sheet_name=sheet_name,
                        skiprows=self.skiprows
                    )
                    self.sheets.append(sheet)
        else:
            raise ValueError(
                f"Unsupported file format: {suffix}. "
                "Supported: .csv, .xls, .xlsx, .ods"
            )


class SimpleTableImporter(TableImporter):
    """
    Simple table importer with column remapping.
    
    Uses ColumnRenames to map source columns to standard names.
    Suitable for most identification file formats.
    
    Attributes:
        renames: ColumnRenames configuration
        peptide_sheet_selector: Sheet selection (e.g., {'name': 'Peptides'} or {'no': 0})
    """
    renames: ColumnRenames
    peptide_sheet_selector: dict | None = None

    def remap_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Remap columns according to ColumnRenames configuration.
        
        Args:
            df: DataFrame with original column names
            
        Returns:
            DataFrame with standard column names
            
        Raises:
            ValueError: If neither scans nor seq_no can be mapped
        """
        r = asdict(self.renames)
        rename_cols = {v: k for k, v in r.items() if v is not None and v != ''}
        result = df.rename(columns=rename_cols)
        
        # Validate that at least one mapping column exists
        if 'scans' not in result.columns and 'seq_no' not in result.columns:
            raise ValueError(
                "Parser must provide at least one of 'scans' or 'seq_no' columns "
                f"for spectrum mapping. Available columns: {list(df.columns)}"
            )
        
        # Return only standard columns that exist
        available_cols = [col for col in r.keys() if col in result.columns]
        return result[available_cols]

    def transform_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform DataFrame before column remapping.
        
        Override in subclasses to perform format-specific transformations
        (e.g., parsing nested data, converting PTM notation).
        
        Args:
            df: DataFrame with original column names
            
        Returns:
            Transformed DataFrame (still with original column names)
        """
        return df

    async def parse_batch(
        self,
        batch_size: int = 1000
    ) -> AsyncIterator[tuple[pd.DataFrame, pd.DataFrame | None]]:
        """
        Parse table file in batches.
        
        Yields:
            Tuple of (peptide_df, None) - protein_df not supported yet
        """
        # Read table if not already loaded
        if self.sheets is None:
            self._read_table()
        
        # Get the sheet with peptide data
        if self.peptide_sheet_selector is None:
            sheet_df = self.get_sheet()
        else:
            sheet_df = self.get_sheet(**self.peptide_sheet_selector)
        
        # Transform and remap columns
        data = self.remap_columns(self.transform_df(sheet_df))
        
        # Yield in batches
        cursor = 0
        while cursor < len(data):
            batch = data[cursor:cursor + batch_size]
            yield batch, None
            cursor += batch_size

    async def validate(self) -> bool:
        """
        Validate file format.
        
        Checks if file can be read and required columns are present.
        
        Returns:
            True if file is valid
        """
        try:
            self._read_table()
            # Try to remap columns to validate configuration
            sheet_df = self.get_sheet() if self.peptide_sheet_selector is None \
                else self.get_sheet(**self.peptide_sheet_selector)
            self.remap_columns(self.transform_df(sheet_df))
            return True
        except Exception:
            return False

    async def get_metadata(self) -> dict:
        """
        Get table file metadata.
        
        Returns:
            dict with sheet information
        """
        if self.sheets is None:
            self._read_table()
        
        return {
            'num_sheets': len(self.sheets),
            'sheets': [
                {'no': s.no, 'name': s.name, 'rows': len(s.data)}
                for s in self.sheets
            ]
        }


class LargeCSVImporter(IdentificationParser, ABC):
    """
    Importer for very large CSV files.
    
    Uses async streaming to handle files that don't fit in memory.
    Processes line-by-line instead of loading entire file.
    
    Attributes:
        reader_params: Parameters for aiocsv reader
        file_has_headers: Whether first row contains column names
        headers: Column names if file doesn't have header row
    """
    reader_params: dict | None = None
    file_has_headers: bool = True
    headers: list[str] | None = None

    @abstractmethod
    def process_line(self, row: dict) -> dict:
        """
        Process a single row from CSV.
        
        Args:
            row: Dict mapping column names to values
            
        Returns:
            Processed row dict with standard column names
        """
        pass

    async def parse_batch(
        self,
        batch_size: int = 1000
    ) -> AsyncIterator[tuple[pd.DataFrame, pd.DataFrame | None]]:
        """
        Parse large CSV file in batches using async streaming.
        
        Yields:
            Tuple of (peptide_df, None)
        """
        reader_params = self.reader_params or {}
        
        async with aiofiles.open(self.file_path, mode='r', encoding='utf-8') as file:
            if self.file_has_headers:
                reader = aiocsv.AsyncDictReader(file, **reader_params)
            else:
                if self.headers is None:
                    raise ValueError("headers must be provided when file_has_headers=False")
                reader = aiocsv.AsyncReader(file, **reader_params)
            
            cursor = 0
            lines = []
            
            async for row in reader:
                # Convert row to dict if using AsyncReader
                if not self.file_has_headers:
                    row = {k: v for k, v in zip(self.headers, row)}
                
                # Process line
                processed = self.process_line(row)
                lines.append(processed)
                cursor += 1
                
                # Yield batch when ready
                if cursor >= batch_size:
                    yield pd.DataFrame(lines), None
                    lines.clear()
                    cursor = 0
            
            # Yield remaining lines
            if lines:
                yield pd.DataFrame(lines), None
