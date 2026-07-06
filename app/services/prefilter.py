"""
Plant likelihood pre-filter — runs between ingestion and identification.

Purpose: classify images as plant-likely / not-plant BEFORE calling PlantNet,
so we don't waste API quota on animals, people, food, vehicles, screenshots, etc.

Design principles:
  - TIGHTER than before: ambiguous images default to FAIL, not pass.
  - Filename-based detection runs first — catches JPEG screenshots the
    resolution check cannot see.
  - GPS is a mild confidence boost only — NOT a bypass. An outdoor photo of
    a dog, a person, food, or a car still has GPS and still fails.
  - No ML dependencies — pure PIL + colorsys pixel analysis.
  - Fast: ~1–3ms per image at 100×100 sample.
  - Stores a rejection category so the UI can show why an image was filtered.

Classification logic (priority order):
  1. Filename indicates screenshot (Screenshot_*, screen_*, etc.) → reject
  2. PNG + standard screen resolution + no green → reject
  3. Any format + known screen resolution + no green → reject
  4. Dominant grey/white/blank → reject
  5. Skin-dominant + no plant signal → reject (person or animal)
  6. Warm-dominant (food/fire colours) + no plant signal → reject
  7. Sky-blue-dominant + no plant signal → reject
  8. Dark interior / nighttime scene → reject
     >10% near-black + essentially zero sky signal + limited green
     (catches windowsill pot plants at night, dark indoor scenes)
  9. Artificially lit interior → reject
     >10% blown-out-bright + >20% neutral grey + no sky + green < 32%
     (catches greenhouse growing scenes, indoor grow lights)
 10. Enough green/earthy vegetation pixels → accept
     - With GPS:    ≥ 12% (outdoor camera, still needs meaningful green)
     - Without GPS: ≥ 22% (stricter — must show clear plant signal)
 11. Default: REJECT (requires positive evidence of plant)

Rejection categories (stored in prefilter_category):
  screenshot, ui_blank, person_animal, food_warm, sky_blue,
  indoor_dark, indoor_bright, no_plant_signal

What this catches:
  ✓ iOS/Android screenshots (by filename and by resolution, all formats)
  ✓ Blank/solid-colour images
  ✓ Outdoor people/portrait photos
  ✓ Outdoor animal photos
  ✓ Food photos (warm, saturated, no green)
  ✓ Car/vehicle photos (grey, metallic, no green)
  ✓ Indoor scenes without plants
  ✓ Sky/water photos
  ✓ Distant/landscape shots with insufficient plant detail
"""

import colorsys
import logging
import time
from pathlib import Path
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.observation import Observation
from app.models.processing import ProcessingLog
from app.services.file_cleanup import delete_observation_file

_pf_log = logging.getLogger("foragingid.prefilter")


# Colour analysis uses a 100×100 thumbnail — fast and sufficient
_ANALYSIS_SIZE = (100, 100)

# Screen resolutions that strongly suggest a screenshot (w×h or h×w)
# Applied to ALL formats — not just PNG.
_SCREEN_RESOLUTIONS: set = {
    (1920, 1080), (2560, 1440), (3840, 2160),    # desktop
    (1170, 2532), (1284, 2778), (1080, 2340),    # modern phones (portrait)
    (2532, 1170), (2778, 1284), (2340, 1080),    # same, landscape
    (1080, 1920), (720, 1280), (1440, 2960),     # older phones
    (1920, 1280), (2560, 1600), (2880, 1800),    # laptops
    (1366, 768),  (1280, 800),  (1280, 720),     # common laptop/TV screens
    (2388, 1668), (2732, 2048),                   # iPad
    (1080, 2400), (1440, 3200),                   # tall modern phones
}

# Filename prefixes/substrings that positively identify screenshots
_SCREENSHOT_FILENAME_MARKERS = (
    "screenshot",
    "screen_shot",
    "screen-shot",
    "screencap",
    "screen_cap",
)

# ── Hue ranges (0–1 scale from colorsys) ──────────────────────────────────

# Vegetation greens
_GREEN_HUE_MIN = 0.22    # ~80° — yellow-green (new leaves)
_GREEN_HUE_MAX = 0.47    # ~170° — blue-green (dark foliage)

# Earthy browns (bark, soil, dried plants)
_BROWN_HUE_MIN = 0.05    # ~18° — warm brown
_BROWN_HUE_MAX = 0.14    # ~50° — yellow-brown

# Skin tones (human and animal — both are rejection targets)
_SKIN_HUE_A_MAX = 0.08   # 0.0–0.08: reds/pinks/peach
_SKIN_HUE_B_MIN = 0.88   # 0.88–1.0: wraps around through red

# Warm saturated non-plant (cooked food, fire, red objects)
_WARM_HUE_MAX = 0.12     # Reds, oranges, warm yellows that are NOT earthy brown

# Sky/water blue
_BLUE_HUE_MIN = 0.53
_BLUE_HUE_MAX = 0.70

# ── Detection thresholds (tightened) ──────────────────────────────────────

# Minimum green+brown signal required to classify as plant-likely
PLANT_GREEN_THRESHOLD     = 0.12   # Without GPS: same as GPS threshold (was 0.22)
PLANT_GREEN_THRESHOLD_GPS = 0.12   # With GPS: needs clear green (was 0.08)

# Rejection thresholds for non-plant categories (all tightened)
SKIN_REJECT_THRESHOLD     = 0.15   # >15% skin-like pixels AND <10% green → reject (was 0.20)
WARM_REJECT_THRESHOLD     = 0.20   # >20% warm-saturated AND <4% green → reject (was 0.25)
BLUE_REJECT_THRESHOLD     = 0.35   # >35% sky-blue AND <5% green → reject (was 0.40)
UI_RATIO_THRESHOLD        = 0.65   # >65% pure-white/pure-black → blank/UI reject
DOMINANT_GREY_THRESHOLD   = 0.50   # >50% near-white/near-black → grey/ui reject

# GPS gives a small confidence boost (not a bypass)
GPS_CONFIDENCE_BOOST      = 0.10

# ── Indoor scene detection thresholds ─────────────────────────────────────
# Dark interior / nighttime (windowsill pots, dark rooms)
INDOOR_DARK_THRESHOLD     = 0.10   # >10% near-black pixels
INDOOR_DARK_BLUE_MAX      = 0.003  # essentially no sky signal
INDOOR_DARK_GREEN_MAX     = 0.20   # plant must be substantially present to override

# Artificially lit interior (greenhouse, grow lights, bright indoor)
INDOOR_BRIGHT_THRESHOLD   = 0.10   # >10% blown-out-bright (overhead artificial light)
INDOOR_BRIGHT_GREY_MIN    = 0.20   # >20% neutral grey (artificial structures, pots, shelving)
INDOOR_BRIGHT_BLUE_MAX    = 0.005  # no real sky visible
INDOOR_BRIGHT_GREEN_MAX   = 0.32   # plant must strongly dominate to override


def _is_screenshot_filename(path: Path) -> bool:
    """Return True if the filename strongly suggests this is a screenshot."""
    name_lower = path.name.lower()
    for marker in _SCREENSHOT_FILENAME_MARKERS:
        if marker in name_lower:
            return True
    return False


def _analyse_pixels(img: "Image.Image") -> dict:
    """
    Sample a 100×100 thumbnail and compute colour ratios.

    Returns dict:
      green_ratio       — vegetation greens + 0.5× earthy browns
      ui_ratio          — very bright + very dark (UI/blank)
      dominant_grey     — majority grey/white + no green
      skin_ratio        — skin-tone pixels (person or animal)
      warm_ratio        — saturated warm reds/oranges (food, objects)
      blue_ratio        — sky/water blues
      very_dark_ratio   — near-black pixels (dark interior, night scenes)
      very_bright_ratio — blown-out-bright pixels (artificial overhead lighting)
      neutral_grey_ratio — true neutral grey pixels (artificial structures, vehicles)
    """
    from PIL import Image
    thumb = img.resize(_ANALYSIS_SIZE, Image.NEAREST).convert("RGB")
    pixels = list(thumb.getdata())
    total = len(pixels)

    green_score  = 0.0
    very_bright  = 0
    very_dark    = 0
    neutral_grey = 0
    skin_score   = 0
    warm_score   = 0
    blue_score   = 0

    for r, g, b in pixels:
        h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)

        # ── Vegetation greens ──────────────────────────────────────────
        if _GREEN_HUE_MIN <= h <= _GREEN_HUE_MAX and s > 0.12 and v > 0.08:
            green_score += 1.0

        # ── Earthy browns (bark, soil, dried stems) ────────────────────
        is_skin_like = (h <= _SKIN_HUE_A_MAX) and (s > 0.20) and (v > 0.30)
        if _BROWN_HUE_MIN <= h <= _BROWN_HUE_MAX and s > 0.15 and 0.15 < v < 0.85:
            if not is_skin_like:
                green_score += 0.5

        # ── Pure white/near-white (UI, paper, blank; artificial overhead light) ──
        if v > 0.92 and s < 0.10:
            very_bright += 1

        # ── Near-black (dark room, night scene) ────────────────────────
        if v < 0.06:
            very_dark += 1

        # ── True neutral grey (artificial structures, cars, shelving) ──
        # Distinct from earthy/brownish grey of dead leaves or bark.
        if s < 0.12 and 0.15 < v < 0.80:
            neutral_grey += 1

        # ── Skin tones (human + animal) ────────────────────────────────
        is_skin_hue = (h <= _SKIN_HUE_A_MAX or h >= _SKIN_HUE_B_MIN)
        if is_skin_hue and 0.15 <= s <= 0.85 and 0.30 <= v <= 0.95:
            skin_score += 1

        # ── Warm saturated (food, cooked dishes, fire, red objects) ────
        if h <= _WARM_HUE_MAX and s > 0.45 and v > 0.30:
            warm_score += 1

        # ── Sky/water blue ─────────────────────────────────────────────
        if _BLUE_HUE_MIN <= h <= _BLUE_HUE_MAX and s > 0.25 and v > 0.35:
            blue_score += 1

    ui_ratio          = (very_bright + very_dark) / total
    green_ratio       = green_score   / total
    skin_ratio        = skin_score    / total
    warm_ratio        = warm_score    / total
    blue_ratio        = blue_score    / total
    very_dark_ratio   = very_dark     / total
    very_bright_ratio = very_bright   / total
    neutral_grey_ratio = neutral_grey / total

    return {
        "green_ratio":        green_ratio,
        "ui_ratio":           ui_ratio,
        "dominant_grey":      ui_ratio > DOMINANT_GREY_THRESHOLD and green_ratio < 0.04,
        "skin_ratio":         skin_ratio,
        "warm_ratio":         warm_ratio,
        "blue_ratio":         blue_ratio,
        "very_dark_ratio":    very_dark_ratio,
        "very_bright_ratio":  very_bright_ratio,
        "neutral_grey_ratio": neutral_grey_ratio,
    }


def classify_plant_likelihood(
    image_path: Path,
    has_gps: bool = False,
    green_threshold_override: Optional[float] = None,
) -> Tuple[bool, float, str]:
    """
    Return (is_plant_likely: bool, confidence: float, category: str).

    category is one of:
      'plant'          — accepted as likely plant
      'screenshot'     — filename or resolution indicates screenshot
      'ui_blank'       — grey/white/blank image (UI, document, solid colour)
      'person_animal'  — dominant skin tones, no plant signal
      'food_warm'      — dominant warm/food colours, no plant signal
      'sky_blue'       — dominant sky-blue, no plant signal
      'indoor_dark'    — dark interior or nighttime scene (windowsill pots, dark rooms)
      'indoor_bright'  — artificially lit interior (greenhouse, grow lights)
      'no_plant_signal'— no positive plant evidence (default reject)

    Raises no exceptions — returns (True, 0.5, 'plant') if image cannot be read
    so we don't accidentally skip files due to read errors.
    """
    # ── 0. Filename-based screenshot detection ────────────────────────────
    # Fast path: no pixel analysis needed for known-screenshot filenames.
    if _is_screenshot_filename(image_path):
        return False, 0.02, "screenshot"

    try:
        from PIL import Image
        img = Image.open(image_path)
        w, h = img.size
        analysis = _analyse_pixels(img)
        img.close()
    except Exception:
        # Can't read image → don't skip, let PlantNet decide
        return True, 0.5, "plant"

    # Read live thresholds from settings service (falls back to module constants)
    try:
        from app.services.settings_service import get_setting as _gs
        # green_threshold_override allows callers (e.g. Pipeline 2) to apply
        # a tighter threshold without changing the global setting.
        _green_thr      = green_threshold_override if green_threshold_override is not None else _gs("prefilter_green_threshold")
        _green_thr_gps  = green_threshold_override if green_threshold_override is not None else _gs("prefilter_green_threshold_gps")
        _skin_thr       = _gs("prefilter_skin_threshold")
        _warm_thr       = _gs("prefilter_warm_threshold")
        _blue_thr       = _gs("prefilter_blue_threshold")
        _indoor_dark    = _gs("prefilter_indoor_dark_threshold")
        _indoor_bright  = _gs("prefilter_indoor_bright_threshold")
    except Exception:
        _green_thr      = PLANT_GREEN_THRESHOLD
        _green_thr_gps  = PLANT_GREEN_THRESHOLD_GPS
        _skin_thr       = SKIN_REJECT_THRESHOLD
        _warm_thr       = WARM_REJECT_THRESHOLD
        _blue_thr       = BLUE_REJECT_THRESHOLD
        _indoor_dark    = INDOOR_DARK_THRESHOLD
        _indoor_bright  = INDOOR_BRIGHT_THRESHOLD

    green_ratio       = analysis["green_ratio"]
    ui_ratio          = analysis["ui_ratio"]
    skin_ratio        = analysis["skin_ratio"]
    warm_ratio        = analysis["warm_ratio"]
    blue_ratio        = analysis["blue_ratio"]
    very_dark_ratio   = analysis["very_dark_ratio"]
    very_bright_ratio = analysis["very_bright_ratio"]
    grey_ratio        = analysis["neutral_grey_ratio"]

    # ── 1. Resolution-based screenshot detection (all formats) ────────────
    # Previously PNG-only. Now applies to JPEG screenshots and any format.
    if (w, h) in _SCREEN_RESOLUTIONS and green_ratio < 0.04:
        return False, 0.05, "screenshot"

    # ── 2. Blank / grey / UI images ────────────────────────────────────────
    if analysis["dominant_grey"] and green_ratio < 0.03:
        return False, 0.05, "ui_blank"
    if ui_ratio > UI_RATIO_THRESHOLD and green_ratio < 0.04:
        return False, 0.05, "ui_blank"

    # ── 3. Person / animal (skin-dominant + no plant signal) ──────────────
    if skin_ratio > _skin_thr and green_ratio < 0.10:
        return False, 0.05, "person_animal"

    # ── 4. Food / warm objects (no plant signal) ───────────────────────────
    if warm_ratio > _warm_thr and green_ratio < 0.04:
        return False, 0.05, "food_warm"

    # ── 5. Sky / water (blue-dominant, no plants) ─────────────────────────
    if blue_ratio > _blue_thr and green_ratio < 0.05:
        return False, 0.05, "sky_blue"

    # ── 5b. Dark interior / nighttime scene ───────────────────────────────
    # Significant near-black pixels + essentially no sky + limited green →
    # dark room, windowsill at night, underground scene.
    # Outdoor dark forest floor typically has >20% green and/or some sky blue.
    if (very_dark_ratio > _indoor_dark
            and blue_ratio < INDOOR_DARK_BLUE_MAX
            and green_ratio < INDOOR_DARK_GREEN_MAX):
        return False, 0.05, "indoor_dark"

    # ── 5c. Artificially lit interior (greenhouse, grow lights) ───────────
    # Blown-out white from overhead artificial lighting + significant neutral
    # grey (structures, pots, shelving) + no sky + limited green signal.
    # Outdoor dappled sunlight differs: still has some sky blue and more green.
    if (very_bright_ratio > _indoor_bright
            and grey_ratio > INDOOR_BRIGHT_GREY_MIN
            and blue_ratio < INDOOR_BRIGHT_BLUE_MAX
            and green_ratio < INDOOR_BRIGHT_GREEN_MAX):
        return False, 0.05, "indoor_bright"

    # ── 6. Positive plant signal ───────────────────────────────────────────
    threshold = _green_thr_gps if has_gps else _green_thr
    if green_ratio >= threshold:
        conf = min(0.90, 0.30 + green_ratio * 3)
        if has_gps:
            conf = min(0.90, conf + GPS_CONFIDENCE_BOOST)
        return True, round(conf, 3), "plant"

    # ── 7. Default: REJECT ─────────────────────────────────────────────────
    # Ambiguous = not a plant. Require positive evidence.
    return False, round(max(0.02, green_ratio), 3), "no_plant_signal"


# ---------------------------------------------------------------------------
# Batch runner
# ---------------------------------------------------------------------------

async def run_prefilter_batch(
    session: AsyncSession,
    batch_size: int = 100,
    reprocess: bool = False,
    progress_callback=None,
) -> dict:
    """
    Classify all un-filtered observations.

    Args:
        reprocess: Re-run on observations that already have is_plant_likely set.
    Returns summary dict.
    """
    stmt = select(Observation).where(Observation.is_duplicate.is_(False))
    if not reprocess:
        stmt = stmt.where(Observation.is_plant_likely.is_(None))
    else:
        # Safety: never reclassify images that have already been successfully
        # identified or manually reviewed — only re-run on unidentified images.
        stmt = stmt.where(
            Observation.identification_status.not_in(["identified"])
        ).where(
            Observation.review_status.not_in(["approved", "manually_verified"])
        )

    rows = (await session.execute(stmt)).scalars().all()
    total = len(rows)
    likely = unlikely = failed = 0
    categories: dict = {}
    rejected_obs = []

    for i, obs in enumerate(rows):
        start = time.monotonic()
        try:
            is_plant, confidence, category = classify_plant_likelihood(
                Path(obs.file_path),
                has_gps=(obs.latitude is not None),
            )
            obs.is_plant_likely = is_plant
            obs.plant_detect_confidence = confidence
            obs.prefilter_category = category

            if not is_plant:
                obs.identification_status = "not_plant"
                obs.review_status = "rejected"
                rejected_obs.append(obs)
                categories[category] = categories.get(category, 0) + 1

            if is_plant:
                likely += 1
            else:
                unlikely += 1

            session.add(ProcessingLog(
                observation_id=obs.id,
                stage="prefilter",
                status="success",
                message=f"plant_likely={is_plant} conf={confidence:.3f} category={category}",
                duration_ms=int((time.monotonic() - start) * 1000),
            ))

        except Exception as exc:
            failed += 1
            session.add(ProcessingLog(
                observation_id=obs.id,
                stage="prefilter",
                status="failed",
                message=str(exc),
            ))

        if (i + 1) % batch_size == 0:
            await session.commit()

        if progress_callback:
            progress_callback(i + 1, total)

    await session.commit()

    for obs in rejected_obs:
        try:
            delete_observation_file(obs)
        except Exception as _exc:
            _pf_log.warning("prefilter obs %d: file cleanup failed: %s", obs.id, _exc)

    return {
        "total": total,
        "plant_likely": likely,
        "not_plant": unlikely,
        "failed": failed,
        "categories": categories,
    }


async def refilter_failed_observations(
    session: AsyncSession,
    dry_run: bool = False,
) -> dict:
    """
    Re-run the (tightened) prefilter against all failed_identification observations.

    For each failed observation:
      - Classify with the current prefilter
      - If not plant-likely: mark as not_plant / rejected (unless dry_run)
      - If plant-likely: leave as failed_identification (eligible for retry)

    Returns breakdown dict safe to show in the UI before triggering any retry.
    """
    stmt = (
        select(Observation)
        .where(Observation.identification_status == "failed_identification")
        .where(Observation.is_duplicate.is_(False))
        # Safety: never touch manually-reviewed or approved observations
        .where(Observation.review_status.not_in(["approved", "manually_verified"]))
    )
    rows = (await session.execute(stmt)).scalars().all()
    total = len(rows)

    plant_likely   = 0
    auto_rejected  = 0
    categories: dict = {}
    errors = 0
    rejected_obs = []

    for obs in rows:
        try:
            is_plant, confidence, category = classify_plant_likelihood(
                Path(obs.file_path),
                has_gps=(obs.latitude is not None),
            )
        except Exception:
            errors += 1
            plant_likely += 1
            continue

        if is_plant:
            plant_likely += 1
            if not dry_run:
                obs.is_plant_likely = True
                obs.plant_detect_confidence = confidence
                obs.prefilter_category = category
        else:
            auto_rejected += 1
            categories[category] = categories.get(category, 0) + 1
            if not dry_run:
                obs.is_plant_likely = False
                obs.plant_detect_confidence = confidence
                obs.prefilter_category = category
                obs.identification_status = "not_plant"
                obs.review_status = "rejected"
                rejected_obs.append(obs)
                session.add(ProcessingLog(
                    observation_id=obs.id,
                    stage="prefilter",
                    status="success",
                    message=f"Re-filter: auto-rejected cat={category} conf={confidence:.3f}",
                ))

    if not dry_run:
        await session.commit()
        for obs in rejected_obs:
            try:
                delete_observation_file(obs)
            except Exception as _exc:
                _pf_log.warning("refilter obs %d: file cleanup failed: %s", obs.id, _exc)

    return {
        "total_failed": total,
        "auto_rejected": auto_rejected,
        "plant_likely_to_retry": plant_likely,
        "read_errors": errors,
        "rejection_categories": categories,
        "dry_run": dry_run,
    }
