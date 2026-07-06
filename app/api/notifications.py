"""
notifications.py — Seasonal return notifications (Phase 11b).

Endpoints:
  GET  /api/notifications/seasonal-returns          — current returning species
  POST /api/notifications/seasonal-returns/dismiss  — dismiss one (per species per season)

In-app only — no browser push. Read endpoint is open (guests see nothing useful
since the bell is owner-only on the frontend); dismiss is a write, so guests are
blocked by the global guest middleware.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.notification import NotificationDismissal
from app.models.species import Species
from app.services.seasonal_returns import DEFAULT_LEAD_DAYS, compute_seasonal_returns

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


DEFAULT_LIMIT = 10


@router.get("/seasonal-returns")
async def seasonal_returns(
    lead_days: int = DEFAULT_LEAD_DAYS,
    limit: int = DEFAULT_LIMIT,
    show_all: bool = Query(False, alias="all"),
    db: AsyncSession = Depends(get_db),
):
    """Ranked, capped seasonal-return notifications.

    Items are ranked: in-season-now before starting-soon, then most-recently-seen,
    then most-encountered. By default the top `limit` (10) are returned; pass
    `?all=true` for the full ranked list. `total` is always the full count so the
    UI can show "10 of 80".
    """
    lead_days = max(0, min(int(lead_days), 60))
    limit = max(1, min(int(limit), 200))

    ranked = await compute_seasonal_returns(db, user_id=1, lead_days=lead_days)
    total = len(ranked)
    items = ranked if show_all else ranked[:limit]
    return {"shown": len(items), "total": total, "lead_days": lead_days, "items": items}


class DismissBody(BaseModel):
    species_id: int
    season_key: str


@router.post("/seasonal-returns/dismiss")
async def dismiss_seasonal_return(body: DismissBody, db: AsyncSession = Depends(get_db)):
    if not (body.season_key or "").strip():
        raise HTTPException(422, detail="season_key required")

    sp = await db.scalar(select(Species).where(Species.id == body.species_id))
    if not sp:
        raise HTTPException(404, detail="Species not found")

    existing = await db.scalar(
        select(NotificationDismissal).where(
            NotificationDismissal.user_id == 1,
            NotificationDismissal.species_id == body.species_id,
            NotificationDismissal.season_key == body.season_key.strip(),
        )
    )
    if existing is None:
        db.add(NotificationDismissal(
            user_id=1, species_id=body.species_id, season_key=body.season_key.strip(),
        ))
        await db.commit()
        log.info("Dismissed seasonal return species=%d season=%s", body.species_id, body.season_key)

    return {"ok": True, "species_id": body.species_id, "season_key": body.season_key.strip()}
