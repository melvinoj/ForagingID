"""
synonyms.py — read-only taxonomic-synonym resolution against species_synonyms.

Called at every name_key-lookup-miss site, immediately before falling through
to "create a new species row". Resolves a registered older/alternate name to
the species that already carries the currently-accepted name, so encountering
a known synonym (e.g. from an ID API) never creates a duplicate card.

Strictly read-only: a single SELECT, nothing else. Never writes edibility,
enrichment, drafts, or approval state, and never creates a species_synonyms
row itself — that table is curated by hand (or a future admin tool), not
grown automatically from resolution traffic.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.taxonomy import normalize_taxon_key


async def resolve_synonym_species_id(db: AsyncSession, name: str) -> Optional[int]:
    """
    Return the canonical species_id if `name` is a registered synonym in
    species_synonyms, else None. Callers use this only after their own
    Species.name_key lookup has already missed.
    """
    if not name:
        return None
    from app.models.species import SpeciesSynonym  # local import — avoids import-order coupling

    key = normalize_taxon_key(name)
    if not key:
        return None
    return await db.scalar(
        select(SpeciesSynonym.canonical_species_id)
        .where(SpeciesSynonym.synonym_name_key == key)
    )
