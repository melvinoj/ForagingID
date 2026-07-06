"""
PlantNet API v2 client.

Docs: https://my-api.plantnet.org/
Endpoint: POST https://my-api.plantnet.org/v2/identify/{project}
  project: "all" (all flora) or a regional project like "weurope"

Request:
  multipart/form-data
  - images: image file bytes
  - organs: organ type per image (auto | leaf | flower | fruit | bark | habit)
  - lang: result language (default "en")

Auth: api-key query parameter.

Failure strategy (per spec):
  - HTTP errors / timeouts → raise PlantNetError so caller stores 'failed_identification'
  - Malformed responses → raise PlantNetError
  - Never silently return empty or fabricated data
"""

import asyncio
import requests as _requests  # sync, reliable for multipart file uploads
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

PLANTNET_BASE = "https://my-api.plantnet.org/v2/identify"
DEFAULT_PROJECT = "all"
DEFAULT_ORGAN = "auto"
# Fail fast when offline: 8 s ceiling so a dead connection never hangs the
# pipeline behind a spinner that never resolves (offline-hardening Fix 1).
REQUEST_TIMEOUT_S = 8


class PlantNetError(Exception):
    """
    Raised on any PlantNet API failure — caller stores 'failed_identification'.

    is_connection_error: True when the failure is a network/timeout problem
    (offline) rather than an API-level error (bad key, malformed response).
    The identification pipeline uses this to route the observation to
    'pending_connection' instead of discarding it.
    """
    def __init__(self, message: str, status_code: Optional[int] = None,
                 is_connection_error: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.is_connection_error = is_connection_error


@dataclass
class PlantNetCandidate:
    scientific_name: str
    common_names: list[str]
    score: float               # 0.0–1.0, higher is more confident
    family: Optional[str]
    genus: Optional[str]
    gbif_id: Optional[str]
    rank: int                  # 1 = top result
    # Reference images from PlantNet — populated when include_related_images=True.
    # Each dict: {"url": str, "organ": str, "author": str}
    # URL points to PlantNet's CDN (medium-size); lazy-load safe.
    images: List[dict] = field(default_factory=list)


@dataclass
class PlantNetResult:
    best_match: Optional[str]
    candidates: list[PlantNetCandidate]
    raw_response: dict          # full API JSON — always stored

    @property
    def top_candidate(self) -> Optional[PlantNetCandidate]:
        return self.candidates[0] if self.candidates else None

    @property
    def top_score(self) -> float:
        return self.candidates[0].score if self.candidates else 0.0


def _parse_response(data: dict) -> PlantNetResult:
    """Parse the PlantNet v2 JSON response into structured types."""
    results = data.get("results", [])
    candidates = []

    for rank, r in enumerate(results, start=1):
        sp = r.get("species", {})
        sci_name = sp.get("scientificNameWithoutAuthor", "").strip()
        if not sci_name:
            continue

        # Extract reference images when include-related-images=true was requested.
        # Each PlantNet image entry: {"url": {"s":…, "m":…, "o":…}, "organ":…, "author":…}
        ref_images: List[dict] = []
        for img in (r.get("images") or []):
            url_obj = img.get("url", {})
            # URL is a nested dict keyed by size (s=small, m=medium, o=original)
            if isinstance(url_obj, dict):
                img_url = url_obj.get("m") or url_obj.get("s") or url_obj.get("o") or ""
            else:
                img_url = str(url_obj) if url_obj else ""
            if img_url:
                ref_images.append({
                    "url": img_url,
                    "organ": img.get("organ", ""),
                    "author": img.get("author", ""),
                })

        candidates.append(PlantNetCandidate(
            scientific_name=sci_name,
            common_names=sp.get("commonNames", []),
            score=float(r.get("score", 0.0)),
            family=(sp.get("family") or {}).get("scientificNameWithoutAuthor"),
            genus=(sp.get("genus") or {}).get("scientificNameWithoutAuthor"),
            gbif_id=str((r.get("gbif") or {}).get("id", "") or "").strip() or None,
            rank=rank,
            images=ref_images,
        ))

    return PlantNetResult(
        best_match=data.get("bestMatch"),
        candidates=candidates,
        raw_response=data,
    )


async def identify_image(
    image_path: Path,
    api_key: str,
    project: str = DEFAULT_PROJECT,
    organ: str = DEFAULT_ORGAN,
    lang: str = "en",
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    include_related_images: bool = False,
) -> PlantNetResult:
    """
    Send one image to PlantNet and return structured results.

    lat/lng: accepted for API compatibility but NOT forwarded to PlantNet.
    The v2 identify endpoint does not accept geographic query parameters —
    sending "lat" or "lng" causes a 400 Bad Request ("lat" is not allowed).

    include_related_images: when True, each candidate in the response includes
    PlantNet reference images (url, organ, author).  These are shown in the
    Second Opinion panel for visual comparison.  Default False — batch
    pipelines (scan, identification) must never set this to True.

    Raises:
        PlantNetError: on any HTTP error, timeout, or malformed response.
                       Caller MUST catch this and store 'failed_identification'.
    """
    url = f"{PLANTNET_BASE}/{project}"
    params = {
        "api-key": api_key,
        "lang": lang,
        "include-related-images": "true" if include_related_images else "false",
    }
    try:
        with open(image_path, "rb") as img_file:
            image_bytes = img_file.read()
    except OSError as e:
        raise PlantNetError(f"Cannot read image file: {e}")

    # Use requests (sync) via executor — more reliable than httpx for mixed
    # multipart file+data POSTs and battle-tested for this exact use case.
    def _do_post() -> _requests.Response:
        return _requests.post(
            url,
            params=params,
            files=[("images", (image_path.name, image_bytes, "image/jpeg"))],
            data=[("organs", organ)],
            timeout=REQUEST_TIMEOUT_S,
        )

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, _do_post)
    except _requests.Timeout:
        raise PlantNetError("PlantNet request timed out", is_connection_error=True)
    except _requests.ConnectionError as e:
        raise PlantNetError(f"PlantNet connection error: {e}", is_connection_error=True)
    except _requests.RequestException as e:
        raise PlantNetError(f"PlantNet network error: {e}")

    if response.status_code == 404:
        # PlantNet returns 404 when no species match at all (not truly an error)
        return PlantNetResult(best_match=None, candidates=[], raw_response={"status": 404, "message": "no_result"})

    if response.status_code != 200:
        raise PlantNetError(
            f"PlantNet API error {response.status_code}: {response.text[:200]}",
            status_code=response.status_code,
        )

    try:
        payload = response.json()
    except Exception as e:
        raise PlantNetError(f"PlantNet returned non-JSON response: {e}")

    return _parse_response(payload)
