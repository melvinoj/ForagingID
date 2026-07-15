import asyncio
import shutil
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, BackgroundTasks, Depends, Query, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from datetime import datetime

from app.database import get_db
from app.models.observation import Observation, ObservationEdit
from app.models.species import Species
from app.services.species_link import set_observation_species
from app.models.processing import ProcessingLog
from app.config import settings
from app.services.write_lock import db_write_lock
from app.services.file_cleanup import delete_observation_file

router = APIRouter(prefix="/api/observations", tags=["observations"])

class ObservationOut(BaseModel):
    id: int
    file_path: str
    thumbnail_path: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    photo_taken_at: Optional[datetime]
    created_at: Optional[datetime]   # ingest timestamp — used for "Recently added" banding
    camera_make: Optional[str]
    camera_model: Optional[str]
    is_plant_likely: Optional[bool]
    plant_detect_confidence: Optional[float]
    prefilter_category: Optional[str] = None
    review_status: str
    review_label: Optional[str] = None
    processing_stage: str
    is_duplicate: bool
    # Identification fields
    identification_status: Optional[str] = None
    species_primary: Optional[str] = None
    species_suggested: Optional[str] = None   # best guess when below min threshold
    species_candidates_json: Optional[str] = None
    human_corrected: bool = False
    # Category
    obs_category: str = "plant"
    category_suggested: Optional[str] = None
    # Upload provenance
    upload_source: Optional[str] = None
    # ITIS taxonomy fields (joined from species table, may be None)
    itis_name_match: Optional[str] = None
    itis_accepted_name: Optional[str] = None
    itis_tsn: Optional[int] = None

    model_config = {"from_attributes": True}


class SpeciesCorrection(BaseModel):
    species_name: str = Field(..., min_length=1, max_length=200, description="Corrected species name")


class NotesUpdate(BaseModel):
    notes: str = Field(..., max_length=2000, description="Reviewer notes")


class CoordinateUpdate(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Decimal latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Decimal longitude")
    source: str = Field("manual", description="How GPS was set (manual / map-click / etc.)")
    force: bool = Field(False, description="Overwrite existing coordinates if True")


class CategoryUpdate(BaseModel):
    category: str = Field(..., pattern="^(plant|fungi|landscape)$",
                          description="Base category: plant | fungi | landscape")


class ObservationEditOut(BaseModel):
    id: int
    field_name: str
    old_value: Optional[str]
    new_value: Optional[str]
    edited_at: datetime
    edited_by: str

    model_config = {"from_attributes": True}


def _log_edit(
    session: AsyncSession,
    obs: Observation,
    field_name: str,
    old_value: Optional[str],
    new_value: Optional[str],
) -> None:
    """Write an immutable audit row to observation_edits (fire-and-forget)."""
    session.add(ObservationEdit(
        observation_id=obs.id,
        field_name=field_name,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        edited_by="human",
    ))


def _copy_to_confirmed(obs: Observation) -> None:
    """
    Copy the observation's original photo to photos/confirmed_plants/{species-slug}/.
    Destination is always inside the ForagingID project root so files are git-tracked.
    Originals are never moved or modified.
    Best-effort — failure is silent so it never blocks the review action.
    """
    try:
        from app.services.export import copy_single
        dest = copy_single(obs, settings.confirmed_plants_dir)
        if dest:
            obs.confirmed_copy_path = str(dest)
    except Exception:
        pass  # non-critical: export_confirmed.py can be re-run to catch any misses


@router.get("/confirmed-no-gps")
async def confirmed_no_gps(
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """
    List confirmed observations (approved / manually_verified + identified) that
    have no GPS coordinates. Used by the map's 'No Location' panel.

    Returns thumbnail_path, species_primary, photo_taken_at, review_status.
    """
    stmt = (
        select(
            Observation.id,
            Observation.thumbnail_path,
            Observation.species_primary,
            Observation.species_candidates_json,
            Observation.photo_taken_at,
            Observation.review_status,
            Observation.human_corrected,
        )
        .where(
            Observation.latitude.is_(None),
            Observation.review_status.in_(["approved", "manually_verified"]),
            Observation.identification_status == "identified",
            Observation.species_primary.is_not(None),
        )
        .order_by(Observation.id.desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()

    return [
        {
            "id": r.id,
            "thumbnail_path": r.thumbnail_path,
            "species_primary": r.species_primary,
            "photo_taken_at": r.photo_taken_at.isoformat() if r.photo_taken_at else None,
            "review_status": r.review_status,
            "human_corrected": r.human_corrected,
        }
        for r in rows
    ]


@router.get("/location-review")
async def location_review_queue(
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """
    Return observations without GPS that are approved or needs_review.
    Also returns the default map centre (latest obs with GPS).
    Used by the Location Review tab in the review UI.
    """
    # Deduplicate by file_path — keep the lowest id (first ingested) when the
    # same source file was imported more than once.
    from sqlalchemy import func as _func
    dedup_subq = (
        select(_func.min(Observation.id).label("min_id"))
        .where(Observation.latitude.is_(None))
        .where(Observation.review_status.in_(["approved", "needs_review", "manually_verified"]))
        .group_by(Observation.file_path)
        .subquery()
    )
    stmt = (
        select(
            Observation.id,
            Observation.thumbnail_path,
            Observation.file_path,
            Observation.species_primary,
            Observation.species_candidates_json,
            Observation.photo_taken_at,
            Observation.review_status,
            Observation.upload_source,
            Observation.human_corrected,
        )
        .where(Observation.id.in_(select(dedup_subq.c.min_id)))
        .order_by(Observation.photo_taken_at.desc().nullslast())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()

    # Fetch the default map centre from the most recent geotagged obs
    center_row = await db.execute(
        select(Observation.latitude, Observation.longitude)
        .where(Observation.latitude.is_not(None))
        .order_by(Observation.photo_taken_at.desc().nullslast())
        .limit(1)
    )
    center = center_row.first()
    default_center = {"lat": center.latitude, "lng": center.longitude} if center else None

    observations = []
    for r in rows:
        # Extract common name from candidates JSON
        common_name = None
        try:
            import json as _json
            cands = _json.loads(r.species_candidates_json or "[]")
            if cands and cands[0].get("common_names"):
                common_name = cands[0]["common_names"][0]
        except Exception:
            pass
        observations.append({
            "id": r.id,
            "thumbnail_path": r.thumbnail_path,
            "species_primary": r.species_primary,
            "common_name": common_name,
            "photo_taken_at": r.photo_taken_at.isoformat() if r.photo_taken_at else None,
            "review_status": r.review_status,
            "upload_source": r.upload_source,
            "human_corrected": r.human_corrected,
        })

    return {
        "observations": observations,
        "default_center": default_center,
        "total": len(observations),
    }


@router.get("", response_model=list[ObservationOut])
async def list_observations(
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    geotagged_only: bool = False,
    no_gps: bool = False,
    named_only: bool = False,
    unnamed_only: bool = False,
    review_status: Optional[str] = None,
    upload_source: Optional[str] = None,
    obs_category: Optional[str] = None,
    prefilter_category: Optional[str] = None,
    review_label: Optional[str] = None,
    q: Optional[str] = None,
    sort: str = "date_desc",
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(
            Observation,
            Species.itis_name_match,
            Species.itis_accepted_name,
            Species.itis_tsn,
        )
        .outerjoin(Species, Observation.species_id == Species.id)
    )
    if geotagged_only:
        stmt = stmt.where(Observation.latitude.is_not(None))
    # No-GPS filter — surfaces observations with no location data so they can be
    # bulk-decided before an internet-dependent session (offline-hardening Fix 3).
    if no_gps:
        stmt = stmt.where(Observation.latitude.is_(None))
    # Named / Unnamed filters key off whether any species name is assigned.
    # 'Named'   = species_primary (confirmed) OR species_suggested (below-threshold
    #             pipeline suggestion) is set. Together these are exhaustive: a photo
    #             either has some identification or it doesn't.
    # 'Unnamed' = both fields NULL — no identification of any kind.
    # Both checked together is contradictory and intentionally returns nothing.
    if named_only:
        stmt = stmt.where(
            (Observation.species_primary.is_not(None)) |
            (Observation.species_suggested.is_not(None))
        )
    if unnamed_only:
        stmt = stmt.where(
            Observation.species_primary.is_(None),
            Observation.species_suggested.is_(None),
        )
    if not review_status:
        # No explicit status filter — exclude rejected rows so "All" means all
        # active observations. Rejected rows are surfaced only via the explicit
        # "Manually rejected" Status filter (review_status="rejected").
        stmt = stmt.where(Observation.review_status != "rejected")
    if review_status:
        # "approved" is a superset that includes manually_verified so the list
        # matches the count shown in the review-queue badge (fix #13).
        if review_status == "approved":
            stmt = stmt.where(
                Observation.review_status.in_(["approved", "manually_verified"])
            )
        elif review_status == "needs_review":
            # Belt-and-suspenders: explicitly exclude approved/manually_verified so
            # observations that have been bulk-re-queued by trust tools (kingdom audit,
            # data trust send-to-review) but then re-approved never ghost back into
            # the queue. The direct == filter is correct but any ORM quirk or future
            # code path can't accidentally include them this way.
            stmt = stmt.where(
                Observation.review_status == "needs_review",
                Observation.review_status.notin_(["approved", "manually_verified", "rejected"]),
            )
        else:
            stmt = stmt.where(Observation.review_status == review_status)
    if upload_source:
        stmt = stmt.where(Observation.upload_source == upload_source)
    if obs_category:
        # "scene" maps to the stored value "landscape"
        cat = "landscape" if obs_category == "scene" else obs_category
        stmt = stmt.where(Observation.obs_category == cat)
    if prefilter_category:
        stmt = stmt.where(Observation.prefilter_category == prefilter_category)
    if review_label:
        stmt = stmt.where(Observation.review_label == review_label)
    # Free-text name search — case-insensitive substring across every name column:
    # the observation's own scientific + below-threshold suggested names, plus the
    # joined Species' ITIS-accepted scientific name and its English common-name list
    # (common_names is a JSON array stored as text, so a fragment matches inside it).
    # ilike follows the existing text-search convention (find.py, culinary.py); on
    # SQLite it compiles to lower(col) LIKE lower(term) → ASCII case-insensitive.
    # itis_name_match is intentionally excluded — it is a match-status enum
    # ("accepted"/"synonym"/"no_match"), not a name. Blank/whitespace q is a no-op.
    if q and q.strip():
        term = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Observation.species_primary.ilike(term),
                Observation.species_suggested.ilike(term),
                Species.itis_accepted_name.ilike(term),
                Species.common_names.ilike(term),
            )
        )
    # Server-side sort so ordering is global across pages, not just within the
    # current page. top_score is the normalised (0-1) confidence of the top candidate.
    sort_map = {
        "date_desc":  Observation.photo_taken_at.desc().nullslast(),
        "date_asc":   Observation.photo_taken_at.asc().nullslast(),
        "conf_desc":  Observation.top_score.desc().nullslast(),
        "conf_asc":   Observation.top_score.asc().nullslast(),
        "added_desc": Observation.id.desc(),   # id monotonically increases with ingest order
    }
    order = sort_map.get(sort, sort_map["date_desc"])
    stmt = stmt.order_by(order).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).all()
    out = []
    for row in rows:
        obs = row[0]
        d = ObservationOut.model_validate(obs).model_dump()
        d["itis_name_match"]    = row[1]
        d["itis_accepted_name"] = row[2]
        d["itis_tsn"]           = row[3]
        out.append(d)
    return out


@router.get("/stats")
async def observation_stats(db: AsyncSession = Depends(get_db)):
    # Canonical counts — single source of truth (app/services/observation_counts.py).
    # total/geotagged keep their existing meaning (active set); the full labelled
    # breakdown is exposed under "counts" so every consumer reads identical numbers.
    from app.services.observation_counts import observation_counts
    counts = await observation_counts(db)
    total     = counts["active"]
    geotagged = counts["geotagged_active"]
    duplicates = await db.scalar(
        select(func.count(Observation.id)).where(Observation.is_duplicate == True)
    )
    # Per-status counts — used by the review queue for accurate pagination
    by_status: dict = {}
    for s in ("pending", "needs_review", "approved", "manually_verified", "rejected"):
        by_status[s] = await db.scalar(
            select(func.count(Observation.id)).where(Observation.review_status == s)
        ) or 0
    phone_uploads = await db.scalar(
        select(func.count(Observation.id)).where(Observation.upload_source == "file_upload")
    ) or 0
    return {
        "total": total,
        "geotagged": geotagged,
        # Canonical labelled breakdown — use these to avoid count drift.
        "counts": counts,
        # Legacy flat fields kept for backwards compat
        "pending_review": by_status["pending"],
        "needs_review": by_status["needs_review"],
        "duplicates": duplicates,
        # New: per-status map for dynamic pagination
        "by_status": by_status,
        "phone_uploads": phone_uploads,
    }


@router.get("/label-counts")
async def label_counts(db: AsyncSession = Depends(get_db)):
    """
    Return {label: count} for all needs_review observations.
    Used by the review queue filter dropdown to show counts per label.
    """
    rows = (await db.execute(
        select(Observation.review_label, func.count(Observation.id))
        .where(Observation.review_status == "needs_review")
        .group_by(Observation.review_label)
    )).all()
    return {(label or ""): count for label, count in rows}


@router.get("/prefilter-categories")
async def list_prefilter_categories(
    review_status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """Return distinct non-null prefilter_category values present in the queue."""
    stmt = (
        select(Observation.prefilter_category)
        .where(Observation.prefilter_category.is_not(None))
        .distinct()
    )
    if review_status:
        if review_status == "needs_review":
            stmt = stmt.where(Observation.review_status == "needs_review")
        elif review_status == "approved":
            stmt = stmt.where(Observation.review_status.in_(["approved", "manually_verified"]))
        else:
            stmt = stmt.where(Observation.review_status == review_status)
    rows = (await db.execute(stmt)).scalars().all()
    return sorted(r for r in rows if r)


@router.get("/{observation_id}", response_model=ObservationOut)
async def get_observation(observation_id: int, db: AsyncSession = Depends(get_db)):
    obs = await db.get(Observation, observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")
    return obs


@router.patch("/{observation_id}/review")
async def update_review(
    observation_id: int,
    background_tasks: BackgroundTasks,
    status: str = Query(..., pattern="^(approved|rejected|needs_review|pending|manually_verified)$"),
    notes: Optional[str] = None,
    workshop_suitable: Optional[bool] = None,
    db: AsyncSession = Depends(get_db),
):
    obs = await db.get(Observation, observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")

    prev_status = obs.review_status

    if notes is not None and obs.reviewer_notes != notes:
        _log_edit(db, obs, "reviewer_notes", obs.reviewer_notes, notes)
        obs.reviewer_notes = notes

    if workshop_suitable is not None:
        obs.workshop_suitable = workshop_suitable

    confirmed_statuses = ("approved", "manually_verified")
    entering_confirmed = status in confirmed_statuses and prev_status not in confirmed_statuses

    # Auto-promotion of suggestions
    species_to_set = None
    update_species = False
    if status in confirmed_statuses and not obs.species_primary and obs.species_suggested:
        species_to_set = obs.species_suggested
        update_species = True
        obs.species_suggested = None
        obs.human_corrected = True

    from app.services.observation_service import update_observation_status
    await update_observation_status(
        session=db,
        obs=obs,
        review_status=status,
        species_name=species_to_set,
        update_species=update_species,
        edited_by="human"
    )

    await db.commit()

    if status == "rejected" and prev_status != "rejected":
        delete_observation_file(obs)

    # Trigger AI draft generation when an observation enters a confirmed state
    # for the first time and has a species name attached.
    if entering_confirmed and obs.species_primary:
        from app.services.enrichment import trigger_ai_drafts_for_species
        background_tasks.add_task(trigger_ai_drafts_for_species, obs.species_primary)

    return {"ok": True}


@router.patch("/{observation_id}/correct")
async def correct_species(
    observation_id: int,
    background_tasks: BackgroundTasks,
    body: SpeciesCorrection,
    db: AsyncSession = Depends(get_db),
):
    """
    Save a human species correction.

    - Overwrites species_primary with the corrected name.
    - Sets review_status = 'manually_verified'.
    - Sets human_corrected = True so the map and DB can distinguish
      human identifications from AI identifications.
    - Strips the moved-off (previous) name from species_candidates_json so the
      cache reflects current reality; all other candidates stay intact. The
      original-AI-guess audit trail is preserved separately in the
      SpeciesCandidate table.
    """
    obs = await db.get(Observation, observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")

    corrected = body.species_name.strip()

    from app.services.observation_service import update_observation_status
    await update_observation_status(
        session=db,
        obs=obs,
        review_status="manually_verified",
        species_name=corrected,
        update_species=True,
        edited_by="human"
    )

    async with db_write_lock():
        await db.commit()

    # Trigger AI draft generation for the corrected species name
    if corrected:
        from app.services.enrichment import trigger_ai_drafts_for_species
        background_tasks.add_task(trigger_ai_drafts_for_species, corrected)

    return {
        "ok": True,
        "id": observation_id,
        "species_primary": corrected,
        "review_status": "manually_verified",
        "human_corrected": True,
    }


class SuggestBody(BaseModel):
    species_suggested: Optional[str] = None


@router.patch("/{observation_id}/suggest")
async def set_species_suggested(
    observation_id: int,
    body: SuggestBody,
    db: AsyncSession = Depends(get_db),
):
    """
    Lightweight write: persist a reviewer's in-progress typed name as
    species_suggested without formally confirming the observation.

    Called automatically when the reviewer triggers a lookup (before selecting
    a result), so that 'Named only' filter and select mode agree with what the
    reviewer sees on-screen.  Does NOT change review_status, species_primary,
    or human_corrected.
    """
    obs = await db.get(Observation, observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")

    name = (body.species_suggested or "").strip() or None
    if obs.species_suggested != name:
        obs.species_suggested = name
        await db.commit()
    return {"ok": True, "species_suggested": name}


@router.patch("/{observation_id}/category")
async def set_category(
    observation_id: int,
    body: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Set the base category for an observation (plant / fungi / landscape).
    - Changing to 'landscape' clears species_primary and marks review_status
      as 'needs_review' so the reviewer can add a description.
    - Changing away from 'landscape' restores review_status to 'needs_review'
      so identification can proceed.
    """
    obs = await db.get(Observation, observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")

    old_cat = obs.obs_category or "plant"
    new_cat = body.category

    if old_cat != new_cat:
        _log_edit(db, obs, "obs_category", old_cat, new_cat)
        obs.obs_category = new_cat

        if new_cat == "landscape":
            # Landscape has no species — clear any assigned name and route to review
            if obs.species_primary:
                _log_edit(db, obs, "species_primary", obs.species_primary, None)
            await set_observation_species(db, obs, None)
            obs.species_suggested = None
            obs.review_status     = "needs_review"
            obs.review_label      = "manual_review"
            obs.identification_status = "identified"   # treated as "done" — no further ID
            obs.processing_stage  = "identified"
        else:
            # Switching from landscape → reset to allow identification
            if old_cat == "landscape":
                obs.identification_status = "pending_identification"
                obs.processing_stage      = "ingested"
                obs.review_status         = "pending"

        obs.reviewed_at = datetime.utcnow()
        await db.commit()

    return {
        "ok": True,
        "observation_id": observation_id,
        "obs_category": obs.obs_category,
        "review_status": obs.review_status,
    }


@router.patch("/{observation_id}/notes")
async def update_notes(
    observation_id: int,
    body: NotesUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update reviewer notes with full audit trail."""
    obs = await db.get(Observation, observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")

    new_notes = body.notes.strip()
    if obs.reviewer_notes != new_notes:
        _log_edit(db, obs, "reviewer_notes", obs.reviewer_notes, new_notes)
        obs.reviewer_notes = new_notes
        obs.reviewed_at = datetime.utcnow()
        await db.commit()

    return {"ok": True, "id": observation_id, "reviewer_notes": obs.reviewer_notes}


@router.patch("/{observation_id}/coordinates")
async def set_coordinates(
    observation_id: int,
    body: CoordinateUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually set GPS coordinates for an observation that has no location data.

    Rules:
      - By default (force=False) this endpoint refuses to overwrite existing
        non-NULL coordinates. Pass force=True to allow overwriting.
      - Writes an audit row to observation_edits for every change.
      - Does NOT automatically update review_status — coordinates are independent
        of the review workflow.

    After a confirmed observation gets GPS, the map pin appears immediately
    on the next GeoJSON reload (client should call loadFeatures()).
    """
    obs = await db.get(Observation, observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")

    if obs.latitude is not None and not body.force:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Observation already has GPS ({obs.latitude:.6f}, {obs.longitude:.6f}). "
                "Pass force=true to overwrite."
            ),
        )

    old_coords = (
        f"{obs.latitude},{obs.longitude}" if obs.latitude is not None else None
    )
    new_coords = f"{body.latitude},{body.longitude}|source={body.source}"

    _log_edit(db, obs, "coordinates", old_coords, new_coords)

    obs.latitude  = body.latitude
    obs.longitude = body.longitude
    await db.commit()

    return {
        "ok": True,
        "observation_id": observation_id,
        "latitude": obs.latitude,
        "longitude": obs.longitude,
        "review_status": obs.review_status,
        "identification_status": obs.identification_status,
        "species_primary": obs.species_primary,
        # Tells the client whether to add a pin to the map
        "map_eligible": (
            obs.review_status in ("approved", "manually_verified")
            and obs.identification_status == "identified"
            and obs.species_primary is not None
        ),
    }


@router.get("/{observation_id}/photo")
async def serve_observation_photo(
    observation_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Serve the original full-size photo for lightbox display."""
    obs = await db.get(Observation, observation_id)
    if not obs or not obs.file_path:
        raise HTTPException(status_code=404, detail="Observation not found")
    p = Path(obs.file_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Photo file not found on disk")
    # Determine media type from extension
    ext = p.suffix.lower()
    media_type = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                  ".heic": "image/heic", ".webp": "image/webp"}.get(ext, "image/jpeg")
    return FileResponse(str(p), media_type=media_type)


@router.get("/{observation_id}/edits", response_model=List[ObservationEditOut])
async def get_edit_history(
    observation_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Return the full human edit history for an observation (newest first)."""
    obs = await db.get(Observation, observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")

    result = await db.execute(
        select(ObservationEdit)
        .where(ObservationEdit.observation_id == observation_id)
        .order_by(ObservationEdit.edited_at.desc())
    )
    return result.scalars().all()


# ---------------------------------------------------------------------------
# POST /api/observations/{id}/reject-undo
# ---------------------------------------------------------------------------

@router.post("/{observation_id}/reject-undo")
async def reject_undo(
    observation_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Undo a reject-photo action within the 30-second window.
    Restores the file from /tmp/foragingid_undo/ and sets review_status = 'approved'.
    """
    obs = await db.get(Observation, observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")
    if obs.review_status != "rejected":
        raise HTTPException(status_code=409, detail="Observation is not in rejected state")

    # Cancel the scheduled hard-delete (shared module)
    from app.services.file_cleanup import _pending_deletes as _fc_pending, UNDO_DIR as _FC_UNDO
    task = _fc_pending.pop(observation_id, None)
    if task:
        task.cancel()

    # Restore files from undo dir — each temp file's name encodes which
    # column it came from (file_path or confirmed_copy_path).
    restored = False
    _FC_UNDO.mkdir(parents=True, exist_ok=True)
    prefix = f"{observation_id}_"
    for temp_path in _FC_UNDO.glob(f"{prefix}*"):
        name_after_id = temp_path.name[len(prefix):]
        if name_after_id.startswith("confirmed_copy_path_") and obs.confirmed_copy_path:
            dest = Path(obs.confirmed_copy_path)
        elif name_after_id.startswith("file_path_") and obs.file_path:
            dest = Path(obs.file_path)
        elif name_after_id.startswith("thumbnail_path_") and obs.thumbnail_path:
            dest = Path(obs.thumbnail_path)
            if not dest.is_absolute():
                dest = Path(__file__).resolve().parent.parent.parent / dest
        else:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(temp_path), str(dest))
        restored = True

    prev_status = obs.review_status
    obs.review_status = "approved"
    obs.reviewed_at = datetime.utcnow()
    _log_edit(db, obs, "review_status", prev_status, "approved")

    db.add(ProcessingLog(
        observation_id=obs.id,
        stage="manual_review",
        status="success",
        message=f"action=manual_rejected_from_map_undone triggered_by=user file_restored={restored}",
    ))
    await db.commit()

    return {
        "ok": True,
        "observation_id": observation_id,
        "restored": restored,
        "review_status": "approved",
    }


# ---------------------------------------------------------------------------
# DELETE /api/observations/{id}
# ---------------------------------------------------------------------------

class DeleteRequest(BaseModel):
    reason: Optional[str] = Field(None, max_length=500, description="Optional reason for deletion")


@router.delete("/{observation_id}")
async def delete_observation(
    observation_id: int,
    body: DeleteRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Permanently delete an observation record from the database.

    - Source photo in ~/Documents/Pictures is NEVER touched.
    - Confirmed copy inside ForagingID project folder is removed if it exists.
    - Full audit row written to processing_logs before deletion.
    - observation_edits rows are also deleted (cascade) — the final log entry
      serves as the permanent record.
    """
    obs = await db.get(Observation, observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")

    # Safety: never delete the source photo from the user's Pictures folder
    home_pics = Path("~/Documents/Pictures").expanduser()

    # Remove confirmed copy if it exists inside the ForagingID project
    confirmed_removed = False
    if obs.confirmed_copy_path:
        cp = Path(obs.confirmed_copy_path)
        # Only delete if it's inside the project folder (never ~/Documents/Pictures)
        if not str(cp.resolve()).startswith(str(home_pics)) and cp.exists():
            try:
                cp.unlink()
                confirmed_removed = True
            except Exception:
                pass  # non-critical

    # Also remove file_path if it's inside the project (uploaded/scanned copy)
    app_file_removed = False
    if obs.file_path:
        fp = Path(obs.file_path)
        project_root = Path(__file__).resolve().parent.parent.parent
        in_project = str(fp.resolve()).startswith(str(project_root))
        in_pics    = str(fp.resolve()).startswith(str(home_pics))
        if in_project and not in_pics and fp.exists():
            try:
                fp.unlink()
                app_file_removed = True
            except Exception:
                pass

    # Remove thumbnail if it exists
    thumb_removed = False
    if obs.thumbnail_path:
        tp = Path(obs.thumbnail_path)
        if not tp.is_absolute():
            tp = Path(__file__).resolve().parent.parent.parent / tp
        if tp.exists():
            try:
                tp.unlink()
                thumb_removed = True
            except Exception:
                pass

    # Record file_hash in deleted_hashes so the file is never re-ingested
    if obs.file_hash:
        from app.models.observation import DeletedHash
        existing_dh = await db.scalar(
            select(DeletedHash).where(DeletedHash.file_hash == obs.file_hash)
        )
        if not existing_dh:
            db.add(DeletedHash(
                file_hash=obs.file_hash,
                original_observation_id=observation_id,
            ))

    # Write permanent audit log entry before any DB deletion
    reason_note = f" | reason: {body.reason}" if body.reason else ""
    db.add(ProcessingLog(
        observation_id=None,  # obs row is about to vanish — store as orphan log
        stage="manual_delete",
        status="success",
        message=(
            f"action=observation_deleted observation_id={observation_id} "
            f"species={obs.species_primary or 'unknown'} "
            f"file={obs.file_path or 'none'} "
            f"confirmed_copy_removed={confirmed_removed} "
            f"app_file_removed={app_file_removed} "
            f"thumb_removed={thumb_removed} "
            f"triggered_by=user"
            f"{reason_note}"
        ),
    ))
    await db.flush()  # write log before deleting obs

    # Delete observation_edits and species_candidates (FK cascade may handle this,
    # but do it explicitly for safety)
    from app.models.species import SpeciesCandidate
    from sqlalchemy import delete as sql_delete

    await db.execute(sql_delete(ObservationEdit).where(ObservationEdit.observation_id == observation_id))
    await db.execute(sql_delete(SpeciesCandidate).where(SpeciesCandidate.observation_id == observation_id))

    # Capture the deleted obs's species link so we can orphan-GC its card after
    # removal — the delete path bypasses set_observation_species.
    _deleted_name = obs.species_primary
    _deleted_species_id = obs.species_id

    await db.delete(obs)
    await db.flush()  # obs row gone before the orphan check queries observations

    # If no surviving observation references the name (either column), mark its
    # card orphaned (never deletes; keyed on zero-observation only).
    from app.services.species_link import gc_species_card_if_orphaned
    await gc_species_card_if_orphaned(db, _deleted_name, _deleted_species_id)

    await db.commit()

    return {
        "ok": True,
        "deleted_id": observation_id,
        "confirmed_copy_removed": confirmed_removed,
        "app_file_removed": app_file_removed,
    }
