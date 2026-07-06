"""
write_lock.py — app-level async write serialisation.

A single asyncio.Lock that both user-facing write endpoints and background
job loops acquire before committing to the DB. This prevents the up-to-10s
SQLite busy-wait that occurs when a user write (accept_species, etc.) contends
with a background job's in-flight commit.

WAL mode + the 10s busy_timeout remain as the safety net.  Under normal
operation this lock ensures writes take ordered turns — each commit is
milliseconds, so the wait is imperceptible.

Usage:
    from app.services.write_lock import db_write_lock

    # Do reads/compute outside the lock:
    rows = await db.execute(...)

    # Wrap ONLY the commit (and any ORM mutations that must be atomic with it):
    async with db_write_lock():
        obs.field = value
        await db.commit()

Background job loops MUST acquire-and-release per iteration, never wrap
the whole loop, so a user write can always slot in between iterations.

The lock is lazily initialised (Python 3.9 pattern) to bind to the
running event loop rather than the import-time context.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

_lock: Optional[asyncio.Lock] = None


def _get_lock() -> asyncio.Lock:
    global _lock
    if _lock is None:
        _lock = asyncio.Lock()
    return _lock


@asynccontextmanager
async def db_write_lock():
    """
    Async context manager that acquires the global DB write lock on entry
    and releases it on exit (in a finally block — exception-safe).

    This is a BLOCKING acquire: the caller always waits for the lock and
    then proceeds.  It never skips.  Do not use where skip-and-log is wanted
    (see pipeline_lock.py for that pattern).
    """
    lock = _get_lock()
    await lock.acquire()
    try:
        yield
    finally:
        lock.release()
