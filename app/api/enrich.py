"""
Enrichment API — run enrichment from the web UI with live polling.

GET  /api/enrich/status          — current state + last-run summary + empty-species count
POST /api/enrich/run             — start full enrichment in background (idempotent if running)
POST /api/enrich/re-enrich-empty — re-fetch PFAF+Wikidata for confirmed species whose
                                   culinary_info row exists but edible_parts is NULL
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from sqlalchemy import func, select, text

from app.database import AsyncSessionLocal
from app.models.culinary import CulinaryInfo
from app.models.observation import Observation
from app.models.species import EnrichmentSource, Species

router = APIRouter(prefix="/api/enrich", tags=["enrich"])

_state: dict = {
    "running":       False,
    "current":       0,
    "total":         0,
    "progress":      [],    # [{name, status}, …] — capped at _MAX_LOG
    "last_run":      None,  # ISO datetime of last completed run
    "last_counters": None,  # {total, enriched, partial, not_found, skipped, failed}
    "last_trigger":  None,  # "manual" | "auto" | "re-enrich-empty"
}

_MAX_LOG = 300


async def _count_empty_species_split() -> dict:
    """
    Count confirmed species with culinary_info but no edible_parts, split into:
    - fillable: PFAF has never been attempted (re-enriching may help)
    - permanent: PFAF was attempted and returned nothing (fungi, ornamentals, non-PFAF regionals)
    """
    async with AsyncSessionLocal() as session:
        confirmed_names = (await session.execute(
            select(Observation.species_primary)
            .where(Observation.review_status.in_(["approved", "manually_verified"]))
            .where(Observation.species_primary.is_not(None))
            .where(Observation.species_primary != "")
            .distinct()
        )).scalars().all()

        if not confirmed_names:
            return {"fillable": 0, "permanent": 0}

        # EXISTS subquery: has a PFAF enrichment attempt on record
        pfaf_tried = (
            select(EnrichmentSource.id)
            .where(
                EnrichmentSource.species_id == CulinaryInfo.species_id,
                EnrichmentSource.source_name == "pfaf",
            )
            .correlate(CulinaryInfo)
            .exists()
        )

        base = (
            select(func.count())
            .select_from(CulinaryInfo)
            .join(Species, Species.id == CulinaryInfo.species_id)
            .where(Species.scientific_name.in_(confirmed_names))
            .where(CulinaryInfo.edible_parts.is_(None))
        )

        fillable  = await session.scalar(base.where(~pfaf_tried))
        permanent = await session.scalar(base.where(pfaf_tried))
        return {"fillable": fillable or 0, "permanent": permanent or 0}


@router.get("/status")
async def enrich_status():
    empty = await _count_empty_species_split()
    return {
        "running":           _state["running"],
        "current":           _state["current"],
        "total":             _state["total"],
        "progress":          _state["progress"][-60:],
        "last_run":          _state["last_run"],
        "last_counters":     _state["last_counters"],
        "last_trigger":      _state["last_trigger"],
        "empty_pfaf_fillable": empty["fillable"],
        "empty_permanently":   empty["permanent"],
    }


@router.get("/last-run-table")
async def last_run_table():
    """
    Returns a per-species, per-source breakdown of the most recent enrichment run.

    For each species that appeared in the last run's progress log, returns:
      - run_status: "enriched" | "partial" | "not_found" | "skipped" | "failed"
      - per source (pfaf, wikidata, inat, trompenburg, culinary_links):
          "filled"        — source returned data (extraction_confidence > 0)
          "no-data"       — source was tried, nothing extracted (confidence == 0)
          "not-attempted" — no enrichment_sources row exists for this source

    Sorted by severity: failed > not_found > partial > enriched > skipped.
    If no run has been recorded this session (_state["progress"] is empty),
    falls back to the 100 most recently touched species across all sources.
    """
    _SOURCE_NAMES = ("pfaf", "wikidata", "inaturalist_taxon", "trompenburg", "culinary_links")
    _STATUS_ORDER = {"failed": 0, "not_found": 1, "partial": 2, "enriched": 3, "skipped": 4}

    # Build the set of species from the last run's progress log
    progress = _state.get("progress") or []
    run_map: dict[str, str] = {p["name"]: p["status"] for p in progress}

    async with AsyncSessionLocal() as session:
        if run_map:
            species_names = list(run_map.keys())
        else:
            # No in-memory run recorded — use the 100 most recently fetched species
            recent = (await session.execute(
                select(Species.scientific_name)
                .join(EnrichmentSource, EnrichmentSource.species_id == Species.id)
                .group_by(Species.id)
                .order_by(func.max(EnrichmentSource.retrieved_at).desc())
                .limit(100)
            )).scalars().all()
            species_names = list(recent)

        if not species_names:
            return {
                "last_run": _state.get("last_run"),
                "last_trigger": _state.get("last_trigger"),
                "last_counters": _state.get("last_counters"),
                "rows": [],
            }

        # Fetch species id → name map
        sp_rows = (await session.execute(
            select(Species.id, Species.scientific_name)
            .where(Species.scientific_name.in_(species_names))
        )).all()
        name_to_id = {r.scientific_name: r.id for r in sp_rows}
        id_to_name = {v: k for k, v in name_to_id.items()}
        sp_ids = list(name_to_id.values())

        # Fetch most-recent enrichment_sources row per (species_id, source_name)
        # SQLite: use a subquery with MAX(id) as proxy for most recent
        src_rows = (await session.execute(
            select(
                EnrichmentSource.species_id,
                EnrichmentSource.source_name,
                EnrichmentSource.extraction_confidence,
                EnrichmentSource.retrieved_at,
                EnrichmentSource.source_url,
            )
            .where(EnrichmentSource.species_id.in_(sp_ids))
            .where(EnrichmentSource.id.in_(
                select(func.max(EnrichmentSource.id))
                .where(EnrichmentSource.species_id.in_(sp_ids))
                .group_by(EnrichmentSource.species_id, EnrichmentSource.source_name)
            ))
        )).all()

    # Build per-species source map
    src_map: dict[int, dict] = {}
    for r in src_rows:
        if r.species_id not in src_map:
            src_map[r.species_id] = {}
        conf = r.extraction_confidence or 0.0
        status = "filled" if conf > 0 else "no-data"
        src_map[r.species_id][r.source_name] = {
            "status": status,
            "confidence": round(conf, 2),
            "retrieved_at": r.retrieved_at.isoformat() if r.retrieved_at else None,
            "source_url": r.source_url,
        }

    rows = []
    for name in species_names:
        sp_id = name_to_id.get(name)
        sources = src_map.get(sp_id, {}) if sp_id else {}
        row = {
            "scientific_name": name,
            "run_status": run_map.get(name),  # None if fallback mode
        }
        for src in _SOURCE_NAMES:
            row[src] = sources.get(src, {"status": "not-attempted", "confidence": None})
        rows.append(row)

    # Sort by severity
    rows.sort(key=lambda r: (_STATUS_ORDER.get(r["run_status"] or "skipped", 4), r["scientific_name"]))

    return {
        "last_run": _state.get("last_run"),
        "last_trigger": _state.get("last_trigger"),
        "last_counters": _state.get("last_counters"),
        "rows": rows,
    }


@router.post("/run")
async def enrich_run(background_tasks: BackgroundTasks):
    if _state["running"]:
        return {"status": "already_running"}
    background_tasks.add_task(_run_enrichment_task, None, "manual")
    return {"status": "started"}


@router.post("/re-enrich-empty")
async def re_enrich_empty(background_tasks: BackgroundTasks):
    """
    Re-fetch PFAF + Wikidata for all confirmed species that already have a
    culinary_info row but whose edible_parts field is NULL (i.e. the original
    enrichment run found nothing).  Uses fill_empty_only=True so manually-set
    or already-present fields are never overwritten.
    """
    if _state["running"]:
        return {"status": "already_running"}

    # Collect the target species names
    async with AsyncSessionLocal() as session:
        confirmed_names = (await session.execute(
            select(Observation.species_primary)
            .where(Observation.review_status.in_(["approved", "manually_verified"]))
            .where(Observation.species_primary.is_not(None))
            .where(Observation.species_primary != "")
            .distinct()
        )).scalars().all()

        from sqlalchemy import func
        rows = (await session.execute(
            select(Species.scientific_name)
            .join(CulinaryInfo, CulinaryInfo.species_id == Species.id)
            .where(Species.scientific_name.in_(confirmed_names))
            .where(CulinaryInfo.edible_parts.is_(None))
            .order_by(Species.scientific_name)
        )).scalars().all()

    target = list(rows)
    if not target:
        return {"status": "nothing_to_do", "count": 0}

    background_tasks.add_task(
        _run_enrichment_task, target, "re-enrich-empty",
        re_enrich=True, fill_empty_only=True,
    )
    return {"status": "started", "count": len(target), "species": target}


async def _run_enrichment_task(
    species_list: Optional[list],
    trigger: str = "manual",
    re_enrich: bool = False,
    fill_empty_only: bool = False,
) -> None:
    """
    Shared enrichment runner used by both the UI button and the Syncthing
    auto-enrich path.  species_list=None means full batch.
    """
    if _state["running"]:
        return

    _state["running"]  = True
    _state["current"]  = 0
    _state["total"]    = 0
    _state["progress"] = []
    _state["last_trigger"] = trigger

    def _cb(current: int, total: int, name: str, status: str) -> None:
        _state["current"] = current
        _state["total"]   = total
        _state["progress"].append({"name": name, "status": status})
        if len(_state["progress"]) > _MAX_LOG:
            _state["progress"] = _state["progress"][-_MAX_LOG:]

    try:
        from app.services.enrichment import run_enrichment_batch
        async with AsyncSessionLocal() as session:
            counters = await run_enrichment_batch(
                session,
                species_list=species_list,
                re_enrich=re_enrich,
                fill_empty_only=fill_empty_only,
                progress_cb=_cb,
            )
        _state["last_counters"] = counters
        _state["last_run"]      = datetime.utcnow().isoformat()
    finally:
        _state["running"] = False
