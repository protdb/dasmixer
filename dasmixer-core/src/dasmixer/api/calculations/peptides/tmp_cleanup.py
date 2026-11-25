"""Cleanup of leftover protein match temporary directories."""

from __future__ import annotations

import shutil
import time

from dasmixer.api.config import config
from dasmixer.utils.logger import logger


def cleanup_peptide_match_tmp(max_age_hours: float = 0) -> None:
    """
    Remove old protein match work directories.

    Deletes the contents of ``{tempdir}/peptide_match`` whose modification time
    is older than ``max_age_hours`` (default 0 = delete everything). Called at
    application start-up, when no protein match run can be active, so deleting
    the previous run's directory (which is kept for debugging, see spec B12) is
    safe. Errors are logged at DEBUG and never propagated.

    Args:
        max_age_hours: Age threshold in hours; 0 (or negative) deletes all.
    """
    try:
        base = config.get_tempdir('root') / 'peptide_match'
    except Exception as exc:
        logger.debug("[tmp_cleanup] Could not resolve peptide_match base dir: %s", exc)
        return

    if not base.exists():
        logger.debug("[tmp_cleanup] peptide_match base dir does not exist: %s", base)
        return

    now = time.time()
    threshold = max_age_hours * 3600
    delete_all = max_age_hours <= 0

    removed = 0
    try:
        children = list(base.iterdir())
    except OSError as exc:
        logger.debug("[tmp_cleanup] Could not list %s: %s", base, exc)
        return

    for child in children:
        try:
            age = now - child.stat().st_mtime
        except OSError as exc:
            logger.debug("[tmp_cleanup] Could not stat %s: %s", child, exc)
            continue

        if not delete_all and age < threshold:
            continue

        try:
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            removed += 1
        except OSError as exc:
            logger.debug("[tmp_cleanup] Could not remove %s: %s", child, exc)

    logger.debug(
        "[tmp_cleanup] Removed %d entries from %s (max_age_hours=%s)",
        removed,
        base,
        max_age_hours,
    )
