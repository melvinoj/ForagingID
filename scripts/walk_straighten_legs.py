"""
walk_straighten_legs.py — replace ORS-detoured legs of a saved walk's line with
straight, dashed legs (walk_route.straighten_legs), then recompute its distance.

    python scripts/walk_straighten_legs.py --walk-id 3 --legs 5-6,8-9,9-10,10-11,16-17,17-18
    python scripts/walk_straighten_legs.py ... --apply          # write (snapshot first!)
    python scripts/walk_straighten_legs.py ... --db copy.sqlite # any DB file

Legs are saved stop numbers ("16-17"; "20-1" is the circular return). Dry run
by default. Writes route_geojson, distance_m (new line length) and duration_min
(scaled at the walk's own saved pace) — nothing else. REFUSES if the walk's
members would change: membership is computed from the line (route buffer), so a
shorter line could drop or add photos. Reads every written field back by id.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from app.services import walk_membership as wm  # noqa: E402
from app.services import walk_route  # noqa: E402

OBS_COLS = ("id, species_id, species_primary, review_status, identification_status, file_path, "
            "photo_taken_at, latitude, longitude, gps_accuracy_m, reviewed_at")


def members(conn, walk: dict) -> dict:
    """{label: sorted obs ids} — walk_membership.compute, loaded as export.py does."""
    ids = sorted(wm.saved_obs_ids(walk))
    q = ",".join("?" * len(ids))
    saved = {r["id"]: dict(r) for r in conn.execute(f"SELECT {OBS_COLS} FROM observations WHERE id IN ({q})", ids)} if ids else {}
    bb = wm.search_bbox(walk)
    near = [dict(r) for r in conn.execute(
        f"SELECT {OBS_COLS} FROM observations WHERE latitude BETWEEN ? AND ? AND longitude BETWEEN ? AND ?", bb)] if bb else []
    m = wm.compute(walk, saved, near)
    return {st["label"]: sorted(o for sp in st["species"] for o in sp["obs_ids"]) for st in m["stops"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--walk-id", type=int, required=True)
    ap.add_argument("--legs", required=True, help="comma-separated saved stop pairs, e.g. 5-6,16-17")
    ap.add_argument("--db", type=Path, default=REPO / "data" / "foragingid.db")
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    conn = sqlite3.connect(str(a.db))
    conn.row_factory = sqlite3.Row
    walk = dict(conn.execute("SELECT * FROM saved_walks WHERE id = ?", (a.walk_id,)).fetchone() or {})
    if not walk:
        sys.exit(f"saved walk {a.walk_id} not found")
    route = json.loads(walk["route_geojson"] or "{}")
    circular = bool((route.get("foragingid") or {}).get("circular"))
    wps = [w for w in json.loads(walk["waypoints_json"] or "[]") if isinstance(w, dict)]
    n_stops = len(wps)
    legs = []
    for part in a.legs.split(","):
        x, y = (int(v) for v in part.split("-"))
        if not (1 <= x <= n_stops and (y == x + 1 or (circular and x == n_stops and y == 1))):
            sys.exit(f"leg {part}: not consecutive saved stops of this walk")
        legs.append(x - 1)

    before = members(conn, walk)
    new_route, length = walk_route.straighten_legs(wps, route, circular, legs)
    old_len = walk_route.line_length_m(walk_route.line_coords(route))
    pace = (walk["duration_min"] or 0) / walk["distance_m"] if walk["distance_m"] else 1 / 80
    new_dist, new_dur = round(length), round(length * pace)
    after = members(conn, dict(walk, route_geojson=json.dumps(new_route)))

    print(f"{walk['name']} (id {walk['id']}): legs {a.legs}")
    print(f"  line {old_len:.0f} m → {length:.0f} m; distance_m {walk['distance_m']} → {new_dist}; "
          f"duration_min {walk['duration_min']} → {new_dur}")
    print(f"  vertices {len(walk_route.line_coords(route))} → {len(walk_route.line_coords(new_route))}; "
          f"straight_ranges {new_route['foragingid'].get('straight_ranges')}")
    if before != after:
        diff = {k: (before.get(k), after.get(k)) for k in set(before) | set(after) if before.get(k) != after.get(k)}
        sys.exit(f"  REFUSED: members would change: {diff}")
    print(f"  members unchanged ({sum(len(v) for v in before.values())} obs at {len(before)} stops)")
    if not a.apply:
        print("  dry run — nothing written (add --apply)")
        return
    conn.execute("UPDATE saved_walks SET route_geojson = ?, distance_m = ?, duration_min = ? WHERE id = ?",
                 (json.dumps(new_route), new_dist, new_dur, walk["id"]))
    conn.commit()
    row = dict(conn.execute("SELECT id, route_geojson, distance_m, duration_min, waypoints_json, obs_ids_json, "
                            "excluded_obs_json, accepted_obs_json FROM saved_walks WHERE id = ?", (walk["id"],)).fetchone())
    ok = (json.loads(row["route_geojson"]) == new_route and row["distance_m"] == new_dist
          and row["duration_min"] == new_dur and row["waypoints_json"] == walk["waypoints_json"]
          and row["obs_ids_json"] == walk["obs_ids_json"] and row["excluded_obs_json"] == walk["excluded_obs_json"]
          and row["accepted_obs_json"] == walk["accepted_obs_json"])
    print(f"  read back id {row['id']}: distance_m {row['distance_m']} duration_min {row['duration_min']} "
          f"vertices {len(walk_route.line_coords(json.loads(row['route_geojson'])))} "
          f"straight_ranges {json.loads(row['route_geojson'])['foragingid'].get('straight_ranges')} "
          f"waypoints/obs/excluded/accepted unchanged: {ok}")
    if not ok:
        sys.exit("  WRITE DID NOT PERSIST AS WRITTEN")
    if members(conn, dict(walk, **{k: row[k] for k in ("route_geojson",)})) != before:
        sys.exit("  members changed after write — restore the snapshot")
    print("  members re-checked after write: unchanged")


if __name__ == "__main__":
    main()
