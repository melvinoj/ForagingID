"""
Idempotent migration: add upload_source column to observations table.

upload_source TEXT — "phone" | NULL
  "phone"  = uploaded directly from browser
  NULL     = ingested from a local folder scan

Also ensures ~/Documents/ForagingID/uploads/ directory exists.

Usage:
    PYTHONPATH=. python scripts/migrate_add_upload_source.py
"""

import asyncio
from pathlib import Path
import aiosqlite
from app.config import settings


async def main() -> None:
    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
    print(f"Database: {db_path}")

    async with aiosqlite.connect(db_path) as db:
        # Check existing columns
        cursor = await db.execute("PRAGMA table_info(observations)")
        cols = {row[1] for row in await cursor.fetchall()}

        if "upload_source" not in cols:
            await db.execute("ALTER TABLE observations ADD COLUMN upload_source TEXT")
            await db.commit()
            print("✓ Added column: upload_source")
        else:
            print("  upload_source column already exists — skipping")

    # Ensure uploads directory exists
    uploads_dir = settings.phone_uploads_dir
    uploads_dir.mkdir(parents=True, exist_ok=True)
    print(f"✓ Uploads directory: {uploads_dir}")
    print("Migration complete.")


asyncio.run(main())
