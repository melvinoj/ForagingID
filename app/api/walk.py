"""
walk.py — Walk feature API: ORS route proxy + saved walks CRUD.

Endpoints:
  POST /api/walk/ors-route      — proxy to OpenRouteService foot-hiking directions
  POST /api/walk/saves          — save a walk
  GET  /api/walk/saves          — list all saved walks (summary)
  GET  /api/walk/saves/{id}     — load a saved walk (full data + computed stops/membership)
  PATCH /api/walk/saves/{id}/membership — set the route buffer (curator)
  POST /api/walk/saves/{id}/accept      — accept older photos near the route (curator)
  POST /api/walk/saves/{id}/exclude     — remove proximity-joined photos (curator)
  POST /api/walk/saves/{id}/renumber    — current stops become the saved snapshot, 1..N (curator)
  DELETE /api/walk/saves/{id}   — delete a saved walk (curator; 409 while published as an experience)
"""

import json
import logging
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.api.identity import Identity, get_identity
from app.models.observation import Observation
from app.models.walk import SavedWalk
from app.services import walk_membership as wm

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/walk", tags=["walk"])

ORS_DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/foot-hiking/geojson"


# ---------------------------------------------------------------------------
# ORS proxy
# ---------------------------------------------------------------------------

class ORSRequest(BaseModel):
    coordinates: List[List[float]]  # [[lng, lat], ...]


@router.post("/ors-route")
async def ors_route(body: ORSRequest):
    """
    Proxy to OpenRouteService foot-hiking directions.
    Returns ORS GeoJSON on success or {"fallback": true, "reason": "..."} on failure.
    """
    if not settings.ors_api_key:
        return {"fallback": True, "reason": "ORS key not configured"}

    if len(body.coordinates) < 2:
        raise HTTPException(400, detail="At least 2 coordinates required")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                ORS_DIRECTIONS_URL,
                headers={
                    "Authorization": settings.ors_api_key,
                    "Content-Type": "application/json",
                },
                json={"coordinates": body.coordinates},
            )

        if resp.status_code == 200:
            return resp.json()

        log.warning("ORS returned %s: %s", resp.status_code, resp.text[:300])
        return {"fallback": True, "reason": f"ORS error {resp.status_code}"}

    except httpx.TimeoutException:
        log.warning("ORS request timed out")
        return {"fallback": True, "reason": "ORS request timed out"}
    except Exception as exc:
        log.warning("ORS request failed: %s", exc)
        return {"fallback": True, "reason": str(exc)}


# ---------------------------------------------------------------------------
# Saved walks — create
# ---------------------------------------------------------------------------

class SaveWalkRequest(BaseModel):
    name: str
    obs_ids: List[int]
    waypoints: List[dict]        # [{lat, lng, obs_id, label}, ...]
    route_geojson: Optional[dict] = None
    distance_m: float = 0.0
    duration_min: int = 0


@router.post("/saves")
async def save_walk(
    body: SaveWalkRequest,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    walk = SavedWalk(
        name=body.name,
        obs_ids_json=json.dumps(body.obs_ids),
        waypoints_json=json.dumps(body.waypoints),
        route_geojson=json.dumps(body.route_geojson) if body.route_geojson else None,
        distance_m=body.distance_m,
        duration_min=body.duration_min,
        user_id=identity.user_id,
    )
    db.add(walk)
    await db.commit()
    await db.refresh(walk)
    return {"ok": True, "id": walk.id, "name": walk.name}


# ---------------------------------------------------------------------------
# Saved walks — list
# ---------------------------------------------------------------------------

@router.get("/saves")
async def list_walks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SavedWalk).order_by(SavedWalk.created_at.desc())
    )
    walks = result.scalars().all()
    return {
        "walks": [
            {
                "id":          w.id,
                "name":        w.name,
                "created_at":  w.created_at.isoformat() if w.created_at else None,
                "distance_m":  w.distance_m,
                "duration_min": w.duration_min,
                # Stops = waypoints (one per stop, field notes included — same
                # count the walk panel shows). obs_ids holds every observation,
                # several per stop since stop clustering.
                "stop_count":  len(json.loads(w.waypoints_json or "[]")),
            }
            for w in walks
        ]
    }


# ---------------------------------------------------------------------------
# Saved walks — load
# ---------------------------------------------------------------------------

async def _load_walk(db: AsyncSession, walk_id: int) -> SavedWalk:
    walk = (await db.execute(select(SavedWalk).where(SavedWalk.id == walk_id))).scalar_one_or_none()
    if not walk:
        raise HTTPException(404, detail="Walk not found")
    return walk


async def walk_membership_for(db: AsyncSession, walk: SavedWalk) -> dict:
    """Saved + nearby observations → walk_membership.compute(). The SQL only
    pre-filters by bounding box; every membership decision is in the service."""
    ids = list(wm.saved_obs_ids(walk))
    saved = {}
    if ids:
        rows = (await db.execute(select(Observation).where(Observation.id.in_(ids)))).scalars().all()
        saved = {o.id: o for o in rows}
    nearby = []
    bb = wm.search_bbox(walk)
    if bb:
        nearby = (await db.execute(
            select(Observation).where(
                Observation.latitude.between(bb[0], bb[1]),
                Observation.longitude.between(bb[2], bb[3]),
            )
        )).scalars().all()
    return wm.compute(walk, saved, nearby)


def _require_curator(identity: Identity) -> None:
    if identity.is_guest:
        raise HTTPException(403, "Curator only")


def _walk_out(walk: SavedWalk, mem: dict) -> dict:
    return {
        "id":           walk.id,
        "name":         walk.name,
        "created_at":   walk.created_at.isoformat() if walk.created_at else None,
        "obs_ids":      json.loads(walk.obs_ids_json or "[]"),
        "waypoints":    json.loads(walk.waypoints_json or "[]"),
        "route_geojson": json.loads(walk.route_geojson) if walk.route_geojson else None,
        "distance_m":   walk.distance_m,
        "duration_min": walk.duration_min,
        # Stops resolved from CURRENT observations + route-proximity members
        # (walk_membership.py). The frontend draws these, not waypoints' labels.
        "stops":        wm.public_stops(mem),
        "membership": {
            "rule":             mem["rule"],
            "line_source":      mem["line_source"],
            "member_obs_ids":   mem["member_obs_ids"],
            "joined_count":     mem["joined_count"],
            "older_candidates": mem["older_candidates"],
        },
    }


@router.get("/saves/{walk_id}")
async def get_walk(walk_id: int, db: AsyncSession = Depends(get_db)):
    walk = await _load_walk(db, walk_id)
    return _walk_out(walk, await walk_membership_for(db, walk))


# ---------------------------------------------------------------------------
# Saved walks — membership actions (curator only; each re-reads the row by id
# after commit and returns the recomputed walk)
# ---------------------------------------------------------------------------

class MembershipSettings(BaseModel):
    buffer_m: Optional[float] = None    # None = back to the default (25 m)


class ObsIdsBody(BaseModel):
    obs_ids: List[int]


async def _commit_and_reread(db: AsyncSession, walk_id: int) -> dict:
    await db.commit()
    db.expire_all()
    walk = await _load_walk(db, walk_id)
    return _walk_out(walk, await walk_membership_for(db, walk))


@router.patch("/saves/{walk_id}/membership")
async def set_walk_membership(
    walk_id: int, body: MembershipSettings,
    db: AsyncSession = Depends(get_db), identity: Identity = Depends(get_identity),
):
    _require_curator(identity)
    walk = await _load_walk(db, walk_id)
    if body.buffer_m is not None and not (wm.BUFFER_MIN_M <= body.buffer_m <= wm.BUFFER_MAX_M):
        raise HTTPException(422, f"buffer_m must be {wm.BUFFER_MIN_M:g}–{wm.BUFFER_MAX_M:g} m")
    walk.buffer_m = body.buffer_m
    out = await _commit_and_reread(db, walk_id)
    if out["membership"]["rule"]["buffer_m"] != (body.buffer_m or wm.DEFAULT_BUFFER_M):
        raise HTTPException(500, "buffer_m write did not persist")
    return out


@router.post("/saves/{walk_id}/accept")
async def accept_older_obs(
    walk_id: int, body: ObsIdsBody,
    db: AsyncSession = Depends(get_db), identity: Identity = Depends(get_identity),
):
    """Accept older photos from the review list. Only ids that are currently
    older candidates of THIS walk are accepted; anything else is rejected."""
    _require_curator(identity)
    walk = await _load_walk(db, walk_id)
    mem = await walk_membership_for(db, walk)
    allowed = {oid for c in mem["older_candidates"] for oid in c["obs_ids"]}
    bad = sorted(set(body.obs_ids) - allowed)
    if bad:
        raise HTTPException(400, f"not older candidates of this walk: {bad}")
    current = set(json.loads(walk.accepted_obs_json or "[]"))
    walk.accepted_obs_json = json.dumps(sorted(current | set(body.obs_ids)))
    out = await _commit_and_reread(db, walk_id)
    missing = sorted(set(body.obs_ids) - set(out["membership"]["member_obs_ids"]))
    if missing:
        raise HTTPException(500, f"accepted but not members after re-read: {missing}")
    return out


@router.post("/saves/{walk_id}/exclude")
async def exclude_joined_obs(
    walk_id: int, body: ObsIdsBody,
    db: AsyncSession = Depends(get_db), identity: Identity = Depends(get_identity),
):
    """Remove photos that JOINED by proximity (not saved-stop photos)."""
    _require_curator(identity)
    walk = await _load_walk(db, walk_id)
    mem = await walk_membership_for(db, walk)
    joined = {oid for st in mem["stops"] for oid in st["joined_obs_ids"]}
    bad = sorted(set(body.obs_ids) - joined)
    if bad:
        raise HTTPException(400, f"not proximity-joined photos of this walk: {bad}")
    current = set(json.loads(walk.excluded_obs_json or "[]"))
    walk.excluded_obs_json = json.dumps(sorted(current | set(body.obs_ids)))
    accepted = set(json.loads(walk.accepted_obs_json or "[]")) - set(body.obs_ids)
    walk.accepted_obs_json = json.dumps(sorted(accepted)) if accepted else None
    out = await _commit_and_reread(db, walk_id)
    still = sorted(set(body.obs_ids) & set(out["membership"]["member_obs_ids"]))
    if still:
        raise HTTPException(500, f"excluded but still members after re-read: {still}")
    return out


@router.post("/saves/{walk_id}/renumber")
async def renumber_walk(
    walk_id: int,
    db: AsyncSession = Depends(get_db), identity: Identity = Depends(get_identity),
):
    """Current stops (saved + joined) become the saved snapshot, numbered 1..N."""
    _require_curator(identity)
    walk = await _load_walk(db, walk_id)
    mem = await walk_membership_for(db, walk)
    waypoints, obs_ids = wm.renumbered_snapshot(mem)
    walk.waypoints_json = json.dumps(waypoints)
    walk.obs_ids_json = json.dumps(obs_ids)
    walk.accepted_obs_json = None      # accepted photos are now saved-stop photos
    out = await _commit_and_reread(db, walk_id)
    labels = [s["label"] for s in out["stops"]]
    if labels != [str(i + 1) for i in range(len(waypoints))] or out["obs_ids"] != obs_ids:
        raise HTTPException(500, f"renumber did not persist as written (labels {labels})")
    return out


# ---------------------------------------------------------------------------
# Saved walks — delete
# ---------------------------------------------------------------------------

@router.delete("/saves/{walk_id}")
async def delete_walk(
    walk_id: int, db: AsyncSession = Depends(get_db), identity: Identity = Depends(get_identity),
):
    """Curator only. 409 while an experience page for this walk is published.
    Draft publications go with the walk; 'unpublished' ones stay as history
    (saved_walk_id → NULL by the FK's ON DELETE SET NULL)."""
    from app.models.experience import ExperiencePublication
    _require_curator(identity)
    result = await db.execute(select(SavedWalk).where(SavedWalk.id == walk_id))
    walk = result.scalar_one_or_none()
    if not walk:
        raise HTTPException(404, detail="Walk not found")
    pubs = (await db.execute(select(ExperiencePublication).where(
        ExperiencePublication.saved_walk_id == walk_id))).scalars().all()
    published = [p.slug for p in pubs if p.status == "published"]
    if published:
        raise HTTPException(409, detail=f"Walk is published as {', '.join(repr(s) for s in published)} "
                                        f"— unpublish it before deleting the walk")
    for p in pubs:
        if p.status == "draft":
            await db.delete(p)
    await db.delete(walk)
    await db.commit()
    return {"ok": True}
