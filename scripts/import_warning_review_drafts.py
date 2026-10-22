"""
Queue every species' unreviewed warning text for curator review — preparation
and look-alike warnings, every verdict (batch 1 / audit D3-01 did caution
preparation warnings only, 20 Oct 2026; widened 21 Oct 2026, Melvin). Was
scripts/import_caution_warning_drafts.py.

Creates pending species_ai_drafts rows, field_name='preparation_warnings' or
'look_alike_warnings' (both CURATOR_DRAFT_FIELDS fields: approving one writes
culinary_info + a history row changed_by='human', which is what every surface
reads as curator-authored — the "not yet reviewed" label goes). The draft's
`model` column records where the text came from:

  pfaf            PFAF Known Hazards, parsed offline from the stored PFAF page
                  (enrichment_sources) with the app's own pfaf._parse — no
                  network. Preparation warnings only (PFAF has no look-alikes).
  unknown_origin  text already in the field, no history row, no PFAF warning:
                  queued as-is so the curator approves, rewrites or removes it.
  marker_confirm  E-14: the field's human-lock row holds a marker string, not
                  the text — the curator confirms the current text is theirs.

When the field already shows text that differs from PFAF's, the field text is
queued (unknown_origin) and PFAF's text goes into the context as pfaf_text
(Melvin, 21 Oct 2026: approving as-is never replaces what the species shows).

Never queued: fields whose current text is already curator-authored, any other
field with a human history row, "None known" / empty fields. Text is copied
verbatim — never generated or edited here.

Species: live cards only (species_has_live_observation — not orphan-marked and
a non-rejected observation points at it), as the verdict queue; --include-orphans
also takes orphan / reference cards.

Idempotent per (species, field): a pending / approved / edited_approved /
rejected draft queued by this script (model in ORIGINS) is skipped — a
rejection is a decision; it is not re-queued. The six text-less 'approved' rows
of 24 Jun (model='human', ids 2296–2301, written with the E-14 marker rows) are
not decisions on any text and do not count; their ids go into the context.

Usage (from the project root):
  python scripts/import_warning_review_drafts.py [--db PATH]          # dry run (read-only)
  python scripts/import_warning_review_drafts.py [--db PATH] --apply  # write, then read back by id
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

from sqlalchemy import create_engine, select  # noqa: E402

from app.integrations import pfaf  # noqa: E402
from app.models.species import Species, is_curator_authored, is_placeholder_marker  # noqa: E402
from app.services.species_link import species_has_live_observation_clause  # noqa: E402

FIELDS = ("preparation_warnings", "look_alike_warnings")
MARKER = "(human-authored preparation_warnings)"      # E-14 marker string (one of the markers)
DECIDED = ("pending", "approved", "edited_approved", "rejected")
ORIGINS = ("pfaf", "unknown_origin", "marker_confirm")   # the `model` values this script writes


def _text(t):
    """Field text, or None when empty or PFAF's 'None known' (= no data)."""
    t = (t or "").strip()
    return None if not t or t.lower() == "none known" else t


def classify(current, history, pfaf_warning):
    """(origin | None, draft_text | None, reason).
    history: [(changed_by, new_value), ...] for this field, newest first.
    pfaf_warning: PFAF Known Hazards text (None for look-alike warnings)."""
    human = [h for h in history if h[0] == "human"]
    if human:
        if is_curator_authored(history[0][0], history[0][1], current):
            return None, None, "curator-authored already (publishable)"
        if _text(current) and any(is_placeholder_marker(h[1]) for h in human):
            return "marker_confirm", current, "E-14 marker row — confirm the text is yours"
        return None, None, "human history row that is not the current text — left alone"
    pf = _text(pfaf_warning)
    cur = _text(current)
    if pf:
        # 21 Oct 2026 (Melvin, Frangula alnus): the card queues the text the
        # species shows now. When PFAF says something else, PFAF's text goes
        # into the draft context only — "Approve as-is" never silently replaces
        # what is shown.
        if cur and " ".join(cur.split()) != " ".join(pf.split()):
            return "unknown_origin", current, "text in the field differs from PFAF — field text queued"
        return "pfaf", pf, "PFAF Known Hazards"
    if cur:
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


def live_species_ids(db_path) -> set:
    """species_has_live_observation, the app's own clause (read-only engine)."""
    eng = create_engine(f"sqlite:///file:{db_path}?mode=ro&uri=true")
    try:
        with eng.connect() as c:
            return {r[0] for r in c.execute(select(Species.id).where(species_has_live_observation_clause()))}
    finally:
        eng.dispose()


def plan(conn, live=None):
    """One item per (species, field) that has text or a marker row. live: a set
    of species ids to restrict to (None = every card)."""
    rows = conn.execute(
        """SELECT s.id sid, s.scientific_name sci, s.edibility_status edib, ci.id ciid,
                  ci.preparation_warnings, ci.look_alike_warnings
             FROM species s JOIN culinary_info ci ON ci.species_id = s.id
            ORDER BY s.scientific_name""").fetchall()
    out = []
    for r in rows:
        if live is not None and r["sid"] not in live:
            continue
        for field in FIELDS:
            hist = conn.execute(
                """SELECT id, changed_by, new_value FROM culinary_info_history
                    WHERE culinary_info_id = ? AND field_name = ?
                    ORDER BY changed_at DESC, id DESC""", (r["ciid"], field)).fetchall()
            if not _text(r[field]) and not hist:
                continue
            pf, src = _pfaf_warning(conn, r["sid"], r["sci"]) if field == "preparation_warnings" else (None, None)
            origin, text, reason = classify(r[field], [(h["changed_by"], h["new_value"]) for h in hist], pf)
            existing = conn.execute(
                f"""SELECT id, status FROM species_ai_drafts WHERE species_id = ? AND field_name = ?
                      AND status IN ({",".join("?" * len(DECIDED))})
                      AND model IN ({",".join("?" * len(ORIGINS))}) ORDER BY id""",
                (r["sid"], field, *DECIDED, *ORIGINS)).fetchall()
            legacy = [d[0] for d in conn.execute(
                """SELECT id FROM species_ai_drafts WHERE species_id = ? AND field_name = ?
                      AND (model IS NULL OR model NOT IN (?, ?, ?)) ORDER BY id""",
                (r["sid"], field, *ORIGINS))]
            if origin and existing:
                reason = f"already queued/decided: draft {', '.join(f'{e[0]} {e[1]}' for e in existing)}"
                origin, text = None, None
            context = None
            if origin:
                context = {
                    "origin": origin, "audit": "D3-01", "queued_by": "scripts/import_warning_review_drafts.py",
                    "field_text_at_import": r[field],
                    "enrichment_source_id": src["id"] if (src and pf) else None,
                    "source_url": src["source_url"] if (src and pf) else None,
                    "pfaf_text": pf if (pf and origin != "pfaf") else None,
                    "marker_history_ids": [h["id"] for h in hist if is_placeholder_marker(h["new_value"])] or None,
                    "legacy_draft_ids": legacy or None,
                }
            out.append({"species_id": r["sid"], "scientific_name": r["sci"], "edibility_status": r["edib"],
                        "field": field, "origin": origin, "draft_text": text, "reason": reason,
                        "context": context,
                        "same_as_field": bool(text) and " ".join((r[field] or "").split()) == " ".join(text.split())})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=str(PROJECT_ROOT / "data" / "foragingid.db"))
    ap.add_argument("--apply", action="store_true", help="write the drafts (default: dry run)")
    ap.add_argument("--include-orphans", action="store_true", help="also orphan / reference cards")
    args = ap.parse_args(argv)

    uri = f"file:{args.db}" + ("" if args.apply else "?mode=ro")
    conn = sqlite3.connect(uri, uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")

    items = plan(conn, None if args.include_orphans else live_species_ids(args.db))
    queued = [i for i in items if i["origin"]]
    print(f"{'APPLY' if args.apply else 'DRY RUN'} — {args.db}")
    print(f"Fields considered: {len(items)} ({'every card' if args.include_orphans else 'live cards'}, both warning fields)")
    reasons = Counter((i["field"], f"QUEUE {i['origin']}" if i["origin"] else
                       "already queued/decided" if i["reason"].startswith("already queued") else i["reason"])
                      for i in items)
    for (f, why), n in sorted(reasons.items()):
        print(f"  {f:<21} {n:>4}  {why}")
    for i in items:
        if not i["origin"]:
            continue
        extra = f" len {len(i['draft_text'])}" + (" (= field)" if i["same_as_field"] else " (≠ field)")
        print(f"  QUEUE {i['origin']:<14} {i['species_id']:>4} {i['scientific_name']:<30} "
              f"{i['edibility_status'] or '-':<9} {i['field']}{extra}")
    print(f"To queue: {len(queued)} — " + ", ".join(
        f"{k[0]}/{k[1]}/{k[2]} {v}" for k, v in sorted(Counter(
            (i["field"], i["edibility_status"], i["origin"]) for i in queued).items())))

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
                (i["species_id"], i["field"], i["draft_text"], now,
                 json.dumps(i["context"], ensure_ascii=False), i["origin"]))
            ids.append(cur.lastrowid)
    print(f"Written: {len(ids)} drafts, ids {ids[0]}–{ids[-1]}" if ids else "Written: 0 drafts")

    # Read-back by id — every field.
    for did in ids:
        row = conn.execute("SELECT * FROM species_ai_drafts WHERE id = ?", (did,)).fetchone()
        print(json.dumps(dict(row), ensure_ascii=False))


if __name__ == "__main__":
    main()
