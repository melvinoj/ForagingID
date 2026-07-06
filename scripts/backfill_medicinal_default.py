"""
A5 retroactive backfill — medicinal_notes default for confirmed species.

For every species that has at least one confirmed observation
(approved/manually_verified) and whose culinary_info.medicinal_notes is
null/empty AND has no medicinal_folklore AND no pending/approved medicinal_notes
AI draft, set medicinal_notes to the standard "No known traditional medicinal
uses" note and mark it approved (ai_approved_fields_json) so it never surfaces
in a review queue.

Idempotent. Run:  python scripts/backfill_medicinal_default.py
"""
import asyncio
import json

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.culinary import CulinaryInfo
from app.models.observation import Observation
from app.models.species import Species, SpeciesAIDraft
from app.services.enrichment import MEDICINAL_NONE_DEFAULT


async def main() -> None:
    async with AsyncSessionLocal() as session:
        confirmed_ids = set((await session.execute(
            select(Observation.species_id)
            .where(Observation.species_id.is_not(None))
            .where(Observation.review_status.in_(["approved", "manually_verified"]))
            .distinct()
        )).scalars().all())

        drafted_ids = set((await session.execute(
            select(SpeciesAIDraft.species_id)
            .where(SpeciesAIDraft.field_name == "medicinal_notes")
            .where(SpeciesAIDraft.status.in_(["pending", "approved", "edited_approved"]))
            .distinct()
        )).scalars().all())

        rows = (await session.execute(
            select(CulinaryInfo, Species)
            .join(Species, Species.id == CulinaryInfo.species_id)
            .where(CulinaryInfo.species_id.in_(confirmed_ids))
        )).all()

        changed = 0
        for ci, sp in rows:
            if ci.medicinal_notes and ci.medicinal_notes.strip():
                continue
            if ci.medicinal_folklore and ci.medicinal_folklore.strip():
                continue
            if ci.species_id in drafted_ids:
                continue
            ci.medicinal_notes = MEDICINAL_NONE_DEFAULT
            try:
                approved = json.loads(ci.ai_approved_fields_json) if ci.ai_approved_fields_json else []
                if not isinstance(approved, list):
                    approved = []
            except (ValueError, TypeError):
                approved = []
            if "medicinal_notes" not in approved:
                approved.append("medicinal_notes")
                ci.ai_approved_fields_json = json.dumps(approved)
            changed += 1

        await session.commit()
        print(f"Backfilled medicinal_notes default for {changed} confirmed species.")


if __name__ == "__main__":
    asyncio.run(main())
