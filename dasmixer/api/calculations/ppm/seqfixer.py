"""
SeqFixer: pipeline for peptide sequence PPM correction.

Covers two scenarios:
1. get_ppm  — given a precursor and its identified sequence (ProForma),
               find the best-fitting charge / PTM combination.
2. get_matched_ppm — same, but a slightly different sequence (from DB BLAST)
                     is provided alongside the originally matched sequence;
                     PTM sites discovered on the original are treated as
                     optional candidates on the new sequence.
"""
# from __future__ import annotations

from copy import deepcopy
from itertools import combinations, product
from typing import Literal

from pyteomics import mass as pymass
from pyteomics.proforma import parse, to_proforma, GenericModification, TagBase

from .dataclasses import SeqMatchParams, SeqResults
from dasmixer.utils.ppm import (
    calculate_theor_mass,
    get_ppm_for_masses,
    PROTON_MASS,
)
from dasmixer.utils.seqfixer_utils import FixedPTM, PossiblePTMPosition

import logging as _logging
_seqfixer_log = _logging.getLogger("dasmixer.seqfixer")

# ── isotope-offset mass constants ────────────────────────────────────────────
ISOTOPE_MASS_13C = 1.003355   # 13C – 12C  (standard for peptide isotope patterns)
ISOTOPE_MASS_NEUTRON = 1.008665  # physical neutron mass

IsotopeMode = Literal["13C", "neutron"]


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _split_and_strip(proforma_seq: str) -> tuple[
    list[tuple[str, list[TagBase] | None]],
    dict,
    str,
]:
    """
    Parse a ProForma string, return:
      - split:  list of (residue, mods_or_None) from pyteomics
      - params: extra keyword params (n_term, c_term, …)
      - canonical: plain AA string without any modifications
    """
    split, params = parse(proforma_seq)
    canonical = "".join(aa for aa, mods in split)
    return split, params, canonical


def _make_seq_match_params(
    sequence: str,
    pepmass: float,
    charge: int,
    isotope_offset: int | None,
    neutral_mass: float | None = None,
) -> SeqMatchParams:
    if neutral_mass is None:
        neutral_mass = calculate_theor_mass(sequence)
    ppm = get_ppm_for_masses(pepmass, neutral_mass, charge)
    return SeqMatchParams(
        sequence=sequence,
        seq_neutral_mass=neutral_mass,
        pepmass=pepmass,
        charge=charge,
        ppm=ppm,
        abs_ppm=abs(ppm),
        isotope_offset=isotope_offset,
    )


def _collect_ptm_sites(
    split: list[tuple[str, list | None]],
    ptm_list: list[FixedPTM],
) -> list[PossiblePTMPosition]:
    """
    Build a flat list of all possible PTM positions:
    - existing mods already in the parsed ProForma sequence
    - all positions matching attach_to residues from ptm_list

    This mirrors the behaviour of seqfixer_utils.get_possible_ptm.
    """
    inter_ptms = [p for p in ptm_list if p.attach_to is not None]
    sites: list[PossiblePTMPosition] = []
    for idx, (aa, mods) in enumerate(split):
        if mods is not None:
            for mod in mods:
                if mod is not None:
                    sites.append(PossiblePTMPosition(idx, aa, mod))
        for ptm in inter_ptms:
            attach = ptm.attach_to
            if isinstance(attach, str):
                attach = [attach]
            if attach is not None and aa in attach and ptm.generic_mod_object is not None:
                sites.append(PossiblePTMPosition(idx, aa, ptm.generic_mod_object))
    return sites


def _apply_positions_to_split(
    base_split: list[tuple[str, list | None]],
    positions: list[PossiblePTMPosition],
    params: dict,
    n_term: FixedPTM | None,
    c_term: FixedPTM | None,
) -> str:
    """Build a ProForma string from a split + selected PTM positions + terminal mods."""
    res_seq = deepcopy(base_split)
    params = deepcopy(params)
    if n_term is not None:
        params["n_term"] = [n_term.generic_mod_object]
    if c_term is not None:
        params["c_term"] = [c_term.generic_mod_object]
    for pos in positions:
        res_seq[pos.idx] = (pos.amino, [pos.ptm])
    return to_proforma(res_seq, **params)


_MAX_PTM_COMBOS = 50_000  # hard cap to prevent combinatorial explosion


def _count_ptm_combos(n_sites: int, max_ptm: int, n_term_combos: int) -> int:
    """Estimate total PTM combo iterations (internal × terminal)."""
    from math import comb
    total = 0
    for lim in range(0, max_ptm + 1):
        total += comb(n_sites, lim)
    return total * n_term_combos


def _iter_ptm_combos(
    split: list[tuple[str, list | None]],
    params: dict,
    ptm_sites: list[PossiblePTMPosition],
    ptm_list: list[FixedPTM],
    max_ptm: int,
    pepmass_corrected: float,
    charge: int,
    target_ppm: float,
    isotope_offset: int,
) -> list[SeqMatchParams]:
    """
    Enumerate all PTM combinations (0 … max_ptm sites) plus terminal mods.
    Returns all SeqMatchParams whose abs_ppm <= target_ppm.

    Guards against combinatorial explosion: if the estimated number of
    combinations exceeds _MAX_PTM_COMBOS, max_ptm is silently capped so
    that the total stays within budget.
    """
    n_term_candidates: list[FixedPTM | None] = [None] + [p for p in ptm_list if p.n_term]
    c_term_candidates: list[FixedPTM | None] = [None] + [p for p in ptm_list if p.c_term]
    term_combos = list(product(n_term_candidates, c_term_candidates))
    n_term_combos = len(term_combos)
    n_sites = len(ptm_sites)

    # --- guard: cap max_ptm if combo count would explode ---
    effective_max_ptm = max_ptm
    if n_sites > 0:
        estimated = _count_ptm_combos(n_sites, max_ptm, n_term_combos)
        if estimated > _MAX_PTM_COMBOS:
            # Binary-search for the highest lim that stays within budget
            lo, hi = 0, max_ptm
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if _count_ptm_combos(n_sites, mid, n_term_combos) <= _MAX_PTM_COMBOS:
                    lo = mid
                else:
                    hi = mid - 1
            effective_max_ptm = lo
            _seqfixer_log.warning(
                "PTM combo explosion: %d sites × max_ptm=%d → ~%d combos "
                "(limit %d). Capping max_ptm to %d.",
                n_sites, max_ptm, estimated, _MAX_PTM_COMBOS, effective_max_ptm,
            )

    results: list[SeqMatchParams] = []

    # 0 internal PTMs — only terminal variants
    for n_term, c_term in term_combos:
        seq_str = _apply_positions_to_split(split, [], params, n_term, c_term)
        neutral = calculate_theor_mass(seq_str)
        ppm = get_ppm_for_masses(pepmass_corrected, neutral, charge)
        if abs(ppm) <= target_ppm:
            results.append(SeqMatchParams(
                sequence=seq_str,
                seq_neutral_mass=neutral,
                pepmass=pepmass_corrected,
                charge=charge,
                ppm=ppm,
                abs_ppm=abs(ppm),
                isotope_offset=isotope_offset,
            ))

    # 1 … effective_max_ptm internal sites
    for lim in range(1, effective_max_ptm + 1):
        for combo in combinations(ptm_sites, lim):
            # reject combos with two mods on the same residue index
            if len({p.idx for p in combo}) < len(combo):
                continue
            for n_term, c_term in term_combos:
                seq_str = _apply_positions_to_split(split, list(combo), params, n_term, c_term)
                neutral = calculate_theor_mass(seq_str)
                ppm = get_ppm_for_masses(pepmass_corrected, neutral, charge)
                if abs(ppm) <= target_ppm:
                    results.append(SeqMatchParams(
                        sequence=seq_str,
                        seq_neutral_mass=neutral,
                        pepmass=pepmass_corrected,
                        charge=charge,
                        ppm=ppm,
                        abs_ppm=abs(ppm),
                        isotope_offset=isotope_offset,
                    ))

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Main class
# ─────────────────────────────────────────────────────────────────────────────

class SeqFixer:
    """
    Peptide sequence PPM correction pipeline.

    Parameters
    ----------
    ptm_list : list[FixedPTM]
        PTM candidates to enumerate over.
    max_ptm : int
        Maximum number of simultaneous internal PTMs to try.
    max_ptm_sites : int
        Maximum number of candidate PTM sites on a sequence before PTM
        enumeration is skipped entirely and only isotope-offset correction
        is attempted.  Sequences with more sites than this value (e.g. long
        poly-Q/poly-L repeats) would otherwise cause a combinatorial explosion.
        Default 10.
    target_ppm : float
        Absolute PPM threshold; results with abs_ppm > target_ppm are rejected.
    override_charges : tuple[int, int]
        (min_charge, max_charge) range for charge override scan.
    max_isotope_offset : int
        Largest precursor isotope offset to consider (0 … max_isotope_offset).
    isotope_mode : "13C" | "neutron"
        Mass step for isotope offset.  Default "13C" (1.003355 Da).
    force_isotope_offset_lookover : bool
        If True, do not stop at the first isotope offset that yields hits —
        scan all offsets 0 … max_isotope_offset and return the result with
        the lowest abs_ppm across all of them.  Default False.
    """

    ISOTOPE_MASSES: dict[str, float] = {
        "13C": ISOTOPE_MASS_13C,
        "neutron": ISOTOPE_MASS_NEUTRON,
    }

    def __init__(
        self,
        ptm_list: list[FixedPTM],
        max_ptm: int,
        target_ppm: float,
        override_charges: tuple[int, int],
        max_isotope_offset: int,
        isotope_mode: IsotopeMode = "13C",
        force_isotope_offset_lookover: bool = False,
        max_ptm_sites: int = 10,
    ) -> None:
        self.ptm_list = ptm_list
        self.max_ptm = max_ptm
        self.max_ptm_sites = max_ptm_sites
        self.target_ppm = target_ppm
        self.override_charges = override_charges
        self.max_isotope_offset = max_isotope_offset
        self.isotope_step = self.ISOTOPE_MASSES[isotope_mode]
        self.force_isotope_offset_lookover = force_isotope_offset_lookover

    # ── public API ───────────────────────────────────────────────────────────

    def get_ppm(
        self,
        sequence: str,
        pepmass: float,
        mgf_charge: int | None,
    ) -> SeqResults:
        """
        Scenario 1: precursor + identified ProForma sequence.

        Pipeline
        --------
        1. Direct hit with mgf_charge (if provided).
        2. Charge override scan in override_charges range.
        3. Isotope offset × PTM enumeration.

        Returns
        -------
        SeqResults
            original — SeqMatchParams for the bare sequence / mgf_charge
                       (no PTM correction applied, isotope_offset=None).
            override — list of alternative SeqMatchParams that passed
                       target_ppm, or None if none were found.
        """
        split, params, canonical = _split_and_strip(sequence)
        canonical_split, canonical_params = parse(canonical)  # mods-free split

        # Build the original params object (bare, no override)
        original = self._make_original(sequence, pepmass, mgf_charge)

        # ── Step 1: direct hit ────────────────────────────────────────────────
        if mgf_charge is not None and original.abs_ppm is not None and original.abs_ppm <= self.target_ppm:
            return SeqResults(original=original, override=None)

        # ── Step 2: charge override (no PTM, no isotope correction) ──────────
        charge_hits, best_charge = self._scan_charges(
            sequence=sequence,
            pepmass=pepmass,
            neutral_mass=original.seq_neutral_mass,
        )
        if charge_hits:
            return SeqResults(original=original, override=charge_hits)

        # ── Step 3: isotope offset + PTM enumeration ──────────────────────────
        # Use best_charge from charge scan (minimum abs_ppm) as the working
        # charge; this is safe even when mgf_charge is None.
        ptm_sites = _collect_ptm_sites(canonical_split, self.ptm_list)
        ptm_hits = self._scan_offsets_and_ptms(
            canonical_split=canonical_split,
            canonical_params=canonical_params,
            ptm_sites=ptm_sites,
            pepmass=pepmass,
            charge=best_charge,
        )
        if ptm_hits:
            return SeqResults(original=original, override=ptm_hits)

        # Nothing found — return bare original with no overrides
        return SeqResults(original=original, override=None)

    def get_matched_ppm(
        self,
        sequence: str,
        matched_sequence: str,
        pepmass: float,
        charge: int,
        isotope_offset: int,
    ) -> SeqResults:
        """
        Scenario 2: sequence found in protein DB (canonical, no mods) +
                    the originally identified ProForma sequence whose PTMs
                    become optional candidates.

        Pipeline
        --------
        1. Direct hit with provided charge / isotope_offset.
        2. Charge override scan.
        3. Isotope offset × PTM enumeration (PTM pool = ptm_list ∪ PTMs from
           the original `sequence`, matched by attach_to residue code).

        Parameters
        ----------
        sequence : str
            Original ProForma sequence (may carry PTMs used as candidates).
        matched_sequence : str
            Canonical sequence from DB search (no modifications expected).
        pepmass : float
            Experimental precursor m/z.
        charge : int
            Charge used / found in the original identification.
        isotope_offset : int
            Isotope offset used in the original identification.

        Returns
        -------
        SeqResults
        """
        # Extract PTM candidates from the original sequence
        orig_split, _, _ = _split_and_strip(sequence)
        extra_ptms = self._extract_ptms_as_fixedptm(orig_split)

        # Build extended PTM pool (avoid duplicates by code)
        extended_ptm_codes = {p.code for p in self.ptm_list}
        extended_ptm_list = list(self.ptm_list)
        for ep in extra_ptms:
            if ep.code not in extended_ptm_codes:
                extended_ptm_list.append(ep)
                extended_ptm_codes.add(ep.code)

        # Parse matched_sequence (canonical — should have no mods)
        matched_split, matched_params, matched_canonical = _split_and_strip(matched_sequence)

        # Corrected pepmass for given isotope_offset
        corrected_pepmass = pepmass - isotope_offset * self.isotope_step / charge

        # Build original SeqMatchParams (bare, as-is)
        neutral_matched = calculate_theor_mass(matched_sequence)
        ppm_direct = get_ppm_for_masses(corrected_pepmass, neutral_matched, charge)
        original = SeqMatchParams(
            sequence=matched_sequence,
            seq_neutral_mass=neutral_matched,
            pepmass=pepmass,
            charge=charge,
            ppm=ppm_direct,
            abs_ppm=abs(ppm_direct),
            isotope_offset=None,
        )

        # ── Step 1: direct hit ────────────────────────────────────────────────
        if original.abs_ppm is not None and original.abs_ppm <= self.target_ppm:
            return SeqResults(original=original, override=None)

        # ── Step 2: charge override ───────────────────────────────────────────
        charge_hits, best_charge = self._scan_charges(
            sequence=matched_sequence,
            pepmass=corrected_pepmass,
            neutral_mass=neutral_matched,
        )
        if charge_hits:
            return SeqResults(original=original, override=charge_hits)

        # ── Step 3: isotope offset + PTM enumeration ──────────────────────────
        ptm_sites = _collect_ptm_sites(matched_split, extended_ptm_list)
        ptm_hits = self._scan_offsets_and_ptms(
            canonical_split=matched_split,
            canonical_params=matched_params,
            ptm_sites=ptm_sites,
            pepmass=pepmass,
            charge=best_charge,
            extended_ptm_list=extended_ptm_list,
        )
        if ptm_hits:
            return SeqResults(original=original, override=ptm_hits)

        return SeqResults(original=original, override=None)

    # ── private helpers ──────────────────────────────────────────────────────

    def _make_original(
        self,
        sequence: str,
        pepmass: float,
        charge: int | None,
    ) -> SeqMatchParams:
        neutral = calculate_theor_mass(sequence)
        if charge is not None:
            ppm = get_ppm_for_masses(pepmass, neutral, charge)
            abs_ppm: float | None = abs(ppm)
        else:
            ppm = None
            abs_ppm = None
        return SeqMatchParams(
            sequence=sequence,
            seq_neutral_mass=neutral,
            pepmass=pepmass,
            charge=charge,
            ppm=ppm,
            abs_ppm=abs_ppm,
            isotope_offset=None,
        )

    def _scan_charges(
        self,
        sequence: str,
        pepmass: float,
        neutral_mass: float,
    ) -> tuple[list[SeqMatchParams] | None, int]:
        """
        Try all charges in override_charges range.

        Returns
        -------
        hits : list[SeqMatchParams] | None
            All charges that pass target_ppm, or None if none did.
        best_charge : int
            Charge with minimum abs_ppm across the whole range — used as the
            charge for subsequent PTM / isotope-offset enumeration even when
            no charge alone passed the threshold.
        """
        min_z, max_z = self.override_charges
        hits: list[SeqMatchParams] = []
        best_charge = min_z
        best_abs_ppm = float("inf")

        for z in range(min_z, max_z + 1):
            ppm = get_ppm_for_masses(pepmass, neutral_mass, z)
            abs_ppm = abs(ppm)
            if abs_ppm < best_abs_ppm:
                best_abs_ppm = abs_ppm
                best_charge = z
            if abs_ppm <= self.target_ppm:
                hits.append(SeqMatchParams(
                    sequence=sequence,
                    seq_neutral_mass=neutral_mass,
                    pepmass=pepmass,
                    charge=z,
                    ppm=ppm,
                    abs_ppm=abs_ppm,
                    isotope_offset=None,
                ))

        return (hits if hits else None), best_charge

    def _scan_offsets_and_ptms(
        self,
        canonical_split: list[tuple[str, list | None]],
        canonical_params: dict,
        ptm_sites: list[PossiblePTMPosition],
        pepmass: float,
        charge: int | None,
        extended_ptm_list: list[FixedPTM] | None = None,
    ) -> list[SeqMatchParams] | None:
        """
        Outer loop: isotope offsets 0 … max_isotope_offset.
        Inner loop: all PTM combinations at the given offset.

        Default behaviour: stops at the first offset that yields any hits and
        returns all passing PTM variants for that offset.

        If force_isotope_offset_lookover is True: scans all offsets regardless,
        then returns only the single SeqMatchParams with the lowest abs_ppm
        found across the entire search.
        """
        ptm_list = extended_ptm_list if extended_ptm_list is not None else self.ptm_list

        if charge is None:
            # Without charge we cannot compute m/z — bail out
            return None

        # Guard: too many PTM sites → skip PTM enumeration entirely,
        # fall back to isotope-offset-only search (ptm_sites=[]).
        if len(ptm_sites) > self.max_ptm_sites:
            _seqfixer_log.warning(
                "PTM site count %d exceeds max_ptm_sites=%d — skipping PTM "
                "enumeration, isotope-offset only.",
                len(ptm_sites), self.max_ptm_sites,
            )
            ptm_sites = []

        all_hits: list[SeqMatchParams] = []

        for offset in range(0, self.max_isotope_offset + 1):
            # Isotope correction: shift experimental mass to account for
            # selecting the (offset)-th isotope peak instead of monoisotopic.
            # pepmass_corrected = pepmass - offset * step / charge
            corrected = pepmass - offset * self.isotope_step / charge

            hits = _iter_ptm_combos(
                split=canonical_split,
                params=canonical_params,
                ptm_sites=ptm_sites,
                ptm_list=ptm_list,
                max_ptm=self.max_ptm,
                pepmass_corrected=corrected,
                charge=charge,
                target_ppm=self.target_ppm,
                isotope_offset=offset,
            )

            if hits:
                if not self.force_isotope_offset_lookover:
                    return hits
                all_hits.extend(hits)

        if not all_hits:
            return None

        # force_isotope_offset_lookover: return all hits sorted by abs_ppm
        return sorted(all_hits, key=lambda x: x.abs_ppm if x.abs_ppm is not None else float("inf"))

    @staticmethod
    def _extract_ptms_as_fixedptm(
        split: list[tuple[str, list | None]],
    ) -> list[FixedPTM]:
        """
        Extract modifications present in a parsed ProForma sequence and wrap
        them as FixedPTM objects (attach_to = the residue they were found on).

        Used by get_matched_ppm to transfer PTM candidates from the original
        sequence to the matched (canonical) sequence.
        """
        seen: dict[str, FixedPTM] = {}
        for aa, mods in split:
            if mods is None:
                continue
            for mod in mods:
                code = str(mod)
                if code in seen:
                    # Extend attach_to if the same PTM appears on a new residue
                    existing = seen[code]
                    attach = existing.attach_to
                    if isinstance(attach, str):
                        attach = [attach]
                    if attach is None:
                        attach = []
                    if aa not in attach:
                        attach = list(attach) + [aa]
                    seen[code] = FixedPTM(
                        code=code,
                        attach_to=attach,
                        mono_mass=existing.mono_mass,
                    )
                else:
                    try:
                        seen[code] = FixedPTM(code=code, attach_to=aa)
                    except Exception:
                        # Skip mods that cannot be resolved in the DB
                        pass
        return list(seen.values())
