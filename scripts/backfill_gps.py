#!/usr/bin/env python3
"""
One-off GPS backfill from Google Takeout JSON sidecars.

Google Takeout exports a <photo>.json sidecar alongside each image containing
GPS in geoData / geoDataExif fields. The original scan only read EXIF from the
image files themselves, so observations from Takeout exports may have no GPS.

This script:
  1. Finds all observations where latitude IS NULL
  2. Checks whether a Takeout JSON sidecar exists alongside the original photo
  3. Reads GPS from the sidecar (geoData preferred over geoDataExif)
  4. Updates the observation record in the database

Rules (never violated):
  - Never overwrites existing non-NULL coordinates (NULL fills only)
  - Source photo files are never read or modified
  - All DB changes committed atomically at the end
  - Dry-run mode (default) logs what would change without writing anything
  - Full audit trail written to observation_edits for every GPS set

Usage:
    python scripts/backfill_gps.py              # dry-run: show what would change
    python scripts/backfill_gps.py --apply      # apply changes to DB
    python scripts/backfill_gps.py --limit 200  # process first N no-GPS observations
    python scripts/backfill_gps.py --apply --limit 200
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.observation import Observation, ObservationEdit
from app.utils.sidecar import read_takeout_gps


async def backfill(dry_run: bool = True, limit: int = 0) -> None:
    checked = updated = no_sidecar = errors = 0

    async with AsyncSessionLocal() as session:
        stmt = (
            select(Observation)
            .where(Observation.latitude.is_(None))
            .order_by(Observation.id)
        )
        if limit > 0:
            stmt = stmt.limit(limit)

        obs_list = (await session.execute(stmt)).scalars().all()
        total = len(obs_list)

        print(f"Found {total} observations with no GPS coordinates.")
        if limit:
            print(f"  (limited to first {limit})")
        print()

        for obs in obs_list:
            checked += 1

            if not obs.file_path:
                no_sidecar += 1
                continue

            try:
                gps = read_takeout_gps(Path(obs.file_path))
            except Exception as exc:
                print(f"  ERROR obs #{obs.id}: {exc}")
                errors += 1
                continue

            if not gps:
                no_sidecar += 1
                continue

            lat, lng = gps
            print(
                f"  {'[DRY-RUN] Would update' if dry_run else 'Updating'} "
                f"obs #{obs.id}  {obs.species_primary or '(no species)'}  "
                f"→ ({lat:.6f}, {lng:.6f})"
            )

            if not dry_run:
                obs.latitude = lat
                obs.longitude = lng
                session.add(ObservationEdit(
                    observation_id=obs.id,
                    field_name="coordinates",
                    old_value=None,
                    new_value=f"{lat},{lng}|source=takeout_sidecar_backfill",
                    edited_at=datetime.utcnow(),
                    edited_by="backfill_gps",
                ))

            updated += 1

        if not dry_run and updated > 0:
            await session.commit()
            print(f"\n✓ Committed {updated} coordinate update(s) to the database.")

    print()
    print("Summary")
    print("─" * 40)
    print(f"  Checked    : {checked}")
    print(f"  Updated    : {updated}{' (dry-run — no DB writes)' if dry_run else ''}")
    print(f"  No sidecar : {no_sidecar}")
    if errors:
        print(f"  Errors     : {errors}")

    if dry_run:
        if updated > 0:
            print(f"\nRe-run with --apply to write {updated} update(s) to the database.")
        else:
            print("\nNo sidecar GPS data found — nothing to apply.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill GPS coordinates from Google Takeout JSON sidecars",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Usage:")[1] if "Usage:" in __doc__ else "",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write GPS coordinates to the database. Default is dry-run (no writes).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        metavar="N",
        help="Process at most N observations (0 = all). Useful for testing.",
    )
    args = parser.parse_args()

    asyncio.run(backfill(dry_run=not args.apply, limit=args.limit))


if __name__ == "__main__":
    main()
