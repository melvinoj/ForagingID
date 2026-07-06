"""
Migration: add species_recipes table + populate from existing culinary_info.recipe data.

Idempotent — safe to run multiple times.
Run with:
    PYTHONPATH=/Users/melvinjarman/Documents/ForagingID python scripts/migrate_add_recipe_bank.py
"""

import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.database import AsyncSessionLocal


# ---------------------------------------------------------------------------
# Season inference from recipe text
# ---------------------------------------------------------------------------

_SEASON_PATTERNS = {
    "spring": re.compile(
        r"\b(spring|early spring|late spring|march|april|may|"
        r"young shoot|new growth|first flush|nettles.*spring|spring nettle)\b",
        re.IGNORECASE,
    ),
    "summer": re.compile(
        r"\b(summer|high summer|midsummer|june|july|august|"
        r"warm month|long day|peak season)\b",
        re.IGNORECASE,
    ),
    "autumn": re.compile(
        r"\b(autumn|fall|september|october|november|harvest|"
        r"forage.*autumn|berry.*autumn|mushroom.*season|seed.*autumn)\b",
        re.IGNORECASE,
    ),
    "winter": re.compile(
        r"\b(winter|december|january|february|cold month|"
        r"overwintering|stored root|winter green|frost)\b",
        re.IGNORECASE,
    ),
}


def _infer_season(text_body: str) -> str:
    """
    Try to infer the primary season from recipe text.
    Returns the season with the most keyword matches, or 'year-round'.
    """
    if not text_body:
        return "year-round"
    counts = {season: len(pat.findall(text_body)) for season, pat in _SEASON_PATTERNS.items()}
    best_season = max(counts, key=counts.get)
    return best_season if counts[best_season] > 0 else "year-round"


def _extract_title(recipe_body: str) -> str:
    """Extract the first # heading from markdown recipe body as title."""
    if not recipe_body:
        return ""
    for line in recipe_body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    # No heading — take first non-empty line
    for line in recipe_body.splitlines():
        if line.strip():
            return line.strip()[:120]
    return ""


# ---------------------------------------------------------------------------
# Main migration
# ---------------------------------------------------------------------------

async def run():
    async with AsyncSessionLocal() as session:
        # ── 1. Create species_recipes table ──────────────────────────────────
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS species_recipes (
                id INTEGER PRIMARY KEY,
                species_id INTEGER NOT NULL REFERENCES species(id),
                title VARCHAR(200),
                body TEXT NOT NULL,
                season VARCHAR(20) NOT NULL DEFAULT 'year-round',
                is_preferred BOOLEAN NOT NULL DEFAULT 0,
                is_medicinal_prep BOOLEAN NOT NULL DEFAULT 0,
                source VARCHAR(30) NOT NULL DEFAULT 'ai_generated',
                status VARCHAR(20) NOT NULL DEFAULT 'approved',
                ai_draft_id INTEGER REFERENCES species_ai_drafts(id),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        await session.commit()
        print("✓ species_recipes table exists")

        # ── 2. Check if already populated ────────────────────────────────────
        existing = (await session.execute(
            text("SELECT COUNT(*) FROM species_recipes")
        )).scalar() or 0
        print(f"  Currently has {existing} recipe rows.")

        # ── 3. Migrate approved AI draft recipes ──────────────────────────────
        # Find all approved recipe drafts that don't yet have a species_recipes row
        drafts = (await session.execute(text("""
            SELECT d.id, d.species_id, d.draft_text, d.final_text, d.generated_at
            FROM species_ai_drafts d
            WHERE d.field_name = 'recipe'
              AND d.status IN ('approved', 'edited_approved')
              AND NOT EXISTS (
                  SELECT 1 FROM species_recipes r WHERE r.ai_draft_id = d.id
              )
        """))).fetchall()

        migrated_drafts = 0
        for row in drafts:
            body = row.final_text or row.draft_text or ""
            if not body.strip():
                continue
            title  = _extract_title(body)
            season = _infer_season(body)
            await session.execute(text("""
                INSERT INTO species_recipes
                    (species_id, title, body, season, is_preferred, is_medicinal_prep,
                     source, status, ai_draft_id, created_at, updated_at)
                VALUES
                    (:species_id, :title, :body, :season, 0, 0,
                     'ai_generated', 'approved', :draft_id, :created_at, CURRENT_TIMESTAMP)
            """), {
                "species_id": row.species_id,
                "title":      title[:200] if title else None,
                "body":       body,
                "season":     season,
                "draft_id":   row.id,
                "created_at": row.generated_at,
            })
            migrated_drafts += 1

        await session.commit()
        print(f"✓ Migrated {migrated_drafts} approved recipe drafts from species_ai_drafts")

        # ── 4. Migrate culinary_info.recipe (fallback for any not yet in bank) ─
        ci_recipes = (await session.execute(text("""
            SELECT ci.species_id, ci.recipe
            FROM culinary_info ci
            WHERE ci.recipe IS NOT NULL
              AND ci.recipe != ''
              AND NOT EXISTS (
                  SELECT 1 FROM species_recipes r WHERE r.species_id = ci.species_id
              )
        """))).fetchall()

        migrated_ci = 0
        for row in ci_recipes:
            body = row.recipe or ""
            if not body.strip():
                continue
            title  = _extract_title(body)
            season = _infer_season(body)
            await session.execute(text("""
                INSERT INTO species_recipes
                    (species_id, title, body, season, is_preferred, is_medicinal_prep,
                     source, status, ai_draft_id)
                VALUES
                    (:species_id, :title, :body, :season, 0, 0,
                     'ai_generated', 'approved', NULL)
            """), {
                "species_id": row.species_id,
                "title":      title[:200] if title else None,
                "body":       body,
                "season":     season,
            })
            migrated_ci += 1

        await session.commit()
        print(f"✓ Migrated {migrated_ci} recipes from culinary_info.recipe (fallback)")

        # ── 5. Summary ────────────────────────────────────────────────────────
        total = (await session.execute(
            text("SELECT COUNT(*) FROM species_recipes WHERE status='approved'")
        )).scalar() or 0
        by_season = (await session.execute(text("""
            SELECT season, COUNT(*) FROM species_recipes WHERE status='approved'
            GROUP BY season ORDER BY COUNT(*) DESC
        """))).fetchall()
        print(f"\n✓ species_recipes now has {total} approved rows")
        for s, c in by_season:
            print(f"    {s}: {c}")


if __name__ == "__main__":
    asyncio.run(run())
