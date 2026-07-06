"""
Culinary link scrapers — Phase 8.

For each of five curated foraging/wild food sites, searches by Latin name and
(optionally) common name. Extracts up to 3 relevant page URLs + titles per site.

NO PAGE CONTENT is stored — only title and URL, to avoid copyright concerns.
These are outbound reference links for the species card.

Sites:
  - Eatweeds (eatweeds.co.uk)
  - Galloway Wild Foods (gallowaywildfoods.com)
  - Wildman Steve Brill (wildmanstevebrill.com)
  - Botanical.com (botanical.com)
  - Wildfoods UK (wildfoodsuk.com)

Design rules:
  - Never raises — returns empty list on any failure
  - Best-effort: a site returning no results is logged, not an error
  - All calls are parallel (asyncio.gather)
  - Respects robots via politeness headers; no repeated rapid hits

────────────────────────────────────────────────────────────────────────────────
SOURCE CLASSIFICATION — two distinct lists govern how external domains are used:

RAW_CONTENT_BLOCKLIST (frozenset)
  Domains that must NEVER be scraped and stored verbatim as enrichment data.
  Any domain in this set is refused by _fetch_search() even if added to _SITES
  by mistake. Content from these sites must not land in the database directly.

SYNTHESIS_SOURCES (list of dicts)
  Domains the AI draft generator (claude_draft.py) may READ as synthesis
  reference material when generating medicinal notes and other editorial fields.
  Rules:
    - The AI output MUST be a synthesis in Melvin's voice — never a reproduction.
    - Content from these sites must NOT be stored in the database.
    - The AI draft generator should fetch the page at generation time, use it as
      context, and discard the raw text. Only the synthesised output is kept.

A domain may appear in both lists simultaneously: that combination means "allowed
as a synthesis reference, but never allow raw content to enter the database."
greenguild.co.uk is the canonical example of this pattern.
────────────────────────────────────────────────────────────────────────────────
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

REQUEST_TIMEOUT_S = 15
_HEADERS = {
    "User-Agent": "ForagingID/0.1 (local foraging research tool; educational use)",
}
# Maximum links returned per site
MAX_LINKS_PER_SITE = 3

# ---------------------------------------------------------------------------
# Source classification lists  (see module docstring for full explanation)
# ---------------------------------------------------------------------------

# Domains blocked from raw-content scraping and storage.
# _fetch_search() will refuse to proceed for any domain in this set.
RAW_CONTENT_BLOCKLIST: frozenset = frozenset({
    "greenguild.co.uk",   # Melvin's own site — never scrape/store verbatim
})

# Domains approved as synthesis-only reference sources for the AI draft
# generator. The AI may fetch and read these pages at draft-generation time,
# but must never store their text and must always produce an original synthesis
# in Melvin's voice. Raw content from these domains must not enter the database.
#
# To hook a synthesis source into the draft generator:
#   1. In claude_draft.py, call fetch_synthesis_context(domain, scientific_name)
#   2. Pass the fetched text as additional context to the Claude prompt
#   3. Instruct the model explicitly: "Do not reproduce text from this source"
SYNTHESIS_SOURCES: list = [
    {
        "label": "Green Guild",
        "domain": "greenguild.co.uk",
        "search_url": "https://greenguild.co.uk/?s={query}",
        "note": "Melvin Jarman's own educational site. May be read as synthesis "
                "reference for medicinal notes. Content must never be stored verbatim.",
    },
    {
        "label": "Healthy Hildegard",
        "domain": "healthyhildegard.com",
        "search_url": "https://www.healthyhildegard.com/?s={query}",
        "note": "Hildegard von Bingen-based medicinal herb and plant resource. "
                "Read for medicinal/traditional use synthesis only.",
    },
    {
        "label": "Eat Weeds",
        "domain": "eatweeds.co.uk",
        "search_url": "https://www.eatweeds.co.uk/?s={query}",
        "note": "UK foraging reference. Also in _SITES as a culinary link source. "
                "May additionally be read for medicinal/traditional use synthesis.",
    },
    {
        "label": "Galloway Wild Foods",
        "domain": "gallowaywildfoods.com",
        "search_url": "https://gallowaywildfoods.com/?s={query}",
        "note": "Scottish foraging resource by Mark Williams. Also in _SITES. "
                "May be read for medicinal/traditional use synthesis.",
    },
    {
        "label": "Wildman Steve Brill",
        "domain": "wildmanstevebrill.com",
        "search_url": "https://www.wildmanstevebrill.com/?s={query}",
        "note": "North American foraging/medicinal plant resource. Also in _SITES. "
                "May be read for medicinal/traditional use synthesis.",
    },
    {
        "label": "Botanical.com",
        "domain": "botanical.com",
        "search_url": "https://botanical.com/?s={query}",
        "note": "Grieve's Modern Herbal — classic medicinal plant reference. "
                "Also in _SITES. Particularly valuable for medicinal synthesis.",
    },
    {
        "label": "Fabulous Fusion Food",
        "domain": "fabulousfusionfood.com",
        "url": "https://www.fabulousfusionfood.com/wild-food/spignel",
        "note": "Wild food guide with spignel/meu culinary reference. "
                "Synthesis reference only — not scraped for raw content.",
    },
    {
        "label": "Plantura Magazin",
        "domain": "plantura.garden",
        "url": "https://plantura.garden/uk/herbs/meu/meu-overview",
        "note": "Meu/Spignel herb overview. "
                "Synthesis reference only — not scraped for raw content.",
    },
    {
        "label": "Hotel Bären Wengen",
        "domain": "baeren-wengen.ch",
        "url": "https://www.baeren-wengen.ch/en/alpine-herbs/alpine-herb-recipes",
        "note": "Alpine herb recipes from Bernese Oberland. "
                "Synthesis reference only — not scraped for raw content.",
    },
    {
        "label": "Bitterkraft — Hildegard von Bingen",
        "domain": "bitterkraft.com",
        "url": "https://bitterkraft.com/blogs/bitterkraft-magazin/hildegard-von-bingen-rezepte",
        "note": "Hildegard von Bingen recipes including Bärwurz/Meum preparations. "
                "Synthesis reference only — not scraped for raw content.",
    },
    {
        "label": "Atlas Obscura — Medieval Cookies",
        "domain": "atlasobscura.com",
        "url": "https://www.atlasobscura.com/articles/medieval-cookie-recipe",
        "note": "Medieval cookie recipe featuring spignel/meu. "
                "Synthesis reference only — not scraped for raw content.",
    },
]


@dataclass
class CulinaryLink:
    source_label: str   # Human-readable site name for display
    title: str
    url: str


# ---------------------------------------------------------------------------
# Site definitions
# ---------------------------------------------------------------------------

_SITES = [
    {
        "label": "Eatweeds",
        "search_url": "https://www.eatweeds.co.uk/?s={query}",
        "domain": "eatweeds.co.uk",
    },
    {
        "label": "Galloway Wild Foods",
        "search_url": "https://gallowaywildfoods.com/?s={query}",
        "domain": "gallowaywildfoods.com",
    },
    {
        "label": "Wildman Steve Brill",
        "search_url": "https://www.wildmanstevebrill.com/?s={query}",
        "domain": "wildmanstevebrill.com",
    },
    {
        "label": "Botanical.com",
        "search_url": "https://botanical.com/?s={query}",
        "domain": "botanical.com",
        # botanical.com may use a URL pattern like /plants/latin-name/
        "alt_url_pattern": "https://botanical.com/plants/{slug}/",
    },
    # wildfoodsuk.com (NXDOMAIN as of 2026-05 — kept as placeholder, returns empty)
    # {
    #     "label": "Wildfoods UK",
    #     "search_url": "https://www.wildfoodsuk.com/?s={query}",
    #     "domain": "wildfoodsuk.com",
    # },
]


# ---------------------------------------------------------------------------
# Core search function per site
# ---------------------------------------------------------------------------

async def _search_site(
    site: dict,
    scientific_name: str,
    common_name: Optional[str] = None,
) -> List[CulinaryLink]:
    """
    Search one site for a species, return up to MAX_LINKS_PER_SITE links.
    Tries scientific name first; if 0 results and common_name provided, tries that too.
    """
    links = await _fetch_search(site, scientific_name)

    if not links and common_name:
        links = await _fetch_search(site, common_name)

    return links[:MAX_LINKS_PER_SITE]


async def _fetch_search(site: dict, query: str) -> List[CulinaryLink]:
    """Fetch one search results page and extract relevant links."""
    url = site["search_url"].format(query=quote_plus(query))
    domain = site["domain"]
    label = site["label"]

    # Blocklist guard — refuse to scrape/store content from protected domains.
    # This fires even if someone accidentally adds a blocked domain to _SITES.
    if domain in RAW_CONTENT_BLOCKLIST:
        log.warning(
            "culinary_links: domain %r is on RAW_CONTENT_BLOCKLIST — "
            "refusing to scrape. Use SYNTHESIS_SOURCES for reference-only access.",
            domain,
        )
        return []

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S, headers=_HEADERS,
                                     follow_redirects=True) as client:
            resp = await client.get(url)
    except Exception as e:
        log.debug("culinary_links %s request failed: %s", label, e)
        return []

    if resp.status_code != 200:
        log.debug("culinary_links %s HTTP %d", label, resp.status_code)
        return []

    return _extract_links(resp.text, domain, label, query)


def _extract_links(html: str, domain: str, label: str, query: str) -> List[CulinaryLink]:
    """
    Extract relevant article/post links from a search results page.
    Filters by domain, deduplicates, and returns title + URL pairs.
    """
    soup = BeautifulSoup(html, "html.parser")
    query_words = set(query.lower().split())

    seen_urls = set()
    links = []

    # Prefer article / search-result containers
    containers = soup.select(
        "article a, .search-result a, h2 a, h3 a, .entry-title a, .post-title a"
    )
    # Fallback: all anchors
    if not containers:
        containers = soup.find_all("a", href=True)

    for a in containers:
        href = a.get("href", "").strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue

        # Normalise relative URLs
        if href.startswith("/"):
            href = f"https://{domain}{href}"

        # Must belong to this domain
        if domain not in href:
            continue

        # Skip home, archive, category, tag, search pages
        skip_patterns = ["/category/", "/tag/", "/page/", "/?s=", "/?p=0", "/wp-"]
        if any(p in href for p in skip_patterns):
            continue

        title = a.get_text(strip=True) or href
        title = " ".join(title.split())

        if not title or len(title) < 3:
            continue
        if href in seen_urls:
            continue

        # Loose relevance check: at least one query word appears in title or URL
        href_lower = href.lower()
        title_lower = title.lower()
        if any(w in title_lower or w in href_lower for w in query_words if len(w) > 3):
            seen_urls.add(href)
            links.append(CulinaryLink(source_label=label, title=title, url=href))

        if len(links) >= MAX_LINKS_PER_SITE:
            break

    return links


# ---------------------------------------------------------------------------
# Public API — run all sites in parallel
# ---------------------------------------------------------------------------

async def fetch_culinary_links(
    scientific_name: str,
    common_name: Optional[str] = None,
) -> List[CulinaryLink]:
    """
    Search all five culinary sites in parallel for a species.
    Returns a flat list of up to (5 × MAX_LINKS_PER_SITE) CulinaryLink objects.
    Never raises — failures are logged and that site's results are empty.
    """
    tasks = [
        _search_site(site, scientific_name, common_name)
        for site in _SITES
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    links: List[CulinaryLink] = []
    for site, result in zip(_SITES, results):
        if isinstance(result, Exception):
            log.debug("culinary_links %s exception: %s", site["label"], result)
        elif result:
            links.extend(result)

    return links


# ---------------------------------------------------------------------------
# Synthesis context fetch — for AI draft generation only
# ---------------------------------------------------------------------------

_SYNTHESIS_CONTENT_LIMIT = 8_000   # characters; trim to keep Claude context lean

async def fetch_synthesis_context(
    domain: str,
    scientific_name: str,
    common_name: Optional[str] = None,
) -> Optional[str]:
    """
    Fetch readable page text from a SYNTHESIS_SOURCES domain for a species.

    Searches the domain using its configured search_url, follows the first
    relevant result, and returns cleaned body text — NEVER stored anywhere.

    The caller (claude_draft.py) must:
      - pass the text as context to Claude
      - instruct Claude not to reproduce it
      - discard the text after generation; never write it to the DB

    Returns None silently on any failure or if the domain is not found in
    SYNTHESIS_SOURCES. Never raises.
    """
    src = next((s for s in SYNTHESIS_SOURCES if s["domain"] == domain), None)
    if src is None:
        log.debug("fetch_synthesis_context: domain %r not in SYNTHESIS_SOURCES", domain)
        return None

    search_url = src["search_url"].format(query=quote_plus(scientific_name))
    label = src["label"]

    try:
        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT_S,
            headers=_HEADERS,
            follow_redirects=True,
        ) as client:
            # Step 1: run the search to find a relevant page URL
            resp = await client.get(search_url)
            if resp.status_code != 200:
                log.debug("fetch_synthesis_context %s search HTTP %d", label, resp.status_code)
                return None

            page_url = _find_best_result_url(resp.text, domain, scientific_name, common_name)
            if not page_url:
                # Try common_name as fallback query
                if common_name and common_name.lower() != scientific_name.lower():
                    alt_url = src["search_url"].format(query=quote_plus(common_name))
                    resp2 = await client.get(alt_url)
                    if resp2.status_code == 200:
                        page_url = _find_best_result_url(resp2.text, domain, common_name, None)
                if not page_url:
                    log.debug("fetch_synthesis_context %s: no relevant page found for %r",
                              label, scientific_name)
                    return None

            # Step 2: fetch the actual content page
            page_resp = await client.get(page_url)
            if page_resp.status_code != 200:
                log.debug("fetch_synthesis_context %s page HTTP %d", label, page_resp.status_code)
                return None

            text = _extract_body_text(page_resp.text, page_url)
            if not text:
                return None

            # Trim to limit and label clearly for Claude context
            trimmed = text[:_SYNTHESIS_CONTENT_LIMIT]
            if len(text) > _SYNTHESIS_CONTENT_LIMIT:
                trimmed += "\n[… content trimmed …]"

            return f"[Source: {label} — {page_url}]\n{trimmed}"

    except Exception as exc:
        log.debug("fetch_synthesis_context %s failed: %s", label, exc)
        return None


def _find_best_result_url(
    html: str,
    domain: str,
    query: str,
    common_name: Optional[str],
) -> Optional[str]:
    """
    Parse a search results page and return the URL of the most relevant hit.
    Prefers links whose title/URL contains words from the query.
    """
    soup = BeautifulSoup(html, "html.parser")
    query_words = set(w.lower() for w in query.split() if len(w) > 3)
    if common_name:
        query_words |= set(w.lower() for w in common_name.split() if len(w) > 3)

    skip_patterns = ["/category/", "/tag/", "/page/", "/?s=", "/wp-admin", "/wp-login"]

    candidates = soup.select(
        "article a, .search-result a, h2 a, h3 a, .entry-title a, .post-title a"
    )
    if not candidates:
        candidates = soup.find_all("a", href=True)

    for a in candidates:
        href = a.get("href", "").strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        if href.startswith("/"):
            href = f"https://{domain}{href}"
        if domain not in href:
            continue
        if any(p in href for p in skip_patterns):
            continue

        title = a.get_text(strip=True).lower()
        href_lower = href.lower()
        if any(w in title or w in href_lower for w in query_words):
            return href

    return None


def _extract_body_text(html: str, url: str) -> Optional[str]:
    """
    Extract readable prose text from an article page.
    Strips nav, header, footer, sidebar, scripts, styles.
    Returns cleaned plain text, or None if nothing useful found.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Remove boilerplate elements
    for tag in soup.select(
        "nav, header, footer, aside, script, style, "
        ".sidebar, .widget, .nav, .menu, .comments, "
        "#comments, .advertisement, .ad, .social-share"
    ):
        tag.decompose()

    # Try article/main content containers first
    article = (
        soup.find("article")
        or soup.find(class_=lambda c: c and any(
            k in c for k in ("entry-content", "post-content", "article-content",
                             "main-content", "page-content", "content-area")
        ))
        or soup.find("main")
    )
    target = article or soup.find("body") or soup

    lines = []
    for elem in target.find_all(["p", "li", "h2", "h3", "h4"]):
        text = elem.get_text(separator=" ", strip=True)
        if text and len(text) > 30:
            lines.append(text)

    body = "\n\n".join(lines)
    return body if len(body) > 100 else None
