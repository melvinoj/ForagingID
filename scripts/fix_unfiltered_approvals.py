"""
Fix 9 — Retroactively demote approved observations that were never pre-filtered.

Root cause: observations processed before the pre-filter existed have
is_plant_likely=NULL. They were auto-approved on PlantNet confidence alone —
no plant-vs-non-plant check was ever run.

Action: set review_status = 'needs_review' so a human can confirm or reject
each one from the Review Queue. Observation data is never deleted.

Usage:
    PYTHONPATH=. python scripts/fix_unfiltered_approvals.py            # dry-run
    PYTHONPATH=. python scripts/fix_unfiltered_approvals.py --apply    # apply
"""

import asyncio
import sys
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.observation import Observation, ObservationEdit
from app.models.processing import ProcessingLog

DRY_RUN = "--apply" not in sys.argv


async def main() -> None:
    engine = create_async_engine(settings.database_url)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        # Find every approved observation that never went through pre-filter
        stmt = (
            select(Observation)
            .where(Observation.review_status == "approved")
            .where(Observation.is_plant_likely.is_(None))
            .order_by(Observation.id)
        )
        rows = (await db.execute(stmt)).scalars().all()

        print(f"{'[DRY RUN] ' if DRY_RUN else ''}Found {len(rows)} approved observations with no pre-filter data:\n")

        for obs in rows:
            print(f"  ID={obs.id:6d}  species={obs.species_primary or '—':40s}  file={obs.file_path}")

            if not DRY_RUN:
                obs.review_status = "needs_review"
                obs.reviewed_at = datetime.utcnow()

                # Audit trail
                db.add(ObservationEdit(
                    observation_id=obs.id,
                    field_name="review_status",
                    old_value="approved",
                    new_value="needs_review",
                    edited_by="system:fix_unfiltered_approvals",
                ))
                db.add(ProcessingLog(
                    observation_id=obs.id,
                    stage="fix_unfiltered_approvals",
                    status="success",
                    message=(
                        "Demoted approved→needs_review: observation was auto-approved "
                        "before pre-filter existed (is_plant_likely=NULL). "
                        "Human review required."
                    ),
                ))

        if DRY_RUN:
            print(f"\nDry run — no changes made. Re-run with --apply to demote all {len(rows)}.")
        else:
            await db.commit()
            print(f"\nApplied: {len(rows)} observations moved to needs_review.")
            print("They will appear in the Review Queue for human confirmation.")

    await engine.dispose()


asyncio.run(main())
