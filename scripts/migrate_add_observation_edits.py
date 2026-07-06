"""
Migration: create observation_edits audit table.
Idempotent — safe to re-run.

Usage:
  python scripts/migrate_add_observation_edits.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "foragingid.db"


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing_tables = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    if "observation_edits" not in existing_tables:
        cur.execute("""
            CREATE TABLE observation_edits (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                observation_id INTEGER NOT NULL
                    REFERENCES observations(id) ON DELETE CASCADE,
                field_name  TEXT    NOT NULL,
                old_value   TEXT,
                new_value   TEXT,
                edited_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                edited_by   TEXT     DEFAULT 'human'
            )
        """)
        cur.execute("CREATE INDEX ix_observation_edits_obs_id ON observation_edits (observation_id)")
        conn.commit()
        print("Created table: observation_edits")
    else:
        print("Nothing to do — observation_edits already exists.")

    conn.close()


if __name__ == "__main__":
    migrate()
