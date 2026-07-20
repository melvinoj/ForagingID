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
    """
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            text("SELECT status FROM background_processes WHERE process_id = :pid"),
            {"pid": process_id},
        )).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Process not found")
    if row[0] not in ("running",):
        raise HTTPException(status_code=409, detail=f"Cannot pause process in state '{row[0]}'")
    await bp_set_status(process_id, "paused")
    return {"ok": True, "process_id": process_id, "status": "paused"}


@router.post("/{process_id}/cancel")
async def cancel_process(process_id: int):
    """
    Signal a process to cancel. Same clean-stop pattern as pause.
    """
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            text("SELECT status FROM background_processes WHERE process_id = :pid"),
            {"pid": process_id},
        )).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Process not found")
    if row[0] in ("complete", "failed", "cancelled", "interrupted"):
        raise HTTPException(status_code=409, detail=f"Process already in terminal state '{row[0]}'")
    await bp_set_status(process_id, "cancelled")
    return {"ok": True, "process_id": process_id, "status": "cancelled"}
