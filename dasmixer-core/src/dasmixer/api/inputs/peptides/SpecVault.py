import pandas as pd
from dasmixer.api.inputs.peptides.table_importer import ColumnRenames, SimpleTableImporter
from pyteomics.proforma import parse

renames = ColumnRenames(
    seq_no="query_identifier",
    sequence="library_peptide",
    canonical_sequence="canonical_sequence",
    ppm="ppm_diff",
    score="combined_score",
    fdr="fdr",
    e_value="e_value",
    q_value="q_value"
)


class SpecVaultImporter(SimpleTableImporter):
    separator = ','
    renames = renames

    @staticmethod
    def get_canonical_seq(seq: str) -> str:
        pf, _ = parse(seq)

        return ''.join([x[0] for x in pf])

    def transform_df(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['query_identifier'] = df['query_identifier'] - 1
        df = df.query("search_type=='target'").copy()
        df['canonical_sequence'] = df['library_peptide'].apply(lambda x: self.get_canonical_seq(x))
        return df


# registry.add_identification_parser("SpecVault", SpecVaultImporter)