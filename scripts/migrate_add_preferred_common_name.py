"""
Idempotent migration: add preferred_common_name column to species table.
Used for user-set alphabetical sort key on the Species page.
"""
import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal


async def run():
    async with AsyncSessionLocal() as session:
        await session.execute(text(
            "ALTER TABLE species ADD COLUMN preferred_common_name VARCHAR(200)"
        ))
        await session.commit()
        print("Added preferred_common_name column to species table.")


if __name__ == "__main__":
    import sys
    try:
        asyncio.run(run())
    except Exception as e:
        if "duplicate column" in str(e).lower():
            print("Column already exists — nothing to do.")
        else:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
