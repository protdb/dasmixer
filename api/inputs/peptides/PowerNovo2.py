"""PowerNovo2 identification parser."""

import pandas as pd
from .table_importer import SimpleTableImporter, ColumnRenames


# Column mapping for PowerNovo2 output
# Note: Column names in PowerNovo2 CSV files use these exact names
renames = ColumnRenames(
    seq_no='SPECTRUM_ID',  # Sequential spectrum number
    sequence='PEPTIDE',    # Peptide sequence with modifications
    canonical_sequence='CANONICAL SEQ.',  # Sequence without modifications
    ppm='PPM DIFFERENCE',  # Mass error in ppm
    score='SCORE',         # Confidence score
    positional_scores='POSITIONAL SCORES'  # Per-position confidence scores
)


class PowerNovo2Importer(SimpleTableImporter):
    """
    Parser for PowerNovo2 de novo sequencing identification files.
    
    PowerNovo2 outputs CSV files with de novo peptide sequencing results.
    Each row represents one spectrum identification with the predicted
    peptide sequence and quality scores.
    
    File format:
        - CSV with comma separator
        - Header row with column names
        - POSITIONAL SCORES column contains space-separated float values
    
    Example usage:
        >>> parser = PowerNovo2Importer("results.csv")
        >>> async for peptide_df, protein_df in parser.parse_batch(batch_size=1000):
        ...     # peptide_df has standardized column names
        ...     print(peptide_df[['seq_no', 'sequence', 'score']])
    """
    
    separator = ','
    renames = renames
    
    def transform_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform PowerNovo2-specific data.
        
        Converts positional scores from space-separated string to list of floats.
        
        Args:
            df: Raw DataFrame from CSV file with original column names
            
        Returns:
            Transformed DataFrame (column names not yet remapped)
        """
        if 'POSITIONAL SCORES' in df.columns:
            df['POSITIONAL SCORES'] = df['POSITIONAL SCORES'].apply(
                lambda x: [float(s) for s in x.split()] if pd.notna(x) else None
            )
        return df
