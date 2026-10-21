"""
Tests for the 21 Oct 2026 fix "AI drafting on DeepSeek + labelled PFAF fallback"
(Melvin D1–D5, audit REPORT section 0).

  * D1 — no Anthropic import or call is reachable from app/ or scripts/; the
    retired backend switch is gone (grep-based).
  * D2/D3 — no path writes "No known traditional medicinal uses": when AI text is
    missing the field gets PFAF's own Medicinal Uses text; PFAF "None known" (or
    no PFAF page) leaves it empty; a retired default is cleared.
  * Guards — only empty, unlocked, non-toxic fields with no pending AI text;
    every write has a pfaf_fallback history row; no text prefix.
  * D5 — is_curator_authored() is False for pfaf_fallback; the experience gates
    withhold that text.
  * An approved DeepSeek draft over PFAF text records the PFAF text as old_value.

No external calls (the AI generator is replaced by a stub). Throw-away SQLite DBs.

Run from project root:  python -m pytest tests/test_pfaf_fallback_deepseek.py -v
Or standalone:          python tests/test_pfaf_fallback_deepseek.py
"""

import asyncio
import json
import os
import re
import sqlite3
import sys
import tempfile
from datetime import datetime

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts", "experience_export"))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main  # noqa: E402,F401  (registers every model on Base.metadata)
import app.api.culinary as culinary  # noqa: E402
import app.services.enrichment as enrichment  # noqa: E402
import gates  # noqa: E402
from app.api.identity import Identity  # noqa: E402
from app.database import Base  # noqa: E402
from app.integrations.claude_draft import AIDraftResult  # noqa: E402
from app.integrations.pfaf import _parse as pfaf_parse  # noqa: E402
from app.models.culinary import CulinaryInfo  # noqa: E402
from app.models.species import (CulinaryInfoHistory, EnrichmentSource, Species,  # noqa: E402
                                SpeciesAIDraft, is_curator_authored, is_pfaf_fallback)
from app.services.ai_placeholder import (has_no_medicinal_uses_claim,  # noqa: E402
                                         is_only_no_medicinal_uses_claim,
                                         strip_no_medicinal_uses_claims)
from app.services.pfaf_fallback import (apply_pfaf_fallback, pfaf_fallback_fields,  # noqa: E402
                                        plan_pfaf_fallback)

CURATOR = Identity(user_id=None, is_guest=False, is_anonymous_guest=False, workshop_session_id=None)
OLD_DEFAULT = "No known traditional medicinal uses"
PFAF_MED = "The root is astringent and diuretic. A decoction is used to treat diarrhoea."
DISCLAIMER = ("Plants For A Future can not take any responsibility for any adverse effects from the use "
              "of plants. Always seek advice from a professional before using a plant medicinally.")


def _run(coro):
    return asyncio.run(coro)


def _pfaf_html(medicinal):
    return ("<html><body><table>"
            "<tr><td>Edibility Rating</td><td>2 (1-5)</td></tr>"
            "<tr><td><b>Known Hazards</b></td><td>None known</td></tr></table>"
            "<h2>Edible Uses</h2><p>Leaves - raw or cooked.</p>"
            f"<h2>Medicinal Uses</h2><p>{DISCLAIMER}</p><p>{medicinal}</p>"
            "<h2>Other Uses</h2><p>Dye.</p></body></html>")


DISCLAIMER_FIRST = ("Traditional and folk use only — not medical advice.  No traditional medicinal uses recorded "
                    "in available sources.  The source material provided contains only botanical data.")
CULINARY_FIRST = ("Young leaves are eaten raw in salads.\n\nNo traditional medicinal uses are recorded in the "
                  "available sources provided. The flowers make a fine cordial.")
CLAIM_AT_END = "Leaves were used to flavour ale.  **No traditional medicinal uses recorded in available sources.**"


# id, name, verdict, severity, PFAF medicinal text (None = no PFAF page), medicinal_notes now
SPECIES = [
    (1, "Filipendula vulgaris", None, "unknown", PFAF_MED, None),          # empty → PFAF text
    (2, "Tragopogon pratensis", "unknown", "unknown", "None known", None),  # PFAF None known → empty
    (3, "Agrimonia eupatoria", "edible", "none", PFAF_MED, OLD_DEFAULT),     # retired default → PFAF text
    (4, "Ganoderma applanatum", None, "unknown", None, OLD_DEFAULT),         # no PFAF page → cleared
    (5, "Conium maculatum", "toxic", "deadly", PFAF_MED, None),              # toxic → never
    (6, "Hedera helix", "inedible", "unknown", PFAF_MED, None),              # AI exclusion → never
    (7, "Aruncus dioicus", "edible", "toxic", PFAF_MED, None),               # toxic severity → never
    (8, "Urtica dioica", "edible", "none", PFAF_MED, None),                  # human-locked → never
    (9, "Sambucus nigra", "caution", "none", PFAF_MED, "Own text."),         # has text → never
    (10, "Rosa canina", "edible", "none", PFAF_MED, None),                   # pending AI draft → PFAF anyway (C1)
    (11, "Rubus idaeus", "edible", "none", PFAF_MED, OLD_DEFAULT),           # pending AI draft → PFAF anyway (C1)
    (12, "Plantago major", "edible", "none", PFAF_MED, None),                # only a no-uses draft → PFAF
    (13, "Digitalis purpurea", "toxic", "toxic", PFAF_MED, OLD_DEFAULT),     # toxic + default → cleared, no PFAF (C2)
    (14, "Lupinus polyphyllus", "inedible", "unknown", None, OLD_DEFAULT),   # inedible + default → cleared (C2)
    (15, "Rumex acetosella", "edible", "none", PFAF_MED, CULINARY_FIRST),     # claim inside text → only it removed
    (16, "Caltha palustris", "toxic", "toxic", None, CLAIM_AT_END),           # toxic too: claim removed, no PFAF
]


async def _db():
    path = os.path.join(tempfile.mkdtemp(prefix="pfftest_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    S = async_sessionmaker(eng, expire_on_commit=False)
    async with S() as s:
        for sid, name, verdict, sev, pf, med in SPECIES:
            s.add(Species(id=sid, scientific_name=name, name_key=name.lower(),
                          edibility_status=verdict, toxicity_severity=sev, kingdom="Plantae"))
            s.add(CulinaryInfo(id=100 + sid, species_id=sid, medicinal_notes=med,
                               ai_approved_fields_json=json.dumps(["medicinal_notes"])
                               if med in (OLD_DEFAULT, CULINARY_FIRST, CLAIM_AT_END) else None))
            if pf:
                s.add(EnrichmentSource(species_id=sid, source_name="pfaf", parsing_method="html_scrape",
                                       source_url=f"https://pfaf.org/user/Plant.aspx?LatinName={name}",
                                       raw_response_json=_pfaf_html(pf), retrieved_at=datetime(2026, 10, 1)))
        s.add(CulinaryInfoHistory(culinary_info_id=108, field_name="medicinal_notes", old_value="x",
                                  new_value=None, changed_by="human", changed_at=datetime(2026, 9, 1)))
        for sid in (10, 11):
            s.add(SpeciesAIDraft(species_id=sid, field_name="medicinal_notes", status="pending",
                                 model="deepseek/deepseek-chat",
                                 draft_text="Leaves were used as a poultice. Traditional and folk use only — not medical advice."))
        s.add(SpeciesAIDraft(species_id=12, field_name="medicinal_notes", status="pending", model="deepseek/deepseek-chat",
                             draft_text="No traditional medicinal uses recorded in available sources."))
        await s.commit()
    return path, eng, S


async def _apply_all(S):
    async with S() as s:
        out = {}
        for sid, *_ in SPECIES:
            sp = await s.get(Species, sid)
            ci = await s.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == sid))
            out[sid] = {d.field: d for d in await apply_pfaf_fallback(s, sp, ci)}
        await s.commit()
    return out


async def _state(S, sid):
    async with S() as s:
        ci = await s.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == sid))
        hist = (await s.execute(
            select(CulinaryInfoHistory).where(CulinaryInfoHistory.culinary_info_id == ci.id)
            .where(CulinaryInfoHistory.changed_by != "human").order_by(CulinaryInfoHistory.id)
        )).scalars().all()
        return ci, hist


# ── D1: no Anthropic path left ───────────────────────────────────────────────

_ANTHROPIC_CODE = re.compile(
    r"import\s+anthropic|from\s+anthropic\b|anthropic\.\w|AsyncAnthropic|api\.anthropic\.com"
    r"|\bgenerate_ai_drafts\b|\benrichment_backend\b|\banthropic_model\b|\bollama_draft\b|_ollama_generate")


def _sources(*dirs):
    for d in dirs:
        for base, _, files in os.walk(os.path.join(ROOT, d)):
            if "__pycache__" in base:
                continue
            for f in files:
                if f.endswith((".py", ".html", ".js")) and "vendor" not in base:
                    yield os.path.join(base, f)


def test_no_anthropic_import_or_call_reachable():
    hits = []
    for p in _sources("app", "scripts", "frontend"):
        for n, line in enumerate(open(p, encoding="utf-8", errors="replace"), 1):
            if line.lstrip().startswith(("#", "//")):
                continue                                   # comments may name what was retired
            if _ANTHROPIC_CODE.search(line):
                hits.append(f"{os.path.relpath(p, ROOT)}:{n}: {line.strip()[:100]}")
    assert not hits, "Anthropic / retired-backend code still present:\n" + "\n".join(hits)


def _code_strings_and_names(path):
    """String constants (docstrings excluded) and identifiers in a Python file."""
    import ast
    tree = ast.parse(open(path, encoding="utf-8").read())
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), ast.Constant):
                docstrings.add(id(first.value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            yield node.value
        elif isinstance(node, ast.Name):
            yield node.id
        elif isinstance(node, ast.Attribute):
            yield node.attr
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name
        elif isinstance(node, ast.alias):
            yield node.name


def test_no_writer_of_the_medicinal_default():
    """No code (comments/docstrings aside) holds the default sentence or the A5 writer."""
    hits = []
    for p in _sources("app", "scripts"):
        if not p.endswith(".py"):
            continue
        for v in _code_strings_and_names(p):
            if "no known traditional medicinal uses" in v.lower() or v in (
                    "MEDICINAL_NONE_DEFAULT", "_ensure_medicinal_default"):
                hits.append(f"{os.path.relpath(p, ROOT)}: {v[:60]!r}")
    assert not hits, hits


def test_claim_predicate_finds_the_claim_anywhere():
    assert has_no_medicinal_uses_claim(OLD_DEFAULT) and is_only_no_medicinal_uses_claim(OLD_DEFAULT)
    assert has_no_medicinal_uses_claim("No traditional medicinal folklore recorded in available sources.")
    # after the disclaimer / a heading — the whole text is the "nothing found" answer
    assert has_no_medicinal_uses_claim(DISCLAIMER_FIRST) and is_only_no_medicinal_uses_claim(DISCLAIMER_FIRST)
    heading = "# Populus tremula Traditional and Folk Uses\n\nNo traditional medicinal uses recorded in available sources."
    assert is_only_no_medicinal_uses_claim(heading)
    # after culinary text, and at the end — embedded, not the whole text
    for t in (CULINARY_FIRST, CLAIM_AT_END):
        assert has_no_medicinal_uses_claim(t) and not is_only_no_medicinal_uses_claim(t), t
    # hedged and source-meta wordings are the same claim
    for t in ("No specific medicinal applications, such as uses for sleep, are recorded within the source data.",
              "The source contains no information about traditional or folk medicinal uses of Epilobium.",
              "Based solely on the provided source data, there are no mentions of traditional medicinal uses for Abies alba.",
              "No known medicinal uses are documented.",
              "No traditional, folk, or ethnobotanical medicinal uses are mentioned in the available data.",
              "No ethnobotanical or folk medicinal applications are documented in the material supplied.",
              "The available source material does not record any traditional or folk medicinal uses."):
        assert has_no_medicinal_uses_claim(t), t


def test_claim_predicate_ignores_narrower_negations_and_real_uses():
    for t in (PFAF_MED, "", None,
              "There are no traditional uses of the root; the leaves were used as a poultice.",
              "There are no traditional medicinal uses of the root; the leaves were used as a poultice for wounds.",
              "A tea of the leaves treats coughs. No further traditional medicinal applications are recorded.",
              "No additional medicinal uses are recorded beyond this respiratory application.",
              "Its names suggest an association with the treatment of gout, though no explicit medicinal use is described.",
              "Traditional and folk use only — not medical advice.",
              # PFAF's own negations stay (they state uses / scope them)
              "Only the correct forms of eyebright are used, since other forms do not possess medicinal virtues[268].",
              "Fat hen is not employed in herbal medicine, though it does have some gentle properties.",
              "The seeds are edible, but should not be used for medicinal purposes.",
              "Although widely planted in herb gardens A. Mollis has no medicinal properties.",
              "Beyond these culinary uses, the source material does not record specific medicinal applications."):
        assert not has_no_medicinal_uses_claim(t), t


def test_placeholder_markers_do_not_collide_with_real_uses():
    """A refusal marker that is also a real use in source text must be a phrase (21 Oct 2026)."""
    from app.services.ai_placeholder import ai_placeholder_reason, is_ai_placeholder
    for field in ("medicinal_notes", "taste_notes", "recipe"):
        for real in ("Common vervain is used internally as a tonic and restorative for headaches, fevers, "
                     "nervous exhaustion, depression, gallbladder complaints and insufficient lactation.",
                     "It is used for dementia due to insufficient blood supply to the brain."):
            assert not is_ai_placeholder(field, real), (field, real)
        refusal = "There is insufficient information in the provided sources to write accurate notes."
        assert is_ai_placeholder(field, refusal)
        assert "insufficient information" in ai_placeholder_reason(field, refusal) \
            or "provided source" in ai_placeholder_reason(field, refusal)


def test_strip_removes_only_the_claim_sentences():
    assert strip_no_medicinal_uses_claims(CULINARY_FIRST) == "Young leaves are eaten raw in salads.\n\nThe flowers make a fine cordial."
    assert strip_no_medicinal_uses_claims(CLAIM_AT_END) == "Leaves were used to flavour ale."
    mid = "The shoots are cooked like asparagus. No known medicinal uses are documented. The flowers make a cordial."
    assert strip_no_medicinal_uses_claims(mid) == "The shoots are cooked like asparagus. The flowers make a cordial."
    italic = "*(The plant is eaten. No traditional medicinal uses beyond food preparation are recorded in the available sources.*"
    assert strip_no_medicinal_uses_claims(italic) == "*(The plant is eaten.*"          # an italic opened earlier stays closed
    assert strip_no_medicinal_uses_claims(PFAF_MED) == PFAF_MED                        # nothing to strip


# ── D2 / D3 / guards ─────────────────────────────────────────────────────────

def test_pfaf_parser_none_known_is_no_data():
    assert pfaf_parse("X", "u", _pfaf_html("None known")).medicinal_folklore is None
    assert pfaf_parse("X", "u", _pfaf_html("None Known")).medicinal_folklore is None
    assert pfaf_parse("X", "u", _pfaf_html("None Known. Although widely planted A. Mollis has no medicinal "
                                           "properties.")).medicinal_folklore is None          # opens with it
    assert pfaf_parse("X", "u", _pfaf_html(PFAF_MED)).medicinal_folklore == PFAF_MED   # disclaimer stripped


def test_fallback_rules_and_guards():
    async def run():
        path, eng, S = await _db()
        decisions = await _apply_all(S)
        states = {sid: await _state(S, sid) for sid, *_ in SPECIES}
        await eng.dispose()
        return decisions, states

    decisions, states = _run(run())
    med = {sid: d["medicinal_notes"] for sid, d in decisions.items()}
    expected = {1: ("fill", "pfaf_text"), 2: ("skip", "pfaf_none"), 3: ("fill", "pfaf_text"),
                4: ("clear", "no_pfaf_page"), 5: ("skip", "toxic_or_inedible"), 6: ("skip", "toxic_or_inedible"),
                7: ("skip", "toxic_or_inedible"), 8: ("skip", "human_locked"), 9: ("skip", "has_text"),
                10: ("fill", "pfaf_text"), 11: ("fill", "pfaf_text"), 12: ("fill", "pfaf_text"),
                13: ("clear", "toxic_or_inedible"), 14: ("clear", "toxic_or_inedible"),
                15: ("strip", "embedded_claim"), 16: ("strip", "embedded_claim")}
    assert {sid: (d.action, d.reason) for sid, d in med.items()} == expected

    for sid, (ci, hist) in states.items():
        value = ci.medicinal_notes
        assert value != OLD_DEFAULT and not has_no_medicinal_uses_claim(value), (sid, value)   # D3
        action = expected[sid][0]
        if action == "fill":
            assert value == PFAF_MED, (sid, value)                       # PFAF's own text, no prefix (D4)
            assert len(hist) == 1 and hist[0].changed_by == "pfaf_fallback" and hist[0].new_value == PFAF_MED
            assert hist[0].old_value == (OLD_DEFAULT if sid in (3, 11) else None)
            assert "medicinal_notes" not in json.loads(ci.ai_approved_fields_json or "[]")
        elif action == "strip":
            assert value and value == strip_no_medicinal_uses_claims(SPECIES[sid - 1][5])
            assert value == {15: "Young leaves are eaten raw in salads.\n\nThe flowers make a fine cordial.",
                             16: "Leaves were used to flavour ale."}[sid]
            assert len(hist) == 1 and hist[0].changed_by == "system:clear_false_default" and hist[0].new_value == value
            assert "medicinal_notes" in json.loads(ci.ai_approved_fields_json)        # still the approved AI text
        elif action == "clear":
            assert value is None
            assert len(hist) == 1 and hist[0].changed_by == "system:clear_false_default" \
                and hist[0].old_value == OLD_DEFAULT and hist[0].new_value is None
            assert "medicinal_notes" not in json.loads(ci.ai_approved_fields_json or "[]")
        else:
            assert hist == [], (sid, hist)                               # nothing written
    assert states[9][0].medicinal_notes == "Own text."
    # fields with no PFAF counterpart are never touched
    assert all(decisions[1][f].reason == "no_pfaf_counterpart" for f in ("taste_notes", "recipe", "medicinal_folklore"))


def test_fallback_is_idempotent_and_dry_plan_writes_nothing():
    async def run():
        path, eng, S = await _db()
        async with S() as s:
            sp = await s.get(Species, 1)
            ci = await s.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == 1))
            plan = await plan_pfaf_fallback(s, sp, ci, ["medicinal_notes"])
            await s.commit()
        _, hist_before = await _state(S, 1)
        await _apply_all(S)
        second = await _apply_all(S)
        _, hist_after = await _state(S, 1)
        await eng.dispose()
        return plan, hist_before, second, hist_after

    plan, hist_before, second, hist_after = _run(run())
    assert plan[0].action == "fill" and hist_before == []
    assert second[1]["medicinal_notes"].reason == "has_text" and len(hist_after) == 1


def test_enrich_species_with_ai_failure_fills_pfaf_or_leaves_empty():
    """End to end through enrich_species: DeepSeek returns nothing (AI failure)."""
    async def no_ai(**kw):
        return None

    async def none_async(*a, **kw):
        return None

    async def run(medicinal):
        path, eng, S = await _db()
        saved = {k: getattr(enrichment, k) for k in ("fetch_pfaf", "fetch_taxon_description", "fetch_trompenburg",
                                                     "_fetch_culinary_links_if_needed",
                                                     "_maybe_enrich_fungi_edibility", "generate_deepseek_drafts")}

        async def fake_pfaf(name, kingdom=None):
            return pfaf_parse(name, "https://pfaf.org/x", _pfaf_html(medicinal))
        enrichment.fetch_pfaf = fake_pfaf
        enrichment.fetch_taxon_description = none_async
        enrichment.fetch_trompenburg = none_async
        enrichment._fetch_culinary_links_if_needed = none_async
        enrichment._maybe_enrich_fungi_edibility = none_async
        enrichment.generate_deepseek_drafts = no_ai
        import app.integrations.culinary_links as cl
        saved_syn, cl.fetch_synthesis_context = cl.fetch_synthesis_context, none_async   # no network
        try:
            async with S() as s:
                s.add(Species(id=50, scientific_name="Geum urbanum", name_key="geum urbanum",
                              edibility_status="edible", toxicity_severity="none", kingdom="Plantae"))
                await s.commit()
                sp = await s.get(Species, 50)
                status = await enrichment.enrich_species(session=s, species=sp, wikidata_cache={})
                await s.commit()
            async with S() as s:
                ci = await s.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == 50))
                hist = (await s.execute(select(CulinaryInfoHistory.changed_by)
                                        .where(CulinaryInfoHistory.culinary_info_id == ci.id)
                                        .where(CulinaryInfoHistory.field_name == "medicinal_notes"))).scalars().all()
        finally:
            for k, v in saved.items():
                setattr(enrichment, k, v)
            cl.fetch_synthesis_context = saved_syn
            await eng.dispose()
        return status, ci, hist

    status, ci, hist = _run(run(PFAF_MED))
    assert status == "partial" and ci.medicinal_notes == PFAF_MED and hist == ["pfaf_fallback"]
    assert "medicinal_notes" not in json.loads(ci.ai_approved_fields_json or "[]")
    status, ci, hist = _run(run("None known"))
    assert ci.medicinal_notes is None and hist == []                       # PFAF None known → empty


def test_regenerate_path_with_ai_failure_uses_the_fallback():
    """culinary._generate_drafts_for_species (backfill / Regenerate) — the other old A5 caller."""
    import app.integrations.deepseek_draft as ds

    async def no_ai(**kw):
        return None

    async def run():
        path, eng, S = await _db()
        saved = ds.generate_deepseek_drafts
        ds.generate_deepseek_drafts = no_ai
        try:
            async with S() as s:
                out = await culinary._generate_drafts_for_species("Filipendula vulgaris", re_enrich=True, db=s)
                await s.commit()
        finally:
            ds.generate_deepseek_drafts = saved
        ci, hist = await _state(S, 1)
        await eng.dispose()
        return out, ci, hist

    out, ci, hist = _run(run())
    assert out["created"] == 0 and out["blocked"] is None
    assert ci.medicinal_notes == PFAF_MED and [h.changed_by for h in hist] == ["pfaf_fallback"]


# ── A: PFAF Medicinal Uses in the medicinal draft context + approve guard ────

def _capture_deepseek(seen):
    """Stub the per-field DeepSeek calls; record the context each one got."""
    import app.integrations.deepseek_draft as ds

    def make(field):
        async def fake(name, ctx_text, *a, **k):
            seen.setdefault(name, {})[field] = ctx_text
            return f"{field} draft for {name}."
        return fake
    saved = {n: getattr(ds, n) for n in ("generate_deepseek_taste_notes", "generate_deepseek_medicinal_notes",
                                         "generate_deepseek_recipe", "generate_deepseek_medicinal_folklore")}
    ds.generate_deepseek_taste_notes = make("taste_notes")
    ds.generate_deepseek_medicinal_notes = make("medicinal_notes")
    ds.generate_deepseek_recipe = make("recipe")
    ds.generate_deepseek_medicinal_folklore = make("medicinal_folklore")
    return ds, saved


def test_medicinal_context_includes_stored_pfaf_text_and_omits_none_known():
    async def none_async(*a, **k):
        return None

    async def run():
        path, eng, S = await _db()
        seen: dict = {}
        ds, saved = _capture_deepseek(seen)
        import app.integrations.culinary_links as cl
        saved_syn, cl.fetch_synthesis_context = cl.fetch_synthesis_context, none_async
        try:
            async with S() as s:
                for sid in (1, 2, 12):        # PFAF uses / PFAF None known / PFAF uses (edible)
                    sp = await s.get(Species, sid)
                    ci = await s.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == sid))
                    ci.edible_parts = "Leaves - raw or cooked."
                    await enrichment._maybe_generate_ai_drafts(
                        session=s, species=sp, ci=ci, re_enrich=True, inat_result=None,
                        trompenburg_result=None, common_names=[])
                await s.commit()
        finally:
            for k, v in saved.items():
                setattr(ds, k, v)
            cl.fetch_synthesis_context = saved_syn
            await eng.dispose()
        return seen

    seen = _run(run())
    assert f"Medicinal Uses (PFAF): {PFAF_MED}" in seen["Filipendula vulgaris"]["medicinal_notes"]
    assert "Medicinal Uses (PFAF)" not in seen["Tragopogon pratensis"]["medicinal_notes"]   # None known → nothing
    assert "Medicinal Uses (PFAF)" in seen["Plantago major"]["medicinal_notes"]
    assert "Medicinal Uses (PFAF)" not in seen["Plantago major"]["recipe"]                  # medicinal context only
    assert "Medicinal Uses (PFAF)" not in seen["Plantago major"]["taste_notes"]


def test_approve_refuses_false_no_uses_draft_and_allows_it_without_pfaf_text():
    from fastapi import HTTPException

    async def run():
        path, eng, S = await _db()
        out = {}
        async with S() as s:
            for sid in (1, 2):                # PFAF lists uses / PFAF None known
                s.add(SpeciesAIDraft(species_id=sid, field_name="medicinal_notes", status="pending",
                                     model="deepseek/deepseek-chat",
                                     draft_text="No traditional medicinal uses recorded in available sources."))
            await s.commit()
            queue = await culinary.ai_draft_review_queue(db=s)
            out["flag"] = {i["scientific_name"]: [d.get("false_no_uses") for d in i["drafts"]] for i in queue}
            for name in ("Filipendula vulgaris", "Tragopogon pratensis"):
                try:
                    r = await culinary.approve_ai_draft(name, "medicinal_notes", culinary.DraftEditApprove(),
                                                        db=s, identity=CURATOR)
                    out[name] = ("ok", r["status"])
                except HTTPException as e:
                    await s.rollback()
                    out[name] = (e.status_code, e.detail)
            # the curator's own edited text is theirs, even when it says "no uses"
            r = await culinary.approve_ai_draft("Filipendula vulgaris", "medicinal_notes",
                                                culinary.DraftEditApprove(edited_text="No known traditional medicinal uses here."),
                                                db=s, identity=CURATOR)
            out["edited"] = r["status"]
        await eng.dispose()
        return out

    out = _run(run())
    assert out["Filipendula vulgaris"][0] == 422 and "PFAF lists Medicinal Uses" in out["Filipendula vulgaris"][1]
    assert out["Tragopogon pratensis"] == ("ok", "approved")
    assert out["flag"]["Filipendula vulgaris"] == [out["Filipendula vulgaris"][1]]          # Review shows the reason
    assert out["flag"]["Tragopogon pratensis"] == [None]
    assert out["edited"] == "edited_approved"


# ── D4 / D5 ──────────────────────────────────────────────────────────────────

def test_pfaf_fallback_is_not_curator_authored():
    assert not is_curator_authored("pfaf_fallback", PFAF_MED, PFAF_MED)
    assert is_pfaf_fallback("pfaf_fallback", PFAF_MED, PFAF_MED)
    assert not is_pfaf_fallback("pfaf_fallback", PFAF_MED, PFAF_MED + " (edited)")
    assert not is_pfaf_fallback("human", PFAF_MED, PFAF_MED)
    assert not is_pfaf_fallback("pfaf_fallback", "", "")


def test_experience_gates_withhold_pfaf_fallback_text():
    async def run():
        path, eng, S = await _db()
        await _apply_all(S)
        async with S() as s:
            chips = await pfaf_fallback_fields(s, [101, 103, 109])
        await eng.dispose()
        return path, chips

    path, chips = _run(run())
    assert chips == {101: {"medicinal_notes"}, 103: {"medicinal_notes"}}
    conn = sqlite3.connect(path)
    assert gates.human_authored(conn, 101, "medicinal_notes", PFAF_MED) is False


def test_print_withholds_pfaf_fallback_text_and_prints_human_text():
    """B: profile payload → lists_pdf flattening → rendered print_pdf.html."""
    import app.api.lists_pdf as lp

    async def run():
        path, eng, S = await _db()
        await _apply_all(S)                              # 1 Filipendula: PFAF fallback text
        async with S() as s:
            ci = await s.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == 12))
            ci.medicinal_notes = "My own note on plantain."  # 12 Plantago: curator text
            s.add(CulinaryInfoHistory(culinary_info_id=ci.id, field_name="medicinal_notes", old_value=PFAF_MED,
                                      new_value=ci.medicinal_notes, changed_by="human", changed_at=datetime(2026, 10, 22)))
            await s.commit()
            profiles = {n: await culinary.species_profile(n, db=s, identity=CURATOR)
                        for n in ("Filipendula vulgaris", "Plantago major")}
        await eng.dispose()
        return profiles

    profiles = _run(run())
    assert profiles["Filipendula vulgaris"]["culinary"]["medicinal_notes"] == PFAF_MED       # species page keeps it (chip)
    assert profiles["Filipendula vulgaris"]["pfaf_fallback_fields"] == ["medicinal_notes"]
    flat = {n: lp._flatten_species(n, p, {}) for n, p in profiles.items()}
    assert flat["Filipendula vulgaris"]["medicinal_notes"] == ""                            # withheld from print
    assert flat["Plantago major"]["medicinal_notes"] == "My own note on plantain."          # human text prints
    ct = lp.ContentToggles().model_dump()
    html = lp._jinja_env.get_template("print_pdf.html").render(
        style="botanical", layout="workshop", cover={}, species=list(flat.values()), ct=ct,   # the layout with medicinal
        page_margin="10mm", goe_width=150, goe_pad=154, seasonal_returns=[])
    assert PFAF_MED not in html and "My own note on plantain." in html


def queue_untouched_draft_has_no_marker(queue):
    sambucus = next(i for i in queue if i["scientific_name"] == "Sambucus nigra")["drafts"][0]
    return "current_pfaf_fallback" not in sambucus                       # field holds own text, not PFAF


def test_review_queue_marks_a_draft_over_pfaf_text():
    async def run():
        path, eng, S = await _db()
        await _apply_all(S)
        async with S() as s:
            for sid in (1, 9):
                s.add(SpeciesAIDraft(species_id=sid, field_name="medicinal_notes", status="pending",
                                     model="deepseek/deepseek-chat", draft_text="Root decoction for diarrhoea."))
            await s.commit()
            queue = await culinary.ai_draft_review_queue(db=s)
        await eng.dispose()
        return queue

    queue = _run(run())
    item = next(i for i in queue if i["scientific_name"] == "Filipendula vulgaris")
    d = item["drafts"][0]
    assert d["current_pfaf_fallback"] is True and d["current_text"] == PFAF_MED
    rosa = next(i for i in queue if i["scientific_name"] == "Rosa canina")["drafts"][0]
    assert rosa["current_pfaf_fallback"] is True                         # C1: filled despite the pending draft
    assert queue_untouched_draft_has_no_marker(queue)


def test_approved_deepseek_draft_records_pfaf_text_as_old_value():
    async def run():
        path, eng, S = await _db()
        await _apply_all(S)
        async with S() as s:
            s.add(SpeciesAIDraft(species_id=1, field_name="medicinal_notes", status="pending",
                                 model="deepseek/deepseek-chat", draft_text="Root decoction for diarrhoea."))
            await s.commit()
            await culinary.approve_ai_draft("Filipendula vulgaris", "medicinal_notes",
                                            culinary.DraftEditApprove(), db=s, identity=CURATOR)
        ci, hist = await _state(S, 1)
        async with S() as s:
            chips = await pfaf_fallback_fields(s, [ci.id])
        await eng.dispose()
        return ci, hist, chips

    ci, hist, chips = _run(run())
    assert ci.medicinal_notes == "Root decoction for diarrhoea."
    last = hist[-1]
    assert last.changed_by == "ai_approved:human" and last.old_value == PFAF_MED
    assert chips == {}                                                   # chip gone once replaced
    assert "medicinal_notes" in json.loads(ci.ai_approved_fields_json)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
