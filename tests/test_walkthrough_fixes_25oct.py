"""
Tests for the bugs found by the 25 Oct 2026 automated walkthrough run.

  1. Saved walk load: leaflet.heat's redraw() reads this._map._animating, so a
     heat update while the layer is off the map (a loaded saved walk hides it)
     threw "Cannot read properties of null (reading '_animating')". Every heat
     update in index.html goes through _heatSetOptions / _heatSetLatLngs /
     _recalcHeatMax, which only store the data off the map. (The live load of
     walks 4 and 5 is checked by scripts/dev/walkthrough_check.py.)
  2. Find → 🍳 Make?: showDiscoverView's _exitWalkMode cleared _walkSaved before
     _openRecipesPage read it. The walk id is remembered first.
  3. Review notes: ObservationOut now carries reviewer_notes (the Review list
     reads it back after a reload); get_observation blanks it for guests.

No external calls; throw-away SQLite DB; page JS run in JavaScriptCore.

Run from project root:  python tests/test_walkthrough_fixes_25oct.py
"""
import asyncio
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main  # noqa: E402,F401  (registers every model on Base.metadata)
from app.api.identity import Identity  # noqa: E402
from app.api.observations import get_observation, list_observations  # noqa: E402
from app.database import Base  # noqa: E402
from app.models.observation import Observation  # noqa: E402

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
CURATOR = Identity(user_id=1, is_guest=False, is_anonymous_guest=False, workshop_session_id=None)
GUEST = Identity(user_id=None, is_guest=True, is_anonymous_guest=True, workshop_session_id=None)
NOTE = "Stem hairy — recheck the umbel next visit."


def _src(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def _fn(src, name):
    """Source of a top-level `function name(...) { ... }` in a page script."""
    i = src.index(f"function {name}(")
    return src[i:src.index("\n}\n", i) + 3]


def _jsc(js):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
        p = f.name
    try:
        out = subprocess.run([JSC, p], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(p)
    assert out.returncode == 0, out.stderr or out.stdout
    return json.loads(out.stdout.strip().splitlines()[-1])


# ── 1. heat layer off the map ────────────────────────────────────────────────

# A heat layer with leaflet.heat 0.2.0's own redraw/setOptions/setLatLngs: off
# the map (_map null) redraw() throws exactly as in the walkthrough.
_HEAT_STUB = r"""
var L = {
  setOptions: function (o, opts) { for (var k in opts) o.options[k] = opts[k]; },
  Util: { requestAnimFrame: function () { return 7; }, cancelAnimFrame: function () { cancelled++; } },
};
var cancelled = 0, removed = 0;
var heatLayer = {
  _map: null, _heat: {}, _frame: null, _latlngs: [], options: {max: 1}, updates: 0,
  _updateOptions: function () { this.updates++; },
  redraw: function () { if (this._heat && !this._frame && !this._map._animating) this._frame = 1; return this; },
  setOptions: function (o) { L.setOptions(this, o); this._updateOptions(); return this.redraw(); },
  setLatLngs: function (p) { this._latlngs = p; return this.redraw(); },
};
var map = { removeLayer: function (l) { removed++; l._map = null; },
            getZoom: function () { return 14; }, getCenter: function () { return {lat: 47.7}; },
            getBounds: function () { return { contains: function () { return true; } }; } };
var document = { getElementById: function () { return { value: '30' }; } };
var _heatPoints = [[47.7, 7.8, 1], [47.7001, 7.8001, 1]];
"""


def test_heat_updates_off_the_map_store_data_and_never_redraw():
    idx = _src("frontend/index.html")
    fns = "\n".join(_fn(idx, n) for n in ("_heatOnMap", "_heatSetOptions", "_heatSetLatLngs",
                                          "_heatRemove", "_recalcHeatMax"))
    js = "\n".join([_HEAT_STUB, fns,
                    "_heatSetOptions({radius: 40, blur: 10});",
                    "_heatSetLatLngs([[1, 2, 1]]);",
                    "_recalcHeatMax();",                       # zoomend from _fitSavedWalk while off the map
                    "var off = {radius: heatLayer.options.radius, latlngs: heatLayer._latlngs.length,"
                    " frame: heatLayer._frame, updates: heatLayer.updates, max: heatLayer.options.max};",
                    "heatLayer._map = {_animating: false};",
                    "_recalcHeatMax();",                       # back on the map: recalibrates and redraws
                    "var on = {max: heatLayer.options.max, frame: heatLayer._frame};",
                    "_heatRemove();",
                    "print(JSON.stringify({off: off, on: on, cancelled: cancelled, removed: removed,"
                    " frameAfter: heatLayer._frame}));"])
    out = _jsc(js)
    assert out["off"] == {"radius": 40, "latlngs": 1, "frame": None, "updates": 1, "max": 1}
    assert out["on"] == {"max": 2, "frame": 1}                   # back on the map: 2 close points → max 2, redrawn
    assert out["cancelled"] == 1 and out["removed"] == 1 and out["frameAfter"] is None


def test_every_heat_update_goes_through_the_guarded_helpers():
    idx = _src("frontend/index.html")
    helpers = "".join(_fn(idx, n) for n in ("_heatSetOptions", "_heatSetLatLngs", "_heatRemove"))
    rest = idx
    for h in (_fn(idx, "_heatSetOptions"), _fn(idx, "_heatSetLatLngs"), _fn(idx, "_heatRemove")):
        rest = rest.replace(h, "")
    for call in ("heatLayer.setOptions(", "heatLayer.setLatLngs(", "heatLayer.redraw(",
                 "heatLayer.addLatLng(", "removeLayer(heatLayer)"):
        assert call not in rest, f"{call} outside the guarded helpers"
    assert "heatLayer.setOptions(" in helpers and "removeLayer(heatLayer)" in helpers
    assert "if (!_heatOnMap()) return;" in _fn(idx, "_recalcHeatMax")
    # walk mode hides the layer through _applyLayer, which removes and re-adds it cleanly
    apply = _fn(idx, "_applyLayer")
    assert "{ map.addLayer(heatLayer); _recalcHeatMax(); }" in apply and "_heatRemove();" in apply


# ── 2. Find → Make? keeps the open walk ──────────────────────────────────────

def test_find_make_opens_recipes_for_the_walk_open_before_find():
    idx = _src("frontend/index.html")
    stub = r"""
var location = {href: ''};
var discover = {active: false, classList: {
  contains: function () { return discover.active; },
  add: function () { discover.active = true; }, remove: function () { discover.active = false; } }};
var document = { getElementById: function (id) {
  if (id === 'discover-view') return discover;
  return { style: {}, classList: { add: function () {}, remove: function () {}, toggle: function () {} },
           focus: function () {} }; } };
var _walkActive = true, _walkSaved = {id: 5, name: 'Morning sunshine'};
function _exitWalkMode() { _walkActive = false; _walkSaved = null; }
function _closeTabPanels() {} function openSidebar() {} function _applyLayer() {}
function _runFindMode() {} function _beginNearMe() {} function showFilterView() {}
var currentLayer = 'pins', _pinsExplicit = false, _findMode = 'season', _nearMePos = null, _nearMeResults = [];
"""
    decl = "let _discoverWalkId = null;"
    assert decl in idx
    js = "\n".join([stub, "var _discoverNearMeOn = false;", decl,
                    _fn(idx, "showDiscoverView"), _fn(idx, "_exitDiscoverView"), _fn(idx, "_openRecipesPage"),
                    "showDiscoverView(); _openRecipesPage(); var withWalk = location.href;",
                    "showDiscoverView(); _openRecipesPage(); var again = location.href;",   # chip tapped again
                    "_exitDiscoverView(); showDiscoverView(); _openRecipesPage(); var noWalk = location.href;",
                    "print(JSON.stringify({withWalk: withWalk, again: again, noWalk: noWalk}));"])
    out = _jsc(js)
    assert out["withWalk"] == "/recipes?walk=5"
    assert out["again"] == "/recipes?walk=5"
    assert out["noWalk"] == "/recipes"


# ── 3. reviewer notes come back in the Review list ───────────────────────────

def test_review_list_returns_reviewer_notes_and_guests_never_see_them():
    async def run():
        path = os.path.join(tempfile.mkdtemp(prefix="wt25_"), "t.db")
        Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
        eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
        S = async_sessionmaker(eng, expire_on_commit=False)
        async with S() as s:
            s.add(Observation(id=1, file_path="/tmp/a.jpg", file_hash="a", review_status="needs_review",
                              identification_status="identified", reviewer_notes=NOTE))
            s.add(Observation(id=2, file_path="/tmp/b.jpg", file_hash="b", review_status="approved",
                              identification_status="identified", species_primary="Urtica dioica",
                              reviewer_notes=NOTE))
            await s.commit()
        async with S() as s:
            rows = await list_observations(limit=500, offset=0, geotagged_only=False, no_gps=False,
                                           named_only=False, unnamed_only=False, review_status="needs_review",
                                           upload_source=None, obs_category=None, prefilter_category=None,
                                           review_label=None, q=None, exclude_not_plant=False,
                                           sort="date_desc", db=s)
            cur = await get_observation(2, db=s, identity=CURATOR)
            gst = await get_observation(2, db=s, identity=GUEST)
        await eng.dispose()
        return rows, cur, gst
    rows, cur, gst = asyncio.run(run())
    assert [(r["id"], r["reviewer_notes"]) for r in rows] == [(1, NOTE)]
    assert cur["reviewer_notes"] == NOTE
    assert gst["reviewer_notes"] is None and gst["id"] == 2


def test_review_card_fills_the_notes_box_from_the_list_row():
    rv = _src("frontend/review.html")
    assert "const notesVal = _resc(obs.reviewer_notes || '');" in rv
    assert 'placeholder="Add reviewer notes…" rows="2">${notesVal}</textarea>' in rv


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
