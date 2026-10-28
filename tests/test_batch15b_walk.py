"""
Batch 15b — walk changes (Melvin, 28 Oct 2026). Code checks only; every gesture
is on Melvin's live walkthrough list.

  * Loop / One-way is a LABEL: "Loop" when the last stop is within 600 m of
    stop 1. walk_route.loop_label and index.html _walkLoopLabel agree; every
    saved walk in the live DB (read-only) is labelled; the toggle is gone, the
    PATCH …/loop endpoint and the stored flag stay.
  * Start here on an open line: walk_route.start_from_middle gives k…N, then
    back k−1…1; the re-route keeps the stored legs (k…N forward, 1…k−1
    backwards) and routes only N → k−1; dry run writes nothing; a closed line
    and stop 1 are refused. The panel offers Start here on every saved stop.
  * Empty saved stops: renumbered_snapshot drops a stop with no species (notes
    kept); the panel, the map markers and the Export summary hide it; Save
    changes opens the Re-route preview when a stop is left empty.
  * GPS recording: the three start controls are hidden, the FAB is never
    shown by JS; the recording code, IndexedDB store, upload button and
    endpoints are still there. Upload buttons are hidden from guests.
  * Edit walk: tapping a stop marks all its photos for removal; the lasso in
    Edit walk toggles pins (same rule as a tap) and never touches the
    Foraging List; leaving walk mode never re-adds the route layer.

Run from project root:  python tests/test_batch15b_walk.py
"""
import json
import os
import pathlib
import re
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import test_route_order_and_warning_review as rt  # noqa: E402
import app.api.walk as walk_api  # noqa: E402
from app.api.identity import get_identity  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.models.observation import Observation  # noqa: E402
from app.models.walk import SavedWalk  # noqa: E402
from app.services import walk_membership as wm  # noqa: E402
from app.services import walk_route as wr  # noqa: E402

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"


def _src(p):
    return pathlib.Path(ROOT, p).read_text(encoding="utf-8")


def _fn(src, name):
    i = src.index(f"function {name}(")
    depth, j = 0, src.index("{", i)
    while True:
        if src[j] == "{": depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0: return src[i:j + 1]
        j += 1


def _jsc(script):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(script)
    out = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=60)
    os.unlink(f.name)
    assert out.returncode == 0 and out.stdout.strip(), out.stderr
    return json.loads(out.stdout.strip().split("\n")[-1])


# ── Loop / One-way label ─────────────────────────────────────────────────────

def _two(d_m):
    return [rt._p(0, 0), rt._p(50, 300), rt._p(d_m, 0)]


def test_loop_label_python():
    assert wr.LOOP_LABEL_MAX_M == 600.0
    for d, want in ((142, "Loop"), (576, "Loop"), (599, "Loop"), (601, "One-way"), (2000, "One-way")):
        assert wr.loop_label(_two(d)) == want, (d, wr.loop_label(_two(d)))
    assert wr.loop_label([]) is None and wr.loop_label([rt._p(0, 0)]) is None
    assert wr.loop_label([{"type": "note"}, rt._p(0, 0)]) is None


def test_loop_label_js_twin_matches():
    idx = _src("frontend/index.html")
    assert "const _WALK_LOOP_LABEL_MAX_M = 600;" in idx
    cases = [_two(d) for d in (142, 576, 599, 601, 2000)] + [[], [rt._p(0, 0)]]
    js = _jsc("const _WALK_LOOP_LABEL_MAX_M = 600;\n" + _fn(idx, "_haversineM") + "\n" + _fn(idx, "_walkLoopLabel") +
              "\nprint(JSON.stringify(" + json.dumps(cases) + ".map(_walkLoopLabel)));")
    assert js == [wr.loop_label(c) for c in cases], js


def test_every_saved_walk_is_labelled():
    db = pathlib.Path(ROOT, "data/foragingid.db")
    if not db.exists():
        return
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        labels = {wid: wr.loop_label([w for w in json.loads(wp or "[]") if isinstance(w, dict)])
                  for wid, wp in con.execute("SELECT id, waypoints_json FROM saved_walks")}
    finally:
        con.close()
    for wid in (1, 3, 4, 5):
        if wid in labels:
            assert labels[wid] == "Loop", (wid, labels[wid])          # walk 3 (576 m) is a loop at 600 m
    print("  walk labels:", labels)


def test_toggle_gone_label_shown_endpoint_kept():
    idx = _src("frontend/index.html")
    assert 'id="walk-loop-btn"' not in idx and "function toggleWalkLoop(" not in idx
    assert 'id="walk-loop-label"' in idx
    assert "_syncWalkLoopUi();                 // Loop / One-way label follows the rendered route" in idx
    assert "let _walkCircular     = true;" in idx                      # new walks: the old default
    assert '@router.patch("/saves/{walk_id}/loop")' in _src("app/api/walk.py")


# ── Start here on an open line ───────────────────────────────────────────────

OPEN = [rt._p(100 * k, 0) for k in range(5)]                 # 5 stops in a line, 100 m apart


def _open_route():
    return {"type": "FeatureCollection", "foragingid": {"version": 2, "circular": False, "stop_radius_m": 30},
            "features": [{"type": "Feature", "properties": {},
                          "geometry": {"type": "LineString", "coordinates": [[s["lng"], s["lat"]] for s in OPEN]}}]}


def test_start_from_middle_order_and_kept_legs():
    assert wr.start_from_middle(list("ABCDE"), 2) == list("CDEBA")
    for bad in (0, 5, -1):
        try:
            wr.start_from_middle(list("ABCDE"), bad)
        except wr.RouteError:
            continue
        raise AssertionError(bad)
    wps = [dict(s, type="obs") for s in OPEN]
    order = wr.start_from_middle(list(range(5)), 2)
    new = [{"lat": wps[k]["lat"], "lng": wps[k]["lng"], "old_index": k} for k in order]
    plan = wr.plan_reroute(wps, _open_route(), new)
    kinds = [(l["kind"], l["reverse"]) for l in plan["legs"]]
    assert kinds == [("keep", False), ("keep", False), ("route", False), ("keep", True)], kinds
    assert plan["runs"] == [[2, 3]] and not plan["closed"]


def _open_db():
    path = os.path.join(tempfile.mkdtemp(prefix="b15b_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    S = async_sessionmaker(eng, expire_on_commit=False)

    async def seed():
        async with S() as s:
            wps = []
            for k, st in enumerate(OPEN):
                s.add(Observation(id=20 + k, file_path=f"/x/b15b_{k}.jpg", latitude=st["lat"], longitude=st["lng"],
                                  species_primary=f"Species {k}", review_status="approved",
                                  identification_status="identified", photo_taken_at=datetime(2026, 5, 1)))
                wps.append({"type": "obs", "lat": st["lat"], "lng": st["lng"], "obs_ids": [20 + k],
                            "labels": [f"Species {k}"]})
            s.add(SavedWalk(id=1, name="Line", waypoints_json=json.dumps(wps), obs_ids_json=json.dumps([20, 21, 22, 23, 24]),
                            route_geojson=json.dumps(_open_route()), distance_m=400.0, duration_min=5,
                            members_since=datetime(2020, 1, 1), created_at=datetime(2026, 1, 1)))
            await s.commit()
    rt._run(seed())

    async def _get_db():
        async with S() as s:
            yield s
    api = FastAPI()
    api.include_router(walk_api.router)
    api.dependency_overrides[get_db] = _get_db
    api.dependency_overrides[get_identity] = lambda: rt.CURATOR
    return TestClient(api), eng, S


def test_reroute_start_here_dry_run_then_confirm():
    c, eng, S = _open_db()
    try:
        before = rt._row(S)
        with rt._Fakes() as f:
            r = c.post("/api/walk/saves/1/reroute", json={"confirm": False, "start_label": "3"})
            assert r.status_code == 200, r.text
            d = r.json()
            assert f.ors == [] and f.snaps == []
        assert d["dry_run"] and d["start_label"] == "3"
        assert d["legs_to_route"] == ["5→2"] and d["legs_kept"] == 3 and d["ors_requests"] == 1, d
        assert rt._row(S) == before                                   # dry run writes nothing
        with rt._Fakes() as f:
            r = c.post("/api/walk/saves/1/reroute", json={"confirm": True, "start_label": "3"})
            assert r.status_code == 200, r.text
            assert f.snaps == [1] and len(f.ors) == 1                  # one new leg
        wps = json.loads(rt._row(S)["waypoints_json"])
        assert [w["obs_ids"] for w in wps] == [[22], [23], [24], [21], [20]]
        for bad, code in (("1", 409), ("9", 409)):
            assert c.post("/api/walk/saves/1/reroute", json={"confirm": False, "start_label": bad}).status_code == code
    finally:
        rt._run(eng.dispose())


def test_reroute_start_here_refused_on_a_closed_line():
    c, eng, S = rt._walk_db()
    try:
        with rt._Fakes():
            r = c.post("/api/walk/saves/1/reroute", json={"confirm": False, "start_label": "2"})
        assert r.status_code == 409 and "closed loop" in r.json()["detail"], r.text
    finally:
        rt._run(eng.dispose())


def test_panel_offers_start_here_on_every_saved_stop():
    idx = _src("frontend/index.html")
    assert "const _canStartHere = !!(_savedWalkData && !_joinedStop && _isSavedRoute" in idx
    assert "onclick=\"walkStartHere(${lmJsArg(_stopLabel(_stop, i))})\"" in idx
    f = _fn(idx, "walkStartHere")
    assert "if (_walkLineClosed) walkReorder('start', label);" in f and "else walkReroute(label);" in f
    rr = idx[idx.index("async function walkReroute(startLabel)"):]
    assert "body: JSON.stringify({ confirm: false, start_label: start })" in rr
    assert "_walkMembershipCall('reroute', 'POST', { confirm: true, start_label: start })" in rr


# ── Empty saved stops ────────────────────────────────────────────────────────

def test_renumber_drops_empty_stops_keeps_notes():
    stops = [
        {"is_note": False, "_wp": {"type": "obs", "lat": 1, "lng": 1}, "lat": 1, "lng": 1, "obs_ids": [1],
         "species": [{"name": "A"}]},
        {"is_note": False, "_wp": {"type": "obs", "lat": 2, "lng": 2}, "lat": 2, "lng": 2, "obs_ids": [2], "species": []},
        {"is_note": True, "_wp": {"type": "note", "note_id": 7}},
        {"is_note": False, "_wp": {"type": "obs", "lat": 3, "lng": 3}, "lat": 3, "lng": 3, "obs_ids": [3],
         "species": [{"name": "C"}]},
    ]
    wps, ids = wm.renumbered_snapshot({"stops": stops})
    assert [w.get("obs_ids") or w.get("note_id") for w in wps] == [[1], 7, [3]], wps
    assert ids == [1, 3]


def test_empty_stops_hidden_on_render_and_drop_on_save():
    idx = _src("frontend/index.html")
    pred = _fn(idx, "_walkStopEmpty")
    assert "_stopSpecies(stop).length === 0" in pred and "is_note" in pred
    panel = idx[idx.index("function renderWalkPanel("):]
    assert "if (_walkStopEmpty(_stop)) continue;" in panel[:panel.index("No confirmed species here now")]
    draw = _fn(idx, "_drawWalkLayer")
    assert draw.index("if (_walkStopEmpty(s)) return [s.lat, s.lng];") < draw.index("L.marker(")
    assert "stops: stops.filter((_, i) => !_walkStopEmpty(_activeWalkRoute[i]))," in idx
    save = idx[idx.index("async function walkSaveChanges("):]
    save = save[:save.index("\n}\n")]
    assert "const _emptied = (_activeWalkRoute || []).some(_walkStopEmpty);" in save
    assert "if (adds.some(id => mem.has(id)) || _emptied) setTimeout(walkReroute, 0);" in save
    js = _jsc(_fn(idx, "_stopSpecies") + "\n" + _fn(idx, "_walkStopEmpty") + """
print(JSON.stringify([
  _walkStopEmpty({ p: { species_primary: null, is_note: false }, species: [] }),
  _walkStopEmpty({ p: { species_primary: 'A', is_note: false }, species: ['A'] }),
  _walkStopEmpty({ p: { species_primary: null, is_note: true }, species: [] }),
  _walkStopEmpty(null)]));""")
    assert js == [True, False, False, False], js


# ── GPS recording hidden from the interface ──────────────────────────────────

def test_recording_start_controls_hidden_code_kept():
    idx = _src("frontend/index.html")
    assert ".rec-ui-off { display: none !important; }" in idx and "const WALK_RECORDING_UI = false;" in idx
    for ctl in ('<button id="wrec-float-btn" class="rec-ui-off"',
                '<button class="wbs-qb-btn rec-ui-off" data-guest-hide onclick="_wbsStartRecording()">',
                '<div class="wbs-entry-card rec-ui-off" data-guest-hide onclick="_wbsStartRecording()">'):
        assert ctl in idx, ctl
    for m in re.finditer(r"<[^>]*onclick=\"_wbsStartRecording\(\)\"[^>]*>|<[^>]*_wrecToggle\(\)[^>]*>", idx):
        assert "rec-ui-off" in m.group(0), m.group(0)                 # every start control hidden
    assert "if (_wrecBtn && WALK_RECORDING_UI) _wrecBtn.style.display = 'flex';" in idx
    # kept: recording code, IndexedDB, sync/flush, walk-record.js, endpoints
    for keep in ("function _wrecToggle()", "window._wbsStartRecording = function()", "_walkSyncPending",
                 "_walkIdbGetPending", "foragingid_walks", '<script src="/static/js/walk-record.js"></script>',
                 'id="wbs-sync-btn" onclick="_walkSyncPending()"'):
        assert keep in idx, keep
    assert '@router.post("")' in _src("app/api/recorded_walks.py") or "router.post" in _src("app/api/recorded_walks.py")
    assert '<div id="wbs-upload" data-guest-hide>' in idx
    assert '<button id="walk-sync-btn" data-guest-hide onclick="_walkSyncPending()">' in idx


# ── Edit walk gestures ───────────────────────────────────────────────────────

def test_edit_walk_stop_tap_and_lasso():
    idx = _src("frontend/index.html")
    js = _jsc("var _walkPinSel = {}; var _walkPending = { add: new Set([12]), remove: new Set() };\n"
              "var _synced = 0; function _syncWalkSaveBtn() { _synced++; } function renderMarkers() {}\n"
              "var _walkRouteLayer = null; function setTimeout(f) {}\n"
              "var _members = new Set([10, 11, 12]); function _walkMemberSet() { return _members; }\n"
              + _fn(idx, "_walkStopIds") + "\n" + _fn(idx, "_walkStopMarked") + "\n" + _fn(idx, "_walkStopToggle")
              + "\n" + _fn(idx, "_walkLassoToggle") + """
var stop = { p: { is_note: false }, obs_ids: [10, 11], joined_obs_ids: [12] };
var r = {};
_walkStopToggle(stop);
r.marked = [..._walkPending.remove].sort(); r.addLeft = [..._walkPending.add]; r.isMarked = _walkStopMarked(stop);
_walkStopToggle(stop);
r.unmarked = [..._walkPending.remove];
_walkStopToggle({ p: { is_note: true }, obs_ids: [99] });
r.noteIgnored = [..._walkPending.remove];
var n = _walkLassoToggle([{ id: 10 }, { id: 50 }, { id: null }]);
r.lasso = { n: n, add: [..._walkPending.add], remove: [..._walkPending.remove] };
_walkLassoToggle([{ id: 10 }, { id: 50 }]);
r.lasso2 = { add: [..._walkPending.add], remove: [..._walkPending.remove] };
print(JSON.stringify(r));""")
    assert js["marked"] == [10, 11, 12] and js["addLeft"] == [] and js["isMarked"] is True, js
    assert js["unmarked"] == [] and js["noteIgnored"] == []
    assert js["lasso"] == {"n": 2, "add": [50], "remove": [10]}, js["lasso"]
    assert js["lasso2"] == {"add": [], "remove": []}, js["lasso2"]
    fin = _fn(idx, "_finishLassoDraw")
    assert fin.index("if (_walkPinSel) { _inBox.push(p); continue; }") < fin.index("ForagingList.add(")
    assert "const n = _walkLassoToggle(_inBox);" in fin
    draw = _fn(idx, "_drawWalkLayer")
    assert "if (!s.p.is_note) stopMk.on('click', () => _walkStopToggle(s));" in draw
    exit_ = _fn(idx, "_walkPinSelExit")
    assert "if (_lassoActive) _exitLassoSelect();" in exit_
    assert "if (_walkRouteLayer && _activeWalkRoute) _drawWalkLayer(true);" in exit_
    # _exitWalkMode removes the layer BEFORE it calls _walkPinSelExit — and the guard keeps it removed
    ew = idx[idx.index("if (_walkRouteLayer) { map.removeLayer(_walkRouteLayer); _walkRouteLayer = null; }"):]
    assert ew.index("_walkRouteLayer = null; }") < ew.index("_walkPinSelExit();")
    assert 'id="walk-lasso-btn"' in idx and "if (lasso) lasso.style.display = _walkPinSel ? '' : 'none';" in idx


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
