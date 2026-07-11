"""
Conditional Edibility API — Phase 10.6 / Phase 12

Endpoints for the Edibility curation tab in /review and the species card gating.

GET   /api/edibility/review-queue              — enriched unknown-edibility queue (Edibility Review tab)
GET   /api/edibility/species                   — species needing conditional detail
GET   /api/edibility/conditions/{species_id}   — conditions for one species
POST  /api/edibility/conditions                — add a condition row
DELETE /api/edibility/conditions/{id}          — remove a condition row
GET   /api/edibility/lookalikes/{species_id}   — all lookalikes (bidirectional)
POST  /api/edibility/lookalikes                — add a lookalike row
DELETE /api/edibility/lookalikes/{id}          — remove a lookalike row
GET   /api/edibility/summary/{species_id}      — full gating summary for species card
PATCH /api/edibility/phenology/{species_id}    — set phenological month data
PATCH /api/edibility/bulk-status               — bulk status update (multi-select confirm)
"""
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.culinary import CulinaryInfo
from app.models.observation import Observation
from app.models.species import Species, SpeciesEdibilityCondition, SpeciesLookalike, SpeciesEdibilityHistory

log = logging.getLogger(__name__)

router = APIRouter(tags=["edibility"])

# A6 — edibility statuses a curator may assign.
_VALID_EDIBILITY = {"edible", "caution", "toxic", "inedible", "unknown"}
_UNKNOWN_STATES = ["unknown", "unclear"]

# Severity ladder for the human-only-relax guard (RULE 2). 'inedible' sits at
# the toxic end (level 2). 'unknown'/'unclear'/NULL are NOT on the ladder —
# they mean "no established verdict" (severity None).
_EDIBILITY_SEVERITY = {"edible": 0, "caution": 1, "toxic": 2, "inedible": 2}


def _edibility_severity(status: Optional[str]) -> Optional[int]:
    """Severity level of a status, or None when it is not an established verdict."""
    return _EDIBILITY_SEVERITY.get((status or "").strip().lower())


def _enforce_edibility_write_rules(old_status: Optional[str], new_status: str,
                                   verified: Optional[bool], changed_by: Optional[str]) -> None:
    """
    Server-side safety gate applied to EVERY species.edibility_status write —
    the PATCH endpoint and /bulk-status both call this identically, so the bulk
    path is not a coupling/relax bypass. Raises HTTPException(400) on violation;
    returns None when the write is permitted. Enforced regardless of frontend.

    RULE 1 — COUPLING: a write that sets edibility_status to 'toxic' or 'caution'
    MUST carry verified=True. The review queue surfaces caution+unverified but
    NEVER toxic+unverified (see edibility.py:88-93), so an uncoupled toxic write
    is a deadly verdict nothing flags. A status-only (verified=None) or
    verified=False write to toxic/caution is rejected.

    RULE 2 — HUMAN-ONLY RELAX (model b): severity edible(0) < caution(1) <
    toxic/inedible(2); unknown/unclear/NULL = no verdict. Moving an EXISTING
    established verdict to a strictly LOWER severity (a relax) must be
    changed_by='human'. A tighten (>= severity) is allowed for any caller.
    Populating a no-verdict state (prior is NULL/unknown/unclear) is allowed for
    any caller — it is not a relax (still subject to RULE 1).
    NOTE (flagged, deliberate per the letter of model b): clearing an
    established verdict TO unknown/unclear is off-ladder, so it is NOT treated
    as a relax here — such a species simply re-enters the unknown review queue
    rather than silently dropping its warning.
    """
    new_norm = (new_status or "").strip().lower()

    # RULE 1 — coupling
    if new_norm in ("toxic", "caution") and verified is not True:
        raise HTTPException(
            400,
            detail="toxic/caution edibility changes must go through the confirm-and-verify path (verified=True required)",
        )

    # RULE 2 — human-only relax
    old_sev = _edibility_severity(old_status)
    new_sev = _edibility_severity(new_norm)
    if old_sev is not None and new_sev is not None and new_sev < old_sev:
        if (changed_by or "").strip().lower() != "human":
            raise HTTPException(
                400,
                detail=(
                    f"relaxing an established '{old_status}' verdict to '{new_norm}' "
                    "must be done by a human curator (changed_by='human')"
                ),
            )

# Guards against overlapping background rescans.
_rescan_state: dict = {"running": False, "queued": 0, "done": 0, "resolved": 0}

# Phrases in PFAF preparation_warnings that strongly suggest toxicity.
_TOXIC_PHRASES = (
    "toxic", "poisonous", "not safe", "not edible", "do not eat",
    "harmful", "narcotic", "carcinogen", "avoid",
)


def _suggest_status(sp: Species, ci: Optional[CulinaryInfo]) -> Optional[str]:
    """
    Derive a suggested edibility status from PFAF data only.
    Returns "toxic" when PFAF warnings contain strong toxicity language.
    Returns None when there is no strong signal — human must decide.
    NEVER returns "edible"; edible is always a human tap.
    """
    if ci is None:
        return None
    warnings = (ci.preparation_warnings or "").lower()
    if any(phrase in warnings for phrase in _TOXIC_PHRASES):
        return "toxic"
    return None


# ---------------------------------------------------------------------------
# GET /api/edibility/review-queue
# Enriched unknown-edibility queue for the Edibility Review tab.
# Sorted by PFAF confidence desc so easy confirms are at the top.
# ---------------------------------------------------------------------------

@router.get("/api/edibility/review-queue")
async def edibility_review_queue(db: AsyncSession = Depends(get_db)):
    """
    Returns confirmed species whose edibility_status is null or unknown,
    enriched with PFAF culinary context and a machine-suggested status.

    Sorted: by edibility_confidence DESC (high-confidence quick confirms first),
    then alphabetically.

    suggested_status: "toxic" when PFAF warnings contain toxicity language;
    null otherwise. Edible is NEVER auto-suggested — always a human tap.
    """
    # Confirmed observation counts per species
    count_map = await _confirmed_obs_counts(db)

    # All unknown/null species + unverified caution (PFAF backfill)
    stmt = (
        select(Species)
        .where(
            or_(
                Species.edibility_status.is_(None),
                Species.edibility_status.in_(_UNKNOWN_STATES),
                and_(Species.edibility_status == "caution", Species.edibility_verified == False),
            )
        )
        .order_by(
            Species.edibility_confidence.desc().nullslast(),
            Species.scientific_name,
        )
    )
    species_rows = (await db.execute(stmt)).scalars().all()

    # Filter to confirmed only
    species_rows = [sp for sp in species_rows if count_map.get(sp.id, 0) > 0]

    if not species_rows:
        return []

    sp_ids = [sp.id for sp in species_rows]

    # Bulk-fetch culinary_info
    ci_rows = (await db.execute(
        select(CulinaryInfo).where(CulinaryInfo.species_id.in_(sp_ids))
    )).scalars().all()
    ci_map = {ci.species_id: ci for ci in ci_rows}

    # Bulk-fetch thumbnails (one per species — most recent confirmed obs)
    thumb_rows = (await db.execute(
        select(Observation.id, Observation.species_id, Observation.thumbnail_path)
        .where(Observation.species_id.in_(sp_ids))
        .where(Observation.review_status.in_(["approved", "manually_verified"]))
        .where(Observation.thumbnail_path.is_not(None))
        .order_by(Observation.photo_taken_at.desc().nullslast())
    )).all()
    thumb_map: dict = {}  # species_id → (obs_id, thumbnail_path)
    for oid, sid, tp in thumb_rows:
        if sid not in thumb_map:
            thumb_map[sid] = (oid, tp)

    import json as _json
    result = []
    for sp in species_rows:
        ci = ci_map.get(sp.id)
        common_names: list = []
        try:
            common_names = _json.loads(sp.common_names or "[]") or []
        except Exception:
            pass

        result.append({
            "id":                 sp.id,
            "scientific_name":    sp.scientific_name,
            "common_name":        sp.preferred_common_name or (common_names[0] if common_names else None),
            "family":             sp.family,
            "edibility_status":   sp.edibility_status or "unknown",
            "edibility_confidence": sp.edibility_confidence,  # PFAF rating/5 or None
            "observation_count":  count_map.get(sp.id, 0),
            "thumbnail":          thumb_map[sp.id][1] if sp.id in thumb_map else None,
            "thumbnail_obs_id":   thumb_map[sp.id][0] if sp.id in thumb_map else None,
            # PFAF context — read-only, shown to help the curator decide
            "edible_parts":       ci.edible_parts if ci else None,
            "preparation_warnings": ci.preparation_warnings if ci else None,
            "look_alike_warnings":  ci.look_alike_warnings if ci else None,
            "traditional_uses":     ci.traditional_uses if ci else None,
            # Suggested status: toxic if PFAF warns; None = no suggestion
            "suggested_status":   _suggest_status(sp, ci),
            "has_pfaf":           bool(ci and ci.pfaf_retrieved_at),
        })

    return result

# ---------------------------------------------------------------------------
# Pydantic request models
# ---------------------------------------------------------------------------

class ConditionIn(BaseModel):
    species_id: int
    part: str           # leaf|berry|shoot|root|flower|whole|other
    preparation: str    # raw|cooked|dried|tinctured|any
    season: str = "any" # spring|summer|autumn|winter|any
    safe: bool
    notes: Optional[str] = None


class LookalikeIn(BaseModel):
    species_id: int
    lookalike_species_id: Optional[int] = None
    lookalike_name: str
    distinguishing_notes: Optional[str] = None
    toxicity_level: str = "caution"  # safe|caution|toxic|deadly


# ---------------------------------------------------------------------------
# GET /api/edibility/species
# Lists species where edibility_status is actionable (not unknown/toxic/inedible)
# — these need conditional detail populated. Sorted: zero conditions+lookalikes first.
# ---------------------------------------------------------------------------

@router.get("/api/edibility/species")
async def list_edibility_species(db: AsyncSession = Depends(get_db)):
    """
    Return all species where edibility_status is 'edible' or 'caution'
    — the ones that need conditional detail. Includes condition count and
    lookalike count. Sorted: zero conditions+zero lookalikes first.
    """
    # Condition counts per species
    cond_counts = (
        await db.execute(
            select(
                SpeciesEdibilityCondition.species_id,
                func.count(SpeciesEdibilityCondition.id).label("cond_count"),
            ).group_by(SpeciesEdibilityCondition.species_id)
        )
    ).all()
    cond_map = {row.species_id: row.cond_count for row in cond_counts}

    # Lookalike counts per species (species_id side only — curators set the primary)
    look_counts = (
        await db.execute(
            select(
                SpeciesLookalike.species_id,
                func.count(SpeciesLookalike.id).label("look_count"),
            ).group_by(SpeciesLookalike.species_id)
        )
    ).all()
    look_map = {row.species_id: row.look_count for row in look_counts}

    # Species that need curation
    stmt = select(Species).where(
        Species.edibility_status.in_(["edible", "caution"])
    ).order_by(Species.scientific_name)
    rows = (await db.execute(stmt)).scalars().all()

    # Bulk thumbnail: most recent confirmed-obs thumbnail per species
    sp_ids = [sp.id for sp in rows]
    thumb_map: dict = {}
    if sp_ids:
        thumb_rows = (await db.execute(
            select(Observation.species_id, Observation.thumbnail_path)
            .where(Observation.species_id.in_(sp_ids))
            .where(Observation.review_status.in_(["approved", "manually_verified"]))
            .where(Observation.thumbnail_path.is_not(None))
            .order_by(Observation.photo_taken_at.desc().nullslast())
        )).all()
        for sid, tp in thumb_rows:
            if sid not in thumb_map:
                thumb_map[sid] = tp

    result = []
    for sp in rows:
        cc = cond_map.get(sp.id, 0)
        lc = look_map.get(sp.id, 0)
        result.append({
            "id": sp.id,
            "scientific_name": sp.scientific_name,
            "preferred_common_name": sp.preferred_common_name,
            "edibility_status": sp.edibility_status,
            "edibility_verified": sp.edibility_verified,
            "condition_count": cc,
            "lookalike_count": lc,
            "priority": 0 if (cc == 0 and lc == 0) else 1,
            "thumbnail": thumb_map.get(sp.id),
        })

    # Zero conditions+lookalikes first
    result.sort(key=lambda x: (x["priority"], x["scientific_name"]))
    return result


# ---------------------------------------------------------------------------
# A6 — Unknown-edibility queue, status correction, and rescan
# ---------------------------------------------------------------------------

class EdibilityStatusIn(BaseModel):
    edibility_status: str           # edible|caution|toxic|inedible|unknown
    verified: Optional[bool] = None  # None = leave edibility_verified/verified_by untouched (status-only write)
    note: Optional[str] = None       # optional curator note, logged to species_edibility_history
    changed_by: str                  # REQUIRED caller identity — gates RULE 2 (human-only relax) and
                                     # stamps the history row. No default: an omitted value is a 422,
                                     # never a silent "human". Every caller (species.html dialog,
                                     # review.html per-card + bulk) sends changed_by:'human' explicitly.


async def _confirmed_obs_counts(db: AsyncSession) -> dict:
    rows = (await db.execute(
        select(Observation.species_id, func.count(Observation.id).label("n"))
        .where(Observation.species_id.is_not(None))
        .where(Observation.review_status.in_(["approved", "manually_verified"]))
        .group_by(Observation.species_id)
    )).all()
    return {r.species_id: r.n for r in rows}


@router.get("/api/edibility/unknown")
async def list_unknown_edibility(db: AsyncSession = Depends(get_db)):
    """
    Species whose edibility is still unknown (null/'unknown'/'unclear') AND that
    have at least one confirmed observation — the actionable triage queue.
    """
    count_map = await _confirmed_obs_counts(db)
    stmt = select(Species).where(
        or_(
            Species.edibility_status.is_(None),
            Species.edibility_status.in_(_UNKNOWN_STATES),
        )
    ).order_by(Species.scientific_name)
    rows = (await db.execute(stmt)).scalars().all()

    # Bulk thumbnail: most recent confirmed-obs thumbnail per species
    sp_ids_unk = [sp.id for sp in rows]
    thumb_map_unk: dict = {}
    if sp_ids_unk:
        thumb_rows_unk = (await db.execute(
            select(Observation.species_id, Observation.thumbnail_path)
            .where(Observation.species_id.in_(sp_ids_unk))
            .where(Observation.review_status.in_(["approved", "manually_verified"]))
            .where(Observation.thumbnail_path.is_not(None))
            .order_by(Observation.photo_taken_at.desc().nullslast())
        )).all()
        for sid, tp in thumb_rows_unk:
            if sid not in thumb_map_unk:
                thumb_map_unk[sid] = tp

    result = []
    for sp in rows:
        n = count_map.get(sp.id, 0)
        if n == 0:
            continue
        result.append({
            "id": sp.id,
            "scientific_name": sp.scientific_name,
            "preferred_common_name": sp.preferred_common_name,
            "edibility_status": sp.edibility_status or "unknown",
            "observation_count": n,
            "thumbnail": thumb_map_unk.get(sp.id),
        })
    return result


class BulkEdibilityIn(BaseModel):
    updates: List[dict]  # [{species_id: int, edibility_status: str}]


@router.patch("/api/edibility/bulk-status")
async def bulk_set_edibility_status(
    payload: BulkEdibilityIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Set edibility_status + edibility_verified for multiple species at once.
    Used by the Edibility Review tab's "Confirm all suggested" bulk action.
    Silently skips invalid species_ids. Returns count of rows updated.
    After commit, fires AI draft generation for each confirmed (non-toxic) species.
    Logs one species_edibility_history row per update (changed_by from the item,
    default 'human'; note=None). Each item passes the shared safety gate
    (_enforce_edibility_write_rules) identically to the PATCH endpoint — a
    RULE 1/RULE 2 violation is surfaced in errors[] and that item is skipped,
    so /bulk-status is not a coupling/relax bypass.
    """
    from app.services.enrichment import trigger_ai_drafts_for_species

    updated = 0
    errors = []
    confirmed_names: list[str] = []
    _NO_DRAFT = ("toxic", "inedible", "not_edible")
    for item in payload.updates:
        try:
            sid = int(item["species_id"])
            status = str(item["edibility_status"]).strip().lower()
        except (KeyError, ValueError, TypeError):
            errors.append(f"Bad item: {item!r}")
            continue
        if status not in _VALID_EDIBILITY:
            errors.append(f"Invalid status {status!r} for species_id {sid}")
            continue
        sp = await db.scalar(select(Species).where(Species.id == sid))
        if sp is None:
            continue
        old_status = sp.edibility_status
        # changed_by is REQUIRED per item — no silent "human" default (mirrors
        # EdibilityStatusIn making it mandatory). A missing/blank value is
        # collected into errors[] and the item is skipped, not defaulted.
        changed_by = str(item.get("changed_by", "")).strip()
        if not changed_by:
            errors.append(f"species_id {sid}: changed_by required (no default)")
            continue
        # bulk always couples verified (status != "unknown"), so this is the
        # effective verified value the guard must see. Same helper as the PATCH
        # path — a rule violation here is surfaced via errors[] (bulk's existing
        # skip-and-collect contract) and the offending item is not written, so
        # /bulk-status is not a coupling/relax bypass.
        try:
            _enforce_edibility_write_rules(old_status, status, status != "unknown", changed_by)
        except HTTPException as e:
            errors.append(f"species_id {sid}: {e.detail}")
            continue
        sp.edibility_status = status
        sp.edibility_verified = status != "unknown"
        sp.edibility_verified_by = "human" if status != "unknown" else None
        db.add(SpeciesEdibilityHistory(
            species_id=sid,
            field="edibility_status",
            old_value=old_status,
            new_value=status,
            changed_by=changed_by,
            note=None,
        ))
        updated += 1
        if status not in _NO_DRAFT and status not in _UNKNOWN_STATES:
            confirmed_names.append(sp.scientific_name)
    await db.commit()
    for name in confirmed_names:
        background_tasks.add_task(trigger_ai_drafts_for_species, name)
    return {"ok": True, "updated": updated, "errors": errors}


@router.patch("/api/edibility/status/{species_id}")
async def set_edibility_status(
    species_id: int,
    payload: EdibilityStatusIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    A6 — persist a curator's edibility-status correction.

    verified is optional: None means a status-only write that leaves
    edibility_verified/edibility_verified_by exactly as they already were
    (added for the species-card status dialog's status-only path — 'edible'/
    'inedible'/'unknown'). When verified is explicitly True/False (the
    existing review.html caller always sends True), it's written together
    with status, same coupled behaviour as before.

    Every write is logged to species_edibility_history (old_value/new_value
    on edibility_status), then re-read from the DB via db.refresh() — not
    the in-memory object — to confirm the write actually persisted before
    reporting success. A 500 here means don't trust the response; it does
    NOT mean "probably fine".

    After commit, fires AI draft generation if the new status is confirmed edible/caution.
    """
    from app.services.enrichment import trigger_ai_drafts_for_species

    status = (payload.edibility_status or "").strip().lower()
    if status not in _VALID_EDIBILITY:
        raise HTTPException(422, detail=f"edibility_status must be one of {sorted(_VALID_EDIBILITY)}")

    sp = await db.scalar(select(Species).where(Species.id == species_id))
    if not sp:
        raise HTTPException(404, detail="Species not found")

    old_status = sp.edibility_status

    # Server-side safety gate (RULE 1 coupling + RULE 2 human-only relax) — same
    # helper as /bulk-status, so neither path is a bypass. Raises 400 on violation.
    _enforce_edibility_write_rules(old_status, status, payload.verified, payload.changed_by)

    sp.edibility_status = status
    # verified is None -> status-only write; leave edibility_verified/_by untouched.
    if payload.verified is not None:
        sp.edibility_verified = bool(payload.verified) and status != "unknown"
        sp.edibility_verified_by = "human" if sp.edibility_verified else None

    db.add(SpeciesEdibilityHistory(
        species_id=species_id,
        field="edibility_status",
        old_value=old_status,
        new_value=status,
        changed_by=payload.changed_by,
        note=payload.note,
    ))

    scientific_name = sp.scientific_name
    await db.commit()

    # Loud-fail on an unconfirmed write.
    await db.refresh(sp)
    if sp.edibility_status != status:
        raise HTTPException(
            status_code=500,
            detail=f"Write did not persist: expected edibility_status={status!r}, found {sp.edibility_status!r}",
        )

    # Fire-and-forget: generate AI drafts when edibility is confirmed as non-toxic
    _NO_DRAFT = ("toxic", "inedible", "not_edible")
    if status not in _NO_DRAFT and status not in _UNKNOWN_STATES:
        background_tasks.add_task(trigger_ai_drafts_for_species, scientific_name)

    return {
        "ok": True,
        "species_id": species_id,
        "scientific_name": scientific_name,
        "edibility_status": sp.edibility_status,
        "edibility_verified": sp.edibility_verified,
        # Tells the UI to drop the card from the unknown queue.
        "still_unknown": status in _UNKNOWN_STATES,
    }


async def _rescan_unknown_worker(species_ids: list[int]) -> None:
    """Background: re-run enrichment for each unknown species (sets edibility
    from PFAF where available). Sequential — respects enrichment rate limits."""
    from app.database import AsyncSessionLocal
    from app.services.enrichment import enrich_species as _enrich

    _rescan_state.update(running=True, queued=len(species_ids), done=0, resolved=0)
    try:
        for sid in species_ids:
            try:
                async with AsyncSessionLocal() as session:
                    sp = await session.scalar(select(Species).where(Species.id == sid))
                    if not sp:
                        continue
                    before = sp.edibility_status
                    await _enrich(
                        session=session, species=sp, dry_run=False,
                        re_enrich=True, fill_empty_only=True, protected_fields=set(),
                    )
                    await session.commit()
                    if sp.edibility_status and sp.edibility_status not in _UNKNOWN_STATES and sp.edibility_status != before:
                        _rescan_state["resolved"] += 1
            except Exception as e:  # noqa: BLE001 — one bad species must not stop the batch
                log.warning("[edibility rescan] species %s failed: %s", sid, e)
            finally:
                _rescan_state["done"] += 1
    finally:
        _rescan_state["running"] = False
        log.info("[edibility rescan] complete: %s/%s processed, %s resolved",
                 _rescan_state["done"], _rescan_state["queued"], _rescan_state["resolved"])


@router.get("/api/edibility/rescan-status")
async def rescan_status():
    """Poll the background rescan progress."""
    return dict(_rescan_state)


@router.post("/api/edibility/rescan")
async def rescan_unknown_edibility(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    A6 — re-run edibility assessment (PFAF/Wikidata enrichment) for every unknown
    species that has confirmed observations. Runs in the background; poll
    /api/edibility/rescan-status. Returns the number queued.
    """
    if _rescan_state.get("running"):
        raise HTTPException(409, detail="A rescan is already running")

    count_map = await _confirmed_obs_counts(db)
    rows = (await db.execute(
        select(Species.id).where(
            or_(
                Species.edibility_status.is_(None),
                Species.edibility_status.in_(_UNKNOWN_STATES),
            )
        )
    )).scalars().all()
    species_ids = [sid for sid in rows if count_map.get(sid, 0) > 0]

    if not species_ids:
        return {"ok": True, "queued": 0, "message": "No unknown species with confirmed observations."}

    background_tasks.add_task(_rescan_unknown_worker, species_ids)
    return {"ok": True, "queued": len(species_ids), "message": f"Rescanning {len(species_ids)} species in the background."}


# ---------------------------------------------------------------------------
# GET /api/edibility/conditions/{species_id}
# ---------------------------------------------------------------------------

@router.get("/api/edibility/conditions/{species_id}")
async def get_conditions(species_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(SpeciesEdibilityCondition).where(
        SpeciesEdibilityCondition.species_id == species_id
    ).order_by(SpeciesEdibilityCondition.part, SpeciesEdibilityCondition.preparation)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "part": r.part,
            "preparation": r.preparation,
            "season": r.season,
            "safe": r.safe,
            "notes": r.notes,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# POST /api/edibility/conditions
# ---------------------------------------------------------------------------

@router.post("/api/edibility/conditions", status_code=201)
async def add_condition(payload: ConditionIn, db: AsyncSession = Depends(get_db)):
    # Validate species exists
    sp = (await db.execute(select(Species).where(Species.id == payload.species_id))).scalar_one_or_none()
    if not sp:
        raise HTTPException(404, "Species not found")

    # Validate enum values
    valid_parts = {"leaf", "berry", "shoot", "root", "flower", "whole", "other"}
    valid_preps = {"raw", "cooked", "dried", "tinctured", "any"}
    valid_seasons = {"spring", "summer", "autumn", "winter", "any"}
    if payload.part not in valid_parts:
        raise HTTPException(400, f"Invalid part. Must be one of: {sorted(valid_parts)}")
    if payload.preparation not in valid_preps:
        raise HTTPException(400, f"Invalid preparation. Must be one of: {sorted(valid_preps)}")
    if payload.season not in valid_seasons:
        raise HTTPException(400, f"Invalid season. Must be one of: {sorted(valid_seasons)}")

    cond = SpeciesEdibilityCondition(
        species_id=payload.species_id,
        part=payload.part,
        preparation=payload.preparation,
        season=payload.season,
        safe=payload.safe,
        notes=payload.notes,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(cond)
    await db.commit()
    await db.refresh(cond)
    return {"id": cond.id, "ok": True}


# ---------------------------------------------------------------------------
# DELETE /api/edibility/conditions/{condition_id}
# ---------------------------------------------------------------------------

@router.delete("/api/edibility/conditions/{condition_id}")
async def delete_condition(condition_id: int, db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(
            select(SpeciesEdibilityCondition).where(SpeciesEdibilityCondition.id == condition_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Condition not found")
    await db.delete(row)
    await db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# GET /api/edibility/lookalikes/{species_id}
# Bidirectional: returns rows where species_id = X  OR lookalike_species_id = X
# ---------------------------------------------------------------------------

@router.get("/api/edibility/lookalikes/{species_id}")
async def get_lookalikes(species_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(SpeciesLookalike).where(
        or_(
            SpeciesLookalike.species_id == species_id,
            SpeciesLookalike.lookalike_species_id == species_id,
        )
    ).order_by(SpeciesLookalike.toxicity_level.desc(), SpeciesLookalike.lookalike_name)
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "id": r.id,
            "species_id": r.species_id,
            "lookalike_species_id": r.lookalike_species_id,
            "lookalike_name": r.lookalike_name,
            "distinguishing_notes": r.distinguishing_notes,
            "toxicity_level": r.toxicity_level,
            "direction": "outgoing" if r.species_id == species_id else "incoming",
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# POST /api/edibility/lookalikes
# ---------------------------------------------------------------------------

@router.post("/api/edibility/lookalikes", status_code=201)
async def add_lookalike(payload: LookalikeIn, db: AsyncSession = Depends(get_db)):
    sp = (await db.execute(select(Species).where(Species.id == payload.species_id))).scalar_one_or_none()
    if not sp:
        raise HTTPException(404, "Species not found")

    valid_toxicity = {"safe", "caution", "toxic", "deadly"}
    if payload.toxicity_level not in valid_toxicity:
        raise HTTPException(400, f"Invalid toxicity_level. Must be one of: {sorted(valid_toxicity)}")

    if not payload.lookalike_name.strip():
        raise HTTPException(400, "lookalike_name is required")

    # If lookalike_species_id given, validate it
    if payload.lookalike_species_id is not None:
        lsp = (await db.execute(select(Species).where(Species.id == payload.lookalike_species_id))).scalar_one_or_none()
        if not lsp:
            raise HTTPException(404, "Lookalike species not found in DB")

    row = SpeciesLookalike(
        species_id=payload.species_id,
        lookalike_species_id=payload.lookalike_species_id,
        lookalike_name=payload.lookalike_name.strip(),
        distinguishing_notes=payload.distinguishing_notes,
        toxicity_level=payload.toxicity_level,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": row.id, "ok": True}


# ---------------------------------------------------------------------------
# DELETE /api/edibility/lookalikes/{lookalike_id}
# ---------------------------------------------------------------------------

@router.delete("/api/edibility/lookalikes/{lookalike_id}")
async def delete_lookalike(lookalike_id: int, db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(
            select(SpeciesLookalike).where(SpeciesLookalike.id == lookalike_id)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Lookalike not found")
    await db.delete(row)
    await db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# GET /api/edibility/summary/{species_id}
# Full gating summary consumed by the species card (Section 4)
# ---------------------------------------------------------------------------

@router.get("/api/edibility/summary/{species_id}")
async def get_edibility_summary(species_id: int, db: AsyncSession = Depends(get_db)):
    """
    Returns conditions list + lookalikes list + a gating flag.
    gating: 'conditional' if any safe=False condition exists
             'all_safe'    if conditions exist and all safe=True
             'no_detail'   if no conditions at all
    """
    sp = (await db.execute(select(Species).where(Species.id == species_id))).scalar_one_or_none()
    if not sp:
        raise HTTPException(404, "Species not found")

    conds_stmt = select(SpeciesEdibilityCondition).where(
        SpeciesEdibilityCondition.species_id == species_id
    )
    conds = (await db.execute(conds_stmt)).scalars().all()

    looks_stmt = select(SpeciesLookalike).where(
        or_(
            SpeciesLookalike.species_id == species_id,
            SpeciesLookalike.lookalike_species_id == species_id,
        )
    )
    looks = (await db.execute(looks_stmt)).scalars().all()

    if not conds:
        gating = "no_detail"
    elif any(not c.safe for c in conds):
        gating = "conditional"
    else:
        gating = "all_safe"

    return {
        "species_id": species_id,
        "edibility_status": sp.edibility_status,
        "gating": gating,
        "conditions": [
            {
                "id": c.id,
                "part": c.part,
                "preparation": c.preparation,
                "season": c.season,
                "safe": c.safe,
                "notes": c.notes,
            }
            for c in conds
        ],
        "lookalikes": [
            {
                "id": l.id,
                "lookalike_name": l.lookalike_name,
                "distinguishing_notes": l.distinguishing_notes,
                "toxicity_level": l.toxicity_level,
            }
            for l in looks
        ],
    }


# ---------------------------------------------------------------------------
# PATCH /api/edibility/phenology/{species_id}
# Set phenological month data for a species (curator-only, not AI-generated)
# ---------------------------------------------------------------------------

class PhenologyIn(BaseModel):
    flower_months: Optional[str] = None  # CSV "3,4,5,6" or null to clear
    fruit_months:  Optional[str] = None
    leaf_months:   Optional[str] = None
    peak_season:   Optional[str] = None


@router.patch("/api/edibility/phenology/{species_id}")
async def set_phenology(species_id: int, payload: PhenologyIn, db: AsyncSession = Depends(get_db)):
    """
    Set or update phenological month data for a species.
    Pass null for a field to clear it. Months validated as CSV of 1–12.
    """
    from app.services.phenology import parse_months, months_to_csv

    sp = (await db.execute(select(Species).where(Species.id == species_id))).scalar_one_or_none()
    if not sp:
        raise HTTPException(404, "Species not found")

    def _clean_months(csv: Optional[str]) -> Optional[str]:
        """Validate and normalise a months CSV; raises 400 on bad input."""
        if csv is None:
            return None  # explicit null → clear the field
        parsed = parse_months(csv)
        if not parsed and csv.strip():
            raise HTTPException(400, f"Invalid months value: {csv!r}. Use CSV of 1–12, e.g. '3,4,5,6'")
        return months_to_csv(list(parsed))  # normalised sorted CSV, or None

    if payload.flower_months is not None or "flower_months" in payload.model_fields_set:
        sp.flower_months = _clean_months(payload.flower_months)
    if payload.fruit_months is not None or "fruit_months" in payload.model_fields_set:
        sp.fruit_months = _clean_months(payload.fruit_months)
    if payload.leaf_months is not None or "leaf_months" in payload.model_fields_set:
        sp.leaf_months = _clean_months(payload.leaf_months)
    if payload.peak_season is not None or "peak_season" in payload.model_fields_set:
        sp.peak_season = payload.peak_season or None

    await db.commit()

    from app.services.phenology import active_months_display
    return {
        "ok": True,
        "species_id": species_id,
        "flower_months": sp.flower_months,
        "fruit_months":  sp.fruit_months,
        "leaf_months":   sp.leaf_months,
        "peak_season":   sp.peak_season,
        "phenology":     active_months_display(sp.flower_months, sp.fruit_months, sp.leaf_months),
    }
