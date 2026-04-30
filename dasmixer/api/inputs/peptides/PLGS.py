import re
import pandas as pd
from .table_importer import SimpleTableImporter, ColumnRenames
from pyteomics.proforma import parse, to_proforma, GenericModification
from dasmixer.utils.logger import logger
from dasmixer.api.project import Protein

renames = ColumnRenames(
    scans='precursor.leID',
    canonical_sequence='peptide.seq',
    score='peptide.score',
    src_file_protein_id='protein.Accession'
)

ptm_renames = {
    'S-pyridylethyl': 'Pyridylethyl',
    'Deamidation': 'Deamidated',

}

ptm_parser_re = re.compile(r'([^;+]+?)\+([A-Z*])\((\d+|\*)\)')

fasta_name_re = re.compile(r'([A-Z]{2})=(.+?)(?=\s+[A-Z]{2}=|$)')

protein_name_re = re.compile(r'^(.+?)\s+[A-Z]{2}=')

class PLGSImporter(SimpleTableImporter):
    renames=renames
    spectra_id_field = 'scans'
    contain_proteins = True



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


    # Protein columns that are aggregated (joined with ';') during deduplication.
    # Keeps per-protein metadata aligned with the aggregated Accession column.
    _PROTEIN_AGG_COLS = ('protein.Accession', 'protein.Entry', 'protein.Description')

    def prepare_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Collapse per-protein rows into one row per LeID (precursor.leID).

        PLGS exports one row per (spectrum, protein) pair. This method groups
        rows by precursor.leID, joins unique values of the protein columns
        (protein.Accession, protein.Entry, protein.Description) with ';',
        and keeps all other columns from the first row of each group.
        """
        scan_col = renames.scans          # 'precursor.leID'

        if scan_col not in df.columns:
            return df

        def join_unique(vals) -> str:
            return ';'.join(dict.fromkeys(str(v) for v in vals if pd.notna(v)))

        agg = {}
        for col in self._PROTEIN_AGG_COLS:
            if col in df.columns:
                agg[col] = join_unique

        other_cols = [c for c in df.columns if c != scan_col and c not in agg]
        agg.update({c: 'first' for c in other_cols})

        result = (
            df.groupby(scan_col, sort=False)
            .agg(agg)
            .reset_index()
        )
        return result

    def transform_df(self, df: pd.DataFrame) -> pd.DataFrame:
        df['sequence'] = df.apply(lambda row: self.get_modified_sequence(row['peptide.seq'], row['peptide.modification']), axis=1)
        return df

    def get_proteins(self, df: pd.DataFrame) -> dict[str, 'Protein'] | None:
        """
        Build a Protein dict from the (already-deduplicated) batch DataFrame.

        After prepare_df(), protein.Accession / protein.Entry /
        protein.Description are ';'-joined strings — one entry per position.
        We split them in lockstep to reconstruct per-protein metadata.
        """
        res = {}
        for _, row in df.iterrows():
            accessions = [a.strip() for a in str(row['protein.Accession']).split(';') if a.strip()]
            entries = [e.strip() for e in str(row.get('protein.Entry', '')).split(';')]
            descriptions = [d.strip() for d in str(row.get('protein.Description', '')).split(';')]

            for i, accession in enumerate(accessions):
                if not accession or accession in res:
                    continue
                entry = entries[i] if i < len(entries) else ''
                description = descriptions[i] if i < len(descriptions) else ''

                params = dict(fasta_name_re.findall(description)) if description else {}
                name_match = protein_name_re.match(description) if description else None

                taxid = params.get('OX', '')
                taxid = int(taxid) if taxid else None

                res[accession] = Protein(
                    id=accession,
                    fasta_name=f"{accession}|{entry}|{description}" if entry or description else accession,
                    gene=params.get('GN', None),
                    taxon_id=taxid,
                    organism_name=params.get('OS', None),
                    name=name_match.group(1) if name_match else None,
                )
        return res