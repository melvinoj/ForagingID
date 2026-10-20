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

Circular vs point-to-point (foragingid.circular) is a VIEW of the stored line,
never a change to it (shown_line): point-to-point on a closed line stops at the
last stop; circular on an open line adds a straight, dashed leg back to stop 1.
Distance / time shown scale the saved figures by line length — distance_m and
duration_min themselves are never rewritten, so toggling back is lossless.
"""
from __future__ import annotations

import copy
import math
from typing import Optional

CLOSED_LOOP_TOLERANCE_M = 30.0     # first/last vertex this close = closed loop


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
    """For each waypoint (in saved order) the vertex the line passes it at.
    The line visits the stops in saved order, so the vertices must not go
    backwards; among all such assignments the one with the smallest total
    stop-to-vertex distance is taken (exact, by dynamic programming — ties
    keep the earliest vertex). A greedy stop-by-stop choice could take the
    wrong pass of a retraced path and push later stops onto far vertices,
    which moved a rotated loop's seam on every Start here round trip.
    Circular walks also get the closing vertex."""
    n, m = len(coords), len(waypoints)
    if m == 0:
        return [n - 1] if circular else []
    d = [[_hav(coords[v], [wp["lng"], wp["lat"]]) for v in range(n)] for wp in waypoints]
    best = d[0][:]                                   # best[v]: stops 0..s with stop s at vertex v
    back = []
    for s_ in range(1, m):
        pm, pv, row, arg = math.inf, 0, [], []
        for v in range(n):                           # prefix minimum of the previous row
            if best[v] < pm:
                pm, pv = best[v], v
            row.append(pm + d[s_][v])
            arg.append(pv)
        best, back = row, back + [arg]
    v = min(range(n), key=lambda q: (best[q], q))
    idx = [v]
    for arg in reversed(back):
        v = arg[v]
        idx.append(v)
    idx.reverse()
    if circular:
        idx.append(n - 1)
    return idx


# ── reorder ──────────────────────────────────────────────────────────────────

def reverse(waypoints: list, route: dict, circular: bool) -> tuple:
    """Walk the other way.
    Stored line a closed loop:
      shown circular       → stop 1 stays stop 1, the rest reverse (1, N … 2)
      shown point-to-point → the last stop becomes stop 1 (N, N-1 … 1) — the
                             loop is first started at N, then reversed
    Stored line open (saved point-to-point): the whole order reverses."""
    coords = line_coords(route)
    if not coords:
        raise RouteError("this walk has no saved line to reverse")
    if is_closed(coords):
        if not circular and len(waypoints) > 1:
            waypoints, route = start_at(waypoints, route, circular, len(waypoints) - 1)
            coords = line_coords(route)
        flags = _ranges_to_flags(straight_ranges(route.get("foragingid"), len(coords)), len(coords))
        return [waypoints[0]] + waypoints[:0:-1], _set_meta(route, coords[::-1], flags[::-1])
    flags = _ranges_to_flags(straight_ranges(route.get("foragingid"), len(coords)), len(coords))
    return waypoints[::-1], _set_meta(route, coords[::-1], flags[::-1])


def start_at(waypoints: list, route: dict, circular: bool, k: int) -> tuple:
    """Waypoint k (0-based) becomes stop 1, same direction. Needs a stored
    closed loop (shown circular or point-to-point — point-to-point then ends at
    the stop before k)."""
    if not 0 < k < len(waypoints):
        raise RouteError(f"stop {k + 1} is not a saved stop of this walk")
    coords = line_coords(route)
    if not coords:
        raise RouteError("this walk has no saved line")
    if not is_closed(coords):
        raise RouteError("this walk's saved line has no leg back to stop 1 — a new start needs a new route")
    n = len(coords)
    flags = _ranges_to_flags(straight_ranges(route.get("foragingid"), n), n)
    v = stop_vertex_indices(coords, waypoints, circular=True)[k]
    m = n - 1                                   # vertex m duplicates vertex 0
    new_coords = coords[v:m] + coords[:v] + [coords[v]]
    new_flags = flags[v:] + flags[:v]           # segment k joins k, k+1 — rotates with vertices
    return waypoints[k:] + waypoints[:k], _set_meta(route, new_coords, new_flags)


# ── circular / point-to-point view ───────────────────────────────────────────

def shown_line(waypoints: list, route: dict, distance_m, duration_min) -> Optional[dict]:
    """The line as the walk is shown, drawn, measured and exported. The stored
    line is never modified; see the module docstring."""
    coords = line_coords(route)
    if not coords:
        return None
    meta = route.get("foragingid") or {}
    circular = bool(meta.get("circular"))
    n = len(coords)
    flags = _ranges_to_flags(straight_ranges(meta, n), n)
    closed = is_closed(coords)
    shown, sflags = coords, flags
    if circular and not closed:
        shown, sflags = coords + [coords[0]], flags + [True]          # dashed leg back to stop 1
    elif not circular and closed and waypoints:
        cut = stop_vertex_indices(coords, waypoints, circular=False)[-1]
        if cut >= 1:
            shown, sflags = coords[:cut + 1], flags[:cut]               # ends at the last stop
    stored_len = line_length_m(coords)
    ratio = line_length_m(shown) / stored_len if shown is not coords and stored_len else 1.0
    return {
        "coordinates":     shown,
        "straight_ranges": _flags_to_ranges(sflags),
        "circular":        circular,
        "line_closed":     closed,
        "distance_m":      distance_m if ratio == 1.0 else round((distance_m or 0) * ratio),
        "duration_min":    duration_min if ratio == 1.0 else round((duration_min or 0) * ratio),
    }


def set_circular(route: dict, circular: bool) -> dict:
    """route_geojson with foragingid.circular set — nothing else changes."""
    out = copy.deepcopy(route)
    out.setdefault("foragingid", {})["circular"] = bool(circular)
    return out


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


# ── re-route through stops (changed legs only) ───────────────────────────────
# "↻ Re-route": the walk's CURRENT stops (saved + side-stops; saved stops left
# with no species dropped) become its saved stops, and the line is rebuilt —
# but only where it changed. A leg between two stops that were already
# consecutive saved stops keeps its stored geometry AND its dashed flags, so a
# detour once replaced by a straight dashed leg can never come back. Only legs
# touching a new stop, or bridging a dropped one, go to ORS; a new leg ORS
# detours on is kept as a straight dashed leg instead (DETOUR_* below).

DETOUR_FACTOR  = 3.0      # routed > factor × straight + slack → detour
DETOUR_SLACK_M = 150.0
ORS_MAX_POINTS = 50       # ORS directions: coordinates per request
REROUTE_MAX_REQUESTS = 10


def is_detour(routed_m: float, straight_m: float) -> bool:
    return routed_m > DETOUR_FACTOR * straight_m + DETOUR_SLACK_M


def plan_reroute(old_waypoints: list, route: dict, new_stops: list) -> dict:
    """new_stops: [{lat, lng, old_index (0-based saved position, or None for a
    new stop)}] in the new order. Returns {legs, runs, closed} where each leg is
    {i, j, kind: 'keep'|'route', range: (a, b) old vertex range for 'keep'} and
    runs are lists of consecutive stop indices to send to ORS (≤ ORS_MAX_POINTS
    each, adjacent runs share an end stop)."""
    coords = line_coords(route)
    closed = bool(coords) and is_closed(coords)
    v = stop_vertex_indices(coords, old_waypoints, circular=closed) if coords else []
    m, n_old = len(new_stops), len(old_waypoints)
    pairs = [(i, i + 1) for i in range(m - 1)] + ([(m - 1, 0)] if closed and m > 1 else [])
    legs = []
    for i, j in pairs:
        a, b = new_stops[i].get("old_index"), new_stops[j].get("old_index")
        keep = None
        if coords and a is not None and b is not None:
            if b == a + 1:
                keep = (v[a], v[b])
            elif closed and j == 0 and a == n_old - 1 and b == 0:
                keep = (v[a], len(coords) - 1)                 # the stored closing leg
        legs.append({"i": i, "j": j, "kind": "keep" if keep and keep[1] > keep[0] else "route",
                     "range": keep if keep and keep[1] > keep[0] else None})
    runs, cur = [], []
    for leg in legs:
        if leg["kind"] == "route":
            if cur and cur[-1] == leg["i"] and len(cur) < ORS_MAX_POINTS:
                cur.append(leg["j"])
            else:
                if cur:
                    runs.append(cur)
                cur = [leg["i"], leg["j"]]
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return {"legs": legs, "runs": runs, "closed": closed}


def assemble_reroute(route: dict, new_stops: list, plan: dict, routed: dict) -> tuple:
    """routed: {(i, j): {"coords": [[lng, lat], …]}} for every 'route' leg.
    Returns (route_geojson, length_m, report) — the stored meta (circular,
    stop radius…) is kept; dashes become straight_ranges."""
    old = line_coords(route)
    old_flags = _ranges_to_flags(straight_ranges(route.get("foragingid"), len(old)), len(old)) if old else []
    coords, flags, report = [], [], []

    def add(seg, seg_flags):
        if coords and seg and coords[-1] == seg[0]:
            seg = seg[1:]
        elif coords and seg:
            flags.append(False)                          # tiny join between two pieces at a stop
        coords.extend(seg)
        flags.extend(seg_flags)

    for leg in plan["legs"]:
        i, j = leg["i"], leg["j"]
        if leg["kind"] == "keep":
            a, b = leg["range"]
            add(old[a:b + 1], old_flags[a:b])
            continue
        seg = routed[(i, j)]["coords"]
        straight = _hav([new_stops[i]["lng"], new_stops[i]["lat"]], [new_stops[j]["lng"], new_stops[j]["lat"]])
        if len(seg) >= 2 and not is_detour(line_length_m(seg), straight):
            add(seg, [False] * (len(seg) - 1))
            report.append({"i": i, "j": j, "kind": "routed", "m": round(line_length_m(seg))})
        else:
            ends = [seg[0], seg[-1]] if len(seg) >= 2 else [[new_stops[i]["lng"], new_stops[i]["lat"]],
                                                              [new_stops[j]["lng"], new_stops[j]["lat"]]]
            add(ends, [True])
            report.append({"i": i, "j": j, "kind": "straight", "m": round(line_length_m(ends)),
                           "routed_m": round(line_length_m(seg)) if len(seg) >= 2 else None})
    out = copy.deepcopy(route) if route else {"type": "FeatureCollection", "features": []}
    if not out.get("features"):
        out["features"] = [{"type": "Feature", "geometry": {"type": "LineString", "coordinates": []}, "properties": {}}]
    out = _set_meta(out, coords, flags)
    out["foragingid"].pop("straight_note", None)          # described old leg numbers — no longer true
    return out, line_length_m(coords), report
