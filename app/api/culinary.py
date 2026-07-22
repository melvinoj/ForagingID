"""
Culinary enrichment API endpoints.

GET  /api/culinary/                     — paginated list of enriched species
GET  /api/culinary/{species_name}       — full profile (species + culinary_info + sources)
PATCH /api/culinary/{species_name}/field — manual correction with audit trail
GET  /api/species/{species_name}/observations  — confirmed observations for a species
GET  /api/species/{species_name}/profile       — combined profile for species pages
POST /api/drafts/backfill                      — backfill missing AI drafts for all eligible species
"""

import json
import uuid
from typing import Optional
from datetime import datetime

import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import logging
log = logging.getLogger(__name__)
from app.database import get_db, AsyncSessionLocal
from app.services.write_lock import db_write_lock
from app.models.culinary import CulinaryInfo
from app.models.notes import MapNote
from app.models.observation import Observation
from app.models.species import CulinaryInfoHistory, EnrichmentSource, Species, SpeciesAIDraft, SpeciesCandidate, SpeciesRecipe, SpeciesEdibilityCondition, SpeciesLookalike
from app.models.encounter import Encounter
from app.models.foray_session import SessionSpecies
from app.models.notification import NotificationDismissal
from app.models.personal_list import PersonalListSpecies
from app.models.sources import Source
from app.api.identity import Identity, get_identity

router = APIRouter(tags=["culinary"])

# ---------------------------------------------------------------------------
# In-memory enrichment job store
# Keyed by job_id (UUID string).  A single-user local app never needs more.
# ---------------------------------------------------------------------------
_enrichment_jobs: dict = {}   # job_id → job dict


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class FieldCorrection(BaseModel):
    field: str = Field(..., description="Name of the culinary_info field to update")
    value: Optional[str] = Field(None, description="New value (None to clear the field)")
    changed_by: str = Field("human", description="Who made the correction")
    mark_reviewed: bool = Field(
        False,
        description="When true (enrichment-review edit+approve), mark the species "
                    "edibility_verified so it leaves the enrichment review queue.",
    )


class TasteNotesEdit(BaseModel):
    value: Optional[str] = Field(None, description="New taste_notes value (None or empty to clear)")


# ---------------------------------------------------------------------------
# GET /api/species/   — all distinct species from confirmed observations
# ---------------------------------------------------------------------------

@router.get("/api/species/")
async def list_species(
    db: AsyncSession = Depends(get_db),
):
    """
    All distinct species found in confirmed (approved/manually_verified) observations.
    Returns enrichment data if available, otherwise just the name and observation count.
    """
    from sqlalchemy import func as sqlfunc

    # Get confirmed obs counts per species
    count_stmt = (
        select(
            Observation.species_primary,
            sqlfunc.count(Observation.id).label("obs_count"),
        )
        .where(Observation.species_primary.is_not(None))
        # Two-field filter, matching map.py's geojson gate exactly. The
        # review_status clause alone would count a row whose species_primary is
        # set while identification_status is not 'identified' — card-counted but
        # never map-eligible, the documented drift shape. No such row exists
        # today (this clause is a no-op on current data), so it is a guard
        # against the state, not a fix for it.
        .where(Observation.review_status.in_(["approved", "manually_verified"]))
        .where(Observation.identification_status == "identified")
        .group_by(Observation.species_primary)
        .order_by(Observation.species_primary)
    )
    count_rows = (await db.execute(count_stmt)).all()

    # Get enriched species lookup
    from sqlalchemy import func as sqlfunc
    enriched_stmt = (
        select(Species, CulinaryInfo)
        .join(CulinaryInfo, CulinaryInfo.species_id == Species.id, isouter=True)
    )
    enriched_rows = (await db.execute(enriched_stmt)).all()
    enriched = {sp.scientific_name: (sp, ci) for sp, ci in enriched_rows}

    # Condition + lookalike counts — bulk query for list view chips
    cond_counts_stmt = select(
        SpeciesEdibilityCondition.species_id,
        sqlfunc.count(SpeciesEdibilityCondition.id).label("n"),
    ).group_by(SpeciesEdibilityCondition.species_id)
    cond_counts = {r.species_id: r.n for r in (await db.execute(cond_counts_stmt)).all()}

    look_counts_stmt = select(
        SpeciesLookalike.species_id,
        sqlfunc.count(SpeciesLookalike.id).label("n"),
    ).group_by(SpeciesLookalike.species_id)
    look_counts = {r.species_id: r.n for r in (await db.execute(look_counts_stmt)).all()}

    from app.services.phenology import in_season_now
    _this_month = datetime.utcnow().month

    results = []
    for row in count_rows:
        name = row.species_primary
        sp, ci = enriched.get(name, (None, None))

        # Fix 24a: Bracken Safety in list view
        edible_parts = ci.edible_parts if ci else None
        if name == "Pteridium aquilinum":
            edible_parts = "DANGER: Not safe for human consumption. " + (edible_parts or "")

        # "In season now" flags — phenology-only (no photo fallback), so species
        # with no phenology data report has_phenology=False and can be excluded
        # when the species-page "In season now" filter is active (11a Prompt 3).
        _in_season, _has_pheno = in_season_now(
            flower_months=sp.flower_months if sp else None,
            fruit_months=sp.fruit_months if sp else None,
            leaf_months=sp.leaf_months if sp else None,
            peak_season=sp.peak_season if sp else None,
            ref_month=_this_month,
        )

        sp_id = sp.id if sp else None
        results.append({
            "id": sp_id,
            "scientific_name": name,
            "common_names": _parse_json_list(sp.common_names) if sp else [],
            "common_names_de": _parse_json_list(sp.common_names_de) if sp else [],
            "preferred_common_name": sp.preferred_common_name if sp else None,
            "family": sp.family if sp else None,
            "kingdom": sp.kingdom if sp else None,
            "edibility_status": sp.edibility_status if sp else None,
            "has_medicinal": bool(ci and (ci.medicinal_folklore or ci.medicinal_notes)) if ci else False,
            "enriched": sp is not None,
            "data_confidence": ci.data_confidence if ci else None,
            "edible_parts": edible_parts,
            "look_alike_warnings": ci.look_alike_warnings if ci else None,
            "observation_count": row.obs_count,
            "condition_count": cond_counts.get(sp_id, 0) if sp_id else 0,
            "lookalike_count": look_counts.get(sp_id, 0) if sp_id else 0,
            "in_season": _in_season,
            "has_phenology": _has_pheno,
        })

    return results


# ---------------------------------------------------------------------------
# POST /api/culinary/backfill-fungi-edibility  — one-off operational endpoint
# Must be defined before /api/culinary/{species_name:path} catch-all.
# ---------------------------------------------------------------------------

@router.post("/api/culinary/backfill-fungi-edibility")
async def backfill_fungi_edibility(
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """
    One-off backfill: run fungi edibility enrichment for all eligible species.

    Eligible species:
      - kingdom = 'Fungi', OR at least one observation with obs_category = 'fungi'
      - edibility_status is NULL, empty, or 'unknown'
      - edibility_verified is False

    Runs _maybe_enrich_fungi_edibility() for each species using the existing
    background_processes infrastructure for progress tracking.

    Returns a summary dict immediately (processing happens inline — the batch
    is expected to be small, typically <100 fungi species).

    Guards:
      - Never touches species that don't meet the fungi criteria
      - Never touches species with edibility_verified = True
      - Never touches species with a human-edited edibility_status history row
        (that guard is already enforced inside _maybe_enrich_fungi_edibility)
    """
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    from app.models.observation import Observation
    from app.services.background_processes import bp_start, bp_progress, bp_finish
    from app.services.enrichment import _maybe_enrich_fungi_edibility
    from app.models.culinary import CulinaryInfo

    log.info("[backfill-fungi-edibility] Starting backfill run")

    # ── Collect candidate species ────────────────────────────────────────────

    # Species with kingdom = 'Fungi'
    kingdom_stmt = (
        select(Species)
        .where(Species.kingdom.ilike("fungi"))
        .where(Species.edibility_verified.is_(False))
        .where(
            (Species.edibility_status.is_(None))
            | (Species.edibility_status == "")
            | (Species.edibility_status == "unknown")
        )
    )
    kingdom_rows = (await db.execute(kingdom_stmt)).scalars().all()
    kingdom_ids  = {sp.id for sp in kingdom_rows}

    # Species without kingdom set but with obs_category = 'fungi' observations
    obs_fungi_stmt = (
        select(Observation.species_primary)
        .where(Observation.obs_category == "fungi")
        .where(Observation.species_primary.is_not(None))
        .where(Observation.species_primary != "")
        .distinct()
    )
    obs_fungi_names = {r[0] for r in (await db.execute(obs_fungi_stmt)).all()}

    # Load those species rows that aren't already in kingdom_rows
    extra_rows: list = []
    if obs_fungi_names:
        extra_stmt = (
            select(Species)
            .where(Species.scientific_name.in_(obs_fungi_names))
            .where(Species.id.not_in(kingdom_ids) if kingdom_ids else True)
            .where(Species.edibility_verified.is_(False))
            .where(
                (Species.edibility_status.is_(None))
                | (Species.edibility_status == "")
                | (Species.edibility_status == "unknown")
            )
        )
        extra_rows = (await db.execute(extra_stmt)).scalars().all()

    all_candidates: list[Species] = list(kingdom_rows) + extra_rows
    total = len(all_candidates)
    log.info("[backfill-fungi-edibility] %d candidate species found", total)

    if total == 0:
        return {
            "ok": True,
            "message": "No eligible fungi species found for backfill",
            "processed": 0,
            "written": 0,
            "queued_review": 0,
            "failed": 0,
            "skipped": 0,
        }

    # ── Start background_processes tracking row ──────────────────────────────
    pid = await bp_start(
        process_type="fungi_edibility_backfill",
        progress_total=total,
        detail=f"Backfilling fungi edibility for {total} species",
    )

    # ── Process each species in its own short-lived session ──────────────────
    from app.database import AsyncSessionLocal

    counters = {"written": 0, "queued_review": 0, "failed": 0, "skipped": 0}

    for i, sp_stub in enumerate(all_candidates):
        sci_name = sp_stub.scientific_name
        try:
            async with AsyncSessionLocal() as sess:
                sp = await sess.scalar(
                    select(Species).where(Species.scientific_name == sci_name)
                )
                if sp is None:
                    counters["skipped"] += 1
                    continue

                # Double-check guards — state may have changed since the query above
                current_status = (sp.edibility_status or "").strip().lower()
                if sp.edibility_verified or (current_status and current_status != "unknown"):
                    counters["skipped"] += 1
                    continue

                # Ensure culinary_info row exists (required for history writes)
                ci = await sess.scalar(
                    select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id)
                )
                if ci is None:
                    ci = CulinaryInfo(species_id=sp.id)
                    sess.add(ci)
                    await sess.flush()

                # Snapshot edibility_status before the call so we can detect changes
                status_before = sp.edibility_status

                await _maybe_enrich_fungi_edibility(sess, sp, ci)

                # Determine outcome by inspecting changes
                status_after = sp.edibility_status

                # Check whether a new pending AI draft was added (requires_review path)
                from app.models.species import SpeciesAIDraft
                new_draft = await sess.scalar(
                    select(SpeciesAIDraft)
                    .where(SpeciesAIDraft.species_id == sp.id)
                    .where(SpeciesAIDraft.field_name == "edibility_status")
                    .where(SpeciesAIDraft.status == "pending")
                    .where(SpeciesAIDraft.model == "fao_fungi+mushroom_observer")
                )

                await sess.commit()

                if status_after and status_after != status_before:
                    counters["written"] += 1
                    log.info("[backfill] %r → edibility_status=%r (written)", sci_name, status_after)
                elif new_draft:
                    counters["queued_review"] += 1
                    log.info("[backfill] %r → queued for review", sci_name)
                else:
                    counters["skipped"] += 1

        except Exception as exc:
            log.warning("[backfill-fungi-edibility] Error processing %r: %s", sci_name, exc)
            counters["failed"] += 1

        await bp_progress(pid, i + 1, total, detail=sci_name)

    processed = total - counters["skipped"]
    summary_msg = (
        f"Backfill complete: {processed} processed, "
        f"{counters['written']} written, "
        f"{counters['queued_review']} queued for review, "
        f"{counters['failed']} failed, "
        f"{counters['skipped']} skipped (already set / not fungi)"
    )
    log.info("[backfill-fungi-edibility] %s", summary_msg)

    await bp_finish(
        pid,
        status="complete",
        current=total,
        total=total,
        error=None,
    )

    return {
        "ok":            True,
        "message":       summary_msg,
        "processed":     processed,
        "written":       counters["written"],
        "queued_review": counters["queued_review"],
        "failed":        counters["failed"],
        "skipped":       counters["skipped"],
        "process_id":    pid,
    }


# ---------------------------------------------------------------------------
# GET /api/culinary/enrichment-review  — must come before /api/culinary/{species:path}
# ---------------------------------------------------------------------------

@router.get("/api/culinary/ai-draft-review")
async def ai_draft_review_queue(
    db: AsyncSession = Depends(get_db),
):
    """
    Returns all pending AI drafts grouped by species, ready for the review queue.
    Each item includes species name, photo thumbnails, and all pending draft fields.
    """
    from collections import OrderedDict
    stmt = (
        select(SpeciesAIDraft, Species)
        .join(Species, Species.id == SpeciesAIDraft.species_id)
        .where(SpeciesAIDraft.status == "pending")
        .order_by(Species.scientific_name, SpeciesAIDraft.field_name)
    )
    rows = (await db.execute(stmt)).all()

    species_map: dict = OrderedDict()
    for draft, sp in rows:
        key = sp.scientific_name
        if key not in species_map:
            species_map[key] = {
                "scientific_name": sp.scientific_name,
                "common_names": _parse_json_list(sp.common_names),
                "family": sp.family,
                "drafts": [],
            }
        species_map[key]["drafts"].append({
            "id": draft.id,
            "field_name": draft.field_name,
            "draft_text": draft.draft_text,
            "generated_at": draft.generated_at.isoformat() if draft.generated_at else None,
            "model": draft.model,
        })

    result = []
    for sci_name, item in species_map.items():
        thumb_stmt = (
            select(Observation.thumbnail_path)
            .where(Observation.species_primary == sci_name)
            .where(Observation.review_status.in_(["approved", "manually_verified"]))
            .where(Observation.thumbnail_path.is_not(None))
            .limit(3)
        )
        thumbs = (await db.execute(thumb_stmt)).scalars().all()
        item["thumbnails"] = list(thumbs)
        result.append(item)

    return result


@router.get("/api/culinary/enrichment-review")
async def enrichment_review_queue(
    confidence_threshold: float = Query(0.6, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns species needing enrichment review, newest manual flags first:
      - manually flagged via "Send to review" (review_requested=1), OR
      - low enrichment confidence (<threshold) and enrichment not yet reviewed, OR
      - PFAF data absent (edible_parts is None) and enrichment not yet reviewed.

    Only species with at least one pending SpeciesAIDraft are returned —
    species that have been surfaced but have no drafts to review are excluded.
    """
    from sqlalchemy import and_, exists, or_

    pending_draft_exists = exists().where(
        (SpeciesAIDraft.species_id == Species.id) & (SpeciesAIDraft.status == "pending")
    )

    # Outer join so ITIS-flagged species appear even without a culinary_info row.
    stmt = (
        select(Species, CulinaryInfo)
        .outerjoin(CulinaryInfo, CulinaryInfo.species_id == Species.id)
        .where(pending_draft_exists)
        .where(
            or_(
                # Existing enrichment conditions (require culinary_info row)
                and_(
                    CulinaryInfo.id.isnot(None),
                    or_(
                        CulinaryInfo.review_requested.is_(True),       # (a) manual flag
                        and_(
                            CulinaryInfo.enrichment_reviewed.is_(False),  # (b)/(c): not yet signed off
                            or_(
                                CulinaryInfo.data_confidence < confidence_threshold,
                                CulinaryInfo.edible_parts.is_(None),
                            ),
                        ),
                    ),
                ),
                # ITIS name issues surface regardless of culinary_info
                Species.itis_name_match.in_(["synonym", "no_match"]),
            )
        )
        .order_by(
            CulinaryInfo.review_requested.desc().nullslast(),
            CulinaryInfo.review_requested_at.desc().nullslast(),
            CulinaryInfo.data_confidence.asc().nullsfirst(),
            Species.scientific_name,
        )
    )
    rows = (await db.execute(stmt)).all()

    result = []
    for sp, ci in rows:
        # Fetch up to 3 confirmed observation thumbnails for visual verification
        thumb_stmt = (
            select(Observation.thumbnail_path)
            .where(Observation.species_primary == sp.scientific_name)
            .where(Observation.review_status.in_(["approved", "manually_verified"]))
            .where(Observation.thumbnail_path.is_not(None))
            .limit(3)
        )
        thumbs = (await db.execute(thumb_stmt)).scalars().all()
        result.append({
            "scientific_name": sp.scientific_name,
            "family": sp.family,
            "edibility_status": sp.edibility_status,
            "data_confidence": ci.data_confidence if ci else None,
            "edible_parts": ci.edible_parts if ci else None,
            "look_alike_warnings": ci.look_alike_warnings if ci else None,
            "preparation_warnings": ci.preparation_warnings if ci else None,
            "pfaf_retrieved_at": ci.pfaf_retrieved_at.isoformat() if (ci and ci.pfaf_retrieved_at) else None,
            "wikidata_retrieved_at": ci.wikidata_retrieved_at.isoformat() if (ci and ci.wikidata_retrieved_at) else None,
            "ai_generated_fields": _parse_json_list(ci.ai_generated_fields_json if ci else None),
            "sources_json": _parse_json_list(ci.sources_json if ci else None),
            "thumbnails": list(thumbs),
            "review_requested": bool(ci.review_requested) if ci else False,
            "review_request_note": ci.review_request_note if ci else None,
            "review_requested_at": ci.review_requested_at.isoformat() if (ci and ci.review_requested_at) else None,
            "enrichment_reviewed": bool(ci.enrichment_reviewed) if ci else False,
            # ITIS name-validation fields
            "itis_name_match":    sp.itis_name_match,
            "itis_accepted_name": sp.itis_accepted_name,
            "itis_tsn":           sp.itis_tsn,
            "itis_checked_at":    sp.itis_checked_at.isoformat() if sp.itis_checked_at else None,
        })
    return result


# ---------------------------------------------------------------------------
# POST /api/culinary/transcribe-audio  — transient Whisper transcription
# Accepts an audio blob, transcribes via Whisper, returns text. No DB writes.
# Must be declared before any {species_name:path} routes.
# ---------------------------------------------------------------------------

@router.post("/api/culinary/transcribe-audio")
async def transcribe_culinary_audio(
    audio: UploadFile = File(...),
    identity: Identity = Depends(get_identity),
):
    """
    Transcribe an uploaded audio blob via OpenAI Whisper and return the text.
    Used by the taste-notes inline recorder to populate the edit textarea.
    No encounter is created; no DB row is written.
    """
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    from app.integrations.whisper import transcribe_file, WhisperError
    from app.config import settings

    content_type = (audio.content_type or "audio/webm").split(";")[0].strip()
    ext_map = {
        "audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a", "audio/x-m4a": ".m4a", "audio/wav": ".wav",
        "audio/wave": ".wav",
    }
    suffix = ext_map.get(content_type, ".webm")

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name
            tmp.write(await audio.read())

        text = await transcribe_file(tmp_path, settings.openai_api_key or "")
    except WhisperError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        log.error("[transcribe-audio] unexpected error: %s", e)
        raise HTTPException(status_code=500, detail="Transcription failed")
    finally:
        if tmp_path:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except Exception:
                pass

    return {"transcript": text}


# ---------------------------------------------------------------------------
# POST /api/culinary/{species_name}/request-review   — flag for enrichment review
# POST /api/culinary/{species_name}/clear-review     — clear a manual flag
# (defined before /{species_name:path}/history so the literal suffixes match
#  before the path catch-all; method is POST so there is no real conflict.)
# ---------------------------------------------------------------------------

class ReviewRequest(BaseModel):
    note: Optional[str] = Field(
        None, max_length=2000,
        description="Optional curator context for why this needs review",
    )


@router.post("/api/culinary/{species_name:path}/request-review")
async def request_enrichment_review(
    species_name: str,
    body: ReviewRequest,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """
    Flag a species for enrichment review (the single canonical write path).
    Surfaces it in the enrichment review queue regardless of data confidence.
    """
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    sp = await _get_species_or_404(db, species_name)
    ci = await db.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id))
    if not ci:
        # No enrichment row yet — create a stub so the flag has somewhere to live.
        ci = CulinaryInfo(species_id=sp.id)
        db.add(ci)
        await db.flush()

    ci.review_requested = True
    ci.review_requested_at = datetime.utcnow()
    ci.review_request_note = (body.note or "").strip() or None
    await db.commit()

    return {
        "ok": True,
        "scientific_name": sp.scientific_name,
        "review_requested": True,
        "review_request_note": ci.review_request_note,
        "review_url": "/review#enrichment",
    }


@router.post("/api/culinary/{species_name:path}/clear-review")
async def clear_enrichment_review(
    species_name: str,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """Clear a manual enrichment-review flag once the species has been reviewed."""
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    sp = await _get_species_or_404(db, species_name)
    ci = await db.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id))
    if ci:
        ci.review_requested = False
        ci.review_requested_at = None
        ci.review_request_note = None
        await db.commit()
    return {"ok": True, "scientific_name": sp.scientific_name, "review_requested": False}


# ---------------------------------------------------------------------------
# POST /api/culinary/{species_name}/approve-enrichment
# ---------------------------------------------------------------------------

@router.post("/api/culinary/{species_name:path}/approve-enrichment")
async def approve_enrichment(
    species_name: str,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """
    Mark enrichment text as curator-reviewed for a species.

    Sets culinary_info.enrichment_reviewed = True only. Does NOT touch
    edibility_status, edibility_verified, or any other species field.
    Edibility verdict is written exclusively via PATCH /api/edibility/status.
    """
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    sp = await _get_species_or_404(db, species_name)
    ci = await db.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id))
    if not ci:
        raise HTTPException(status_code=404, detail="No culinary data for this species")
    ci.enrichment_reviewed = True
    await db.commit()
    return {
        "ok": True,
        "scientific_name": sp.scientific_name,
        "enrichment_reviewed": True,
        "edibility_status": sp.edibility_status,
        "edibility_verified": sp.edibility_verified,
    }


# ---------------------------------------------------------------------------
# POST /api/culinary/{species_name}/mark-verified  [DISABLED]
# ---------------------------------------------------------------------------
# Removed from all call paths — edibility_verified is now written exclusively
# via PATCH /api/edibility/status (the Edibility tab).  Endpoint kept as a
# 410-Gone stub so stale clients get a clear error rather than a silent 404.

@router.post("/api/culinary/{species_name}/mark-verified")
async def mark_species_verified(
    species_name: str,
    identity: Identity = Depends(get_identity),
):
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    raise HTTPException(
        status_code=410,
        detail=(
            "mark-verified is retired. "
            "Use POST /api/culinary/{name}/approve-enrichment to mark enrichment text reviewed, "
            "or PATCH /api/edibility/status to set the edibility verdict."
        ),
    )


# ---------------------------------------------------------------------------
# POST /api/culinary/{species_name}/send-for-reid
# ---------------------------------------------------------------------------

@router.post("/api/culinary/{species_name:path}/send-for-reid")
async def send_species_for_reid(
    species_name: str,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """
    Send the most recent approved/manually_verified observation for this species
    back to the Species ID review queue.  Sets review_status='needs_review' and
    review_label='manual_review'.  Does NOT touch SpeciesAIDraft records.
    """
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    sp = await _get_species_or_404(db, species_name)
    obs = await db.scalar(
        select(Observation)
        .where(Observation.species_primary == sp.scientific_name)
        .where(Observation.review_status.in_(["approved", "manually_verified"]))
        .order_by(Observation.id.desc())
        .limit(1)
    )
    if not obs:
        raise HTTPException(404, f"No approved observation found for {species_name!r}")

    obs.review_status = "needs_review"
    obs.review_label  = "manual_review"
    await db.commit()

    return {
        "ok": True,
        "scientific_name": sp.scientific_name,
        "observation_id":  obs.id,
        "review_status":   obs.review_status,
        "review_label":    obs.review_label,
    }


# ---------------------------------------------------------------------------
# GET /api/culinary/{species_name}/history
# ---------------------------------------------------------------------------

@router.get("/api/culinary/{species_name:path}/history")
async def culinary_field_history(
    species_name: str,
    field: Optional[str] = Query(None, description="Filter by field name"),
    db: AsyncSession = Depends(get_db),
):
    """Edit history for all (or one) culinary_info field(s) for a species."""
    sp = await _get_species_or_404(db, species_name)
    ci = await db.scalar(
        select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id)
    )
    if not ci:
        return {"history": []}

    stmt = (
        select(CulinaryInfoHistory)
        .where(CulinaryInfoHistory.culinary_info_id == ci.id)
        .order_by(CulinaryInfoHistory.changed_at.desc())
    )
    if field:
        stmt = stmt.where(CulinaryInfoHistory.field_name == field)
    rows = (await db.execute(stmt)).scalars().all()

    return {
        "history": [
            {
                "field_name": r.field_name,
                "old_value": r.old_value,
                "new_value": r.new_value,
                "changed_at": r.changed_at.isoformat() if r.changed_at else None,
                "changed_by": r.changed_by,
            }
            for r in rows
        ]
    }


# ---------------------------------------------------------------------------
# POST /api/species/merge  — must come before /api/species/{name:path}
# ---------------------------------------------------------------------------

class MergeRequest(BaseModel):
    keep: str = Field(..., description="Scientific name of the species to keep")
    discard: str = Field(..., description="Scientific name of the species to discard (reassign obs first)")


class RenameRequest(BaseModel):
    new_name: str = Field(..., min_length=1, max_length=200,
                          description="New scientific name (Latin binomial)")
    new_common_name: Optional[str] = Field(None, max_length=200,
                                           description="Optional: replace primary common name")


@router.post("/api/species/rename")
async def rename_species(
    body: RenameRequest,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """
    DEPRECATED path — use POST /api/species/{old_name}/rename instead.
    Kept for backwards compatibility. Requires old_name in body.
    """
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    raise HTTPException(400, "Use POST /api/species/{old_name}/rename")


@router.post("/api/species/{species_name:path}/rename")
async def rename_species_by_name(
    species_name: str,
    body: RenameRequest,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """
    Rename a species (correct the scientific name) with full audit trail.

    Steps:
      1. Check new name doesn't already exist (prevent duplicates).
      2. Update species.scientific_name  →  new_name.
      3. Update all observation.species_primary  old_name → new_name.
      4. Optionally update common_names.
      5. Determine protected fields (fields with human edit history — never overwrite).
      6. Trigger re-enrichment: fill_empty_only=True, protected_fields from history.
      7. Write audit row to culinary_info_history (_rename_event field).

    If the new name returns no enrichment data from PFAF/Wikidata, the existing
    culinary data is left intact and `not_found=True` is returned so the UI can
    show: "No enrichment data found for this name — check spelling or try the
    Latin name."
    """
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    old_name = species_name.strip()
    new_name = body.new_name.strip()

    if old_name == new_name and not body.new_common_name:
        raise HTTPException(400, "New name is identical to current name — nothing to change")

    # Check for collision with an existing species row.
    # When the target name already exists, auto-merge silently rather than
    # surfacing an error — move observations, copy missing enrichment fields,
    # then proceed as a normal rename into the existing record.
    if old_name != new_name:
        conflict = await db.scalar(
            select(Species).where(Species.scientific_name == new_name)
        )
        if conflict:
            return await _auto_merge_into(
                db=db,
                source_name=old_name,
                target_sp=conflict,
                new_common_name=body.new_common_name,
            )

    from app.services.taxonomy import normalize_taxon_key

    # Get the species row (or create one if name only exists on observations)
    sp = await db.scalar(select(Species).where(Species.scientific_name == old_name))
    if sp is None:
        # Guard B: only mint a card if old_name is actually on ≥1 observation.
        # Renaming a name that exists on zero observations would create a card
        # with no backing observation (an instant phantom), so bail out with the
        # existing not_found shape instead.
        has_obs = await db.scalar(
            select(Observation.id).where(Observation.species_primary == old_name).limit(1)
        )
        if has_obs is None:
            return {
                "ok": True,
                "old_name": old_name,
                "new_name": new_name,
                "enrichment_status": "not_found",
                "not_found": True,
                "not_found_message": (
                    "No enrichment data found for this name — "
                    "check spelling or try the Latin name"
                ),
                "protected_fields": [],
            }

        # Species not in enrichment DB — create it under the new name directly
        sp = Species(scientific_name=new_name, name_key=normalize_taxon_key(new_name))
        if body.new_common_name:
            sp.common_names = json.dumps([body.new_common_name])
        db.add(sp)
        await db.flush()
        # Still update observations (old name may exist on obs without an enrichment row)
        from sqlalchemy import update as sqla_update
        await db.execute(
            sqla_update(Observation)
            .where(Observation.species_primary == old_name)
            .values(species_primary=new_name, species_id=sp.id)
        )
        await db.commit()
        return {
            "ok": True,
            "old_name": old_name,
            "new_name": new_name,
            "enrichment_status": "not_found",
            "not_found": True,
            "not_found_message": (
                "No enrichment data found for this name — "
                "check spelling or try the Latin name"
            ),
            "protected_fields": [],
        }

    # Apply rename
    if old_name != new_name:
        sp.scientific_name = new_name
        sp.name_key = normalize_taxon_key(new_name)

    if body.new_common_name:
        # Prepend user-supplied common name; keep existing names
        existing = []
        if sp.common_names:
            try:
                existing = json.loads(sp.common_names) or []
            except Exception:
                pass
        # Put new name first, remove duplicates
        merged = [body.new_common_name] + [n for n in existing if n != body.new_common_name]
        sp.common_names = json.dumps(merged)
    elif old_name != new_name:
        # Name changed but no user-provided common name → clear stale English common
        # names so Wikidata can populate fresh names for the new scientific name.
        # German names are always re-fetched regardless (Wikidata-only source).
        sp.common_names = None

    # Update all observations — keep the species_id FK pointed at the same row
    from sqlalchemy import update as sqla_update
    await db.execute(
        sqla_update(Observation)
        .where(Observation.species_primary == old_name)
        .values(species_primary=new_name, species_id=sp.id)
    )

    # Update map note species_tags that reference the old name
    if old_name != new_name:
        await _update_map_note_tags(db, old_name, new_name)

    # Enrichment cascade — only when scientific name changed.
    # handle_species_rename() resets all stale enrichment data, flags recipes,
    # cancels pending AI drafts, and writes the _rename_event audit row.
    # When only a common name changed, enrichment data is still valid — skip reset.
    name_changed = (old_name != new_name)
    if name_changed:
        from app.services.enrichment import handle_species_rename as _handle_rename
        await _handle_rename(db, sp, old_name, new_name)

    await db.commit()
    await db.refresh(sp)

    # Re-enrich under the new name.
    # After a scientific-name change: full re-fetch (fields were reset above).
    # After a common-name-only change: fill empty fields only.
    from app.services.enrichment import enrich_species as _enrich_sp
    enrichment_status = await _enrich_sp(
        session=db,
        species=sp,
        dry_run=False,
        re_enrich=True,
        fill_empty_only=(not name_changed),
        protected_fields=set(),   # reset already cleared all fields; nothing to protect
    )
    await db.commit()

    not_found = enrichment_status == "not_found"

    return {
        "ok": True,
        "old_name": old_name,
        "new_name": new_name,
        "enrichment_status": enrichment_status,
        "not_found": not_found,
        "not_found_message": (
            "No enrichment data found for this name — "
            "check spelling or try the Latin name"
        ) if not_found else None,
        "protected_fields": [],   # cleared on rename; re-enrichment fills fresh data
    }


# ---------------------------------------------------------------------------
# PATCH /api/species/{name}/preferred-common-name
# ---------------------------------------------------------------------------

class PreferredCommonNameRequest(BaseModel):
    preferred_common_name: Optional[str] = None  # None = clear / reset


@router.patch("/api/species/{species_name:path}/preferred-common-name")
async def set_preferred_common_name(
    species_name: str,
    body: PreferredCommonNameRequest,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """
    Set or clear the preferred common name for a species.
    This name is used as the primary sort key on the Species page.
    When cleared, sorting falls back to the first common name.
    """
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    sp = await db.scalar(select(Species).where(Species.scientific_name == species_name.strip()))
    if sp is None:
        raise HTTPException(404, f"Species not found: {species_name!r}")
    sp.preferred_common_name = body.preferred_common_name.strip() if body.preferred_common_name else None
    await db.commit()
    return {
        "ok": True,
        "scientific_name": sp.scientific_name,
        "preferred_common_name": sp.preferred_common_name,
    }


class CommonNamesEdit(BaseModel):
    preferred_common_name: Optional[str] = None
    common_names: Optional[list] = None
    common_names_de: Optional[list] = None


@router.patch("/api/species/{species_name:path}/common-names")
async def edit_common_names(
    species_name: str,
    body: CommonNamesEdit,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """
    Save human-edited common names (EN and/or DE) and preferred_common_name.
    Writes a culinary_info_history row with changed_by='human' for the lock badge.
    """
    if identity.is_guest:
        raise HTTPException(403, "Curator only")

    sp = await _get_species_or_404(db, species_name)

    old_en = sp.common_names
    old_de = sp.common_names_de
    old_pref = sp.preferred_common_name

    if body.common_names is not None:
        cleaned = [n.strip() for n in body.common_names if n and n.strip()]
        sp.common_names = json.dumps(cleaned) if cleaned else None
    if body.common_names_de is not None:
        cleaned = [n.strip() for n in body.common_names_de if n and n.strip()]
        sp.common_names_de = json.dumps(cleaned) if cleaned else None
    if body.preferred_common_name is not None:
        sp.preferred_common_name = body.preferred_common_name.strip() or None

    ci = await db.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id))
    if not ci:
        ci = CulinaryInfo(species_id=sp.id)
        db.add(ci)
        await db.flush()

    db.add(CulinaryInfoHistory(
        culinary_info_id=ci.id,
        field_name="common_names",
        old_value=json.dumps({"en": old_en, "de": old_de, "preferred": old_pref}),
        new_value=json.dumps({
            "en": sp.common_names,
            "de": sp.common_names_de,
            "preferred": sp.preferred_common_name,
        }),
        changed_at=datetime.utcnow(),
        changed_by="human",
    ))

    await db.commit()
    return {
        "ok": True,
        "common_names": _parse_json_list(sp.common_names),
        "common_names_de": _parse_json_list(sp.common_names_de),
        "preferred_common_name": sp.preferred_common_name,
    }


class ForagingNotesRequest(BaseModel):
    foraging_notes: Optional[str] = None


@router.patch("/api/species/{species_name:path}/foraging-notes")
async def set_foraging_notes(
    species_name: str,
    body: ForagingNotesRequest,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """
    Save the per-species running Foraging Notes field (editable text area on the
    species card). Stores to species.foraging_notes. Whisper transcripts from
    foraging_note encounters are appended to the same field by the encounters
    transcribe endpoint, so this is the canonical store for both typed notes and
    auto-appended transcripts. Empty string clears the field to NULL.
    """
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    sp = await db.scalar(select(Species).where(Species.scientific_name == species_name.strip()))
    if sp is None:
        raise HTTPException(404, f"Species not found: {species_name!r}")
    text = (body.foraging_notes or "").strip()
    sp.foraging_notes = text or None
    await db.commit()
    return {
        "ok": True,
        "scientific_name": sp.scientific_name,
        "foraging_notes": sp.foraging_notes,
    }


async def _update_map_note_tags(db: AsyncSession, old_name: str, new_name: str) -> int:
    """Replace old_name with new_name inside MapNote.species_tags JSON arrays."""
    result = await db.execute(
        select(MapNote).where(MapNote.species_tags.isnot(None))
    )
    notes = result.scalars().all()
    updated = 0
    for note in notes:
        try:
            tags = json.loads(note.species_tags)
        except Exception:
            continue
        if old_name in tags:
            note.species_tags = json.dumps([new_name if t == old_name else t for t in tags])
            updated += 1
    return updated


async def _auto_merge_into(
    db: AsyncSession,
    source_name: str,
    target_sp: Species,
    new_common_name: Optional[str],
) -> dict:
    """
    Silently merge `source_name` into `target_sp` when a rename would create
    a duplicate.  Called automatically by the rename endpoint — never shown to
    the user as an error.

    Steps:
      1. Move all observations from source → target.
      2. Reassign enrichment sources from source → target.
      3. Copy any culinary_info fields that are None on target but set on source.
      4. Mark the source species row as merged (never deleted).
      5. Optionally prepend new_common_name to target's common_names list.
      6. Trigger re-enrichment on the target (fill_empty_only).
    """
    from sqlalchemy import update as sqla_update
    from app.services.enrichment import enrich_species as _enrich_sp

    source_sp = await db.scalar(
        select(Species).where(Species.scientific_name == source_name)
    )

    # 1 — Move observations (repoint both the display cache and the FK)
    await db.execute(
        sqla_update(Observation)
        .where(Observation.species_primary == source_name)
        .values(species_primary=target_sp.scientific_name, species_id=target_sp.id)
    )

    if source_sp:
        # 2 — Reassign enrichment sources
        await db.execute(
            sqla_update(EnrichmentSource)
            .where(EnrichmentSource.species_id == source_sp.id)
            .values(species_id=target_sp.id)
        )

        # 2b — Migrate pending AI drafts (queue entries) to target species
        await db.execute(
            sqla_update(SpeciesAIDraft)
            .where(SpeciesAIDraft.species_id == source_sp.id)
            .values(species_id=target_sp.id)
        )

        # 2c — Migrate recipes to target species
        await db.execute(
            sqla_update(SpeciesRecipe)
            .where(SpeciesRecipe.species_id == source_sp.id)
            .values(species_id=target_sp.id)
        )

        # 3 — Copy missing culinary fields source → target
        source_ci = await db.scalar(
            select(CulinaryInfo).where(CulinaryInfo.species_id == source_sp.id)
        )
        target_ci = await db.scalar(
            select(CulinaryInfo).where(CulinaryInfo.species_id == target_sp.id)
        )
        if source_ci:
            if target_ci is None:
                # Target has no culinary row — just reassign the source row
                source_ci.species_id = target_sp.id
                target_ci = source_ci
            else:
                # Copy field-by-field: only fill None slots on target
                _CULINARY_COPYABLE = [
                    "edible_parts", "preparation_methods", "cooking_techniques",
                    "preservation_methods", "seasonal_peak", "harvest_stage",
                    "culinary_traditions", "look_alike_warnings", "preparation_warnings",
                    "flavour_profile", "pairing_ideas", "recipe_ideas",
                    "workshop_value_score", "traditional_uses", "cultural_notes",
                    "medicinal_folklore",
                ]
                for field in _CULINARY_COPYABLE:
                    if getattr(target_ci, field) is None:
                        src_val = getattr(source_ci, field, None)
                        if src_val is not None:
                            setattr(target_ci, field, src_val)
                # Keep the higher confidence score
                src_conf = source_ci.data_confidence or 0.0
                tgt_conf = target_ci.data_confidence or 0.0
                if src_conf > tgt_conf:
                    target_ci.data_confidence = src_conf

            # Write audit row
            if target_ci and target_ci.id:
                db.add(CulinaryInfoHistory(
                    culinary_info_id=target_ci.id,
                    field_name="_merge_event",
                    old_value=None,
                    new_value=(
                        f"Auto-merged from '{source_name}' (id={source_sp.id}) "
                        f"into '{target_sp.scientific_name}' via rename"
                    ),
                    changed_by="auto_merge",
                ))

        # 4 — Mark source as merged (never delete)
        source_sp.edibility_status = f"_merged_into:{target_sp.scientific_name}"

    # 5 — Optionally prepend common name
    if new_common_name:
        existing = []
        if target_sp.common_names:
            try:
                existing = json.loads(target_sp.common_names) or []
            except Exception:
                pass
        merged_names = [new_common_name] + [n for n in existing if n != new_common_name]
        target_sp.common_names = json.dumps(merged_names)

    # 5b — Update MapNote species_tags that reference the old name
    await _update_map_note_tags(db, source_name, target_sp.scientific_name)

    await db.commit()
    await db.refresh(target_sp)

    # 6 — Re-enrich the target species
    enrichment_status = await _enrich_sp(
        session=db,
        species=target_sp,
        dry_run=False,
        re_enrich=False,
        fill_empty_only=True,
    )
    await db.commit()

    not_found = enrichment_status == "not_found"
    return {
        "ok": True,
        "old_name": source_name,
        "new_name": target_sp.scientific_name,
        "enrichment_status": enrichment_status,
        "not_found": not_found,
        "not_found_message": None,
        "protected_fields": [],
        "auto_merged": True,
    }


@router.post("/api/species/merge")
async def merge_species(
    body: MergeRequest,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """
    Merge two species records. All child rows from `discard` are reparented to
    `keep`. The `discard` species row is soft-deleted (edibility_status marked
    _merged_into:keep — never physically deleted).

    Tables covered (14 top-level + culinary_info_history inline):
      observations, enrichment_sources, species_ai_drafts, species_recipes,
      culinary_info (+ culinary_info_history reparented before discard CI deleted),
      encounters, notification_dismissals, personal_list_species,
      session_species (reparented FIRST — CASCADE FK), sources,
      species_candidates, species_edibility_conditions, species_lookalikes,
      species_resources (string-keyed by species_name, not species_id).

    Unique-constraint conflicts → keeper row wins, discard row deleted.
    Verdict fields (edibility_status, ev_by, edibility_confidence) are NEVER
    copied from discard to keeper.
    """
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    from sqlalchemy import update as sqla_update, text as sqla_text

    keep_sp = await db.scalar(select(Species).where(Species.scientific_name == body.keep))
    if not keep_sp:
        raise HTTPException(status_code=404, detail=f"Species '{body.keep}' not found")

    discard_sp = await db.scalar(select(Species).where(Species.scientific_name == body.discard))
    if not discard_sp:
        raise HTTPException(status_code=404, detail=f"Species '{body.discard}' not found")

    if keep_sp.id == discard_sp.id:
        raise HTTPException(status_code=400, detail="Cannot merge a species with itself")

    kid = keep_sp.id
    did = discard_sp.id

    # ── 0. session_species — CASCADE FK: reparent BEFORE anything touches ────
    # the discard row, or these rows vanish silently on DELETE.
    # Dedupe: if same session already has keeper, drop the discard row instead.
    await db.execute(sqla_text("""
        DELETE FROM session_species
        WHERE species_id = :did
          AND EXISTS (
              SELECT 1 FROM session_species ss2
              WHERE ss2.species_id = :kid
                AND ss2.session_id = session_species.session_id
          )
    """), {"did": did, "kid": kid})
    await db.execute(
        sqla_update(SessionSpecies)
        .where(SessionSpecies.species_id == did)
        .values(species_id=kid)
    )

    # ── 1. observations ───────────────────────────────────────────────────────
    # Primary match on species_primary string (display cache); secondary sweep
    # catches any obs linked by FK only (species_primary may differ).
    await db.execute(
        sqla_update(Observation)
        .where(Observation.species_primary == body.discard)
        .values(species_primary=body.keep, species_id=kid)
    )
    await db.execute(
        sqla_update(Observation)
        .where(Observation.species_id == did)
        .values(species_id=kid)
    )

    # ── 2. enrichment_sources ─────────────────────────────────────────────────
    await db.execute(
        sqla_update(EnrichmentSource)
        .where(EnrichmentSource.species_id == did)
        .values(species_id=kid)
    )

    # ── 3. species_ai_drafts ──────────────────────────────────────────────────
    await db.execute(
        sqla_update(SpeciesAIDraft)
        .where(SpeciesAIDraft.species_id == did)
        .values(species_id=kid)
    )

    # ── 4. species_recipes ────────────────────────────────────────────────────
    await db.execute(
        sqla_update(SpeciesRecipe)
        .where(SpeciesRecipe.species_id == did)
        .values(species_id=kid)
    )

    # ── 5. culinary_info — field-level merge, verdict fields excluded ─────────
    _CULINARY_COPYABLE = [
        "edible_parts", "preparation_methods", "cooking_techniques",
        "preservation_methods", "seasonal_peak", "harvest_stage",
        "culinary_traditions", "look_alike_warnings", "preparation_warnings",
        "flavour_profile", "pairing_ideas", "recipe_ideas",
        "workshop_value_score", "traditional_uses", "cultural_notes",
        "medicinal_folklore", "taste_notes", "medicinal_notes", "recipe",
    ]
    source_ci = await db.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == did))
    target_ci = await db.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == kid))
    if source_ci:
        if target_ci is None:
            source_ci.species_id = kid
            target_ci = source_ci
        else:
            for _f in _CULINARY_COPYABLE:
                if getattr(target_ci, _f) is None:
                    src_val = getattr(source_ci, _f, None)
                    if src_val is not None:
                        setattr(target_ci, _f, src_val)
            src_conf = source_ci.data_confidence or 0.0
            tgt_conf = target_ci.data_confidence or 0.0
            if src_conf > tgt_conf:
                target_ci.data_confidence = src_conf
            # Reparent culinary_info_history before deleting the discard CI row
            # (culinary_info_history has no ON DELETE CASCADE — FK violation otherwise)
            await db.execute(
                sqla_update(CulinaryInfoHistory)
                .where(CulinaryInfoHistory.culinary_info_id == source_ci.id)
                .values(culinary_info_id=target_ci.id)
            )
            await db.delete(source_ci)

    # ── 6. encounters ─────────────────────────────────────────────────────────
    await db.execute(
        sqla_update(Encounter)
        .where(Encounter.species_id == did)
        .values(species_id=kid)
    )

    # ── 7. notification_dismissals — unique (user_id, species_id, season_key) ─
    await db.execute(sqla_text("""
        DELETE FROM notification_dismissals
        WHERE species_id = :did
          AND EXISTS (
              SELECT 1 FROM notification_dismissals nd2
              WHERE nd2.species_id = :kid
                AND nd2.user_id = notification_dismissals.user_id
                AND nd2.season_key = notification_dismissals.season_key
          )
    """), {"did": did, "kid": kid})
    await db.execute(
        sqla_update(NotificationDismissal)
        .where(NotificationDismissal.species_id == did)
        .values(species_id=kid)
    )

    # ── 8. personal_list_species — unique (list_id, species_id) ──────────────
    await db.execute(sqla_text("""
        DELETE FROM personal_list_species
        WHERE species_id = :did
          AND EXISTS (
              SELECT 1 FROM personal_list_species pls2
              WHERE pls2.species_id = :kid
                AND pls2.list_id = personal_list_species.list_id
          )
    """), {"did": did, "kid": kid})
    await db.execute(
        sqla_update(PersonalListSpecies)
        .where(PersonalListSpecies.species_id == did)
        .values(species_id=kid)
    )

    # ── 9. sources ────────────────────────────────────────────────────────────
    await db.execute(
        sqla_update(Source)
        .where(Source.species_id == did)
        .values(species_id=kid)
    )

    # ── 10. species_candidates ────────────────────────────────────────────────
    await db.execute(
        sqla_update(SpeciesCandidate)
        .where(SpeciesCandidate.species_id == did)
        .values(species_id=kid)
    )

    # ── 11. species_edibility_conditions ─────────────────────────────────────
    await db.execute(
        sqla_update(SpeciesEdibilityCondition)
        .where(SpeciesEdibilityCondition.species_id == did)
        .values(species_id=kid)
    )

    # ── 12. species_lookalikes (both FK columns) ──────────────────────────────
    await db.execute(
        sqla_update(SpeciesLookalike)
        .where(SpeciesLookalike.species_id == did)
        .values(species_id=kid)
    )
    await db.execute(
        sqla_update(SpeciesLookalike)
        .where(SpeciesLookalike.lookalike_species_id == did)
        .values(lookalike_species_id=kid)
    )
    # Remove self-references (species_id == lookalike_species_id) created by merge
    await db.execute(sqla_text(
        "DELETE FROM species_lookalikes WHERE species_id = lookalike_species_id"
    ))
    # Dedupe identical (species_id, lookalike_name) pairs — keep lowest id
    await db.execute(sqla_text("""
        DELETE FROM species_lookalikes
        WHERE id NOT IN (
            SELECT MIN(id) FROM species_lookalikes
            GROUP BY species_id, lookalike_name
        )
    """))

    # ── 13. species_resources — string-keyed by species_name (no species_id FK) ─
    # Dedupe first: drop discard rows whose URL already exists on keeper's name.
    await db.execute(sqla_text("""
        DELETE FROM species_resources
        WHERE species_name = :dn
          AND url IS NOT NULL
          AND url IN (SELECT url FROM species_resources WHERE species_name = :kn)
    """), {"dn": body.discard, "kn": body.keep})
    # Reparent any remaining discard rows to keeper's name.
    await db.execute(sqla_text(
        "UPDATE species_resources SET species_name = :kn WHERE species_name = :dn"
    ), {"dn": body.discard, "kn": body.keep})

    # ── 14. map note tags ─────────────────────────────────────────────────────
    await _update_map_note_tags(db, body.discard, body.keep)

    # ── audit log ─────────────────────────────────────────────────────────────
    ci_keep = await db.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == kid))
    if ci_keep:
        db.add(CulinaryInfoHistory(
            culinary_info_id=ci_keep.id,
            field_name="_merge_event",
            old_value=None,
            new_value=f"Merged '{body.discard}' (id={did}) into '{body.keep}' (id={kid})",
            changed_by="human_merge",
        ))

    # ── soft-delete discard — never physically delete ─────────────────────────
    discard_sp.edibility_status = f"_merged_into:{body.keep}"

    await db.commit()

    return {
        "ok": True,
        "merged_into": body.keep,
        "discarded": body.discard,
        "discard_id": did,
        "keep_id": kid,
    }


# ---------------------------------------------------------------------------
# GET /api/culinary/
# ---------------------------------------------------------------------------

@router.get("/api/culinary/")
async def list_enriched_species(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List all species that have culinary enrichment data."""
    stmt = (
        select(Species, CulinaryInfo)
        .join(CulinaryInfo, CulinaryInfo.species_id == Species.id, isouter=True)
        .where(CulinaryInfo.id.is_not(None))
        .order_by(Species.scientific_name)
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(stmt)).all()

    results = []
    for sp, ci in rows:
        res = {
            "scientific_name": sp.scientific_name,
            "common_names": _parse_json_list(sp.common_names),
            "common_names_de": _parse_json_list(sp.common_names_de),
            "family": sp.family,
            "edibility_status": sp.edibility_status,
            "data_confidence": ci.data_confidence,
            "edible_parts": ci.edible_parts,
            "workshop_value_score": ci.workshop_value_score,
        }
        # Fix 24a: Safety warning in list view
        if sp.scientific_name == "Pteridium aquilinum":
            res["edible_parts"] = "DANGER: Not safe for human consumption. " + (res["edible_parts"] or "")
        results.append(res)
    return results


# ---------------------------------------------------------------------------
# GET /api/culinary/{species_name}
# ---------------------------------------------------------------------------

@router.get("/api/culinary/{species_name:path}")
async def get_culinary_profile(
    species_name: str,
    db: AsyncSession = Depends(get_db),
):
    """Full enriched profile: species taxonomy + culinary info + raw sources."""
    sp = await _get_species_or_404(db, species_name)

    ci = await db.scalar(
        select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id)
    )

    sources_rows = (
        await db.execute(
            select(EnrichmentSource)
            .where(EnrichmentSource.species_id == sp.id)
            .order_by(EnrichmentSource.retrieved_at.desc())
        )
    ).scalars().all()

    ai_fields = _parse_json_list(ci.ai_generated_fields_json if ci else None)
    sources = [
        {
            "source_name": s.source_name,
            "source_url": s.source_url,
            "retrieved_at": s.retrieved_at.isoformat() if s.retrieved_at else None,
            "extraction_confidence": s.extraction_confidence,
            "parsing_method": s.parsing_method,
        }
        for s in sources_rows
    ]

    # Include recipe bank (current-season + all approved) — for walk panel collation
    _edib = (sp.edibility_status or "").lower()
    _edib_blocked = _edib in ("toxic", "inedible", "not_edible") or sp.edibility_status is None
    _recipe_rows: list = []
    if not _edib_blocked:
        _recipe_stmt = (
            select(SpeciesRecipe)
            .where(SpeciesRecipe.species_id == sp.id)
            .where(SpeciesRecipe.status == "approved")
            .order_by(SpeciesRecipe.is_preferred.desc(), SpeciesRecipe.created_at.desc())
        )
        _recipe_rows = (await db.execute(_recipe_stmt)).scalars().all()

    recipes_out = [
        {"id": r.id, "title": r.title, "body": r.body,
         "season": r.season, "is_preferred": r.is_preferred,
         "is_medicinal_prep": r.is_medicinal_prep}
        for r in _recipe_rows
    ]

    return {
        "species": {
            "id": sp.id,
            "scientific_name": sp.scientific_name,
            "common_names": _parse_json_list(sp.common_names),
            "common_names_de": _parse_json_list(sp.common_names_de),
            "family": sp.family,
            "genus": sp.genus,
            "edibility_status": sp.edibility_status,
            "edibility_verified": sp.edibility_verified,
        },
        "culinary": _culinary_to_dict(ci, sp.scientific_name) if ci else None,
        "ai_generated_fields": ai_fields,
        "enrichment_sources": sources,
        "recipes": recipes_out,
    }


# ---------------------------------------------------------------------------
# PATCH /api/culinary/{species_name}/field
# ---------------------------------------------------------------------------

@router.patch("/api/culinary/{species_name:path}/field")
async def correct_culinary_field(
    species_name: str,
    body: FieldCorrection,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """
    Manually correct a single culinary_info field.
    Writes an audit row to culinary_info_history before updating.
    """
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    sp = await _get_species_or_404(db, species_name)
    ci = await db.scalar(
        select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id)
    )
    if not ci:
        raise HTTPException(status_code=404, detail="No culinary data for this species")

    # Validate field name — only allow known CulinaryInfo columns
    allowed_fields = {
        "edible_parts", "flavour_profile", "preparation_methods", "cooking_techniques",
        "preservation_methods", "seasonal_peak", "harvest_stage", "pairing_ideas",
        "culinary_traditions", "recipe_ideas", "traditional_uses", "cultural_notes",
        "medicinal_folklore", "look_alike_warnings", "preparation_warnings",
        # Phase 8 fields
        "id_notes", "taste_notes", "medicinal_notes", "medicinal_clinical", "recipe",
    }
    if body.field not in allowed_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Field '{body.field}' is not editable. Allowed: {sorted(allowed_fields)}"
        )

    old_value = getattr(ci, body.field, None)
    new_value = body.value

    # Write audit record BEFORE updating
    history_row = CulinaryInfoHistory(
        culinary_info_id=ci.id,
        field_name=body.field,
        old_value=old_value,
        new_value=new_value,
        changed_at=datetime.utcnow(),
        # Provenance is server-derived, never client-supplied. The is_guest 403
        # guard above means anything reaching here is the curator → 'human'.
        # body.changed_by is now accepted-but-ignored.
        changed_by="human",
    )
    db.add(history_row)

    # Apply correction
    setattr(ci, body.field, new_value)

    # If the field was previously AI-generated, remove it from that list
    if ci.ai_generated_fields_json:
        try:
            ai_fields = json.loads(ci.ai_generated_fields_json)
            if body.field in ai_fields:
                ai_fields.remove(body.field)
                ci.ai_generated_fields_json = json.dumps(ai_fields)
        except Exception:
            pass

    # A4 — a human-saved correction is an approval: record the field in
    # ai_approved_fields_json (it was landing in limbo before — removed from
    # generated but never marked approved).
    if new_value:
        approved = _parse_json_list(ci.ai_approved_fields_json)
        if body.field not in approved:
            approved.append(body.field)
            ci.ai_approved_fields_json = json.dumps(approved)

    # A4 — edit+approve from the enrichment review queue: mark enrichment text
    # reviewed so the species leaves the queue (b)/(c) conditions.
    # Does NOT touch edibility_verified — that is written only via the Edibility tab.
    if body.mark_reviewed and ci:
        ci.enrichment_reviewed = True

    await db.commit()

    return {
        "ok": True,
        "species": species_name,
        "field": body.field,
        "old_value": old_value,
        "new_value": new_value,
        "approved": bool(new_value),
        "edibility_verified": sp.edibility_verified,
    }


# ---------------------------------------------------------------------------
# PATCH /api/culinary/{species_name}/taste-notes  — human edit of taste_notes
# changed_by is always 'human', set server-side — never from the client.
# Writing the history row is the human-lock that blocks future AI overwrites.
# ---------------------------------------------------------------------------

@router.patch("/api/culinary/{species_name:path}/taste-notes")
async def edit_taste_notes(
    species_name: str,
    body: TasteNotesEdit,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """
    Save a human-authored taste_notes value.
    Always writes a culinary_info_history row with changed_by='human', which
    is the retroactive lock checked by all AI enrichment paths before overwriting.
    """
    if identity.is_guest:
        raise HTTPException(403, "Curator only")

    sp = await _get_species_or_404(db, species_name)
    ci = await db.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id))
    if not ci:
        raise HTTPException(404, "No culinary data for this species")

    old_value = ci.taste_notes
    new_value = (body.value or "").strip() or None

    # Write the human-lock history row — server-side only, never client-supplied.
    db.add(CulinaryInfoHistory(
        culinary_info_id=ci.id,
        field_name="taste_notes",
        old_value=old_value,
        new_value=new_value,
        changed_at=datetime.utcnow(),
        changed_by="human",
    ))

    ci.taste_notes = new_value

    # Ensure the field appears on the species card as approved.
    approved = _parse_json_list(ci.ai_approved_fields_json)
    if "taste_notes" not in approved:
        approved.append("taste_notes")
        ci.ai_approved_fields_json = json.dumps(approved)

    await db.commit()
    return {"ok": True, "taste_notes": ci.taste_notes}


# ---------------------------------------------------------------------------
# GET /api/species/{species_name}/observations
# ---------------------------------------------------------------------------

@router.get("/api/species/{species_name:path}/observations")
async def species_observations(
    species_name: str,
    db: AsyncSession = Depends(get_db),
):
    """All confirmed observations for a species (thumbnails + coords)."""
    stmt = (
        select(
            Observation.id,
            Observation.thumbnail_path,
            Observation.latitude,
            Observation.longitude,
            Observation.photo_taken_at,
            Observation.review_status,
            Observation.human_corrected,
        )
        .where(Observation.species_primary == species_name)
        .where(Observation.review_status.in_(["approved", "manually_verified"]))
        .order_by(Observation.photo_taken_at.desc().nullslast())
    )
    rows = (await db.execute(stmt)).all()

    return [
        {
            "id": r.id,
            "thumbnail": r.thumbnail_path,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "taken_at": r.photo_taken_at.isoformat() if r.photo_taken_at else None,
            "review_status": r.review_status,
            "human_corrected": r.human_corrected,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# GET /api/species/{species_name}/profile
# ---------------------------------------------------------------------------

@router.get("/api/species/{species_name:path}/profile")
async def species_profile(
    species_name: str,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """
    Combined species profile for species.html page.
    Returns species taxonomy + culinary info + observation summary.

    Guest requests (identity.is_guest) get a server-shaped payload: unapproved
    AI drafts are never fetched, and enrichment fields are filtered through
    _guest_field_classification() — see that function's docstring. Curator
    requests are unchanged.
    """
    sp = await _get_species_or_404(db, species_name)

    ci = await db.scalar(
        select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id)
    )

    # Observation summary
    obs_stmt = (
        select(
            Observation.id,
            Observation.thumbnail_path,
            Observation.latitude,
            Observation.longitude,
            Observation.photo_taken_at,
            Observation.review_status,
            Observation.human_corrected,
        )
        .where(Observation.species_primary == species_name)
        .order_by(Observation.photo_taken_at.desc().nullslast())
        .limit(50)
    )
    obs_rows = (await db.execute(obs_stmt)).all()

    confirmed = [
        r for r in obs_rows
        if r.review_status in ("approved", "manually_verified")
    ]

    ai_fields = _parse_json_list(ci.ai_generated_fields_json if ci else None)

    # Pending AI drafts for this species — TIER 1: never fetched for a guest.
    # The query itself does not run, so unapproved draft_text never leaves
    # the DB layer for a guest request, let alone reaches the response.
    if identity.is_guest:
        pending_drafts = []
    else:
        pending_drafts_stmt = (
            select(SpeciesAIDraft)
            .where(SpeciesAIDraft.species_id == sp.id)
            .where(SpeciesAIDraft.status == "pending")
        )
        pending_drafts = (await db.execute(pending_drafts_stmt)).scalars().all()

    # Mushroom Observer link for fungi species
    mo_url = None
    if (sp.kingdom or "").lower() == "fungi":
        from app.integrations.mushroom_observer import species_url as _mo_url
        mo_url = _mo_url(sp.scientific_name)

    # Phase 12 follow-up — edibility lock + source notes:
    # 1. Was edibility_status set by a human? (determines whether "Flag for review" shows)
    # 2. FAO/MO source notes from the most recent fao_fungi+mushroom_observer history row
    _edibility_human_verified = False
    _fungi_edibility_notes = None
    _taste_notes_human_locked = False
    if ci:
        _history_stmt = (
            select(CulinaryInfoHistory)
            .where(CulinaryInfoHistory.culinary_info_id == ci.id)
            .where(CulinaryInfoHistory.field_name == "edibility_status")
            .order_by(CulinaryInfoHistory.changed_at.desc())
        )
        _history_rows = (await db.execute(_history_stmt)).scalars().all()
        for _hr in _history_rows:
            if _hr.changed_by == "human":
                _edibility_human_verified = True
                break
        for _hr in _history_rows:
            if _hr.changed_by == "fao_fungi+mushroom_observer" and _hr.notes:
                _fungi_edibility_notes = _hr.notes
                break
        # Check whether taste_notes has ever been human-edited (the retroactive lock).
        _tn_lock_row = await db.scalar(
            select(CulinaryInfoHistory.id)
            .where(CulinaryInfoHistory.culinary_info_id == ci.id)
            .where(CulinaryInfoHistory.field_name == "taste_notes")
            .where(CulinaryInfoHistory.changed_by == "human")
        )
        _taste_notes_human_locked = _tn_lock_row is not None
    # common_names human-lock — separate from ci because it writes to the same history table
    _common_names_human_locked = False
    if ci:
        _cn_lock_row = await db.scalar(
            select(CulinaryInfoHistory.id)
            .where(CulinaryInfoHistory.culinary_info_id == ci.id)
            .where(CulinaryInfoHistory.field_name == "common_names")
            .where(CulinaryInfoHistory.changed_by == "human")
        )
        _common_names_human_locked = _cn_lock_row is not None

    # Recipe bank — enforce edibility rules
    edib = (sp.edibility_status or "").lower()
    _edibility_blocked = edib in ("toxic", "inedible", "not_edible") or sp.edibility_status is None
    recipes_stmt = (
        select(SpeciesRecipe)
        .where(SpeciesRecipe.species_id == sp.id)
        .where(SpeciesRecipe.status == "approved")
        .order_by(SpeciesRecipe.is_preferred.desc(), SpeciesRecipe.created_at.desc())
    )
    _all_recipes = (await db.execute(recipes_stmt)).scalars().all() if not _edibility_blocked else []
    recipes_list = [
        {
            "id":                r.id,
            "title":             r.title,
            "body":              r.body,
            "season":            r.season,
            "is_preferred":      r.is_preferred,
            "is_medicinal_prep": r.is_medicinal_prep,
            "source":            r.source,
        }
        for r in _all_recipes
    ]

    from app.services.phenology import active_months_display
    phenology = active_months_display(sp.flower_months, sp.fruit_months, sp.leaf_months)

    culinary_out = _culinary_to_dict(ci, sp.scientific_name) if ci else None
    ai_fields_out = ai_fields
    field_source_tags: dict = {}
    if identity.is_guest:
        culinary_out, field_source_tags = await _apply_guest_field_mask(
            db, culinary_out, ci.id if ci else None
        )
        ai_fields_out = [f for f in ai_fields if (culinary_out or {}).get(f) is not None]

    return {
        "species": {
            "id": sp.id,
            "scientific_name": sp.scientific_name,
            "common_names": _parse_json_list(sp.common_names),
            "common_names_de": _parse_json_list(sp.common_names_de),
            "preferred_common_name": sp.preferred_common_name,
            "family": sp.family,
            "genus": sp.genus,
            "kingdom": sp.kingdom,
            "edibility_status": sp.edibility_status,
            "edibility_verified": sp.edibility_verified,
            "toxicity_severity": sp.toxicity_severity,  # none | toxic | deadly (0039) — drives safety-box colour
            "mushroom_observer_url": mo_url,
            # Phenology
            "flower_months": sp.flower_months,
            "fruit_months":  sp.fruit_months,
            "leaf_months":   sp.leaf_months,
            "peak_season":   sp.peak_season,
            "phenology":     phenology,
            "foraging_notes": sp.foraging_notes,
            # ITIS name validation
            "itis_tsn":           sp.itis_tsn,
            "itis_accepted_name": sp.itis_accepted_name,
            "itis_name_match":    sp.itis_name_match,
            "itis_checked_at":    sp.itis_checked_at.isoformat() if sp.itis_checked_at else None,
        },
        "culinary": culinary_out,
        "ai_generated_fields": ai_fields_out,
        # field_source_tags: {field_name: "PFAF"|"EMA"|"Source: reference data"}.
        # Only ever populated for guest requests — curators get full provenance
        # via ai_generated_fields/ai_approved_fields + the drafts below instead.
        "field_source_tags": field_source_tags,
        **({} if identity.is_guest else {
            "pending_draft_count": len(pending_drafts),
            "pending_draft_fields": [d.field_name for d in pending_drafts],
            "pending_drafts": [
                {
                    "id": d.id,
                    "field_name": d.field_name,
                    "draft_text": d.draft_text,
                    "model": d.model,
                    "generated_at": d.generated_at.isoformat() if d.generated_at else None,
                }
                for d in pending_drafts
            ],
        }),
        "recipes": recipes_list,
        "recipe_count": len(recipes_list),
        "edibility_blocked_recipes": _edibility_blocked,
        # Phase 12 follow-up — edibility lock + source notes
        "edibility_human_verified":   _edibility_human_verified,
        "fungi_edibility_notes":      _fungi_edibility_notes,
        "taste_notes_human_locked":   _taste_notes_human_locked,
        "common_names_human_locked":  _common_names_human_locked,
        "observations": {
            "total": len(obs_rows),
            "confirmed": len(confirmed),
            "thumbnails": [
                {
                    "id": r.id,
                    "thumbnail": r.thumbnail_path,
                    "latitude": r.latitude,
                    "longitude": r.longitude,
                    "taken_at": r.photo_taken_at.isoformat() if r.photo_taken_at else None,
                    "review_status": r.review_status,
                    "human_corrected": r.human_corrected,
                }
                for r in obs_rows
            ],
        },
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_species_or_404(db: AsyncSession, scientific_name: str) -> Species:
    sp = await db.scalar(
        select(Species).where(Species.scientific_name == scientific_name)
    )
    if not sp:
        raise HTTPException(
            status_code=404,
            detail=f"Species '{scientific_name}' not found. Run enrich.py first.",
        )
    return sp


def _parse_json_list(val: Optional[str]) -> list:
    if not val:
        return []
    try:
        result = json.loads(val)
        return result if isinstance(result, list) else []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Guest-visibility gate for /api/species/{name}/profile
#
# Verified (audit, 2026-07-02) that "column has content" does NOT imply
# "content was approved" — the enrichment pipeline, a self-auto-approve
# placeholder, and merge/rename cascades all write these columns with no
# draft/approval step and often no history row at all. The gate below is
# therefore history-row-driven and fails CLOSED: a field is only shown to a
# guest when its latest real (non-mechanical) authoring row proves it, or —
# for a narrow, toggle-gated class of historyless direct-scrape fields — is
# explicitly allow-listed as such. Everything else is omitted.
# ---------------------------------------------------------------------------

# The 21 enrichment text fields on culinary_info (per the provenance census).
_GUEST_GATED_FIELDS = [
    "edible_parts", "flavour_profile", "preparation_methods", "cooking_techniques",
    "preservation_methods", "seasonal_peak", "harvest_stage", "pairing_ideas",
    "culinary_traditions", "recipe_ideas", "workshop_value_score", "traditional_uses",
    "cultural_notes", "medicinal_folklore", "look_alike_warnings", "preparation_warnings",
    "id_notes", "taste_notes", "medicinal_notes", "medicinal_clinical", "recipe",
]

# Housekeeping changed_by tags that are never the "real" authoring event —
# walk past these to find the actual authoring row underneath.
_MECHANICAL_CHANGED_BY = {"normalization", "system_remediation", "system_retroactive"}

# Tier 2 (safe, shown with a named source tag).
_GUEST_SOURCED_CHANGED_BY = {"ema": "EMA", "pfaf_reparse": "PFAF", "pfaf": "PFAF"}

# Tier 2 (safe, shown clean — a human wrote or approved it).
_GUEST_CLEAN_CHANGED_BY = {"human", "ai_approved:human"}

# Tier 3 — fields where "no history row" means "unaudited direct pipeline
# scrape" (safe-ish, toggle-gated), NOT "unapproved AI draft content".
# The AI-draft-approval-gated fields (medicinal_folklore, taste_notes,
# medicinal_notes, medicinal_clinical, recipe) are deliberately excluded —
# for those, a historyless row is the _ensure_medicinal_default() placeholder
# class or an anomaly, and must stay Tier-1-omitted regardless of the toggle.
_GUEST_TIER3_ELIGIBLE_FIELDS = {
    "edible_parts", "flavour_profile", "preparation_methods", "cooking_techniques",
    "preservation_methods", "seasonal_peak", "harvest_stage", "pairing_ideas",
    "culinary_traditions", "recipe_ideas", "workshop_value_score", "traditional_uses",
    "cultural_notes", "look_alike_warnings", "preparation_warnings", "id_notes",
}


async def _guest_field_classification(db: AsyncSession, ci_id: Optional[int]) -> dict:
    """
    Classify each of the 21 enrichment fields for guest display.

    Returns {field_name: (tier, source_label)} where tier is one of:
      "omit"          — never shown to a guest
      "show_clean"    — shown, no badge
      "show_sourced"  — shown, tagged with source_label (e.g. "PFAF", "EMA")
      "show_tier3"    — shown ONLY if guest_show_sourced_fields is True,
                         tagged "Source: reference data"
    """
    result = {f: ("omit", None) for f in _GUEST_GATED_FIELDS}
    if not ci_id:
        return result

    rows = (await db.execute(
        select(CulinaryInfoHistory.field_name, CulinaryInfoHistory.changed_by)
        .where(CulinaryInfoHistory.culinary_info_id == ci_id)
        .where(CulinaryInfoHistory.field_name.in_(_GUEST_GATED_FIELDS))
        .order_by(CulinaryInfoHistory.id.desc())
    )).all()

    # First non-mechanical row per field wins (rows already newest-first).
    latest_real: dict = {}
    for field_name, changed_by in rows:
        if field_name in latest_real:
            continue
        if changed_by in _MECHANICAL_CHANGED_BY:
            continue
        latest_real[field_name] = changed_by

    for field in _GUEST_GATED_FIELDS:
        cb = latest_real.get(field)
        if cb in _GUEST_SOURCED_CHANGED_BY:
            result[field] = ("show_sourced", _GUEST_SOURCED_CHANGED_BY[cb])
        elif cb in _GUEST_CLEAN_CHANGED_BY:
            result[field] = ("show_clean", None)
        elif cb is None and field in _GUEST_TIER3_ELIGIBLE_FIELDS:
            result[field] = ("show_tier3", "Source: reference data")
        else:
            result[field] = ("omit", None)  # unrecognised changed_by, or a
            # historyless draft-gated field (e.g. the medicinal_notes
            # placeholder) — fail closed.

    return result


async def _apply_guest_field_mask(
    db: AsyncSession,
    culinary_dict: Optional[dict],
    ci_id: Optional[int],
) -> Optional[dict]:
    """
    Mutate a copy of the _culinary_to_dict() output for guest visibility.
    Also returns field_source_tags for whatever remains shown.
    """
    if culinary_dict is None:
        return None, {}

    from app.services.settings_service import get_setting as _gs
    show_tier3 = bool(_gs("guest_show_sourced_fields"))

    classification = await _guest_field_classification(db, ci_id)
    masked = dict(culinary_dict)
    tags: dict = {}

    for field, (tier, label) in classification.items():
        if field not in masked:
            continue
        if tier == "omit":
            masked[field] = None
        elif tier == "show_tier3":
            if show_tier3 and masked.get(field) is not None:
                tags[field] = label
            else:
                masked[field] = None
        elif tier == "show_sourced" and masked.get(field) is not None:
            tags[field] = label
        # "show_clean", or a field with no actual content — leave as-is, no tag

    # Trim provenance metadata lists to match what's actually visible —
    # these are field-name lists, not content, but should still only name
    # fields the guest can actually see.
    visible_fields = {f for f in _GUEST_GATED_FIELDS if masked.get(f) is not None}
    if masked.get("ai_generated_fields"):
        masked["ai_generated_fields"] = [f for f in masked["ai_generated_fields"] if f in visible_fields]
    if masked.get("ai_approved_fields"):
        masked["ai_approved_fields"] = [f for f in masked["ai_approved_fields"] if f in visible_fields]

    return masked, tags


# ---------------------------------------------------------------------------
# POST /api/culinary/{species_name}/enrich   — on-demand single-species enrichment
# ---------------------------------------------------------------------------

@router.post("/api/culinary/{species_name:path}/enrich")
async def enrich_species_now(
    species_name: str,
    section: Optional[str] = Query(None, description="taste | recipe | medicinal — run only this AI generation"),
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """
    Trigger on-demand enrichment for one species.

    section (optional): when provided, skips PFAF/Wikidata and runs only the
    specified AI draft generation (taste=taste_notes, recipe=recipe,
    medicinal=medicinal_notes).  Returns {"ok", "section_queued": field_name}.

    Full enrichment (no section):
    - Fetches PFAF + Wikidata concurrently (same as batch enrichment).
    - Only fills fields that are currently NULL/empty.
    - Fields that have been manually edited (have a CulinaryInfoHistory row
      with changed_by='human') are NEVER overwritten.
    - Returns: what was filled, what was already set, what remains empty.
    """
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    sp = await _get_species_or_404(db, species_name)

    # ── Section-only path ──────────────────────────────────────────────────────
    _SECTION_MAP = {"taste": "taste_notes", "recipe": "recipe", "medicinal": "medicinal_notes"}
    if section:
        field_name = _SECTION_MAP.get(section)
        if not field_name:
            raise HTTPException(400, f"Unknown section {section!r}. Use: taste, recipe, medicinal")

        from app.services.enrichment import _section_ai_draft
        queued = await _section_ai_draft(db, sp, field_name)
        await db.commit()
        return {"ok": True, "section": section, "section_queued": field_name, "queued": queued}

    # ── Full enrichment path ───────────────────────────────────────────────────
    ci = await db.scalar(
        select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id)
    )

    # Determine which fields have human edits — never overwrite those
    human_edited_fields: set = set()
    if ci:
        history_rows = (await db.execute(
            select(CulinaryInfoHistory)
            .where(CulinaryInfoHistory.culinary_info_id == ci.id)
            .where(CulinaryInfoHistory.changed_by == "human")
        )).scalars().all()
        human_edited_fields = {r.field_name for r in history_rows}

    # Run enrichment via the enrichment service — fill_empty_only + protect human edits
    from app.services.enrichment import enrich_species as _enrich_species
    result_status = await _enrich_species(
        session=db,
        species=sp,
        dry_run=False,
        re_enrich=True,          # force re-fetch even if already enriched
        fill_empty_only=True,    # only fill currently-empty fields
        protected_fields=human_edited_fields,  # never overwrite human corrections
    )

    await db.commit()

    # Reload culinary info to report on what's populated now
    ci_new = await db.scalar(
        select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id)
    )

    trackable_fields = [
        "edible_parts", "preparation_methods", "look_alike_warnings",
        "preparation_warnings", "seasonal_peak", "traditional_uses",
        "cultural_notes", "culinary_traditions",
    ]

    filled   = []
    empty    = []
    protected = []

    for f in trackable_fields:
        if f in human_edited_fields:
            protected.append(f)
        elif ci_new and getattr(ci_new, f, None):
            filled.append(f)
        else:
            empty.append(f)

    return {
        "ok": True,
        "species": species_name,
        "enrichment_status": result_status,
        "data_confidence": ci_new.data_confidence if ci_new else 0.0,
        "fields_filled": filled,
        "fields_empty": empty,
        "fields_protected_human_edit": protected,
        # Current values for the enrichment-review card fields, so the UI can
        # refresh them inline after a Repopulate (A4) without a full reload.
        "values": {
            "edible_parts":         ci_new.edible_parts if ci_new else None,
            "preparation_warnings": ci_new.preparation_warnings if ci_new else None,
            "look_alike_warnings":  ci_new.look_alike_warnings if ci_new else None,
        },
        "pfaf_retrieved_at": ci_new.pfaf_retrieved_at.isoformat() if (ci_new and ci_new.pfaf_retrieved_at) else None,
        "wikidata_retrieved_at": ci_new.wikidata_retrieved_at.isoformat() if (ci_new and ci_new.wikidata_retrieved_at) else None,
    }


# ---------------------------------------------------------------------------
# POST /api/species/{species_name}/drafts/{field}/approve
# ---------------------------------------------------------------------------

class DraftEditApprove(BaseModel):
    edited_text: Optional[str] = Field(None, description="Edited version of the draft (None = approve as-is)")
    approved_by: str = Field("human", description="Who approved")
    season: Optional[str] = Field(None, description="Season tag for recipe bank (spring/summer/autumn/winter/year-round)")


@router.post("/api/species/{species_name:path}/drafts/{field}/approve")
async def approve_ai_draft(
    species_name: str,
    field: str,
    body: DraftEditApprove,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """
    Approve an AI-drafted field (optionally with edits).

    - Marks the draft as 'approved' or 'edited_approved'
    - Copies the approved text to culinary_info.{field}
    - Adds the field to ci.ai_approved_fields_json

    Field must be one of: taste_notes, medicinal_notes, recipe, medicinal_folklore
    """
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    _APPROVABLE = {"taste_notes", "medicinal_notes", "recipe", "medicinal_folklore"}
    if field not in _APPROVABLE:
        raise HTTPException(400, f"field must be one of: {sorted(_APPROVABLE)}")

    sp = await _get_species_or_404(db, species_name)

    # Find the most recent pending draft for this field
    draft = await db.scalar(
        select(SpeciesAIDraft)
        .where(SpeciesAIDraft.species_id == sp.id)
        .where(SpeciesAIDraft.field_name == field)
        .where(SpeciesAIDraft.status == "pending")
        .order_by(SpeciesAIDraft.generated_at.desc())
    )
    if not draft:
        raise HTTPException(404, f"No pending AI draft found for '{field}' on {species_name}")

    # Approve
    approved_text = body.edited_text.strip() if body.edited_text else draft.draft_text
    is_edited = bool(body.edited_text and body.edited_text.strip() != (draft.draft_text or "").strip())

    draft.status = "edited_approved" if is_edited else "approved"
    draft.final_text = body.edited_text if is_edited else None
    draft.approved_at = datetime.utcnow()
    # Server-derived provenance (is_guest 403 guard above → curator). body.approved_by ignored.
    draft.approved_by = "human"

    # Apply to culinary_info
    ci = await db.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id))
    if not ci:
        ci = CulinaryInfo(species_id=sp.id)
        db.add(ci)
        await db.flush()  # Ensure ci.id is populated for history
    else:
        # Human-lock guard — an existing human-authored edit must not be overwritten by AI approval.
        _locked = (await db.execute(
            select(CulinaryInfoHistory.id)
            .where(CulinaryInfoHistory.culinary_info_id == ci.id)
            .where(CulinaryInfoHistory.field_name == field)
            .where(CulinaryInfoHistory.changed_by == "human")
            .limit(1)
        )).fetchone()
        if _locked:
            raise HTTPException(
                status_code=409,
                detail=f"Field '{field}' is human-locked and cannot be overwritten by an AI draft.",
            )

    setattr(ci, field, approved_text)

    # Track in ai_approved_fields_json
    approved_fields = _parse_json_list(ci.ai_approved_fields_json)
    if field not in approved_fields:
        approved_fields.append(field)
    ci.ai_approved_fields_json = json.dumps(approved_fields)

    # Write to culinary_info_history for audit trail (only when ci has a real PK)
    if ci.id:
        db.add(CulinaryInfoHistory(
            culinary_info_id=ci.id,
            field_name=field,
            old_value=None,
            new_value=approved_text,
            changed_at=datetime.utcnow(),
            changed_by=f"ai_approved:human",
        ))

    # For recipe approvals: also write to species_recipes bank
    if field == "recipe" and approved_text:
        import re as _re
        _SEASON_RE = {
            "spring": _re.compile(r"\b(spring|early spring|late spring|march|april|may|young shoot)\b", _re.IGNORECASE),
            "summer": _re.compile(r"\b(summer|high summer|june|july|august)\b", _re.IGNORECASE),
            "autumn": _re.compile(r"\b(autumn|fall|september|october|november|harvest)\b", _re.IGNORECASE),
            "winter": _re.compile(r"\b(winter|december|january|february|stored root)\b", _re.IGNORECASE),
        }
        _VALID_SEASONS = {"spring", "summer", "autumn", "winter", "year-round"}
        # Use provided season or infer from text
        recipe_season = body.season if (body.season and body.season in _VALID_SEASONS) else "year-round"
        if recipe_season == "year-round":
            counts = {s: len(p.findall(approved_text)) for s, p in _SEASON_RE.items()}
            best = max(counts, key=counts.get)
            if counts[best] > 0:
                recipe_season = best
        # Extract title from first # heading
        recipe_title = None
        for line in approved_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                recipe_title = stripped.lstrip("#").strip()[:200]
                break
        # Check if recipe bank entry already exists from this draft
        existing_rb = await db.scalar(
            select(SpeciesRecipe).where(SpeciesRecipe.ai_draft_id == draft.id)
        )
        if not existing_rb:
            db.add(SpeciesRecipe(
                species_id=sp.id,
                title=recipe_title,
                body=approved_text,
                season=recipe_season,
                source="ai_generated",
                status="approved",
                ai_draft_id=draft.id,
            ))

    await db.commit()

    return {
        "ok": True,
        "species": species_name,
        "field": field,
        "status": draft.status,
        "approved_text_preview": (approved_text or "")[:200],
    }


# ---------------------------------------------------------------------------
# POST /api/species/{species_name}/drafts/{field}/reject
# ---------------------------------------------------------------------------

@router.post("/api/species/{species_name:path}/drafts/{field}/reject")
async def reject_ai_draft(
    species_name: str,
    field: str,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """Mark a pending AI draft as rejected (does not affect culinary_info)."""
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    sp = await _get_species_or_404(db, species_name)
    draft = await db.scalar(
        select(SpeciesAIDraft)
        .where(SpeciesAIDraft.species_id == sp.id)
        .where(SpeciesAIDraft.field_name == field)
        .where(SpeciesAIDraft.status == "pending")
        .order_by(SpeciesAIDraft.generated_at.desc())
    )
    if not draft:
        raise HTTPException(404, f"No pending AI draft found for '{field}' on {species_name}")
    draft.status = "rejected"
    await db.commit()
    return {"ok": True, "field": field, "status": "rejected"}


# ---------------------------------------------------------------------------
# POST /api/drafts/generate          — generate AI drafts for one species
# POST /api/drafts/bulk-generate     — generate AI drafts for many species
#
# "Generate" creates drafts for fields that have none pending/approved.
# "Regenerate" (re_enrich=True) invalidates existing pending drafts first,
# then generates fresh drafts from the current scraped source data.
# Both paths respect the edibility gate from claude_draft.py — toxic/inedible/
# null/unknown species never receive recipe or taste_notes drafts.
# ---------------------------------------------------------------------------

class DraftGenerateRequest(BaseModel):
    scientific_name: str
    re_enrich: bool = False  # True = invalidate existing pending drafts first


class BulkDraftGenerateRequest(BaseModel):
    species: list  # list of scientific name strings
    re_enrich: bool = False


async def _generate_drafts_for_species(
    scientific_name: str,
    re_enrich: bool,
    db: AsyncSession,
    field: Optional[str] = None,
    reprocess_rejected: bool = False,
) -> dict:
    """
    Core generate/regenerate logic for one species.

    field: when set (one draft field), only that domain is generated — used by
        per-domain backfill. reprocess_rejected: when True, rejected drafts are
        treated as outstanding (backfill path). Both apply to the re_enrich=False
        path only.

    re_enrich=False: delegates to _maybe_generate_ai_drafts, which skips fields
        that already have a pending/approved/edited_approved draft (and, unless
        reprocess_rejected, a rejected one too).
    re_enrich=True: calls generate_ai_drafts directly, bypassing the "already
        has drafts" guard so a fresh pending draft is always created.
        Existing pending drafts are invalidated first; approved drafts are
        left in place (the new pending draft enters the review queue alongside
        them — the curator chooses whether to replace or discard).

    Returns {"created": N, "blocked": reason|None, "scientific_name": name}
    """
    from app.config import settings as _settings
    from app.integrations.claude_draft import generate_ai_drafts
    from app.services.enrichment import _maybe_generate_ai_drafts
    from sqlalchemy import func as _func, update as _upd

    from app.services.settings_service import get_setting as _gs_draft
    _draft_backend = _gs_draft("enrichment_backend") or "anthropic"
    if _draft_backend == "anthropic" and not _settings.anthropic_api_key:
        return {"scientific_name": scientific_name, "created": 0, "blocked": "ANTHROPIC_API_KEY not set"}

    sp = await db.scalar(select(Species).where(Species.scientific_name == scientific_name))
    if not sp:
        return {"scientific_name": scientific_name, "created": 0, "blocked": "Species not found"}

    # Edibility gate — hard block, mirrors generate_ai_drafts() internal check
    edib = (sp.edibility_status or "").lower()
    if edib in ("toxic", "inedible", "not_edible"):
        return {"scientific_name": scientific_name, "created": 0, "blocked": f"Edibility gate: {edib}"}

    ci = await db.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id))

    common_names: list = []
    if sp.common_names:
        try:
            common_names = json.loads(sp.common_names) or []
        except Exception:
            pass

    count_before = (await db.scalar(
        select(_func.count(SpeciesAIDraft.id))
        .where(SpeciesAIDraft.species_id == sp.id)
        .where(SpeciesAIDraft.status == "pending")
    )) or 0

    if not re_enrich:
        # "Generate" path: only fills gaps (fields with no existing draft at all)
        await _maybe_generate_ai_drafts(
            session=db, species=sp, ci=ci, re_enrich=False,
            inat_result=None, trompenburg_result=None, common_names=common_names,
            only_field=field, reprocess_rejected=reprocess_rejected,
        )
    else:
        # "Regenerate" path: force fresh drafts regardless of existing approved ones.
        # 1. Invalidate any existing PENDING drafts (so they don't clutter the queue)
        await db.execute(
            _upd(SpeciesAIDraft)
            .where(SpeciesAIDraft.species_id == sp.id)
            .where(SpeciesAIDraft.status == "pending")
            .values(status="invalidated")
        )
        await db.flush()

        # 2. Build conditions caveat for caution species
        edibility_conditions: Optional[str] = None
        if edib == "caution":
            try:
                cond_rows = (await db.execute(
                    select(SpeciesEdibilityCondition)
                    .where(SpeciesEdibilityCondition.species_id == sp.id)
                )).scalars().all()
                if cond_rows:
                    edibility_conditions = "; ".join(
                        f"{c.part} ({c.preparation}): {'safe' if c.safe else 'unsafe'}"
                        + (f" — {c.notes}" if c.notes else "")
                        for c in cond_rows
                    )
            except Exception:
                pass

        # 3. Call generate_ai_drafts directly — bypasses "already has drafts" guard
        from app.services.settings_service import get_setting as _gs
        draft_result = await generate_ai_drafts(
            scientific_name=scientific_name,
            api_key=_settings.anthropic_api_key,
            model=_gs("anthropic_model"),
            common_names=common_names,
            edible_parts=ci.edible_parts if ci else None,
            preparation_methods=ci.preparation_methods if ci else None,
            traditional_uses=ci.traditional_uses if ci else None,
            medicinal_folklore=ci.medicinal_folklore if ci else None,
            inat_description=None,
            trompenburg_description=None,
            edibility_status=sp.edibility_status,
            edibility_conditions=edibility_conditions,
            preparation_warnings=ci.preparation_warnings if ci else None,
        )

        if draft_result:
            # Placeholder filter — same as enrichment.py (culinary fields only)
            _NON_ANSWERS = (
                "not enough information", "not enough sourced", "i don't have",
                "i cannot", "i'm unable", "unable to provide", "cannot provide",
                "insufficient", "not able to", "no sourced information",
            )
            _CULINARY_FIELDS = {"taste_notes", "recipe"}
            field_map = {
                "taste_notes":    draft_result.taste_notes,
                "medicinal_notes": draft_result.medicinal_notes,
                "recipe":         draft_result.recipe,
            }
            ctx_json = json.dumps(draft_result.context_used)
            for field_name, text in field_map.items():
                if not text:
                    continue
                if field_name in _CULINARY_FIELDS and any(p in text.lower() for p in _NON_ANSWERS):
                    continue
                db.add(SpeciesAIDraft(
                    species_id=sp.id,
                    field_name=field_name,
                    draft_text=text,
                    status="pending",
                    generated_at=datetime.utcnow(),
                    generation_context_json=ctx_json,
                    model=draft_result.model,
                ))
        await db.flush()

    # Mirror enrich_species() A5: if no medicinal_notes and no source folklore,
    # apply the standard "No traditional medicinal uses recorded" default.
    # The backfill runner calls _generate_drafts_for_species without going through
    # enrich_species(), so _ensure_medicinal_default was never reached on that path.
    if ci is not None:
        from app.services.enrichment import _ensure_medicinal_default
        await _ensure_medicinal_default(db, sp, ci)

    count_after = (await db.scalar(
        select(_func.count(SpeciesAIDraft.id))
        .where(SpeciesAIDraft.species_id == sp.id)
        .where(SpeciesAIDraft.status == "pending")
    )) or 0

    created = max(0, count_after - count_before)
    return {"scientific_name": scientific_name, "created": created, "blocked": None}


@router.post("/api/drafts/generate")
async def generate_drafts(
    body: DraftGenerateRequest,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """
    Generate (or regenerate) AI drafts for a single species.

    re_enrich=False (default): only generates drafts for fields that have no
      existing pending/approved/rejected draft. Safe to call at any time.
    re_enrich=True: invalidates all existing pending drafts first, then
      generates fresh drafts. Use this for an explicit "regenerate" action.

    Returns immediately with {ok, scientific_name, created, blocked}.
    New drafts appear in the AI Draft Review queue with status=pending.
    """
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    result = await _generate_drafts_for_species(body.scientific_name, body.re_enrich, db)
    await db.commit()
    return {"ok": True, **result}


@router.post("/api/drafts/bulk-generate")
async def bulk_generate_drafts(
    body: BulkDraftGenerateRequest,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    """
    Generate (or regenerate) AI drafts for multiple species.

    Processes sequentially; each species is committed independently so a
    failure on one does not roll back the others. Returns per-species results.
    """
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    if not body.species:
        return {"ok": True, "results": [], "total_created": 0}

    results = []
    total_created = 0
    for name in body.species:
        try:
            result = await _generate_drafts_for_species(name, body.re_enrich, db)
            await db.commit()
            results.append(result)
            total_created += result.get("created", 0)
        except Exception as exc:
            await db.rollback()
            results.append({"scientific_name": name, "created": 0, "blocked": str(exc)})

    return {"ok": True, "results": results, "total_created": total_created}


# ---------------------------------------------------------------------------
# POST /api/enrichment/run  — start a full enrichment batch job
# GET  /api/enrichment/status/{job_id}  — poll for progress and result
# ---------------------------------------------------------------------------

class EnrichmentRunRequest(BaseModel):
    re_enrich: bool = Field(True, description="Re-fetch even if already enriched")


async def _run_enrichment_job(job_id: str, re_enrich: bool) -> None:
    """
    Background worker: runs the enrichment batch and writes progress updates
    into _enrichment_jobs[job_id] and background_processes table.
    Uses its own DB session (BackgroundTasks run outside the request session lifecycle).

    Resume: if a paused background_processes row exists for 'enrichment_run',
    the run continues from progress_current rather than restarting from 0.
    """
    from app.services.background_processes import bp_progress, bp_finish, bp_active_row
    from app.services.enrichment import run_enrichment_batch

    job = _enrichment_jobs[job_id]
    process_id = job.get("process_id")

    # Determine resume position from any paused row (set before this task started)
    start_from = job.get("resume_from", 0)

    _hb_counter = 0

    def _progress(current: int, total: int, name: str, status: str) -> None:
        nonlocal _hb_counter
        job["progress"] = {
            "current": current,
            "total": total,
            "current_species": name,
            "last_status": status,
        }
        job["log"].append(f"{name} → {status}")
        _hb_counter += 1
        # Update DB every 5 items to avoid hammering SQLite on large runs
        if _hb_counter % 5 == 0 and process_id:
            import asyncio
            detail = f"Enriching {name} ({current} of {total})"
            asyncio.create_task(bp_progress(process_id, current, total, detail))

    async def _cancel_check() -> Optional[str]:
        """Read current BP status from DB; return 'paused'/'cancelled' or None."""
        if not process_id:
            return None
        try:
            from sqlalchemy import text as _text
            async with AsyncSessionLocal() as _db:
                row = await _db.execute(
                    _text("SELECT status FROM background_processes WHERE process_id = :pid"),
                    {"pid": process_id},
                )
                r = row.fetchone()
                if r and r[0] in ("paused", "cancelled"):
                    return r[0]
        except Exception:
            pass
        return None

    try:
        # run_enrichment_batch manages its own per-species sessions internally —
        # do NOT pass a long-lived session here.
        result = await run_enrichment_batch(
            dry_run=False,
            re_enrich=re_enrich,
            progress_cb=_progress,
            cancel_check_fn=_cancel_check,
            start_from=start_from,
        )

        # Count pending AI drafts — short-lived read session, closed immediately.
        async with AsyncSessionLocal() as _count_sess:
            from sqlalchemy import func as sqlfunc
            draft_count = (await _count_sess.execute(
                select(sqlfunc.count(SpeciesAIDraft.id))
                .where(SpeciesAIDraft.status == "pending")
            )).scalar_one() or 0

        stopped_at = result.get("stopped_at")
        prog = job["progress"]

        if stopped_at is not None:
            # Loop exited due to pause or cancel — leave BP status as-is (already set by API)
            job["status"] = "paused"
            job["resume_from"] = stopped_at
        else:
            job["status"] = "complete"
            job["result"] = {
                "total":       result.get("total", 0),
                "enriched":    result.get("enriched", 0),
                "partial":     result.get("partial", 0),
                "not_found":   result.get("not_found", 0),
                "skipped":     result.get("skipped", 0),
                "failed":      result.get("failed", 0),
                "ai_drafts_pending": draft_count,
            }
            job["finished_at"] = datetime.utcnow().isoformat()
            await bp_finish(process_id, status="complete",
                            current=prog.get("current", 0), total=prog.get("total", 0))

    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)
        job["finished_at"] = datetime.utcnow().isoformat()
        await bp_finish(process_id, status="failed", error=str(exc))


@router.post("/api/enrichment/run")
async def start_enrichment_run(
    body: EnrichmentRunRequest,
    background_tasks: BackgroundTasks,
    identity: Identity = Depends(get_identity),
):
    """
    Start a full enrichment batch run in the background.
    Returns immediately with a job_id.  Poll /api/enrichment/status/{job_id}
    for progress and the final summary.

    Only one job may run at a time — returns 409 if one is already running
    (checked via both in-memory state and background_processes table).
    """
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    from app.services.background_processes import bp_active_count, bp_active_row, bp_start

    # Guard: refuse if already running (in-memory fast path)
    for existing in _enrichment_jobs.values():
        if existing.get("status") == "running":
            bp_row = await bp_active_row("enrichment_run")
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "already_running",
                    "process_type": "enrichment_run",
                    "progress_current": bp_row["progress_current"] if bp_row else 0,
                    "progress_total":   bp_row["progress_total"]   if bp_row else 0,
                    "detail": bp_row["detail"] if bp_row else "Enrichment run in progress",
                },
            )

    # Resume from a paused job if one exists in memory
    resume_from = 0
    paused_job = None
    for existing in reversed(list(_enrichment_jobs.values())):
        if existing.get("status") == "paused":
            paused_job = existing
            resume_from = existing.get("resume_from", 0)
            break

    job_id = str(uuid.uuid4())
    _enrichment_jobs[job_id] = {
        "job_id":      job_id,
        "status":      "running",
        "re_enrich":   body.re_enrich,
        "resume_from": resume_from,
        "started_at":  datetime.utcnow().isoformat(),
        "finished_at": None,
        "progress":    {"current": resume_from, "total": 0, "current_species": "", "last_status": ""},
        "log":         [],
        "result":      None,
        "error":       None,
        "process_id":  None,
    }

    # If resuming, reuse the existing paused BP row (update status back to running)
    if paused_job and paused_job.get("process_id"):
        process_id = paused_job["process_id"]
        # Routed through bp_set_status so background_processes.py stays the sole
        # writer of this table. heartbeat=True reproduces the previous raw UPDATE
        # exactly (status + updated_at + last_heartbeat).
        from app.services.background_processes import bp_set_status as _bp_set_status
        await _bp_set_status(process_id, "running", heartbeat=True)
        detail = f"Resuming enrichment from item {resume_from}…"
    else:
        process_id = await bp_start("enrichment_run", detail="Starting enrichment…")
        detail = "Starting enrichment…"

    _enrichment_jobs[job_id]["process_id"] = process_id

    background_tasks.add_task(
        _run_enrichment_job,
        job_id=job_id,
        re_enrich=body.re_enrich,
    )
    return {"job_id": job_id, "status": "running", "process_id": process_id, "resume_from": resume_from}


@router.get("/api/enrichment/status/{job_id}")
async def get_enrichment_status(job_id: str):
    """
    Poll enrichment job status.

    Returns:
      status:    "running" | "complete" | "failed"
      progress:  {current, total, current_species, last_status}
      result:    summary dict once complete
      log:       list of per-species status lines
      error:     error message if status=="failed"
    """
    job = _enrichment_jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"No enrichment job with id {job_id!r}")
    return job


@router.get("/api/enrichment/running")
async def get_running_job():
    """Return the currently-running job, or null if none is running."""
    for job in reversed(list(_enrichment_jobs.values())):
        if job.get("status") == "running":
            return job
    return None


def _culinary_to_dict(ci: Optional["CulinaryInfo"], sci_name: Optional[str] = None) -> Optional[dict]:
    if ci is None:
        return None

    # Fix 24a: Bracken Safety Logic
    is_bracken = False
    if sci_name and sci_name.strip().lower() == "pteridium aquilinum":
        is_bracken = True

    bracken_warning = (
        "Not safe for human consumption. Contains ptaquiloside (a carcinogen) "
        "and thiaminase. Do not eat."
    )

    edible_parts = ci.edible_parts
    if is_bracken:
        edible_parts = f"DANGER: {bracken_warning} " + (edible_parts or "")

    return {
        # Phase 6 fields
        "edible_parts": edible_parts,
        "flavour_profile": ci.flavour_profile,
        "preparation_methods": ci.preparation_methods,
        "cooking_techniques": ci.cooking_techniques,
        "preservation_methods": ci.preservation_methods,
        "seasonal_peak": ci.seasonal_peak,
        "harvest_stage": ci.harvest_stage,
        "pairing_ideas": ci.pairing_ideas,
        "culinary_traditions": ci.culinary_traditions,
        "recipe_ideas": ci.recipe_ideas,
        "workshop_value_score": ci.workshop_value_score,
        "traditional_uses": ci.traditional_uses,
        "cultural_notes": ci.cultural_notes,
        "medicinal_folklore": ci.medicinal_folklore,
        "look_alike_warnings": ci.look_alike_warnings,
        "preparation_warnings": ci.preparation_warnings,
        "primary_source_url": ci.primary_source_url,
        "sources_json": _parse_json_list(ci.sources_json),
        "data_confidence": ci.data_confidence,
        # Phase 8: ID notes
        "id_notes": ci.id_notes,
        "id_notes_sources": _parse_json_list(ci.id_notes_sources_json),
        # Phase 8: Culinary links
        "culinary_links": _parse_json_list(ci.culinary_links_json),
        # Phase 8: AI-approved fields (only set once approved through review queue)
        "taste_notes": ci.taste_notes if not is_bracken else None,
        "medicinal_notes": ci.medicinal_notes,
        "medicinal_clinical": ci.medicinal_clinical,
        "recipe": ci.recipe if not is_bracken else None,
        # Provenance
        "ai_generated_fields": _parse_json_list(ci.ai_generated_fields_json),
        "ai_approved_fields": _parse_json_list(ci.ai_approved_fields_json),
        "pfaf_retrieved_at": ci.pfaf_retrieved_at.isoformat() if ci.pfaf_retrieved_at else None,
        "wikidata_retrieved_at": ci.wikidata_retrieved_at.isoformat() if ci.wikidata_retrieved_at else None,
        "inat_retrieved_at": ci.inat_retrieved_at.isoformat() if ci.inat_retrieved_at else None,
        "trompenburg_retrieved_at": ci.trompenburg_retrieved_at.isoformat() if ci.trompenburg_retrieved_at else None,
    }


# ---------------------------------------------------------------------------
# POST /api/drafts/backfill — generate missing AI drafts for all eligible species
# ---------------------------------------------------------------------------

# In-memory job state (one run at a time, same pattern as _enrichment_jobs)
_draft_backfill_job: Optional[dict] = None

_DRAFT_BACKFILL_BLOCKED_STATUSES = frozenset({
    None, "", "unknown", "unclear", "toxic", "inedible", "not_edible",
})
_DRAFT_FIELDS = ("taste_notes", "medicinal_notes", "recipe")


# A draft field is "covered" (not a backfill target) only when it has a draft
# in one of these statuses. 'rejected' is intentionally excluded so a rejected
# draft is re-processable — it counts as outstanding, per the backfill spec.
_BACKFILL_COVERED_STATUSES = ["pending", "approved", "edited_approved"]


async def _collect_backfill_targets(
    db: AsyncSession, field: Optional[str] = None
) -> list[str]:
    """
    Return scientific names of species eligible for AI draft backfill:
      - edibility_status is confirmed (not None/unknown/unclear/toxic/inedible/not_edible)
      - at least one observation with review_status in ('approved', 'manually_verified')
      - the requested field(s) have no draft in (pending, approved, edited_approved)
        — a rejected (or missing) draft makes the field outstanding.

    field: when set (one of _DRAFT_FIELDS), only that single domain is considered;
        when None, a species is a target if ANY of the three fields is outstanding.
    """
    from app.models.observation import Observation

    wanted = [field] if field else list(_DRAFT_FIELDS)

    # Species with a confirmed edibility that have approved/verified observations
    obs_subq = (
        select(Observation.species_primary)
        .where(Observation.review_status.in_(["approved", "manually_verified"]))
        .where(Observation.species_primary.is_not(None))
        .where(Observation.species_primary != "")
        .distinct()
        .scalar_subquery()
    )

    candidates = (await db.execute(
        select(Species.scientific_name, Species.id)
        .where(Species.scientific_name.in_(obs_subq))
        .where(Species.edibility_status.is_not(None))
        .where(Species.edibility_status != "")
        .where(Species.edibility_status.not_in(["unknown", "unclear", "toxic", "inedible", "not_edible"]))
        .order_by(Species.scientific_name)
    )).all()

    if not candidates:
        return []

    # For each candidate, check whether the wanted draft field(s) are already covered
    result = []
    for sci_name, sp_id in candidates:
        covered = set((await db.execute(
            select(SpeciesAIDraft.field_name)
            .where(SpeciesAIDraft.species_id == sp_id)
            .where(SpeciesAIDraft.status.in_(_BACKFILL_COVERED_STATUSES))
        )).scalars().all())
        if any(f not in covered for f in wanted):
            result.append(sci_name)

    return result


async def _run_draft_backfill_task(
    jq_id: int,
    pid: Optional[int],
    species_list: list[str],
    field: Optional[str] = None,
    manage_lock: bool = True,
) -> None:
    """
    Background worker for AI draft backfill. Polls job_queue for pause/cancel signals.

    field: when set, only that single draft domain is generated per species.
    manage_lock: when True (default), the global _draft_backfill_job lock is
        released in the finally block. The Run-all orchestrator passes False and
        manages the lock itself across the whole sequence.
    """
    global _draft_backfill_job
    from app.api.queue_api import _broadcast
    from app.services.background_processes import bp_progress, bp_finish

    total   = len(species_list)
    created = 0
    skipped = 0
    blocked = 0
    failed  = 0

    async def _jq_status() -> str:
        """Read current job_queue status for this job."""
        try:
            from sqlalchemy import text as _t
            async with AsyncSessionLocal() as _db:
                row = (await _db.execute(
                    _t("SELECT status FROM job_queue WHERE id = :id"), {"id": jq_id}
                )).fetchone()
                return (row[0] if row else "running")
        except Exception:
            return "running"

    async def _jq_set_progress(current: int, detail: str) -> None:
        try:
            from sqlalchemy import text as _t
            async with AsyncSessionLocal() as _db:
                await _db.execute(
                    _t("UPDATE job_queue SET progress_current=:c, progress_total=:t, last_heartbeat=:hb WHERE id=:id"),
                    {"c": current, "t": total, "id": jq_id, "hb": __import__("datetime").datetime.utcnow()},
                )
                async with db_write_lock():
                    await _db.commit()
            await _broadcast()
        except Exception:
            pass

    async def _jq_finish(status: str, error: str = "") -> None:
        try:
            from sqlalchemy import text as _t
            async with AsyncSessionLocal() as _db:
                await _db.execute(
                    _t("UPDATE job_queue SET status=:s, progress_current=:c, "
                       "progress_total=:t, ended_at=:now, error_message=:e WHERE id=:id"),
                    {"s": status, "c": total, "t": total,
                     "now": datetime.utcnow(), "e": error or None, "id": jq_id},
                )
                async with db_write_lock():
                    await _db.commit()
            await _broadcast()
        except Exception:
            pass

    try:
        for i, sci_name in enumerate(species_list):
            # Check pause/cancel every 5 species
            if i % 5 == 0:
                sig = await _jq_status()
                if sig in ("paused", "cancelled"):
                    log.info("[draft-backfill] Stopping at %d/%d — signal: %s", i, total, sig)
                    if pid:
                        await bp_finish(pid, status=sig, current=i, total=total)
                    return

                await _jq_set_progress(i, sci_name)
                if pid:
                    await bp_progress(pid, i, total, detail=sci_name)

            try:
                async with AsyncSessionLocal() as sess:
                    result = await _generate_drafts_for_species(
                        sci_name, re_enrich=False, db=sess,
                        field=field, reprocess_rejected=True,
                    )
                    async with db_write_lock():
                        await sess.commit()
                n = result.get("created", 0)
                b = result.get("blocked")
                if b:
                    blocked += 1
                    log.info("[draft-backfill] blocked %r: %s", sci_name, b)
                elif n:
                    created += n
                else:
                    skipped += 1
            except Exception as exc:
                failed += 1
                log.warning("[draft-backfill] Error on %r: %s", sci_name, exc)

        summary = (f"Backfill complete: {created} drafts queued, "
                   f"{skipped} already covered, {blocked} blocked, {failed} failed")
        log.info("[draft-backfill] %s", summary)

        await _jq_finish("complete")
        if pid:
            await bp_finish(pid, status="complete", current=total, total=total)

    except Exception as exc:
        log.error("[draft-backfill] Fatal error: %s", exc)
        await _jq_finish("failed", error=str(exc))
        if pid:
            await bp_finish(pid, status="failed", error=str(exc))
    finally:
        # C1: always release the global lock so backfill is not single-use per
        # server lifetime. The orchestrator manages the lock itself (manage_lock=False).
        if manage_lock:
            _draft_backfill_job = None


@router.get("/api/drafts/backfill-counts")
async def get_backfill_counts():
    """
    Return counts for each backfill domain (edibility_status is NOT a domain —
    it is authoritative-source only and never AI-generated).

    Total = all Species in DB.
      - identification_notes: done = id_notes populated; outstanding = total − done
        (every species without id_notes is processable — the task upserts the row).
      - taste_notes / recipe / medicinal_notes: done = species with an
        approved/edited_approved draft. outstanding = the EXACT set the per-domain
        Run will process — eligible species (confirmed edibility + an approved/
        verified observation) whose field has no pending/approved/edited_approved
        draft (a rejected or missing draft makes it outstanding, I8). So for draft
        fields Total ≥ Done + Outstanding (the gap = pending or ineligible species).
    """
    from sqlalchemy import text as _t

    # Outstanding for a draft field = exactly what _collect_backfill_targets(field)
    # would return. Kept in SQL (mirrors that predicate) for efficiency.
    _OUTSTANDING_SQL = _t(
        "SELECT COUNT(*) FROM species s "
        "WHERE s.edibility_status IS NOT NULL AND s.edibility_status != '' "
        "  AND s.edibility_status NOT IN ('unknown','unclear','toxic','inedible','not_edible') "
        "  AND EXISTS (SELECT 1 FROM observations o "
        "              WHERE o.species_primary = s.scientific_name "
        "                AND o.review_status IN ('approved','manually_verified')) "
        "  AND EXISTS (SELECT 1 FROM culinary_info ci "
        "              WHERE ci.species_id = s.id "
        "                AND (ci.edible_parts IS NOT NULL "
        "                     OR ci.traditional_uses IS NOT NULL "
        "                     OR ci.medicinal_folklore IS NOT NULL)) "
        "  AND NOT EXISTS (SELECT 1 FROM species_ai_drafts d "
        "                  WHERE d.species_id = s.id AND d.field_name = :field "
        "                    AND d.status IN ('pending','approved','edited_approved'))"
    )
    _DRAFT_DONE_SQL = _t(
        "SELECT COUNT(DISTINCT species_id) FROM species_ai_drafts "
        "WHERE field_name = :field AND status IN ('approved','edited_approved')"
    )

    async with AsyncSessionLocal() as db:
        total = (await db.execute(_t("SELECT COUNT(*) FROM species"))).scalar() or 0

        # id_notes — on culinary_info table
        id_done = (await db.execute(_t(
            "SELECT COUNT(*) FROM species s "
            "JOIN culinary_info ci ON ci.species_id = s.id "
            "WHERE ci.id_notes IS NOT NULL AND ci.id_notes != ''"
        ))).scalar() or 0

        async def _draft_counts(field: str) -> dict:
            done = (await db.execute(_DRAFT_DONE_SQL, {"field": field})).scalar() or 0
            outstanding = (await db.execute(_OUTSTANDING_SQL, {"field": field})).scalar() or 0
            return {"total": total, "done": done, "outstanding": outstanding}

        result = {
            "identification_notes": {"total": total, "done": id_done, "outstanding": total - id_done},
            "taste_notes":          await _draft_counts("taste_notes"),
            "recipe":               await _draft_counts("recipe"),
            "medicinal_notes":      await _draft_counts("medicinal_notes"),
        }

    return result


# ---------------------------------------------------------------------------
# Per-domain backfill helper for id_notes
# ---------------------------------------------------------------------------

async def _run_id_notes_backfill_task(
    jq_id: int, pid: Optional[int], manage_lock: bool = True
) -> None:
    """
    Generate identification notes (CulinaryInfo.id_notes) for species missing them.

    - I7: builds real source context (common names + culinary_info fields) via
      _build_context/_context_to_text — never name-only.
    - I9: LEFT JOIN + upsert, so species with no culinary_info row are processed
      and a row is created on write (not permanently stuck in 'outstanding').
    - M12: records AI provenance (id_notes_sources_json + ai_generated_fields_json).
    """
    global _draft_backfill_job
    from app.api.queue_api import _broadcast
    from app.services.background_processes import bp_progress, bp_finish
    from app.services.settings_service import get_setting as _gs
    from app.integrations.deepseek_draft import generate_deepseek_id_notes
    from app.integrations.claude_draft import _build_context, _context_to_text
    from sqlalchemy import text as _t

    # LEFT JOIN so species without a culinary_info row are included (I9)
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(_t(
            "SELECT s.id, s.scientific_name, s.common_names, "
            "       ci.edible_parts, ci.preparation_methods, "
            "       ci.traditional_uses, ci.medicinal_folklore "
            "FROM species s "
            "LEFT JOIN culinary_info ci ON ci.species_id = s.id "
            "WHERE (ci.id IS NULL OR ci.id_notes IS NULL OR ci.id_notes = '') "
            "ORDER BY s.scientific_name"
        ))).fetchall()

    targets = [tuple(r) for r in rows]
    total = len(targets)
    created = 0
    failed = 0

    deepseek_key   = _gs("deepseek_api_key")
    deepseek_model = _gs("deepseek_model") or "deepseek-chat"

    async def _jq_status() -> str:
        try:
            async with AsyncSessionLocal() as _db:
                row = (await _db.execute(
                    _t("SELECT status FROM job_queue WHERE id = :id"), {"id": jq_id}
                )).fetchone()
                return row[0] if row else "running"
        except Exception:
            return "running"

    async def _jq_set_progress(current: int) -> None:
        try:
            async with AsyncSessionLocal() as _db:
                await _db.execute(
                    _t("UPDATE job_queue SET progress_current=:c, progress_total=:t, last_heartbeat=:hb WHERE id=:id"),
                    {"c": current, "t": total, "id": jq_id, "hb": datetime.utcnow()},
                )
                async with db_write_lock():
                    await _db.commit()
            await _broadcast()
        except Exception:
            pass

    async def _jq_finish(status: str, error: str = "") -> None:
        try:
            async with AsyncSessionLocal() as _db:
                await _db.execute(
                    _t("UPDATE job_queue SET status=:s, progress_current=:c, progress_total=:t, "
                       "ended_at=:now, error_message=:e WHERE id=:id"),
                    {"s": status, "c": total, "t": total, "now": datetime.utcnow(),
                     "e": error or None, "id": jq_id},
                )
                async with db_write_lock():
                    await _db.commit()
            await _broadcast()
        except Exception:
            pass

    async def _write_id_notes(sp_id: int, text: str) -> None:
        """Upsert culinary_info.id_notes for one species, recording AI provenance."""
        async with AsyncSessionLocal() as wdb:
            ci = await wdb.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == sp_id))
            if ci is None:
                ci = CulinaryInfo(species_id=sp_id)
                wdb.add(ci)
            ci.id_notes = text
            ci.id_notes_sources_json = json.dumps([{"source": "ai_deepseek", "url": None}])
            gen_fields = _parse_json_list(ci.ai_generated_fields_json)
            if "id_notes" not in gen_fields:
                gen_fields.append("id_notes")
            ci.ai_generated_fields_json = json.dumps(gen_fields)
            ci.updated_at = datetime.utcnow()
            async with db_write_lock():
                await wdb.commit()

    try:
        for i, (sp_id, sci_name, common_names_json, edible_parts, prep, trad, med_folk) in enumerate(targets):
            if i % 5 == 0:
                sig = await _jq_status()
                if sig in ("paused", "cancelled"):
                    log.info("[id-notes-backfill] Stopping at %d/%d — signal: %s", i, total, sig)
                    if pid:
                        await bp_finish(pid, status=sig, current=i, total=total)
                    return
                await _jq_set_progress(i)
                if pid:
                    await bp_progress(pid, i, total, detail=sci_name)

            try:
                # I7 — build real source context, not name-only
                common_names = _parse_json_list(common_names_json)
                ctx = _build_context(
                    scientific_name=sci_name,
                    common_names=common_names,
                    edible_parts=edible_parts,
                    preparation_methods=prep,
                    traditional_uses=trad,
                    medicinal_folklore=med_folk,
                    inat_description=None,
                    trompenburg_description=None,
                )
                ctx_text = _context_to_text(sci_name, ctx)
                text = await generate_deepseek_id_notes(
                    scientific_name=sci_name,
                    ctx_text=ctx_text,
                    api_key=deepseek_key,
                    model=deepseek_model,
                )
                if text:
                    await _write_id_notes(sp_id, text)
                    created += 1
            except Exception as exc:
                failed += 1
                log.warning("[id-notes-backfill] Error on %r: %s", sci_name, exc)

        log.info("[id-notes-backfill] complete: created=%d failed=%d", created, failed)
        await _jq_finish("complete")
        if pid:
            await bp_finish(pid, status="complete", current=total, total=total)
    except Exception as exc:
        log.error("[id-notes-backfill] Fatal: %s", exc)
        await _jq_finish("failed", error=str(exc))
        if pid:
            await bp_finish(pid, status="failed", error=str(exc))
    finally:
        if manage_lock:
            _draft_backfill_job = None


@router.get("/api/drafts/prompt-defaults")
async def get_prompt_defaults():
    """Return the built-in default prompts for the prompt editor UI."""
    from app.integrations.claude_draft import (
        _TASTE_SYSTEM_PROMPT,
        _MEDICINAL_SYSTEM_PROMPT,
        _RECIPE_SYSTEM_PROMPT,
    )
    return {
        "prompt_taste": _TASTE_SYSTEM_PROMPT,
        "prompt_medicinal": _MEDICINAL_SYSTEM_PROMPT,
        "prompt_recipe": _RECIPE_SYSTEM_PROMPT,
    }


# Draft domains handled by the combined draft generator (taste/medicinal/recipe).
# edibility_status is NOT a domain — it is authoritative-source only.
_DRAFT_FIELD_DOMAINS = {"taste_notes", "recipe", "medicinal_notes"}

# id_notes target predicate (LEFT JOIN — species with no culinary_info row count too).
_ID_NOTES_OUTSTANDING_SQL = (
    "SELECT COUNT(*) FROM species s "
    "LEFT JOIN culinary_info ci ON ci.species_id = s.id "
    "WHERE (ci.id IS NULL OR ci.id_notes IS NULL OR ci.id_notes = '')"
)


async def _create_backfill_job(job_type: str, label: str, total: int) -> tuple[int, Optional[int]]:
    """Insert a running job_queue row and start a background-process record.

    Returns (jq_id, pid). Used by both the endpoint and the Run-all orchestrator
    so every domain appears as its own job_queue row.
    """
    from app.api.queue_api import _broadcast
    from app.services.background_processes import bp_start
    from sqlalchemy import text as _t

    now = datetime.utcnow()
    async with AsyncSessionLocal() as _db:
        result = await _db.execute(
            _t("INSERT INTO job_queue (job_type, label, status, queue_position, "
               "progress_current, progress_total, payload, created_at) "
               "VALUES (:jt, :lbl, 'running', 0, 0, :tot, '{}', :now)"),
            {"jt": job_type, "lbl": label, "tot": total, "now": now},
        )
        await _db.commit()
        jq_id = result.lastrowid
    await _broadcast()
    # Pass B Phase 2 dual-write: mirror the job_queue row's shape onto the bp
    # twin (label, payload='{}', queue_position=0, created_at=same now). No
    # job_queue write changes; nothing reads these bp columns yet.
    pid = await bp_start(
        job_type, progress_total=total, detail=label,
        label=label, payload="{}", queue_position=0, created_at=now,
    )
    return jq_id, pid


async def _run_backfill_all_task() -> None:
    """
    Run-all orchestrator (M15): runs each domain sequentially as its OWN job —
    first id_notes, then a single combined draft job (taste/medicinal/recipe) —
    via chained awaits (never concurrently). Holds the global lock for the whole
    sequence and releases it once, at the end.
    """
    global _draft_backfill_job
    from sqlalchemy import text as _t
    try:
        # 1. id_notes
        async with AsyncSessionLocal() as _db:
            id_total = (await _db.execute(_t(_ID_NOTES_OUTSTANDING_SQL))).scalar() or 0
        if id_total:
            jq_id, pid = await _create_backfill_job(
                "ai_draft_backfill_id_notes", f"Backfill ID notes ({id_total} species)", id_total)
            await _run_id_notes_backfill_task(jq_id, pid, manage_lock=False)

        # 2. combined draft fields (taste/medicinal/recipe) — one pass per species
        async with AsyncSessionLocal() as _db:
            targets = await _collect_backfill_targets(_db)
        if targets:
            jq_id, pid = await _create_backfill_job(
                "ai_draft_backfill", f"AI draft backfill ({len(targets)} species)", len(targets))
            await _run_draft_backfill_task(jq_id, pid, targets, field=None, manage_lock=False)
    except Exception as exc:
        log.error("[backfill-all] Fatal error: %s", exc)
    finally:
        _draft_backfill_job = None


@router.post("/api/drafts/backfill")
async def start_draft_backfill(
    background_tasks: BackgroundTasks,
    field: Optional[str] = Query(default=None),
    identity: Identity = Depends(get_identity),
):
    """
    Backfill AI drafts.

    ?field=<domain> runs one domain only. Valid domains:
        identification_notes, taste_notes, recipe, medicinal_notes.
    ?field=all runs every domain sequentially as separate jobs (orchestrated).
    ?field omitted runs the combined taste/medicinal/recipe backfill (all eligible).

    edibility_status is intentionally NOT a domain — it is authoritative-source
    only and never AI-generated.
    """
    if identity.is_guest:
        raise HTTPException(403, "Curator only")
    global _draft_backfill_job
    from sqlalchemy import text

    if _draft_backfill_job and _draft_backfill_job.get("status") == "running":
        raise HTTPException(409, detail="A backfill job is already running")

    # Run all → orchestrator (single background task, sequential sub-jobs)
    if field == "all":
        _draft_backfill_job = {"status": "running"}
        background_tasks.add_task(_run_backfill_all_task)
        log.info("[draft-backfill] Run-all started")
        return {"ok": True, "status": "started", "field": "all"}

    if field == "identification_notes":
        async with AsyncSessionLocal() as _db:
            total = (await _db.execute(text(_ID_NOTES_OUTSTANDING_SQL))).scalar() or 0
        if total == 0:
            return {"ok": True, "status": "nothing_to_do", "count": 0}
        jq_id, pid = await _create_backfill_job(
            "ai_draft_backfill_id_notes", f"Backfill ID notes ({total} species)", total)
        _draft_backfill_job = {"status": "running", "jq_id": jq_id, "pid": pid}
        background_tasks.add_task(_run_id_notes_backfill_task, jq_id, pid)
        return {"ok": True, "status": "started", "field": field, "count": total, "job_queue_id": jq_id}

    if field in _DRAFT_FIELD_DOMAINS or field is None:
        async with AsyncSessionLocal() as _read_db:
            targets = await _collect_backfill_targets(_read_db, field)

        if not targets:
            return {"ok": True, "status": "nothing_to_do", "count": 0,
                    "message": "All eligible species already have drafts for this domain"}

        total = len(targets)
        lbl   = f"Backfill {field} ({total} species)" if field else f"AI draft backfill ({total} species)"
        jq_id, pid = await _create_backfill_job("ai_draft_backfill", lbl, total)
        _draft_backfill_job = {"status": "running", "jq_id": jq_id, "pid": pid}
        background_tasks.add_task(_run_draft_backfill_task, jq_id, pid, targets, field)
        log.info("[draft-backfill] Started: field=%s %d species, jq_id=%d, pid=%s", field, total, jq_id, pid)
        return {"ok": True, "status": "started", "field": field, "count": total, "job_queue_id": jq_id}

    raise HTTPException(400, detail=f"Unknown backfill field: {field!r}")
