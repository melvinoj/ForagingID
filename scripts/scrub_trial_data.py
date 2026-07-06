"""
CLI: scrub all trial observation data from the database and generated files.

What is deleted:
  - All observations, species_candidates, processing_logs, observation_edits,
    observation_tags, locations (pipeline data)
  - All species, culinary_info, enrichment_sources, culinary_info_history
    (trial enrichment data)
  - data/thumbnails/   — regenerated from observations; wiped clean
  - data/cache/        — API response cache; wiped clean
  - data/checkpoint_*.json  — scan checkpoint files; removed
  - uploads/           — pending browser uploads; wiped clean

What is PRESERVED:
  - All database table schemas (no tables are dropped)
  - All app code, migrations, config
  - data/test_photos/  — prefilter test fixtures; kept for testing
  - photos/confirmed_plants/  — sample confirmed photos committed to git

After running, the database is empty and ready for a fresh scan.

Usage:
  python scripts/scrub_trial_data.py --dry-run     (default — shows what would be deleted)
  python scripts/scrub_trial_data.py --confirm      (actually deletes)
"""

import sys
import shutil
import sqlite3
from pathlib import Path

import click

DB_PATH  = Path(__file__).parent.parent / "data" / "foragingid.db"
DATA_DIR = Path(__file__).parent.parent / "data"


# Tables to clear and their deletion order (respect FK dependencies)
TABLES_TO_CLEAR = [
    # Child tables first
    "observation_edits",
    "observation_tags",
    "species_candidates",
    "processing_logs",
    "locations",
    # Main observation table
    "observations",
    # Enrichment child tables
    "culinary_info_history",
    "culinary_info",
    "enrichment_sources",
    # Master taxonomy table
    "species",
    # Empty but clean up anyway
    "tags",
    "sources",
    "workshop_sites",
]

DIRS_TO_WIPE = [
    DATA_DIR / "thumbnails",
    DATA_DIR / "cache",
    Path(__file__).parent.parent / "uploads",
]


@click.command()
@click.option("--confirm", "confirmed", is_flag=True, default=False,
              help="Actually perform the scrub. Without this flag, only a preview is shown.")
def main(confirmed: bool):
    """
    Scrub all trial observation data.

    Without --confirm: shows a preview of what would be deleted (safe to run).
    With --confirm: permanently deletes trial data (irreversible).
    """
    dry_run = not confirmed
    label = "[PREVIEW] " if dry_run else ""
    click.echo(f"\n{label}ForagingID — Trial Data Scrub")
    click.echo("=" * 52)

    if not DB_PATH.exists():
        click.echo(f"  Database not found: {DB_PATH}")
        click.echo("  Nothing to scrub.")
        return

    # ── Inspect current state ──────────────────────────────────────────────
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    click.echo("  Current row counts:")
    totals = {}
    for table in TABLES_TO_CLEAR:
        try:
            count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            totals[table] = count
            if count:
                click.echo(f"    {table:<30} {count:>6,} rows  ← will delete")
        except Exception:
            pass

    conn.close()

    total_rows = sum(totals.values())
    if total_rows == 0:
        click.echo("\n  ✓ Database already empty — nothing to scrub.")
        return

    click.echo(f"\n  Total rows to delete: {total_rows:,}")

    # ── Directories ────────────────────────────────────────────────────────
    click.echo("\n  Directories to wipe:")
    for d in DIRS_TO_WIPE:
        if d.exists():
            file_count = sum(1 for _ in d.rglob("*") if _.is_file())
            if file_count:
                click.echo(f"    {d.relative_to(Path.cwd()) if d.is_relative_to(Path.cwd()) else d}  ({file_count} files)")

    # ── Checkpoints ────────────────────────────────────────────────────────
    cps = list(DATA_DIR.glob("checkpoint_*.json"))
    if cps:
        click.echo(f"\n  Checkpoint files to delete: {len(cps)}")

    if dry_run:
        click.echo("\n" + "-" * 52)
        click.echo(click.style(
            "  Dry run only — no changes made.\n"
            "  Run with --confirm to execute the scrub.",
            fg="yellow"
        ))
        return

    # ── Confirmation prompt ────────────────────────────────────────────────
    click.echo("\n" + "!" * 52)
    click.echo("  WARNING: This will permanently delete all trial data.")
    click.echo("  Table schemas and app code are preserved.")
    click.echo("  data/test_photos/ and photos/confirmed_plants/ are kept.")
    click.echo("!" * 52)
    if not click.confirm("\n  Proceed with scrub?"):
        click.echo("  Aborted.")
        return

    # ── Execute scrub ──────────────────────────────────────────────────────
    click.echo("\n  Scrubbing database…")

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # SQLite doesn't enforce FKs by default, but let's still be orderly
    cur.execute("PRAGMA foreign_keys = OFF")

    deleted_total = 0
    for table in TABLES_TO_CLEAR:
        try:
            count = cur.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            cur.execute(f"DELETE FROM {table}")
            deleted_total += count
            if count:
                click.echo(f"    ✓ Cleared {table} ({count:,} rows)")
        except Exception as exc:
            click.echo(click.style(f"    ✗ Could not clear {table}: {exc}", fg="yellow"))

    # Reset auto-increment counters
    cur.execute("DELETE FROM sqlite_sequence")
    cur.execute("PRAGMA foreign_keys = ON")
    conn.commit()  # Commit all deletes before VACUUM (VACUUM cannot run inside a transaction)
    conn.close()

    # VACUUM must run outside any connection with open transactions
    conn2 = sqlite3.connect(DB_PATH)
    conn2.execute("VACUUM")
    conn2.close()

    click.echo(f"\n  ✓ Deleted {deleted_total:,} rows from database")
    click.echo("  ✓ sqlite_sequence reset (IDs restart from 1)")

    # ── Wipe directories ───────────────────────────────────────────────────
    click.echo("\n  Wiping generated file directories…")
    for d in DIRS_TO_WIPE:
        if d.exists():
            wiped = 0
            for f in d.rglob("*"):
                if f.is_file():
                    f.unlink()
                    wiped += 1
            # Remove empty subdirectories
            for sub in sorted(d.rglob("*"), reverse=True):
                if sub.is_dir():
                    try: sub.rmdir()
                    except OSError: pass
            click.echo(f"    ✓ Wiped {d.name}/ ({wiped} files removed)")

    # ── Remove checkpoint files ────────────────────────────────────────────
    removed_cps = 0
    for cp in DATA_DIR.glob("checkpoint_*.json"):
        cp.unlink()
        removed_cps += 1
    if removed_cps:
        click.echo(f"    ✓ Removed {removed_cps} checkpoint file(s)")

    # ── Summary ────────────────────────────────────────────────────────────
    click.echo("\n" + "=" * 52)
    click.echo(click.style(
        "  ✓ Scrub complete. Database is empty and ready for a fresh scan.\n\n"
        "  Next steps:\n"
        "    1. python scripts/scan.py ~/Documents/Pictures\n"
        "    2. python scripts/prefilter.py\n"
        "    3. python scripts/identify.py\n"
        "    4. python scripts/enrich.py",
        fg="green"
    ))
    click.echo("=" * 52)


if __name__ == "__main__":
    main()
