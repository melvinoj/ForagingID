"""
recipe_fields_backfill.py — title / summary / recipe_type for the Recipes page
(Melvin, 25 Oct 2026). Dry run by default: lists every proposal, writes nothing.

  title        only where empty, and only when it comes from a real heading
               (recipe_display_title / recipe_title_source == 'heading'). A
               title that would be a first prose sentence is NOT written: it is
               listed as "needs a title" (the page still shows the same display
               fallback — the export's rule — until the curator types one).
  summary      only where empty: recipe_summary_line (first sentence of the
               body, safety lines skipped, ~120 chars).
  recipe_type  only where NULL: propose_recipe_type (title keywords; exactly one
               type, else left NULL = "Other").

Never overwrites a value that is already set. Approved and needs_review rows;
archived rows are left alone.

  python scripts/recipe_fields_backfill.py                 # dry run → report
  python scripts/recipe_fields_backfill.py --apply         # after a snapshot
"""
import argparse
import os
import sqlite3
import sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.models.species import (is_safety_note_line, propose_recipe_type,  # noqa: E402
                                recipe_display_title, recipe_summary_line, recipe_title_source)

DB = os.path.join(os.path.dirname(__file__), "..", "data", "foragingid.db")


def proposals(conn):
    # Before migration 0059 the dry run still works: missing columns read as empty.
    cols = {r[1] for r in conn.execute("PRAGMA table_info(species_recipes)")}
    summ = "r.summary" if "summary" in cols else "NULL"
    rtyp = "r.recipe_type" if "recipe_type" in cols else "NULL"
    rows = conn.execute(
        f"SELECT r.id, r.title, r.body, {summ}, {rtyp}, r.season, r.status, s.scientific_name "
        "FROM species_recipes r JOIN species s ON s.id = r.species_id "
        "WHERE r.status IN ('approved', 'needs_review') ORDER BY r.id").fetchall()
    out = []
    for rid, title, body, summary, rtype, season, status, sci in rows:
        has_title = bool((title or "").strip())
        src = recipe_title_source(title, body)
        shown = recipe_display_title(title, body) or None
        new_title = shown if (not has_title and src == "heading") else None
        eff_title = shown
        new_summary = None if (summary or "").strip() else (recipe_summary_line(eff_title, body) or None)
        new_type = None if rtype else propose_recipe_type(eff_title)
        out.append({"id": rid, "species": sci, "status": status, "season": season,
                    "title": title, "new_title": new_title, "new_summary": new_summary,
                    "new_type": new_type, "eff_title": eff_title, "title_source": src,
                    "title_is_safety_line": bool(eff_title) and is_safety_note_line(eff_title)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--db", default=DB)
    args = ap.parse_args()
    conn = sqlite3.connect(args.db if args.apply else f"file:{args.db}?mode=ro", uri=not args.apply)
    props = proposals(conn)
    t = [p for p in props if p["new_title"]]
    s = [p for p in props if p["new_summary"]]
    ty = Counter(p["new_type"] or "(none → Other)" for p in props)
    print(f"Recipes considered: {len(props)}")
    print(f"Titles proposed from a heading (empty today): {len(t)}; "
          f"needs a title (only a prose sentence — not written): "
          f"{sum(1 for p in props if p['title_source'] == 'line')}; no usable line: "
          f"{sum(1 for p in props if not p['eff_title'])}")
    print(f"Summaries proposed: {len(s)}; none found: {sum(1 for p in props if not p['new_summary'])}")
    print("Types proposed:", dict(ty))
    print(f"Titles that are a safety line (must be 0): {sum(p['title_is_safety_line'] for p in props)}")
    print("\n| id | species | season | title (→ proposed) | type | summary |")
    print("|---|---|---|---|---|---|")
    for p in props:
        tt = (p["title"] or "") if not p["new_title"] else f"→ {p['new_title']}"
        if p["title_source"] == "line":
            tt = f"NEEDS A TITLE (shown meanwhile: {p['eff_title']})"
        print(f"| {p['id']} | {p['species']} | {p['season']} | {tt.replace('|', '/')} | "
              f"{p['new_type'] or '—'} | {(p['new_summary'] or '—').replace('|', '/')} |")
    if not args.apply:
        print("\nDry run — nothing written.")
        return
    # Each column only while it is still empty (never overwrites a curator edit
    # made between the dry run and the write).
    guard = {"title": "(title IS NULL OR trim(title) = '')",
             "summary": "(summary IS NULL OR trim(summary) = '')",
             "recipe_type": "recipe_type IS NULL"}
    n = 0
    for p in props:
        wrote = False
        for col, key in (("title", "new_title"), ("summary", "new_summary"), ("recipe_type", "new_type")):
            if p[key]:
                cur = conn.execute(f"UPDATE species_recipes SET {col} = ? WHERE id = ? AND {guard[col]}",
                                   (p[key], p["id"]))
                wrote = wrote or cur.rowcount > 0
        n += wrote
    conn.commit()
    print(f"\nWritten: {n} recipe rows.")


if __name__ == "__main__":
    main()
