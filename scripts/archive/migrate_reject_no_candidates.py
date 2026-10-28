"""
One-time migration: auto-reject all identified observations that have no
PlantNet candidates (empty or missing species_candidates_json).

These are images PlantNet had no match for. Human review adds no value —
they are not plants, or the photo was too poor quality to identify.

Safe to re-run (idempotent): only touches rows currently in needs_review.

Usage:
  python scripts/migrate_reject_no_candidates.py
  python scripts/migrate_reject_no_candidates.py --dry-run
"""

import asyncio
import json
import sys
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")
from pathlib import Path

import click

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import init_db, AsyncSessionLocal
from app.models.observation import Observation
from sqlalchemy import select


@click.command()
@click.option("--dry-run", is_flag=True, help="Report counts without writing")
def main(dry_run: bool):
    asyncio.run(_run(dry_run))


async def _run(dry_run: bool):
    await init_db()

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(Observation)
            .where(Observation.identification_status == "identified")
            .where(Observation.review_status == "needs_review")
        )).scalars().all()

    no_candidates = []
    for obs in rows:
        try:
            cands = json.loads(obs.species_candidates_json or "[]")
            if not cands:
                no_candidates.append(obs.id)
        except Exception:
            no_candidates.append(obs.id)

    click.echo(f"Identified + needs_review:   {len(rows)}")
    click.echo(f"  With candidates:           {len(rows) - len(no_candidates)}")
    click.echo(f"  No candidates (to reject): {len(no_candidates)}")

    if not no_candidates:
        click.echo("Nothing to do.")
        return

    if dry_run:
        click.echo("\nDRY RUN — no changes written.")
        click.echo(f"Would reject {len(no_candidates)} observations.")
        return

    async with AsyncSessionLocal() as session:
        # Reload within this session to update
        rows2 = (await session.execute(
            select(Observation).where(Observation.id.in_(no_candidates))
        )).scalars().all()

        for obs in rows2:
            obs.review_status = "rejected"

        await session.commit()

    click.echo(click.style(
        f"\n✓ {len(no_candidates)} observations auto-rejected (no PlantNet candidates).",
        fg="green"
    ))


if __name__ == "__main__":
    main()
