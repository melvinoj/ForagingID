"""
walk_route.py — the saved walk LINE: which legs are drawn straight (dashed),
and reordering a saved walk without a new ORS route. The ONLY place these
rules live; pure Python, no DB access. Shared by app/api/walk.py (reorder
endpoint), scripts/experience_export/export.py and
scripts/walk_straighten_legs.py. Frontend mirror: _walkStraightRangesOf()
in frontend/index.html (same reading rule).

Straight legs are stored in route_geojson.foragingid as vertex ranges:

    straight_ranges: [[a, b], ...]   0 <= a < b <= n-1, the line from vertex a
                                     to vertex b is drawn dashed
    straight_from:   sf              legacy (walk 4, 18 Oct 2026) — the same as
                                     [[sf, n-1]]; read, never written again

Internally a line's dashes are one flag per segment (segment k joins vertex k
and k+1), so reversing / rotating / straightening moves each dash with its
physical leg.

Reordering never calls ORS and never changes distance_m / duration_min: the
same closed loop walked from another stop, or the other way round, is the same
length. Saved stop numbers are positions in waypoints_json, so they change;
"7a" labels are recomputed on read (walk_membership) against the new order.
"""
from __future__ import annotations

import copy
import math
from typing import Optional

CLOSED_LOOP_TOLERANCE_M = 30.0     # first/last vertex this close = closed loop
PASS_TOLERANCE_M        = 15.0     # stop_vertex_indices: earliest pass this close to the best


class RouteError(ValueError):
    """The saved line cannot support the requested change."""


def _hav(a, b) -> float:
    """Metres between two [lng, lat] points."""
    lng1, lat1, lng2, lat2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2)
    return 2 * 6371000.0 * math.asin(math.sqrt(h))


def line_length_m(coords: list) -> float:
    return sum(_hav(coords[i], coords[i + 1]) for i in range(len(coords) - 1))


def line_coords(route: dict) -> Optional[list]:
    """The first LineString's [lng, lat] coordinates, or None."""
    for f in (route or {}).get("features") or []:
        g = (f or {}).get("geometry") or {}
        if g.get("type") == "LineString" and len(g.get("coordinates") or []) >= 2:
            return g["coordinates"]
    return None


def is_closed(coords: list) -> bool:
    return bool(coords) and _hav(coords[0], coords[-1]) <= CLOSED_LOOP_TOLERANCE_M


# ── straight (dashed) legs ───────────────────────────────────────────────────

def straight_ranges(meta: dict, n: int) -> list:
    """Validated, merged dashed vertex ranges for a line of n vertices.
    Invalid entries are dropped (drawn solid) — the same leniency the map had
    for a bad straight_from."""
    meta = meta or {}
    raw = meta.get("straight_ranges")
    out = []
    if isinstance(raw, list):
        for r in raw:
            if (isinstance(r, (list, tuple)) and len(r) == 2
                    and all(isinstance(x, int) and not isinstance(x, bool) for x in r)
                    and 0 <= r[0] < r[1] <= n - 1):
                out.append([r[0], r[1]])
    else:
        sf = meta.get("straight_from")
        if isinstance(sf, int) and not isinstance(sf, bool) and 0 <= sf < n - 1:
            out.append([sf, n - 1])
    return _flags_to_ranges(_ranges_to_flags(out, n))


def _ranges_to_flags(ranges: list, n: int) -> list:
    flags = [False] * max(n - 1, 0)
    for a, b in ranges:
        for k in range(a, b):
            flags[k] = True
    return flags


def _flags_to_ranges(flags: list) -> list:
    out, start = [], None
    for k, f in enumerate(flags + [False]):
        if f and start is None:
            start = k
        elif not f and start is not None:
            out.append([start, k])
            start = None
    return out


def _set_meta(route: dict, coords: list, flags: list) -> dict:
    """New route_geojson with these coords + dashes (straight_from dropped)."""
    out = copy.deepcopy(route)
    for f in out.get("features") or []:
        g = (f or {}).get("geometry") or {}
        if g.get("type") == "LineString":
            g["coordinates"] = coords
            break
    meta = out.setdefault("foragingid", {})
    meta.pop("straight_from", None)
    ranges = _flags_to_ranges(flags)
    if ranges:
        meta["straight_ranges"] = ranges
    else:
        meta.pop("straight_ranges", None)
    return out


# ── stops on the line ────────────────────────────────────────────────────────

def stop_vertex_indices(coords: list, waypoints: list, circular: bool) -> list:
    """For each waypoint (in saved order) the vertex the line passes it at:
    the nearest vertex at or after the previous stop's vertex (the line visits
    the stops in this order). A line that retraces a path passes a stop more
    than once, so the FIRST pass within PASS_TOLERANCE_M of the best is taken,
    never a later, marginally closer one. Circular walks also get the closing
    vertex."""
    idx, start = [], 0
    for wp in waypoints:
        p = [wp["lng"], wp["lat"]]
        d = [_hav(coords[k], p) for k in range(start, len(coords))]
        best = min(d)
        j = start + next(i for i, x in enumerate(d) if x <= best + PASS_TOLERANCE_M)
        idx.append(j)
        start = j
    if circular:
        idx.append(len(coords) - 1)
    return idx


# ── reorder ──────────────────────────────────────────────────────────────────

def reverse(waypoints: list, route: dict, circular: bool) -> tuple:
    """Walk the other way. Circular: stop 1 stays stop 1, the rest reverse
    (1, N, N-1 … 2). Point-to-point: the whole order reverses."""
    coords = line_coords(route)
    if not coords:
        raise RouteError("this walk has no saved line to reverse")
    if circular and not is_closed(coords):
        raise RouteError("the saved line is not a closed loop — reverse needs a new route")
    flags = _ranges_to_flags(straight_ranges(route.get("foragingid"), len(coords)), len(coords))
    new_wps = [waypoints[0]] + waypoints[:0:-1] if circular else waypoints[::-1]
    return new_wps, _set_meta(route, coords[::-1], flags[::-1])


def start_at(waypoints: list, route: dict, circular: bool, k: int) -> tuple:
    """Circular walk only: waypoint k (0-based) becomes stop 1, same direction."""
    if not circular:
        raise RouteError("a point-to-point walk can only be reversed")
    if not 0 < k < len(waypoints):
        raise RouteError(f"stop {k + 1} is not a saved stop of this walk")
    coords = line_coords(route)
    if not coords:
        raise RouteError("this walk has no saved line")
    if not is_closed(coords):
        raise RouteError("the saved line is not a closed loop — a new start needs a new route")
    n = len(coords)
    flags = _ranges_to_flags(straight_ranges(route.get("foragingid"), n), n)
    v = stop_vertex_indices(coords, waypoints, circular=True)[k]
    m = n - 1                                   # vertex m duplicates vertex 0
    new_coords = coords[v:m] + coords[:v] + [coords[v]]
    new_flags = flags[v:] + flags[:v]           # segment k joins k, k+1 — rotates with vertices
    return waypoints[k:] + waypoints[:k], _set_meta(route, new_coords, new_flags)


# ── straighten detour legs (curator data fix) ────────────────────────────────

def straighten_legs(waypoints: list, route: dict, circular: bool, legs: list) -> tuple:
    """Replace the routed line between saved stops i → i+1 (0-based; i+1 may be
    the closing return to stop 1) with one straight, dashed segment between the
    vertices the line passes those stops at. Returns (route_geojson, length_m)."""
    coords = line_coords(route)
    if not coords:
        raise RouteError("this walk has no saved line")
    n = len(coords)
    flags = _ranges_to_flags(straight_ranges(route.get("foragingid"), n), n)
    idx = stop_vertex_indices(coords, waypoints, circular)
    for i in sorted(set(legs), reverse=True):          # back to front keeps indices valid
        if not 0 <= i < len(idx) - 1:
            raise RouteError(f"leg {i + 1}→{i + 2} is not on this walk")
        a, b = idx[i], idx[i + 1]
        if b <= a:
            raise RouteError(f"leg {i + 1}→{i + 2} has no line between its stops")
        coords = coords[:a + 1] + coords[b:]
        flags = flags[:a] + [True] + flags[b:]
    return _set_meta(route, coords, flags), line_length_m(coords)
