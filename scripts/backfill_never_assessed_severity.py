"""
Mark never-assessed species as toxicity_severity='unknown' (fix batch 3, audit
B2-02 / P2, 20 Oct 2026).

Until batch 3 no app code wrote toxicity_severity: its default 'none' read as
"known safe" to every culinary gate (culinary_allowed), so a species with NO
verdict was treated as assessed-safe. This sets 'unknown' — fails closed —
where nothing says the species was ever assessed:

  edibility_status NULL / 'unknown' / 'unclear'
  AND toxicity_severity = 'none'
  AND no species_edibility_history row for toxicity_severity by a human

Species WITH a verdict keep their severity (edible/caution 'none' is consistent
with the verdict; inedible is left for the curator — B2-06). One history row
per change (field toxicity_severity, changed_by 'system:never_assessed').
Batch 3b's verdict sweep resolves these through review drafts.

Usage (project root):
  python scripts/backfill_never_assessed_severity.py [--db PATH]          # dry run
  python scripts/backfill_never_assessed_severity.py [--db PATH] --apply  # write + read back by id
Take a Settings snapshot first.
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOTE = "never assessed: no verdict, severity was the 'none' default (fix batch 3, B2-02)"

SELECT = """
SELECT s.id, s.scientific_name, s.edibility_status, s.toxicity_severity
  FROM species s
 WHERE (s.edibility_status IS NULL OR s.edibility_status IN ('unknown', 'unclear'))
   AND s.toxicity_severity = 'none'
   AND NOT EXISTS (SELECT 1 FROM species_edibility_history h
                    WHERE h.species_id = s.id AND h.field = 'toxicity_severity' AND h.changed_by = 'human')
 ORDER BY s.id"""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(PROJECT_ROOT / "data" / "foragingid.db"))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    conn = sqlite3.connect(f"file:{args.db}" + ("" if args.apply else "?mode=ro"), uri=True, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")
    rows = conn.execute(SELECT).fetchall()
    by = {}
    for r in rows:
        by[r[2]] = by.get(r[2], 0) + 1
    print(f"{'APPLY' if args.apply else 'DRY RUN'} — {args.db}: {len(rows)} species to mark 'unknown' "
          f"(by verdict: {by})")
    if not args.apply:
        for r in rows[:15]:
            print(f"  {r[0]:>4} {r[1]:<34} verdict={r[2]!r}")
        print("  …" if len(rows) > 15 else "", "Dry run — nothing written.")
        return
    now = datetime.utcnow().isoformat(sep=" ")
    hist_ids = []
    with conn:
        for sid, _sci, _st, _sev in rows:
            cur = conn.execute("UPDATE species SET toxicity_severity = 'unknown' "
                               "WHERE id = ? AND toxicity_severity = 'none'", (sid,))
            assert cur.rowcount == 1, sid
            h = conn.execute("INSERT INTO species_edibility_history (species_id, field, old_value, new_value, "
                             "changed_at, changed_by, note) VALUES (?, 'toxicity_severity', 'none', 'unknown', ?, "
                             "'system:never_assessed', ?)", (sid, now, NOTE))
            hist_ids.append(h.lastrowid)
    # Read back every row by id.
    bad = 0
    for (sid, sci, st, _), hid in zip(rows, hist_ids):
        sp = conn.execute("SELECT id, scientific_name, edibility_status, toxicity_severity FROM species WHERE id=?",
                          (sid,)).fetchone()
        h = conn.execute("SELECT id, species_id, field, old_value, new_value, changed_at, changed_by, note "
                         "FROM species_edibility_history WHERE id=?", (hid,)).fetchone()
        ok = sp[3] == "unknown" and sp[2] == st and h[1] == sid and h[3:5] == ("none", "unknown")
        bad += not ok
        print(("OK " if ok else "BAD"), sp, h)
    print(f"Written: {len(rows)} species, history ids {hist_ids[0] if hist_ids else '-'}–"
          f"{hist_ids[-1] if hist_ids else '-'}; read-back mismatches: {bad}")


if __name__ == "__main__":
    main()
