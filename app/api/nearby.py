"""
/api/nearby — "Near me / in season" species list (prompt 10a.4).

Given a GPS position and a radius, return the confirmed species observed
within that radius, aggregated per species. The data comes from a single
join (observations → species) — there are no per-pin API calls.

Each species carries:
  - the nearest-observation distance (metres)
  - an observation count (within radius)
  - the most recent photo + its thumbnail
  - an edibility status (badge labelling is the frontend's job)
  - an in_season flag from the photo-month proxy: any observation whose
    photo_taken_at month is within ±1 of the supplied calendar month
    (December/January wrap around).

Display policy matches /api/map/geojson — CONFIRMED, GEOTAGGED sightings only.
Edibility is NOT a filter: every confirmed species in range is returned and the
frontend's edibility badge does the labelling.

The four core inputs are lat, lng, radius_m, month. The optional species /
months / workshop / human_only params let the caller mirror the map's active
filters so "near me" stays consistent with what's shown on the map.
"""

import json as _json
import math
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.observation import Observation
from app.models.species import Species
from app.services.phenology import species_in_season

router = APIRouter(prefix="/api/nearby", tags=["nearby"])

_CONFIRMED_STATUSES = ("approved", "manually_verified")
_EARTH_R = 6371000.0  # metres
_M_PER_DEG_LAT = 111320.0


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return _EARTH_R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _in_season(photo_month: Optional[int], ref_month: int) -> bool:
    """True if photo_month is within ±1 of ref_month, wrapping Dec↔Jan.
    Kept for backwards compatibility — nearby() now calls species_in_season()
    which uses this as its fallback when no phenological data is set."""
    if not photo_month:
        return False
    return any(((ref_month - 1 + d) % 12) + 1 == photo_month for d in (-1, 0, 1))


@router.get("")
async def nearby(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_m: float = Query(200.0, gt=0),
    month: int = Query(..., ge=1, le=12),
    species: Optional[str] = Query(None, description="CSV of scientific names — mirrors the active species filter"),
    months: Optional[str] = Query(None, description="CSV of months 1-12 — mirrors the active month filter"),
    workshop: bool = Query(False),
    human_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    # Bounding-box pre-filter (index-friendly on lat/lng) → exact haversine refine.
    lat_delta = radius_m / _M_PER_DEG_LAT
    cos_lat = abs(math.cos(math.radians(lat))) or 1e-6
    lng_delta = radius_m / (_M_PER_DEG_LAT * cos_lat)

    filters = [
        Observation.latitude.isnot(None),
        Observation.longitude.isnot(None),
        Observation.review_status.in_(list(_CONFIRMED_STATUSES)),
        Observation.identification_status == "identified",
        Observation.species_primary.isnot(None),
        Observation.latitude >= lat - lat_delta,
        Observation.latitude <= lat + lat_delta,
        Observation.longitude >= lng - lng_delta,
        Observation.longitude <= lng + lng_delta,
    ]
    if workshop:
        filters.append(Observation.workshop_suitable.is_(True))
    if human_only:
        filters.append(Observation.human_corrected.is_(True))
    if species:
        names = [s for s in (x.strip() for x in species.split(",")) if s]
        if names:
            filters.append(Observation.species_primary.in_(names))

    month_filter = None
    if months:
        try:
            month_filter = {int(x) for x in months.split(",") if x.strip()}
        except ValueError:
            month_filter = None

    # Single join: observations → species (by name; species_primary is always
    # set on confirmed rows, whereas species_id can be NULL when the FK is unsynced).
    stmt = (
        select(
            Observation.species_primary,
            Observation.latitude,
            Observation.longitude,
            Observation.photo_taken_at,
            Observation.thumbnail_path,
            Species.edibility_status,
            Species.common_names,
            # Phenological fields — NULL when not yet populated; fallback logic applied below
            Species.flower_months,
            Species.fruit_months,
            Species.leaf_months,
            Species.peak_season,
        )
        .join(Species, Species.scientific_name == Observation.species_primary, isouter=True)
        .where(*filters)
    )
    rows = (await db.execute(stmt)).all()

    # Aggregate per species in one pass over the joined rows.
    agg: dict = {}
    for r in rows:
        d = _haversine_m(lat, lng, r.latitude, r.longitude)
        if d > radius_m:
            continue
        pmonth = r.photo_taken_at.month if r.photo_taken_at else None
        if month_filter and (pmonth not in month_filter):
            continue

        key = r.species_primary
        a = agg.get(key)
        if a is None:
            common_name = None
            if r.common_names:
                try:
                    cn = _json.loads(r.common_names) or []
                    common_name = cn[0] if cn else None
                except Exception:
                    pass
            a = {
                "scientific_name": key,
                "common_name": common_name,
                "edibility_status": r.edibility_status,
                "observation_count": 0,
                "most_recent_photo_taken_at": None,
                "thumbnail": None,
                "distance_m": d,
                "in_season": False,
                # Phenology — passed through to Find tab / Near me display
                "flower_months": r.flower_months,
                "fruit_months":  r.fruit_months,
                "leaf_months":   r.leaf_months,
                "peak_season":   r.peak_season,
            }
            agg[key] = a

        a["observation_count"] += 1
        if d < a["distance_m"]:
            a["distance_m"] = d

        # In-season check: phenological data takes priority over photo proxy
        if not a["in_season"]:
            a["in_season"] = species_in_season(
                flower_months=r.flower_months,
                fruit_months=r.fruit_months,
                leaf_months=r.leaf_months,
                ref_month=month,
                photo_month=pmonth,
            )

        # Track the most recent photo and carry its thumbnail.
        iso = r.photo_taken_at.isoformat() if r.photo_taken_at else None
        if iso and (a["most_recent_photo_taken_at"] is None or iso > a["most_recent_photo_taken_at"]):
            a["most_recent_photo_taken_at"] = iso
            a["thumbnail"] = r.thumbnail_path
        if a["thumbnail"] is None and r.thumbnail_path:
            a["thumbnail"] = r.thumbnail_path

    results = sorted(agg.values(), key=lambda x: x["distance_m"])
    for a in results:
        a["distance_m"] = round(a["distance_m"], 1)

    return {"results": results, "count": len(results), "radius_m": radius_m}
