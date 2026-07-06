"""
Migration: add prefilter_category column to observations table.
Idempotent — safe to re-run.

Usage:
  python scripts/migrate_add_prefilter_category.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "foragingid.db"


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing = {row[1] for row in cur.execute("PRAGMA table_info(observations)")}

    added = []
    if "prefilter_category" not in existing:
        cur.execute(
            "ALTER TABLE observations ADD COLUMN prefilter_category VARCHAR(30)"
        )
        added.append("prefilter_category")

    conn.commit()
    conn.close()

    if added:
        print(f"Added columns: {', '.join(added)}")
    else:
        print("Nothing to do — column already exists.")


if __name__ == "__main__":
    migrate()
