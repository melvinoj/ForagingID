"""
Seasonal return notifications — Phase 11b.

Computes "returning species": species the user has confirmed before (via approved
observations or recorded encounters) that are now entering their season. Two
triggers, combined:

  1. Phenology  — where flower/fruit/leaf months are set, fire when the current
     month is in (or, with the lead window, about to enter) one of those windows.
  2. Anniversary — where phenology is blank, fall back to the calendar anniversary
     of the last sighting ("you found this around now last year").

Notifications are in-app only (no browser push), deduped per species per season
via notification_dismissals (season_key).
"""

import json
import logging
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.encounter import Encounter
from app.models.notification import NotificationDismissal
from app.models.observation import Observation
from app.models.species import Species
from app.services.phenology import parse_months

log = logging.getLogger(__name__)

DEFAULT_LEAD_DAYS = 14

# Confirmed = a sighting the user stands behind.
_CONFIRMED_STATUSES = ("approved", "manually_verified")

# Priority order when a month falls in more than one window — fruit is the most
# foraging-actionable, then flower, then leaf.
_CATEGORY_LABEL = {"fruit": "Fruiting", "flower": "Flowering", "leaf": "Leafing"}
_CATEGORY_ORDER = ("fruit", "flower", "leaf")


def _obs_date(photo_taken_at, created_at) -> Optional[datetime]:
    return photo_taken_at or created_at


def _to_date(dt) -> Optional[date]:
    if dt is None:
        return None
    return dt.date() if isinstance(dt, datetime) else dt


def _anniversary(last: date, year: int) -> date:
    """Anniversary of `last` in `year`, guarding Feb 29 on non-leap years."""
    day = last.day
    if last.month == 2 and day == 29:
        try:
            return date(year, 2, 29)
        except ValueError:
            return date(year, 2, 28)
    return date(year, last.month, day)


def _first_common_name(common_names_json: Optional[str]) -> Optional[str]:
    if not common_names_json:
        return None
    try:
        arr = json.loads(common_names_json)
        if isinstance(arr, list) and arr:
            return str(arr[0])
    except (ValueError, TypeError):
        pass
    return None


def _classify(sp: Species, last_seen: date, today: date, lead_days: int) -> Optional[dict]:
    """Return {basis, category, timing, reason, season_key} or None if not returning."""
    ref_month = today.month
    lead_month = (today + timedelta(days=lead_days)).month
    year = today.year

    windows = {
        "fruit":  parse_months(sp.fruit_months),
        "flower": parse_months(sp.flower_months),
        "leaf":   parse_months(sp.leaf_months),
    }
    any_phen = any(windows.values())

    if any_phen:
        # In season now — any window containing the current month.
        for cat in _CATEGORY_ORDER:
            if ref_month in windows[cat]:
                return {
                    "basis": "phenology", "category": cat, "timing": "now",
                    "reason": f"{_CATEGORY_LABEL[cat]} season now",
                    "season_key": f"{year}:{cat}",
                }
        # Starting soon — opens within the lead window and isn't already open.
        for cat in _CATEGORY_ORDER:
            if lead_month in windows[cat] and ref_month not in windows[cat]:
                return {
                    "basis": "phenology", "category": cat, "timing": "soon",
                    "reason": f"{_CATEGORY_LABEL[cat]} season starting soon",
                    "season_key": f"{year}:{cat}",
                }
        return None

    # Anniversary fallback — only a "return" if last seen in a previous year.
    if last_seen is None or last_seen.year >= year:
        return None
    anniv = _anniversary(last_seen, year)
    delta = (anniv - today).days
    if -lead_days <= delta <= lead_days:
        years_ago = year - last_seen.year
        when = "last year" if years_ago == 1 else f"{years_ago} years ago"
        return {
            "basis": "anniversary", "category": None,
            "timing": "soon" if delta > 0 else "now",
            "reason": f"You found this around now {when}",
            "season_key": f"{year}:anniversary",
        }
    return None


async def compute_seasonal_returns(
    session: AsyncSession,
    user_id: int = 1,
    lead_days: int = DEFAULT_LEAD_DAYS,
    today: Optional[date] = None,
) -> list[dict]:
    today = today or date.today()

    # ── Last sighting per species (latest wins) + total sighting count ──
    last_seen: dict[int, dict] = {}
    counts: dict[int, int] = {}

    obs_rows = await session.execute(
        select(
            Observation.species_id, Observation.photo_taken_at, Observation.created_at,
            Observation.latitude, Observation.longitude,
        ).where(
            Observation.species_id.isnot(None),
            Observation.review_status.in_(_CONFIRMED_STATUSES),
        )
    )
    for sid, taken, created, lat, lng in obs_rows.all():
        counts[sid] = counts.get(sid, 0) + 1
        d = _to_date(_obs_date(taken, created))
        if d is None:
            continue
        cur = last_seen.get(sid)
        if cur is None or d > cur["date"]:
            last_seen[sid] = {"date": d, "lat": lat, "lng": lng, "place": None}

    # ── …and from encounters (carry a place name where present) ──
    enc_rows = await session.execute(
        select(
            Encounter.species_id, Encounter.encounter_date,
            Encounter.latitude, Encounter.longitude, Encounter.location_name,
        ).where(Encounter.species_id.isnot(None))
    )
    for sid, edate, lat, lng, place in enc_rows.all():
        counts[sid] = counts.get(sid, 0) + 1
        d = _to_date(edate)
        if d is None:
            continue
        cur = last_seen.get(sid)
        if cur is None or d > cur["date"]:
            last_seen[sid] = {"date": d, "lat": lat, "lng": lng, "place": place or None}

    if not last_seen:
        return []

    # ── Species rows for the known set ──
    sp_rows = await session.execute(
        select(Species).where(Species.id.in_(list(last_seen.keys())))
    )
    species = {sp.id: sp for sp in sp_rows.scalars().all()}

    # ── Dismissed (species_id, season_key) for this user ──
    dis_rows = await session.execute(
        select(NotificationDismissal.species_id, NotificationDismissal.season_key)
        .where(NotificationDismissal.user_id == user_id)
    )
    dismissed = {(sid, key) for sid, key in dis_rows.all()}

    items: list[dict] = []
    for sid, seen in last_seen.items():
        sp = species.get(sid)
        if sp is None:
            continue
        verdict = _classify(sp, seen["date"], today, lead_days)
        if verdict is None:
            continue
        if (sid, verdict["season_key"]) in dismissed:
            continue
        items.append({
            "species_id":       sid,
            "scientific_name":  sp.scientific_name,
            "common_name":      _first_common_name(sp.common_names),
            "reason":           verdict["reason"],
            "basis":            verdict["basis"],
            "category":         verdict["category"],
            "timing":           verdict["timing"],
            "peak_season":      sp.peak_season,
            "season_key":       verdict["season_key"],
            "last_seen":        seen["date"].isoformat(),
            "last_seen_place":  seen["place"],
            "last_seen_lat":    seen["lat"],
            "last_seen_lng":    seen["lng"],
            "sighting_count":   counts.get(sid, 0),
        })

    # Ranking (priority order):
    #   1. in-season now before starting-soon
    #   2. most-recently-seen first
    #   3. most-encountered first
    # Single key: timing rank ascending, then last_seen + count descending.
    items.sort(key=lambda it: (
        0 if it["timing"] == "now" else 1,
        _neg_iso(it["last_seen"]),
        -it["sighting_count"],
    ))
    return items


def _neg_iso(iso: str) -> str:
    """A sort proxy that orders ISO dates DESCENDING under an ascending sort:
    invert each digit so newer dates compare 'smaller'. Keeps the sort stable and
    purely string-based (no date parsing in the hot path)."""
    return "".join(str(9 - int(ch)) if ch.isdigit() else ch for ch in iso)
