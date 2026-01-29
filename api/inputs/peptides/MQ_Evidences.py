"""MaxQuant Evidence.txt file parser."""

import pandas as pd
from .table_importer import SimpleTableImporter, ColumnRenames


# Column mapping for MaxQuant evidence.txt
renames = ColumnRenames(
    scans='MS/MS scan number',
    sequence='Modified sequence',
    canonical_sequence='Sequence',
    score='Score',
    ppm='Mass error [ppm]'
)


# PTM notation conversions from MaxQuant to ProForma-like notation
ptm_replacements = [
    ('(Deamidation (NQ))', '[Deamidation]'),
    ('(de)', '[Deamidation]'),
    ('_', ''),  # Remove underscores
    ('(Pyridylethyl)', '[Pyridylethyl]'),
    ('(Oxidation (M))', '[Oxidation]'),
]


class MaxQuantEvidenceParser(SimpleTableImporter):
    """
    Parser for MaxQuant evidence.txt files.
    
    MaxQuant is a widely-used proteomics software for peptide identification
    and quantification. The evidence.txt file contains peptide-level information
    including identifications, scores, and quantification data.
    
    File format:
        - Tab-separated values
        - Header row with column names
        - Modified sequences use MaxQuant PTM notation (parentheses)
    
    Features:
        - Converts MaxQuant PTM notation to ProForma-like notation
        - Maps scan numbers for spectrum matching
        - Extracts mass error (ppm) and scores
    
    Example usage:
        >>> parser = MaxQuantEvidenceParser("evidence.txt")
        >>> async for peptide_df, protein_df in parser.parse_batch():
        ...     print(peptide_df[['scans', 'sequence', 'ppm']])
    """
    
    separator = '\t'
    renames = renames

    @staticmethod
    def _fix_sequence(mod_seq: str) -> str:
        """
        Convert MaxQuant PTM notation to ProForma-like notation.
        
        Replaces MaxQuant-specific modification annotations with
        standardized bracket notation.
        
        Args:
            mod_seq: Sequence with MaxQuant PTM notation
                    (e.g., "_PEPT(Oxidation (M))IDE_")
            
        Returns:
            Sequence with ProForma-like notation
            (e.g., "PEPT[Oxidation]IDE")
        """
        for src, repl in ptm_replacements:
            mod_seq = mod_seq.replace(src, repl)
        return mod_seq

    def transform_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform MaxQuant-specific data.
        
        Converts PTM notation in Modified sequence column.
        
        Args:
            df: Raw DataFrame with MaxQuant column names
            
        Returns:
            Transformed DataFrame
        """
        if 'Modified sequence' in df.columns:
            df['Modified sequence'] = df['Modified sequence'].apply(self._fix_sequence)
        return df
