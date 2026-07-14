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

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.observation import Observation
from app.models.species import Species
from app.services.taxonomy import normalize_taxon_key


async def resolve_species_id(
    session: AsyncSession, scientific_name: Optional[str]
) -> Optional[int]:
    """Return the Species.id whose scientific_name matches, or None."""
    if not scientific_name:
        return None
    return await session.scalar(
        select(Species.id).where(Species.scientific_name == scientific_name)
    )


async def _name_has_backing_observation(
    session: AsyncSession, name: Optional[str], species_id: Optional[int]
) -> bool:
    """True if ANY observation references this species by EITHER linkage column
    (species_primary == name OR species_id == species_id). Both are checked
    because the columns desync. Callers rely on autoflush so a pending move-off
    of the current observation is already visible (it won't self-count)."""
    if name:
        hit = await session.scalar(
            select(Observation.id).where(Observation.species_primary == name).limit(1)
        )
        if hit is not None:
            return True
    if species_id is not None:
        hit = await session.scalar(
            select(Observation.id).where(Observation.species_id == species_id).limit(1)
        )
        if hit is not None:
            return True
    return False


async def _find_card(
    session: AsyncSession, name: Optional[str], species_id: Optional[int]
) -> Optional[Species]:
    """Locate the Species card by name_key (preferred) then by id."""
    if name:
        sp = await session.scalar(
            select(Species).where(Species.name_key == normalize_taxon_key(name))
        )
        if sp is not None:
            return sp
    if species_id is not None:
        return await session.get(Species, species_id)
    return None


async def gc_species_card_if_orphaned(
    session: AsyncSession, name: Optional[str], species_id: Optional[int]
) -> Optional[int]:
    """Mark a species card orphaned (set orphaned_at=now) when NO observation
    references it by either column — a true phantom. Keyed on zero-observation
    ONLY, never on review status, so in_review cards are never marked. Does not
    delete. Returns the marked Species.id, or None if nothing was marked."""
    if not name and species_id is None:
        return None
    if await _name_has_backing_observation(session, name, species_id):
        return None
    card = await _find_card(session, name, species_id)
    if card is None:
        return None
    if card.orphaned_at is None:
        card.orphaned_at = datetime.utcnow()
    return card.id


async def _clear_orphan_marker(
    session: AsyncSession, name: Optional[str], species_id: Optional[int]
) -> None:
    """Un-orphan the card the observation now points at — it has a backing obs
    again, so the marker (if any) is stale. Self-healing / reversible."""
    card = await _find_card(session, name, species_id)
    if card is not None and card.orphaned_at is not None:
        card.orphaned_at = None


async def set_observation_species(
    session: AsyncSession,
    obs: Observation,
    scientific_name: Optional[str],
) -> None:
    """Set species_primary (display cache) and keep species_id (FK) in sync.

    Pass scientific_name=None to clear both fields.

    Orphan-GC: when the observation moves OFF a name, mark that name's card
    orphaned if nothing else references it (both columns, all observations); and
    un-mark the card it moves ONTO. Additive marking only — never deletes.
    """
    old_name = obs.species_primary
    old_id = obs.species_id

    obs.species_primary = scientific_name
    obs.species_id = await resolve_species_id(session, scientific_name)

    # The card this obs now points at has a backing observation → clear any
    # stale orphan marker on it.
    if scientific_name:
        await _clear_orphan_marker(session, scientific_name, obs.species_id)

    # The obs moved off old_name → orphan-check that name's card. Guarded on a
    # real change so fresh-obs calls (old_name is None) are no-ops.
    if old_name and old_name != scientific_name:
        await gc_species_card_if_orphaned(session, old_name, old_id)
