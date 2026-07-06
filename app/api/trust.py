"""
Data Trust & Bulk Correction API — Phase 10.5

Endpoints:
  GET  /api/trust/stats                  — Section A stat chips
  GET  /api/trust/confidence-review      — Section B paginated review queue
  POST /api/trust/bulk-send-to-review    — Section C Tool 1
  POST /api/trust/bulk-reassign          — Section C Tool 2
  POST /api/trust/kingdom-audit          — retroactive non-plant/fungi kingdom scan

All write endpoints write ObservationEdit rows — no silent mutations.
"""

import asyncio
import json as _json
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func, or_, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.observation import Observation, ObservationEdit
from app.models.species import Species, SpeciesAIDraft
from app.models.culinary import CulinaryInfo
from app.services.write_lock import db_write_lock

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trust", tags=["trust"])


# ---------------------------------------------------------------------------
# GET /api/trust/stats  — Section A chips + distribution
# ---------------------------------------------------------------------------

def _bucket_scores(scores) -> dict:
    """Bin a list of 0–1 confidence scores into display bands."""
    dist = {"lt60": 0, "60_70": 0, "70_80": 0, "80_90": 0, "gte90": 0}
    for s in scores:
        if s < 0.60:   dist["lt60"]   += 1
        elif s < 0.70: dist["60_70"]  += 1
        elif s < 0.80: dist["70_80"]  += 1
        elif s < 0.90: dist["80_90"]  += 1
        else:          dist["gte90"]  += 1
    return dist


@router.get("/stats")
async def trust_stats(db: AsyncSession = Depends(get_db)):
    """Return confidence dashboard stats and per-category distributions for Section A."""

    # Total approved
    total_approved = await db.scalar(
        select(func.count(Observation.id))
        .where(Observation.review_status.in_(["approved", "manually_verified"]))
    ) or 0

    # Auto-approved: pipeline-approved, not subsequently human-corrected
    auto_approved = await db.scalar(
        select(func.count(Observation.id))
        .where(Observation.review_status == "approved")
        .where(Observation.human_corrected.is_(False))
    ) or 0

    # Manually confirmed: review_status='manually_verified' — always human-confirmed
    manually_verified_count = await db.scalar(
        select(func.count(Observation.id))
        .where(Observation.review_status == "manually_verified")
    ) or 0

    # Manual override (human_corrected=True across all approved statuses)
    manual_override = await db.scalar(
        select(func.count(Observation.id))
        .where(Observation.review_status.in_(["approved", "manually_verified"]))
        .where(Observation.human_corrected.is_(True))
    ) or 0

    # Dual-source agreed
    dual_source = await db.scalar(
        select(func.count(Observation.id))
        .where(Observation.review_status.in_(["approved", "manually_verified"]))
        .where(Observation.dual_source_agreement == 1)
    ) or 0

    # Below 60% confidence (auto-approved only)
    below_60 = await db.scalar(
        select(func.count(Observation.id))
        .where(Observation.review_status == "approved")
        .where(Observation.human_corrected.is_(False))
        .where(Observation.top_score < 0.60)
        .where(Observation.top_score.is_not(None))
    ) or 0

    # Pending re-review (from 9.6 fix)
    pending_rereview = await db.scalar(
        select(func.count(Observation.id))
        .where(Observation.reviewer_notes.contains("auto-approve re-review"))
    ) or 0

    # ── Per-category confidence distributions ──────────────────────────────────
    async def _dist(where_clauses):
        rows = (await db.execute(
            select(Observation.top_score)
            .where(*where_clauses)
            .where(Observation.top_score.is_not(None))
        )).scalars().all()
        return _bucket_scores(rows)

    auto_approved_dist        = await _dist([Observation.review_status == "approved",
                                             Observation.human_corrected.is_(False)])
    manually_verified_dist    = await _dist([Observation.review_status == "manually_verified"])
    needs_review_dist         = await _dist([Observation.review_status == "needs_review"])
    rejected_dist             = await _dist([Observation.review_status == "rejected"])

    # Lowest confidence for manually-confirmed (shown in the summary row)
    mv_min_row = await db.scalar(
        select(func.min(Observation.top_score))
        .where(Observation.review_status == "manually_verified")
        .where(Observation.top_score.is_not(None))
    )
    manually_verified_lowest = round(mv_min_row, 4) if mv_min_row is not None else None

    # Top 10 low-confidence species (<75%, auto-approved only)
    _Int = __import__("sqlalchemy").Integer
    low_conf_rows = (await db.execute(
        select(
            Observation.species_primary,
            func.count(Observation.id).label("approved_total"),
            func.sum((Observation.top_score < 0.75).cast(_Int)).label("low_conf_count"),
            func.min(Observation.top_score).label("lowest_score"),
        )
        .where(Observation.review_status == "approved")
        .where(Observation.human_corrected.is_(False))
        .where(Observation.species_primary.is_not(None))
        .where(Observation.top_score.is_not(None))
        .where(Observation.top_score < 0.75)
        .group_by(Observation.species_primary)
        .order_by(func.sum((Observation.top_score < 0.75).cast(_Int)).desc())
        .limit(10)
    )).all()

    top10 = []
    for r in low_conf_rows:
        src_rows = (await db.execute(
            select(Observation.dual_source_agreement, Observation.human_corrected)
            .where(Observation.species_primary == r.species_primary)
            .where(Observation.review_status == "approved")
            .where(Observation.top_score < 0.75)
            .where(Observation.top_score.is_not(None))
        )).all()
        dual_count   = sum(1 for x in src_rows if x.dual_source_agreement == 1)
        manual_count = sum(1 for x in src_rows if x.human_corrected)
        total_src    = len(src_rows)
        if manual_count == total_src:
            source_type = "Manual"
        elif dual_count > total_src / 2:
            source_type = "Dual"
        else:
            source_type = "Single"

        top10.append({
            "species":        r.species_primary,
            "approved_obs":   r.approved_total,
            "low_conf_count": r.low_conf_count or 0,
            "lowest_score":   round(r.lowest_score, 4) if r.lowest_score else None,
            "source_type":    source_type,
        })

    return {
        "chips": {
            "total_approved":          total_approved,
            "auto_approved":           auto_approved,
            "manually_verified_count": manually_verified_count,
            "manually_verified_lowest": manually_verified_lowest,
            "manual_override":         manual_override,
            "dual_source":             dual_source,
            "below_60":                below_60,
            "pending_rereview":        pending_rereview,
        },
        # Per-category distributions — frontend switches chart by clicking tabs.
        # 'distribution' kept for any caller still referencing the old key.
        "distribution":  auto_approved_dist,
        "distributions": {
            "auto_approved":     auto_approved_dist,
            "manually_verified": manually_verified_dist,
            "needs_review":      needs_review_dist,
            "rejected":          rejected_dist,
        },
        "top10_low_conf": top10,
    }


# ---------------------------------------------------------------------------
# GET /api/trust/confidence-review  — Section B paginated queue
# ---------------------------------------------------------------------------

@router.get("/confidence-review")
async def confidence_review(
    min_score: Optional[float] = Query(None),
    max_score: Optional[float] = Query(None),
    status: str = Query("all"),       # approved | needs_review | all
    source: str = Query("all"),       # single | dual | manual | all
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """Paginated confidence review queue for Section B."""
    q = select(Observation).where(Observation.species_primary.is_not(None))

    # Status filter
    if status == "approved":
        q = q.where(Observation.review_status.in_(["approved", "manually_verified"]))
    elif status == "needs_review":
        q = q.where(Observation.review_status == "needs_review")
    else:
        q = q.where(Observation.review_status.in_(["approved", "manually_verified", "needs_review"]))

    # Source filter
    if source == "single":
        q = q.where(Observation.dual_source_agreement == 0)
        q = q.where(Observation.human_corrected.is_(False))
    elif source == "dual":
        q = q.where(Observation.dual_source_agreement == 1)
        q = q.where(Observation.human_corrected.is_(False))
    elif source == "manual":
        q = q.where(Observation.human_corrected.is_(True))

    # Score filters
    if min_score is not None:
        q = q.where(
            or_(
                Observation.top_score >= min_score,
                Observation.human_corrected.is_(True),  # manual overrides always included
            )
        )
    if max_score is not None:
        q = q.where(
            or_(
                Observation.top_score <= max_score,
                Observation.top_score.is_(None),
            )
        )

    # Count total before pagination
    count_q = select(func.count()).select_from(q.subquery())
    total = await db.scalar(count_q) or 0

    # Order and paginate
    q = q.order_by(Observation.top_score.asc().nullsfirst(), Observation.id.desc())
    q = q.offset(offset).limit(limit)
    rows = (await db.execute(q)).scalars().all()

    items = []
    for obs in rows:
        if obs.human_corrected:
            source_label = "manual"
        elif obs.dual_source_agreement == 1:
            source_label = "dual"
        else:
            source_label = "single"

        items.append({
            "id": obs.id,
            "species_primary": obs.species_primary,
            "review_status": obs.review_status,
            "top_score": obs.top_score,
            "dual_source_agreement": obs.dual_source_agreement,
            "human_corrected": obs.human_corrected,
            "source_label": source_label,
            "routing_reason": obs.routing_reason,
            "thumbnail_path": obs.thumbnail_path,
            "photo_taken_at": obs.photo_taken_at.isoformat() if obs.photo_taken_at else None,
            "reviewer_notes": obs.reviewer_notes,
        })

    return {"total": total, "offset": offset, "limit": limit, "items": items}


# ---------------------------------------------------------------------------
# POST /api/trust/bulk-send-to-review  — Section C Tool 1
# ---------------------------------------------------------------------------

class BulkSendPayload(BaseModel):
    min_score: Optional[float] = None
    max_score: Optional[float] = None
    source_filter: str = "all"    # single | dual | all
    filter_description: str = ""  # human-readable label for audit trail
    dry_run: bool = False


# ---------------------------------------------------------------------------
# POST /api/trust/accept-species  — B2: Accept button in top-10 table
# ---------------------------------------------------------------------------

class AcceptSpeciesPayload(BaseModel):
    species: str
    reason: str = "Data Trust: manually accepted"


@router.post("/accept-species")
async def accept_species(
    payload: AcceptSpeciesPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    B2 — Accept all auto-approved observations for a species from the
    top-10 low-confidence table. Promotes them to manually_verified and
    sets human_corrected=True so they are excluded from future bulk-send
    operations. Writes an ObservationEdit row per change.
    """
    rows = (await db.execute(
        select(Observation)
        .where(Observation.species_primary == payload.species)
        .where(Observation.review_status == "approved")
        .where(Observation.human_corrected.is_(False))
    )).scalars().all()

    from app.services.observation_service import update_observation_status
    accepted = 0
    for obs in rows:
        await update_observation_status(
            session=db,
            obs=obs,
            review_status="manually_verified",
            edited_by="trust:accept_species",
        )
        accepted += 1

    async with db_write_lock():
        await db.commit()
    return {
        "ok": True,
        "species": payload.species,
        "accepted": accepted,
    }


@router.post("/bulk-send-to-review")
async def bulk_send_to_review(
    payload: BulkSendPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Bulk-demote auto-approved observations to needs_review by filter.
    Manual override observations are explicitly excluded.
    Idempotent — skips obs already in needs_review.
    Writes ObservationEdit per changed observation.
    """
    q = (
        select(Observation)
        .where(Observation.review_status.in_(["approved", "manually_verified"]))
        .where(Observation.human_corrected.is_(False))  # never touch manual overrides
    )

    if payload.source_filter == "single":
        q = q.where(Observation.dual_source_agreement == 0)
    elif payload.source_filter == "dual":
        q = q.where(Observation.dual_source_agreement == 1)

    if payload.min_score is not None:
        q = q.where(Observation.top_score >= payload.min_score)
    if payload.max_score is not None:
        q = q.where(
            or_(Observation.top_score <= payload.max_score, Observation.top_score.is_(None))
        )

    rows = (await db.execute(q)).scalars().all()

    if payload.dry_run:
        return {"dry_run": True, "would_send": len(rows)}

    reason = f"Data Trust: bulk sent to review ({payload.filter_description})"
    sent = 0
    for obs in rows:
        if obs.review_status == "needs_review":
            continue
        old_status = obs.review_status
        obs.review_status = "needs_review"
        obs.review_label  = "data_trust"
        existing = obs.reviewer_notes or ""
        sep = "\n" if existing else ""
        obs.reviewer_notes = existing + sep + reason
        db.add(ObservationEdit(
            observation_id=obs.id,
            field_name="review_status",
            old_value=old_status,
            new_value="needs_review",
            edited_by="trust:bulk_send",
        ))
        sent += 1

    await db.commit()
    return {"ok": True, "sent": sent, "total_matched": len(rows)}


# ---------------------------------------------------------------------------
# POST /api/trust/bulk-reassign  — Section C Tool 2
# ---------------------------------------------------------------------------

class BulkReassignPayload(BaseModel):
    source_species: str
    target_species: str
    dry_run: bool = False


@router.post("/bulk-reassign")
async def bulk_reassign(
    payload: BulkReassignPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Reassign all observations from source_species to target_species.
    Uses handle_species_rename() for enrichment/recipe/notes cascade.
    Writes ObservationEdit per observation.
    """
    from app.services.enrichment import handle_species_rename

    if payload.source_species == payload.target_species:
        return {"ok": False, "error": "Source and target species are the same"}

    # Count affected observations
    obs_rows = (await db.execute(
        select(Observation)
        .where(Observation.species_primary == payload.source_species)
        .where(Observation.review_status.in_(["approved", "manually_verified", "needs_review"]))
    )).scalars().all()

    if payload.dry_run:
        return {
            "dry_run": True,
            "source": payload.source_species,
            "target": payload.target_species,
            "would_reassign": len(obs_rows),
            "sample": [{"id": o.id, "status": o.review_status} for o in obs_rows[:5]],
        }

    # Ensure target species row exists (or get its ID)
    target_sp = await db.scalar(
        select(Species).where(Species.scientific_name == payload.target_species)
    )
    if not target_sp:
        return {
            "ok": False,
            "error": f"Target species '{payload.target_species}' not found in database. "
                     "Add it via the review queue first.",
        }

    # Run the rename cascade on the source species row
    source_sp = await db.scalar(
        select(Species).where(Species.scientific_name == payload.source_species)
    )
    if source_sp:
        await handle_species_rename(
            db,
            species=source_sp,
            new_name=payload.target_species,
            is_rename=False,
        )

    # Reassign all matching observations
    from app.services.species_link import set_observation_species
    reassigned = 0
    for obs in obs_rows:
        old_name = obs.species_primary
        await set_observation_species(db, obs, payload.target_species)
        db.add(ObservationEdit(
            observation_id=obs.id,
            field_name="species_primary",
            old_value=old_name,
            new_value=payload.target_species,
            edited_by="trust:bulk_reassign",
        ))
        reassigned += 1

    await db.commit()
    return {
        "ok": True,
        "reassigned": reassigned,
        "source": payload.source_species,
        "target": payload.target_species,
    }


# ---------------------------------------------------------------------------
# POST /api/trust/kingdom-audit  — retroactive non-plant/fungi kingdom scan
# ---------------------------------------------------------------------------

_INAT_ALLOWED_KINGDOMS = {"plantae", "fungi"}
_INAT_KINGDOM_THRESHOLD_STORED = 5.0  # iNat scores stored in 0-100 range


async def _inat_get_kingdom(species_name: str) -> Optional[str]:
    """Query the iNaturalist taxa API to get iconic_taxon_name for a species."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.inaturalist.org/v1/taxa",
                params={"q": species_name, "rank": "species", "per_page": 3},
            )
        if resp.status_code != 200:
            return None
        results = resp.json().get("results", [])
        name_lower = species_name.lower()
        best = next(
            (r for r in results if (r.get("name") or "").lower() == name_lower),
            results[0] if results else None,
        )
        return (best.get("iconic_taxon_name") or None) if best else None
    except Exception:
        return None


@router.post("/kingdom-audit")
async def kingdom_audit(
    apply: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """
    Retroactive scan: find observations in needs_review/approved where
    the top iNaturalist candidate is outside Plantae/Fungi at ≥5% confidence.

    - apply=false (default): report only, no changes
    - apply=true: send flagged observations to review with kingdom note

    Works by looking at species_candidates_json for stored iNat candidates.
    For observations where iconic_taxon_name isn't stored yet (pre-fix data),
    performs a live iNaturalist taxa lookup per unique species name.

    Writes ObservationEdit per change when apply=true.
    """
    # Fetch all active observations with iNat candidates
    rows = (await db.execute(
        select(Observation)
        .where(Observation.review_status.in_(["needs_review", "approved", "manually_verified"]))
        .where(Observation.species_candidates_json.is_not(None))
        .where(Observation.species_candidates_json.not_in(["[]", "", "null"]))
    )).scalars().all()

    # Collect unique iNat species that need kingdom lookup
    # Map: species_name → (score, kingdom_if_stored)
    species_to_check: dict[str, tuple[float, Optional[str]]] = {}
    obs_inat_top: dict[int, tuple[str, float, Optional[str]]] = {}  # obs_id → (species, score, kingdom)

    for obs in rows:
        try:
            cands = _json.loads(obs.species_candidates_json or "[]")
        except Exception:
            continue
        inat_top = next(
            (c for c in cands if c.get("source") == "inaturalist" and c.get("score", 0) >= _INAT_KINGDOM_THRESHOLD_STORED),
            None,
        )
        if not inat_top:
            continue
        name    = inat_top.get("scientific_name", "")
        score   = inat_top.get("score", 0.0)
        kingdom = inat_top.get("kingdom")  # None for pre-fix data
        if name:
            obs_inat_top[obs.id] = (name, score, kingdom)
            if name not in species_to_check:
                species_to_check[name] = (score, kingdom)

    # For species without stored kingdom, query iNaturalist
    unknown_names = [n for n, (_, k) in species_to_check.items() if k is None]
    kingdom_map: dict[str, Optional[str]] = {
        n: k for n, (_, k) in species_to_check.items() if k is not None
    }

    for name in unknown_names:
        k = await _inat_get_kingdom(name)
        kingdom_map[name] = k
        await asyncio.sleep(0.3)  # avoid rate-limiting the iNat API

    # Identify flagged observations
    flagged = []
    for obs_id, (name, score, _) in obs_inat_top.items():
        kingdom = kingdom_map.get(name)
        if kingdom and kingdom.lower() not in _INAT_ALLOWED_KINGDOMS:
            flagged.append({
                "obs_id": obs_id,
                "species_name": name,
                "score": score,
                "kingdom": kingdom,
            })

    if not apply:
        # Report only
        species_summary: dict[str, dict] = {}
        for f in flagged:
            k = f["species_name"]
            if k not in species_summary:
                species_summary[k] = {"kingdom": f["kingdom"], "count": 0, "obs_ids": []}
            species_summary[k]["count"] += 1
            species_summary[k]["obs_ids"].append(f["obs_id"])
        return {
            "dry_run": True,
            "total_flagged": len(flagged),
            "species": [
                {"species": k, "kingdom": v["kingdom"], "count": v["count"], "obs_ids": v["obs_ids"]}
                for k, v in sorted(species_summary.items(), key=lambda x: -x[1]["count"])
            ],
        }

    # Apply: send to review
    obs_map = {obs.id: obs for obs in rows}
    sent = 0
    for f in flagged:
        obs = obs_map.get(f["obs_id"])
        if not obs:
            continue
        note = (
            f"Kingdom audit: iNaturalist returned {f['kingdom']}"
            f" ({f['species_name']} {f['score']:.1f}%)"
        )
        old_status = obs.review_status
        obs.review_status = "needs_review"
        obs.review_label  = "non_plant"
        existing = obs.reviewer_notes or ""
        obs.reviewer_notes = existing + ("\n" if existing else "") + note
        db.add(ObservationEdit(
            observation_id=obs.id,
            field_name="review_status",
            old_value=old_status,
            new_value="needs_review",
            edited_by="trust:kingdom_audit",
        ))
        sent += 1

    await db.commit()

    species_summary = {}
    for f in flagged:
        k = f["species_name"]
        if k not in species_summary:
            species_summary[k] = {"kingdom": f["kingdom"], "count": 0}
        species_summary[k]["count"] += 1

    return {
        "ok": True,
        "total_flagged": len(flagged),
        "sent_to_review": sent,
        "species": [
            {"species": k, "kingdom": v["kingdom"], "count": v["count"]}
            for k, v in sorted(species_summary.items(), key=lambda x: -x[1]["count"])
        ],
    }


# ---------------------------------------------------------------------------
# POST /api/trust/bulk-landscape
# ---------------------------------------------------------------------------

class BulkLandscapePayload(BaseModel):
    observation_ids: List[int]


@router.post("/bulk-landscape")
async def bulk_landscape(
    payload: BulkLandscapePayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Mark non-plant observations as landscape category:
    - Sets obs_category = 'landscape'
    - Clears species_primary (via species_id = NULL + species_primary = NULL)
    - Sets review_status = 'not_applicable' — exits the approved pool silently,
      no review queue entry, no map pin.

    Intended for non_plant_approved audit findings where the subject is a
    scene/landscape photo that was mis-classified.
    """
    if not payload.observation_ids:
        return {"ok": True, "updated": 0}

    rows = (await db.execute(
        select(Observation).where(Observation.id.in_(payload.observation_ids))
    )).scalars().all()

    updated = 0
    for obs in rows:
        old_cat = obs.obs_category
        old_status = obs.review_status
        obs.obs_category = "landscape"
        obs.species_primary = None
        obs.species_id = None
        obs.species_suggested = None
        obs.review_status = "not_applicable"
        obs.identification_status = "identified"
        db.add(ObservationEdit(
            observation_id=obs.id,
            field_name="obs_category",
            old_value=old_cat,
            new_value="landscape",
            edited_by="trust:bulk_landscape",
        ))
        db.add(ObservationEdit(
            observation_id=obs.id,
            field_name="review_status",
            old_value=old_status,
            new_value="not_applicable",
            edited_by="trust:bulk_landscape",
        ))
        updated += 1

    await db.commit()
    return {"ok": True, "updated": updated}


# ---------------------------------------------------------------------------
# POST /api/trust/bulk-clear-culinary
# ---------------------------------------------------------------------------

_CULINARY_FIELDS_TO_CLEAR = [
    "taste_notes", "medicinal_notes", "recipe",
    "recipe_ideas", "edible_parts", "flavour_profile",
    "preparation_methods", "cooking_techniques",
]


class BulkClearCulinaryPayload(BaseModel):
    species_names: List[str]


@router.post("/bulk-clear-culinary")
async def bulk_clear_culinary(
    payload: BulkClearCulinaryPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Remove culinary content from toxic species.

    For each species: nulls the culinary enrichment fields that imply
    edibility (taste_notes, medicinal_notes, recipe, recipe_ideas,
    edible_parts, flavour_profile, preparation_methods, cooking_techniques)
    on the culinary_info row.

    Creates a SpeciesAIDraft record per field nulled (status='pending',
    model='data_trust_clear', draft_text=None) as an auditable clearing record.
    Does NOT send any observations to the review queue.
    """
    if not payload.species_names:
        return {"ok": True, "species_cleared": 0, "fields_cleared": 0}

    species_rows = (await db.execute(
        select(Species).where(Species.scientific_name.in_(payload.species_names))
    )).scalars().all()

    species_cleared = 0
    fields_cleared = 0

    for sp in species_rows:
        ci = (await db.execute(
            select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id)
        )).scalar_one_or_none()

        if not ci:
            continue

        cleared_fields = []
        for field in _CULINARY_FIELDS_TO_CLEAR:
            current_val = getattr(ci, field, None)
            if current_val is not None:
                setattr(ci, field, None)
                cleared_fields.append(field)

        if cleared_fields:
            for field in cleared_fields:
                db.add(SpeciesAIDraft(
                    species_id=sp.id,
                    field_name=field,
                    draft_text=None,
                    status="pending",
                    model="data_trust_clear",
                    generation_context_json=_json.dumps({
                        "action": "bulk_clear_culinary",
                        "reason": "Toxic species — culinary content cleared by Data Trust audit",
                        "species": sp.scientific_name,
                    }),
                ))
            fields_cleared += len(cleared_fields)
            species_cleared += 1

    await db.commit()
    return {
        "ok": True,
        "species_cleared": species_cleared,
        "fields_cleared": fields_cleared,
    }
