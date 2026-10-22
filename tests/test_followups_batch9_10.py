"""
Follow-ups + audit batches 9 and 10 (Melvin, 22 Oct 2026). Recon:
RECON_followups_batch9_10_22oct.md.

  * A1 recorded walks: a guest sees one (list, detail, trace) only when it is
    shown to guests; the audio is refused either way.
  * A2 recipe titles: never a blockquote or a safety-note line (Python rule and
    its JS twin agree on the same cases).
  * A3 interrupted publish: repaired when its commit is on the remote, failed
    otherwise; never pushes.
  * B1-03 kingdom audit, B1-05 reject-undo, B1-06 terminal evidence,
    C-02 encounter photos, E-05c copy log, E-05g anchored delete guard.

Run: python tests/test_followups_batch9_10.py
"""
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "experience_export"))

from sqlalchemy import text  # noqa: E402

from test_batch8_guest_and_culinary_warnings import (  # noqa: E402
    CURATOR, _app_client, _curator_device, _extract, _guest_device, _jsc, _src,
)
from test_enrichment_safety import Env, _run  # noqa: E402
from test_enrichment_scope_and_recipe_warnings import _Patch, _add, _job_queue  # noqa: E402
from test_stage_c_publish import Fakes, Site, _env as _pub_env, _pub, _publish, sh  # noqa: E402

import app.main as main  # noqa: E402
from app.models.encounter import Encounter, EncounterPhoto  # noqa: E402
from app.models.observation import Observation, ObservationEdit  # noqa: E402
from app.models.recorded_walk import RecordedWalk  # noqa: E402
from app.models.workshop import WorkshopParticipant  # noqa: E402
from app.models.species import recipe_display_title  # noqa: E402
from app.services import experience_publish as xp  # noqa: E402
from app.services import file_cleanup as fc  # noqa: E402
from app.services import guest_access as ga  # noqa: E402
from app.services import observation_service as osvc  # noqa: E402

TRACK = json.dumps([{"lat": 47.7, "lng": 7.8, "t": 0}, {"lat": 47.71, "lng": 7.81, "t": 60}])


def _done(env):
    main.app.dependency_overrides.clear()
    env.close()


# ══ A1 recorded walks ═════════════════════════════════════════════════════════

def _walk_env():
    env = Env()
    _job_queue(env)
    _add(env, [WorkshopParticipant(id=2, name="Alice")])          # the guest device's participant
    _add(env, [RecordedWalk(id=1, name="Private loop", started_at=datetime(2026, 10, 1), track_points_json=TRACK,
                            audio_note_path="media/recorded_walks/walk_a.webm", user_id=1),
               RecordedWalk(id=2, name="Workshop route", started_at=datetime(2026, 10, 2), track_points_json=TRACK,
                            audio_note_path="media/recorded_walks/walk_b.webm", user_id=1, shared_with_guests=True)])
    return env


def test_guest_sees_a_recorded_walk_only_when_shown_and_never_its_audio():
    env = _walk_env()
    try:
        with _guest_device(env):
            c = _app_client(env, None)
            lst = c.get("/api/recorded-walks").json()
            assert [w["id"] for w in lst] == [2] and lst[0]["audio_note_path"] is None
            assert c.get("/api/recorded-walks/1").status_code == 404               # hidden = not found
            d = c.get("/api/recorded-walks/2").json()
            assert len(d["track_points"]) == 2 and d["audio_note_path"] is None    # trace yes, audio no
            for f in ("walk_a.webm", "walk_b.webm"):
                r = c.get(f"/media/recorded-walks/{f}")
                assert r.status_code == 404 and r.headers.get("x-guest-gate") == "refused", f
            assert c.patch("/api/recorded-walks/1/share", json={"shared": True}).status_code == 403
        assert env.q("SELECT id, shared_with_guests FROM recorded_walks ORDER BY id") == [(1, 0), (2, 1)]
        with _curator_device(env):
            c = _app_client(env, CURATOR)
            lst = c.get("/api/recorded-walks").json()
            assert [w["id"] for w in lst] == [2, 1] and lst[1]["audio_note_path"]          # curator unchanged
            assert c.get("/api/recorded-walks/1").json()["audio_note_path"]
            r = c.patch("/api/recorded-walks/1/share", json={"shared": True})
            assert r.status_code == 200 and r.json() == {"id": 1, "shared_with_guests": True}
            assert env.q("SELECT shared_with_guests FROM recorded_walks WHERE id = 1") == [(1,)]
            c.patch("/api/recorded-walks/2/share", json={"shared": False})
        with _guest_device(env):
            c = _app_client(env, None)
            assert [w["id"] for w in c.get("/api/recorded-walks").json()] == [1]
            assert c.get("/api/recorded-walks/2").status_code == 404
        assert not ga.guest_api_allowed("PATCH", "/api/recorded-walks/1/share")
        idx = _src("frontend/index.html")
        assert '<label class="wd-share" data-guest-hide' in idx and "_wdSetShared(" in idx
    finally:
        _done(env)


# ══ A2 recipe titles ══════════════════════════════════════════════════════════

TITLE_CASES = [
    ({"title": "Nettle soup", "body": "> **Safety note** x"}, "Nettle soup"),
    ({"title": None, "body": "> **Safety note — read before you cook.** Possible digestive complaints.\n\n---\n\n"
                            "Acorns are one of the great quiet ingredients of the British larder, and more.\n"},
     "Acorns are one of the great quiet ingredients of the British larder, and more."),
    ({"title": "", "body": "**Safety note — read first:** Poisonous to ruminants.\n\n## Pickled Ash Keys\n\nText."},
     "Pickled Ash Keys"),
    ({"title": None, "body": "**Safety warning – mandatory statement:**\nHeart rhythm affected by large doses.\n\n"
                            "**Horehound Broth with Roasted Roots**\n\nMethod."}, "Horehound Broth with Roasted Roots"),
    ({"title": None, "body": "SAFETY WARNING — READ FIRST:** rotenone.\n\n### Safety\n\nGreat Mullein Infusion"},
     "Great Mullein Infusion"),
    ({"title": None, "body": "Recipe Title: Marsh Willowherb Soup\n\nBody."}, "Marsh Willowherb Soup"),
    ({"title": None, "body": "> quote only\n> still quote\n---\n"}, ""),
    ({"title": None, "body": "x" * 30 + " " + "y" * 200}, "x" * 30 + "…"),
]


def test_recipe_title_is_never_a_quote_or_safety_note_python_and_js():
    for rec, want in TITLE_CASES:
        got = recipe_display_title(rec["title"], rec["body"])
        assert got == want, (rec, got)
        low = got.lower()
        assert not got.startswith(">") and not low.startswith(("safety", "caution", "warning")), got
    js = _extract(_src("frontend/index.html"), "function _recipeMdPlain(", "function _summaryRecipe(")
    out = _jsc(js + "\nprint(JSON.stringify(" + json.dumps([c[0] for c in TITLE_CASES]) + ".map(_recipeTitle)));")
    assert out == [c[1] for c in TITLE_CASES], out                                          # the JS twin agrees
    src = _src("scripts/experience_export/export.py")
    assert "return recipe_display_title(rec.get(\"title\"), rec.get(\"body\"))" in src


# ══ A3 interrupted publish ════════════════════════════════════════════════════

def _bp_row(env, payload, status="running"):
    async def go():
        async with env.S() as s:
            r = await s.execute(text(
                "INSERT INTO background_processes (process_type, status, started_at, updated_at, last_heartbeat, "
                "progress_current, progress_total, detail, payload) VALUES ('experience_publish', :st, :now, :now, "
                ":now, 4, 8, 'Publish walk', :p)"), {"st": status, "now": datetime.utcnow(), "p": json.dumps(payload)})
            await s.commit()
            return r.lastrowid
    return _run(go())


def _bp(env, pid):
    st, payload, err = env.q(f"SELECT status, payload, error FROM background_processes WHERE process_id = {pid}")[0]
    return st, json.loads(payload), err


def test_interrupted_publish_is_repaired_when_its_commit_is_on_the_remote():
    site, env = Site(), _pub_env()
    try:
        # The run made its commit and pushed it, then the server died before "record".
        (site.clone / "w").mkdir(exist_ok=True)
        (site.clone / "w" / "x.txt").write_text("pushed")
        sh(site.clone, "add", "-A")
        sh(site.clone, "commit", "-qm", "publish")
        sha = sh(site.clone, "rev-parse", "HEAD")
        sh(site.clone, "push", "-q", "origin", "main")
        n = site.remote_count()
        snap = {"is_default": False, "species": [{"id": 1}], "recipes": []}
        pid = _bp_row(env, {"publication_id": 1, "kind": "publish", "commit": sha, "snapshot": snap})
        with Fakes(site).patch():
            done = _run(xp.repair_interrupted(site.clone))
        assert done and done[0]["state"] == "repaired", done
        status, commit, published, _, _ = _pub(env)
        assert (status, commit, published) == ("published", sha, 1)
        assert json.loads(env.q("SELECT public_species_json FROM experience_publications WHERE id = 1")[0][0]) == snap
        st, p, _ = _bp(env, pid)
        assert st == "complete" and p["repair"] == "repaired" and "record repaired" in p["repair_message"]
        assert site.remote_count() == n                                                      # nothing pushed
        with _curator_device(env), Fakes(site).patch():
            lr = _app_client(env, CURATOR).get("/api/experience/walks/5/panel").json()["publication"]["last_repair"]
        assert lr["state"] == "repaired" and sha[:7] in lr["message"]
        assert _run(xp.repair_interrupted(site.clone)) == []                                  # done once
    finally:
        _done(env)
        site.close()


def test_interrupted_publish_fails_when_the_commit_never_reached_the_remote():
    site, env = Site(), _pub_env()
    try:
        other = site.tmp / "other"
        subprocess.run(["git", "clone", "-q", str(site.remote), str(other)], check=True, capture_output=True)
        (other / "z.txt").write_text("never pushed")
        sh(other, "add", "-A")
        sh(other, "commit", "-qm", "local only")
        lost = sh(other, "rev-parse", "HEAD")
        n, head = site.remote_count(), site.remote_head()
        p1 = _bp_row(env, {"publication_id": 1, "kind": "publish", "commit": lost, "snapshot": None})
        p2 = _bp_row(env, {"publication_id": 1, "kind": "publish"}, status="interrupted")    # died before its commit
        with Fakes(site).patch():
            done = {d["process_id"]: d for d in _run(xp.repair_interrupted(site.clone))}
        assert done[p1]["state"] == "failed" and "not on GitHub" in done[p1]["message"]
        assert done[p2]["state"] == "failed" and "before its commit" in done[p2]["message"]
        assert _bp(env, p1)[0] == "failed" and _bp(env, p2)[0] == "failed"
        assert _pub(env)[0] == "draft"
        assert site.remote_count() == n and site.remote_head() == head and site.clean()      # never pushes
        src = Path(xp.__file__).read_text()
        body = src[src.index("async def repair_interrupted("):src.index("async def last_repair(")]
        assert not re.search(r'git\([^)]*"push"', body)                                  # no git push call at all
    finally:
        _done(env)
        site.close()


def test_interrupted_publish_offline_is_left_for_the_next_start():
    site, env = Site(), _pub_env()
    try:
        sha = site.head()
        sh(site.clone, "remote", "set-url", "origin", "https://foraging-experience.invalid/x.git")
        pid = _bp_row(env, {"publication_id": 1, "kind": "publish", "commit": sha, "snapshot": None})
        with Fakes(site).patch():
            done = _run(xp.repair_interrupted(site.clone))
        assert done[0]["state"] == "pending" and "couldn't check GitHub" in done[0]["message"]
        assert _bp(env, pid)[0] == "interrupted" and _pub(env)[0] == "draft"
    finally:
        _done(env)
        site.close()


def test_publish_stops_before_push_when_the_commit_cannot_be_saved():
    site, env = Site(), _pub_env()
    try:
        n = site.remote_count()

        async def nowhere(pid, **kw):
            return None
        with _Patch((xp, "bp_patch", nowhere)):
            _, job = _publish(env, Fakes(site))
        assert job["status"] == "stopped" and "Couldn't save the job record" in job["message"], job
        assert site.remote_count() == n and site.clean() and _pub(env)[0] == "draft"
    finally:
        _done(env)
        site.close()


# ══ B1-03 kingdom audit ═══════════════════════════════════════════════════════

def test_kingdom_audit_never_demotes_a_finalized_row():
    env = Env()
    try:
        cands = json.dumps([{"source": "inaturalist", "scientific_name": "Lumbricus terrestris", "score": 40.0,
                             "kingdom": "Animalia"}])
        _add(env, [Observation(id=301, file_path="/x/a.jpg", review_status="approved", identification_status="identified",
                               species_primary="Rumex acetosa", species_candidates_json=cands),
                   Observation(id=302, file_path="/x/b.jpg", review_status="manually_verified",
                               identification_status="identified", species_primary="Rumex acetosa",
                               species_candidates_json=cands),
                   Observation(id=303, file_path="/x/c.jpg", review_status="needs_review",
                               identification_status="identified", species_primary="Rumex acetosa",
                               species_candidates_json=cands)])
        with _curator_device(env):
            c = _app_client(env, CURATOR)
            dry = c.post("/api/trust/kingdom-audit").json()
            assert dry["total_flagged"] == 3 and dry["terminal_listed_not_changed"] == [301, 302]
            r = c.post("/api/trust/kingdom-audit?apply=true").json()
        assert r["sent_to_review"] == 1 and r["terminal_listed_not_changed"] == [301, 302]
        assert env.q("SELECT id, review_status, review_label FROM observations WHERE id IN (301,302,303) ORDER BY id") == \
            [(301, "approved", None), (302, "manually_verified", None), (303, "needs_review", "non_plant")]
        assert env.q("SELECT observation_id FROM observation_edits") == [(303,)]
    finally:
        _done(env)


# ══ B1-05 reject-undo ═════════════════════════════════════════════════════════

def _reject_and_undo(env, oid):
    with _curator_device(env), _Patch((fc, "UNDO_DIR", Path(tempfile.mkdtemp(prefix="undo_")))):
        c = _app_client(env, CURATOR)
        assert c.patch(f"/api/observations/{oid}/review?status=rejected").status_code == 200
        return c.post(f"/api/observations/{oid}/reject-undo")


def test_reject_undo_restores_the_status_and_reviewed_at_it_had():
    env = Env()
    try:
        human = datetime(2026, 9, 1, 10, 0)
        _add(env, [Observation(id=401, file_path="/x/a.jpg", review_status="approved", identification_status="identified",
                               species_primary="Rumex acetosa", reviewed_at=None),              # AI-agreed
                   Observation(id=402, file_path="/x/b.jpg", review_status="manually_verified",
                               identification_status="identified", species_primary="Rumex acetosa", reviewed_at=human),
                   Observation(id=403, file_path="/x/c.jpg", review_status="needs_review",
                               identification_status="identified", species_primary="Rumex acetosa")])
        for oid, want in ((401, "approved"), (402, "manually_verified"), (403, "needs_review")):
            r = _reject_and_undo(env, oid)
            assert r.status_code == 200 and r.json()["review_status"] == want, (oid, r.text)
        assert env.q("SELECT id, review_status, reviewed_at FROM observations WHERE id IN (401,402) ORDER BY id") == \
            [(401, "approved", None), (402, "manually_verified", "2026-09-01 10:00:00.000000")]   # AI-agreed stays AI-agreed
        # A row rejected with no recorded prior status is not guessed at.
        _add(env, [Observation(id=404, file_path="/x/d.jpg", review_status="rejected", identification_status="identified",
                               species_primary="Rumex acetosa")])
        with _curator_device(env):
            r = _app_client(env, CURATOR).post("/api/observations/404/reject-undo")
        assert r.status_code == 409 and env.q("SELECT review_status FROM observations WHERE id = 404") == [("rejected",)]
    finally:
        _done(env)


# ══ B1-06 terminal evidence ═══════════════════════════════════════════════════

def test_evidence_and_card_writes_respect_the_terminal_guard():
    src = _src("app/api/scan.py")
    body = src[src.index("async def _identify_scanned_inner("):src.index("async def _upsert_species_card(")]
    assert body.index("terminal = is_terminal_review_status(obs.review_status)") < body.index("obs.plantnet_raw_json")
    assert 'if obs.obs_category == "plant" and not terminal:' in body
    assert "            if not terminal:\n                obs.plantnet_raw_json = _json.dumps(" in body
    assert 'elif top["scientific_name"] and not terminal:\n' in body
    for line in body.splitlines():                                   # no other unguarded evidence write
        if "obs.plantnet_raw_json =" in line or "obs.category_suggested =" in line:
            assert line.startswith(" " * 16), line


# ══ C-02 encounter photos ═════════════════════════════════════════════════════

def test_reject_never_deletes_an_encounter_photo():
    env = Env()
    tmp = Path(tempfile.mkdtemp(prefix="c02_"))
    up, undo = tmp / "uploads", tmp / "undo"
    up.mkdir()
    try:
        bound, free = up / "enc.jpg", up / "free.jpg"
        bound.write_bytes(b"encounter photo")
        free.write_bytes(b"ordinary photo")
        _add(env, [Observation(id=501, file_path=str(bound), review_status="rejected", upload_source="file_upload"),
                   Observation(id=502, file_path=str(free), review_status="rejected", upload_source="file_upload"),
                   Encounter(id=14, user_id=1, encounter_date=datetime(2026, 10, 1), text_note="n"),
                   EncounterPhoto(encounter_id=14, observation_id=501, binding_method="own_named")])

        async def go():
            with _Patch((fc, "_DELETABLE_ROOTS", (up,)), (fc, "UNDO_DIR", undo)):
                async with env.S() as s:
                    for oid in (501, 502):
                        fc.delete_observation_file(await s.get(Observation, oid))
            for t in list(fc._pending_deletes.values()):
                t.cancel()
            fc._pending_deletes.clear()
        _run(go())
        assert bound.read_bytes() == b"encounter photo"                               # kept
        assert not free.exists() and len(list(undo.iterdir())) == 1                  # an ordinary one still goes
        import app.database as database
        with _Patch((database, "AsyncSessionLocal", None)):                           # lookup error → fails closed
            assert fc._bound_to_encounter(502) is True
    finally:
        _done(env)


# ══ E-05g anchored delete guard ═══════════════════════════════════════════════

def test_is_deletable_is_anchored_to_the_project():
    R = str(fc._PROJECT_ROOT)
    for p in (R + "/uploads/x.jpg", R + "/photos/pipeline2/a.jpg", R + "/photos/confirmed_plants/s/a.jpg", "uploads/x.jpg"):
        assert fc._is_deletable(p), p
    for p in ("/Volumes/DIGIERA/Pictures/uploads/x.jpg", R + "/uploads/../data/foragingid.db", R + "/uploads",
              "/tmp/uploads/x.jpg", "/Users/melvinjarman/Local(unsynced)/PhoneForaging/x.jpg", R + "/photos/x.jpg"):
        assert not fc._is_deletable(p), p


# ══ E-05c one confirmed-copy helper, failures logged ══════════════════════════

def test_confirmed_copy_has_one_definition_and_logs_failures():
    defs = subprocess.run(["grep", "-rn", "def _copy_to_confirmed", os.path.join(ROOT, "app")],
                          capture_output=True, text=True).stdout.strip().splitlines()
    assert len(defs) == 1 and "observation_service.py" in defs[0], defs
    assert "from app.services.observation_service import _copy_to_confirmed" in _src("app/api/bulk_actions.py")
    records = []

    class H(logging.Handler):
        def emit(self, r):
            records.append(r.getMessage())
    h = H()
    osvc._log.addHandler(h)
    try:
        o = Observation(id=601, file_path="/nowhere/missing.jpg", species_primary="Rumex acetosa")
        osvc._copy_to_confirmed(o)
        assert o.confirmed_copy_path is None and any("601" in m and "missing.jpg" in m for m in records), records

        def boom(obs, d):
            raise OSError("disk full")
        import app.services.export as ex
        with _Patch((ex, "copy_single", boom)):
            osvc._copy_to_confirmed(o)
        assert any("FAILED" in m and "disk full" in m for m in records), records
    finally:
        osvc._log.removeHandler(h)
    assert "so files are git-tracked" not in _src("app/services/observation_service.py")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
