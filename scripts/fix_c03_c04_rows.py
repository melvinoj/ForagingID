"""
Data fixes for audit C-03 and C-04 (fix batch 14, 21 Oct 2026), through the
same app helpers the approve / confirm paths now use.

C-03 — five confirmed observations name a species with no species row (map pins
with no card, edibility or enrichment): 21382 Filipendula vulgaris, 21453 and
21454 Ganoderma applanatum, 21950 and 22074 Conyza canadensis.
  species_link.ensure_species_row(): Conyza canadensis links to its registered
  synonym's card (Erigeron canadensis, 342); the other two names get a bare row
  (scientific_name + name_key, toxicity_severity 'unknown' → fails closed).
  Enrichment is NOT run here. One observation_edits row per link (species_id).

C-04 — obs 21585 species_primary 'norway spruce' (the reviewer's typed text,
promoted by an approve that read the row before the 'Picea abies' pick
committed). Set back to the pick through observation_service.
update_observation_status (status stays 'approved'); the junk 'norway spruce'
card (685) is orphan-marked by the existing orphan rule, not deleted.

Usage (project root):
  python scripts/fix_c03_c04_rows.py            # dry run (read-only)
  python scripts/fix_c03_c04_rows.py --apply    # write + read back by id
Take a Settings snapshot first.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select  # noqa: E402

import app.main  # noqa: E402,F401  (models on Base.metadata)
from app.database import AsyncSessionLocal  # noqa: E402
from app.models.observation import Observation, ObservationEdit  # noqa: E402
from app.models.species import Species  # noqa: E402
from app.services.species_link import ensure_species_row, resolve_species_id  # noqa: E402

C03_IDS = [21382, 21453, 21454, 21950, 22074]
C04_ID, C04_FROM, C04_TO = 21585, "norway spruce", "Picea abies"


async def dry_run():
    async with AsyncSessionLocal() as s:
        for oid in C03_IDS:
            o = await s.get(Observation, oid)
            sid = await resolve_species_id(s, o.species_primary)
            print(f"C-03 {oid} {o.species_primary!r} {o.review_status} species_id={o.species_id} -> "
                  + (f"link to existing species {sid}" if sid else "create a bare species row and link"))
        o = await s.get(Observation, C04_ID)
        print(f"C-04 {C04_ID} species_primary={o.species_primary!r} species_id={o.species_id} "
              f"review_status={o.review_status} -> {C04_TO!r} (species {await resolve_species_id(s, C04_TO)})")
        assert o.species_primary == C04_FROM, "21585 changed since the audit — stop"
        await s.rollback()
    print("Dry run — nothing written.")


async def apply():
    from app.services.observation_service import update_observation_status
    from app.services.write_lock import db_write_lock
    async with AsyncSessionLocal() as s:
        for oid in C03_IDS:
            o = await s.get(Observation, oid)
            assert o.species_id is None and o.review_status in ("approved", "manually_verified"), oid
            sid = await ensure_species_row(s, o)
            s.add(ObservationEdit(observation_id=oid, field_name="species_id", old_value=None,
                                  new_value=str(sid), edited_by="audit_fix:C-03"))
        o = await s.get(Observation, C04_ID)
        assert o.species_primary == C04_FROM, "21585 changed since the audit — stop"
        await update_observation_status(session=s, obs=o, review_status=o.review_status,
                                        species_name=C04_TO, update_species=True,
                                        edited_by="audit_fix:C-04")
        async with db_write_lock():
            await s.commit()

    # Read back by id — every field touched.
    async with AsyncSessionLocal() as s:
        for oid in C03_IDS + [C04_ID]:
            o = await s.get(Observation, oid)
            sp = await s.get(Species, o.species_id) if o.species_id else None
            front = (json.loads(o.species_candidates_json or "[]") or [{}])[0]
            print(f"obs {o.id}: species_primary={o.species_primary!r} species_id={o.species_id} "
                  f"review_status={o.review_status} identification_status={o.identification_status} "
                  f"species_suggested={o.species_suggested!r} obs_category={o.obs_category} "
                  f"top_score={o.top_score} front={front.get('scientific_name')!r}/{front.get('score')}")
            if sp:
                print(f"   species {sp.id}: {sp.scientific_name!r} name_key={sp.name_key!r} "
                      f"edibility_status={sp.edibility_status!r} toxicity_severity={sp.toxicity_severity!r} "
                      f"kingdom={sp.kingdom!r} orphaned_at={sp.orphaned_at} created_at={sp.created_at}")
            for e in (await s.execute(select(ObservationEdit).where(
                    ObservationEdit.observation_id == oid,
                    ObservationEdit.edited_by.in_(["audit_fix:C-03", "audit_fix:C-04"]))
                    .order_by(ObservationEdit.id))).scalars():
                print(f"   edit {e.id}: {e.field_name} {e.old_value!r} -> {e.new_value!r} "
                      f"by {e.edited_by} at {e.edited_at}")
        junk = await s.scalar(select(Species).where(Species.name_key == "norway spruce"))
        if junk:
            print(f"species {junk.id} {junk.scientific_name!r} orphaned_at={junk.orphaned_at}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    asyncio.run(apply() if ap.parse_args().apply else dry_run())
