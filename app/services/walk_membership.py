"""
Walk membership by route proximity — the ONLY place this rule lives.

A saved walk's members are computed when it is read, never stored:

    saved stops (waypoints_json, with their saved observation ids)
  + confirmed observations within buffer_m of the walk's line that were taken
    on/after members_since, or were accepted from the older-photos review
  − observations removed by hand (excluded_obs_json)

Species are resolved from the CURRENT observation rows, so re-IDs and
rejections show on the next load (CHANGELOG pending item 6) and a species only
appears once its observation is confirmed (is_confirmed_observation — same rule
as the map and the experience export).

Joined observations go to the nearest saved stop within the walk's stop radius;
otherwise they form new stops (greedy centroid clustering, same radius), which
are labelled after the saved stop that precedes them along the line: "7a",
"7b"… Letters are given in photo-time order so a later upload never relabels
an earlier new stop. Saved stops keep their saved numbers until the curator
runs "Renumber stops" (renumbered_snapshot below).

Pure Python on dicts or ORM rows — no DB access — so app/api/walk.py,
app/api/foray_sessions.py and scripts/experience_export/export.py share it.

Clocks: photo_taken_at is EXIF local time (naive); saved_walks.created_at is
UTC (CLAUDE.md "two clocks"). members_since is stored in the PHOTO clock; the
default is created_at converted to local time, compared as naive local.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable, Optional

from app.models.observation import is_confirmed_observation, is_human_confirmed

DEFAULT_BUFFER_M      = 25.0
BUFFER_MIN_M          = 10.0
BUFFER_MAX_M          = 60.0
DEFAULT_STOP_RADIUS_M = 30.0
# A line that retraces a path passes a point more than once: every pass within
# this of the nearest counts as a candidate (stop order / 7a labels below).
PASS_TOLERANCE_M      = 15.0


# ── field access (ORM row, sqlite3.Row-as-dict, or plain dict) ───────────────

def _f(o, name):
    return o.get(name) if isinstance(o, dict) else getattr(o, name, None)


def _json_list(raw) -> list:
    if not raw:
        return []
    try:
        v = json.loads(raw) if isinstance(raw, str) else raw
        return list(v) if isinstance(v, (list, tuple)) else []
    except (ValueError, TypeError):
        return []


def _to_dt(v) -> Optional[datetime]:
    if v is None or isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v).replace("Z", "").strip())
    except ValueError:
        return None


def _utc_to_local_naive(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().replace(tzinfo=None)


# ── per-walk rule ────────────────────────────────────────────────────────────

def walk_rule(walk) -> dict:
    buf = _f(walk, "buffer_m")
    buffer_m = float(buf) if buf is not None else DEFAULT_BUFFER_M
    buffer_m = max(BUFFER_MIN_M, min(BUFFER_MAX_M, buffer_m))

    since = _to_dt(_f(walk, "members_since"))
    since_is_default = since is None
    if since is None:
        created = _to_dt(_f(walk, "created_at"))
        since = _utc_to_local_naive(created) if created else None

    route = _route_dict(walk)
    meta = route.get("foragingid") or {}
    radius = meta.get("stop_radius_m") or DEFAULT_STOP_RADIUS_M

    return {
        "buffer_m":          buffer_m,
        "buffer_is_default": buf is None,
        "since":             since,
        "since_is_default":  since_is_default,
        "stop_radius_m":     float(radius),
        "excluded":          {int(x) for x in _json_list(_f(walk, "excluded_obs_json"))},
        "accepted":          {int(x) for x in _json_list(_f(walk, "accepted_obs_json"))},
    }


def _route_dict(walk) -> dict:
    raw = _f(walk, "route_geojson")
    if not raw:
        return {}
    try:
        v = json.loads(raw) if isinstance(raw, str) else raw
        return v if isinstance(v, dict) else {}
    except (ValueError, TypeError):
        return {}


def _is_note_wp(wp: dict) -> bool:
    # Same rule as loadSavedWalk (index.html): old walks stored notes as label 'Note'.
    return wp.get("type") == "note" or (not wp.get("type") and wp.get("label") == "Note")


def _wp_obs_ids(wp: dict) -> list:
    if isinstance(wp.get("obs_ids"), list):
        return [int(x) for x in wp["obs_ids"] if x is not None]
    return [int(wp["obs_id"])] if wp.get("obs_id") is not None else []


def accepted_ids(walk) -> set:
    """Photos the curator added to the walk by hand (accepted_obs_json). Callers
    load these rows by id as well as the bbox query — an accepted photo can be
    far from the line (compute lets it join whatever its distance)."""
    return {int(x) for x in _json_list(_f(walk, "accepted_obs_json"))}


def saved_obs_ids(walk) -> set:
    """Every observation id the saved snapshot references (obs_ids_json + stops)."""
    ids = {int(x) for x in _json_list(_f(walk, "obs_ids_json"))}
    for wp in _json_list(_f(walk, "waypoints_json")):
        if isinstance(wp, dict) and not _is_note_wp(wp):
            ids.update(_wp_obs_ids(wp))
    return ids


# ── geometry (local equirectangular metres — fine at walk scale) ─────────────

def _line_latlng(walk, waypoints: list) -> tuple[list, str]:
    for feat in _route_dict(walk).get("features") or []:
        geom = (feat or {}).get("geometry") or {}
        if geom.get("type") == "LineString" and len(geom.get("coordinates") or []) >= 2:
            return [(c[1], c[0]) for c in geom["coordinates"]], "saved_line"
    pts = [(wp["lat"], wp["lng"]) for wp in waypoints
           if isinstance(wp, dict) and wp.get("lat") is not None and wp.get("lng") is not None]
    return pts, "stops"


class _Frame:
    def __init__(self, lat0: float, lng0: float):
        self.lat0, self.lng0 = lat0, lng0
        self.kx = 111320.0 * math.cos(math.radians(lat0))
        self.ky = 110540.0

    def xy(self, lat, lng):
        return ((lng - self.lng0) * self.kx, (lat - self.lat0) * self.ky)

    def latlng(self, x, y):
        return (self.lat0 + y / self.ky, self.lng0 + x / self.kx)


class _Line:
    def __init__(self, frame: _Frame, pts_latlng: list):
        self.pts = [frame.xy(la, ln) for la, ln in pts_latlng]
        self.cum = [0.0]
        for (ax, ay), (bx, by) in zip(self.pts, self.pts[1:]):
            self.cum.append(self.cum[-1] + math.hypot(bx - ax, by - ay))
        # Closed loop (circular walk): last vertex back at the first (same 30 m
        # tolerance as walk_route.CLOSED_LOOP_TOLERANCE_M).
        self.closed = len(self.pts) > 2 and math.hypot(self.pts[-1][0] - self.pts[0][0],
                                                       self.pts[-1][1] - self.pts[0][1]) <= 30.0

    def project(self, p) -> tuple[float, float]:
        """(distance to the line, chainage along it) in metres. Ties keep the
        earliest segment, so a circular walk's start stop gets chainage 0."""
        px, py = p
        if len(self.pts) == 1:
            ax, ay = self.pts[0]
            return math.hypot(px - ax, py - ay), 0.0
        best_d, best_ch = math.inf, 0.0
        for i, ((ax, ay), (bx, by)) in enumerate(zip(self.pts, self.pts[1:])):
            dx, dy = bx - ax, by - ay
            seg2 = dx * dx + dy * dy
            t = 0.0 if seg2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
            d = math.hypot(px - ax - t * dx, py - ay - t * dy)
            if d < best_d:
                best_d, best_ch = d, self.cum[i] + t * math.sqrt(seg2)
        return best_d, best_ch

    def passes(self, p, tol: float = PASS_TOLERANCE_M, merge_seam: bool = True) -> list:
        """Chainage of each pass of the line within tol of the nearest point
        (a retraced path is passed more than once) — one per pass, at that
        pass's nearest point, ascending."""
        px, py = p
        if len(self.pts) == 1:
            return [0.0]
        hits = []
        for i, ((ax, ay), (bx, by)) in enumerate(zip(self.pts, self.pts[1:])):
            dx, dy = bx - ax, by - ay
            seg2 = dx * dx + dy * dy
            t = 0.0 if seg2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
            hits.append((math.hypot(px - ax - t * dx, py - ay - t * dy), self.cum[i] + t * math.sqrt(seg2)))
        best = min(d for d, _ in hits)
        runs, run = [], None                     # consecutive segments of one pass
        for k, (d, ch) in enumerate(hits):
            if d <= best + tol:
                run = run or []
                run.append((d, ch, k))
            elif run:
                runs.append(run)
                run = None
        if run:
            runs.append(run)
        # Closed loop: a pass running across the start/end seam is ONE pass
        # (otherwise starting the walk at another stop could split it in two).
        # Not for saved stops (merge_seam=False): stop 1 IS the start of the line.
        if (merge_seam and len(runs) > 1 and self.closed and runs[0][0][2] == 0
                and runs[-1][-1][2] == len(hits) - 1):
            runs[0] = runs.pop() + runs[0]
        return sorted(min(r)[1] for r in runs)    # one chainage per pass: its nearest point


def search_bbox(walk) -> Optional[tuple]:
    """(min_lat, max_lat, min_lng, max_lng) to pre-filter nearby observations in SQL."""
    waypoints = [w for w in _json_list(_f(walk, "waypoints_json")) if isinstance(w, dict)]
    pts, _ = _line_latlng(walk, waypoints)
    if not pts:
        return None
    buf = walk_rule(walk)["buffer_m"] + 5.0
    lat0 = pts[0][0]
    dlat = buf / 110540.0
    dlng = buf / (111320.0 * math.cos(math.radians(lat0)))
    lats = [p[0] for p in pts]; lngs = [p[1] for p in pts]
    return (min(lats) - dlat, max(lats) + dlat, min(lngs) - dlng, max(lngs) + dlng)


# ── membership ───────────────────────────────────────────────────────────────

def _letters(n: int) -> str:
    """0 → 'a', 25 → 'z', 26 → 'aa' …"""
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(97 + r) + s
    return s


def _add_species(stop: dict, o, joined: bool) -> None:
    name = _f(o, "species_primary")
    oid = int(_f(o, "id"))
    human = is_human_confirmed(o)
    for sp in stop["species"]:
        if sp["name"] == name:
            sp["obs_ids"].append(oid)
            sp["human"] = sp["human"] or human
            sp["joined"] = sp["joined"] and joined
            return
    stop["species"].append({"name": name, "species_id": _f(o, "species_id"),
                            "human": human, "joined": joined, "obs_ids": [oid]})


def compute(walk, saved_obs: dict, nearby_obs: Iterable) -> dict:
    """
    walk       — SavedWalk row or dict (the columns of saved_walks)
    saved_obs  — {obs_id: observation} for saved_obs_ids(walk)
    nearby_obs — observations inside search_bbox(walk) (may overlap saved_obs)

    Returns {rule, line_source, stops, member_obs_ids, joined_count,
             older_candidates}. Stops are in display order; each carries
    label, origin ('saved'|'joined'), species[{name, species_id, human,
    joined, obs_ids}] and obs_ids (every id at the stop — saved ones even when
    no longer confirmed, so a renumber keeps them).
    """
    rule = walk_rule(walk)
    buffer_m, since, radius = rule["buffer_m"], rule["since"], rule["stop_radius_m"]
    excluded, accepted = rule["excluded"], rule["accepted"]
    waypoints = [w for w in _json_list(_f(walk, "waypoints_json")) if isinstance(w, dict)]
    saved_ids = saved_obs_ids(walk)

    line_pts, line_source = _line_latlng(walk, waypoints)
    if not line_pts:
        return {"rule": _rule_out(rule), "line_source": None, "stops": [],
                "member_obs_ids": [], "joined_count": 0, "older_candidates": []}
    frame = _Frame(*line_pts[0])
    line = _Line(frame, line_pts)

    # Saved stops — numbered by saved order (notes included, as the walk panel does).
    stops, anchors = [], []          # anchors: (stop, xy, chainage) for non-note stops
    for i, wp in enumerate(waypoints):
        label = str(i + 1)
        if _is_note_wp(wp):
            stops.append({"label": label, "origin": "saved", "is_note": True,
                          "lat": wp["lat"], "lng": wp["lng"],
                          "note_id": wp.get("note_id", wp.get("obs_id")),
                          "species": [], "obs_ids": [], "joined_obs_ids": [],
                          "_wp": wp, "_ch": line.project(frame.xy(wp["lat"], wp["lng"]))[1]})
            continue
        ids = _wp_obs_ids(wp)
        stop = {"label": label, "origin": "saved", "is_note": False,
                "lat": wp["lat"], "lng": wp["lng"], "species": [],
                "obs_ids": [x for x in ids if x not in excluded], "joined_obs_ids": [], "_wp": wp}
        for oid in ids:
            o = saved_obs.get(oid)
            if o is not None and oid not in excluded and is_confirmed_observation(o):
                _add_species(stop, o, joined=False)
        xy = frame.xy(stop["lat"], stop["lng"])
        stop["_ch"] = line.project(xy)[1]
        stops.append(stop)
        anchors.append((stop, xy))

    # Chainage of saved stops = the pass the walk makes in SAVED ORDER: the first
    # close pass at or after the previous stop's (nearest pass if none). On a
    # path walked out and back the nearest pass alone can be the wrong one, and
    # which one wins would flip when the walk is reversed (walk_route.reverse).
    prev_ch = 0.0
    for st in stops:
        cands = line.passes(frame.xy(st["lat"], st["lng"]), merge_seam=False)
        later = [c for c in cands if c >= prev_ch]
        st["_ch"] = later[0] if later else st["_ch"]
        prev_ch = st["_ch"]

    on_walk = {sp["name"] for st in stops for sp in st["species"]}

    # Nearby confirmed observations not in the snapshot. A photo the curator
    # ACCEPTED (older-photos list, or "Select pins → Add to walk") always joins,
    # whatever its distance from the line: it was added deliberately. Callers
    # load accepted rows by id (accepted_ids) so a far one is in nearby_obs.
    joining, older = [], defaultdict(list)
    off_line = {}                     # obs id → metres from the line (joined photos)
    seen = set()
    for o in nearby_obs:
        oid = int(_f(o, "id"))
        if oid in seen or oid in saved_ids or oid in excluded:
            continue
        seen.add(oid)
        if not is_confirmed_observation(o):
            continue
        lat, lng = _f(o, "latitude"), _f(o, "longitude")
        if lat is None or lng is None:
            continue
        picked = oid in accepted
        acc = _f(o, "gps_accuracy_m")
        if not picked and acc is not None and acc > buffer_m:   # position less certain than the buffer
            continue
        xy = frame.xy(lat, lng)
        d, ch = line.project(xy)
        if d > buffer_m and not picked:
            continue
        taken = _to_dt(_f(o, "photo_taken_at"))
        if picked or (since is not None and taken is not None and taken >= since):
            joining.append((o, xy, ch, taken))
            off_line[oid] = d
        else:
            older[_f(o, "species_primary")].append((o, d))

    # Assign: nearest saved stop within the stop radius, else a new stop.
    clusters = []                     # {sx, sy, n, obs:[...], t_min}
    for o, xy, ch, taken in sorted(joining, key=lambda r: r[2]):
        best, best_d = None, math.inf
        for st, sxy in anchors:
            dd = math.hypot(xy[0] - sxy[0], xy[1] - sxy[1])
            if dd < best_d:
                best, best_d = st, dd
        if best is not None and best_d <= radius:
            _add_species(best, o, joined=True)
            best["obs_ids"].append(int(_f(o, "id")))
            best["joined_obs_ids"].append(int(_f(o, "id")))
            continue
        home = None
        for c in clusters:
            cx, cy = c["sx"] / c["n"], c["sy"] / c["n"]
            if math.hypot(xy[0] - cx, xy[1] - cy) <= radius:
                home = c
                break
        if home is None:
            home = {"sx": 0.0, "sy": 0.0, "n": 0, "obs": [], "t_min": None}
            clusters.append(home)
        home["sx"] += xy[0]; home["sy"] += xy[1]; home["n"] += 1
        home["obs"].append(o)
        if taken is not None and (home["t_min"] is None or taken < home["t_min"]):
            home["t_min"] = taken

    # New stops: label after the saved stop that precedes them along the line.
    # A new stop on a path the walk passes more than once takes the pass whose
    # two neighbouring saved stops are physically closest to it — the same pair
    # whichever way round the walk goes, so "7a" stays between the same stops.
    # The stored line's shape, not the circular/point-to-point VIEW flag
    # (walk_route.shown_line) — toggling the view never moves a "7a" label.
    circular = line.closed

    def _prev_at(ch):
        prev = None
        for st in stops:
            if st["_ch"] <= ch and (prev is None or st["_ch"] >= prev["_ch"]):
                prev = st
        return prev

    def _pair_cost(xy, prev):
        k = stops.index(prev) if prev is not None else -1
        nxt = stops[k + 1] if k + 1 < len(stops) else (stops[0] if circular and stops else None)
        cost = 0.0
        for st in (prev, nxt):
            if st is not None:
                sx, sy = frame.xy(st["lat"], st["lng"])
                cost += math.hypot(xy[0] - sx, xy[1] - sy)
        return cost

    by_prev = defaultdict(list)
    for c in clusters:
        cx, cy = c["sx"] / c["n"], c["sy"] / c["n"]
        lat, lng = frame.latlng(cx, cy)
        ch = min(line.passes((cx, cy)), key=lambda k: (_pair_cost((cx, cy), _prev_at(k)), k))
        prev = _prev_at(ch)
        stop = {"origin": "joined", "is_note": False, "lat": lat, "lng": lng,
                "species": [], "obs_ids": [], "joined_obs_ids": [], "_ch": ch}
        for o in c["obs"]:
            _add_species(stop, o, joined=True)
            stop["obs_ids"].append(int(_f(o, "id")))
            stop["joined_obs_ids"].append(int(_f(o, "id")))
        by_prev[prev["label"] if prev else "0"].append((c["t_min"], ch, stop))

    ordered = []
    def _emit(key):
        group = sorted(by_prev.get(key, []),
                       key=lambda r: (r[0] is None, r[0] or datetime.min, r[1]))
        for k, (_, _, st) in enumerate(group):
            st["label"] = f"{key}{_letters(k)}"
            ordered.append(st)
    _emit("0")
    for st in stops:
        ordered.append(st)
        _emit(st["label"])

    # "140 m off route": a stop holding a joined photo beyond the route buffer
    # (only an accepted photo can be) shows how far from the line it is.
    for st in ordered:
        far = [off_line[o] for o in st.get("joined_obs_ids", []) if off_line.get(o, 0) > buffer_m]
        st["off_route_m"] = round(max(far)) if far else None

    members = sorted({oid for st in ordered for sp in st["species"] for oid in sp["obs_ids"]})
    joined_count = sum(len(st["joined_obs_ids"]) for st in ordered)
    on_walk |= {sp["name"] for st in ordered for sp in st["species"]}

    candidates = []
    for name, rows in older.items():
        if not name or name in on_walk:
            continue
        candidates.append({
            "species":    name,
            "species_id": _f(rows[0][0], "species_id"),
            "obs_ids":    sorted(int(_f(o, "id")) for o, _ in rows),
            "n":          len(rows),
            "nearest_m":  round(min(d for _, d in rows), 1),
            # Pin positions, so the review list can highlight them on the map.
            "points":     [[_f(o, "latitude"), _f(o, "longitude"), int(_f(o, "id"))] for o, _ in rows],
            "human":      any(is_human_confirmed(o) for o, _ in rows),
        })
    candidates.sort(key=lambda c: (-c["n"], c["species"]))

    return {"rule": _rule_out(rule), "line_source": line_source, "stops": ordered,
            "member_obs_ids": members, "joined_count": joined_count,
            "older_candidates": candidates}


def _rule_out(rule: dict) -> dict:
    return {
        "buffer_m":          rule["buffer_m"],
        "buffer_is_default": rule["buffer_is_default"],
        "since":             rule["since"].isoformat(sep=" ") if rule["since"] else None,
        "since_is_default":  rule["since_is_default"],
        "stop_radius_m":     rule["stop_radius_m"],
        "excluded_count":    len(rule["excluded"]),
        "accepted_count":    len(rule["accepted"]),
    }


def public_stops(result: dict) -> list:
    """Stops without the private _wp/_ch working fields (API output)."""
    return [{k: v for k, v in st.items() if not k.startswith("_")} for st in result["stops"]]


def renumbered_snapshot(result: dict) -> tuple[list, list]:
    """
    "Renumber stops": the current computed stops become the saved snapshot,
    numbered 1..N in display order. Returns (waypoints, obs_ids) for
    waypoints_json / obs_ids_json. Saved stops keep their stored waypoint
    fields (only obs_ids/labels refreshed); labels become the current confirmed
    species names, so stale save-time labels are replaced too.
    """
    waypoints, all_ids = [], []
    for st in result["stops"]:
        if st["is_note"]:
            waypoints.append(dict(st["_wp"]))
            continue
        wp = dict(st.get("_wp") or {"type": "obs", "lat": st["lat"], "lng": st["lng"]})
        wp["type"] = "obs"
        wp["obs_ids"] = list(dict.fromkeys(st["obs_ids"]))
        wp["labels"] = [sp["name"] for sp in st["species"]]
        wp.pop("obs_id", None); wp.pop("label", None)
        waypoints.append(wp)
        all_ids.extend(wp["obs_ids"])
    return waypoints, list(dict.fromkeys(all_ids))
