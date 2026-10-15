"""
enrich_gate.py — ingest takes priority over auto-enrichment.

Why this exists
---------------
Auto-enrichment (PFAF / Wikidata / iNat fetches + LLM drafts) and ingest
(P1 Syncthing, P2 upload / delta / archive, re-identify batches) both write to
the single SQLite writer. On 15 Oct 2026 a P1 batch of 148 files produced 30
"database is locked" failures: per-card enrichments fired mid-batch, competed
with identification commits, and lost or won the writer at random. Ingest is
the work that must not fail, so enrichment now waits for it.

Three pieces, one module:

1. Ingest registry — batches report liveness in memory (no DB writes):
       ingest_active(key)   # at batch start and on every completed item
       ingest_done(key)     # in the batch's finally / close path
   ingest_busy() is True while any registered batch has reported within
   INGEST_STALL_S. A batch that stops reporting (hung, browser closed,
   process path that never reached its finally) stops blocking enrichment
   after INGEST_STALL_S — the same 5-minute rule scan_sessions.is_stalled
   uses. So the queue drains whether a batch ends normally, fails, or stalls.

2. Card-enrichment queue — queue_card_enrichment(name) replaces the old
   fire-and-forget create_task(_enrich_new_species_card(name)). Species cards
   are still created immediately by _upsert_species_card; only enrichment is
   deferred. One worker task drains the queue, starting nothing while
   ingest_busy().

3. One auto-enrichment at a time — enrichment_slot() is a single shared
   asyncio.Semaphore(1). The queue worker and _run_enrichment_task both hold
   it while enriching, so at most one enrichment touches the DB at once.

Everything is in-memory and lazily bound to the running loop (Python 3.9
pattern, same as pipeline_lock.py / write_lock.py). A server restart empties
the queue; species left unenriched by a restart are picked up by the existing
backfill, exactly as a failed enrichment always has been.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

# Same threshold as scan_sessions.is_stalled (last_heartbeat > 5 min).
INGEST_STALL_S = 300
# How often a waiting worker re-checks ingest state when no batch-end wakes it.
_POLL_S = 15

_slot: Optional[asyncio.Semaphore] = None
_wake: Optional[asyncio.Event] = None
_worker: Optional[asyncio.Task] = None

_batches: Dict[str, float] = {}   # key -> time.monotonic() of last report
_queue: List[str] = []            # species names, FIFO, de-duplicated


def _get_slot() -> asyncio.Semaphore:
    global _slot
    if _slot is None:
        _slot = asyncio.Semaphore(1)
    return _slot


def _get_wake() -> asyncio.Event:
    global _wake
    if _wake is None:
        _wake = asyncio.Event()
    return _wake


# ---------------------------------------------------------------------------
# Ingest registry
# ---------------------------------------------------------------------------

def ingest_active(key: str) -> None:
    """Register a batch, or refresh its liveness. Call at start and per item."""
    if key not in _batches:
        log.info("[enrich_gate] ingest batch active: %s — auto-enrichment deferred", key)
    _batches[key] = time.monotonic()


def ingest_done(key: str) -> None:
    """Deregister a batch. Call from the batch's finally / close path."""
    if _batches.pop(key, None) is not None:
        log.info("[enrich_gate] ingest batch done: %s (queued enrichments: %d)",
                 key, len(_queue))
    # Wake the worker so queued enrichment starts promptly rather than on the
    # next poll. Harmless when nothing is queued.
    _get_wake().set()
    if _queue:
        _ensure_worker()


def ingest_busy() -> bool:
    """True while any registered batch has reported within INGEST_STALL_S."""
    now = time.monotonic()
    busy = False
    for key, last in list(_batches.items()):
        if now - last <= INGEST_STALL_S:
            busy = True
        else:
            # Stalled: stop blocking. Dropped from the registry (logged once);
            # a late report from the same batch simply re-registers it.
            log.warning(
                "[enrich_gate] ingest batch %s silent for %ds — treating as "
                "stalled; no longer deferring enrichment", key, int(now - last),
            )
            _batches.pop(key, None)
    return busy


async def wait_for_ingest_idle(reason: str) -> None:
    """Block until no live ingest batch is registered."""
    if not ingest_busy():
        return
    log.info("[enrich_gate] %s waiting for ingest to finish (%s)",
             reason, ", ".join(sorted(_batches)))
    wake = _get_wake()
    while ingest_busy():
        wake.clear()
        try:
            await asyncio.wait_for(wake.wait(), timeout=_POLL_S)
        except asyncio.TimeoutError:
            pass
    log.info("[enrich_gate] %s — ingest idle, proceeding", reason)


@asynccontextmanager
async def enrichment_slot():
    """The single auto-enrichment slot (Semaphore(1)), exception-safe."""
    slot = _get_slot()
    await slot.acquire()
    try:
        yield
    finally:
        slot.release()


# ---------------------------------------------------------------------------
# Card-enrichment queue + worker
# ---------------------------------------------------------------------------

def queue_card_enrichment(scientific_name: str) -> None:
    """
    Queue a newly-created species card for enrichment. Never blocks; the card
    itself already exists. Runs as soon as no ingest batch is live and the
    enrichment slot is free.
    """
    if scientific_name in _queue:
        return
    _queue.append(scientific_name)
    if ingest_busy():
        log.info("[enrich_gate] queued enrichment for %r until ingest finishes "
                 "(queue: %d)", scientific_name, len(_queue))
    _get_wake().set()
    _ensure_worker()


def queued_names() -> List[str]:
    return list(_queue)


def _ensure_worker() -> None:
    """Start the worker if it is not running (first use, or it ever died)."""
    global _worker
    if _worker is None or _worker.done():
        _worker = asyncio.get_event_loop().create_task(_worker_loop())


async def _worker_loop() -> None:
    from app.api.scan import _enrich_new_species_card

    wake = _get_wake()
    while True:
        try:
            if not _queue:
                wake.clear()
                try:
                    await asyncio.wait_for(wake.wait(), timeout=60)
                except asyncio.TimeoutError:
                    pass
                continue

            if ingest_busy():
                await wait_for_ingest_idle(f"{len(_queue)} queued card enrichment(s)")
                continue

            async with enrichment_slot():
                # The slot may have been held by a long manual/auto batch run;
                # an ingest batch can have started meanwhile. Re-check under
                # the slot so enrichment never starts while ingest is live.
                if ingest_busy() or not _queue:
                    continue
                name = _queue.pop(0)
                log.info("[enrich_gate] starting card enrichment for %r "
                         "(remaining in queue: %d)", name, len(_queue))
                try:
                    await _enrich_new_species_card(name)
                except Exception:
                    # _enrich_new_species_card logs its own failures; this is
                    # the backstop so one species can never kill the worker.
                    log.exception("[enrich_gate] card enrichment raised for %r", name)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("[enrich_gate] worker iteration failed — continuing")
            await asyncio.sleep(_POLL_S)
