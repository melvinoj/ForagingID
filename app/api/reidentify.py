"""
Re-identification power suite — Phase 5.5 / species-level accuracy tools.

Endpoints:

  POST /api/observations/{id}/reidentify
    Runs PlantNet + iNaturalist vision in parallel.  Returns top 5 merged
    candidates sorted by confidence, source-labelled.

  POST /api/observations/{id}/confirm-species
    Writes a user-selected species to the observation record with full audit
    trail.  source = 'manual_reidentification' | 'manual_entry'.

  GET  /api/species/lookup?q={name}
    GBIF species search + iNaturalist taxa autocomplete in parallel.
    Used by the manual-entry workflow.

  GET  /api/observations/{id}/gbif-check?species={name}
    GBIF UK occurrence count for a species.  Read-only, display-only.
    Result stored on the observation for Phase 6 profiles.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.integrations.inaturalist import score_image as inat_score, taxa_autocomplete as inat_taxa
from app.integrations import mushroom_observer as mo
from app.integrations.plantnet import PlantNetError, identify_image as plantnet_identify
from app.models.observation import Observation, ObservationEdit
from app.services.species_link import set_observation_species
from app.services.taxonomy import collapse_autonym
from app.services.write_lock import db_write_lock
from app.models.processing import ProcessingLog

router = APIRouter(tags=["reidentify"])

GBIF_OCCURRENCE_URL = "https://api.gbif.org/v1/occurrence/search"
GBIF_SPECIES_URL    = "https://api.gbif.org/v1/species/search"
GBIF_TIMEOUT_S      = 10


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _log_edit(
    session: AsyncSession,
    obs: Observation,
    field_name: str,
    old_value: Optional[str],
    new_value: Optional[str],
) -> None:
    session.add(ObservationEdit(
        observation_id=obs.id,
        field_name=field_name,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        edited_by="human",
    ))


async def _gbif_species_search(query: str, limit: int) -> List[Dict]:
    """Search GBIF name index. Returns list of dicts; empty list on any failure."""
    try:
        async with httpx.AsyncClient(timeout=GBIF_TIMEOUT_S) as client:
            resp = await client.get(
                GBIF_SPECIES_URL,
                params={"q": query, "limit": limit, "rank": "SPECIES"},
            )
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:
        return []

    out = []
    for item in data.get("results", []):
        sci = item.get("canonicalName") or item.get("scientificName") or ""
        if not sci.strip():
            continue
        out.append({
            "scientific_name": sci.strip(),
            "common_name": item.get("vernacularName"),
            "rank": (item.get("rank") or "").lower(),
            "family": item.get("family"),
            "genus": item.get("genus"),
            "gbif_key": item.get("key"),
            "source": "gbif",
        })
    return out


# ---------------------------------------------------------------------------
# POST /api/observations/{id}/reidentify
# ---------------------------------------------------------------------------

PLANTNET_ORGANS = frozenset({"auto", "leaf", "flower", "fruit", "bark", "habit"})


class ReidentifyRequest(BaseModel):
    # Which sources to use — None means "use all available"
    sources: Optional[List[str]] = None   # e.g. ["plantnet", "inaturalist"]
    # PlantNet organ hint — "auto" lets PlantNet detect organ type automatically
    organ: str = "auto"                   # auto | leaf | flower | fruit | bark | habit


@router.post("/api/observations/{observation_id}/reidentify")
async def reidentify_observation(
    observation_id: int,
    body: Optional[ReidentifyRequest] = None,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Run identification sources in parallel, merge and return top 5.
    Never raises for API failures — degraded results are returned instead.

    Body (optional JSON):
      sources: ["plantnet", "inaturalist"]  — subset to run; omit for all
      organ:   "auto" | "leaf" | "flower" | "fruit" | "bark" | "habit"
    """
    obs = await db.get(Observation, observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")

    path = Path(obs.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Photo file not found on disk")

    api_key    = settings.plantnet_api_key
    inat_token = settings.inaturalist_api_token

    # Determine which sources to query
    requested = set(body.sources or []) if body and body.sources else None
    obs_cat = (obs.obs_category or "plant").lower()

    # Category default: fungi always skips PlantNet
    if obs_cat == "fungi" and requested is None:
        requested = {"inaturalist"}

    use_pn   = (requested is None or "plantnet"    in requested) and bool(api_key)
    use_inat = (requested is None or "inaturalist" in requested) and bool(inat_token)

    # Organ hint — sanitise to known values; fall back to "auto"
    _organ = (body.organ if body and body.organ else "auto").lower()
    if _organ not in PLANTNET_ORGANS:
        _organ = "auto"

    # Run in parallel — never let one failure kill the other
    async def _plantnet() -> object:
        if not use_pn:
            return None
        try:
            return await plantnet_identify(
                path, api_key=api_key,
                lat=obs.latitude, lng=obs.longitude,
                organ=_organ,
            )
        except PlantNetError:
            return None
        except Exception:
            return None

    pn_result, inat_candidates = await asyncio.gather(
        _plantnet(),
        inat_score(
            path, api_token=inat_token,
            lat=obs.latitude, lng=obs.longitude,
            observed_on=(obs.photo_taken_at.date().isoformat()
                         if obs.photo_taken_at else None),
        ) if use_inat else asyncio.sleep(0, result=[]),
    )

    # Merge results keyed by lowercased scientific_name
    merged: Dict[str, dict] = {}

    def _add(sci: str, common: Optional[str], common_names: List[str],
             score: float, source: str) -> None:
        key = sci.lower().strip()
        if not key:
            return
        if key not in merged:
            merged[key] = {
                "scientific_name": sci,
                "common_name": common,
                "common_names": list(common_names),
                "confidence": score,
                "sources": {source},
            }
        else:
            if score > merged[key]["confidence"]:
                merged[key]["confidence"] = score
            merged[key]["sources"].add(source)
            if common and not merged[key]["common_name"]:
                merged[key]["common_name"] = common
            if common_names and not merged[key]["common_names"]:
                merged[key]["common_names"] = list(common_names)

    if pn_result is not None:
        for c in (pn_result.candidates or []):
            _add(c.scientific_name, c.common_names[0] if c.common_names else None,
                 c.common_names, c.score, "plantnet")

    for c in (inat_candidates or []):
        _add(c.scientific_name, c.common_name, c.common_names, c.score, "inaturalist")

    top5 = sorted(merged.values(), key=lambda x: x["confidence"], reverse=True)[:5]

    results = []
    for i, item in enumerate(top5):
        srcs: Set[str] = item["sources"]
        source_label = "both" if len(srcs) > 1 else next(iter(srcs))
        results.append({
            "rank": i + 1,
            "scientific_name": item["scientific_name"],
            "common_name": item["common_name"],
            "common_names": item["common_names"],
            "confidence": round(item["confidence"], 4),
            "source": source_label,
        })

    warnings = []
    if not api_key:
        warnings.append("PlantNet: no API key configured (set PLANTNET_API_KEY in .env)")
    elif pn_result is None:
        warnings.append("PlantNet: no results (API may have returned an error or rate limit)")
    if not inat_token:
        warnings.append(
            "iNaturalist: no API token configured — "
            "get yours at https://www.inaturalist.org/users/api_token "
            "and set INATURALIST_API_TOKEN in .env"
        )
    elif not inat_candidates:
        warnings.append("iNaturalist: no results (API error)")

    return {
        "observation_id": observation_id,
        "results": results,
        "plantnet_ok": pn_result is not None,
        "inaturalist_ok": bool(inat_candidates),
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# POST /api/observations/{id}/second-opinion
# ---------------------------------------------------------------------------

@router.post("/api/observations/{observation_id}/second-opinion")
async def second_opinion(
    observation_id: int,
    organ: str = Query(default="auto"),
    include_related_images: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Query PlantNet (image), iNaturalist (image), and GBIF (name search) in
    parallel and return a merged, ranked list of species candidates.

    PlantNet and iNat do image-based scoring.  GBIF searches by the
    observation's current species_primary to confirm / offer alternatives.
    All three run concurrently — any single failure degrades gracefully.

    Query params:
      organ:                  PlantNet organ hint — auto | leaf | flower | fruit | bark | habit
      include_related_images: When true, each PlantNet candidate includes up to 2 reference
                              image URLs from PlantNet's herbarium for visual comparison.
                              Uses one extra API call against the daily quota.
    """
    obs = await db.get(Observation, observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")

    path = Path(obs.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Photo file not found on disk")

    api_key    = settings.plantnet_api_key
    inat_token = settings.inaturalist_api_token
    gbif_query = (obs.species_primary or "").strip()

    # Sanitise organ param — unknown values fall back to "auto"
    _organ = organ.lower() if organ else "auto"
    if _organ not in PLANTNET_ORGANS:
        _organ = "auto"

    async def _plantnet() -> object:
        if not api_key:
            return None
        try:
            return await plantnet_identify(
                path, api_key=api_key,
                lat=obs.latitude, lng=obs.longitude,
                organ=_organ,
                include_related_images=include_related_images,
            )
        except Exception:
            return None

    async def _inat() -> list:
        return await inat_score(
            path, api_token=inat_token,
            lat=obs.latitude, lng=obs.longitude,
            observed_on=(obs.photo_taken_at.date().isoformat()
                         if obs.photo_taken_at else None),
        )

    async def _gbif() -> list:
        if not gbif_query:
            return []
        return await _gbif_species_search(gbif_query, 6)

    pn_result, inat_candidates, gbif_results = await asyncio.gather(
        _plantnet(), _inat(), _gbif(),
    )

    # Remaining PlantNet quota from the raw response (when available)
    remaining_quota: Optional[int] = None
    if pn_result is not None:
        rq = pn_result.raw_response.get("remainingIdentificationRequests")
        if rq is not None:
            try:
                remaining_quota = int(rq)
            except (TypeError, ValueError):
                pass

    # Merge image-based candidates keyed by lowercased scientific name.
    # Scores are stored per-source on a normalised 0–1 scale so they can be
    # combined meaningfully: PlantNet already returns 0–1; iNaturalist's
    # combined_score is a 0–100 percentage and is divided by 100 at the call
    # site below.  The final per-species confidence is computed after merging
    # (average when two sources agree, single source's score otherwise).
    merged: Dict[str, dict] = {}

    def _add_img(sci: str, common: Optional[str], common_names: List[str],
                 score: float, source: str,
                 ref_images: Optional[List[dict]] = None) -> None:
        key = sci.lower().strip()
        if not key:
            return
        if key not in merged:
            merged[key] = {
                "scientific_name": sci,
                "common_name": common,
                "common_names": list(common_names),
                "scores": {},          # source -> normalised 0–1 score
                "sources": set(),
                "reference_images": list(ref_images or []),
            }
        entry = merged[key]
        entry["sources"].add(source)
        entry["scores"][source] = score
        if common and not entry["common_name"]:
            entry["common_name"] = common
        if common_names and not entry["common_names"]:
            entry["common_names"] = list(common_names)
        # Keep PlantNet reference images if the existing entry has none
        if ref_images and not entry["reference_images"]:
            entry["reference_images"] = list(ref_images)

    if pn_result is not None:
        for c in (pn_result.candidates or []):
            cn = c.common_names[0] if c.common_names else None
            _add_img(c.scientific_name, cn, c.common_names, c.score, "plantnet",
                     ref_images=c.images)

    for c in (inat_candidates or []):
        # iNaturalist combined_score is 0–100 — normalise to 0–1 to match PlantNet
        inat_norm = min(c.score / 100.0, 1.0)
        _add_img(c.scientific_name, c.common_name, c.common_names, inat_norm, "inaturalist")

    # Add GBIF-only names not already in image results (fixed score 0.50 display)
    for g in (gbif_results or []):
        key = g["scientific_name"].lower().strip()
        if key not in merged:
            merged[key] = {
                "scientific_name": g["scientific_name"],
                "common_name": g.get("common_name"),
                "common_names": [g["common_name"]] if g.get("common_name") else [],
                "scores": {"gbif": 0.50},   # name-match only — not image confidence
                "sources": {"gbif"},
                "reference_images": [],
            }
        else:
            merged[key]["sources"].add("gbif")
            merged[key]["scores"].setdefault("gbif", 0.50)

    # Resolve a single 0–1 confidence per species:
    #   both image sources present -> average of the two
    #   one image source present   -> that source's score
    #   GBIF-only                  -> fixed 0.50 name-match score
    for entry in merged.values():
        pn   = entry["scores"].get("plantnet")
        inat = entry["scores"].get("inaturalist")
        if pn is not None and inat is not None:
            entry["confidence"] = (pn + inat) / 2.0
        elif pn is not None:
            entry["confidence"] = pn
        elif inat is not None:
            entry["confidence"] = inat
        else:
            entry["confidence"] = entry["scores"].get("gbif", 0.50)

    top10 = sorted(merged.values(), key=lambda x: x["confidence"], reverse=True)[:10]

    results = []
    for i, item in enumerate(top10):
        srcs: Set[str] = item["sources"]
        results.append({
            "rank": i + 1,
            "scientific_name": item["scientific_name"],
            "common_name": item["common_name"],
            "common_names": item["common_names"],
            "confidence": round(item["confidence"], 4),
            "sources": sorted(srcs),          # list so JSON-serialisable
            "reference_images": item.get("reference_images", []),
        })

    warnings = []
    if not api_key:
        warnings.append("PlantNet: no API key — set PLANTNET_API_KEY in .env")
    elif pn_result is None:
        warnings.append("PlantNet: no results (API error or rate limit)")
    if not inat_token:
        warnings.append("iNaturalist: no token — set INATURALIST_API_TOKEN in .env")
    elif not inat_candidates:
        warnings.append("iNaturalist: no results (API error)")
    if not gbif_query:
        warnings.append("GBIF: skipped — no current species name to search")
    elif not gbif_results:
        warnings.append("GBIF: no backbone results for current species name")

    return {
        "observation_id": observation_id,
        "results": results,
        "plantnet_ok": pn_result is not None,
        "inaturalist_ok": bool(inat_candidates),
        "gbif_ok": bool(gbif_results),
        "warnings": warnings,
        # Remaining PlantNet API calls today (populated from raw response when available)
        "remaining_quota": remaining_quota,
    }


# ---------------------------------------------------------------------------
# POST /api/observations/{id}/retry-identify   (Prompt G — Retry ID)
# ---------------------------------------------------------------------------
#
# Scoped feature for UNNAMED observations in the review queue.  Re-runs the
# identification sources appropriate to the observation's obs_category and
# returns every candidate grouped by API source for human confirmation.
#
#   plant  -> PlantNet (image) + iNaturalist (image)
#   fungi  -> iNaturalist (image) + Mushroom Observer (name cross-check)
#
# Mushroom Observer has no public computer-vision endpoint, so for fungi it is
# queried by name against the iNaturalist candidates to confirm which species
# are recorded there (and link to the MO record).  This never auto-approves —
# all results flow back to the dropdown.  It does not touch reidentify or
# second-opinion behaviour.

# How many iNat candidate names to cross-check against Mushroom Observer.
_MO_CROSSCHECK_LIMIT = 6
# Per-group candidate display cap.
_RETRY_GROUP_CAP = 8


@router.post("/api/observations/{observation_id}/retry-identify")
async def retry_identify(
    observation_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Re-run identification for an unnamed observation and return candidates
    grouped by API source.  Never auto-approves; never raises on API failure.
    """
    obs = await db.get(Observation, observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")

    path = Path(obs.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Photo file not found on disk")

    api_key    = settings.plantnet_api_key
    inat_token = settings.inaturalist_api_token
    obs_cat    = (obs.obs_category or "plant").lower()
    is_fungi   = obs_cat == "fungi"

    # Source matrix by category — PlantNet is plant-only.
    use_pn   = (not is_fungi) and bool(api_key)
    use_inat = bool(inat_token)

    async def _plantnet() -> object:
        if not use_pn:
            return None
        try:
            return await plantnet_identify(
                path, api_key=api_key,
                lat=obs.latitude, lng=obs.longitude,
            )
        except Exception:
            return None

    pn_result, inat_candidates = await asyncio.gather(
        _plantnet(),
        inat_score(
            path, api_token=inat_token,
            lat=obs.latitude, lng=obs.longitude,
            observed_on=(obs.photo_taken_at.date().isoformat()
                         if obs.photo_taken_at else None),
        ) if use_inat else asyncio.sleep(0, result=[]),
    )

    groups: List[dict] = []

    # PlantNet group (plants only) — scores already 0–1.
    if use_pn:
        pn_cands = []
        if pn_result is not None:
            for c in (pn_result.candidates or []):
                pn_cands.append({
                    "scientific_name": c.scientific_name,
                    "common_name": c.common_names[0] if c.common_names else None,
                    "confidence": round(c.score, 4),
                })
        groups.append({
            "source": "plantnet", "label": "PlantNet", "scored": True,
            "candidates": pn_cands[:_RETRY_GROUP_CAP],
        })

    # iNaturalist group (plants + fungi) — score_image already normalises to 0–1.
    if use_inat:
        inat_cands = []
        for c in (inat_candidates or []):
            inat_cands.append({
                "scientific_name": c.scientific_name,
                "common_name": c.common_name,
                "confidence": round(c.score, 4),
            })
        groups.append({
            "source": "inaturalist", "label": "iNaturalist", "scored": True,
            "candidates": inat_cands[:_RETRY_GROUP_CAP],
        })

    # Mushroom Observer group (fungi only) — name cross-check on iNat candidates.
    if is_fungi:
        mo_cands = []
        names = [c.scientific_name for c in (inat_candidates or []) if c.scientific_name][:_MO_CROSSCHECK_LIMIT]
        if names:
            mo_results = await asyncio.gather(
                *[mo.search_by_name(n) for n in names], return_exceptions=True
            )
            for res in mo_results:
                if isinstance(res, Exception) or not res:
                    continue
                mo_cands.append({
                    "scientific_name": res.scientific_name,
                    "common_name": None,
                    "confidence": None,                       # name-match only — no image score
                    "observation_count": res.observation_count,
                    "mo_url": res.mo_url,
                })
        groups.append({
            "source": "mushroom_observer", "label": "Mushroom Observer", "scored": False,
            "candidates": mo_cands,
        })

    total = sum(len(g["candidates"]) for g in groups)

    warnings = []
    if use_pn and pn_result is None:
        warnings.append("PlantNet: no results (API error or rate limit)")
    elif not is_fungi and not api_key:
        warnings.append("PlantNet: no API key configured (set PLANTNET_API_KEY in .env)")
    if not inat_token:
        warnings.append(
            "iNaturalist: no API token configured — refresh at "
            "inaturalist.org/users/api_token and set INATURALIST_API_TOKEN in .env"
        )
    elif not inat_candidates:
        warnings.append("iNaturalist: no results (API error or expired token)")

    return {
        "observation_id": observation_id,
        "obs_category": obs_cat,
        "groups": groups,
        "total": total,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# POST /api/observations/{id}/retry-confirm   (Prompt G — Retry ID approve)
# ---------------------------------------------------------------------------

class RetryConfirmRequest(BaseModel):
    scientific_name: str
    common_name: Optional[str] = None
    confidence: Optional[float] = None
    source_api: Optional[str] = None       # plantnet | inaturalist | mushroom_observer


@router.post("/api/observations/{observation_id}/retry-confirm")
async def retry_confirm(
    observation_id: int,
    background_tasks: BackgroundTasks,
    body: RetryConfirmRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Approve a candidate returned by retry-identify: set identification_status
    to 'identified' and species_primary to the selected name, then trigger the
    standard enrichment flow.  Does not auto-approve regardless of confidence.
    """
    obs = await db.get(Observation, observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")

    new_species = body.scientific_name.strip()
    if not new_species:
        raise HTTPException(status_code=400, detail="scientific_name is required")

    old_species = obs.species_primary
    old_id_status = obs.identification_status

    await set_observation_species(db, obs, new_species)
    obs.human_corrected = True
    obs.reviewed_at = datetime.utcnow()

    # Strip the moved-off name from this obs's candidate cache so the stale old
    # primary stops lingering there (it is otherwise never rewritten on re-ID).
    if old_species and old_species != new_species:
        from app.services.species_link import strip_candidate_from_obs
        strip_candidate_from_obs(obs, old_species)

    if old_species != new_species:
        _log_edit(db, obs, "species_primary", old_species, new_species)
    if old_id_status != "identified":
        _log_edit(db, obs, "identification_status", old_id_status, "identified")
        obs.identification_status = "identified"

    db.add(ProcessingLog(
        observation_id=obs.id,
        stage="retry_identification",
        status="success",
        message=(
            f"action=retry_id_confirm triggered_by=user "
            f"species={new_species} "
            f"source_api={body.source_api or 'none'} "
            f"confidence={body.confidence if body.confidence is not None else 'none'}"
        ),
    ))
    await db.commit()

    # Standard enrichment flow — same trigger used by manual confirmation paths.
    from app.services.enrichment import trigger_ai_drafts_for_species
    background_tasks.add_task(trigger_ai_drafts_for_species, new_species)

    return {
        "ok": True,
        "observation_id": observation_id,
        "species_primary": obs.species_primary,
        "identification_status": obs.identification_status,
    }


# ---------------------------------------------------------------------------
# POST /api/observations/{id}/confirm-species
# ---------------------------------------------------------------------------

class ConfirmSpeciesRequest(BaseModel):
    scientific_name: str
    common_name: Optional[str] = None
    confidence: Optional[float] = None
    source: str = "manual_reidentification"  # or "manual_entry"


@router.post("/api/observations/{observation_id}/confirm-species")
async def confirm_species(
    observation_id: int,
    background_tasks: BackgroundTasks,
    body: ConfirmSpeciesRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Write a user-selected species to the observation.
    source = 'manual_reidentification' (from API results) |
             'manual_entry' (typed by user + GBIF/iNat lookup)
    """
    obs = await db.get(Observation, observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")

    new_species = collapse_autonym(body.scientific_name.strip())
    if not new_species:
        raise HTTPException(status_code=400, detail="scientific_name is required")

    from app.services.observation_service import update_observation_status
    await update_observation_status(
        session=db,
        obs=obs,
        review_status="manually_verified",
        species_name=new_species,
        update_species=True,
        edited_by="human",
    )

    db.add(ProcessingLog(
        observation_id=obs.id,
        stage="manual_review",
        status="success",
        message=(
            f"action={body.source} triggered_by=user "
            f"species={new_species} "
            f"common_name={body.common_name or 'none'} "
            f"confidence={body.confidence or 'none'}"
        ),
    ))
    async with db_write_lock():
        await db.commit()

    # Trigger AI draft generation for the confirmed species name
    from app.services.enrichment import trigger_ai_drafts_for_species
    background_tasks.add_task(trigger_ai_drafts_for_species, new_species)

    return {
        "ok": True,
        "observation_id": observation_id,
        "species_primary": obs.species_primary,
        "review_status": obs.review_status,
    }


# ---------------------------------------------------------------------------
# GET /api/species/lookup
# ---------------------------------------------------------------------------

# Ranks considered species-level or below (GBIF nomenclature + iNat equivalents).
# Genus-level and above are filtered out of lookup results.
_SPECIES_RANKS: Set[str] = {
    "species", "subspecies", "variety", "form", "infraspecies",
    "infraspecific", "cultivar", "hybrid",
}


def _is_species_rank(rank: Optional[str]) -> bool:
    """Return True when rank is species-level or finer, or when rank is unknown."""
    if not rank:
        return True  # rank unknown — include rather than silently drop
    return rank.lower() in _SPECIES_RANKS


async def _inat_vision_for_obs(obs: Observation) -> List[dict]:
    """
    Run iNat vision against an observation's local image file.
    Returns a list of lookup-shaped dicts (with vision=True marker).
    Returns [] silently on any failure.
    """
    token = settings.inaturalist_api_token
    if not token:
        return []
    if not obs.file_path:
        return []
    path = Path(obs.file_path)
    if not path.exists():
        return []

    candidates = await inat_score(
        path,
        api_token=token,
        lat=obs.latitude,
        lng=obs.longitude,
    )
    out = []
    for c in candidates:
        if not _is_species_rank(c.rank):
            continue
        out.append({
            "scientific_name": c.scientific_name,
            "common_name": c.common_name,
            "rank": c.rank,
            "family": None,
            "genus": None,
            "source": "inat_vision",
            "vision": True,
            "score": round(c.score * 100, 1),
        })
    return out


@router.get("/api/species/lookup")
async def species_lookup(
    q: str = Query("", min_length=0),
    obs_id: Optional[int] = Query(None),
    limit: int = Query(5, ge=1, le=10),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Look up a species name against GBIF and iNaturalist in parallel.
    Also runs iNat vision against the observation's photo when obs_id is supplied.

    Ranking rules:
    - Genus-level results filtered out (species and below only).
    - Name-search results where the search term matches the common name rank first.
    - Name-search results come before vision results.
    - Vision results are deduped against name-search results by scientific name.
    - When q is empty, vision results only are returned (requires obs_id).
    """
    query = q.strip()

    # Fetch observation for vision (if obs_id provided)
    obs: Optional[Observation] = None
    if obs_id is not None:
        obs = await db.get(Observation, obs_id)

    # ── Name search tasks (skip when q is empty) ──────────────────────────────
    name_results: List[dict] = []
    if query:
        gbif_task  = _gbif_species_search(query, limit)
        inat_task  = inat_taxa(query, limit)
        async def _no_vision() -> List[dict]:
            return []

        vision_task = _inat_vision_for_obs(obs) if obs else _no_vision()

        gbif_results, inat_results, vision_raw = await asyncio.gather(
            gbif_task, inat_task, vision_task, return_exceptions=True
        )

        merged: Dict[str, dict] = {}

        if not isinstance(gbif_results, Exception):
            for item in (gbif_results or []):
                if not _is_species_rank(item.get("rank")):
                    continue
                key = item["scientific_name"].lower()
                if key not in merged:
                    merged[key] = dict(item)

        if not isinstance(inat_results, Exception):
            for t in (inat_results or []):
                if not _is_species_rank(t.rank):
                    continue
                key = t.scientific_name.lower()
                if key not in merged:
                    merged[key] = {
                        "scientific_name": t.scientific_name,
                        "common_name": t.common_name,
                        "rank": t.rank,
                        "family": None,
                        "genus": None,
                        "source": "inaturalist",
                    }
                elif t.common_name and not merged[key].get("common_name"):
                    merged[key]["common_name"] = t.common_name

        # Boost: entries whose common name contains the query term rank first.
        ql = query.lower()
        def _name_rank(item: dict) -> int:
            cn = (item.get("common_name") or "").lower()
            return 0 if ql in cn else 1

        name_results = sorted(merged.values(), key=_name_rank)

        # Vision results — dedupe against name-search hits
        seen = {r["scientific_name"].lower() for r in name_results}
        if not isinstance(vision_raw, Exception):
            for v in (vision_raw or []):
                if v["scientific_name"].lower() not in seen:
                    name_results.append(v)

        return {"results": name_results[:limit * 2]}  # wider cap so vision appends show

    else:
        # Empty query — vision only
        if not obs:
            return {"results": []}
        vision_raw = await _inat_vision_for_obs(obs)
        return {"results": vision_raw[:limit]}


# ---------------------------------------------------------------------------
# POST /api/observations/{id}/gbif-check
# ---------------------------------------------------------------------------
# POST (not GET): this handler persists gbif_occurrence_json + makes an outbound
# call, so it must not be a mutating GET. As a non-whitelisted POST it is also
# blocked for tunnel guests by the guest middleware → curator-only.

@router.post("/api/observations/{observation_id}/gbif-check")
async def gbif_uk_check(
    observation_id: int,
    species: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Check GBIF for UK occurrences of the observation's species.
    Display-only. Result is also stored on the observation for Phase 6.
    """
    obs = await db.get(Observation, observation_id)
    if not obs:
        raise HTTPException(status_code=404, detail="Observation not found")

    name = (species or obs.species_primary or "").strip()
    if not name:
        return {"found": False, "count": 0, "summary": "No species identified yet"}

    try:
        async with httpx.AsyncClient(timeout=GBIF_TIMEOUT_S) as client:
            resp = await client.get(
                GBIF_OCCURRENCE_URL,
                params={"scientificName": name, "country": "GB", "limit": 1},
            )
        if resp.status_code != 200:
            return {"found": False, "count": 0, "summary": "GBIF check unavailable"}
        data = resp.json()
    except Exception:
        return {"found": False, "count": 0, "summary": "GBIF check unavailable"}

    count = data.get("count", 0)

    if count == 0:
        summary = "No UK records in GBIF"
        found = False
    elif count < 10:
        summary = f"Rare in UK — {count} GBIF record{'s' if count != 1 else ''}"
        found = True
    elif count < 100:
        summary = f"Uncommon in UK — {count} GBIF records"
        found = True
    elif count < 1000:
        summary = f"Recorded in UK — {count:,} GBIF records"
        found = True
    else:
        summary = f"Common in UK — {count:,} GBIF records"
        found = True

    result = {"found": found, "count": count, "summary": summary}

    # Persist for Phase 6 species profiles (best-effort)
    try:
        if hasattr(obs, "gbif_occurrence_json"):
            obs.gbif_occurrence_json = json.dumps(result)
            await db.commit()
    except Exception:
        pass

    return result
