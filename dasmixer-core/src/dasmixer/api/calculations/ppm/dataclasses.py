from dataclasses import dataclass

@dataclass
class SeqMatchParams:
    sequence: str
    seq_neutral_mass: float
    pepmass: float
    charge: int | None = None
    ppm: float | None = None
    abs_ppm: float | None = None
    isotope_offset: int | None = None

@dataclass
class SeqResults:
    original: SeqMatchParams
    override: list[SeqMatchParams] | None