"""
Recipes batch (Melvin, 28 Oct 2026).

Step 1 — one Large / Grid / List switch (frontend/static/js/view-switch.js),
  used by species.html and recipes.html; species behaviour unchanged (the
  executed species-view tests in test_names_and_species_views.py run on it);
  the generated toggle is the old static species markup; a remembered-view key
  per page.
Step 2 — recipes in three views: every card / row carries the species badge
  (LmViewSwitch.badge, the species list's own); List = title, species, season,
  badge, safety first; thumbnails = the species list's best confirmed photo
  (one rule, best_confirmed_thumbnails), lazy, over a drawn placeholder.
Step 3 — a safety sentence is never a title (recipe 258 "Always cook well…"):
  is_safety_note_line + its JS twin widened; a list / card shows only an own or
  heading title (recipe_list_title), else "Untitled recipe" + species. No DB write.
Step 4 — recipe season (#19): curator-set (not ai_generated) always wins; else a
  season word in the title beats the keyword guess (recipe 74 → spring); every
  served season reads recipe_season; the draft-approve guess checks the title
  first. No DB write.
Step 5 — lighter design, recipes page only: page-scoped CSS; serif from local
  fonts only on titles; the safety CSS (badges, warning boxes, ☠) untouched.

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
    assert "localStorage.getItem(_SP_VIEW_KEY)" not in page and "localStorage.getItem(_RC_VIEW_KEY)" not in page
    assert "deadly: 0, toxic: 1" not in page                                                   # one safety order


def test_species_uses_the_one_switch():
    sp = _src("frontend/species.html")
    _one_copy(sp)
    assert "const _SP_VIEW_KEY = 'foragingid_species_view';" in sp
    assert "let _spView = LmViewSwitch.stored(_SP_VIEW_KEY, 'grid');" in sp
    assert "'/static/js/view-switch.js'" in _src("frontend/static/sw.js")


# ── Step 2: recipes in three views ───────────────────────────────────────────

def _recipes_page_js():
    page = _src("frontend/recipes.html")
    m = re.search(r"<script>\n// ── Recipes page ─+\n(.*?)\n\(function init\(\)", page, re.S)
    assert m
    return m.group(1)


def _decision(level, label, verdict, allowed, warn=None):
    return {"level": level, "label": label, "verdict": verdict, "culinary_allowed": allowed,
            "warnings": {"look_alike": {"text": warn, "reviewed": True}} if warn else {}}


def _rc_data():
    sp = {  # id: (sci, common, verdict, decision, conditions, thumbnail)
        1: ("Urtica dioica", "Nettle", "edible", _decision("none", "", "edible", True), 0, "n.jpg"),
        2: ("Allium ursinum", "Ramsons", "caution",
            _decision("caution", "⚠ caution", "caution", True, "Lily of the valley"), 0, None),
        3: ("Sambucus nigra", "Elder", "edible", _decision("none", "", "edible", True), 2, None),
        4: ("Conium maculatum", "Hemlock", "toxic", _decision("deadly", "☠ deadly", "toxic", False), 0, "h.jpg"),
    }
    recs = []
    for rid, (sid, title, season) in enumerate([(1, "Nettle Soup", "spring"), (2, "Ramsons Pesto", "spring"),
                                                 (3, "Elder Cordial", "summer"), (4, "Never Shown", "spring"),
                                                 (1, "Apple Nettle Tart", "autumn")], 1):
        sci, common, verdict, d, conds, thumb = sp[sid]
        recs.append({"id": rid, "title": title, "summary": "", "recipe_type": None, "season": season, "parts": [],
                     "approved_at": "2026-10-0%d" % rid, "website_url": None, "walks": [],
                     "species": {"id": sid, "scientific_name": sci, "common": common, "level": d["level"],
                                 "label": d["label"], "edibility_status": verdict, "condition_count": conds,
                                 "thumbnail": thumb}})
    return {"recipes": recs, "safety": {str(k): v[3] for k, v in sp.items()}, "types": []}


RC_STUBS = """
var window = this; window.scrollY = 0;
var location = {search: ''};
function URLSearchParams(){ this.get = function(){ return null; }; }
var _el = {}; function _get(id) { return _el[id] || (_el[id] = {value: 'az', style: {}, innerHTML: '', textContent: '',
                                                     className: '', addEventListener: function(){} }); }
var document = { getElementById: _get, querySelectorAll: function(){ return []; } };
var _store = %s; var _wrote = {};
var localStorage = { getItem: function (k) { return _store[k] || null; }, setItem: function (k, v) { _wrote[k] = v; } };
"""


def _rc_run(extra, store=None):
    return _jsc(RC_STUBS % json.dumps(store or {}) + "\n".join([
        _src("frontend/static/js/esc.js"), _src("frontend/static/js/safety-gate.js"),
        _src("frontend/static/js/species-names.js"), _src("frontend/static/js/view-switch.js"),
        _recipes_page_js(), "_data = %s;" % json.dumps(_rc_data()), extra]))


RC_RENDER_ALL = """
var res = {};
['large', 'grid', 'list'].forEach(function (v) { _rcView = v; render(); res[v] = _get('rc-results').innerHTML; });
res.badges = {}; _visible().forEach(function (r) { res.badges[r.id] = _rcBadge(r); });
res.spBadge = LmViewSwitch.badge({ safety: _data.safety['2'], edibility_status: 'caution', condition_count: 0 });
print(JSON.stringify(res));
"""


def _chunks(html):
    marks = [(html.rindex("<", 0, m.start()), m.group(1)) for m in re.finditer(r'data-name="(\d+)"', html)]
    return {int(n): html[p: marks[i + 1][0] if i + 1 < len(marks) else len(html)] for i, (p, n) in enumerate(marks)}


def test_recipes_three_views_same_items_same_badge():
    res = _rc_run(RC_RENDER_ALL)
    for v in ("large", "grid", "list"):
        ch = _chunks(res[v])
        assert sorted(ch) == [1, 2, 3, 5], (v, sorted(ch))          # the deadly species' recipe never drawn
        for rid, b in res["badges"].items():
            assert b and b in ch[int(rid)], (v, rid)                # the species badge on every card / row
    b = res["badges"]
    assert "✓ edible" in b["1"] and "⚠ caution" in b["2"] and "⚡ conditional" in b["3"]
    assert b["2"] == res["spBadge"]                                 # the species list's own badge
    assert "Lily of the valley" in _chunks(res["grid"])[2] and "Lily of the valley" in _chunks(res["list"])[2]
    assert "Lily of the valley" in _chunks(res["large"])[2]          # warnings in every view


def test_recipes_thumbnails_lazy_with_placeholder():
    res = _rc_run(RC_RENDER_ALL)
    for v in ("large", "list"):
        ch = _chunks(res[v])
        assert 'src="/thumbnails/n.jpg" loading="lazy"' in ch[1], v       # the species' photo, lazy
        assert "<img" not in ch[2] and 'class="rc-ph"' in ch[2], v        # no photo → drawn placeholder
        assert 'class="rc-ph"' in ch[1], v                                # placeholder sits under a failing photo
        assert 'onerror="this.remove()"' in ch[1], v
    assert "<img" not in res["grid"]                                      # Grid stays photo-free, as species
    page = _src("frontend/recipes.html")
    assert "const _RC_PLACEHOLDER = '<svg class=\"rc-ph\"" in page                  # inline, no external asset
    assert not re.search(r"url\(\s*['\"]?(https?:|/static/)", page) and "fonts.googleapis" not in page


def test_recipes_list_columns_and_safety_first_sort():
    res = _rc_run("""
_rcView = 'list';
function order() { return _rcSorted(_visible()).map(function (r) { return r.id; }); }
var out = { def: _rcListSort, safety: order() };
sortRecipesList('title'); out.title = order(); sortRecipesList('title'); out.titleRev = order();
sortRecipesList('season'); out.season = order();
render(); out.html = _get('rc-results').innerHTML;
print(JSON.stringify(out));""")
    assert res["def"] == {"key": "safety", "dir": 1}
    assert res["safety"] == [2, 5, 3, 1]          # caution first; edible ties by title (Apple…, Elder…, Nettle…)
    assert res["title"] == [5, 3, 1, 2] and res["titleRev"] == [2, 1, 3, 5]
    assert res["season"][:2] == [1, 2] or res["season"][:2] == [2, 1]
    for col in ("Recipe", "Species", "Season", "Safety"):
        assert f">{col}" in res["html"], col
    ch = _chunks(res["html"])
    assert "Ramsons" in ch[2] and "🌱 Spring" in ch[2] and "Ramsons Pesto" in ch[2]


def test_recipes_safety_rank_is_the_species_order():
    res = _run("""
function d(level, verdict) { return { level: level, label: level === 'none' ? '' : level, verdict: verdict,
  culinary_allowed: level === 'none' || level === 'caution', warnings: {} }; }
print(JSON.stringify([d('deadly','toxic'), d('toxic','toxic'), d('unknown','unknown'), d('caution','caution'),
  d('none','edible'), d('none','inedible')].map(LmViewSwitch.safetyRank)));""")
    assert res == [0, 1, 2, 3, 4, 5]


def test_recipes_remembered_view_is_its_own():
    res = _rc_run("print(JSON.stringify({v: _rcView}));", store={"foragingid_species_view": "list"})
    assert res["v"] == "grid"
    res = _rc_run("print(JSON.stringify({v: _rcView}));", store={"foragingid_recipes_view": "large"})
    assert res["v"] == "large"
    res = _rc_run("render(); setRecipesView('list'); print(JSON.stringify({w: _wrote, v: _rcView}));")
    assert res["w"] == {"foragingid_recipes_view": "list"} and res["v"] == "list"


def test_recipes_uses_the_one_switch():
    rc = _src("frontend/recipes.html")
    _one_copy(rc)
    assert "const _RC_VIEW_KEY = 'foragingid_recipes_view';" in rc and "foragingid_species_view" not in rc
    assert "LmViewSwitch.toggleHtml('rc-view-btn', 'setRecipesView')" in rc
    assert "LmViewSwitch.badge(" in rc and "edibility_status ===" not in rc   # no second badge reader


def test_api_serves_thumbnail_and_badge_inputs():
    import asyncio
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_recipes_page as trp
    from app.models.observation import Observation
    from app.models.species import SpeciesEdibilityCondition
    import app.api.recipes as recipes_api
    import app.api.culinary as culinary_api

    async def run():
        eng, S = await trp._api_db()
        async with S() as s:
            cand = lambda n, sc: json.dumps([{"scientific_name": n, "score": sc}])
            for oid, sp, thumb, cj, rs in (
                    (1, "Urtica dioica", "thumbnails/low.jpg", cand("Urtica dioica", 0.4), "approved"),
                    (2, "Urtica dioica", "thumbnails/best.jpg", cand("Urtica dioica", 0.9), "manually_verified"),
                    (3, "Urtica dioica", "thumbnails/pending.jpg", cand("Urtica dioica", 0.99), "needs_review"),
                    (4, "Urtica dioica", "thumbnails/other.jpg", cand("Urtica urens", 0.95), "approved")):
                s.add(Observation(id=oid, file_path=f"uploads/{oid}.jpg", species_primary=sp, thumbnail_path=thumb,
                                  species_candidates_json=cj, review_status=rs, identification_status="identified"))
            s.add(SpeciesEdibilityCondition(species_id=1, part="leaf", preparation="cooked", safe=True))
            await s.commit()
            api = await recipes_api.all_recipes(q=None, db=s, identity=trp.GUEST)
            sp_list = await culinary_api.list_species(db=s)
        await eng.dispose()
        return api, sp_list
    api, sp_list = asyncio.run(run())
    by = {r["id"]: r["species"] for r in api["recipes"]}
    assert by[101]["thumbnail"] == "best.jpg"                  # highest own-species score, confirmed only
    assert by[102]["thumbnail"] is None
    assert by[101]["edibility_status"] == "edible" and by[101]["condition_count"] == 1
    assert by[102]["edibility_status"] == "caution" and by[102]["condition_count"] == 0
    nettle = [x for x in sp_list if x["scientific_name"] == "Urtica dioica"][0]
    assert nettle["thumbnail"] == "best.jpg"                   # the species list: the same one rule


# ── Step 3: titles ────────────────────────────────────────────────────────────

BODY_258 = ("Always cook well; some people react, so try a little first.\n\n"
            "Chicken of the woods is a young fungus for a young appetite — firm and bright.\n\n"
            "## Ingredients\n- 300 g chicken of the woods\n")
NOTE_LINES = ["Always cook well; some people react.", "Never eat it raw.", "Do not confuse with X.",
              "Don't eat the old brackets.", "Don’t eat the old brackets.", "Avoid during pregnancy.",
              "Caution: bitter.", "Warning – look-alikes.", "SAFETY NOTE", "  never raw", "DO NOT pick near roads."]
NOT_NOTES = ["Always a favourite in spring.", "Nevertheless a fine soup.", "Doughnuts with elderflower",
             "Avocado and ramsons toast", "Spring Beech Leaf Salad", "Neverland Nettle Broth", ""]


def test_safety_openers_python_and_js_agree():
    from app.models.species import is_safety_note_line
    for t in NOTE_LINES:
        assert is_safety_note_line(t), t
    for t in NOT_NOTES:
        assert not is_safety_note_line(t), t
    wp = _src("frontend/static/js/index/walk-panel.js")
    fn = wp[wp.index("function _isSafetyNoteLine(plain)"):].split("\n")[0]
    got = _jsc(fn + "\nprint(JSON.stringify(%s.map(_isSafetyNoteLine)));" % json.dumps(NOTE_LINES + NOT_NOTES))
    assert got == [True] * len(NOTE_LINES) + [False] * len(NOT_NOTES)


def test_recipe_258_never_gets_its_warning_as_title():
    from app.models.species import recipe_display_title, recipe_list_title, recipe_title_source
    shown = recipe_display_title(None, BODY_258)
    assert not shown.startswith("Always") and shown.startswith("Chicken of the woods")
    assert recipe_title_source(None, BODY_258) == "line"          # still in the needs_title queue
    assert recipe_list_title(None, BODY_258) == ""                # untitled — no prose sentence as a title
    assert recipe_list_title(None, "# Nettle Soup\n\nText.") == "Nettle Soup"
    assert recipe_list_title("  Own Title ", "Never raw.") == "Own Title"
    assert recipe_list_title(None, "Never eat raw.\n\nDo not pick near roads.") == ""


def test_untitled_label_on_recipes_page_and_species_card():
    res = _rc_run("""
_data.recipes[0].title = ''; _rcView = 'grid';
print(JSON.stringify({ t: _rcTitle(_data.recipes[0]), tile: tileHtml(_data.recipes[0]),
                       row: rowHtml(_data.recipes[0]) }));""")
    assert res["t"] == "Untitled recipe · Nettle"
    assert "Untitled recipe · Nettle" in res["tile"] and "Untitled recipe · Nettle" in res["row"]
    sp = _src("frontend/species.html")
    assert "const titleText = r.display_title || (r.is_medicinal_prep ? 'Untitled preparation' : 'Untitled recipe');" in sp
    assert "r.body.split('\\n')[0]" not in sp                     # no first-line title fallback left
    assert '"display_title":     recipe_list_title(r.title, r.body),' in _src("app/api/culinary.py")
    assert '"title": recipe_list_title(r.title, r.body),' in _src("app/api/recipes.py")


# ── Step 4: season ────────────────────────────────────────────────────────────

def test_recipe_74_spring_and_curator_season_wins():
    from app.models.species import recipe_season, recipe_title_season
    t74 = "Spring Beech Leaf Salad with Toasted Beechnut, Aged Sheep's Cheese & Wild Herb Dressing"
    assert recipe_season("autumn", "ai_generated", t74, "beechnut autumn harvest") == "spring"
    assert recipe_season("autumn", "curator", t74, "x") == "autumn"                 # curator-set wins
    assert recipe_season("summer", "Friture Sauvage menu, Hofgut LEO, 5 July 2026", "Spring Soup", "x") == "summer"
    assert recipe_season("autumn", "ai_generated", "Beech Nut Butter", "x") == "autumn"   # no title word: stored
    assert recipe_season("autumn", "ai_generated", None, "# Spring Beech Salad\n\nx") == "spring"   # heading title
    assert recipe_season("autumn", "ai_generated", None, "Spring is here and so is beech.") == "autumn"  # prose ≠ title
    assert recipe_season(None, "ai_generated", "Wood Sorrel Soup", "x") == "year-round"
    # season words that are not the dish's season
    for t in ("Ox-Eye Daisy Shoots with Charred Spring Onions", "Wood Blewit with Winter Savory",
              "Wild Pear, Blette, and Honey — A Slow Cure for Winter", "Springy Thistle Broth",
              "Winter and Summer Salad", "Spring Garlic Butter", "Summer Squash Fritters"):
        assert recipe_title_season(t) is None, t
    for t, want in (("A Winter Salad of Ivy-Leaved Toadflax", "winter"), ("Summer Bolete, Spelt", "summer"),
                    ("Sorrel — A Spring Braise", "spring"), ("autumn hedgerow jelly", "autumn"),
                    ("Spring Onion and Spring Nettle Tart", "spring")):
        assert recipe_title_season(t) == want, t


def test_every_served_season_reads_the_rule():
    assert src_count("app/api/recipes.py", "recipe_season(r.season, r.source, r.title, r.body)") == 2
    assert src_count("app/api/culinary.py", "recipe_season(r.season, r.source, r.title, r.body)") == 2
    assert src_count("app/api/find.py", "recipe_season(r.season, r.source, r.title, r.body)") == 1
    assert 'recipe_season(r["season"], r["source"], r["title"], r["body"])' in _src("scripts/experience_export/export.py")
    cul = _src("app/api/culinary.py")
    appr = cul[cul.index("_VALID_SEASONS = {"):cul.index("existing_rb = await db.scalar(")]
    assert appr.index("recipe_title_season(recipe_title)") < appr.index("_SEASON_RE.items()")   # title before keywords
    assert "season=new_season," in cul and "season=recipe_season," not in cul
    assert "'foragingid-species-5'" in _src("frontend/static/sw.js")                      # cached profiles evicted


def src_count(rel, needle):
    return _src(rel).count(needle)


def test_api_serves_derived_season_without_writing():
    import asyncio
    import sqlite3 as _sq
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_recipes_page as trp
    import app.api.recipes as recipes_api
    from app.models.species import SpeciesRecipe

    async def run():
        eng, S = await trp._api_db()
        async with S() as s:
            r = await s.get(SpeciesRecipe, 101)
            r.title, r.season = "Spring Nettle Salad", "autumn"
            r2 = await s.get(SpeciesRecipe, 102)
            r2.title, r2.season, r2.source = "Spring Ramsons Pesto", "autumn", "curator"
            await s.commit()
            api = await recipes_api.all_recipes(q=None, db=s, identity=trp.CURATOR)
            lst = await recipes_api.list_recipes("Urtica dioica", db=s)
            stored = (await s.get(SpeciesRecipe, 101)).season
        url = str(eng.url).replace("sqlite+aiosqlite:///", "")
        await eng.dispose()
        return api, lst, stored, url
    api, lst, stored, url = asyncio.run(run())
    by = {r["id"]: r for r in api["recipes"]}
    assert by[101]["season"] == "spring" and by[102]["season"] == "autumn"
    assert [r["season"] for r in lst["recipes"] if r["id"] == 101] == ["spring"]
    assert stored == "autumn"
    assert _sq.connect(url).execute("SELECT season FROM species_recipes WHERE id = 101").fetchone()[0] == "autumn"


# ── Step 5: lighter design — the safety CSS is untouched ───────────────────────

def _rc_css():
    page = _src("frontend/recipes.html")
    return page[page.index("<style>"):page.index("</style>")]


def _rules(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [(sel.strip(), body.strip()) for sel, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)]


SAFETY_CLASS = re.compile(r"(?<!col-)safety|culinary-warn|warn-badge|toxic-badge|sw-unreviewed|skull|☠|obs-badge|inedible-badge")


def test_badge_css_is_the_species_pages_and_nothing_else_touches_safety():
    rules = _rules(_rc_css())
    safety_rules = [(sel, body) for sel, body in rules if SAFETY_CLASS.search(sel)]
    norm = lambda b: re.sub(r"\s+", " ", b)
    assert [(sel, norm(b)) for sel, b in safety_rules] == [
        ("#rc-results .obs-badge, #rc-results .inedible-badge",
         "display: inline-block; font-size: 0.72rem; padding: 2px 7px; border-radius: 10px; font-weight: 600;"),
        ("#rc-results .inedible-badge", "background: #fef3c7; color: #854d0e; font-weight: 400;"),
    ]
    sp = _src("frontend/species.html")
    assert ".sp-table .obs-badge, .sp-table .inedible-badge {\n      display: inline-block; font-size: 0.72rem; " \
           "padding: 2px 7px; border-radius: 10px; font-weight: 600;\n    }" in sp
    assert ".sp-table .inedible-badge { background: #fef3c7; color: #854d0e; font-weight: 400; }" in sp
    # no page rule reaches into a warning box or a badge by element or attribute
    for sel, _ in rules:
        assert "[style" not in sel and "details div" not in sel and "details *" not in sel, sel
    # the badge markup itself is unchanged (inline styles, from LmViewSwitch.badge / SafetyGate.badge)
    vs = _src("frontend/static/js/view-switch.js")
    assert '<span class="obs-badge" style="background:#2a2010;color:#d4a840;border:1px solid #4a3a10">⚠ caution</span>' in vs
    sg = _src("frontend/static/js/safety-gate.js")
    assert "'padding:1px 6px;border-radius:4px;font-weight:700;background:' + (red ? '#dc2626' : '#fef3c7')" in sg
    assert "'font-size:0.78rem;color:#7a2000;background:#fff7ed;border-left:3px solid #ea580c;'" in sg


def test_serif_on_titles_only_and_no_font_fetch():
    rules = _rules(_rc_css())
    serif = [sel for sel, body in rules if "--rc-serif)" in body and "font-family" in body]
    assert sorted(serif) == sorted(["#recipes-page h2", ".rc-group-h", ".recipe-tile .rt-title", ".rc-table .rl-title"]), serif
    body = [b for sel, b in rules if sel == "body"][0]
    assert "system-ui" in body and "serif;" not in body.replace("sans-serif", "")
    page = _src("frontend/recipes.html")
    assert "@import" not in page and "@font-face" not in page and "fonts.g" not in page
    assert "Iowan Old Style" in page and "Georgia" in page
    assert "--rc-" in page and not re.search(r"^\s*--(ink|paper|moss|leaf|ground)\s*:", _rc_css(), re.M)  # no token redefined


def test_batch_commits_leave_shared_css_and_safety_gate_alone():
    out = subprocess.run(["git", "log", "--format=%s", "a67236e..HEAD", "--",
                          "frontend/static/css/tokens.css", "frontend/static/css/site-header.css",
                          "frontend/static/js/safety-gate.js"],
                         cwd=ROOT, capture_output=True, text=True).stdout
    assert not [l for l in out.splitlines() if l.startswith("Recipes batch")], out
    diff = subprocess.run(["git", "diff", "--stat", "HEAD", "--", "frontend/static/css/tokens.css",
                           "frontend/static/css/site-header.css", "frontend/static/js/safety-gate.js"],
                          cwd=ROOT, capture_output=True, text=True).stdout
    assert diff.strip() == "", diff
    # page-scoped: no other page links a recipes stylesheet, and the page adds none
    assert re.findall(r'<link rel="stylesheet" href="([^"]+)"', _src("frontend/recipes.html")) == \
        ["/static/css/tokens.css", "/static/css/site-header.css"]


if __name__ == "__main__":
    fns = [v for k, v in globals().items() if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
