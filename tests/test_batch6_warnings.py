"""
Batch 6 (audit B2-03 + E-14, 21 Oct 2026) — one warnings rule for every surface.

  * species_warnings / handout_warnings (app/models/species.py) are the only
    definition of which preparation / look-alike text a surface shows; served
    inside `safety` and read by static/js/safety-gate.js.
  * In-app: full text, uncurated text labelled, never dropped.
  * Outgoing (PDF, Export summary, print, experience page): curator-authored
    only; toxic falls back to TOXIC_FALLBACK_TEXT; a caution species without a
    curator-authored warning withholds culinary content (handout rule).
  * Never cut: no truncation anywhere.
  * Placeholder markers (E-14) are never warning text, never curator-authored,
    and the DB refuses new ones (migration 0055).

Run: python tests/test_batch6_warnings.py
"""
import asyncio
import importlib.util
import os
import re
import sqlite3
import sys
import tempfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "experience_export"))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main  # noqa: E402,F401
import app.api.culinary as culinary  # noqa: E402
import app.api.lists_pdf as lp  # noqa: E402
import app.api.sharing as sharing  # noqa: E402
from app.api.identity import Identity  # noqa: E402
from app.database import Base  # noqa: E402
from app.models.culinary import CulinaryInfo  # noqa: E402
from app.models.species import (CAUTION_UNREVIEWED_LABEL, TOXIC_FALLBACK_TEXT, CulinaryInfoHistory,  # noqa: E402
                                Species, SpeciesRecipe, handout_warnings, is_curator_authored,
                                is_placeholder_marker, placeholder_marker_sql, safety_decision,
                                species_warnings)
from app.services.safety_gate import safety_by_names  # noqa: E402
from app.services.taxonomy import normalize_taxon_key  # noqa: E402

CURATOR = Identity(user_id=1, is_guest=False, is_anonymous_guest=False, workshop_session_id=None)

# Long texts (> every old limit: map 120, PDF 140, summary 130) with a tail sentinel.
LONG = " Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor." * 4
PREP = {4: "CAUTION-PREP cook berries well." + LONG + " PREP-END-4",
        6: "EDIBLE-PREP oxalates; eat in moderation." + LONG + " PREP-END-6",
        2: "TOXIC-PREP every part is poisonous." + LONG + " PREP-END-2"}
LOOK = {4: "CAUTION-LOOK dwarf elder." + LONG + " LOOK-END-4",
        6: "EDIBLE-LOOK lily of the valley." + LONG + " LOOK-END-6",
        2: "TOXIC-LOOK ivy-leaved things." + LONG + " LOOK-END-2"}
UNREV_PREP = "UNREVIEWED-PFAF-PREP may irritate."
MARKER = "(human-authored preparation_warnings)"
RECIPE_TEXT = "RECIPE-SENTINEL fry gently"
EDIBLE_TEXT = "EDIBLE-PARTS-SENTINEL"

# id, name, verdict, severity
SPECIES = [
    (2, "Hedera helix", "toxic", "toxic"),        # curator prep + look
    (4, "Sambucus nigra", "caution", "none"),     # curator prep + look
    (6, "Allium ursinum", "edible", "none"),      # curator prep + look
    (7, "Ajuga reptans", "caution", "none"),      # prep uncurated (PFAF) → withheld on handouts
    (8, "Populus tremula", "edible", "none"),     # E-14: real text, marker history row
    (9, "Oenanthe crocata", "toxic", "deadly"),   # look-alike locked by "(set)" marker only
]


def _run(coro):
    return asyncio.run(coro)


async def _db():
    path = os.path.join(tempfile.mkdtemp(prefix="b6test_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    S = async_sessionmaker(eng, expire_on_commit=False)
    t = datetime(2026, 10, 20)
    async with S() as s:
        for sid, name, verdict, sev in SPECIES:
            s.add(Species(id=sid, scientific_name=name, name_key=normalize_taxon_key(name),
                          edibility_status=verdict, toxicity_severity=sev, kingdom="Plantae"))
            prep = PREP.get(sid) or {7: UNREV_PREP, 8: "ASPEN-PREP salicin."}.get(sid)
            look = LOOK.get(sid) or {9: "OENANTHE-LOOK wild celery."}.get(sid)
            s.add(CulinaryInfo(id=100 + sid, species_id=sid, edible_parts=EDIBLE_TEXT,
                               preparation_warnings=prep, look_alike_warnings=look))
            s.add(SpeciesRecipe(species_id=sid, title="R" + str(sid), body=RECIPE_TEXT,
                                status="approved", is_preferred=True, source="curator"))
            for col, txt in (("preparation_warnings", PREP.get(sid)), ("look_alike_warnings", LOOK.get(sid))):
                if txt:
                    s.add(CulinaryInfoHistory(culinary_info_id=100 + sid, field_name=col, old_value=None,
                                              new_value=txt, changed_by="human", changed_at=t))
        s.add(CulinaryInfoHistory(culinary_info_id=107, field_name="preparation_warnings", old_value=None,
                                  new_value=UNREV_PREP, changed_by="pfaf_reparse", changed_at=t))
        s.add(CulinaryInfoHistory(culinary_info_id=108, field_name="preparation_warnings", old_value=None,
                                  new_value=MARKER, changed_by="human", changed_at=t))
        s.add(CulinaryInfoHistory(culinary_info_id=109, field_name="look_alike_warnings", old_value=None,
                                  new_value="(set)", changed_by="human", changed_at=t))
        await s.commit()
    return eng, S


async def _decisions():
    eng, S = await _db()
    async with S() as s:
        d = await safety_by_names(s, [n for _, n, _, _ in SPECIES] + ["Not in the database"])
    await eng.dispose()
    return d


# ── the rule (pure) ──────────────────────────────────────────────────────────

MARKER_CASES = [("(set)", True), (MARKER, True), ("  (set)\n", True),
                ("(5 human-authored recipes for Meum athamanticum)", True),
                ("()", True), ("(", False), ("", False), (None, False),
                ("(see Conium) and also Aethusa (Fool's parsley)", False),   # two phrases
                ("Raw berries are toxic (cook them).", False),
                ("(" + "x" * 79 + ")", False), ("(" + "x" * 78 + ")", True)]


def test_marker_predicate_python_sql_and_migration_agree():
    conn = sqlite3.connect(":memory:")
    spec = importlib.util.spec_from_file_location(
        "m0055", os.path.join(ROOT, "migrations", "versions", "0055_refuse_placeholder_markers.py"))
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)
    assert mig._marker_sql("X") == placeholder_marker_sql("X")       # frozen copy == app rule
    for text, want in MARKER_CASES:
        assert is_placeholder_marker(text) is want, text
        got = conn.execute(f"SELECT {placeholder_marker_sql(':t')}", {"t": text}).fetchone()[0]
        assert bool(got) is want, (text, got)


def test_species_warnings_and_handout_rule():
    w = species_warnings({
        "preparation_warnings": ("Real text", "human", "Real text"),
        "look_alike_warnings": ("PFAF look", "pfaf_reparse", "PFAF look")})
    assert w == {"preparation": {"text": "Real text", "reviewed": True},
                 "look_alike": {"text": "PFAF look", "reviewed": False}}
    # markers, "None known" and empty text are never a warning
    for cur in (MARKER, "(set)", "None known", "  ", None):
        assert species_warnings({"preparation_warnings": (cur, "human", cur)})["preparation"] is None, cur
    # a marker history row never makes the current text curator-authored
    assert species_warnings({"preparation_warnings": ("Aspen text", "human", MARKER)})["preparation"] == \
        {"text": "Aspen text", "reviewed": False}
    assert is_curator_authored("human", "(set)", "(set)") is False
    # handouts: curator text only; toxic / deadly always get a preparation warning
    assert handout_warnings("none", w) == {"preparation": "Real text", "preparation_is_fallback": False,
                                           "look_alike": None}
    for level in ("toxic", "deadly"):
        hw = handout_warnings(level, species_warnings({}))
        assert hw["preparation"] == TOXIC_FALLBACK_TEXT and hw["preparation_is_fallback"]
    assert handout_warnings("caution", species_warnings({}))["preparation"] is None


def test_handout_culinary_rule():
    ok = safety_decision("none", "caution", "W")
    no = safety_decision("none", "caution", None)
    assert ok["handout_culinary_allowed"] and ok["handout_label"] == "⚠ caution"
    assert no["culinary_allowed"] and not no["handout_culinary_allowed"]        # in-app keeps it
    assert no["handout_label"] == CAUTION_UNREVIEWED_LABEL == "⚠ caution — warning not yet reviewed"
    for sev, verdict in (("none", "edible"), ("toxic", "toxic"), ("none", "inedible"), ("unknown", "unknown")):
        d = safety_decision(sev, verdict, None)
        assert d["handout_culinary_allowed"] == d["culinary_allowed"] and d["handout_label"] == d["label"]


# ── served payloads ──────────────────────────────────────────────────────────

def test_served_warnings_full_text_and_reviewed_flags():
    d = _run(_decisions())
    for sid, name, _, _ in SPECIES[:3]:
        w = d[name]["warnings"]
        assert w["preparation"] == {"text": PREP[sid], "reviewed": True}, name
        assert w["look_alike"] == {"text": LOOK[sid], "reviewed": True}, name
        assert d[name]["handout_warnings"]["preparation"] == PREP[sid]
        assert d[name]["handout_warnings"]["look_alike"] == LOOK[sid]
    aj = d["Ajuga reptans"]
    assert aj["warnings"]["preparation"] == {"text": UNREV_PREP, "reviewed": False}   # in-app: shown, labelled
    assert aj["handout_warnings"]["preparation"] is None and not aj["handout_culinary_allowed"]
    assert d["Populus tremula"]["warnings"]["preparation"]["reviewed"] is False      # E-14 marker row
    oe = d["Oenanthe crocata"]
    assert oe["warnings"]["look_alike"] == {"text": "OENANTHE-LOOK wild celery.", "reviewed": False}
    assert oe["handout_warnings"]["preparation"] == TOXIC_FALLBACK_TEXT
    nd = d["Not in the database"]
    assert nd["warnings"] == {"preparation": None, "look_alike": None} and not nd["handout_culinary_allowed"]


def test_both_endpoints_serve_the_warnings():
    async def run():
        eng, S = await _db()
        out = {}
        async with S() as s:
            for _, name, _, _ in SPECIES:
                c = await culinary.get_culinary_profile(name, db=s)
                p = await culinary.species_profile(name, db=s, identity=CURATOR)
                out[name] = (c["safety"], p["safety"])
        await eng.dispose()
        return out
    got = _run(run())
    for sid, name, _, _ in SPECIES[:3]:
        for d in got[name]:
            assert d["warnings"]["look_alike"]["text"] == LOOK[sid] and "handout_warnings" in d


# ── outgoing surfaces ────────────────────────────────────────────────────────

def _client_profile(name):
    # A hostile client: claims warnings that are not in the DB and culinary content.
    return {"species": {"edibility_status": "edible", "common_names": ["C"]},
            "culinary": {"edible_parts": EDIBLE_TEXT, "look_alike_warnings": "CLIENT-FAKE-LOOK",
                         "preparation_warnings": "CLIENT-FAKE-PREP", "id_notes": "ID notes stay."},
            "recipes": [{"title": "R", "body": RECIPE_TEXT, "is_preferred": True}]}


def _pdf_html(layout, decisions):
    captured = {}
    real = lp._jinja_env.get_template("print_pdf.html")

    class _T:
        def render(self, **kw):
            html = real.render(**kw)
            captured["html"] = html
            raise RuntimeError("stop before WeasyPrint")
    orig = lp._jinja_env.get_template
    lp._jinja_env.get_template = lambda n: _T()
    try:
        out = {}
        for _, name, _, _ in SPECIES:
            body = lp.PdfRequest(species=[lp.SpeciesData(scientific_name=name, profile=_client_profile(name))],
                                 layout=layout, toggles=lp.ContentToggles(id_notes=False))   # toggles off
            lp.render_pdf(body, decisions)
            out[name] = captured["html"]
    finally:
        lp._jinja_env.get_template = orig
    return out


def _species_block(html):
    return html[html.index('<div class="species-grid">'):]


def test_pdf_prints_full_warnings_in_every_layout():
    d = _run(_decisions())
    for layout in ("field_guide", "recipe_booklet", "workshop"):
        pages = _pdf_html(layout, d)
        for sid, name, _, _ in SPECIES[:3]:
            b = _species_block(pages[name])
            assert PREP[sid] in b and LOOK[sid] in b, (layout, name)          # whole text, uncut
            assert "…" not in b.split("PREP-END")[0][-5:], (layout, name)
        for name, b in pages.items():
            b = _species_block(b)
            assert "CLIENT-FAKE" not in b, (layout, name)                     # never from the payload
            assert MARKER not in b and "(set)" not in b, (layout, name)
            assert UNREV_PREP not in b, (layout, name)                        # outgoing: curator only
        aj = _species_block(pages["Ajuga reptans"])
        assert CAUTION_UNREVIEWED_LABEL in aj and EDIBLE_TEXT not in aj and RECIPE_TEXT not in aj, layout
        assert TOXIC_FALLBACK_TEXT in _species_block(pages["Oenanthe crocata"]), layout


def test_export_summary_warnings_rechecked_server_side():
    W = sharing.WalkSpecies
    body = sharing.WalkExportRequest(stops=[sharing.WalkStop(num=1, label="1", species=[
        W(species_scientific=n, edibility="edible", culinary_notes=EDIBLE_TEXT, recipe_title="R",
          recipe_body=RECIPE_TEXT, preparation_warning="CLIENT-FAKE-PREP", look_alike_warning="CLIENT-FAKE-LOOK")
        for _, n, _, _ in SPECIES])],
        also_here=[])

    async def run():
        eng, S = await _db()
        async with S() as s:
            resp = await sharing.export_walk(body, db=s)
        await eng.dispose()
        return resp.body.decode()
    html = _run(run())
    import html as _html
    text = _html.unescape(html)
    for sid, name, _, _ in SPECIES[:3]:
        assert PREP[sid] in text and LOOK[sid] in text, name
    assert "CLIENT-FAKE" not in text and MARKER not in text and UNREV_PREP not in text
    i = text.index(">Ajuga reptans</div>")
    aj = text[i:text.find('<div class="walk-sp"', i)]
    assert CAUTION_UNREVIEWED_LABEL in aj and EDIBLE_TEXT not in aj and RECIPE_TEXT not in aj
    assert TOXIC_FALLBACK_TEXT in text


def test_experience_gates_use_the_shared_rule():
    import gates
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE culinary_info_history (id INTEGER PRIMARY KEY, culinary_info_id INT, field_name TEXT,"
              " new_value TEXT, changed_by TEXT, changed_at TEXT)")
    c.execute("INSERT INTO culinary_info_history VALUES (1, 5, 'preparation_warnings', 'Edible prep.', 'human', '2026')")
    c.execute("INSERT INTO culinary_info_history VALUES (2, 5, 'look_alike_warnings', '(set)', 'human', '2026')")
    sp = {"id": 1, "scientific_name": "X", "edibility_status": "edible", "toxicity_severity": "none"}
    ci = {"id": 5, "preparation_warnings": "Edible prep.", "look_alike_warnings": "Look text"}
    assert gates.safety_texts(sp, ci, c) == {"preparation": "Edible prep."}   # edible prep now published
    tox = dict(sp, edibility_status="toxic", toxicity_severity="toxic")
    assert gates.safety_texts(tox, dict(ci, preparation_warnings="PFAF"), c)["toxic"] == TOXIC_FALLBACK_TEXT


# ── E-14: the database refuses new markers ───────────────────────────────────

def test_migration_triggers_refuse_markers():
    spec = importlib.util.spec_from_file_location(
        "m0055", os.path.join(ROOT, "migrations", "versions", "0055_refuse_placeholder_markers.py"))
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE culinary_info (id INTEGER PRIMARY KEY, preparation_warnings TEXT, look_alike_warnings TEXT,"
              " taste_notes TEXT)")
    c.execute("CREATE TABLE culinary_info_history (id INTEGER PRIMARY KEY, culinary_info_id INT, field_name TEXT,"
              " old_value TEXT, new_value TEXT)")
    for sql in mig.TRIGGERS.values():
        c.execute(sql)
    c.execute("INSERT INTO culinary_info VALUES (1, 'Real (cooked) text.', NULL, NULL)")
    c.execute("INSERT INTO culinary_info_history VALUES (1, 1, 'look_alike_warnings', NULL, 'Real text.')")
    c.execute("UPDATE culinary_info SET taste_notes = '(set)' WHERE id = 1")      # not a warning column
    refused = [
        "INSERT INTO culinary_info_history VALUES (2, 1, 'preparation_warnings', NULL, '(human-authored preparation_warnings)')",
        "INSERT INTO culinary_info_history VALUES (3, 1, 'taste_notes', NULL, ' (set) ')",
        "UPDATE culinary_info_history SET new_value = '(set)' WHERE id = 1",
        "INSERT INTO culinary_info VALUES (2, NULL, '(set)', NULL)",
        "UPDATE culinary_info SET preparation_warnings = '(set)' WHERE id = 1",
        "UPDATE culinary_info SET look_alike_warnings = '(placeholder)' WHERE id = 1",
    ]
    for sql in refused:
        try:
            c.execute(sql)
        except sqlite3.IntegrityError as e:
            assert "E-14" in str(e)
        else:
            raise AssertionError("not refused: " + sql)
    assert c.execute("SELECT preparation_warnings FROM culinary_info WHERE id = 1").fetchone()[0] == "Real (cooked) text."


# ── pages read the shared helper; no truncation (source checks — no JS runtime) ─

def _src(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def test_pages_render_warnings_through_the_helper_uncut():
    idx = _src("frontend/index.html")
    inj = idx[idx.index("async function _injectEnrichment("):idx.index("function _trunc(")]
    assert "SafetyGate.warnings(safety)" in inj                                       # map pop-up
    assert "look_alike_warnings" not in inj and "preparation_warnings" not in inj       # no raw / cut text
    assert "${SafetyGate.warnings(_gate.safety, { collapse: 'auto' })}" in idx         # walk stop card
    prox = idx[idx.index("function _renderProxPanel("):]
    assert "SafetyGate.warnings(sp.safety, { collapse: 'all' })" in prox[:4000]        # proximity alert
    sp = _src("frontend/species.html")
    assert "(_safety.warnings || {}).preparation" in sp and "(_safety.warnings || {}).look_alike" in sp
    for p in ("frontend/lists.html", "frontend/print.html"):
        s = _src(p)
        assert "look_alike_warnings" not in s.replace("cul.look_alike_warnings || cul.preparation_warnings", ""), p
        assert "preparation_warnings" not in s.replace("cul.look_alike_warnings || cul.preparation_warnings", ""), p
        assert "SafetyGate.warning(" not in s and s.count("_printWarnings(prof") >= 2, p
    tpl = _src("app/templates/print_pdf.html")
    assert "look_alike[:" not in tpl and "preparation_warnings[:" not in tpl
    assert not re.search(r"ct\.id_notes and sp\.look_alike", tpl)
    js = _src("frontend/static/js/safety-gate.js")
    assert ".slice(" not in js and "substring(" not in js                              # the helper never cuts
    assert "'Source text — not yet reviewed'" in js and f"'{CAUTION_UNREVIEWED_LABEL}'" in js
    assert "'foragingid-species-2'" in _src("frontend/static/sw.js")                   # stale payloads evicted


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
