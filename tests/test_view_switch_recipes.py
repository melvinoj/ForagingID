"""
Recipes batch (Melvin, 28 Oct 2026).

Step 1 — one Large / Grid / List switch (frontend/static/js/view-switch.js),
  used by species.html and recipes.html; species behaviour unchanged (the
  executed species-view tests in test_names_and_species_views.py run on it);
  the generated toggle is the old static species markup; a remembered-view key
  per page.

The JS is EXECUTED in macOS JavaScriptCore (`jsc`) with small DOM stubs. No
browser — the live checks stay Melvin's.

Run: python tests/test_view_switch_recipes.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"

# species.html's toggle as it was before 28 Oct (static markup, commit a67236e).
OLD_SPECIES_TOGGLE = """
      <button type="button" class="sp-view-btn" data-view="large" onclick="setSpeciesView('large')" title="Large — big photo cards" aria-label="Large view">
        <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="1" y="1" width="6" height="6" rx="1"/><rect x="9" y="1" width="6" height="6" rx="1"/><rect x="1" y="9" width="6" height="6" rx="1"/><rect x="9" y="9" width="6" height="6" rx="1"/></svg>
      </button>
      <button type="button" class="sp-view-btn" data-view="grid" onclick="setSpeciesView('grid')" title="Grid — compact cards" aria-label="Grid view">
        <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="1" y="1" width="4" height="4" rx=".6"/><rect x="6" y="1" width="4" height="4" rx=".6"/><rect x="11" y="1" width="4" height="4" rx=".6"/><rect x="1" y="6" width="4" height="4" rx=".6"/><rect x="6" y="6" width="4" height="4" rx=".6"/><rect x="11" y="6" width="4" height="4" rx=".6"/><rect x="1" y="11" width="4" height="4" rx=".6"/><rect x="6" y="11" width="4" height="4" rx=".6"/><rect x="11" y="11" width="4" height="4" rx=".6"/></svg>
      </button>
      <button type="button" class="sp-view-btn" data-view="list" onclick="setSpeciesView('list')" title="List — sortable rows" aria-label="List view">
        <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="1" y="2" width="3" height="3" rx=".6"/><rect x="6" y="2.75" width="9" height="1.5" rx=".5"/><rect x="1" y="6.5" width="3" height="3" rx=".6"/><rect x="6" y="7.25" width="9" height="1.5" rx=".5"/><rect x="1" y="11" width="3" height="3" rx=".6"/><rect x="6" y="11.75" width="9" height="1.5" rx=".5"/></svg>
      </button>
"""


def _src(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def _jsc(script: str):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(script)
        path = f.name
    try:
        out = subprocess.run([JSC, path], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(path)
    assert out.returncode == 0, out.stderr or out.stdout
    return json.loads(out.stdout.strip().split("\n")[-1])


def _squash(html):
    return re.sub(r">\s+<", "><", html.strip())


STUBS = """
var window = this; window.scrollY = 0;
var _store = %s; var _wrote = {};
var localStorage = { getItem: function (k) { return _store[k] || null; },
                     setItem: function (k, v) { _wrote[k] = v; } };
var _btns = ['large', 'grid', 'list'].map(function (v) {
  var b = { dataset: { view: v }, cls: {}, attrs: {} };
  b.classList = { toggle: function (c, on) { b.cls[c] = on; } };
  b.setAttribute = function (k, v2) { b.attrs[k] = v2; };
  return b; });
var document = { querySelectorAll: function () { return _btns; } };
"""


def _run(extra, store=None):
    return _jsc(STUBS % json.dumps(store or {}) + _src("frontend/static/js/safety-gate.js") + "\n"
                + _src("frontend/static/js/view-switch.js") + "\n" + extra)


# ── Step 1: shared view switch ───────────────────────────────────────────────

def test_toggle_is_the_old_species_markup():
    got = _run("print(JSON.stringify({ h: LmViewSwitch.toggleHtml('sp-view-btn', 'setSpeciesView') }));")["h"]
    assert _squash(got) == _squash(OLD_SPECIES_TOGGLE)


def test_remembered_view_per_page_key():
    res = _run("""
var out = { sp: LmViewSwitch.stored('foragingid_species_view', 'grid'),
            rc: LmViewSwitch.stored('foragingid_recipes_view', 'grid'),
            bogus: LmViewSwitch.stored('x', 'list') };
LmViewSwitch.remember('foragingid_recipes_view', 'list');
out.wrote = _wrote;
LmViewSwitch.sync('.b', 'list');
out.btns = _btns.map(function (b) { return [b.cls.active, b.attrs['aria-pressed']]; });
print(JSON.stringify(out));""", store={"foragingid_species_view": "large", "x": "nope"})
    assert res["sp"] == "large" and res["rc"] == "grid" and res["bogus"] == "list"
    assert res["wrote"] == {"foragingid_recipes_view": "list"}          # never the species key
    assert res["btns"] == [[False, "false"], [False, "false"], [True, "true"]]


def _one_copy(page):
    assert '<script src="/static/js/view-switch.js"></script>' in page
    assert 'data-view="large"' not in page and "<rect x=\"1\" y=\"1\" width=\"6\"" not in page   # no copied buttons
    assert "localStorage.getItem(" not in page.split("// ── Species views")[0].split("_SP_VIEW_KEY")[-1][:300]
    assert "deadly: 0, toxic: 1" not in page                                                   # one safety order


def test_species_uses_the_one_switch():
    sp = _src("frontend/species.html")
    _one_copy(sp)
    assert "const _SP_VIEW_KEY = 'foragingid_species_view';" in sp
    assert "let _spView = LmViewSwitch.stored(_SP_VIEW_KEY, 'grid');" in sp
    assert "'/static/js/view-switch.js'" in _src("frontend/static/sw.js")


if __name__ == "__main__":
    fns = [v for k, v in globals().items() if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
