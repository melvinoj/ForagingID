"""
Shared pipeline mutex — prevents P1 (Syncthing) and P2 (archive scan) from
running concurrently. SQLite is single-writer; overlapping batch writes cause
lock contention and job failures.

Usage at each pipeline's outermost entry point:

    from app.services.pipeline_lock import pipeline_try_acquire, pipeline_release, pipeline_holder

    acquired = await pipeline_try_acquire("P1 (Syncthing)")
    if not acquired:
        log.warning("[P1] SKIPPED — mutex held by %s", pipeline_holder())
        return
    try:
        ...pipeline body...
    finally:
        pipeline_release()

Non-blocking: pipeline_try_acquire never waits. If the lock is already held it
returns False immediately so the caller can skip-and-log. No queuing, no retry.

The asyncio.Lock is lazily initialised (Python 3.9 pattern) so it binds to the
running event loop rather than the import-time context.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger(__name__)

_lock: Optional[asyncio.Lock] = None
_holder: Optional[str] = None
_acquired_at: Optional[datetime] = None


def _get_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


async def pipeline_try_acquire(pipeline_name: str) -> bool:
    """
    Try to acquire the shared pipeline mutex without blocking.

    Returns True (lock is now held by caller) or False (lock already held;
    caller must skip its run). In asyncio, the check-then-acquire sequence is
    race-safe: no other coroutine can run between locked() returning False and
    the non-contended acquire() completing, because neither step suspends.
    """
    global _holder, _acquired_at
    lk = _get_lock()
    if lk.locked():
        return False
    await lk.acquire()
    _holder = pipeline_name
    _acquired_at = datetime.utcnow()
    return True


def pipeline_release() -> None:
    """Release the shared pipeline mutex. Must be called in a finally block."""
    global _holder, _acquired_at
    prev_holder = _holder
    _holder = None
    _acquired_at = None
    lk = _get_lock()
    try:
        lk.release()
    except RuntimeError:
        log.error(
            "[pipeline_lock] release() called but lock was not held "
            "(previous holder: %s)", prev_holder,
        )


def pipeline_holder() -> Optional[str]:
    """Return the name of the pipeline currently holding the lock, or None."""
    return _holder


def pipeline_acquired_at() -> Optional[datetime]:
    """Return the UTC datetime when the lock was last acquired, or None."""
    return _acquired_at
