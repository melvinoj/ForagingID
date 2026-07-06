"""
CLI: run culinary enrichment on identified species.

Fetches PFAF and Wikidata data for each unique species found in identified
observations. Populates the species and culinary_info tables.

Usage:
  python scripts/enrich.py               # full batch
  python scripts/enrich.py --dry-run     # count species, no network calls
  python scripts/enrich.py --re-enrich   # overwrite existing enrichment
  python scripts/enrich.py --species "Urtica dioica"   # single species test
"""

import asyncio
import logging
import sys
from pathlib import Path

import click
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import init_db, AsyncSessionLocal
from app.services.enrichment import run_enrichment_batch


@click.command()
@click.option("--dry-run", is_flag=True, help="List species to enrich — no network calls")
@click.option("--re-enrich", is_flag=True, help="Re-fetch and overwrite existing enrichment")
@click.option("--species", default=None, help="Enrich a single species by name (partial match ok)")
@click.option("--verbose", "-v", is_flag=True, help="Enable INFO logging so every step is visible")
def main(dry_run: bool, re_enrich: bool, species: str, verbose: bool):
    """Enrich identified species with PFAF + Wikidata culinary data."""
    if verbose:
        logging.basicConfig(
            level=logging.INFO,
            format="%(levelname)s  %(name)s  %(message)s",
            stream=sys.stderr,
        )
        # Quieten noisy transport-layer loggers
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("anthropic._base_client").setLevel(logging.WARNING)
    asyncio.run(_run(dry_run, re_enrich, species))


async def _run(dry_run: bool, re_enrich: bool, species_filter: str):
    await init_db()

    bar = None

    def progress(current: int, total: int, name: str, status: str):
        nonlocal bar
        if bar is None:
            bar = tqdm(total=total, unit="species", desc="Enriching")
        bar.set_postfix_str(f"{name[:30]} → {status}")
        bar.update(1)

    if dry_run:
        click.echo(click.style("DRY RUN — no network calls will be made", fg="yellow"))

    async with AsyncSessionLocal() as session:
        counters = await run_enrichment_batch(
            session,
            dry_run=dry_run,
            re_enrich=re_enrich,
            species_filter=species_filter,
            progress_cb=progress,
        )

    if bar:
        bar.close()

    click.echo("")
    click.echo(click.style("─" * 40, fg="cyan"))
    click.echo(click.style("Enrichment complete", fg="green", bold=True))
    click.echo(f"  Total species:  {counters['total']}")
    click.echo(f"  Enriched:       {counters.get('enriched', 0)}")
    click.echo(f"  Partial:        {counters.get('partial', 0)}")
    click.echo(f"  Not found:      {counters.get('not_found', 0)}")
    click.echo(f"  Skipped:        {counters.get('skipped', 0)}")
    click.echo(f"  Failed:         {counters.get('failed', 0)}")
    click.echo(click.style("─" * 40, fg="cyan"))


if __name__ == "__main__":
    main()
