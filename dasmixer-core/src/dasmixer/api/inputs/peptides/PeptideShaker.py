import logging
from typing import AsyncIterator
from copy import deepcopy
import re

import pandas as pd
from pyteomics.proforma import parse, GenericModification, to_proforma
from pyteomics.mass import calculate_mass

from .table_importer import SimpleTableImporter, TableImporter, ColumnRenames


terminal_ptm = {
    'NH2': 'Amidated',
    'COOH': 'Carboxy',
    'pyroE': 'Glu->pyro-Glu',
    'pyroQ': 'Gln->pyro-Glu'
}
internal_ptm = {
    'pyri': 'Pyridylethyl',
    'deam': 'Deamidated',
    'ox': 'Oxidation',
    'p': 'Phospho'
}

split_rg = re.compile(r'[A-Z](?:<[^<>]*>)?')

renames = ColumnRenames(
    seq_no='seq_no',
    sequence='proforma',
    canonical_sequence='Sequence',
    score='Algorithm Confidence [%]',
    ppm='Precursor m/z Error [ppm]',
    theor_mass='Theoretical Mass',
)


class PeptideShakerImporter(TableImporter):
    require_project = True

    @staticmethod
    def to_proforma(sequence: str) -> str:
        parts = sequence.split('-')
        if len(parts) == 3:
            start, seq, end = parts
        elif len(parts) == 2:
            if parts[0] in terminal_ptm.keys():
                start, seq = parts
                end = None
            else:
                seq, end = parts
                start = None
        elif len(parts) == 1:
            seq = parts[0]
            end = None
            start = None
        else:
            raise ValueError('Too many parts')
        if start == 'NH2':
            start = None
        if end == 'COOH':
            end = None
        if start == 'pyro':
            if seq.startswith('E'):
                start = 'pyroE'
            elif seq.startswith('Q'):
                start = 'pyroQ'
            else:
                logging.warning(f'pyro-term at wrong residue in {sequence}')
        if start is not None:
            start = [GenericModification(terminal_ptm[start])]
        if end is not None:
            end = [GenericModification(terminal_ptm[end])]
        split_seq = split_rg.findall(seq)
        transformed_seq = []
        for aa in split_seq:
            if len(aa) == 1:
                transformed_seq.append((aa.upper(), None))
            else:
                aa_name = aa[0].upper()
                ptm = internal_ptm.get(aa[2:-1], None)
                transformed_seq.append((aa_name, [ptm]))
        return to_proforma(transformed_seq, n_term=start, c_term=end)

    async def get_mapping_data(self) -> pd.DataFrame:
        res = await self.project.execute_query_df(
            "SELECT seq_no, pepmass, rt from spectre where spectre_file_id=?",
            (self.spectra_file_id,)
        )
        return res

    async def get_merged_data(self) -> pd.DataFrame:
        if self.sheets is None:
            self._read_table()
        seq_df = self.get_sheet(name='Peptide Identification Summary')[['Sequence', 'Modified Sequence']]
        scan_match_df = self.get_sheet(name='Peptide Spectrum Matching Summa')
        seq_df['proforma'] = seq_df['Modified Sequence'].apply(self.to_proforma)
        seq_df['theor_mass'] = seq_df['proforma'].apply(lambda x: round(calculate_mass(proforma=x), 3))
        seqs = {x: [] for x in seq_df['Sequence'].unique()}
        for _, row in seq_df.iterrows():
            seqs[row['Sequence']].append({'proforma': row['proforma'], 'theor_mass': row['theor_mass'],})

        spectra_df = await self.get_mapping_data()

        spectra_df['pepmass'] = spectra_df['pepmass'].round(4)
        spectra_df['rt'] = spectra_df['rt'].round(4)

        scan_match_df['pepmass'] = scan_match_df['m/z'].round(4)
        scan_match_df['rt'] = scan_match_df['RT'].round(4)

        df = pd.merge(
            scan_match_df,
            spectra_df,
            on=['rt', 'pepmass'],
            how='left',
        )
        if len(df.query("seq_no != seq_no")):
            # TODO: correct logging with list of entities
            logging.warning("mismatched peptide ids")

        proformas = []

        for _, row in df.iterrows():
            pf = deepcopy(seqs.get(row['Sequence'], []))
            print('pf', pf)
            if len(pf) == 0:
                proformas.append(None)
            elif len(pf) == 1:
                proformas.append(pf[0]['proforma'])
            else:
                pf.sort(key=lambda x: abs(x['theor_mass'] - row['Theoretical Mass']))
                proformas.append(pf[0]['proforma'])
        df['proforma'] = proformas
        bad_pfs = df.query("proforma != proforma")
        if len(bad_pfs) > 0:
            logging.warning(f"reqorlds with bat proforma: {len(bad_pfs)}")
            print(bad_pfs.to_markdown(index=False))
        return df.query("proforma == proforma").copy()

    async def parse_batch(
        self,
        batch_size: int = 1000
    ) -> AsyncIterator[pd.DataFrame]:
        result = await self.get_merged_data()
        rename_cols = renames.mapping
        print(rename_cols)
        print(result.columns)
        print(result.head(10).to_markdown(index=False))
        for col in rename_cols.keys():
            if col not in result.columns:
                result[col] = None
        result.rename(columns=rename_cols, inplace=True)
        print(result.columns)
        print([col for col in rename_cols.keys() if col in result.columns])
        sheet_df = result[[col for col in rename_cols.values() if col in result.columns]]
        cursor = 0
        print(sheet_df.head(10).to_markdown(index=False))
        while cursor < len(sheet_df):
            batch = sheet_df[cursor:cursor + batch_size]
            yield batch
            cursor += batch_size

    async def validate(self) -> bool:
        try:
            # TODO: more detailed logging!
            self._read_table()
            peptide_sheet = self.get_sheet(name='Peptide Identification Summary')
            matching_sheet = self.get_sheet(name='Peptide Spectrum Matching Summa')
            peptide_sheet = peptide_sheet[['Sequence', 'Modified Sequence']]
            matching_sheet = matching_sheet[['m/z', 'RT', 'Theoretical Mass', 'Sequence']]
            return True
        except (KeyError, ValueError) as e:
            logging.exception(e)
            return False