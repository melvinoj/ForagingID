"""
Tests for the Recipes page + the public Recipes tab (Melvin, 25 Oct 2026).

  * Rules (app/models/species.py): a title is never a quote or safety line; a
    prose-sentence title is "needs a title", not a real one; the summary skips
    safety lines, hazard / medicinal wording and cited source text; the type is
    the dish noun's; the website link is https on melvinjarman.co.uk only.
  * Backfill (scripts/recipe_fields_backfill.py): fills only empty fields, never
    a safety-line title, second run writes nothing.
  * GET /api/recipes: only approved, non-medicinal recipes of culinary-allowed
    species — toxic / unknown / inedible / withheld never; caution carries ⚠;
    guests get the same recipes without curator fields. PATCH: validated,
    curator only.
  * Recipes page tile → /species?s=…&recipe=<id>#recipe-card-<id>; the species
    page opens that card. Find → Make? opens the Recipes page.
  * Public build (scripts/experience_export): build_recipe_bank lists gated,
    unhidden recipes only, never the body; the Recipes tab renders teasers;
    #recipes opens it; preview.html links to it and stays script-free.

No external calls; throw-away SQLite DBs; JS run in JavaScriptCore.

Run from project root:  python tests/test_recipes_page.py
"""
import asyncio
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "experience_export"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from fastapi import HTTPException  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main  # noqa: E402,F401  (registers every model on Base.metadata)
import app.api.recipes as recipes_api  # noqa: E402
from app.api.identity import Identity  # noqa: E402
from app.database import Base  # noqa: E402
from app.models.culinary import CulinaryInfo  # noqa: E402
from app.models.species import (CulinaryInfoHistory, Species, SpeciesRecipe,  # noqa: E402
                                is_safety_note_line, propose_recipe_type, recipe_display_title,
                                recipe_summary_line, recipe_title_source, recipe_website_url_ok)

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
CURATOR = Identity(user_id=1, is_guest=False, is_anonymous_guest=False, workshop_session_id=None)
GUEST = Identity(user_id=None, is_guest=True, is_anonymous_guest=True, workshop_session_id=None)
LOOK = "Confusable with deadly Conium maculatum — check the stem."
TS = "2026-10-20 10:00:00"

BODY_SAFETY_FIRST = ("**Safety note:** Avoid during pregnancy. Do not eat raw.\n\n"
                     "> A quote that is not a title.\n\n"
                     "**Nettle & Ramsons Soup**\n\n"
                     "This spring soup is bright, green and quick to make on a cold evening. Then more.\n\n"
                     "## Ingredients\n- 200 g nettle tops\n- 1 onion\n\n"
                     "## Method\nSweat the onion slowly in butter until soft, then add the nettle tops and "
                     "stock, simmer for five minutes and blend until completely smooth and glossy green.")
BODY_PROSE = ("Let me tell you about betony. Most people walk past it without a second glance, but its "
              "leaves carry a clean, aromatic bitterness that lifts a dish in the same way bay does.")


def _run(coro):
    return asyncio.run(coro)


# ── rules ─────────────────────────────────────────────────────────────────────

def test_title_never_a_quote_or_safety_line_and_prose_needs_a_title():
    assert recipe_display_title(None, BODY_SAFETY_FIRST) == "Nettle & Ramsons Soup"
    assert recipe_title_source(None, BODY_SAFETY_FIRST) == "heading"            # bold standalone line
    assert recipe_title_source(None, "Title: Birch Syrup Sorbet\n\nText here.") == "heading"
    assert recipe_display_title(None, "Recipe: Hawthorn Tea\n\nText.") == "Hawthorn Tea"   # label stripped
    assert recipe_title_source(None, BODY_PROSE) == "line"                      # not a real title
    assert recipe_title_source("Own title", BODY_PROSE) == "own"
    for body in (BODY_SAFETY_FIRST, "**Caution:** cook well.\n\n# Elder Cordial\n\nText.",
                 "> quoted line\n\nWarning: raw seeds are toxic.\n\n## Rowan Jelly\n\nText."):
        t = recipe_display_title(None, body)
        assert t and not is_safety_note_line(t) and not t.startswith(">"), t


def test_summary_skips_safety_lines_hazard_wording_and_citations():
    s = recipe_summary_line(None, BODY_SAFETY_FIRST)
    assert s == "This spring soup is bright, green and quick to make on a cold evening."
    body = ("Avoid ones growing on yew. The seed is not toxic[76]. It soothes digestion nicely enough.\n\n"
            "Chicken of the woods is a young fungus for a young appetite, firm and sulphur-bright.")
    assert recipe_summary_line("Fried Chicken of the Woods", body) == \
        "Chicken of the woods is a young fungus for a young appetite, firm and sulphur-bright."
    long = "A " + "very " * 60 + "long first sentence about elderflowers in June."
    out = recipe_summary_line(None, long)
    assert out.endswith("…") and len(out) <= 120


def test_type_is_the_dish_noun_before_with():
    assert propose_recipe_type("Raspberry Leaf Tea with Fermented Raspberries and Burnt Honey") == "drink"
    assert propose_recipe_type("Harebell Salad with Charred Wild Garlic Dressing") == "side"
    assert propose_recipe_type("Red Clover Flower Tea Cake with Honey Glaze") == "sweet"
    assert propose_recipe_type("Nettle, White Miso & Toasted Hazelnut Soup") == "main"
    assert propose_recipe_type("Wild-Green Sauerkraut") == "ferment"
    assert propose_recipe_type("Hairy Bittercress with Anchovy, Walnut & Pomegranate") is None   # → Other
    assert propose_recipe_type("Fool's Watercress with Anchovy") is None        # "Fool's" is not a fool


def test_website_link_only_https_on_melvinjarman():
    assert recipe_website_url_ok("https://melvinjarman.co.uk/recipes/nettle-soup")
    assert recipe_website_url_ok("https://www.melvinjarman.co.uk/x")
    for bad in ("http://melvinjarman.co.uk/x", "https://evil.example/melvinjarman.co.uk",
                "javascript:alert(1)", "https://melvinjarman.co.uk.evil.com/", ""):
        assert not recipe_website_url_ok(bad), bad


# ── backfill ──────────────────────────────────────────────────────────────────

def test_backfill_fills_only_empty_fields_and_second_run_is_a_no_op():
    import recipe_fields_backfill as bf
    path = os.path.join(tempfile.mkdtemp(prefix="rcbf_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    c = sqlite3.connect(path)
    c.execute("INSERT INTO species (id, scientific_name, name_key, edibility_verified, created_at, updated_at) "
              "VALUES (1, 'Urtica dioica', 'urtica dioica', 0, ?, ?)", (TS, TS))
    rows = [(1, None, BODY_SAFETY_FIRST, None, None), (2, None, BODY_PROSE, None, None),
            (3, "Kept Title", BODY_PROSE, "Kept summary.", "main")]
    for rid, title, body, summ, rtype in rows:
        c.execute("INSERT INTO species_recipes (id, species_id, title, body, season, is_preferred, is_medicinal_prep, "
                  "source, status, summary, recipe_type, hide_from_public, created_at, updated_at) VALUES "
                  "(?, 1, ?, ?, 'spring', 0, 0, 'ai_generated', 'approved', ?, ?, 0, ?, ?)",
                  (rid, title, body, summ, rtype, TS, TS))
    c.commit(); c.close()
    sys.argv = ["x", "--apply", "--db", path]
    bf.main()
    c = sqlite3.connect(path)
    got = {r[0]: r[1:] for r in c.execute("SELECT id, title, summary, recipe_type FROM species_recipes")}
    assert got[1][0] == "Nettle & Ramsons Soup" and got[1][2] == "main"
    assert not is_safety_note_line(got[1][1]) and "pregnan" not in got[1][1].lower()
    assert got[2][0] is None                                      # prose: needs a title, nothing written
    assert got[3] == ("Kept Title", "Kept summary.", "main")      # never overwritten
    props = bf.proposals(c)
    assert not any(p["new_title"] or p["new_summary"] or p["new_type"] for p in props)
    c.close()


# ── GET /api/recipes ──────────────────────────────────────────────────────────

# id, name, verdict, severity
SPECIES = [(1, "Urtica dioica", "edible", "none"), (2, "Allium ursinum", "caution", "none"),
           (3, "Conium maculatum", "toxic", "deadly"), (4, "Fagus sylvatica", "unknown", "unknown"),
           (5, "Taxus baccata", "toxic", "toxic"), (6, "Lunaria annua", "inedible", "none"),
           (7, "Sambucus nigra", None, "unknown")]


async def _api_db():
    path = os.path.join(tempfile.mkdtemp(prefix="rcapi_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    S = async_sessionmaker(eng, expire_on_commit=False)
    async with S() as s:
        for sid, name, verdict, sev in SPECIES:
            s.add(Species(id=sid, scientific_name=name, name_key=name.lower(), edibility_status=verdict,
                          toxicity_severity=sev, edibility_verified=True, edibility_verified_by="human"))
        await s.flush()
        s.add(CulinaryInfo(id=12, species_id=2, look_alike_warnings=LOOK))
        await s.flush()
        s.add(CulinaryInfoHistory(culinary_info_id=12, field_name="look_alike_warnings", old_value=None,
                                  new_value=LOOK, changed_by="human"))
        rid = 100
        for sid, *_ in SPECIES:
            rid += 1
            s.add(SpeciesRecipe(id=rid, species_id=sid, title=f"Dish {sid}", body=BODY_SAFETY_FIRST,
                                season="spring", source="ai_generated", status="approved"))
        s.add(SpeciesRecipe(id=200, species_id=1, title="Archived", body="x", status="archived"))
        s.add(SpeciesRecipe(id=201, species_id=1, title="Tincture", body="x", status="approved",
                            is_medicinal_prep=True))
        s.add(SpeciesRecipe(id=202, species_id=1, title=None, body=BODY_PROSE, status="approved",
                            hide_from_public=True))
        await s.commit()
    return eng, S


def test_api_lists_only_gated_recipes_and_caution_carries_its_warning():
    async def run():
        eng, S = await _api_db()
        async with S() as s:
            cur = await recipes_api.all_recipes(q=None, db=s, identity=CURATOR)
            gst = await recipes_api.all_recipes(q=None, db=s, identity=GUEST)
            srch = await recipes_api.all_recipes(q="ramsons soup", db=s, identity=CURATOR)
        await eng.dispose()
        return cur, gst, srch
    cur, gst, srch = _run(run())
    ids = sorted(r["id"] for r in cur["recipes"])
    assert ids == [101, 102, 202]                         # edible, caution, hidden-from-public (app shows it)
    by = {r["id"]: r for r in cur["recipes"]}
    assert by[102]["species"]["level"] == "caution"
    assert cur["safety"]["2"]["warnings"]["look_alike"]["text"] == LOOK
    assert by[202]["needs_title"] is True and by[202]["hide_from_public"] is True
    assert by[101]["needs_title"] is False
    assert all("body" not in r for r in cur["recipes"])
    assert sorted(r["id"] for r in gst["recipes"]) == ids  # guests: the same recipes the species pages show
    assert all("hide_from_public" not in r and "needs_title" not in r for r in gst["recipes"])
    assert sorted(r["id"] for r in srch["recipes"]) == [101, 102]   # matches the body (soup) — 202 is prose


def test_patch_validates_and_refuses_guests():
    async def run():
        eng, S = await _api_db()
        res = {}
        async with S() as s:
            for key, patch, who in (("guest", {"summary": "x"}, GUEST),
                                    ("bad_url", {"website_url": "https://evil.example/r"}, CURATOR),
                                    ("bad_type", {"recipe_type": "soup"}, CURATOR)):
                try:
                    await recipes_api.edit_recipe("Urtica dioica", 101, recipes_api.RecipePatch(**patch),
                                                  db=s, identity=who)
                    res[key] = "ok"
                except HTTPException as e:
                    res[key] = e.status_code
            out = await recipes_api.edit_recipe("Urtica dioica", 101, recipes_api.RecipePatch(
                title="  Nettle Soup ", summary="Green and quick.", recipe_type="main", hide_from_public=True,
                website_url="https://melvinjarman.co.uk/recipes/nettle"), db=s, identity=CURATOR)
            res["saved"] = (out["title"], out["summary"], out["recipe_type"], out["hide_from_public"], out["website_url"])
            out = await recipes_api.edit_recipe("Urtica dioica", 101, recipes_api.RecipePatch(
                recipe_type="", website_url=""), db=s, identity=CURATOR)
            res["cleared"] = (out["recipe_type"], out["website_url"])
        await eng.dispose()
        return res
    r = _run(run())
    assert r["guest"] == 403 and r["bad_url"] == 400 and r["bad_type"] == 400
    assert r["saved"] == ("Nettle Soup", "Green and quick.", "main", True, "https://melvinjarman.co.uk/recipes/nettle")
    assert r["cleared"] == (None, None)


# ── Recipes page / species page / Find (page JS in JavaScriptCore) ───────────

def _src(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


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


def _page_script(page):
    m = re.search(r"<script>\n// ── Recipes page ─+\n(.*?)\n\(function init\(\)", page, re.S)
    assert m, "recipes.html main script not found"
    return m.group(1)


def test_recipes_page_tile_links_to_the_recipe_card_and_shows_caution():
    page = _src("frontend/recipes.html")
    caution = {"level": "caution", "label": "⚠ caution", "culinary_allowed": True,
               "warnings": {"look_alike": {"text": LOOK, "reviewed": True}, "preparation": None}}
    edible = {"level": "none", "label": "", "culinary_allowed": True, "warnings": {}}
    toxic = {"level": "toxic", "label": "☠ toxic", "culinary_allowed": False, "warnings": {}}
    rec = lambda rid, sid, sci: {"id": rid, "title": f"Dish {rid}", "summary": "s", "recipe_type": None,
                                 "season": "spring", "parts": [], "approved_at": "2026-10-01", "website_url": None,
                                 "species": {"id": sid, "scientific_name": sci, "common": None},
                                 "walks": [], "needs_title": False, "hide_from_public": False}
    data = {"recipes": [rec(1, 1, "Urtica dioica"), rec(2, 2, "Allium ursinum"), rec(3, 3, "Conium maculatum")],
            "safety": {"1": edible, "2": caution, "3": toxic}, "types": []}
    stub = ("var window = this; var location = {search: ''}; "
            "function URLSearchParams(){ this.get = function(){ return null; }; } "
            "var document = {getElementById: function(){ return {value: 'az', style: {}, addEventListener: function(){} }; },"
            " querySelectorAll: function(){ return []; }};")
    js = "\n".join([stub, _src("frontend/static/js/esc.js"), _src("frontend/static/js/safety-gate.js"), _src("frontend/static/js/species-names.js"),
                    _page_script(page),
                    "_data = %s;" % json.dumps(data),
                    "var vis = _visible().map(function (r) { return r.id; });",
                    "print(JSON.stringify({vis: vis, href: recipeHref(_data.recipes[1]),"
                    " caution: tileHtml(_data.recipes[1]), edible: tileHtml(_data.recipes[0])}));"])
    out = _jsc(js)
    assert out["vis"] == [1, 2]                                  # fail closed: a toxic decision is never drawn
    assert out["href"] == "/species?s=Allium%20ursinum&recipe=2#recipe-card-2"
    assert "⚠ caution" in out["caution"] and LOOK in out["caution"]
    assert "⚠ caution" not in out["edible"]


def test_species_page_opens_the_linked_recipe_card():
    sp = _src("frontend/species.html")
    fn = sp[sp.index("function _openLinkedRecipe(recipes) {"):sp.index("// ── Recipe card: curator details")]
    assert "params.get('recipe')" in fn and "setRecipeSeason('all')" in fn
    assert "document.getElementById(`recipe-card-${want}`)" in fn and "recipe-linked" in fn
    assert "_renderRecipeBank(recipes, window._recipeSeason, el);\n      _openLinkedRecipe(recipes);" in sp
    assert 'id="${cardId}"' in sp and "const cardId = `recipe-card-${r.id}`;" in sp
    assert 'class="recipe-edit-form" id="recipe-edit-${r.id}" data-guest-hide' in sp   # curator only


def test_find_make_opens_the_recipes_page():
    idx = _src("frontend/index.html")
    assert 'onclick="_openRecipesPage()">🍳 Make?</button>' in idx
    assert "async function _findRecipes(" not in idx
    fn = idx[idx.index("function _openRecipesPage() {"):]
    fn = fn[:fn.index("\n}\n") + 3]
    assert "`/recipes?walk=${encodeURIComponent(walkId)}`" in fn and "'/recipes'" in fn
    nav = _src("frontend/static/js/site-header.js")
    assert "{ href: '/recipes',    label: 'Recipes' }" in nav


# ── public build ─────────────────────────────────────────────────────────────

def _export_conn():
    path = os.path.join(tempfile.mkdtemp(prefix="rcexp_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    c = sqlite3.connect(path)
    c.row_factory = sqlite3.Row
    for sid, name, verdict, sev in SPECIES:
        c.execute("INSERT INTO species (id, scientific_name, name_key, family, genus, edibility_status, "
                  "toxicity_severity, edibility_verified, edibility_verified_by, created_at, updated_at) "
                  "VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'human', ?, ?)",
                  (sid, name, name.lower(), "Urticaceae", name.split()[0], verdict, sev, TS, TS))
    c.execute("INSERT INTO species (id, scientific_name, name_key, family, genus, edibility_status, "
              "toxicity_severity, edibility_verified, edibility_verified_by, created_at, updated_at) VALUES "
              "(8, 'Anthriscus sylvestris', 'anthriscus sylvestris', 'Apiaceae', 'Anthriscus', 'caution', 'none', "
              "1, 'human', ?, ?)", (TS, TS))
    c.execute("INSERT INTO culinary_info (id, species_id, look_alike_warnings, created_at, updated_at) "
              "VALUES (12, 2, ?, ?, ?)", (LOOK, TS, TS))
    c.execute("INSERT INTO culinary_info_history (culinary_info_id, field_name, old_value, new_value, changed_at, "
              "changed_by) VALUES (12, 'look_alike_warnings', NULL, ?, '2026-10-20 10:00:00', 'human')", (LOOK,))
    rows = [(101, 1, "Nettle Soup", 0, None), (102, 2, "Ramsons Pesto", 0, "https://melvinjarman.co.uk/r/pesto"),
            (103, 3, "Hemlock Dish", 0, None), (104, 4, "Beech Dish", 0, None), (105, 5, "Yew Dish", 0, None),
            (106, 8, "Cow Parsley Dish", 0, None), (107, 1, "Hidden Nettle Dish", 1, None),
            (108, 1, None, 0, None), (109, 2, "Bad Link Dish", 0, "https://evil.example/x")]
    for rid, sid, title, hidden, url in rows:
        body = BODY_PROSE if title is None else BODY_SAFETY_FIRST
        c.execute("INSERT INTO species_recipes (id, species_id, title, body, season, is_preferred, is_medicinal_prep, "
                  "source, status, summary, recipe_type, hide_from_public, website_url, created_at, updated_at) "
                  "VALUES (?, ?, ?, ?, 'spring', 0, 0, 'ai_generated', 'approved', NULL, 'main', ?, ?, ?, ?)",
                  (rid, sid, title, body, hidden, url, TS, TS))
    c.execute("INSERT INTO species_recipes (id, species_id, title, body, season, is_preferred, is_medicinal_prep, "
              "source, status, hide_from_public, created_at, updated_at) VALUES (110, 1, 'Nettle Tincture', 'x', "
              "'spring', 0, 1, 'ai_generated', 'approved', 0, ?, ?)", (TS, TS))
    c.commit()
    return c


EXPORT_CFG = {"recipe_sources_allowed": ["ai_generated", "curator"], "exclude_recipe_ids": [],
              "exclude_recipe_species_ids": [], "teaser_skip_patterns": ["\\bmedic"]}


def test_public_bank_only_gated_unhidden_titled_recipes_and_never_the_body():
    import export
    c = _export_conn()
    bank, excluded = export.build_recipe_bank(c, EXPORT_CFG)
    assert sorted(b["recipe_id"] for b in bank) == [101, 102, 109]
    why = {rid: w for rid, _, w in excluded}
    assert why[103] == "toxic species" and why[105] == "toxic species"
    assert why[104].startswith("toxicity unknown") and why[106] == "Apiaceae — ID card only"
    assert why[107] == "hidden from public" and why[108] == "needs a title"
    assert why[110] == "medicinal preparation"
    b = {x["recipe_id"]: x for x in bank}
    assert b[102]["caution"] is True and b[102]["warnings"][0]["text"] == LOOK
    assert b[102]["url"] == "https://melvinjarman.co.uk/r/pesto" and b[109]["url"] is None
    assert b[101]["line"] == "This spring soup is bright, green and quick to make on a cold evening."
    dump = json.dumps(bank, ensure_ascii=False)
    for leak in ("200 g nettle tops", "Sweat the onion", "Avoid during pregnancy", "## Method"):
        assert leak not in dump, leak
    assert not any(set(x) & {"body", "ingredients", "method"} for x in bank)


def test_public_recipes_tab_renders_teasers_and_hash_opens_it():
    tpl = _src("scripts/experience_export/templates/index.html")
    assert 'var tabs = ["walk", "plants", "recipes", "taxonomy"];' in tpl
    assert 'show((location.hash || "#walk").slice(1));' in tpl
    seg = tpl[tpl.index("  // ── recipes: every public recipe"):tpl.index("  rfView.addEventListener")]
    seg = seg.replace('var rg = document.getElementById("recipe-grid");', "") \
             .replace('var rfView = document.getElementById("rf-view");', "")
    stub = ("function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;')"
            ".replace(/>/g,'&gt;').replace(/\"/g,'&quot;');}"
            "function recipeWarn(r){return (r.warnings||[]).map(function(w){return '<div class=\"warn\">'+esc(w.text)+'</div>';}).join('');}"
            "var rg = {innerHTML: ''}; var rfView = {value: 'now'};")
    bank = [{"recipe_id": 1, "dish": "Nettle Soup", "line": "Bright and green.", "season": "spring", "type": "main",
             "approved_at": "2026-10-20", "url": None, "sci": "Urtica dioica", "en": "Nettle", "caution": False,
             "warnings": []},
            {"recipe_id": 2, "dish": "Ramsons Pesto", "line": "Garlicky.", "season": "year-round", "type": "condiment",
             "approved_at": "2026-10-21", "url": "https://melvinjarman.co.uk/r/pesto", "sci": "Allium ursinum",
             "en": "Ramsons", "caution": True, "warnings": [{"kind": "look_alike", "heading": "Look-alikes", "text": LOOK}]},
            {"recipe_id": 3, "dish": "Elder Cordial", "line": "Floral.", "season": "summer", "type": "drink",
             "approved_at": "2026-10-19", "url": None, "sci": "Sambucus nigra", "en": "Elder", "caution": False,
             "warnings": []}]
    js = "\n".join([stub, "var D = {recipe_bank: %s};" % json.dumps(bank), seg,
                    "var groups = bankGroups('season', D.recipe_bank).map(function(g){return g.label;});",
                    "var recent = bankGroups('recent', D.recipe_bank)[0].items.map(function(r){return r.recipe_id;});",
                    "rfView.value = 'type'; renderBank();",
                    "print(JSON.stringify({groups: groups, recent: recent, html: rg.innerHTML,"
                    " tile: bankTile(D.recipe_bank[1])}));"])
    out = _jsc(js)
    assert out["groups"] == ["Spring", "Summer", "Year-round"]
    assert out["recent"] == [2, 1, 3]
    assert "⚠ Caution" in out["tile"] and LOOK in out["tile"]
    assert 'href="https://melvinjarman.co.uk/r/pesto"' in out["tile"] and "Full recipe →" in out["tile"]
    assert "Full recipe →" not in bankTile_html_for(out["html"], "Nettle Soup")


def bankTile_html_for(html, dish):
    i = html.index(dish)
    return html[i:html.index("</article>", i)]


def test_preview_card_links_to_the_recipes_tab_and_stays_script_free():
    pv = _src("scripts/experience_export/templates/preview.html")
    assert '<a href="index.html#recipes" target="_top">All recipes →</a>' in pv
    assert "<script" not in pv.lower()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
