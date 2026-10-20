"""
Put each CONFIRMED observation's own species at the front of its candidate cache
(fix batch 14, audit B1-08, 21 Oct 2026).

Until batch 14 confirm/correct only stripped the moved-off name, so on confirmed
rows candidates[0] could be another species — and the review card %, its
"Also:" line, the map pin's confidence and top_score read candidates[0] /
top_score. New species changes now go through
app.services.species_link.confirmed_candidate_first(); this applies the same
function to the rows confirmed before the fix.

Scope: review_status approved / manually_verified, species_primary set, not a
landscape row, and candidates[0] is NOT already that species (by name_key) —
including rows with no candidates at all. Rows whose front is already right are
left exactly as they are.

Per row: species_candidates_json and top_score, each with an observation_edits
row (old and new value, edited_by 'backfill:B1-08'). The UPDATE is guarded on
both old values, so a row changed since the read is skipped, not overwritten.

Usage (project root):
  python scripts/backfill_confirmed_candidate_first.py [--db PATH]          # dry run
  python scripts/backfill_confirmed_candidate_first.py [--db PATH] --apply  # write + read back by id
Take a Settings snapshot first.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.models.observation import Observation  # noqa: E402
from app.services.species_link import confirmed_candidate_first  # noqa: E402
from app.services.taxonomy import normalize_taxon_key  # noqa: E402

EDITED_BY = "backfill:B1-08"

SELECT = """
SELECT id, species_primary, species_candidates_json, top_score
  FROM observations
 WHERE review_status IN ('approved', 'manually_verified')
   AND species_primary IS NOT NULL AND species_primary != ''
   AND COALESCE(obs_category, 'plant') != 'landscape'
 ORDER BY id"""


def plan(conn):
    out, kinds = [], Counter()
    for oid, sp, cj, ts in conn.execute(SELECT).fetchall():
        try:
            cands = json.loads(cj) if cj else []
        except (ValueError, TypeError):
            kinds["malformed_json_skipped"] += 1
            continue
        if cands and isinstance(cands, list) and isinstance(cands[0], dict) \
                and normalize_taxon_key(cands[0].get("scientific_name") or "") == normalize_taxon_key(sp):
            kinds["front_already_right"] += 1
            continue
        obs = Observation(species_primary=sp, species_candidates_json=cj, top_score=ts)
        confirmed_candidate_first(obs)
        new_c = json.loads(obs.species_candidates_json)
        if not cands:
            kind = "no_candidates"
        elif new_c[0].get("source") == "curator" and len(new_c) == len(cands) + 1:
            kind = "not_listed_by_any_api"
        else:
            kind = "listed_not_first"
        kinds[kind] += 1
        out.append((oid, sp, cj, ts, obs.species_candidates_json, obs.top_score, kind))
    return out, kinds


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(PROJECT_ROOT / "data" / "foragingid.db"))
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    conn = sqlite3.connect(f"file:{args.db}" + ("" if args.apply else "?mode=ro"), uri=True, timeout=30)
    conn.execute("PRAGMA busy_timeout = 30000")

    rows, kinds = plan(conn)
    print(f"{'APPLY' if args.apply else 'DRY RUN'} — {args.db}: {len(rows)} confirmed rows to fix; {dict(kinds)}")
    ts_changes = Counter(("None" if r[5] is None else "score") + (" (was None)" if r[3] is None else "")
                         for r in rows)
    print(f"  new top_score: {dict(ts_changes)}")
    if not args.apply:
        show = [r for r in rows if r[0] == 24353] + rows[:12]
        for oid, sp, cj, ts, nj, nts, kind in show:
            old0 = (json.loads(cj)[0].get("scientific_name") if cj and json.loads(cj) else None)
            print(f"  {oid:>6} {kind:<22} {sp:<32} front {old0!r} -> {json.loads(nj)[0]['scientific_name']!r}"
                  f"  top_score {ts} -> {nts}")
        print("Dry run — nothing written.")
        return

    now = datetime.utcnow().isoformat(sep=" ")
    written, skipped, edit_ids = [], [], []
    with conn:
        for oid, sp, cj, ts, nj, nts, kind in rows:
            cur = conn.execute(
                "UPDATE observations SET species_candidates_json = ?, top_score = ? "
                "WHERE id = ? AND species_candidates_json IS ? AND top_score IS ? AND species_primary = ?",
                (nj, nts, oid, cj, ts, sp))
            if cur.rowcount != 1:
                skipped.append(oid)
                continue
            for field, old, new in (("species_candidates_json", cj, nj), ("top_score", ts, nts)):
                if old == new:
                    continue
                e = conn.execute(
                    "INSERT INTO observation_edits (observation_id, field_name, old_value, new_value, "
                    "edited_at, edited_by) VALUES (?, ?, ?, ?, ?, ?)",
                    (oid, field, None if old is None else str(old), None if new is None else str(new),
                     now, EDITED_BY))
                edit_ids.append(e.lastrowid)
            written.append((oid, sp, nj, nts))

    # Read back every written row by id — every field this touched.
    bad = 0
    for oid, sp, nj, nts in written:
        r = conn.execute("SELECT id, species_primary, review_status, species_candidates_json, top_score "
                         "FROM observations WHERE id = ?", (oid,)).fetchone()
        front = json.loads(r[3])[0]
        ok = (r[1] == sp and r[3] == nj and r[4] == nts
              and normalize_taxon_key(front["scientific_name"]) == normalize_taxon_key(sp))
        bad += not ok
        print(("OK " if ok else "BAD"), r[0], r[1], r[2], f"front={front['scientific_name']!r}",
              f"score={front.get('score')}", f"top_score={r[4]}")
    edits = conn.execute(f"SELECT COUNT(*) FROM observation_edits WHERE id IN ({','.join('?' * len(edit_ids))})",
                         edit_ids).fetchone()[0] if edit_ids else 0
    print(f"Written: {len(written)} rows; skipped (changed since read): {skipped}; "
          f"observation_edits ids {edit_ids[0] if edit_ids else '-'}–{edit_ids[-1] if edit_ids else '-'} "
          f"({edits} rows); read-back mismatches: {bad}")


if __name__ == "__main__":
    main()
