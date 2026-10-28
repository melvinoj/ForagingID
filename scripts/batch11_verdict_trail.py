"""
Audit batch 11 — verdict trail data (Melvin's decisions, 25 Oct 2026).

  4. B2-08: the 13 species with edibility_status NULL → 'unknown' (severity
     'unknown' where not already), one species_edibility_history row each:
     old_value NULL, changed_by 'system:never_assessed'.
  5. B2-07 locks:
     - 583 Allium cepa: confirmed by Melvin → edibility_verified_by 'human',
       verdict unchanged, history row changed_by 'human'.
     - 148 Luffa aegyptiaca, 149 Cynodon dactylon: lock cleared
       (edibility_verified 0, edibility_verified_by NULL), verdict unchanged,
       history rows noting the unlock (changed_by 'human' — Melvin's decision).
  6. C-06: every species with a verdict (not NULL/unknown) and no verdict
     history row in either table → one row: old_value NULL, new_value = the
     current verdict, changed_by 'origin_unknown'. No past value is invented.

Dry run by default (prints every row it would write). --apply takes a
snapshot through the SQLite backup API (snapshots/db_<local ts>.sqlite, no git
commit), refuses if the planned rows differ from --expect counts, writes in one
transaction, then reads every written row back by id.

Run:  ~/foragingid-venv/bin/python scripts/batch11_verdict_trail.py [--apply --expect 13,3,60]
"""
import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.services import db_snapshot  # noqa: E402

DB = ROOT / "data" / "foragingid.db"
NULL_IDS = [491, 685, 855, 862, 863, 864, 865, 866, 867, 868, 869, 870, 877]
CONFIRM_ID = 583
UNLOCK_IDS = [148, 149]
NOTE_NEVER = "audit B2-08 (batch 11): card created with no verdict; never assessed"
NOTE_CONFIRM = "Melvin 25 Oct 2026: lock confirmed (audit B2-07; was 'auto')"
NOTE_UNLOCK = "Melvin 25 Oct 2026: lock cleared — machine provenance, not human-confirmed (audit B2-07)"
NOTE_ORIGIN = "audit C-06 (batch 11): verdict predates the history trail; origin unknown"

C06_SQL = """
SELECT s.id, s.scientific_name, s.edibility_status FROM species s
 WHERE s.edibility_status IS NOT NULL AND s.edibility_status != 'unknown'
   AND s.edibility_status NOT LIKE '\\_merged\\_into:%' ESCAPE '\\'
   AND NOT EXISTS (SELECT 1 FROM species_edibility_history e
                    WHERE e.species_id = s.id AND e.field = 'edibility_status')
   AND NOT EXISTS (SELECT 1 FROM culinary_info ci JOIN culinary_info_history h ON h.culinary_info_id = ci.id
                    WHERE ci.species_id = s.id AND h.field_name = 'edibility_status')
 ORDER BY s.id"""


def plan(con):
    """(species updates, history rows) — every write, nothing yet written."""
    ups, hist = [], []
    q = lambda sql, *a: con.execute(sql, a).fetchall()
    # 4. NULL verdicts
    for sid, name, status, sev in q(f"SELECT id, scientific_name, edibility_status, toxicity_severity FROM species "
                                    f"WHERE id IN ({','.join('?' * len(NULL_IDS))}) ORDER BY id", *NULL_IDS):
        if status is not None:
            continue
        ups.append((sid, name, {"edibility_status": "unknown",
                                **({} if sev == "unknown" else {"toxicity_severity": "unknown"})}))
        hist.append((sid, "edibility_status", None, "unknown", "system:never_assessed", NOTE_NEVER))
        if sev != "unknown":
            hist.append((sid, "toxicity_severity", sev, "unknown", "system:never_assessed", NOTE_NEVER))
    # 5. locks
    (sid, name, v, by), = q("SELECT id, scientific_name, edibility_verified, edibility_verified_by FROM species "
                            "WHERE id = ?", CONFIRM_ID)
    if v and by != "human":
        ups.append((sid, name, {"edibility_verified_by": "human"}))
        hist.append((sid, "edibility_verified_by", by, "human", "human", NOTE_CONFIRM))
    for sid, name, v, by in q("SELECT id, scientific_name, edibility_verified, edibility_verified_by FROM species "
                              "WHERE id IN (?, ?) ORDER BY id", *UNLOCK_IDS):
        if not v and by is None:
            continue
        ups.append((sid, name, {"edibility_verified": 0, "edibility_verified_by": None}))
        if v:
            hist.append((sid, "edibility_verified", "1", "0", "human", NOTE_UNLOCK))
        if by is not None:
            hist.append((sid, "edibility_verified_by", by, None, "human", NOTE_UNLOCK))
    # 6. C-06
    c06 = q(C06_SQL)
    for sid, name, status in c06:
        hist.append((sid, "edibility_status", None, status, "origin_unknown", NOTE_ORIGIN))
    return ups, hist, c06


def counts(ups, hist, c06):
    return (sum(1 for _, _, f in ups if "edibility_status" in f),
            sum(1 for _, _, f in ups if "edibility_status" not in f),
            len(c06))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--expect", help="null,locks,c06 counts the dry run showed, e.g. 13,3,60")
    a = ap.parse_args()

    con = sqlite3.connect(DB)
    ups, hist, c06 = plan(con)
    print("Species updates:")
    for sid, name, f in ups:
        print(f"  {sid:>4} {name:<34} {f}")
    print(f"History rows ({len(hist)}):")
    for h in hist:
        print(f"  {h[0]:>4} {h[1]:<22} {h[2]!r:>22} → {h[3]!r:<12} {h[4]}")
    n = counts(ups, hist, c06)
    print(f"Counts: NULL→unknown {n[0]}, lock changes {n[1]}, C-06 origin_unknown {n[2]}")
    if not a.apply:
        print("Dry run — nothing written.")
        return
    want = tuple(int(x) for x in (a.expect or "").split(","))
    if want != n:
        sys.exit(f"Refusing: planned {n}, expected {want}")
    con.close()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")            # local, like every snapshot filename
    snap = ROOT / "snapshots" / f"db_{ts}.sqlite"
    info = db_snapshot.backup_to_file(DB, snap)
    print(f"Snapshot: {snap.name} {info}")

    con = sqlite3.connect(DB, timeout=30)
    con.execute("BEGIN IMMEDIATE")
    ups2, hist2, c062 = plan(con)                             # re-plan inside the write lock
    if (ups2, hist2) != (ups, hist):
        con.rollback()
        sys.exit("Refusing: the data changed between the dry run and the write")
    now = datetime.utcnow().isoformat(sep=" ")               # DB audit columns are UTC
    for sid, _, f in ups:
        cols = ", ".join(f"{k} = ?" for k in f)
        cur = con.execute(f"UPDATE species SET {cols} WHERE id = ?", (*f.values(), sid))
        assert cur.rowcount == 1, sid
    ids = []
    for sid, field, old, new, by, note in hist:
        cur = con.execute("INSERT INTO species_edibility_history (species_id, field, old_value, new_value, "
                          "changed_at, changed_by, note) VALUES (?,?,?,?,?,?,?)",
                          (sid, field, old, new, now, by, note))
        ids.append(cur.lastrowid)
    con.commit()

    # Read back by id — every field written.
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    bad = 0
    print("Read-back species:")
    for sid, name, f in ups:
        row = con.execute(f"SELECT id, scientific_name, edibility_status, toxicity_severity, edibility_verified, "
                          f"edibility_verified_by FROM species WHERE id = ?", (sid,)).fetchone()
        got = dict(zip(("id", "scientific_name", "edibility_status", "toxicity_severity", "edibility_verified",
                        "edibility_verified_by"), row))
        ok = all(got[k] == v for k, v in f.items())
        bad += not ok
        print(f"  {'ok ' if ok else 'BAD'} {got}")
    print(f"Read-back history rows {ids[0]}–{ids[-1]}:")
    for hid, h in zip(ids, hist):
        row = con.execute("SELECT species_id, field, old_value, new_value, changed_by, note, changed_at "
                          "FROM species_edibility_history WHERE id = ?", (hid,)).fetchone()
        ok = row is not None and row[:6] == h
        bad += not ok
        print(f"  {'ok ' if ok else 'BAD'} {hid} {row}")
    left = con.execute(C06_SQL).fetchall()
    nulls = con.execute("SELECT count(*) FROM species WHERE edibility_status IS NULL").fetchone()[0]
    print(f"After: NULL verdicts {nulls}; verdicts with no history row {len(left)}; mismatches {bad}")
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
