from dataclasses import dataclass
from itertools import combinations, product
from typing import Any
from copy import deepcopy

from dasmixer.utils.ppm import calculate_ppm, calculate_theor_mass, get_uncharged_mass
from pyteomics.proforma import parse, GenericModification, to_proforma
import warnings

PROTON_MASS = 1.007276

@dataclass
class FixedPTM:
    code: str
    attach_to: str | list[str] | None = None
    mono_mass: float | None = None
    n_term: bool = False
    c_term: bool = False
    generic_mod_object: GenericModification | None = None

    def get_mz(self, charge: int) -> float:
        return (self.mono_mass + charge * PROTON_MASS) / charge

    def __post_init__(self):
        self.generic_mod_object = GenericModification(self.code)
        try:
            db_mass = self.generic_mod_object.mass
        except (KeyError, ImportError) as e:
            raise Exception('No data for PTM found! Create one with Composition and add it to pyteomics.mass.unimod!')
        if not self.mono_mass:
            self.mono_mass = self.generic_mod_object.mass
        else:
            if db_mass != self.mono_mass:
                warnings.warn(f"FixedPTM: {self.code}: mass in code differs from one in DB!")

@dataclass
class PossiblePTMPosition:
    idx: int
    amino: str
    ptm: GenericModification

@dataclass
class PossibleSequence:
    sequence: str
    ppm: float
    ppm_abs: float
    modifications: list[PossiblePTMPosition]

class PossibleSequenceCreator:
    canonical_sequence: str
    canonical_sequence_split: list[tuple[str, list[GenericModification | None]]]
    canonical_sequence_params: dict[str, Any]
    pepmass: float
    charge: int

    def __init__(self, canonical_sequence: str, pepmass: float, charge: int):
        self.canonical_sequence = canonical_sequence
        self.canonical_sequence_split, self.canonical_sequence_params = parse(canonical_sequence)
        self.pepmass = pepmass
        self.charge = charge

    def get_sequence_version(self, positions: list[PossiblePTMPosition], c_term: None | FixedPTM = None, n_term: None | FixedPTM = None) -> PossibleSequence:
        print(positions, c_term, n_term)
        res_seq = deepcopy(self.canonical_sequence_split)
        params = deepcopy(self.canonical_sequence_params)
        print(params)
        if c_term is not None:
            params['c_term'] = [c_term.generic_mod_object]
        if n_term is not None:
            params['n_term'] = [n_term.generic_mod_object]
        print(params)
        for pos in positions:
            res_seq[pos.idx] = (pos.amino, [pos.ptm])
        seq_proforma = to_proforma(res_seq, **params)
        print(seq_proforma)
        ppm = calculate_ppm(seq_proforma, self.pepmass, self.charge)
        return PossibleSequence(
            seq_proforma,
            ppm,
            abs(ppm),
            positions
        )







PTMS = [
    FixedPTM(
        'Pyridylethyl',
        'C',
    ),
    FixedPTM(
        'Deamidated',
        ['N', 'Q'],
        mono_mass=0.984016,
    ),
    FixedPTM(
        'Amidated',
        attach_to=None,
        c_term=True,
        # mono_mass=-0.984016,
    ),
]

def get_possible_ptm(
        ptm_list: list[FixedPTM],
        seq: str,
        pepmass: float, charge: int,
        max_ptm: int, max_ppm: float=10.0
) -> list[str]:
    split_seq, seq_adds = parse(seq)
    canonical_seq = ''.join(x for x, y in split_seq if y is None)
    canonical_ppm = calculate_ppm(canonical_seq, pepmass, charge)
    inter_ptms = [x for x in ptm_list if x.attach_to is not None]
    n_term_ptms = [None] + [x for x in ptm_list if x.n_term]
    c_term_ptms = [None] + [x for x in ptm_list if x.c_term]
    term_combos = list(product(n_term_ptms, c_term_ptms))
    seq_creator = PossibleSequenceCreator(canonical_seq, pepmass, charge)
    print(split_seq)
    print(seq_adds)
    ptm_sites = []
    for idx, pos in enumerate(split_seq):
        if pos[1] is not None:
            ptm_sites.append(PossiblePTMPosition(idx, pos[0], pos[1]))
        for ptm in inter_ptms:
            if pos[0] in ptm.attach_to:
                ptm_sites.append(PossiblePTMPosition(idx, pos[0], ptm.generic_mod_object))
    possible_sequences = []
    # only terminal processing
    for n_term, c_term in term_combos:
        pos_seq = seq_creator.get_sequence_version(
            [],
            c_term=c_term,
            n_term=n_term
        )
        if pos_seq.ppm_abs <= max_ppm:
            possible_sequences.append(pos_seq)
    for lim in range(1, max_ptm + 1):
        ptm_combos = combinations(ptm_sites, lim)
        for combo in ptm_combos:
            indexes = {x.idx for x in combo}
            if len(indexes) < len(combo):
                continue #  skip the case with PTMs on the same AA
            for n_term, c_term in term_combos:
                pos_seq = seq_creator.get_sequence_version(list(combo), n_term=n_term, c_term=c_term)
                print(pos_seq)
                print(calculate_theor_mass(pos_seq.sequence) - get_uncharged_mass(pepmass, charge))
                if pos_seq.ppm_abs <= max_ppm:
                    possible_sequences.append(pos_seq)
    return [x.sequence for x in possible_sequences]




if __name__ == '__main__':
    res = get_possible_ptm(
        PTMS,
        'AVGDKLPECEADDGCPKPPEIAHGYVEHSVR',
        883.1747,
        4,
        5,
        max_ppm=300.0

    )
    print(res)