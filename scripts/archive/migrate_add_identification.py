"""
One-time migration: add identification columns to the observations table.

Safe to run multiple times (uses IF NOT EXISTS / checks before altering).
Run with:  python scripts/migrate_add_identification.py
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DB_PATH = Path("data/foragingid.db")

NEW_COLUMNS = [
    # (column_name, sqlite_type, default_expression)
    ("identification_status",  "TEXT",    "'pending_identification'"),
    ("species_primary",        "TEXT",    "NULL"),
    ("species_candidates_json","TEXT",    "NULL"),  # JSON array of top candidates
    ("plantnet_raw_json",      "TEXT",    "NULL"),  # full API response blob
]


def get_existing_columns(cur, table: str) -> set[str]:
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def main():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}. Run a scan first.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing = get_existing_columns(cur, "observations")
    added = []

    for col_name, col_type, default in NEW_COLUMNS:
        if col_name in existing:
            print(f"  skip  {col_name} (already exists)")
        else:
            sql = f"ALTER TABLE observations ADD COLUMN {col_name} {col_type} DEFAULT {default}"
            cur.execute(sql)
            added.append(col_name)
            print(f"  added {col_name}")

    conn.commit()
    conn.close()

    if added:
        print(f"\n✓ Migration complete — {len(added)} column(s) added.")
    else:
        print("\n✓ Nothing to migrate — all columns already present.")


if __name__ == "__main__":
    main()
