"""
Migration: create enrichment_sources and culinary_info_history tables.
Idempotent — safe to re-run.

Usage:
  python scripts/migrate_add_enrichment_tables.py
"""
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "foragingid.db"


def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    existing_tables = {
        row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }

    created = []

    if "enrichment_sources" not in existing_tables:
        cur.execute("""
            CREATE TABLE enrichment_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                species_id INTEGER NOT NULL REFERENCES species(id),
                source_name VARCHAR(50) NOT NULL,
                source_url VARCHAR(512),
                retrieved_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                raw_response_json TEXT,
                extraction_confidence FLOAT,
                parsing_method VARCHAR(30)
            )
        """)
        cur.execute("CREATE INDEX ix_enrichment_sources_species_id ON enrichment_sources (species_id)")
        created.append("enrichment_sources")

    if "culinary_info_history" not in existing_tables:
        cur.execute("""
            CREATE TABLE culinary_info_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                culinary_info_id INTEGER NOT NULL REFERENCES culinary_info(id),
                field_name VARCHAR(100) NOT NULL,
                old_value TEXT,
                new_value TEXT,
                changed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                changed_by VARCHAR(100) NOT NULL DEFAULT 'human'
            )
        """)
        cur.execute(
            "CREATE INDEX ix_culinary_info_history_culinary_info_id "
            "ON culinary_info_history (culinary_info_id)"
        )
        created.append("culinary_info_history")

    conn.commit()
    conn.close()

    if created:
        print(f"Created tables: {', '.join(created)}")
    else:
        print("Nothing to do — tables already exist.")


if __name__ == "__main__":
    migrate()
