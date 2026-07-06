"""
CLI: scan a photo folder and ingest images into the database.

Usage:
  python scripts/scan.py /path/to/photos
  python scripts/scan.py /path/to/photos --dry-run
  python scripts/scan.py /path/to/photos --no-resume      # ignore checkpoint, re-scan all
  python scripts/scan.py /path/to/photos --clear-checkpoint
"""

import asyncio
import sys
from pathlib import Path

import click
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.database import init_db, AsyncSessionLocal
from app.services.ingestion import scan_folder, clear_checkpoint


@click.command()
@click.argument("folder", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--dry-run", is_flag=True, help="Discover files and report counts only — no DB writes")
@click.option("--resume/--no-resume", default=True, show_default=True, help="Resume from checkpoint")
@click.option("--clear-checkpoint", "do_clear", is_flag=True, help="Delete checkpoint and start fresh")
@click.option("--thumbnail-size", default=300, show_default=True, help="Thumbnail max px")
@click.option("--batch-size", default=50, show_default=True, help="Images per DB commit")
def main(
    folder: Path,
    dry_run: bool,
    resume: bool,
    do_clear: bool,
    thumbnail_size: int,
    batch_size: int,
):
    """Recursively scan FOLDER and ingest images into ForagingID."""
    asyncio.run(_run(folder, dry_run, resume, do_clear, thumbnail_size, batch_size))


async def _run(
    folder: Path,
    dry_run: bool,
    resume: bool,
    do_clear: bool,
    thumbnail_size: int,
    batch_size: int,
):
    settings.ensure_dirs()

    if do_clear:
        clear_checkpoint(folder)
        click.echo(click.style("✓ Checkpoint cleared.", fg="yellow"))

    if not dry_run:
        await init_db()

    click.echo(f"{'[DRY RUN] ' if dry_run else ''}Scanning: {folder.resolve()}")
    if not dry_run:
        click.echo(f"Database:  {settings.database_url}")
        click.echo(f"Thumbnails:{settings.thumbnails_dir}")
        click.echo(f"Batch size:{batch_size}  |  Resume: {resume}")

    pbar = None

    def on_progress(current: int, total: int):
        nonlocal pbar
        if pbar is None:
            pbar = tqdm(total=total, unit="img", desc="Scanning", ncols=72)
        pbar.n = current
        pbar.refresh()

    async with AsyncSessionLocal() as session:
        result = await scan_folder(
            session,
            folder,
            thumbnails_dir=Path(settings.thumbnails_dir),
            thumbnail_size=thumbnail_size,
            batch_size=batch_size,
            dry_run=dry_run,
            resume=resume,
            progress_callback=on_progress,
        )

    if pbar:
        pbar.close()

    click.echo("")
    _print_summary(result, dry_run)


def _print_summary(result: dict, dry_run: bool) -> None:
    label = "[DRY RUN] " if dry_run else ""
    click.echo("=" * 44)
    click.echo(f"  {label}Total found:   {result['total']:>7,}")
    if not dry_run:
        click.echo(f"  Ingested:      {result['ingested']:>7,}")
        click.echo(f"  Skipped:       {result['skipped']:>7,}")
        click.echo(f"  Duplicates:    {result['duplicates']:>7,}")
        click.echo(f"  Failed:        {result['failed']:>7,}")
    click.echo(f"  Geotagged:     {result['geotagged']:>7,}", nl=False)
    if dry_run:
        click.echo("  (estimated)")
    else:
        click.echo("")
    click.echo("=" * 44)
    if not dry_run and result["failed"] > 0:
        click.echo(click.style(
            f"  ⚠ {result['failed']} file(s) failed — check processing_logs table.",
            fg="yellow"
        ))


if __name__ == "__main__":
    main()
