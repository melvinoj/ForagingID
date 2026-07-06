"""
timeline.py — Data layer for the Seasons/Species/Timeline UI.

Endpoints:
  GET /api/timeline/positions?lens=edibility  — all species positions + visibility windows
  GET /api/timeline/at?day=<doy>&lens=edibility — content for current scroll: photos + phenology
"""

import hashlib
import logging
import math
import struct
from collections import Counter, defaultdict
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.observation import Observation
from app.models.encounter import Encounter
from app.models.species import Species

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/timeline", tags=["timeline"])

# ── Lens registry ─────────────────────────────────────────────────────────
# Each lens maps species → centrality score 0-1.  Higher = biased toward
# vertical centre (y≈0.5); lower = toward edges.

LensFn = Callable[[dict], float]
_LENS_REGISTRY: Dict[str, LensFn] = {}


def register_lens(name: str, fn: LensFn):
    _LENS_REGISTRY[name] = fn


def _edibility_lens(sp: dict) -> float:
    status = (sp.get("edibility_status") or "").lower()
    if status == "edible":
        return 0.9
    if status == "caution":
        return 0.6
    if status in ("toxic", "inedible", "not_edible"):
        return 0.15
    return 0.4


register_lens("edibility", _edibility_lens)


def _get_lens(name: str) -> LensFn:
    return _LENS_REGISTRY.get(name, _edibility_lens)


# ── Deterministic Poisson-disk placement ──────────────────────────────────

YEAR_CONSTANT = 2026
POISSON_MIN_DIST_Y = 0.08
POISSON_ATTEMPTS = 60
X_JITTER = 0.12
# The canvas aspect ratio is ~12:1 (X is STOPS/3 ≈ 12 viewWidths, Y is 1 viewHeight).
# Scale X in the distance check so 1 unit of X ≈ 1 unit of Y in pixel space.
_ASPECT_RATIO = 12.0


def _det_hash(species_id: int, seed: int = YEAR_CONSTANT) -> float:
    h = hashlib.sha256(struct.pack("<II", species_id, seed)).digest()
    return struct.unpack("<Q", h[:8])[0] / (2**64)


def _det_hash2(species_id: int, seed: int = YEAR_CONSTANT) -> Tuple[float, float]:
    """Two independent deterministic hashes from one seed."""
    h = hashlib.sha256(struct.pack("<II", species_id, seed)).digest()
    a = struct.unpack("<Q", h[:8])[0] / (2**64)
    b = struct.unpack("<Q", h[8:16])[0] / (2**64)
    return a, b


def _poisson_place(
    species_list: List[dict],
    lens_fn: LensFn,
) -> Dict[int, Tuple[float, float]]:
    """Assign (x, y) to each species with 2D Poisson disk placement.

    x is anchored to peak day-of-year with bounded horizontal jitter so
    co-peaking species spread into a cloud across roughly the middle third.
    y spans full height, biased toward 0.5 by lens centrality score.
    """
    placed: Dict[int, Tuple[float, float]] = {}
    occupied: List[Tuple[float, float]] = []

    for sp in species_list:
        sid = sp["species_id"]
        x_anchor = sp["peak_doy"] / 366.0
        centrality = lens_fn(sp)

        best = None
        best_dist = -1.0
        fallback = None
        fallback_dist = -1.0
        for attempt in range(POISSON_ATTEMPTS):
            hx, hy = _det_hash2(sid, YEAR_CONSTANT + attempt)
            x_jitter = (hx - 0.5) * 2 * X_JITTER
            x = max(0.02, min(0.98, x_anchor + x_jitter))
            raw_y = hy
            y = 0.5 + (raw_y - 0.5) * (1.0 - centrality * 0.5)
            y = max(0.14, min(0.86, y))

            ok = True
            min_d = float("inf")
            for ox, oy in occupied:
                dx_scaled = (x - ox) * _ASPECT_RATIO
                d = math.sqrt(dx_scaled ** 2 + (y - oy) ** 2)
                if d < POISSON_MIN_DIST_Y:
                    ok = False
                min_d = min(min_d, d)

            if ok and min_d > best_dist:
                best = (x, y)
                best_dist = min_d
            elif not ok and min_d > fallback_dist:
                fallback = (x, y)
                fallback_dist = min_d

        if best is None:
            best = fallback or (
                max(0.02, min(0.98, x_anchor + (_det_hash(sid) - 0.5) * 2 * X_JITTER)),
                max(0.14, min(0.86, _det_hash(sid + 1000))),
            )

        placed[sid] = best
        occupied.append(best)

    return placed


# ── Sighting density analysis ─────────────────────────────────────────────

def _analyse_sightings(doys: List[int]) -> Tuple[int, int, int]:
    """From a list of day-of-year values, find peak bin and visible window.

    Returns (peak_doy, visible_from_doy, visible_to_doy).
    Uses 10-day bins. Peak = mode bin centre. Window = bins with ≥20% of peak count.
    """
    if not doys:
        return (183, 1, 366)

    bin_size = 10
    bins: Counter = Counter()
    for d in doys:
        bins[d // bin_size] += 1

    peak_bin = bins.most_common(1)[0][0]
    peak_count = bins[peak_bin]
    threshold = max(1, peak_count * 0.2)

    active_bins = sorted(b for b, c in bins.items() if c >= threshold)
    vis_from = active_bins[0] * bin_size + 1
    vis_to = min(366, (active_bins[-1] + 1) * bin_size)
    peak_doy = peak_bin * bin_size + bin_size // 2

    return (peak_doy, vis_from, vis_to)


def _photo_date_doy(taken_at, created_at) -> Optional[int]:
    dt = taken_at or created_at
    if dt is None:
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except ValueError:
            return None
    return dt.timetuple().tm_yday


# ── Phenology parsing ─────────────────────────────────────────────────────

def _parse_month_csv(val: Optional[str]) -> List[int]:
    if not val:
        return []
    out = []
    for part in val.split(","):
        part = part.strip()
        if part.isdigit():
            m = int(part)
            if 1 <= m <= 12:
                out.append(m)
    return sorted(set(out))


def _phenology_arcs(flower: Optional[str], fruit: Optional[str], leaf: Optional[str]) -> Optional[dict]:
    f = _parse_month_csv(flower)
    fr = _parse_month_csv(fruit)
    lf = _parse_month_csv(leaf)
    if not f and not fr and not lf:
        return None
    return {
        "flower_months": f or None,
        "fruit_months": fr or None,
        "leaf_months": lf or None,
    }


# ── ENDPOINT A — positions ────────────────────────────────────────────────

@router.get("/positions")
async def timeline_positions(
    lens: str = Query("edibility"),
    db: AsyncSession = Depends(get_db),
):
    lens_fn = _get_lens(lens)

    # Fetch all approved observations with dates, grouped by species
    rows = (await db.execute(
        select(
            Observation.species_id,
            Observation.photo_taken_at,
            Observation.created_at,
        ).where(
            Observation.species_id.isnot(None),
            Observation.review_status.in_(["approved", "manually_verified"]),
        )
    )).all()

    species_doys: Dict[int, List[int]] = defaultdict(list)
    for sid, taken_at, created_at in rows:
        doy = _photo_date_doy(taken_at, created_at)
        if doy is not None:
            species_doys[sid].append(doy)

    # Also include species from encounters
    enc_rows = (await db.execute(
        select(Encounter.species_id, Encounter.encounter_date).where(
            Encounter.species_id.isnot(None),
        )
    )).all()
    for sid, enc_date in enc_rows:
        doy = _photo_date_doy(enc_date, None)
        if doy is not None:
            species_doys[sid].append(doy)

    if not species_doys:
        return {"positions": [], "lens": lens}

    # Fetch species metadata
    sp_rows = (await db.execute(
        select(
            Species.id, Species.scientific_name, Species.edibility_status,
            Species.preferred_common_name, Species.common_names,
            Species.flower_months, Species.fruit_months, Species.leaf_months,
        ).where(Species.id.in_(list(species_doys.keys())))
    )).all()

    sp_map = {}
    for sid, sci, edib, pref, common, flower, fruit, leaf in sp_rows:
        common_list = []
        if common:
            import json
            try:
                common_list = json.loads(common)
            except Exception:
                pass
        display = pref or (common_list[0] if common_list else sci)
        sp_map[sid] = {
            "species_id": sid,
            "scientific_name": sci,
            "display_name": display,
            "edibility_status": edib,
            "flower_months": flower,
            "fruit_months": fruit,
            "leaf_months": leaf,
        }

    # Analyse sighting density per species
    species_list = []
    for sid, doys in species_doys.items():
        if sid not in sp_map:
            continue
        peak, vis_from, vis_to = _analyse_sightings(doys)
        entry = {**sp_map[sid], "peak_doy": peak, "sighting_count": len(doys)}
        species_list.append(entry)

    # Sort by lens score (highest first) then sighting count, then species_id for stability
    species_list.sort(key=lambda s: (-lens_fn(s), -s["sighting_count"], s["species_id"]))

    # Poisson placement
    positions = _poisson_place(species_list, lens_fn)

    result = []
    for sp in species_list:
        sid = sp["species_id"]
        peak, vis_from, vis_to = _analyse_sightings(species_doys[sid])
        x, y = positions.get(sid, (0.5, 0.5))
        result.append({
            "species_id": sid,
            "name": sp["scientific_name"],
            "display_name": sp["display_name"],
            "edibility_status": sp["edibility_status"],
            "home": {"x": round(x, 4), "y": round(y, 4)},
            "visible_from": vis_from,
            "visible_to": vis_to,
            "peak_doy": peak,
            "sighting_count": sp["sighting_count"],
            "centrality": round(lens_fn(sp), 2),
            "flower_months": sp.get("flower_months"),
            "fruit_months": sp.get("fruit_months"),
            "leaf_months": sp.get("leaf_months"),
        })

    return {"positions": result, "lens": lens}


# ── ENDPOINT B — content at scroll position ───────────────────────────────

@router.get("/at")
async def timeline_at(
    day: int = Query(..., ge=1, le=366),
    lens: str = Query("edibility"),
    db: AsyncSession = Depends(get_db),
):
    lens_fn = _get_lens(lens)

    # Re-derive positions (cached in production; fine for now)
    pos_resp = await timeline_positions(lens=lens, db=db)
    all_positions = pos_resp["positions"]

    # Filter to species visible at this day
    visible = [
        p for p in all_positions
        if _is_visible(p["visible_from"], p["visible_to"], day)
    ]

    # Sort by centrality then sighting count, stable tiebreak
    visible.sort(key=lambda p: (-p["centrality"], -p["sighting_count"], p["species_id"]))

    # Bulk-fetch species rows for phenology
    sp_ids = [sp["species_id"] for sp in visible]
    sp_rows_list = (await db.execute(
        select(Species).where(Species.id.in_(sp_ids))
    )).scalars().all()
    sp_row_map = {s.id: s for s in sp_rows_list}

    # Bulk-fetch sighting DOYs for species without phenology (density markers)
    obs_doy_rows = (await db.execute(
        select(Observation.species_id, Observation.photo_taken_at, Observation.created_at).where(
            Observation.species_id.in_(sp_ids),
            Observation.review_status.in_(["approved", "manually_verified"]),
        )
    )).all()
    species_sighting_doys: Dict[int, List[int]] = defaultdict(list)
    for sid, taken_at, created_at in obs_doy_rows:
        doy = _photo_date_doy(taken_at, created_at)
        if doy is not None:
            species_sighting_doys[sid].append(doy)

    # Also include encounter dates in sighting DOYs
    enc_doy_rows = (await db.execute(
        select(Encounter.species_id, Encounter.encounter_date).where(
            Encounter.species_id.in_(sp_ids),
        )
    )).all()
    for sid, enc_date in enc_doy_rows:
        doy = _photo_date_doy(enc_date, None)
        if doy is not None:
            species_sighting_doys[sid].append(doy)

    # Bulk-fetch encounter photos for zoom view (all encounters per species)
    enc_rows = (await db.execute(
        select(
            Encounter.id, Encounter.species_id, Encounter.encounter_date,
            Encounter.text_note, Encounter.location_name,
        ).where(
            Encounter.species_id.in_(sp_ids),
        ).order_by(Encounter.encounter_date.desc())
    )).all()

    from app.models.encounter import EncounterPhoto
    enc_ids = [e.id for e in enc_rows]
    enc_photo_rows = []
    if enc_ids:
        enc_photo_rows = (await db.execute(
            select(EncounterPhoto.encounter_id, Observation.thumbnail_path).join(
                Observation, EncounterPhoto.observation_id == Observation.id
            ).where(
                EncounterPhoto.encounter_id.in_(enc_ids),
                Observation.thumbnail_path.isnot(None),
            )
        )).all()
    enc_thumbs: Dict[int, str] = {}
    for eid, tpath in enc_photo_rows:
        if eid not in enc_thumbs and tpath:
            enc_thumbs[eid] = "/thumbnails/" + tpath.rsplit("/", 1)[-1]

    species_encounters: Dict[int, list] = defaultdict(list)
    for enc in enc_rows:
        enc_doy = _photo_date_doy(enc.encounter_date, None)
        entry = {
            "encounter_id": enc.id,
            "doy": enc_doy,
            "date": enc.encounter_date.isoformat() if enc.encounter_date else None,
            "location": enc.location_name,
            "has_photo": enc.id in enc_thumbs,
        }
        if enc.id in enc_thumbs:
            entry["thumbnail"] = enc_thumbs[enc.id]
        elif enc.text_note:
            entry["text_note"] = enc.text_note[:120]
        species_encounters[enc.species_id].append(entry)

    results = []
    for sp in visible:
        sid = sp["species_id"]
        photo = await _nearest_photo(db, sid, day)

        sp_row = sp_row_map.get(sid)
        phenology = None
        sighting_doys = None
        if sp_row:
            phenology = _phenology_arcs(sp_row.flower_months, sp_row.fruit_months, sp_row.leaf_months)
        if not phenology:
            sighting_doys = sorted(set(species_sighting_doys.get(sid, [])))

        results.append({
            "species_id": sid,
            "name": sp["name"],
            "display_name": sp["display_name"],
            "edibility_status": sp["edibility_status"],
            "home": sp["home"],
            "thumbnail": photo,
            "phenology": phenology,
            "sighting_doys": sighting_doys,
            "encounters": species_encounters.get(sid, []),
        })

    return {"day": day, "species": results, "lens": lens}


def _is_visible(vis_from: int, vis_to: int, day: int) -> bool:
    if vis_from <= vis_to:
        return vis_from <= day <= vis_to
    return day >= vis_from or day <= vis_to


async def _nearest_photo(db: AsyncSession, species_id: int, target_doy: int) -> Optional[str]:
    """Find the approved observation whose photo_taken_at day-of-year is closest to target_doy."""
    rows = (await db.execute(
        select(Observation.thumbnail_path, Observation.photo_taken_at, Observation.created_at).where(
            Observation.species_id == species_id,
            Observation.review_status.in_(["approved", "manually_verified"]),
            Observation.thumbnail_path.isnot(None),
        ).order_by(Observation.photo_taken_at.desc().nullslast())
        .limit(50)
    )).all()

    if not rows:
        return None

    best_thumb = None
    best_diff = 367
    for thumb_path, taken_at, created_at in rows:
        doy = _photo_date_doy(taken_at, created_at)
        if doy is None:
            continue
        diff = min(abs(doy - target_doy), 366 - abs(doy - target_doy))
        if diff < best_diff:
            best_diff = diff
            best_thumb = thumb_path

    if best_thumb:
        return "/thumbnails/" + best_thumb.rsplit("/", 1)[-1]
    return None
