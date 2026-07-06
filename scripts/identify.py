"""
CLI: run PlantNet species identification on ingested observations.

This is a completely separate layer from scan.py.
Run scan.py first, then identify.py on the resulting observations.

Usage:
  python scripts/identify.py
  python scripts/identify.py --dry-run
  python scripts/identify.py --retry-failed
  python scripts/identify.py --batch-size 10
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
from app.services.identification import run_identification_batch, LOW_CONFIDENCE_THRESHOLD


@click.command()
@click.option("--dry-run", is_flag=True, help="Count eligible observations — no API calls")
@click.option("--retry-failed", is_flag=True, help="Also retry previously failed identifications")
@click.option("--batch-size", default=20, show_default=True, help="DB commit interval")
@click.option("--api-key", default=None, help="PlantNet API key (overrides .env)")
def main(dry_run: bool, retry_failed: bool, batch_size: int, api_key: str):
    """Run PlantNet identification on pending observations."""
    asyncio.run(_run(dry_run, retry_failed, batch_size, api_key))


async def _run(dry_run: bool, retry_failed: bool, batch_size: int, api_key_override: str):
    settings.ensure_dirs()
    await init_db()

    api_key = api_key_override or settings.plantnet_api_key
    if not api_key:
        click.echo(click.style(
            "ERROR: PLANTNET_API_KEY not set. Add it to .env or pass --api-key.",
            fg="red"
        ))
        sys.exit(1)

    label = "[DRY RUN] " if dry_run else ""
    click.echo(f"{label}PlantNet identification pipeline")
    click.echo(f"Low-confidence threshold: {LOW_CONFIDENCE_THRESHOLD:.0%}")
    if retry_failed:
        click.echo("  ↻ Will retry previously failed identifications")

    pbar = None

    def on_progress(current: int, total: int):
        nonlocal pbar
        if pbar is None:
            pbar = tqdm(total=total, unit="obs", desc="Identifying", ncols=72)
        pbar.n = current
        pbar.refresh()

    async with AsyncSessionLocal() as session:
        result = await run_identification_batch(
            session,
            api_key=api_key,
            batch_size=batch_size,
            retry_failed=retry_failed,
            dry_run=dry_run,
            progress_callback=on_progress,
        )

    if pbar:
        pbar.close()

    click.echo("")
    _print_summary(result, dry_run)


def _print_summary(result: dict, dry_run: bool) -> None:
    label = "[DRY RUN] " if dry_run else ""
    click.echo("=" * 48)
    click.echo(f"  {label}Eligible observations: {result['total_eligible']:>6,}")
    if not dry_run:
        click.echo(f"  Identified:            {result['identified']:>6,}")
        click.echo(f"  Failed (stored):       {result['failed']:>6,}")
        click.echo(f"  Flagged for review:    {result['low_confidence_flagged']:>6,}")
        click.echo(f"  (confidence < {LOW_CONFIDENCE_THRESHOLD:.0%})")
    click.echo("=" * 48)

    if not dry_run:
        if result["failed"]:
            click.echo(click.style(
                f"\n  ⚠  {result['failed']} failures stored as 'failed_identification'."
                "\n     Re-run with --retry-failed to attempt again.",
                fg="yellow"
            ))
        if result["low_confidence_flagged"]:
            click.echo(click.style(
                f"\n  🔍 {result['low_confidence_flagged']} low-confidence results sent to review queue.",
                fg="cyan"
            ))


if __name__ == "__main__":
    main()
