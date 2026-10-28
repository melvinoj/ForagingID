"""
21 Oct 2026 (Melvin) — two items.

Item 1  Route order by geometry: walk_route.tidy_order (nearest-neighbour, then
        2-opt) and "Tidy route order" on a saved walk (POST /api/walk/saves/{id}/tidy).
        Removes crossings, keeps stop 1, circular and point-to-point; a stored
        leg walked backwards is kept (reversed), not re-routed; the dry run
        writes nothing; the write is refused if members would change.
Item 2  Review cards for every unreviewed warning: Approve / Edit (batch-1
        path, curator-authored, 409 if the field changed since drafting),
        Remove (field cleared + history row changed_by='human'; never for a
        deadly species), walk species first, warning cards outside Approve all.

Throw-away SQLite DBs; ORS and the DB snapshot are replaced by fakes.
Run from project root:  python tests/test_route_order_and_warning_review.py
"""
import asyncio
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from datetime import datetime

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main  # noqa: E402,F401  (every model on Base.metadata)
import app.api.walk as walk_api  # noqa: E402
import app.api.culinary as culinary_api  # noqa: E402
from app.api.identity import Identity, get_identity  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.models.culinary import CulinaryInfo  # noqa: E402
from app.models.observation import Observation  # noqa: E402
from app.models.species import CulinaryInfoHistory, Species, SpeciesAIDraft  # noqa: E402
from app.models.walk import SavedWalk  # noqa: E402
from app.services import walk_route as wr  # noqa: E402
from app.services.safety_gate import safety_by_names  # noqa: E402
from app.services.taxonomy import normalize_taxon_key  # noqa: E402

CURATOR = Identity(user_id=1, is_guest=False, is_anonymous_guest=False, workshop_session_id=None)
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"


def _run(coro):
    return asyncio.run(coro)


def _fixture(name):
    with open(os.path.join(ROOT, "tests", "fixtures", name), encoding="utf-8") as f:
        return json.load(f)


# ── Item 1: tidy_order (pure) ────────────────────────────────────────────────

def _ring(n=12, seed=7):
    """Stops on a ~600 m circle, shuffled — the shortest tour is the ring."""
    import math
    pts = [{"lat": 47.71 + 0.0027 * math.sin(2 * math.pi * k / n),
            "lng": 7.82 + 0.0040 * math.cos(2 * math.pi * k / n)} for k in range(n)]
    rest = pts[1:]
    random.Random(seed).shuffle(rest)
    return [pts[0]] + rest


def test_tidy_order_removes_crossings_and_keeps_stop_1_circular():
    stops = _ring()
    nn = list(range(len(stops)))
    assert wr.crossing_legs(stops, nn, True)                        # shuffled: crossings
    for given in (None, nn):                                         # NN start, or from a saved order
        o = wr.tidy_order(stops, True, 0, given)
        assert o[0] == 0 and sorted(o) == list(range(len(stops)))
        assert wr.crossing_legs(stops, o, True) == []
        assert wr.order_length_m(stops, o, True) <= wr.order_length_m(stops, nn, True)


def test_tidy_order_point_to_point_keeps_stop_1_and_has_no_crossings():
    stops = _ring(14, seed=3)
    o = wr.tidy_order(stops, False, 0, list(range(len(stops))))
    assert o[0] == 0 and wr.crossing_legs(stops, o, False) == []
    # a point-to-point walk need not return: its order differs from the loop's
    assert wr.order_length_m(stops, o, False) <= wr.order_length_m(stops, list(range(len(stops))), False)


def test_tidy_order_fixed_start_other_than_zero():
    stops = _ring(9, seed=1)
    o = wr.tidy_order(stops, True, 4)
    assert o[0] == 4 and wr.crossing_legs(stops, o, True) == []


def test_tidy_order_on_walk_5_matches_the_diagnosis():
    fx = _fixture("walk5_stops.json")
    stops = fx["stops"]
    cur = list(range(len(stops)))
    assert len(wr.crossing_legs(stops, cur, True)) == 3
    o = wr.tidy_order(stops, True, 0, cur)
    assert o[0] == 0 and wr.crossing_legs(stops, o, True) == []
    old = {frozenset(e) for e in wr.order_legs(cur, True)}
    changed = [e for e in wr.order_legs(o, True) if frozenset(e) not in old]
    assert len(changed) == 13, changed
    assert round(wr.order_length_m(stops, o, True)) == 6015


def test_tidy_order_rejects_a_bad_given_order():
    stops = _ring(5)
    for bad in ([1, 0, 2, 3, 4], [0, 1, 2, 3], [0, 1, 1, 3, 4]):
        try:
            wr.tidy_order(stops, True, 0, bad)
        except wr.RouteError:
            continue
        raise AssertionError(bad)


# ── Item 1: reversed stored legs are kept ────────────────────────────────────

# 200 m square: A SW, B NE, C SE, D NW; saved circular order A B C D (A-B and
# C-D cross). Metres → degrees at lat 47.71.
DLAT, DLNG = 1 / 111320.0, 1 / 74930.0
BASE = (47.71, 7.82)


def _p(x, y):
    return {"lat": BASE[0] + y * DLAT, "lng": BASE[1] + x * DLNG}


SQ = [_p(0, 0), _p(200, 200), _p(200, 0), _p(0, 200)]


def _square_route(dashed_bc=False):
    coords = [[s["lng"], s["lat"]] for s in SQ] + [[SQ[0]["lng"], SQ[0]["lat"]]]
    meta = {"version": 2, "circular": True, "stop_radius_m": 30}
    if dashed_bc:
        meta["straight_ranges"] = [[1, 2]]                    # B→C stored dashed
    return {"type": "FeatureCollection", "foragingid": meta,
            "features": [{"type": "Feature", "properties": {}, "geometry": {"type": "LineString", "coordinates": coords}}]}


def test_plan_reroute_keeps_a_stored_leg_walked_backwards_with_its_dash():
    route = _square_route(dashed_bc=True)
    wps = [dict(s, type="obs") for s in SQ]
    o = wr.tidy_order(wps, True, 0, [0, 1, 2, 3])
    assert o == [0, 2, 1, 3], o                                # A C B D: south and north sides
    new = [{"lat": wps[k]["lat"], "lng": wps[k]["lng"], "old_index": k} for k in o]
    plan = wr.plan_reroute(wps, route, new)
    kinds = [(l["kind"], l["reverse"]) for l in plan["legs"]]
    assert kinds == [("route", False), ("keep", True), ("route", False), ("keep", False)], kinds
    routed = {(l["i"], l["j"]): {"coords": [[new[l["i"]]["lng"], new[l["i"]]["lat"]],
                                            [new[l["j"]]["lng"], new[l["j"]]["lat"]]]}
              for l in plan["legs"] if l["kind"] == "route"}
    out, length, _ = wr.assemble_reroute(route, new, plan, routed)
    coords = wr.line_coords(out)
    assert [tuple(c) for c in coords] == [tuple([s["lng"], s["lat"]]) for s in (SQ[0], SQ[2], SQ[1], SQ[3], SQ[0])]
    # The stored dashed B→C leg is now C→B (segment 1) and stays dashed.
    assert wr.straight_ranges(out["foragingid"], len(coords)) == [[1, 2]]
    assert abs(length - 800) < 2


def test_plan_reroute_forward_legs_unchanged():
    route = _square_route()
    wps = [dict(s, type="obs") for s in SQ]
    new = [{"lat": w["lat"], "lng": w["lng"], "old_index": k} for k, w in enumerate(wps)]
    plan = wr.plan_reroute(wps, route, new)
    assert all(l["kind"] == "keep" and not l["reverse"] for l in plan["legs"]) and plan["runs"] == []


# ── Item 1: the endpoint ─────────────────────────────────────────────────────

def _walk_db(extra_obs=False):
    path = os.path.join(tempfile.mkdtemp(prefix="tidytest_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    S = async_sessionmaker(eng, expire_on_commit=False)

    async def seed():
        async with S() as s:
            wps = []
            for k, st in enumerate(SQ):
                s.add(Observation(id=10 + k, file_path=f"/x/{k}.jpg", latitude=st["lat"], longitude=st["lng"],
                                  species_primary=f"Species {k}", review_status="approved",
                                  identification_status="identified", photo_taken_at=datetime(2026, 5, 1)))
                wps.append({"type": "obs", "lat": st["lat"], "lng": st["lng"], "obs_ids": [10 + k],
                            "labels": [f"Species {k}"]})
            if extra_obs:      # 15 m south of the new A→C leg, ~80 m from every stored leg
                q = _p(100, -15)
                s.add(Observation(id=99, file_path="/x/99.jpg", latitude=q["lat"], longitude=q["lng"],
                                  species_primary="Species X", review_status="approved",
                                  identification_status="identified", photo_taken_at=datetime(2026, 6, 1)))
            s.add(SavedWalk(id=1, name="Square", waypoints_json=json.dumps(wps), obs_ids_json=json.dumps([10, 11, 12, 13]),
                            route_geojson=json.dumps(_square_route()), distance_m=966.0, duration_min=12,
                            members_since=datetime(2020, 1, 1), created_at=datetime(2026, 1, 1)))
            await s.commit()
    _run(seed())

    async def _get_db():
        async with S() as s:
            yield s
    api = FastAPI()
    api.include_router(walk_api.router)
    api.dependency_overrides[get_db] = _get_db
    api.dependency_overrides[get_identity] = lambda: CURATOR
    return TestClient(api), eng, S


def _row(S):
    async def q():
        async with S() as s:
            w = await s.get(SavedWalk, 1)
            return {c.key: getattr(w, c.key) for c in SavedWalk.__table__.columns}
    return _run(q())


class _Fakes:
    """ORS returns the straight line through the requested points; the snapshot
    hook records its calls."""
    def __enter__(self):
        self.ors, self.snaps = [], []
        self._o, self._s = walk_api._ors_post, walk_api._reroute_snapshot

        async def ors(coords):
            self.ors.append(coords)
            return {"features": [{"geometry": {"coordinates": coords},
                                  "properties": {"way_points": list(range(len(coords)))}}]}

        async def snap(wid):
            self.snaps.append(wid)
            return "snapshots/db_test.sqlite"
        walk_api._ors_post, walk_api._reroute_snapshot = ors, snap
        return self

    def __exit__(self, *a):
        walk_api._ors_post, walk_api._reroute_snapshot = self._o, self._s


def test_tidy_dry_run_writes_nothing():
    c, eng, S = _walk_db()
    try:
        before = _row(S)
        with _Fakes() as f:
            r = c.post("/api/walk/saves/1/tidy", json={"confirm": False})
            assert r.status_code == 200, r.text
            d = r.json()
            assert f.ors == [] and f.snaps == []                  # no ORS, no snapshot
        assert d["dry_run"] and d["crossings_before"] == 1 and d["crossings_after"] == 0
        assert d["order"] == ["1", "3", "2", "4"] and d["legs_changed"] == ["1→3", "2→4"]
        assert d["legs_kept"] == 2 and d["legs_kept_reversed"] == 1 and d["ors_requests"] == 2
        assert abs(d["estimated_distance_m"] - 800) <= 2 and d["distance_before_m"] == 966.0
        assert _row(S) == before
    finally:
        _run(eng.dispose())


def test_tidy_confirm_writes_new_order_members_unchanged_and_reads_back():
    c, eng, S = _walk_db()
    try:
        before = _row(S)
        with _Fakes() as f:
            r = c.post("/api/walk/saves/1/tidy", json={"confirm": True})
            assert r.status_code == 200, r.text
            out = r.json()
            assert f.snaps == [1] and len(f.ors) == 2               # only the 2 new legs
        after = _row(S)
        wps = json.loads(after["waypoints_json"])
        assert [w["obs_ids"] for w in wps] == [[10], [12], [11], [13]]         # stops unchanged, new order
        assert after["obs_ids_json"] == before["obs_ids_json"]                  # members' saved ids unchanged
        assert sorted(out["membership"]["member_obs_ids"]) == [10, 11, 12, 13]
        assert abs(after["distance_m"] - 800) <= 2 and out["tidy"]["crossings_after"] == 0
        assert wps[0] == json.loads(before["waypoints_json"])[0]               # stop 1 unchanged
        assert c.post("/api/walk/saves/1/tidy", json={"confirm": False}).status_code == 409   # already tidy
    finally:
        _run(eng.dispose())


def test_tidy_refused_when_members_would_change():
    c, eng, S = _walk_db(extra_obs=True)
    try:
        before = _row(S)
        with _Fakes():
            r = c.post("/api/walk/saves/1/tidy", json={"confirm": True})
        assert r.status_code == 409, r.text
        det = r.json()["detail"]
        assert det["would_join"] == [99] and det["would_leave"] == []
        assert _row(S) == before                                   # nothing written
    finally:
        _run(eng.dispose())


def test_build_walk_tidy_order_endpoint():
    c, eng, S = _walk_db()
    try:
        r = c.post("/api/walk/tidy-order", json={"stops": SQ, "circular": True})
        assert r.status_code == 200 and r.json()["order"][0] == 0
        assert wr.crossing_legs(SQ, r.json()["order"], True) == []
        assert c.post("/api/walk/tidy-order", json={"stops": [{"lat": "x"}]}).status_code == 422
    finally:
        _run(eng.dispose())


def test_build_walk_uses_the_server_order():
    from index_source import index_source   # batch 16: split page, read re-inlined
    src = index_source()
    assert src.count("await _tidyRoute(_clusterStops(") == 2
    assert "_nnRoute(_clusterStops(" not in src


# ── Item 2: warning review cards ─────────────────────────────────────────────

PREP = "PFAF-PREP sentinel: cook thoroughly."
LOOK = "LOOK sentinel: resembles hemlock."
# id, name, verdict, severity
SP = [(1, "Allium ursinum", "edible", "none"), (2, "Frangula alnus", "toxic", "toxic"),
      (3, "Aconitum napellus", "toxic", "deadly"), (4, "Symphytum officinale", "caution", "none")]


def _warn_db():
    path = os.path.join(tempfile.mkdtemp(prefix="warntest_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    S = async_sessionmaker(eng, expire_on_commit=False)

    async def seed():
        async with S() as s:
            for sid, name, verdict, sev in SP:
                s.add(Species(id=sid, scientific_name=name, name_key=normalize_taxon_key(name),
                              edibility_status=verdict, toxicity_severity=sev, kingdom="Plantae"))
                look = LOOK if sid == 4 else None
                s.add(CulinaryInfo(id=100 + sid, species_id=sid, preparation_warnings=PREP, look_alike_warnings=look))
                for field, text in (("preparation_warnings", PREP), ("look_alike_warnings", look)):
                    if text:
                        s.add(SpeciesAIDraft(species_id=sid, field_name=field, draft_text=text, status="pending",
                                             model="unknown_origin", generated_at=datetime(2026, 10, 21),
                                             generation_context_json=json.dumps({"field_text_at_import": text})))
            s.add(SpeciesAIDraft(species_id=1, field_name="taste_notes", draft_text="Garlicky.", status="pending",
                                 model="ai", generated_at=datetime(2026, 10, 21)))
            await s.commit()
    _run(seed())

    async def _get_db():
        async with S() as s:
            yield s
    api = FastAPI()
    api.include_router(culinary_api.router)
    api.dependency_overrides[get_db] = _get_db
    api.dependency_overrides[get_identity] = lambda: CURATOR
    return TestClient(api), eng, S


def _q(S, fn):
    async def q():
        async with S() as s:
            return await fn(s)
    return _run(q())


def _field(S, sid, col):
    return _q(S, lambda s: s.scalar(select(getattr(CulinaryInfo, col)).where(CulinaryInfo.species_id == sid)))


def _hist(S, sid, col):
    return _q(S, lambda s: s.execute(select(CulinaryInfoHistory.changed_by, CulinaryInfoHistory.old_value,
                                            CulinaryInfoHistory.new_value)
                                     .where(CulinaryInfoHistory.culinary_info_id == 100 + sid,
                                            CulinaryInfoHistory.field_name == col))).all()


def _draft(S, sid, col):
    return _q(S, lambda s: s.scalar(select(SpeciesAIDraft).where(SpeciesAIDraft.species_id == sid,
                                                                SpeciesAIDraft.field_name == col)))


def _served(S, name):
    return _q(S, lambda s: safety_by_names(s, [name]))[name]


def test_approve_drops_not_yet_reviewed_everywhere():
    c, eng, S = _warn_db()
    try:
        assert _served(S, "Symphytum officinale")["warnings"]["look_alike"]["reviewed"] is False
        assert _served(S, "Symphytum officinale")["handout_warnings"]["look_alike"] is None
        r = c.post("/api/species/Symphytum officinale/drafts/look_alike_warnings/approve", json={})
        assert r.status_code == 200, r.text                     # 2b: look-alike joins CURATOR_DRAFT_FIELDS
        d = _served(S, "Symphytum officinale")                  # the decision every surface reads
        assert d["warnings"]["look_alike"] == {"text": LOOK, "reviewed": True}
        assert d["handout_warnings"]["look_alike"] == LOOK
        assert _hist(S, 4, "look_alike_warnings") == [("human", LOOK, LOOK)]
        # Edit then approve: the curator's text, human history row.
        r = c.post("/api/species/Allium ursinum/drafts/preparation_warnings/approve",
                   json={"edited_text": "Own words: cook it."})
        assert r.status_code == 200 and _field(S, 1, "preparation_warnings") == "Own words: cook it."
        assert _served(S, "Allium ursinum")["warnings"]["preparation"]["reviewed"] is True
    finally:
        _run(eng.dispose())


def test_remove_clears_the_field_with_a_human_history_row():
    c, eng, S = _warn_db()
    try:
        r = c.post("/api/species/Frangula alnus/drafts/preparation_warnings/remove")
        assert r.status_code == 200, r.text
        assert _field(S, 2, "preparation_warnings") is None
        assert _hist(S, 2, "preparation_warnings") == [("human", PREP, None)]
        dr = _draft(S, 2, "preparation_warnings")
        assert dr.status == "rejected" and json.loads(dr.generation_context_json)["removed_field"] is True
        d = _served(S, "Frangula alnus")
        assert d["warnings"]["preparation"] is None and d["handout_warnings"]["preparation_is_fallback"] is True
        assert c.post("/api/species/Frangula alnus/drafts/preparation_warnings/remove").status_code == 404
    finally:
        _run(eng.dispose())


def test_remove_refused_for_a_deadly_species():
    c, eng, S = _warn_db()
    try:
        r = c.post("/api/species/Aconitum napellus/drafts/preparation_warnings/remove")
        assert r.status_code == 409, r.text
        assert _field(S, 3, "preparation_warnings") == PREP and _hist(S, 3, "preparation_warnings") == []
        assert _draft(S, 3, "preparation_warnings").status == "pending"
    finally:
        _run(eng.dispose())


def test_approve_and_remove_refused_when_the_field_changed_since_drafting():
    c, eng, S = _warn_db()
    try:
        async def change(s):
            ci = await s.get(CulinaryInfo, 101)
            ci.preparation_warnings = "Changed by enrichment after the draft."
            await s.commit()
        _q(S, change)
        for verb, body in (("approve", {}), ("approve", {"edited_text": "x"}), ("remove", None)):
            r = c.post(f"/api/species/Allium ursinum/drafts/preparation_warnings/{verb}", json=body)
            assert r.status_code == 409, (verb, r.status_code, r.text)
        assert _field(S, 1, "preparation_warnings") == "Changed by enrichment after the draft."
        assert _hist(S, 1, "preparation_warnings") == []
    finally:
        _run(eng.dispose())


def test_queue_sorts_walk_species_first_and_marks_removable():
    c, eng, S = _warn_db()
    orig = walk_api.species_on_saved_walks

    async def fake(db):
        return {"Symphytum officinale": ["Square"], "Frangula alnus": ["Square"]}
    walk_api.species_on_saved_walks = fake
    try:
        d = c.get("/api/culinary/ai-draft-review").json()
        assert [x["scientific_name"] for x in d] == ["Frangula alnus", "Symphytum officinale",
                                                     "Aconitum napellus", "Allium ursinum"]
        rem = {(x["scientific_name"], dr["field_name"]): dr.get("removable") for x in d for dr in x["drafts"]}
        assert rem[("Aconitum napellus", "preparation_warnings")] is False
        assert rem[("Frangula alnus", "preparation_warnings")] is True
        assert rem[("Allium ursinum", "taste_notes")] is None            # not a warning card
    finally:
        walk_api.species_on_saved_walks = orig
        _run(eng.dispose())


def test_reject_route_keeps_an_optional_reason_and_works_without_a_body():
    c, eng, S = _warn_db()
    try:
        r = c.post("/api/species/Allium ursinum/drafts/taste_notes/reject",
                   json={"reason": "Melvin census 22 Oct: placeholder — no medicinal content"})
        assert r.status_code == 200 and r.json()["reason"].startswith("Melvin census 22 Oct:"), r.text
        d = _draft(S, 1, "taste_notes")
        ctx = json.loads(d.generation_context_json)
        assert d.status == "rejected" and ctx["rejected_reason"] == "Melvin census 22 Oct: placeholder — no medicinal content"
        assert ctx["rejected_at"]
        # No body: rejected as before, no reason stored.
        r = c.post("/api/species/Frangula alnus/drafts/preparation_warnings/reject")
        assert r.status_code == 200 and r.json()["reason"] is None
        dr = _draft(S, 2, "preparation_warnings")
        assert dr.status == "rejected" and "rejected_reason" not in json.loads(dr.generation_context_json)
    finally:
        _run(eng.dispose())


def _fn(src, name):
    m = re.search(r"^(async )?function %s\(" % re.escape(name), src, re.M)
    i = src.index("{", m.end())
    depth = 0
    for k in range(i, len(src)):
        depth += {"{": 1, "}": -1}.get(src[k], 0)
        if depth == 0:
            return src[m.start():k + 1]


def test_warning_cards_stay_out_of_approve_all_and_offer_remove():
    src = open(os.path.join(ROOT, "frontend/review.html"), encoding="utf-8").read()
    consts = "\n".join(re.search(p, src, re.S).group(0) for p in (
        r"const _CURATOR_DRAFT_FIELDS = new Set\([^;]+\);", r"const _WARNING_DRAFT_ORIGIN = \{.*?\n\};"))
    js = ("var window = this;\n" + open(os.path.join(ROOT, "frontend/static/js/esc.js"), encoding="utf-8").read() + "\n"
          + open(os.path.join(ROOT, "frontend/static/js/species-names.js"), encoding="utf-8").read()
          + "\n" + _fn(src, "_resc") + "\nconst _esc = _resc;\n" + _fn(src, "_escId") + "\n" + _fn(src, "_fieldLabel")
          + "\n" + consts + "\n" + _fn(src, "_renderAIDraftField") + "\n" + _fn(src, "_renderAIDraftCard") + """
function card(removable) {
  return _renderAIDraftCard({ scientific_name: 'Aconitum napellus', common_names: [], thumbnails: [], on_walks: ['Square'],
    drafts: [{ id: 1, field_name: 'taste_notes', draft_text: 'T', model: 'ai' },
             { id: 2, field_name: 'look_alike_warnings', draft_text: 'L', model: 'unknown_origin', current_text: 'L', removable: removable },
             { id: 3, field_name: 'preparation_warnings', draft_text: 'P', model: 'pfaf', current_text: 'P', removable: removable }] });
}
print(JSON.stringify({ yes: card(true), no: card(false) }));
""")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
    out = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=60)
    os.unlink(f.name)
    assert out.returncode == 0, out.stderr or out.stdout
    html = json.loads(out.stdout.strip().splitlines()[-1])
    yes, no = html["yes"], html["no"]
    assert "Approve all 1 draft for this species (not the review cards or two-version fields)" in yes
    assert yes.count('class="ai-draft-field ai-draft-safety"') == 2              # both warning fields
    assert yes.count("removeWarningField(") == 2 and "removeWarningField(" not in no   # no Remove on deadly
    assert "Look-alike warning" in yes and "🚶 On walk: Square" in yes
    # Approve all (and Approve selected, which calls it) skips .ai-draft-safety.
    fn = _fn(src, "approveAllDrafts")
    assert ".ai-draft-field:not(.ai-draft-safety)" in fn


if __name__ == "__main__":
    for _name, _f in list(globals().items()):
        if _name.startswith("test_") and callable(_f):
            _f()
            print("ok", _name)
