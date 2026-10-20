"""
db_snapshot.py — WAL-safe DB snapshot and restore (audit E-01 / E-02, fix batch 2).

The live DB runs in WAL mode: committed transactions can sit in
foragingid.db-wal for a while before a checkpoint moves them into the main
file. So:

  - A file copy of foragingid.db (the old shutil.copy2 snapshot) can miss
    committed rows (E-01).
  - A file copy OVER foragingid.db while the server holds connections is
    undone by the WAL the server still has (E-02).

Both go through SQLite's online backup API instead:

  snapshot   live ──backup──▶ <dest>.partial  → journal_mode=DELETE → quick_check
             → os.replace to <dest>. The backup reads one consistent state that
             includes the WAL. The snapshot is a plain rollback-journal file
             (opens read-only anywhere, no -wal/-shm). A partial file never
             carries a snapshot name.

  restore    1. the snapshot passes integrity_check (opened immutable — it is
                never written)
             2. the caller has refused while a background job runs, and taken
                a pre-restore snapshot (dev.py) — so the restore can be undone
             3. snapshot ──backup──▶ live, through a normal connection to the
                live file. SQLite writes the pages through the live pager as one
                write transaction: under WAL it lands in the WAL like any other
                commit, open connections see the restored state on their next
                read, and there is no older WAL left to replay over it. Server
                writers wait on busy_timeout while it runs.
             4. journal_mode is WAL again, wal_checkpoint(TRUNCATE) (best
                effort), quick_check on the live file.

Pure, synchronous functions on paths — dev.py runs them in a thread; the tests
run them on throw-away WAL databases.
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from typing import Optional

BUSY_TIMEOUT_MS = 30000

# Snapshot files the restore endpoint accepts: snapshots/db_<name>.sqlite (the files
# list_snapshots shows — timestamped ones and named ones like db_pre_review_label_backfill).
SNAPSHOT_NAME_RE = re.compile(r"^db_[A-Za-z0-9_-]+\.sqlite$")
# Git commits the restore endpoint accepts (hex only — never an option or ref).
COMMIT_HASH_RE = re.compile(r"^[0-9a-f]{7,40}$")


class SnapshotError(RuntimeError):
    """The snapshot or restore cannot be done safely — nothing was changed."""


def _check(conn: sqlite3.Connection, pragma: str) -> str:
    rows = conn.execute(f"PRAGMA {pragma}").fetchall()
    return "ok" if rows == [("ok",)] else "; ".join(str(r[0]) for r in rows[:5])


def backup_to_file(src_path: Path, dest_path: Path) -> dict:
    """Consistent snapshot of src_path (WAL included) at dest_path. Raises SnapshotError."""
    src_path, dest_path = Path(src_path), Path(dest_path)
    if dest_path.exists():
        raise SnapshotError(f"snapshot already exists: {dest_path.name}")
    tmp = dest_path.with_name(dest_path.name + ".partial")
    tmp.unlink(missing_ok=True)
    src = sqlite3.connect(str(src_path), timeout=BUSY_TIMEOUT_MS / 1000)
    try:
        dst = sqlite3.connect(str(tmp))
        try:
            src.backup(dst)                                  # one step: one consistent read
            dst.execute("PRAGMA journal_mode=DELETE")        # plain file: no -wal/-shm needed to read it
            qc = _check(dst, "quick_check")
            rows_hint = dst.execute("SELECT count(*) FROM sqlite_master").fetchone()[0]
        finally:
            dst.close()
    except sqlite3.Error as exc:
        tmp.unlink(missing_ok=True)
        raise SnapshotError(f"backup failed: {exc}") from exc
    finally:
        src.close()
    if qc != "ok":
        tmp.unlink(missing_ok=True)
        raise SnapshotError(f"snapshot quick_check failed: {qc}")
    os.replace(tmp, dest_path)
    return {"path": str(dest_path), "bytes": dest_path.stat().st_size, "quick_check": qc,
            "schema_objects": rows_hint}


def open_snapshot_readonly(path: Path) -> sqlite3.Connection:
    """Snapshots are never written: immutable=1 needs no -shm, so it also opens
    pre-batch-2 snapshots (shutil.copy2 of a WAL file — WAL header, no -wal)."""
    return sqlite3.connect(f"file:{Path(path)}?immutable=1", uri=True)


def snapshot_info(path: Path) -> dict:
    """integrity_check + alembic revision of a snapshot file (read-only)."""
    conn = open_snapshot_readonly(path)
    try:
        try:
            integ = _check(conn, "integrity_check")
        except sqlite3.DatabaseError as exc:                 # malformed / not a database at all
            return {"integrity_check": f"unreadable: {exc}", "alembic_revision": None}
        try:
            rev = conn.execute("SELECT version_num FROM alembic_version").fetchone()
            rev = rev[0] if rev else None
        except sqlite3.Error:
            rev = None
        return {"integrity_check": integ, "alembic_revision": rev}
    finally:
        conn.close()


def restore_from_file(snap_path: Path, live_path: Path) -> dict:
    """Replace live_path's content with snap_path's, through the backup API.
    Raises SnapshotError (live DB untouched) if the snapshot fails integrity_check."""
    snap_path, live_path = Path(snap_path), Path(live_path)
    info = snapshot_info(snap_path)
    if info["integrity_check"] != "ok":
        raise SnapshotError(f"snapshot integrity_check failed: {info['integrity_check']}")
    src = open_snapshot_readonly(snap_path)
    try:
        live = sqlite3.connect(str(live_path), timeout=BUSY_TIMEOUT_MS / 1000)
        try:
            live.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            mode_before = live.execute("PRAGMA journal_mode").fetchone()[0]
            src.backup(live)                                 # one write transaction on the live DB
            mode = live.execute("PRAGMA journal_mode").fetchone()[0]
            if mode_before == "wal" and mode != "wal":
                mode = live.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            try:
                ckpt = live.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            except sqlite3.Error as exc:                     # best effort: readers may hold the WAL
                ckpt = f"skipped: {exc}"
            qc = _check(live, "quick_check")
        finally:
            live.close()
    except sqlite3.Error as exc:
        raise SnapshotError(f"restore failed: {exc}") from exc
    finally:
        src.close()
    return {"snapshot": str(snap_path), "snapshot_alembic_revision": info["alembic_revision"],
            "journal_mode": mode, "wal_checkpoint": list(ckpt) if isinstance(ckpt, tuple) else ckpt,
            "live_quick_check": qc}


def validate_snapshot_path(raw: str, snapshots_dir: Path) -> Path:
    """The restore endpoint's db_path: an existing db_*.sqlite file directly in
    snapshots_dir (no other file can be copied over the DB). Raises ValueError."""
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = Path(snapshots_dir) / p
    p = p.resolve()
    if p.parent != Path(snapshots_dir).resolve():
        raise ValueError("db_path must be a file in snapshots/")
    if not SNAPSHOT_NAME_RE.match(p.name):
        raise ValueError("db_path must be a snapshots/db_*.sqlite file")
    if not p.is_file():
        raise ValueError(f"snapshot not found: {p.name}")
    return p


def validate_commit_hash(raw: Optional[str]) -> str:
    h = (raw or "").strip().lower()
    if not COMMIT_HASH_RE.match(h):
        raise ValueError("commit_hash must be 7–40 hex characters")
    return h
