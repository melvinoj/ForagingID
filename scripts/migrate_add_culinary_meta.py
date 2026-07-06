"""
Migration: add data-provenance columns to culinary_info table.
  - ai_generated_fields_json TEXT
  - pfaf_retrieved_at DATETIME
  - wikidata_retrieved_at DATETIME

Idempotent — safe to re-run.

Usage:
  python scripts/migrate_add_culinary_meta.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "foragingid.db"


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing = {row[1] for row in cur.execute("PRAGMA table_info(culinary_info)")}

    added = []
    if "ai_generated_fields_json" not in existing:
        cur.execute("ALTER TABLE culinary_info ADD COLUMN ai_generated_fields_json TEXT")
        added.append("ai_generated_fields_json")

    if "pfaf_retrieved_at" not in existing:
        cur.execute("ALTER TABLE culinary_info ADD COLUMN pfaf_retrieved_at DATETIME")
        added.append("pfaf_retrieved_at")

    if "wikidata_retrieved_at" not in existing:
        cur.execute("ALTER TABLE culinary_info ADD COLUMN wikidata_retrieved_at DATETIME")
        added.append("wikidata_retrieved_at")

    conn.commit()
    conn.close()

    if added:
        print(f"Added columns: {', '.join(added)}")
    else:
        print("Nothing to do — columns already exist.")


if __name__ == "__main__":
    migrate()
