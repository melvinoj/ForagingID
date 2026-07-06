"""
Scan session service — lightweight helpers for creating and updating
scan_sessions rows. Used by both pipelines; never touches identification logic.

All functions are fire-and-forget safe: they catch and log exceptions so a DB
hiccup never disrupts the pipeline that calls them.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text

from app.database import AsyncSessionLocal

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Label builders
# ---------------------------------------------------------------------------

def _label_p1(started_at: datetime, files_received: int) -> str:
    """Pipeline 1 label: '2026-05-30 21:15 (124 files)'"""
    ts = started_at.strftime("%Y-%m-%d %H:%M")
    return f"{ts} ({files_received} file{'s' if files_received != 1 else ''})"


def _label_p2(started_at: datetime, files_received: int, source_path: Optional[str]) -> str:
    """
    Pipeline 2 label:
      folder supplied → 'Gresgen Walk - 2026-05-30 (84 files)'
      no folder       → 'Upload - 2026-05-30 (12 files)'
    """
    date = started_at.strftime("%Y-%m-%d")
    n = f"{files_received} file{'s' if files_received != 1 else ''}"
    if source_path:
        # Use the last component of the path as the folder name
        import os
        folder = os.path.basename(source_path.rstrip("/\\")) or source_path
        return f"{folder} - {date} ({n})"
    return f"Upload - {date} ({n})"


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

async def session_create(
    pipeline: int,
    files_received: int,
    source_path: Optional[str] = None,
) -> Optional[int]:
    """
    Insert a new scan_sessions row and return its id.
    Returns None on any failure (non-fatal).
    """
    try:
        now = datetime.utcnow()
        if pipeline == 1:
            label = _label_p1(now, files_received)
        else:
            label = _label_p2(now, files_received, source_path)

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text(
                    "INSERT INTO scan_sessions "
                    "(pipeline, label, started_at, files_received, "
                    " files_processed, files_approved, files_review, "
                    " files_rejected, files_failed, files_skipped, source_path, "
                    " status, last_heartbeat, files_new, files_retryable, files_already_processed) "
                    "VALUES (:pipeline, :label, :started_at, :files_received, "
                    "        0, 0, 0, 0, 0, 0, :source_path, "
                    "        'running', :started_at, 0, 0, 0)"
                ),
                {
                    "pipeline":       pipeline,
                    "label":          label,
                    "started_at":     now,
                    "files_received": files_received,
                    "source_path":    source_path,
                },
            )
            await db.commit()
            return result.lastrowid
    except Exception:
        log.exception("scan_sessions: session_create failed")
        return None


async def session_open_p1(files_received: int, window_s: int = 300) -> Optional[int]:
    """
    Pipeline-1 session opener with a coalescing window.

    Syncthing delivers a phone batch over 1-3 minutes; the 60s auto-scan loop
    would otherwise open a fresh session on every tick that finds new files,
    fragmenting one transfer into several rows (e.g. 7 photos recorded as
    2 + 4 + 1). To present one transfer as a single session, reuse the most
    recent P1 session when it ended within `window_s` seconds (or is still
    open), extending its received-file count, recomputing its label, and
    reopening it (ended_at -> NULL). Otherwise create a fresh session.

    Returns the session id (reopened or new), or None on failure (non-fatal —
    the caller treats None as "no session tracking").
    """
    try:
        now = datetime.utcnow()
        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                text(
                    "SELECT id, started_at, ended_at, files_received "
                    "FROM scan_sessions WHERE pipeline = 1 "
                    "ORDER BY started_at DESC LIMIT 1"
                )
            )).fetchone()

            if row is not None:
                started = _to_dt(row[1])
                ended = _to_dt(row[2])
                # Coalesce if the previous session is still open, or closed
                # within the window.
                within_window = ended is None or (now - ended).total_seconds() <= window_s
                if within_window:
                    new_total = (row[3] or 0) + files_received
                    label = _label_p1(started or now, new_total)
                    await db.execute(
                        text(
                            "UPDATE scan_sessions "
                            "SET files_received = :n, ended_at = NULL, label = :label "
                            "WHERE id = :id"
                        ),
                        {"n": new_total, "label": label, "id": row[0]},
                    )
                    await db.commit()
                    return row[0]
    except Exception:
        log.exception("scan_sessions: session_open_p1 coalesce failed")

    # No recent session to coalesce into (or the lookup failed) — start fresh.
    return await session_create(pipeline=1, files_received=files_received)


async def session_inc(session_id: Optional[int], **fields: int) -> None:
    """
    Atomically increment one or more counter fields on a session row.
    Accepted field names: files_processed, files_approved, files_review,
                          files_rejected, files_failed.
    Silently does nothing if session_id is None or row not found.
    """
    if session_id is None:
        return
    _allowed = {
        "files_processed", "files_approved", "files_review",
        "files_rejected", "files_duplicate", "files_failed", "files_skipped",
        "files_new", "files_retryable", "files_already_processed",
    }
    cols = {k: v for k, v in fields.items() if k in _allowed and v}
    if not cols:
        return
    try:
        sets = ", ".join(f"{c} = {c} + :{c}" for c in cols)
        params = {c: v for c, v in cols.items()}
        params["id"] = session_id
        async with AsyncSessionLocal() as db:
            await db.execute(
                text(f"UPDATE scan_sessions SET {sets} WHERE id = :id"),
                params,
            )
            await db.commit()
    except Exception:
        log.exception("scan_sessions: session_inc failed (session_id=%s)", session_id)


async def session_close(session_id: Optional[int]) -> None:
    """Set ended_at = now and status = 'complete' on a session row."""
    if session_id is None:
        return
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                text(
                    "UPDATE scan_sessions "
                    "SET ended_at = :t, status = 'complete' "
                    "WHERE id = :id"
                ),
                {"t": datetime.utcnow(), "id": session_id},
            )
            await db.commit()
    except Exception:
        log.exception("scan_sessions: session_close failed (session_id=%s)", session_id)


async def session_set_status(session_id: Optional[int], status: str) -> None:
    """
    Update the status field on a session row.
    Valid values: queued / running / paused / complete / failed / stalled.
    Silently ignores None / missing rows.
    """
    if session_id is None:
        return
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                text("UPDATE scan_sessions SET status = :s WHERE id = :id"),
                {"s": status, "id": session_id},
            )
            await db.commit()
    except Exception:
        log.exception("scan_sessions: session_set_status failed (session_id=%s, status=%s)",
                      session_id, status)


async def session_heartbeat(session_id: Optional[int]) -> None:
    """
    Stamp last_heartbeat = now.  Called every ~10 files during a running batch
    so the UI can distinguish a live batch from a stalled one.
    Silently ignores None / missing rows.
    """
    if session_id is None:
        return
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                text("UPDATE scan_sessions SET last_heartbeat = :t WHERE id = :id"),
                {"t": datetime.utcnow(), "id": session_id},
            )
            await db.commit()
    except Exception:
        log.exception("scan_sessions: session_heartbeat failed (session_id=%s)", session_id)


async def session_reopen(session_id: Optional[int]) -> None:
    """
    Re-arm a stalled/abandoned session for another process pass.
    Sets status='running', clears ended_at, and stamps last_heartbeat=now.
    The duplicate-hash check in the scan endpoint ensures already-processed
    files are skipped — only genuinely unfinished files get re-identified.
    """
    if session_id is None:
        return
    try:
        now = datetime.utcnow()
        async with AsyncSessionLocal() as db:
            await db.execute(
                text(
                    "UPDATE scan_sessions "
                    "SET status = 'running', ended_at = NULL, last_heartbeat = :t "
                    "WHERE id = :id"
                ),
                {"t": now, "id": session_id},
            )
            await db.commit()
    except Exception:
        log.exception("scan_sessions: session_reopen failed (session_id=%s)", session_id)


# ---------------------------------------------------------------------------
# Query helpers (used by the API endpoints)
# ---------------------------------------------------------------------------

def _to_dt(val):
    """Coerce a DB value (datetime obj or ISO string) to datetime, or return None."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        # SQLite returns datetimes as strings like "2026-05-30 21:35:12.120114"
        return datetime.fromisoformat(str(val))
    except Exception:
        return None


def _row_to_dict(row) -> dict:
    started = _to_dt(row[3])
    ended   = _to_dt(row[4])
    duration_s = None
    if started and ended:
        try:
            duration_s = int((ended - started).total_seconds())
        except Exception:
            pass
    heartbeat  = _to_dt(row[15]) if len(row) > 15 else None
    status_val = row[14] if len(row) > 14 else "complete"
    # Stalled: computed at read time — status still 'running' but heartbeat is
    # absent (never written) or stale (>5 min ago). Never written to DB.
    # NOTE: NULL heartbeat also counts as stalled so P2 batches that never
    # called session_heartbeat() are not silently excluded.
    is_stalled = (
        status_val == "running"
        and (
            heartbeat is None
            or (datetime.utcnow() - heartbeat).total_seconds() > 300
        )
    )
    # Legacy rows (pre-migration 0021) have no heartbeat and status may be NULL.
    # Treat them as 'legacy' so the UI can say "history not available" rather
    # than showing a misleading 'stalled' badge.
    if status_val is None or (status_val == "complete" and heartbeat is None and ended is None):
        display_status = "legacy"
    else:
        display_status = status_val
    return {
        "id":                      row[0],
        "pipeline":                row[1],
        "label":                   row[2],
        "started_at":              started.isoformat() if started else None,
        "ended_at":                ended.isoformat()   if ended   else None,
        "duration_s":              duration_s,
        "files_received":          row[5],
        "files_processed":         row[6],
        "files_approved":          row[7],
        "files_review":            row[8],
        "files_rejected":          row[9],
        "files_failed":            row[10],
        "source_path":             row[11],
        "files_duplicate":         row[12],
        "files_skipped":           row[13] if len(row) > 13 else 0,
        "status":                  display_status,
        "last_heartbeat":          heartbeat.isoformat() if heartbeat else None,
        "files_new":               row[16] if len(row) > 16 else 0,
        "files_retryable":         row[17] if len(row) > 17 else 0,
        "files_already_processed": row[18] if len(row) > 18 else 0,
        "is_stalled":              is_stalled,
    }


_SELECT = (
    "SELECT id, pipeline, label, started_at, ended_at, "
    "files_received, files_processed, files_approved, "
    "files_review, files_rejected, files_failed, source_path, "
    "files_duplicate, COALESCE(files_skipped, 0), "
    "COALESCE(status, 'complete'), last_heartbeat, "
    "COALESCE(files_new, 0), COALESCE(files_retryable, 0), "
    "COALESCE(files_already_processed, 0) "
    "FROM scan_sessions"
)


async def sessions_list(pipeline: int, limit: Optional[int] = None) -> list:
    """Return sessions for a pipeline, newest first, optionally capped."""
    try:
        q = f"{_SELECT} WHERE pipeline = :p ORDER BY started_at DESC"
        params: dict = {"p": pipeline}
        if limit:
            q += " LIMIT :lim"
            params["lim"] = limit
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(text(q), params)).fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception:
        log.exception("scan_sessions: sessions_list failed")
        return []


async def sessions_breakdown(pipeline: int) -> dict:
    """
    Lifetime pipeline file-count breakdown for one pipeline, summed across all
    recorded sessions.

    The terminal counters are mutually exclusive per file, so:
        files_received = rejected_prefilter + rejected_duplicate
                         + failed + completed
    where completed = approved + review.

    Session tracking began only when the scan_sessions table was introduced, so
    these totals describe activity *since then* — earlier history can't be
    broken down (no per-file outcome was recorded). `tracking_since` carries the
    earliest session start so the UI can say so. `unaccounted` exposes any
    residual (e.g. a session that was reopened by coalescing but never fully
    re-counted) rather than silently hiding it.
    """
    try:
        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                text(
                    "SELECT COUNT(*), MIN(started_at), "
                    "COALESCE(SUM(files_received),0), "
                    "COALESCE(SUM(files_rejected),0), "
                    "COALESCE(SUM(files_duplicate),0), "
                    "COALESCE(SUM(files_failed),0), "
                    "COALESCE(SUM(files_approved),0), "
                    "COALESCE(SUM(files_review),0), "
                    "COALESCE(SUM(COALESCE(files_skipped,0)),0) "
                    "FROM scan_sessions WHERE pipeline = :p"
                ),
                {"p": pipeline},
            )).fetchone()

        session_count = row[0] or 0
        since = _to_dt(row[1])
        received = row[2] or 0
        rejected_prefilter = row[3] or 0
        rejected_duplicate = row[4] or 0
        failed = row[5] or 0
        completed = (row[6] or 0) + (row[7] or 0)
        skipped = row[8] or 0
        accounted = rejected_prefilter + rejected_duplicate + failed + completed + skipped

        return {
            "pipeline":           pipeline,
            "session_count":      session_count,
            "tracking_since":     since.isoformat() if since else None,
            "files_received":     received,
            "rejected_prefilter": rejected_prefilter,
            "rejected_duplicate": rejected_duplicate,
            "failed":             failed,
            "skipped":            skipped,
            "completed":          completed,
            "unaccounted":        max(received - accounted, 0),
            "historical_unavailable": True,
        }
    except Exception:
        log.exception("scan_sessions: sessions_breakdown failed")
        return {}
