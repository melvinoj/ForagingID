"""
Tests for audit batch 12 + A-04 + two batch 11 leftovers (Melvin, 25 Oct 2026).

  * D3-02: the export plan collects every GateError into its blockers (two
    unverified 'edible' species → two blockers in one plan); only the build
    stops, writing nothing. Real export.py on a backup copy of the DB.
  * C-05: a published publication row makes the saved-walk delete guard refuse
    (walk 4's row was backfilled from the site clone).
  * D3-05: the plan's changes show stop renumbering against the live page —
    per species old → new stop numbers, stops added and removed.
  * D3-04 leftover: the publish commit removes the site-root photos/ only when
    no file refers to it (local bare repo); the plan lists it as removed.
  * A-04: secrets come from the environment / .env only; Settings writes .env,
    never app_settings; a test run has no .env (never the real one); the live
    app_settings holds no secret value; .env is gitignored.
  * Batch 11 leftovers: startup writes no 'human' stamp; the bracken constant
    fills only empty fields and never overwrites text (a differing constant
    becomes a review card).

No external calls. Throw-away DBs, a temp copy of the live DB (read-only
source), a local bare git repo. Nothing touches ~/foraging-experience or GitHub.

Run from project root:  python tests/test_batch12_publish_secrets.py
"""
import asyncio
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

from test_stage_c_publish import (  # noqa: E402
    CURATOR, SITE, Fakes, Site, _app_client, _curator_device, _done, _env, _publish, good_plan,
)
from test_enrichment_scope_and_recipe_warnings import _add, _Patch  # noqa: E402
import app.config as config  # noqa: E402
import app.database as database  # noqa: E402
import app.services.settings_service as ss  # noqa: E402
from app.database import Base  # noqa: E402
from app.models.culinary import CulinaryInfo  # noqa: E402
from app.models.experience import ExperiencePublication  # noqa: E402
from app.models.settings import AppSetting  # noqa: E402
from app.models.species import CulinaryInfoHistory, Species, SpeciesAIDraft  # noqa: E402
from app.models.walk import SavedWalk  # noqa: E402
from app.services import experience_publish as xp  # noqa: E402
from app.services.enrichment import BRACKEN_CONSTANT_TEXT, enrich_species  # noqa: E402

EXPORT = os.path.join(ROOT, "scripts", "experience_export", "export.py")
LIVE_DB = Path(ROOT) / "data" / "foragingid.db"
SENTINEL = "sk-B12-DEEPSEEK-SENTINEL-4242"


# ── D3-02: every blocker in one plan ─────────────────────────────────────────

def _export(db, *args):
    return subprocess.run([sys.executable, EXPORT, "--walk-id", "4", "--db", str(db), *args],
                          capture_output=True, text=True, timeout=240)


def test_plan_lists_every_gate_blocker_and_the_build_writes_nothing():
    from app.services.db_snapshot import backup_to_file
    tmp = Path(tempfile.mkdtemp(prefix="b12plan_"))
    try:
        db = tmp / "t.db"
        backup_to_file(LIVE_DB, db)                       # read-only use of the live DB
        base = json.loads(_export(db, "--plan-json").stdout)
        assert base["ok"], base
        edible = [p["id"] for p in base["public_species"]
                  if p["badge"] == "edible" and p["verified_by"] == "human"][:2]
        assert len(edible) == 2, "walk 4 needs two human-verified edible species for this test"
        con = sqlite3.connect(db)
        con.execute(f"UPDATE species SET edibility_verified_by = 'auto' WHERE id IN ({edible[0]}, {edible[1]})")
        con.commit(); con.close()
        plan = json.loads(_export(db, "--plan-json").stdout)
        assert plan["ok"] and plan["buildable"] is False
        gate = [b for b in plan["blockers"] if "not human-verified" in b]
        assert sorted(int(b.split()[1]) for b in gate) == sorted(edible), plan["blockers"]
        badges = {p["id"]: p["badge"] for p in plan["public_species"]}
        assert badges[edible[0]] == badges[edible[1]] == "blocked"
        assert len(xp.plan_problems(plan)) >= 2
        out = tmp / "out"
        r = _export(db, "--out", str(out))
        assert r.returncode != 0 and "2 blocker(s), nothing written" in (r.stderr + r.stdout)
        assert not (out / "index.html").exists()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── C-05: the delete guard sees a published row ──────────────────────────────

def test_published_walk_cannot_be_deleted():
    env = _env()
    try:
        _add(env, [SavedWalk(id=4, name="Rümmelsbühl foray"),
                   ExperiencePublication(id=3, saved_walk_id=4, slug="rummelsbuhl-foray", is_default=False,
                                         status="published", published_at=datetime(2026, 10, 21, 17, 0, 10),
                                         published_commit="ed3b4d9f229a5f4bca66752b07748fb1a5b2e734",
                                         created_at=datetime(2026, 10, 25), updated_at=datetime(2026, 10, 25))])
        with _curator_device(env):
            r = _app_client(env, CURATOR).delete("/api/walk/saves/4")
        assert r.status_code == 409 and "rummelsbuhl-foray" in r.text, (r.status_code, r.text)
        assert env.q("SELECT id FROM saved_walks WHERE id = 4") == [(4,)]
    finally:
        from app import main
        main.app.dependency_overrides.clear()
        env.close()


def test_live_walk4_row_matches_the_site_clone():
    """Read-only: the backfilled row (batch 12 data) records what is live."""
    con = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    rows = con.execute("SELECT slug, status, is_default, published_commit, published_at FROM experience_publications "
                       "WHERE saved_walk_id = 4").fetchall()
    assert rows == [("rummelsbuhl-foray", "published", 0, "ed3b4d9f229a5f4bca66752b07748fb1a5b2e734",
                     "2026-10-21 17:00:10")], rows


# ── D3-05: stop renumbering in the plan ──────────────────────────────────────

def _live(stops):
    return {"species": [{"id": 1, "en": "Sorrel"}, {"id": 2, "en": "Nettle"}, {"id": 3, "en": "Ash"}],
            "walk": {"stops": stops}}


def test_plan_shows_stop_renumbering_added_and_removed():
    before = _live([{"n": "1", "lat": 47.1, "lng": 7.1, "species": [1]},
                    {"n": "2", "lat": 47.2, "lng": 7.2, "species": [2]},
                    {"n": "3", "lat": 47.3, "lng": 7.3, "species": [3]}])
    plan = good_plan()
    plan["public_species"].append({"id": 3, "scientific_name": "Fraxinus excelsior", "en": "Ash", "badge": "edible"})
    plan["stops"] = [{"label": "1", "lat": 47.1, "lng": 7.1, "species_ids": [1]},
                     {"label": "2", "lat": 47.3, "lng": 7.3, "species_ids": [3]},      # was 3
                     {"label": "2a", "lat": 47.25, "lng": 7.25, "species_ids": [2]}]   # new point
    s = xp.plan_changes(plan, before, "w/x/index.html")["stops"]
    assert s["stops_before"] == 3 and s["stops_now"] == 3
    assert s["renumbered_stops"] == [{"from": "3", "to": "2"}]
    assert {"species": "Ash", "from": ["3"], "to": ["2"]} in s["species_renumbered"]
    assert {"species": "Nettle", "from": ["2"], "to": ["2a"]} in s["species_renumbered"]
    assert s["stops_added"] == [{"stop": "2a", "species": ["Nettle"]}]
    assert s["stops_removed"] == [{"stop": "2", "species": ["Nettle"]}]
    assert xp.plan_changes(plan, None, "")["stops"] is None                          # first publish
    same = _live([{"n": st["label"], "lat": st["lat"], "lng": st["lng"], "species": st["species_ids"]}
                  for st in plan["stops"]])
    s2 = xp.plan_changes(plan, same, "w")["stops"]
    assert s2["renumbered_stops"] == s2["species_renumbered"] == s2["stops_added"] == s2["stops_removed"] == []


def test_panel_renders_stop_changes_and_removed_from_site():
    js = Path(ROOT, "frontend/static/js/walk-publish.js").read_text(encoding="utf-8")
    assert "h += renderStopChanges(c.stops);" in js and "function renderStopChanges(s)" in js
    assert "c.removed_from_site" in js and "Removed from site" in js


# ── D3-04 leftover: orphan root photos/ ──────────────────────────────────────

def test_orphan_detection_resolves_every_reference_form():
    tmp = Path(tempfile.mkdtemp(prefix="b12ph_"))
    try:
        (tmp / "photos").mkdir()
        (tmp / "photos" / "1.jpg").write_bytes(b"x" * 10)
        (tmp / "w" / "a" / "photos").mkdir(parents=True)
        (tmp / "index.html").write_text('<img src="w/a/photos/1.jpg">')
        (tmp / "w" / "a" / "index.html").write_text('<img src="photos/1.jpg"> s.photo = "photos/" + id;')
        assert xp.root_photos_refs(tmp, SITE) == []
        with _Patch((xp, "site_url", lambda: SITE)):
            assert xp.orphan_root_photos(tmp) == {"files": 1, "bytes": 10}
            for rel, text in (("w/a/tree.html", '<img src="../../photos/1.jpg">'),
                              ("walks.json", json.dumps({"image": SITE + "photos/1.jpg"})),
                              ("preview.html", "<script>var p = 'photos/' + n;</script>")):
                (tmp / rel).write_text(text)
                assert xp.root_photos_refs(tmp, SITE) == [rel], rel
                assert xp.orphan_root_photos(tmp) is None
                (tmp / rel).unlink()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_publish_removes_unreferenced_root_photos_in_the_same_commit():
    site, env = Site(front=None), _env()        # legacy root walk with root photos/
    try:
        before = site.remote_count()
        _, job = _publish(env, Fakes(site), front_page=False)
        assert job["status"] == "done", job
        assert site.remote_count() == before + 1
        files = site.remote_files()
        assert "photos/1.jpg" not in files                  # root copy gone
        assert "w/legacy/photos/1.jpg" in files             # the preserved walk keeps its own
        assert site.clean()
    finally:
        _done(env, site)


def test_referenced_root_photos_stay():
    site, env = Site(front=None), _env()
    try:
        (site.clone / "README.md").write_text("![map](photos/1.jpg)\n")
        subprocess.run(["git", "-C", str(site.clone), "commit", "-qam", "readme uses root photos"], check=True)
        subprocess.run(["git", "-C", str(site.clone), "push", "-q", "origin", "main"], check=True)
        _, job = _publish(env, Fakes(site), front_page=False)
        assert job["status"] == "done", job
        assert "photos/1.jpg" in site.remote_files()
    finally:
        _done(env, site)


def test_plan_lists_orphan_root_photos_as_removed_from_site():
    site, env = Site(front=None), _env()
    try:
        (site.clone / "preview.html").write_text('<img src="w/other/photos/1.jpg">')   # nothing uses root photos
        (site.clone / "index.html").write_text("<html>walk collection</html>")
        with _curator_device(env), Fakes(site).patch():
            r = _app_client(env, CURATOR).post("/api/experience/publications/1/plan")
        assert r.status_code == 200, r.text
        rm = r.json()["changes"]["removed_from_site"]
        assert len(rm) == 1 and rm[0].startswith("photos/ at the site root — 1 files"), rm
    finally:
        _done(env, site)


# ── A-04: secrets from the environment only ──────────────────────────────────

def test_a_test_run_never_reads_the_real_env_file():
    assert config.ENV_FILE is None
    assert config.env_file_path() is None
    r = subprocess.run(["git", "-C", ROOT, "check-ignore", "-q", ".env"])
    assert r.returncode == 0, ".env must be gitignored"


def _settings_db():
    path = os.path.join(tempfile.mkdtemp(prefix="b12set_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    return eng, async_sessionmaker(eng, expire_on_commit=False)


def test_secret_comes_from_env_never_the_db_and_settings_writes_env():
    async def run():
        eng, S = _settings_db()
        async with S() as s:
            s.add(AppSetting(key="deepseek_api_key", value="DB-VALUE-IGNORED", updated_by="human"))
            await s.commit()
        async with S() as s:
            await ss.load_settings_from_db(s)
        old = config.settings.deepseek_api_key
        object.__setattr__(config.settings, "deepseek_api_key", "")
        tmp_env = Path(tempfile.mkdtemp(prefix="b12env_")) / ".env"
        try:
            assert ss.get_setting("deepseek_api_key") == ""          # the DB row is never read
            # With no .env for this process, a save is refused (never the real file).
            async with S() as s:
                try:
                    await ss.save_setting("deepseek_api_key", SENTINEL, s)
                    raise AssertionError("saved with no .env")
                except ValueError:
                    pass
            with _Patch((config, "ENV_FILE", tmp_env)):
                async with S() as s:
                    await ss.save_setting("deepseek_api_key", SENTINEL, s)
                assert ss.get_setting("deepseek_api_key") == SENTINEL
                assert tmp_env.read_text() == f"DEEPSEEK_API_KEY={SENTINEL}\n"
                assert oct(tmp_env.stat().st_mode & 0o777) == "0o600"
                from app.services.api_dashboard import set_api_key
                async with S() as s:
                    r = await set_api_key("deepseek", SENTINEL + "-2", s)
                assert r["destination"] == "env" and f"DEEPSEEK_API_KEY={SENTINEL}-2" in tmp_env.read_text()
                async with S() as s:
                    await ss.reset_setting("deepseek_api_key", s)
                assert "DEEPSEEK_API_KEY=\n" in tmp_env.read_text() and ss.get_setting("deepseek_api_key") == ""
            async with S() as s:
                rows = {r.key: r.value for r in (await s.execute(select(AppSetting))).scalars()}
            assert rows == {"deepseek_api_key": "DB-VALUE-IGNORED"}   # the DB was never written
        finally:
            object.__setattr__(config.settings, "deepseek_api_key", old)
            await eng.dispose()
    asyncio.run(run())


def test_live_app_settings_holds_no_secret_value():
    con = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    rows = con.execute("SELECT key, length(value) FROM app_settings WHERE key IN "
                       "('deepseek_api_key', 'gdrive_access_token') OR key LIKE '%api_key%' "
                       "OR key LIKE '%token%' OR key LIKE '%secret%'").fetchall()
    assert all(n == 0 for _, n in rows), rows
    secret_keys = [e["key"] for e in ss.get_registry() if ss.is_secret_setting(e)]
    assert secret_keys == ["deepseek_api_key"] and all(e.get("env") for e in ss.get_registry()
                                                       if ss.is_secret_setting(e))


def test_nothing_reads_a_secret_from_app_settings_or_writes_one_there():
    from app.services import api_dashboard
    assert not any(a.get("db_key") for a in api_dashboard.API_REGISTRY)
    src = Path(ROOT, "app/services/api_dashboard.py").read_text(encoding="utf-8")
    assert "destination\": \"db\"" not in src and "_ENV_PATH" not in src


# ── Batch 11 leftovers ───────────────────────────────────────────────────────

def test_startup_writes_no_human_stamp():
    src = Path(ROOT, "app/database.py").read_text(encoding="utf-8")
    assert "SET edibility_verified_by = 'human'" not in src

    async def run():
        eng, S = _settings_db()
        async with S() as s:
            s.add(Species(id=1, scientific_name="Rumex testus", name_key="rumex testus", edibility_status="edible",
                          toxicity_severity="none", edibility_verified=True))     # lock, no provenance, no fingerprint
            await s.commit()
        real = database.engine
        database.engine = eng
        try:
            await database.init_db()
        finally:
            database.engine = real
        async with S() as s:
            sp = await s.get(Species, 1)
        await eng.dispose()
        return sp
    sp = asyncio.run(run())
    assert sp.edibility_verified_by == "unlocked_for_review" and not sp.edibility_verified


def _bracken(edible_parts, prep, human_history=False):
    async def run():
        eng, S = _settings_db()
        async with S() as s:
            s.add(Species(id=12, scientific_name="Pteridium aquilinum", name_key="pteridium aquilinum",
                          edibility_status="toxic", toxicity_severity="toxic", edibility_verified=True,
                          edibility_verified_by="human"))
            s.add(CulinaryInfo(id=5, species_id=12, edible_parts=edible_parts, preparation_warnings=prep))
            if human_history:
                s.add(CulinaryInfoHistory(culinary_info_id=5, field_name="preparation_warnings", old_value=None,
                                          new_value=prep, changed_by="human", changed_at=datetime(2026, 10, 1)))
            await s.commit()
        async with S() as s:
            sp = await s.get(Species, 12)
            await enrich_species(session=s, species=sp, re_enrich=True)
            await s.commit()
        async with S() as s:
            ci = await s.get(CulinaryInfo, 5)
            drafts = [(d.field_name, d.draft_text, d.status) for d in
                      (await s.execute(select(SpeciesAIDraft))).scalars()]
        await eng.dispose()
        return ci, drafts
    return asyncio.run(run())


def test_bracken_fills_only_empty_fields():
    ci, drafts = _bracken(None, "")
    assert ci.edible_parts == BRACKEN_CONSTANT_TEXT["edible_parts"]
    assert ci.preparation_warnings == BRACKEN_CONSTANT_TEXT["preparation_warnings"]
    assert drafts == []


def test_bracken_never_overwrites_curator_text_and_queues_a_review_card():
    mine = "Melvin: all parts carcinogenic — never eat, not even the young fronds."
    ci, drafts = _bracken("None", mine, human_history=True)
    assert ci.preparation_warnings == mine and ci.edible_parts == "None"
    assert ("preparation_warnings", BRACKEN_CONSTANT_TEXT["preparation_warnings"], "pending") in drafts
    assert ("edible_parts", BRACKEN_CONSTANT_TEXT["edible_parts"], "pending") in drafts


def test_bracken_equal_text_writes_nothing():
    ci, drafts = _bracken(BRACKEN_CONSTANT_TEXT["edible_parts"], BRACKEN_CONSTANT_TEXT["preparation_warnings"])
    assert drafts == []


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
