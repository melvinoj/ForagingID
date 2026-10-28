"""
Idempotent migration: add common_names_de column to species table.
"""
import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal


async def run():
    async with AsyncSessionLocal() as session:
        await session.execute(text(
            "ALTER TABLE species ADD COLUMN common_names_de TEXT"
        ))
        await session.commit()
        print("Added common_names_de column to species table.")


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
