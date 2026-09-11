"""PTM configuration: user-editable CSV files for FixedPTM defaults and
identification-parser PTM renames. Files live in {app_dir}/ptm/ and are
created from built-in defaults on first run if absent."""

import csv
from functools import lru_cache
from pathlib import Path

import typer


def get_ptm_config_dir() -> Path:
    d = Path(typer.get_app_dir("dasmixer")) / "ptm"
    d.mkdir(parents=True, exist_ok=True)
    return d


ALL_PTM_CONFIG_FILENAME = "all_ptm_config.csv"
IMPORT_PTM_RENAMES_FILENAME = "import_ptm_renames.csv"


# name, attach_to (tuple[str,...] | None), mono_mass (float | None), n_term, c_term, default
DEFAULT_PTM_CONFIG: list[tuple[str, tuple[str, ...] | None, float | None, bool, bool, bool]] = [
    ("Acetyl", ("K",), 42.010565, True, False, False),
    ("Amidated", None, None, False, True, True),
    ("Carbamidomethyl", ("C",), 57.021464, True, False, False),
    ("Carbamyl", ("K",), 43.005814, True, False, False),
    ("Carboxymethyl", ("C",), 58.005479, False, False, False),
    ("Deamidated", ("N", "Q"), 0.984016, False, False, True),
    ("Met->Hse", ("M",), -29.992806, False, False, False),
    ("Met->Hsl", ("M",), -48.003371, False, False, False),
    ("NIPCAM", ("C",), 99.068414, False, False, False),
    ("Phospho", ("S", "T", "Y"), 79.966331, False, False, False),
    ("Dehydrated", ("C",), -18.010565, False, False, False),
    ("Propionamide", ("C",), 71.037114, False, False, False),
    ("Pyro-carbamidomethyl", ("C",), 39.994915, False, False, False),
    ("Glu->pyro-Glu", ("E",), -18.010565, False, False, False),
    ("Gln->pyro-Glu", ("Q",), -17.026549, False, False, False),
    ("Cation:Na", ("D", "E"), 21.981943, False, True, False),
    ("Pyridylethyl", ("C",), None, False, False, True),
    ("Methyl", ("D", "E"), 14.01565, False, True, False),
    ("Oxidation", ("H", "M", "W"), 15.994915, False, False, False),
    ("Methylthio", ("C",), 45.987721, False, False, False),
    ("Sulfo", ("S", "T", "Y"), 79.956815, False, False, False),
    ("Guanidinyl", ("K",), 42.021798, False, False, False),
    ("ICAT-C", ("C",), 227.126991, False, False, False),
    ("ICAT-C:13C(9)", ("C",), 236.157185, False, False, False),
    ("Formyl", None, 27.994915, True, False, False),
    ("Label:18O(2)", None, 4.008491, False, True, False),
    ("iTRAQ4plex", ("K", "Y"), 144.102063, True, False, False),
    ("Label:18O(1)", None, 2.004246, False, True, False),
    ("ICPL:13C(6)", ("K",), 111.041593, True, False, False),
    ("ICPL", ("K",), 105.021464, True, False, False),
    ("Dehydro", ("C",), -1.007825, False, False, False),
    ("Ammonia-loss", ("C",), -17.026549, False, False, False),
    ("Dioxidation", ("M",), 31.989829, False, False, False),
    ("ICPL:2H(4)", ("K",), 109.046571, True, False, False),
    ("iTRAQ8plex", ("K", "Y"), 304.20536, True, False, False),
    ("TMT6plex", ("K",), 229.162932, True, False, False),
    ("TMT2plex", ("K",), 225.155833, True, False, False),
    ("mTRAQ", ("K", "Y"), 140.094963, True, False, False),
    ("ICPL:13C(6)2H(4)", ("K",), 115.0667, True, False, False),
    ("mTRAQ:13C(3)15N(1)", ("K", "Y"), 144.102063, True, False, False),
    ("mTRAQ:13C(6)15N(2)", ("K", "Y"), 148.109162, True, False, False),
    ("TMTpro", ("K",), 304.207146, True, False, False),
    ("6C-CysPAT", ("C",), 221.081695, True, False, False),
]

# source, proforma, parser, is_terminal
DEFAULT_PTM_RENAMES: list[tuple[str, str, str, bool]] = [
    # --- MaxQuant (MQ_Evidences.py: ptm_replacements) ---
    ("(Deamidation (NQ))", "[Deamidated]", "MaxQuant", False),
    ("(de)", "[Deamidated]", "MaxQuant", False),
    ("_", "", "MaxQuant", False),
    ("(Pyridylethyl)", "[Pyridylethyl]", "MaxQuant", False),
    ("(Oxidation (M))", "[Oxidation]", "MaxQuant", False),
    ("(Phospho (STY))", "[Phospho]", "MaxQuant", False),
    ("(ox)", "[Oxidation]", "MaxQuant", False),
    ("(Acetyl (Protein N-term))", "[-89.029920]-", "MaxQuant", True),
    # --- PLGS (PLGS.py: ptm_renames dict) ---
    ("S-pyridylethyl", "Pyridylethyl", "PLGS", False),
    ("Deamidation", "Deamidated", "PLGS", False),
    # --- PeptideShaker (PeptideShaker.py: terminal_ptm + internal_ptm dicts) ---
    ("NH2", "Amidated", "PeptideShaker XLS", True),
    ("COOH", "Carboxy", "PeptideShaker XLS", True),
    ("pyroE", "Glu->pyro-Glu", "PeptideShaker XLS", True),
    ("pyroQ", "Gln->pyro-Glu", "PeptideShaker XLS", True),
    ("pyri", "Pyridylethyl", "PeptideShaker XLS", False),
    ("deam", "Deamidated", "PeptideShaker XLS", False),
    ("ox", "Oxidation", "PeptideShaker XLS", False),
    ("p", "Phospho", "PeptideShaker XLS", False),
]


def _ensure_all_ptm_config_file() -> Path:
    """Create all_ptm_config.csv from DEFAULT_PTM_CONFIG if file does not exist."""
    path = get_ptm_config_dir() / ALL_PTM_CONFIG_FILENAME
    if not path.exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "attach_to", "mono_mass", "n_term", "c_term", "default"])
            for name, attach_to, mono_mass, n_term, c_term, is_default in DEFAULT_PTM_CONFIG:
                writer.writerow([
                    name,
                    ";".join(attach_to) if attach_to else "",
                    "" if mono_mass is None else mono_mass,
                    "Y" if n_term else "N",
                    "Y" if c_term else "N",
                    "Y" if is_default else "N",
                ])
    return path


@lru_cache(maxsize=1)
def load_ptm_config() -> list[dict]:
    """
    Read all_ptm_config.csv (creates if absent), return list of raw records.

    Each record is a dict with keys: name (str), attach_to (list[str] | None),
    mono_mass (float | None), n_term (bool), c_term (bool), default (bool).
    """
    path = _ensure_all_ptm_config_file()
    result = []
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            attach_raw = (row.get("attach_to") or "").strip()
            attach_to = attach_raw.split(";") if attach_raw else None
            mass_raw = (row.get("mono_mass") or "").strip()
            result.append({
                "name": row["name"].strip(),
                "attach_to": attach_to,
                "mono_mass": float(mass_raw) if mass_raw else None,
                "n_term": (row.get("n_term") or "").strip().upper() == "Y",
                "c_term": (row.get("c_term") or "").strip().upper() == "Y",
                "default": (row.get("default") or "").strip().upper() == "Y",
            })
    return result


def _ensure_import_ptm_renames_file() -> Path:
    """Create import_ptm_renames.csv from DEFAULT_PTM_RENAMES if file does not exist."""
    path = get_ptm_config_dir() / IMPORT_PTM_RENAMES_FILENAME
    if not path.exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["source", "proforma", "parser", "is_terminal"])
            for source, proforma, parser, is_terminal in DEFAULT_PTM_RENAMES:
                writer.writerow([source, proforma, parser, "Y" if is_terminal else "N"])
    return path


@lru_cache(maxsize=1)
def load_ptm_renames() -> list[dict]:
    """
    Read import_ptm_renames.csv (creates if absent). Each record:
    {"source": str, "proforma": str, "parser": str, "is_terminal": bool}.
    """
    path = _ensure_import_ptm_renames_file()
    result = []
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            result.append({
                "source": row["source"],
                "proforma": row["proforma"],
                "parser": row["parser"].strip(),
                "is_terminal": (row.get("is_terminal") or "").strip().upper() == "Y",
            })
    return result