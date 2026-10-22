"""
experience_publish.py — Stage C: publish / unpublish a saved walk's experience
page to the foraging-experience site (Melvin, 22 Oct 2026). Recon:
RECON_stage_c_publish_22oct.md.

Everything git happens in the foraging-experience clone (CLONE) — never in the
ForagingID repo, whose single commit point (End Session) is unchanged.

Publish, in order; nothing is pushed until the push step:
  1. site      — the clone is on main and clean; `git fetch`; the remote has not
                 moved on (if it has: stop and report, never pull/rebase/reset);
                 the stored GitHub login works (`git push --dry-run`, sends nothing).
                 No network → stops here.
  2. plan      — export.py --plan-json: buildable, no blocker (rule 7), no
                 placeholder warning.
  3. build     — export.py into a temp folder (the gates run inside the build).
  4. checks    — every photo: no EXIF / GPS / XMP / IPTC (exiftool + PIL);
                 every page: no unfilled {{X}}, Impressum + Datenschutz set.
  5. commit    — in a temporary detached worktree of the clone: only this
                 walk's files change; one commit.
  6. push      — normal `git push origin HEAD:refs/heads/main` (never --force).
                 Rejected → the remote moved on: stop and report. Then the clone's
                 main fast-forwards to the pushed commit (--ff-only).
  7. record    — experience_publications: status, published_at, commit; read
                 back by id.
  8. live      — the page files on the site are HTTP 200 and byte-identical to
                 the build (cache-busted with ?v=<commit>; GitHub Pages takes a
                 minute or two).

A run that stops before the push leaves the clone exactly as it was: main and
the working tree are untouched (the commit is made in the temporary worktree,
which is deleted). No token is stored by the app: git uses the macOS keychain
login it already has; prompting is disabled so a bad login fails, never hangs.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import sys
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from app import database
from app.models.experience import ExperiencePublication
from app.models.walk import SavedWalk
from app.services.background_processes import bp_finish, bp_patch, bp_progress, bp_start

log = logging.getLogger(__name__)

REPO = Path(__file__).resolve().parents[2]
EXPORT_DIR = REPO / "scripts" / "experience_export"
EXPORT_SCRIPT = EXPORT_DIR / "export.py"
EXPORT_CONFIG = EXPORT_DIR / "config.json"
OVERRIDES_DIR = EXPORT_DIR / "overrides"

CLONE = Path.home() / "foraging-experience"
REMOTE = "origin"
BRANCH = "main"
OWNED_FILES = ("index.html", "preview.html", "tree.html")    # export.py OWNED_FILES

PLAN_TIMEOUT_S = 180
BUILD_TIMEOUT_S = 900
GIT_TIMEOUT_S = 90
LIVE_TIMEOUT_S = 300
LIVE_POLL_S = 10

PUBLISH_STEPS = (("site", "Check the site copy and GitHub login"), ("plan", "Plan"),
                 ("build", "Build"), ("checks", "Photo and page checks"), ("commit", "Commit"),
                 ("push", "Push"), ("record", "Record"), ("live", "Check the live page"))
UNPUBLISH_STEPS = (("site", "Check the site copy and GitHub login"), ("commit", "Commit"),
                   ("push", "Push"), ("record", "Record"), ("live", "Check the page is gone"))

_OFFLINE = ("could not resolve host", "failed to connect", "couldn't connect", "network is unreachable",
            "connection timed out", "operation timed out", "connection refused", "no route to host",
            "temporary failure in name resolution", "timed out after")
_AUTH = ("authentication failed", "could not read username", "could not read password",
         "invalid username or password", "permission to", "403", "401", "denied")
_REJECTED = ("[rejected]", "non-fast-forward", "fetch first", "failed to push some refs")

LOGIN_FIX = ("To fix it: open Terminal, run  cd ~/foraging-experience && git push  and sign in when asked "
             "(a GitHub token with write access to melvinoj/foraging-experience). macOS Keychain then "
             "remembers it — the app stores no token.")


class PublishStop(Exception):
    """A planned stop: nothing (more) is pushed. kind: offline | login |
    remote_moved | blocked | check | build | site | busy."""
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


# ── Jobs (in memory: the panel polls these; the Jobs pop-up reads background_processes) ──

_JOBS: dict[str, dict] = {}
_ACTIVE: Optional[str] = None          # one publish / unpublish at a time
_REPAIRING = False                     # startup repair of an interrupted run in progress


def job_status(job_id: str) -> Optional[dict]:
    return _JOBS.get(job_id)


def active_job() -> Optional[dict]:
    return _JOBS.get(_ACTIVE) if _ACTIVE else None


def _new_job(kind: str, pub_id: int, steps) -> dict:
    global _ACTIVE
    if _ACTIVE and _JOBS.get(_ACTIVE, {}).get("status") == "running":
        raise PublishStop("busy", "Another publish or unpublish is running — wait for it to finish.")
    if _REPAIRING:
        raise PublishStop("busy", "Checking an interrupted publish from before the restart — try again in a minute.")
    job_id = uuid.uuid4().hex[:12]
    job = {"job_id": job_id, "kind": kind, "publication_id": pub_id, "status": "running",
           "steps": [{"key": k, "label": l, "state": "pending", "detail": ""} for k, l in steps],
           "message": "", "stop_kind": None, "result": {}, "process_id": None,
           "started_at": datetime.utcnow().isoformat()}
    _JOBS[job_id] = job
    _ACTIVE = job_id
    return job


def _step(job: dict, key: str, state: str, detail: str = "") -> None:
    for s in job["steps"]:
        if s["key"] == key:
            s["state"] = state
            if detail:
                s["detail"] = detail


# ── git (clone only) ─────────────────────────────────────────────────────────

def _git_env() -> dict:
    env = os.environ.copy()
    # Never prompt: a missing / rejected login fails at once instead of hanging
    # the job. The keychain helper (credential.helper=osxkeychain) still runs.
    env.update(GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="/usr/bin/false", SSH_ASKPASS="/usr/bin/false",
               GCM_INTERACTIVE="never", LC_ALL="C")
    return env


async def _run(cmd: list, cwd: Path, timeout: int, env: Optional[dict] = None) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(*cmd, cwd=str(cwd), env=env,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return 124, "", f"timed out after {timeout}s"
    return proc.returncode, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")


async def git(cwd: Path, *args: str, timeout: int = GIT_TIMEOUT_S) -> tuple[int, str, str]:
    return await _run(["git", *args], cwd, timeout, _git_env())


async def _git_ok(cwd: Path, *args: str, what: str, timeout: int = GIT_TIMEOUT_S) -> str:
    rc, out, err = await git(cwd, *args, timeout=timeout)
    if rc != 0:
        raise PublishStop("site", f"{what} failed: {(err or out).strip()[-400:]}")
    return out.strip()


def _classify(err: str) -> Optional[str]:
    e = err.lower()
    if any(m in e for m in _OFFLINE):
        return "offline"
    if any(m in e for m in _REJECTED):
        return "remote_moved"
    if any(m in e for m in _AUTH):
        return "login"
    return None


def _network_stop(err: str, doing: str) -> PublishStop:
    kind = _classify(err) or "site"
    tail = err.strip()[-300:]
    if kind == "offline":
        return PublishStop("offline", f"No network — couldn't reach GitHub while {doing}. Nothing was pushed. ({tail})")
    if kind == "login":
        return PublishStop("login", f"GitHub didn't accept the stored login while {doing}. Nothing was pushed. "
                                    f"{LOGIN_FIX} ({tail})")
    if kind == "remote_moved":
        return PublishStop("remote_moved", _moved_text(f"GitHub refused the push ({tail})"))
    return PublishStop("site", f"git failed while {doing}: {tail}")


def _moved_text(why: str) -> str:
    return (f"The site on GitHub has changed since this Mac's copy was last updated — {why}. Nothing was "
            "pushed and nothing was overwritten. Bring the copy up to date in Terminal ("
            "cd ~/foraging-experience && git pull --ff-only), then publish again.")


async def check_site(clone: Optional[Path] = None) -> dict:
    """Step 1 for publish and unpublish. Raises PublishStop; returns {head}."""
    clone = clone or CLONE
    if not (clone / ".git").exists():
        raise PublishStop("site", f"The site copy {clone} is missing or is not a git clone.")
    branch = await _git_ok(clone, "symbolic-ref", "--short", "HEAD", what="Reading the branch")
    if branch != BRANCH:
        raise PublishStop("site", f"The site copy is on branch {branch!r}, not {BRANCH!r} — switch back first.")
    dirty = await _git_ok(clone, "status", "--porcelain", what="git status")
    if dirty:
        raise PublishStop("site", "The site copy has uncommitted changes — nothing was touched. "
                                  f"Check ~/foraging-experience: {dirty.splitlines()[:5]}")
    rc, out, err = await git(clone, "fetch", REMOTE, BRANCH)
    if rc != 0:
        raise _network_stop(err or out, "fetching the site")
    head = await _git_ok(clone, "rev-parse", "HEAD", what="rev-parse HEAD")
    remote = await _git_ok(clone, "rev-parse", f"{REMOTE}/{BRANCH}", what="rev-parse remote")
    if head != remote:
        behind = (await git(clone, "merge-base", "--is-ancestor", head, remote))[0] == 0
        ahead = (await git(clone, "merge-base", "--is-ancestor", remote, head))[0] == 0
        if behind:
            raise PublishStop("remote_moved", _moved_text(f"GitHub is at {remote[:7]}, this copy at {head[:7]}"))
        if ahead:
            raise PublishStop("site", f"The site copy has commits that aren't on GitHub ({remote[:7]}..{head[:7]}). "
                                      "Nothing was pushed — sort these out in Terminal first.")
        raise PublishStop("remote_moved", _moved_text(f"the copy and GitHub have diverged ({head[:7]} vs {remote[:7]})"))
    # Login check: an authenticated push request that sends nothing.
    rc, out, err = await git(clone, "push", "--dry-run", "--porcelain", REMOTE, f"HEAD:refs/heads/{BRANCH}")
    if rc != 0:
        raise _network_stop(err or out, "checking the GitHub login")
    return {"head": head}


# ── export (plan / build) — subprocess, as app/api/experience.py did ──────────

def site_url() -> str:
    return json.loads(EXPORT_CONFIG.read_text(encoding="utf-8"))["site_url"].rstrip("/") + "/"


def _db_file() -> str:
    from sqlalchemy.engine import make_url
    from app.config import settings
    db = make_url(settings.database_url).database
    return str((REPO / db).resolve()) if not Path(db).is_absolute() else db


def _overrides_for(pub) -> dict:
    ov = json.loads(pub.overrides_json) if pub.overrides_json else {}
    ov["slug"] = pub.slug
    return ov


async def _export(pub, extra: list, timeout: int) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory(prefix="exp_ov_") as tmp:
        ov_path = Path(tmp) / "overrides.json"
        ov_path.write_text(json.dumps(_overrides_for(pub), ensure_ascii=False), encoding="utf-8")
        cmd = [sys.executable, str(EXPORT_SCRIPT), "--walk-id", str(pub.saved_walk_id),
               "--overrides", str(ov_path), "--db", _db_file(), *extra]
        if pub.is_default:
            cmd.append("--default")
        return await _run(cmd, REPO, timeout)


async def run_plan(pub) -> dict:
    """export.py --plan-json for this publication (no files written)."""
    rc, out, err = await _export(pub, ["--plan-json"], PLAN_TIMEOUT_S)
    if rc == 124:
        raise PublishStop("build", f"The export plan timed out after {PLAN_TIMEOUT_S}s.")
    try:
        plan = json.loads(out)
    except ValueError:
        raise PublishStop("build", "The export plan failed: " + err.strip()[-500:])
    plan["returncode"] = rc
    return plan


async def run_build(pub, out_dir: Path) -> None:
    """The full export into out_dir (a temp folder, never the clone)."""
    rc, out, err = await _export(pub, ["--out", str(out_dir)], BUILD_TIMEOUT_S)
    if rc != 0:
        msg = next((l for l in reversed((err or out).splitlines()) if "BUILD FAILED" in l), (err or out).strip()[-500:])
        raise PublishStop("build", f"The build failed — nothing was pushed. {msg}")


def plan_problems(plan: dict) -> list[str]:
    """Why this plan may not be published (empty list = may go ahead)."""
    if not plan.get("ok"):
        return [f"Build error: {plan.get('build_error')}"]
    probs = [f"Blocker: {b}" for b in plan.get("blockers", [])]
    if not plan.get("buildable", False) and not probs:
        probs.append("The plan is not buildable.")
    probs += [f"Placeholder: {w}" for w in plan.get("warnings", []) if "PLACEHOLDER" in w]
    return probs


# ── checks on the built files ────────────────────────────────────────────────

def page_dirs(root: Path, slug: str, is_default: bool) -> list[Path]:
    return [root, root / "w" / slug] if is_default else [root / "w" / slug]


async def check_photos(paths: list[Path]) -> list[str]:
    """Every photo: no EXIF / GPS / XMP / IPTC at all (exiftool, independent of
    PIL), and PIL sees no EXIF either. Fails closed if exiftool is missing."""
    if not paths:
        return []
    exiftool = shutil.which("exiftool")
    if not exiftool:
        return ["exiftool is not installed — the metadata check could not run"]
    bad = []
    for i in range(0, len(paths), 200):
        chunk = paths[i:i + 200]
        rc, out, err = await _run([exiftool, "-j", "-a", "-G1", "-GPS:all", "-EXIF:all", "-XMP:all",
                                   "-IPTC:all", *map(str, chunk)], REPO, 120)
        try:
            rows = json.loads(out) if out.strip() else []
        except ValueError:
            return [f"exiftool output could not be read: {err.strip()[-200:]}"]
        for r in rows:
            tags = [k for k in r if k != "SourceFile"]
            if tags:
                bad.append(f"{Path(r['SourceFile']).name}: {', '.join(tags[:4])}")
        if rc not in (0, 1) and not rows:
            return [f"exiftool failed: {err.strip()[-200:]}"]
    from PIL import Image
    for p in paths:
        with Image.open(p) as im:
            if len(im.getexif()):
                bad.append(f"{p.name}: EXIF (PIL)")
    return bad


def page_data(html: str) -> Optional[dict]:
    """window.DATA from an exported index.html (None if absent)."""
    i = html.find("window.DATA = ")
    if i < 0:
        return None
    try:
        return json.JSONDecoder().raw_decode(html, i + len("window.DATA = "))[0]
    except ValueError:
        return None


def check_pages(dirs: list[Path]) -> list[str]:
    bad = []
    for d in dirs:
        for name in OWNED_FILES:
            f = d / name
            if not f.is_file():
                bad.append(f"{d.name}/{name} missing")
                continue
            if re.search(r"\{\{[A-Z0-9_]+\}\}", f.read_text(encoding="utf-8")):
                bad.append(f"{name}: unfilled {{{{…}}}} placeholder")
        idx = d / "index.html"
        data = page_data(idx.read_text(encoding="utf-8")) if idx.is_file() else None
        if idx.is_file() and data is None:
            bad.append("index.html: page data not found")
        elif data is not None:
            for k in ("impressum_url", "datenschutz_url", "contact_url"):
                if not data.get(k):
                    bad.append(f"index.html: {k} is a placeholder (not set)")
        if not (d / "photos").is_dir():
            bad.append("photos/ missing")
    return bad


# ── what changed since the page now on the site ──────────────────────────────

async def site_page(slug: str, is_default: bool, clone: Optional[Path] = None) -> tuple[Optional[dict], str]:
    """(window.DATA, where) of this publication's page as committed in the
    clone (local, no network). The front page counts only if it is this
    publication's (its DATA slug), or a legacy page without a slug when this
    publication is the default."""
    clone = clone or CLONE
    for rel in [f"w/{slug}/index.html"] + (["index.html"] if is_default else []):
        rc, out, _ = await git(clone, "show", f"HEAD:{rel}")
        if rc == 0:
            d = page_data(out)
            if d is not None and d.get("slug", slug) == slug:
                return d, rel
    return None, ""


async def front_page_slug(clone: Optional[Path] = None) -> tuple[bool, Optional[str]]:
    """(exists, slug) of the site's front page in the clone (slug None = legacy page)."""
    rc, out, _ = await git(clone or CLONE, "show", "HEAD:index.html")
    if rc != 0:
        return False, None
    d = page_data(out) or {}
    return True, d.get("slug")


def plan_changes(plan: dict, before: Optional[dict], where: str) -> dict:
    """Added / removed species, badge changes, recipes in/out vs the page on the
    site; plus the recipes this plan withholds (caution without a warning)."""
    withheld = [{"species": c["scientific_name"], "recipe_ids": c["recipes_withheld"]}
                for c in plan.get("caution", []) if c.get("recipes_withheld")]
    if not plan.get("ok"):
        return {"first_publish": before is None, "withheld": withheld}
    now_sp = {p["id"]: p for p in plan.get("public_species", [])}
    now_rec = {r["recipe_id"]: r for r in plan.get("recipes", {}).get("included", [])}
    if before is None:
        return {"first_publish": True, "where": "", "species_now": len(now_sp), "withheld": withheld}
    was_sp = {p["id"]: p for p in before.get("species", [])}
    was_rec = {r["recipe_id"]: r for r in before.get("recipes", [])}
    name = lambda p: p.get("en") or p.get("sci") or p.get("scientific_name")
    badge = lambda p: (p.get("badge") or {}).get("kind") if isinstance(p.get("badge"), dict) else p.get("badge")
    return {
        "first_publish": False, "where": where,
        "species_before": len(was_sp), "species_now": len(now_sp),
        "added": sorted(name(now_sp[i]) for i in set(now_sp) - set(was_sp)),
        "removed": sorted(name(was_sp[i]) for i in set(was_sp) - set(now_sp)),
        "badge_changes": sorted(({"species": name(now_sp[i]), "from": badge(was_sp[i]), "to": badge(now_sp[i])}
                                 for i in set(now_sp) & set(was_sp) if badge(now_sp[i]) != badge(was_sp[i])),
                                key=lambda c: c["species"] or ""),
        "recipes_added": sorted(now_rec[i]["dish"] for i in set(now_rec) - set(was_rec)),
        "recipes_removed": sorted(was_rec[i].get("dish", str(i)) for i in set(was_rec) - set(now_rec)),
        "withheld": withheld,
    }


# ── worktree commit + push ───────────────────────────────────────────────────

def _replace_page(src_dirs: list[Path], dst_dirs: list[Path]) -> None:
    for src, dst in zip(src_dirs, dst_dirs):
        dst.mkdir(parents=True, exist_ok=True)
        for name in OWNED_FILES:
            (dst / name).unlink(missing_ok=True)
            shutil.copy2(src / name, dst / name)
        if (dst / "photos").exists():
            shutil.rmtree(dst / "photos")
        shutil.copytree(src / "photos", dst / "photos")


def _remove_page(d: Path, root: bool) -> list[str]:
    """Remove a page's own files (OWNED_FILES + photos/) from d. For w/<slug>
    the folder goes; for the root only those files (README, w/ stay)."""
    gone = []
    if not root:
        if d.exists():
            shutil.rmtree(d)
            gone.append(d.name)
        return gone
    for name in OWNED_FILES:
        if (d / name).exists():
            (d / name).unlink()
            gone.append(name)
    if (d / "photos").exists():
        shutil.rmtree(d / "photos")
        gone.append("photos/")
    return gone


async def _commit_and_push(clone: Path, change: Callable[[Path], list[str]], message: str,
                           allowed: list[str], on_committed=None) -> Optional[str]:
    """Make the change in a temporary detached worktree, one commit, normal push.
    Returns the pushed commit, or None when nothing changed. Every changed path
    must lie under `allowed` (else nothing is pushed). On any stop the worktree
    is deleted: the clone's main and files never moved."""
    wt_parent = Path(tempfile.mkdtemp(prefix="exp_wt_"))
    wt = wt_parent / "site"
    try:
        await _git_ok(clone, "worktree", "add", "--detach", str(wt), "HEAD", what="Creating a work copy")
        changed_paths = change(wt)
        if not changed_paths:
            return None
        await _git_ok(wt, "add", "-A", what="git add")
        status = await _git_ok(wt, "status", "--porcelain", what="git status")
        if not status:
            return None
        stray = [l for l in status.splitlines()
                 if not any(l[3:].strip('"').startswith(a.rstrip("/")) for a in allowed)]
        if stray:
            raise PublishStop("check", f"Unexpected files would change: {stray[:5]} — nothing was pushed.")
        await _git_ok(wt, "commit", "-q", "-m", message, what="git commit")
        sha = await _git_ok(wt, "rev-parse", "HEAD", what="rev-parse")
        if on_committed is not None:
            await on_committed(sha)
        rc, out, err = await git(wt, "push", REMOTE, f"HEAD:refs/heads/{BRANCH}", timeout=GIT_TIMEOUT_S * 2)
        if rc != 0:
            raise _network_stop(err or out, "pushing")
        # Pushed: bring the clone's main up to it (a fast-forward only).
        rc, out, err = await git(clone, "merge", "--ff-only", "-q", sha)
        if rc != 0:
            log.warning("experience publish: pushed %s but the clone did not fast-forward: %s", sha, err)
        return sha
    finally:
        shutil.rmtree(wt_parent, ignore_errors=True)
        await git(clone, "worktree", "prune")


# ── live check ───────────────────────────────────────────────────────────────

async def fetch_url(url: str) -> tuple[int, bytes]:
    import httpx
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as c:
        r = await c.get(url, headers={"Cache-Control": "no-cache"})
        return r.status_code, r.content


async def wait_live(expect: dict[str, Optional[bytes]], sha: str, timeout: int = LIVE_TIMEOUT_S) -> dict:
    """Poll each URL (cache-busted) until it serves exactly the expected bytes
    (None = expect 404). {ok, pending:[url…], detail}."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    pending = dict(expect)
    last = {}
    while True:
        for url, want in list(pending.items()):
            try:
                code, body = await fetch_url(f"{url}?v={sha[:12]}")
            except Exception as e:
                last[url] = f"error {e}"
                continue
            last[url] = f"HTTP {code}"
            if (want is None and code == 404) or (want is not None and code == 200 and body == want):
                pending.pop(url)
        if not pending or loop.time() >= deadline:
            break
        await asyncio.sleep(LIVE_POLL_S)
    return {"ok": not pending, "pending": list(pending), "detail": {u: last.get(u) for u in expect}}


def _page_urls(slug: str, is_default: bool) -> list[tuple[str, str]]:
    """(url, relative dir) for each place the page is served."""
    base = site_url()
    out = [(f"{base}w/{slug}/", f"w/{slug}")]
    if is_default:
        out.insert(0, (base, ""))
    return out


# ── DB ───────────────────────────────────────────────────────────────────────

async def _load(pub_id: int):
    async with database.AsyncSessionLocal() as db:
        p = await db.get(ExperiencePublication, pub_id)
        w = await db.get(SavedWalk, p.saved_walk_id) if p is not None and p.saved_walk_id else None
        return p, w


async def _record(pub_id: int, **fields) -> dict:
    """Write the publication row, then read it back by id; raise if any field
    did not land."""
    async with database.AsyncSessionLocal() as db:
        p = await db.get(ExperiencePublication, pub_id)
        for k, v in fields.items():
            setattr(p, k, v)
        p.updated_at = datetime.utcnow()
        await db.commit()
    async with database.AsyncSessionLocal() as db:
        row = await db.get(ExperiencePublication, pub_id)
        wrong = {k: getattr(row, k) for k, v in fields.items() if getattr(row, k) != v}
        if wrong:
            raise PublishStop("site", f"publication {pub_id}: write did not persist {wrong}")
        return {"id": row.id, "slug": row.slug, "status": row.status, "is_default": bool(row.is_default),
                "published_at": row.published_at.isoformat() if row.published_at else None,
                "unpublished_at": row.unpublished_at.isoformat() if row.unpublished_at else None,
                "published_commit": row.published_commit}


# ── the two jobs ─────────────────────────────────────────────────────────────

def start_publish(pub_id: int) -> dict:
    return _new_job("publish", pub_id, PUBLISH_STEPS)


def start_unpublish(pub_id: int) -> dict:
    return _new_job("unpublish", pub_id, UNPUBLISH_STEPS)


async def _run_job(job: dict, body, label: str, n_steps: int) -> None:
    global _ACTIVE
    # The payload is what a restart needs to repair an interrupted run
    # (repair_interrupted): the publication, and — written before the push —
    # the commit and the snapshot to record.
    pid = await bp_start(f"experience_{job['kind']}", progress_total=n_steps, detail=label,
                         payload=json.dumps({"publication_id": job["publication_id"], "kind": job["kind"],
                                             "started_at": job["started_at"]}))
    job["process_id"] = pid
    done = 0

    async def progress(key: str, state: str, detail: str = ""):
        nonlocal done
        _step(job, key, state, detail)
        if state == "ok":
            done += 1
        await bp_progress(pid, done, n_steps, f"{label} — {detail or key}")

    try:
        job["result"] = await body(progress)
        job["status"] = "done"
        job["message"] = job["result"].get("message", "Done.")
        await bp_finish(pid, "complete", current=n_steps, total=n_steps)
    except PublishStop as e:
        running = next((s for s in job["steps"] if s["state"] == "running"), None)
        if running:
            _step(job, running["key"], "failed", e.message)
        job.update(status="stopped", message=e.message, stop_kind=e.kind)
        await bp_finish(pid, "failed", error=e.message)
    except Exception as e:                                    # unexpected: same clean stop
        log.exception("experience %s failed", job["kind"])
        running = next((s for s in job["steps"] if s["state"] == "running"), None)
        if running:
            _step(job, running["key"], "failed", str(e))
        job.update(status="failed", message=f"Unexpected error: {e}", stop_kind="error")
        await bp_finish(pid, "failed", error=str(e))
    finally:
        if _ACTIVE == job["job_id"]:
            _ACTIVE = None


async def run_publish(job: dict, clone: Optional[Path] = None) -> None:
    clone = clone or CLONE
    pub, walk = await _load(job["publication_id"])
    label = f"Publish walk {walk.id if walk else '?'} → {pub.slug if pub else '?'}"

    async def body(progress):
        if pub is None or walk is None:
            raise PublishStop("site", "This publication or its walk no longer exists.")
        await progress("site", "running")
        site = await check_site(clone)
        await progress("site", "ok", f"site at {site['head'][:7]}, login ok")

        await progress("plan", "running")
        plan = await run_plan(pub)
        probs = plan_problems(plan)
        if probs:
            raise PublishStop("blocked", "Not published: " + "; ".join(probs))
        await progress("plan", "ok", f"{len(plan['public_species'])} species, {len(plan['stops'])} stops, "
                                     f"{plan['images_planned']} photos")
        snapshot = {"is_default": bool(pub.is_default),
                    "species": [{"id": p["id"], "scientific_name": p["scientific_name"], "en": p["en"],
                                 "badge": p["badge"]} for p in plan["public_species"]],
                    "recipes": [{"recipe_id": r["recipe_id"], "species_id": r["species_id"], "dish": r["dish"]}
                                for r in plan["recipes"]["included"]]}
        with tempfile.TemporaryDirectory(prefix="exp_build_") as tmp:
            out = Path(tmp)
            await progress("build", "running")
            await run_build(pub, out)
            await progress("build", "ok")

            await progress("checks", "running")
            dirs = page_dirs(out, pub.slug, bool(pub.is_default))
            photos = sorted({p for d in dirs for p in (d / "photos").glob("*.jpg")}) if dirs else []
            bad = check_pages(dirs) + await check_photos(photos)
            if bad:
                raise PublishStop("check", "Checks failed — nothing was pushed: " + "; ".join(bad[:8])
                                  + (f" (+{len(bad) - 8} more)" if len(bad) > 8 else ""))
            await progress("checks", "ok", f"{len(photos)} photos clean, pages complete")

            await progress("commit", "running")
            exists, root_slug = await front_page_slug(clone)
            root_was_ours = exists and (root_slug == pub.slug if root_slug is not None else bool(pub.is_default))
            rels = [rel for _, rel in _page_urls(pub.slug, bool(pub.is_default))]
            drop_root = root_was_ours and not pub.is_default      # no longer the default: its old front page goes

            def change(wt: Path) -> list[str]:
                _replace_page(dirs, [wt / r if r else wt for r in rels])
                if drop_root:
                    _remove_page(wt, root=True)
                return rels
            allowed = [r for r in rels if r]
            if "" in rels or drop_root:
                allowed += ["index.html", "preview.html", "tree.html", "photos"]
            msg = (f"Publish walk {walk.id} '{walk.name}' → {', '.join(r or '/' for r in rels)}\n\n"
                   f"{len(plan['public_species'])} species, {len(plan['stops'])} stops. "
                   f"From ForagingID experience publication #{pub.id}.")
            async def committed(c):
                await _persist_commit(job, c, snapshot)          # before the push: a restart can repair
                await progress("commit", "ok", f"one commit {c[:7]}")
                await progress("push", "running")
            sha = await _commit_and_push(clone, change, msg, allowed, committed)
            if sha is None:
                sha = (await git(clone, "rev-parse", "HEAD"))[1].strip()
                await progress("commit", "ok", "no change")
                await progress("push", "ok", "the site already has exactly this page — nothing to push")
            else:
                await progress("push", "ok", f"pushed {sha[:7]}")
            expect = {}
            for (url, rel), d in zip(_page_urls(pub.slug, bool(pub.is_default)), dirs):
                for name in OWNED_FILES:
                    expect[url + ("" if name == "index.html" else name)] = (d / name).read_bytes()

        await progress("record", "running")
        row = await _record(pub.id, status="published", published_at=datetime.utcnow(), unpublished_at=None,
                            published_commit=sha, public_species_json=json.dumps(snapshot, ensure_ascii=False))
        await progress("record", "ok", f"publication #{row['id']} published at {sha[:7]}")

        await progress("live", "running", "waiting for GitHub Pages")
        live = await wait_live(expect, sha)
        await progress("live", "ok" if live["ok"] else "failed",
                       "live pages match the build" if live["ok"] else
                       f"not live yet after {LIVE_TIMEOUT_S}s: {live['pending'][:3]} — pushed and recorded; check again")
        url = _page_urls(pub.slug, bool(pub.is_default))[0][0]
        return {"message": f"Published {url} at {sha[:7]}." + ("" if live["ok"] else " The live page isn't showing it yet."),
                "commit": sha, "url": url, "live": live, "publication": row}

    await _run_job(job, body, label, len(PUBLISH_STEPS))


async def run_unpublish(job: dict, clone: Optional[Path] = None) -> None:
    clone = clone or CLONE
    pub, walk = await _load(job["publication_id"])
    label = f"Unpublish {pub.slug if pub else '?'}"

    async def body(progress):
        if pub is None:
            raise PublishStop("site", "This publication no longer exists.")
        if pub.status != "published":
            raise PublishStop("site", f"This page is not published (status {pub.status}).")
        await progress("site", "running")
        site = await check_site(clone)
        await progress("site", "ok", f"site at {site['head'][:7]}, login ok")

        await progress("commit", "running")
        exists, root_slug = await front_page_slug(clone)
        root_ours = exists and (root_slug == pub.slug if root_slug is not None else bool(pub.is_default))
        removed: list[str] = []

        def change(wt: Path) -> list[str]:
            removed.extend(f"w/{pub.slug}/" for _ in _remove_page(wt / "w" / pub.slug, root=False))
            if root_ours:
                removed.extend(_remove_page(wt, root=True))
            return removed
        allowed = [f"w/{pub.slug}"] + (["index.html", "preview.html", "tree.html", "photos"] if root_ours else [])
        msg = (f"Unpublish {pub.slug}" + (" (and the front page)" if root_ours else "")
               + (f" — walk {walk.id} '{walk.name}'" if walk else "")
               + f"\n\nFrom ForagingID experience publication #{pub.id}. The saved walk is kept.")
        async def committed(c):
            await _persist_commit(job, c, None)                  # before the push: a restart can repair
            await progress("commit", "ok", f"one commit {c[:7]}")
            await progress("push", "running")
        sha = await _commit_and_push(clone, change, msg, allowed, committed)
        if sha is None:
            sha = (await git(clone, "rev-parse", "HEAD"))[1].strip()
            await progress("commit", "ok", "no change")
            await progress("push", "ok", "the page was not on the site — nothing to push")
        else:
            await progress("push", "ok", f"pushed {sha[:7]}")

        await progress("record", "running")
        row = await _record(pub.id, status="unpublished", unpublished_at=datetime.utcnow(), is_default=False)
        await progress("record", "ok", f"publication #{row['id']} unpublished")

        await progress("live", "running", "waiting for GitHub Pages")
        gone = [u for u, rel in _page_urls(pub.slug, root_ours)]
        live = await wait_live({u: None for u in gone}, sha)
        await progress("live", "ok" if live["ok"] else "failed",
                       "the page returns 404" if live["ok"] else f"still served after {LIVE_TIMEOUT_S}s: {live['pending'][:3]}")
        return {"message": f"Unpublished {pub.slug} ({', '.join(removed) or 'nothing was on the site'}). "
                           "The saved walk is kept. The page stays in git history and in other people's caches.",
                "commit": sha, "removed": removed, "live": live, "publication": row}

    await _run_job(job, body, label, len(UNPUBLISH_STEPS))


# ── interrupted runs (server restart / reload mid-job) ───────────────────────

async def _bp_payload(pid: int) -> Optional[dict]:
    from sqlalchemy import text
    async with database.AsyncSessionLocal() as db:
        raw = await db.scalar(text("SELECT payload FROM background_processes WHERE process_id = :p"), {"p": pid})
    try:
        return json.loads(raw) if raw else None
    except ValueError:
        return None


async def _persist_commit(job: dict, commit: str, snapshot: Optional[dict]) -> None:
    """Write the commit (and the snapshot to record) to the job's
    background_processes row BEFORE the push, then read it back. If it did not
    land, stop here: nothing is pushed that a restart could not account for."""
    pid = job.get("process_id")
    payload = {"publication_id": job["publication_id"], "kind": job["kind"], "started_at": job["started_at"],
               "commit": commit, "snapshot": snapshot}
    if pid is not None:
        await bp_patch(pid, payload=json.dumps(payload, ensure_ascii=False))
    back = await _bp_payload(pid) if pid is not None else None
    if not back or back.get("commit") != commit:
        raise PublishStop("site", "Couldn't save the job record before pushing — nothing was pushed. Try again.")


async def repair_interrupted(clone: Optional[Path] = None) -> list[dict]:
    """Server start: every publish / unpublish row still running or interrupted
    belongs to a run that died with the old process (jobs live in memory). Its
    commit on GitHub → record the publication and read it back; no commit, or a
    commit GitHub does not have → failed, with the reason; GitHub unreachable →
    left 'interrupted' for the next start. Never pushes. Returns what it did."""
    global _REPAIRING
    from sqlalchemy import text
    clone = clone or CLONE
    live = {j.get("process_id") for j in _JOBS.values() if j.get("status") == "running"}
    async with database.AsyncSessionLocal() as db:
        rows = (await db.execute(text(
            "SELECT process_id, process_type, payload FROM background_processes "
            "WHERE process_type IN ('experience_publish', 'experience_unpublish') "
            "AND status IN ('running', 'interrupted') ORDER BY process_id"))).all()
    rows = [r for r in rows if r[0] not in live]
    if not rows:
        return []
    _REPAIRING = True
    done = []
    try:
        fetched: Optional[str] = None
        for pid, ptype, raw in rows:
            try:
                p = json.loads(raw) if raw else {}
            except ValueError:
                p = {}
            out = {"process_id": pid, "publication_id": p.get("publication_id"), "kind": p.get("kind")}

            async def finish(state: str, message: str, status: str):
                p.update(repair=state, repair_message=message, repaired_at=datetime.utcnow().isoformat())
                await bp_patch(pid, payload=json.dumps(p, ensure_ascii=False))
                await bp_finish(pid, status, error="" if state == "repaired" else message)
                out.update(state=state, message=message)
                done.append(out)

            commit = p.get("commit")
            if not p.get("publication_id"):
                await finish("failed", "Interrupted — no record of which page it was. Nothing was pushed now.", "failed")
                continue
            if not commit:
                await finish("failed", "Interrupted before its commit was made — nothing was pushed. "
                                       "Publish again.", "failed")
                continue
            if fetched is None:
                if not (clone / ".git").exists():
                    fetched = f"the site copy {clone} is missing"
                else:
                    rc, o, e = await git(clone, "fetch", REMOTE, BRANCH)
                    fetched = "" if rc == 0 else ("offline" if _classify(e or o) == "offline" else (e or o).strip()[-200:])
            if fetched:
                await finish("pending", f"Interrupted — couldn't check GitHub ({fetched}). It will be checked "
                                        "again when the server next starts.", "interrupted")
                continue
            rc, _, _ = await git(clone, "merge-base", "--is-ancestor", commit, f"{REMOTE}/{BRANCH}")
            if rc != 0:
                await finish("failed", f"Interrupted — its commit {commit[:7]} is not on GitHub, so the push never "
                                       "happened. Nothing was pushed now. Publish again.", "failed")
                continue
            try:
                if p.get("kind") == "unpublish":
                    await _record(p["publication_id"], status="unpublished", unpublished_at=datetime.utcnow(),
                                  is_default=False)
                else:
                    snap = p.get("snapshot")
                    await _record(p["publication_id"], status="published", published_at=datetime.utcnow(),
                                  unpublished_at=None, published_commit=commit,
                                  public_species_json=json.dumps(snap, ensure_ascii=False) if snap else None)
            except Exception as ex:                       # e.g. the publication was deleted meanwhile
                await finish("failed", f"Interrupted — the commit {commit[:7]} is on GitHub but the record "
                                       f"could not be written: {ex}", "failed")
                continue
            await finish("repaired", f"Interrupted — record repaired (commit {commit[:7]} is on GitHub).", "complete")
        # The clone's main may still be behind the pushed commit: a fast-forward
        # only (never a reset), and only when its working tree is clean.
        if (clone / ".git").exists():
            await git(clone, "worktree", "prune")
            if fetched == "" and not (await git(clone, "status", "--porcelain"))[1].strip():
                await git(clone, "merge", "--ff-only", "-q", f"{REMOTE}/{BRANCH}")
    finally:
        _REPAIRING = False
    for d in done:
        log.warning("experience %s #%s: %s", d.get("kind"), d.get("publication_id"), d.get("message"))
    return done


async def last_repair(pub_id: int) -> Optional[dict]:
    """The latest repair note for this publication (the Publish panel shows it),
    or None when its last run was not an interrupted one."""
    from sqlalchemy import text
    async with database.AsyncSessionLocal() as db:
        rows = (await db.execute(text(
            "SELECT process_id, status, payload FROM background_processes "
            "WHERE process_type IN ('experience_publish', 'experience_unpublish') "
            "ORDER BY process_id DESC LIMIT 50"))).all()
    for pid, status, raw in rows:
        try:
            p = json.loads(raw) if raw else {}
        except ValueError:
            continue
        if p.get("publication_id") != pub_id:
            continue
        if not p.get("repair"):
            return None                                   # its latest run ended normally
        return {"process_id": pid, "state": p["repair"], "message": p.get("repair_message"),
                "at": p.get("repaired_at"), "commit": p.get("commit")}
    return None


# ── overrides files (copy a CLI walk's texts into a new publication) ─────────

def override_files() -> list[dict]:
    out = []
    for f in sorted(OVERRIDES_DIR.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and isinstance(d.get("slug"), str):
            out.append({"file": f.name, "slug": d["slug"], "title_en": d.get("title_en", "")})
    return out


def read_override_file(name: str) -> dict:
    if name not in {o["file"] for o in override_files()}:
        raise ValueError(f"no overrides file {name!r}")
    d = json.loads((OVERRIDES_DIR / name).read_text(encoding="utf-8"))
    return {k: v for k, v in d.items() if not k.startswith("_")}
