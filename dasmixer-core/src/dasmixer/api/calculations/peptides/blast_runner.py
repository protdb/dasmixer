"""BLAST runner.

Runs npysearch in a child process because the native call blocks and writes
its output CSV into the current working directory.
"""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from dasmixer.utils.logger import logger


def _blast_worker(
    query_path: str,
    db_path: str,
    work_dir: str,
    max_accepts: int,
    max_rejects: int,
    min_identity: float,
    result_name: str,
) -> str:
    """Executed in a child process: run npysearch.blast and rename its CSV output."""
    import npysearch as npy

    old_cwd = os.getcwd()
    os.chdir(work_dir)
    try:
        out = npy.blast(
            query_path,
            db_path,
            maxAccepts=max_accepts,
            maxRejects=max_rejects,
            minIdentity=min_identity,
            alphabet='protein',
            outputToFile=True,
        )
        final = os.path.join(work_dir, result_name)
        os.replace(out, final)
        return final
    finally:
        os.chdir(old_cwd)


async def run_blast(
    executor: ProcessPoolExecutor,
    query_path: Path,
    db_path: Path,
    work_dir: Path,
    max_accepts: int,
    max_rejects: int,
    min_identity: float,
    result_name: str,
) -> Path:
    """
    Run npysearch.blast in a child process and return the absolute path to the
    result CSV.

    Raises:
        ImportError: if npysearch is not installed (propagated from the worker).
    """
    loop = asyncio.get_running_loop()
    query_abs = str(Path(query_path).resolve())
    db_abs = str(Path(db_path).resolve())
    work_dir_abs = str(Path(work_dir).resolve())
    logger.debug(
        "run_blast: query=%s identity=%s -> %s",
        query_abs,
        min_identity,
        result_name,
    )
    result = await loop.run_in_executor(
        executor,
        _blast_worker,
        query_abs,
        db_abs,
        work_dir_abs,
        int(max_accepts),
        int(max_rejects),
        float(min_identity),
        str(result_name),
    )
    logger.debug("run_blast: done -> %s", result)
    return Path(result)
