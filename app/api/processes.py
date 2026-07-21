"""
Background Processes API

GET  /api/processes/active           — all running/paused or recently-active processes
POST /api/processes/{id}/pause       — signal a process to pause
POST /api/processes/{id}/cancel      — signal a process to cancel
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app.database import AsyncSessionLocal
from app.services.background_processes import _row_to_dict, bp_set_status

router = APIRouter(prefix="/api/processes", tags=["processes"])

# Rows with last_heartbeat within this window are included even if status != running/paused.
_RECENT_WINDOW_S = 90

# ── Which process types actually honour a pause/cancel signal ────────────────
# A process is listed here ONLY if its worker loop reads its own
# background_processes.status and stops when it sees paused/cancelled. Both
# entries below run through run_enrichment_batch(cancel_check_fn=…), which
# checks the signal before each species and returns cleanly with stopped_at.
#
# This set exists to make one specific lie impossible. Before it, these
# endpoints accepted ANY process_id: the row flipped to 'cancelled', the worker
# — which never reads that column — carried on to the end, and its bp_finish
# then flipped the row to 'complete'. The user saw a cancel that visibly undid
# itself while the work they cancelled ran to completion. Refusing the request
# up front is the fix; guarding bp_finish would only have hidden the flip-back
# while the work still ran.
#
# Types NOT listed here are not cancellable *through this endpoint* — some have
# their own real stop route, which is where their UI must send the signal:
#   p2_delta, archive_scan            → POST /api/scan/pause/{session_id}
#   ai_draft_backfill, *_id_notes     → POST /api/queue/{id}/cancel
# The rest (bulk_*, itis_backfill, fungi_edibility_backfill, reprocess_pending,
# p1_syncthing, p1_reprocess, folder_scan, rescan_unknown, elevation_enrich)
# have no cooperative stop at all and must not offer one.
CANCELLABLE_TYPES = {"enrichment_run", "auto_enrich"}

# ── Which process types can be RESUMED from a paused row, and where ─────────
# Same principle as CANCELLABLE_TYPES: listed only if a route genuinely restarts
# the run from its stop index rather than from zero.
#
# 'enrichment_run' is deliberately absent even though it does support resume.
# Its resume is folded into POST /api/enrichment/run — the same route that
# STARTS a run — which falls back to a fresh run from 0 when it finds no paused
# job in memory. That is fine behind review.html's own button, which is driven
# by that page's job state, but a generic Resume button firing it could silently
# launch a whole new enrichment. Its affordance stays where it is.
RESUME_ROUTES = {
    "auto_enrich": "/api/enrich/resume",
}


async def _load_row(process_id: int):
    """Fetch (status, process_type) for a process row, or 404."""
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            text("SELECT status, process_type FROM background_processes WHERE process_id = :pid"),
            {"pid": process_id},
        )).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Process not found")
    return row[0], row[1]


def _require_honouring_type(process_type: str, verb: str) -> None:
    """409 unless this type's worker loop genuinely observes the signal."""
    if process_type not in CANCELLABLE_TYPES:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Process type '{process_type}' does not support {verb}: its worker "
                f"does not check for a stop signal, so {verb} would mark the row "
                f"without stopping the work. Use that process's own stop route if "
                f"it has one (scan sessions: /api/scan/pause/{{session_id}}; "
                f"queue jobs: /api/queue/{{id}}/cancel)."
            ),
        )


@router.get("/active")
async def get_active_processes():
    """
    Return all rows that are running/paused OR had a heartbeat within the last
    90 seconds (catches stalled processes that never reached a terminal status).
    """
    cutoff = datetime.utcnow() - timedelta(seconds=_RECENT_WINDOW_S)
    try:
        async with AsyncSessionLocal() as db:
            rows = (await db.execute(
                text(
                    "SELECT process_id, process_type, status, started_at, updated_at, "
                    "       last_heartbeat, progress_current, progress_total, detail, error "
                    "FROM background_processes "
                    "WHERE status IN ('running', 'paused') "
                    "   OR last_heartbeat >= :cutoff "
                    "ORDER BY started_at DESC "
                    "LIMIT 50"
                ),
                {"cutoff": cutoff},
            )).fetchall()
        return [_row_to_dict(r) for r in rows]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{process_id}/pause")
async def pause_process(process_id: int):
    """
    Signal a process to pause. The running process must poll for this and stop
    cleanly on its next iteration — this does not kill the thread.

    Refused for types that never poll (see CANCELLABLE_TYPES): pause carries
    exactly the same flip-back lie as cancel, so it is gated by the same set.
    The only in-app caller is review.html's enrichment banner ('enrichment_run'),
    which is in the set.
    """
    status, process_type = await _load_row(process_id)
    if status not in ("running",):
        raise HTTPException(status_code=409, detail=f"Cannot pause process in state '{status}'")
    _require_honouring_type(process_type, "pause")
    await bp_set_status(process_id, "paused")
    return {"ok": True, "process_id": process_id, "status": "paused"}


@router.post("/{process_id}/cancel")
async def cancel_process(process_id: int):
    """
    Signal a process to cancel. Same clean-stop pattern as pause.

    Only accepted for types whose worker loop genuinely observes the signal —
    everything else gets a 409 rather than a status flip that the worker ignores
    and its own bp_finish then overwrites.
    """
    status, process_type = await _load_row(process_id)
    if status in ("complete", "failed", "cancelled", "interrupted"):
        raise HTTPException(status_code=409, detail=f"Process already in terminal state '{status}'")
    _require_honouring_type(process_type, "cancel")
    await bp_set_status(process_id, "cancelled")
    return {"ok": True, "process_id": process_id, "status": "cancelled"}


@router.post("/{process_id}/dismiss")
async def dismiss_process(process_id: int):
    """
    Clear a dead row out of the active feed. NOT a cancel.

    Accepted only for a row that is already terminal, or one still marked
    running whose heartbeat is outside the stall threshold (its driver is gone).
    A genuinely running process — fresh heartbeat — is refused with 409, because
    a dismiss that could silence a live worker would be a backdoor cancel with
    none of the cancel gate's guarantees.

    The staleness test is the shared _STALE_WHERE predicate in
    background_processes.py, the same one recover_stale_processes() sweeps with.
    """
    from app.services.background_processes import bp_dismiss

    result = await bp_dismiss(process_id)
    if result["ok"]:
        return {"ok": True, "process_id": process_id, "action": result["action"]}

    reason = result.get("reason")
    if reason == "not_found":
        raise HTTPException(status_code=404, detail="Process not found")
    if reason == "running":
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot dismiss a running process; cancel it first if cancellable. "
                "This row has a recent heartbeat, so its worker is still alive — "
                "dismissing it would hide work that is still happening."
            ),
        )
    if reason == "paused":
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot dismiss a paused process: it is stopped but resumable, "
                "not dead. Resume it, or cancel it if it is cancellable."
            ),
        )
    raise HTTPException(status_code=500, detail="Dismiss failed; see server log.")


@router.get("/cancellable-types")
async def list_cancellable_types():
    """
    The capability map the UI must gate its per-row controls on, served from the
    same constants the endpoints enforce. One source of truth: a client cannot
    drift into offering End for a type the server will refuse, or Resume for a
    type with no resume route.
    """
    # A type gets a widget PAUSE button only where the full pause→resume loop is
    # reachable from the widget: it must be pausable at the endpoint (in
    # CANCELLABLE_TYPES, which /pause enforces) AND have a widget resume route
    # (in RESUME_ROUTES). enrichment_run is pausable but intentionally absent
    # from RESUME_ROUTES — resuming it is folded into its own start route — so a
    # widget Pause on it would strand the row paused with no way back. Serving
    # the intersection keeps that judgement on the server, derived from the same
    # constants the endpoints enforce, rather than a literal the client could
    # drift from. Today this is exactly {auto_enrich}.
    pausable_types = sorted(CANCELLABLE_TYPES & set(RESUME_ROUTES))
    return {
        "cancellable_types": sorted(CANCELLABLE_TYPES),
        "resume_routes":     dict(RESUME_ROUTES),
        "pausable_types":    pausable_types,
    }
