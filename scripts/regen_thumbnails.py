"""
CLI: Audit and regenerate broken or missing thumbnails.

Finds observations whose thumbnail is missing, too small, or fails PIL
decode, then regenerates them using the current thumbnail pipeline.

Usage:
  python scripts/regen_thumbnails.py              # fix broken only
  python scripts/regen_thumbnails.py --force-all  # regenerate everything
  python scripts/regen_thumbnails.py --dry-run    # audit, no changes
"""

import asyncio
import sys
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")
from pathlib import Path
from typing import Optional, Tuple

import click
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.database import init_db, AsyncSessionLocal
from app.models.observation import Observation
from app.utils.thumbnail import generate_thumbnail, MIN_THUMB_BYTES  # noqa: F401 (re-exported)
from sqlalchemy import select


def _thumb_status(thumb_path_str: Optional[str]) -> Tuple[bool, str]:
    """Return (needs_regen, reason). reason is 'ok' when fine."""
    if not thumb_path_str:
        return True, "no thumbnail_path in DB"
    p = Path(thumb_path_str)
    if not p.exists():
        return True, "file missing"
    size = p.stat().st_size
    if size < MIN_THUMB_BYTES:
        return True, f"too small ({size} bytes)"
    try:
        from PIL import Image
        with Image.open(p) as img:
            img.verify()  # raises on corrupt JPEG
        return False, "ok"
    except Exception as e:
        return True, f"corrupt ({e})"


@click.command()
@click.option("--force-all", is_flag=True,
              help="Regenerate all thumbnails, not just broken ones")
@click.option("--dry-run", is_flag=True,
              help="Audit only — print what would be regenerated, write nothing")
@click.option("--batch-size", default=50, show_default=True,
              help="DB commit interval")
def main(force_all: bool, dry_run: bool, batch_size: int):
    """Audit and regenerate broken or missing thumbnails."""
    asyncio.run(_run(force_all, dry_run, batch_size))


async def _run(force_all: bool, dry_run: bool, batch_size: int):
    settings.ensure_dirs()
    await init_db()
    thumbnails_dir = Path(settings.thumbnails_dir)

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(
            select(Observation)
            .where(Observation.is_duplicate.is_(False))
            .order_by(Observation.id)
        )).scalars().all()

    click.echo(f"Checking {len(rows)} observations…")

    # ── Audit pass ──────────────────────────────────────────────────────────
    to_regen: list = []
    ok_count = 0

    for obs in rows:
        if force_all:
            to_regen.append((obs, "force-all"))
        else:
            needs, reason = _thumb_status(obs.thumbnail_path)
            if needs:
                to_regen.append((obs, reason))
            else:
                ok_count += 1

    click.echo(f"  OK:                  {ok_count:>6,}")
    click.echo(f"  Need regeneration:   {len(to_regen):>6,}")

    if not to_regen:
        click.echo(click.style("\nAll thumbnails look good.", fg="green"))
        return

    if dry_run:
        click.echo("\nDRY RUN — no files written. First 30 needing regen:")
        for obs, reason in to_regen[:30]:
            click.echo(f"  #{obs.id:>5}  {reason:<30}  {Path(obs.file_path).name}")
        return

    # ── Regeneration pass ───────────────────────────────────────────────────
    regenerated = src_missing = failed = 0

    async with AsyncSessionLocal() as session:
        for i, (obs, reason) in enumerate(
            tqdm(to_regen, desc="Regenerating", ncols=72, unit="img")
        ):
            src = Path(obs.file_path)
            if not src.exists():
                src_missing += 1
                continue

            thumb = await asyncio.get_event_loop().run_in_executor(
                None, generate_thumbnail, src, thumbnails_dir, settings.thumbnail_size, True
            )

            if thumb:
                obs_db = await session.get(Observation, obs.id)
                if obs_db:
                    obs_db.thumbnail_path = str(thumb)
                regenerated += 1
            else:
                failed += 1

            if (i + 1) % batch_size == 0:
                await session.commit()

        await session.commit()

    click.echo("")
    click.echo("=" * 52)
    click.echo(f"  Regenerated:       {regenerated:>6,}")
    click.echo(f"  Source missing:    {src_missing:>6,}")
    click.echo(f"  Failed:            {failed:>6,}")
    click.echo("=" * 52)

    if regenerated:
        click.echo(click.style(
            f"\n  ✓ {regenerated} thumbnail(s) fixed.",
            fg="green"
        ))
    if failed:
        click.echo(click.style(
            f"  ✗ {failed} could not be generated (source files may be corrupt).",
            fg="red"
        ))


if __name__ == "__main__":
    main()
