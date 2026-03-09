import re

from pyteomics import mass
from pyteomics.auxiliary import PyteomicsError

# proton mass
PROTON_MASS = 1.007276

# Canonical amino acid alphabet
CANONICAL_AA = 'ARNDCQEGHILKMFPSTWYV'

# Average mass per residue (used as fallback for non-canonical residues)
_AVG_MASS = mass.calculate_mass(CANONICAL_AA) / len(CANONICAL_AA)

# Regex for old-style modification notation: (+42.01) or (-17.03) etc.
_MOD_PATTERN_ROUND = re.compile(r'\(([+-]?\d*\.?\d*)\)')


def calculate_theor_mass(sequence: str) -> float:
    """
    Calculate theoretical monoisotopic neutral mass of a peptide.

    Supports two modification notations:
    - ProForma / peptacular: square brackets, e.g. "PEP[+15.99]TIDE"
    - Legacy round-bracket notation: e.g. "EAM(+15.99)DTSSK"

    For sequences without modifications (m,no '[' and no '('), and for the
    canonical-only part after stripping non-canonical residues, uses
    pyteomics mass.calculate_mass.  On PyteomicsError (caused by unknown
    residues such as 'X', 'B', 'U', etc.) falls back to:
        mass(canonical residues) + avg_residue_mass * count(non-canonical)

    Args:
        sequence: Peptide sequence string, optionally with modifications.

    Returns:
        Theoretical neutral monoisotopic mass (float, in Da).
    """
    # --- ProForma / square-bracket notation ---
    if '[' in sequence:
        try:
            return mass.calculate_mass(proforma=sequence, ion_type='M', charge=0)
        except PyteomicsError:
            # Strip modifications and fall back to canonical-residue calculation
            clean = re.sub(r'\[.*?\]', '', sequence)
            return _canonical_fallback(clean)

    # --- Legacy round-bracket notation ---
    if '(' in sequence:
        modifications = _MOD_PATTERN_ROUND.findall(sequence)
        mod_masses = [float(m) for m in modifications]
        clean = _MOD_PATTERN_ROUND.sub('', sequence)
        base_mass = _canonical_fallback(clean)
        return base_mass + sum(mod_masses)

    # --- Plain sequence (no modifications) ---
    return _canonical_fallback(sequence)


def _canonical_fallback(clean_sequence: str) -> float:
    """
    Calculate neutral mass for a plain (modification-free) sequence.

    Tries pyteomics first; on failure splits into canonical / non-canonical
    residues and uses average mass for the non-canonical ones.

    Args:
        clean_sequence: Sequence string without any modification tokens.

    Returns:
        Neutral monoisotopic mass (float).
    """
    try:
        return mass.calculate_mass(sequence=clean_sequence, ion_type='M', charge=0)
    except PyteomicsError:
        canonical_part = ''
        non_canonical_count = 0
        for letter in clean_sequence:
            if letter.upper() in CANONICAL_AA:
                canonical_part += letter
            else:
                non_canonical_count += 1
        canon_mass = mass.calculate_mass(sequence=canonical_part, ion_type='M', charge=0) if canonical_part else 0.0
        return canon_mass + non_canonical_count * _AVG_MASS


def calculate_ppm(sequence: str, pepmass: float, charge: int) -> float:
    """
    Calculate PPM difference between experimental and theoretical peptide mass.

    Uses calculate_theor_mass() internally, so supports both ProForma
    ([+15.99]) and legacy ((+15.99)) modification notations as well as
    non-canonical residues.

    Parameters
    ----------
    sequence : str
        Peptide sequence with optional modifications, e.g.:
        "(+42.01)ALDLERPR"   - N-terminal modification (legacy notation)
        "EAM(+15.99)DTSSK"  - methionine oxidation (legacy notation)
        "PEP[+15.99]TIDE"    - oxidation in ProForma notation
    pepmass : float
        Experimental m/z from the PEPMASS field in the MGF file.
    charge : int
        Precursor charge state.

    Returns
    -------
    float
        PPM difference: (experimental - theoretical) / theoretical * 1e6.
    """
    proton = 1.007276
    neutral_mass = calculate_theor_mass(sequence)
    theoretical_mz = (neutral_mass + charge * proton) / charge

    ppm = ((pepmass - theoretical_mz) / theoretical_mz) * 1e6
    return ppm


def calculate_ppm_and_charge(
        sequence: str,
        pepmass: int | float,
        neutral_mass: float | None = None,
        min_charge: int=1,
        max_charge: int=4
) -> tuple[float, int, float]:
    """
    Calculate PPM difference between experimental and theoretical peptide mass for unknown (or ignored) charge
    :param sequence: peptide sequence in ProForma notation
    :param pepmass: precursor mass (in Da)
    :param neutral_mass: neutral mass (in Da), calculated if not given
    :param min_charge: minimum charge value to calculate (default: 1)
    :param max_charge: maximum charge value to calculate (default: 4)
    :return: minimum ppm error, charge value, neutral mass
    """
    if neutral_mass is None:
        neutral_mass = calculate_theor_mass(sequence)

    charges = list(range(min_charge, max_charge + 1))
    ppms = []
    abs_ppms = []

    for charge in charges:
        theoretical_mz = (neutral_mass + charge * PROTON_MASS) / charge
        ppm = ((pepmass - theoretical_mz) / theoretical_mz) * 1e6
        ppms.append(ppm)
        abs_ppms.append(abs(ppm))
    idx = abs_ppms.index(min(abs_ppms))
    return ppms[idx], charges[idx], neutral_mass