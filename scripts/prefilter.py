"""
CLI: run the plant likelihood pre-filter on ingested observations.

Run this between scan.py and identify.py to avoid wasting API calls
on screenshots, animals, people, food, vehicles, and other non-plant content.

Usage:
  python scripts/prefilter.py
  python scripts/prefilter.py --dry-run
  python scripts/prefilter.py --reprocess    # re-run on already-filtered rows
"""

import asyncio
import sys
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")
from pathlib import Path

import click
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.database import init_db, AsyncSessionLocal
from app.services.prefilter import (
    run_prefilter_batch,
    PLANT_GREEN_THRESHOLD,
    PLANT_GREEN_THRESHOLD_GPS,
)


@click.command()
@click.option("--dry-run", is_flag=True, help="Count eligible observations — no DB writes")
@click.option("--reprocess", is_flag=True, help="Re-run on already-filtered observations")
@click.option("--batch-size", default=100, show_default=True, help="DB commit interval")
def main(dry_run: bool, reprocess: bool, batch_size: int):
    """Pre-filter ingested observations: classify plant-likely vs not-plant."""
    asyncio.run(_run(dry_run, reprocess, batch_size))


async def _run(dry_run: bool, reprocess: bool, batch_size: int):
    settings.ensure_dirs()
    await init_db()

    label = "[DRY RUN] " if dry_run else ""
    click.echo(f"{label}Plant pre-filter (tightened)")
    click.echo(f"  Green threshold (no GPS): {PLANT_GREEN_THRESHOLD:.0%}")
    click.echo(f"  Green threshold (GPS):    {PLANT_GREEN_THRESHOLD_GPS:.0%}")
    click.echo(f"  GPS: confidence boost only — NOT a bypass")
    click.echo(f"  Default: REJECT (requires positive plant evidence)")
    click.echo(f"  Reprocess already-filtered: {reprocess}")

    if dry_run:
        from sqlalchemy import select, func
        from app.models.observation import Observation
        async with AsyncSessionLocal() as session:
            total = await session.scalar(
                select(func.count(Observation.id))
                .where(Observation.is_duplicate.is_(False))
                .where(Observation.is_plant_likely.is_(None))
            )
        click.echo(f"\n[DRY RUN] Would process {total:,} observations")
        return

    pbar = None

    def on_progress(current: int, total: int):
        nonlocal pbar
        if pbar is None:
            pbar = tqdm(total=total, unit="img", desc="Pre-filtering", ncols=72)
        pbar.n = current
        pbar.refresh()

    async with AsyncSessionLocal() as session:
        result = await run_prefilter_batch(
            session,
            batch_size=batch_size,
            reprocess=reprocess,
            progress_callback=on_progress,
        )

    if pbar:
        pbar.close()

    click.echo("")
    _print_summary(result)


def _print_summary(result: dict) -> None:
    total     = result["total"]
    likely    = result["plant_likely"]
    not_plant = result["not_plant"]
    failed    = result["failed"]
    cats      = result.get("categories", {})
    saved_pct = f"{not_plant/total*100:.0f}%" if total else "0%"

    click.echo("=" * 52)
    click.echo(f"  Total processed:       {total:>7,}")
    click.echo(f"  Plant-likely:          {likely:>7,}  → PlantNet identification")
    click.echo(f"  Rejected (not-plant):  {not_plant:>7,}  → {saved_pct} of API calls saved")
    if failed:
        click.echo(f"  Failed:                {failed:>7,}")
    click.echo("─" * 52)

    # Category breakdown for rejected images
    cat_labels = {
        "screenshot":     "Screenshots",
        "ui_blank":       "Blank/UI/grey images",
        "person_animal":  "People or animals",
        "food_warm":      "Food or warm objects",
        "sky_blue":       "Sky/water/indoor (no plants)",
        "no_plant_signal":"No plant signal (ambiguous)",
    }
    if cats:
        click.echo("  Rejection breakdown:")
        for key, label in cat_labels.items():
            n = cats.get(key, 0)
            if n:
                click.echo(f"    {label:<32} {n:>5,}")

    click.echo("=" * 52)

    if likely:
        click.echo(click.style(
            f"\n  ✓ {likely:,} image(s) queued for PlantNet identification.",
            fg="green"
        ))
    if not_plant:
        click.echo(click.style(
            f"  ✓ {not_plant:,} image(s) auto-rejected — PlantNet will skip these.",
            fg="cyan"
        ))
    if failed:
        click.echo(click.style(
            f"  ⚠ {failed} pre-filter error(s) — check processing_logs.",
            fg="yellow"
        ))


if __name__ == "__main__":
    main()
