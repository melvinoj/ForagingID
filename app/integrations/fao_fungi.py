"""
FAO Wild Edible Fungi integration — edibility lookup via wildusefulfungi.org.

The Wild Useful Fungi database (wildusefulfungi.org) is a public, UN-affiliated
FAO-referenced reference for edibility verdicts on fungi species. This module
scrapes edibility facts only (factual data points, not editorial text).

Public function:
  fetch_fao_edibility(scientific_name: str) -> dict | None

Returns None on any failure — never raises to caller.
"""

import asyncio
import logging
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Optional

import httpx

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUEST_TIMEOUT_S   = 10
CRAWL_DELAY_S       = 2.0   # mandatory delay before every request

_BASE_URL      = "http://www.wildusefulfungi.org"
_SEARCH_URL    = "http://www.wildusefulfungi.org/search"
_FACTSHEET_URL = "http://www.wildusefulfungi.org/factsheets/{slug}.html"

# Keyword sets for edibility verdict extraction from HTML
_EDIBLE_PHRASES  = {"edible", "choice edible", "excellent edible", "good edible",
                    "highly edible", "widely eaten", "edible and choice"}
_TOXIC_PHRASES   = {"toxic", "poisonous", "deadly", "deadly poisonous", "inedible",
                    "not edible", "hallucinogenic", "hallucinogenic species", "lethal"}
_CAUTION_PHRASES = {"caution", "with caution", "conditionally edible", "edible with caution",
                    "when cooked only", "mild toxin", "mild toxins"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def fetch_fao_edibility(scientific_name: str) -> Optional[dict]:
    """
    Look up a fungi species by scientific name on wildusefulfungi.org.

    Returns a dict with keys:
        edibility_status  str          "edible" | "toxic" | "caution" | "unknown"
        notes             str | None   brief edibility note from the page (may be None)
        source_url        str          canonical URL for the species page
        retrieved_at      str          ISO 8601 datetime (UTC)

    Returns None if the species is not found or any request fails.
    Never raises — always degrades gracefully.
    """
    if not scientific_name or not scientific_name.strip():
        return None

    name = scientific_name.strip()

    # 2-second crawl delay before every request (polite scraping)
    await asyncio.sleep(CRAWL_DELAY_S)

    try:
        result = await _try_factsheet_lookup(name)
        if result:
            return result

        # Factsheet miss — fall back to site search
        result = await _try_search_lookup(name)
        return result   # may be None

    except Exception as exc:
        log.warning("[fao_fungi] Unexpected error for %r: %s", name, exc)
        return None


# ---------------------------------------------------------------------------
# Internal fetch helpers
# ---------------------------------------------------------------------------

async def _try_factsheet_lookup(scientific_name: str) -> Optional[dict]:
    """
    Attempt a direct factsheet URL using the common slug pattern:
    /factsheets/Genus_species.html
    """
    slug = scientific_name.replace(" ", "_")
    url  = _FACTSHEET_URL.format(slug=slug)
    html = await _fetch_html(url, scientific_name)
    if html is None:
        return None

    status, notes = _extract_edibility_from_html(html, scientific_name)
    if status == "unknown" and "not found" in html.lower():
        return None

    return _make_result(status, notes, url)


async def _try_search_lookup(scientific_name: str) -> Optional[dict]:
    """
    Fall back to the site's search endpoint.
    Looks for a species link in results and fetches that factsheet.
    """
    params = {"q": scientific_name}
    search_url = _SEARCH_URL + "?" + urllib.parse.urlencode(params)
    html = await _fetch_html(search_url, scientific_name)
    if html is None:
        return None

    # Try to find a species page link in the search results
    match = re.search(
        r'href=["\']([^"\']*factsheets[^"\']+)["\']',
        html, re.IGNORECASE
    )
    if not match:
        log.debug("[fao_fungi] No factsheet link found in search results for %r", scientific_name)
        return None

    factsheet_path = match.group(1)
    # Resolve relative URLs
    if factsheet_path.startswith("http"):
        factsheet_url = factsheet_path
    else:
        factsheet_url = _BASE_URL.rstrip("/") + "/" + factsheet_path.lstrip("/")

    # One further request — re-apply crawl delay
    await asyncio.sleep(CRAWL_DELAY_S)
    factsheet_html = await _fetch_html(factsheet_url, scientific_name)
    if factsheet_html is None:
        return None

    status, notes = _extract_edibility_from_html(factsheet_html, scientific_name)
    return _make_result(status, notes, factsheet_url)


async def _fetch_html(url: str, scientific_name: str) -> Optional[str]:
    """
    Fetch a URL and return the response text.
    Returns None on any HTTP or network error — logs at WARNING.
    """
    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_S,
            follow_redirects=True,
            headers={"User-Agent": "ForagingID-research/1.0 (educational/non-commercial)"},
        ) as client:
            r = await client.get(url)
            if r.status_code == 404:
                log.debug("[fao_fungi] 404 for %r at %s", scientific_name, url)
                return None
            if r.status_code != 200:
                log.warning(
                    "[fao_fungi] HTTP %d fetching %s for %r",
                    r.status_code, url, scientific_name,
                )
                return None
            return r.text
    except httpx.TimeoutException:
        log.warning("[fao_fungi] Timeout fetching %s for %r", url, scientific_name)
        return None
    except Exception as exc:
        log.warning("[fao_fungi] Request failed for %r (%s): %s", scientific_name, url, exc)
        return None


# ---------------------------------------------------------------------------
# Edibility extraction
# ---------------------------------------------------------------------------

def _extract_edibility_from_html(html: str, scientific_name: str) -> tuple[str, Optional[str]]:
    """
    Parse edibility verdict from a factsheet page.

    Strategy:
    1. Look for an explicit "Edibility:" or "Status:" field in the structured data.
    2. Fall back to scanning the page text for verdict keywords.

    Returns (edibility_status, notes) where edibility_status is one of:
        "edible" | "toxic" | "caution" | "unknown"
    and notes is a short extracted string or None.

    SAFETY: Toxic signals take precedence over all other signals.
    """
    # Strip HTML tags for text matching — preserve enough whitespace for context
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).lower()

    notes: Optional[str] = None

    # 1. Look for structured field patterns: "Edibility: <value>" or "Status: <value>"
    struct_match = re.search(
        r"(?:edibility|edible status|status)\s*[:\-]\s*([^\n\.\<]{3,80})",
        text, re.IGNORECASE,
    )
    if struct_match:
        field_text = struct_match.group(1).strip().lower()
        notes = struct_match.group(1).strip()[:200]
        verdict = _classify_text(field_text)
        if verdict != "unknown":
            return verdict, notes

    # 2. Keyword scan across full page text (lower confidence)
    verdict = _classify_text(text)
    return verdict, notes


def _classify_text(text: str) -> str:
    """
    Classify text into edibility verdict.
    SAFETY: toxic/caution signals override edible — checked first.
    """
    text_lower = text.lower()

    # SAFETY-FIRST: toxic checked before edible
    for phrase in _TOXIC_PHRASES:
        if phrase in text_lower:
            return "toxic"

    for phrase in _CAUTION_PHRASES:
        if phrase in text_lower:
            return "caution"

    for phrase in _EDIBLE_PHRASES:
        if phrase in text_lower:
            return "edible"

    return "unknown"


def _make_result(status: str, notes: Optional[str], source_url: str) -> dict:
    """Build the standard return dict."""
    return {
        "edibility_status": status,
        "notes":            notes,
        "source_url":       source_url,
        "retrieved_at":     datetime.now(timezone.utc).isoformat(),
    }
