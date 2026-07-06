"""
Intent-Based Search API — Phase 10.6 Section 6

GET /api/find/in-season   — all confirmed species in season this month
GET /api/find/recipes     — recipe search by ingredient free-text
GET /api/find/medicinal   — medicinal prep search by symptom/use free-text

Mode 4 (Near me + in season) is handled client-side by calling /api/nearby
and filtering in_season=True — no separate endpoint needed.
"""

import json as _json
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.observation import Observation
from app.models.species import Species, SpeciesRecipe
from app.services.phenology import species_in_season

router = APIRouter(prefix="/api/find", tags=["find"])

_CONFIRMED = ("approved", "manually_verified")


# ---------------------------------------------------------------------------
# Mode 1: GET /api/find/in-season
# All confirmed species in season for the given month.
# Uses phenological data where set; falls back to photo-month proxy.
# ---------------------------------------------------------------------------

@router.get("/in-season")
async def find_in_season(
    month: int = Query(..., ge=1, le=12, description="Calendar month 1–12"),
    edible_only: bool = Query(False, description="If true, only return edible/caution species"),
    db: AsyncSession = Depends(get_db),
):
    """
    Return all confirmed species that are active/harvestable this month.

    Priority: if species has any phenological months set → use those.
    Fallback: if any confirmed observation's photo_taken_at month is within
    ±1 of the requested month → mark in season (existing photo proxy).
    """
    # Fetch all confirmed observations with species phenology
    stmt = (
        select(
            Observation.species_primary,
            Observation.photo_taken_at,
            Observation.thumbnail_path,
            Species.id.label("species_id"),
            Species.common_names,
            Species.preferred_common_name,
            Species.edibility_status,
            Species.flower_months,
            Species.fruit_months,
            Species.leaf_months,
            Species.peak_season,
        )
        .join(Species, Species.scientific_name == Observation.species_primary, isouter=True)
        .where(Observation.review_status.in_(list(_CONFIRMED)))
        .where(Observation.identification_status == "identified")
        .where(Observation.species_primary.isnot(None))
    )
    rows = (await db.execute(stmt)).all()

    # Recipe counts per species (non-medicinal, approved)
    rec_stmt = (
        select(
            SpeciesRecipe.species_id,
            func.count(SpeciesRecipe.id).label("n"),
        )
        .where(SpeciesRecipe.status == "approved")
        .where(SpeciesRecipe.is_medicinal_prep.is_(False))
        .group_by(SpeciesRecipe.species_id)
    )
    recipe_counts = {r.species_id: r.n for r in (await db.execute(rec_stmt)).all()}

    # Aggregate per species
    agg: dict = {}
    for r in rows:
        key = r.species_primary
        if key not in agg:
            cn = None
            if r.common_names:
                try:
                    cl = _json.loads(r.common_names) or []
                    cn = cl[0] if cl else None
                except Exception:
                    pass
            agg[key] = {
                "scientific_name": key,
                "common_name": r.preferred_common_name or cn,
                "edibility_status": r.edibility_status,
                "flower_months": r.flower_months,
                "fruit_months":  r.fruit_months,
                "leaf_months":   r.leaf_months,
                "peak_season":   r.peak_season,
                "species_id":    r.species_id,
                "thumbnail":     r.thumbnail_path,
                "observation_count": 0,
                "in_season": False,
                # Store photo months for fallback
                "_photo_months": set(),
            }
        sp = agg[key]
        sp["observation_count"] += 1
        if sp["thumbnail"] is None and r.thumbnail_path:
            sp["thumbnail"] = r.thumbnail_path
        if r.photo_taken_at:
            sp["_photo_months"].add(r.photo_taken_at.month)

    # Compute in_season using phenology or photo proxy
    results = []
    for key, sp in agg.items():
        # Pick any photo month that is closest to target (for fallback)
        # — try exact match first, then ±1
        photo_months = sp.pop("_photo_months")
        best_photo_month = None
        for m in photo_months:
            if best_photo_month is None:
                best_photo_month = m
            # Prefer the one within the ±1 window
            if abs(m - month) <= 1 or abs(m - month) >= 11:
                best_photo_month = m

        sp["in_season"] = species_in_season(
            flower_months=sp["flower_months"],
            fruit_months=sp["fruit_months"],
            leaf_months=sp["leaf_months"],
            ref_month=month,
            photo_month=best_photo_month,
        )
        sp["recipe_count"] = recipe_counts.get(sp["species_id"], 0)
        results.append(sp)

    # Filter by edible_only if requested
    if edible_only:
        results = [s for s in results if s["edibility_status"] in ("edible", "caution")]

    # Sort: in_season first, then alphabetically
    results.sort(key=lambda x: (0 if x["in_season"] else 1, x["scientific_name"]))

    return {
        "month": month,
        "total": len(results),
        "in_season_count": sum(1 for s in results if s["in_season"]),
        "results": results,
    }


# ---------------------------------------------------------------------------
# Mode 2: GET /api/find/recipes?q=nettle
# Full-text search on recipe title + body (non-medicinal, approved only)
# ---------------------------------------------------------------------------

@router.get("/recipes")
async def find_recipes(
    q: str = Query(..., min_length=2, description="Ingredient or keyword to search"),
    db: AsyncSession = Depends(get_db),
):
    """
    Search approved recipes for an ingredient or keyword.
    Returns matches grouped by species, with snippet context.
    """
    pattern = f"%{q}%"
    stmt = (
        select(
            SpeciesRecipe.id,
            SpeciesRecipe.title,
            SpeciesRecipe.body,
            SpeciesRecipe.season,
            SpeciesRecipe.is_preferred,
            SpeciesRecipe.species_id,
            Species.scientific_name,
            Species.preferred_common_name,
            Species.common_names,
            Species.edibility_status,
        )
        .join(Species, Species.id == SpeciesRecipe.species_id)
        .where(SpeciesRecipe.status == "approved")
        .where(SpeciesRecipe.is_medicinal_prep.is_(False))
        .where(
            or_(
                SpeciesRecipe.title.ilike(pattern),
                SpeciesRecipe.body.ilike(pattern),
            )
        )
        .order_by(Species.scientific_name, SpeciesRecipe.is_preferred.desc())
    )
    rows = (await db.execute(stmt)).all()

    # Group by species
    grouped: dict = {}
    for r in rows:
        key = r.scientific_name
        if key not in grouped:
            cn = None
            if r.common_names:
                try:
                    cl = _json.loads(r.common_names) or []
                    cn = cl[0] if cl else None
                except Exception:
                    pass
            grouped[key] = {
                "scientific_name": key,
                "common_name": r.preferred_common_name or cn,
                "edibility_status": r.edibility_status,
                "species_id": r.species_id,
                "recipes": [],
            }
        grouped[key]["recipes"].append({
            "id": r.id,
            "title": r.title,
            "body": r.body,
            "season": r.season,
            "is_preferred": r.is_preferred,
            "snippet": _snippet(r.body, q, 120),
        })

    return {
        "query": q,
        "species_count": len(grouped),
        "recipe_count": sum(len(v["recipes"]) for v in grouped.values()),
        "results": list(grouped.values()),
    }


# ---------------------------------------------------------------------------
# Mode 3: GET /api/find/medicinal?q=inflammation
# Full-text search on medicinal preparation title + body
# ---------------------------------------------------------------------------

@router.get("/medicinal")
async def find_medicinal(
    q: str = Query(..., min_length=2, description="Symptom, condition, or use to search"),
    db: AsyncSession = Depends(get_db),
):
    """
    Search medicinal preparations for a symptom or use.
    Searches is_medicinal_prep=True rows in species_recipes.
    """
    pattern = f"%{q}%"
    stmt = (
        select(
            SpeciesRecipe.id,
            SpeciesRecipe.title,
            SpeciesRecipe.body,
            SpeciesRecipe.season,
            SpeciesRecipe.species_id,
            Species.scientific_name,
            Species.preferred_common_name,
            Species.common_names,
            Species.edibility_status,
        )
        .join(Species, Species.id == SpeciesRecipe.species_id)
        .where(SpeciesRecipe.status == "approved")
        .where(SpeciesRecipe.is_medicinal_prep.is_(True))
        .where(
            or_(
                SpeciesRecipe.title.ilike(pattern),
                SpeciesRecipe.body.ilike(pattern),
            )
        )
        .order_by(Species.scientific_name, SpeciesRecipe.created_at)
    )
    rows = (await db.execute(stmt)).all()

    # Group by species
    grouped: dict = {}
    for r in rows:
        key = r.scientific_name
        if key not in grouped:
            cn = None
            if r.common_names:
                try:
                    cl = _json.loads(r.common_names) or []
                    cn = cl[0] if cl else None
                except Exception:
                    pass
            grouped[key] = {
                "scientific_name": key,
                "common_name": r.preferred_common_name or cn,
                "edibility_status": r.edibility_status,
                "species_id": r.species_id,
                "preparations": [],
            }
        grouped[key]["preparations"].append({
            "id": r.id,
            "title": r.title,
            "body": r.body,
            "snippet": _snippet(r.body, q, 120),
        })

    return {
        "query": q,
        "species_count": len(grouped),
        "prep_count": sum(len(v["preparations"]) for v in grouped.values()),
        "results": list(grouped.values()),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _snippet(text: str, query: str, max_len: int = 120) -> str:
    """Extract a context snippet around the first match of query in text."""
    if not text:
        return ""
    idx = text.lower().find(query.lower())
    if idx == -1:
        return text[:max_len] + ("…" if len(text) > max_len else "")
    start = max(0, idx - 40)
    end = min(len(text), idx + len(query) + 80)
    snippet = ("…" if start > 0 else "") + text[start:end] + ("…" if end < len(text) else "")
    return snippet
