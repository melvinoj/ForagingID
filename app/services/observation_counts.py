"""Single source of truth for observation counts.

Every endpoint/UI that shows "total / geotagged / map pins" MUST call
``observation_counts()`` so the numbers can never disagree across the app. This
retires the recurring "Fix 5 total/geotagged count" drift: instead of each call site
re-deriving a count with a slightly different WHERE clause (lat-only vs lat+lng,
all rows vs active rows), they all read the same labelled values defined here.

Definitions (pick the field that matches what a given display *means*):
  total_all          — every observation row, no filter.
  active             — identification_status IN (identified, below_threshold,
                       pending_identification): the "live" set; excludes
                       not_plant / failed_identification / pending_connection.
  geotagged_all      — any row with BOTH latitude and longitude set.
  geotagged_active   — active rows with BOTH latitude and longitude set.
  map_eligible       — review_status IN (approved, manually_verified)
                       AND identification_status = 'identified'.
  map_pins           — map_eligible AND geotagged (what actually renders on the map).
"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.observation import Observation

# Shared predicates — the only place these definitions live.
ACTIVE_IDENT = Observation.identification_status.in_(
    ["identified", "below_threshold", "pending_identification"]
)
HAS_COORDS = Observation.latitude.is_not(None) & Observation.longitude.is_not(None)
MAP_ELIGIBLE = Observation.review_status.in_(["approved", "manually_verified"]) & (
    Observation.identification_status == "identified"
)

# Review queue — what the Review page shows by default (its Status filter opens
# on "Needs review"). The ONLY definition: the list query
# (GET /api/observations?review_status=needs_review), the per-status count the
# page paginates with, and the nav Review badge (review_queue_count) all use it,
# so the badge equals the queue (fix batch 14, 21 Oct 2026 — the badge used to
# add every 'pending' row too: 2,080 vs the queue's 386). The second clause is
# the list query's existing belt-and-suspenders exclusion, kept verbatim.
REVIEW_QUEUE_STATUS = "needs_review"
REVIEW_QUEUE = (Observation.review_status == REVIEW_QUEUE_STATUS) & (
    Observation.review_status.notin_(["approved", "manually_verified", "rejected"])
)


async def review_queue_count(db: AsyncSession) -> int:
    return await db.scalar(select(func.count(Observation.id)).where(REVIEW_QUEUE)) or 0


async def observation_counts(db: AsyncSession) -> dict:
    """Return the canonical observation counts. See module docstring for definitions."""

    async def _count(*conds) -> int:
        stmt = select(func.count(Observation.id))
        for c in conds:
            stmt = stmt.where(c)
        return int(await db.scalar(stmt) or 0)

    return {
        "total_all":        await _count(),
        "active":           await _count(ACTIVE_IDENT),
        "geotagged_all":    await _count(HAS_COORDS),
        "geotagged_active": await _count(ACTIVE_IDENT, HAS_COORDS),
        "map_eligible":     await _count(MAP_ELIGIBLE),
        "map_pins":         await _count(MAP_ELIGIBLE, HAS_COORDS),
    }
