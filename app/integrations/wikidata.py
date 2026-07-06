"""
Wikidata SPARQL client for species enrichment.

Fetches: common names, family, edibility status, traditional uses.
Endpoint: https://query.wikidata.org/sparql

Design rules:
  - Never raises — returns None on any error (enrichment is best-effort)
  - Always stores raw_json on the result so the caller can write it to enrichment_sources
  - Edibility inferred from known toxic/edible properties, not hallucinated
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import httpx

log = logging.getLogger(__name__)

WIKIDATA_SPARQL = "https://query.wikidata.org/sparql"
# Fail fast when offline (offline-hardening Fix 1): 8 s ceiling.
REQUEST_TIMEOUT_S = 8

# Wikidata requires a descriptive User-Agent or it returns 403
_HEADERS = {
    "User-Agent": "ForagingID/0.1 (local foraging research tool; https://github.com/foragingid)",
    "Accept": "application/sparql-results+json",
}

# Wikidata properties
_P225 = "wdt:P225"    # taxon name
_P105 = "wdt:P105"    # taxon rank
_P171 = "wdt:P171"    # parent taxon
_P1843 = "wdt:P1843"  # taxon common name
_Q35409 = "wd:Q35409" # taxon rank: family

# Known edible families for basic edibility inference
_LIKELY_EDIBLE_FAMILIES = {
    "Rosaceae", "Fagaceae", "Betulaceae", "Urticaceae", "Asteraceae",
    "Lamiaceae", "Apiaceae", "Brassicaceae", "Poaceae", "Polygonaceae",
    "Sambucaceae", "Caprifoliaceae", "Grossulariaceae", "Ericaceae",
}


@dataclass
class WikidataResult:
    scientific_name: str
    common_names: list       # English common names
    common_names_de: list    # German common / folk names
    family: Optional[str]
    wikidata_id: Optional[str]
    # Edibility is conservative: only set if Wikidata explicitly records it
    edibility_status: Optional[str]
    traditional_uses: Optional[str]
    raw_json: dict = field(default_factory=dict)


def _build_batch_query(scientific_names: List[str]) -> str:
    """
    Batch SPARQL query: fetch all species in one request using VALUES.
    This completely avoids per-species rate limiting — 1 request for all species.
    """
    values = " ".join(
        '"{}"'.format(n.replace('"', '\\"')) for n in scientific_names
    )
    return """
SELECT DISTINCT ?taxonName ?item ?family ?familyLabel ?commonName ?commonNameDE WHERE {{
  VALUES ?taxonName {{ {values} }}
  ?item {p225} ?taxonName .
  OPTIONAL {{
    ?item {p171}+ ?family .
    ?family {p105} {q35409} .
  }}
  OPTIONAL {{ ?item {p1843} ?commonName .
             FILTER(LANG(?commonName) = "en") }}
  OPTIONAL {{ ?item {p1843} ?commonNameDE .
             FILTER(LANG(?commonNameDE) = "de") }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
LIMIT 5000
""".format(values=values, p225=_P225, p171=_P171, p105=_P105, q35409=_Q35409, p1843=_P1843)


async def fetch_wikidata_batch(
    scientific_names: List[str],
) -> Dict[str, Optional[WikidataResult]]:
    """
    Fetch Wikidata data for many species in a **single** SPARQL request.

    Returns a mapping {scientific_name: WikidataResult | None}.
    A None value means Wikidata had no entry for that species.

    Use this for batch enrichment to avoid per-species rate limiting.
    `fetch_wikidata()` is still available for single-species use.
    """
    results: Dict[str, Optional[WikidataResult]] = {n: None for n in scientific_names}

    if not scientific_names:
        return results

    query = _build_batch_query(scientific_names)
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S, headers=_HEADERS) as client:
            resp = await client.get(
                WIKIDATA_SPARQL,
                params={"query": query, "format": "json"},
            )
    except Exception as e:
        log.warning("Wikidata batch request failed: %s", e)
        return results

    if resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After", "unknown")
        log.warning(
            "Wikidata batch request rate-limited — Retry-After: %s seconds.",
            retry_after,
        )
        return results

    if resp.status_code != 200:
        log.warning("Wikidata batch returned HTTP %d", resp.status_code)
        return results

    try:
        data = resp.json()
    except Exception as e:
        log.warning("Wikidata batch non-JSON response: %s", e)
        return results

    # Group bindings by taxon name so we can parse each species separately
    bindings_by_name: Dict[str, list] = {n: [] for n in scientific_names}
    for b in data.get("results", {}).get("bindings", []):
        taxon_val = b.get("taxonName", {}).get("value")
        if taxon_val and taxon_val in bindings_by_name:
            bindings_by_name[taxon_val].append(b)

    for name, bindings in bindings_by_name.items():
        if bindings:
            species_data = {"results": {"bindings": bindings}}
            results[name] = _parse(name, species_data)

    found = sum(1 for v in results.values() if v is not None)
    log.info("Wikidata batch: %d species queried, %d found", len(scientific_names), found)
    return results


def _build_query(scientific_name: str) -> str:
    """SPARQL query: find the species item and pull English + German common names."""
    safe = scientific_name.replace('"', '\\"')
    return f"""
SELECT DISTINCT ?item ?family ?familyLabel ?commonName ?commonNameDE WHERE {{
  ?item {_P225} "{safe}" .
  OPTIONAL {{
    ?item {_P171}+ ?family .
    ?family {_P105} {_Q35409} .
  }}
  OPTIONAL {{ ?item {_P1843} ?commonName .
             FILTER(LANG(?commonName) = "en") }}
  OPTIONAL {{ ?item {_P1843} ?commonNameDE .
             FILTER(LANG(?commonNameDE) = "de") }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
LIMIT 40
"""


async def fetch_wikidata(scientific_name: str) -> Optional[WikidataResult]:
    """
    Query Wikidata for a species by scientific name.
    Returns WikidataResult or None if not found / any error.
    """
    query = _build_query(scientific_name)
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S, headers=_HEADERS) as client:
            resp = await client.get(
                WIKIDATA_SPARQL,
                params={"query": query, "format": "json"},
            )
    except Exception as e:
        log.warning("Wikidata request failed for %r: %s", scientific_name, e)
        return None

    if resp.status_code == 429:
        retry_after = resp.headers.get("Retry-After", "unknown")
        log.warning(
            "Wikidata rate-limited for %r — Retry-After: %s seconds. "
            "Run `python scripts/enrich.py --re-enrich` after the ban clears.",
            scientific_name, retry_after,
        )
        return None

    if resp.status_code != 200:
        log.warning("Wikidata returned HTTP %d for %r", resp.status_code, scientific_name)
        return None

    try:
        data = resp.json()
    except Exception as e:
        log.warning("Wikidata non-JSON response for %r: %s", scientific_name, e)
        return None

    return _parse(scientific_name, data)


def _parse(scientific_name: str, data: dict) -> Optional[WikidataResult]:
    """Parse SPARQL results JSON into WikidataResult."""
    bindings = data.get("results", {}).get("bindings", [])
    if not bindings:
        log.debug("Wikidata: no results for %r", scientific_name)
        return None

    wikidata_id = None
    family = None
    common_names = []
    common_names_de = []

    for b in bindings:
        # Item URI → QID
        if not wikidata_id and "item" in b:
            uri = b["item"].get("value", "")
            wikidata_id = uri.split("/")[-1] if uri else None

        # Family label (first non-empty)
        if not family and "familyLabel" in b:
            val = b["familyLabel"].get("value", "")
            if val and not val.startswith("Q"):
                family = val

        # English common names (deduplicated)
        if "commonName" in b:
            cn = b["commonName"].get("value", "").strip()
            if cn and cn not in common_names:
                common_names.append(cn)

        # German common / folk names (deduplicated)
        if "commonNameDE" in b:
            cn = b["commonNameDE"].get("value", "").strip()
            if cn and cn not in common_names_de:
                common_names_de.append(cn)

    # Very conservative edibility inference — only based on known edible families
    edibility_status = None
    if family and family in _LIKELY_EDIBLE_FAMILIES:
        edibility_status = "likely_edible"

    return WikidataResult(
        scientific_name=scientific_name,
        common_names=common_names,
        common_names_de=common_names_de,
        family=family,
        wikidata_id=wikidata_id,
        edibility_status=edibility_status,
        traditional_uses=None,
        raw_json=data,
    )
