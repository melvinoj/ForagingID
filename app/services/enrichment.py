"""
Culinary enrichment pipeline — Phase 6 + Phase 8.

Design rules:
  - Strictly separate from ingestion and identification pipelines
  - Raw source data stored BEFORE parsing — never discarded
  - PFAF wins on culinary/safety fields; Wikidata fills taxonomy gaps
  - Phase 8 adds: iNaturalist taxon description, TrompenburgPlants,
    culinary link scrapers (Eatweeds, Galloway Wild Foods, Wildman Steve Brill,
    Botanical.com, Wildfoods UK), and Claude AI draft generation
  - AI-generated drafts go into species_ai_drafts (pending) — never shown
    until user approves in the review queue
  - Enrichment is best-effort — failures log a warning, never abort the batch
  - Idempotent: re-running skips already-enriched species unless re_enrich=True
  - Culinary link sources: skip if already fetched; retry only when re_enrich=True
    (which is triggered on species rename, so the name-change retry rule is natural)
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Callable, Dict, Optional

from sqlalchemy import select
from sqlalchemy.exc import OperationalError as _SAOperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.taxonomy import collapse_autonym, normalize_taxon_key
from app.integrations.pfaf import PFAFResult, fetch_pfaf
from app.integrations.wikidata import WikidataResult, fetch_wikidata, fetch_wikidata_batch
from app.integrations.trompenburg import TrompenburgResult, fetch_trompenburg
from app.integrations.inaturalist import INatTaxonDescription, fetch_taxon_description
from app.integrations.culinary_links import CulinaryLink, fetch_culinary_links
from app.integrations.claude_draft import AIDraftResult, generate_ai_drafts
from app.models.culinary import CulinaryInfo
from app.models.observation import Observation
from app.models.species import CulinaryInfoHistory, EnrichmentSource, Species, SpeciesAIDraft

log = logging.getLogger(__name__)

# Fields that are AI-interpreted, not sourced from external data
_AI_GENERATED_FIELDS = [
    "flavour_profile", "pairing_ideas", "workshop_value_score",
    "taste_notes", "medicinal_notes", "recipe",
]

# Delay between PFAF requests — be polite to a small charity site
PFAF_DELAY_S = 1.5
# Additional delay before each Wikidata request inside a batch — Wikidata SPARQL
# enforces strict IP-based rate limits (Retry-After: 1000 on violation).
# A 2s gap between species means ≤30 Wikidata req/min, well under their limits.
WIKIDATA_DELAY_S = 2.0


# ---------------------------------------------------------------------------
# Core single-species enricher
# ---------------------------------------------------------------------------

async def enrich_species(
    session: AsyncSession,
    species: Species,
    dry_run: bool = False,
    re_enrich: bool = False,
    fill_empty_only: bool = False,
    protected_fields: Optional[set] = None,
    wikidata_cache: Optional[Dict[str, Optional[WikidataResult]]] = None,
) -> str:
    """
    Fetch and store enrichment data for one species.

    Args:
        fill_empty_only:  When True, only populate fields that are currently None/empty.
                          Existing non-None values are never overwritten.
        protected_fields: Set of field names that must never be touched regardless of
                          fill_empty_only. Intended for fields with human edits.

    Returns one of:
      "enriched"   — both sources returned data
      "partial"    — only one source returned data
      "not_found"  — neither source had data
      "failed"     — unexpected error during fetch/store
      "skipped"    — already enriched and re_enrich=False
    """
    protected_fields = protected_fields or set()

    # Check if already enriched (has a culinary_info row)
    existing_ci = await session.scalar(
        select(CulinaryInfo).where(CulinaryInfo.species_id == species.id)
    )
    if existing_ci and not re_enrich and not fill_empty_only:
        return "skipped"

    if dry_run:
        log.info("[dry-run] Would enrich: %s", species.scientific_name)
        return "enriched"

    # Fix 24a: Bracken Safety Flagging
    if species.scientific_name == "Pteridium aquilinum":
        species.edibility_status = "toxic"
        species.edibility_verified = True
        if not existing_ci:
            existing_ci = CulinaryInfo(species_id=species.id)
            session.add(existing_ci)
        existing_ci.edible_parts = "None - TOXIC"
        existing_ci.preparation_warnings = "Not safe for human consumption. Contains ptaquiloside (a carcinogen) and thiaminase. Do not eat."
        await session.flush()
        return "enriched"

    # ── Fetch all sources concurrently ────────────────────────────────────
    common_names_raw = []
    try:
        existing_names = json.loads(species.common_names or "[]")
        if isinstance(existing_names, list):
            common_names_raw = existing_names
    except Exception:
        pass
    first_common = common_names_raw[0] if common_names_raw else None

    # Use ITIS-validated accepted name for external source lookups when available.
    # Falls back to species.scientific_name when ITIS lookup is pending or returned no_match.
    _lookup_name = (
        species.itis_accepted_name
        if (
            species.itis_accepted_name
            and species.itis_name_match in ("accepted", "synonym")
        )
        else species.scientific_name
    )
    if _lookup_name != species.scientific_name:
        log.info(
            "[enrich] using ITIS accepted name %r for external lookups (stored as %r)",
            _lookup_name, species.scientific_name,
        )

    try:
        if wikidata_cache is not None:
            # Wikidata was pre-fetched in a single batch request — no extra network call needed
            wikidata_result = wikidata_cache.get(species.scientific_name)
            (
                pfaf_result,
                inat_result,
                trompenburg_result,
            ) = await asyncio.gather(
                fetch_pfaf(_lookup_name, kingdom=species.kingdom),
                fetch_taxon_description(_lookup_name),
                fetch_trompenburg(_lookup_name),
                return_exceptions=False,
            )
        else:
            # Individual Wikidata call — not pre-batched. Apply the configured delay
            # BEFORE fetching to respect Wikidata's strict IP-based rate limits
            # (Retry-After: 1000 on violation). This path is hit when enrich_species
            # is called outside the batch runner (e.g. trigger_ai_drafts_for_species).
            from app.services.settings_service import get_setting as _gs_wd
            await asyncio.sleep(_gs_wd("wikidata_delay_s"))
            (
                wikidata_result,
                pfaf_result,
                inat_result,
                trompenburg_result,
            ) = await asyncio.gather(
                fetch_wikidata(_lookup_name),
                fetch_pfaf(_lookup_name, kingdom=species.kingdom),
                fetch_taxon_description(_lookup_name),
                fetch_trompenburg(_lookup_name),
                return_exceptions=False,
            )
    except Exception as e:
        log.error("Enrichment fetch failed for %r: %s", species.scientific_name, e)
        return "failed"

    # Culinary links — run separately to avoid slowing the main batch on heavy scraping
    culinary_link_results = await _fetch_culinary_links_if_needed(
        session, species, first_common, re_enrich=re_enrich
    )

    # ── Store raw source data immediately — before any parsing ─────────────
    await _store_raw_source(session, species.id, "wikidata", wikidata_result)
    await _store_raw_source(session, species.id, "pfaf", pfaf_result)
    await _store_raw_source_inat(session, species.id, inat_result)
    await _store_raw_source_trompenburg(session, species.id, trompenburg_result)

    # ── Update species taxonomy from Wikidata ─────────────────────────────
    if wikidata_result:
        await _apply_wikidata_to_species(session, species, wikidata_result)
        # Re-read common names after Wikidata update
        try:
            common_names_raw = json.loads(species.common_names or "[]") or []
        except Exception:
            pass

    # ── Upsert culinary_info ───────────────────────────────────────────────
    if existing_ci:
        ci = existing_ci
    else:
        ci = CulinaryInfo(species_id=species.id)
        session.add(ci)

    sources_built = []

    if pfaf_result:
        _apply_pfaf_to_culinary(ci, pfaf_result,
                                fill_empty_only=fill_empty_only,
                                protected_fields=protected_fields)
        # Edibility verdict is NO LONGER auto-resolved from PFAF (safety doctrine):
        # _apply_pfaf_to_species_edibility is now a no-op. The species keeps an
        # empty/'unknown' edibility_status and surfaces in Edibility Review for
        # human confirmation. Call retained for auditability; PFAF source text is
        # still written to culinary_info by _apply_pfaf_to_culinary above.
        _apply_pfaf_to_species_edibility(species, pfaf_result)
        ci.pfaf_retrieved_at = datetime.utcnow()
        sources_built.append({"name": "PFAF", "url": pfaf_result.source_url})

    if wikidata_result:
        _apply_wikidata_to_culinary(ci, wikidata_result,
                                    fill_empty_only=fill_empty_only,
                                    protected_fields=protected_fields)
        ci.wikidata_retrieved_at = datetime.utcnow()
        wd_url = (
            f"https://www.wikidata.org/wiki/{wikidata_result.wikidata_id}"
            if wikidata_result.wikidata_id
            else "https://www.wikidata.org"
        )
        sources_built.append({"name": "Wikidata", "url": wd_url})

    # ── ID notes from iNaturalist + Trompenburg ───────────────────────────
    if "id_notes" not in protected_fields:
        _apply_id_notes(ci, inat_result, trompenburg_result, fill_empty_only=fill_empty_only)

    if inat_result:
        ci.inat_retrieved_at = datetime.utcnow()
        if inat_result.wikipedia_url:
            sources_built.append({"name": "iNaturalist", "url": inat_result.wikipedia_url})

    if trompenburg_result:
        ci.trompenburg_retrieved_at = datetime.utcnow()
        sources_built.append({"name": "TrompenburgPlants", "url": trompenburg_result.source_url})

    # ── Culinary links ────────────────────────────────────────────────────
    if culinary_link_results is not None:
        _apply_culinary_links(ci, culinary_link_results)

    # ── Fungi edibility enrichment (Phase 12 Prompt 1) ───────────────────
    # Only runs for fungi species; never touches plant species.
    # Runs after PFAF/Wikidata so those sources take precedence for plants,
    # and after ci is upserted so we have a culinary_info_id for history rows.
    await _maybe_enrich_fungi_edibility(session, species, ci)

    # ── Mark AI-generated fields ──────────────────────────────────────────
    ci.ai_generated_fields_json = json.dumps(_AI_GENERATED_FIELDS)

    # ── Source provenance ─────────────────────────────────────────────────
    if sources_built:
        ci.sources_json = json.dumps(sources_built)
        if "primary_source_url" not in protected_fields:
            ci.primary_source_url = sources_built[0]["url"]

    # ── Confidence score (factual sources only — not AI) ──────────────────
    found_count = sum(1 for r in [wikidata_result, pfaf_result] if r is not None)
    ci.data_confidence = 1.0 if found_count == 2 else (0.6 if found_count == 1 else 0.0)

    await session.flush()

    # ── AI draft generation ───────────────────────────────────────────────
    # Only generate if we have some source data to work from, and only if
    # there are no current pending/approved drafts (unless re_enrich=True)
    await _maybe_generate_ai_drafts(
        session=session,
        species=species,
        ci=ci,
        re_enrich=re_enrich,
        inat_result=inat_result,
        trompenburg_result=trompenburg_result,
        common_names=common_names_raw,
    )

    # A5 — if no medicinal data exists from any source, record the standard
    # "no known uses" note and mark it reviewed so it never enters a review queue.
    await _ensure_medicinal_default(session, species, ci)

    await session.flush()

    status = "enriched" if found_count == 2 else ("partial" if found_count == 1 else "not_found")
    log.info("Enriched %r → %s (confidence %.1f)", species.scientific_name, status, ci.data_confidence)
    return status


# ---------------------------------------------------------------------------
# Species rename cascade
# ---------------------------------------------------------------------------

# All culinary_info fields populated by external sources or AI generation.
# These are stale after a scientific-name change and must be cleared so that
# re-enrichment fetches fresh data under the new identity.
_ENRICHMENT_CLEARABLE_FIELDS = [
    "edible_parts", "flavour_profile", "preparation_methods", "cooking_techniques",
    "preservation_methods", "seasonal_peak", "harvest_stage", "pairing_ideas",
    "culinary_traditions", "recipe_ideas", "workshop_value_score", "traditional_uses",
    "cultural_notes", "medicinal_folklore", "look_alike_warnings", "preparation_warnings",
    "primary_source_url", "sources_json", "id_notes", "id_notes_sources_json",
    "culinary_links_json", "taste_notes", "medicinal_notes", "recipe",
    "ai_generated_fields_json", "ai_approved_fields_json",
]

_ENRICHMENT_TIMESTAMPS = [
    "pfaf_retrieved_at", "wikidata_retrieved_at", "inat_retrieved_at",
    "trompenburg_retrieved_at", "culinary_links_retrieved_at",
]


async def handle_species_rename(
    db: AsyncSession,
    sp: Species,
    old_name: str,
    new_name: str,
    is_rename: bool = True,
) -> None:
    """
    Post-rename enrichment cascade.  Called by ALL rename paths so the
    behaviour is consistent regardless of which UI triggered the rename.

    Steps
    -----
    1. Ensure a culinary_info row exists (creates one if needed).
    2. Reset every source-derived enrichment field to None — data fetched
       under the old name is invalid for the new identity.
    3. Reset all source timestamps — forces a full re-fetch on next enrich.
    4. Reset data_confidence to 0.0.
    5. Reset species.edibility_status → 'unknown' and edibility_verified → False.
       Safety-critical: edibility cannot carry over from a wrong identification.
    6. Flag all approved recipes → status='needs_review' with a system note.
    7. Cancel pending AI drafts → status='stale' (content was for the old name).
    8. Write a _rename_event row to culinary_info_history for full audit trail.

    The caller is responsible for committing and then triggering re-enrichment
    (call enrich_species with re_enrich=True, fill_empty_only=False).
    """
    from app.models.culinary import CulinaryInfo, CulinaryInfoHistory
    from app.models.species import SpeciesAIDraft, SpeciesRecipe
    from sqlalchemy import update as sqla_update

    # 1. Ensure culinary_info row exists
    ci = await db.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id))
    if ci is None:
        ci = CulinaryInfo(species_id=sp.id)
        db.add(ci)
        await db.flush()  # get ci.id before writing history

    # 2 + 3. Reset enrichment fields and source timestamps
    for field in _ENRICHMENT_CLEARABLE_FIELDS:
        setattr(ci, field, None)
    for ts in _ENRICHMENT_TIMESTAMPS:
        setattr(ci, ts, None)

    # 4. Reset confidence
    ci.data_confidence = 0.0

    # 5. Reset edibility on species row only on a true scientific-name rename.
    # On merge/reassign (is_rename=False) the edibility has already been curated
    # for this identity and must be preserved.
    if is_rename:
        sp.edibility_status = "unknown"
        sp.edibility_verified = False

    # 6. Flag approved recipes for review
    await db.execute(
        sqla_update(SpeciesRecipe)
        .where(SpeciesRecipe.species_id == sp.id)
        .where(SpeciesRecipe.status == "approved")
        .values(
            status="needs_review",
            notes="species renamed — recipe may be incorrect",
        )
    )

    # 7. Cancel pending AI drafts (content generated for old name)
    await db.execute(
        sqla_update(SpeciesAIDraft)
        .where(SpeciesAIDraft.species_id == sp.id)
        .where(SpeciesAIDraft.status == "pending")
        .values(status="stale")
    )

    # 8. Audit trail
    db.add(CulinaryInfoHistory(
        culinary_info_id=ci.id,
        field_name="_rename_event",
        old_value=old_name,
        new_value=new_name,
        changed_at=datetime.utcnow(),
        changed_by="human",
    ))

    await db.flush()
    log.info(
        "handle_species_rename: cleared enrichment for %r → %r (species_id=%d)",
        old_name, new_name, sp.id,
    )


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

async def run_enrichment_batch(
    session: Optional[AsyncSession] = None,
    dry_run: bool = False,
    re_enrich: bool = False,
    fill_empty_only: bool = False,
    species_filter: Optional[str] = None,
    species_list: Optional[list] = None,
    progress_cb: Optional[Callable] = None,
    cancel_check_fn: Optional[Callable] = None,
    start_from: int = 0,
) -> dict:
    """
    Enrich all species derived from identified observations.

    The ``session`` parameter is accepted for backward compatibility but IGNORED —
    this function creates its own short-lived sessions (one per species) so that
    no write-lock is held across the full duration of a long batch.

    species_list:    if provided, only these exact names are enriched (auto-enrich path).
    cancel_check_fn: optional async callable() → str | None; called each iteration.
                     If it returns 'paused' or 'cancelled', the loop exits cleanly.
    start_from:      resume index — skip the first N species (used after a pause/resume).
    Returns summary dict: {total, enriched, partial, not_found, skipped, failed, stopped_at}
    """
    from app.database import AsyncSessionLocal

    # Collect distinct species_primary names — short-lived read session, closed immediately.
    # review_status captures both AI-approved (≥70%) and human-verified species.
    #
    # We intentionally do NOT also require identification_status == 'identified':
    # a human-confirmed observation can legitimately carry a species name while
    # its identification_status is still a stale value (e.g. 'failed_identification'
    # left over from the original AI pass). Requiring 'identified' here silently
    # dropped such species from enrichment. The species_primary not-null/non-empty
    # filter below is sufficient to guarantee we only process rows with a name.
    async with AsyncSessionLocal() as _read_session:
        stmt = (
            select(Observation.species_primary)
            .where(Observation.species_primary.is_not(None))
            .where(Observation.species_primary != "")
            .where(Observation.review_status.in_(["approved", "manually_verified"]))
            .distinct()
        )
        rows = (await _read_session.execute(stmt)).all()
    species_names = [r[0] for r in rows if r[0]]

    if species_list is not None:
        allowed = set(species_list)
        species_names = [n for n in species_names if n in allowed]
    elif species_filter:
        species_names = [n for n in species_names if species_filter.lower() in n.lower()]

    log.info("Found %d distinct species to enrich (start_from=%d)", len(species_names), start_from)

    # Resume support: skip already-processed items
    if start_from > 0:
        species_names = species_names[start_from:]

    counters = dict(
        total=len(species_names) + start_from,
        enriched=0, partial=0, not_found=0, skipped=0, failed=0,
        stopped_at=None,
    )

    # ── Pre-fetch all Wikidata in ONE batch request ───────────────────────────
    # This replaces 62 individual SPARQL calls with a single VALUES query,
    # completely eliminating the per-species rate-limit problem.
    if dry_run:
        wikidata_cache: Optional[Dict[str, Optional[WikidataResult]]] = None
    else:
        log.info("Fetching Wikidata for %d species in one batch request…", len(species_names))
        wikidata_cache = await fetch_wikidata_batch(species_names)
        found_wd = sum(1 for v in wikidata_cache.values() if v is not None)
        log.info("Wikidata batch complete: %d/%d species found", found_wd, len(species_names))

    for i, name in enumerate(species_names):
        # Check for pause/cancel signal before each item
        if cancel_check_fn is not None:
            signal = await cancel_check_fn()
            if signal in ("paused", "cancelled"):
                counters["stopped_at"] = start_from + i
                log.info(
                    "run_enrichment_batch: %s signal received at item %d — exiting cleanly",
                    signal, start_from + i,
                )
                return counters

        # Short-lived session per species — released immediately after commit so no
        # write-lock accumulates across the full batch duration.
        try:
            async with AsyncSessionLocal() as _sess:
                # Upsert into species table
                sp = await _get_or_create_species(_sess, name)

                # Pull taxonomy from stored PlantNet candidates if species row is sparse
                await _backfill_taxonomy_from_observations(_sess, sp)

                # Determine which culinary fields have human edits — never overwrite those.
                protected_fields: set = set()
                ci_for_sp = await _sess.scalar(
                    select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id)
                )
                if ci_for_sp:
                    history_rows = (await _sess.execute(
                        select(CulinaryInfoHistory.field_name)
                        .where(CulinaryInfoHistory.culinary_info_id == ci_for_sp.id)
                        .where(CulinaryInfoHistory.changed_by == "human")
                    )).scalars().all()
                    protected_fields = set(history_rows)

                # Enrich — pass pre-fetched Wikidata so no further SPARQL calls are made
                status = await enrich_species(
                    _sess, sp, dry_run=dry_run, re_enrich=re_enrich,
                    fill_empty_only=fill_empty_only,
                    protected_fields=protected_fields,
                    wikidata_cache=wikidata_cache,
                )
                counters[status] = counters.get(status, 0) + 1
                await _sess.commit()
                # _sess closes here — connection returned to pool
        except Exception as _item_exc:
            log.warning("run_enrichment_batch: error enriching %r: %s", name, _item_exc)
            counters["failed"] = counters.get("failed", 0) + 1
            status = "failed"

        if progress_cb:
            progress_cb(start_from + i + 1, counters["total"], name, status)

        # Rate-limit between species for PFAF only (Wikidata is now batched).
        if not dry_run and status != "skipped":
            from app.services.settings_service import get_setting as _gs
            await asyncio.sleep(_gs("pfaf_delay_s"))

    return counters


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_or_create_species(session: AsyncSession, scientific_name: str) -> Species:
    """Return existing Species row or create a new one."""
    sp = await session.scalar(
        select(Species).where(Species.name_key == normalize_taxon_key(scientific_name))
    )
    if sp:
        return sp
    # Known-synonym resolution (read-only) — before creating a new card,
    # check whether this name is a registered synonym of an existing one.
    from app.services.synonyms import resolve_synonym_species_id
    canonical_id = await resolve_synonym_species_id(session, scientific_name)
    if canonical_id is not None:
        sp = await session.get(Species, canonical_id)
        if sp:
            return sp
    _sci = collapse_autonym(scientific_name)
    sp = Species(scientific_name=_sci, name_key=normalize_taxon_key(_sci))
    session.add(sp)
    await session.flush()
    return sp


async def _backfill_taxonomy_from_observations(session: AsyncSession, sp: Species) -> None:
    """
    Fill missing family/genus/common_names on a Species row from
    the species_candidates_json stored on observations (PlantNet data).
    Only writes fields that are currently None.
    """
    if sp.family and sp.genus and sp.common_names:
        return  # Already populated

    # Find an observation with candidates JSON for this species
    obs = await session.scalar(
        select(Observation)
        .where(Observation.species_primary == sp.scientific_name)
        .where(Observation.species_candidates_json.is_not(None))
        .limit(1)
    )
    if not obs or not obs.species_candidates_json:
        return

    try:
        candidates = json.loads(obs.species_candidates_json)
    except Exception:
        return

    if not candidates:
        return

    _sp_key = sp.name_key or normalize_taxon_key(sp.scientific_name)
    matching = [c for c in candidates
                if normalize_taxon_key(c.get("scientific_name", "")) == _sp_key]
    if not matching:
        return
    top = matching[0]

    if not sp.family and top.get("family"):
        sp.family = top["family"]
    if not sp.genus and top.get("genus"):
        sp.genus = top["genus"]
    if not sp.common_names and top.get("common_name"):
        sp.common_names = json.dumps([top["common_name"]])

    await session.flush()


async def _store_raw_source(
    session: AsyncSession,
    species_id: int,
    source_name: str,
    result: object,
) -> None:
    """Write a raw EnrichmentSource row for an integration result."""
    if result is None:
        # Store a "no data" record so we know we tried
        src = EnrichmentSource(
            species_id=species_id,
            source_name=source_name,
            source_url=None,
            retrieved_at=datetime.utcnow(),
            raw_response_json=None,
            extraction_confidence=0.0,
            parsing_method="sparql" if source_name == "wikidata" else "html_scrape",
        )
        session.add(src)
        return

    if source_name == "wikidata":
        raw = json.dumps(result.raw_json)
        url = (
            f"https://www.wikidata.org/wiki/{result.wikidata_id}"
            if result.wikidata_id
            else WIKIDATA_SPARQL_URL
        )
        method = "sparql"
        confidence = 1.0 if result.family or result.common_names else 0.5
    else:  # pfaf
        raw = result.raw_html  # already a string
        url = result.source_url
        method = "html_scrape"
        rating = result.edibility_rating
        confidence = min(1.0, (rating / 5.0)) if rating is not None else 0.5

    src = EnrichmentSource(
        species_id=species_id,
        source_name=source_name,
        source_url=url,
        retrieved_at=datetime.utcnow(),
        raw_response_json=raw,
        extraction_confidence=confidence,
        parsing_method=method,
    )
    session.add(src)


WIKIDATA_SPARQL_URL = "https://www.wikidata.org/wiki/Special:EntityPage"


async def _apply_wikidata_to_species(
    session: AsyncSession,
    sp: Species,
    r: WikidataResult,
) -> None:
    """Merge Wikidata result into Species row (don't overwrite non-None fields).

    For edible/caution values: if species.edibility_verified is True the field
    has been manually curated — queue as a pending SpeciesAIDraft rather than
    overwriting. Toxic values are written directly regardless (safety-first).
    """
    if not sp.family and r.family:
        sp.family = r.family
    if not sp.common_names and r.common_names:
        sp.common_names = json.dumps(r.common_names)
    if r.common_names_de:  # always update DE — Wikidata is the only DE source
        sp.common_names_de = json.dumps(r.common_names_de)
    if not sp.edibility_status and r.edibility_status:
        _wd_edib = r.edibility_status
        _is_edible_value = _wd_edib not in ("toxic",)
        if _is_edible_value and sp.edibility_verified:
            # Human has already curated edibility — route Wikidata suggestion to review.
            existing_draft = await session.scalar(
                select(SpeciesAIDraft)
                .where(SpeciesAIDraft.species_id == sp.id)
                .where(SpeciesAIDraft.field_name == "edibility_status")
                .where(SpeciesAIDraft.status == "pending")
            )
            if not existing_draft:
                _wd_url = (
                    f"https://www.wikidata.org/wiki/{r.wikidata_id}"
                    if r.wikidata_id
                    else "https://www.wikidata.org"
                )
                session.add(SpeciesAIDraft(
                    species_id=sp.id,
                    field_name="edibility_status",
                    draft_text=_wd_edib,
                    status="pending",
                    generated_at=datetime.utcnow(),
                    generation_context_json=json.dumps({"source_url": _wd_url}),
                    model="wikidata",
                ))
                log.info(
                    "[wikidata] edibility_verified=True for %r — queued wikidata suggestion %r as pending draft",
                    sp.scientific_name, _wd_edib,
                )
        else:
            # SAFETY DOCTRINE: automated sources must NEVER write the live
            # edibility verdict. This branch previously set sp.edibility_status
            # directly from Wikidata (including 'toxic'). It is now a no-op so the
            # species keeps an empty verdict and surfaces in Edibility Review for
            # human confirmation. The ONLY permitted writer of edibility_status /
            # edibility_verified is PATCH /api/edibility/status/{id}.
            # Wikidata's culinary text is still written by _apply_wikidata_to_culinary,
            # so the curator can still see the supporting evidence.
            pass


def _apply_pfaf_to_species_edibility(species: Species, r: PFAFResult) -> None:
    """
    DISABLED (safety doctrine): automated sources must NEVER write the live
    edibility verdict.

    This function previously derived species.edibility_status (edible / caution /
    toxic) from PFAF edibility_rating at enrichment/ID time. It is now a no-op for
    the verdict: an empty/'unknown' edibility_status routes the species to
    Edibility Review for human confirmation. The ONLY permitted writer of
    edibility_status / edibility_verified is PATCH /api/edibility/status/{id}.

    PFAF source text (edible_parts, preparation_warnings, etc.) is still written to
    culinary_info via _apply_pfaf_to_culinary, so the curator sees the evidence.

    Kept as a named no-op (rather than removing the call site at the enrichment
    orchestrator) for auditability and to make the gating explicit.
    """
    return


def _apply_pfaf_to_culinary(
    ci: CulinaryInfo,
    r: PFAFResult,
    fill_empty_only: bool = False,
    protected_fields: Optional[set] = None,
) -> None:
    """Apply PFAF result to CulinaryInfo — PFAF wins on culinary/safety fields."""
    protected_fields = protected_fields or set()

    def _set(field: str, value: Optional[str]) -> None:
        if not value:
            return
        if field in protected_fields:
            return
        if fill_empty_only and getattr(ci, field, None):
            return
        setattr(ci, field, value)

    _set("edible_parts",         r.edible_parts)
    _set("preparation_methods",  r.preparation_methods)
    _set("culinary_traditions",  r.culinary_traditions)
    _set("seasonal_peak",        r.seasonal_peak)
    _set("harvest_stage",        r.harvest_stage)
    # Safety fields — only write if PFAF has content (never clear existing warnings)
    _set("preparation_warnings", r.preparation_warnings)
    _set("look_alike_warnings",  r.look_alike_warnings)
    _set("traditional_uses",     r.traditional_uses)


def _apply_wikidata_to_culinary(
    ci: CulinaryInfo,
    r: WikidataResult,
    fill_empty_only: bool = False,
    protected_fields: Optional[set] = None,
) -> None:
    """Apply Wikidata result to CulinaryInfo — fills gaps only."""
    protected_fields = protected_fields or set()
    if (
        r.traditional_uses
        and "traditional_uses" not in protected_fields
        and not ci.traditional_uses
    ):
        ci.traditional_uses = r.traditional_uses


# ---------------------------------------------------------------------------
# Phase 8 helpers
# ---------------------------------------------------------------------------

def _apply_id_notes(
    ci: CulinaryInfo,
    inat: Optional[INatTaxonDescription],
    trompenburg: Optional[TrompenburgResult],
    fill_empty_only: bool = False,
) -> None:
    """Combine iNaturalist + Trompenburg descriptions into id_notes."""
    if fill_empty_only and ci.id_notes:
        return

    parts = []
    sources = []

    if inat:
        text = None
        if inat.identification_notes:
            text = inat.identification_notes
        elif inat.description:
            # Trim to a reasonable ID-notes excerpt
            text = inat.description[:800]
        if text:
            parts.append(f"[iNaturalist] {text}")
            sources.append({"source": "iNaturalist", "url": inat.wikipedia_url or "https://www.inaturalist.org"})

    if trompenburg and trompenburg.description:
        excerpt = trompenburg.description[:800]
        parts.append(f"[TrompenburgPlants] {excerpt}")
        sources.append({"source": "TrompenburgPlants", "url": trompenburg.source_url})

    if parts:
        ci.id_notes = "\n\n".join(parts)
        ci.id_notes_sources_json = json.dumps(sources)


def _apply_culinary_links(ci: CulinaryInfo, links: list) -> None:
    """Serialise culinary link list to culinary_links_json."""
    if not links:
        return
    ci.culinary_links_json = json.dumps([
        {"source_label": lk.source_label, "title": lk.title, "url": lk.url}
        for lk in links
    ])
    ci.culinary_links_retrieved_at = datetime.utcnow()


async def _fetch_culinary_links_if_needed(
    session: AsyncSession,
    species: Species,
    common_name: Optional[str],
    re_enrich: bool,
) -> Optional[list]:
    """
    Fetch culinary links, skipping if already fetched (unless re_enrich=True).
    Returns list of CulinaryLink or None (meaning: skip, keep existing).
    """
    if not re_enrich:
        # Check if we've already fetched links for this species
        existing = await session.scalar(
            select(EnrichmentSource)
            .where(EnrichmentSource.species_id == species.id)
            .where(EnrichmentSource.source_name == "culinary_links")
        )
        if existing:
            log.debug("Culinary links already fetched for %r — skipping", species.scientific_name)
            return None

    try:
        links = await fetch_culinary_links(species.scientific_name, common_name)
    except Exception as e:
        log.warning("Culinary links fetch failed for %r: %s", species.scientific_name, e)
        links = []

    # Store raw source record
    session.add(EnrichmentSource(
        species_id=species.id,
        source_name="culinary_links",
        source_url=None,
        retrieved_at=datetime.utcnow(),
        raw_response_json=json.dumps([
            {"source_label": lk.source_label, "title": lk.title, "url": lk.url}
            for lk in links
        ]) if links else json.dumps({"no_results": True}),
        extraction_confidence=1.0 if links else 0.0,
        parsing_method="html_scrape",
    ))

    return links


async def _store_raw_source_inat(
    session: AsyncSession,
    species_id: int,
    result: Optional[INatTaxonDescription],
) -> None:
    """Store iNaturalist taxon description as an EnrichmentSource row."""
    session.add(EnrichmentSource(
        species_id=species_id,
        source_name="inaturalist_taxon",
        source_url=result.wikipedia_url if result else None,
        retrieved_at=datetime.utcnow(),
        raw_response_json=json.dumps(result.raw_json) if result else None,
        extraction_confidence=1.0 if (result and result.description) else 0.0,
        parsing_method="json_api",
    ))


async def _store_raw_source_trompenburg(
    session: AsyncSession,
    species_id: int,
    result: Optional[TrompenburgResult],
) -> None:
    """Store Trompenburg result as an EnrichmentSource row."""
    session.add(EnrichmentSource(
        species_id=species_id,
        source_name="trompenburg",
        source_url=result.source_url if result else None,
        retrieved_at=datetime.utcnow(),
        raw_response_json=result.raw_html if result else None,
        extraction_confidence=1.0 if (result and result.description) else 0.0,
        parsing_method="html_scrape",
    ))


# ---------------------------------------------------------------------------
# Fungi edibility enrichment helper (Phase 12 Prompt 1)
# ---------------------------------------------------------------------------

async def _maybe_enrich_fungi_edibility(
    session: AsyncSession,
    species: Species,
    ci: "CulinaryInfo",
) -> None:
    """
    Attempt fungi-specific edibility enrichment via FAO + Mushroom Observer.

    Guards:
      - Only runs for fungi (kingdom='Fungi' or obs_category='fungi' on observations)
      - Only runs when edibility_status is currently null/empty/'unknown'
      - Never overwrites a human-verified edibility_status
      - Both integrations failing → species unchanged, no exception to caller

    Safety rules enforced here (not just in fungi_edibility.py):
      - Fungi edibility is human-confirmed ONLY — this path NEVER writes
        species.edibility_status or sets species.edibility_verified=True.
      - A two-source agreement is a strong suggestion; it is queued as a pending
        SpeciesAIDraft for manual confirmation, exactly like requires_review.
      - "fungi always route to review" — mirrors the plant suggestion path in
        _apply_wikidata_to_species (queue draft, do not overwrite).
    """
    # ── Guard 1: Is this a fungi species? ────────────────────────────────

    is_fungi = species.kingdom and species.kingdom.lower() == "fungi"

    if not is_fungi:
        # kingdom not set — check one observation for obs_category='fungi'
        try:
            from app.models.observation import Observation as _Obs
            cat_row = await session.scalar(
                select(_Obs.obs_category)
                .where(_Obs.species_primary == species.scientific_name)
                .limit(1)
            )
            is_fungi = cat_row and cat_row.lower() == "fungi"
        except Exception as _e:
            log.debug("[fungi_edibility] obs_category check failed for %r: %s", species.scientific_name, _e)
            is_fungi = False

    if not is_fungi:
        return  # not fungi — do not touch plants

    # ── Guard 2: Edibility already resolved? ─────────────────────────────

    current_status = (species.edibility_status or "").strip().lower()
    if current_status and current_status != "unknown":
        log.debug(
            "[fungi_edibility] edibility already set (%r) for %r — skipping",
            species.edibility_status, species.scientific_name,
        )
        return

    # ── Guard 3: Human-verified — never overwrite ─────────────────────────

    if species.edibility_verified:
        log.debug(
            "[fungi_edibility] edibility_verified=True for %r — skipping",
            species.scientific_name,
        )
        return

    # ── Guard 4: Check culinary_info_history for prior human edits ───────
    # Pattern mirrors the batch runner's protected_fields check.
    # If a human has previously edited edibility_status, do not overwrite.

    human_edited_edibility = False
    if ci.id:
        try:
            human_edit_row = await session.scalar(
                select(CulinaryInfoHistory.id)
                .where(CulinaryInfoHistory.culinary_info_id == ci.id)
                .where(CulinaryInfoHistory.field_name == "edibility_status")
                .where(CulinaryInfoHistory.changed_by == "human")
            )
            human_edited_edibility = human_edit_row is not None
        except Exception as _e:
            log.warning(
                "[fungi_edibility] history check failed for %r: %s",
                species.scientific_name, _e,
            )
            return  # safe: don't proceed if we can't verify history

    if human_edited_edibility:
        log.info(
            "[fungi_edibility] edibility_status has human history for %r — skipping write",
            species.scientific_name,
        )
        return

    # ── Run two-source resolution ─────────────────────────────────────────

    try:
        from app.services.fungi_edibility import resolve_fungi_edibility
        result = await resolve_fungi_edibility(species.scientific_name)
    except Exception as exc:
        log.info(
            "[fungi_edibility] Both integrations failed for %r (%s) — leaving unchanged",
            species.scientific_name, exc,
        )
        return  # graceful degradation: both fail → no change, no exception

    if not result:
        log.info("[fungi_edibility] Empty result for %r — leaving unchanged", species.scientific_name)
        return

    # ── Apply result: fungi edibility is human-confirmed ONLY ─────────────
    # SAFETY: never auto-write species.edibility_status or set edibility_verified
    # on the fungi path. A two-source agreement is a strong *suggestion*, but
    # fungi edibility must be manually confirmed (mirrors the plant suggestion
    # path in _apply_wikidata_to_species and "fungi always route to review").
    # Both the two-source-agreement case and the requires_review case are queued
    # as a pending, UNVERIFIED SpeciesAIDraft for a curator to confirm.

    is_two_source_agreement = bool(result.get("edibility_verified")) and not result.get("requires_review")
    needs_review            = bool(result.get("requires_review"))

    if not (is_two_source_agreement or needs_review):
        # Result exists but is indeterminate (boundary confidence) — leave unchanged.
        log.info(
            "[fungi_edibility] Indeterminate result for %r (verified=%s requires_review=%s) "
            "— leaving unchanged",
            species.scientific_name,
            result.get("edibility_verified"),
            result.get("requires_review"),
        )
        return

    # Avoid duplicate pending drafts
    existing_draft = await session.scalar(
        select(SpeciesAIDraft)
        .where(SpeciesAIDraft.species_id == species.id)
        .where(SpeciesAIDraft.field_name == "edibility_status")
        .where(SpeciesAIDraft.status == "pending")
    )
    if existing_draft:
        log.debug(
            "[fungi_edibility] Pending edibility draft already exists for %r — skipping",
            species.scientific_name,
        )
        return

    sources_summary = "; ".join(
        f"{s.get('source','?')}: {s.get('edibility_status','?')}"
        for s in result.get("sources", [])
    ) or "no source data"

    if is_two_source_agreement:
        draft_text = (
            f"Fungi edibility lookup — both sources agree: "
            f"status={result.get('edibility_status','unknown')}, "
            f"confidence={result.get('confidence', 0):.2f}. "
            f"Sources: {sources_summary}. "
            f"Suggestion only — fungi edibility must be manually confirmed before approving."
        )
    else:
        draft_text = (
            f"Fungi edibility lookup: status={result.get('edibility_status','unknown')}, "
            f"confidence={result.get('confidence', 0):.2f}. "
            f"Sources: {sources_summary}. "
            f"Requires manual review — please verify before approving."
        )

    session.add(SpeciesAIDraft(
        species_id=species.id,
        field_name="edibility_status",
        draft_text=draft_text,
        status="pending",
        generated_at=datetime.utcnow(),
        generation_context_json=json.dumps({
            "source": "fao_fungi+mushroom_observer",
            "result": result,
        }),
        model="fao_fungi+mushroom_observer",
    ))

    log.info(
        "[fungi_edibility] Queued edibility review draft for %r "
        "(status=%r two_source_agreement=%s requires_review=%s) — not auto-verified",
        species.scientific_name, result.get("edibility_status"),
        is_two_source_agreement, needs_review,
    )


# A5 — standard note for species with no medicinal information from any source.
MEDICINAL_NONE_DEFAULT = "No known traditional medicinal uses"


async def _ensure_medicinal_default(
    session: AsyncSession,
    species: Species,
    ci: CulinaryInfo,
) -> None:
    """
    A5 — when medicinal_notes is null/empty *and* there is no medicinal source
    data (no folklore) *and* no pending/approved medicinal draft, auto-fill the
    standard "No known traditional medicinal uses" note and mark it approved so
    it never surfaces in a review queue.

    If medicinal_notes has a human-edit history row, the field is considered
    manually curated — create a pending SpeciesAIDraft for human review instead
    of writing directly.
    """
    if ci.medicinal_notes and ci.medicinal_notes.strip():
        return
    if ci.medicinal_folklore and ci.medicinal_folklore.strip():
        return  # genuine medicinal data exists — leave for normal drafting/review

    draft = await session.scalar(
        select(SpeciesAIDraft.id)
        .where(SpeciesAIDraft.species_id == species.id)
        .where(SpeciesAIDraft.field_name == "medicinal_notes")
        .where(SpeciesAIDraft.status.in_(["pending", "approved", "edited_approved"]))
    )
    if draft:
        return  # a real medicinal draft is in flight — don't override it

    # Check whether a human has previously edited medicinal_notes directly.
    # If so, do not overwrite — route to the draft review queue instead.
    human_edited = ci.id and await session.scalar(
        select(CulinaryInfoHistory.id)
        .where(CulinaryInfoHistory.culinary_info_id == ci.id)
        .where(CulinaryInfoHistory.field_name == "medicinal_notes")
        .where(CulinaryInfoHistory.changed_by == "human")
    )
    if human_edited:
        session.add(SpeciesAIDraft(
            species_id=species.id,
            field_name="medicinal_notes",
            draft_text=MEDICINAL_NONE_DEFAULT,
            status="pending",
            generated_at=datetime.utcnow(),
            model="system",
        ))
        log.info(
            "[A5] medicinal_notes has human history — queued as pending draft for %r",
            species.scientific_name,
        )
        return

    ci.medicinal_notes = MEDICINAL_NONE_DEFAULT
    try:
        approved = json.loads(ci.ai_approved_fields_json) if ci.ai_approved_fields_json else []
        if not isinstance(approved, list):
            approved = []
    except (ValueError, TypeError):
        approved = []
    if "medicinal_notes" not in approved:
        approved.append("medicinal_notes")
        ci.ai_approved_fields_json = json.dumps(approved)
    log.info("[A5] medicinal_notes default applied + approved for %r", species.scientific_name)


async def _maybe_generate_ai_drafts(
    session: AsyncSession,
    species: Species,
    ci: CulinaryInfo,
    re_enrich: bool,
    inat_result: Optional[INatTaxonDescription],
    trompenburg_result: Optional[TrompenburgResult],
    common_names: list,
    only_field: Optional[str] = None,
    reprocess_rejected: bool = False,
    pfaf_result: Optional[PFAFResult] = None,
) -> None:
    """
    Generate AI drafts for taste_notes, medicinal_notes, recipe — if conditions met.

    Conditions:
      - For Anthropic backend: settings.anthropic_api_key must be set.
      - For Ollama backend: Ollama must be running (falls back to Anthropic on error).
      - Sufficient source context must exist (at least edible_parts or traditional_uses)
      - No existing pending drafts, unless re_enrich=True (which invalidates them first)

    only_field: when set (one of the draft fields), restrict generation to that
        single field — used by the per-domain backfill so "Run" on one domain
        only produces that domain's draft.
    reprocess_rejected: when True, a previously *rejected* draft no longer counts
        as "covered" — the field becomes eligible for a fresh draft. Used by the
        backfill path so rejected drafts are re-processable; the enrichment path
        keeps the default (rejected stays covered).
    """
    from app.services.settings_service import get_setting as _gs_early
    _backend = _gs_early("enrichment_backend")
    if _backend == "anthropic" and not settings.anthropic_api_key:
        log.warning(
            "[AI drafts] ANTHROPIC_API_KEY not set — skipping drafts for %r",
            species.scientific_name,
        )
        return

    # Check we have enough context to generate meaningful drafts
    has_context = any([
        ci.edible_parts,
        ci.traditional_uses,
        ci.medicinal_folklore,
        inat_result and inat_result.description,
        trompenburg_result and trompenburg_result.description,
        pfaf_result and pfaf_result.medicinal_folklore,
    ])
    if not has_context:
        log.info(
            "[AI drafts] No source context for %r — skipping (edible_parts=%r, trad_uses=%r, inat=%r)",
            species.scientific_name,
            bool(ci.edible_parts),
            bool(ci.traditional_uses),
            bool(inat_result and inat_result.description),
        )
        return

    # Edibility gate — mirrors _section_ai_draft
    _NO_CONTENT = ("toxic", "inedible", "not_edible")
    if species.edibility_status in _NO_CONTENT:
        log.info("[AI drafts] suppressing drafts for toxic/inedible species %r", species.scientific_name)
        return

    # Fix 24a: Suppress AI drafts for Bracken
    if species.scientific_name == "Pteridium aquilinum":
        log.info("[AI drafts] Skipping generation for toxic species: %r", species.scientific_name)
        return

    # If re_enrich: invalidate any existing pending drafts
    if re_enrich:
        from sqlalchemy import update as _upd
        await session.execute(
            _upd(SpeciesAIDraft)
            .where(SpeciesAIDraft.species_id == species.id)
            .where(SpeciesAIDraft.status == "pending")
            .values(status="invalidated")
        )
        await session.flush()

    # Check which fields already have a draft. A "covered" field is one that
    # already has a draft in a status we should not overwrite. By default that
    # includes 'rejected'; when reprocess_rejected=True (backfill), a rejected
    # field is treated as outstanding and eligible for a fresh draft.
    _DRAFT_FIELDS = ["taste_notes", "medicinal_notes", "recipe", "medicinal_folklore"]
    _covered_statuses = ["pending", "approved", "edited_approved"]
    if not reprocess_rejected:
        _covered_statuses.append("rejected")
    existing_drafts = (await session.execute(
        select(SpeciesAIDraft.field_name)
        .where(SpeciesAIDraft.species_id == species.id)
        .where(SpeciesAIDraft.status.in_(_covered_statuses))
    )).scalars().all()
    fields_needed = [f for f in _DRAFT_FIELDS if f not in existing_drafts]

    # Per-domain backfill: restrict to the single requested field
    if only_field:
        fields_needed = [f for f in fields_needed if f == only_field]

    # Edibility gate (unconfirmed): restrict to medicinal fields only
    if species.edibility_status in (None, "unknown", "unclear"):
        log.info("[AI drafts] suppressing taste_notes/recipe — edibility unconfirmed for %r", species.scientific_name)
        fields_needed = [f for f in fields_needed if f in ("medicinal_notes", "medicinal_folklore")]

    # Human-lock gate — skip any field with a changed_by='human' history row.
    if ci and fields_needed:
        _human_locked = set((await session.execute(
            select(CulinaryInfoHistory.field_name)
            .where(CulinaryInfoHistory.culinary_info_id == ci.id)
            .where(CulinaryInfoHistory.changed_by == "human")
        )).scalars().all())
        for _f in sorted(_human_locked & set(fields_needed)):
            log.debug("[AI drafts] Skipping AI draft for %r: human-locked (%r)", _f, species.scientific_name)
        fields_needed = [f for f in fields_needed if f not in _human_locked]

    if not fields_needed:
        log.info("[AI drafts] All 3 draft fields already exist for %r — skipping", species.scientific_name)
        return

    log.info("Generating AI drafts for %r: %s", species.scientific_name, fields_needed)

    _gs = _gs_early  # already imported above as _gs_early

    # For conditionally edible (caution) species, fetch any curator-set edibility
    # conditions to embed in the recipe caveat. Read conditions lazily here so the
    # main enrichment path does not need a new import at the top of the file.
    edibility_conditions: Optional[str] = None
    if species.edibility_status == "caution":
        try:
            from app.models.species import SpeciesEdibilityCondition
            cond_rows = (await session.execute(
                select(SpeciesEdibilityCondition)
                .where(SpeciesEdibilityCondition.species_id == species.id)
            )).scalars().all()
            if cond_rows:
                parts = [
                    f"{c.part} ({c.preparation}{'/' + c.season if c.season != 'any' else ''}): "
                    f"{'safe' if c.safe else 'unsafe'}"
                    + (f" — {c.notes}" if c.notes else "")
                    for c in cond_rows
                ]
                edibility_conditions = "; ".join(parts)
        except Exception as _e:
            log.warning("[AI drafts] Failed to fetch edibility conditions for %r: %s", species.scientific_name, _e)

    _draft_kwargs = dict(
        scientific_name=species.scientific_name,
        common_names=common_names,
        edible_parts=ci.edible_parts,
        preparation_methods=ci.preparation_methods,
        traditional_uses=ci.traditional_uses,
        medicinal_folklore=ci.medicinal_folklore,
        inat_description=inat_result.description if inat_result else None,
        trompenburg_description=trompenburg_result.description if trompenburg_result else None,
        edibility_status=species.edibility_status,
        edibility_conditions=edibility_conditions,
        preparation_warnings=ci.preparation_warnings,
        pfaf_medicinal_text=pfaf_result.medicinal_folklore if pfaf_result else None,
    )

    # ── Synthesis context fetch (medicinal_notes only, thin source data) ─────────
    # Fetches reference text from SYNTHESIS_SOURCES at generation time.
    # Never stored — passed to the AI as read-only context only.
    # Gate: only when medicinal_notes is needed AND source data is sparse.
    _CULINARY_SOURCE_FIELDS = ("edible_parts", "preparation_methods", "traditional_uses", "medicinal_folklore")
    _populated_count = sum(1 for f in _CULINARY_SOURCE_FIELDS if getattr(ci, f, None))
    _thin_source_data = _populated_count < 3
    synthesis_context: Optional[str] = None

    if "medicinal_notes" in fields_needed and _thin_source_data:
        try:
            from app.integrations.culinary_links import (
                SYNTHESIS_SOURCES as _SYNTHESIS_SOURCES,
                fetch_synthesis_context as _fetch_syn,
            )
            import asyncio as _asyncio_syn
            _syn_common = common_names[0] if common_names else None
            _syn_tasks = [
                _fetch_syn(src["domain"], species.scientific_name, _syn_common)
                for src in _SYNTHESIS_SOURCES
            ]
            _syn_results = await _asyncio_syn.gather(*_syn_tasks, return_exceptions=True)
            _syn_parts = []
            for src, result in zip(_SYNTHESIS_SOURCES, _syn_results):
                if isinstance(result, Exception):
                    log.debug(
                        "[AI drafts] synthesis fetch error for %r from %r: %s",
                        species.scientific_name, src["domain"], result,
                    )
                elif result:
                    _syn_parts.append(f"--- {src['label']} ---\n{result}")
            if _syn_parts:
                synthesis_context = "\n\n".join(_syn_parts)
                log.info(
                    "[AI drafts] synthesis context gathered for %r: %d source(s), %d chars",
                    species.scientific_name, len(_syn_parts), len(synthesis_context),
                )
            else:
                log.debug(
                    "[AI drafts] synthesis fetch returned no content for %r (thin source, sources empty/unreachable)",
                    species.scientific_name,
                )
        except Exception as _syn_err:
            log.warning(
                "[AI drafts] synthesis context fetch failed for %r — continuing without: %s",
                species.scientific_name, _syn_err,
            )

    backend = _gs("enrichment_backend")
    draft_result = None

    try:
        from app.integrations.ollama_draft import OllamaConnectionError as _OllamaConnErr1
    except ImportError:
        class _OllamaConnErr1(Exception): pass

    if backend == "ollama":
        try:
            from app.integrations.ollama_draft import generate_ollama_drafts
            ollama_model = _gs("ollama_model") if _gs("ollama_model") else "mistral"
            draft_result = await generate_ollama_drafts(
                model=ollama_model,
                **_draft_kwargs,
            )
            if draft_result:
                log.info("[AI drafts] Ollama draft OK for %r", species.scientific_name)
        except _OllamaConnErr1 as _oe:
            log.warning(
                "[AI drafts] Ollama unreachable for %r — falling back to Anthropic. Error: %s",
                species.scientific_name, _oe,
            )
            backend = "anthropic"  # fall through to Anthropic block below
        except Exception as _oe:
            log.error(
                "[AI drafts] Ollama error for %r (%s: %s) — falling back to Anthropic",
                species.scientific_name, type(_oe).__name__, _oe,
            )
            backend = "anthropic"

    if backend == "hybrid":

        try:
            from app.integrations.deepseek_draft import (
                generate_deepseek_recipe,
                generate_deepseek_taste_notes,
                generate_deepseek_medicinal_notes,
                generate_deepseek_medicinal_folklore,
            )
            from app.services.settings_service import get_setting as _gs_hybrid

            deepseek_key   = _gs_hybrid("deepseek_api_key")
            deepseek_model = _gs_hybrid("deepseek_model") or "deepseek-chat"

            # Build context text shared by all DeepSeek calls
            from app.integrations.claude_draft import _build_context, _context_to_text, _build_safety_caveat
            _gen_culinary = species.edibility_status in ("edible", "caution")
            ctx = _build_context(
                scientific_name=_draft_kwargs["scientific_name"],
                common_names=_draft_kwargs.get("common_names") or [],
                edible_parts=_draft_kwargs.get("edible_parts"),
                preparation_methods=_draft_kwargs.get("preparation_methods"),
                traditional_uses=_draft_kwargs.get("traditional_uses"),
                medicinal_folklore=_draft_kwargs.get("medicinal_folklore"),
                inat_description=_draft_kwargs.get("inat_description"),
                trompenburg_description=_draft_kwargs.get("trompenburg_description"),
                synthesis_reference=synthesis_context,
                preparation_warnings=_draft_kwargs.get("preparation_warnings"),
            )
            ctx_text = _context_to_text(_draft_kwargs["scientific_name"], ctx)
            recipe_ctx = ctx_text + _build_safety_caveat(
                generate_culinary=_gen_culinary,
                is_conditional=(species.edibility_status == "caution"),
                preparation_warnings=_draft_kwargs.get("preparation_warnings"),
                edibility_conditions=_draft_kwargs.get("edibility_conditions"),
            )

            async def _ds_noop():
                return None

            pfaf_medicinal_text = _draft_kwargs.get("pfaf_medicinal_text")

            import asyncio as _asyncio
            ds_taste, ds_medicinal, ds_recipe, ds_folklore = await _asyncio.gather(
                generate_deepseek_taste_notes(
                    scientific_name=_draft_kwargs["scientific_name"],
                    ctx_text=ctx_text,
                    api_key=deepseek_key,
                    model=deepseek_model,
                ) if _gen_culinary and "taste_notes" in fields_needed else _ds_noop(),
                generate_deepseek_medicinal_notes(
                    scientific_name=_draft_kwargs["scientific_name"],
                    ctx_text=ctx_text,
                    api_key=deepseek_key,
                    model=deepseek_model,
                ) if "medicinal_notes" in fields_needed else _ds_noop(),
                generate_deepseek_recipe(
                    scientific_name=_draft_kwargs["scientific_name"],
                    ctx_text=recipe_ctx,
                    api_key=deepseek_key,
                    model=deepseek_model,
                ) if _gen_culinary and "recipe" in fields_needed else _ds_noop(),
                generate_deepseek_medicinal_folklore(
                    scientific_name=_draft_kwargs["scientific_name"],
                    pfaf_text=pfaf_medicinal_text,
                    api_key=deepseek_key,
                    model=deepseek_model,
                ) if pfaf_medicinal_text and "medicinal_folklore" in fields_needed else _ds_noop(),
            )

            if ds_taste or ds_medicinal or ds_recipe or ds_folklore:
                from app.integrations.ollama_draft import OllamaDraftResult
                draft_result = OllamaDraftResult(
                    taste_notes=ds_taste,
                    medicinal_notes=ds_medicinal,
                    recipe=ds_recipe,
                    medicinal_folklore=ds_folklore,
                    model="hybrid/deepseek",
                    context_used=ctx,
                )
                log.info("[AI drafts] Hybrid draft OK for %r", species.scientific_name)

        except _OllamaConnErr1 as _oe:
            log.warning("[AI drafts] Hybrid: Ollama unreachable for %r — %s", species.scientific_name, _oe)
        except Exception as _oe:
            log.error("[AI drafts] Hybrid error for %r: %s: %s", species.scientific_name, type(_oe).__name__, _oe)

    if backend == "anthropic" and draft_result is None:
        if not settings.anthropic_api_key:
            log.warning(
                "[AI drafts] ANTHROPIC_API_KEY not set and Ollama unavailable — skipping drafts for %r",
                species.scientific_name,
            )
            return
        draft_result = await generate_ai_drafts(
            api_key=settings.anthropic_api_key,
            model=_gs("anthropic_model"),
            synthesis_context=synthesis_context,
            **_draft_kwargs,
        )

    if not draft_result:
        log.warning("AI draft generation returned no result for %r", species.scientific_name)
        return

    ctx_json = json.dumps(draft_result.context_used)

    field_map = {
        "taste_notes": draft_result.taste_notes,
        "medicinal_notes": draft_result.medicinal_notes,
        "recipe": draft_result.recipe,
        "medicinal_folklore": getattr(draft_result, "medicinal_folklore", None),
    }

    # Phrases that indicate the model couldn't write real content — discard silently.
    # Applied to taste_notes and recipe only (never medicinal_notes — "No traditional
    # medicinal uses recorded" is the intended _ensure_medicinal_default() fallback).
    _PLACEHOLDER_MARKERS = (
        "not enough information",
        "not enough sourced",
        "i don't have", "i don't have specific",
        "i cannot", "i'm unable",
        "unable to provide", "cannot provide",
        "insufficient", "not able to",
        "no sourced information",
        "cannot determine",
    )
    _PLACEHOLDER_CULINARY_ONLY = {"taste_notes", "recipe"}  # fields where filter applies

    for field_name in fields_needed:
        text = field_map.get(field_name)
        if not text:
            continue
        # Reject placeholder / refusal responses — culinary fields only.
        # medicinal_notes is excluded: "No traditional medicinal uses recorded" is
        # the intended _ensure_medicinal_default() fallback, not a failure.
        text_lower = text.lower()
        if field_name in _PLACEHOLDER_CULINARY_ONLY and any(m in text_lower for m in _PLACEHOLDER_MARKERS):
            log.warning(
                "  Discarding placeholder draft for %r → %s (starts: %r)",
                species.scientific_name, field_name, text[:60],
            )
            continue
        session.add(SpeciesAIDraft(
            species_id=species.id,
            field_name=field_name,
            draft_text=text,
            status="pending",
            generated_at=datetime.utcnow(),
            generation_context_json=ctx_json,
            model=draft_result.model,
        ))
        log.info("  Created pending draft: %r → %s", species.scientific_name, field_name)


# ---------------------------------------------------------------------------
# Section-only AI draft: used by the per-section ↻ Repopulate button
# ---------------------------------------------------------------------------

async def _section_ai_draft(
    session: AsyncSession,
    species: Species,
    field_name: str,
) -> bool:
    """
    Generate (or regenerate) a single AI draft field for a species.

    - Invalidates any existing pending draft for that field.
    - Calls the active backend (ollama or anthropic) for just the one field.
    - Saves the result as a new pending SpeciesAIDraft.
    - Returns True if a draft was queued, False if generation failed or was
      suppressed by the edibility gate.

    Does NOT fetch PFAF / Wikidata — uses whatever is already in culinary_info.
    """
    from app.services.settings_service import get_setting as _gs
    from sqlalchemy import update as _upd

    if field_name not in ("taste_notes", "recipe", "medicinal_notes"):
        log.warning("[_section_ai_draft] unknown field_name %r — skipping", field_name)
        return False

    # Edibility gate — mirrors _maybe_generate_ai_drafts
    _NO_CONTENT = ("toxic", "inedible", "not_edible")
    if species.edibility_status in _NO_CONTENT:
        log.info("[_section_ai_draft] suppressing %r for toxic species %r", field_name, species.scientific_name)
        return False
    # Culinary fields blocked for unconfirmed edibility
    if field_name in ("taste_notes", "recipe") and species.edibility_status in (None, "unknown", "unclear"):
        log.info("[_section_ai_draft] suppressing %r — edibility unconfirmed for %r", field_name, species.scientific_name)
        return False

    # Load existing culinary_info for context
    ci = await session.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == species.id))

    # Collect inat / trompenburg descriptions from raw sources if available
    inat_desc: Optional[str] = None
    trompen_desc: Optional[str] = None
    try:
        from app.models.species import EnrichmentSource as _ES
        raw_rows = (await session.execute(
            select(_ES).where(_ES.species_id == species.id).where(_ES.source_name.in_(["inaturalist", "trompenburg"]))
        )).scalars().all()
        for row in raw_rows:
            if row.source_name == "inaturalist" and row.raw_response_json:
                import json as _json
                d = _json.loads(row.raw_response_json) if isinstance(row.raw_response_json, str) else row.raw_response_json
                inat_desc = d.get("description") if isinstance(d, dict) else None
            elif row.source_name == "trompenburg" and row.raw_response_json:
                import json as _json
                d = _json.loads(row.raw_response_json) if isinstance(row.raw_response_json, str) else row.raw_response_json
                trompen_desc = d.get("description") if isinstance(d, dict) else None
    except Exception as _e:
        log.warning("[_section_ai_draft] failed to load raw sources for %r: %s", species.scientific_name, _e)

    common_names_raw: list = []
    try:
        import json as _json
        existing_names = _json.loads(species.common_names or "[]")
        if isinstance(existing_names, list):
            common_names_raw = existing_names
    except Exception:
        pass

    # Edibility conditions for caution species
    edibility_conditions: Optional[str] = None
    if species.edibility_status == "caution":
        try:
            from app.models.species import SpeciesEdibilityCondition
            cond_rows = (await session.execute(
                select(SpeciesEdibilityCondition).where(SpeciesEdibilityCondition.species_id == species.id)
            )).scalars().all()
            if cond_rows:
                parts = [
                    f"{c.part} ({c.preparation}{'/' + c.season if c.season != 'any' else ''}): "
                    f"{'safe' if c.safe else 'unsafe'}"
                    + (f" — {c.notes}" if c.notes else "")
                    for c in cond_rows
                ]
                edibility_conditions = "; ".join(parts)
        except Exception as _e:
            log.warning("[_section_ai_draft] failed to load edibility conditions for %r: %s", species.scientific_name, _e)

    # Load voice context — 'recipe' context for culinary fields, general for medicinal
    try:
        from app.services.voice_library import load_voice_context as _load_voice
        _voice_ctx = "recipe" if field_name in ("taste_notes", "recipe") else None
        _voice = _load_voice(_voice_ctx)
    except Exception:
        _voice = ""

    _draft_kwargs = dict(
        scientific_name=species.scientific_name,
        common_names=common_names_raw,
        edible_parts=ci.edible_parts if ci else None,
        preparation_methods=ci.preparation_methods if ci else None,
        traditional_uses=ci.traditional_uses if ci else None,
        medicinal_folklore=ci.medicinal_folklore if ci else None,
        inat_description=inat_desc,
        trompenburg_description=trompen_desc,
        edibility_status=species.edibility_status,
        edibility_conditions=edibility_conditions,
        preparation_warnings=ci.preparation_warnings if ci else None,
        voice_context=_voice,
    )

    # Call active backend
    backend = _gs("enrichment_backend")
    draft_result = None

    if backend == "ollama":
        try:
            from app.integrations.ollama_draft import OllamaConnectionError, generate_ollama_drafts
            draft_result = await generate_ollama_drafts(
                model=_gs("ollama_model") or "mistral",
                **_draft_kwargs,
            )
        except Exception as _oe:
            log.warning("[_section_ai_draft] Ollama failed for %r — fallback to Anthropic: %s", species.scientific_name, _oe)
            backend = "anthropic"

    if backend == "hybrid":
        try:
            from app.integrations.ollama_draft import OllamaConnectionError as _OllamaConnErr2
        except ImportError:
            class _OllamaConnErr2(Exception): pass

        try:
            from app.integrations.deepseek_draft import (
                generate_deepseek_recipe,
                generate_deepseek_taste_notes,
                generate_deepseek_medicinal_notes,
            )
            from app.services.settings_service import get_setting as _gs_hybrid

            deepseek_key   = _gs_hybrid("deepseek_api_key")
            deepseek_model = _gs_hybrid("deepseek_model") or "deepseek-chat"

            # Build context text shared by all DeepSeek calls
            from app.integrations.claude_draft import _build_context, _context_to_text, _build_safety_caveat
            _gen_culinary = species.edibility_status in ("edible", "caution")
            ctx = _build_context(
                scientific_name=_draft_kwargs["scientific_name"],
                common_names=_draft_kwargs.get("common_names") or [],
                edible_parts=_draft_kwargs.get("edible_parts"),
                preparation_methods=_draft_kwargs.get("preparation_methods"),
                traditional_uses=_draft_kwargs.get("traditional_uses"),
                medicinal_folklore=_draft_kwargs.get("medicinal_folklore"),
                inat_description=_draft_kwargs.get("inat_description"),
                trompenburg_description=_draft_kwargs.get("trompenburg_description"),
                preparation_warnings=_draft_kwargs.get("preparation_warnings"),
            )
            ctx_text = _context_to_text(_draft_kwargs["scientific_name"], ctx)
            recipe_ctx = ctx_text + _build_safety_caveat(
                generate_culinary=_gen_culinary,
                is_conditional=(species.edibility_status == "caution"),
                preparation_warnings=_draft_kwargs.get("preparation_warnings"),
                edibility_conditions=_draft_kwargs.get("edibility_conditions"),
            )

            import asyncio as _asyncio
            ds_taste, ds_medicinal, ds_recipe = await _asyncio.gather(
                generate_deepseek_taste_notes(
                    scientific_name=_draft_kwargs["scientific_name"],
                    ctx_text=ctx_text,
                    api_key=deepseek_key,
                    model=deepseek_model,
                ),
                generate_deepseek_medicinal_notes(
                    scientific_name=_draft_kwargs["scientific_name"],
                    ctx_text=ctx_text,
                    api_key=deepseek_key,
                    model=deepseek_model,
                ),
                generate_deepseek_recipe(
                    scientific_name=_draft_kwargs["scientific_name"],
                    ctx_text=recipe_ctx,
                    api_key=deepseek_key,
                    model=deepseek_model,
                ),
            )

            if ds_taste or ds_medicinal or ds_recipe:
                from app.integrations.ollama_draft import OllamaDraftResult
                draft_result = OllamaDraftResult(
                    taste_notes=ds_taste,
                    medicinal_notes=ds_medicinal,
                    recipe=ds_recipe,
                    model="hybrid/deepseek",
                    context_used=ctx,
                )
                log.info("[AI drafts] Hybrid draft OK for %r", species.scientific_name)

        except _OllamaConnErr2 as _oe:
            log.warning("[AI drafts] Hybrid: Ollama unreachable for %r — %s", species.scientific_name, _oe)
        except Exception as _oe:
            log.error("[AI drafts] Hybrid error for %r: %s: %s", species.scientific_name, type(_oe).__name__, _oe)

    if backend == "anthropic" and draft_result is None:
        from app.config import settings as _cfg
        if not _cfg.anthropic_api_key:
            log.warning("[_section_ai_draft] no API key for Anthropic — skipping %r", species.scientific_name)
            return False
        draft_result = await generate_ai_drafts(
            api_key=_cfg.anthropic_api_key,
            model=_gs("anthropic_model"),
            **_draft_kwargs,
        )

    if not draft_result:
        log.warning("[_section_ai_draft] generation returned no result for %r field=%r", species.scientific_name, field_name)
        return False

    text = getattr(draft_result, field_name, None)
    if not text:
        log.info("[_section_ai_draft] backend returned no text for field %r species %r", field_name, species.scientific_name)
        return False

    # Invalidate any existing pending draft for this field
    await session.execute(
        _upd(SpeciesAIDraft)
        .where(SpeciesAIDraft.species_id == species.id)
        .where(SpeciesAIDraft.field_name == field_name)
        .where(SpeciesAIDraft.status == "pending")
        .values(status="invalidated")
    )
    await session.flush()

    import json as _json
    session.add(SpeciesAIDraft(
        species_id=species.id,
        field_name=field_name,
        draft_text=text,
        status="pending",
        generated_at=datetime.utcnow(),
        generation_context_json=_json.dumps(draft_result.context_used),
        model=draft_result.model,
    ))
    log.info("[_section_ai_draft] queued pending draft  species=%r  field=%r", species.scientific_name, field_name)
    return True


# ---------------------------------------------------------------------------
# Background-task trigger: called from API endpoints on species confirmation
# ---------------------------------------------------------------------------

async def trigger_ai_drafts_for_species(scientific_name: str) -> None:
    """
    Fire-and-forget background task: ensure AI drafts are queued for a species
    after its name is confirmed or corrected in the review queue.

    Creates its own DB session so it is safe to schedule after the request
    session has closed.

    Behaviour:
      - Species not yet in enrichment DB → runs full enrich_species() (PFAF +
        Wikidata + AI drafts in one pass).
      - Species already has culinary_info → skips PFAF/Wikidata and calls
        _maybe_generate_ai_drafts() directly for minimal latency.
      - Respects edibility suppression rules via generate_ai_drafts() logic
        (toxic / inedible → nothing; unknown → medicinal only; edible → all).
      - All failures are caught and logged — never propagates to caller.
    """
    if not scientific_name:
        return
    log.info("[trigger_drafts] Starting for %r", scientific_name)
    try:
        from app.database import AsyncSessionLocal
        from app.services.write_lock import db_write_lock
        async with AsyncSessionLocal() as session:
            try:
                sp = await session.scalar(
                    select(Species).where(Species.name_key == normalize_taxon_key(scientific_name))
                )
                if sp is None:
                    # Known-synonym resolution (read-only) before creating a new card.
                    from app.services.synonyms import resolve_synonym_species_id
                    canonical_id = await resolve_synonym_species_id(session, scientific_name)
                    if canonical_id is not None:
                        sp = await session.get(Species, canonical_id)
                if sp is None:
                    _sci = collapse_autonym(scientific_name)
                    sp = Species(scientific_name=_sci, name_key=normalize_taxon_key(_sci))
                    session.add(sp)
                    await session.flush()

                ci = await session.scalar(
                    select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id)
                )

                if ci is None:
                    # Not yet enriched — run full pass (PFAF + Wikidata + AI drafts).
                    # No culinary_info row exists yet, so there's no history to
                    # protect — pass an empty set for the same signature the
                    # other two enrich_species() entry points use.
                    log.info(
                        "[trigger_drafts] No culinary_info for %r — running full enrich",
                        scientific_name,
                    )
                    await enrich_species(
                        session=session, species=sp, dry_run=False, re_enrich=False,
                        protected_fields=set(),
                    )
                else:
                    # Already enriched — jump straight to AI draft generation
                    log.info(
                        "[trigger_drafts] culinary_info exists for %r — generating drafts only",
                        scientific_name,
                    )
                    common_names: list = []
                    if sp.common_names:
                        try:
                            common_names = json.loads(sp.common_names) or []
                        except Exception:
                            pass
                    await _maybe_generate_ai_drafts(
                        session=session,
                        species=sp,
                        ci=ci,
                        re_enrich=False,
                        inat_result=None,
                        trompenburg_result=None,
                        common_names=common_names,
                    )

                async with db_write_lock():
                    await session.commit()
                log.info("[trigger_drafts] Done for %r", scientific_name)
            except _SAOperationalError as op_err:
                if "database is locked" in str(op_err).lower():
                    log.warning(
                        "[trigger_drafts] DB locked for %r — rolling back session",
                        scientific_name,
                    )
                    await session.rollback()
                else:
                    raise
    except Exception as exc:
        log.error(
            "[trigger_drafts] Failed for %r: %s: %s",
            scientific_name, type(exc).__name__, exc,
        )
