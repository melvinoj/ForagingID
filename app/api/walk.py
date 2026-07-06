"""
walk.py — Walk feature API: ORS route proxy + saved walks CRUD.

Endpoints:
  POST /api/walk/ors-route      — proxy to OpenRouteService foot-hiking directions
  POST /api/walk/saves          — save a walk
  GET  /api/walk/saves          — list all saved walks (summary)
  GET  /api/walk/saves/{id}     — load a saved walk (full data)
  DELETE /api/walk/saves/{id}   — delete a saved walk
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
from app.models.walk import SavedWalk

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
async def save_walk(body: SaveWalkRequest, db: AsyncSession = Depends(get_db)):
    walk = SavedWalk(
        name=body.name,
        obs_ids_json=json.dumps(body.obs_ids),
        waypoints_json=json.dumps(body.waypoints),
        route_geojson=json.dumps(body.route_geojson) if body.route_geojson else None,
        distance_m=body.distance_m,
        duration_min=body.duration_min,
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
                "stop_count":  len(json.loads(w.obs_ids_json or "[]")),
            }
            for w in walks
        ]
    }


# ---------------------------------------------------------------------------
# Saved walks — load
# ---------------------------------------------------------------------------

@router.get("/saves/{walk_id}")
async def get_walk(walk_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SavedWalk).where(SavedWalk.id == walk_id))
    walk = result.scalar_one_or_none()
    if not walk:
        raise HTTPException(404, detail="Walk not found")
    return {
        "id":           walk.id,
        "name":         walk.name,
        "created_at":   walk.created_at.isoformat() if walk.created_at else None,
        "obs_ids":      json.loads(walk.obs_ids_json or "[]"),
        "waypoints":    json.loads(walk.waypoints_json or "[]"),
        "route_geojson": json.loads(walk.route_geojson) if walk.route_geojson else None,
        "distance_m":   walk.distance_m,
        "duration_min": walk.duration_min,
    }


# ---------------------------------------------------------------------------
# Saved walks — delete
# ---------------------------------------------------------------------------

@router.delete("/saves/{walk_id}")
async def delete_walk(walk_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SavedWalk).where(SavedWalk.id == walk_id))
    walk = result.scalar_one_or_none()
    if not walk:
        raise HTTPException(404, detail="Walk not found")
    await db.delete(walk)
    await db.commit()
    return {"ok": True}
