"""
recorded_walks.py — GPS recorded walk CRUD + elevation enrichment.

Endpoints:
  POST   /api/recorded-walks                    — save a new recorded walk
  GET    /api/recorded-walks                    — list all recorded walks
  GET    /api/recorded-walks/{id}               — walk detail + linked observations
  POST   /api/recorded-walks/{id}/elevation     — async elevation enrichment (fire-and-forget)
  DELETE /api/recorded-walks/{id}               — delete walk + linked records
"""

import json
import logging
import math
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

AUDIO_DIR = Path("media/recorded_walks")
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal, get_db
from app.models.recorded_walk import RecordedWalk, RecordedWalkObservation
from app.api.identity import Identity, get_identity

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recorded-walks", tags=["recorded-walks"])

OPEN_TOPO_URL = "https://api.open-topo-data.com/v1/srtm30m"


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TrackPoint(BaseModel):
    lat: float
    lng: float
    alt: Optional[float] = None
    ts:  int  # Unix ms


class ProximityEncounter(BaseModel):
    observation_id: int
    encountered_at: Optional[str] = None  # ISO string


class RecordedWalkCreate(BaseModel):
    name:              str
    started_at:        str   # ISO string
    ended_at:          str   # ISO string
    distance_m:        Optional[float] = None
    duration_s:        Optional[int]   = None
    track_points:      List[TrackPoint] = []
    audio_note_path:   Optional[str]   = None
    proximity_encounters: List[ProximityEncounter] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_dt(s: str) -> datetime:
    """Parse ISO string (with or without Z) to UTC datetime."""
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _haversine_m(lat1, lng1, lat2, lng2) -> float:
    R = 6_371_000
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _compute_distance(points: List[TrackPoint]) -> float:
    total = 0.0
    for i in range(1, len(points)):
        total += _haversine_m(
            points[i - 1].lat, points[i - 1].lng,
            points[i].lat,     points[i].lng,
        )
    return total


# ---------------------------------------------------------------------------
# Background: elevation enrichment
# ---------------------------------------------------------------------------

async def _enrich_elevation(walk_id: int, track_points: List[TrackPoint]) -> None:
    """Sample up to 100 track points, query Open-Topo-Data, write gain/loss."""
    if len(track_points) < 2:
        return
    step = max(1, len(track_points) // 100)
    sampled = track_points[::step]
    locations = "|".join(f"{p.lat},{p.lng}" for p in sampled)

    # ── Durable process row (Pass C — additive, display-only) ─────────────
    # Started after the <2-points no-op guard above, so a walk with no usable
    # track creates no row. This is the shortest of the seven — one HTTP call
    # to Open-Topo-Data, typically a second or two — so it will usually appear
    # and clear between two widget polls. Wired anyway for completeness: it is
    # exactly the job that looks like a hang when the API is slow or timing out
    # (20s client timeout), and that case is the one worth being able to see.
    # No intermediate progress exists to mirror: there is a single request, so
    # the row goes 0/N → terminal. walk_id is carried in detail for the same
    # reason p2_delta carries session_id.
    from app.services.background_processes import bp_start, bp_finish
    _el_pid    = await bp_start(
        "elevation_enrich",
        progress_total=len(sampled),
        detail=f"walk:{walk_id} — Elevation: {len(sampled)} points",
    )
    _el_status = "failed"
    _el_error  = "Elevation enrichment did not complete"

    try:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                r = await client.get(OPEN_TOPO_URL, params={"locations": locations})
                r.raise_for_status()
                data = r.json()
        except Exception as exc:
            log.warning("elevation lookup failed for walk %d: %s", walk_id, exc)
            _el_error = f"Elevation lookup failed: {exc}"
            return

        results = data.get("results", [])
        elevations = [res.get("elevation") for res in results if res.get("elevation") is not None]
        if len(elevations) < 2:
            _el_error = "Fewer than 2 elevation samples returned"
            return

        gain = loss = 0.0
        for i in range(1, len(elevations)):
            diff = elevations[i] - elevations[i - 1]
            if diff > 0:
                gain += diff
            else:
                loss += abs(diff)

        async with AsyncSessionLocal() as session:
            walk = await session.get(RecordedWalk, walk_id)
            if walk:
                walk.elevation_gain_m = round(gain, 1)
                walk.elevation_loss_m = round(loss, 1)
                await session.commit()
        log.info("elevation enriched for walk %d: +%.0fm -%.0fm", walk_id, gain, loss)
        _el_status, _el_error = "complete", ""
    finally:
        await bp_finish(
            _el_pid, _el_status, error=_el_error,
            current=len(sampled) if _el_status == "complete" else 0,
            total=len(sampled),
        )


# ---------------------------------------------------------------------------
# POST /api/recorded-walks
# ---------------------------------------------------------------------------

@router.post("")
async def create_recorded_walk(
    body: RecordedWalkCreate,
    background_tasks: BackgroundTasks,
    identity: Identity = Depends(get_identity),
    db: AsyncSession = Depends(get_db),
):
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    started = _parse_dt(body.started_at)
    ended   = _parse_dt(body.ended_at)

    distance = body.distance_m
    if distance is None and body.track_points:
        distance = round(_compute_distance(body.track_points), 1)

    walk = RecordedWalk(
        name              = body.name,
        started_at        = started,
        ended_at          = ended,
        distance_m        = distance,
        duration_s        = body.duration_s,
        track_points_json = json.dumps([p.model_dump() for p in body.track_points]),
        audio_note_path   = body.audio_note_path,
        user_id           = identity.user_id,
    )
    db.add(walk)
    await db.flush()  # get walk.id

    # Proximity encounters (deduplicated)
    seen_obs: set[int] = set()
    for enc in body.proximity_encounters:
        if enc.observation_id not in seen_obs:
            seen_obs.add(enc.observation_id)
            db.add(RecordedWalkObservation(
                recorded_walk_id = walk.id,
                observation_id   = enc.observation_id,
                encountered_at   = _parse_dt(enc.encountered_at) if enc.encountered_at else None,
            ))

    # Observations created within the walk window (additive to proximity encounters)
    if started and ended:
        obs_rows = await db.execute(
            text("""
                SELECT id FROM observations
                WHERE created_at >= :start AND created_at <= :end
            """),
            {"start": started, "end": ended},
        )
        for (obs_id,) in obs_rows:
            if obs_id not in seen_obs:
                seen_obs.add(obs_id)
                db.add(RecordedWalkObservation(
                    recorded_walk_id = walk.id,
                    observation_id   = obs_id,
                    encountered_at   = None,
                ))

    await db.commit()
    await db.refresh(walk)

    # Fire-and-forget elevation enrichment
    if body.track_points:
        background_tasks.add_task(_enrich_elevation, walk.id, body.track_points)

    return {"id": walk.id, "name": walk.name, "distance_m": walk.distance_m}


# ---------------------------------------------------------------------------
# GET /api/recorded-walks
# ---------------------------------------------------------------------------

@router.get("")
async def list_recorded_walks(db: AsyncSession = Depends(get_db)):
    rows = await db.execute(
        select(RecordedWalk).order_by(RecordedWalk.started_at.desc())
    )
    walks = rows.scalars().all()
    return [
        {
            "id":               w.id,
            "name":             w.name,
            "started_at":       w.started_at.isoformat() if w.started_at else None,
            "ended_at":         w.ended_at.isoformat()   if w.ended_at   else None,
            "distance_m":       w.distance_m,
            "duration_s":       w.duration_s,
            "elevation_gain_m": w.elevation_gain_m,
            "elevation_loss_m": w.elevation_loss_m,
            "audio_note_path":  w.audio_note_path,
            "created_at":       w.created_at.isoformat() if w.created_at else None,
        }
        for w in walks
    ]


# ---------------------------------------------------------------------------
# GET /api/recorded-walks/{id}
# ---------------------------------------------------------------------------

@router.get("/{walk_id}")
async def get_recorded_walk(walk_id: int, db: AsyncSession = Depends(get_db)):
    walk = await db.get(RecordedWalk, walk_id)
    if not walk:
        raise HTTPException(404, detail="Walk not found")

    link_rows = await db.execute(
        select(RecordedWalkObservation).where(
            RecordedWalkObservation.recorded_walk_id == walk_id
        )
    )
    links = link_rows.scalars().all()

    # Fetch observation details (lat/lng/thumbnail/species) in one query
    obs_ids = [lnk.observation_id for lnk in links]
    obs_detail: dict = {}
    if obs_ids:
        obs_rows = await db.execute(
            text("""
                SELECT id, latitude, longitude, thumbnail_path,
                       species_primary, common_name
                FROM observations
                WHERE id IN :ids
            """),
            {"ids": tuple(obs_ids) if len(obs_ids) > 1 else (obs_ids[0], obs_ids[0])},
        )
        for row in obs_rows:
            obs_detail[row.id] = {
                "latitude":       row.latitude,
                "longitude":      row.longitude,
                "thumbnail_path": row.thumbnail_path,
                "species":        row.species_primary,
                "common_name":    row.common_name,
            }

    observations_out = []
    for lnk in links:
        detail = obs_detail.get(lnk.observation_id, {})
        observations_out.append({
            "observation_id": lnk.observation_id,
            "encountered_at": lnk.encountered_at.isoformat() if lnk.encountered_at else None,
            "latitude":       detail.get("latitude"),
            "longitude":      detail.get("longitude"),
            "thumbnail_path": detail.get("thumbnail_path"),
            "species":        detail.get("species"),
            "common_name":    detail.get("common_name"),
        })

    return {
        "id":               walk.id,
        "name":             walk.name,
        "started_at":       walk.started_at.isoformat() if walk.started_at else None,
        "ended_at":         walk.ended_at.isoformat()   if walk.ended_at   else None,
        "distance_m":       walk.distance_m,
        "duration_s":       walk.duration_s,
        "elevation_gain_m": walk.elevation_gain_m,
        "elevation_loss_m": walk.elevation_loss_m,
        "track_points":     json.loads(walk.track_points_json or "[]"),
        "audio_note_path":  walk.audio_note_path,
        "created_at":       walk.created_at.isoformat() if walk.created_at else None,
        "observations":     observations_out,
    }


# ---------------------------------------------------------------------------
# POST /api/recorded-walks/{id}/elevation  (idempotent re-enrichment)
# ---------------------------------------------------------------------------

@router.post("/{walk_id}/elevation")
async def enrich_elevation(
    walk_id: int,
    background_tasks: BackgroundTasks,
    identity: Identity = Depends(get_identity),
    db: AsyncSession = Depends(get_db),
):
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    walk = await db.get(RecordedWalk, walk_id)
    if not walk:
        raise HTTPException(404, detail="Walk not found")
    points = [TrackPoint(**p) for p in json.loads(walk.track_points_json or "[]")]
    background_tasks.add_task(_enrich_elevation, walk_id, points)
    return {"queued": True}


# ---------------------------------------------------------------------------
# DELETE /api/recorded-walks/{id}
# ---------------------------------------------------------------------------

@router.delete("/{walk_id}")
async def delete_recorded_walk(
    walk_id: int,
    identity: Identity = Depends(get_identity),
    db: AsyncSession = Depends(get_db),
):
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    walk = await db.get(RecordedWalk, walk_id)
    if not walk:
        raise HTTPException(404, detail="Walk not found")
    await db.execute(
        delete(RecordedWalkObservation).where(
            RecordedWalkObservation.recorded_walk_id == walk_id
        )
    )
    await db.delete(walk)
    await db.commit()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# POST /api/recorded-walks/audio-upload
# ---------------------------------------------------------------------------

@router.post("/audio-upload")
async def upload_audio_note(
    file: UploadFile = File(...),
    identity: Identity = Depends(get_identity),
):
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    """Save a walk audio note blob; return its relative path."""
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "note.webm").suffix or ".webm"
    fname  = f"walk_{uuid.uuid4().hex}{suffix}"
    dest   = AUDIO_DIR / fname
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"path": str(dest)}
