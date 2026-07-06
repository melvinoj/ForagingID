"""
Fix 1 data repair — restore observations that were incorrectly demoted from
confirmed (approved/manually_verified) to needs_review by audit "send-to-review"
actions triggered for SPECIES-METADATA reasons (missing common name, edibility
uncategorised, recipe-bank hygiene, AI-draft provenance) — none of which relate
to whether the observation's identification is correct.

Observations that have ANY genuine identification concern (low confidence,
non-plant prefilter, single-source/two-source rule, human-correction anomaly)
are LEFT in needs_review.

Each restored observation:
  - review_status -> its prior confirmed status (from the audit log)
  - the reversed [Audit] note lines are stripped; other notes preserved
  - an ObservationEdit row is logged (edited_by='system:fix1_restore')

Idempotent: only touches rows currently in needs_review that match the metadata
filter and were ever confirmed. Re-running after restore is a no-op.
"""
import sqlite3
import sys
from datetime import datetime

DB = "data/foragingid.db"

LEGIT_MARKERS = [
    "low confidence score",
    "no_plant_signal",
    "two-source agreement",
    "single API source",
    "does not appear in the original API candidates",
]
METADATA_MARKERS = [
    "no common name",
    "edibility",
    "recipe bank",
    "approved recipe",
    "culinary enrichment",
    "no corresponding approved",
    "test audit send",
]


def has_marker(notes, markers):
    n = (notes or "")
    return any(m in n for m in markers)


def strip_metadata_note_lines(notes):
    """Remove [Audit] lines that match a metadata marker; keep everything else."""
    if not notes:
        return notes
    kept = []
    for line in notes.split("\n"):
        is_audit = "[Audit]" in line
        if is_audit and any(m in line for m in METADATA_MARKERS):
            continue  # drop the reversed demotion note
        kept.append(line)
    return "\n".join(kept).strip() or None


def main(apply_changes):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    # ever-confirmed set
    cur.execute("""
        SELECT DISTINCT observation_id FROM observation_edits
        WHERE field_name='review_status' AND new_value IN ('approved','manually_verified')
    """)
    ever_conf = {r[0] for r in cur.fetchall()}

    # prior confirmed status per obs (latest confirmed edit)
    cur.execute("""
        SELECT observation_id, new_value, edited_at, id FROM observation_edits
        WHERE field_name='review_status' AND new_value IN ('approved','manually_verified')
        ORDER BY edited_at ASC, id ASC
    """)
    prior_status = {}
    for r in cur.fetchall():
        prior_status[r["observation_id"]] = r["new_value"]  # last wins = latest

    # candidate rows
    cur.execute("""
        SELECT id, review_status, reviewer_notes FROM observations
        WHERE review_status='needs_review'
    """)
    rows = cur.fetchall()

    restored = []
    now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")

    for r in rows:
        oid = r["id"]
        if oid not in ever_conf:
            continue
        notes = r["reviewer_notes"]
        if has_marker(notes, LEGIT_MARKERS):
            continue  # genuine ID concern — keep in review
        if not has_marker(notes, METADATA_MARKERS):
            continue  # not a metadata demotion — leave alone
        target = prior_status.get(oid, "approved")
        new_notes = strip_metadata_note_lines(notes)
        restored.append((oid, target, new_notes))

    print(f"Will restore {len(restored)} observations")
    by_target = {}
    for _, t, _ in restored:
        by_target[t] = by_target.get(t, 0) + 1
    print("  by target status:", by_target)

    if not apply_changes:
        print("DRY RUN — no changes written. Pass --apply to commit.")
        for oid, t, _ in restored[:10]:
            print(f"   #{oid} -> {t}")
        con.close()
        return

    for oid, target, new_notes in restored:
        cur.execute(
            "UPDATE observations SET review_status=?, reviewer_notes=?, updated_at=? WHERE id=?",
            (target, new_notes, now, oid),
        )
        cur.execute(
            """INSERT INTO observation_edits
               (observation_id, field_name, old_value, new_value, edited_at, edited_by)
               VALUES (?, 'review_status', 'needs_review', ?, ?, 'system:fix1_restore')""",
            (oid, target, now),
        )
    con.commit()
    print(f"Committed. Restored {len(restored)} observations.")
    con.close()


if __name__ == "__main__":
    main("--apply" in sys.argv)
