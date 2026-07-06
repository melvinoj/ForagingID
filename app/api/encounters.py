"""
encounters.py — Field encounter capture and retrieval.

Endpoints:
  POST   /api/encounters                              — create encounter (multipart/form-data, optional audio)
  GET    /api/encounters                              — list all encounters, newest first
  GET    /api/encounters/pending-transcripts          — count with audio but no transcript
  GET    /api/encounters/field-recipes                — encounters with field recipes (optional species_id filter)
  GET    /api/encounters/{id}                         — single encounter detail
  DELETE /api/encounters/{id}                         — delete encounter + remove audio file from disk
  POST   /api/encounters/{id}/transcribe              — Whisper transcription
  POST   /api/encounters/{id}/extract                 — Claude extraction (suggestions only)
  POST   /api/encounters/{id}/suggestions/{sid}/{act} — confirm/dismiss a suggestion
  PATCH  /api/encounters/{id}/field-recipe            — save/update a field recipe
  DELETE /api/encounters/{id}/field-recipe            — clear the field recipe
  POST   /api/encounters/reading-note                 — Whisper-transcribe audio and append to voice_library/goethean_sources.md
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.encounter import Encounter, EncounterPhoto
from app.models.species import CulinaryInfoHistory, Species, SpeciesAIDraft
from app.api.identity import Identity, get_identity

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/encounters", tags=["encounters"])

_AUDIO_EXTENSIONS = {
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/aac": ".m4a",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
}


def _encounters_dir() -> Path:
    from app.config import settings
    return settings.encounters_media_dir


def _audio_url(audio_path: Optional[str]) -> Optional[str]:
    if not audio_path:
        return None
    return f"/media/encounters/{Path(audio_path).name}"


def _parse_suggestions(raw: Optional[str]) -> list:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (ValueError, TypeError):
        return []


def _parse_field_recipe(raw: Optional[str]) -> Optional[dict]:
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else None
    except (ValueError, TypeError):
        return None


def _enc_to_dict(enc: Encounter, species_name: Optional[str]) -> dict:
    photos = []
    for p in (enc.photos or []):
        obs = p.observation
        thumb = None
        if obs and obs.thumbnail_path:
            thumb = "/thumbnails/" + obs.thumbnail_path.rsplit("/", 1)[-1]
        photos.append({
            "id": p.id,
            "observation_id": p.observation_id,
            "binding_method": p.binding_method,
            "binding_detail": p.binding_detail,
            "thumbnail": thumb,
        })
    return {
        "id":                  enc.id,
        "user_id":             enc.user_id,
        "species_id":          enc.species_id,
        "species_name":        species_name,
        "observation_id":      enc.observation_id,
        "list_id":             enc.list_id,
        "workshop_session_id": enc.workshop_session_id,
        "encounter_date":      enc.encounter_date.isoformat() if enc.encounter_date else None,
        "latitude":            enc.latitude,
        "longitude":           enc.longitude,
        "location_name":       enc.location_name,
        "audio_url":           _audio_url(enc.audio_path),
        "has_audio":           bool(enc.audio_path),
        "text_note":           enc.text_note,
        "sketch_path":         enc.sketch_path,
        "prompt_stage":        enc.prompt_stage,
        "prompt_response":     enc.prompt_response,
        "encounter_type":      enc.encounter_type,
        "transcript":          enc.transcript,
        "suggestions":         _parse_suggestions(enc.encounter_suggestions),
        "field_recipe":        _parse_field_recipe(enc.field_recipes),
        "research_visible":    enc.research_visible,
        "client_uuid":         enc.client_uuid,
        "expected_filename":   enc.expected_filename,
        "photos":              photos,
        "created_at":          enc.created_at.isoformat() if enc.created_at else None,
    }


async def _species_name_for(db: AsyncSession, species_id: Optional[int]) -> Optional[str]:
    if not species_id:
        return None
    return await db.scalar(select(Species.scientific_name).where(Species.id == species_id))


# ---------------------------------------------------------------------------
# Create encounter
# ---------------------------------------------------------------------------

@router.post("")
async def create_encounter(
    species_id:        Optional[int]  = Form(None),
    encounter_date:    Optional[str]  = Form(None),
    latitude:          Optional[float]= Form(None),
    longitude:         Optional[float]= Form(None),
    location_name:     Optional[str]  = Form(None),
    text_note:         Optional[str]  = Form(None),
    prompt_response:   Optional[str]  = Form(None),
    encounter_type:    str            = Form("field"),
    research_visible:  bool           = Form(True),
    client_uuid:       Optional[str]  = Form(None),
    expected_filename: Optional[str]  = Form(None),
    photo_observation_ids: Optional[str] = Form(None),
    audio: Optional[UploadFile]       = File(None),
    db: AsyncSession                  = Depends(get_db),
    identity: Identity                = Depends(get_identity),
):
    if identity.is_anonymous_guest:
        raise HTTPException(403, detail="Token required")

    # Idempotency (offline write queue, 13.10b): the client generates client_uuid at
    # capture time and replays the POST until it gets a 2xx. If flaky cellular dropped
    # the response to an earlier attempt that already committed, the replay arrives with
    # a client_uuid we've seen — return that existing row unchanged rather than inserting
    # a duplicate. Old clients send no client_uuid and skip this path entirely.
    client_uuid = (client_uuid or "").strip() or None
    if client_uuid:
        existing = await db.scalar(select(Encounter).where(Encounter.client_uuid == client_uuid))
        if existing is not None:
            return _enc_to_dict(existing, await _species_name_for(db, existing.species_id))

    # Validate species exists (only when species_id supplied)
    sp = None
    if species_id is not None:
        sp = await db.scalar(select(Species).where(Species.id == species_id))
        if not sp:
            raise HTTPException(404, detail="Species not found")

    # Parse date
    try:
        enc_date = datetime.fromisoformat(encounter_date) if encounter_date else datetime.utcnow()
    except ValueError:
        raise HTTPException(422, detail="encounter_date must be ISO 8601")

    # Save audio file if provided
    audio_path: Optional[str] = None
    if audio and audio.filename:
        content_type = (audio.content_type or "audio/webm").split(";")[0].strip()
        ext = _AUDIO_EXTENSIONS.get(content_type, ".webm")
        filename = f"{uuid.uuid4().hex}{ext}"
        dest = _encounters_dir() / filename
        dest.write_bytes(await audio.read())
        audio_path = str(dest)
        log.info("Saved encounter audio: %s", dest)

    # Stage 1 Goethean prompt ("What do you actually see?") — only Stage 1 is
    # captured in 11a.3; the other three stages are deferred. Tag the response
    # with prompt_stage="1" so later stages can be added without ambiguity.
    _prompt_response = (prompt_response or "").strip() or None

    enc = Encounter(
        user_id=identity.user_id,
        species_id=species_id,
        encounter_date=enc_date,
        latitude=latitude,
        longitude=longitude,
        location_name=location_name or None,
        audio_path=audio_path,
        text_note=text_note or None,
        prompt_stage="1" if _prompt_response else None,
        prompt_response=_prompt_response,
        encounter_type=(encounter_type if encounter_type in ("field", "season", "foraging_note") else "field"),
        research_visible=research_visible,
        workshop_session_id=identity.workshop_session_id,
        client_uuid=client_uuid,
        expected_filename=(expected_filename or "").strip() or None,
    )
    db.add(enc)
    try:
        await db.commit()
    except IntegrityError:
        # Race: a concurrent replay of the same client_uuid committed first and won the
        # unique index. Roll back and return whichever row landed — still idempotent.
        await db.rollback()
        existing = await db.scalar(select(Encounter).where(Encounter.client_uuid == client_uuid))
        if existing is not None:
            return _enc_to_dict(existing, await _species_name_for(db, existing.species_id))
        raise
    await db.refresh(enc)

    # Bind photos if observation IDs provided (online capture path)
    if photo_observation_ids:
        try:
            from app.models.observation import Observation
            ids_raw = json.loads(photo_observation_ids) if isinstance(photo_observation_ids, str) else photo_observation_ids
            for entry in (ids_raw if isinstance(ids_raw, list) else []):
                obs_id = entry.get("observation_id") if isinstance(entry, dict) else int(entry)
                method = entry.get("binding_method", "own_named") if isinstance(entry, dict) else "own_named"
                detail = entry.get("binding_detail") if isinstance(entry, dict) else None
                obs = await db.scalar(select(Observation).where(Observation.id == obs_id))
                if obs:
                    db.add(EncounterPhoto(
                        encounter_id=enc.id,
                        observation_id=obs_id,
                        binding_method=method,
                        binding_detail=detail,
                    ))
            await db.commit()
        except Exception as e:
            log.warning("Failed to bind photos to encounter %d: %s", enc.id, e)

    return _enc_to_dict(enc, sp.scientific_name if sp else None)


# ---------------------------------------------------------------------------
# Pending transcripts badge — MUST be before /{encounter_id} route
# ---------------------------------------------------------------------------

@router.get("/pending-transcripts")
async def pending_transcripts(db: AsyncSession = Depends(get_db)):
    """Count of encounters that have audio but no transcript yet."""
    count = await db.scalar(
        select(func.count()).select_from(Encounter).where(
            Encounter.audio_path.isnot(None),
            Encounter.transcript.is_(None),
        )
    )
    return {"count": int(count or 0)}


# ---------------------------------------------------------------------------
# Field recipes index — MUST be before /{encounter_id} route
# ---------------------------------------------------------------------------

@router.get("/field-recipes")
async def list_field_recipes(
    species_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    """Return encounters that have a field_recipe containing the given species_id.
    If species_id is omitted, returns all encounters with any field_recipe."""
    stmt = (
        select(Encounter, Species.scientific_name)
        .outerjoin(Species, Encounter.species_id == Species.id)
        .where(Encounter.field_recipes.isnot(None))
        .order_by(Encounter.encounter_date.desc())
    )
    rows = await db.execute(stmt)
    results = []
    for enc, sp_name in rows.all():
        fr = _parse_field_recipe(enc.field_recipes)
        if fr is None:
            continue
        if species_id is not None:
            ings = fr.get("ingredients") or []
            if not any(ing.get("species_id") == species_id for ing in ings):
                continue
        results.append(_enc_to_dict(enc, sp_name))
    return {"encounters": results}


# ---------------------------------------------------------------------------
# List encounters
# ---------------------------------------------------------------------------

@router.get("")
async def list_encounters(
    species_id: Optional[int] = None,
    date_from:  Optional[str] = None,
    date_to:    Optional[str] = None,
    user_id:    Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """List encounters, newest first. Optional filters:
      - species_id : only this species
      - date_from  : ISO date/datetime — encounters on/after this instant
      - date_to    : ISO date/datetime — encounters on/before this instant
      - user_id    : curator-only — view a specific participant's encounters
    Guest scoping: anonymous guests get []; participant tokens see only their own.
    """
    if identity.is_anonymous_guest:
        return {"encounters": []}

    stmt = (
        select(Encounter, Species.scientific_name)
        .outerjoin(Species, Encounter.species_id == Species.id)
    )
    if identity.is_guest:
        stmt = stmt.where(Encounter.user_id == identity.user_id)
    elif user_id is not None:
        stmt = stmt.where(Encounter.user_id == user_id)
    if species_id is not None:
        stmt = stmt.where(Encounter.species_id == species_id)
    if date_from:
        try:
            stmt = stmt.where(Encounter.encounter_date >= datetime.fromisoformat(date_from))
        except ValueError:
            raise HTTPException(422, detail="date_from must be ISO 8601")
    if date_to:
        try:
            stmt = stmt.where(Encounter.encounter_date <= datetime.fromisoformat(date_to))
        except ValueError:
            raise HTTPException(422, detail="date_to must be ISO 8601")

    rows = await db.execute(stmt.order_by(Encounter.encounter_date.desc()))
    return {
        "encounters": [
            _enc_to_dict(enc, sp_name)
            for enc, sp_name in rows.all()
        ]
    }


# ---------------------------------------------------------------------------
# Photo binding: candidates + manual bind
# ---------------------------------------------------------------------------

@router.get("/{encounter_id}/photo-candidates")
async def photo_candidates(
    encounter_id: int,
    radius_m: int = 20,
    window_s: int = 300,
    db: AsyncSession = Depends(get_db),
):
    """Find nearby observations as photo-binding candidates."""
    enc = await db.get(Encounter, encounter_id)
    if not enc:
        raise HTTPException(404, "Encounter not found")
    if enc.latitude is None or enc.longitude is None:
        return {"candidates": []}

    from app.services.photo_binding import _haversine_m
    import math

    obs_time = enc.encounter_date
    window = timedelta(seconds=window_s)
    lat_delta = radius_m / 111320
    lon_delta = radius_m / (111320 * math.cos(math.radians(enc.latitude)))

    from app.models.observation import Observation
    obs_rows = (await db.execute(
        select(Observation).where(
            Observation.latitude.isnot(None),
            Observation.photo_taken_at.isnot(None),
            Observation.photo_taken_at.between(obs_time - window, obs_time + window),
            Observation.latitude.between(enc.latitude - lat_delta, enc.latitude + lat_delta),
            Observation.longitude.between(enc.longitude - lon_delta, enc.longitude + lon_delta),
        )
    )).scalars().all()

    already_bound = set(p.observation_id for p in (enc.photos or []))

    candidates = []
    for obs in obs_rows:
        if obs.id in already_bound:
            continue
        dist = _haversine_m(enc.latitude, enc.longitude, obs.latitude, obs.longitude)
        if dist <= radius_m:
            dt = abs((obs.photo_taken_at - obs_time).total_seconds())
            thumb = None
            if obs.thumbnail_path:
                thumb = "/thumbnails/" + obs.thumbnail_path.rsplit("/", 1)[-1]
            candidates.append({
                "observation_id": obs.id,
                "thumbnail": thumb,
                "distance_m": round(dist, 1),
                "time_delta_s": round(dt),
                "photo_taken_at": obs.photo_taken_at.isoformat() if obs.photo_taken_at else None,
            })

    candidates.sort(key=lambda c: (c["time_delta_s"], c["distance_m"]))
    return {"candidates": candidates}


class PhotoBindRequest(BaseModel):
    observation_id: int
    binding_method: str = "manual"


@router.post("/{encounter_id}/bind-photo")
async def bind_photo(
    encounter_id: int,
    body: PhotoBindRequest,
    db: AsyncSession = Depends(get_db),
):
    """Manually bind a photo to an encounter."""
    enc = await db.get(Encounter, encounter_id)
    if not enc:
        raise HTTPException(404, "Encounter not found")

    from app.models.observation import Observation
    obs = await db.get(Observation, body.observation_id)
    if not obs:
        raise HTTPException(404, "Observation not found")

    existing = await db.scalar(
        select(EncounterPhoto.id).where(
            EncounterPhoto.encounter_id == encounter_id,
            EncounterPhoto.observation_id == body.observation_id,
        )
    )
    if existing:
        return {"ok": True, "already_bound": True}

    db.add(EncounterPhoto(
        encounter_id=encounter_id,
        observation_id=body.observation_id,
        binding_method=body.binding_method,
    ))
    await db.commit()
    return {"ok": True, "already_bound": False}


@router.post("/backfill-photo-bindings")
async def backfill_photo_bindings():
    """Run filename + proximity resolvers over all GPS-tagged observations."""
    from app.services.photo_binding import backfill_bindings
    stats = await backfill_bindings()
    return {"ok": True, **stats}


# ---------------------------------------------------------------------------
# Get single encounter
# ---------------------------------------------------------------------------

@router.get("/{encounter_id}")
async def get_encounter(encounter_id: int, db: AsyncSession = Depends(get_db)):
    row = await db.execute(
        select(Encounter, Species.scientific_name)
        .outerjoin(Species, Encounter.species_id == Species.id)
        .where(Encounter.id == encounter_id)
    )
    result = row.one_or_none()
    if not result:
        raise HTTPException(404, detail="Encounter not found")
    enc, sp_name = result
    return _enc_to_dict(enc, sp_name)


# ---------------------------------------------------------------------------
# Set encounter coordinates — curator map-pin to resolve a location-pending capture
# ---------------------------------------------------------------------------

class EncounterCoordinates(BaseModel):
    latitude:  float = Field(..., ge=-90.0,  le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    force:     bool  = Field(False, description="Overwrite an existing location if True")


@router.patch("/{encounter_id}/coordinates")
async def set_encounter_coordinates(
    encounter_id: int,
    body: EncounterCoordinates,
    db: AsyncSession = Depends(get_db),
):
    """Curator-only (PATCH is not in the guest write whitelist, so the guest
    middleware blocks tunnel guests). Pin a location onto an encounter — e.g. to
    resolve a field capture that was saved location-pending because GPS hadn't
    locked. Fill-when-empty by default; pass force=true to overwrite."""
    enc = await db.scalar(select(Encounter).where(Encounter.id == encounter_id))
    if not enc:
        raise HTTPException(404, detail="Encounter not found")
    if enc.latitude is not None and not body.force:
        raise HTTPException(
            409,
            detail=f"Encounter already has a location ({enc.latitude:.5f}, {enc.longitude:.5f}); "
                   "pass force=true to overwrite.",
        )
    enc.latitude  = body.latitude
    enc.longitude = body.longitude
    await db.commit()
    await db.refresh(enc)
    return _enc_to_dict(enc, await _species_name_for(db, enc.species_id))


# ---------------------------------------------------------------------------
# Delete encounter
# ---------------------------------------------------------------------------

@router.delete("/{encounter_id}")
async def delete_encounter(encounter_id: int, db: AsyncSession = Depends(get_db)):
    enc = await db.scalar(select(Encounter).where(Encounter.id == encounter_id))
    if not enc:
        raise HTTPException(404, detail="Encounter not found")

    if enc.audio_path:
        p = Path(enc.audio_path)
        if p.exists():
            p.unlink()
            log.info("Deleted encounter audio: %s", p)

    await db.delete(enc)
    await db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Transcription (Whisper) — deliberate laptop-side step, never automatic
# ---------------------------------------------------------------------------

@router.post("/{encounter_id}/transcribe")
async def transcribe_encounter(encounter_id: int, db: AsyncSession = Depends(get_db)):
    """Send the encounter's audio file to OpenAI Whisper and store the transcript.
    Estimated cost ~£0.006/minute. Returns the transcript text."""
    from app.config import settings
    from app.integrations.whisper import WhisperError, transcribe_file

    enc = await db.scalar(select(Encounter).where(Encounter.id == encounter_id))
    if not enc:
        raise HTTPException(404, detail="Encounter not found")
    if not enc.audio_path:
        raise HTTPException(400, detail="This encounter has no audio to transcribe")

    try:
        text = await transcribe_file(
            enc.audio_path,
            api_key=settings.openai_api_key,
            model=settings.whisper_model,
        )
    except WhisperError as e:
        # 503 for offline/connection cases so the UI can suggest retrying; 400 otherwise.
        raise HTTPException(503 if e.is_connection_error else 400, detail=str(e))

    enc.transcript = text or None

    # Auto-append the transcript to the species' running Foraging Notes field
    # (Phase 11a). Only for foraging_note encounters linked to a species. The
    # transcript is appended with a datestamp separator (e.g. "— 02 Jun 2026 —").
    # Idempotent: skip if this exact transcript text is already present, so a
    # re-transcribe never duplicates the entry.
    appended_to_species = False
    if text and enc.encounter_type == "foraging_note" and enc.species_id:
        sp = await db.scalar(select(Species).where(Species.id == enc.species_id))
        if sp is not None and text.strip() not in (sp.foraging_notes or ""):
            stamp = (enc.encounter_date or datetime.utcnow()).strftime("%d %b %Y")
            entry = f"— {stamp} —\n{text.strip()}"

            # Check whether a human has previously edited foraging_notes directly.
            # If so, route the transcript to the draft review queue instead of appending.
            from app.models.culinary import CulinaryInfo
            ci = await db.scalar(
                select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id)
            )
            human_edited_foraging = ci and await db.scalar(
                select(CulinaryInfoHistory.id)
                .where(CulinaryInfoHistory.culinary_info_id == ci.id)
                .where(CulinaryInfoHistory.field_name == "foraging_notes")
                .where(CulinaryInfoHistory.changed_by == "human")
            )
            if human_edited_foraging:
                db.add(SpeciesAIDraft(
                    species_id=sp.id,
                    field_name="foraging_notes",
                    draft_text=entry,
                    status="pending",
                    generated_at=datetime.utcnow(),
                    model="whisper",
                ))
                log.info(
                    "Transcript for %r routed to draft queue (foraging_notes has human history)",
                    sp.scientific_name,
                )
            else:
                sp.foraging_notes = (
                    f"{sp.foraging_notes.rstrip()}\n\n{entry}"
                    if (sp.foraging_notes or "").strip()
                    else entry
                )
                appended_to_species = True

    await db.commit()
    await db.refresh(enc)
    log.info("Transcribed encounter %d (%d chars)", encounter_id, len(text or ""))
    return {
        "id": enc.id,
        "transcript": enc.transcript,
        "appended_to_species_notes": appended_to_species,
    }


# ---------------------------------------------------------------------------
# Extraction (Claude) — surfaces SUGGESTIONS only; never auto-writes species cards
# ---------------------------------------------------------------------------

async def _species_index(db: AsyncSession) -> list:
    """Confirmed-species name index for reconciling species mentions."""
    rows = await db.execute(select(Species.id, Species.scientific_name, Species.common_names))
    index = []
    for sid, sci, common_raw in rows.all():
        common = []
        if common_raw:
            try:
                parsed = json.loads(common_raw)
                if isinstance(parsed, list):
                    common = [str(c) for c in parsed]
            except (ValueError, TypeError):
                pass
        index.append({"id": sid, "scientific_name": sci, "common_names": common})
    return index


@router.post("/{encounter_id}/extract")
async def extract_encounter(encounter_id: int, db: AsyncSession = Depends(get_db)):
    """Run a lightweight Claude extraction over the transcript. Stores the
    resulting suggestions (species / phenology / field_recipe / location) for the user
    to confirm or dismiss. Suggestions only — nothing is written to species cards."""
    from app.config import settings
    from app.integrations.encounter_extract import extract_suggestions

    enc = await db.scalar(select(Encounter).where(Encounter.id == encounter_id))
    if not enc:
        raise HTTPException(404, detail="Encounter not found")
    if not enc.transcript:
        raise HTTPException(400, detail="Transcribe this encounter before extracting")

    index = await _species_index(db)
    suggestions = await extract_suggestions(
        enc.transcript,
        api_key=settings.anthropic_api_key,
        species_index=index,
        model="claude-haiku-4-5-20251001",
    )

    enc.encounter_suggestions = json.dumps(suggestions) if suggestions else None
    await db.commit()
    await db.refresh(enc)
    log.info("Extracted %d suggestions for encounter %d", len(suggestions), encounter_id)
    return {"id": enc.id, "suggestions": suggestions}


# ---------------------------------------------------------------------------
# Confirm / dismiss a single suggestion
# ---------------------------------------------------------------------------

@router.post("/{encounter_id}/suggestions/{suggestion_id}/{action}")
async def resolve_suggestion(
    encounter_id: int,
    suggestion_id: str,
    action: str,
    db: AsyncSession = Depends(get_db),
):
    """action = 'confirm' (kept + logged) or 'dismiss' (discarded from the stored list).

    On confirm:
      - species      → sets encounter.species_id to the matched species (only when the
                       encounter has no species linked yet; never writes the species record)
      - location     → enriches location_name when it is currently empty
      - field_recipe → status marked confirmed, no further side-effect (user saves via PATCH)
      - phenology / foraging_note / safety_note → status marked confirmed, no side-effect
    """
    if action not in ("confirm", "dismiss"):
        raise HTTPException(422, detail="action must be 'confirm' or 'dismiss'")

    enc = await db.scalar(select(Encounter).where(Encounter.id == encounter_id))
    if not enc:
        raise HTTPException(404, detail="Encounter not found")

    suggestions = _parse_suggestions(enc.encounter_suggestions)
    target = next((s for s in suggestions if s.get("id") == suggestion_id), None)
    if target is None:
        raise HTTPException(404, detail="Suggestion not found")

    if action == "dismiss":
        # Dismissed suggestions are discarded.
        suggestions = [s for s in suggestions if s.get("id") != suggestion_id]
        log.info("Dismissed suggestion %s on encounter %d", suggestion_id, encounter_id)
    else:
        target["status"] = "confirmed"
        stype = target.get("type")
        # Species cue — link encounter to the matched species card (encounter.species_id
        # only; the species record itself is never touched per 11a.2).
        # Only sets when encounter has no species linked yet so it never silently
        # overwrites a species the user chose at capture.
        if stype == "species" and target.get("matched_species_id") and enc.species_id is None:
            enc.species_id = int(target["matched_species_id"])
        # Location cue — enriches location_name when currently empty.
        elif stype == "location" and not (enc.location_name or "").strip():
            enc.location_name = target.get("value")
        log.info(
            "Confirmed suggestion %s (type=%s) on encounter %d",
            suggestion_id, stype, encounter_id,
        )

    enc.encounter_suggestions = json.dumps(suggestions) if suggestions else None
    await db.commit()
    await db.refresh(enc)

    sp_name = None
    if enc.species_id:
        sp_name = await db.scalar(select(Species.scientific_name).where(Species.id == enc.species_id))
    return _enc_to_dict(enc, sp_name)


# ---------------------------------------------------------------------------
# Field Recipe — save/update/delete
# ---------------------------------------------------------------------------

class FieldRecipeBody(BaseModel):
    title: Optional[str] = None
    body: Optional[str] = None
    ingredients: Optional[list] = None  # list of {name, quantity, species_id}
    date: Optional[str] = None
    location_name: Optional[str] = None


@router.patch("/{encounter_id}/field-recipe")
async def save_field_recipe(
    encounter_id: int,
    recipe: FieldRecipeBody,
    db: AsyncSession = Depends(get_db),
):
    enc = await db.scalar(select(Encounter).where(Encounter.id == encounter_id))
    if not enc:
        raise HTTPException(404, detail="Encounter not found")
    data = recipe.model_dump(exclude_none=False)
    # Filter out None values but keep empty strings/lists
    clean = {k: v for k, v in data.items() if v is not None}
    enc.field_recipes = json.dumps(clean) if clean else None
    await db.commit()
    await db.refresh(enc)

    sp_name = None
    if enc.species_id:
        sp_name = await db.scalar(select(Species.scientific_name).where(Species.id == enc.species_id))
    return _enc_to_dict(enc, sp_name)


@router.delete("/{encounter_id}/field-recipe")
async def delete_field_recipe(encounter_id: int, db: AsyncSession = Depends(get_db)):
    enc = await db.scalar(select(Encounter).where(Encounter.id == encounter_id))
    if not enc:
        raise HTTPException(404, detail="Encounter not found")
    enc.field_recipes = None
    await db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Reading note — transcribe audio and append to voice_library/goethean_sources.md
# ---------------------------------------------------------------------------

_GOETHEAN_PATH = Path("./voice_library/goethean_sources.md")
_READING_NOTE_UPLOADS = Path("./uploads/reading_notes")


@router.post("/reading-note")
async def save_reading_note(
    source: str = Form(...),
    audio: UploadFile = File(...),
):
    """Accept audio + source name, transcribe via Whisper, append to goethean_sources.md."""
    from app.config import settings
    from app.integrations.whisper import WhisperError, transcribe_file

    source = source.strip()
    if not source:
        raise HTTPException(400, detail="Source name is required")

    # Save upload to a temp file so Whisper can read it by path
    _READING_NOTE_UPLOADS.mkdir(parents=True, exist_ok=True)
    suffix = Path(audio.filename or "recording.webm").suffix or ".webm"
    tmp_path = _READING_NOTE_UPLOADS / f"rn_{uuid.uuid4().hex}{suffix}"
    try:
        data = await audio.read()
        tmp_path.write_bytes(data)

        try:
            transcript = await transcribe_file(
                str(tmp_path),
                api_key=settings.openai_api_key,
                model=settings.whisper_model,
            )
        except WhisperError as e:
            raise HTTPException(503 if e.is_connection_error else 400, detail=str(e))
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    if not transcript:
        raise HTTPException(400, detail="Whisper returned an empty transcript")

    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    entry = f"\n---\ndate: {date_str}\nsource: {source}\n{transcript}\n"

    _GOETHEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _GOETHEAN_PATH.open("a", encoding="utf-8") as fh:
        fh.write(entry)

    log.info("Reading note appended to %s (%d chars)", _GOETHEAN_PATH, len(transcript))
    return {"ok": True, "transcript": transcript, "date": date_str}
