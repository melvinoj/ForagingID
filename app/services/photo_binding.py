"""
Photo → encounter binding resolvers.

Two resolvers, run fire-and-forget after each observation is persisted:

1. **Filename resolver** (deterministic, may auto-bind):
   Matches the observation's original camera filename against
   encounters.expected_filename within a ±24h window.
   Binding method: "own_named" if the filename starts with "encounter_",
   otherwise "filename".

2. **Proximity + time resolver** (probabilistic, candidates only):
   For encounters with no expected_filename and no bound photo, finds
   observations within PROXIMITY_RADIUS_M and PROXIMITY_TIME_WINDOW_S.
   Surfaces candidates — never auto-binds.

Both resolvers are non-blocking and non-fatal: errors are logged, never
raised. Ingest timing and success are unaffected.
"""

import logging
import math
import re
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.encounter import Encounter, EncounterPhoto
from app.models.observation import Observation

log = logging.getLogger(__name__)

# ── Config constants (tunable) ────────────────────────────────────────────
FILENAME_TIME_WINDOW_H = 24
PROXIMITY_RADIUS_M = 20
PROXIMITY_TIME_WINDOW_S = 300  # 5 minutes

# ── Filename normalisation ────────────────────────────────────────────────

_SYNCTHING_SUFFIX = re.compile(r" \(\d+\)$")


def _normalise_stem(filename: str) -> str:
    """Strip path, extension, Syncthing (N) suffix, and .MP Motion Photo marker."""
    from pathlib import Path
    stem = Path(filename).stem
    stem = stem.replace(".MP", "")
    stem = _SYNCTHING_SUFFIX.sub("", stem)
    return stem


def _extract_camera_name(file_path: str) -> str:
    """Extract original camera filename from a UUID-prefixed pipeline path."""
    basename = file_path.rsplit("/", 1)[-1]
    if len(basename) > 33 and basename[32] == "_":
        return basename[33:]
    return basename


# ── Filename resolver ─────────────────────────────────────────────────────

async def resolve_by_filename(obs_id: int) -> Optional[int]:
    """
    Check if the newly ingested observation matches any encounter's
    expected_filename. If so, auto-bind and return the encounter_id.
    Returns None if no match.
    """
    try:
        async with AsyncSessionLocal() as session:
            obs = await session.get(Observation, obs_id)
            if not obs or not obs.file_path:
                return None

            camera_name = _extract_camera_name(obs.file_path)
            obs_stem = _normalise_stem(camera_name)
            if not obs_stem:
                return None

            obs_time = obs.photo_taken_at or obs.created_at
            window_start = obs_time - timedelta(hours=FILENAME_TIME_WINDOW_H)
            window_end = obs_time + timedelta(hours=FILENAME_TIME_WINDOW_H)

            encounters = (await session.execute(
                select(Encounter).where(
                    Encounter.expected_filename.isnot(None),
                    Encounter.encounter_date.between(window_start, window_end),
                )
            )).scalars().all()

            for enc in encounters:
                enc_stem = _normalise_stem(enc.expected_filename)
                if enc_stem == obs_stem:
                    existing = await session.scalar(
                        select(EncounterPhoto.id).where(
                            EncounterPhoto.encounter_id == enc.id,
                            EncounterPhoto.observation_id == obs_id,
                        )
                    )
                    if existing:
                        log.info("[photo_binding] Already bound: enc=%d obs=%d", enc.id, obs_id)
                        return enc.id

                    method = "own_named" if (enc.expected_filename or "").startswith("encounter_") else "filename"
                    session.add(EncounterPhoto(
                        encounter_id=enc.id,
                        observation_id=obs_id,
                        binding_method=method,
                        binding_detail=f"matched={camera_name} expected={enc.expected_filename}",
                    ))
                    await session.commit()
                    log.info(
                        "[photo_binding] Filename bound: enc=%d obs=%d method=%s file=%s",
                        enc.id, obs_id, method, camera_name,
                    )
                    return enc.id

            return None
    except Exception as e:
        log.error("[photo_binding] Filename resolver error for obs %d: %s", obs_id, e)
        return None


# ── Proximity + time resolver ─────────────────────────────────────────────

def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in metres."""
    R = 6_371_000
    rlat1, rlat2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def resolve_by_proximity(obs_id: int) -> list:
    """
    Find encounters near the newly ingested observation in both space and time.
    Returns a list of candidate dicts (never auto-binds).
    """
    try:
        async with AsyncSessionLocal() as session:
            obs = await session.get(Observation, obs_id)
            if not obs or obs.latitude is None or obs.longitude is None:
                return []

            obs_time = obs.photo_taken_at or obs.created_at
            time_window = timedelta(seconds=PROXIMITY_TIME_WINDOW_S)
            window_start = obs_time - time_window
            window_end = obs_time + time_window

            lat_delta = PROXIMITY_RADIUS_M / 111320
            lon_delta = PROXIMITY_RADIUS_M / (111320 * math.cos(math.radians(obs.latitude)))

            encounters = (await session.execute(
                select(Encounter).where(
                    Encounter.latitude.isnot(None),
                    Encounter.longitude.isnot(None),
                    Encounter.encounter_date.between(window_start, window_end),
                    Encounter.latitude.between(obs.latitude - lat_delta, obs.latitude + lat_delta),
                    Encounter.longitude.between(obs.longitude - lon_delta, obs.longitude + lon_delta),
                )
            )).scalars().all()

            candidates = []
            for enc in encounters:
                already_bound = await session.scalar(
                    select(EncounterPhoto.id).where(
                        EncounterPhoto.encounter_id == enc.id,
                        EncounterPhoto.observation_id == obs_id,
                    )
                )
                if already_bound:
                    continue

                dist = _haversine_m(obs.latitude, obs.longitude, enc.latitude, enc.longitude)
                if dist <= PROXIMITY_RADIUS_M:
                    time_delta = abs((obs_time - enc.encounter_date).total_seconds())
                    candidates.append({
                        "encounter_id": enc.id,
                        "observation_id": obs_id,
                        "distance_m": round(dist, 1),
                        "time_delta_s": round(time_delta),
                    })
                    log.info(
                        "[photo_binding] Proximity candidate: enc=%d obs=%d dist=%.1fm dt=%ds",
                        enc.id, obs_id, dist, time_delta,
                    )

            return candidates
    except Exception as e:
        log.error("[photo_binding] Proximity resolver error for obs %d: %s", obs_id, e)
        return []


# ── Combined resolver (fire-and-forget after ingest) ──────────────────────

async def run_resolvers(obs_id: int) -> None:
    """Run both resolvers for a newly ingested observation. Non-fatal."""
    bound = await resolve_by_filename(obs_id)
    if bound:
        return
    await resolve_by_proximity(obs_id)


# ── Backfill: run resolvers over all GPS-tagged observations ──────────────

async def backfill_bindings() -> dict:
    """
    Run both resolvers retroactively over existing observations that have GPS
    and are not yet bound to any encounter. Returns stats.
    """
    stats = {"checked": 0, "filename_bound": 0, "proximity_candidates": 0}
    try:
        async with AsyncSessionLocal() as session:
            already_bound_obs = set(
                r[0] for r in (await session.execute(
                    select(EncounterPhoto.observation_id)
                )).fetchall()
            )

            obs_rows = (await session.execute(
                select(Observation.id).where(
                    Observation.latitude.isnot(None),
                    Observation.longitude.isnot(None),
                )
            )).scalars().all()

        for obs_id in obs_rows:
            if obs_id in already_bound_obs:
                continue
            stats["checked"] += 1
            bound = await resolve_by_filename(obs_id)
            if bound:
                stats["filename_bound"] += 1
                already_bound_obs.add(obs_id)
                continue
            candidates = await resolve_by_proximity(obs_id)
            stats["proximity_candidates"] += len(candidates)

    except Exception as e:
        log.error("[photo_binding] Backfill error: %s", e)
        stats["error"] = str(e)

    log.info("[photo_binding] Backfill complete: %s", stats)
    return stats
