"""
Verdict sweep (fix batch 3b, Melvin 20 Oct 2026): draft a proposed edibility
verdict + toxicity severity for every species that has no verdict, or whose
verdict and severity don't fit together — from STORED sources only. Nothing is
set: each draft is one decision for the curator in Review → Edibility Review →
Verdict drafts (POST /api/edibility/verdict-drafts/{id}/approve).

In scope: edibility_status NULL / 'unknown' / 'unclear', or a severity outside
ALLOWED_SEVERITIES for its verdict. Left out: cards with no live observation
that are not reference cards (species_link.species_is_listable_clause — which
also leaves out orphan-marked non-reference cards).

Sources per species (no network; app/services/verdict_drafts.py decides):
  severity    recorded toxic / deadly toxicity_severity (+ its history row)
  human       latest human verdict row in species_edibility_history /
              culinary_info_history
  conditions  curator edibility conditions
  pfaf        latest stored PFAF page, parsed with the app's pfaf._parse
  fungi       stored FAO / Mushroom Observer lookup drafts
Shown as context only (no verdict): curator-authored preparation /
look-alike warnings. Excluded, and said so: Wikidata (its edibility hint is a
family list — no-veto decision), culinary link search hits (not species-specific).

Each draft: species_ai_drafts row, field_name 'edibility_status', model
'verdict_sweep', draft_text = proposed verdict, generation_context_json =
{proposed, evidence, reason, sources (exact quoted text), context, excluded,
at_draft (state the approve path compares), confirmed_pins, superseded}.
Pending FAO/MO lookup drafts of the same species ("no source data", audit
B3-04) are marked 'invalidated' — their text is carried into the new draft.

Idempotent: a species that already has a verdict_sweep draft pending, approved
or rejected is skipped (a rejection is a decision).

Usage (project root):
  python scripts/verdict_sweep_drafts.py [--db PATH]          # dry run (read-only)
  python scripts/verdict_sweep_drafts.py [--db PATH] --apply  # write, then read back by id
Take a Settings snapshot first.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.integrations import pfaf  # noqa: E402
from app.models.species import ALLOWED_SEVERITIES, is_curator_authored  # noqa: E402
from app.services.species_link import listable_species_ids_sql  # noqa: E402
from app.services.verdict_drafts import (FIELD, MODEL, VERDICTS, pfaf_signal, propose,  # noqa: E402
                                         verdict_state)

FUNGI_MODEL = "fao_fungi+mushroom_observer"
DECIDED = ("pending", "approved", "edited_approved", "rejected")


def in_scope(verdict, severity) -> bool:
    v = (verdict or "").strip().lower()
    if v in ("", "unknown", "unclear"):
        return True
    return v in ALLOWED_SEVERITIES and (severity or "") not in ALLOWED_SEVERITIES[v]


def _d(ts):
    return str(ts)[:10] if ts else "?"


def gather(conn, sp) -> tuple:
    """(sources, context, excluded, superseded_ids, at_draft) for one species row."""
    sid = sp["id"]
    sources, context, excluded = [], [], []

    # severity — a recorded toxic / deadly severity
    if sp["toxicity_severity"] in ("toxic", "deadly"):
        h = conn.execute("""SELECT id, old_value, new_value, changed_at, changed_by, note FROM species_edibility_history
                             WHERE species_id = ? AND field = 'toxicity_severity' ORDER BY id DESC LIMIT 1""",
                         (sid,)).fetchone()
        sources.append({
            "source": "severity", "label": "Recorded toxicity severity", "says": "toxic",
            "why": f"toxicity_severity is {sp['toxicity_severity']}"
                   + (f" (set by {h['changed_by']} on {_d(h['changed_at'])})" if h else " (set before history was kept)"),
            "quotes": [{"field": "history note", "text": h["note"]}] if h and h["note"] else [],
            "ref": {"species_edibility_history_id": h["id"] if h else None}})

    # human — the latest human verdict row in either history table
    hum = conn.execute("""
        SELECT 'species_edibility_history' tbl, id, old_value, new_value, changed_at, note FROM species_edibility_history
         WHERE species_id = ? AND field = 'edibility_status' AND changed_by = 'human'
        UNION ALL
        SELECT 'culinary_info_history', h.id, h.old_value, h.new_value, h.changed_at, h.notes
          FROM culinary_info_history h JOIN culinary_info c ON c.id = h.culinary_info_id
         WHERE c.species_id = ? AND h.field_name = 'edibility_status' AND h.changed_by = 'human'
        ORDER BY changed_at DESC LIMIT 1""", (sid, sid)).fetchone()
    if hum:
        v = (hum["new_value"] or "").strip().lower()
        entry = {"source": "human", "label": "Your earlier verdict",
                 "quotes": [{"field": "history note", "text": hum["note"]}] if hum["note"] else [],
                 "ref": {hum["tbl"] + "_id": hum["id"]}}
        if v in VERDICTS and v != "unknown":
            sources.append({**entry, "says": v, "why": f"set to {v} by you on {_d(hum['changed_at'])}"})
        else:
            context.append({**entry, "why": f"you last set it to {v or 'empty'} on {_d(hum['changed_at'])}"})

    # conditions — curator edibility conditions
    conds = conn.execute("""SELECT id, part, preparation, season, safe, notes FROM species_edibility_conditions
                             WHERE species_id = ? ORDER BY id""", (sid,)).fetchall()
    if conds:
        sources.append({
            "source": "conditions", "label": "Your edibility conditions", "says": "caution",
            "why": f"{len(conds)} condition(s) recorded for safe use",
            "quotes": [{"field": f"condition {c['id']}",
                        "text": " · ".join(str(x) for x in (c["part"], c["preparation"], c["season"],
                                                              "safe" if c["safe"] else "not safe", c["notes"]) if x)}
                       for c in conds],
            "ref": {"condition_ids": [c["id"] for c in conds]}})

    # pfaf — latest stored page with content
    src = conn.execute("""SELECT id, source_url, raw_response_json FROM enrichment_sources
                           WHERE species_id = ? AND source_name = 'pfaf' AND length(raw_response_json) > 1000
                           ORDER BY retrieved_at DESC, id DESC LIMIT 1""", (sid,)).fetchone()
    if src:
        r = pfaf._parse(sp["scientific_name"], src["source_url"], src["raw_response_json"])
        s = pfaf_signal({"rating": r.edibility_rating, "hazards": r.preparation_warnings,
                         "edible_uses": r.edible_parts, "url": src["source_url"], "enrichment_source_id": src["id"]},
                        sp["scientific_name"])
        if s:
            sources.append(s)

    # fungi — stored FAO / MO lookups
    superseded = []
    for fd in conn.execute("""SELECT id, status, draft_text FROM species_ai_drafts
                               WHERE species_id = ? AND field_name = ? AND model = ? ORDER BY id""",
                           (sid, FIELD, FUNGI_MODEL)).fetchall():
        m = re.search(r"status=(\w+)", fd["draft_text"] or "")
        st = (m.group(1).lower() if m else None)
        entry = {"source": "fungi", "label": f"Fungi lookup (FAO + Mushroom Observer, draft {fd['id']})",
                 "quotes": [{"field": "lookup", "text": fd["draft_text"]}], "ref": {"draft_id": fd["id"]}}
        if st in VERDICTS and st != "unknown" and "no source data" not in (fd["draft_text"] or ""):
            sources.append({**entry, "says": st, "why": f"lookup returned {st}"})
        else:
            context.append({**entry, "why": "lookup returned no data"})
        if fd["status"] == "pending":
            superseded.append(fd["id"])

    # context — curator-authored warnings (text shown, no verdict drawn from it)
    ci = conn.execute("SELECT id, preparation_warnings, look_alike_warnings FROM culinary_info WHERE species_id = ?",
                      (sid,)).fetchone()
    if ci:
        for field in ("preparation_warnings", "look_alike_warnings"):
            last = conn.execute("""SELECT changed_by, new_value FROM culinary_info_history
                                    WHERE culinary_info_id = ? AND field_name = ?
                                    ORDER BY changed_at DESC, id DESC LIMIT 1""", (ci["id"], field)).fetchone()
            if last and is_curator_authored(last["changed_by"], last["new_value"], ci[field]):
                context.append({"source": "curator_text", "label": f"Your {field.replace('_', ' ')}",
                                "why": "curator-authored text (context only — no verdict drawn from it)",
                                "quotes": [{"field": field, "text": ci[field]}]})

    # excluded — and why
    if conn.execute("SELECT 1 FROM enrichment_sources WHERE species_id = ? AND source_name = 'wikidata' "
                    "AND length(raw_response_json) > 10 LIMIT 1", (sid,)).fetchone():
        excluded.append({"source": "wikidata", "why": "its edibility hint comes from a family list (no-veto decision)"})
    if conn.execute("SELECT 1 FROM enrichment_sources WHERE species_id = ? AND source_name = 'culinary_links' "
                    "AND length(raw_response_json) > 100 LIMIT 1", (sid,)).fetchone():
        excluded.append({"source": "culinary_links", "why": "link search hits, not species-specific"})

    last_seh = conn.execute("SELECT max(id) FROM species_edibility_history WHERE species_id = ?", (sid,)).fetchone()[0]
    last_cih = conn.execute("""SELECT max(h.id) FROM culinary_info_history h JOIN culinary_info c ON c.id = h.culinary_info_id
                                WHERE c.species_id = ? AND h.field_name = 'edibility_status'""", (sid,)).fetchone()[0]

    class _Sp:                                 # verdict_state reads attributes
        edibility_status = sp["edibility_status"]
        toxicity_severity = sp["toxicity_severity"]
        edibility_verified = sp["edibility_verified"]
        edibility_verified_by = sp["edibility_verified_by"]
    return sources, context, excluded, superseded, verdict_state(_Sp, last_seh, last_cih)


def plan(conn):
    pins = dict(conn.execute("""SELECT species_id, count(*) FROM observations
                                 WHERE species_id IS NOT NULL AND review_status IN ('approved','manually_verified')
                                   AND identification_status = 'identified' AND latitude IS NOT NULL
                                 GROUP BY species_id""").fetchall())
    items, skipped = [], Counter()
    # Live observation OR reference card — the shared predicate (species_link), not a copy.
    listable = {r[0] for r in conn.execute(listable_species_ids_sql()).fetchall()}
    for sp in conn.execute("""SELECT id, scientific_name, kingdom, edibility_status, toxicity_severity,
                                     edibility_verified, edibility_verified_by, orphaned_at
                                FROM species ORDER BY scientific_name""").fetchall():
        if not in_scope(sp["edibility_status"], sp["toxicity_severity"]):
            continue
        if sp["id"] not in listable:
            skipped["no live observation and not a reference card"
                    + (" (orphan-marked)" if sp["orphaned_at"] else "")] += 1
            continue
        prior = conn.execute(f"""SELECT id, status FROM species_ai_drafts WHERE species_id = ? AND field_name = ?
                                   AND model = ? AND status IN ({','.join('?' * len(DECIDED))})""",
                             (sp["id"], FIELD, MODEL, *DECIDED)).fetchall()
        if prior:
            skipped[f"verdict draft already {prior[0]['status']}"] += 1
            continue
        sources, context, excluded, superseded, at_draft = gather(conn, sp)
        prop = propose(sp["toxicity_severity"], sources)
        items.append({
            "species_id": sp["id"], "scientific_name": sp["scientific_name"], "pins": pins.get(sp["id"], 0),
            "proposal": prop, "superseded": superseded,
            "context": {
                "kind": "verdict", "batch": "3b", "queued_by": "scripts/verdict_sweep_drafts.py",
                "proposed": {"edibility_status": prop["edibility_status"],
                             "toxicity_severity": prop["toxicity_severity"]},
                "evidence": prop["evidence"], "reason": prop["reason"],
                "sources": sources, "context": context, "excluded": excluded,
                "at_draft": at_draft, "confirmed_pins": pins.get(sp["id"], 0),
                "kingdom": sp["kingdom"], "superseded_draft_ids": superseded or None,
            }})
    return items, skipped


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=str(PROJECT_ROOT / "data" / "foragingid.db"))
    ap.add_argument("--apply", action="store_true", help="write the drafts (default: dry run)")
    ap.add_argument("--show", type=int, default=0, help="print N full drafts")
    args = ap.parse_args(argv)
    conn = sqlite3.connect(f"file:{args.db}" + ("" if args.apply else "?mode=ro"), uri=True, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 30000")

    items, skipped = plan(conn)
    by_verdict = Counter(i["proposal"]["edibility_status"] for i in items)
    by_evidence = Counter(i["proposal"]["evidence"] for i in items)
    lacking = by_evidence["thin"] + by_evidence["conflict"]
    print(f"{'APPLY' if args.apply else 'DRY RUN'} — {args.db}")
    print(f"Drafts to create: {len(items)}; skipped: {dict(skipped)}")
    print(f"  by proposed verdict: {dict(by_verdict)}")
    print(f"  by evidence: {dict(by_evidence)} — lacking enough evidence (thin + conflict): {lacking}")
    print(f"  with confirmed map pins: {sum(1 for i in items if i['pins'])}; "
          f"superseded fungi lookup drafts: {sum(len(i['superseded']) for i in items)}")
    for i in sorted(items, key=lambda x: (x["proposal"]["evidence"] in ("thin",), -x["pins"], x["scientific_name"])):
        p = i["proposal"]
        if p["evidence"] != "thin":
            print(f"  {i['species_id']:>4} {i['scientific_name']:<32} pins {i['pins']:>3}  → {p['edibility_status']:<8}"
                  f" / {p['toxicity_severity']:<8} [{p['evidence']}] {p['reason'][:150]}")
    for i in items[: args.show]:
        print(json.dumps(i["context"], ensure_ascii=False, indent=1)[:4000])
    if not args.apply:
        print("Dry run — nothing written.")
        return

    now = datetime.utcnow().isoformat(sep=" ")
    ids, invalidated = [], []
    with conn:                                      # one transaction
        for i in items:
            cur = conn.execute(
                # approved_by: the column is NOT NULL and defaults to 'human' (audit
                # B3-03 — reads as a human approval that never happened); the
                # approve endpoint sets 'human' when the curator decides.
                """INSERT INTO species_ai_drafts (species_id, field_name, draft_text, status, generated_at,
                                                  generation_context_json, model, approved_by)
                   VALUES (?, ?, ?, 'pending', ?, ?, ?, 'system:verdict_sweep')""",
                (i["species_id"], FIELD, i["proposal"]["edibility_status"], now,
                 json.dumps(i["context"], ensure_ascii=False), MODEL))
            ids.append(cur.lastrowid)
            for did in i["superseded"]:
                c2 = conn.execute("UPDATE species_ai_drafts SET status = 'invalidated' WHERE id = ? AND status = 'pending'",
                                  (did,))
                if c2.rowcount == 1:
                    invalidated.append(did)

    # Read back every written row by id — every field.
    bad = 0
    for did, i in zip(ids, items):
        r = conn.execute("SELECT * FROM species_ai_drafts WHERE id = ?", (did,)).fetchone()
        ctx = json.loads(r["generation_context_json"])
        ok = (r["species_id"] == i["species_id"] and r["field_name"] == FIELD and r["model"] == MODEL
              and r["status"] == "pending" and r["draft_text"] == i["proposal"]["edibility_status"]
              and ctx == i["context"])
        bad += not ok
        print(("OK " if ok else "BAD"), r["id"], r["species_id"], i["scientific_name"], r["draft_text"],
              ctx["proposed"]["toxicity_severity"], ctx["evidence"], r["status"], r["generated_at"])
    for did in invalidated:
        r = conn.execute("SELECT id, species_id, field_name, status, model FROM species_ai_drafts WHERE id = ?",
                         (did,)).fetchone()
        bad += r["status"] != "invalidated"
        print("SUPERSEDED", dict(r))
    print(f"Written: {len(ids)} drafts, ids {ids[0] if ids else '-'}–{ids[-1] if ids else '-'}; "
          f"invalidated fungi lookups: {invalidated}; read-back mismatches: {bad}")


if __name__ == "__main__":
    main()
