from peptacular import FragmentMatch
from pyteomics.proforma import parse

def calculate_peptide_quality(
        matches: list[FragmentMatch],
        sequence: str,
        ion_types: list[str],
) -> float:
    """
    Quality assessment for peptide identification.
    Based on: https://doi.org/10.1093/bioinformatics/bth947

    NOTE: value can become meaningless if more than only b and y ions selected!

    :param matches: list of matches from get_peptacular.score.get_fragment_matches()
    :param sequence: peptide sequence in ProForma format
    :param ion_types: list of ion types, e.g ['b','y','z']
    :return: quality value from 0.0 to 1.0 where 0.0 means no fragments matched and 1.0 means all fragments matched
    """
    n_ion_types = len(ion_types)
    seq_length = len(parse(sequence)[0])

    uq_matched = set()
    for match in matches:
        uq_matched.add(f'{match.fragment.ion_type}{match.fragment.start - match.fragment.end}')

    n_ions = len(uq_matched)

    quality = (1/n_ion_types) * (n_ions / (seq_length - 1))
    return quality


def calculate_longest_consec_run_ratio(matches: list[FragmentMatch], sequence: str) -> float:
    ions = {}
    for match in matches:
        typ = match.fragment.ion_type
        pos = match.fragment.end - match.fragment.start
        if not typ in ions:
            ions[typ] = set()
        ions[typ].add(pos)
    res = 0
    for typ, val_set in ions.items():
        vals = list(val_set)
        vals.sort()
        longest = 1
        current = 1
        for prev, curr in zip(vals, vals[1:]):
            if curr - prev == 1:
                current += 1
            else:
                current = 1
            longest = max(longest, current)
        res = max(res, longest)

    seq_length = len(parse(sequence)[0])
    return res / seq_length
