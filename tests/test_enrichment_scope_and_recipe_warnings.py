"""
Enrichment scope + handout culinary rule + prep warnings with recipes
(Melvin, 22 Oct 2026).

  * Every bulk enrichment / backfill run takes a scope — a saved walk (walk
    membership, as on the map), Current list (Foraging List) or all eligible —
    through ONE resolver (app/services/enrichment_scope.py). No scope = nothing
    runs. Capped per run (default 25, walk species first); the rest are not
    queued and the summary says how many remain. The dry run counts the chosen
    scope only. A paused / interrupted enrichment run resumes within its own
    saved list, never across all eligible species.
  * Handout rule (safety_decision): a caution species prints culinary content
    with a curator-authored preparation OR look-alike warning.
  * (The cautionary-text-with-culinary-content tests moved to
    tests/test_batch8_guest_and_culinary_warnings.py with Fix B.)

Run: python tests/test_enrichment_scope_and_recipe_warnings.py
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

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

import test_enrichment_safety as base  # noqa: E402  (Env, Fakes, _client: temp DB + fake sources)
from test_enrichment_safety import CURATOR, JSC, Env, Fakes, _client, _run  # noqa: E402

import app.api.culinary as culinary_api  # noqa: E402
import app.api.encounters as encounters_api  # noqa: E402
import app.api.find as find_api  # noqa: E402
import app.api.lists_pdf as lp  # noqa: E402
import app.api.sharing as sharing  # noqa: E402
import app.api.walk as walk_api  # noqa: E402
import app.integrations.deepseek_draft as deepseek_draft  # noqa: E402
import app.services.enrichment as enr  # noqa: E402
from app.api.identity import get_identity  # noqa: E402
from app.database import get_db  # noqa: E402
from app.models.culinary import CulinaryInfo  # noqa: E402
from app.models.encounter import Encounter  # noqa: E402
from app.models.observation import Observation  # noqa: E402
from app.models.species import CulinaryInfoHistory, Species, safety_decision  # noqa: E402
from app.models.walk import SavedWalk  # noqa: E402
from app.services import enrichment_scope as es  # noqa: E402
from app.services.safety_gate import safety_for_species  # noqa: E402
from app.services.taxonomy import normalize_taxon_key  # noqa: E402

CURATED_PREP = "CURATED-PREP cook the leaves well." + " Long text." * 20 + " PREP-END"
CURATED_LOOK = "CURATED-LOOK dwarf elder looks alike." + " Long text." * 20 + " LOOK-END"
RECIPE_BODY = "RECIPE-SENTINEL fry gently"


JOB_QUEUE_SQL = ("CREATE TABLE IF NOT EXISTS job_queue (id INTEGER PRIMARY KEY, job_type VARCHAR(32) NOT NULL, "
                 "label TEXT NOT NULL, status VARCHAR(16) DEFAULT 'queued' NOT NULL, queue_position INTEGER, "
                 "progress_current INTEGER DEFAULT 0 NOT NULL, progress_total INTEGER DEFAULT 0 NOT NULL, payload TEXT, "
                 "created_at DATETIME NOT NULL, started_at DATETIME, ended_at DATETIME, error_message TEXT, "
                 "last_heartbeat DATETIME)")


def _job_queue(env):
    """job_queue is raw SQL in the app (no model), so create_all does not make it."""
    async def go():
        async with env.S() as s:
            await s.execute(text(JOB_QUEUE_SQL))
            await s.commit()
    _run(go())


def _add(env, rows):
    async def go():
        async with env.S() as s:
            for r in rows:
                s.add(r)
            await s.commit()
    _run(go())


def _species(env, sid, name, verdict="edible", sev="none", kingdom="Plantae", obs=True, ci=None, history=()):
    rows = [Species(id=sid, scientific_name=name, name_key=normalize_taxon_key(name),
                    edibility_status=verdict, toxicity_severity=sev, kingdom=kingdom)]
    if obs:
        rows.append(Observation(id=100 + sid, file_path=f"/x/{sid}.jpg", species_primary=name,
                                review_status="approved", identification_status="identified"))
    if ci is not None:
        rows.append(CulinaryInfo(id=500 + sid, species_id=sid, **ci))
        for field, txt, by in history:
            rows.append(CulinaryInfoHistory(culinary_info_id=500 + sid, field_name=field, old_value=None,
                                            new_value=txt, changed_by=by, changed_at=datetime(2026, 10, 20)))
    _add(env, rows)


class _Patch:
    def __init__(self, *triples):
        self.triples = triples

    def __enter__(self):
        self.saved = [(o, a, getattr(o, a)) for o, a, _ in self.triples]
        for o, a, v in self.triples:
            setattr(o, a, v)
        return self

    def __exit__(self, *a):
        for o, a, v in self.saved:
            setattr(o, a, v)


def _no_walks():
    async def none(db):
        return {}
    return _Patch((walk_api, "species_on_saved_walks", none))


def _resolve(env, req, eligible):
    async def go():
        async with env.S() as s:
            return await es.resolve(s, req, eligible)
    return _run(go())


# ── 1. the resolver ──────────────────────────────────────────────────────────

def test_resolver_scopes_walk_first_and_no_scope():
    env = Env()
    try:
        async def on_walks(db):
            return {"Urtica dioica": ["Walk A"]}

        async def walk_sp(db, walk_id):
            assert walk_id == 5
            return "Walk A", ["Rumex acetosa", "Not eligible here"]
        eligible = ["Allium ursinum", "Rumex acetosa", "Urtica dioica"]
        with _Patch((walk_api, "species_on_saved_walks", on_walks), (es, "walk_species", walk_sp)):
            for bad in (es.ScopeRequest(), es.ScopeRequest(scope="everything"), es.ScopeRequest(scope="walk"),
                        es.ScopeRequest(scope="list", species=[])):
                try:
                    _resolve(env, bad, eligible)
                    raise AssertionError(f"no 400 for {bad}")
                except HTTPException as e:
                    assert e.status_code == 400, bad
            w = _resolve(env, es.ScopeRequest(scope="walk", walk_id=5), eligible)
            assert w["names"] == ["Rumex acetosa"] and w["scope_label"] == "walk: Walk A" and w["remaining"] == 0
            lst = _resolve(env, es.ScopeRequest(scope="list", species=["Allium ursinum", "urtica  dioica"]), eligible)
            assert lst["names"] == ["Urtica dioica", "Allium ursinum"], lst      # name_key match, walk species first
            a = _resolve(env, es.ScopeRequest(scope="all"), eligible)
            assert a["names"] == ["Urtica dioica", "Allium ursinum", "Rumex acetosa"], a
    finally:
        env.close()


def test_cap_defaults_to_25_and_reports_the_remainder():
    env = Env()
    try:
        names = [f"Genus species{i:02d}" for i in range(30)]
        with _no_walks():
            r = _resolve(env, es.ScopeRequest(scope="all"), names)
            assert es.DEFAULT_CAP == 25 and r["cap"] == 25
            assert r["names"] == names[:25] and r["remaining"] == 5 and r["eligible_in_scope"] == 30
            r2 = _resolve(env, es.ScopeRequest(scope="all", cap=2), names)
            assert r2["names"] == names[:2] and r2["remaining"] == 28
            assert es.scope_summary(r2) == {"scope": "all", "scope_label": "all eligible species",
                                            "eligible_in_scope": 30, "remaining": 28, "cap": 2, "queued": 2}
    finally:
        env.close()


def test_walk_scope_is_the_walk_membership():
    env = Env()
    try:
        _add(env, [SavedWalk(id=5, name="Morning walk")])
        calls = []

        async def mem(db, walk):
            calls.append(walk.id)
            return {"stops": [{"species": [{"name": "Rumex acetosa"}, {"name": "Allium ursinum"}], "_wp": {}},
                              {"species": [{"name": "Rumex acetosa"}]}]}
        with _Patch((walk_api, "walk_membership_for", mem)):
            async def go():
                async with env.S() as s:
                    return await es.walk_species(s, 5)
            assert _run(go()) == ("Morning walk", ["Rumex acetosa", "Allium ursinum"]) and calls == [5]
    finally:
        env.close()


# ── 2. endpoints: each scope runs only its species; no scope = nothing ───────

def test_dry_runs_count_only_the_chosen_scope():
    env = Env()
    try:
        c = _client(env)
        with _no_walks():
            for url in ("/api/enrich/run", "/api/enrichment/run"):
                d = c.post(url + "?dry_run=true&scope=list&species=Urtica dioica", json={}).json()
                assert d["species_count"] == 1 and d["species_sample"] == ["Urtica dioica"], (url, d)
                assert d["queued"] == 1 and d["eligible_in_scope"] == 1 and d["remaining"] == 0, (url, d)
                assert d["scope_label"] == "Current list (1 species)", d
            d = c.post("/api/drafts/backfill?dry_run=true&field=recipe&scope=list&species=Urtica dioica").json()
            assert d["fields"] == {"recipe": 1} and d["species_count"] == 1, d
            d = c.post("/api/enrichment/run?dry_run=true&scope=all&cap=2", json={}).json()
            assert d["species_count"] == 2 and d["remaining"] == 1 and d["cap"] == 2, d
    finally:
        env.close()


def test_no_scope_runs_nothing():
    env = Env()
    try:
        _job_queue(env)
        c = _client(env)
        before = env.snapshot()
        culinary_api._enrichment_jobs.clear()
        with Fakes("ok", draft=None):
            for url, body in (("/api/enrich/run", None), ("/api/enrich/re-enrich-empty", None),
                              ("/api/enrichment/run", {}), ("/api/drafts/backfill", None),
                              ("/api/drafts/backfill?field=all", None),
                              ("/api/drafts/backfill?field=identification_notes", None),
                              ("/api/drafts/redraft-medicinal", {}),
                              ("/api/culinary/backfill-fungi-edibility", None)):
                r = c.post(url, json=body) if body is not None else c.post(url)
                assert r.status_code == 400 and r.json()["detail"] == es.NO_SCOPE_DETAIL, (url, r.text[:200])
        assert env.snapshot() == before
        assert not culinary_api._enrichment_jobs
        assert env.q("SELECT count(*) FROM job_queue")[0][0] == 0
    finally:
        env.close()


def test_scoped_run_enriches_only_its_species_and_saves_the_list():
    env = Env()
    try:
        c = _client(env)
        culinary_api._enrichment_jobs.clear()
        with _no_walks(), Fakes("ok", draft=None):
            d = c.post("/api/enrichment/run?scope=list&species=Rumex acetosa", json={}).json()
        assert d["count"] == 1 and d["remaining"] == 0, d
        job = culinary_api._enrichment_jobs[d["job_id"]]
        assert [l.split(" → ")[0] for l in job["log"]] == ["Rumex acetosa"], job["log"]
        payload = json.loads(env.q("SELECT payload FROM background_processes WHERE process_id = :p",
                                   p=d["process_id"])[0][0])
        assert payload["species"] == ["Rumex acetosa"] and payload["scope"]["scope"] == "list", payload
    finally:
        env.close()


def test_cap_stops_the_run_and_the_summary_reports_the_remainder():
    env = Env()
    try:
        c = _client(env)
        culinary_api._enrichment_jobs.clear()
        with _no_walks(), Fakes("ok", draft=None):
            d = c.post("/api/enrichment/run?scope=all&cap=2", json={}).json()
        assert d["count"] == 2 and d["remaining"] == 1 and d["cap"] == 2, d
        job = culinary_api._enrichment_jobs[d["job_id"]]
        assert len(job["log"]) == 2 and job["status"] == "complete", job
        assert job["result"]["remaining"] == 1 and job["result"]["cap"] == 2, job["result"]
    finally:
        env.close()


def _bp_row(env, pid, status, payload):
    async def go():
        async with env.S() as s:
            await s.execute(text(
                "INSERT INTO background_processes (process_id, process_type, status, started_at, updated_at, "
                "progress_current, progress_total, payload) VALUES (:pid, 'enrichment_run', :st, :t, :t, 1, 2, :p)"),
                {"pid": pid, "st": status, "t": f"2026-10-22 0{pid}:00", "p": json.dumps(payload)})
            await s.commit()
    _run(go())


def test_interrupted_scoped_run_resumes_within_its_own_list():
    env = Env()
    try:
        c = _client(env)
        culinary_api._enrichment_jobs.clear()
        _bp_row(env, 1, "interrupted", {"resume_after": "Allium ursinum",
                                        "species": ["Allium ursinum", "Urtica dioica"], "scope": {"scope": "walk"}})
        with Fakes("ok", draft=None):
            d = c.post("/api/enrichment/run", json={}).json()            # no scope needed to resume
        assert d["resume_source"] == "interrupted" and d["process_id"] == 1, d
        job = culinary_api._enrichment_jobs[d["job_id"]]
        assert [l.split(" → ")[0] for l in job["log"]] == ["Urtica dioica"], job["log"]   # never Rumex
    finally:
        env.close()


def test_old_unscoped_resume_point_is_never_resumed_across_all_species():
    env = Env()
    try:
        c = _client(env)
        culinary_api._enrichment_jobs.clear()
        _bp_row(env, 2, "paused", {"resume_after": "Allium ursinum"})      # pre-scope row: no species list
        r = c.post("/api/enrichment/run?dry_run=true", json={})
        assert r.status_code == 400 and r.json()["detail"] == es.NO_SCOPE_DETAIL, r.text
        with _no_walks():
            d = c.post("/api/enrichment/run?dry_run=true&scope=list&species=Rumex acetosa", json={}).json()
        assert d["species_count"] == 1 and "Fresh run" in d["note"], d
        r = c.post("/api/enrichment/run", json={})
        assert r.status_code == 400 and not culinary_api._enrichment_jobs
    finally:
        env.close()


def test_id_notes_backfill_respects_the_scope():
    env = Env()
    try:
        _job_queue(env)
        _species(env, 4, "Plantago major")             # no culinary_info → id_notes outstanding
        _species(env, 5, "Bellis perennis")
        c = _client(env)
        calls = []

        async def fake(scientific_name, ctx_text, api_key, model):
            calls.append(scientific_name)
            return "ID notes for " + scientific_name
        with _no_walks(), _Patch((deepseek_draft, "generate_deepseek_id_notes", fake)):
            d = c.post("/api/drafts/backfill?dry_run=true&field=identification_notes&scope=list"
                       "&species=Plantago major").json()
            assert d["fields"] == {"identification_notes": 1} and d["species_count"] == 1, d
            culinary_api._draft_backfill_job = None
            r = c.post("/api/drafts/backfill?field=identification_notes&scope=list&species=Plantago major").json()
            assert r["count"] == 1 and r["queued"] == 1, r
        assert calls == ["Plantago major"], calls
        assert env.q("SELECT id_notes FROM culinary_info WHERE species_id = 4")[0][0] == "ID notes for Plantago major"
        assert env.q("SELECT count(*) FROM culinary_info WHERE species_id = 5")[0][0] == 0
    finally:
        culinary_api._draft_backfill_job = None
        env.close()


LOGS = os.path.join(ROOT, "logs")


def test_redraft_medicinal_respects_the_scope_and_has_a_dry_run():
    logs_before = set(os.listdir(LOGS))
    env = Env()
    try:
        _job_queue(env)
        c = _client(env)
        calls = []

        async def fake(sess, sp, field):
            calls.append((sp.scientific_name, field))
            return False
        with _no_walks(), _Patch((enr, "_section_ai_draft", fake)):
            before = env.snapshot()
            d = c.post("/api/drafts/redraft-medicinal?dry_run=true&scope=list&species=Urtica dioica", json={}).json()
            assert d["dry_run"] and d["species_count"] == 1 and d["species_sample"] == ["Urtica dioica"], d
            assert d["queued"] == 1 and env.snapshot() == before
            culinary_api._draft_backfill_job = None
            r = c.post("/api/drafts/redraft-medicinal?scope=list&species=Urtica dioica", json={}).json()
            assert r["count"] == 1, r
        assert calls == [("Urtica dioica", "medicinal_notes")], calls
    finally:
        culinary_api._draft_backfill_job = None
        # The task writes logs/redraft_medicinal_jq<id>.json into the real logs/ — remove what this test wrote.
        for f in set(os.listdir(LOGS)) - logs_before:
            if f.startswith("redraft_medicinal_jq"):
                os.remove(os.path.join(LOGS, f))
        env.close()


def test_fungi_edibility_backfill_respects_the_scope_and_has_a_dry_run():
    env = Env()
    try:
        _species(env, 6, "Cantharellus cibarius", verdict="unknown", sev=None, kingdom="Fungi")
        _species(env, 7, "Boletus edulis", verdict="unknown", sev=None, kingdom="Fungi")
        c = _client(env)
        calls = []

        async def fake(sess, sp, ci):
            calls.append(sp.scientific_name)
        with _no_walks(), _Patch((enr, "_maybe_enrich_fungi_edibility", fake)):
            before = env.snapshot()
            d = c.post("/api/culinary/backfill-fungi-edibility?dry_run=true&scope=list"
                       "&species=Cantharellus cibarius").json()
            assert d["dry_run"] and d["species_count"] == 1 and d["drafts_may_create"] == {"edibility_status": 1}, d
            assert d["eligible_in_scope"] == 1 and env.snapshot() == before
            d = c.post("/api/culinary/backfill-fungi-edibility?dry_run=true&scope=all").json()
            assert d["species_count"] == 2, d
            r = c.post("/api/culinary/backfill-fungi-edibility?scope=list&species=Cantharellus cibarius").json()
        assert calls == ["Cantharellus cibarius"] and r["queued"] == 1, (calls, r)
    finally:
        env.close()


def test_every_bulk_button_picks_a_scope_first():
    """Each bulk enrichment / backfill button calls the scoped helper; the real
    request uses the same scoped URL the dry run used."""
    want = {"scan.html": ["'/api/enrich/run'", "'/api/enrich/re-enrich-empty'",
                          "'/api/drafts/backfill?field=' + encodeURIComponent(field)", "'/api/drafts/backfill?field=all'",
                          "'/api/culinary/backfill-fungi-edibility'", "'/api/drafts/redraft-medicinal'"],
            "review.html": ["'/api/enrichment/run'"], "settings.html": ["'/api/drafts/backfill'"]}
    for page, urls in want.items():
        src = open(os.path.join(ROOT, "frontend", page), encoding="utf-8").read()
        assert src.index('src="/static/js/lists.js"') < src.index('src="/static/js/dry-run.js"'), page
        for u in urls:
            assert ("lmScopedDryRunCheck(" + u) in src or ("lmScopedDryRunConfirm(" + u) in src, (page, u)
        assert "lmDryRunCheck('/api/drafts/backfill'" not in src and "lmDryRunCheck('/api/enrich/" not in src, page
    scan = open(os.path.join(ROOT, "frontend", "scan.html"), encoding="utf-8").read()
    assert scan.count("lmScopedDryRunCheck('/api/drafts/backfill', ") == 2         # queue resume / re-run
    assert 'id="btn-backfill-fungi"' in scan and 'id="btn-redraft-medicinal"' in scan


def test_scope_picker_js_sends_the_scope_to_dry_run_and_run():
    js = open(os.path.join(ROOT, "frontend/static/js/dry-run.js"), encoding="utf-8").read()
    script = """var window = this; var calls = [];
function fetch(u, i) { calls.push(u); return Promise.resolve({ ok: true, status: 200,
  json: function () { return Promise.resolve({ dry_run: true, species_count: 1, scope_label: 'walk: W', eligible_in_scope: 30,
    queued: 25, cap: 25, remaining: 5 }); } }); }
function confirm(t) { window.lastText = t; return true; } function alert() {}
""" + js + """
print(JSON.stringify({
  walk: lmScopeQuery({ scope: 'walk', walk_id: 5, cap: 25 }),
  list: lmScopeQuery({ scope: 'list', species: ['Allium ursinum', "St John's wort"], cap: 10 }),
  all: lmScopeQuery({ scope: 'all', cap: 25 }),
  text: lmDryRunSummaryText({ species_count: 25, scope_label: 'walk: W', eligible_in_scope: 30, queued: 25, cap: 25, remaining: 5 }, 'Run?')
}));"""
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(script)
    out = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=30)
    os.unlink(f.name)
    d = json.loads(out.stdout.strip().splitlines()[-1])
    assert d["walk"] == "scope=walk&cap=25&walk_id=5", d
    assert d["list"] == "scope=list&cap=10&species=Allium%20ursinum&species=St%20John's%20wort", d
    assert d["all"] == "scope=all&cap=25", d
    assert "Scope: walk: W — 30 eligible, 25 queued (cap 25); 5 not queued — run again for the rest" in d["text"], d
    # No preselected scope: Continue stays disabled until one is chosen; "all" is never checked by default.
    assert 'value="all" checked' not in js and "class=\"lm-scope-ok\" disabled" in js


# ── 3. handout rule ──────────────────────────────────────────────────────────

def test_caution_with_curator_lookalike_prints_culinary_content():
    look_only = safety_decision("none", "caution", None, "Curated look-alike")
    assert look_only["handout_culinary_allowed"] and look_only["handout_label"] == "⚠ caution"
    assert look_only["warning"] is None                                       # "warning" stays prep-only
    neither = safety_decision("none", "caution", None, None)
    assert not neither["handout_culinary_allowed"] and neither["culinary_allowed"]
    assert safety_decision("none", "caution", "Curated prep", None)["handout_culinary_allowed"]
    assert not safety_decision("toxic", "caution", None, "x")["handout_culinary_allowed"]


def test_handout_rule_reads_only_curator_authored_lookalikes():
    env = Env()
    try:
        _species(env, 11, "Sambucus nigra", verdict="caution",
                 ci={"look_alike_warnings": CURATED_LOOK},
                 history=[("look_alike_warnings", CURATED_LOOK, "human")])
        _species(env, 12, "Hypericum perforatum", verdict="caution",
                 ci={"look_alike_warnings": "PFAF look text"},
                 history=[("look_alike_warnings", "PFAF look text", "pfaf_reparse")])
        _species(env, 13, "Tanacetum vulgare", verdict="caution", ci={})

        async def go():
            async with env.S() as s:
                return {sid: await safety_for_species(s, await s.get(Species, sid)) for sid in (11, 12, 13)}
        d = _run(go())
        assert d[11]["handout_culinary_allowed"], d[11]
        assert not d[12]["handout_culinary_allowed"] and d[12]["handout_label"] == "⚠ caution — warning not yet reviewed"
        assert not d[13]["handout_culinary_allowed"]
        import gates
        c = sqlite3.connect(":memory:")
        c.execute("CREATE TABLE culinary_info_history (id INTEGER PRIMARY KEY, culinary_info_id INT, field_name TEXT,"
                  " new_value TEXT, changed_by TEXT, changed_at TEXT)")
        c.execute("INSERT INTO culinary_info_history VALUES (1, 5, 'look_alike_warnings', 'Look text', 'human', '2026')")
        sp = {"id": 1, "scientific_name": "X", "edibility_status": "caution", "toxicity_severity": "none"}
        assert gates.caution_lookalike(sp, {"id": 5, "look_alike_warnings": "Look text"}, c) == "Look text"
        assert gates.caution_warning(sp, {"id": 5, "look_alike_warnings": "Look text"}, c) is None
    finally:
        env.close()


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
