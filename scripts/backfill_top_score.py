"""Backfill Observation.top_score from species_candidates_json[0].score.

The review-queue server-side confidence sort (A7) orders by the top_score
column, but legacy rows were written before that column was populated, so
they were all NULL. This sets top_score from the cached top candidate score,
using the same normalisation guard as the live identification path.

Usage:
    python -m scripts.backfill_top_score            # dry-run (no writes)
    python -m scripts.backfill_top_score --apply    # write changes
"""
from __future__ import annotations

import asyncio
import json
import sys

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.observation import Observation


def _top_from_candidates(raw: str | None):
    try:
        cands = json.loads(raw or "[]")
    except (ValueError, TypeError):
        return None
    if not cands:
        return None
    score = cands[0].get("score")
    if score is None:
        return None
    # Same guard as identification.py: candidate scores are 0.0-1.0, but defend
    # against a stray 0-100 value.
    return (score / 100.0) if score > 1.0 else score


async def main(apply: bool):
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(Observation).where(Observation.top_score.is_(None))
            )
        ).scalars().all()

        updated = 0
        skipped = 0
        for obs in rows:
            val = _top_from_candidates(obs.species_candidates_json)
            if val is None:
                skipped += 1
                continue
            updated += 1
            if apply:
                obs.top_score = val

        if apply:
            await session.commit()

        print(f"NULL top_score rows scanned : {len(rows)}")
        print(f"  would set from candidates : {updated}")
        print(f"  no candidate score        : {skipped}")
        print("APPLIED" if apply else "DRY-RUN (no writes) — pass --apply to commit")


if __name__ == "__main__":
    asyncio.run(main("--apply" in sys.argv))
