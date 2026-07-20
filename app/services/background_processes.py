"""
Lightweight helpers for creating and updating background_processes rows.

All functions are fire-and-forget safe: exceptions are caught and logged so
a DB hiccup never disrupts the calling process. Pattern mirrors scan_sessions.py.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import text

from app.database import AsyncSessionLocal

log = logging.getLogger(__name__)

# A process is considered stalled when running and last_heartbeat is older than this.
STALL_THRESHOLD_S = 60


async def bp_start(process_type: str, progress_total: int = 0, detail: str = "") -> Optional[int]:
    """
    INSERT a new background_processes row and return its process_id.
    Returns None on any failure.
    """
    try:
        now = datetime.utcnow()
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text(
                    "INSERT INTO background_processes "
                    "(process_type, status, started_at, updated_at, last_heartbeat, "
                    " progress_current, progress_total, detail) "
                    "VALUES (:pt, 'running', :now, :now, :now, 0, :total, :detail)"
                ),
                {"pt": process_type, "now": now, "total": progress_total, "detail": detail},
            )
            await db.commit()
            return result.lastrowid
    except Exception:
        log.exception("background_processes: bp_start failed (type=%s)", process_type)
        return None


async def bp_progress(
    process_id: Optional[int],
    current: int,
    total: int,
    detail: str = "",
    heartbeat: bool = True,
) -> None:
    """Update progress_current, progress_total, detail, and optionally last_heartbeat."""
    if process_id is None:
        return
    try:
        now = datetime.utcnow()
        hb = ", last_heartbeat = :now" if heartbeat else ""
        async with AsyncSessionLocal() as db:
            await db.execute(
                text(
                    f"UPDATE background_processes "
                    f"SET progress_current = :cur, progress_total = :tot, "
                    f"    detail = :detail, updated_at = :now{hb} "
                    f"WHERE process_id = :pid"
                ),
                {"cur": current, "tot": total, "detail": detail, "now": now, "pid": process_id},
            )
            await db.commit()
    except Exception:
        log.exception("background_processes: bp_progress failed (id=%s)", process_id)


async def bp_heartbeat(process_id: Optional[int]) -> None:
    """Stamp last_heartbeat = now (called during long-running loops)."""
    if process_id is None:
        return
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                text("UPDATE background_processes SET last_heartbeat = :now WHERE process_id = :pid"),
                {"now": datetime.utcnow(), "pid": process_id},
            )
            await db.commit()
    except Exception:
        log.exception("background_processes: bp_heartbeat failed (id=%s)", process_id)


async def bp_finish(
    process_id: Optional[int],
    status: str = "complete",
    error: str = "",
    current: Optional[int] = None,
    total: Optional[int] = None,
) -> None:
    """Mark the process as complete / failed / cancelled."""
    if process_id is None:
        return
    try:
        now = datetime.utcnow()
        parts = ["status = :status", "updated_at = :now", "last_heartbeat = :now"]
        params: dict = {"status": status, "now": now, "pid": process_id, "error": error or None}
        parts.append("error = :error")
        if current is not None:
            parts.append("progress_current = :cur")
            params["cur"] = current
        if total is not None:
            parts.append("progress_total = :tot")
            params["tot"] = total
        async with AsyncSessionLocal() as db:
            await db.execute(
                text(f"UPDATE background_processes SET {', '.join(parts)} WHERE process_id = :pid"),
                params,
            )
            await db.commit()
    except Exception:
        log.exception("background_processes: bp_finish failed (id=%s)", process_id)


async def bp_set_status(process_id: Optional[int], status: str, heartbeat: bool = False) -> None:
    """
    Set status field only (used for pause/cancel from the API).

    heartbeat=True also stamps last_heartbeat — needed when returning a row to
    'running' (e.g. enrichment resume), otherwise the row is immediately judged
    stalled by _row_to_dict. Defaults False so pause/cancel behaviour is
    unchanged.
    """
    if process_id is None:
        return
    try:
        hb = ", last_heartbeat = :now" if heartbeat else ""
        async with AsyncSessionLocal() as db:
            await db.execute(
                text(f"UPDATE background_processes SET status = :s, updated_at = :now{hb} WHERE process_id = :pid"),
                {"s": status, "now": datetime.utcnow(), "pid": process_id},
            )
            await db.commit()
    except Exception:
        log.exception("background_processes: bp_set_status failed (id=%s)", process_id)


# ── The stale predicate — ONE definition, two expressions ────────────────────
# "Stale" means: still marked running, but nothing has stamped a heartbeat
# inside the threshold, so the process driving it is not alive.
#
# THREE call sites must agree about what counts as dead:
#   recover_stale_processes()  — startup sweep          (SQL)
#   bp_dismiss()               — manual clear-out       (SQL)
#   _row_to_dict()['is_stalled'] — the flag the UI shows (Python)
# A dismiss looser than the sweep would be a way to clear a row whose worker is
# still running; a display flag looser than either shows STALLED next to a job
# that is working fine, and invites exactly that dismiss.
#
# The predicate cannot literally be shared code — one side is a WHERE clause
# evaluated by SQLite, the other runs on a row already in memory. So they are
# kept clause-for-clause parallel below, over the same fields, against the same
# threshold constant, and their agreement is asserted by test rather than
# assumed. The disjuncts are numbered so the two stay aligned by eye.
#
# Parameterised on :thresh (a UTC datetime). Applies only to status='running';
# callers add their own status handling for paused/terminal rows.
_STALE_WHERE = (
    "status='running' AND ("
    "  (last_heartbeat IS NOT NULL AND last_heartbeat < :thresh) "
    "  OR (last_heartbeat IS NULL AND started_at IS NOT NULL AND started_at < :thresh) "
    "  OR (last_heartbeat IS NULL AND started_at IS NULL) "
    ")"
)


def stale_threshold() -> datetime:
    """The cutoff a heartbeat must beat to count as alive."""
    return datetime.utcnow() - timedelta(seconds=STALL_THRESHOLD_S)


def is_stale_row(
    status: Optional[str],
    last_heartbeat: Optional[datetime],
    started_at: Optional[datetime],
    threshold: Optional[datetime] = None,
) -> bool:
    """
    Python expression of _STALE_WHERE, disjunct for disjunct.

    Takes parsed datetimes (or None) so callers do their own column decoding.
    threshold defaults to stale_threshold() — the SAME cutoff the SQL is given,
    never a second constant.

    Before this was unified, the display flag used its own rule and said
    "stalled" for ANY null heartbeat, ignoring started_at entirely. That marked
    a freshly-started row STALLED for as long as it went without its first
    heartbeat, while the sweep — correctly — left it alone.

    One deliberate difference at the edges: a column that cannot be parsed into
    a datetime arrives here as None, where SQLite would compare the raw value.
    That resolves to the null branches below, i.e. toward "stalled", which shows
    a warning rather than hiding a dead row.
    """
    if status != "running":
        return False
    if threshold is None:
        threshold = stale_threshold()

    # d1: last_heartbeat IS NOT NULL AND last_heartbeat < :thresh
    if last_heartbeat is not None:
        return last_heartbeat < threshold
    # d2: last_heartbeat IS NULL AND started_at IS NOT NULL AND started_at < :thresh
    if started_at is not None:
        return started_at < threshold
    # d3: last_heartbeat IS NULL AND started_at IS NULL
    return True


async def recover_stale_processes() -> None:
    """
    Called once at server startup. Any row still 'running' whose last_heartbeat
    (or started_at, when no heartbeat was ever written) is older than the stall
    threshold was driven by a process that is no longer alive — a hard kill or
    restart mid-run, where the bp_finish in the caller's `finally` never ran.

    Without this a killed process leaves a row that /api/processes/active keeps
    returning forever, because its status clause matches 'running' regardless of
    heartbeat age. Transitioning to 'interrupted' makes it terminal, so it drops
    out once its heartbeat leaves the endpoint's recent window.

    Mirrors queue_api.recover_stale_jobs(), which does exactly this for job_queue.
    """
    try:
        threshold = stale_threshold()
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text(
                    "UPDATE background_processes SET status='interrupted', updated_at=:now "
                    f"WHERE {_STALE_WHERE}"
                ),
                {"now": datetime.utcnow(), "thresh": threshold},
            )
            await db.commit()
            n = result.rowcount
        if n:
            log.info("[processes] Startup recovery: %d stale running process(es) → interrupted", n)
    except Exception:
        log.exception("background_processes: recover_stale_processes failed")


TERMINAL_STATUSES = ("complete", "failed", "cancelled", "interrupted")


async def bp_dismiss(process_id: int) -> dict:
    """
    Clear a DEAD row out of the active feed. Never touches live work.

    Returns {"ok": True, "action": …} on success, or {"ok": False, "reason": …}
    for the caller to turn into an HTTP status:
        "not_found"    — no such row
        "running"      — running with a heartbeat inside the threshold: REFUSED.
                         This is the whole safety property. A dismiss is not a
                         backdoor cancel; if the work should stop, it has to go
                         through a real cancel route that the worker observes.
        "paused"       — deliberately paused and resumable, so not dead either.

    Two accepted cases, both audit-preserving — the row stays, and no recorded
    outcome is ever rewritten:
      • stale (running, heartbeat past the shared _STALE_WHERE cutoff)
        → 'interrupted', the exact transition recover_stale_processes() applies
          at startup. Dismiss is just that sweep, run on demand for one row.
      • already terminal → status left EXACTLY as it is.

    Both then clear last_heartbeat, which is what actually removes the row from
    /api/processes/active: that endpoint returns terminal rows while their
    heartbeat is inside its recency window, so a NULL heartbeat drops the row
    immediately instead of leaving it on screen for another 90 s. The field is a
    liveness signal, not an outcome — on a row that is finished or dead it
    carries no information, while status, error, progress and started_at (the
    audit) are all untouched.
    """
    try:
        threshold = stale_threshold()
        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                text("SELECT status FROM background_processes WHERE process_id = :pid"),
                {"pid": process_id},
            )).fetchone()
            if not row:
                return {"ok": False, "reason": "not_found"}
            status = row[0]

            if status == "paused":
                return {"ok": False, "reason": "paused"}

            if status not in TERMINAL_STATUSES:
                # Running (or any unexpected non-terminal value): only dismissable
                # when the SHARED stale predicate says the driver is gone. The
                # check is done in SQL, in the same statement shape the startup
                # sweep uses, so the two can never diverge.
                stale = (await db.execute(
                    text(
                        "SELECT 1 FROM background_processes "
                        f"WHERE process_id = :pid AND {_STALE_WHERE}"
                    ),
                    {"pid": process_id, "thresh": threshold},
                )).fetchone()
                if not stale:
                    return {"ok": False, "reason": "running"}
                await db.execute(
                    text(
                        "UPDATE background_processes "
                        "SET status='interrupted', updated_at=:now, last_heartbeat=NULL "
                        "WHERE process_id = :pid"
                    ),
                    {"now": datetime.utcnow(), "pid": process_id},
                )
                await db.commit()
                return {"ok": True, "action": "interrupted"}

            # Already terminal — drop it from the feed, leave the outcome alone.
            await db.execute(
                text(
                    "UPDATE background_processes "
                    "SET updated_at=:now, last_heartbeat=NULL WHERE process_id = :pid"
                ),
                {"now": datetime.utcnow(), "pid": process_id},
            )
            await db.commit()
            return {"ok": True, "action": "dismissed"}
    except Exception:
        log.exception("background_processes: bp_dismiss failed (id=%s)", process_id)
        return {"ok": False, "reason": "error"}


async def bp_active_count(process_type: str) -> int:
    """Count rows with status IN ('running', 'paused') for a given process_type."""
    try:
        async with AsyncSessionLocal() as db:
            row = await db.execute(
                text(
                    "SELECT COUNT(*) FROM background_processes "
                    "WHERE process_type = :pt AND status IN ('running', 'paused')"
                ),
                {"pt": process_type},
            )
            return row.scalar() or 0
    except Exception:
        log.exception("background_processes: bp_active_count failed")
        return 0


async def bp_active_row(process_type: str) -> Optional[dict]:
    """Return the most recent active (running/paused) row for a process_type, or None."""
    try:
        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                text(
                    "SELECT process_id, process_type, status, started_at, updated_at, "
                    "       last_heartbeat, progress_current, progress_total, detail, error "
                    "FROM background_processes "
                    "WHERE process_type = :pt AND status IN ('running', 'paused') "
                    "ORDER BY started_at DESC LIMIT 1"
                ),
                {"pt": process_type},
            )).fetchone()
            if not row:
                return None
            return _row_to_dict(row)
    except Exception:
        log.exception("background_processes: bp_active_row failed")
        return None


def _row_to_dict(row) -> dict:
    from datetime import datetime as _dt
    def _dt_parse(v):
        if v is None: return None
        if isinstance(v, _dt): return v
        try: return _dt.fromisoformat(str(v))
        except Exception: return None

    now = datetime.utcnow()
    heartbeat = _dt_parse(row[5])
    status = row[2]
    # Shared predicate — same rule, same threshold as the startup sweep and
    # bp_dismiss. started_at (row[3]) participates; it used to be ignored here.
    is_stalled = is_stale_row(status, heartbeat, _dt_parse(row[3]))
    return {
        "process_id":       row[0],
        "process_type":     row[1],
        "status":           status,
        "started_at":       _dt_parse(row[3]).isoformat() if _dt_parse(row[3]) else None,
        "updated_at":       _dt_parse(row[4]).isoformat() if _dt_parse(row[4]) else None,
        "last_heartbeat":   heartbeat.isoformat() if heartbeat else None,
        "progress_current": row[6] or 0,
        "progress_total":   row[7] or 0,
        "detail":           row[8],
        "error":            row[9],
        "is_stalled":       is_stalled,
        "heartbeat_age_s":  int((now - heartbeat).total_seconds()) if heartbeat else None,
    }
