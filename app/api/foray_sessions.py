"""
foray_sessions.py — Session/Foray model API

Endpoints:
  GET    /api/sessions              — list all sessions (summary)
  POST   /api/sessions              — create session
  GET    /api/sessions/{id}         — detail (species + attendees)
  PATCH  /api/sessions/{id}         — update metadata
  DELETE /api/sessions/{id}         — delete + cascade

  POST   /api/sessions/{id}/auto-populate          — populate from walk pins
  POST   /api/sessions/{id}/species                — add species manually
  DELETE /api/sessions/{id}/species/{species_id}   — remove species
  PATCH  /api/sessions/{id}/species/reorder        — update display_order

  POST   /api/sessions/{id}/attendees              — add attendee
  DELETE /api/sessions/{id}/attendees/{att_id}     — remove attendee
"""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.foray_session import ForagingSession, SessionSpecies, SessionAttendee
from app.models.species import Species
from app.models.walk import SavedWalk
from app.models.observation import Observation

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class SessionCreate(BaseModel):
    name:              str           = Field(..., min_length=1, max_length=200)
    status:            str           = Field("draft", pattern="^(draft|scheduled|completed|archived)$")
    walk_id:           Optional[int] = None
    location_override: Optional[str] = None
    session_date:      Optional[str] = None
    facilitator_notes: Optional[str] = None


class SessionUpdate(BaseModel):
    name:              Optional[str] = Field(None, min_length=1, max_length=200)
    status:            Optional[str] = Field(None, pattern="^(draft|scheduled|completed|archived)$")
    walk_id:           Optional[int] = None
    location_override: Optional[str] = None
    session_date:      Optional[str] = None
    facilitator_notes: Optional[str] = None


class AddSpeciesBody(BaseModel):
    scientific_name: str = Field(..., min_length=1)


class ReorderBody(BaseModel):
    order: list[dict]   # [{species_id: int, display_order: int}, ...]


class AddAttendeeBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session_summary(s: ForagingSession, walk_name: Optional[str] = None) -> dict:
    return {
        "id":                s.id,
        "name":              s.name,
        "status":            s.status,
        "walk_id":           s.walk_id,
        "walk_name":         walk_name,
        "location_override": s.location_override,
        "session_date":      s.session_date,
        "facilitator_notes": s.facilitator_notes,
        "created_at":        s.created_at.isoformat() if s.created_at else None,
        "updated_at":        s.updated_at.isoformat() if s.updated_at else None,
    }


async def _get_session_or_404(db: AsyncSession, session_id: int) -> ForagingSession:
    s = await db.get(ForagingSession, session_id)
    if not s:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return s


# ---------------------------------------------------------------------------
# List / Create
# ---------------------------------------------------------------------------

@router.get("")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(ForagingSession).order_by(ForagingSession.created_at.desc())
    )).scalars().all()
    # Batch-fetch walk names
    walk_ids = {s.walk_id for s in rows if s.walk_id}
    walk_map: dict = {}
    if walk_ids:
        walks = (await db.execute(
            select(SavedWalk).where(SavedWalk.id.in_(walk_ids))
        )).scalars().all()
        walk_map = {w.id: w.name for w in walks}
    return [_session_summary(s, walk_map.get(s.walk_id)) for s in rows]


@router.post("", status_code=201)
async def create_session(body: SessionCreate, db: AsyncSession = Depends(get_db)):
    s = ForagingSession(
        name=body.name,
        status=body.status,
        walk_id=body.walk_id,
        location_override=body.location_override,
        session_date=body.session_date,
        facilitator_notes=body.facilitator_notes,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    walk_name = None
    if s.walk_id:
        w = await db.get(SavedWalk, s.walk_id)
        walk_name = w.name if w else None
    return _session_summary(s, walk_name)


# ---------------------------------------------------------------------------
# Detail / Update / Delete
# ---------------------------------------------------------------------------

@router.get("/{session_id}")
async def get_session(session_id: int, db: AsyncSession = Depends(get_db)):
    s = await _get_session_or_404(db, session_id)

    walk_name = None
    if s.walk_id:
        w = await db.get(SavedWalk, s.walk_id)
        walk_name = w.name if w else None

    # Species — join species table for scientific_name + edibility
    sp_rows = (await db.execute(
        select(SessionSpecies, Species)
        .join(Species, SessionSpecies.species_id == Species.id)
        .where(SessionSpecies.session_id == session_id)
        .order_by(SessionSpecies.display_order, SessionSpecies.added_at)
    )).all()

    species_list = [
        {
            "id":              ss.id,
            "species_id":      ss.species_id,
            "scientific_name": sp.scientific_name,
            "common_names":    json.loads(sp.common_names or "[]"),
            "edibility_status": sp.edibility_status,
            "display_order":   ss.display_order,
            "source":          ss.source,
            "added_at":        ss.added_at.isoformat() if ss.added_at else None,
        }
        for ss, sp in sp_rows
    ]

    # Attendees
    att_rows = (await db.execute(
        select(SessionAttendee)
        .where(SessionAttendee.session_id == session_id)
        .order_by(SessionAttendee.display_order, SessionAttendee.id)
    )).scalars().all()

    attendees = [{"id": a.id, "name": a.name, "display_order": a.display_order} for a in att_rows]

    result = _session_summary(s, walk_name)
    result["species"]   = species_list
    result["attendees"] = attendees
    auto_count   = sum(1 for item in species_list if item["source"] == "auto")
    manual_count = sum(1 for item in species_list if item["source"] == "manual")
    result["auto_count"]   = auto_count
    result["manual_count"] = manual_count
    return result


@router.patch("/{session_id}")
async def update_session(session_id: int, body: SessionUpdate, db: AsyncSession = Depends(get_db)):
    s = await _get_session_or_404(db, session_id)
    if body.name              is not None: s.name              = body.name
    if body.status            is not None: s.status            = body.status
    if body.walk_id           is not None: s.walk_id           = body.walk_id
    if body.location_override is not None: s.location_override = body.location_override
    if body.session_date      is not None: s.session_date      = body.session_date
    if body.facilitator_notes is not None: s.facilitator_notes = body.facilitator_notes
    s.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(s)
    walk_name = None
    if s.walk_id:
        w = await db.get(SavedWalk, s.walk_id)
        walk_name = w.name if w else None
    return _session_summary(s, walk_name)


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: int, db: AsyncSession = Depends(get_db)):
    s = await _get_session_or_404(db, session_id)
    await db.delete(s)
    await db.commit()


# ---------------------------------------------------------------------------
# Auto-populate from walk pins
# ---------------------------------------------------------------------------

@router.post("/{session_id}/auto-populate")
async def auto_populate(session_id: int, db: AsyncSession = Depends(get_db)):
    """
    One-time starting point: query observations associated with the session's
    saved walk (via obs_ids_json), find distinct confirmed species, insert into
    session_species with source=auto.

    Idempotent: clears existing auto entries first, preserves manual entries.
    Walk association required — returns 400 if session has no walk_id.
    """
    s = await _get_session_or_404(db, session_id)
    if not s.walk_id:
        raise HTTPException(status_code=400, detail="Session has no walk associated — set walk_id first")

    walk = await db.get(SavedWalk, s.walk_id)
    if not walk:
        raise HTTPException(status_code=404, detail=f"Walk {s.walk_id} not found")

    obs_ids = json.loads(walk.obs_ids_json or "[]")
    if not obs_ids:
        return {"inserted": 0, "message": "Walk has no pinned observations"}

    # Fetch confirmed species from the pinned observations
    obs_rows = (await db.execute(
        select(Observation.species_primary)
        .where(
            Observation.id.in_(obs_ids),
            Observation.species_primary.is_not(None),
            Observation.review_status.in_(["approved", "manually_verified"]),
            Observation.identification_status == "identified",
        )
    )).scalars().all()

    distinct_names = list(dict.fromkeys(n for n in obs_rows if n))  # preserve first-seen order

    # Resolve species_ids
    if not distinct_names:
        return {"inserted": 0, "message": "No confirmed species found on this walk"}

    sp_rows = (await db.execute(
        select(Species).where(Species.scientific_name.in_(distinct_names))
    )).scalars().all()
    name_to_id = {sp.scientific_name: sp.id for sp in sp_rows}

    # Keep existing manual entries — only clear auto
    await db.execute(
        delete(SessionSpecies).where(
            SessionSpecies.session_id == session_id,
            SessionSpecies.source == "auto",
        )
    )

    # Find manual entries so we don't duplicate them
    manual_sp_ids = set(
        (await db.execute(
            select(SessionSpecies.species_id)
            .where(SessionSpecies.session_id == session_id, SessionSpecies.source == "manual")
        )).scalars().all()
    )

    inserted = 0
    for order, name in enumerate(distinct_names):
        sp_id = name_to_id.get(name)
        if sp_id and sp_id not in manual_sp_ids:
            db.add(SessionSpecies(
                session_id=session_id,
                species_id=sp_id,
                display_order=order,
                source="auto",
            ))
            inserted += 1

    s.updated_at = datetime.utcnow()
    await db.commit()
    return {"inserted": inserted, "total_walk_species": len(distinct_names)}


# ---------------------------------------------------------------------------
# Species management
# ---------------------------------------------------------------------------

@router.post("/{session_id}/species", status_code=201)
async def add_species(session_id: int, body: AddSpeciesBody, db: AsyncSession = Depends(get_db)):
    await _get_session_or_404(db, session_id)

    sp = await db.scalar(select(Species).where(Species.scientific_name == body.scientific_name))
    if not sp:
        raise HTTPException(status_code=404, detail=f"Species '{body.scientific_name}' not found")

    # Idempotent — don't double-add
    existing = await db.scalar(
        select(SessionSpecies).where(
            SessionSpecies.session_id == session_id,
            SessionSpecies.species_id == sp.id,
        )
    )
    if existing:
        return {"id": existing.id, "species_id": sp.id, "source": existing.source, "already_present": True}

    # Place at end
    max_order_row = await db.scalar(
        select(SessionSpecies.display_order)
        .where(SessionSpecies.session_id == session_id)
        .order_by(SessionSpecies.display_order.desc())
    )
    next_order = (max_order_row or 0) + 1

    entry = SessionSpecies(
        session_id=session_id,
        species_id=sp.id,
        display_order=next_order,
        source="manual",
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return {"id": entry.id, "species_id": sp.id, "source": "manual", "already_present": False}


@router.delete("/{session_id}/species/{species_id}", status_code=204)
async def remove_species(session_id: int, species_id: int, db: AsyncSession = Depends(get_db)):
    await _get_session_or_404(db, session_id)
    await db.execute(
        delete(SessionSpecies).where(
            SessionSpecies.session_id == session_id,
            SessionSpecies.species_id == species_id,
        )
    )
    await db.commit()


@router.patch("/{session_id}/species/reorder")
async def reorder_species(session_id: int, body: ReorderBody, db: AsyncSession = Depends(get_db)):
    await _get_session_or_404(db, session_id)
    for item in body.order:
        sp_id = item.get("species_id")
        order = item.get("display_order")
        if sp_id is not None and order is not None:
            row = await db.scalar(
                select(SessionSpecies).where(
                    SessionSpecies.session_id == session_id,
                    SessionSpecies.species_id == sp_id,
                )
            )
            if row:
                row.display_order = order
    await db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Attendees
# ---------------------------------------------------------------------------

@router.post("/{session_id}/attendees", status_code=201)
async def add_attendee(session_id: int, body: AddAttendeeBody, db: AsyncSession = Depends(get_db)):
    await _get_session_or_404(db, session_id)
    max_order = await db.scalar(
        select(SessionAttendee.display_order)
        .where(SessionAttendee.session_id == session_id)
        .order_by(SessionAttendee.display_order.desc())
    )
    att = SessionAttendee(
        session_id=session_id,
        name=body.name.strip(),
        display_order=(max_order or 0) + 1,
    )
    db.add(att)
    await db.commit()
    await db.refresh(att)
    return {"id": att.id, "name": att.name, "display_order": att.display_order}


@router.delete("/{session_id}/attendees/{attendee_id}", status_code=204)
async def remove_attendee(session_id: int, attendee_id: int, db: AsyncSession = Depends(get_db)):
    await _get_session_or_404(db, session_id)
    att = await db.get(SessionAttendee, attendee_id)
    if att and att.session_id == session_id:
        await db.delete(att)
        await db.commit()
