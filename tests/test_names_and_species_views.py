"""
Names in sentence case + species page views (Melvin, 21 Oct 2026).

Item 1 — English common names are shown in sentence case through the shared
helpers only: sentence_case_name / display_common_name (app/models/species.py)
and spCommon / spCommonList / spNameHtml / spNameText
(frontend/static/js/species-names.js). Stored names stay as sourced; German
names are never changed.

Item 2 — species.html Large / Grid / List views share one data set, one badge
reader (_spEdibBadge → SafetyGate) and select mode.

The JS is EXECUTED (macOS JavaScriptCore `jsc`, with small DOM stubs), not just
grepped: species-names.js, safety-gate.js and the view functions sliced out of
species.html. No browser — the live checks stay Melvin's.

Run: python tests/test_names_and_species_views.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import app.main  # noqa: E402,F401
import app.api.lists_pdf as lp  # noqa: E402
import app.api.sharing as sharing  # noqa: E402
from app.models.species import display_common_name, safety_decision, sentence_case_name  # noqa: E402

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"

NAME_CASES = [
    ("disc mayweed", "Disc mayweed"),               # lower-case → first letter only
    ("Disc mayweed", "Disc mayweed"),               # already capitalised
    ("St John's wort", "St John's wort"),           # apostrophe, rest untouched
    ("lady's bedstraw", "Lady's bedstraw"),
    ("Ragged Robin", "Ragged Robin"),               # sourced capitals kept
    ("3-leaved clover", "3-leaved clover"),         # non-letter start: unchanged
    ("'t Hooft's moss", "'t Hooft's moss"),
    ("élan weed", "Élan weed"),                     # non-ASCII letter
    ("", ""), (None, ""),
]


def _src(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def _jsc(script: str):
    """Run JS in JavaScriptCore; the script prints one JSON line."""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(script)
        path = f.name
    try:
        out = subprocess.run([JSC, path], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(path)
    assert out.returncode == 0, out.stderr or out.stdout
    return json.loads(out.stdout.strip().splitlines()[-1])


# ── Item 1: names ────────────────────────────────────────────────────────────

def test_server_sentence_case():
    for raw, want in NAME_CASES:
        assert sentence_case_name(raw) == want, raw
    assert display_common_name(None, '["disc mayweed", "pineapple weed"]') == "Disc mayweed"
    assert display_common_name("pineapple weed", None) == "Pineapple weed"
    assert display_common_name(None, None) == ""


def test_js_sentence_case_matches_server():
    cases = [c for c, _ in NAME_CASES]
    got = _jsc("var window = this;\n" + _src("frontend/static/js/esc.js") + "\n" + _src("frontend/static/js/species-names.js") + """
var cases = %s;
print(JSON.stringify({
  one: cases.map(function (c) { return spCommon(c); }),
  list: spCommonList(["disc mayweed", "pineapple weed"]),
  listComma: spCommonList(["disc mayweed", "St John's wort"], ", "),
  html: spNameHtml("Matricaria discoidea", "pineapple weed"),
  text: spNameText("Matricaria discoidea", "pineapple weed"),
  latinOnly: spNameText("Matricaria discoidea", "matricaria discoidea")
}));""" % json.dumps(cases))
    assert got["one"] == [w for _, w in NAME_CASES], got["one"]
    assert got["list"] == "Disc mayweed · Pineapple weed"
    assert got["listComma"] == "Disc mayweed, St John's wort"
    assert got["html"] == "Pineapple weed (<em>Matricaria discoidea</em>)"
    assert got["text"] == "Pineapple weed (Matricaria discoidea)"
    assert got["latinOnly"] == "Matricaria discoidea"


def test_server_surfaces_pdf_and_export_summary():
    flat = lp._flatten_species("Matricaria discoidea",
                               {"species": {"common_names": ["pineapple weed"]}, "culinary": {}}, {},
                               safety_decision("none", "edible"))
    assert flat["common_name"] == "Pineapple weed"
    sp = sharing.WalkSpecies(species_scientific="Matricaria discoidea", species_common="disc mayweed",
                             all_common=["disc mayweed", "pineapple weed"])
    html = sharing._walk_species_html(sp, True)
    assert ">Disc mayweed</div>" in html and "Pineapple weed" in html and "pineapple weed" not in html


# One check per surface found in recon: the display site reads the helper.
SURFACES = {
    # species grid tiles (all three views) and both header renderers
    "frontend/species.html": ["${_esc(spCommonList(allNames))}", "_esc(spCommon(allNames[0]))",
                              "${_esc(spCommon(n))}${isPref ? ' ★' : ''}", "commonEl.textContent = spCommon(preferred);"],
    # map detail pop-up, walk stop card, lasso list, proximity alert, near-me, find, search, walk diary
    "frontend/index.html": ["${_esc(spCommon(_allCommon[0]))}", "_esc(spCommonList(_allCommon.slice(1)))",
                            "walk-stop-common\">${_esc(spCommon(commonName))}", "wbs-lasso-common\">${_esc(spCommon(common))}",
                            "_esc(spCommon(sp.common_name)) + '</div>'", "nearme-common\">${_esc(spCommon(sp.common_name))}",
                            "find-common\">${_escHtml(spCommon(sp.common_name || ''))}",
                            "sub: spPickCommon(", "var cn = _esc(spCommon(o.common_name || ''));"],
    # Lists: compact rows, detail rows, print entries, seasonal returns, session species
    "frontend/lists.html": ["sp-compact-common\">${_esc(common)}", "_esc(spCommonList(sp.common_names, ', '))",
                            "const common = spPickCommon(sp.preferred_common_name || base.preferred_common_name,",
                            "sr-common\">${_esc(spCommon(it.common_name))}", "sp-sp-common\">${_esc(spPickCommon("],
    # browser print
    "frontend/print.html": ["const common = spPickCommon(sp.preferred_common_name || base.preferred_common_name,",
                            "sr-common\">${_esc(spCommon(it.common_name))}"],
    # review cards
    "frontend/review.html": ["spCommonList(top.common_names)", "spCommonList(sugMatch.common_names)",
                             "sop-common\">${_esc(spCommon(r.common_name))}", "sop-common\">${_esc(spCommon(c.common_name))}",
                             "_resc(spCommon(sp.common_names[0]))", "edib-common", "_esc(spCommon(sp.common_name))",
                             "loc-common\">${_esc(spCommon(obs.common_name))}", "comEl.textContent = spCommon(common);"],
    "frontend/static/js/reidentify.js": ["_esc(_spCommon(c.common_name))", "_esc(_spCommon(item.common_name))"],
    "frontend/static/js/seasonal-returns.js": ["window.spCommon ? window.spCommon(it.common_name)"],
}


def test_every_surface_routes_through_the_helper():
    for rel, needles in SURFACES.items():
        s = _src(rel)
        for n in needles:
            assert n in s, (rel, n)
    # pages that format names load the helper before their own script
    for rel in ("frontend/species.html", "frontend/lists.html", "frontend/print.html",
                "frontend/index.html", "frontend/review.html"):
        assert '<script src="/static/js/species-names.js"></script>' in _src(rel), rel
    # experience export + map pins + walk names: display_common_name (server)
    assert "display_common_name(sp.get(\"preferred_common_name\"), sp.get(\"common_names\"))" in \
        _src("scripts/experience_export/export.py")
    # German names: never through the helper
    for rel in ("frontend/species.html",):
        assert "spCommon(sp.common_names_de" not in _src(rel) and "spCommonList(sp.common_names_de" not in _src(rel)


# ── Item 2: species page views (executed) ────────────────────────────────────

def _slice(s, start, end, include_end=False):
    a = s.index(start)
    b = s.index(end, a)
    return s[a: b + (len(end) if include_end else 0)]


def _view_js():
    page = _src("frontend/species.html")
    parts = [
        _slice(page, "function _esc(s) {", "\n}\n", True),
        _slice(page, "function _sortKey(sp) {", "\n}\n", True),
        _slice(page, "function _selToggleCard(el) {", "\n}\n", True),
        _slice(page, "// Species views (Large / Grid / List) — declared before", "let _spThumbsPromise = null;\n", True),
        _slice(page, "// ── Species views (Melvin, 21 Oct 2026)", "function toggleDeNames() {"),
    ]
    return "\n".join(parts)


def _species():
    rows = [  # id, sci, common, verdict, severity, sightings, family
        (1, "Conium maculatum", "hemlock", "toxic", "deadly", 12, "Apiaceae"),
        (2, "Hedera helix", "ivy", "toxic", "toxic", 40, "Araliaceae"),
        (3, "Sambucus nigra", "elder", "caution", "none", 30, "Adoxaceae"),
        (4, "Allium ursinum", "ramsons", "edible", "none", 50, "Amaryllidaceae"),
        (5, "Heracleum sibiricum", "hogweed", "unknown", "unknown", 3, None),
        (6, "Briza media", "quaking grass", "inedible", "none", 7, "Poaceae"),
    ]
    out = []
    for sid, sci, common, verdict, sev, n, fam in rows:
        out.append({"id": sid, "scientific_name": sci, "common_names": [common], "common_names_de": ["echte " + common],
                    "preferred_common_name": None, "family": fam, "kingdom": "Plantae", "edibility_status": verdict,
                    "observation_count": n, "enriched": True, "lookalike_count": 0, "condition_count": 0,
                    "safety": safety_decision(sev, verdict, "W" if verdict == "caution" else None)})
    return out


def _run_views(select=False, stored_view=None, storage_throws=False, extra=""):
    harness = """
var window = this; window.scrollY = 0;
var _grid = { className: '', innerHTML: '' };
var document = { getElementById: function (id) { return id === 'species-grid' ? _grid : null; },
                 querySelectorAll: function () { return []; } };
var _store = %(store)s; var _wrote = {};
var localStorage = { getItem: function (k) { if (%(throws)s) throw new Error('blocked'); return _store[k] || null; },
                     setItem: function (k, v) { _wrote[k] = v; } };
function fetch() { return Promise.reject(new Error('offline')); }
var _selected = {'Allium ursinum': 1};
var ForagingList = { has: function (n) { return !!_selected[n]; }, getPhoto: function () { return null; },
                     toggle: function (n) { if (_selected[n]) delete _selected[n]; else _selected[n] = 1; },
                     setPhoto: function () {} };
function _syncStripChosen() {} function _updateSpSelectCount() {}
var _selectMode = %(select)s;
var _spThumbs = {};               // declared with the router in the page
var allSpecies = %(species)s;
""" % {"store": json.dumps({"foragingid_species_view": stored_view} if stored_view else {}),
       "throws": "true" if storage_throws else "false", "select": "true" if select else "false",
       "species": json.dumps(_species())}
    return _jsc(harness + _src("frontend/static/js/esc.js") + "\n" + _src("frontend/static/js/safety-gate.js") + "\n"
                + _src("frontend/static/js/species-names.js") + "\n" + _view_js() + "\n" + extra)


def _per_species(html):
    """{data-name: html chunk} for one rendered view."""
    out = {}
    # each chunk starts at the opening "<" of the element that carries data-name
    marks = [(html.rindex("<", 0, m.start()), m.group(1)) for m in re.finditer(r'data-name="([^"]+)"', html)]
    for i, (pos, name) in enumerate(marks):
        out[name] = html[pos: marks[i + 1][0] if i + 1 < len(marks) else len(html)]
    return out


RENDER_ALL = """
var res = {};
['large', 'grid', 'list'].forEach(function (v) {
  _spView = v; renderList(allSpecies.slice(0, 5));   // the same filtered set for every view
  res[v] = { cls: _grid.className, html: _grid.innerHTML };
});
res.badges = {}; allSpecies.forEach(function (sp) { res.badges[sp.scientific_name] = _spEdibBadge(sp); });
print(JSON.stringify(res));
"""


def test_views_same_count_and_same_badges():
    res = _run_views(extra=RENDER_ALL)
    assert res["grid"]["cls"] == "species-grid" and res["large"]["cls"] == "species-grid sp-large" \
        and res["list"]["cls"] == "sp-list"
    names = [s["scientific_name"] for s in _species()[:5]]
    for v in ("large", "grid", "list"):
        chunks = _per_species(res[v]["html"])
        assert sorted(chunks) == sorted(names), (v, sorted(chunks))           # same species, same count
        for n in names:
            assert res["badges"][n] and res["badges"][n] in chunks[n], (v, n)  # same badge in every view
    b = res["badges"]
    assert "☠ deadly" in b["Conium maculatum"] and "☠ toxic" in b["Hedera helix"]
    assert "⚠ caution" in b["Sambucus nigra"] and "✓ edible" in b["Allium ursinum"]
    assert "⚠ toxicity unknown" in b["Heracleum sibiricum"] and "✗ not edible" in b["Briza media"]
    # names: sentence case in every view, German as sourced
    for v in ("large", "grid", "list"):
        assert "Ramsons" in res[v]["html"] and ">ramsons" not in res[v]["html"], v
        assert "echte ramsons" in res[v]["html"], v
    # Large and List lazy-load their thumbnails (none here: the fetch failed → no <img>)
    assert 'loading="lazy"' in _src("frontend/species.html").split("function _spThumbImg")[1][:400]


def test_view_fails_closed_without_a_decision():
    res = _run_views(extra="""
var sp = JSON.parse(JSON.stringify(allSpecies[3])); delete sp.safety;     // edible, but no served decision
print(JSON.stringify({ b: _spEdibBadge(sp) }));""")
    assert "⚠ toxicity unknown" in res["b"] and "edible" not in res["b"]


def test_list_sort_orders():
    res = _run_views(extra="""
function order(key, dir) { _spListSort = { key: key, dir: dir };
  return _spSortedForList(allSpecies).map(function (s) { return s.scientific_name; }); }
var out = { safety: order('safety', 1), sightings: order('sightings', -1), latin: order('latin', 1),
            name: order('name', 1), family: order('family', 1) };
_spListSort = { key: 'name', dir: 1 }; sortSpeciesList('sightings'); out.firstSightings = _spListSort;
sortSpeciesList('sightings'); out.secondSightings = _spListSort;
sortSpeciesList('safety'); out.firstSafety = _spListSort;
print(JSON.stringify(out));""")
    assert res["safety"] == ["Conium maculatum", "Hedera helix", "Heracleum sibiricum", "Sambucus nigra",
                             "Allium ursinum", "Briza media"]          # deadly, toxic, unknown, caution, edible, not edible
    assert res["sightings"] == ["Allium ursinum", "Hedera helix", "Sambucus nigra", "Conium maculatum",
                                "Briza media", "Heracleum sibiricum"]
    assert res["latin"] == sorted(res["latin"])
    assert res["name"] == ["Sambucus nigra", "Conium maculatum", "Heracleum sibiricum", "Hedera helix",
                           "Briza media", "Allium ursinum"]           # elder, hemlock, hogweed, ivy, quaking grass, ramsons
    assert res["family"][-1] == "Heracleum sibiricum"                   # no family sorts last
    assert res["firstSightings"] == {"key": "sightings", "dir": -1}     # most sightings first
    assert res["secondSightings"] == {"key": "sightings", "dir": 1}     # second click reverses
    assert res["firstSafety"] == {"key": "safety", "dir": 1}


def test_remembered_view():
    assert _run_views(stored_view="list", extra="print(JSON.stringify({v: _spView}));")["v"] == "list"
    assert _run_views(stored_view="large", extra="print(JSON.stringify({v: _spView}));")["v"] == "large"
    assert _run_views(stored_view="bogus", extra="print(JSON.stringify({v: _spView}));")["v"] == "grid"
    assert _run_views(extra="print(JSON.stringify({v: _spView}));")["v"] == "grid"           # default
    assert _run_views(storage_throws=True, extra="print(JSON.stringify({v: _spView}));")["v"] == "grid"
    res = _run_views(extra="""
renderList(allSpecies); setSpeciesView('list');
print(JSON.stringify({ wrote: _wrote, v: _spView, cls: _grid.className }));""")
    assert res["wrote"] == {"foragingid_species_view": "list"} and res["cls"] == "sp-list"


def test_select_mode_in_every_view():
    res = _run_views(select=True, extra=RENDER_ALL.replace("print(JSON.stringify(res));", """
var row = { dataset: { name: 'Hedera helix' }, _cls: {},
            classList: { toggle: function (c, on) { row._cls[c] = on; } }, querySelectorAll: function () { return []; } };
_selToggleCard(row);
res.toggled = { selected: ForagingList.has('Hedera helix'), cls: row._cls.selected };
print(JSON.stringify(res));"""))
    for v in ("large", "grid", "list"):
        chunks = _per_species(res[v]["html"])
        assert len(chunks) == 5, v
        for n, h in chunks.items():
            assert "_selToggleCard(this)" in h and "sel-card" in h, (v, n)
        assert "sel-card selected" in chunks["Allium ursinum"].split(">")[0], v            # pre-selected shown
        assert "sel-card selected" not in chunks["Hedera helix"].split(">")[0], v
        assert "/species?s=" not in res[v]["html"], v                                     # no navigation in select mode
    assert res["toggled"] == {"selected": True, "cls": True}


def test_toggle_markup_and_phone_layout():
    page = _src("frontend/species.html")
    for v, tip in (("large", "Large"), ("grid", "Grid"), ("list", "List")):
        assert f'data-view="{v}" onclick="setSpeciesView(\'{v}\')" title="{tip}' in page
    css = page[page.index("/* ── Species views: Large / Grid / List"):page.index("/* ── Filter chips")]
    assert ".sp-table .col-family { display: none; }" in css and "table-layout: fixed" in css
    assert "overflow-wrap: anywhere" in css
    # the state is declared before the router calls into the views (TDZ)
    assert page.index("let _spView = ") < page.index("if (speciesParam) {")
    # no new safety logic: the views read the served decision only
    views = page[page.index("// ── Species views (Melvin"):page.index("function toggleDeNames() {")]
    assert "toxicity_severity" not in views and "edibility_status ===" not in views


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
