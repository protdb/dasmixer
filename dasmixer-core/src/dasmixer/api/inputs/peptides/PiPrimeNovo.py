"""Pi-PrimeNovo identification parser (TSV)."""

import re

import pandas as pd
from pyteomics.proforma import parse

from .table_importer import ColumnRenames, SimpleTableImporter


# Column mapping for Pi-PrimeNovo TSV output.
# - label       -> title (spectrum mapping via normalized title)
# - prediction  -> sequence (transformed to ProForma in transform_df)
# - score       -> score
# canonical_sequence is synthesized inside transform_df (no source column),
# hence the identity mapping below.
renames = ColumnRenames(
    title="label",
    sequence="prediction",
    canonical_sequence="canonical_sequence",
    score="score",
)


class PiPrimeNovoImporter(SimpleTableImporter):
    """Parser for Pi-PrimeNovo de novo sequencing TSV files.

    The ``prediction`` column uses Pi-PrimeNovo's bracketed mass notation with
    ``B`` as a phospho/artifact placeholder; ``transform_sequence`` converts it
    to standard ProForma notation.
    """

    PARSER_ID = "Pi-PrimeNovo"
    separator = "\t"
    renames = renames
    spectra_id_field = "title"
    contain_proteins = False

    _PHOSPHO_B = re.compile(r"B([STY])")

    # Ordered replacements: N-terminal first, then amino-acid side-chain PTMs.
    # Order matters (longer/more-specific keys first where they overlap).
    _REPLACES = {
        # N-terminal
        "[+43.006-17.027]": "[Carbamyl][Ammonia-loss]-",
        "[+42.011]": "[Acetyl]-",
        "[+43.006]": "[Carbamyl]-",
        "[-17.027]": "[Ammonia-loss]-",
        # amino-acid side chains
        "[+57.021]": "[Carbamidomethyl]",
        "[+15.995]": "[Oxidation]",
        "[+0.984]": "[Deamidated]",
    }

    @classmethod
    def transform_sequence(cls, raw: str) -> str:
        """Convert a Pi-PrimeNovo prediction string to ProForma notation.

        Order (as agreed): (1) ``B`` before S/T/Y -> ``[Phospho]``,
        (2) remove a lone ``B`` before any other residue, (3) apply the
        mass/terminal replacements from ``_REPLACES``.
        """
        s = cls._PHOSPHO_B.sub(r"\1[Phospho]", raw)
        s = re.sub(r"B(?=[A-Z])", "", s)
        for src, dst in cls._REPLACES.items():
            s = s.replace(src, dst)
        return s

    def transform_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """Transform raw columns before remapping.

        - ``prediction`` -> ProForma sequence (via transform_sequence);
        - ``label`` -> normalized title (strip + lower);
        - synthesize ``canonical_sequence`` from the transformed prediction.
        """
        df = df.copy()
        df["prediction"] = df["prediction"].apply(self.transform_sequence)
        df["label"] = df["label"].astype(str).str.strip().str.lower()
        df["canonical_sequence"] = df["prediction"].apply(
            lambda s: "".join(aa for aa, _ in parse(s)[0])
        )
        return df
