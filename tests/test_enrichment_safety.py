"""
Enrichment safety + clean drafts (Melvin, 22 Oct 2026) — the lessons of the
21 Oct offline run (bp 203) and the 22 Oct AI draft census.

The REAL enrichment code (enrich_species, run_enrichment_batch, the draft
generators, the endpoints) on a throw-away DB. Source fetchers and DeepSeek are
replaced by fakes; a fake fetcher reports to net_health exactly as the real
ones do (DNS failure → note_failure, answer → note_success).

Run from project root:  python tests/test_enrichment_safety.py
"""
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main  # noqa: E402,F401
import app.database as database  # noqa: E402
import app.api.culinary as culinary_api  # noqa: E402
import app.api.enrich as enrich_api  # noqa: E402
import app.api.recipes as recipes_api  # noqa: E402
import app.integrations.deepseek_draft as deepseek_mod  # noqa: E402
import app.integrations.wikidata as wikidata  # noqa: E402
import app.services.background_processes as bp_mod  # noqa: E402
import app.services.enrichment as enr  # noqa: E402
import app.services.settings_service as ss  # noqa: E402
from app.api.identity import Identity, get_identity  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.integrations.claude_draft import AIDraftResult  # noqa: E402
from app.integrations.pfaf import PFAFResult  # noqa: E402
from app.models.culinary import CulinaryInfo  # noqa: E402
from app.models.observation import Observation  # noqa: E402
from app.models.species import EnrichmentSource, Species, SpeciesAIDraft  # noqa: E402
from app.services import draft_gate, net_health  # noqa: E402
from app.services.taxonomy import normalize_taxon_key  # noqa: E402

CURATOR = Identity(user_id=1, is_guest=False, is_anonymous_guest=False, workshop_session_id=None)
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
ss._cache.update({"pfaf_delay_s": 0, "wikidata_delay_s": 0})


def _run(c):
    return asyncio.run(c)


# ── fixture ──────────────────────────────────────────────────────────────────
PREP = "Curator-free source warning: cook well."
SPECIES = [  # id, name, verdict, severity, edible_parts
    (1, "Allium ursinum", "edible", "none", "Leaves raw or cooked."),
    (2, "Urtica dioica", "edible", "none", "Young leaves cooked."),
    (3, "Rumex acetosa", "caution", "none", "Leaves in small amounts."),
]


class Env:
    def __init__(self):
        path = os.path.join(tempfile.mkdtemp(prefix="enrsafe_"), "t.db")
        Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
        self.eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
        self.S = async_sessionmaker(self.eng, expire_on_commit=False)
        self._patched = []
        for mod in (database, culinary_api, enrich_api, bp_mod):
            self._patched.append((mod, "AsyncSessionLocal", getattr(mod, "AsyncSessionLocal")))
            mod.AsyncSessionLocal = self.S

        async def seed():
            async with self.S() as s:
                for sid, name, verdict, sev, ep in SPECIES:
                    s.add(Species(id=sid, scientific_name=name, name_key=normalize_taxon_key(name),
                                  edibility_status=verdict, toxicity_severity=sev, kingdom="Plantae"))
                    s.add(CulinaryInfo(id=100 + sid, species_id=sid, edible_parts=ep, preparation_warnings=PREP,
                                       seasonal_peak="spring", id_notes="Old ID notes.", data_confidence=0.6,
                                       sources_json=json.dumps([{"name": "PFAF", "url": "u"}]),
                                       traditional_uses="Old uses."))
                    s.add(Observation(id=10 + sid, file_path=f"/x/{sid}.jpg", species_primary=name,
                                      review_status="approved", identification_status="identified"))
                s.add(SpeciesAIDraft(id=900, species_id=1, field_name="taste_notes", draft_text="Old pending taste.",
                                     status="pending", generated_at=datetime(2026, 10, 1), model="m"))
                await s.commit()
        _run(seed())

    def close(self):
        for mod, attr, val in self._patched:
            setattr(mod, attr, val)
        _run(self.eng.dispose())

    def q(self, sql, **kw):
        async def go():
            async with self.S() as s:
                return (await s.execute(text(sql), kw)).fetchall()
        return _run(go())

    def snapshot(self):
        """Every row of the tables enrichment may touch."""
        return {t: self.q(f"SELECT * FROM {t} ORDER BY 1") for t in
                ("species", "culinary_info", "culinary_info_history", "enrichment_sources", "species_ai_drafts",
                 "background_processes")}


class Fakes:
    """Source fetchers + DeepSeek. mode: 'ok' | 'offline' | 'pfaf_down'."""
    def __init__(self, mode="ok", pfaf=None, draft=None, network_up=False):
        self.mode, self.pfaf, self.draft, self._up = mode, pfaf, draft, network_up
        self.deepseek_calls = 0

    def __enter__(self):
        self._saved = [(enr, n, getattr(enr, n)) for n in
                       ("fetch_pfaf", "fetch_taxon_description", "fetch_trompenburg", "fetch_wikidata",
                        "fetch_wikidata_batch", "generate_deepseek_drafts", "_fetch_culinary_links_if_needed")]
        self._saved.append((deepseek_mod, "generate_deepseek_drafts", deepseek_mod.generate_deepseek_drafts))
        self._saved.append((net_health, "network_up", net_health.network_up))
        f = self

        async def pfaf(name, kingdom=None):
            if f.mode in ("offline", "pfaf_down"):
                net_health.note_failure("pfaf", "[Errno 8] nodename nor servname provided")
                return None
            net_health.note_success("pfaf")
            return f.pfaf

        async def inat(name):
            if f.mode == "offline":
                net_health.note_failure("inaturalist", "[Errno 8]")
                return None
            net_health.note_success("inaturalist")
            return None

        async def tromp(name):
            if f.mode == "offline":
                net_health.note_failure("trompenburg", "curl exit 6")
                return None
            net_health.note_success("trompenburg")
            return None

        async def wd_batch(names):
            return {n: (wikidata.WIKIDATA_FAILED if f.mode == "offline" else None) for n in names}

        async def wd_one(name):
            return None

        async def deepseek(**kw):
            f.deepseek_calls += 1
            return f.draft

        async def links(*a, **k):
            return None

        async def up(timeout=5.0):
            return f._up

        enr.fetch_pfaf, enr.fetch_taxon_description, enr.fetch_trompenburg = pfaf, inat, tromp
        enr.fetch_wikidata_batch, enr.fetch_wikidata = wd_batch, wd_one
        enr.generate_deepseek_drafts = deepseek
        deepseek_mod.generate_deepseek_drafts = deepseek
        enr._fetch_culinary_links_if_needed = links
        net_health.network_up = up
        return self

    def __exit__(self, *a):
        for mod, n, v in self._saved:
            setattr(mod, n, v)


def _pfaf(**kw):
    base = dict(scientific_name="x", source_url="https://pfaf.org/x", raw_html="<html>page</html>",
                edible_parts=None, preparation_methods=None, culinary_traditions=None, seasonal_peak=None,
                harvest_stage=None, preparation_warnings=None, look_alike_warnings=None, traditional_uses=None,
                edibility_rating=None)
    base.update(kw)
    return PFAFResult(**base)


def _draft(**kw):
    return AIDraftResult(taste_notes=kw.get("taste"), medicinal_notes=kw.get("med"), recipe=kw.get("recipe"),
                         medicinal_folklore=None, model="deepseek/test", context_used={"edible_parts": "x"})


def _client(env):
    api = FastAPI()
    api.include_router(culinary_api.router)
    api.include_router(enrich_api.router)
    api.include_router(recipes_api.router)

    async def _get_db():
        async with env.S() as s:
            yield s
    api.dependency_overrides[get_db] = _get_db
    api.dependency_overrides[get_identity] = lambda: CURATOR
    return TestClient(api)


async def _enrich_one(env, sid, **kw):
    async with env.S() as s:
        sp = await s.get(Species, sid)
        st = await enr.enrich_species(s, sp, re_enrich=True, **kw)
        if st == "no_network":
            await s.rollback()
        else:
            await s.commit()
        return st


# ── 1. offline run ───────────────────────────────────────────────────────────

def test_offline_run_writes_nothing_and_pauses():
    env = Env()
    try:
        before = env.snapshot()
        with Fakes("offline", network_up=False) as f:
            out = _run(enr.run_enrichment_batch(re_enrich=True))
        assert out["stopped_reason"] == "no_network", out
        assert out["stopped_at"] is not None and out["last_completed"] is None, out
        assert out["no_network"] >= 1 and f.deepseek_calls == 0, out
        after = env.snapshot()
        assert after == before, {t: (len(before[t]), len(after[t])) for t in before if before[t] != after[t]}
    finally:
        env.close()


def test_offline_species_alone_returns_no_network_and_writes_nothing():
    env = Env()
    try:
        before = env.snapshot()
        with Fakes("offline"):
            assert _run(_enrich_one(env, 1)) == "no_network"
        assert env.snapshot() == before
    finally:
        env.close()


# ── 2. failed source ─────────────────────────────────────────────────────────

def test_failed_source_leaves_confidence_fields_and_sources_unchanged():
    env = Env()
    try:
        before = env.q("SELECT data_confidence, sources_json, edible_parts, preparation_warnings, seasonal_peak, "
                       "traditional_uses, id_notes FROM culinary_info WHERE id=101")
        with Fakes("pfaf_down"):
            st = _run(_enrich_one(env, 1))
        assert st != "no_network"                       # iNat / Trompenburg answered
        after = env.q("SELECT data_confidence, sources_json, edible_parts, preparation_warnings, seasonal_peak, "
                      "traditional_uses, id_notes FROM culinary_info WHERE id=101")
        assert after == before, (before, after)
        pf = env.q("SELECT count(*) FROM enrichment_sources WHERE species_id=1 AND source_name='pfaf'")[0][0]
        assert pf == 0                                   # no empty "no data" row for the failed source
    finally:
        env.close()


# ── 3. bulk never touches pending drafts; regenerate side by side ────────────

def test_bulk_run_leaves_every_pending_draft_untouched():
    env = Env()
    try:
        with Fakes("ok", pfaf=None, draft=_draft(taste="New taste text that is long enough to keep.",
                                                 med="Leaves were used as a spring tonic in folk practice.",
                                                 recipe="Wild garlic pesto: blend leaves with oil and nuts.")):
            out = _run(enr.run_enrichment_batch(re_enrich=True))
        old = env.q("SELECT status, draft_text FROM species_ai_drafts WHERE id=900")[0]
        assert old == ("pending", "Old pending taste."), old
        taste_pending = env.q("SELECT count(*) FROM species_ai_drafts WHERE species_id=1 AND field_name='taste_notes' "
                              "AND status='pending'")[0][0]
        assert taste_pending == 1                          # no second taste draft beside the pending one
        assert env.q("SELECT count(*) FROM species_ai_drafts WHERE status='invalidated'")[0][0] == 0
        assert out["drafts_created"] > 0, out              # fields with none pending still got drafts
    finally:
        env.close()


def test_single_species_regenerate_side_by_side_and_keep_new():
    env = Env()
    try:
        c = _client(env)
        with Fakes("ok", draft=_draft(taste="A fresh taste note about garlicky leaves, mild and green.")):
            r = c.post("/api/drafts/generate", json={"scientific_name": "Allium ursinum", "re_enrich": True})
        assert r.status_code == 200 and r.json()["created"] >= 1, r.text
        rows = env.q("SELECT id, status FROM species_ai_drafts WHERE species_id=1 AND field_name='taste_notes' ORDER BY id")
        assert [s for _, s in rows] == ["pending", "pending"], rows        # both, side by side
        new_id = rows[-1][0]
        q = c.get("/api/culinary/ai-draft-review").json()
        tastes = [d for sp in q if sp["scientific_name"] == "Allium ursinum" for d in sp["drafts"]
                  if d["field_name"] == "taste_notes"]
        assert len(tastes) == 2
        r = c.post(f"/api/species/Allium ursinum/drafts/taste_notes/approve?draft_id={new_id}", json={})
        assert r.status_code == 200 and r.json()["retired_versions"] == 1, r.text
        st = dict(env.q("SELECT id, status FROM species_ai_drafts WHERE species_id=1 AND field_name='taste_notes'"))
        assert st == {900: "invalidated", new_id: "approved"}, st
        ctx = json.loads(env.q("SELECT generation_context_json FROM species_ai_drafts WHERE id=900")[0][0])
        assert ctx["invalidated_reason"] == f"replaced: Melvin kept draft {new_id}"
    finally:
        env.close()


def test_rejecting_the_new_version_keeps_the_old_one():
    env = Env()
    try:
        c = _client(env)
        with Fakes("ok", draft=_draft(taste="Another fresh taste note, peppery and green, good raw.")):
            c.post("/api/drafts/generate", json={"scientific_name": "Allium ursinum", "re_enrich": True})
        new_id = env.q("SELECT max(id) FROM species_ai_drafts")[0][0]
        assert c.post(f"/api/species/Allium ursinum/drafts/taste_notes/reject?draft_id={new_id}").status_code == 200
        assert env.q("SELECT status FROM species_ai_drafts WHERE id=900")[0][0] == "pending"
    finally:
        env.close()


def test_failed_regenerate_changes_nothing():
    env = Env()
    try:
        c = _client(env)
        before = env.snapshot()
        with Fakes("ok", draft=None):                       # DeepSeek returned nothing
            r = c.post("/api/drafts/generate", json={"scientific_name": "Allium ursinum", "re_enrich": True})
        assert r.status_code == 200 and r.json()["created"] == 0
        after = env.snapshot()
        assert after["species_ai_drafts"] == before["species_ai_drafts"]
    finally:
        env.close()


# ── 4 / 5. protected fields ──────────────────────────────────────────────────

def test_warning_fields_never_overwritten_empty_filled_changed_becomes_review_card():
    env = Env()
    try:
        async def clear_look():
            async with env.S() as s:
                (await s.get(CulinaryInfo, 101)).look_alike_warnings = None
                await s.commit()
        _run(clear_look())
        new = _pfaf(preparation_warnings="PFAF says something different now.",
                    look_alike_warnings="Resembles lily of the valley.")
        with Fakes("ok", pfaf=new):
            _run(_enrich_one(env, 1))
        row = env.q("SELECT preparation_warnings, look_alike_warnings FROM culinary_info WHERE id=101")[0]
        assert row == (PREP, "Resembles lily of the valley."), row          # kept / filled when empty
        card = env.q("SELECT field_name, draft_text, status, model, generation_context_json FROM species_ai_drafts "
                     "WHERE species_id=1 AND field_name='preparation_warnings'")
        assert len(card) == 1 and card[0][1:4] == ("PFAF says something different now.", "pending", "source_update:pfaf")
        assert json.loads(card[0][4])["field_text_at_import"] == PREP
        # A "None known" source never proposes blanking a warning.
        with Fakes("ok", pfaf=_pfaf(preparation_warnings="None known")):
            _run(_enrich_one(env, 2))
        assert env.q("SELECT preparation_warnings FROM culinary_info WHERE id=102")[0][0] == PREP
        assert env.q("SELECT count(*) FROM species_ai_drafts WHERE species_id=2 AND field_name='preparation_warnings'")[0][0] == 0
    finally:
        env.close()


def test_edible_parts_id_notes_seasonal_peak_with_text_never_overwritten():
    env = Env()
    try:
        from app.integrations.inaturalist import INatTaxonDescription
        new = _pfaf(edible_parts="Completely new edible parts text.", seasonal_peak="autumn")
        with Fakes("ok", pfaf=new) as f:
            async def inat(name):
                net_health.note_success("inaturalist")
                return INatTaxonDescription(scientific_name=name, taxon_id=1, description="New iNat description.",
                                            identification_notes=None, wikipedia_url="https://w", raw_json={})
            enr.fetch_taxon_description = inat
            _run(_enrich_one(env, 1))
        row = env.q("SELECT edible_parts, seasonal_peak, id_notes FROM culinary_info WHERE id=101")[0]
        assert row == ("Leaves raw or cooked.", "spring", "Old ID notes."), row
        cards = {r[0]: r[1] for r in env.q("SELECT field_name, draft_text FROM species_ai_drafts "
                                           "WHERE species_id=1 AND model LIKE 'source_update:%'")}
        assert cards["edible_parts"] == "Completely new edible parts text." and cards["seasonal_peak"] == "autumn"
        assert "New iNat description." in cards["id_notes"]
    finally:
        env.close()


# ── 6. Wikidata batches ──────────────────────────────────────────────────────

def test_wikidata_batch_of_638_names_stays_under_the_url_limit():
    names = [f"Longgenusname{i:03d} verylongepithetname{i:03d} subsp. evenlongerinfraspecificname" for i in range(638)]
    chunks = wikidata._chunks(names)
    assert sum(len(c) for c in chunks) == 638 and len(chunks) >= 13
    assert max(wikidata.batch_url_length(c) for c in chunks) <= wikidata.MAX_URL_LEN
    assert wikidata.batch_url_length(names) > 20000                      # the 21 Oct single request


def test_wikidata_failed_batch_is_marked_failed_not_no_entry():
    import httpx

    class _C:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url, params=None):
            return httpx.Response(414, request=httpx.Request("GET", url))
    real = wikidata.httpx.AsyncClient
    wikidata.httpx.AsyncClient = _C
    try:
        out = _run(wikidata.fetch_wikidata_batch(["Allium ursinum", "Urtica dioica"]))
    finally:
        wikidata.httpx.AsyncClient = real
    assert all(v is wikidata.WIKIDATA_FAILED for v in out.values()), out


# ── 7. resume ────────────────────────────────────────────────────────────────

def test_resume_continues_after_the_last_completed_species():
    env = Env()
    try:
        seen = []
        with Fakes("ok", draft=None):
            out = _run(enr.run_enrichment_batch(re_enrich=True, resume_after="Allium ursinum",
                                                progress_cb=lambda c, t, n, s: seen.append((c, t, n))))
        assert [n for _, _, n in seen] == ["Rumex acetosa", "Urtica dioica"], seen      # sorted, after Allium
        assert seen[0][:2] == (2, 3) and out["last_completed"] == "Urtica dioica"
    finally:
        env.close()


def test_interrupted_run_with_a_resume_point_is_resumed():
    env = Env()
    try:
        async def rows():
            async with env.S() as s:
                await s.execute(text(
                    "INSERT INTO background_processes (process_id, process_type, status, started_at, updated_at, "
                    "progress_current, progress_total, payload) VALUES (1, 'enrichment_run', 'interrupted', "
                    "'2026-10-22 01:00', '2026-10-22 02:00', 1, 3, :p)"), {"p": json.dumps({
                        "resume_after": "Allium ursinum",
                        # the run's scoped list (22 Oct 2026) — a resume stays within it
                        "species": ["Allium ursinum", "Rumex acetosa", "Urtica dioica"]})})
                await s.commit()
        _run(rows())
        pt = _run(bp_mod.bp_resume_point("enrichment_run"))
        assert pt["resume_after"] == "Allium ursinum" and pt["status"] == "interrupted"
        c = _client(env)
        d = c.post("/api/enrichment/run?dry_run=true", json={}).json()
        assert d["species_count"] == 2 and "after Allium ursinum" in d["note"], d
    finally:
        env.close()


# ── 8. the shared pre-save check ─────────────────────────────────────────────

class _Sp:
    def __init__(self, edib="edible", sev="none", name="Allium ursinum"):
        self.edibility_status, self.toxicity_severity, self.scientific_name, self.id = edib, sev, name, 1


class _Ci:
    def __init__(self, ep="Leaves raw or cooked."):
        self.edible_parts = ep


def test_gate_refuses_each_case_and_counts_it():
    cases = [
        ("medicinal_notes", "No traditional medicinal uses are recorded for Picea orientalis in the available data.",
         _Sp(), _Ci(), "no_use"),
        ("medicinal_notes", "Picea orientalis yields resin. No specific medicinal uses are recorded; a tea…",
         _Sp(), _Ci(), "no_use"),
        ("recipe", "Here’s a recipe written in Melvin Jarman’s voice, using hornbeam as the core ingredient.",
         _Sp(), _Ci(), "chat_phrasing"),
        ("taste_notes", "Based solely on the provided source data, the leaves taste mild and grassy overall.",
         _Sp(), _Ci(), "chat_phrasing"),
        ("recipe", "Simmer the leaves gently with butter and serve on toast with lemon.",
         _Sp(), _Ci("None known"), "no_edible_parts"),
        ("recipe", "Simmer the leaves gently with butter and serve on toast with lemon.",
         _Sp("toxic", "toxic"), _Ci(), "toxic_culinary"),
        ("medicinal_notes", "A tincture of the root, 5 drops taken internally, was used for pain in folk medicine.",
         _Sp("toxic", "deadly", "Aconitum napellus"), _Ci(), "deadly_internal"),
    ]
    with draft_gate.summary_scope() as summ:
        for field, txt, sp, ci, reason in cases:
            g = draft_gate.check_ai_draft(field, txt, sp, ci)
            assert not g.ok and g.reason == reason, (field, txt[:40], g)
            assert draft_gate.save_ai_draft(None, sp, ci, field, txt, model="m") is None
    assert summ.created == 0 and sum(summ.skipped.values()) == len(cases), summ
    assert summ.skipped["chat_phrasing"] == 2 and summ.skipped["no_use"] == 2


def test_run_summary_counts_refused_drafts():
    env = Env()
    try:
        with Fakes("ok", draft=_draft(med="No traditional medicinal uses are documented for this species.",
                                      recipe="Wild garlic pesto, written in Melvin’s voice: blend the leaves with oil and nuts.")):
            out = _run(enr.run_enrichment_batch(re_enrich=True))
        assert out["drafts_skipped"].get("no_use", 0) >= 1 and out["drafts_skipped"].get("chat_phrasing", 0) >= 1, out
        assert env.q("SELECT count(*) FROM species_ai_drafts WHERE field_name IN ('medicinal_notes','recipe')")[0][0] == 0
    finally:
        env.close()


def test_leading_none_known_line_is_stripped_from_a_saved_recipe():
    env = Env()
    try:
        body = "**Safety note — preparation warning: None known**\n\n---\n\n# Wild garlic butter\n\nSoften butter, fold in leaves."
        with Fakes("ok", draft=_draft(recipe=body)):
            c = _client(env)
            async def clear():
                async with env.S() as s:
                    for d in (await s.scalars(select(SpeciesAIDraft))).all():
                        d.status = "rejected"
                    await s.commit()
            _run(clear())
            c.post("/api/drafts/generate", json={"scientific_name": "Allium ursinum", "re_enrich": True})
        saved = env.q("SELECT draft_text FROM species_ai_drafts WHERE field_name='recipe' AND status='pending'")
        assert saved and saved[0][0] == "# Wild garlic butter\n\nSoften butter, fold in leaves.", saved
        for v in ("None known", "**None known**", "Safety note: None known", "**Safety Warning:** None known",
                  "SAFETY (mandatory): None known", "None known — though I’ve never had trouble"):
            assert draft_gate.strip_none_known_line(v + "\n\nBody.") == "Body.", v
    finally:
        env.close()


# ── 9. every button: dry run first, writes nothing ───────────────────────────

def test_every_dry_run_writes_nothing():
    env = Env()
    try:
        c = _client(env)
        before = env.snapshot()
        with Fakes("ok", draft=_draft(taste="x" * 80)) as f:
            calls = [
                ("/api/enrichment/run?dry_run=true&scope=all", {}),
                ("/api/drafts/generate?dry_run=true", {"scientific_name": "Allium ursinum", "re_enrich": True}),
                ("/api/drafts/bulk-generate?dry_run=true", {"species": ["Allium ursinum", "Urtica dioica"]}),
                ("/api/drafts/backfill?dry_run=true&scope=all", None),
                ("/api/drafts/backfill?field=all&dry_run=true&scope=all", None),
                ("/api/drafts/backfill?field=identification_notes&dry_run=true&scope=all", None),
                ("/api/drafts/redraft-medicinal?dry_run=true&scope=all", {}),
                ("/api/culinary/backfill-fungi-edibility?dry_run=true&scope=all", None),
                ("/api/culinary/Allium ursinum/enrich?dry_run=true", None),
                ("/api/culinary/Allium ursinum/enrich?section=taste&dry_run=true", None),
                ("/api/enrich/run?dry_run=true&scope=all", None),
                ("/api/enrich/re-enrich-empty?dry_run=true&scope=all", None),
            ]
            for url, body in calls:
                r = c.post(url, json=body) if body is not None else c.post(url)
                assert r.status_code == 200 and r.json().get("dry_run") is True, (url, r.status_code, r.text[:200])
            assert f.deepseek_calls == 0
        assert env.snapshot() == before
        assert not any(j.get("status") == "running" for j in culinary_api._enrichment_jobs.values())
    finally:
        env.close()


BUTTON_ENDPOINTS = re.compile(r"/api/(enrichment/run|enrich/run|enrich/re-enrich-empty|drafts/(generate|bulk-generate|backfill|redraft-medicinal)(?![\w-])"
                              r"|culinary/backfill-fungi-edibility"
                              r"|culinary/\$\{[^}]+\}/enrich|species/\$\{[^}]+\}/recipes/regenerate)")


def test_every_frontend_button_asks_the_dry_run_first():
    """Each fetch that starts enrichment / drafts goes through lmDryRunConfirm, or sits
    in a handler whose first statement is lmDryRunCheck. Auto-enrich after a species-ID
    correction (Review) is not a button and is listed explicitly."""
    AUTO = {"review.html": 4}          # _enrichAfterCorrection-style calls (approve flow)
    for page in ("review.html", "scan.html", "settings.html", "species.html", "index.html"):
        src = open(os.path.join(ROOT, "frontend", page), encoding="utf-8").read()
        assert '<script src="/static/js/dry-run.js"></script>' in src, page
        unguarded = []
        for m in re.finditer(r"(?:await\s+)?(fetch|lmDryRunConfirm|lmDryRunCheck|lmScopedDryRunConfirm|lmScopedDryRunCheck)\(\s*[`'\"]([^`'\"]+)", src):
            kind, url = m.group(1), m.group(2)
            if not BUTTON_ENDPOINTS.search(url) or "dry_run=true" in url or "/status" in url:
                continue
            if kind != "fetch":
                continue
            fn_start = src.rfind("function ", 0, m.start())
            body = src[fn_start:m.start()]
            if any(h in body for h in ("lmDryRunCheck(", "lmDryRunConfirm(", "lmDryRunSummaryText(",
                                       "lmScopedDryRunCheck(", "lmScopedDryRunConfirm(")):
                continue
            unguarded.append((src.count("\n", 0, m.start()) + 1, url))
        assert len(unguarded) == AUTO.get(page, 0), (page, unguarded)


def test_dry_run_helper_cancel_sends_nothing_real():
    js = open(os.path.join(ROOT, "frontend/static/js/dry-run.js"), encoding="utf-8").read()
    script = """var window = this; var calls = [];
function fetch(u, i) { calls.push(u); return Promise.resolve({ ok: true, status: 200,
  json: function () { return Promise.resolve({ dry_run: true, species_count: 2, fields_may_fill: { edible_parts: 1 } }); } }); }
var answer = false; function confirm(t) { window.lastText = t; return answer; } function alert() {}
""" + js + """
lmDryRunConfirm('/api/enrichment/run', { method: 'POST' }, 'Run?').then(function (r) {
  var cancelled = { r: r, calls: calls.slice() };
  answer = true; calls = [];
  return lmDryRunConfirm('/api/enrichment/run', { method: 'POST' }, 'Run?').then(function (r2) {
    print(JSON.stringify({ cancelled: cancelled, ok_calls: calls, text: window.lastText }));
  });
});"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(script)
    out = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=30)
    os.unlink(f.name)
    d = json.loads(out.stdout.strip().splitlines()[-1])
    assert d["cancelled"]["r"] is None and d["cancelled"]["calls"] == ["/api/enrichment/run?dry_run=true"], d
    assert d["ok_calls"] == ["/api/enrichment/run?dry_run=true", "/api/enrichment/run"], d
    assert "Species: 2" in d["text"] and "edible parts: 1" in d["text"] and "Nothing has been written yet" in d["text"]


if __name__ == "__main__":
    for _name, _fn in list(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print("ok", _name)
