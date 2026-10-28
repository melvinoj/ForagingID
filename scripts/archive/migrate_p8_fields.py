#!/usr/bin/env python3
"""
Phase 8 — idempotent migration.

Adds to culinary_info:
  id_notes, id_notes_sources_json, inat_retrieved_at, trompenburg_retrieved_at,
  culinary_links_json, culinary_links_retrieved_at,
  taste_notes, medicinal_notes, recipe, ai_approved_fields_json

Creates new table:
  species_ai_drafts

Safe to run multiple times — skips columns / tables that already exist.

Usage:
    python scripts/migrate_p8_fields.py
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "foragingid.db"

# Columns to add to culinary_info: (column_name, sql_type)
CULINARY_INFO_COLUMNS = [
    ("id_notes",                    "TEXT"),
    ("id_notes_sources_json",       "TEXT"),
    ("inat_retrieved_at",           "DATETIME"),
    ("trompenburg_retrieved_at",    "DATETIME"),
    ("culinary_links_json",         "TEXT"),
    ("culinary_links_retrieved_at", "DATETIME"),
    ("taste_notes",                 "TEXT"),
    ("medicinal_notes",             "TEXT"),
    ("recipe",                      "TEXT"),
    ("ai_approved_fields_json",     "TEXT"),
]

CREATE_AI_DRAFTS = """
CREATE TABLE IF NOT EXISTS species_ai_drafts (
    id                      INTEGER PRIMARY KEY,
    species_id              INTEGER NOT NULL REFERENCES species(id),
    field_name              VARCHAR(50) NOT NULL,
    draft_text              TEXT,
    status                  VARCHAR(30) NOT NULL DEFAULT 'pending',
    generated_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    approved_at             DATETIME,
    approved_by             VARCHAR(100) NOT NULL DEFAULT 'human',
    final_text              TEXT,
    generation_context_json TEXT,
    model                   VARCHAR(80)
)
"""

CREATE_AI_DRAFTS_IDX = """
CREATE INDEX IF NOT EXISTS ix_species_ai_drafts_species_id
    ON species_ai_drafts(species_id)
"""

CREATE_AI_DRAFTS_STATUS_IDX = """
CREATE INDEX IF NOT EXISTS ix_species_ai_drafts_status
    ON species_ai_drafts(status)
"""


def _existing_columns(cur: sqlite3.Cursor, table: str) -> set:
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def main() -> None:
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        print("Run the app once (uvicorn app.main:app) to initialise the DB, then re-run this script.")
        sys.exit(1)

    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()

    # ── culinary_info columns ──────────────────────────────────────────────
    existing = _existing_columns(cur, "culinary_info")
    added = []
    for col, sql_type in CULINARY_INFO_COLUMNS:
        if col not in existing:
            cur.execute(f"ALTER TABLE culinary_info ADD COLUMN {col} {sql_type}")
            added.append(col)

    if added:
        print(f"culinary_info: added {len(added)} column(s): {', '.join(added)}")
    else:
        print("culinary_info: all Phase 8 columns already present — skipped")

    # ── species_ai_drafts table ────────────────────────────────────────────
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='species_ai_drafts'")
    if cur.fetchone():
        print("species_ai_drafts: table already exists — skipped")
    else:
        cur.execute(CREATE_AI_DRAFTS)
        cur.execute(CREATE_AI_DRAFTS_IDX)
        cur.execute(CREATE_AI_DRAFTS_STATUS_IDX)
        print("species_ai_drafts: table created with indexes")

    con.commit()
    con.close()
    print("\nMigration complete.")


if __name__ == "__main__":
    main()
