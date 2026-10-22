"""
Stage C — the Publish panel (Melvin, 22 Oct 2026). Recon:
RECON_stage_c_publish_22oct.md.

Every git step runs against a throwaway site: a local bare "GitHub" repo plus a
clone of it, both in a temp folder. The export (plan / build) is replaced by a
fake that writes real page files and JPEGs; the "live site" is read from the
bare repo. Nothing touches ~/foraging-experience, GitHub or the ForagingID
repo's git.

  * Publish is refused / stopped by an unconfirmed hazard, a failed EXIF check
    and an unticked confirm; nothing is committed in any of those cases.
  * A successful run makes exactly one commit in the site and none in ForagingID.
  * Remote moved on → stop, no force-push. Offline → stop before the push, clone clean.
  * Unpublish removes the walk's page in one commit and keeps the saved walk;
    the front page goes only when it is this walk's.
  * Guests never see the Publish block or reach its endpoints.

Run: python tests/test_stage_c_publish.py
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "experience_export"))

from PIL import Image  # noqa: E402

from test_batch8_guest_and_culinary_warnings import (  # noqa: E402
    CURATOR, _app_client, _curator_device, _guest_device, _src,
)
from test_enrichment_safety import Env, _run  # noqa: E402
from test_enrichment_scope_and_recipe_warnings import _Patch, _add, _job_queue  # noqa: E402

import app.main as main  # noqa: E402
import gates  # noqa: E402
from app.models.experience import ExperiencePublication  # noqa: E402
from app.models.walk import SavedWalk  # noqa: E402
from app.services import experience_publish as xp  # noqa: E402
from app.services import guest_access as ga  # noqa: E402

SITE = "https://example.test/site/"
GIT_ID = ["-c", "user.name=Test", "-c", "user.email=test@example.test", "-c", "commit.gpgsign=false"]


def sh(cwd, *args):
    r = subprocess.run(["git", *GIT_ID, *args], cwd=str(cwd), capture_output=True, text=True)
    assert r.returncode == 0, (args, r.stderr)
    return r.stdout.strip()


def page_html(slug, title="T", impressum="https://x.test/impressum"):
    data = {"slug": slug, "title": title, "impressum_url": impressum, "datenschutz_url": "https://x.test/ds",
            "contact_url": "https://x.test/c",
            "species": [{"id": 1, "sci": "Rumex acetosa", "en": "Sorrel", "badge": {"kind": "edible"}}],
            "recipes": [{"recipe_id": 7, "species_id": 1, "dish": "Sorrel soup"}]}
    return f"<html><script>window.DATA = {json.dumps(data)};</script></html>"


class Site:
    """A bare 'GitHub' repo + the clone the app publishes from, with a legacy
    front page (no slug) and another walk's page already live."""
    def __init__(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="stagec_"))
        self.remote = self.tmp / "remote.git"
        self.clone = self.tmp / "clone"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.remote)], check=True)
        subprocess.run(["git", "clone", "-q", str(self.remote), str(self.clone)], check=True, capture_output=True)
        sh(self.clone, "checkout", "-q", "-B", "main")
        for k, v in (("user.name", "Test"), ("user.email", "test@example.test"), ("commit.gpgsign", "false")):
            sh(self.clone, "config", k, v)
        (self.clone / "README.md").write_text("site\n")
        for rel, slug in (("", None), ("w/other", "other")):
            d = self.clone / rel
            d.mkdir(parents=True, exist_ok=True)
            (d / "index.html").write_text(page_html(slug) if slug else "<html><script>window.DATA = {\"title\": \"legacy\"};</script></html>")
            (d / "preview.html").write_text("p")
            (d / "tree.html").write_text("t")
            (d / "photos").mkdir(exist_ok=True)
            (d / "photos" / "1.jpg").write_bytes(b"old")
        sh(self.clone, "add", "-A")
        sh(self.clone, "commit", "-q", "-m", "initial site")
        sh(self.clone, "push", "-q", "origin", "main")

    def head(self):
        return sh(self.clone, "rev-parse", "HEAD")

    def remote_head(self):
        return subprocess.run(["git", "--git-dir", str(self.remote), "rev-parse", "main"],
                              capture_output=True, text=True).stdout.strip()

    def remote_count(self):
        return int(subprocess.run(["git", "--git-dir", str(self.remote), "rev-list", "--count", "main"],
                                  capture_output=True, text=True).stdout.strip())

    def remote_file(self, rel):
        r = subprocess.run(["git", "--git-dir", str(self.remote), "show", f"main:{rel}"], capture_output=True)
        return r.stdout if r.returncode == 0 else None

    def remote_files(self, commit="main"):
        out = subprocess.run(["git", "--git-dir", str(self.remote), "ls-tree", "-r", "--name-only", commit],
                             capture_output=True, text=True).stdout
        return set(out.split())

    def clean(self):
        st = sh(self.clone, "status", "--porcelain")
        wts = sh(self.clone, "worktree", "list").splitlines()
        return st == "" and len(wts) == 1

    def close(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def clean_jpeg(path):
    Image.new("RGB", (40, 30), (40, 120, 40)).save(path, "JPEG")


def gps_jpeg(path):
    im = Image.new("RGB", (40, 30), (40, 120, 40))
    ex = Image.Exif()
    ex[0x010F] = "PhoneMaker"                                      # Make
    gps = ex.get_ifd(0x8825)
    gps[1], gps[2], gps[3], gps[4] = "N", (47.0, 42.0, 0.0), "E", (7.0, 50.0, 0.0)
    im.save(path, "JPEG", exif=ex.tobytes())


def good_plan(blockers=(), warnings=()):
    return {"ok": True, "buildable": not blockers, "blockers": list(blockers), "warnings": list(warnings),
            "public_species": [{"id": 1, "scientific_name": "Rumex acetosa", "en": "Sorrel", "badge": "edible"},
                               {"id": 2, "scientific_name": "Urtica dioica", "en": "Nettle", "badge": "caution"}],
            "stops": [{"label": "1"}, {"label": "2"}], "images_planned": 4,
            "recipes": {"included": [{"recipe_id": 7, "species_id": 1, "dish": "Sorrel soup"}], "excluded": []},
            "caution": [{"scientific_name": "Urtica dioica", "recipes_withheld": [9]}],
            "ai_agreed_obs": [{"obs_id": 55, "species_id": 3, "name": "Conium maculatum", "stop": "2",
                               "toxicity_severity": "deadly", "hazard": bool(blockers), "shown": False}]}


class Fakes:
    """Replace the export (plan + build) and the live-site fetch."""
    def __init__(self, site, plan=None, photo=clean_jpeg, impressum="https://x.test/impressum"):
        self.site, self.plan, self.photo, self.impressum = site, plan or good_plan(), photo, impressum
        self.builds = 0

    async def run_plan(self, pub):
        return json.loads(json.dumps(self.plan))

    async def run_build(self, pub, out):
        self.builds += 1
        for d in xp.page_dirs(Path(out), pub.slug, bool(pub.is_default)):
            (d / "photos").mkdir(parents=True, exist_ok=True)
            (d / "index.html").write_text(page_html(pub.slug, title=f"build {self.builds}", impressum=self.impressum))
            (d / "preview.html").write_text(f"preview {pub.slug} {self.builds}")
            (d / "tree.html").write_text(f"tree {pub.slug}")
            self.photo(d / "photos" / "1.jpg")
            clean_jpeg(d / "photos" / "1_t.jpg")

    async def fetch_url(self, url):
        rel = url.split("?")[0][len(SITE):]
        rel = rel + "index.html" if rel == "" or rel.endswith("/") else rel
        body = self.site.remote_file(rel)
        return (404, b"") if body is None else (200, body)

    def patch(self):
        return _Patch((xp, "run_plan", self.run_plan), (xp, "run_build", self.run_build),
                      (xp, "fetch_url", self.fetch_url), (xp, "site_url", lambda: SITE),
                      (xp, "CLONE", self.site.clone), (xp, "LIVE_POLL_S", 0), (xp, "LIVE_TIMEOUT_S", 2))


def _env(is_default=False, status="draft", slug="sunny-walk"):
    env = Env()
    _job_queue(env)
    _add(env, [SavedWalk(id=5, name="Morning sunshine", distance_m=7600, duration_min=93),
               ExperiencePublication(id=1, saved_walk_id=5, slug=slug, is_default=is_default, status=status,
                                     created_at=datetime(2026, 10, 22), updated_at=datetime(2026, 10, 22))])
    return env


def _pub(env):
    return env.q("SELECT status, published_commit, published_at IS NOT NULL, unpublished_at IS NOT NULL, "
                 "is_default FROM experience_publications WHERE id = 1")[0]


def _foragingid_git():
    return (subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout,
            subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout)


def _publish(env, fakes, confirm=True, kind="publish"):
    with _curator_device(env), fakes.patch():
        c = _app_client(env, CURATOR)
        r = c.post(f"/api/experience/publications/1/{kind}", json={"confirm": confirm})
        if r.status_code != 200:
            return r, None
        return r, xp.job_status(r.json()["job_id"])


def _done(env, site):
    main.app.dependency_overrides.clear()
    env.close()
    site.close()


# ══ refused / stopped: nothing committed ═════════════════════════════════════

def test_unconfirmed_hazard_blocks_and_nothing_is_committed():
    site, env = Site(), _env()
    try:
        before = (site.head(), site.remote_head(), site.remote_count())
        f = Fakes(site, plan=good_plan(blockers=["hazard at stop 2 not human-confirmed: Conium maculatum (obs 55)"]))
        r, job = _publish(env, f)
        assert r.status_code == 200 and job["status"] == "stopped" and job["stop_kind"] == "blocked", job
        assert "Conium maculatum" in job["message"] and f.builds == 0
        assert [s["state"] for s in job["steps"]][:3] == ["ok", "failed", "pending"]
        assert (site.head(), site.remote_head(), site.remote_count()) == before and site.clean()
        assert _pub(env)[0] == "draft"
        # A placeholder (Impressum not set) blocks the same way.
        _, job = _publish(env, Fakes(site, plan=good_plan(warnings=["impressum_url is a PLACEHOLDER — …"])))
        assert job["stop_kind"] == "blocked" and "Placeholder" in job["message"]
        assert site.remote_count() == before[2] and site.clean()
    finally:
        _done(env, site)


def test_failed_exif_check_stops_before_commit():
    site, env = Site(), _env()
    try:
        before = (site.head(), site.remote_count())
        r, job = _publish(env, Fakes(site, photo=gps_jpeg))
        assert job["status"] == "stopped" and job["stop_kind"] == "check", job
        assert "1.jpg" in job["message"] and "nothing was pushed" in job["message"]
        assert (site.head(), site.remote_count()) == before and site.clean() and _pub(env)[0] == "draft"
        # A page whose Impressum is not set fails the page check too.
        _, job = _publish(env, Fakes(site, impressum=None))
        assert job["stop_kind"] == "check" and "impressum_url" in job["message"]
        assert site.remote_count() == before[1] and site.clean()
    finally:
        _done(env, site)


def test_unticked_confirm_is_refused():
    site, env = Site(), _env()
    try:
        before = site.remote_count()
        r, job = _publish(env, Fakes(site), confirm=False)
        assert r.status_code == 400 and job is None and "Tick" in r.json()["detail"]
        r, _ = _publish(env, Fakes(site), confirm=False, kind="unpublish")
        assert r.status_code == 400
        assert site.remote_count() == before and site.clean() and _pub(env)[0] == "draft"
        js = _src("frontend/static/js/walk-publish.js")
        assert 'id="wpub-go" class="wpub-btn wpub-primary" disabled' in js        # button starts disabled
        assert "if (!tick || !tick.checked) return;" in js
        assert not re.search(r"(?<![\w.])(confirm|alert|prompt)\(", js)          # no browser dialogs
    finally:
        _done(env, site)


# ══ success ═══════════════════════════════════════════════════════════════════

def test_publish_makes_one_site_commit_and_none_in_foragingid():
    site, env = Site(), _env()
    try:
        fid_before = _foragingid_git()
        n = site.remote_count()
        r, job = _publish(env, Fakes(site))
        assert job["status"] == "done", job
        assert [s["state"] for s in job["steps"]] == ["ok"] * 8, job["steps"]
        assert site.remote_count() == n + 1 and site.head() == site.remote_head() and site.clean()
        changed = sh(site.clone, "show", "--name-only", "--format=", "HEAD").split()
        assert changed and all(p.startswith("w/sunny-walk/") for p in changed), changed
        assert site.remote_file("index.html").startswith(b"<html><script>window.DATA = {\"title\": \"legacy\"")
        assert site.remote_file("w/other/index.html") is not None                  # other walks untouched
        status, commit, published, unpublished, is_def = _pub(env)
        assert (status, commit, published, unpublished) == ("published", site.remote_head(), 1, 0)
        assert job["result"]["live"]["ok"] and job["result"]["publication"]["published_commit"] == commit
        snap = json.loads(env.q("SELECT public_species_json FROM experience_publications WHERE id = 1")[0][0])
        assert [s["id"] for s in snap["species"]] == [1, 2] and snap["is_default"] is False
        assert _foragingid_git() == fid_before                                     # no commit in ForagingID
        # Republishing an identical build changes nothing: no new commit, nothing pushed.
        _, job = _publish(env, Fakes(site))
        assert job["status"] == "done", job
        assert site.remote_count() == n + 1 and site.clean()
        assert {s["key"]: s["detail"] for s in job["steps"]}["push"].endswith("nothing to push")
    finally:
        _done(env, site)


def test_default_publish_replaces_the_front_page_and_mirror():
    site, env = Site(), _env(is_default=True)
    try:
        n = site.remote_count()
        _, job = _publish(env, Fakes(site))
        assert job["status"] == "done", job
        assert site.remote_count() == n + 1
        root, mirror = site.remote_file("index.html"), site.remote_file("w/sunny-walk/index.html")
        assert root == mirror and b'"slug": "sunny-walk"' in root
        assert site.remote_file("README.md") == b"site\n" and site.remote_file("w/other/index.html") is not None
        assert set(job["result"]["live"]["detail"]) == {SITE, SITE + "preview.html", SITE + "tree.html",
                                                         SITE + "w/sunny-walk/", SITE + "w/sunny-walk/preview.html",
                                                         SITE + "w/sunny-walk/tree.html"}
    finally:
        _done(env, site)


# ══ remote moved / offline ════════════════════════════════════════════════════

def test_remote_moved_on_stops_without_force_push():
    site, env = Site(), _env()
    try:
        other = site.tmp / "other"
        subprocess.run(["git", "clone", "-q", str(site.remote), str(other)], check=True, capture_output=True)
        (other / "README.md").write_text("edited on GitHub\n")
        sh(other, "commit", "-qam", "edited elsewhere")
        sh(other, "push", "-q", "origin", "HEAD:main")
        moved, mine = site.remote_head(), site.head()
        r, job = _publish(env, Fakes(site))
        assert job["status"] == "stopped" and job["stop_kind"] == "remote_moved", job
        assert "git pull --ff-only" in job["message"] and "Nothing was" in job["message"]
        assert site.remote_head() == moved and site.head() == mine and site.clean()   # nothing overwritten
        assert _pub(env)[0] == "draft"
        # Push-time race: GitHub refuses a non-fast-forward → reported as moved, never forced.
        assert xp._classify(" ! [rejected]        HEAD -> main (fetch first)") == "remote_moved"
        src = Path(xp.__file__).read_text()
        calls = re.findall(r"git(?:_ok)?\(([^)]*)\)", src)                    # every git(...) call
        for bad in ('"--force"', '"-f"', '"reset"', '"rebase"', '"--force-with-lease"'):
            assert not any(bad in c for c in calls), bad
    finally:
        _done(env, site)


def test_offline_stops_before_push_and_leaves_the_clone_clean():
    site, env = Site(), _env()
    try:
        sh(site.clone, "remote", "set-url", "origin", "https://foraging-experience.invalid/x.git")
        head, n = site.head(), site.remote_count()
        r, job = _publish(env, Fakes(site))
        assert job["status"] == "stopped" and job["stop_kind"] == "offline", job
        assert "No network" in job["message"] and job["steps"][0]["state"] == "failed"
        assert all(s["state"] == "pending" for s in job["steps"][1:])
        assert site.head() == head and site.remote_count() == n and site.clean() and _pub(env)[0] == "draft"
        assert xp._classify("fatal: unable to access 'https://github.com/x/': Could not resolve host: github.com") == "offline"
        assert xp._classify("remote: Invalid username or password.\nfatal: Authentication failed") == "login"
        assert "the app stores no token" in xp.LOGIN_FIX
    finally:
        _done(env, site)


def test_offline_during_push_leaves_no_stray_commit():
    site, env = Site(), _env()
    try:
        head, n = site.head(), site.remote_count()
        real_git = xp.git

        async def git(cwd, *args, timeout=xp.GIT_TIMEOUT_S):
            if args[:1] == ("push",) and "--dry-run" not in args:
                return 128, "", "fatal: unable to access: Could not resolve host: github.com"
            return await real_git(cwd, *args, timeout=timeout)
        with _Patch((xp, "git", git)):
            r, job = _publish(env, Fakes(site))
        assert job["stop_kind"] == "offline", job
        states = {s["key"]: s["state"] for s in job["steps"]}
        assert states["commit"] == "ok" and states["push"] == "failed" and states["record"] == "pending"
        assert site.head() == head and site.remote_count() == n and site.clean()   # main never moved
        assert sh(site.clone, "branch", "--list") == "* main" and _pub(env)[0] == "draft"
    finally:
        _done(env, site)


# ══ unpublish ═════════════════════════════════════════════════════════════════

def test_unpublish_removes_the_page_in_one_commit_and_keeps_the_walk():
    site, env = Site(), _env()
    try:
        _, job = _publish(env, Fakes(site))
        assert job["status"] == "done"
        n = site.remote_count()
        _, job = _publish(env, Fakes(site), kind="unpublish")
        assert job["status"] == "done", job
        assert site.remote_count() == n + 1 and site.clean()
        files = site.remote_files()
        assert not any(f.startswith("w/sunny-walk/") for f in files)
        assert {"README.md", "index.html", "w/other/index.html"} <= files          # front page wasn't this walk's
        assert env.q("SELECT id, name FROM saved_walks WHERE id = 5") == [(5, "Morning sunshine")]
        status, _, _, unpublished, is_def = _pub(env)
        assert status == "unpublished" and unpublished == 1 and not is_def
        assert job["result"]["live"]["ok"] and "git history" in job["result"]["message"]
    finally:
        _done(env, site)


def test_unpublish_of_the_default_also_removes_the_front_page():
    site, env = Site(), _env(is_default=True)
    try:
        _publish(env, Fakes(site))
        n = site.remote_count()
        _, job = _publish(env, Fakes(site), kind="unpublish")
        assert job["status"] == "done", job
        files = site.remote_files()
        assert site.remote_count() == n + 1
        assert not ({"index.html", "preview.html", "tree.html"} & files) and not any(f.startswith("photos/") for f in files)
        assert "README.md" in files and "w/other/index.html" in files
        assert env.q("SELECT COUNT(*) FROM saved_walks WHERE id = 5")[0][0] == 1
    finally:
        _done(env, site)


# ══ guests ════════════════════════════════════════════════════════════════════

def test_guests_never_reach_the_publish_endpoints_or_block():
    site, env = Site(), _env()
    try:
        n = site.remote_count()
        with _guest_device(env), Fakes(site).patch():
            c = _app_client(env, None)
            for method, url in (("GET", "/api/experience/walks/5/panel"), ("GET", "/api/experience/jobs/abc"),
                                ("POST", "/api/experience/publications/1/plan"),
                                ("POST", "/api/experience/publications/1/publish"),
                                ("POST", "/api/experience/publications/1/unpublish"),
                                ("POST", "/api/experience/publications"),
                                ("PATCH", "/api/experience/publications/1")):
                r = c.request(method, url, json={"confirm": True})
                assert r.status_code == 403, (method, url, r.status_code)
        for p in ("/api/experience/publications/1/publish", "/api/experience/publications/1/unpublish"):
            assert not ga.guest_api_allowed("POST", p)
        assert site.remote_count() == n and _pub(env)[0] == "draft"
        idx = _src("frontend/index.html")
        assert '<div id="walk-publish" data-guest-hide style="display:none"></div>' in idx
        js = _src("frontend/static/js/walk-publish.js")
        assert "if (!walkId || isGuest())" in js and "e.status === 403" in js
    finally:
        _done(env, site)


# ══ pieces ════════════════════════════════════════════════════════════════════

def test_panel_and_plan_changes():
    site, env = Site(), _env()
    try:
        with _curator_device(env), Fakes(site).patch():
            c = _app_client(env, CURATOR)
            d = c.get("/api/experience/walks/5/panel").json()
            assert d["publication"]["slug"] == "sunny-walk" and d["publication"]["url"] == SITE + "w/sunny-walk/"
            plan = c.post("/api/experience/publications/1/plan").json()
            assert plan["changes"]["first_publish"] is True and plan["problems"] == []
            assert plan["summary"] == {"species": 2, "stops": 2, "photo_files": 4, "recipe_count": 1}
            assert plan["changes"]["withheld"] == [{"species": "Urtica dioica", "recipe_ids": [9]}]
        before = {"species": [{"id": 1, "sci": "Rumex acetosa", "en": "Sorrel", "badge": {"kind": "caution"}},
                              {"id": 4, "sci": "Allium ursinum", "en": "Ramsons", "badge": {"kind": "edible"}}],
                  "recipes": [{"recipe_id": 8, "species_id": 4, "dish": "Ramsons pesto"}]}
        ch = xp.plan_changes(good_plan(), before, "w/sunny-walk/index.html")
        assert ch["added"] == ["Nettle"] and ch["removed"] == ["Ramsons"]
        assert ch["badge_changes"] == [{"species": "Sorrel", "from": "caution", "to": "edible"}]
        assert ch["recipes_added"] == ["Sorrel soup"] and ch["recipes_removed"] == ["Ramsons pesto"]
        assert xp.plan_problems({"ok": False, "build_error": "x"}) == ["Build error: x"]
    finally:
        _done(env, site)


def test_overrides_file_copied_into_a_new_publication():
    env = Env()
    try:
        _add(env, [SavedWalk(id=4, name="Rümmelsbühl foray")])
        with _curator_device(env):
            c = _app_client(env, CURATOR)
            files = c.get("/api/experience/walks/4/panel").json()["override_files"]
            assert {"file": "walk4.json", "slug": "ruemmelsbuehl", "title_en": "Foraging Experience — Gresgen"} in files
            r = c.post("/api/experience/publications", json={"saved_walk_id": 4, "slug": "ruemmelsbuehl",
                                                             "overrides_file": "walk4.json"})
            assert r.status_code == 200, r.text
            ov = r.json()["overrides"]
            assert ov["title_en"] == "Foraging Experience — Gresgen" and "slug" not in ov and "_note" not in ov
            assert c.post("/api/experience/publications", json={"saved_walk_id": 4, "slug": "x",
                                                                "overrides_file": "../config.json"}).status_code == 400
    finally:
        main.app.dependency_overrides.clear()
        env.close()


def test_caution_rule_is_one_helper_in_the_export():
    assert gates.caution_warning_shown({"look_alike": "x"}) and gates.caution_warning_shown({"caution": "x"})
    assert not gates.caution_warning_shown({"preparation": "x"}) and not gates.caution_warning_shown({})
    src = _src("scripts/experience_export/export.py")
    assert src.count("gates.caution_warning_shown(") == 2 and '"caution" in pub' not in src \
        and '"caution" not in pub' not in src
    assert '"ai_agreed_obs": ai_agreed_obs' in src and "gates.obs_unconfirmed_hazard(o, sp_row)" in src


def test_jobs_popup_labels_and_no_token_storage():
    w = _src("frontend/static/js/job-status-widget.js")
    assert "'experience_publish':        'Publish walk'" in w and "'experience_unpublish':      'Unpublish walk'" in w
    src = Path(xp.__file__).read_text()
    for bad in ("token =", "TOKEN", "x-access-token", "https://melvinoj:", "ghp_", "github_pat",
                "credential approve", "credential.helper=store", "set_setting"):
        assert bad not in src, bad
    assert 'GIT_TERMINAL_PROMPT="0"' in src


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
