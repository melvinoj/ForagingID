"""
walk.py — Walk feature API: ORS route proxy + saved walks CRUD.

Endpoints:
  POST /api/walk/ors-route      — proxy to OpenRouteService foot-hiking directions
  POST /api/walk/saves          — save a walk
  GET  /api/walk/saves          — list all saved walks (summary)
  GET  /api/walk/saves/{id}     — load a saved walk (full data + computed stops/membership)
  PATCH /api/walk/saves/{id}/membership — set the route buffer (curator)
  POST /api/walk/saves/{id}/accept      — add photos to the walk, any distance (curator; older-photos list / Select pins)
  POST /api/walk/saves/{id}/exclude     — remove photos from the walk, incl. saved-stop photos (curator)
  POST /api/walk/saves/{id}/renumber    — current stops become the saved snapshot, 1..N (curator)
  POST /api/walk/saves/{id}/reorder     — reverse direction / start at a saved stop (curator; no ORS)
  PATCH /api/walk/saves/{id}/loop       — circular / point-to-point view of the saved line (curator; no ORS)
  POST /api/walk/saves/{id}/reroute     — rebuild the line through the current stops, changed legs only (curator; ORS)
  DELETE /api/walk/saves/{id}   — delete a saved walk (curator; 409 while published as an experience)
"""

import json
import logging
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.api.identity import Identity, get_identity
from app.models.observation import Observation, is_confirmed_observation
from app.models.walk import SavedWalk
from app.services import walk_membership as wm

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/walk", tags=["walk"])

ORS_DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/foot-hiking/geojson"


# ---------------------------------------------------------------------------
# ORS proxy
# ---------------------------------------------------------------------------

class ORSRequest(BaseModel):
    coordinates: List[List[float]]  # [[lng, lat], ...]


@router.post("/ors-route")
async def ors_route(body: ORSRequest):
    """
    Proxy to OpenRouteService foot-hiking directions.
    Returns ORS GeoJSON on success or {"fallback": true, "reason": "..."} on failure.
    """
    if len(body.coordinates) < 2:
        raise HTTPException(400, detail="At least 2 coordinates required")
    return await _ors_post(body.coordinates)


async def _ors_post(coordinates: list) -> dict:
    """One ORS foot-hiking directions request ([lng, lat] list, in the order
    given — ORS does not reorder). ORS GeoJSON, or {"fallback": True, "reason"}.
    Shared by the map's proxy above and the saved-walk re-route."""
    if not settings.ors_api_key:
        return {"fallback": True, "reason": "ORS key not configured"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                ORS_DIRECTIONS_URL,
                headers={
                    "Authorization": settings.ors_api_key,
                    "Content-Type": "application/json",
                },
                json={"coordinates": coordinates},
            )

        if resp.status_code == 200:
            return resp.json()

        log.warning("ORS returned %s: %s", resp.status_code, resp.text[:300])
        return {"fallback": True, "reason": f"ORS error {resp.status_code}"}

    except httpx.TimeoutException:
        log.warning("ORS request timed out")
        return {"fallback": True, "reason": "ORS request timed out"}
    except Exception as exc:
        log.warning("ORS request failed: %s", exc)
        return {"fallback": True, "reason": str(exc)}


# ---------------------------------------------------------------------------
# Saved walks — create
# ---------------------------------------------------------------------------

class SaveWalkRequest(BaseModel):
    name: str
    obs_ids: List[int]
    waypoints: List[dict]        # [{lat, lng, obs_id, label}, ...]
    route_geojson: Optional[dict] = None
    distance_m: float = 0.0
    duration_min: int = 0


@router.post("/saves")
async def save_walk(
    body: SaveWalkRequest,
    db: AsyncSession = Depends(get_db),
    identity: Identity = Depends(get_identity),
):
    walk = SavedWalk(
        name=body.name,
        obs_ids_json=json.dumps(body.obs_ids),
        waypoints_json=json.dumps(body.waypoints),
        route_geojson=json.dumps(body.route_geojson) if body.route_geojson else None,
        distance_m=body.distance_m,
        duration_min=body.duration_min,
        user_id=identity.user_id,
    )
    db.add(walk)
    await db.commit()
    await db.refresh(walk)
    return {"ok": True, "id": walk.id, "name": walk.name}


# ---------------------------------------------------------------------------
# Saved walks — list
# ---------------------------------------------------------------------------

@router.get("/saves")
async def list_walks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(SavedWalk).order_by(SavedWalk.created_at.desc())
    )
    walks = result.scalars().all()
    return {
        "walks": [
            {
                "id":          w.id,
                "name":        w.name,
                "created_at":  w.created_at.isoformat() if w.created_at else None,
                "distance_m":  w.distance_m,
                "duration_min": w.duration_min,
                # Stops = waypoints (one per stop, field notes included — same
                # count the walk panel shows). obs_ids holds every observation,
                # several per stop since stop clustering.
                "stop_count":  len(json.loads(w.waypoints_json or "[]")),
            }
            for w in walks
        ]
    }


# ---------------------------------------------------------------------------
# Saved walks — load
# ---------------------------------------------------------------------------

async def _load_walk(db: AsyncSession, walk_id: int) -> SavedWalk:
    walk = (await db.execute(select(SavedWalk).where(SavedWalk.id == walk_id))).scalar_one_or_none()
    if not walk:
        raise HTTPException(404, detail="Walk not found")
    return walk


async def walk_membership_for(db: AsyncSession, walk: SavedWalk) -> dict:
    """Saved + nearby observations → walk_membership.compute(). The SQL only
    pre-filters by bounding box; every membership decision is in the service."""
    ids = list(wm.saved_obs_ids(walk))
    saved = {}
    if ids:
        rows = (await db.execute(select(Observation).where(Observation.id.in_(ids)))).scalars().all()
        saved = {o.id: o for o in rows}
    nearby = []
    bb = wm.search_bbox(walk)
    if bb:
        nearby = (await db.execute(
            select(Observation).where(
                Observation.latitude.between(bb[0], bb[1]),
                Observation.longitude.between(bb[2], bb[3]),
            )
        )).scalars().all()
    # Hand-added photos can lie outside the bbox (any distance from the line).
    extra = wm.accepted_ids(walk) - set(ids) - {o.id for o in nearby}
    if extra:
        nearby = list(nearby) + list((await db.execute(
            select(Observation).where(Observation.id.in_(sorted(extra))))).scalars().all())
    return wm.compute(walk, saved, nearby)


async def saved_walks_by_species(db: AsyncSession) -> dict:
    """{scientific name: [{id, name}]} for every species at a stop of a saved
    walk — the walk panel's own live membership (walk_membership.compute), so
    Review's "on a walk" and the Recipes page's walk view agree with what the
    walk shows."""
    out: dict = {}
    for walk in (await db.execute(select(SavedWalk).order_by(SavedWalk.id))).scalars().all():
        mem = await walk_membership_for(db, walk)
        for st in wm.public_stops(mem):
            for sp in st.get("species") or []:
                walks = out.setdefault(sp["name"], [])
                if all(w["id"] != walk.id for w in walks):
                    walks.append({"id": walk.id, "name": walk.name})
    return out


async def species_on_saved_walks(db: AsyncSession) -> dict:
    """{scientific name: [walk names]} — saved_walks_by_species, names only."""
    return {name: [w["name"] for w in walks]
            for name, walks in (await saved_walks_by_species(db)).items()}


def _require_curator(identity: Identity) -> None:
    if identity.is_guest:
        raise HTTPException(403, "Curator only")


def _walk_out(walk: SavedWalk, mem: dict) -> dict:
    from app.services import walk_route
    route = json.loads(walk.route_geojson) if walk.route_geojson else None
    waypoints = [w for w in json.loads(walk.waypoints_json or "[]") if isinstance(w, dict)]
    return {
        "id":           walk.id,
        "name":         walk.name,
        "created_at":   walk.created_at.isoformat() if walk.created_at else None,
        "obs_ids":      json.loads(walk.obs_ids_json or "[]"),
        "waypoints":    json.loads(walk.waypoints_json or "[]"),
        "route_geojson": json.loads(walk.route_geojson) if walk.route_geojson else None,
        "distance_m":   walk.distance_m,
        "duration_min": walk.duration_min,
        # The line as shown (circular / point-to-point VIEW of the stored line,
        # walk_route.shown_line): what the map draws, measures and exports.
        "shown":        walk_route.shown_line(waypoints, route, walk.distance_m, walk.duration_min) if route else None,
        # Stops resolved from CURRENT observations + route-proximity members
        # (walk_membership.py). The frontend draws these, not waypoints' labels.
        "stops":        wm.public_stops(mem),
        "membership": {
            "rule":             mem["rule"],
            "line_source":      mem["line_source"],
            "member_obs_ids":   mem["member_obs_ids"],
            "joined_count":     mem["joined_count"],
            "older_candidates": mem["older_candidates"],
        },
    }


async def _species_names(db: AsyncSession, out: dict) -> dict:
    """{scientific name: English common name} for every species the walk
    response names (stops + older candidates) — names rule, display_common_name."""
    from app.models.species import Species, display_common_name
    want = ({sp["name"] for st in out["stops"] for sp in st["species"]}
            | {c["species"] for c in out["membership"]["older_candidates"] if c["species"]})
    if not want:
        return {}
    rows = (await db.execute(select(Species.scientific_name, Species.preferred_common_name, Species.common_names)
                             .where(Species.scientific_name.in_(sorted(want))))).all()
    return {r.scientific_name: n for r in rows if (n := display_common_name(r.preferred_common_name, r.common_names))}


@router.get("/saves/{walk_id}")
async def get_walk(walk_id: int, db: AsyncSession = Depends(get_db)):
    walk = await _load_walk(db, walk_id)
    out = _walk_out(walk, await walk_membership_for(db, walk))
    out["names"] = await _species_names(db, out)
    return out


# ---------------------------------------------------------------------------
# Saved walks — membership actions (curator only; each re-reads the row by id
# after commit and returns the recomputed walk)
# ---------------------------------------------------------------------------

class MembershipSettings(BaseModel):
    buffer_m: Optional[float] = None    # None = back to the default (25 m)


class ObsIdsBody(BaseModel):
    obs_ids: List[int]


async def _commit_and_reread(db: AsyncSession, walk_id: int) -> dict:
    await db.commit()
    db.expire_all()
    walk = await _load_walk(db, walk_id)
    out = _walk_out(walk, await walk_membership_for(db, walk))
    out["names"] = await _species_names(db, out)
    return out


@router.patch("/saves/{walk_id}/membership")
async def set_walk_membership(
    walk_id: int, body: MembershipSettings,
    db: AsyncSession = Depends(get_db), identity: Identity = Depends(get_identity),
):
    _require_curator(identity)
    walk = await _load_walk(db, walk_id)
    if body.buffer_m is not None and not (wm.BUFFER_MIN_M <= body.buffer_m <= wm.BUFFER_MAX_M):
        raise HTTPException(422, f"buffer_m must be {wm.BUFFER_MIN_M:g}–{wm.BUFFER_MAX_M:g} m")
    walk.buffer_m = body.buffer_m
    out = await _commit_and_reread(db, walk_id)
    if out["membership"]["rule"]["buffer_m"] != (body.buffer_m or wm.DEFAULT_BUFFER_M):
        raise HTTPException(500, "buffer_m write did not persist")
    return out


def _ids(raw) -> set:
    return {int(x) for x in json.loads(raw or "[]")}


def _dump_ids(ids: set):
    return json.dumps(sorted(ids)) if ids else None


@router.post("/saves/{walk_id}/accept")
async def accept_obs(
    walk_id: int, body: ObsIdsBody,
    db: AsyncSession = Depends(get_db), identity: Identity = Depends(get_identity),
):
    """Add photos to the walk: the older-photos list, or Select pins → Add to
    walk. Any photo that passes the walk's confirmed rule (is_confirmed_
    observation) and has a position may be added, whatever its distance from
    the line (walk_membership joins accepted photos unconditionally). Others are
    skipped with the reason, never written. A photo removed earlier is
    un-removed first and accepted only if that alone does not bring it back —
    so Add after Remove restores the row exactly."""
    _require_curator(identity)
    walk = await _load_walk(db, walk_id)
    want = list(dict.fromkeys(int(x) for x in body.obs_ids))
    rows = {o.id: o for o in (await db.execute(select(Observation).where(Observation.id.in_(want)))).scalars().all()}
    members = set((await walk_membership_for(db, walk))["member_obs_ids"])
    skipped, ok = [], []
    for oid in want:
        o = rows.get(oid)
        if o is None:
            skipped.append({"obs_id": oid, "reason": "not found"})
        elif not is_confirmed_observation(o):
            skipped.append({"obs_id": oid, "reason": f"not confirmed ({o.review_status}/{o.identification_status})"})
        elif o.latitude is None or o.longitude is None:
            skipped.append({"obs_id": oid, "reason": "no GPS position"})
        elif oid in members:
            skipped.append({"obs_id": oid, "reason": "already on the walk"})
        else:
            ok.append(oid)
    if ok:
        excluded = _ids(walk.excluded_obs_json)
        walk.excluded_obs_json = _dump_ids(excluded - set(ok))
        now = set((await walk_membership_for(db, walk))["member_obs_ids"])
        walk.accepted_obs_json = _dump_ids(_ids(walk.accepted_obs_json) | (set(ok) - now))
    out = await _commit_and_reread(db, walk_id)
    missing = sorted(set(ok) - set(out["membership"]["member_obs_ids"]))
    if missing:
        raise HTTPException(500, f"accepted but not members after re-read: {missing}")
    out["skipped"] = skipped
    return out


@router.post("/saves/{walk_id}/exclude")
async def exclude_obs(
    walk_id: int, body: ObsIdsBody,
    db: AsyncSession = Depends(get_db), identity: Identity = Depends(get_identity),
):
    """Remove photos from the walk: proximity-joined, hand-added or saved-stop
    photos (Select pins → Remove from walk, or a stop card's ✕). A hand-added
    photo is un-accepted first and excluded only if it is still on the walk —
    so Remove after Add restores the row exactly. Saved stops are never
    deleted: a stop whose photos are all removed stays on the line with no
    species until the walk is re-routed."""
    _require_curator(identity)
    walk = await _load_walk(db, walk_id)
    want = list(dict.fromkeys(int(x) for x in body.obs_ids))
    mem = await walk_membership_for(db, walk)
    on_walk = set(mem["member_obs_ids"]) | {oid for st in mem["stops"] for oid in st["obs_ids"]}
    skipped = [{"obs_id": oid, "reason": "not on this walk"} for oid in want if oid not in on_walk]
    ok = [oid for oid in want if oid in on_walk]
    if ok:
        walk.accepted_obs_json = _dump_ids(_ids(walk.accepted_obs_json) - set(ok))
        mem = await walk_membership_for(db, walk)
        still = set(mem["member_obs_ids"]) | {oid for st in mem["stops"] for oid in st["obs_ids"]}
        walk.excluded_obs_json = _dump_ids(_ids(walk.excluded_obs_json) | (set(ok) & still))
    out = await _commit_and_reread(db, walk_id)
    left = sorted(set(ok) & (set(out["membership"]["member_obs_ids"])
                             | {oid for st in out["stops"] for oid in st["obs_ids"]}))
    if left:
        raise HTTPException(500, f"excluded but still on the walk after re-read: {left}")
    out["skipped"] = skipped
    return out


@router.post("/saves/{walk_id}/renumber")
async def renumber_walk(
    walk_id: int,
    db: AsyncSession = Depends(get_db), identity: Identity = Depends(get_identity),
):
    """Current stops (saved + joined) become the saved snapshot, numbered 1..N."""
    _require_curator(identity)
    walk = await _load_walk(db, walk_id)
    mem = await walk_membership_for(db, walk)
    waypoints, obs_ids = wm.renumbered_snapshot(mem)
    walk.waypoints_json = json.dumps(waypoints)
    walk.obs_ids_json = json.dumps(obs_ids)
    walk.accepted_obs_json = None      # accepted photos are now saved-stop photos
    out = await _commit_and_reread(db, walk_id)
    labels = [s["label"] for s in out["stops"]]
    if labels != [str(i + 1) for i in range(len(waypoints))] or out["obs_ids"] != obs_ids:
        raise HTTPException(500, f"renumber did not persist as written (labels {labels})")
    return out


class LoopBody(BaseModel):
    circular: bool


@router.patch("/saves/{walk_id}/loop")
async def set_walk_loop(
    walk_id: int, body: LoopBody,
    db: AsyncSession = Depends(get_db), identity: Identity = Depends(get_identity),
):
    """Circular / point-to-point for a saved walk: only foragingid.circular is
    written. The stored line, distance_m and duration_min stay as they are — the
    view (walk_route.shown_line) cuts or closes the line, so toggling back is
    lossless. No ORS call."""
    from app.services import walk_route
    _require_curator(identity)
    walk = await _load_walk(db, walk_id)
    route = json.loads(walk.route_geojson) if walk.route_geojson else {}
    if not walk_route.line_coords(route):
        raise HTTPException(409, "this walk has no saved line")
    before = (walk.waypoints_json, walk.distance_m, walk.duration_min, walk_route.line_coords(route))
    new_route = walk_route.set_circular(route, body.circular)
    walk.route_geojson = json.dumps(new_route)
    out = await _commit_and_reread(db, walk_id)
    # Read-back by id: flag written, everything else untouched.
    rg = out["route_geojson"] or {}
    if (bool((rg.get("foragingid") or {}).get("circular")) != body.circular
            or (json.dumps(out["waypoints"]), out["distance_m"], out["duration_min"], walk_route.line_coords(rg))
            != (json.dumps(json.loads(before[0] or "[]")), before[1], before[2], before[3])):
        raise HTTPException(500, "circular setting did not persist as written")
    return out


class RerouteBody(BaseModel):
    confirm: bool = False              # False = dry run: what would change, no ORS call, no write


async def _reroute_snapshot(walk_id: int) -> str:
    """DB snapshot before a re-route writes (tests replace this hook)."""
    from app.api.dev import create_snapshot, SnapshotRequest
    res = await create_snapshot(SnapshotRequest(description=f"before re-route of saved walk {walk_id}"))
    if not res.get("ok"):
        raise HTTPException(500, f"snapshot failed — nothing re-routed: {res}")
    return res.get("db_snapshot") or ""


async def _route_runs(plan: dict, new_stops: list) -> dict:
    """ORS for every 'route' leg of a walk_route plan → {(i, j): {"coords"}}.
    Any failure raises (nothing is written by the callers)."""
    routed = {}
    for run in plan["runs"]:
        res = await _ors_post([[new_stops[k]["lng"], new_stops[k]["lat"]] for k in run])
        if res.get("fallback"):
            raise HTTPException(502, f"ORS could not route {'→'.join(new_stops[k]['label'] for k in run)}: "
                                     f"{res.get('reason')} — nothing written")
        feat = (res.get("features") or [{}])[0]
        line = (feat.get("geometry") or {}).get("coordinates") or []
        wpts = (feat.get("properties") or {}).get("way_points") or []
        if len(wpts) != len(run) or len(line) < 2:
            raise HTTPException(502, "ORS returned an unusable route — nothing written")
        for q in range(len(run) - 1):
            routed[(run[q], run[q + 1])] = {"coords": line[wpts[q]:wpts[q + 1] + 1]}
    return routed


@router.post("/saves/{walk_id}/reroute")
async def reroute_walk(
    walk_id: int, body: RerouteBody,
    db: AsyncSession = Depends(get_db), identity: Identity = Depends(get_identity),
):
    """"↻ Re-route through stops" (walk_route.plan_reroute): the current stops —
    saved + side-stops, saved stops with no species dropped, notes kept —
    become the saved stops, numbered 1..N (old stop 1 stays first). Legs
    between stops that were already consecutive keep their stored geometry and
    dashes; only changed legs go to ORS (≤ 50 points per request, ≤ 10
    requests), and a new leg ORS detours on is kept as a straight dashed leg.
    Distance = new line length; time at the walk's own pace. Dry run first
    (confirm=false); confirm=true takes a DB snapshot, then writes and reads
    the row back by id. Any ORS failure → nothing written."""
    from app.services import walk_route
    _require_curator(identity)
    walk = await _load_walk(db, walk_id)
    old_wps = [w for w in json.loads(walk.waypoints_json or "[]") if isinstance(w, dict)]
    route = json.loads(walk.route_geojson) if walk.route_geojson else {}
    mem = await walk_membership_for(db, walk)
    kept = [st for st in mem["stops"] if st["is_note"] or st["species"]]
    dropped = [st["label"] for st in mem["stops"] if not (st["is_note"] or st["species"])]
    added = [st["label"] for st in kept if st["origin"] == "joined"]
    # Walking order "as if they were there all along": saved stops keep their
    # order (old stop 1 first on a loop). A side-stop the line already passes
    # (within the route buffer — no "m off route") keeps its place along the
    # line; a far, hand-added one goes where it adds the least distance
    # (walk_route.insert_cheapest), not simply after the stop its label names.
    closed = bool(walk_route.line_coords(route)) and walk_route.is_closed(walk_route.line_coords(route))
    base = [st for st in kept if st["origin"] == "saved" or not st.get("off_route_m")]
    far = [st for st in kept if st["origin"] == "joined" and st.get("off_route_m")]
    if closed:
        k0 = next((k for k, st in enumerate(base) if st["origin"] == "saved" and st["label"] == "1"), 0)
        base = base[k0:] + base[:k0]
    kept = walk_route.insert_cheapest(base, far, closed)
    new_stops = [{"lat": st["lat"], "lng": st["lng"], "label": st["label"],
                  "old_index": int(st["label"]) - 1 if st["origin"] == "saved" else None} for st in kept]
    if len(new_stops) < 2:
        raise HTTPException(409, "fewer than two stops would remain — nothing to route")
    plan = walk_route.plan_reroute(old_wps, route, new_stops)
    to_route = [(new_stops[l["i"]]["label"], new_stops[l["j"]]["label"]) for l in plan["legs"] if l["kind"] == "route"]
    summary = {
        "dry_run": not body.confirm,
        "stops_before": len(mem["stops"]), "stops_after": len(new_stops),
        "added_stops": added, "dropped_stops": dropped,
        "legs_kept": sum(l["kind"] == "keep" for l in plan["legs"]),
        "legs_to_route": [f"{a}→{b}" for a, b in to_route],
        "ors_requests": len(plan["runs"]),
        "distance_before_m": walk.distance_m, "duration_before_min": walk.duration_min,
    }
    if not to_route and not dropped and not added:
        raise HTTPException(409, "nothing changed since the line was drawn — nothing to re-route")
    if len(plan["runs"]) > walk_route.REROUTE_MAX_REQUESTS:
        raise HTTPException(409, f"{len(plan['runs'])} separate ORS requests needed (max "
                                 f"{walk_route.REROUTE_MAX_REQUESTS}) — too many changes for one re-route")
    if not body.confirm:
        return summary

    snapshot = await _reroute_snapshot(walk_id)
    routed = await _route_runs(plan, new_stops)
    new_route, length, report = walk_route.assemble_reroute(route, new_stops, plan, routed)
    pace = (walk.duration_min / walk.distance_m) if walk.distance_m else 1 / 80
    new_dist, new_dur = round(length), round(length * pace)
    waypoints, obs_ids = wm.renumbered_snapshot({"stops": kept})
    walk.waypoints_json = json.dumps(waypoints)
    walk.obs_ids_json = json.dumps(obs_ids)
    walk.accepted_obs_json = None              # accepted photos are now saved-stop photos
    walk.route_geojson = json.dumps(new_route)
    walk.distance_m, walk.duration_min = new_dist, new_dur
    out = await _commit_and_reread(db, walk_id)
    if (out["waypoints"] != waypoints or out["route_geojson"] != new_route
            or out["distance_m"] != new_dist or out["duration_min"] != new_dur):
        raise HTTPException(500, "re-route did not persist as written — restore " + snapshot)
    label = {k: st["label"] for k, st in enumerate(new_stops)}
    # The new legs can pass other confirmed photos, which then join by the walk's
    # proximity rule — reported (never silently excluded) so the curator decides.
    before = {oid for st in kept for sp in st["species"] for oid in sp["obs_ids"]}
    newly = [{"obs_id": oid, "species": sp["name"], "stop": st["label"]}
             for st in out["stops"] for sp in st["species"] for oid in sp["obs_ids"] if oid not in before]
    summary.update({"dry_run": False, "snapshot": snapshot, "distance_m": new_dist, "duration_min": new_dur,
                    "newly_joined": newly,
                    "legs": [{"leg": f"{label[r['i']]}→{label[r['j']]}", **{k: v for k, v in r.items() if k not in ('i', 'j')}}
                             for r in report]})
    out["reroute"] = summary
    return out


class TidyOrderBody(BaseModel):
    stops: List[dict]                  # [{lat, lng}] — stop 1 first
    circular: bool = True


@router.post("/tidy-order")
async def tidy_order_endpoint(body: TidyOrderBody):
    """Build walk's stop order: walk_route.tidy_order (nearest-neighbour from
    stop 1, then 2-opt). Pure — no DB, no ORS."""
    from app.services import walk_route
    try:
        stops = [{"lat": float(s["lat"]), "lng": float(s["lng"])} for s in body.stops]
    except (KeyError, TypeError, ValueError):
        raise HTTPException(422, "each stop needs numeric lat and lng")
    if len(stops) > 500:
        raise HTTPException(422, "too many stops")
    return {"order": walk_route.tidy_order(stops, body.circular, 0)}


def _walk_probe(walk: SavedWalk, **override):
    """A detached stand-in for a saved walk with some fields replaced — for
    computing membership of a line that is not written yet."""
    from types import SimpleNamespace
    fields = {c.key: getattr(walk, c.key) for c in SavedWalk.__table__.columns}
    fields.update(override)
    return SimpleNamespace(**fields)


@router.post("/saves/{walk_id}/tidy")
async def tidy_walk(
    walk_id: int, body: RerouteBody,
    db: AsyncSession = Depends(get_db), identity: Identity = Depends(get_identity),
):
    """"Tidy route order": the saved stops in the order walk_route.tidy_order
    finds — 2-opt from the current order (fewest legs changed), stop 1 fixed,
    circular or point-to-point as the walk is set. Stops and members do not
    change; only the order and the changed legs do. Stored legs — also ones
    now walked backwards — keep their geometry and dashes; only new legs go to
    ORS (the Re-route rules: detour → straight dashed leg). Dry run first
    (confirm=false: before/after distance, legs changed, no ORS, no write);
    confirm=true takes the Re-route snapshot, routes, REFUSES if the new line
    would change the walk's members, then writes and reads back by id."""
    from app.services import walk_route
    _require_curator(identity)
    walk = await _load_walk(db, walk_id)
    old_wps = [w for w in json.loads(walk.waypoints_json or "[]") if isinstance(w, dict)]
    route = json.loads(walk.route_geojson) if walk.route_geojson else {}
    meta = route.get("foragingid") or {}
    circular = bool(meta.get("circular"))
    if len(old_wps) < 4 or not walk_route.line_coords(route):
        raise HTTPException(409, "needs a saved line and at least 4 stops")
    cur = list(range(len(old_wps)))
    order = walk_route.tidy_order(old_wps, circular, 0, cur)
    lbl = lambda k: str(k + 1)
    old_legs = {frozenset(e) for e in walk_route.order_legs(cur, circular)}
    changed = [e for e in walk_route.order_legs(order, circular) if frozenset(e) not in old_legs]
    new_stops = [{"lat": old_wps[k]["lat"], "lng": old_wps[k]["lng"], "label": lbl(k), "old_index": k}
                 for k in order]
    plan = walk_route.plan_reroute(old_wps, route, new_stops)
    # Estimate: kept legs at their stored length + new legs as straight lines.
    straight = {(l["i"], l["j"]): {"coords": [[new_stops[l["i"]]["lng"], new_stops[l["i"]]["lat"]],
                                              [new_stops[l["j"]]["lng"], new_stops[l["j"]]["lat"]]]}
                for l in plan["legs"] if l["kind"] == "route"}
    _r, est_m, _rep = walk_route.assemble_reroute(route, new_stops, plan, straight)
    summary = {
        "dry_run": not body.confirm,
        "circular": circular,
        "order": [lbl(k) for k in order],
        "legs_changed": [f"{lbl(a)}→{lbl(b)}" for a, b in changed],
        "legs_kept": sum(l["kind"] == "keep" for l in plan["legs"]),
        "legs_kept_reversed": sum(bool(l.get("reverse")) for l in plan["legs"]),
        "ors_requests": len(plan["runs"]),
        "crossings_before": len(walk_route.crossing_legs(old_wps, cur, circular)),
        "crossings_after": len(walk_route.crossing_legs(old_wps, order, circular)),
        "straight_before_m": round(walk_route.order_length_m(old_wps, cur, circular)),
        "straight_after_m": round(walk_route.order_length_m(old_wps, order, circular)),
        "distance_before_m": walk.distance_m,
        "estimated_distance_m": round(est_m),
    }
    if order == cur:
        raise HTTPException(409, "the stop order is already tidy — nothing to change")
    if len(plan["runs"]) > walk_route.REROUTE_MAX_REQUESTS:
        raise HTTPException(409, f"{len(plan['runs'])} separate ORS requests needed (max "
                                 f"{walk_route.REROUTE_MAX_REQUESTS}) — too many changes for one tidy")
    if not body.confirm:
        return summary

    before = await walk_membership_for(db, walk)
    snapshot = await _reroute_snapshot(walk_id)
    routed = await _route_runs(plan, new_stops)
    new_route, length, report = walk_route.assemble_reroute(route, new_stops, plan, routed)
    new_wps = [old_wps[k] for k in order]
    pace = (walk.duration_min / walk.distance_m) if walk.distance_m else 1 / 80
    new_dist, new_dur = round(length), round(length * pace)
    # Members unchanged (Melvin, 21 Oct 2026): membership depends on the line,
    # so check the new line before writing anything.
    after = await walk_membership_for(db, _walk_probe(walk, waypoints_json=json.dumps(new_wps),
                                                      route_geojson=json.dumps(new_route)))
    b, a = set(before["member_obs_ids"]), set(after["member_obs_ids"])
    if a != b:
        raise HTTPException(409, {"detail": "the tidied line would change the walk's members — nothing written",
                                  "would_join": sorted(a - b), "would_leave": sorted(b - a),
                                  "snapshot": snapshot})
    walk.waypoints_json = json.dumps(new_wps)
    walk.route_geojson = json.dumps(new_route)
    walk.distance_m, walk.duration_min = new_dist, new_dur
    out = await _commit_and_reread(db, walk_id)
    if (out["waypoints"] != new_wps or out["route_geojson"] != new_route
            or out["distance_m"] != new_dist or out["duration_min"] != new_dur):
        raise HTTPException(500, "tidy did not persist as written — restore " + snapshot)
    if set(out["membership"]["member_obs_ids"]) != b:
        raise HTTPException(500, "members changed after the write — restore " + snapshot)
    label = {k: st["label"] for k, st in enumerate(new_stops)}
    summary.update({"dry_run": False, "snapshot": snapshot, "distance_m": new_dist, "duration_min": new_dur,
                    "legs": [{"leg": f"{label[r['i']]}→{label[r['j']]}", **{k: v for k, v in r.items() if k not in ('i', 'j')}}
                             for r in report]})
    out["tidy"] = summary
    return out


class ReorderBody(BaseModel):
    mode: str                          # 'reverse' | 'start'
    stop_label: Optional[str] = None   # mode 'start': the saved stop that becomes stop 1


@router.post("/saves/{walk_id}/reorder")
async def reorder_walk(
    walk_id: int, body: ReorderBody,
    db: AsyncSession = Depends(get_db), identity: Identity = Depends(get_identity),
):
    """Reverse the direction, or start a circular walk at another saved stop.
    The saved line is reversed / rotated (walk_route.py) — no ORS call;
    distance_m / duration_min, members and removed/accepted photos unchanged.
    Saved stop numbers follow the new order; 7a labels are recomputed on read."""
    from app.services import walk_route
    _require_curator(identity)
    walk = await _load_walk(db, walk_id)
    waypoints = [w for w in json.loads(walk.waypoints_json or "[]") if isinstance(w, dict)]
    route = json.loads(walk.route_geojson) if walk.route_geojson else {}
    circular = bool((route.get("foragingid") or {}).get("circular"))
    dist, dur = walk.distance_m, walk.duration_min
    try:
        if body.mode == "reverse":
            new_wps, new_route = walk_route.reverse(waypoints, route, circular)
        elif body.mode == "start":
            label = (body.stop_label or "").strip()
            if not label.isdigit():
                raise HTTPException(400, f"stop {label!r} is a new stop (joined by route proximity) — "
                                         f"run Renumber stops first, then start there")
            k = int(label) - 1
            if 0 <= k < len(waypoints) and wm._is_note_wp(waypoints[k]):
                raise HTTPException(400, f"stop {label} is a field note — start at a species stop")
            new_wps, new_route = walk_route.start_at(waypoints, route, circular, k)
        else:
            raise HTTPException(400, "mode must be 'reverse' or 'start'")
    except walk_route.RouteError as e:
        raise HTTPException(409, str(e))
    walk.waypoints_json = json.dumps(new_wps)
    walk.route_geojson = json.dumps(new_route)
    out = await _commit_and_reread(db, walk_id)
    # Read-back by id: the row must hold exactly what was written, figures untouched.
    if (out["waypoints"] != new_wps or out["route_geojson"] != new_route
            or out["distance_m"] != dist or out["duration_min"] != dur):
        raise HTTPException(500, "reorder did not persist as written")
    return out


# ---------------------------------------------------------------------------
# Saved walks — delete
# ---------------------------------------------------------------------------

@router.delete("/saves/{walk_id}")
async def delete_walk(
    walk_id: int, db: AsyncSession = Depends(get_db), identity: Identity = Depends(get_identity),
):
    """Curator only. 409 while an experience page for this walk is published.
    Draft publications go with the walk; 'unpublished' ones stay as history
    (saved_walk_id → NULL by the FK's ON DELETE SET NULL)."""
    from app.models.experience import ExperiencePublication
    _require_curator(identity)
    result = await db.execute(select(SavedWalk).where(SavedWalk.id == walk_id))
    walk = result.scalar_one_or_none()
    if not walk:
        raise HTTPException(404, detail="Walk not found")
    pubs = (await db.execute(select(ExperiencePublication).where(
        ExperiencePublication.saved_walk_id == walk_id))).scalars().all()
    published = [p.slug for p in pubs if p.status == "published"]
    if published:
        raise HTTPException(409, detail=f"Walk is published as {', '.join(repr(s) for s in published)} "
                                        f"— unpublish it before deleting the walk")
    for p in pubs:
        if p.status == "draft":
            await db.delete(p)
    await db.delete(walk)
    await db.commit()
    return {"ok": True}
