"""
Safety batch, 28 Oct 2026 (docs/audit/2026-10-20/CLOSEOUT_28oct.md section 4;
decisions = Claude.ai defaults, Melvin 28 Oct).

1. Seasonal Returns: default Off; every entry through the SafetyGate (handout
   badge + handout warnings); toxic/deadly never "in season" without both.
   One rule for Lists, browser print and PDF. Tested with Digitalis purpurea.
2. Source links: flagged when neither title nor URL names the species; flagged
   links never reach a guest, are flagged for the curator, never printed.
3. Workshop page: one full safety box per species, no repeats before Foraging
   / Recipe — and at least one full copy always stays (Lists, print, PDF).
4. Traditional / other uses in their own "Other uses" section, not under
   "Medicinal preparations"; empty sections omitted (Lists, print; PDF has none).

Temp DB + JavaScriptCore only — the live checks are Melvin's.
Run from project root:  python tests/test_safety_batch_28oct.py
"""
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main  # noqa: E402,F401
import app.api.lists_pdf as lp  # noqa: E402
from app.api.identity import Identity  # noqa: E402
from app.database import Base  # noqa: E402
from app.models.culinary import CulinaryInfo  # noqa: E402
from app.models.species import TOXIC_FALLBACK_TEXT, CulinaryInfoHistory, Species  # noqa: E402
from app.services.safety_gate import safety_by_names  # noqa: E402
from app.services.seasonal_returns import gate_seasonal_returns, seasonal_return_gate  # noqa: E402
from app.services.taxonomy import normalize_taxon_key  # noqa: E402

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
CURATOR = Identity(user_id=1, is_guest=False, is_anonymous_guest=False, workshop_session_id=None)

DIGI_LOOK = "DIGI-LOOK comfrey and borage leaves."
SAMB_PREP = "SAMB-PREP cook the berries."
SAMB_LOOK = "SAMB-LOOK dwarf elder."
# id, name, verdict, severity
SPECIES = [
    (1, "Digitalis purpurea", "toxic", "deadly"),   # curator look-alike; prep = toxic fallback
    (2, "Sambucus nigra", "caution", "none"),       # curator prep + look
    (3, "Urtica dioica", "edible", "none"),         # no warnings
]


def _src(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def _jsc(script):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(script)
        path = f.name
    try:
        out = subprocess.run([JSC, path], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(path)
    assert out.returncode == 0, out.stderr or out.stdout
    return json.loads(out.stdout.strip().split("\n")[-1])


async def _db():
    path = os.path.join(tempfile.mkdtemp(prefix="sb28_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    S = async_sessionmaker(eng, expire_on_commit=False)
    t = datetime(2026, 10, 20)
    async with S() as s:
        for sid, name, verdict, sev in SPECIES:
            s.add(Species(id=sid, scientific_name=name, name_key=normalize_taxon_key(name),
                          edibility_status=verdict, toxicity_severity=sev, kingdom="Plantae"))
        s.add(CulinaryInfo(id=101, species_id=1, look_alike_warnings=DIGI_LOOK))
        s.add(CulinaryInfo(id=102, species_id=2, preparation_warnings=SAMB_PREP, look_alike_warnings=SAMB_LOOK))
        s.add(CulinaryInfo(id=103, species_id=3))
        for ci, col, txt in ((101, "look_alike_warnings", DIGI_LOOK), (102, "preparation_warnings", SAMB_PREP),
                             (102, "look_alike_warnings", SAMB_LOOK)):
            s.add(CulinaryInfoHistory(culinary_info_id=ci, field_name=col, old_value=None,
                                      new_value=txt, changed_by="human", changed_at=t))
        await s.commit()
    return eng, S


def _decisions():
    async def go():
        eng, S = await _db()
        async with S() as s:
            d = await safety_by_names(s, [n for _, n, _, _ in SPECIES] + ["Not in the database"])
        await eng.dispose()
        return d
    return asyncio.run(go())


def _sr_items():
    return [{"species_id": sid, "scientific_name": n, "common_name": None, "timing": "now",
             "last_seen": "2026-06-01", "last_seen_place": "", "reason": "r"} for sid, n, _, _ in SPECIES] + \
           [{"species_id": 99, "scientific_name": "Not in the database", "timing": "now",
             "last_seen": "2026-06-01", "reason": "r"}]


# ── 1. Seasonal Returns ──────────────────────────────────────────────────────

def test_sr_python_gate_digitalis_badge_and_full_warnings():
    d = _decisions()
    g = seasonal_return_gate(d["Digitalis purpurea"])
    assert g["level"] == "deadly" and "☠" in g["label"]
    assert g["look_alike"] == DIGI_LOOK and g["preparation"] == TOXIC_FALLBACK_TEXT.strip()
    s = seasonal_return_gate(d["Sambucus nigra"])
    assert s["preparation"] == SAMB_PREP and s["look_alike"] == SAMB_LOOK and s["caution"]
    u = seasonal_return_gate(None)                       # missing decision fails closed
    assert u["level"] == "unknown" and "unknown" in u["label"]
    # A deadly decision without warning text or without a label is dropped.
    assert seasonal_return_gate({"level": "deadly", "label": "☠ deadly", "handout_warnings": {}}) is None
    assert seasonal_return_gate({"level": "toxic", "label": "", "handout_warnings": {"preparation": "x"}}) is None


def test_sr_pdf_uses_server_decision_not_payload():
    d = _decisions()
    forged = [dict(it, safety={"level": "none", "label": "", "culinary_allowed": True}) for it in _sr_items()]
    gated = gate_seasonal_returns([{k: v for k, v in it.items() if k != "safety"} for it in forged], d)
    digi = next(it for it in gated if it["scientific_name"] == "Digitalis purpurea")
    assert digi["gate"]["level"] == "deadly" and digi["gate"]["look_alike"] == DIGI_LOOK

    async def go():
        eng, S = await _db()
        captured = {}
        real = lp._jinja_env.get_template("print_pdf.html")

        class _T:
            def render(self, **kw):
                captured["html"] = real.render(**kw)
                raise RuntimeError("stop before WeasyPrint")
        orig = lp._jinja_env.get_template
        lp._jinja_env.get_template = lambda n: _T()
        try:
            async with S() as s:
                body = lp.PdfRequest(species=[lp.SpeciesData(scientific_name="Urtica dioica", profile={})],
                                     layout="workshop", seasonal_returns=forged)
                try:
                    await lp.generate_pdf(body, db=s, identity=CURATOR)
                except Exception:
                    pass
        finally:
            lp._jinja_env.get_template = orig
            await eng.dispose()
        return captured["html"]
    html = asyncio.run(go())
    sr = html[html.index('<div class="sr-section">'):]
    sr = sr[:sr.index('<div class="species-grid">')] if '<div class="species-grid">' in sr else sr
    entry = sr[sr.index("Digitalis purpurea"):]
    entry = entry[:entry.index('<div class="sr-entry">')] if '<div class="sr-entry">' in entry else entry
    assert "☠" in entry and "pill-toxic" in entry
    assert DIGI_LOOK in entry and "Not safe to eat" in entry
    assert "toxicity unknown" in sr                     # the unknown species is labelled, not silent


def _sr_render_js(page):
    src = _src(page)
    m = re.search(r"function _seasonalReturnsHtml\(items\) \{.*?\n\}\n", src, re.S)
    assert m, page
    return m.group(0)


def test_sr_lists_and_print_render_through_the_gate():
    d = _decisions()
    items = [dict(it, safety=d.get(it["scientific_name"])) for it in _sr_items()]
    items.append({"scientific_name": "Forged deadly", "timing": "now", "last_seen": "",
                  "safety": {"level": "deadly", "label": "☠ deadly", "culinary_allowed": False,
                             "handout_warnings": {}}})
    core = ("var window = this;\n" + _src("frontend/static/js/esc.js") + "\n" +
            _src("frontend/static/js/safety-gate.js") + "\nvar SafetyGate = window.SafetyGate;" +
            "var _esc = window.lmEsc; function spCommon(x){return x;}\n")
    for page in ("frontend/lists.html", "frontend/print.html"):
        out = _jsc(core + _sr_render_js(page) + "\nprint(JSON.stringify(_seasonalReturnsHtml(" +
                   json.dumps(items) + ")));")
        digi = out[out.index("Digitalis purpurea"):]
        digi = digi[:digi.index('<div class="sr-entry">')]
        assert "☠" in digi and DIGI_LOOK in digi and "Not safe to eat" in digi, page
        assert "Forged deadly" not in out, page          # deadly without warnings: dropped
        assert "toxicity unknown" in out, page
        assert _jsc(core + _sr_render_js(page) + "\nprint(JSON.stringify(_seasonalReturnsHtml([])));") == ""


def test_sr_default_off_and_new_cache_keys():
    lists = _src("frontend/lists.html")
    assert '<option value="0" selected>Off</option>' in lists
    assert '<option value="10" selected>' not in lists
    assert "getItem(SR_LIMIT_KEY) || '0'" in lists
    assert "if (limit === '0') { _srData = []" in lists
    assert "SR_DATA_KEY  = 'foragingid_sr_data_v2'" in lists
    assert "getItem('foragingid_sr_data_v2')" in _src("frontend/print.html")
    assert "foragingid_sr_data'" not in _src("frontend/print.html")


def test_sr_api_attaches_the_decision():
    src = _src("app/api/notifications.py")
    assert 'it["safety"] = decisions.get(it["species_id"])' in src


# ── 2. Source links ──────────────────────────────────────────────────────────

ELDER_LINKS = [
    {"source_label": "Eatweeds", "title": "The Traditional and Modern Uses of Elder",
     "url": "https://www.eatweeds.co.uk/elder-sambucus-nigra"},
    {"source_label": "Galloway", "title": "Elderberry Vinegar Recipe", "url": "https://x/elderberry-vinegar/"},
    {"source_label": "Galloway", "title": "Ground elder \u2013 Identification, distribution, edibility.",
     "url": "https://gallowaywildfoods.com/ground-elder-identification-distribution-edibility/"},
    {"source_label": "Brill", "title": "ScoutsThis hands-on environmental program",
     "url": "https://www.wildmanstevebrill.com/scout"},
    {"source_label": "Old name", "title": "Notes", "url": "https://x/sambucus-arborescens-notes"},
]


def test_links_rule():
    from app.services.source_links import flag_links, species_link_names
    names = species_link_names("Sambucus nigra", "Elderberry", ["Sambucus arborescens"])
    got = [lk["flagged"] for lk in flag_links(ELDER_LINKS, names)]
    assert got == [False, False, True, True, False], got
    # apostrophes and accents
    assert not flag_links([{"title": "Dryad\u2019s Saddle \u2013 Edibility", "url": "u"}],
                          species_link_names("Cerioporus squamosus", "Dryad's Saddle"))[0]["flagged"]
    assert flag_links([{"title": "t", "url": "u"}], [])[0]["flagged"]          # nothing to check: flagged


def test_links_guest_never_gets_flagged_curator_sees_flag():
    from app.models.species import SpeciesSynonym
    from app.services.source_links import apply_link_check

    async def go():
        eng, S = await _db()
        async with S() as s:
            s.add(SpeciesSynonym(synonym_name_key=normalize_taxon_key("Sambucus arborescens"),
                                 synonym_scientific_name="Sambucus arborescens", canonical_species_id=2))
            sp = await s.get(Species, 2)
            sp.preferred_common_name = "Elderberry"
            await s.commit()
            cur, gst = {"culinary_links": list(ELDER_LINKS)}, {"culinary_links": list(ELDER_LINKS)}
            await apply_link_check(s, sp, cur, False)
            await apply_link_check(s, sp, gst, True)
        await eng.dispose()
        return cur, gst
    cur, gst = asyncio.run(go())
    assert [lk["flagged"] for lk in cur["culinary_links"]] == [False, False, True, True, False]
    assert len(gst["culinary_links"]) == 3 and not any(lk["flagged"] for lk in gst["culinary_links"])
    assert not any("ground-elder" in lk["url"] or "brill" in lk["url"] for lk in gst["culinary_links"])


def test_links_both_endpoints_and_species_page():
    src = _src("app/api/culinary.py")
    assert src.count("await apply_link_check(db, sp, ") == 2
    page = _src("frontend/species.html")
    assert "lk.flagged ? ' class=\"culinary-link-flagged\"'" in page
    assert "@media print { .culinary-link-flagged { display: none !important; } }" in page
    # no printed / handout surface reads culinary_links at all
    for rel in ("frontend/lists.html", "frontend/print.html", "app/templates/print_pdf.html",
                "app/api/lists_pdf.py"):
        assert "culinary_links" not in _src(rel), rel


# ── 3 + 4. Workshop page ─────────────────────────────────────────────────────

WS_LOOK, WS_PREP = "WS-LOOK dwarf elder LOOK-END", "WS-PREP cook the berries PREP-END"
OTHER = "OTHER-USES Compost Dye Wood"


def _fn(src, name):
    m = re.search(r"\nfunction " + re.escape(name) + r"\(.*?\n\}\n", src, re.S)
    assert m, name
    return m.group(0)


def _ws_profile(warn=True, other=OTHER):
    hw = {"look_alike": WS_LOOK, "preparation": WS_PREP} if warn else {}
    safety = {"level": "caution", "label": "⚠ caution", "handout_label": "⚠ caution", "culinary_allowed": True,
              "handout_culinary_allowed": True, "warning": WS_PREP if warn else None, "handout_warnings": hw}
    return {"safety": safety, "species": {"edibility_status": "caution", "common_names": ["Elder"]},
            "culinary": {"edible_parts": "EDIBLE-PARTS flowers", "harvest_stage": "June",
                         "medicinal_notes": "MED-NOTES", "traditional_uses": other,
                         "flavour_profile": "FLAVOUR"},
            "recipes": [{"title": "Cordial", "body": "RECIPE-SENTINEL", "is_preferred": True}],
            "pfaf_fallback_fields": []}


def _ws_js(page, prof):
    src = _src(page)
    core = ("var window = this;\n" + _src("frontend/static/js/esc.js") + "\n" + _src("frontend/static/js/md.js") +
            "\n" + _src("frontend/static/js/safety-gate.js") + "\nvar SafetyGate = window.SafetyGate, LmMd = window.LmMd;"
            "var _esc = window.lmEsc; function spPickCommon(p, c){ return p || (c||[])[0] || ''; }\n")
    names = ["edClass", "edLabel", "_guestNotesHtml", "_printCulinary", "_printRecipes", "_printSafety",
             "_printWarnings", "_seasonText", "_workshopPage"]
    if page.endswith("lists.html"):
        names += ["_fieldGuideBlock"]
        core += ("var _profileCache = {N: %s}; var _baseByName = {}; function _photoFileFor(){ return null; }"
                 "function _getSectionPrefs(){ return {}; }"
                 "function _loadContentToggles(){ return {recipes:true, herbal:true, id_notes:true, foraging:true,"
                 " culinary:true, season:false, my_notes:false, photos:false}; }\n") % json.dumps(prof)
        call = "_workshopPage('N')"
    else:
        call = ("_workshopPage('N', %s, {}, {}, false, false, {recipes:true, herbal:true, id_notes:true,"
                " foraging:true, culinary:true})") % json.dumps(prof)
    body = "".join(_fn(src, n) for n in names)
    body = body.replace("function _guestNotesHtml(", "function _guestNotesHtml_unused(") + \
        "\nfunction _guestNotesHtml(){ return ''; }\n"
    return _jsc(core + body + "\nprint(JSON.stringify(" + call + "));")


def test_ws_lists_and_print_warnings_once_and_other_uses():
    for page in ("frontend/lists.html", "frontend/print.html"):
        out = _ws_js(page, _ws_profile())
        assert out.count("LOOK-END") == 1 and out.count("PREP-END") == 1, (page, out)
        assert out.index("ws-safety") < out.index("LOOK-END") < out.index("RECIPE-SENTINEL"), page
        assert "culinary-warning" not in out, page
        med = out[out.index("Medicinal preparations"):]
        med = med[:med.index("ws-section-h", 30)] if "ws-section-h" in med[30:] else med
        assert "MED-NOTES" in med and OTHER not in med and "Traditional uses" not in med, page
        assert ">Other uses</div>" in out and OTHER in out[out.index(">Other uses</div>"):], page
        none = _ws_js(page, _ws_profile(other=""))
        assert "Other uses" not in none, page                        # empty section omitted
        bare = _ws_js(page, _ws_profile(warn=False))
        assert "ws-safety" in bare and ("always confirm identification" in bare or
                                        "specific reason not yet documented" in bare), page   # box always stays


def test_ws_pdf_warnings_once_and_always_one_copy():
    for warn in (True, False):
        prof = _ws_profile(warn=warn)
        d = prof["safety"]
        d.setdefault("warnings", {})
        captured = {}
        real = lp._jinja_env.get_template("print_pdf.html")

        class _T:
            def render(self, **kw):
                captured["html"] = real.render(**kw)
                raise RuntimeError("stop before WeasyPrint")
        orig = lp._jinja_env.get_template
        lp._jinja_env.get_template = lambda n: _T()
        try:
            body = lp.PdfRequest(species=[lp.SpeciesData(scientific_name="N", profile=prof)], layout="workshop")
            try:
                lp.render_pdf(body, {"N": d})
            except RuntimeError:
                pass
        finally:
            lp._jinja_env.get_template = orig
        h = captured["html"]
        h = h[h.index('<div class="species-grid">'):]
        assert "entry-safety" in h and "Safety &amp; edibility" in h
        if warn:
            assert h.count("LOOK-END") == 1 and h.count("PREP-END") == 1 and "culinary-warning" not in h
            assert h.index("LOOK-END") < h.index("RECIPE-SENTINEL")
        else:
            assert "always confirm identification" in h
        assert OTHER not in h                                         # PDF never printed traditional_uses


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as exc:  # noqa: BLE001
                fails += 1
                print("FAIL", name, repr(exc)[:400])
    print("failures:", fails)
    sys.exit(1 if fails else 0)
