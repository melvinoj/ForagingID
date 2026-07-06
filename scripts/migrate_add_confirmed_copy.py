"""
One-time migration: add confirmed_copy_path column to observations.

Safe to run multiple times.
Run with: python scripts/migrate_add_confirmed_copy.py
"""

import sqlite3, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
DB_PATH = Path("data/foragingid.db")

def main():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}. Run a scan first.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    existing = {r[1] for r in cur.execute("PRAGMA table_info(observations)").fetchall()}

    if "confirmed_copy_path" in existing:
        print("  skip  confirmed_copy_path (already exists)")
    else:
        cur.execute("ALTER TABLE observations ADD COLUMN confirmed_copy_path TEXT DEFAULT NULL")
        print("  added confirmed_copy_path")

    conn.commit()
    conn.close()
    print("\n✓ Migration complete.")

if __name__ == "__main__":
    main()
