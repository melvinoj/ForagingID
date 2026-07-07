"""
gbif.py — GBIF backbone taxonomy client + lineage write-gate.

Descriptive metadata ONLY. Nothing in this module is read by identification,
confidence scoring, dual-API agreement, auto-approve routing, or edibility
logic. It resolves a full taxonomic lineage (kingdom → genus) for a species
card and marks the card with how confident that resolution was.

Two entry points:
  - gbif_match(name, kingdom_hint)  → name-based /species/match  (Step 3 backfill)
  - gbif_lineage_by_key(usage_key)  → direct /species/{key} lookup (Step 4 hook,
                                       when a card already carries gbif_usage_key)

apply_gbif_lineage(species, match) is the shared write-gate. It mutates the ORM
object but never commits — the caller owns the session. Rules:
  - Always records gbif_match_type + gbif_match_confidence (marks the row).
  - Writes lineage ONLY on matchType == EXACT.
  - Never overwrites a non-null human-curated kingdom/family/genus. If GBIF's
    EXACT match disagrees with any of those, the whole lineage is withheld
    (status EXACT_CONFLICT) — a coherent "no lineage" beats a stitched-together
    one. New rank columns (phylum/class_/order_) are filled only on a clean EXACT.
  - gbif_usage_key is written only where not already set.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx

log = logging.getLogger(__name__)

MATCH_URL = "https://api.gbif.org/v1/species/match"
SPECIES_URL = "https://api.gbif.org/v1/species"
TIMEOUT = 15.0  # seconds


@dataclass
class GBIFMatch:
    """Result of a single GBIF backbone resolution."""

    match_type: str  # EXACT | FUZZY | HIGHERRANK | NONE | ERROR
    confidence: Optional[int] = None
    usage_key: Optional[int] = None
    kingdom: Optional[str] = None
    phylum: Optional[str] = None
    class_: Optional[str] = None
    order_: Optional[str] = None
    family: Optional[str] = None
    genus: Optional[str] = None
    raw: dict = field(default_factory=dict)


def _parse(payload: dict, *, default_match_type: str) -> GBIFMatch:
    """Map a GBIF backbone JSON blob to a GBIFMatch. GBIF returns the class rank
    under the JSON key "class" and order under "order" — read them verbatim."""
    mt = (payload.get("matchType") or default_match_type or "NONE").upper()
    conf = payload.get("confidence")
    return GBIFMatch(
        match_type=mt,
        confidence=int(conf) if isinstance(conf, (int, float)) else None,
        usage_key=payload.get("usageKey"),
        kingdom=payload.get("kingdom"),
        phylum=payload.get("phylum"),
        class_=payload.get("class"),
        order_=payload.get("order"),
        family=payload.get("family"),
        genus=payload.get("genus"),
        raw=payload,
    )


async def gbif_match(
    name: str,
    kingdom_hint: Optional[str] = None,
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> GBIFMatch:
    """Resolve a scientific name via the GBIF backbone /species/match endpoint.

    kingdom_hint (when the card already carries a non-null kingdom) is passed as
    a disambiguator so a plant name that collides with an animal/fungal genus
    resolves in the right kingdom. Never assumes a plant ladder.

    Network/HTTP failures return match_type='ERROR' (never raises) so a single
    bad name can't abort a whole backfill.
    """
    params = {"name": name, "strict": "false"}
    if kingdom_hint and kingdom_hint.strip():
        params["kingdom"] = kingdom_hint.strip()

    owns_client = client is None
    try:
        if owns_client:
            client = httpx.AsyncClient(timeout=TIMEOUT)
        resp = await client.get(MATCH_URL, params=params)
        resp.raise_for_status()
        return _parse(resp.json(), default_match_type="NONE")
    except Exception as exc:  # noqa: BLE001 — mark and move on, never abort batch
        log.warning("GBIF match failed for %r: %s", name, exc)
        return GBIFMatch(match_type="ERROR", raw={"error": str(exc)})
    finally:
        if owns_client and client is not None:
            await client.aclose()


async def gbif_lineage_by_key(
    usage_key: int,
    *,
    client: Optional[httpx.AsyncClient] = None,
) -> GBIFMatch:
    """Direct backbone lookup by usageKey → /species/{key}. A resolved backbone
    key is authoritative, so it is reported as EXACT with confidence 100."""
    owns_client = client is None
    try:
        if owns_client:
            client = httpx.AsyncClient(timeout=TIMEOUT)
        resp = await client.get(f"{SPECIES_URL}/{usage_key}")
        resp.raise_for_status()
        m = _parse(resp.json(), default_match_type="EXACT")
        m.match_type = "EXACT"
        if m.confidence is None:
            m.confidence = 100
        if m.usage_key is None:
            m.usage_key = usage_key
        return m
    except Exception as exc:  # noqa: BLE001
        log.warning("GBIF key lookup failed for %s: %s", usage_key, exc)
        return GBIFMatch(match_type="ERROR", raw={"error": str(exc)})
    finally:
        if owns_client and client is not None:
            await client.aclose()


def _norm(v: Optional[str]) -> str:
    return (v or "").strip().lower()


def apply_gbif_lineage(sp, m: GBIFMatch) -> dict:
    """Apply the EXACT-only write gate to a Species ORM object (mutates in place,
    does NOT commit). Returns {"status": str, "flags": [str, ...]}.

    status values:
      EXACT           — clean EXACT, lineage written (nulls filled)
      EXACT_CONFLICT  — EXACT but disagrees with curated data; lineage withheld
      FUZZY/HIGHERRANK/NONE — marked only, no lineage
      ERROR           — resolution failed; nothing written
    """
    if m.match_type == "ERROR":
        return {"status": "ERROR", "flags": []}

    # Always mark the row with how the match went.
    sp.gbif_match_type = m.match_type
    sp.gbif_match_confidence = m.confidence

    if m.match_type != "EXACT":
        return {"status": m.match_type, "flags": []}

    # EXACT — check for disagreement against non-null human-curated values.
    conflicts: list[str] = []
    for fld, gval in (("kingdom", m.kingdom), ("family", m.family), ("genus", m.genus)):
        cur = getattr(sp, fld)
        if cur and _norm(cur) and gval and _norm(cur) != _norm(gval):
            conflicts.append(f"{fld}: existing={cur!r} vs GBIF={gval!r}")
    if m.usage_key and sp.gbif_usage_key and sp.gbif_usage_key != m.usage_key:
        conflicts.append(
            f"gbif_usage_key: existing={sp.gbif_usage_key} vs GBIF={m.usage_key}"
        )

    if conflicts:
        # Coherent "no lineage" beats a stitched-together one. Row stays marked
        # EXACT (with confidence) so it is findable, but no lineage is written.
        return {"status": "EXACT_CONFLICT", "flags": conflicts}

    # Clean EXACT — fill new rank columns freely; fill curated columns only where
    # currently empty (never clobber); set usage_key only where not already set.
    if m.phylum:
        sp.phylum = m.phylum
    if m.class_:
        sp.class_ = m.class_
    if m.order_:
        sp.order_ = m.order_
    if m.kingdom and not _norm(sp.kingdom):
        sp.kingdom = m.kingdom
    if m.family and not _norm(sp.family):
        sp.family = m.family
    if m.genus and not _norm(sp.genus):
        sp.genus = m.genus
    if m.usage_key and sp.gbif_usage_key is None:
        sp.gbif_usage_key = m.usage_key

    return {"status": "EXACT", "flags": []}


async def enrich_species_taxonomy(sp, *, client: Optional[httpx.AsyncClient] = None) -> dict:
    """Resolve a Species ORM object's GBIF lineage and apply the write-gate.

    Resolution order matches the Step 4 spec: use the existing gbif_usage_key
    (direct backbone lookup) when present, else fall back to a name match. The
    key path degrades to a name match if the direct lookup errors. Mutates sp in
    place; the CALLER owns the session/commit. Returns apply_gbif_lineage()'s
    result dict. Descriptive metadata only — never consulted by identification,
    confidence, dual-API agreement, auto-approve, or edibility.
    """
    if sp.gbif_usage_key:
        m = await gbif_lineage_by_key(sp.gbif_usage_key, client=client)
        if m.match_type == "ERROR":
            m = await gbif_match(sp.scientific_name, kingdom_hint=sp.kingdom, client=client)
    else:
        m = await gbif_match(sp.scientific_name, kingdom_hint=sp.kingdom, client=client)
    return apply_gbif_lineage(sp, m)
