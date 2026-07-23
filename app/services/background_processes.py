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


def _warn_unobserved(process_type: str) -> None:
    """
    One recognisable line for every way bp_start can fail to produce an id.

    A None from bp_start is never deliberate — the contract is "an id, or a
    failure" — and every downstream helper (bp_progress, bp_heartbeat,
    bp_finish, bp_set_status) early-returns on None. So a lost id silently
    demotes a process to unobserved: it runs correctly and completely, and the
    widget never knows it existed. That is precisely what happened to a real P1
    batch on 20 July 2026 — two concurrent P1 invocations, one bp row, and no
    trace of the missing one. Grep for this string when a process runs but
    never appears.
    """
    log.warning(
        "bp_start returned None for %s — process runs unobserved "
        "(likely DB contention); no background_processes row will exist for it",
        process_type,
    )


async def bp_start(
    process_type: str,
    progress_total: int = 0,
    detail: str = "",
    *,
    label: Optional[str] = None,
    payload: Optional[str] = None,
    queue_position: Optional[int] = None,
    created_at: Optional[datetime] = None,
    source_job_queue_id: Optional[int] = None,
) -> Optional[int]:
    """
    INSERT a new background_processes row and return its process_id.
    Returns None on any failure — never as a deliberate no-op, which is why
    every None path below warns. Still swallow-and-continue: the caller's work
    must proceed unobserved rather than fail.

    Pass B Phase 2 dual-write params (keyword-only, all default None so existing
    callers are byte-unchanged and leave the new columns NULL). Only bp rows that
    have a job_queue twin populate them — mirroring job_queue exactly:
      label          fixed job name (distinct from `detail`, the mutating step)
      payload        rerun payload as a JSON *string* (job_queue.payload is TEXT)
      queue_position job_queue ordering value
      created_at     enqueue time (distinct from started_at). Pass the SAME
                     timestamp used for the job_queue INSERT so the twins agree.
    Nothing reads these columns this phase.

    Pass B Phase 3b (migration 0052) adds source_job_queue_id (keyword-only,
    default None so existing callers are byte-unchanged and leave it NULL): the
    explicit id of the job_queue twin, for identity-based de-dup in a later phase.
    Still unread this phase.
    """
    try:
        now = datetime.utcnow()
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text(
                    "INSERT INTO background_processes "
                    "(process_type, status, started_at, updated_at, last_heartbeat, "
                    " progress_current, progress_total, detail, "
                    " label, payload, queue_position, created_at, source_job_queue_id) "
                    "VALUES (:pt, 'running', :now, :now, :now, 0, :total, :detail, "
                    " :label, :payload, :qpos, :created_at, :sjqid)"
                ),
                {"pt": process_type, "now": now, "total": progress_total, "detail": detail,
                 "label": label, "payload": payload, "qpos": queue_position,
                 "created_at": created_at, "sjqid": source_job_queue_id},
            )
            await db.commit()
            pid = result.lastrowid
            if not pid:
                # The previously SILENT path: no exception, but no usable id
                # either. The except below has always logged; this returned a
                # falsy id with no trace at all.
                _warn_unobserved(process_type)
                return None
            return pid
    except Exception:
        # Keep the traceback (ERROR), and add the greppable one-liner so both
        # failure paths surface identically.
        log.exception("background_processes: bp_start failed (type=%s)", process_type)
        _warn_unobserved(process_type)
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
        # Pass B Phase 2 dual-write. error_text mirrors job_queue.error_message
        # (same value; `error` is left exactly as before). ended_at mirrors
        # job_queue.ended_at — set ONLY on a genuinely terminal status. bp_finish
        # is also called with status='paused' by the draft-loop signal path, and
        # a paused row must NOT get an ended_at (job_queue's pause path leaves it
        # NULL too). Nothing reads these columns this phase.
        parts.append("error_text = :error")
        if status in ("complete", "failed", "cancelled", "interrupted"):
            parts.append("ended_at = :now")
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


async def bp_patch(
    process_id: Optional[int],
    *,
    status: Optional[str] = None,
    queue_position: Optional[int] = None,
    label: Optional[str] = None,
    payload: Optional[str] = None,
    heartbeat: bool = False,
) -> None:
    """
    General-purpose mutation helper for a bp row's job_queue-twin columns.

    Fills the gap Pass B Phase 3a found: bp had start/progress/heartbeat/finish/
    set_status but no way to mutate queue_position/label/payload after creation,
    so a job_queue reorder/relabel could not propagate to its twin. This is that
    writer — capability only; NO call sites are added here (wired in Phase 3c).

    Whitelist, not **kwargs: the mutable set is exactly {status, queue_position,
    label, payload}, named explicitly so a typo can never write an unintended
    column and the set stays a deliberate decision.

    Rules:
      • Only non-None params are written. A call with every column param None and
        heartbeat=False is a pure no-op — it does NOT touch the row (not even
        updated_at).
      • Any write always bumps updated_at, matching bp_progress. heartbeat=True
        additionally stamps last_heartbeat.
      • This helper is NOT a terminal writer. bp_finish is the single owner of
        terminal transitions (status in TERMINAL_STATUSES → it also sets
        ended_at). If a terminal status is passed here, raise ValueError rather
        than writing a terminal status without the ended_at bp_finish guarantees.
        The terminal set is TERMINAL_STATUSES — the same tuple bp_finish's
        ended_at guard and bp_dismiss use.
    """
    if process_id is None:
        return
    if status is not None and status in TERMINAL_STATUSES:
        raise ValueError(
            f"bp_patch cannot write terminal status {status!r}; "
            "bp_finish is the single terminal writer (it also sets ended_at)"
        )

    parts: list[str] = []
    params: dict = {"pid": process_id}
    if status is not None:
        parts.append("status = :status")
        params["status"] = status
    if queue_position is not None:
        parts.append("queue_position = :qpos")
        params["qpos"] = queue_position
    if label is not None:
        parts.append("label = :label")
        params["label"] = label
    if payload is not None:
        parts.append("payload = :payload")
        params["payload"] = payload

    # Nothing to write and no heartbeat requested → true no-op, row untouched.
    if not parts and not heartbeat:
        return

    now = datetime.utcnow()
    params["now"] = now
    parts.append("updated_at = :now")
    if heartbeat:
        parts.append("last_heartbeat = :now")

    try:
        async with AsyncSessionLocal() as db:
            await db.execute(
                text(f"UPDATE background_processes SET {', '.join(parts)} WHERE process_id = :pid"),
                params,
            )
            await db.commit()
    except Exception:
        log.exception("background_processes: bp_patch failed (id=%s)", process_id)


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
                    "       last_heartbeat, progress_current, progress_total, detail, error, "
                    "       error_text "
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
    # Pass B Phase 3b error reconciliation. bp_finish writes BOTH error (row[9],
    # VARCHAR(512), truncatable) and error_text (row[10], unbounded, the
    # Phase-4-canonical column). Surface error_text when present — it is the
    # fuller, untruncated value and survives error's eventual retirement —
    # falling back to error for pre-Phase-2 rows that never got an error_text.
    # Defensive on length: a 10-column row (no error_text selected) still works.
    error_val = row[9]
    if len(row) > 10 and row[10] is not None:
        error_val = row[10]
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
        "error":            error_val,
        "is_stalled":       is_stalled,
        "heartbeat_age_s":  int((now - heartbeat).total_seconds()) if heartbeat else None,
    }
