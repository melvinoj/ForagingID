"""
Mushroom Observer integration — species lookup and profile links.

Mushroom Observer (mushroomobserver.org) is a community fungi identification
resource. Their API supports name-based observation lookup but does NOT provide
a public computer vision / image-scoring endpoint.

This module provides:
  - search_by_name(scientific_name)  — find MO records for a species name
  - species_url(scientific_name)     — direct URL to species page on MO
  - observation_search_url(name)     — search URL for observations of a species
  - fetch_mo_edibility(scientific_name) — infer edibility from MO description text

For image-based fungi identification, use iNaturalist (already integrated).
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import httpx

log = logging.getLogger(__name__)

MO_API_BASE   = "https://mushroomobserver.org/api2"
MO_NAME_URL   = "https://mushroomobserver.org/names/show_name?q={name}"
MO_SEARCH_URL = "https://mushroomobserver.org/observations?q[name]={name}"
# Fail fast when offline (offline-hardening Fix 1): 8 s ceiling on all calls.
REQUEST_TIMEOUT_S = 8


@dataclass
class MOSpeciesResult:
    """Result from a Mushroom Observer species name lookup."""
    scientific_name: str
    mo_name_id: Optional[int]
    mo_url: str                # Direct MO species URL
    observation_count: int
    description: Optional[str]
    thumbnail_url: Optional[str]


def species_url(scientific_name: str) -> str:
    """Return a Mushroom Observer search URL for the given scientific name."""
    import urllib.parse
    return MO_SEARCH_URL.format(name=urllib.parse.quote(scientific_name))


async def search_by_name(scientific_name: str) -> Optional[MOSpeciesResult]:
    """
    Search Mushroom Observer API for observations of a scientific name.
    Returns None on any failure (best-effort, non-blocking).
    """
    if not scientific_name:
        return None
    import urllib.parse
    params = {
        "method":         "names",
        "text_name":      scientific_name,
        "format":         "json",
        "detail":         "high",
    }
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S) as client:
            r = await client.get(MO_API_BASE, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        log.debug("MO search failed for %r: %s", scientific_name, exc)
        return None

    results = data.get("results") or []
    if not results:
        return None

    item = results[0]
    name_id = item.get("id")
    mo_url = (
        f"https://mushroomobserver.org/name/show_name/{name_id}"
        if name_id else species_url(scientific_name)
    )

    obs_count = 0
    try:
        op = {
            "method":    "observations",
            "name":      scientific_name,
            "format":    "json",
            "detail":    "none",
        }
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S) as client:
            or_ = await client.get(MO_API_BASE, params=op)
            or_.raise_for_status()
            obs_count = or_.json().get("number_of_records", 0) or 0
    except Exception:
        pass

    return MOSpeciesResult(
        scientific_name=scientific_name,
        mo_name_id=name_id,
        mo_url=mo_url,
        observation_count=obs_count,
        description=item.get("general_description") or item.get("notes"),
        thumbnail_url=None,
    )


# ---------------------------------------------------------------------------
# Edibility extraction (Phase 12 Prompt 1)
# ---------------------------------------------------------------------------

# Keyword maps for edibility inference from unstructured description text.
# SAFETY: toxic/caution signals checked before edible — toxic always wins.
_MO_EDIBLE_SIGNALS  = {"edible", "choice", "good eating", "excellent", "widely eaten",
                       "choice edible", "excellent edible"}
_MO_TOXIC_SIGNALS   = {"toxic", "poisonous", "deadly", "inedible", "not edible",
                       "hallucinogenic", "not recommended", "known to cause illness",
                       "known to be toxic"}
_MO_CAUTION_SIGNALS = {"caution", "with caution", "when cooked", "mild toxin",
                       "mild toxins", "conditionally edible", "edible only when"}

# MO description text is community-written and unstructured — confidence is
# lower than a structured FAO source.
_MO_CONFIDENCE = 0.4


async def fetch_mo_edibility(scientific_name: str) -> Optional[dict]:
    """
    Infer edibility from a Mushroom Observer species description.

    Reuses the existing search_by_name() call — does not make additional
    API requests beyond what search_by_name already performs.

    Returns a dict with keys:
        edibility_status  str    "edible" | "toxic" | "caution" | "unknown"
        confidence        float  0.4 (MO text-parsing confidence)
        source_url        str    canonical MO URL for this species
        retrieved_at      str    ISO 8601 datetime (UTC)

    Returns None if search_by_name returns None (species not on MO).
    Never raises — degrades gracefully on all failure paths.
    """
    if not scientific_name or not scientific_name.strip():
        return None

    try:
        result = await search_by_name(scientific_name)
    except Exception as exc:
        log.warning("[mo_edibility] search_by_name failed for %r: %s", scientific_name, exc)
        return None

    if result is None:
        log.debug("[mo_edibility] No MO record for %r", scientific_name)
        return None

    description = result.description or ""
    status      = _classify_mo_description(description)

    return {
        "edibility_status": status,
        "confidence":       _MO_CONFIDENCE,
        "source_url":       result.mo_url,
        "retrieved_at":     datetime.now(timezone.utc).isoformat(),
    }


def _classify_mo_description(text: str) -> str:
    """
    Classify a MO description string into an edibility verdict.

    SAFETY-FIRST: toxic signals checked before edible signals.
    Returns "edible" | "toxic" | "caution" | "unknown".
    """
    if not text:
        return "unknown"

    text_lower = text.lower()

    # Toxic checked first — safety-critical
    for signal in _MO_TOXIC_SIGNALS:
        if signal in text_lower:
            return "toxic"

    for signal in _MO_CAUTION_SIGNALS:
        if signal in text_lower:
            return "caution"

    for signal in _MO_EDIBLE_SIGNALS:
        if signal in text_lower:
            return "edible"

    return "unknown"
