"""
personal_lists.py — Standing personal species lists + the personal card (Phase 11a.3).

A personal list is the "workshop-of-one": the same machinery as a multi-participant
workshop list, differing only in member count. The standing "My Season" list is
auto-created per user (user_id = 1) on first access.

Architectural boundary (11a): everything here references species READ-ONLY by ID.
  - List membership stores species_id only — never copies species data.
  - The personal card is a read-only JOIN of the shared species scaffold (name, photo,
    recipe/notes) with this user's encounters. It never writes to species / observations
    / enrichment tables.

Endpoints:
  GET    /api/personal-lists/my-season                      — standing list + read-only species rows
  POST   /api/personal-lists/my-season/species              — add a species (by id) to the standing list
  DELETE /api/personal-lists/my-season/species/{species_id} — remove a species from the standing list
  GET    /api/personal-lists/card/{species_id}              — personal card (scaffold ⋈ your encounters)
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.culinary import CulinaryInfo
from app.models.encounter import Encounter
from app.models.observation import Observation
from app.models.personal_list import PersonalList, PersonalListSpecies
from app.models.species import Species, SpeciesRecipe

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/personal-lists", tags=["personal-lists"])

USER_ID = 1
MY_SEASON_SLUG = "my-season"


# ---------------------------------------------------------------------------
# Standing list helper — get or create "My Season" for the current user
# ---------------------------------------------------------------------------

async def _get_or_create_my_season(db: AsyncSession, user_id: int = USER_ID) -> PersonalList:
    pl = await db.scalar(
        select(PersonalList).where(
            PersonalList.user_id == user_id,
            PersonalList.slug == MY_SEASON_SLUG,
        )
    )
    if pl is None:
        pl = PersonalList(
            user_id=user_id,
            slug=MY_SEASON_SLUG,
            name="My Season",
            is_standing=True,
        )
        db.add(pl)
        await db.commit()
        await db.refresh(pl)
    return pl


def _first_common_name(common_names_json: Optional[str]) -> Optional[str]:
    from app.api.culinary import _parse_json_list
    names = _parse_json_list(common_names_json)
    return names[0] if names else None


async def _species_thumbnail(db: AsyncSession, species: Species) -> Optional[str]:
    """A representative confirmed-observation thumbnail for a species (read-only)."""
    return await db.scalar(
        select(Observation.thumbnail_path)
        .where(Observation.species_primary == species.scientific_name)
        .where(Observation.review_status.in_(["approved", "manually_verified"]))
        .where(Observation.thumbnail_path.is_not(None))
        .order_by(Observation.photo_taken_at.desc().nullslast())
        .limit(1)
    )


# ---------------------------------------------------------------------------
# GET /api/personal-lists/my-season  — standing list + read-only species rows
# ---------------------------------------------------------------------------

@router.get("/my-season")
async def get_my_season(db: AsyncSession = Depends(get_db)):
    pl = await _get_or_create_my_season(db)

    # Per-species encounter counts for this user (read-only aggregate).
    counts = dict(
        (sid, (n, last))
        for sid, n, last in (
            await db.execute(
                select(
                    Encounter.species_id,
                    func.count(Encounter.id),
                    func.max(Encounter.encounter_date),
                )
                .where(Encounter.user_id == USER_ID)
                .where(Encounter.species_id.is_not(None))
                .group_by(Encounter.species_id)
            )
        ).all()
    )

    # Membership rows joined to the shared species scaffold (read-only).
    rows = (
        await db.execute(
            select(PersonalListSpecies, Species)
            .join(Species, PersonalListSpecies.species_id == Species.id)
            .where(PersonalListSpecies.list_id == pl.id)
            .order_by(PersonalListSpecies.added_at.desc())
        )
    ).all()

    species_out = []
    for member, sp in rows:
        thumb = await _species_thumbnail(db, sp)
        n, last = counts.get(sp.id, (0, None))
        species_out.append({
            "species_id":       sp.id,
            "scientific_name":  sp.scientific_name,
            "common_name":      sp.preferred_common_name or _first_common_name(sp.common_names),
            "edibility_status": sp.edibility_status,
            "thumbnail":        thumb,
            "added_at":         member.added_at.isoformat() if member.added_at else None,
            "encounter_count":  n,
            "last_encounter":   last.isoformat() if last else None,
        })

    return {
        "list": {
            "id":          pl.id,
            "slug":        pl.slug,
            "name":        pl.name,
            "is_standing": pl.is_standing,
            "member_count": len(species_out),
        },
        "species": species_out,
    }


# ---------------------------------------------------------------------------
# POST /api/personal-lists/my-season/species  — add a species (read-only ref)
# ---------------------------------------------------------------------------

class AddSpeciesIn(BaseModel):
    species_id: int


@router.post("/my-season/species")
async def add_species_to_my_season(body: AddSpeciesIn, db: AsyncSession = Depends(get_db)):
    # Validate species exists (read-only) — never create or mutate species rows.
    sp = await db.scalar(select(Species).where(Species.id == body.species_id))
    if not sp:
        raise HTTPException(404, detail="Species not found")

    pl = await _get_or_create_my_season(db)

    existing = await db.scalar(
        select(PersonalListSpecies).where(
            PersonalListSpecies.list_id == pl.id,
            PersonalListSpecies.species_id == body.species_id,
        )
    )
    if existing:
        return {"ok": True, "added": False, "species_id": body.species_id}

    db.add(PersonalListSpecies(list_id=pl.id, species_id=body.species_id))
    await db.commit()
    return {"ok": True, "added": True, "species_id": body.species_id}


# ---------------------------------------------------------------------------
# DELETE /api/personal-lists/my-season/species/{species_id}
# ---------------------------------------------------------------------------

@router.delete("/my-season/species/{species_id}")
async def remove_species_from_my_season(species_id: int, db: AsyncSession = Depends(get_db)):
    pl = await _get_or_create_my_season(db)
    member = await db.scalar(
        select(PersonalListSpecies).where(
            PersonalListSpecies.list_id == pl.id,
            PersonalListSpecies.species_id == species_id,
        )
    )
    if not member:
        raise HTTPException(404, detail="Species not in My Season")
    await db.delete(member)
    await db.commit()
    return {"ok": True, "removed": True, "species_id": species_id}


# ---------------------------------------------------------------------------
# GET /api/personal-lists/card/{species_id}  — the personal card
# Read-only join: shared species scaffold ⋈ this user's encounters.
# ---------------------------------------------------------------------------

def _audio_url(audio_path: Optional[str]) -> Optional[str]:
    if not audio_path:
        return None
    return f"/media/encounters/{Path(audio_path).name}"


@router.get("/card/{species_id}")
async def get_personal_card(species_id: int, db: AsyncSession = Depends(get_db)):
    sp = await db.scalar(select(Species).where(Species.id == species_id))
    if not sp:
        raise HTTPException(404, detail="Species not found")

    ci = await db.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id))

    # Preferred (or most recent) approved recipe — read-only scaffold content.
    recipe = await db.scalar(
        select(SpeciesRecipe)
        .where(SpeciesRecipe.species_id == sp.id)
        .where(SpeciesRecipe.status == "approved")
        .order_by(SpeciesRecipe.is_preferred.desc(), SpeciesRecipe.created_at.desc())
        .limit(1)
    )

    thumb = await _species_thumbnail(db, sp)

    # This user's encounters for this species (the personal half of the join).
    enc_rows = (
        await db.execute(
            select(Encounter)
            .where(Encounter.user_id == USER_ID)
            .where(Encounter.species_id == sp.id)
            .order_by(Encounter.encounter_date.desc())
        )
    ).scalars().all()

    encounters = [
        {
            "id":              e.id,
            "encounter_date":  e.encounter_date.isoformat() if e.encounter_date else None,
            "location_name":   e.location_name,
            "latitude":        e.latitude,
            "longitude":       e.longitude,
            "text_note":       e.text_note,
            "audio_url":       _audio_url(e.audio_path),
            "prompt_stage":    e.prompt_stage,
            "prompt_response": e.prompt_response,
        }
        for e in enc_rows
    ]

    # Whether this species is on the standing list (so the card can offer add/remove).
    pl = await _get_or_create_my_season(db)
    in_my_season = await db.scalar(
        select(func.count(PersonalListSpecies.id)).where(
            PersonalListSpecies.list_id == pl.id,
            PersonalListSpecies.species_id == sp.id,
        )
    )

    return {
        # ── Shared species scaffold (read-only) ───────────────────────────
        "species": {
            "id":               sp.id,
            "scientific_name":  sp.scientific_name,
            "common_name":      sp.preferred_common_name or _first_common_name(sp.common_names),
            "common_names":     [n for n in [
                sp.preferred_common_name or _first_common_name(sp.common_names)
            ] if n],
            "edibility_status": sp.edibility_status,
            "peak_season":      sp.peak_season,
            "thumbnail":        thumb,
        },
        "recipe": {"title": recipe.title, "body": recipe.body} if recipe else None,
        "notes": {
            "taste_notes":     ci.taste_notes if ci else None,
            "id_notes":        ci.id_notes if ci else None,
            "medicinal_notes": ci.medicinal_notes if ci else None,
        },
        # ── This user's personal encounters (read-only) ───────────────────
        "encounters":     encounters,
        "encounter_count": len(encounters),
        "in_my_season":    bool(in_my_season),
    }
