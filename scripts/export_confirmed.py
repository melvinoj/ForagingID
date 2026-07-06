"""
CLI: copy confirmed plant photos (confidence ≥ threshold) to photos/confirmed_plants/.

Run this standalone to (re-)export confirmed photos without re-running identification.
Originals are never moved or modified.

Usage:
  python scripts/export_confirmed.py
  python scripts/export_confirmed.py --dest /custom/path
  python scripts/export_confirmed.py --threshold 0.5   # lower bar
  python scripts/export_confirmed.py --rerun           # re-copy already-exported
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
from app.services.export import run_export_batch, CONFIRMED_THRESHOLD


@click.command()
@click.option("--dest", default=None, help="Destination folder (default: photos/confirmed_plants/)")
@click.option("--threshold", default=CONFIRMED_THRESHOLD, show_default=True,
              help="Minimum confidence score to qualify as confirmed")
@click.option("--rerun", is_flag=True, help="Re-copy already-exported photos")
def main(dest: str, threshold: float, rerun: bool):
    """Copy confirmed plant photos to a clean organised folder."""
    asyncio.run(_run(dest, threshold, rerun))


async def _run(dest_str: str, threshold: float, rerun: bool):
    settings.ensure_dirs()
    await init_db()

    if dest_str:
        confirmed_dir = Path(dest_str)
    else:
        confirmed_dir = Path("photos/confirmed_plants")

    click.echo(f"Exporting confirmed plants")
    click.echo(f"  Destination:  {confirmed_dir.resolve()}")
    click.echo(f"  Min score:    {threshold:.0%}")
    click.echo(f"  Re-run:       {rerun}")
    click.echo(f"  Copy only — originals untouched")

    pbar = None

    def on_progress(current: int, total: int):
        nonlocal pbar
        if pbar is None:
            pbar = tqdm(total=total, unit="img", desc="Copying", ncols=72)
        pbar.n = current
        pbar.refresh()

    async with AsyncSessionLocal() as session:
        result = await run_export_batch(
            session,
            confirmed_dir=confirmed_dir,
            threshold=threshold,
            rerun=rerun,
            progress_callback=on_progress,
        )

    if pbar:
        pbar.close()

    click.echo("")
    _print_summary(result)


def _print_summary(result: dict) -> None:
    click.echo("=" * 52)
    click.echo(f"  Eligible (score ≥ {result['threshold_used']:.0%}): {result['total_eligible']:>6,}")
    click.echo(f"  Copied:                       {result['copied']:>6,}")
    if result.get("skipped_no_file"):
        click.echo(f"  Skipped (file missing):       {result['skipped_no_file']:>6,}")
    if result.get("failed"):
        click.echo(f"  Failed:                       {result['failed']:>6,}")
    click.echo(f"  Destination: {result['destination']}")
    click.echo("=" * 52)

    if result["copied"]:
        click.echo(click.style(
            f"\n  ✓ {result['copied']} photo(s) copied. Originals untouched.",
            fg="green"
        ))


if __name__ == "__main__":
    main()
