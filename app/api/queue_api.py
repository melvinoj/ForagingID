"""
Job Queue API

POST /api/queue/enqueue              — add a job to the queue
GET  /api/queue/list                 — current queue state (all active + recent 60 s completed)
GET  /api/queue/sse                  — SSE stream; pushes full list on each change
PATCH /api/queue/{id}                — update status/progress (called by browser during execution)
POST /api/queue/{id}/cancel          — cancel queued or running job
POST /api/queue/{id}/pause           — pause a running job
POST /api/queue/{id}/resume          — resume a paused job
POST /api/queue/{id}/move-to-top     — move queued job to front of queue
POST /api/queue/kill-all             — set all non-terminal jobs to cancelled (emergency kill switch)
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text

from app.database import AsyncSessionLocal

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/queue", tags=["queue"])

# A running job whose last_heartbeat (or started_at if no heartbeat) is older
# than this is considered interrupted — the server process that was driving it
# has gone away.
_STALE_THRESHOLD_S = 30

# ── SSE broadcaster ───────────────────────────────────────────────────────────

_sse_listeners: set[asyncio.Queue] = set()


async def _broadcast():
    jobs = await _list_jobs()
    data = json.dumps(jobs, default=str)
    dead: set[asyncio.Queue] = set()
    for q in list(_sse_listeners):
        try:
            q.put_nowait(data)
        except asyncio.QueueFull:
            dead.add(q)
    _sse_listeners.difference_update(dead)


# ── DB helpers ────────────────────────────────────────────────────────────────

_COLS = (
    "id, job_type, label, status, queue_position, "
    "progress_current, progress_total, payload, "
    "created_at, started_at, ended_at, error_message, last_heartbeat"
)


def _is_stale(status: str, started_at_str, heartbeat_str) -> bool:
    """Return True if a running job has had no activity for _STALE_THRESHOLD_S seconds."""
    if status != "running":
        return False
    now = datetime.utcnow()

    def _parse(v):
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        try:
            return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except Exception:
            return None

    # Use last_heartbeat if available, fall back to started_at
    ref = _parse(heartbeat_str) or _parse(started_at_str)
    if ref is None:
        return True  # no reference time at all → assume stale
    # Strip tz info for comparison (all times are UTC)
    if ref.tzinfo is not None:
        ref = ref.replace(tzinfo=None)
    return (now - ref).total_seconds() > _STALE_THRESHOLD_S


def _row_to_dict(row) -> dict:
    raw_status = row[3]
    # Surface stale running jobs as 'interrupted' without writing to DB.
    # Indices: 9=started_at, 12=last_heartbeat
    effective_status = raw_status
    if _is_stale(raw_status, row[9], row[12]):
        effective_status = "interrupted"

    return {
        "id":               row[0],
        "job_type":         row[1],
        "label":            row[2],
        "status":           effective_status,
        "_db_status":       raw_status,   # real DB value, used by cancel/pause guards
        "queue_position":   row[4],
        "progress_current": row[5],
        "progress_total":   row[6],
        "payload":          json.loads(row[7]) if row[7] else {},
        "created_at":       str(row[8])  if row[8]  else None,
        "started_at":       str(row[9])  if row[9]  else None,
        "ended_at":         str(row[10]) if row[10] else None,
        "error_message":    row[11],
        "last_heartbeat":   str(row[12]) if row[12] else None,
    }


async def _list_jobs() -> list[dict]:
    """Return all active jobs plus recently-completed/cancelled (last 60 s)."""
    cutoff = datetime.utcnow() - timedelta(seconds=60)
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            text(
                f"SELECT {_COLS} FROM job_queue "
                "WHERE status IN ('queued','running','paused','failed','interrupted') "
                "   OR (status IN ('complete','cancelled') AND ended_at >= :cutoff) "
                "ORDER BY "
                "  CASE status WHEN 'running' THEN 0 WHEN 'paused' THEN 1 "
                "              WHEN 'queued'  THEN 2 ELSE 3 END, "
                "  COALESCE(queue_position, 9999999), created_at"
            ),
            {"cutoff": cutoff},
        )).fetchall()
    return [_row_to_dict(r) for r in rows]


async def _max_queue_position() -> int:
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            text("SELECT COALESCE(MAX(queue_position), 0) FROM job_queue WHERE status='queued'")
        )).fetchone()
    return (row[0] or 0)


# ── Startup recovery ──────────────────────────────────────────────────────────

async def recover_stale_jobs() -> None:
    """
    Called once at server startup.  Any job_queue row still in 'running' state
    whose last_heartbeat (or started_at, if no heartbeat has ever been written)
    is older than _STALE_THRESHOLD_S seconds was driving by a process that is no
    longer alive.  Transition those rows to 'interrupted' so the UI can offer a
    Rerun button rather than showing a phantom "Running" badge.

    This is a DB write — once done the interrupted status persists across future
    list calls, so no re-computation is needed.
    """
    try:
        threshold = datetime.utcnow() - timedelta(seconds=_STALE_THRESHOLD_S)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text(
                    "UPDATE job_queue SET status='interrupted', ended_at=:now "
                    "WHERE status='running' AND ("
                    "  (last_heartbeat IS NOT NULL AND last_heartbeat < :thresh) "
                    "  OR (last_heartbeat IS NULL AND started_at IS NOT NULL AND started_at < :thresh) "
                    "  OR (last_heartbeat IS NULL AND started_at IS NULL) "
                    ")"
                ),
                {"now": datetime.utcnow(), "thresh": threshold},
            )
            await db.commit()
            n = result.rowcount
        if n:
            log.info("[queue] Startup recovery: %d stale running job(s) → interrupted", n)
    except Exception:
        log.exception("[queue] recover_stale_jobs failed")


# ── Pydantic models ───────────────────────────────────────────────────────────

class EnqueueBody(BaseModel):
    job_type: str
    label:    str
    payload:  Optional[dict] = None


class PatchBody(BaseModel):
    status:           Optional[str] = None
    progress_current: Optional[int] = None
    progress_total:   Optional[int] = None
    error_message:    Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/enqueue")
async def enqueue(body: EnqueueBody):
    pos = await _max_queue_position() + 1
    now = datetime.utcnow()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                "INSERT INTO job_queue "
                "(job_type, label, status, queue_position, progress_current, "
                " progress_total, payload, created_at) "
                "VALUES (:jt, :lb, 'queued', :pos, 0, 0, :pl, :now)"
            ),
            {
                "jt":  body.job_type,
                "lb":  body.label,
                "pos": pos,
                "pl":  json.dumps(body.payload or {}),
                "now": now,
            },
        )
        await db.commit()
        job_id = result.lastrowid

    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            text(f"SELECT {_COLS} FROM job_queue WHERE id = :id"),
            {"id": job_id},
        )).fetchone()

    await _broadcast()
    return _row_to_dict(row)


@router.get("/list")
async def list_jobs():
    return await _list_jobs()


@router.get("/sse")
async def sse_stream():
    q: asyncio.Queue = asyncio.Queue(maxsize=50)
    _sse_listeners.add(q)

    # Send current state immediately on connect
    jobs = await _list_jobs()
    initial = json.dumps(jobs, default=str)

    async def generator():
        try:
            yield f"data: {initial}\n\n"
            while True:
                try:
                    data = await asyncio.wait_for(q.get(), timeout=25.0)
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            _sse_listeners.discard(q)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.patch("/{job_id}")
async def patch_job(job_id: int, body: PatchBody):
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            text("SELECT status FROM job_queue WHERE id = :id"),
            {"id": job_id},
        )).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")

    updates: list[str] = []
    params: dict = {"id": job_id}
    now = datetime.utcnow()

    if body.status is not None:
        updates.append("status = :status")
        params["status"] = body.status
        if body.status in ("running",) and row[0] == "queued":
            updates.append("started_at = :started_at")
            params["started_at"] = now
        if body.status in ("complete", "failed", "cancelled", "interrupted"):
            updates.append("ended_at = :ended_at")
            params["ended_at"] = now

    if body.progress_current is not None:
        updates.append("progress_current = :pc")
        params["pc"] = body.progress_current
        # Any progress report counts as a heartbeat — keeps the job from
        # being flagged as stale while the browser is actively working.
        updates.append("last_heartbeat = :hb")
        params["hb"] = now

    if body.progress_total is not None:
        updates.append("progress_total = :pt")
        params["pt"] = body.progress_total

    if body.error_message is not None:
        updates.append("error_message = :em")
        params["em"] = body.error_message

    if not updates:
        return {"ok": True}

    async with AsyncSessionLocal() as db:
        await db.execute(
            text(f"UPDATE job_queue SET {', '.join(updates)} WHERE id = :id"),
            params,
        )
        await db.commit()

    await _broadcast()
    return {"ok": True}


async def _set_terminal(job_id: int, status: str, detail: str):
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            text("SELECT status FROM job_queue WHERE id = :id"),
            {"id": job_id},
        )).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    if row[0] in ("complete", "cancelled"):
        raise HTTPException(status_code=409, detail=f"Job already in terminal state '{row[0]}'")
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("UPDATE job_queue SET status=:s, ended_at=:now WHERE id=:id"),
            {"s": status, "now": datetime.utcnow(), "id": job_id},
        )
        await db.commit()
    await _broadcast()
    return {"ok": True, "status": status}


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: int):
    return await _set_terminal(job_id, "cancelled", detail="")


@router.post("/{job_id}/pause")
async def pause_job(job_id: int):
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            text("SELECT status FROM job_queue WHERE id = :id"),
            {"id": job_id},
        )).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    if row[0] != "running":
        raise HTTPException(status_code=409, detail=f"Cannot pause job in state '{row[0]}'")
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("UPDATE job_queue SET status='paused' WHERE id=:id"),
            {"id": job_id},
        )
        await db.commit()
    await _broadcast()
    return {"ok": True, "status": "paused"}


@router.post("/{job_id}/resume")
async def resume_job(job_id: int):
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            text("SELECT status FROM job_queue WHERE id = :id"),
            {"id": job_id},
        )).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    if row[0] != "paused":
        raise HTTPException(status_code=409, detail=f"Cannot resume job in state '{row[0]}'")
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("UPDATE job_queue SET status='queued' WHERE id=:id"),
            {"id": job_id},
        )
        await db.commit()
    await _broadcast()
    return {"ok": True, "status": "queued"}


@router.post("/{job_id}/move-to-top")
async def move_to_top(job_id: int):
    async with AsyncSessionLocal() as db:
        row = (await db.execute(
            text("SELECT status FROM job_queue WHERE id = :id"),
            {"id": job_id},
        )).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    if row[0] != "queued":
        raise HTTPException(status_code=409, detail=f"Cannot move job in state '{row[0]}' to top")
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("UPDATE job_queue SET queue_position = 0 WHERE id=:id"),
            {"id": job_id},
        )
        await db.commit()
    await _broadcast()
    return {"ok": True}


@router.post("/kill-all")
async def kill_all_jobs():
    """
    Emergency kill switch.  Sets all non-terminal jobs (queued, running, paused,
    interrupted, failed) to 'cancelled' in one DB write.  Called from the
    Settings "Kill all jobs" button when the queue is hung and individual job
    controls are not responding.

    Does NOT set any in-memory browser signals — those are managed by the
    browser side (scan.html).  This endpoint only fixes the DB state so the
    queue panel shows a clean slate on next reload.
    """
    now = datetime.utcnow()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text(
                "UPDATE job_queue SET status='cancelled', ended_at=:now "
                "WHERE status IN ('queued','running','paused','interrupted','failed')"
            ),
            {"now": now},
        )
        await db.commit()
        n = result.rowcount
    log.info("[queue] kill-all: %d job(s) cancelled", n)
    await _broadcast()
    return {"ok": True, "cancelled": n}
