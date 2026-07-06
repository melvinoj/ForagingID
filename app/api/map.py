"""
Map data endpoint — returns lightweight GeoJSON for Leaflet rendering.

Display policy — CONFIRMED ONLY:
  Only observations that satisfy ALL of the following are returned:
    - review_status IN ('approved', 'manually_verified')
    - identification_status = 'identified'
    - species_primary IS NOT NULL
    - latitude IS NOT NULL  (geotagged)

  Excluded unconditionally:
    - review_status = 'pending'
    - review_status = 'needs_review'
    - review_status = 'rejected'
    - identification_status != 'identified'
    - species_primary IS NULL
    - Not geotagged

  Architectural rule: the map is a CONFIRMED SIGHTINGS ONLY view.
  Pending, needs_review, and rejected observations NEVER appear as pins.
  This is a hard data-layer constraint, not a display-layer toggle.

  Icon tier is determined by enrichment state:
    has_enrichment = True  → Dark green filled pin  (culinary data available)
    has_enrichment = False → Hollow ring pin         (confirmed, enrichment pending)
"""

import json as _json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.culinary import CulinaryInfo
from app.models.observation import Observation
from app.models.species import Species
from app.services.phenology import in_season_now

router = APIRouter(prefix="/api/map", tags=["map"])

_CONFIRMED_STATUSES = ("approved", "manually_verified")


@router.get("/config")
async def map_config():
    """
    Map tile configuration for the frontend.
    Returns the Thunderforest API key so index.html can build tile URLs without
    hardcoding the key. Key is empty string when not configured.
    """
    from app.config import settings as _settings
    return {
        "thunderforest_api_key": _settings.thunderforest_api_key or "",
    }


async def _in_season_species(db: AsyncSession) -> set:
    """Set of scientific names whose phenology puts them in season THIS month.
    Phenology-only (flower/fruit/leaf months + best-effort peak_season text) —
    species with no phenology data are absent, so the map "In season" toggle
    hides them when active (11a Prompt 4)."""
    ref_month = datetime.utcnow().month
    rows = (
        await db.execute(
            select(
                Species.scientific_name,
                Species.flower_months,
                Species.fruit_months,
                Species.leaf_months,
                Species.peak_season,
            )
        )
    ).all()
    out = set()
    for r in rows:
        in_season, _ = in_season_now(
            flower_months=r.flower_months,
            fruit_months=r.fruit_months,
            leaf_months=r.leaf_months,
            peak_season=r.peak_season,
            ref_month=ref_month,
        )
        if in_season:
            out.add(r.scientific_name)
    return out


def _bbox_clause(min_lng, min_lat, max_lng, max_lat):
    """Return a list of WHERE clauses bounding to the given box, or [] if any
    bound is missing (callers then get the unbounded whole-archive result)."""
    if None in (min_lng, min_lat, max_lng, max_lat):
        return []
    return [
        Observation.longitude >= min_lng,
        Observation.longitude <= max_lng,
        Observation.latitude >= min_lat,
        Observation.latitude <= max_lat,
    ]


@router.get("/geojson")
async def map_geojson(
    db: AsyncSession = Depends(get_db),
    min_lng: Optional[float] = Query(None),
    min_lat: Optional[float] = Query(None),
    max_lng: Optional[float] = Query(None),
    max_lat: Optional[float] = Query(None),
):
    """
    GeoJSON of confirmed observations ONLY — the heavy pin payload.

    Strict filter: review_status IN ('approved','manually_verified')
                   AND identification_status = 'identified'
                   AND species_primary IS NOT NULL
                   AND latitude IS NOT NULL

    Pending, needs_review, and rejected observations are excluded at the
    query level — they never appear in the response regardless of GPS state.

    Optional bbox: pass min_lng/min_lat/max_lng/max_lat to bound the result to
    the current map viewport (the frontend refetches pins on pan/zoom). When
    any bound is omitted the whole archive is returned (backward compatible).
    The lightweight whole-archive heatmap is served separately by /api/map/heat.
    """
    _bbox = _bbox_clause(min_lng, min_lat, max_lng, max_lat)
    _cols = [
        Observation.id,
        Observation.species_id,
        Observation.latitude,
        Observation.longitude,
        Observation.thumbnail_path,
        Observation.photo_taken_at,
        Observation.review_status,
        Observation.identification_status,
        Observation.species_primary,
        Observation.species_candidates_json,
        Observation.human_corrected,
        Observation.workshop_suitable,
        Observation.is_plant_likely,
        Observation.plant_detect_confidence,
        Observation.processing_stage,
        Observation.upload_source,
        Observation.obs_category,
        Observation.reviewer_notes,   # used as description for landscape pins
    ]

    # ── Species observations (plant + fungi) — must have species_primary ─────
    stmt = select(*_cols).where(
        Observation.latitude.isnot(None),
        Observation.longitude.isnot(None),
        Observation.review_status.in_(list(_CONFIRMED_STATUSES)),
        Observation.identification_status == "identified",
        Observation.species_primary.isnot(None),
        *_bbox,
    )

    # ── Landscape observations — no species required ─────────────────────────
    stmt_landscape = select(*_cols).where(
        Observation.latitude.isnot(None),
        Observation.longitude.isnot(None),
        Observation.review_status.in_(list(_CONFIRMED_STATUSES)),
        Observation.obs_category == "landscape",
        *_bbox,
    )

    rows_species   = (await db.execute(stmt)).all()
    rows_landscape = (await db.execute(stmt_landscape)).all()
    in_season_names = await _in_season_species(db)
    # Merge — deduplicate landscape rows already covered by species query
    species_ids = {r.id for r in rows_species}
    rows = list(rows_species) + [r for r in rows_landscape if r.id not in species_ids]

    # ── Build species enrichment lookup (common_name + has_enrichment) ─────
    # One extra query, but it's a tiny table and avoids N+1 per feature.
    enrich_rows = (
        await db.execute(
            select(
                Species.id,
                Species.scientific_name,
                Species.common_names,
                Species.edibility_status,
                CulinaryInfo.id.label("culinary_id"),
            ).join(CulinaryInfo, CulinaryInfo.species_id == Species.id, isouter=True)
        )
    ).all()
    # Keyed by BOTH species_id (the FK — preferred) and scientific_name (fallback
    # for the handful of obs whose name has no Species row). Integer and string
    # keys never collide, so a single dict serves both lookups.
    _enrich_lookup = {}
    for er in enrich_rows:
        names = []
        if er.common_names:
            try:
                names = _json.loads(er.common_names) or []
            except Exception:
                pass
        entry = {
            "common_name": names[0] if names else None,
            "common_names": names,
            "edibility_status": er.edibility_status,
            "has_enrichment": er.culinary_id is not None,
        }
        _enrich_lookup[er.id] = entry
        _enrich_lookup[er.scientific_name] = entry
    # ─────────────────────────────────────────────────────────────────────────

    features = []
    for row in rows:
        # All returned rows are confirmed — WHERE clause guarantees this.
        # map_status is always "confirmed"; has_enrichment controls icon style.
        sp_enrich = (
            _enrich_lookup.get(row.species_id)
            or _enrich_lookup.get(row.species_primary)
            or {}
        )

        # Parse top candidate score
        top_score = None
        if row.species_candidates_json:
            try:
                candidates = _json.loads(row.species_candidates_json)
                if candidates:
                    top_score = candidates[0].get("score")
            except Exception:
                pass

        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [row.longitude, row.latitude],
            },
            "properties": {
                "id": row.id,
                "map_status": "confirmed",
                "thumbnail": row.thumbnail_path,
                "taken_at": row.photo_taken_at.isoformat() if row.photo_taken_at else None,
                "review_status": row.review_status,
                "identification_status": row.identification_status,
                "is_plant_likely": row.is_plant_likely,
                "confidence": top_score,
                "stage": row.processing_stage,
                "species_primary": row.species_primary,
                "common_name": sp_enrich.get("common_name"),
                "common_names": sp_enrich.get("common_names", []),
                "edibility_status": sp_enrich.get("edibility_status"),
                "has_enrichment": sp_enrich.get("has_enrichment", False),
                "human_corrected": row.human_corrected,
                "upload_source": row.upload_source,
                "workshop_suitable": row.workshop_suitable,
                "obs_category": row.obs_category or "plant",
                "description": row.reviewer_notes or None,  # landscape description
                "in_season": row.species_primary in in_season_names,
            },
        })

    return {"type": "FeatureCollection", "features": features}


@router.get("/heat")
async def map_heat(db: AsyncSession = Depends(get_db)):
    """
    Lightweight whole-archive points for the heatmap density field.

    Returns coordinates plus the minimal fields the frontend needs to keep the
    heatmap filter-responsive (species / human-verified / workshop / month) —
    but NOT the heavy per-pin payload (no thumbnails, enrichment, candidates).
    Covers every confirmed, geotagged species observation; landscape pins are
    excluded from the density field, matching the pin-layer behaviour. This is
    always the full archive regardless of viewport: the heatmap shows global
    density at any zoom, so it must not be bbox-bounded the way the pins are.

    Also returns whole-archive aggregate counts the frontend uses for the
    stats bar, since the bbox-limited pin layer can no longer be counted for
    those totals.
    """
    base_filters = (
        Observation.latitude.isnot(None),
        Observation.review_status.in_(list(_CONFIRMED_STATUSES)),
    )

    # Species points (plant + fungi) — the heat density field.
    # Order per point: [lat, lng, species_primary, human_corrected,
    #                   workshop_suitable, month|None, in_season]
    rows = (
        await db.execute(
            select(
                Observation.latitude,
                Observation.longitude,
                Observation.species_primary,
                Observation.human_corrected,
                Observation.workshop_suitable,
                Observation.photo_taken_at,
            ).where(
                *base_filters,
                Observation.identification_status == "identified",
                Observation.species_primary.isnot(None),
            )
        )
    ).all()
    in_season_names = await _in_season_species(db)
    # Point order: [lat, lng, species_primary, human_corrected,
    #               workshop_suitable, month|None, in_season]
    points = [
        [
            r.latitude,
            r.longitude,
            r.species_primary,
            bool(r.human_corrected),
            bool(r.workshop_suitable),
            r.photo_taken_at.month if r.photo_taken_at else None,
            r.species_primary in in_season_names,
        ]
        for r in rows
    ]

    # Distinct confirmed species across the whole archive (stats bar)
    species_count = (
        await db.execute(
            select(func.count(func.distinct(Observation.species_primary))).where(
                *base_filters,
                Observation.identification_status == "identified",
                Observation.species_primary.isnot(None),
            )
        )
    ).scalar_one()

    # Landscape pins are confirmed sightings too — count them toward the total
    landscape_count = (
        await db.execute(
            select(func.count(Observation.id)).where(
                *base_filters,
                Observation.obs_category == "landscape",
                Observation.species_primary.is_(None),
            )
        )
    ).scalar_one()

    return {
        "points": points,
        "count": len(points),
        "total": len(points) + (landscape_count or 0),
        "species_count": species_count or 0,
    }
