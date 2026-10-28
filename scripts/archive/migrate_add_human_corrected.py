"""
Migration: add human_corrected column to observations table.
Idempotent — safe to re-run.

Usage:
  python scripts/migrate_add_human_corrected.py
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "foragingid.db"


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing = {row[1] for row in cur.execute("PRAGMA table_info(observations)")}

    added = []
    if "human_corrected" not in existing:
        cur.execute(
            "ALTER TABLE observations ADD COLUMN human_corrected BOOLEAN NOT NULL DEFAULT 0"
        )
        added.append("human_corrected")

    conn.commit()
    conn.close()

    if added:
        print(f"Added columns: {', '.join(added)}")
    else:
        print("Nothing to do — columns already exist.")


if __name__ == "__main__":
    migrate()
