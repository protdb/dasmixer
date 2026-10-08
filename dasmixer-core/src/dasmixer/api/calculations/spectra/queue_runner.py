"""Queue runner for batch identification processing.

Runs a process-pool worker function over contiguous chunks of identification
dicts with bounded in-flight concurrency, accumulating and periodically
flushing results via an async callback. This module is pure core logic: it
does not touch the database and must not import from ``dasmixer.gui.*``.
"""

from __future__ import annotations

import asyncio
import functools
import logging
from concurrent.futures import ProcessPoolExecutor
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

__all__ = ["run_identification_queue"]


async def run_identification_queue(
    worker_dicts: list[dict],
    executor: ProcessPoolExecutor,
    chunk_size: int,
    flush_every: int,
    process_fn: Callable[..., list[dict]],
    process_fn_kwargs: dict,
    flush_callback: Callable[[list[dict]], Awaitable[None]],
    progress_callback: Callable[[int], None] | None = None,
    stop_check: Callable[[], bool] | None = None,
) -> int:
    """Process identifications in parallel chunks and flush results in batches.

    Splits ``worker_dicts`` into contiguous chunks of ``chunk_size`` items,
    submits each chunk to ``executor`` via ``loop.run_in_executor`` (passing
    the chunk positionally as the first argument and ``process_fn_kwargs``
    as keyword arguments), and bounds the number of in-flight tasks with a
    semaphore sized to the executor's worker count. Completed results are
    accumulated and handed to ``flush_callback`` every ``flush_every``
    completed chunks (plus one final flush for any remainder).

    Parameters
    ----------
    worker_dicts:
        Identification dicts to process. Processed in-place order is not
        preserved for results, but each dict belongs to exactly one chunk.
    executor:
        The ``ProcessPoolExecutor`` that runs ``process_fn`` chunks.
    chunk_size:
        Number of dicts per chunk. Values < 1 are treated as 1.
    flush_every:
        Flush accumulated results after this many completed chunks.
        Values < 1 are treated as 1.
    process_fn:
        Worker function executed in the pool. It is called as
        ``process_fn(chunk, **process_fn_kwargs)`` and must return a
        ``list[dict]`` of result rows.
    process_fn_kwargs:
        Extra keyword arguments passed to ``process_fn``.
    flush_callback:
        Async callback receiving the accumulated result rows. Called
        every ``flush_every`` completed chunks and once more at the end
        if any unflushed rows remain.
    progress_callback:
        Optional synchronous callback invoked with the cumulative count
        of processed identifications after each completed chunk.
    stop_check:
        Optional synchronous callback; if it returns ``True`` after a
        completed chunk, the processing loop stops early (already
        completed results are still flushed).

    Returns
    -------
    int
        Total number of processed identifications (sum of returned rows).
    """
    if not worker_dicts:
        logger.debug("run_identification_queue: empty input, nothing to do")
        return 0

    if chunk_size < 1:
        chunk_size = 1
    if flush_every < 1:
        flush_every = 1

    chunks = [worker_dicts[i:i + chunk_size] for i in range(0, len(worker_dicts), chunk_size)]

    max_workers = getattr(executor, "_max_workers", None) or len(chunks)
    sem = asyncio.Semaphore(max_workers)
    loop = asyncio.get_running_loop()

    async def _run_chunk(chunk: list[dict]) -> list[dict]:
        async with sem:
            # run_in_executor only takes positional args, so bind the chunk
            # (positional) and process_fn_kwargs (keyword) via functools.partial.
            fn = functools.partial(process_fn, chunk, **process_fn_kwargs)
            return await loop.run_in_executor(executor, fn)

    tasks = [asyncio.create_task(_run_chunk(chunk)) for chunk in chunks]

    accumulated: list[dict] = []
    processed: int = 0
    completed: int = 0

    for coro in asyncio.as_completed(tasks):
        rows = await coro
        accumulated.extend(rows)
        processed += len(rows)
        completed += 1

        if progress_callback is not None:
            progress_callback(processed)

        if stop_check is not None and stop_check():
            logger.debug("run_identification_queue: stop requested after %s chunks", completed)
            break

        if completed % flush_every == 0:
            await flush_callback(accumulated)
            accumulated = []

    if accumulated:
        await flush_callback(accumulated)

    # After an early stop, cancel and reap any still-pending chunk tasks so
    # their abandoned results do not surface as "Task exception was never
    # retrieved" warnings when the executor shuts down. Their rows are
    # intentionally discarded: the caller requested a stop. This is a no-op
    # after normal completion (all tasks are already done).
    pending = [t for t in tasks if not t.done()]
    if pending:
        for t in pending:
            t.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    logger.debug(
        "run_identification_queue: done, processed %s identifications in %s/%s chunks",
        processed,
        completed,
        len(chunks),
    )
    return processed
