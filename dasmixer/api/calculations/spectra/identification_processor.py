import logging
import os
import time
import traceback
from pathlib import Path
from typing import Literal

from dasmixer.api.calculations.ppm import SeqFixer, SeqMatchParams
from dasmixer.utils.seqfixer_utils import PTMS, FixedPTM
from dasmixer.api.calculations.spectra.ion_match import IonMatchParameters, match_predictions, MatchResult

# ---------------------------------------------------------------------------
# Per-worker file logger
# ---------------------------------------------------------------------------
# Each worker process gets its own log file named worker_<PID>.log so there is
# no contention and we can pinpoint exactly which identification causes a hang.
# Logging is intentionally coarse (one line per item) to keep overhead low.
# ---------------------------------------------------------------------------

_worker_logger: logging.Logger | None = None


def _get_worker_logger() -> logging.Logger:
    """
    Return (and lazily create) the per-process logger.

    Behaviour depends on AppConfig:
    - log_to_file=False: returns the root logger (all worker output goes to
      the main app log or is discarded if no handlers are configured).
    - log_to_file=True, log_separate_workers=True: each worker writes its own
      per-PID file under log_folder (or the default cache dir).
    - log_to_file=True, log_separate_workers=False: propagates to root logger
      so all output is merged into the single dasmixer log file.
    """
    global _worker_logger
    if _worker_logger is not None:
        return _worker_logger

    # Try to read config; fall back to standalone per-PID file on any error
    try:
        from dasmixer.api.config import config as _cfg
        log_to_file: bool = bool(_cfg.log_to_file)
        separate_workers: bool = bool(_cfg.log_separate_workers)
        log_level_name: str = _cfg.log_level or "DEBUG"
        log_folder_str: str | None = _cfg.log_folder
    except Exception:
        log_to_file = True
        separate_workers = True
        log_level_name = "DEBUG"
        log_folder_str = None

    level = getattr(logging, log_level_name, logging.DEBUG)
    pid = os.getpid()
    logger_name = f"dasmixer.worker.{pid}"

    if not log_to_file:
        # Logging disabled globally — return a no-op logger
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.CRITICAL + 1)
        logger.propagate = False
        _worker_logger = logger
        return logger

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    if separate_workers:
        # Write to a dedicated per-PID file
        logger.propagate = False
        if not logger.handlers:
            log_dir = (
                Path(log_folder_str) / "workers"
                if log_folder_str
                else Path.home() / ".cache" / "dasmixer" / "worker_logs"
            )
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / f"worker_{pid}.log"
            fh = logging.FileHandler(log_path, mode="a", encoding="utf-8")
            fh.setLevel(level)
            fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            logger.addHandler(fh)
    else:
        # Propagate to root logger (merged with main app log)
        logger.propagate = True

    _worker_logger = logger
    return logger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_best_override(
    overrides: list[tuple[SeqMatchParams, MatchResult]], criteria: str
) -> tuple[SeqMatchParams, MatchResult]:
    """Select the best override by primary criterion, then by abs_ppm."""
    if criteria == "coverage":
        criteria = "intensity_percent"
    overrides.sort(key=lambda row: (-getattr(row[1], criteria), row[0].abs_ppm))
    return overrides[0]


def process_single_ident(
    fixer: SeqFixer,
    params: IonMatchParameters,
    fragment_charges: list[int],
    sequence: str,
    pepmass: float,
    mz_array,
    intensity_array,
    mgf_charge: int | None = None,
    selection_criteria: str = "intensity_percent",
) -> dict:
    seq_results = fixer.get_ppm(sequence, pepmass, mgf_charge)
    if not seq_results.override:
        ppm_result = seq_results.original
        match_result = match_predictions(
            params=params,
            mz=mz_array,
            intensity=intensity_array,
            charges=fragment_charges,
            sequence=sequence,
        )
    else:
        all_matches = []
        for override in seq_results.override:
            match_res = match_predictions(
                params=params,
                mz=mz_array,
                intensity=intensity_array,
                charges=fragment_charges,
                sequence=override.sequence,
            )
            all_matches.append((override, match_res))
        ppm_result, match_result = _get_best_override(all_matches, criteria=selection_criteria)

    return {
        "sequence": ppm_result.sequence,
        "ppm": ppm_result.ppm,
        "theor_mass": ppm_result.seq_neutral_mass,
        "override_charge": ppm_result.charge,
        "isotope_offset": ppm_result.isotope_offset,
        "intensity_coverage": match_result.intensity_percent,
        "ions_matched": match_result.max_ion_matches,
        "ion_match_type": match_result.top_matched_ion_type,
        "top_peaks_covered": match_result.top10_intensity_matches,
    }


def process_matched_peptide():
    pass


# ---------------------------------------------------------------------------
# Batch entry point (called from ProcessPoolExecutor)
# ---------------------------------------------------------------------------

def process_identificatons_batch(
    batch: list[dict],
    params_dict: dict,
    fragment_charges: list[int],
    target_ppm: float,
    min_charge: int = 1,
    max_charge: int = 4,
    max_isotope_offset: int = 2,
    force_isotope_offset_lookover: bool = True,
    ptm_names_list: list[str] | None = None,
    max_ptm: int = 5,
    seq_criteria: Literal["peaks", "top_peaks", "coverage"] = "coverage",
    max_ptm_sites: int = 10,
) -> list[dict]:
    log = _get_worker_logger()
    log.info("=== batch START  size=%d  pid=%d ===", len(batch), os.getpid())

    params = IonMatchParameters(
        ions=params_dict.get("ions", ["b", "y"]),
        tolerance=params_dict.get("tolerance", 20.0),
        mode=params_dict.get("mode", "largest"),
        water_loss=params_dict.get("water_loss", False),
        ammonia_loss=params_dict.get("ammonia_loss", False),
    )
    if ptm_names_list is None:
        ptms = PTMS
    else:
        ptms = [x for x in PTMS if x.code in ptm_names_list]

    fixer = SeqFixer(
        ptm_list=ptms,
        max_ptm=max_ptm,
        target_ppm=target_ppm,
        override_charges=(min_charge, max_charge),
        max_isotope_offset=max_isotope_offset,
        force_isotope_offset_lookover=force_isotope_offset_lookover,
        max_ptm_sites=max_ptm_sites,
    )

    results = []
    for item in batch:
        ident_id = item["id"]
        spectre_id = item.get("spectre_id", "?")
        sequence = item.get("sequence", "")
        pepmass = item.get("pepmass")
        charge = item.get("charge")
        mz_array = item.get("mz_array", [])
        intensity_array = item.get("intensity_array", [])

        log.debug(
            "ENTER  ident_id=%s  spectre_id=%s  seq=%s  pepmass=%s  charge=%s  peaks=%d",
            ident_id, spectre_id, sequence, pepmass, charge, len(mz_array),
        )
        t0 = time.monotonic()

        try:
            result = process_single_ident(
                fixer,
                params,
                fragment_charges,
                sequence,
                pepmass,
                mz_array,
                intensity_array,
                mgf_charge=charge,
                selection_criteria=seq_criteria,
            )
            elapsed = time.monotonic() - t0
            log.debug(
                "DONE   ident_id=%s  spectre_id=%s  elapsed=%.3fs  ppm=%s  cov=%s",
                ident_id, spectre_id, elapsed,
                result.get("ppm"), result.get("intensity_coverage"),
            )
            result["id"] = ident_id
            result["source_sequence"] = sequence
            results.append(result)

        except Exception as exc:
            elapsed = time.monotonic() - t0
            log.error(
                "ERROR  ident_id=%s  spectre_id=%s  elapsed=%.3fs  exc=%s\n%s",
                ident_id, spectre_id, elapsed, exc, traceback.format_exc(),
            )
            results.append({
                "id": ident_id,
                "sequence": sequence,
                "ppm": None,
                "theor_mass": None,
                "override_charge": None,
                "intensity_coverage": None,
                "ions_matched": None,
                "ion_match_type": None,
                "top_peaks_covered": None,
                "isotope_offset": None,
                "source_sequence": sequence,
            })

    log.info("=== batch DONE   size=%d  results=%d ===", len(batch), len(results))
    return results
