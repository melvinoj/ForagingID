"""
Trompenburg Arboretum & Botanic Garden plant database scraper.

Search URL pattern: https://trompenburg.nl/planten/?s={latin_name}
(WordPress-style search, no API key required)

Extracts:
  - Taxonomic description / ID notes from the plant detail page
  - Stored with source label 'TrompenburgPlants'

Design rules:
  - Never raises — returns None on any failure
  - Stores raw_html on result for EnrichmentSource
  - Uses curl subprocess as the HTTP transport because the macOS system Python
    (LibreSSL 2.8.3) cannot negotiate TLS 1.3 with Cloudflare-backed sites.
    curl uses macOS SecureTransport which handles this correctly.
"""

import asyncio
import logging
import shutil
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

TROMPENBURG_SEARCH = "https://trompenburg.nl/planten/?s={query}"
REQUEST_TIMEOUT_S = 20
_UA = "ForagingID/0.1 (local foraging research tool; educational use)"

# curl path — present on all macOS and most Linux systems
_CURL = shutil.which("curl") or "curl"


@dataclass
class TrompenburgResult:
    scientific_name: str
    description: Optional[str]        # Taxonomic / ID description text
    source_url: str                    # URL of the plant detail page found
    raw_html: str                      # Full response HTML (stored, never deleted)


async def _curl_get(url: str) -> Optional[str]:
    """
    Fetch a URL via the system curl binary and return the response body as text.
    Returns None on any failure.

    We use curl because macOS Python 3.9 ships with LibreSSL 2.8.3 which cannot
    negotiate TLS 1.3 with Cloudflare-hosted sites (the error is
    TLSV1_ALERT_PROTOCOL_VERSION). curl uses SecureTransport and works fine.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            _CURL,
            "-sL",                      # silent + follow redirects
            "--max-time", str(REQUEST_TIMEOUT_S),
            "-A", _UA,
            "-H", "Accept-Language: en,nl;q=0.8",
            "--insecure",               # skip cert validation (same as verify=False)
            url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=REQUEST_TIMEOUT_S + 5
        )
        if proc.returncode != 0:
            log.debug("curl exit %d for %r: %s", proc.returncode, url,
                      stderr.decode(errors="replace")[:200])
            return None
        text = stdout.decode("utf-8", errors="replace")
        return text if text.strip() else None
    except Exception as e:
        log.debug("curl fetch failed for %r: %s", url, e)
        return None


async def fetch_trompenburg(scientific_name: str) -> Optional[TrompenburgResult]:
    """
    Search Trompenburg for a species and extract its description.
    Returns TrompenburgResult or None if not found / any error.
    """
    search_url = TROMPENBURG_SEARCH.format(query=quote_plus(scientific_name))

    raw_html = await _curl_get(search_url)
    if not raw_html:
        log.warning("Trompenburg: no response for %r", scientific_name)
        return None

    # Find the first matching plant detail link from search results
    detail_url = _extract_detail_link(raw_html, scientific_name)
    if not detail_url:
        log.debug("Trompenburg: no results for %r", scientific_name)
        return None

    # Fetch the detail page
    detail_html = await _curl_get(detail_url)
    if not detail_html:
        log.warning("Trompenburg: detail page unavailable for %r at %s",
                    scientific_name, detail_url)
        return None

    description = _extract_description(detail_html)

    return TrompenburgResult(
        scientific_name=scientific_name,
        description=description,
        source_url=detail_url,
        raw_html=detail_html,
    )


def _extract_detail_link(search_html: str, scientific_name: str) -> Optional[str]:
    """
    Parse search results page and return the URL of the best-matching plant page.
    Matches by scientific name (case-insensitive substring check on link text / href).
    """
    soup = BeautifulSoup(search_html, "html.parser")
    name_lower = scientific_name.lower()

    # Look for article links, post links, or any anchor containing the name
    candidates = []
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        text = a.get_text(strip=True).lower()
        # Match if either the link text or the URL slug contains the name or its genus
        genus = name_lower.split()[0] if " " in name_lower else name_lower
        if name_lower in text or genus in href.lower():
            if "trompenburg.nl" in href or href.startswith("/"):
                full = href if href.startswith("http") else f"https://trompenburg.nl{href}"
                candidates.append((full, text))

    if not candidates:
        return None

    # Prefer links where the text exactly starts with the genus or full name
    for url, text in candidates:
        if text.startswith(name_lower.split()[0]):
            return url

    return candidates[0][0]


def _extract_description(detail_html: str) -> Optional[str]:
    """
    Extract the main descriptive text from a Trompenburg plant detail page.
    Looks for the post content / description section.
    """
    soup = BeautifulSoup(detail_html, "html.parser")

    # Try WordPress-style post content divs in order of specificity
    for selector in [
        ".entry-content", ".post-content", "article .content",
        ".plant-description", ".plant-detail", "main p",
    ]:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(separator=" ", strip=True)
            text = " ".join(text.split())
            if len(text) > 80:  # ignore tiny fragments
                return text[:2000]  # cap at 2000 chars

    # Fallback: grab first substantial <p> under <main> or <article>
    container = soup.find("main") or soup.find("article") or soup
    for p in container.find_all("p"):  # type: ignore[union-attr]
        text = p.get_text(strip=True)
        text = " ".join(text.split())
        if len(text) > 80:
            return text[:2000]

    return None
