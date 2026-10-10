"""CasaNovo identification parser (mzTab-based, single sample)."""

from pyteomics.proforma import parse

from .MzTab import MzTabImporter


class CasaNovoImporter(MzTabImporter):
    """Parser for CasaNovo mzTab output (single samples, de novo).

    CasaNovo already emits a ready-made ProForma sequence in the
    ``opt_global_cv_MS:1003169_proforma_peptidoform_sequence`` column, so the
    ``modifications`` column is ignored and the ready ProForma value is used
    as-is. Per-residue confidence scores from ``opt_global_aa_scores`` are
    stored as ``positional_scores`` (list of floats).
    """

    PARSER_ID = "CasaNovo"
    contain_proteins = False
    can_import_multifile = False
    spectra_id_field = "seq_no"

    PROFORMA_COL = "opt_global_cv_MS:1003169_proforma_peptidoform_sequence"
    AA_SCORES_COL = "opt_global_aa_scores"

    def _source_sequence(self, row: dict) -> str:
        return row.get(self.PROFORMA_COL) or ""

    def get_modified_sequence(self, seq: str, mods: str) -> str:
        # The ready ProForma sequence is used as-is; modifications are ignored.
        return seq

    def get_canonical_sequence(self, row: dict) -> str:
        return "".join(aa for aa, _ in parse(self._source_sequence(row))[0])

    def _positional_scores(self, row: dict):
        raw = row.get(self.AA_SCORES_COL)
        if raw is None or not str(raw).strip():
            return None
        try:
            return [float(x) for x in str(raw).split(",")]
        except ValueError:
            return None
