"""
ITIS (Integrated Taxonomic Information System) — name validation client.

Queries https://www.itis.gov/ITISWebService/jsonservice/ to:
  1. Confirm whether a scientific name is the currently accepted name.
  2. If not, resolve it to the accepted name (synonym → accepted name).
  3. Extract kingdom for downstream gate checks.

All calls are read-only. No API key required.
Rate limit: 1 request/second (ITIS fair-use policy). Callers are responsible
for enforcing the delay between calls; this module makes no assumptions.

ITIS API calls used:
  searchByScientificName  — find TSN(s) matching a name
  getAcceptedNamesFromTSN — resolve synonym TSN to accepted name
"""

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

log = logging.getLogger(__name__)

BASE    = "https://www.itis.gov/ITISWebService/jsonservice"
TIMEOUT = 15.0   # seconds — ITIS can be slow under load


@dataclass
class ITISResult:
    """Result of a single ITIS name lookup."""
    tsn:           Optional[int]   # ITIS TSN for the queried name
    accepted_tsn:  Optional[int]   # TSN of the currently accepted name
    accepted_name: Optional[str]   # Currently accepted scientific name
    match_status:  str             # "accepted" | "synonym" | "no_match"
    kingdom:       Optional[str]   # "Plantae" | "Fungi" | etc.


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def lookup_itis(scientific_name: str) -> ITISResult:
    """
    Full ITIS validation for one scientific name.

    Returns ITISResult with match_status:
      "accepted" — name is the currently accepted name in ITIS
      "synonym"  — name is a known synonym; accepted_name holds the preferred name
      "no_match" — ITIS has no record for this name (possible misidentification
                   or very recent taxonomy not yet indexed)

    Raises httpx.TimeoutException or httpx.HTTPError on network problems
    (callers should catch and mark itis_name_match accordingly).
    """
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        # Step 1 — search by name to obtain TSN(s)
        hits = await _search_by_name(client, scientific_name)
        if not hits:
            return ITISResult(
                tsn=None, accepted_tsn=None, accepted_name=None,
                match_status="no_match", kingdom=None,
            )

        # Find the best exact match in the result list
        hit = _find_exact(hits, scientific_name)
        if not hit:
            return ITISResult(
                tsn=None, accepted_tsn=None, accepted_name=None,
                match_status="no_match", kingdom=None,
            )

        tsn     = int(hit["tsn"])
        kingdom = _extract_kingdom(hit)

        # Step 2 — determine accepted / synonym status
        accepted = await _get_accepted_names(client, tsn)

        if not accepted:
            # Empty list → this TSN IS the currently accepted name
            return ITISResult(
                tsn=tsn, accepted_tsn=tsn,
                accepted_name=scientific_name,
                match_status="accepted", kingdom=kingdom,
            )

        # Non-empty → synonym; resolve to accepted name
        acc       = accepted[0]
        acc_name  = _normalise_name(
            acc.get("acceptedName") or acc.get("completeName") or "",
            fallback=scientific_name,
        )
        acc_tsn_s = str(acc.get("acceptedTsn") or acc.get("tsn") or tsn)
        acc_tsn   = int(acc_tsn_s) if acc_tsn_s.isdigit() else tsn

        if acc_tsn == tsn:
            # Pointing to itself — edge case, treat as accepted
            return ITISResult(
                tsn=tsn, accepted_tsn=tsn,
                accepted_name=scientific_name,
                match_status="accepted", kingdom=kingdom,
            )

        return ITISResult(
            tsn=tsn, accepted_tsn=acc_tsn,
            accepted_name=acc_name,
            match_status="synonym", kingdom=kingdom,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _search_by_name(client: httpx.AsyncClient, name: str) -> list[dict]:
    """Call searchByScientificName; return list of name-match dicts."""
    resp = await client.get(f"{BASE}/searchByScientificName", params={"srchKey": name})
    if resp.status_code != 200:
        log.warning("ITIS searchByScientificName HTTP %d for %r", resp.status_code, name)
        return []
    data = resp.json()
    names = data.get("scientificNames")
    if not names:
        return []
    # ITIS returns [null] when no match — filter those out
    return [n for n in names if n and n.get("tsn")]


async def _get_accepted_names(client: httpx.AsyncClient, tsn: int) -> list[dict]:
    """
    Call getAcceptedNamesFromTSN.
    Returns [] if the TSN is already the accepted name.
    Returns a list with the accepted name entry if this TSN is a synonym.
    """
    resp = await client.get(f"{BASE}/getAcceptedNamesFromTSN", params={"tsn": str(tsn)})
    if resp.status_code != 200:
        log.warning("ITIS getAcceptedNamesFromTSN HTTP %d for TSN %d", resp.status_code, tsn)
        return []
    data = resp.json()
    names = data.get("acceptedNames")
    if not names:
        return []
    return [n for n in names if n and (n.get("acceptedName") or n.get("completeName"))]


def _find_exact(hits: list[dict], query: str) -> Optional[dict]:
    """
    Find the best genus+epithet match from searchByScientificName results.
    Ignores author strings; case-insensitive.
    """
    q = query.strip().lower()
    q_parts = q.split()

    # Primary: match first N words of combinedName against full query
    for h in hits:
        cn = (h.get("combinedName") or "").strip().lower().split()
        if len(cn) >= len(q_parts) and " ".join(cn[: len(q_parts)]) == q:
            return h

    # Secondary: match unitName1 + unitName2
    for h in hits:
        u1 = (h.get("unitName1") or "").strip().lower()
        u2 = (h.get("unitName2") or "").strip().lower()
        combined = f"{u1} {u2}".strip() if u2 else u1
        if combined == q:
            return h

    return None


def _extract_kingdom(hit: dict) -> Optional[str]:
    return hit.get("kingdom") or hit.get("kingdomName") or None


def _normalise_name(raw: str, fallback: str) -> str:
    """
    Strip author string from an ITIS accepted-name string.
    e.g. "Taraxacum officinale G.H.Weber ex Wiggers" → "Taraxacum officinale"
    """
    if not raw:
        return fallback
    parts = raw.strip().split()
    if len(parts) >= 2:
        return f"{parts[0]} {parts[1]}"
    return raw.strip() or fallback
