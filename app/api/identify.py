"""
Identification trigger endpoint — kick off PlantNet identification from the API.
For large batches use scripts/identify.py instead.
"""

import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List

from app.config import settings
from app.database import get_db
from app.models.observation import Observation, TERMINAL_REVIEW_STATUSES
from app.services.file_cleanup import delete_observation_file
from app.services.id_ratelimit import LOW_CONFIDENCE_THRESHOLD

_log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/identify", tags=["identification"])

_identify_status: dict = {
    "running": False,
    "processed": 0,
    "total": 0,
    "started_at": None,       # Unix timestamp (float) when current run started
    "last_result": None,
    "stop_requested": False,  # set to True by POST /stop; cleared on each new run
}


@router.get("/status")
async def identification_status():
    return _identify_status


@router.get("/pending-connection")
async def pending_connection_count(db: AsyncSession = Depends(get_db)):
    """
    Count observations parked as 'pending_connection' — i.e. identification
    could not run because the device was offline. Drives the reconnect banner.
    """
    from sqlalchemy import func
    count = await db.scalar(
        select(func.count(Observation.id)).where(
            Observation.identification_status == "pending_connection"
        )
    )
    return {"count": count or 0, "running": _identify_status["running"]}


@router.post("/stop")
async def stop_identification():
    """
    Gracefully stop an in-progress identification run.
    The current photo completes normally; no data is lost.
    The job can be resumed at any time via /run with retry_failed=True.
    """
    if not _identify_status["running"]:
        raise HTTPException(status_code=409, detail="No identification run is currently in progress")
    _identify_status["stop_requested"] = True
    return {
        "status": "stop_requested",
        "message": "Will stop after the current photo completes — no data is lost.",
        "processed_so_far": _identify_status["processed"],
    }


class PrefilterFailedRequest(BaseModel):
    dry_run: bool = True


@router.post("/prefilter-failed")
async def prefilter_failed_observations(
    req: PrefilterFailedRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Run the tightened pre-filter against all 'failed_identification' observations.

    dry_run=True  (default): count what would be rejected — no DB changes.
    dry_run=False           : auto-reject non-plant images, mark plant-likely for retry.
                              Returns the same breakdown plus confirmation of changes applied.
    """
    from app.services.prefilter import refilter_failed_observations
    # refilter_failed_observations commits internally when dry_run=False
    result = await refilter_failed_observations(db, dry_run=req.dry_run)
    return result


# Tier thresholds — mirrors the frontend display labels
_TIER_CONFIDENT = 0.80   # confident plant: ready for identification
_TIER_PROBABLE  = 0.55   # probable plant: worth trying
_TIER_UNCERTAIN = 0.0    # uncertain: anything positive but low confidence


def _obs_tier(is_plant: Optional[bool], confidence: Optional[float]) -> str:
    """Classify a single observation into a prefilter tier."""
    if not is_plant:
        return "non_plant"
    conf = confidence or 0.0
    if conf >= _TIER_CONFIDENT:
        return "confident_plant"
    if conf >= _TIER_PROBABLE:
        return "probable_plant"
    return "uncertain"


@router.get("/prefilter-breakdown")
async def prefilter_breakdown(db: AsyncSession = Depends(get_db)):
    """
    4-tier pre-filter breakdown of observations eligible for (re-)identification.

    Scope: observations with identification_status IN ('pending_identification',
           'failed_identification') that passed the pre-filter (is_plant_likely=True).
    Also counts non-plant observations still in pending/failed state.

    Returns per-tier counts and category breakdowns. Does NOT modify any records.
    """
    from sqlalchemy import func
    from sqlalchemy.sql import case

    stmt = select(
        Observation.id,
        Observation.is_plant_likely,
        Observation.plant_detect_confidence,
        Observation.prefilter_category,
        Observation.identification_status,
    ).where(
        Observation.identification_status.in_(["pending_identification", "failed_identification"]),
    )
    rows = (await db.execute(stmt)).all()

    tiers: dict = {
        "confident_plant": {"count": 0, "obs_ids": []},
        "probable_plant":  {"count": 0, "obs_ids": []},
        "uncertain":       {"count": 0, "obs_ids": []},
        "non_plant":       {"count": 0, "obs_ids": [], "categories": {}},
    }
    pending_count = 0
    failed_count  = 0

    for row in rows:
        tier = _obs_tier(row.is_plant_likely, row.plant_detect_confidence)
        tiers[tier]["count"] += 1
        tiers[tier]["obs_ids"].append(row.id)
        if tier == "non_plant" and row.prefilter_category:
            cat = tiers["non_plant"]["categories"]
            cat[row.prefilter_category] = cat.get(row.prefilter_category, 0) + 1
        if row.identification_status == "pending_identification":
            pending_count += 1
        else:
            failed_count += 1

    # Strip obs_ids from response (too large); keep counts only
    for t in tiers.values():
        del t["obs_ids"]

    return {
        "total": len(rows),
        "pending_identification": pending_count,
        "failed_identification":  failed_count,
        "tiers": tiers,
        "thresholds": {
            "confident_plant": _TIER_CONFIDENT,
            "probable_plant":  _TIER_PROBABLE,
        },
    }


class TierActionRequest(BaseModel):
    tier: str          # "confident_plant" | "probable_plant" | "uncertain" | "non_plant" | "all_plant"
    action: str        # "queue_for_id" | "send_to_review" | "reject"
    scope: str = "pending"  # "pending" | "failed" | "both"


@router.post("/tier-action")
async def prefilter_tier_action(
    req: TierActionRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Apply a bulk action to all observations in a pre-filter tier.

    tier:   which confidence tier to target
    action: what to do (queue_for_id / send_to_review / reject)
    scope:  which identification_status to include

    Safeguards:
    - Never touches approved / manually_verified observations
    - Never touches phone upload observations (upload_source='phone')
    - Returns count of affected rows; always a dry-run check first
    """
    from sqlalchemy import and_

    valid_tiers   = {"confident_plant", "probable_plant", "uncertain", "non_plant", "all_plant"}
    valid_actions = {"queue_for_id", "send_to_review", "reject"}
    valid_scopes  = {"pending", "failed", "both"}

    if req.tier   not in valid_tiers:   raise HTTPException(400, f"Invalid tier: {req.tier}")
    if req.action not in valid_actions: raise HTTPException(400, f"Invalid action: {req.action}")
    if req.scope  not in valid_scopes:  raise HTTPException(400, f"Invalid scope: {req.scope}")

    # Build scope filter
    scope_filter = {
        "pending": ["pending_identification"],
        "failed":  ["failed_identification"],
        "both":    ["pending_identification", "failed_identification"],
    }[req.scope]

    # Fetch candidates
    stmt = select(Observation).where(
        Observation.identification_status.in_(scope_filter),
        Observation.review_status.notin_(TERMINAL_REVIEW_STATUSES),
        Observation.upload_source.isnot("phone"),   # never bulk-act on phone uploads
    )
    obs_list = (await db.execute(stmt)).scalars().all()

    # Filter by tier
    def matches(obs: Observation) -> bool:
        if req.tier == "all_plant":
            return bool(obs.is_plant_likely)
        return _obs_tier(obs.is_plant_likely, obs.plant_detect_confidence) == req.tier

    targets = [o for o in obs_list if matches(o)]

    if not targets:
        return {"affected": 0, "action": req.action, "tier": req.tier, "message": "No matching observations"}

    # Apply action
    if req.action == "queue_for_id":
        for o in targets:
            o.identification_status = "pending_identification"
    elif req.action == "send_to_review":
        for o in targets:
            o.review_status = "needs_review"
    elif req.action == "reject":
        for o in targets:
            o.review_status      = "rejected"
            o.identification_status = "not_plant"

    await db.commit()

    if req.action == "reject":
        for o in targets:
            try:
                delete_observation_file(o)
            except Exception as exc:
                _log.warning("bulk reject obs %d: file cleanup failed: %s", o.id, exc)

    return {
        "affected": len(targets),
        "action": req.action,
        "tier": req.tier,
        "scope": req.scope,
        "message": f"{len(targets):,} observations updated",
    }


@router.get("/test-connection")
async def test_plantnet_connection():
    """
    Verify the PlantNet API key is configured and accepted.
    Hits the PlantNet /v2/projects endpoint (no image required).
    Returns: {ok, key_configured, message, status_code?}
    """
    import httpx as _httpx

    api_key = settings.plantnet_api_key
    if not api_key:
        return {
            "ok": False,
            "key_configured": False,
            "message": "No API key set — add PLANTNET_API_KEY=<your-key> to .env and restart the server",
        }

    try:
        async with _httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://my-api.plantnet.org/v2/projects",
                params={"api-key": api_key},
            )

        if r.status_code == 200:
            return {
                "ok": True,
                "key_configured": True,
                "status_code": 200,
                "message": "Connected — PlantNet API key is valid",
            }
        elif r.status_code == 429:
            return {
                "ok": False,
                "key_configured": True,
                "status_code": 429,
                "message": "Key is valid but daily quota exhausted (500 requests/day — resets midnight UTC)",
            }
        elif r.status_code in (401, 403):
            return {
                "ok": False,
                "key_configured": True,
                "status_code": r.status_code,
                "message": "API key rejected — check PLANTNET_API_KEY in .env",
            }
        else:
            return {
                "ok": False,
                "key_configured": True,
                "status_code": r.status_code,
                "message": f"Unexpected response ({r.status_code}) from PlantNet — key may be invalid",
            }
    except _httpx.TimeoutException:
        return {
            "ok": False,
            "key_configured": True,
            "message": "Connection timed out — PlantNet may be unreachable",
        }
    except Exception as e:
        return {
            "ok": False,
            "key_configured": True,
            "message": f"Connection failed: {e}",
        }


@router.get("/queue")
async def review_queue(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Observations flagged for review (low confidence or no match)."""
    stmt = (
        select(
            Observation.id,
            Observation.file_path,
            Observation.thumbnail_path,
            Observation.species_primary,
            Observation.species_candidates_json,
            Observation.identification_status,
            Observation.review_status,
            Observation.latitude,
            Observation.longitude,
            Observation.photo_taken_at,
        )
        .where(Observation.review_status == "needs_review")
        .order_by(Observation.id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id": r.id,
            "file_path": r.file_path,
            "thumbnail_path": r.thumbnail_path,
            "species_primary": r.species_primary,
            "candidates": json.loads(r.species_candidates_json or "[]"),
            "identification_status": r.identification_status,
            "review_status": r.review_status,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "photo_taken_at": r.photo_taken_at.isoformat() if r.photo_taken_at else None,
        }
        for r in rows
    ]


@router.get("/stats")
async def identification_stats(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func
    from sqlalchemy.sql import case

    stmt = select(
        func.count(Observation.id).label("total"),
        func.sum(
            case((Observation.identification_status == "identified", 1), else_=0)
        ).label("identified"),
        func.sum(
            case((Observation.identification_status == "pending_identification", 1), else_=0)
        ).label("pending"),
        func.sum(
            case((Observation.identification_status == "failed_identification", 1), else_=0)
        ).label("failed"),
        func.sum(
            case((Observation.review_status == "needs_review", 1), else_=0)
        ).label("needs_review"),
    )
    row = (await db.execute(stmt)).one()
    return {
        "total": row.total or 0,
        "identified": row.identified or 0,
        "pending_identification": row.pending or 0,
        "failed_identification": row.failed or 0,
        "needs_review": row.needs_review or 0,
        "low_confidence_threshold": LOW_CONFIDENCE_THRESHOLD,
    }
