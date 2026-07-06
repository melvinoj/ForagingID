"""
iNaturalist API client.

Vision scoring:
  POST https://api.inaturalist.org/v1/computervision/score_image
  multipart/form-data  field: 'image'
  Requires Authorization: Bearer <token> since mid-2024.
  Token from: https://www.inaturalist.org/users/api_token
  Set INATURALIST_API_TOKEN in .env.  Returns [] if no token or any failure.

Taxa autocomplete:
  GET  https://api.inaturalist.org/v1/taxa/autocomplete?q={q}&limit={n}
  No auth required. Returns matching taxa with common names.

Both methods return empty lists on any failure rather than raising — callers
treat iNaturalist as a best-effort enrichment, not a hard dependency.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import httpx

log = logging.getLogger("foragingid.inaturalist")

VISION_URL = "https://api.inaturalist.org/v1/computervision/score_image"
TAXA_URL   = "https://api.inaturalist.org/v1/taxa/autocomplete"
TAXA_SEARCH_URL = "https://api.inaturalist.org/v1/taxa"
TAXA_DETAIL_URL = "https://api.inaturalist.org/v1/taxa/{taxon_id}"
# Fail fast when offline: 8 s ceiling so a dead connection never hangs the
# pipeline behind a spinner that never resolves (offline-hardening Fix 1).
TIMEOUT_S  = 8

# Last observed iNaturalist call status — surfaced to the owner UI (via /api/me) so an
# expired token, which silently routes every scan to needs_review, is visible during
# work rather than only in the boot log. Updated on each inat_score() call and at boot.
_LAST_STATUS = {"state": "unknown", "detail": None, "at": None}


def record_inat_status(state: str, detail: Optional[str] = None) -> None:
    """state: 'ok' | 'token_expired' | 'rate_limited' | 'error' | 'unreachable'."""
    from datetime import datetime
    _LAST_STATUS["state"] = state
    _LAST_STATUS["detail"] = detail
    _LAST_STATUS["at"] = datetime.utcnow().isoformat()


def last_inat_status() -> dict:
    return dict(_LAST_STATUS)


class INatConnectionError(Exception):
    """
    Raised only by score_image (when raise_on_connection_error=True) on a
    network/timeout failure — i.e. the device is offline. HTTP-status errors
    (401/429) and other problems still fall through to an empty list, since
    iNaturalist is otherwise a best-effort source.
    """


@dataclass
class INatCandidate:
    scientific_name: str
    common_name: Optional[str]
    score: float                        # 0.0–1.0 — GATING score (threshold/auto-approve)
    taxon_id: Optional[int]
    rank: Optional[str]
    common_names: List[str] = field(default_factory=list)
    # e.g. "Plantae", "Fungi", "Animalia" — useful for category auto-detection
    iconic_taxon_name: Optional[str] = None
    # Pure visual CV confidence, geo-independent (iNat `vision_score`/100).
    vision_score: Optional[float] = None
    # Geo-weighted confidence (iNat `combined_score`/100). Equals vision_score
    # when no location was supplied. Used for RANKING only — locally plausible
    # species rank higher. Never used to gate auto-approval (see score_image).
    geo_score: Optional[float] = None


@dataclass
class INatTaxon:
    scientific_name: str
    common_name: Optional[str]
    rank: Optional[str]
    taxon_id: int
    family: Optional[str] = None
    genus: Optional[str] = None


@dataclass
class INatTaxonDescription:
    """
    Result from the iNaturalist taxa search endpoint.
    Carries description / ID notes for enrichment.
    """
    scientific_name: str
    taxon_id: int
    description: Optional[str]          # Wikipedia summary or iNat description
    identification_notes: Optional[str]  # From taxon.identification_tips if present
    wikipedia_url: Optional[str]
    raw_json: dict


async def score_image(
    image_path: Path,
    api_token: Optional[str] = None,
    raise_on_connection_error: bool = False,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    observed_on: Optional[str] = None,
) -> List[INatCandidate]:
    """
    Submit one image to iNaturalist vision and return ranked candidates.
    api_token — Bearer token from https://www.inaturalist.org/users/api_token.
                Required as of mid-2024 (API returns 401 without it).
                Falls through to empty list when absent, not an error.
    raise_on_connection_error — when True, a network/timeout failure (offline)
                raises INatConnectionError instead of returning []. The
                identification pipeline sets this so offline observations can be
                parked as 'pending_connection' rather than silently dropped.
                Default False keeps the best-effort contract for all other callers.
    lat, lng — observation coordinates. When BOTH are supplied, iNaturalist's
                Geomodel weights the vision results by spatio-temporal frequency,
                so locally plausible species rank higher (Fix E — location bias).
                PlantNet does not accept coordinates (see A2); this is iNat-only.
    observed_on — optional ISO date (YYYY-MM-DD) for seasonal weighting.

    Location bias is RANKING-ONLY and safe for auto-approval:
      - candidates are ordered by the geo-weighted `combined_score` (geo_score);
      - the `score` field used downstream for confidence thresholds and the
        dual-source auto-approve gate is min(combined_score, vision_score), so
        geo can only DEMOTE a candidate, never inflate it above its pure visual
        score. Location bias can therefore never cause a new auto-approval
        (Fix E safety check #4). With no coordinates, behaviour is unchanged.

    Returns empty list (never raises by default) so PlantNet failures don't cascade.
    """
    # Vision API requires a token since mid-2024
    if not api_token:
        log.warning("iNat vision skipped: no API token configured")
        return []

    try:
        image_bytes = image_path.read_bytes()
    except OSError as exc:
        log.warning("iNat vision skipped: cannot read %s (%s)", image_path, exc)
        return []

    # Derive correct MIME type from extension — hardcoding image/jpeg for PNGs
    # or WebPs causes iNat to return HTTP 500 on payload validation.
    _MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
             ".png": "image/png", ".webp": "image/webp"}
    mime = _MIME.get(image_path.suffix.lower(), "image/jpeg")

    # Location bias is applied only when BOTH coordinates are present — a lone
    # lat or lng is meaningless to the Geomodel and is ignored.
    geo_applied = lat is not None and lng is not None
    form_data: dict = {}
    if geo_applied:
        form_data["lat"] = str(lat)
        form_data["lng"] = str(lng)
    if observed_on:
        form_data["observed_on"] = observed_on

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            resp = await client.post(
                VISION_URL,
                headers={"Authorization": f"Bearer {api_token}"},
                files={"image": (image_path.name, image_bytes, mime)},
                data=form_data or None,
            )
        if resp.status_code != 200:
            hint = ""
            if resp.status_code == 401:
                hint = " — token expired or invalid; refresh at inaturalist.org/users/api_token"
            elif resp.status_code == 429:
                hint = " — rate limited; slow down request cadence"
            elif resp.status_code == 500:
                hint = " — server error or soft rate-limit (iNat returns 500 on quota exhaustion)"
            # Log up to 300 chars of the response body so the cause is diagnosable
            # (iNat sometimes embeds a useful message even on 500).
            try:
                body_excerpt = resp.text[:300].strip()
            except Exception:
                body_excerpt = "<unreadable>"
            log.warning(
                "iNat vision HTTP %s for %s%s | body: %s",
                resp.status_code, image_path.name, hint, body_excerpt,
            )
            record_inat_status(
                "token_expired" if resp.status_code == 401
                else "rate_limited" if resp.status_code == 429
                else "error",
                f"HTTP {resp.status_code}",
            )
            return []
        data = resp.json()
        record_inat_status("ok")
    except (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError) as exc:
        # Offline / unreachable — distinct from a quota or token problem.
        log.warning("iNat vision connection failed: %s: %s", type(exc).__name__, exc)
        record_inat_status("unreachable", str(exc)[:120])
        if raise_on_connection_error:
            raise INatConnectionError(str(exc)) from exc
        return []
    except Exception as exc:
        log.warning("iNat vision request failed: %s: %s", type(exc).__name__, exc)
        return []

    candidates: List[INatCandidate] = []
    for item in data.get("results", []):
        taxon = item.get("taxon") or {}
        sci   = (taxon.get("name") or "").strip()
        if not sci:
            continue
        # Scores are returned in the 0–100 range by the iNaturalist API; divide
        # by 100 to normalise to the same 0.0–1.0 scale used by PlantNet.
        # combined_score = vision + geo/seasonal weighting (geo-aware when lat/lng
        # were sent); vision_score = pure visual confidence. Fall back gracefully
        # if either field is absent on a given result.
        raw_combined = item.get("combined_score")
        if raw_combined is None:
            raw_combined = item.get("score") or 0.0
        combined = float(raw_combined) / 100.0
        raw_vision = item.get("vision_score")
        vision = float(raw_vision) / 100.0 if raw_vision is not None else combined
        # GATING score: the pure visual confidence, geo-independent. This is what
        # all downstream threshold / dual-source auto-approve logic reads, so
        # location is RANKING-ONLY and leaves gating untouched (#2: "ranking bias
        # only — do not change confidence thresholds"). It can therefore never
        # create OR suppress an auto-approval (#4). With no coordinates the API
        # returns combined == vision, so this matches legacy behaviour exactly.
        gate = vision
        pref_common = taxon.get("preferred_common_name")
        candidates.append(INatCandidate(
            scientific_name=sci,
            common_name=pref_common,
            score=gate,
            taxon_id=taxon.get("id"),
            rank=taxon.get("rank"),
            common_names=[pref_common] if pref_common else [],
            iconic_taxon_name=taxon.get("iconic_taxon_name"),
            vision_score=vision,
            geo_score=combined,
        ))
    # Rank by the geo-weighted combined score so locally plausible species
    # surface higher (Fix E ranking bias). Stable sort; with no coordinates this
    # preserves the API's original (vision-only) ordering.
    candidates.sort(
        key=lambda c: c.geo_score if c.geo_score is not None else c.score,
        reverse=True,
    )
    return candidates


async def fetch_taxon_description(scientific_name: str) -> Optional[INatTaxonDescription]:
    """
    Query iNaturalist taxa endpoint for a species by scientific name.

    Uses GET /v1/taxa?q={name}&rank=species — no auth required.
    Extracts:
      - wikipedia_summary (taxon description / ID notes)
      - wikipedia_url
      - identification tips if present

    Returns INatTaxonDescription or None on any failure.
    """
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            resp = await client.get(
                TAXA_SEARCH_URL,
                params={"q": scientific_name.strip(), "rank": "species", "per_page": 3},
            )
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception:
        return None

    results = data.get("results", [])
    if not results:
        return None

    # Find the best match — prefer exact scientific name
    best = None
    name_lower = scientific_name.lower()
    for item in results:
        if (item.get("name") or "").lower() == name_lower:
            best = item
            break
    if best is None:
        best = results[0]

    taxon_id = best.get("id", 0)
    wiki_url = best.get("wikipedia_url")

    # The search endpoint /v1/taxa doesn't return wikipedia_summary.
    # Fetch the individual taxon record /v1/taxa/{id} to get the full description.
    wiki_summary = best.get("wikipedia_summary") or best.get("description")
    id_tips = best.get("identification_tips")
    if taxon_id and not wiki_summary:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_S) as _c:
                _dr = await _c.get(TAXA_DETAIL_URL.format(taxon_id=taxon_id))
            if _dr.status_code == 200:
                _detail_data = _dr.json()
                _detail_results = _detail_data.get("results", [])
                if _detail_results:
                    _dt = _detail_results[0]
                    wiki_summary = _dt.get("wikipedia_summary") or _dt.get("description") or wiki_summary
                    id_tips = id_tips or _dt.get("identification_tips")
                    wiki_url = wiki_url or _dt.get("wikipedia_url")
        except Exception:
            pass  # best-effort — continue with whatever we have

    # Clean HTML from wiki summary if present
    if wiki_summary:
        try:
            from bs4 import BeautifulSoup as _BS
            wiki_summary = _BS(wiki_summary, "html.parser").get_text(separator=" ", strip=True)
            wiki_summary = " ".join(wiki_summary.split())
            wiki_summary = wiki_summary[:3000]  # cap length
        except Exception:
            pass

    if id_tips:
        try:
            from bs4 import BeautifulSoup as _BS
            id_tips = _BS(id_tips, "html.parser").get_text(separator=" ", strip=True)
            id_tips = " ".join(id_tips.split())
            id_tips = id_tips[:1500]
        except Exception:
            pass

    return INatTaxonDescription(
        scientific_name=scientific_name,
        taxon_id=taxon_id,
        description=wiki_summary or None,
        identification_notes=id_tips or None,
        wikipedia_url=wiki_url or None,
        raw_json=best,
    )


async def taxa_autocomplete(query: str, limit: int = 5) -> List[INatTaxon]:
    """
    Autocomplete species/taxon name lookup.
    Returns empty list on any failure.
    """
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            resp = await client.get(
                TAXA_URL,
                params={"q": query.strip(), "limit": limit},
            )
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:
        return []

    taxa: List[INatTaxon] = []
    for item in data.get("results", []):
        sci = (item.get("name") or "").strip()
        if not sci:
            continue
        taxa.append(INatTaxon(
            scientific_name=sci,
            common_name=item.get("preferred_common_name"),
            rank=item.get("rank"),
            taxon_id=item.get("id", 0),
            family=None,
            genus=None,
        ))
    return taxa


async def get_regional_obs_count(
    taxon_name: str, lat: float, lng: float, radius_km: int = 150
) -> int:
    """Return iNaturalist observation count near a location. Returns 0 on any error."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
            resp = await client.get(
                "https://api.inaturalist.org/v1/observations",
                params={
                    "taxon_name": taxon_name,
                    "lat": lat,
                    "lng": lng,
                    "radius": radius_km,
                    "per_page": 0,
                },
            )
        if resp.status_code != 200:
            return 0
        data = resp.json()
    except Exception:
        return 0
    return int(data.get("total_results", 0))
