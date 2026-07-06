"""
workshop_tokens.py — Workshop sessions, tokens, and participants.

POST /api/workshop/participants       — create participant
POST /api/workshop/participants/find-or-create
POST /api/workshop/tokens             — mint a guest token
GET  /api/workshop/participants       — list all participants
GET  /api/workshop/tokens             — list all tokens
POST /api/workshop/tokens/{id}/revoke

POST /api/workshop/sessions           — create foraging session
GET  /api/workshop/sessions           — list sessions with counts
PATCH /api/workshop/sessions/{id}     — update session (link walk)
GET  /api/workshop/sessions/{id}/location-suggestions

All routes are curator-only.
"""
import json
import math
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.workshop import GuestToken, WorkshopParticipant
from app.models.foray_session import ForagingSession
from app.models.encounter import Encounter
from app.models.recorded_walk import RecordedWalk
from app.models.species import Species
from app.api.identity import Identity, get_identity

router = APIRouter(prefix="/api/workshop", tags=["workshop"])

_DEFAULT_EXPIRY_DAYS = 7
_MAX_EXPIRY_DAYS = 90


class ParticipantCreate(BaseModel):
    name:  str           = Field(..., min_length=1, max_length=200)
    notes: Optional[str] = None


class TokenMint(BaseModel):
    participant_id:      Optional[int] = None
    workshop_session_id: Optional[int] = None
    expires_days:        Optional[int] = Field(default=_DEFAULT_EXPIRY_DAYS, ge=1, le=_MAX_EXPIRY_DAYS)


class SessionCreate(BaseModel):
    name:             str           = Field(..., min_length=1, max_length=200)
    session_date:     Optional[str] = Field(default=None, max_length=10)  # YYYY-MM-DD
    recorded_walk_id: Optional[int] = None


class SessionUpdate(BaseModel):
    name:             Optional[str] = Field(default=None, min_length=1, max_length=200)
    session_date:     Optional[str] = Field(default=None, max_length=10)
    recorded_walk_id: Optional[int] = None


_HISTORY_SNIPPET_LEN = 160


def _require_curator(identity: Identity) -> None:
    if identity.is_guest:
        raise HTTPException(403, "Curator only")


@router.post("/participants/find-or-create", status_code=200)
async def find_or_create_participant(
    body:     ParticipantCreate,
    identity: Identity      = Depends(get_identity),
    db:       AsyncSession  = Depends(get_db),
):
    """Return existing participant by name (case-insensitive) or create a new one."""
    _require_curator(identity)
    name = body.name.strip()
    existing = await db.scalar(
        select(WorkshopParticipant)
        .where(func.lower(WorkshopParticipant.name) == name.lower())
        .where(WorkshopParticipant.id > 1)
    )
    if existing is not None:
        return {"id": existing.id, "name": existing.name, "notes": existing.notes, "created": False}
    p = WorkshopParticipant(name=name, notes=body.notes)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return {"id": p.id, "name": p.name, "notes": p.notes, "created": True}


@router.post("/participants", status_code=201)
async def create_participant(
    body:     ParticipantCreate,
    identity: Identity      = Depends(get_identity),
    db:       AsyncSession  = Depends(get_db),
):
    _require_curator(identity)
    p = WorkshopParticipant(name=body.name.strip(), notes=body.notes)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return {"id": p.id, "name": p.name, "notes": p.notes}


@router.post("/tokens", status_code=201)
async def mint_token(
    body:     TokenMint,
    identity: Identity     = Depends(get_identity),
    db:       AsyncSession = Depends(get_db),
):
    _require_curator(identity)
    if body.participant_id is not None:
        if body.participant_id < 2:
            raise HTTPException(422, "participant_id=1 is the curator tombstone — use null for a curator token")
        p = await db.get(WorkshopParticipant, body.participant_id)
        if p is None:
            raise HTTPException(422, f"participant_id {body.participant_id} does not exist")
    days    = min(body.expires_days or _DEFAULT_EXPIRY_DAYS, _MAX_EXPIRY_DAYS)
    expires = datetime.utcnow() + timedelta(days=days)
    tok = GuestToken(
        token=uuid.uuid4().hex,
        participant_id=body.participant_id,
        workshop_session_id=body.workshop_session_id,
        expires_at=expires,
        is_active=True,
    )
    db.add(tok)
    await db.commit()
    await db.refresh(tok)
    return {
        "id":                  tok.id,
        "token":               tok.token,
        "participant_id":      tok.participant_id,
        "workshop_session_id": tok.workshop_session_id,
        "expires_at":          tok.expires_at.isoformat(),
        "is_active":           tok.is_active,
    }


# ── Sessions (the named, dated occasion) ──────────────────────────────────────

@router.post("/sessions", status_code=201)
async def create_session(
    body:     SessionCreate,
    identity: Identity      = Depends(get_identity),
    db:       AsyncSession  = Depends(get_db),
):
    """Create a foraging_session — the named, dated occasion a token attaches to."""
    _require_curator(identity)
    s = ForagingSession(
        name=body.name.strip(),
        session_date=(body.session_date or None),
        recorded_walk_id=body.recorded_walk_id,
    )
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return {
        "id": s.id, "name": s.name,
        "session_date": s.session_date,
        "status": s.status,
        "recorded_walk_id": s.recorded_walk_id,
    }


@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: int,
    body:       SessionUpdate,
    identity:   Identity      = Depends(get_identity),
    db:         AsyncSession  = Depends(get_db),
):
    """Update session metadata — primarily to link a recorded walk post-foray."""
    _require_curator(identity)
    s = await db.get(ForagingSession, session_id)
    if s is None:
        raise HTTPException(404, "Session not found")
    if body.name             is not None:                    s.name             = body.name.strip()
    if body.session_date     is not None:                    s.session_date     = body.session_date or None
    if "recorded_walk_id"    in body.model_fields_set:       s.recorded_walk_id = body.recorded_walk_id
    s.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(s)
    return {
        "id": s.id, "name": s.name,
        "session_date": s.session_date,
        "status": s.status,
        "recorded_walk_id": s.recorded_walk_id,
    }


@router.get("/sessions")
async def list_sessions(
    identity: Identity     = Depends(get_identity),
    db:       AsyncSession = Depends(get_db),
):
    """List sessions with participant count (distinct token participants) and
    encounter count (encounters scoped to the session). Newest session_date first."""
    _require_curator(identity)

    # Distinct participants who hold a token for each session
    part_counts = (
        await db.execute(
            select(
                GuestToken.workshop_session_id,
                func.count(func.distinct(GuestToken.participant_id)).label("cnt"),
            )
            .where(GuestToken.workshop_session_id.isnot(None))
            .where(GuestToken.participant_id.isnot(None))
            .group_by(GuestToken.workshop_session_id)
        )
    ).all()
    part_map = {row.workshop_session_id: row.cnt for row in part_counts}

    # Encounters scoped to each session
    enc_counts = (
        await db.execute(
            select(
                Encounter.workshop_session_id,
                func.count(Encounter.id).label("cnt"),
            )
            .where(Encounter.workshop_session_id.isnot(None))
            .group_by(Encounter.workshop_session_id)
        )
    ).all()
    enc_map = {row.workshop_session_id: row.cnt for row in enc_counts}

    rows = (
        await db.execute(
            select(ForagingSession)
            .order_by(ForagingSession.session_date.desc().nullslast(),
                      ForagingSession.id.desc())
        )
    ).scalars().all()

    return [
        {
            "id":                s.id,
            "name":              s.name,
            "session_date":      s.session_date,
            "status":            s.status,
            "recorded_walk_id":  s.recorded_walk_id,
            "participant_count": part_map.get(s.id, 0),
            "encounter_count":   enc_map.get(s.id, 0),
        }
        for s in rows
    ]


# ── Location suggestions ─────────────────────────────────────────────────────

def _nearest_track_point(track_points: list, encounter_ms: int) -> Optional[dict]:
    """Return the track point with the smallest |ts - encounter_ms|, or None."""
    if not track_points:
        return None
    best = min(track_points, key=lambda p: abs(p["ts"] - encounter_ms))
    return best


@router.get("/sessions/{session_id}/location-suggestions")
async def location_suggestions(
    session_id: int,
    identity:   Identity     = Depends(get_identity),
    db:         AsyncSession = Depends(get_db),
):
    """
    For each location-less encounter in this session, find the temporally nearest
    point on the linked recorded walk track and return it as a suggestion.

    Never writes anything — caller confirms via PATCH /api/encounters/{id}/coordinates.
    Returns 400 if the session has no recorded_walk_id or the walk has no track points.

    Each suggestion carries delta_seconds (|encounter_time − track_point_time|) so the
    UI can flag high-uncertainty matches (e.g. > 5 min away on the track).
    """
    _require_curator(identity)
    s = await db.get(ForagingSession, session_id)
    if s is None:
        raise HTTPException(404, "Session not found")
    if not s.recorded_walk_id:
        raise HTTPException(400, "Session has no linked recorded walk — link one first")

    walk = await db.get(RecordedWalk, s.recorded_walk_id)
    if walk is None:
        raise HTTPException(404, f"Recorded walk {s.recorded_walk_id} not found")

    track_points = json.loads(walk.track_points_json or "[]")
    if not track_points:
        raise HTTPException(400, "Linked walk has no GPS track points")

    # Encounters in this session with no location
    enc_rows = (await db.execute(
        select(Encounter)
        .where(
            Encounter.workshop_session_id == session_id,
            Encounter.latitude.is_(None),
        )
        .order_by(Encounter.encounter_date)
    )).scalars().all()

    suggestions = []
    for enc in enc_rows:
        enc_ms = int(enc.encounter_date.timestamp() * 1000)
        nearest = _nearest_track_point(track_points, enc_ms)
        if nearest is None:
            continue
        delta_s = abs(nearest["ts"] - enc_ms) // 1000
        snippet = (enc.text_note or enc.transcript or "").strip()
        if len(snippet) > 120:
            snippet = snippet[:120].rstrip() + "…"
        suggestions.append({
            "encounter_id":    enc.id,
            "encounter_date":  enc.encounter_date.isoformat(),
            "suggested_lat":   nearest["lat"],
            "suggested_lng":   nearest["lng"],
            "track_point_ts":  nearest["ts"],
            "delta_seconds":   delta_s,
            "snippet":         snippet or None,
        })

    return {
        "session_id":   session_id,
        "walk_id":      s.recorded_walk_id,
        "walk_name":    walk.name,
        "suggestions":  suggestions,
        "total":        len(suggestions),
    }


# ── Participant history (curator-facing, read-only) ───────────────────────────

@router.get("/participants/{participant_id}/history")
async def participant_history(
    participant_id: int,
    identity: Identity     = Depends(get_identity),
    db:       AsyncSession = Depends(get_db),
):
    """Return a participant's accumulated encounters across ALL sessions,
    grouped by session and ordered by session_date desc. Read-only join —
    species names and session metadata are surfaced for the curator to review
    a returning participant's prior activity before issuing a fresh token."""
    _require_curator(identity)
    if participant_id < 2:
        raise HTTPException(422, "participant_id=1 is the curator tombstone")
    participant = await db.get(WorkshopParticipant, participant_id)
    if participant is None:
        raise HTTPException(404, f"participant_id {participant_id} does not exist")

    rows = (
        await db.execute(
            select(
                Encounter.id,
                Encounter.workshop_session_id,
                Encounter.encounter_date,
                Encounter.encounter_type,
                Encounter.text_note,
                Encounter.transcript,
                Encounter.species_id,
                ForagingSession.name.label("session_name"),
                ForagingSession.session_date.label("session_date"),
                Species.scientific_name.label("species_scientific"),
                Species.preferred_common_name.label("species_common"),
            )
            .select_from(Encounter)
            .outerjoin(ForagingSession, Encounter.workshop_session_id == ForagingSession.id)
            .outerjoin(Species, Encounter.species_id == Species.id)
            .where(Encounter.user_id == participant_id)
            .order_by(ForagingSession.session_date.desc().nullslast(),
                      Encounter.encounter_date.desc())
        )
    ).all()

    # Group into ordered session buckets (preserving the query's session ordering)
    groups: list = []
    index: dict = {}
    for r in rows:
        key = r.workshop_session_id
        bucket = index.get(key)
        if bucket is None:
            bucket = {
                "session_id":   r.workshop_session_id,
                "session_name": r.session_name,   # None when encounter has no session
                "session_date": r.session_date,
                "encounters":   [],
            }
            index[key] = bucket
            groups.append(bucket)
        snippet = (r.text_note or r.transcript or "").strip()
        if len(snippet) > _HISTORY_SNIPPET_LEN:
            snippet = snippet[:_HISTORY_SNIPPET_LEN].rstrip() + "…"
        bucket["encounters"].append({
            "encounter_id":   r.id,
            "encounter_date": r.encounter_date.isoformat() if r.encounter_date else None,
            "encounter_type": r.encounter_type,
            "species_id":     r.species_id,
            "species_name":   r.species_common or r.species_scientific,  # None if unlinked
            "snippet":        snippet or None,
        })

    return {
        "participant": {"id": participant.id, "name": participant.name},
        "total_encounters": len(rows),
        "sessions": groups,
    }


@router.get("/participants")
async def list_participants(
    identity: Identity     = Depends(get_identity),
    db:       AsyncSession = Depends(get_db),
):
    _require_curator(identity)
    now = datetime.utcnow()

    # Participants with encounter counts
    enc_counts = (
        await db.execute(
            select(Encounter.user_id, func.count(Encounter.id).label("cnt"))
            .where(Encounter.user_id > 1)
            .group_by(Encounter.user_id)
        )
    ).all()
    enc_map = {row.user_id: row.cnt for row in enc_counts}

    # Latest active token per participant
    active_tokens = (
        await db.execute(
            select(GuestToken.participant_id, func.max(GuestToken.expires_at).label("exp"))
            .where(GuestToken.is_active.is_(True), GuestToken.expires_at > now)
            .where(GuestToken.participant_id.isnot(None))
            .group_by(GuestToken.participant_id)
        )
    ).all()
    active_map = {row.participant_id: row.exp for row in active_tokens}

    # Any token (including expired) per participant for "expired" status
    any_token = (
        await db.execute(
            select(GuestToken.participant_id, func.max(GuestToken.id).label("latest_id"))
            .where(GuestToken.participant_id.isnot(None))
            .group_by(GuestToken.participant_id)
        )
    ).all()
    any_map = {row.participant_id for row in any_token}

    rows = (
        await db.execute(
            select(WorkshopParticipant)
            .where(WorkshopParticipant.id > 1)
            .order_by(WorkshopParticipant.id)
        )
    ).scalars().all()

    result = []
    for p in rows:
        if p.id in active_map:
            token_status = "active"
        elif p.id in any_map:
            token_status = "expired"
        else:
            token_status = "none"
        result.append({
            "id":            p.id,
            "name":          p.name,
            "notes":         p.notes,
            "created_at":    p.created_at.isoformat(),
            "encounter_count": enc_map.get(p.id, 0),
            "token_status":  token_status,
        })
    return result


@router.get("/tokens")
async def list_tokens(
    workshop_session_id: Optional[int] = None,
    participant_id:      Optional[int] = None,
    identity: Identity     = Depends(get_identity),
    db:       AsyncSession = Depends(get_db),
):
    _require_curator(identity)
    stmt = (
        select(GuestToken, WorkshopParticipant.name)
        .outerjoin(WorkshopParticipant, GuestToken.participant_id == WorkshopParticipant.id)
        .order_by(GuestToken.id)
    )
    if workshop_session_id is not None:
        stmt = stmt.where(GuestToken.workshop_session_id == workshop_session_id)
    if participant_id is not None:
        stmt = stmt.where(GuestToken.participant_id == participant_id)
    rows = (await db.execute(stmt)).all()
    return [
        {
            "id":                  t.id,
            "token":               t.token,
            "participant_id":      t.participant_id,
            "participant_name":    (pname if pname != "__reserved__" else None),
            "workshop_session_id": t.workshop_session_id,
            "expires_at":          t.expires_at.isoformat(),
            "is_active":           t.is_active,
            "created_at":          t.created_at.isoformat(),
        }
        for t, pname in rows
    ]


@router.post("/tokens/{token_id}/revoke", status_code=200)
async def revoke_token(
    token_id: int,
    identity: Identity     = Depends(get_identity),
    db:       AsyncSession = Depends(get_db),
):
    _require_curator(identity)
    tok = await db.get(GuestToken, token_id)
    if tok is None:
        raise HTTPException(404, "Token not found")
    tok.is_active = False
    await db.commit()
    return {"ok": True, "id": tok.id, "is_active": False}
