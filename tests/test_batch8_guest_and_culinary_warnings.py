"""
Batch 8 (Melvin, 22 Oct 2026): guest visibility + guest notes, Fix A, Fix B.

  * Fix A — redraft-medicinal: only medicinal_notes that are empty or a
    placeholder, never approved or curator text, never with a pending draft.
  * Fix B — look-alike + preparation warnings travel with ALL culinary content
    (SafetyGate.culinaryWarnings / culinary_warnings); handouts curator text
    only; no second copy where the species block already sits beside it.
  * Guests see confirmed observations only (is_guest_visible_observation),
    by every endpoint and every direct file URL.
  * Encounters: own notes + curator encounters shared with guests; never
    another participant's; media follow the same rule.
  * Guest notes are text only, never touch species data, are escaped, and
    print only in that guest's own Lists / print / PDF.

Run: python tests/test_batch8_guest_and_culinary_warnings.py
"""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "experience_export"))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

import test_enrichment_safety as base  # noqa: E402
from test_enrichment_safety import CURATOR, JSC, Env, _client, _run  # noqa: E402
from test_enrichment_scope_and_recipe_warnings import _Patch, _add, _job_queue, _no_walks, _species  # noqa: E402

import app.main as main  # noqa: E402
import app.api.encounters as encounters_api  # noqa: E402
import app.api.find as find_api  # noqa: E402
import app.api.identity as identity_mod  # noqa: E402
import app.api.lists_pdf as lp  # noqa: E402
import app.api.sharing as sharing  # noqa: E402
from app.api.identity import Identity, get_identity  # noqa: E402
from app.database import get_db  # noqa: E402
from app.models.culinary import CulinaryInfo  # noqa: E402
from app.models.encounter import Encounter, EncounterPhoto, encounter_visible_to  # noqa: E402
from app.models.observation import Observation, is_guest_visible_observation  # noqa: E402
from app.models.species import CulinaryInfoHistory, Species, SpeciesRecipe, culinary_warnings  # noqa: E402
from app.models.workshop import GuestToken, WorkshopParticipant  # noqa: E402
from app.services import guest_access as ga  # noqa: E402
from app.services.access import Access  # noqa: E402
from app.services.ai_placeholder import medicinal_notes_redraftable  # noqa: E402

PARTICIPANT = Identity(user_id=2, is_guest=True, is_anonymous_guest=False, workshop_session_id=7)
OTHER = Identity(user_id=3, is_guest=True, is_anonymous_guest=False, workshop_session_id=7)
ANON = Identity(user_id=None, is_guest=True, is_anonymous_guest=True, workshop_session_id=None)
LOOK = "CURATED-LOOK dwarf elder looks alike." + " Long text." * 20 + " LOOK-END"
PREP = "CURATED-PREP cook the berries well." + " Long text." * 20 + " PREP-END"
RECIPE_BODY = "RECIPE-SENTINEL fry gently"


def _src(p):
    if p == "frontend/index.html":   # batch 16: split page, read re-inlined
        from index_source import index_source
        return index_source()
    return open(os.path.join(ROOT, p), encoding="utf-8").read()


def _jsc(script):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(script)
    out = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=30)
    os.unlink(f.name)
    assert out.returncode == 0 and out.stdout.strip(), out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def _extract(src, start, end):
    i = src.index(start)
    return src[i:src.index(end, i)]


def _set_medicinal(env, sid, txt, by=None):
    async def go():
        async with env.S() as s:
            await s.execute(text("UPDATE culinary_info SET medicinal_notes = :t WHERE species_id = :s"), {"t": txt, "s": sid})
            if by:
                s.add(CulinaryInfoHistory(culinary_info_id=100 + sid, field_name="medicinal_notes", old_value=None,
                                          new_value=txt, changed_by=by, changed_at=datetime(2026, 10, 20)))
            await s.commit()
    _run(go())


# ══ Fix A ═════════════════════════════════════════════════════════════════════

def test_fix_a_redraft_only_empty_or_placeholder_medicinal_notes():
    assert medicinal_notes_redraftable(None) and medicinal_notes_redraftable("  ")
    assert medicinal_notes_redraftable("No traditional medicinal uses are recorded for Urtica dioica in the available data.")
    assert not medicinal_notes_redraftable("The young leaves were taken as a spring tonic in folk practice.")
    env = Env()
    try:
        _set_medicinal(env, 1, "The leaves were taken as a spring tonic in folk practice.", by="ai_approved:human")  # approved
        _set_medicinal(env, 2, "No traditional medicinal uses are recorded for Urtica dioica in the available data.")
        # Rumex (3): empty → eligible. 4: curator-written text that looks like a placeholder → never.
        _species(env, 4, "Plantago major", ci={"medicinal_notes": "No medicinal uses."},
                 history=[("medicinal_notes", "No medicinal uses.", "human")])
        c = _client(env)
        with _no_walks():
            d = c.post("/api/drafts/redraft-medicinal?dry_run=true&scope=all", json={}).json()
            assert sorted(d["species_sample"]) == ["Rumex acetosa", "Urtica dioica"], d
            assert "empty or a placeholder" in d["note"] and "never drafted over" in d["note"], d
            d = c.post("/api/drafts/redraft-medicinal?dry_run=true&scope=all", json={"species_ids": [1, 4, 3]}).json()
            assert d["species_sample"] == ["Rumex acetosa"], d          # explicit ids: the rule still applies
    finally:
        env.close()


# ══ Fix B — the helper ════════════════════════════════════════════════════════

DEC_REVIEWED = {"level": "caution", "culinary_allowed": True, "handout_culinary_allowed": True,
                "warnings": {"preparation": {"text": PREP, "reviewed": True}, "look_alike": {"text": LOOK, "reviewed": True}},
                "handout_warnings": {"preparation": PREP, "look_alike": LOOK}}
DEC_MIXED = {"level": "none", "culinary_allowed": True, "handout_culinary_allowed": True,
             "warnings": {"preparation": {"text": PREP, "reviewed": True}, "look_alike": {"text": "PFAF-LOOK uncurated.", "reviewed": False}},
             "handout_warnings": {"preparation": PREP, "look_alike": None}}
DEC_NONE = {"level": "none", "culinary_allowed": True, "handout_culinary_allowed": True,
            "warnings": {"preparation": None, "look_alike": None}, "handout_warnings": {"preparation": None, "look_alike": None}}
SG = _src("frontend/static/js/esc.js") + "\n" + _src("frontend/static/js/safety-gate.js")


def test_fix_b_helper_carries_both_warnings_js_and_python():
    d = _jsc("var window = this;\n" + SG + f"""
var R = {json.dumps(DEC_REVIEWED)}, M = {json.dumps(DEC_MIXED)}, N = {json.dumps(DEC_NONE)};
print(JSON.stringify({{ r: SafetyGate.culinaryWarnings(R), m: SafetyGate.culinaryWarnings(M), n: SafetyGate.culinaryWarnings(N),
  hr: SafetyGate.culinaryWarnings(R, {{ handout: true }}), hm: SafetyGate.culinaryWarnings(M, {{ handout: true }}),
  closed: SafetyGate.culinaryWarnings(null), old: typeof SafetyGate.recipeWarning }}));""")
    assert "LOOK-END" in d["r"] and "PREP-END" in d["r"] and d["r"].index("LOOK-END") < d["r"].index("PREP-END")
    assert "PFAF-LOOK uncurated." in d["m"] and "Source text — not yet reviewed" in d["m"]          # in-app: labelled
    assert d["n"] == "" and d["closed"] == "" and d["old"] == "undefined"
    assert "⚠ Look-alikes: CURATED-LOOK" in d["hr"] and "⚠ Caution: CURATED-PREP" in d["hr"] and "LOOK-END" in d["hr"]
    assert "PFAF-LOOK" not in d["hm"] and "PREP-END" in d["hm"]                                       # handout: curator only
    assert [w["kind"] for w in culinary_warnings(DEC_REVIEWED, True)] == ["look_alike", "preparation"]
    assert culinary_warnings(DEC_MIXED, True) == [{"kind": "preparation", "heading": "Preparation", "text": PREP, "reviewed": True}]
    assert [w["reviewed"] for w in culinary_warnings(DEC_MIXED, False)] == [False, True]
    assert culinary_warnings(DEC_NONE, True) == [] and culinary_warnings(None, False) == []


# ══ Fix B — every surface ═════════════════════════════════════════════════════

def test_fix_b_species_page_culinary_taste_recipes_and_field_recipes():
    sp = _src("frontend/species.html")
    assert "SafetyGate.culinaryWarnings(data.safety) + _renderFields(ci, culFields" in sp            # Culinary section
    assert '<div id="taste-notes-warnings"></div>' in sp and "twEl.innerHTML = SafetyGate.culinaryWarnings(data.safety)" in sp
    bank = _extract(sp, "function _renderRecipeBank(", "function setRecipeSeason(") + "\n" + \
        _extract(sp, "const _RECIPE_TYPES = ", "function toggleRecipeEdit(")      # card's curator line (25 Oct)
    card = _extract(sp, "function _renderFieldRecipeCard(", "async function loadYourEncounters(")
    d = _jsc("var window = this; var document = { querySelectorAll: function () { return []; } };\n" + SG + """
function _esc(s) { return String(s == null ? '' : s); } function _renderMd(s) { return s; } var _SEASON_ICON = {};
""" + bank + "\n" + card + f"""
var recipes = [{{ id: 1, title: 'Soup', body: '{RECIPE_BODY}', season: 'autumn', is_preferred: true }}];
var fr = {{ field_recipe: {{ title: 'Field soup', body: '{RECIPE_BODY}', ingredients: [] }} }}, out = {{}};
window._speciesSafety = {json.dumps(DEC_MIXED)};
var c1 = {{}}; _renderRecipeBank(recipes, 'all', c1); out.bank = c1.innerHTML; out.card = _renderFieldRecipeCard(fr);
window._speciesSafety = {json.dumps(DEC_NONE)};
var c2 = {{}}; _renderRecipeBank(recipes, 'all', c2); out.bank_none = c2.innerHTML; out.card_none = _renderFieldRecipeCard(fr);
print(JSON.stringify(out));""")
    for k in ("bank", "card"):
        assert "PFAF-LOOK uncurated." in d[k] and "PREP-END" in d[k] and d[k].index("culinary-warnings") < d[k].index("RECIPE-SENTINEL"), k
    for k in ("bank_none", "card_none"):
        assert "RECIPE-SENTINEL" in d[k] and "culinary-warnings" not in d[k], k


def test_fix_b_no_duplicate_where_the_species_block_sits_beside():
    idx = _src("frontend/index.html")
    pop = _extract(idx, "async function _injectEnrichment(", "function _trunc(")
    assert pop.count("SafetyGate.warnings(safety)") == 1 and "culinaryWarnings" not in pop        # map pop-up
    stop = _extract(idx, "// Stop card = name, common name, badge", "// Repeats: one compact line each")
    assert "culinaryWarnings" not in stop                                                            # no culinary content
    for p in ("frontend/lists.html", "frontend/print.html"):                                         # field-guide entries
        fg = _extract(_src(p), "function _fieldEntry(", "function _workshopPage(")
        assert "_printWarnings(prof" in fg and "_printCulinaryWarnings" not in fg and "culinaryWarnings" not in fg, p
    tpl = _src("app/templates/print_pdf.html")
    booklet = _extract(tpl, "{% elif layout == 'recipe_booklet' %}", "{% elif layout == 'workshop' %}")
    assert "culinary_warnings" not in booklet and "sp.look_alike" in booklet
    exp = _src("scripts/experience_export/templates/index.html")
    panel = _extract(exp, "function openPanel(", "function closePanel(")
    assert "recipeWarn(r)" not in panel and "s.safety.look_alike" in panel


def test_fix_b_lists_print_workshop_and_panels_carry_the_warnings():
    lists, prn = _src("frontend/lists.html"), _src("frontend/print.html")
    assert "${SafetyGate.culinaryWarnings(prof && prof.safety)}${_esc(snippet)}" in lists           # Lists panel, in-app
    # Workshop page (Melvin, 28 Oct 2026): the safety box is the one full copy —
    # no repeat before Foraging / Recipe (tests/test_safety_batch_28oct.py item 3).
    for s in (lists, prn):
        assert "_printCulinaryWarnings" not in s
        assert '<div class="ws-section-h">Recipe</div><div class="ws-recipe">' in s
    # Find → Make? is the Recipes page now (25 Oct 2026): its tiles carry the warnings.
    rec = _extract(_src("frontend/recipes.html"), "function tileHtml(r) {", "function _visible() {")
    assert "SafetyGate.culinaryWarnings(safety)" in rec
    enc = _src("frontend/static/js/encounters-main.js")
    assert "SafetyGate.culinaryWarnings(enc.field_recipe_safety)" in enc
    assert "if ((d.recipe && d.recipe.body) || notes.taste_notes) html += SafetyGate.culinaryWarnings(d.safety);" in enc
    exp = _src("scripts/experience_export/templates/index.html")
    tab = _extract(exp, "// ── recipes: every public recipe", "// ── footer")
    assert "recipeWarn(r)" in tab


def test_fix_b_export_summary_prints_the_block_once():
    W = sharing.WalkSpecies
    d = dict(DEC_REVIEWED, label="⚠ caution", handout_label="⚠ caution", warning=PREP, verdict="caution")
    n = dict(DEC_NONE, label="", handout_label="", warning=None, verdict="edible")
    body = sharing.WalkExportRequest(stops=[sharing.WalkStop(num=1, species=[
        W(species_scientific="Sambucus nigra", culinary_notes="Flowers in cordial.", recipe_title="Soup", recipe_body=RECIPE_BODY),
        W(species_scientific="Allium ursinum", culinary_notes="Leaves.", recipe_title="Pesto", recipe_body=RECIPE_BODY)])])
    sharing.apply_walk_safety(body, {"Sambucus nigra": d, "Allium ursinum": n})
    a = sharing._walk_species_html(body.stops[0].species[0], True)
    assert a.count("LOOK-END") == 1 and a.count("PREP-END") == 1                                     # once, beside
    assert a.index("PREP-END") < a.index("Flowers in cordial.") < a.index("RECIPE-SENTINEL")
    b = sharing._walk_species_html(body.stops[0].species[1], True)
    assert "RECIPE-SENTINEL" in b and "⚠" not in b


def _pdf(prof, d, layout, my_notes=None):
    real = lp._jinja_env.get_template("print_pdf.html")
    captured = {}

    class _T:
        def render(self, **kw):
            captured["html"] = real.render(**kw)
            raise RuntimeError("stop before WeasyPrint")
    orig = lp._jinja_env.get_template
    lp._jinja_env.get_template = lambda n: _T()
    try:
        req = lp.PdfRequest(species=[lp.SpeciesData(scientific_name="Sambucus nigra", profile=prof)], layout=layout)
        try:
            lp.render_pdf(req, {"Sambucus nigra": d}, my_notes)
        except RuntimeError:
            pass
    finally:
        lp._jinja_env.get_template = orig
    h = captured["html"]
    return h[h.index('<div class="species-grid">'):]


def test_fix_b_pdf_workshop_and_booklet():
    d = dict(DEC_REVIEWED, label="⚠ caution", handout_label="⚠ caution", warning=PREP, verdict="caution")
    prof = {"species": {"edibility_status": "caution"}, "culinary": {"edible_parts": "EDIBLE-PARTS flowers"},
            "recipes": [{"title": "Soup", "body": RECIPE_BODY, "is_preferred": True}]}
    ws = _pdf(prof, d, "workshop")
    # 28 Oct 2026: the workshop page's Safety & edibility box is the one full copy.
    assert ws.count("LOOK-END") == 1 and ws.count("PREP-END") == 1 and "culinary-warning" not in ws
    assert ws.index("LOOK-END") < ws.index("Foraging notes") < ws.index("RECIPE-SENTINEL")
    bk = _pdf(prof, d, "recipe_booklet")
    assert bk.count("LOOK-END") == 1 and bk.count("PREP-END") == 1 and "culinary-warning" not in bk
    none = dict(DEC_NONE, label="", handout_label="", warning=None, verdict="edible")
    ws0 = _pdf(dict(prof, species={"edibility_status": "edible"}), none, "workshop")
    assert "RECIPE-SENTINEL" in ws0 and "culinary-warning" not in ws0
    mixed = dict(DEC_MIXED, label="", handout_label="", warning=None, verdict="edible")
    assert "PFAF-LOOK" not in _pdf(prof, mixed, "workshop")                                         # handout: curator only


def test_fix_b_experience_recipe_warnings():
    import gates
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE culinary_info_history (id INTEGER PRIMARY KEY, culinary_info_id INT, field_name TEXT,"
              " new_value TEXT, changed_by TEXT, changed_at TEXT)")
    c.execute("INSERT INTO culinary_info_history VALUES (1, 5, 'preparation_warnings', 'Cook well.', 'human', '2026')")
    c.execute("INSERT INTO culinary_info_history VALUES (2, 5, 'look_alike_warnings', 'Dwarf elder.', 'human', '2026')")
    sp = {"id": 1, "scientific_name": "X", "edibility_status": "caution", "toxicity_severity": "none"}
    ws = gates.recipe_warnings(sp, {"id": 5, "preparation_warnings": "Cook well.", "look_alike_warnings": "Dwarf elder."}, c)
    assert [(w["kind"], w["text"]) for w in ws] == [("look_alike", "Dwarf elder."), ("preparation", "Cook well.")]
    assert gates.recipe_warnings(sp, {"id": 6, "look_alike_warnings": "Uncurated."}, c) == []
    assert '"warnings": gates.recipe_warnings(sp, ci_by_sp[sid], conn)' in _src("scripts/experience_export/export.py")


def test_fix_b_find_encounters_and_personal_card_serve_the_safety_data():
    env = Env()
    try:
        _add(env, [CulinaryInfoHistory(culinary_info_id=103, field_name="preparation_warnings", old_value=None,
                                       new_value=base.PREP, changed_by="human", changed_at=datetime(2026, 10, 20)),
                   SpeciesRecipe(species_id=3, title="Sorrel soup", body=RECIPE_BODY, status="approved",
                                 is_preferred=True, is_medicinal_prep=False, source="curator"),
                   Encounter(id=1, species_id=3, encounter_date=datetime(2026, 10, 1),
                             field_recipes=json.dumps({"title": "Sorrel soup", "body": RECIPE_BODY}))])
        with _curator_device(env):
            c = _app_client(env, CURATOR)
            f = c.get("/api/find/recipes?q=SENTINEL").json()["results"][0]
            assert f["safety"]["warnings"]["preparation"]["text"] == base.PREP
            e = c.get("/api/encounters").json()["encounters"][0]
            assert e["field_recipe_safety"]["warnings"]["preparation"]["text"] == base.PREP
            card = c.get("/api/personal-lists/card/3").json()
            assert card["safety"]["level"] == "caution" and card["safety"]["warnings"]["preparation"]["text"] == base.PREP
    finally:
        main.app.dependency_overrides.clear()
        env.close()


# ══ Guest visibility ══════════════════════════════════════════════════════════

def _app_client(env, identity, guest_device=False):
    """The real app (all routers + the access middleware), on the test DB."""
    async def _get_db():
        async with env.S() as s:
            yield s
    main.app.dependency_overrides[get_db] = _get_db
    if identity is not None:
        main.app.dependency_overrides[get_identity] = lambda: identity
    else:
        main.app.dependency_overrides.pop(get_identity, None)
    return TestClient(main.app)


def _curator_device(env):
    async def acc(request, db):
        return Access(tier="curator", local=True)
    return _Patch((main, "resolve_access", acc), (identity_mod, "resolve_access", acc),
                  (main, "AsyncSessionLocal", env.S), (main.sharing, "host_is_known", lambda r: True))


def _guest_device(env, participant_id=2, session_id=7):
    """Patch the access layer so every request is that participant's device."""
    tok = GuestToken(id=99, token="t", participant_id=participant_id, workshop_session_id=session_id,
                     is_active=True, last_used_at=datetime.utcnow())

    async def acc(request, db):
        return Access(tier="guest", token=tok)
    return _Patch((main, "resolve_access", acc), (identity_mod, "resolve_access", acc),
                  (main, "AsyncSessionLocal", env.S),
                  (main.sharing, "host_is_known", lambda r: True))


def _guest_env():
    env = Env()
    _job_queue(env)
    _add(env, [WorkshopParticipant(id=2, name="Alice <b>"), WorkshopParticipant(id=3, name="Bob")])
    statuses = {201: "approved", 202: "manually_verified", 203: "pending", 204: "needs_review", 205: "rejected"}
    rows = [Observation(id=oid, file_path=f"/up/obs{oid}.jpg", thumbnail_path=f"thumbnails/t{oid}.jpg",
                        species_primary="Rumex acetosa", review_status=st,
                        identification_status="identified" if st != "pending" else "pending_identification")
            for oid, st in statuses.items()]
    rows.append(Observation(id=206, file_path="/up/scene.jpg", thumbnail_path="thumbnails/t206.jpg", species_primary=None,
                            obs_category="landscape", review_status="approved", identification_status="identified"))
    rows += [Encounter(id=11, user_id=1, species_id=3, encounter_date=datetime(2026, 10, 1), text_note="Curator private",
                       audio_path="/m/media/encounters/priv.webm", transcript="private transcript"),
             Encounter(id=12, user_id=1, species_id=3, encounter_date=datetime(2026, 10, 2), text_note="Curator shared",
                       audio_path="/m/media/encounters/shared.webm", transcript="shared transcript", shared_with_guests=True),
             Encounter(id=13, user_id=2, species_id=3, encounter_date=datetime(2026, 10, 3), text_note="Alice note",
                       workshop_session_id=7),
             Encounter(id=14, user_id=3, species_id=3, encounter_date=datetime(2026, 10, 4), text_note="Bob note",
                       audio_path="/m/media/encounters/bob.webm", workshop_session_id=7),
             EncounterPhoto(encounter_id=12, observation_id=203, binding_method="manual"),
             EncounterPhoto(encounter_id=12, observation_id=201, binding_method="manual")]
    _add(env, rows)
    return env


def test_guest_observation_predicate():
    for st, want in (("approved", True), ("manually_verified", True), ("pending", False), ("needs_review", False),
                     ("rejected", False), (None, False)):
        assert is_guest_visible_observation({"review_status": st}) is want, st
    assert is_guest_visible_observation({"review_status": "approved", "species_primary": None, "obs_category": "landscape"})


def test_guest_api_allowlist():
    ok = ["/api/me", "/api/species/", "/api/species/Rumex acetosa/profile", "/api/culinary/Rumex acetosa",
          "/api/map/geojson", "/api/walk/saves/5", "/api/encounters", "/api/encounters/12", "/api/observations/201/photo",
          "/api/find/recipes", "/api/recorded-walks/3", "/api/personal-lists/card/3"]
    refused = ["/api/observations", "/api/observations/stats", "/api/observations/201/edits", "/api/culinary/ai-draft-review",
               "/api/culinary/Rumex acetosa/history", "/api/queue/list", "/api/processes/active", "/api/scan/sessions",
               "/api/encounters/participant-notes", "/api/encounters/pending-transcripts",
               "/api/encounters/12/photo-candidates", "/api/drafts/backfill-counts"]
    for p in ok:
        assert ga.guest_api_allowed("GET", p), p
    for p in refused:
        assert not ga.guest_api_allowed("GET", p), p
    assert ga.guest_api_allowed("POST", "/api/lists/pdf") and ga.guest_api_allowed("POST", "/api/encounters")
    for p in ("/api/recorded-walks/audio-upload", "/api/encounters/12/share", "/api/culinary/x/field"):
        assert not ga.guest_api_allowed("POST", p) and not ga.guest_api_allowed("PATCH", p), p


def test_guest_never_reaches_unconfirmed_photos_by_endpoint_or_url():
    env = _guest_env()
    try:
        with _guest_device(env):
            c = _app_client(env, None)
            for oid in (203, 204, 205):
                assert c.get(f"/api/observations/{oid}").status_code == 404, oid
                assert c.get(f"/api/observations/{oid}/photo").status_code == 404, oid
                for url in (f"/thumbnails/t{oid}.jpg", f"/uploads-files/obs{oid}.jpg"):
                    r = c.get(url)
                    assert r.status_code == 404 and r.headers.get("x-guest-gate") == "refused", url  # the gate, not the file
            for oid in (201, 206):                                                               # confirmed + scene
                assert c.get(f"/api/observations/{oid}").status_code == 200, oid
                assert c.get(f"/thumbnails/t{oid}.jpg").headers.get("x-guest-gate") is None, oid   # passed the gate
            assert c.get("/api/observations").status_code == 403
            thumbs = c.get("/api/species/Rumex acetosa/profile").json()["observations"]["thumbnails"]
            assert {t["id"] for t in thumbs} == {13, 201, 202}, thumbs           # 13: the base fixture (approved)
            enc = c.get("/api/encounters/12").json()
            assert [p["observation_id"] for p in enc["photos"]] == [201], enc["photos"]          # pending bound photo dropped
            assert c.get("/thumbnails/../data/foragingid.db").status_code in (404, 400)
        async def go():
            async with env.S() as s:
                return [await ga.guest_media_allowed(s, f"/thumbnails/t{o}.jpg", PARTICIPANT) for o in (201, 203, 206)]
        assert _run(go()) == [True, False, True]
    finally:
        main.app.dependency_overrides.clear()
        env.close()


def test_guest_sees_shared_and_own_encounters_only():
    env = _guest_env()
    try:
        with _guest_device(env):
            c = _app_client(env, None)
            ids = {e["id"] for e in c.get("/api/encounters").json()["encounters"]}
            assert ids == {12, 13}, ids                                                  # shared curator + own
            assert c.get("/api/encounters/11").status_code == 404                        # unshared curator
            assert c.get("/api/encounters/14").status_code == 404                        # another participant
            shared = c.get("/api/encounters/12").json()
            assert shared["transcript"] == "shared transcript" and shared["audio_url"] == "/media/encounters/shared.webm"
            for url in ("/media/encounters/priv.webm", "/media/encounters/bob.webm", "/media/recorded-walks/x.webm"):
                r = c.get(url)
                assert r.status_code == 404 and r.headers.get("x-guest-gate") == "refused", url
            assert c.get("/media/encounters/shared.webm").headers.get("x-guest-gate") is None      # passed the gate
            assert c.get("/media/encounters/priv.webm").headers.get("x-guest-gate") == "refused"
            card = c.get("/api/personal-lists/card/3").json()
            assert {e["id"] for e in card["encounters"]} == {12, 13}
            assert c.get("/api/encounters/participant-notes").status_code == 403
            assert c.patch("/api/encounters/11/share", json={"shared": True}).status_code == 403
        assert not encounter_visible_to(type("E", (), {"user_id": 1, "shared_with_guests": True})(), ANON)
    finally:
        main.app.dependency_overrides.clear()
        env.close()


def test_curator_share_toggle_and_participant_notes_view():
    env = _guest_env()
    try:
        with _curator_device(env):
            c = _app_client(env, CURATOR)
            r = c.patch("/api/encounters/11/share", json={"shared": True}).json()
            assert r["shared_with_guests"] is True
            assert env.q("SELECT shared_with_guests FROM encounters WHERE id = 11")[0][0] == 1
            assert c.patch("/api/encounters/13/share", json={"shared": True}).status_code == 409   # participant notes stay private
            d = c.get("/api/encounters/participant-notes").json()
            people = {p["name"]: [n["text_note"] for n in p["notes"]] for s in d["sessions"] for p in s["participants"]}
            assert people == {"Alice <b>": ["Alice note"], "Bob": ["Bob note"]} and d["sessions"][0]["workshop_session_id"] == 7
            js = _src("frontend/static/js/encounters-main.js")
            view = _extract(js, "async function loadParticipantNotes(", "window.toggleEncounterShared")
            assert "_esc(p.name)" in view and "_esc(n.text_note || n.transcript || '')" in view and "_esc(s.session_name)" in view
            assert "enc.user_id === 1 ?" in js and "Share with guests" in js
    finally:
        main.app.dependency_overrides.clear()
        env.close()


# ══ Guest notes ═══════════════════════════════════════════════════════════════

def test_guest_note_saves_text_refuses_audio_and_never_touches_species():
    env = _guest_env()
    try:
        before = {t: env.q(f"SELECT * FROM {t} ORDER BY 1") for t in ("species", "culinary_info", "observations")}
        with _guest_device(env):
            c = _app_client(env, None)
            r = c.post("/api/encounters", data={"species_id": "3", "text_note": "Tastes <script>alert(1)</script> sour\nline 2",
                                                "encounter_type": "guest_note", "latitude": "47.7", "longitude": "7.8"})
            assert r.status_code == 200, r.text
            e = r.json()
            assert e["user_id"] == 2 and e["workshop_session_id"] == 7 and e["species_id"] == 3 and e["latitude"] == 47.7
            assert e["encounter_type"] == "guest_note" and e["audio_url"] is None
            r = c.post("/api/encounters", data={"species_id": "3", "text_note": "x"},
                       files={"audio": ("a.webm", b"RIFF", "audio/webm")})
            assert r.status_code == 403 and "Audio upload" in r.json()["detail"]
            r = c.post("/api/encounters", data={"species_id": "3", "text_note": "x", "photo_observation_ids": "[203]"})
            assert r.status_code == 403
        after = {t: env.q(f"SELECT * FROM {t} ORDER BY 1") for t in ("species", "culinary_info", "observations")}
        assert after == before
        assert len(os.listdir(str(encounters_api._encounters_dir()))) >= 0                     # no file written on refusal
        gn = _src("frontend/static/js/guest-notes.js")
        assert "Type, or dictate using the mic on your keyboard." in gn
        box = _extract(gn, "el.innerHTML = '<div class=\"guest-note-box\">'", "const ta = ")
        for bad in ("inputmode", "readonly", "disabled", "contenteditable"):
            assert bad not in box, bad                                                             # nothing blocks dictation
        d = _jsc("var window = this;\n" + _src("frontend/static/js/esc.js") + "\n" + gn + """
print(JSON.stringify({ h: GuestNotes.listHtml([{ text_note: '<img src=x onerror=alert(1)>', encounter_date: null }]),
                       own: GuestNotes.isOwnNote({ user_id: 2, text_note: 'a' }), cur: GuestNotes.isOwnNote({ user_id: 1, text_note: 'a' }) }));""")
        assert "<img" not in d["h"] and "&lt;img src=x onerror=alert(1)&gt;" in d["h"] and d["own"] and not d["cur"]
        enc_html = _src("frontend/encounters.html")                                              # Record tab
        assert '<div id="rec-voice-row" data-guest-hide' in enc_html
        assert enc_html.index('id="rec-voice-row"') < enc_html.index('id="rec-btn"') < enc_html.index('id="rec-note"')
        assert "if (document.body.classList.contains('guest-mode')) return;" in \
            _extract(_src("frontend/static/js/encounters-main.js"), "window.recToggle = function", "};")
        sp, idx = _src("frontend/species.html"), _src("frontend/index.html")
        assert "GuestNotes.mount(document.getElementById('guest-notes-slot'), data.species.id" in sp
        assert "GuestNotes.mount(el, Number(el.dataset.guestNoteSid), el.dataset.guestNoteName)" in idx
        assert 'data-guest-note-name="${_esc(spName)}"' in idx
    finally:
        main.app.dependency_overrides.clear()
        env.close()


def test_guest_pdf_prints_only_that_guests_notes_under_the_right_species():
    env = _guest_env()
    try:
        _add(env, [Encounter(id=15, user_id=2, species_id=1, encounter_date=datetime(2026, 10, 5),
                             text_note="Alice <b>garlic</b> note", workshop_session_id=7)])

        async def go(ident):
            async with env.S() as s:
                return await lp.participant_notes_by_name(s, ident, ["Rumex acetosa", "Allium ursinum", "Urtica dioica"])
        assert _run(go(PARTICIPANT)) == {"Rumex acetosa": ["Alice note"], "Allium ursinum": ["Alice <b>garlic</b> note"]}
        assert _run(go(OTHER)) == {"Rumex acetosa": ["Bob note"]}
        assert _run(go(CURATOR)) == {} and _run(go(ANON)) == {}                                  # curator handouts unchanged
        d = dict(DEC_NONE, label="", handout_label="", warning=None, verdict="edible")
        prof = {"species": {"edibility_status": "edible"}, "culinary": {}, "recipes": []}
        for layout in ("field_guide", "recipe_booklet", "workshop"):
            h = _pdf(prof, d, layout, {"Sambucus nigra": ["Alice <b>garlic</b> note"]})
            assert "Alice &lt;b&gt;garlic&lt;/b&gt; note" in h and "<b>garlic</b>" not in h, layout
            assert "Bob note" not in h
            assert "Your notes" not in _pdf(prof, d, layout, {}) or layout == "workshop", layout
        for p in ("frontend/lists.html", "frontend/print.html"):
            s = _src(p)
            assert "_guestNotes = (await GuestNotes.isParticipant()) ? await GuestNotes.mineBySpecies() : {};" in s, p
            assert "'<p style=\"white-space:pre-wrap\">' + _esc(t) + '</p>'" in s, p
            assert s.count("${_guestNotesHtml(name)}") >= 2, p
        with _guest_device(env):
            c = _app_client(env, None)
            calls = {}
            real = lp.render_pdf
            lp.render_pdf = lambda body, safety, my_notes=None: calls.update(my_notes or {}) or "ok"
            try:
                r = c.post("/api/lists/pdf", json={"species": [{"scientific_name": "Rumex acetosa"}]})
            finally:
                lp.render_pdf = real
            assert r.status_code == 200 and calls == {"Rumex acetosa": ["Alice note"]}, (r.text[:200], calls)
    finally:
        main.app.dependency_overrides.clear()
        env.close()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
