import pandas as pd

from .table_importer import ColumnRenames, SimpleTableImporter

renames = ColumnRenames(
    score='PowerNovo Score',
    sequence='PowerNovo Peptides',
    positional_scores='PowerNovo aaScore'
)



class PowerNovoImporter(SimpleTableImporter):
    field_to_proforma='PowerNovo Peptides'
    def transform_df(self, df: pd.DataFrame) -> pd.DataFrame:
        df['seq_no'] = df['Spectrum Name'].apply(lambda x: int(x.split(':index=')[1]))
        df['PowerNovo aaScore'] = df['PowerNove aaScore'].apply(lambda y: [float(x) for x in y.split(' ')])