"""
Data Integrity Audit — GET /api/audit/run

Checks all confirmed observations and species records for data quality issues.
Returns a structured report grouped by issue type. Never makes automatic fixes.

Issue types:
  approved_no_species    – approved observation with no species_primary
  non_plant_approved     – prefilter rejected as non-plant but got approved
  orphan_species         – species row with no confirmed observations
  toxic_enriched         – toxic/inedible species with culinary "edible" content
  ai_field_no_draft      – taste_notes/medicinal_notes/recipe with no approved AI draft
  suspicious_correction  – human-corrected species not found in original API candidates
  low_confidence_live    – on-map observation with confidence < 0.35 (not human-corrected)
"""

import json as _json
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.observation import Observation, ObservationEdit
from app.services.file_cleanup import delete_observation_file
from app.models.culinary import CulinaryInfo
from app.models.species import Species, SpeciesAIDraft, SpeciesRecipe

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit", tags=["audit"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _obs_link(obs_id: int) -> str:
    return f"/review?id={obs_id}"


def _species_link(name: str) -> str:
    import urllib.parse
    return f"/species?species={urllib.parse.quote(name)}"


def _enrichment_link(name: str) -> str:
    return f"/review#enrichment"


# ---------------------------------------------------------------------------
# Main audit endpoint
# ---------------------------------------------------------------------------

_ALL_CHECKS = {
    "id_mismatches":            "ID mismatches (low confidence + suspicious corrections)",
    "enrichment_gaps":          "Enrichment gaps (orphan species + missing common name)",
    "missing_gps":              "Approved observations missing GPS co-ordinates",
    "non_plant_approved":       "Non-plant observations that reached approved status",
    "toxic_enriched":           "Toxic/inedible species with culinary content",
    "ai_content_issues":        "AI content issues (populated field without draft)",
    "missing_edibility":        "Edibility categorisation missing or uncertain",
    "recipe_edibility_conflict":"Recipes present on toxic/unknown-edibility species",
}


@router.get("/checks")
async def list_checks():
    """Return the list of available audit check types with labels."""
    return [{"id": k, "label": v} for k, v in _ALL_CHECKS.items()]


@router.get("/run")
async def run_audit(
    checks: Optional[str] = None,  # comma-separated list of check IDs; None = run all
    db: AsyncSession = Depends(get_db),
):
    """
    Run integrity checks. Returns issues list + summary.
    Pass ?checks=id_mismatches,toxic_enriched to run specific checks only.
    Read-only — no writes.
    """
    selected = set(checks.split(",")) if checks else set(_ALL_CHECKS.keys())
    issues = []

    # ── 1. Approved observations with no species_primary ──────────────────
    rows = (await db.execute(
        select(Observation.id, Observation.upload_source, Observation.reviewed_at)
        .where(Observation.review_status.in_(["approved", "manually_verified"]))
        .where(Observation.species_primary.is_(None))
        .where(Observation.identification_status != "not_plant")
        .order_by(Observation.id)
        .limit(200)
    )).all()
    for r in rows:
        issues.append({
            "type": "approved_no_species",
            "severity": "error",
            "obs_id": r.id,
            "species": None,
            "description": f"Observation #{r.id} is approved but has no species assigned.",
            "suggestion": "Open in Review Queue and either assign a species or reject.",
            "link": _obs_link(r.id),
            "link_label": f"Open #{r.id} in Review Queue",
        })

    # ── 2. Non-plant observations that reached approved status ────────────
    NON_PLANT_CATS = ("person_animal", "food_warm", "sky_blue", "screenshot",
                      "ui_blank", "indoor_dark", "indoor_bright", "no_plant_signal")
    rows = (await db.execute(
        select(
            Observation.id, Observation.prefilter_category,
            Observation.species_primary, Observation.human_corrected,
        )
        .where(Observation.review_status.in_(["approved", "manually_verified"]))
        .where(Observation.prefilter_category.in_(NON_PLANT_CATS))
        .order_by(Observation.id)
        .limit(200)
    )).all()
    for r in rows:
        hc = " (human-corrected)" if r.human_corrected else ""
        issues.append({
            "type": "non_plant_approved",
            "severity": "warning",
            "obs_id": r.id,
            "species": r.species_primary,
            "description": (
                f'Observation #{r.id} pre-filter category is "{r.prefilter_category}"{hc}, '
                f"but it is approved on the map."
            ),
            "suggestion": (
                "Verify this was intentionally approved (e.g. after human review). "
                "If not, reject it."
            ),
            "link": _obs_link(r.id),
            "link_label": f"Open #{r.id} in Review Queue",
        })

    # ── 3. Low-confidence live observations ───────────────────────────────
    # Auto-approved observations (not human-corrected) with top score < 0.35
    LOW_SCORE = 0.35
    rows = (await db.execute(
        select(
            Observation.id, Observation.species_primary,
            Observation.species_candidates_json,
        )
        .where(Observation.review_status.in_(["approved", "manually_verified"]))
        .where(Observation.human_corrected.is_(False))
        .where(Observation.species_primary.is_not(None))
        .order_by(Observation.id)
        .limit(1000)
    )).all()
    for r in rows:
        try:
            cands = _json.loads(r.species_candidates_json or "[]")
            if cands:
                top_score = float(cands[0].get("score", 1.0))
                if top_score < LOW_SCORE:
                    issues.append({
                        "type": "low_confidence_live",
                        "severity": "warning",
                        "obs_id": r.id,
                        "species": r.species_primary,
                        "description": (
                            f"Observation #{r.id} ({r.species_primary}) is live on the map "
                            f"with a low confidence score of {top_score:.0%}."
                        ),
                        "suggestion": "Review and either confirm or correct the species identification.",
                        "link": _obs_link(r.id),
                        "link_label": f"Open #{r.id} in Review Queue",
                    })
        except Exception:
            pass

    # ── 4. Human corrections where corrected name ∉ original candidates ──
    rows = (await db.execute(
        select(
            Observation.id, Observation.species_primary,
            Observation.species_candidates_json,
        )
        .where(Observation.human_corrected.is_(True))
        .where(Observation.species_primary.is_not(None))
        .where(Observation.review_status.in_(["approved", "manually_verified", "needs_review"]))
        .order_by(Observation.id)
        .limit(500)
    )).all()
    for r in rows:
        try:
            cands = _json.loads(r.species_candidates_json or "[]")
            candidate_names = {c.get("scientific_name", "") for c in cands}
            if candidate_names and r.species_primary not in candidate_names:
                issues.append({
                    "type": "suspicious_correction",
                    "severity": "info",
                    "obs_id": r.id,
                    "species": r.species_primary,
                    "description": (
                        f'Observation #{r.id} was manually corrected to "{r.species_primary}", '
                        f"which does not appear in the original API candidates."
                    ),
                    "suggestion": (
                        "Verify the corrected name is spelled correctly and is a valid "
                        "scientific name. This may be intentional (novel species not in API)."
                    ),
                    "link": _obs_link(r.id),
                    "link_label": f"Open #{r.id} in Review Queue",
                })
        except Exception:
            pass

    # ── 5. Orphaned species (no confirmed observations) ───────────────────
    # Species in the species table with no approved/manually_verified observations
    confirmed_names_q = (await db.execute(
        select(Observation.species_primary)
        .where(Observation.review_status.in_(["approved", "manually_verified"]))
        .where(Observation.species_primary.is_not(None))
        .distinct()
    )).scalars().all()
    confirmed_set = set(confirmed_names_q)

    species_rows = (await db.execute(
        select(Species.id, Species.scientific_name, Species.created_at)
        .order_by(Species.scientific_name)
    )).all()
    for sp in species_rows:
        if sp.scientific_name not in confirmed_set:
            issues.append({
                "type": "orphan_species",
                "severity": "info",
                "obs_id": None,
                "species": sp.scientific_name,
                "description": (
                    f'Species "{sp.scientific_name}" has a record in the database '
                    f"but no confirmed observations."
                ),
                "suggestion": (
                    "Delete the species record if it was created in error, or "
                    "check whether its observations were rejected."
                ),
                "link": _species_link(sp.scientific_name),
                "link_label": f"View {sp.scientific_name}",
            })

    # ── 6. Toxic/inedible species with culinary "edible" enrichment ───────
    rows = (await db.execute(
        select(
            Species.id, Species.scientific_name, Species.edibility_status,
            CulinaryInfo.edible_parts, CulinaryInfo.preparation_methods,
        )
        .join(CulinaryInfo, CulinaryInfo.species_id == Species.id)
        .where(Species.edibility_status.in_(["toxic", "inedible"]))
        .where(
            or_(
                CulinaryInfo.edible_parts.is_not(None),
                CulinaryInfo.preparation_methods.is_not(None),
            )
        )
        .order_by(Species.scientific_name)
    )).all()
    for r in rows:
        issues.append({
            "type": "toxic_enriched",
            "severity": "error",
            "obs_id": None,
            "species": r.scientific_name,
            "description": (
                f'"{r.scientific_name}" is marked as "{r.edibility_status}" but has '
                f"culinary enrichment data (edible parts / preparation methods) set. "
                f"This is a safety risk."
            ),
            "suggestion": (
                "Review and clear the edible_parts and preparation_methods fields, "
                "or correct the edibility_status."
            ),
            "link": _species_link(r.scientific_name),
            "link_label": f"View {r.scientific_name}",
        })

    # ── 7. AI-drafted fields with no approved draft record ────────────────
    # culinary_info rows where taste_notes/medicinal_notes/recipe are populated
    # but the matching species_ai_drafts approval record doesn't exist
    rows = (await db.execute(
        select(
            Species.id, Species.scientific_name,
            CulinaryInfo.taste_notes, CulinaryInfo.medicinal_notes, CulinaryInfo.recipe,
        )
        .join(CulinaryInfo, CulinaryInfo.species_id == Species.id)
        .where(
            or_(
                CulinaryInfo.taste_notes.is_not(None),
                CulinaryInfo.medicinal_notes.is_not(None),
                CulinaryInfo.recipe.is_not(None),
            )
        )
        .order_by(Species.scientific_name)
    )).all()

    for r in rows:
        # Check which fields are populated but lack an approved draft
        fields_to_check = []
        if r.taste_notes:
            fields_to_check.append("taste_notes")
        if r.medicinal_notes:
            fields_to_check.append("medicinal_notes")
        if r.recipe:
            fields_to_check.append("recipe")

        for field in fields_to_check:
            approved_draft = await db.scalar(
                select(SpeciesAIDraft)
                .where(SpeciesAIDraft.species_id == r.id)
                .where(SpeciesAIDraft.field_name == field)
                .where(SpeciesAIDraft.status.in_(["approved", "edited_approved"]))
            )
            if not approved_draft:
                issues.append({
                    "type": "ai_field_no_draft",
                    "severity": "warning",
                    "obs_id": None,
                    "species": r.scientific_name,
                    "description": (
                        f'"{r.scientific_name}" has {field.replace("_", " ")} populated '
                        f"in the database but no corresponding approved AI draft record."
                    ),
                    "suggestion": (
                        "The field may have been set outside the AI draft workflow. "
                        "Review the content for accuracy."
                    ),
                    "link": _enrichment_link(r.scientific_name),
                    "link_label": "Open Enrichment Review",
                })

    # ── 8. Species with confirmed observations but no common name ─────────
    # These should be enriched to add a common name — flag as info.
    import json as _json2
    no_common_rows = (await db.execute(
        select(Species.scientific_name, Species.common_names)
        .where(Species.scientific_name.in_(confirmed_set))
        .order_by(Species.scientific_name)
    )).all()
    for r in no_common_rows:
        names = []
        try:
            names = _json2.loads(r.common_names or "[]") if r.common_names else []
        except Exception:
            pass
        if not names:
            issues.append({
                "type": "missing_common_name",
                "severity": "info",
                "obs_id": None,
                "species": r.scientific_name,
                "description": (
                    f'"{r.scientific_name}" has confirmed observations but no common name. '
                    f"Common name enrichment should be prioritised."
                ),
                "suggestion": (
                    "Re-run enrichment for this species, or add a common name manually "
                    "via the species page. Common name is shown to users on the map."
                ),
                "link": _species_link(r.scientific_name),
                "link_label": f"View {r.scientific_name}",
            })

    # ── 9. Approved observations without GPS ─────────────────────────────
    rows = (await db.execute(
        select(Observation.id, Observation.species_primary, Observation.upload_source)
        .where(Observation.review_status.in_(["approved", "manually_verified"]))
        .where(Observation.latitude.is_(None))
        .where(Observation.species_primary.is_not(None))
        .order_by(Observation.id)
        .limit(200)
    )).all()
    for r in rows:
        issues.append({
            "type": "missing_gps",
            "severity": "info",
            "obs_id": r.id,
            "species": r.species_primary,
            "description": (
                f"Observation #{r.id} ({r.species_primary}) is approved on the map "
                f"but has no GPS co-ordinates — it cannot be placed on the map."
            ),
            "suggestion": (
                "Open in Location Review to add GPS from a photo taken at the same "
                "location, or reject this observation."
            ),
            "link": "/review#location",
            "link_label": f"Open #{r.id} in Location Review",
        })

    # ── 10. Confirmed species with no edibility categorisation ────────────
    edib_rows = (await db.execute(
        select(Species.scientific_name, Species.edibility_status)
        .where(Species.scientific_name.in_(confirmed_set))
        .where(
            or_(
                Species.edibility_status.is_(None),
                Species.edibility_status.in_(["unknown", "unclear"]),
            )
        )
        .order_by(Species.scientific_name)
        .limit(200)
    )).all()
    for r in edib_rows:
        issues.append({
            "type": "missing_edibility",
            "severity": "info",
            "obs_id": None,
            "species": r.scientific_name,
            "description": (
                f'"{r.scientific_name}" has confirmed observations but its edibility '
                f"is not categorised ({r.edibility_status or 'null'}). "
                f"AI recipe/taste generation is suppressed until confirmed edible."
            ),
            "suggestion": (
                "Set edibility_status on the species page to enable full AI draft "
                "generation, or mark as 'unknown' to suppress all culinary content."
            ),
            "link": _species_link(r.scientific_name),
            "link_label": f"View {r.scientific_name}",
        })

    # ── 11. Recipes on wrong-edibility species ────────────────────────────
    # Finds species_recipes rows that violate edibility rules:
    #   - recipes on toxic/inedible species
    #   - recipes on species with unknown/null edibility
    recipe_conflict_rows = (await db.execute(
        select(
            Species.scientific_name, Species.edibility_status,
            SpeciesRecipe.id, SpeciesRecipe.title,
        )
        .join(SpeciesRecipe, SpeciesRecipe.species_id == Species.id)
        .where(SpeciesRecipe.status == "approved")
        .where(
            or_(
                Species.edibility_status.in_(["toxic", "inedible", "not_edible"]),
                Species.edibility_status.is_(None),
                Species.edibility_status.in_(["unknown", "unclear"]),
            )
        )
        .order_by(Species.scientific_name)
        .limit(200)
    )).all()

    for r in recipe_conflict_rows:
        edib_label = r.edibility_status or "null"
        is_toxic = edib_label in ("toxic", "inedible", "not_edible")
        issues.append({
            "type": "recipe_edibility_conflict",
            "severity": "error" if is_toxic else "warning",
            "obs_id": None,
            "species": r.scientific_name,
            "recipe_id": r.id,
            "description": (
                f'"{r.scientific_name}" (edibility: {edib_label}) has an approved recipe '
                f'"{r.title or "untitled"}" in the recipe bank. '
                + ("Toxic/inedible species must not have recipes." if is_toxic
                   else "Recipe bank should be blank until edibility is confirmed.")
            ),
            "suggestion": (
                "Review and archive the recipe, or update the edibility status. "
                "Do not auto-delete — use the review queue."
            ),
            "link": _species_link(r.scientific_name),
            "link_label": f"View {r.scientific_name}",
        })

    # ── Map issue types → check groups ───────────────────────────────────
    _TYPE_TO_CHECK = {
        "approved_no_species":      "id_mismatches",
        "non_plant_approved":       "non_plant_approved",
        "low_confidence_live":      "id_mismatches",
        "suspicious_correction":    "id_mismatches",
        "orphan_species":           "enrichment_gaps",
        "toxic_enriched":           "toxic_enriched",
        "ai_field_no_draft":        "ai_content_issues",
        "missing_common_name":      "enrichment_gaps",
        "missing_gps":              "missing_gps",
        "missing_edibility":        "missing_edibility",
        "recipe_edibility_conflict":"recipe_edibility_conflict",
    }

    # Filter to selected checks (skip if all checks requested)
    if selected != set(_ALL_CHECKS.keys()):
        issues = [i for i in issues if _TYPE_TO_CHECK.get(i["type"]) in selected]

    # ── Build summary ─────────────────────────────────────────────────────
    type_counts: dict = {}
    severity_counts: dict = {"error": 0, "warning": 0, "info": 0}
    for iss in issues:
        t = iss["type"]
        type_counts[t] = type_counts.get(t, 0) + 1
        s = iss.get("severity", "info")
        severity_counts[s] = severity_counts.get(s, 0) + 1

    return {
        "total": len(issues),
        "summary": {
            "errors": severity_counts["error"],
            "warnings": severity_counts["warning"],
            "info": severity_counts["info"],
            "by_type": type_counts,
        },
        "issues": issues,
    }


# ---------------------------------------------------------------------------
# POST /api/audit/send-to-review
# ---------------------------------------------------------------------------

from pydantic import BaseModel


class SendToReviewPayload(BaseModel):
    obs_id: Optional[int] = None
    species: Optional[str] = None
    reason: str = "Flagged by audit"


@router.post("/send-to-review")
async def audit_send_to_review(
    payload: SendToReviewPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Push an observation or all observations for a species into needs_review.
    Used by the audit results UI — each flagged issue has a 'Send to review' button.
    Appends the audit reason as a note so reviewers know why it was queued.

    Every demotion writes an ObservationEdit row so the change is never silent —
    a regression once stripped ~130 observations out of confirmed via this
    endpoint with no audit trail, making the cause hard to find.
    """
    updated = 0

    def _demote(obs):
        nonlocal updated
        if obs.review_status == "needs_review":
            return
        old_status = obs.review_status
        obs.review_status = "needs_review"
        obs.review_label  = "data_trust"
        if payload.reason:
            existing_notes = obs.reviewer_notes or ""
            sep = "\n" if existing_notes else ""
            obs.reviewer_notes = existing_notes + sep + f"[Audit] {payload.reason}"
        db.add(ObservationEdit(
            observation_id=obs.id,
            field_name="review_status",
            old_value=old_status,
            new_value="needs_review",
            edited_by="audit:send_to_review",
        ))
        updated += 1

    if payload.obs_id:
        obs = await db.get(Observation, payload.obs_id)
        if obs:
            _demote(obs)

    elif payload.species:
        rows = (await db.execute(
            select(Observation)
            .where(Observation.species_primary == payload.species)
            .where(Observation.review_status.in_(["approved", "manually_verified"]))
        )).scalars().all()
        for obs in rows:
            _demote(obs)

    await db.commit()
    return {
        "ok": True,
        "queued": updated,
        "obs_id": payload.obs_id,
        "species": payload.species,
        "reason": payload.reason,
    }


# ---------------------------------------------------------------------------
# POST /api/audit/reject
# ---------------------------------------------------------------------------


class RejectPayload(BaseModel):
    obs_id: Optional[int] = None
    species: Optional[str] = None
    reason: str = "Rejected by audit"


@router.post("/reject")
async def audit_reject(
    payload: RejectPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Reject an observation (or all currently-live observations for a species)
    straight from the audit results UI.

    Non-destructive: sets review_status = 'rejected' (the record is kept as a
    rejection marker, matching the rest of the app) and appends the audit
    reason to reviewer_notes. The map / approved set excludes rejected rows.
    """
    from datetime import datetime as _dt

    rejected = 0
    rejected_obs = []

    def _reject(obs):
        nonlocal rejected
        if obs.review_status == "rejected":
            return
        old_status = obs.review_status
        obs.review_status = "rejected"
        obs.reviewed_at = _dt.utcnow()
        if payload.reason:
            existing_notes = obs.reviewer_notes or ""
            sep = "\n" if existing_notes else ""
            obs.reviewer_notes = existing_notes + sep + f"[Audit] Rejected: {payload.reason}"
        db.add(ObservationEdit(
            observation_id=obs.id,
            field_name="review_status",
            old_value=old_status,
            new_value="rejected",
            edited_by="audit:reject",
        ))
        rejected_obs.append(obs)
        rejected += 1

    if payload.obs_id:
        obs = await db.get(Observation, payload.obs_id)
        if obs:
            _reject(obs)

    elif payload.species:
        rows = (await db.execute(
            select(Observation)
            .where(Observation.species_primary == payload.species)
            .where(Observation.review_status.in_(["approved", "manually_verified", "needs_review"]))
        )).scalars().all()
        for obs in rows:
            _reject(obs)

    await db.commit()

    for obs in rejected_obs:
        try:
            delete_observation_file(obs)
        except Exception as exc:
            log.warning("audit reject obs %d: file cleanup failed: %s", obs.id, exc)
    return {
        "ok": True,
        "rejected": rejected,
        "obs_id": payload.obs_id,
        "species": payload.species,
        "reason": payload.reason,
    }


# ---------------------------------------------------------------------------
# POST /api/audit/reenrich-common-name
# ---------------------------------------------------------------------------


class ReenrichCommonNamePayload(BaseModel):
    species: str


@router.post("/reenrich-common-name")
async def audit_reenrich_common_name(
    payload: ReenrichCommonNamePayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Re-enrich one species to fetch a fresh common name from PFAF + Wikidata +
    iNaturalist. Batch action behind the "Re-enrich all" button on the
    "Species missing a common name" integrity-check category.

    This is a DIRECT re-enrichment — it does NOT send anything to the review
    queue. The scientific name is already confirmed correct; only the missing
    common-name metadata is being filled, so no human review step is needed.

    Runs the same enrichment pipeline as the post-scan auto-enrich
    (_enrich_new_species_card → enrich_species), but with re_enrich=True and
    fill_empty_only=False so common names are fetched fresh even though these
    species already have other populated fields. (The post-scan helper itself
    skips already-enriched species, so we call enrich_species directly with the
    re-enrich flags.) common_names is only set when currently empty
    (_apply_wikidata_to_species), which is exactly the case here.
    """
    import json as _json3
    from app.services.enrichment import enrich_species

    def _has_common(sp) -> bool:
        try:
            names = _json3.loads(sp.common_names or "[]")
            return bool(isinstance(names, list) and names)
        except Exception:
            return False

    sp = await db.scalar(
        select(Species).where(Species.scientific_name == payload.species)
    )
    if not sp:
        return {"ok": False, "species": payload.species, "error": "Species not found"}

    had_before = _has_common(sp)

    try:
        status = await enrich_species(
            db, sp, dry_run=False, re_enrich=True, fill_empty_only=False,
        )
        # iNaturalist common-name fallback. enrich_species only fills common_names
        # from Wikidata; when Wikidata has no entry (or is rate-limited) we fall
        # back to iNaturalist — which the user named as a common-name source and
        # which carries names Wikidata lacks for many taxa. Only fills when still
        # empty, so an existing name is never overwritten.
        if not _has_common(sp):
            try:
                from app.integrations.inaturalist import taxa_autocomplete
                taxa = await taxa_autocomplete(sp.scientific_name)
                match = next(
                    (t for t in taxa
                     if t.scientific_name.lower() == sp.scientific_name.lower()),
                    taxa[0] if taxa else None,
                )
                if match and match.common_name:
                    sp.common_names = _json3.dumps([match.common_name])
            except Exception as inat_exc:
                log.warning(
                    "[audit:reenrich] iNat common-name fallback failed for %r: %s",
                    payload.species, inat_exc,
                )
        await db.commit()
        await db.refresh(sp)
    except Exception as exc:
        log.warning("[audit:reenrich] Failed for %r: %s", payload.species, exc)
        return {"ok": False, "species": payload.species, "error": str(exc)}

    has_after = _has_common(sp)
    return {
        "ok": True,
        "species": payload.species,
        "status": status,
        "had_common_name": had_before,
        "has_common_name": has_after,
        # True only when this run actually filled a previously-missing name.
        "populated": (not had_before) and has_after,
    }
