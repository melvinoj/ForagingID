"""
Tests for batch 5 (audit REPORT section 9, 21 Oct 2026): B2-01 / B2-04 + the P1
shared safety gate + B2-09.

  * safety_decision() (app/models/species.py) is the ONE rule: culinary content
    only when toxicity_severity == 'none' (and the verdict isn't toxic); labels
    deadly "☠ deadly", toxic "☠ toxic", unknown/missing "⚠ toxicity unknown",
    caution "⚠ caution" + the approved (curator-authored) warning.
  * It is served as `safety` by /api/culinary/{name} and /profile.
  * Server-rendered surfaces re-ask the DB (B2-09): PDF and walk Export summary
    ignore client-sent severity / culinary text.
  * Pages (map pop-up, walk panel, species page, Lists, browser print) read the
    served decision through static/js/safety-gate.js — grep-style checks, since
    Code cannot run them in a browser (and there is no Node here).

No external calls. Throw-away SQLite DB.

Run from project root:  python tests/test_batch5_safety_gate.py
"""

import asyncio
import os
import re
import sys
import tempfile
from datetime import datetime

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main  # noqa: E402,F401  (registers every model on Base.metadata)
import app.api.culinary as culinary  # noqa: E402
import app.api.lists_pdf as lp  # noqa: E402
import app.api.sharing as sharing  # noqa: E402
from app.api.identity import Identity  # noqa: E402
from app.database import Base  # noqa: E402
from app.models.culinary import CulinaryInfo  # noqa: E402
from app.models.species import (CulinaryInfoHistory, SAFETY_LABELS, Species, SpeciesRecipe,  # noqa: E402
                                safety_decision)
from app.services.safety_gate import safety_by_names  # noqa: E402
from app.services.taxonomy import normalize_taxon_key  # noqa: E402

CURATOR = Identity(user_id=1, is_guest=False, is_anonymous_guest=False, workshop_session_id=None)
GUEST = Identity(user_id=None, is_guest=True, is_anonymous_guest=True, workshop_session_id=None)

EDIBLE_TEXT = "EDIBLE-PARTS-SENTINEL young leaves"
TASTE_TEXT = "TASTE-SENTINEL nutty"
RECIPE_TEXT = "RECIPE-SENTINEL fry gently"
CAUTION_WARN = "Cook berries well; raw berries cause nausea."
AI_WARN = "AI-approved prep text, not curator-authored."

# id, name, verdict, severity
SPECIES = [
    (1, "Conium maculatum", "toxic", "deadly"),
    (2, "Hedera helix", "toxic", "toxic"),
    (3, "Heracleum sibiricum", "unknown", "unknown"),
    (4, "Sambucus nigra", "caution", "none"),       # curator-authored warning
    (5, "Ajuga reptans", "caution", "none"),        # warning only AI-approved → no warning
    (6, "Allium ursinum", "edible", "none"),
    (7, "Tragopogon dubius", None, "none"),         # NULL verdict = never assessed → unknown (21 Oct follow-up)
    (8, "Briza media", "inedible", "none"),         # inedible → blocked, no label, verdict badge kept
]
EXPECT = {   # name: (level, allowed, warning)
    "Conium maculatum":   ("deadly", False, None),
    "Hedera helix":       ("toxic", False, None),
    "Heracleum sibiricum": ("unknown", False, None),
    "Sambucus nigra":     ("caution", True, CAUTION_WARN),
    "Ajuga reptans":      ("caution", True, None),
    "Allium ursinum":     ("none", True, None),
    "Tragopogon dubius":  ("unknown", False, None),
    "Briza media":        ("none", False, None),
    "Not in the database": ("unknown", False, None),
}
BLOCKED = [n for n, (lvl, ok, _) in EXPECT.items() if not ok]
# Outgoing surfaces (batch 6): a caution species without a curator-authored
# warning also withholds culinary content there (handout_culinary_allowed).
HANDOUT_WITHHELD = {"Ajuga reptans"}


def _run(coro):
    return asyncio.run(coro)


async def _db():
    path = os.path.join(tempfile.mkdtemp(prefix="b5test_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    S = async_sessionmaker(eng, expire_on_commit=False)
    async with S() as s:
        for sid, name, verdict, sev in SPECIES:
            s.add(Species(id=sid, scientific_name=name, name_key=normalize_taxon_key(name),
                          edibility_status=verdict, toxicity_severity=sev, kingdom="Plantae",
                          common_names='["Common ' + name.split()[0] + '"]'))
            prep = CAUTION_WARN if sid == 4 else AI_WARN if sid == 5 else None
            s.add(CulinaryInfo(id=100 + sid, species_id=sid, edible_parts=EDIBLE_TEXT, taste_notes=TASTE_TEXT,
                               harvest_stage="HARVEST-SENTINEL spring", preparation_warnings=prep))
            s.add(SpeciesRecipe(species_id=sid, title="Recipe " + name, body=RECIPE_TEXT,
                                status="approved", is_preferred=True, source="curator"))
        s.add(CulinaryInfoHistory(culinary_info_id=104, field_name="preparation_warnings", old_value=None,
                                  new_value=CAUTION_WARN, changed_by="human", changed_at=datetime(2026, 10, 20)))
        s.add(CulinaryInfoHistory(culinary_info_id=105, field_name="preparation_warnings", old_value=None,
                                  new_value=AI_WARN, changed_by="ai_approved:human", changed_at=datetime(2026, 10, 20)))
        await s.commit()
    return eng, S


# ── the rule ─────────────────────────────────────────────────────────────────

def test_safety_decision_rule_table():
    cases = [
        (("deadly", "toxic"), "deadly", False, "☠ deadly"),
        (("toxic", "toxic"), "toxic", False, "☠ toxic"),
        (("toxic", "inedible"), "toxic", False, "☠ toxic"),
        (("none", "toxic"), "toxic", False, "☠ toxic"),            # verdict half only tightens
        (("unknown", "unknown"), "unknown", False, "⚠ toxicity unknown"),
        ((None, "edible"), "unknown", False, "⚠ toxicity unknown"),  # missing fails closed
        (("", "edible"), "unknown", False, "⚠ toxicity unknown"),
        (("garbage", "edible"), "unknown", False, "⚠ toxicity unknown"),
        (("NONE", "edible"), "unknown", False, "⚠ toxicity unknown"),  # exact match only
        (("none", "caution"), "caution", True, "⚠ caution"),
        (("none", "edible"), "none", True, ""),
        (("none", "Edible"), "none", True, ""),
        # Melvin 21 Oct follow-up: culinary content ONLY for an edible / caution
        # verdict. Inedible / other verdicts are blocked without a label (pages
        # show the verdict badge); unknown / NULL verdict = never assessed.
        (("none", "inedible"), "none", False, ""),
        (("none", "not_edible"), "none", False, ""),
        (("none", "unknown"), "unknown", False, "⚠ toxicity unknown"),
        (("none", None), "unknown", False, "⚠ toxicity unknown"),
        (("none", ""), "unknown", False, "⚠ toxicity unknown"),
        (("unknown", "inedible"), "unknown", False, "⚠ toxicity unknown"),
        (("toxic", "caution"), "toxic", False, "☠ toxic"),
    ]
    for (sev, verdict), level, ok, label in cases:
        d = safety_decision(sev, verdict, "W")
        assert (d["level"], d["culinary_allowed"], d["label"]) == (level, ok, label), (sev, verdict, d)
        assert d["warning"] == ("W" if level == "caution" else None), d
    assert safety_decision("none", "caution", None)["warning"] is None
    assert safety_decision("none", "caution", "   ")["warning"] is None
    assert set(SAFETY_LABELS) == {"deadly", "toxic", "unknown", "caution", "none"}


def test_safety_by_names_from_db_with_curator_warning_only():
    async def run():
        eng, S = await _db()
        async with S() as s:
            out = await safety_by_names(s, list(EXPECT) + ["  hedera   HELIX "])   # name_key lookup
        await eng.dispose()
        return out
    out = _run(run())
    for name, (level, ok, warn) in EXPECT.items():
        d = out[name]
        assert (d["level"], d["culinary_allowed"], d["warning"]) == (level, ok, warn), (name, d)
    assert out["  hedera   HELIX "]["level"] == "toxic"


def test_payloads_serve_the_decision():
    async def run():
        eng, S = await _db()
        got = {}
        async with S() as s:
            for _, name, _, _ in SPECIES:
                c = await culinary.get_culinary_profile(name, db=s)
                p = await culinary.species_profile(name, db=s, identity=CURATOR)
                g = await culinary.species_profile(name, db=s, identity=GUEST)
                got[name] = (c["safety"], p["safety"], g["safety"], c["recipes"], p["recipes"])
        await eng.dispose()
        return got
    got = _run(run())
    for name, (c, p, g, c_rec, p_rec) in got.items():
        level, ok, warn = EXPECT[name]
        for d in (c, p, g):
            assert (d["level"], d["culinary_allowed"], d["warning"]) == (level, ok, warn), (name, d)
        if not ok:
            assert c_rec == [] and p_rec == [], name          # server recipe gate agrees


def test_culinary_allowed_and_sql_are_the_one_rule():
    """culinary_allowed() delegates to safety_decision(); CULINARY_ALLOWED_SQL
    selects exactly the same rows over every severity × verdict combination."""
    from sqlalchemy import select
    from app.models.species import CULINARY_ALLOWED_SQL, culinary_allowed
    sevs = ["none", "toxic", "deadly", "unknown", "", "NONE", "garbage"]   # column is NOT NULL; None: rule table
    verdicts = ["edible", "caution", "inedible", "toxic", "unknown", None, "", "Edible", " caution ",
                "not_edible", "medicinal"]

    async def run():
        path = os.path.join(tempfile.mkdtemp(prefix="b5sql_"), "t.db")
        Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
        eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
        S = async_sessionmaker(eng, expire_on_commit=False)
        want, i = set(), 0
        async with S() as s:
            for sev in sevs:
                for v in verdicts:
                    i += 1
                    sp = Species(id=i, scientific_name=f"Sp {i}", name_key=f"sp {i}", edibility_status=v)
                    s.add(sp)
                    await s.flush()
                    sp.toxicity_severity = sev           # override the column default
                    if culinary_allowed(sev, v):
                        want.add(i)
                    assert culinary_allowed(sev, v) == safety_decision(sev, v)["culinary_allowed"]
            await s.commit()
            got = set((await s.execute(select(Species.id).where(CULINARY_ALLOWED_SQL))).scalars().all())
        await eng.dispose()
        return want, got
    want, got = _run(run())
    assert want == got, (want ^ got)
    assert len(want) == 4           # none × {edible, caution, Edible, " caution "}


# ── PDF (B2-09: server decision, not the client's) ───────────────────────────

def _client_profile(name):
    """What print.html sends — including a lying severity / no safety object."""
    return {"species": {"common_names": ["Common"], "edibility_status": "edible", "toxicity_severity": "none",
                        "phenology": {}},
            "safety": {"culinary_allowed": True, "level": "none", "label": "", "warning": None},
            "culinary": {"edible_parts": EDIBLE_TEXT, "taste_notes": TASTE_TEXT, "harvest_stage": "HARVEST-SENTINEL",
                         "flavour_profile": "FLAVOUR-SENTINEL", "id_notes": "ID notes stay."},
            "recipes": [{"title": "R", "body": RECIPE_TEXT, "is_preferred": True}]}


def _pdf_html(layout, decisions):
    flat = [lp._flatten_species(n, _client_profile(n), {}, decisions.get(n)) for n in EXPECT]
    return {sp["scientific_name"]: lp._jinja_env.get_template("print_pdf.html").render(
        style="botanical", layout=layout, species=[sp], ct=lp.ContentToggles().model_dump(), cover={},
        page_margin="10mm", goe_width=150, goe_pad=154, seasonal_returns=[]) for sp in flat}


def test_pdf_every_layout_gates_on_the_server_decision():
    async def run():
        eng, S = await _db()
        async with S() as s:
            d = await safety_by_names(s, list(EXPECT))
        await eng.dispose()
        return d
    decisions = _run(run())
    for layout in ("field_guide", "recipe_booklet", "workshop"):
        for name, html in _pdf_html(layout, decisions).items():
            level, ok, warn = EXPECT[name]
            ok = ok and name not in HANDOUT_WITHHELD
            for sentinel in (EDIBLE_TEXT, RECIPE_TEXT, "HARVEST-SENTINEL"):
                if ok and layout == "field_guide" and sentinel == RECIPE_TEXT:
                    continue                                  # field guide prints no recipe
                if ok and layout == "recipe_booklet" and sentinel != RECIPE_TEXT:
                    continue                                  # booklet prints recipes only
                assert (sentinel in html) == ok, (layout, name, sentinel)
            assert "ID notes stay." in html or layout == "recipe_booklet"
            label = SAFETY_LABELS[level]
            if label:
                assert label in html, (layout, name, label)
            if warn:
                assert "Caution: " + warn in html, (layout, name)     # workshop: inside the ⚠ Safety box
            assert "AI-approved prep text" not in html.split("Caution:")[-1][:60] if "Caution:" in html else True
    # No decision at all (flatten called without one) fails closed.
    flat = lp._flatten_species("Allium ursinum", _client_profile("Allium ursinum"), {})
    assert flat["culinary_allowed"] is False and flat["recipe_body"] == "" and flat["edible_parts"] == ""
    assert flat["safety_label"] == "⚠ toxicity unknown"


def test_pdf_route_takes_decisions_from_the_db():
    captured = {}

    def fake_render(body, safety, my_notes=None):
        captured.update(safety)
        return "ok"

    async def run():
        eng, S = await _db()
        real = lp.render_pdf
        lp.render_pdf = fake_render
        try:
            async with S() as s:
                body = lp.PdfRequest(species=[lp.SpeciesData(scientific_name=n, profile=_client_profile(n))
                                              for n in EXPECT])
                await lp.generate_pdf(body, db=s, identity=CURATOR)
        finally:
            lp.render_pdf = real
        await eng.dispose()
    _run(run())
    for name, (level, ok, _) in EXPECT.items():
        assert captured[name]["level"] == level and captured[name]["culinary_allowed"] == ok, name


# ── walk Export summary (B2-09) ──────────────────────────────────────────────

def _walk_body():
    W = sharing.WalkSpecies
    return sharing.WalkExportRequest(stops=[
        sharing.WalkStop(num=1, label="1", species=[
            # the client claims everything is fine and sends culinary content
            W(species_scientific=n, edibility="edible", toxicity_warning=None,
              culinary_notes=EDIBLE_TEXT, recipe_title="R", recipe_body=RECIPE_TEXT) for n in EXPECT
        ]),
        sharing.WalkStop(num=2, label="2", also_here=[
            sharing.WalkRepeat(species_scientific=n, first_label="1", toxicity_warning=None) for n in EXPECT
        ]),
    ])


def test_export_summary_regates_server_side():
    async def run():
        eng, S = await _db()
        async with S() as s:
            resp = await sharing.export_walk(_walk_body(), db=s)
        await eng.dispose()
        return resp.body.decode()
    html = _run(run())
    blocks = {}
    for name in EXPECT:
        i = html.index(f">{name}</div>")
        j = html.find('<div class="walk-sp"', i)
        blocks[name] = html[i: j if j != -1 else html.index("Also here:")]
    for name, (level, ok, warn) in EXPECT.items():
        b = blocks[name]
        ok = ok and name not in HANDOUT_WITHHELD
        assert (EDIBLE_TEXT in b) == ok and (RECIPE_TEXT in b) == ok, (name, b[:300])
        if SAFETY_LABELS[level]:
            assert SAFETY_LABELS[level] in b, (name, level)
        if warn:
            assert "⚠ Caution: " + warn in b
    # inedible: no culinary content, no label, but its verdict badge stays
    assert ">inedible</span>" in blocks["Briza media"]
    assert ">edible</span>" not in blocks["Conium maculatum"]
    also = html[html.index("Also here:"):]
    for name in BLOCKED:
        assert SAFETY_LABELS[EXPECT[name][0]] in also


# ── pages: grep-style (B2-01 / B2-04 / P1) ───────────────────────────────────

def _src(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


PAGES = ("frontend/index.html", "frontend/species.html", "frontend/lists.html", "frontend/print.html")
# Curator editing / review tools and the user's own encounter notes are not
# display surfaces for the gate.
EXEMPT = {"frontend/review.html", "frontend/scan.html", "frontend/static/js/encounters-main.js",
          "frontend/scratch-filename-test.html"}


def test_every_page_loads_the_helper_and_sw_caches_it():
    for p in PAGES:
        assert '<script src="/static/js/safety-gate.js"></script>' in _src(p), p
    sw = _src("frontend/static/sw.js")
    # v11: dry-run.js joined the app shell (22 Oct 2026, enrichment safety).
    # v15: hazard-ack.js joined it (22 Oct 2026, hazard candidates).
    assert "'/static/js/safety-gate.js'" in sw and "foragingid-v17" in sw


def test_no_page_rederives_the_rule():
    pat = re.compile(r"toxicity_severity\s*[!=]==|_toxicity\b|sp\.toxicity\b|edibility_status\s*===\s*'caution'"
                     r"|edib\s*===\s*'caution'")
    for p in PAGES:
        hits = [l for l in _src(p).splitlines() if pat.search(l) and not l.strip().startswith("//")
                # species grid verdict FILTER chip (filters by verdict; not a label)
                and l.strip() != "const isCaution   = edib === 'caution';"]
        assert not hits, (p, hits)
    idx = _src("frontend/index.html")
    body = idx[idx.index("function _culinaryGate("):idx.index("function _culinaryGateBadge(")]
    assert "SafetyGate.decision" in body and "'none'" not in body


def test_culinary_reads_go_through_the_gate():
    culinary_read = re.compile(r"\.(edible_parts|taste_notes|harvest_stage)\b|\.recipes\b")
    for root, _, files in os.walk(os.path.join(ROOT, "frontend")):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), ROOT)
            if not f.endswith((".html", ".js")) or rel in EXEMPT or rel.endswith("safety-gate.js"):
                continue
            for n, line in enumerate(_src(rel).splitlines(), 1):
                probe = re.sub(r"\b(ct|prefs)\.recipes\b", "", line)     # content toggles, not data
                if not culinary_read.search(probe) or line.strip().startswith("//"):
                    continue
                ok = (
                    # Lists / print: `cul` is _printCulinary(prof) (gated); recipes only via _printRecipes
                    (rel in ("frontend/lists.html", "frontend/print.html")
                     and ("cul." in line or "SafetyGate.recipes" in line or "SafetyGate.handoutRecipes" in line))
                    # map pop-up (inside the SafetyGate.allowed else-branch), Export summary (gate.ok),
                    # Find recipes (server-gated by CULINARY_ALLOWED_SQL)
                    or (rel == "frontend/index.html" and (
                        "ci.edible_parts" in line or "_hOk ? (ed?.recipes" in line
                        or "ci ? (ci.edible_parts" in line or "sp.recipes" in line))
                    # species page: inside `if (culinaryBlocked) … else` / SafetyGate.allowed
                    or (rel == "frontend/species.html" and (
                        "ci.taste_notes" in line or "data.recipes" in line or "result.taste_notes" in line))
                    # Recipes page (25 Oct 2026): server-gated by CULINARY_ALLOWED_SQL, and every
                    # recipe drawn passes SafetyGate.allowed; _allWalks reads only the walk names
                    or (rel == "frontend/recipes.html" and (
                        "SafetyGate.allowed(_data.safety" in line or "_data.recipes.forEach(r => r.walks" in line))
                )
                assert ok, f"{rel}:{n} reads culinary content outside the gate: {line.strip()[:120]}"
    lists = _src("frontend/lists.html") + _src("frontend/print.html")
    assert lists.count("prof.culinary") == 2 and lists.count("prof.recipes") == 2   # only in the two accessors


def test_gated_branches_are_where_the_grep_assumes():
    idx = _src("frontend/index.html")
    inj = idx[idx.index("async function _injectEnrichment("):idx.index("function _trunc(")]
    assert inj.index("if (!SafetyGate.allowed(safety))") < inj.index("ci.edible_parts")
    sp = _src("frontend/species.html")
    taste = sp[sp.index("// ── 4. Taste notes"):sp.index("// ── 5. Recipe Bank")]
    assert taste.index("if (culinaryBlocked)") < taste.index("ci.taste_notes")
    recipe = sp[sp.index("// ── 5. Recipe Bank"):]
    assert recipe.index("if (culinaryBlocked || edibBlocked)") < recipe.index("recipes.length") \
        if "recipes.length" in recipe else True
    assert "const culinaryBlocked = !SafetyGate.allowed(_safety);" in sp
    grid = sp[sp.index("const _sg = SafetyGate.decision(sp.safety);"):]
    assert grid.index("!SafetyGate.allowed(_sg)") < grid.index("'✓ edible'")
    for p in ("frontend/lists.html", "frontend/print.html"):
        s = _src(p)
        acc = s[s.index("function _printCulinary("):s.index("function _printSafety(")]
        assert "SafetyGate.handoutCulinary(" in acc and "SafetyGate.handoutRecipes(" in acc   # batch 6: handout rule


def test_js_and_pdf_share_one_field_list_and_labels():
    js = _src("frontend/static/js/safety-gate.js")
    fields = set(re.findall(r"'([a-z_]+)'", js[js.index("CULINARY_FIELDS = ["):js.index("];", js.index("CULINARY_FIELDS = ["))]))
    assert fields == set(lp.CULINARY_FIELDS), fields ^ set(lp.CULINARY_FIELDS)
    assert f"label: '{SAFETY_LABELS['unknown']}'" in js                       # fail-closed default
    assert "LEVELS = ['deadly', 'toxic', 'unknown', 'caution', 'none']" in js


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
