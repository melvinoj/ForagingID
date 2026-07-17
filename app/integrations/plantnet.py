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
import logging
import requests as _requests  # sync, reliable for multipart file uploads
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List

_log = logging.getLogger(__name__)

PLANTNET_BASE = "https://my-api.plantnet.org/v2/identify"
DEFAULT_PROJECT = "all"
DEFAULT_ORGAN = "auto"

# (connect, read) rather than a scalar.
#
# requests' timeout is NOT a total-request budget: the value applies to the
# connect phase and then to each individual socket operation independently.
# The old scalar 8 therefore never meant "the upload may take 8 s" — it meant
# "no single socket op may stall 8 s", which is a different and much more easily
# tripped condition.
#
# Measured against 22099's real 4.03 MB photo, 8 trials, uplink at 8.99 Mbit/s:
#   OK 4.84 / 5.02 / 3.79 / 3.22 / 3.23 / 3.57 / 4.12 s   (7 of 8)
#   FAIL 9.63 s — "request timed out"                     (1 of 8)
# Successes cluster at 3.2–5.0 s, i.e. 40–60% of the old ceiling. The failure is
# not a call running slightly over budget; it is a momentary socket stall on a
# link shared with ngrok and Syncthing. 4 MB at 8.99 Mbit/s needs only ~3.6 s of
# transfer, so bandwidth is not the constraint.
#
#   connect=5  keeps the fail-fast property that mattered on 15 July: the DNS
#              failure surfaced in well under 1 s, and a dead network must never
#              hang the pipeline behind a spinner.
#   read=25    a real ceiling ~5x the observed worst success (5.02 s) and well
#              outside the success range, so a trip means something is genuinely
#              wrong rather than merely slow.
#
# Raising this further would not fix the stall — it would only wait longer for
# the same fault. The stall is handled by the bounded retry below, not here.
REQUEST_TIMEOUT = (5, 25)

# Back-compat: callers/tests that read a scalar get the effective ceiling.
REQUEST_TIMEOUT_S = 25

# Bounded retry for transport transients only.
#
# Attempt count: first-attempt success measured at 7/8 (~87.5%). Independent
# stalls compound as (1/8)^n, so 3 attempts ≈ 1-in-512 residual failure. That is
# the knee of the curve — a 4th attempt buys ~1-in-4096 while adding another
# 25 s of worst-case latency to a call that is already failing. Kept low
# deliberately: retry masks a real fault, so it must not become a way of never
# seeing it.
#
# Backoff: 0.5 s then 1.5 s. The observed stall is momentary (neighbouring calls
# in the same loop succeeded in ~3 s), so a short pause is enough to land on a
# clear socket. Deliberately not exponential-with-jitter — this is a single-user
# local pipeline against an API we are not thundering-herding, and the total
# added latency on a fully failed call stays bounded at ~2 s of sleep.
PLANTNET_MAX_ATTEMPTS = 3
PLANTNET_RETRY_BACKOFF_S = (0.5, 1.5)


class PlantNetError(Exception):
    """
    Raised on any PlantNet API failure — caller stores 'failed_identification'.

    is_connection_error: True when the failure is a network/timeout problem
    (offline) rather than an API-level error (bad key, malformed response).
    The identification pipeline uses this to route the observation to
    'pending_connection' instead of discarding it.

    attempts: how many transport attempts were made before giving up. 1 for any
    non-retried failure (HTTP errors are never retried). Lets callers log the
    real retry cost so the transient-stall rate stays measurable.
    """
    def __init__(self, message: str, status_code: Optional[int] = None,
                 is_connection_error: bool = False, attempts: int = 1):
        super().__init__(message)
        self.status_code = status_code
        self.is_connection_error = is_connection_error
        self.attempts = attempts


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
    # Transport attempts needed to obtain this response. 1 = first attempt.
    # >1 means a transient socket stall was retried through. Purely diagnostic:
    # it records what the transport cost, and must never influence candidates,
    # scores, thresholds or routing — a retried success is otherwise identical
    # to a first-attempt success.
    attempts: int = 1

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
            timeout=REQUEST_TIMEOUT,
        )

    # ── Bounded retry — transport transients ONLY ────────────────────────────
    # Retries a socket-level stall (Timeout / ConnectionError), which is the
    # ~1-in-8 fault measured against this endpoint. Never retries an HTTP
    # status: a 4xx/5xx means PlantNet answered, and re-sending a 4 MB image to
    # an API that already gave a verdict is quota abuse — a 429 in particular
    # would be made strictly worse by retrying it. Those paths fall through to
    # the status handling below on the first response, exactly as before.
    #
    # Purely a transport concern: identical request each attempt, and the
    # response of a retried success is the same object shape a first-attempt
    # success returns. Nothing here can alter candidates, scores, thresholds or
    # routing — a retried success is indistinguishable downstream except for
    # .attempts on the result.
    loop = asyncio.get_event_loop()
    response = None
    attempts = 0
    last_transport_error: Optional[PlantNetError] = None

    for attempt in range(1, PLANTNET_MAX_ATTEMPTS + 1):
        attempts = attempt
        try:
            response = await loop.run_in_executor(None, _do_post)
            break
        except _requests.Timeout:
            last_transport_error = PlantNetError(
                "PlantNet request timed out", is_connection_error=True
            )
        except _requests.ConnectionError as e:
            last_transport_error = PlantNetError(
                f"PlantNet connection error: {e}", is_connection_error=True
            )
        except _requests.RequestException as e:
            # Not a socket stall (malformed request, invalid URL, …) — a retry
            # would fail identically. Surface immediately.
            raise PlantNetError(f"PlantNet network error: {e}")

        if attempt < PLANTNET_MAX_ATTEMPTS:
            _log.warning(
                "PlantNet transport failure on attempt %d/%d for %s: %s — retrying",
                attempt, PLANTNET_MAX_ATTEMPTS, image_path.name, last_transport_error,
            )
            await asyncio.sleep(PLANTNET_RETRY_BACKOFF_S[attempt - 1])

    if response is None:
        # Every attempt hit a transport stall. Preserve the real recorded fault
        # (is_connection_error stays True) and state the attempt count so the
        # retry is never silent — the messaging contract from 16 July stands:
        # report what was recorded, never a guessed cause.
        _log.warning(
            "PlantNet: all %d attempts failed for %s — %s",
            attempts, image_path.name, last_transport_error,
        )
        raise PlantNetError(
            f"{last_transport_error} (after {attempts} attempts)",
            is_connection_error=True,
            attempts=attempts,
        )

    if attempts > 1:
        _log.info(
            "PlantNet: succeeded on attempt %d/%d for %s",
            attempts, PLANTNET_MAX_ATTEMPTS, image_path.name,
        )

    # From here on the request is answered — these paths are reached on the
    # first response and are never retried (see the loop comment above).
    if response.status_code == 404:
        # PlantNet returns 404 when no species match at all (not truly an error)
        return PlantNetResult(best_match=None, candidates=[],
                              raw_response={"status": 404, "message": "no_result"},
                              attempts=attempts)

    if response.status_code != 200:
        raise PlantNetError(
            f"PlantNet API error {response.status_code}: {response.text[:200]}",
            status_code=response.status_code,
            attempts=attempts,
        )

    try:
        payload = response.json()
    except Exception as e:
        raise PlantNetError(f"PlantNet returned non-JSON response: {e}", attempts=attempts)

    result = _parse_response(payload)
    result.attempts = attempts
    return result
