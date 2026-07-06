"""
Google Takeout JSON sidecar reader.

Google Photos Takeout exports a JSON sidecar alongside each photo using one of
several naming patterns depending on filename length and photo type:

    Standard:
        IMG_1234.jpg  →  IMG_1234.jpg.supplemental-metadata.json
        PXL_20240901_123456789.jpg  →  PXL_20240901_123456789.jpg.supplemental-metadata.json

    Truncated suffix (filesystem 255-char limit hit):
        PXL_20250827_203058728.jpg  →  PXL_20250827_203058728.jpg.supplemental-metada.json

    BURST photos (extension truncated):
        00000IMG_BURST20201116_COVER.jpg  →  00000IMG_BURST20201116_COVER.jp.json

    UUID-prefixed (Takeout adds prefix to the sidecar when the photo was renamed):
        PXL_20260328_074645604.NIGHT.jpg
            →  original_bca9b6cb-6e15-45bc-8971_PXL_20260328_074645604.NIGHT.jpg.json

The sidecar can contain GPS in two fields:
    geoData      — GPS at time the photo was taken (phone GPS lock)
    geoDataExif  — GPS embedded in the EXIF of the image file

We prefer geoData (more likely to reflect true location) and fall back to
geoDataExif. Both are skipped if either coordinate is 0.0 (the null sentinel
Google uses for "no location data").

This module is side-effect-free — it never writes any file.
"""

import json
import logging
from pathlib import Path
from typing import Optional, Tuple

log = logging.getLogger(__name__)


def _find_sidecar(photo_path: Path) -> Optional[Path]:
    """
    Locate the Google Takeout JSON sidecar for a photo using all known patterns.

    Patterns tried in order:
      1. <photo>.supplemental-metadata.json  — standard Takeout suffix
      2. <photo>.supplemental-metada.json    — truncated at 255-char filesystem limit
      3. <photo>.json                         — simple / legacy pattern
      4. <stem><ext_minus_last_char>.json    — BURST truncation (.jpg → .jp.json)
      5. Directory scan for any *.json containing the photo filename as a substring
         (handles UUID-prefixed sidecars: original_UUID_<photo>.supplemental-metadata.json)

    Returns the first matching Path, or None if no sidecar is found.
    Never raises — returns None on any filesystem error.
    """
    photo_name = photo_path.name   # e.g. "PXL_20250827_203058728.jpg"
    parent = photo_path.parent

    # Patterns 1–3: deterministic candidates, no directory scan needed
    for candidate in (
        parent / (photo_name + ".supplemental-metadata.json"),
        parent / (photo_name + ".supplemental-metada.json"),
        parent / (photo_name + ".json"),
    ):
        if candidate.exists():
            return candidate

    # Pattern 4: BURST / long-name truncation — last char of extension stripped
    # e.g. "file.jpg" → "file.jp.json",  "file.jpeg" → "file.jpe.json"
    ext = photo_path.suffix   # e.g. ".jpg"
    if len(ext) >= 2:
        burst_candidate = parent / (photo_path.stem + ext[:-1] + ".json")
        if burst_candidate.exists():
            return burst_candidate

    # Pattern 5: Directory scan — UUID-prefixed and other non-deterministic patterns.
    # Match any *.json in the same directory whose name contains the full photo
    # filename as a substring (the UUID prefix comes before the original name).
    try:
        for candidate in sorted(parent.glob("*.json")):
            if photo_name in candidate.name:
                return candidate
    except (PermissionError, OSError):
        pass

    return None


def read_takeout_gps(photo_path: Path) -> Optional[Tuple[float, float]]:
    """
    Read GPS coordinates from a Google Takeout JSON sidecar file.

    Searches for the sidecar using all known Takeout naming patterns
    (see module docstring for the full list).

    Returns (latitude, longitude) or None if:
        - No sidecar file exists under any recognised pattern
        - Sidecar has no GPS data
        - Both coordinates are 0.0 (Google null sentinel)
        - Coordinates are out of valid range
        - Any parse error occurs

    Never raises — always returns None on any failure.
    """
    sidecar = _find_sidecar(photo_path)
    if sidecar is None:
        return None

    log.debug("Found sidecar: %s", sidecar)
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8", errors="replace"))
    except Exception as exc:
        log.debug("Sidecar parse error for %s: %s", sidecar, exc)
        return None

    # Try geoData first (higher accuracy on modern phones), then geoDataExif
    for key in ("geoData", "geoDataExif"):
        geo = data.get(key)
        if not isinstance(geo, dict):
            continue

        lat = geo.get("latitude")
        lng = geo.get("longitude")
        if lat is None or lng is None:
            continue

        try:
            lat = float(lat)
            lng = float(lng)
        except (TypeError, ValueError):
            continue

        # Google uses exactly (0.0, 0.0) as a "no GPS" sentinel — skip it
        if lat == 0.0 and lng == 0.0:
            continue

        # Basic coordinate range sanity check
        if not (-90.0 <= lat <= 90.0):
            continue
        if not (-180.0 <= lng <= 180.0):
            continue

        return lat, lng

    return None
