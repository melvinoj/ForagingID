"""Keep observations.species_id (the FK) in sync with species_primary (the
denormalised display-name cache).

The canonical link from an observation to a species is the integer FK
`Observation.species_id`. `species_primary` is a cached scientific-name string
used by ~120 read-sites and the map display. The two must never drift apart,
so every place that writes `species_primary` should set both fields together
via `set_observation_species` (or clear both via the same call with name=None).

Backfill rule: species_id is resolved by exact scientific_name match against
the Species table. When no Species row exists for the name (e.g. a manual entry
whose Species row is created later by background enrichment), species_id stays
NULL — that is the correct state at write time.
"""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.observation import Observation
from app.models.species import Species


async def resolve_species_id(
    session: AsyncSession, scientific_name: Optional[str]
) -> Optional[int]:
    """Return the Species.id whose scientific_name matches, or None."""
    if not scientific_name:
        return None
    return await session.scalar(
        select(Species.id).where(Species.scientific_name == scientific_name)
    )


async def set_observation_species(
    session: AsyncSession,
    obs: Observation,
    scientific_name: Optional[str],
) -> None:
    """Set species_primary (display cache) and keep species_id (FK) in sync.

    Pass scientific_name=None to clear both fields.
    """
    obs.species_primary = scientific_name
    obs.species_id = await resolve_species_id(session, scientific_name)
