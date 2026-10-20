"""
Tests for app/services/db_snapshot.py — WAL-safe snapshot and restore (audit
E-01 / E-02, fix batch 2, 20 Oct 2026). Every test uses a throw-away WAL DB in
a temp directory, with a connection held open the way the server's pool holds
one, and wal_autocheckpoint=0 so committed rows stay in the -wal file.

Run from project root:  python -m pytest tests/test_db_snapshot.py -v
Or standalone:          python tests/test_db_snapshot.py
"""

import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.db_snapshot import (  # noqa: E402
    SnapshotError, backup_to_file, restore_from_file, snapshot_info,
    validate_commit_hash, validate_snapshot_path,
)


def _wal_db(d: Path, n: int):
    """live.db in WAL mode with n committed rows still in the WAL; returns the open connection."""
    conn = sqlite3.connect(str(d / "live.db"))
    assert conn.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    conn.execute("PRAGMA wal_autocheckpoint=0")
    conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT)")
    conn.executemany("INSERT INTO t (v) VALUES (?)", [(f"r{i}",) for i in range(n)])
    conn.commit()
    assert (d / "live.db-wal").stat().st_size > 0
    return conn


def _count(path: Path) -> int:
    c = sqlite3.connect(str(path))
    try:
        return c.execute("SELECT count(*) FROM t").fetchone()[0]
    finally:
        c.close()


def _tmp():
    return Path(tempfile.mkdtemp(prefix="snaptest_"))


# ── E-01: snapshot ───────────────────────────────────────────────────────────

def test_old_file_copy_misses_wal_rows():
    """The bug being fixed: copying the main file loses rows still in the WAL."""
    d = _tmp()
    live = _wal_db(d, 50)
    shutil.copy2(d / "live.db", d / "copy.db")
    c = sqlite3.connect(f"file:{d / 'copy.db'}?immutable=1", uri=True)
    assert c.execute("SELECT count(*) FROM sqlite_master WHERE name='t'").fetchone()[0] == 0
    c.close(); live.close()


def test_snapshot_contains_rows_committed_in_wal():
    d = _tmp()
    live = _wal_db(d, 50)
    info = backup_to_file(d / "live.db", d / "db_20261020_120000.sqlite")
    assert info["quick_check"] == "ok"
    assert _count(d / "db_20261020_120000.sqlite") == 50
    live.close()


def test_snapshot_is_plain_file_readable_readonly():
    d = _tmp()
    live = _wal_db(d, 5)
    snap = d / "db_20261020_120000.sqlite"
    backup_to_file(d / "live.db", snap)
    c = sqlite3.connect(f"file:{snap}?mode=ro", uri=True)        # failed for copy2 snapshots of a WAL DB
    assert c.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    assert c.execute("SELECT count(*) FROM t").fetchone()[0] == 5
    c.close(); live.close()
    assert not (d / "db_20261020_120000.sqlite-wal").exists()
    assert sorted(f.name for f in d.iterdir() if f.name.startswith("db_")) == ["db_20261020_120000.sqlite"]


def test_snapshot_sees_rows_committed_by_another_open_connection():
    d = _tmp()
    live = _wal_db(d, 10)
    other = sqlite3.connect(str(d / "live.db"))
    other.executemany("INSERT INTO t (v) VALUES (?)", [("x",)] * 7)
    other.commit()
    backup_to_file(d / "live.db", d / "db_20261020_120001.sqlite")
    assert _count(d / "db_20261020_120001.sqlite") == 17
    other.close(); live.close()


def test_snapshot_never_overwrites_an_existing_file():
    d = _tmp()
    live = _wal_db(d, 3)
    snap = d / "db_20261020_120000.sqlite"
    backup_to_file(d / "live.db", snap)
    try:
        backup_to_file(d / "live.db", snap)
    except SnapshotError:
        live.close()
        return
    raise AssertionError("second snapshot to the same name must raise")


# ── E-02: restore ────────────────────────────────────────────────────────────

def _restore_setup(d: Path):
    """Snapshot at 2,000 rows, then 3,000 inserts + deletes left in the WAL (the audit's reproduction)."""
    live = _wal_db(d, 2000)
    snap = d / "db_20261020_130000.sqlite"
    backup_to_file(d / "live.db", snap)
    live.executemany("INSERT INTO t (v) VALUES (?)", [("later",)] * 3000)
    live.execute("DELETE FROM t WHERE id % 3 = 0")
    live.commit()
    assert live.execute("SELECT count(*) FROM t").fetchone()[0] != 2000
    return live, snap


def test_restore_sticks_for_open_connections_and_after_reopen():
    d = _tmp()
    live, snap = _restore_setup(d)
    res = restore_from_file(snap, d / "live.db")
    assert res["live_quick_check"] == "ok" and res["journal_mode"] == "wal"
    # the connection that was open throughout (the server's pool) sees the restored state
    assert live.execute("SELECT count(*) FROM t").fetchone()[0] == 2000
    assert live.execute("SELECT count(*) FROM t WHERE v='later'").fetchone()[0] == 0
    live.close()
    # and so does a fresh open of the file after every connection closed (no WAL replay undoes it)
    assert _count(d / "live.db") == 2000
    c = sqlite3.connect(str(d / "live.db"))
    assert c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert c.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    c.close()


def test_old_file_copy_restore_is_undone_by_wal():
    """The bug being fixed: copying a snapshot over the live file while a connection is open."""
    d = _tmp()
    live, snap = _restore_setup(d)
    n_before = live.execute("SELECT count(*) FROM t").fetchone()[0]
    shutil.copy2(snap, d / "live.db")
    assert live.execute("SELECT count(*) FROM t").fetchone()[0] == n_before   # restore had no effect
    live.close()


def test_writes_after_restore_persist():
    d = _tmp()
    live, snap = _restore_setup(d)
    restore_from_file(snap, d / "live.db")
    live.execute("INSERT INTO t (v) VALUES ('after')")
    live.commit()
    live.close()
    assert _count(d / "live.db") == 2001


def test_restore_from_pre_batch2_copy_snapshot():
    """Old snapshots are copy2 files of a WAL DB (WAL header, no -wal): still restorable."""
    d = _tmp()
    live = _wal_db(d, 40)
    live.execute("PRAGMA wal_checkpoint(TRUNCATE)")          # old copies were good only when checkpointed
    shutil.copy2(d / "live.db", d / "db_20260628_000000.sqlite")
    live.executemany("INSERT INTO t (v) VALUES (?)", [("later",)] * 25)
    live.commit()
    restore_from_file(d / "db_20260628_000000.sqlite", d / "live.db")
    assert live.execute("SELECT count(*) FROM t").fetchone()[0] == 40
    live.close()
    assert _count(d / "live.db") == 40


def test_restore_refuses_a_corrupt_snapshot_and_leaves_live_untouched():
    d = _tmp()
    live = _wal_db(d, 12)
    bad = d / "db_20261020_140000.sqlite"
    backup_to_file(d / "live.db", bad)
    page = sqlite3.connect(str(bad)).execute("PRAGMA page_size").fetchone()[0]
    with open(bad, "r+b") as fh:                            # break page 2's b-tree header (table t's root)
        fh.seek(page)
        fh.write(b"\x0d\xff\xff\xff\xff\xff\xff\xff")
    assert snapshot_info(bad)["integrity_check"] != "ok"
    try:
        restore_from_file(bad, d / "live.db")
    except SnapshotError:
        pass
    else:
        raise AssertionError("corrupt snapshot must be refused")
    assert live.execute("SELECT count(*) FROM t").fetchone()[0] == 12
    live.close()


def test_restore_refuses_a_non_database_file():
    d = _tmp()
    live = _wal_db(d, 4)
    junk = d / "db_20261020_150000.sqlite"
    junk.write_bytes(b"not a database" * 100)
    try:
        restore_from_file(junk, d / "live.db")
    except SnapshotError:
        assert live.execute("SELECT count(*) FROM t").fetchone()[0] == 4
        live.close()
        return
    raise AssertionError("a non-database file must be refused")


# ── restore endpoint input checks ────────────────────────────────────────────

def test_validate_snapshot_path():
    d = _tmp()
    snaps = d / "snapshots"
    snaps.mkdir()
    (snaps / "db_20261020_120000.sqlite").write_bytes(b"x")
    (snaps / "db_pre_review_label_backfill.sqlite").write_bytes(b"x")
    (snaps / "manual_20261020_120000.db").write_bytes(b"x")
    (d / "db_20261020_120000.sqlite").write_bytes(b"x")              # right name, wrong folder
    assert validate_snapshot_path(str(snaps / "db_20261020_120000.sqlite"), snaps).name == "db_20261020_120000.sqlite"
    assert validate_snapshot_path("db_pre_review_label_backfill.sqlite", snaps).parent == snaps.resolve()
    for raw in (str(d / "db_20261020_120000.sqlite"),                 # outside snapshots/
                str(snaps / ".." / "db_20261020_120000.sqlite"),      # traversal
                str(snaps / "manual_20261020_120000.db"),             # not a db_*.sqlite name
                "/etc/passwd",
                str(snaps / "db_20991231_000000.sqlite")):            # does not exist
        try:
            validate_snapshot_path(raw, snaps)
        except ValueError:
            continue
        raise AssertionError(f"accepted {raw}")


def test_validate_commit_hash():
    assert validate_commit_hash("db9b955e") == "db9b955e"
    assert validate_commit_hash("A" * 40) == "a" * 40
    for raw in ("", None, "abc", "--orphan", "main", "HEAD~1", "db9b955e; rm -rf /", "g" * 8, "a" * 41):
        try:
            validate_commit_hash(raw)
        except ValueError:
            continue
        raise AssertionError(f"accepted {raw!r}")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
