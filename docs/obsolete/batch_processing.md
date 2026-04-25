# Batch Processing: Reliability and Performance

Describes the approach used for long-running batch write operations in DASMixer,
covering both **Calculate Ions** (`IonCoverageAction`) and **Map Proteins**
(`MatchProteinsAction`).

---

## Problem Statement

Two operations perform large-scale updates to the SQLite project file:

| Operation | Action class | Write method |
|---|---|---|
| Calculate Ions | `IonCoverageAction` | `put_identification_data_batch` |
| Map Proteins | `MatchProteinsAction` | `add_peptide_matches_batch` |

Both share the same failure modes:

1. **File corruption on crash** — without WAL mode, SQLite uses a rollback
   journal (`.journal` file). If the process is killed mid-write, the journal
   is left on disk. On re-open SQLite attempts a rollback, which may leave the
   DB in a partially-recovered state that is unreadable by the application.

2. **Lost work** — a single `commit()` only at the end of the entire run means
   every previously written batch is uncommitted. A crash discards all progress.

3. **Idle I/O time** — the original loop was strictly sequential:
   read → compute → write → read → compute → write …
   The I/O phases (read and write) were not overlapped with the CPU-bound
   compute phase running in a `ProcessPoolExecutor`.

---

## Solution: Three-Layer Fix

### Layer 1 — WAL Journal Mode

`ProjectLifecycle.initialize()` now sets:

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
```

**Why WAL?**

- The WAL file is a forward log, not a rollback log. On crash, SQLite replays
  the WAL into the main file on the *next open* — the main file itself is
  never left in a torn state.
- `synchronous = NORMAL` is safe with WAL: data survives OS crashes (power
  loss), while being significantly faster than the default `FULL` mode.
- Concurrent readers are never blocked by an active writer.

The WAL file (`<project>.dasmix-wal`) is a normal SQLite artefact and is
automatically merged back into the main file on a clean close (`PRAGMA
wal_checkpoint(FULL)` is implicit on `close()`).

### Layer 2 — Per-Batch Lightweight Commit

`ProjectBase` exposes a new method:

```python
async def _commit(self) -> None
```

Unlike `save()`, it commits the current transaction **without** updating
`project_metadata.modified_at`. This makes it cheap enough to call after every
batch write without polluting the metadata table.

The sequence in each pipeline step is:

```
_executemany(UPDATE …)   ← write batch rows
_commit()                ← atomically persist this batch; WAL checkpoint triggered by SQLite
…
save()                   ← called once at the end to update modified_at
```

If the process is killed between two `_commit()` calls, the worst case is
losing the work of the current in-flight batch — never more.

### Layer 3 — Pipeline Overlap (Double-Buffering)

The original loop structure:

```
[read N] ──→ [compute N] ──→ [write N] ──→ [read N+1] ──→ …
```

The new structure (both actions):

```
[read 0] ──→ [compute 0] ─────────────────────────┐
                           [read 1] ──→ [compute 1] ┤
                           [write 0] ───────────────┘
                                        [read 2] ──→ [compute 2] ─┐
                                        [write 1] ─────────────────┘
                                                     …
```

Concretely, using `asyncio.gather`:

```python
# Overlap write of batch N with read of batch N+1
write_task = asyncio.create_task(write_and_commit(pending_results))
read_task  = asyncio.create_task(project.get_next_batch(...))
next_batch, _ = await asyncio.gather(read_task, write_task)
# then compute next_batch while loop iterates
pending_results = await compute(next_batch)
```

**Why this works:**

- `compute` is CPU-bound and runs in a `ProcessPoolExecutor` — it occupies
  worker processes, not the asyncio event loop thread.
- `write` calls `aiosqlite`, which offloads SQLite I/O to a background thread
  — it also does not occupy the event loop thread.
- `read` (DB SELECT + numpy decompression) is also routed through `aiosqlite`.

All three phases are thus genuinely concurrent: compute uses CPU cores, while
read and write share the SQLite thread. In practice the bottleneck shifts from
"waiting for write before reading" to CPU throughput.

**Memory management:**

Heavy objects (deserialized numpy spectrum arrays) are explicitly freed with
`del` immediately after the worker-dict conversion, before compute starts:

```python
worker_batch = [obj.to_worker_dict() for obj in batch_objects]
del batch_objects  # numpy arrays released here
pending_results = await _compute_batch(…, worker_batch, …)
del worker_batch
```

---

## IonCoverageAction — Pipeline Detail

```
IonCoverageAction.run()
│
├─ prime: read batch[0]
├─ prime: compute batch[0]  →  pending_results
│
└─ while True:
    ├─ gather(
    │    write_and_commit(pending_results),   ← aiosqlite thread
    │    read batch[N]                        ← aiosqlite thread
    │  )
    ├─ total_processed += len(pending_results)
    ├─ del pending_results
    ├─ if next batch empty → break
    └─ pending_results = await compute(next_batch)  ← ProcessPoolExecutor
```

The `ProcessPoolExecutor` is kept alive for the full duration of the tool loop
via a `with` block, avoiding subprocess spawn overhead per batch.

---

## MatchProteinsAction — Pipeline Detail

`map_proteins` is an `AsyncGenerator` that internally handles read + BLAST +
ion recalculation and yields `(matches_df, count, tool_id)` per batch.
Because the generator is itself async, it can be overlapped with the write of
the previous result using the same pattern:

```python
write_task = asyncio.create_task(write_and_commit(pending_df))
next_task  = asyncio.create_task(_anext_or_none(gen))
_, next_item = await asyncio.gather(write_task, next_task)
```

`_anext_or_none` is a module-level helper that wraps `StopAsyncIteration` into
a `None` return so it composes cleanly with `asyncio.gather`.

Note: `map_proteins` is CPU-bound internally (BLAST via `npysearch`, ion match
via `match_predictions`) but runs entirely in the asyncio thread because it
does not use a process pool. The overlap benefit here is primarily hiding the
DB write latency behind generator execution.

---

## File Locations

| File | Change |
|---|---|
| `dasmixer/api/project/core/lifecycle.py` | `PRAGMA journal_mode = WAL`, `PRAGMA synchronous = NORMAL` in `initialize()` |
| `dasmixer/api/project/core/base.py` | Added `_commit()` lightweight commit method |
| `dasmixer/gui/actions/ion_actions.py` | Pipeline overlap, per-batch `_commit()`, explicit `del` of spectrum arrays |
| `dasmixer/gui/actions/protein_map_action.py` | Pipeline overlap, per-batch `_commit()`, `_anext_or_none` helper |
