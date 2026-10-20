"""
Queue caution species' preparation warnings for curator review (audit D3-01,
fix pass batch 1; Melvin 20 Oct 2026 — option C, B as fallback).

Creates pending species_ai_drafts rows, field_name='preparation_warnings'
(a CURATOR_DRAFT_FIELDS field: approving one writes culinary_info + a history
row changed_by='human', which is what the experience gates read as
curator-authored). The draft's `model` column records where the text came from:

  pfaf            PFAF Known Hazards, parsed offline from the stored PFAF page
                  (enrichment_sources) with the app's own pfaf._parse — no network.
  unknown_origin  text already in the field, no history row, no PFAF warning:
                  queued as-is so the curator approves, rewrites or rejects it.
  marker_confirm  E-14: the field's human-lock row holds a marker string, not
                  the text — the curator confirms the current text is theirs.

Never queued: fields whose current text is already curator-authored, any other
field with a human history row, "None known" / empty fields (no text anywhere
→ recipes stay withheld until the curator writes a warning). Text is copied
verbatim — never generated or edited here.

Idempotent: a species with a pending / approved / edited_approved / rejected
draft queued by THIS script (model in ORIGINS) is skipped — a rejection is a
decision; it is not re-queued. The six text-less 'approved' rows of 24 Jun
(model='human', ids 2296–2301, written with the E-14 marker rows) are not
decisions on any text and do not count; their ids go into the context.

Usage (from the project root):
  python scripts/import_caution_warning_drafts.py [--db PATH]          # dry run (read-only)
  python scripts/import_caution_warning_drafts.py [--db PATH] --apply  # write, then read back by id
Take a snapshot first (Write Protocol) — this script does not.
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

from app.integrations import pfaf  # noqa: E402
from app.models.species import is_curator_authored  # noqa: E402

FIELD = "preparation_warnings"
MARKER = "(human-authored preparation_warnings)"      # E-14 marker string
DECIDED = ("pending", "approved", "edited_approved", "rejected")
ORIGINS = ("pfaf", "unknown_origin", "marker_confirm")   # the `model` values this script writes


def _text(t):
    """Field text, or None when empty or PFAF's 'None known' (= no data)."""
    t = (t or "").strip()
    return None if not t or t.lower() == "none known" else t


def classify(current, history, pfaf_warning):
    """(origin | None, draft_text | None, reason).
    history: [(changed_by, new_value), ...] for this field, newest first."""
    human = [h for h in history if h[0] == "human"]
    if human:
        if is_curator_authored(history[0][0], history[0][1], current):
            return None, None, "curator-authored already (publishable)"
        if _text(current) and any((h[1] or "").strip() == MARKER for h in human):
            return "marker_confirm", current, "E-14 marker row — confirm the text is yours"
        return None, None, "human history row that is not the current text — left alone"
    pf = _text(pfaf_warning)
    if pf:
        return "pfaf", pf, "PFAF Known Hazards"
    if _text(current):
        if history:
            return None, None, "machine text with a non-human history row — not queued"
        return "unknown_origin", current, "text in the field, origin unknown"
    return None, None, "no warning text anywhere"


def _pfaf_warning(conn, sid, sci):
    src = conn.execute(
        """SELECT id, source_url, raw_response_json FROM enrichment_sources
            WHERE species_id = ? AND source_name = 'pfaf'
            ORDER BY retrieved_at DESC, id DESC LIMIT 1""", (sid,)).fetchone()
    if not src or not src["raw_response_json"]:
        return None, None
    return pfaf._parse(sci, src["source_url"], src["raw_response_json"]).preparation_warnings, src


def plan(conn):
    rows = conn.execute(
        """SELECT s.id sid, s.scientific_name sci, s.edibility_status edib,
                  ci.id ciid, ci.preparation_warnings pw
             FROM species s LEFT JOIN culinary_info ci ON ci.species_id = s.id
            WHERE s.edibility_status = 'caution'
               OR ci.id IN (SELECT culinary_info_id FROM culinary_info_history
                             WHERE field_name = ? AND changed_by = 'human' AND new_value = ?)
            ORDER BY s.scientific_name""", (FIELD, MARKER)).fetchall()
    out = []
    for r in rows:
        hist = conn.execute(
            """SELECT id, changed_by, new_value FROM culinary_info_history
                WHERE culinary_info_id = ? AND field_name = ?
                ORDER BY changed_at DESC, id DESC""", (r["ciid"], FIELD)).fetchall() if r["ciid"] else []
        pf, src = _pfaf_warning(conn, r["sid"], r["sci"])
        origin, text, reason = classify(r["pw"], [(h["changed_by"], h["new_value"]) for h in hist], pf)
        existing = conn.execute(
            f"""SELECT id, status FROM species_ai_drafts WHERE species_id = ? AND field_name = ?
                  AND status IN ({",".join("?" * len(DECIDED))})
                  AND model IN ({",".join("?" * len(ORIGINS))}) ORDER BY id""",
            (r["sid"], FIELD, *DECIDED, *ORIGINS)).fetchall()
        legacy = [d[0] for d in conn.execute(
            """SELECT id FROM species_ai_drafts WHERE species_id = ? AND field_name = ?
                  AND (model IS NULL OR model NOT IN (?, ?, ?)) ORDER BY id""",
            (r["sid"], FIELD, *ORIGINS))]
        if origin and existing:
            reason = f"already queued/decided: draft {', '.join(f'{e[0]} {e[1]}' for e in existing)}"
            origin, text = None, None
        context = None
        if origin:
            context = {
                "origin": origin, "audit": "D3-01", "queued_by": "scripts/import_caution_warning_drafts.py",
                "field_text_at_import": r["pw"],
                "enrichment_source_id": src["id"] if (origin == "pfaf" and src) else None,
                "source_url": src["source_url"] if (origin == "pfaf" and src) else None,
                "marker_history_ids": [h["id"] for h in hist if (h["new_value"] or "").strip() == MARKER] or None,
                "legacy_draft_ids": legacy or None,
            }
        out.append({"species_id": r["sid"], "scientific_name": r["sci"], "edibility_status": r["edib"],
                    "origin": origin, "draft_text": text, "reason": reason, "context": context,
                    "same_as_field": bool(text) and " ".join((r["pw"] or "").split()) == " ".join(text.split())})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=str(PROJECT_ROOT / "data" / "foragingid.db"))
    ap.add_argument("--apply", action="store_true", help="write the drafts (default: dry run)")
    args = ap.parse_args(argv)

    uri = f"file:{args.db}" + ("" if args.apply else "?mode=ro")
    conn = sqlite3.connect(uri, uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")

    items = plan(conn)
    queued = [i for i in items if i["origin"]]
    print(f"{'APPLY' if args.apply else 'DRY RUN'} — {args.db}")
    print(f"Species considered: {len(items)} (caution, plus any with an E-14 marker row)")
    print("Reasons:", dict(Counter(i["reason"] if not i["origin"] else f"QUEUE {i['origin']}" for i in items)))
    for i in items:
        tag = f"QUEUE {i['origin']:<14}" if i["origin"] else "skip                "
        extra = (f" len {len(i['draft_text'])}" + (" (= field)" if i["same_as_field"] else " (≠ field)")) if i["origin"] else ""
        print(f"  {tag} {i['species_id']:>4} {i['scientific_name']:<30} {i['reason']}{extra}")
    print(f"To queue: {len(queued)} — " + ", ".join(f"{k} {v}" for k, v in Counter(i["origin"] for i in queued).items()))

    if not args.apply:
        print("Dry run — nothing written.")
        return

    now = datetime.utcnow().isoformat(sep=" ")
    ids = []
    with conn:                                   # one transaction
        for i in queued:
            cur = conn.execute(
                """INSERT INTO species_ai_drafts
                       (species_id, field_name, draft_text, status, generated_at,
                        generation_context_json, model)
                   VALUES (?, ?, ?, 'pending', ?, ?, ?)""",
                (i["species_id"], FIELD, i["draft_text"], now,
                 json.dumps(i["context"], ensure_ascii=False), i["origin"]))
            ids.append(cur.lastrowid)
    print(f"Written: {len(ids)} drafts, ids {ids[0]}–{ids[-1]}" if ids else "Written: 0 drafts")

    # Read-back by id — every field.
    for did in ids:
        row = conn.execute("SELECT * FROM species_ai_drafts WHERE id = ?", (did,)).fetchone()
        print(json.dumps(dict(row), ensure_ascii=False))


if __name__ == "__main__":
    main()
