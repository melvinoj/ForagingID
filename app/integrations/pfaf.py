"""
PFAF (Plants For A Future) scraper for species enrichment.

URL pattern: https://pfaf.org/user/Plant.aspx?LatinName={scientific_name}

Parses:
  - Edible Uses section (edible_parts, preparation_methods, culinary_traditions)
  - Cautions / Hazards section (preparation_warnings, look_alike_warnings)
  - Edibility rating (0–5 from the ratings table)
  - Harvest / seasonal notes
  - Traditional / ethnobotanical uses (Other Uses section)

Design rules:
  - Never raises — returns None on 404, parse failure, or network error
  - Always stores raw_html so the caller can write it to enrichment_sources
  - Safety fields (warnings) are never synthesised — only extracted verbatim
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

PFAF_BASE = "https://pfaf.org/user/Plant.aspx?LatinName={name}"
# Fail fast when offline (offline-hardening Fix 1): 8 s ceiling.
REQUEST_TIMEOUT_S = 8
# Be polite — PFAF is a small charity site
_HEADERS = {
    "User-Agent": "ForagingID/0.1 (local foraging research tool; contact: foragingid@local)",
}

# PFAF is a plants-only database — these fungal genera never have entries.
# Matches the genus-based classification used in the gate-2 diagnostic.
_FUNGI_GENERA: frozenset[str] = frozenset({
    "Amanita", "Apioperdon", "Armillaria", "Ascocoryne", "Boletus",
    "Calocera", "Cantharellus", "Cerioporus", "Clitocybe", "Collybia",
    "Collybiopsis", "Coprinellus", "Coprinopsis", "Coprinus", "Dacrymyces",
    "Fistulina", "Fomitopsis", "Ganoderma", "Hydnum", "Hypholoma",
    "Imleria", "Kretzschmaria", "Lactarius", "Lactifluus", "Laetiporus",
    "Leccinum", "Lycoperdon", "Macrolepiota", "Meripilus", "Mycena",
    "Oudemansiella", "Parmelia", "Pholiota", "Physarum", "Pleurotus",
    "Pluteus", "Polyporus", "Psathyrella", "Psilocybe", "Pyxine",
    "Russula", "Stereum", "Trametes", "Tricholomopsis", "Tubaria",
    "Xerocomellus", "Xylaria",
})

# PFAF returns its "Plant Search" page (HTTP 200, ~46–73k chars) when no species
# entry exists — this string appears only in the <title> of that fallback page.
_PFAF_SEARCH_PAGE_MARKER = "Pfaf Plant Search"


@dataclass
class PFAFResult:
    scientific_name: str
    source_url: str
    # Culinary (factual — sourced verbatim from PFAF)
    edible_parts: Optional[str]
    preparation_methods: Optional[str]
    culinary_traditions: Optional[str]
    seasonal_peak: Optional[str]
    harvest_stage: Optional[str]
    # Safety (verbatim only — never inferred)
    preparation_warnings: Optional[str]
    look_alike_warnings: Optional[str]
    # Traditional uses (separate from culinary)
    traditional_uses: Optional[str]
    # Ratings
    edibility_rating: Optional[int]   # 0–5
    # Medicinal folklore (raw scrape — AI-draft source material only, never a direct write)
    medicinal_folklore: Optional[str] = None
    # Raw HTML preserved forever
    raw_html: str = field(default_factory=str)


async def fetch_pfaf(
    scientific_name: str,
    kingdom: Optional[str] = None,
) -> Optional["PFAFResult"]:
    """
    Fetch and parse the PFAF page for a species.
    Returns PFAFResult or None if not found / any error.

    kingdom: when set, used to fast-skip fungi (PFAF is plants-only).
    For hybrids with Unicode × in the name, automatically retries with
    ASCII x substitution before concluding no entry exists.
    """
    # Fast skip for fungi — PFAF has no fungal entries.
    genus = scientific_name.split()[0]
    if genus in _FUNGI_GENERA or (kingdom and "fung" in kingdom.lower()):
        log.debug("PFAF: skipping fungi %r", scientific_name)
        return None

    result = await _fetch_pfaf_single(scientific_name, scientific_name)

    # Hybrid retry: PFAF indexes hybrids under ASCII "x", not Unicode "×".
    # Only retry when the original lookup returned nothing.
    if result is None and "×" in scientific_name:
        ascii_name = scientific_name.replace("×", "x")
        log.debug("PFAF: retrying %r with ASCII-x form %r", scientific_name, ascii_name)
        result = await _fetch_pfaf_single(scientific_name, ascii_name)

    return result


async def _fetch_pfaf_single(
    scientific_name: str,
    lookup_name: str,
) -> Optional["PFAFResult"]:
    """
    Single HTTP fetch attempt for PFAF. scientific_name is the canonical name
    to store; lookup_name is what goes into the URL (may differ for × retries).
    """
    url = PFAF_BASE.format(name=quote(lookup_name))
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S, headers=_HEADERS) as client:
            resp = await client.get(url, follow_redirects=True)
    except Exception as e:
        log.warning("PFAF request failed for %r: %s", lookup_name, e)
        return None

    if resp.status_code == 404:
        log.debug("PFAF: no page for %r", lookup_name)
        return None

    if resp.status_code != 200:
        log.warning("PFAF returned HTTP %d for %r", resp.status_code, lookup_name)
        return None

    raw_html = resp.text

    # Legacy no-match strings (pre-existing check)
    if "No plant records found" in raw_html or "Plant not found" in raw_html:
        log.debug("PFAF: no records for %r", lookup_name)
        return None

    # PFAF returns HTTP 200 with its "Plant Search" search/fallback page when the
    # species name doesn't match any entry. The title tag is the reliable signal —
    # a real species page has the species name in the title, not "Pfaf Plant Search".
    if _PFAF_SEARCH_PAGE_MARKER in raw_html:
        log.debug("PFAF: search-page fallback for %r — no species entry found", lookup_name)
        return None

    return _parse(scientific_name, url, raw_html)


def _clean(text: Optional[str]) -> Optional[str]:
    """Strip whitespace and return None for empty strings."""
    if text is None:
        return None
    cleaned = " ".join(text.split())
    return cleaned if cleaned else None


def _section_text(soup: BeautifulSoup, heading: str) -> Optional[str]:
    """
    Extract text from a section identified by a heading string.
    PFAF uses <h2>, <h3>, or <b> elements as section headers.
    """
    # Try finding a tag whose text matches the heading (partial match)
    for tag in soup.find_all(["h2", "h3", "h4", "b", "strong"]):
        if heading.lower() in tag.get_text(strip=True).lower():
            # Collect sibling paragraph text until the next heading.
            # Skip bare <a> siblings (navigation anchors like "References",
            # "More on Edible Uses") to avoid scraping nav link text.
            parts = []
            for sib in tag.find_next_siblings():
                if sib.name in ("h2", "h3", "h4"):
                    break
                if sib.name == "a":
                    # Bare anchor sibling — navigation/reference link, skip it
                    continue
                text = sib.get_text(separator=" ", strip=True)
                # Stop when we hit a references/navigation footer
                if re.search(r'\bReferences\b|^More on ', text):
                    break
                if text:
                    parts.append(text)
            result = " ".join(parts)
            if result.strip():
                return _clean(result)
            # Empty result — tag was a ratings-table stub (e.g. <b>Other Uses</b>
            # inside a <td>); continue to the next matching tag (e.g. <h2>Other Uses</h2>).
    return None


def _td_text(soup: BeautifulSoup, label: str) -> Optional[str]:
    """
    Extract text from PFAF's ratings summary table.
    Finds <td><b>LABEL</b></td> and returns text from the adjacent sibling <td>.
    Used for fields like "Known Hazards" which appear only in the table, not as
    section headings — _section_text() cannot reach them.
    """
    label_lower = label.lower()
    for td in soup.find_all("td"):
        td_text = td.get_text(strip=True)
        if td_text.lower() == label_lower:
            next_td = td.find_next_sibling("td")
            if next_td:
                return _clean(next_td.get_text(separator=" ", strip=True))
    return None


def _edibility_rating(soup: BeautifulSoup) -> Optional[int]:
    """
    Extract the numeric edibility rating from the ratings table.
    PFAF shows ratings as filled/empty star images or a numeric value in a table.
    """
    # Look for a table row containing "Edibility" and a numeric value
    for td in soup.find_all("td"):
        text = td.get_text(strip=True)
        if text.lower().startswith("edibility"):
            # Next sibling cell or next td
            next_td = td.find_next_sibling("td")
            if next_td:
                val = next_td.get_text(strip=True)
                m = re.search(r"\d", val)
                if m:
                    return int(m.group())
    # Alternative: look for a span or div with a rating number
    for span in soup.find_all(["span", "div"]):
        if "edibility" in span.get("id", "").lower():
            m = re.search(r"\d", span.get_text())
            if m:
                return int(m.group())
    return None


def _seasonal_from_text(text: Optional[str]) -> Optional[str]:
    """
    Extract month/season references from a text blob.
    Returns a short summary like "Spring leaves, Autumn seeds" or None.
    """
    if not text:
        return None
    months = [
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
    ]
    seasons = ["spring", "summer", "autumn", "fall", "winter"]
    found = []
    lower = text.lower()
    for term in months + seasons:
        if term in lower:
            found.append(term.capitalize())
    return ", ".join(dict.fromkeys(found)) if found else None


# Confirmed verbatim-identical across all 6 tested Medicinal Uses samples.
_MEDICINAL_DISCLAIMER = (
    "Plants For A Future can not take any responsibility for any adverse effects "
    "from the use of plants. Always seek advice from a professional before using "
    "a plant medicinally."
)


def _strip_medicinal_disclaimer(text: Optional[str]) -> Optional[str]:
    """
    Strip PFAF's standard medicinal-use disclaimer prefix, if present.

    PFAF also writes the literal body "None known" for species with no documented
    medicinal use — the same null-content convention it uses for Known Hazards,
    applied independently within the Medicinal Uses section itself (confirmed via
    raw HTML inspection, not a Known Hazards bleed-through). Normalize that to None
    so downstream code treats it as absent data rather than a stub string.
    """
    if text is None:
        return None
    stripped = text.strip()
    if stripped.startswith(_MEDICINAL_DISCLAIMER):
        stripped = stripped[len(_MEDICINAL_DISCLAIMER):].strip()
    cleaned = _clean(stripped)
    if cleaned and cleaned.strip().lower() == "none known":
        return None
    return cleaned


def _parse(scientific_name: str, url: str, raw_html: str) -> PFAFResult:
    soup = BeautifulSoup(raw_html, "html.parser")

    edible_text = _section_text(soup, "Edible Uses")
    # Known Hazards lives in the ratings summary table (<td><b>Known Hazards</b></td>
    # adjacent to the value <td>) — _section_text() cannot reach it because the <b>
    # tag has no siblings. The old "Caution"/"Hazard" selectors never matched anything.
    known_hazards = _td_text(soup, "Known Hazards")
    other_uses = _section_text(soup, "Other Uses")
    cultivation = _section_text(soup, "Cultivation")
    medicinal_folklore = _strip_medicinal_disclaimer(_section_text(soup, "Medicinal Uses"))

    # PFAF's "checked, nothing found" value appears with inconsistent casing
    # ("None known" / "None Known") — normalize so downstream display logic
    # can match it with a single exact string.
    if known_hazards and known_hazards.strip().lower() == "none known":
        known_hazards = "None known"

    warnings = known_hazards

    # Seasonal info: look in edible text or cultivation notes
    seasonal = _seasonal_from_text(edible_text) or _seasonal_from_text(cultivation)

    return PFAFResult(
        scientific_name=scientific_name,
        source_url=url,
        edible_parts=_clean(edible_text),
        preparation_methods=None,   # embedded in edible_text for now
        culinary_traditions=None,   # PFAF doesn't explicitly categorise by tradition
        seasonal_peak=seasonal,
        harvest_stage=None,
        preparation_warnings=_clean(warnings),
        look_alike_warnings=None,   # PFAF rarely lists look-alikes explicitly
        traditional_uses=_clean(other_uses),
        edibility_rating=_edibility_rating(soup),
        medicinal_folklore=medicinal_folklore,
        raw_html=raw_html,
    )
