"""
dev.py — Developer tools: changelog, snapshots, session management, Drive sync.

Admin-only. These endpoints are not exposed in guest mode (the frontend
hides the UI controls via data-guest-hide; the backend does not add extra
auth — the Settings page is already blocked from guests).

Endpoints:
  GET  /api/dev/changelog        — full CHANGELOG.md text
  GET  /api/dev/current-state    — ## Current State block only
  PUT  /api/dev/current-state    — rewrite ## Current State
  POST /api/dev/log              — append structured entry to ## History
  POST /api/dev/snapshot         — create timestamped snapshot (git + DB) + Drive sync
  GET  /api/dev/snapshots        — list all snapshots
  POST /api/dev/restore          — restore to a snapshot (destructive)
  POST /api/dev/end-session      — update state + snapshot + history entry
  POST /api/dev/gdrive-sync      — manually sync CHANGELOG.md to Google Drive
                                     (also fires automatically on every snapshot)
  POST /api/dev/backup-external  — copy the latest DB snapshot to /Volumes/DIGIERA
                                     (also fires automatically, best-effort, on End Session)
  GET  /api/dev/backup-external-status — last external-backup timestamp/error
"""

import asyncio
import hashlib
import logging
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.integrations.gdrive import GDriveError, sync_changelog as _gdrive_sync
from app.services.changelog_service import (
    append_history_entry,
    get_current_state,
    read_changelog,
    rewrite_current_state,
)
from app.services.settings_service import get_setting

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dev", tags=["dev"])

# ---------------------------------------------------------------------------
# GDrive sync state — tracks last success/failure across requests.
# In-memory only; resets on server restart (intentional — a restart usually
# means a token change or re-config, so stale timestamps would be misleading).
# ---------------------------------------------------------------------------
_gdrive_status: dict = {
    "last_sync_at":    None,   # ISO timestamp of last successful sync
    "last_error":      None,   # Error message from last failed sync attempt
}

# ---------------------------------------------------------------------------
# External-drive backup state — same in-memory/reset-on-restart pattern as
# _gdrive_status above.
# ---------------------------------------------------------------------------
_backup_status: dict = {
    "last_backup_at": None,   # ISO timestamp of last successful backup
    "last_error":     None,   # Error message from last failed *manual* attempt
                              # (silent skips from End Session do not set this)
}

PROJECT_ROOT  = Path(__file__).parent.parent.parent
DB_PATH       = PROJECT_ROOT / "data" / "foragingid.db"
SNAPSHOTS_DIR = PROJECT_ROOT / "snapshots"

EXTERNAL_DRIVE      = Path("/Volumes/DIGIERA")
EXTERNAL_BACKUP_DIR = EXTERNAL_DRIVE / "ForagingID_Backup"

# Retention: keep all snapshots < 7 days, one per day for 7–28 days, delete older.
_RETENTION_FULL_DAYS = 7
_RETENTION_THIN_DAYS = 28


def _prune_snapshots() -> int:
    """Apply rolling retention to SNAPSHOTS_DIR. Returns count of files deleted."""
    if not SNAPSHOTS_DIR.exists():
        return 0
    now = datetime.now()
    by_day: dict[str, list[Path]] = {}
    for f in SNAPSHOTS_DIR.glob("db_*.sqlite*"):
        age_days = (now - datetime.fromtimestamp(f.stat().st_mtime)).total_seconds() / 86400
        if age_days < _RETENTION_FULL_DAYS:
            continue
        day_key = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d")
        by_day.setdefault(day_key, []).append((f, age_days))
    deleted = 0
    for day_key, files in by_day.items():
        files.sort(key=lambda x: x[0].stat().st_mtime)
        age = files[0][1]
        if age > _RETENTION_THIN_DAYS:
            for f, _ in files:
                f.unlink(missing_ok=True)
                deleted += 1
        else:
            for f, _ in files[1:]:
                f.unlink(missing_ok=True)
                deleted += 1
    return deleted


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _latest_snapshot_file() -> Optional[Path]:
    """Most recently modified db_*.sqlite* file in SNAPSHOTS_DIR, or None."""
    if not SNAPSHOTS_DIR.exists():
        return None
    files = [f for f in SNAPSHOTS_DIR.glob("db_*.sqlite*") if f.is_file()]
    if not files:
        return None
    return max(files, key=lambda f: f.stat().st_mtime)


def _backup_to_external() -> dict:
    """
    Copy the most recent DB snapshot to the external drive, if mounted.

    Never copies the live data/foragingid.db directly — snapshot-only, for
    write-consistency (matches the existing restore trust model: only a
    file that was written atomically at a point in time is trustworthy to
    copy around, not a file that may be mid-write).

    Returns a result dict; never raises. Callers decide how to log/report
    based on the "skipped" flag (drive not mounted — expected, not an error)
    vs "ok": False with a real error.
    """
    if not EXTERNAL_DRIVE.is_mount():
        return {"ok": False, "skipped": True, "error": "External drive not connected"}

    latest = _latest_snapshot_file()
    if latest is None:
        return {
            "ok": False, "skipped": False,
            "error": "No snapshot file found in snapshots/ — create one first",
        }

    try:
        EXTERNAL_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        dest = EXTERNAL_BACKUP_DIR / latest.name
        # Plain chunked read/write — NOT shutil.copyfile/copy2. On macOS,
        # shutil's fast path shells out to the native copyfile(3) syscall,
        # which tries to preserve xattrs/resource forks (leaves a stray
        # ._<name> AppleDouble sidecar) and intermittently raises
        # "Operation not permitted" (EPERM) against this ExFAT-formatted
        # drive. A manual byte copy has no such OS-level fast path to fail.
        with latest.open("rb") as src_fh, dest.open("wb") as dest_fh:
            for chunk in iter(lambda: src_fh.read(4 * 1024 * 1024), b""):
                dest_fh.write(chunk)

        # Verify — checksum compare (file is a few hundred MB at most; sha256
        # over local disk is fast, and this is stronger than a size compare).
        src_hash  = _sha256(latest)
        dest_hash = _sha256(dest)
        if src_hash != dest_hash:
            return {
                "ok": False, "skipped": False,
                "error": f"Copy verification failed — checksum mismatch for {latest.name}",
            }

        return {
            "ok": True, "skipped": False,
            "file": latest.name,
            "dest_path": str(dest),
            "size_bytes": dest.stat().st_size,
            "checksum": dest_hash,
        }
    except Exception as exc:
        return {"ok": False, "skipped": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Changelog — read
# ---------------------------------------------------------------------------

@router.get("/changelog")
async def get_changelog():
    """Return full CHANGELOG.md text."""
    return {"content": read_changelog()}


@router.get("/current-state")
async def get_current_state_endpoint():
    """Return the ## Current State section."""
    return {"state": get_current_state()}


# ---------------------------------------------------------------------------
# Changelog — write
# ---------------------------------------------------------------------------

class StateUpdate(BaseModel):
    state: str


@router.put("/current-state")
async def update_current_state(body: StateUpdate):
    """Rewrite the ## Current State block."""
    rewrite_current_state(body.state)
    return {"ok": True}


class LogEntry(BaseModel):
    prompt_summary: str
    features_built: Optional[List[str]] = None
    fixes_applied:  Optional[List[str]] = None
    files_changed:  Optional[List[str]] = None
    pending:        Optional[List[str]] = None


@router.post("/log")
async def append_log(entry: LogEntry):
    """
    Append a structured entry to the ## History section of CHANGELOG.md.
    Call at the end of each prompt to record what was built.
    """
    parts: list[str] = []
    if entry.prompt_summary:
        parts.append(f"**{entry.prompt_summary}**\n")
    if entry.features_built:
        parts.append("**Built:**")
        parts.extend(f"- {f}" for f in entry.features_built)
    if entry.fixes_applied:
        parts.append("**Fixed:**")
        parts.extend(f"- {f}" for f in entry.fixes_applied)
    if entry.files_changed:
        parts.append("**Files:** " + ", ".join(f"`{f}`" for f in entry.files_changed))
    if entry.pending:
        parts.append("**Pending:**")
        parts.extend(f"- {p}" for p in entry.pending)

    append_history_entry("\n".join(parts))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Snapshot — create
# ---------------------------------------------------------------------------

class SnapshotRequest(BaseModel):
    description:   Optional[str] = None
    current_state: Optional[str] = None  # if set, rewrites ## Current State first


@router.post("/snapshot")
async def create_snapshot(body: SnapshotRequest = None):  # type: ignore[assignment]
    """
    Create a timestamped snapshot:
    1. Copy foragingid.db → snapshots/db_YYYYMMDD_HHMMSS.sqlite
    2. Optionally rewrite ## Current State in CHANGELOG.md
    3. Append a snapshot entry to ## History
    4. git add -A && git commit (allow-empty) with message "snapshot: TIMESTAMP"
    """
    if body is None:
        body = SnapshotRequest()

    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    ts_human = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Ensure snapshots dir exists
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Copy DB
    db_snap = SNAPSHOTS_DIR / f"db_{ts}.sqlite"
    if DB_PATH.exists():
        shutil.copy2(DB_PATH, db_snap)

    # 3. Optionally rewrite Current State
    if body.current_state:
        rewrite_current_state(body.current_state)

    # 4. Append snapshot entry to History
    desc = body.description or "Manual snapshot"
    append_history_entry(
        f"**Snapshot** — {desc}\n"
        f"DB: `snapshots/db_{ts}.sqlite`"
    )

    # 5. Git commit — async subprocesses so the event loop stays alive and
    #    deferred SIGINT cannot fire as KeyboardInterrupt mid-operation.
    commit_hash: Optional[str] = None
    git_error:   Optional[str] = None
    try:
        git_msg = f"snapshot: {ts_human}"

        add_proc = await asyncio.create_subprocess_exec(
            "git", "add", "-A",
            cwd=PROJECT_ROOT,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, add_err = await add_proc.communicate()
        if add_proc.returncode != 0:
            raise RuntimeError(add_err.decode().strip())

        commit_proc = await asyncio.create_subprocess_exec(
            "git", "commit", "--allow-empty", "-m", git_msg,
            cwd=PROJECT_ROOT,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, commit_err = await commit_proc.communicate()
        if commit_proc.returncode == 0:
            rev_proc = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "HEAD",
                cwd=PROJECT_ROOT,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            rev_out, _ = await rev_proc.communicate()
            if rev_proc.returncode == 0:
                commit_hash = rev_out.decode().strip()[:8]
        else:
            git_error = commit_err.decode().strip()
    except Exception as exc:
        git_error = str(exc)

    # 6. Sync CHANGELOG.md to Google Drive (best-effort — never fails the snapshot)
    gdrive_result: Optional[dict] = None
    gdrive_error:  Optional[str]  = None
    try:
        token = get_setting("gdrive_access_token")
        if token:
            gdrive_result = await _gdrive_sync(token)
            log.info("gdrive: snapshot sync complete — %s", gdrive_result.get("action"))
            _gdrive_status["last_sync_at"] = datetime.utcnow().isoformat() + "Z"
            _gdrive_status["last_error"]   = None
        else:
            log.debug("gdrive: no token configured, skipping Drive sync")
    except GDriveError as exc:
        gdrive_error = str(exc)
        _gdrive_status["last_error"] = str(exc)
        log.warning("gdrive: sync failed (snapshot) — %s", exc)
    except Exception as exc:
        gdrive_error = f"Unexpected error: {exc}"
        _gdrive_status["last_error"] = gdrive_error
        log.exception("gdrive: unexpected error during snapshot sync")

    # 7. Prune old snapshots per retention policy
    pruned = _prune_snapshots()

    return {
        "ok":              True,
        "timestamp":       ts,
        "timestamp_human": ts_human,
        "db_snapshot":     str(db_snap),
        "commit_hash":     commit_hash,
        "git_error":       git_error,
        "gdrive":          gdrive_result,
        "gdrive_error":    gdrive_error,
        "snapshots_pruned": pruned,
    }


# ---------------------------------------------------------------------------
# Snapshot — list
# ---------------------------------------------------------------------------

@router.get("/snapshots")
async def list_snapshots():
    """
    Return all snapshots by combining:
    - git commits whose message starts with "snapshot:"
    - DB files in ~/ForagingID/snapshots/
    """
    snapshots: list[dict] = []

    # --- git snapshot commits ---
    try:
        result = subprocess.run(
            ["git", "log", "--grep=^snapshot:", "--format=%H|%ci|%s"],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
        )
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue
            full_hash, commit_date, msg = parts
            ts_str = msg.replace("snapshot: ", "").strip()
            # Derive DB filename: "2025-06-01 14:30:00" → "20250601_143000"
            ts_key = (
                ts_str.replace("-", "")
                       .replace(":", "")
                       .replace(" ", "_")
            )
            db_file = SNAPSHOTS_DIR / f"db_{ts_key}.sqlite"
            snapshots.append({
                "commit_hash":    full_hash[:8],
                "full_hash":      full_hash,
                "date":           commit_date.strip(),
                "description":    msg.strip(),
                "has_db":         db_file.exists(),
                "db_path":        str(db_file) if db_file.exists() else None,
            })
    except Exception:
        pass

    # --- DB-only files not matched above ---
    if SNAPSHOTS_DIR.exists():
        listed_db_paths = {s["db_path"] for s in snapshots if s.get("db_path")}
        for db_file in sorted(SNAPSHOTS_DIR.glob("db_*.sqlite"), reverse=True):
            if str(db_file) not in listed_db_paths:
                ts_key = db_file.stem.replace("db_", "")
                snapshots.append({
                    "commit_hash": None,
                    "full_hash":   None,
                    "date":        None,
                    "description": f"DB-only snapshot ({ts_key})",
                    "has_db":      True,
                    "db_path":     str(db_file),
                })

    return {"snapshots": snapshots}


# ---------------------------------------------------------------------------
# Snapshot — restore
# ---------------------------------------------------------------------------

class RestoreRequest(BaseModel):
    commit_hash: Optional[str] = None  # short or full hash
    db_path:     Optional[str] = None  # absolute path to snapshot DB


@router.post("/restore")
async def restore_snapshot(body: RestoreRequest):
    """
    Restore to a snapshot.  Two independent operations — either or both:

    1. db_path  → overwrite foragingid.db with the snapshot DB
    2. commit_hash → git checkout <hash>  (puts repo in detached-HEAD state)

    ⚠️ DESTRUCTIVE.  Frontend must display a confirmation before calling.
    Restart the server after a code restore for changes to take effect.
    """
    results: dict = {}

    # 1. Restore database
    if body.db_path:
        snap_db = Path(body.db_path)
        if not snap_db.exists():
            raise HTTPException(400, detail=f"DB snapshot not found: {body.db_path}")
        shutil.copy2(snap_db, DB_PATH)
        results["db_restored"] = str(snap_db)

    # 2. Git checkout
    if body.commit_hash:
        try:
            result = subprocess.run(
                ["git", "checkout", body.commit_hash],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            if result.returncode != 0:
                raise HTTPException(
                    500,
                    detail=f"git checkout failed: {result.stderr or result.stdout}",
                )
            results["git_restored"] = body.commit_hash
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(500, detail=f"git checkout error: {exc}")

    if not results:
        raise HTTPException(400, detail="Provide commit_hash and/or db_path.")

    return {
        "ok": True,
        **results,
        "note": "Restart the server to apply any code changes.",
    }


# ---------------------------------------------------------------------------
# Snapshot — view CHANGELOG.md from a commit
# ---------------------------------------------------------------------------

_HASH_RE = re.compile(r"^[0-9a-fA-F]{4,40}$")


@router.get("/snapshot-changelog")
async def snapshot_changelog(commit: str):
    """Return CHANGELOG.md as it existed at the given snapshot commit."""
    commit = commit.strip()
    if not _HASH_RE.match(commit):
        raise HTTPException(400, detail="Invalid commit hash.")
    try:
        result = subprocess.run(
            ["git", "show", f"{commit}:CHANGELOG.md"],
            cwd=PROJECT_ROOT, capture_output=True, text=True,
        )
    except Exception as exc:
        raise HTTPException(500, detail=f"git show error: {exc}")
    if result.returncode != 0:
        raise HTTPException(
            404,
            detail=f"CHANGELOG.md not found at {commit}: {result.stderr.strip() or 'unknown error'}",
        )
    return {"commit": commit, "changelog": result.stdout}


# ---------------------------------------------------------------------------
# End session — helpers
# ---------------------------------------------------------------------------

def _update_claude_md_phase(current_phase: str, next_steps: str) -> None:
    """
    Replace only the content of the ## Current Phase and ## Next Steps
    sections in CLAUDE.md.  Everything else is left unchanged.
    """
    path = PROJECT_ROOT / "CLAUDE.md"
    if not path.exists():
        return
    text = path.read_text()

    # Replace ## Current Phase section body (stop at next ## heading or end-of-file)
    text = re.sub(
        r"(## Current Phase\n\n<!-- auto-updated by end-session[^\n]*\n).*?(?=\n## |\Z)",
        lambda m: m.group(1) + current_phase + "\n",
        text,
        flags=re.DOTALL,
    )

    # Replace ## Next Steps section body
    text = re.sub(
        r"(## Next Steps\n\n<!-- auto-updated by end-session[^\n]*\n).*?(?=\n## |\Z)",
        lambda m: m.group(1) + next_steps + "\n",
        text,
        flags=re.DOTALL,
    )

    path.write_text(text)


def _update_current_phase_doc(
    current_phase: str,
    next_steps: str,
    current_state_text: str,
    ts_human: str,
) -> None:
    """
    Rewrite the variable header section of docs/current_phase.md.
    Everything from '## Critical Discipline Notes' onwards is static and
    preserved unchanged.
    """
    path = PROJECT_ROOT / "docs" / "current_phase.md"
    if not path.exists():
        return
    existing = path.read_text()

    # Find the static section boundary — preserve from here down
    static_marker = "## Critical Discipline Notes"
    idx = existing.find(static_marker)
    preserved = existing[idx:] if idx != -1 else ""

    variable_section = (
        f"# ForagingID — Current Phase\n"
        f"*Last updated: {ts_human}*\n\n"
        f"## Status\n\n"
        f"{current_phase}\n\n"
        f"---\n\n"
        f"## What's Running Now\n\n"
        f"{current_state_text.strip()}\n\n"
        f"---\n\n"
        f"## Next Up\n\n"
        f"{next_steps}\n\n"
        f"---\n\n"
    )

    path.write_text(variable_section + preserved)


# ---------------------------------------------------------------------------
# End session
# ---------------------------------------------------------------------------

class EndSessionRequest(BaseModel):
    current_state:   str
    session_summary: Optional[str] = None
    current_phase:   Optional[str] = None   # short label for CLAUDE.md + current_phase.md
    next_steps:      Optional[str] = None   # what's next for CLAUDE.md + current_phase.md


@router.post("/end-session")
async def end_session(body: EndSessionRequest):
    """
    Clean end-of-session action:
    1. Rewrite ## Current State in CHANGELOG.md
    2. Update docs/current_phase.md variable section (if current_phase/next_steps supplied)
    3. Update ## Current Phase and ## Next Steps in CLAUDE.md (if supplied)
    4. Append session-end entry to ## History in CHANGELOG.md
    5. Create a full snapshot (DB copy + local git commit)
    6. Push to origin/main — best-effort, non-fatal on failure
    7. Back up latest snapshot to external drive — best-effort, non-fatal,
       silently skipped if /Volumes/DIGIERA isn't mounted
    """
    summary   = body.session_summary or "Session ended"
    ts_human  = datetime.now().strftime("%Y-%m-%d %H:%M")
    docs_updated = False

    # 1. Rewrite Current State in CHANGELOG.md
    rewrite_current_state(body.current_state)

    # 2 + 3. Update docs files when phase/next-steps data is provided
    if body.current_phase or body.next_steps:
        cp = body.current_phase or "—"
        ns = body.next_steps    or "—"
        try:
            _update_current_phase_doc(cp, ns, body.current_state, ts_human)
            _update_claude_md_phase(cp, ns)
            docs_updated = True
        except Exception as exc:
            log.warning("end_session: docs update failed — %s", exc)

    # 4. Append session-end entry to History
    append_history_entry(f"**Session ended** — {summary}")

    # 5. Create snapshot (DB copy + local git commit)
    snap = await create_snapshot(
        SnapshotRequest(description=f"End of session — {summary}")
    )

    # 5b. Push to origin/main — best-effort, never blocks End Session on
    # network issues. A failed/skipped push just means the next session's
    # remote-vs-local check (or a manual /api/dev/git-push) will catch it.
    push_result: dict = {"attempted": False}
    try:
        push_proc = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=45,
        )
        push_result = {
            "attempted": True,
            "ok": push_proc.returncode == 0,
            "output": (push_proc.stdout.strip() or push_proc.stderr.strip()
                       if push_proc.returncode == 0 else None),
            "error": (push_proc.stderr.strip() or push_proc.stdout.strip()
                      if push_proc.returncode != 0 else None),
        }
        if push_proc.returncode == 0:
            log.info("end_session: git push origin main succeeded")
        else:
            log.warning("end_session: git push failed — %s", push_result["error"])
    except subprocess.TimeoutExpired:
        push_result = {"attempted": True, "ok": False, "error": "git push timed out after 45s — check wifi"}
        log.warning("end_session: git push timed out")
    except Exception as exc:
        push_result = {"attempted": True, "ok": False, "error": str(exc)}
        log.warning("end_session: git push error — %s", exc)

    # 5c. Back up latest snapshot to external drive — best-effort, never
    # blocks End Session. Drive-not-mounted is the expected common case
    # (laptop not docked) and is skipped silently, not logged as a warning.
    backup_result: dict = {"attempted": False}
    try:
        backup_result = _backup_to_external()
        backup_result["attempted"] = True
        if backup_result.get("ok"):
            _backup_status["last_backup_at"] = datetime.utcnow().isoformat() + "Z"
            _backup_status["last_error"] = None
            log.info("end_session: external backup complete — %s", backup_result.get("file"))
        elif backup_result.get("skipped"):
            log.debug("end_session: external drive not connected, skipping backup")
        else:
            _backup_status["last_error"] = backup_result.get("error")
            log.warning("end_session: external backup failed — %s", backup_result.get("error"))
    except Exception as exc:
        backup_result = {"attempted": True, "ok": False, "error": str(exc)}
        _backup_status["last_error"] = str(exc)
        log.warning("end_session: external backup error — %s", exc)

    # 6. Obsidian vault sync — additive, never blocks on failure
    try:
        vault_path_str = get_setting("obsidian_vault_path")
        if vault_path_str:
            vault = Path(str(vault_path_str)).expanduser()
            vault.mkdir(parents=True, exist_ok=True)
            date_str = datetime.now().strftime("%Y-%m-%d")
            # Current State.md — overwrite with date header + current state text
            (vault / "Current State.md").write_text(
                f"# {date_str}\n\n{body.current_state}\n", encoding="utf-8"
            )
            # Decisions Log.md — append one line, never overwrite
            one_liner = (body.session_summary or summary).split("\n")[0][:200]
            decisions_log = vault / "Decisions Log.md"
            with decisions_log.open("a", encoding="utf-8") as fh:
                fh.write(f"- {date_str} — {one_liner}\n")
            log.info("obsidian_sync: wrote to %s", vault)
    except Exception as exc:
        log.warning("obsidian_sync: skipped — %s", exc)

    # 7. Export encounters created since the previous snapshot to Obsidian
    encounter_export: dict = {}
    try:
        # Find the most recent snapshot timestamp from git log (before this session's
        # snapshot, so use the second-most-recent — snap itself is the latest).
        # Fall back to None (export all) if no prior snapshot exists.
        since_dt: Optional[datetime] = None
        try:
            result = subprocess.run(
                ["git", "log", "--grep=^snapshot:", "--format=%ci", "--skip=1", "-1"],
                cwd=PROJECT_ROOT, capture_output=True, text=True,
            )
            ts_line = result.stdout.strip()
            if ts_line:
                # git commit date format: "2026-06-05 21:09:29 +0100"
                since_dt = datetime.fromisoformat(ts_line.split("+")[0].split("-0")[0].strip())
        except Exception as _ts_exc:
            log.warning("end_session: could not parse last snapshot timestamp — exporting all: %s", _ts_exc)

        encounter_export = await _export_encounters_to_obsidian(since=since_dt)
        log.info(
            "end_session: encounter export complete — written=%d skipped=%d since=%s",
            encounter_export.get("written", 0),
            encounter_export.get("skipped", 0),
            since_dt.isoformat() if since_dt else "all",
        )
    except Exception as exc:
        log.warning("end_session: encounter export failed — %s", exc)

    return {
        "ok":                    True,
        "current_state_updated": True,
        "docs_updated":          docs_updated,
        "snapshot":              snap,
        "git_push":              push_result,
        "external_backup":       backup_result,
        "encounter_export":      encounter_export,
    }


# ---------------------------------------------------------------------------
# Git push  (manual trigger — end-session also pushes automatically, best-effort)
# ---------------------------------------------------------------------------

@router.post("/git-push")
async def git_push():
    """
    Push local commits to the remote (origin main).
    Manual/on-demand version of the push end-session now runs automatically
    (see end_session() step 6) — useful for pushing outside the session-end flow,
    or retrying after a network failure during End Session.
    Returns success message or raises HTTPException with the git error output.
    """
    try:
        result = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=45,
        )
        if result.returncode == 0:
            output = (result.stdout.strip() or result.stderr.strip() or "Push successful")
            return {"ok": True, "output": output}
        else:
            err = result.stderr.strip() or result.stdout.strip() or "git push failed"
            raise HTTPException(status_code=500, detail=err)
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="git push timed out after 45 s — check wifi connection",
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"git push error: {exc}")


# ---------------------------------------------------------------------------
# External-drive backup — manual trigger + status
# (end-session also runs this automatically, best-effort, see end_session())
# ---------------------------------------------------------------------------

@router.get("/backup-external-status")
async def backup_external_status():
    """Return the last external-backup result (in-memory, resets on restart)."""
    return {
        "last_backup_at": _backup_status["last_backup_at"],
        "last_error":     _backup_status["last_error"],
        "drive_mounted":  EXTERNAL_DRIVE.is_mount(),
    }


@router.post("/backup-external")
async def backup_external():
    """
    Manually copy the latest DB snapshot to /Volumes/DIGIERA/ForagingID_Backup/.

    Unlike the automatic End Session step, a manual click always surfaces a
    clear error (including "drive not connected") rather than skipping
    silently — the whole point of clicking the button is to know whether it
    worked.
    """
    result = _backup_to_external()
    if result.get("ok"):
        _backup_status["last_backup_at"] = datetime.utcnow().isoformat() + "Z"
        _backup_status["last_error"] = None
        return {
            "ok": True,
            "file": result["file"],
            "dest_path": result["dest_path"],
            "size_bytes": result["size_bytes"],
            "timestamp": _backup_status["last_backup_at"],
        }
    _backup_status["last_error"] = result["error"]
    raise HTTPException(status_code=400, detail=result["error"])


# ---------------------------------------------------------------------------
# Google Drive — manual sync + connection test
# ---------------------------------------------------------------------------

@router.get("/gdrive-status")
async def gdrive_status():
    """
    Return the last Google Drive sync result (in-memory, resets on restart).
    Used by settings.html to show the last-synced timestamp and amber warning.
    """
    return {
        "last_sync_at": _gdrive_status["last_sync_at"],
        "last_error":   _gdrive_status["last_error"],
        "has_token":    bool(get_setting("gdrive_access_token")),
    }


@router.post("/gdrive-sync")
async def gdrive_sync():
    """
    Manually sync CHANGELOG.md to Google Drive.

    Uses the 'gdrive_access_token' setting. Returns a result dict that the
    Settings page Drive card uses to show success/error feedback.
    """
    try:
        token = get_setting("gdrive_access_token")
    except KeyError:
        token = ""

    if not token:
        raise HTTPException(
            status_code=400,
            detail="No Google Drive token configured — add it in Settings → Google Drive",
        )

    try:
        result = await _gdrive_sync(token)
        _gdrive_status["last_sync_at"] = datetime.utcnow().isoformat() + "Z"
        _gdrive_status["last_error"]   = None
        return {
            "ok":     True,
            "action": result.get("action"),
            "file_id":   result.get("file_id"),
            "folder_id": result.get("folder_id"),
        }
    except GDriveError as exc:
        _gdrive_status["last_error"] = str(exc)
        raise HTTPException(status_code=502, detail=str(exc))
    except Exception as exc:
        err = f"Unexpected error: {exc}"
        _gdrive_status["last_error"] = err
        log.exception("gdrive: unexpected error on manual sync")
        raise HTTPException(status_code=500, detail=err)


# ---------------------------------------------------------------------------
# POST /api/dev/export-encounters-to-obsidian
# ---------------------------------------------------------------------------

def _slug(text: str) -> str:
    """Convert a string to a lowercase filename-safe slug."""
    import re as _re
    text = text.lower().strip()
    text = _re.sub(r"[^\w\s-]", "", text)
    text = _re.sub(r"[\s_]+", "-", text)
    return text[:60].strip("-")


def _render_suggestions(json_str: str) -> str:
    """Render encounter_suggestions JSON as a readable bullet list."""
    import json as _json
    try:
        data = _json.loads(json_str)
    except Exception:
        return json_str
    lines = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                label = item.get("type") or item.get("category") or ""
                value = item.get("value") or item.get("text") or item.get("suggestion") or str(item)
                lines.append(f"- **{label}:** {value}" if label else f"- {value}")
            else:
                lines.append(f"- {item}")
    elif isinstance(data, dict):
        for k, v in data.items():
            lines.append(f"- **{k}:** {v}")
    return "\n".join(lines) if lines else json_str


def _build_encounter_note(enc, species_name: Optional[str], common_name: Optional[str]) -> str:
    """Return the full markdown body for one encounter."""
    date_str = enc.encounter_date.strftime("%Y-%m-%d") if enc.encounter_date else "unknown-date"

    if common_name:
        title_species = common_name
    elif species_name:
        title_species = species_name
    else:
        title_species = "General observation"

    if enc.latitude is not None and enc.longitude is not None:
        location_str = f"{enc.latitude:.5f}, {enc.longitude:.5f}"
        if enc.location_name:
            location_str = f"{enc.location_name} ({location_str})"
    elif enc.location_name:
        location_str = enc.location_name
    else:
        location_str = "No location recorded"

    if species_name and common_name:
        species_str = f"{common_name} — {species_name}"
    elif species_name:
        species_str = species_name
    else:
        species_str = "Unlinked"

    lines = [
        f"# Encounter — {title_species} — {date_str}",
        "",
        f"**Date:** {date_str}",
        f"**Location:** {location_str}",
        f"**Type:** {enc.encounter_type or 'field'}",
        f"**Species:** {species_str}",
        "",
        "## Notes",
        enc.text_note.strip() if enc.text_note else "No notes recorded",
        "",
        "## Transcript",
        enc.transcript.strip() if enc.transcript else "No transcript",
    ]

    if enc.encounter_suggestions:
        rendered = _render_suggestions(enc.encounter_suggestions)
        if rendered:
            lines += ["", "## Extraction suggestions", rendered]

    lines.append("")  # trailing newline
    return "\n".join(lines)


async def _export_encounters_to_obsidian(since: Optional[datetime] = None) -> dict:
    """
    Write encounter records to ~/Documents/Obsidian/ForagingID/foraging/ as
    dated markdown notes.  Append-only — existing files are never overwritten.

    since: if provided, only encounters with encounter_date >= since are exported.
           Pass None to export all encounters (full history / one-time run).

    Returns {"total", "written", "skipped", "output_dir"}.
    """
    import json as _json
    from sqlalchemy import select as _select
    from app.database import AsyncSessionLocal
    from app.models.encounter import Encounter
    from app.models.species import Species

    obsidian_dir = Path.home() / "Documents" / "Obsidian" / "ForagingID" / "foraging"
    obsidian_dir.mkdir(parents=True, exist_ok=True)

    async with AsyncSessionLocal() as session:
        q = (
            _select(Encounter, Species.scientific_name, Species.common_names)
            .outerjoin(Species, Species.id == Encounter.species_id)
            .order_by(Encounter.encounter_date)
        )
        if since is not None:
            q = q.where(Encounter.encounter_date >= since)
        rows = (await session.execute(q)).all()

    written = 0
    skipped = 0
    total   = len(rows)

    for enc, sci_name, common_names_json in rows:
        common_name: Optional[str] = None
        if common_names_json:
            try:
                names = _json.loads(common_names_json)
                if isinstance(names, list) and names:
                    common_name = names[0]
            except Exception:
                pass

        date_str = enc.encounter_date.strftime("%Y-%m-%d") if enc.encounter_date else "unknown-date"
        file_slug = _slug(sci_name) if sci_name else "observation"

        dest = obsidian_dir / f"{date_str}_{file_slug}.md"
        if dest.exists():
            # Deduplicate same-date same-species with encounter id suffix
            dest = obsidian_dir / f"{date_str}_{file_slug}_{enc.id}.md"
            if dest.exists():
                skipped += 1
                continue

        dest.write_text(
            _build_encounter_note(enc, sci_name, common_name),
            encoding="utf-8",
        )
        written += 1

    return {"total": total, "written": written, "skipped": skipped,
            "output_dir": str(obsidian_dir)}


@router.post("/export-encounters-to-obsidian")
async def export_encounters_to_obsidian():
    """
    One-time export: write all encounters to
    ~/Documents/Obsidian/ForagingID/foraging/ as dated markdown notes.
    Append-only — existing files are skipped.
    """
    result = await _export_encounters_to_obsidian(since=None)
    return {"ok": True, **result}
