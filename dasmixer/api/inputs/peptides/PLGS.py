import re
import pandas as pd
from .table_importer import SimpleTableImporter, ColumnRenames
from pyteomics.proforma import parse, to_proforma, GenericModification
from dasmixer.utils.logger import logger

renames = ColumnRenames(
    scans='precursor.leID',
    canonical_sequence='peptide.seq',
    score='peptide.score'
)

ptm_renames = {
    'S-pyridylethyl': 'Pyridylethyl',
    'Deamidation': 'Deamidated',

}

ptm_parser_re = re.compile(r'([^;+]+?)\+([A-Z*])\((\d+|\*)\)')

class PLGSImporter(SimpleTableImporter):
    renames=renames
    spectra_id_field = 'scans'


    @staticmethod
    def get_modified_sequence(seq:str, ptm_str:str) -> str:
        logger.debug(ptm_str)
        if not ptm_str or ptm_str == 'None':
            return seq
        if type(ptm_str) != str:
            return seq
        pf_seq, pf_params = parse(seq)
        ptm_list = ptm_parser_re.findall(ptm_str)

        for name, aa, index in ptm_list:
            ptm_obj = GenericModification(ptm_renames.get(name, name))
            if index != '*':
                proforma_idx = int(index) - 1
                if pf_seq[proforma_idx][0] != aa:
                    logger.debug(f'PTM mismatch @ {index}: {pf_seq[proforma_idx]} != {aa}')
                if pf_seq[proforma_idx][1] is None:
                    pf_seq[proforma_idx] = (pf_seq[proforma_idx][0], [ptm_obj])
                else:
                    pf_seq[proforma_idx][1].append(ptm_obj)
            else:
                pf_params['unlocalized_modifications'].append(ptm_obj)
        return to_proforma(pf_seq, **pf_params)


    def transform_df(self, df: pd.DataFrame) -> pd.DataFrame:
        df['sequence'] = df.apply(lambda row: self.get_modified_sequence(row['peptide.seq'], row['peptide.modification']), axis=1)
        return df

