"""
Phenology helpers — Phase 10.6 Section 5.

Central place for all "is this species in season?" logic.

Fallback contract:
  1. If a species has any phenological months set (flower/fruit/leaf), use those.
  2. Otherwise fall back to the photo_taken_at month proxy (±1 window).

This ensures the existing Near me behaviour is NEVER broken — the fallback
is identical to the old _in_season() in nearby.py.
"""
from typing import Optional


# ---------------------------------------------------------------------------
# Month parsing
# ---------------------------------------------------------------------------

def parse_months(csv: Optional[str]) -> set[int]:
    """Parse a comma-separated month string ("3,4,5,6") into a set of ints.
    Returns an empty set for NULL / blank / invalid values.
    """
    if not csv:
        return set()
    result = set()
    for part in csv.split(","):
        part = part.strip()
        if part.isdigit():
            m = int(part)
            if 1 <= m <= 12:
                result.add(m)
    return result


def months_to_csv(months: list[int]) -> Optional[str]:
    """Convert a list of month ints to a sorted CSV string, or None if empty."""
    valid = sorted({m for m in months if 1 <= m <= 12})
    return ",".join(str(m) for m in valid) if valid else None


# peak_season is a free-text note (e.g. "Best harvested April–May before
# flowering"), not a month CSV. parse_peak_season_months does a best-effort
# extraction of English month names/abbreviations so the "In season now"
# filters can honour peak_season as the prompt specifies, without breaking the
# canonical flower/fruit/leaf month logic used everywhere else.
_MONTH_LOOKUP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def parse_peak_season_months(text: Optional[str]) -> set[int]:
    """Best-effort: pull month numbers out of a free-text peak_season note.
    Matches whole English month names / abbreviations (case-insensitive).
    Returns an empty set when nothing recognisable is present."""
    if not text:
        return set()
    import re
    found = set()
    for word in re.findall(r"[a-zA-Z]+", text):
        m = _MONTH_LOOKUP.get(word.lower())
        if m:
            found.add(m)
    return found


def in_season_now(
    *,
    flower_months: Optional[str],
    fruit_months: Optional[str],
    leaf_months: Optional[str],
    peak_season: Optional[str],
    ref_month: int,
) -> tuple[bool, bool]:
    """Phenology-only "is this species in season this month?" used by the
    "In season now" filters on the species page and the map.

    Unlike species_in_season(), there is NO photo-month fallback: species with
    no phenology data at all are reported as has_phenology=False so the filter
    can exclude them when active (per the prompt spec).

    Considers flower/fruit/leaf month CSVs plus best-effort month names parsed
    from the free-text peak_season note.

    Returns (in_season, has_phenology).
    """
    months = (
        parse_months(flower_months)
        | parse_months(fruit_months)
        | parse_months(leaf_months)
        | parse_peak_season_months(peak_season)
    )
    if not months:
        return (False, False)
    return (ref_month in months, True)


# ---------------------------------------------------------------------------
# In-season check
# ---------------------------------------------------------------------------

def species_in_season(
    *,
    flower_months: Optional[str],
    fruit_months: Optional[str],
    leaf_months: Optional[str],
    ref_month: int,
    # Fallback params — used when no phenological data available
    photo_month: Optional[int] = None,
) -> bool:
    """
    Return True if the species is active / harvestable in ref_month.

    Priority:
      1. If ANY of flower/fruit/leaf months is set: return True iff ref_month
         appears in the union of all set month lists.
      2. Otherwise (all NULL): fall back to ±1 photo-month proxy.
    """
    flower = parse_months(flower_months)
    fruit  = parse_months(fruit_months)
    leaf   = parse_months(leaf_months)

    all_months = flower | fruit | leaf

    if all_months:
        return ref_month in all_months

    # Fallback: photo month proxy (original behaviour — ±1 window, Dec/Jan wrap)
    return _photo_month_proxy(photo_month, ref_month)


def _photo_month_proxy(photo_month: Optional[int], ref_month: int) -> bool:
    """±1 month window with December↔January wrap-around. Identical to the
    original _in_season() in nearby.py."""
    if not photo_month:
        return False
    return any(((ref_month - 1 + d) % 12) + 1 == photo_month for d in (-1, 0, 1))


# ---------------------------------------------------------------------------
# Convenience: list of active months for display
# ---------------------------------------------------------------------------

_MONTH_NAMES = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def active_months_display(
    flower_months: Optional[str],
    fruit_months: Optional[str],
    leaf_months: Optional[str],
) -> dict:
    """
    Return a display dict suitable for the species card / Find tab:
    {
        "flower": [3, 4, 5],           # int list
        "fruit":  [8, 9, 10],
        "leaf":   [3, 4, 5, 6],
        "flower_label": "Mar · Apr · May",
        "fruit_label":  "Aug · Sep · Oct",
        "leaf_label":   "Mar · Apr · May · Jun",
        "any_set": True,
    }
    """
    flower = sorted(parse_months(flower_months))
    fruit  = sorted(parse_months(fruit_months))
    leaf   = sorted(parse_months(leaf_months))

    def label(months: list[int]) -> str:
        return " · ".join(_MONTH_NAMES[m] for m in months) if months else ""

    return {
        "flower":        flower,
        "fruit":         fruit,
        "leaf":          leaf,
        "flower_label":  label(flower),
        "fruit_label":   label(fruit),
        "leaf_label":    label(leaf),
        "any_set":       bool(flower or fruit or leaf),
    }
