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

import json
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.observation import Observation
from app.models.species import Species
from app.services.taxonomy import normalize_taxon_key


def strip_candidate_from_obs(obs: Observation, old_name: Optional[str]) -> bool:
    """Remove ONLY the moved-off name's entry from this observation's
    species_candidates_json, leaving every other candidate intact.

    Call this after moving an observation off ``old_name`` so the cache reflects
    current reality. The original-AI-guess audit trail lives separately in the
    SpeciesCandidate table (scan.py), so this only drops the redundant drifting
    copy in the JSON — it never touches SpeciesCandidate.

    Sync (mutates the obs object only; caller commits). No-op — returns False —
    when old_name is falsy, the cache is empty, or the JSON is malformed. Callers
    guard on old_name != new_name so the current primary is never stripped.
    """
    if not old_name or not obs.species_candidates_json:
        return False
    try:
        cands = json.loads(obs.species_candidates_json)
    except (ValueError, TypeError):
        return False
    if not isinstance(cands, list):
        return False
    filtered = [
        c for c in cands
        if not (isinstance(c, dict) and c.get("scientific_name") == old_name)
    ]
    if len(filtered) != len(cands):
        obs.species_candidates_json = json.dumps(filtered)
        return True
    return False


def candidate_own_score(entry: dict) -> Optional[float]:
    """The best stored image score for ONE candidate entry: its listed `score`,
    or iNaturalist's gating score min(vision, combined) when that is higher.
    None when no image source scored it (e.g. a curator-named species no API
    listed). Never invents a value."""
    scores = []
    listed = entry.get("score")
    if isinstance(listed, (int, float)):
        scores.append(float(listed))
    inat = [v for v in (entry.get("inat_vision_score"), entry.get("inat_combined_score"))
            if isinstance(v, (int, float))]
    if inat:
        scores.append(float(min(inat)))
    return max(scores) if scores else None


def confirmed_candidate_first(obs: Observation,
                              common_names: Optional[list] = None) -> bool:
    """After a HUMAN species change, put the observation's species at the front
    of species_candidates_json with its own score, and set top_score to it.

    Audit B1-08 (21 Oct 2026): confirm/correct only stripped the moved-off name,
    so candidates[0] stayed another species. The review card %, its "Also:" line,
    the map pin's confidence and top_score all read candidates[0] / top_score,
    so they showed another species' score (obs 24353: Lysimachia nemorum
    confirmed, card "31.9%" = PlantNet's Micromeria douglasii).

    Its own score = candidate_own_score() of its stored entry — PlantNet's or
    iNat's, whichever scored it higher in the stored run (24353: iNat 0.4613,
    the same 46% Second Opinion showed). When no stored entry names it, a
    curator entry with score None goes first: no score is invented, and a
    client-sent number (e.g. Second Opinion's) is never stored — so a GBIF
    name-match-only pick can never acquire a score.

    Matches by name_key. Sync, mutates obs only; caller commits. Call it ONLY
    where a human sets the species (never in scan — machine order is evidence).
    Returns True when it changed anything.
    """
    name = obs.species_primary
    if not name:
        return False
    raw = obs.species_candidates_json
    try:
        cands = json.loads(raw) if raw else []
    except (ValueError, TypeError):
        return False
    if cands is None:                       # stored "null"
        cands = []
    if not isinstance(cands, list):
        return False

    key = normalize_taxon_key(name)
    idx = next((i for i, c in enumerate(cands)
                if isinstance(c, dict) and normalize_taxon_key(c.get("scientific_name") or "") == key),
               None)
    if idx is None:
        entry = {"scientific_name": name, "common_names": list(common_names or []),
                 "score": None, "source": "curator"}
    else:
        entry = dict(cands.pop(idx))
        own = candidate_own_score(entry)
        if own != entry.get("score"):
            entry["listed_score"] = entry.get("score")
            entry["score"] = own
            entry["score_basis"] = "inaturalist"    # only iNat's gate can be higher
        if common_names and not entry.get("common_names"):
            entry["common_names"] = list(common_names)
    cands.insert(0, entry)

    new_json = json.dumps(cands)
    changed = new_json != raw or obs.top_score != entry["score"]
    obs.species_candidates_json = new_json
    obs.top_score = entry["score"]
    return changed


async def resolve_species_id(
    session: AsyncSession, scientific_name: Optional[str]
) -> Optional[int]:
    """Return the Species.id for a name, or None: exact scientific_name first,
    then name_key (case, ×/x hybrid marker, autonym — CLAUDE.md "use name_key
    for all species lookups"), then a registered synonym (species_synonyms), the
    same chain trigger_ai_drafts_for_species uses to pick the card it enriches.

    Before 21 Oct 2026 this was exact-name only (audit C-03/C-07), so e.g. the
    two 'Conyza canadensis' pins stayed unlinked although their card is the
    synonym-registered Erigeron canadensis (342)."""
    if not scientific_name:
        return None
    sid = await session.scalar(
        select(Species.id).where(Species.scientific_name == scientific_name)
    )
    if sid is not None:
        return sid
    key = normalize_taxon_key(scientific_name)
    if not key:
        return None
    sid = await session.scalar(select(Species.id).where(Species.name_key == key))
    if sid is not None:
        return sid
    from app.services.synonyms import resolve_synonym_species_id
    return await resolve_synonym_species_id(session, scientific_name)


async def promotable_suggestion(session: AsyncSession, obs: Observation) -> Optional[str]:
    """The scientific name an APPROVE may promote from species_suggested, or None
    when the suggestion is not a recognised scientific name.

    species_suggested holds either the pipeline's below-threshold top candidate
    or whatever the reviewer typed before pressing Look up (PATCH /suggest) —
    which can be a common name. Approve used to promote it unchecked: obs 21585
    got species_primary 'norway spruce' (audit C-04) and enrichment then made a
    'norway spruce' species card.

    Recognised = (1) a stored candidate (the pipeline's own suggestion always
    is one), (2) a species card in use — exact or name_key, not orphan-marked,
    or (3) a registered synonym. Returns the stored spelling."""
    sug = (obs.species_suggested or "").strip()
    if not sug:
        return None
    key = normalize_taxon_key(sug)
    try:
        cands = json.loads(obs.species_candidates_json or "[]") or []
    except (ValueError, TypeError):
        cands = []
    if isinstance(cands, list):
        for c in cands:
            if isinstance(c, dict) and normalize_taxon_key(c.get("scientific_name") or "") == key:
                return c.get("scientific_name") or sug
    from sqlalchemy import or_
    sci = await session.scalar(
        select(Species.scientific_name)
        .where(or_(Species.scientific_name == sug, Species.name_key == key))
        .where(Species.orphaned_at.is_(None))
    )
    if sci:
        return sci
    from app.services.synonyms import resolve_synonym_species_id
    if await resolve_synonym_species_id(session, sug) is not None:
        return sug
    return None


async def ensure_species_row(session: AsyncSession, obs: Observation) -> Optional[int]:
    """A CONFIRMED observation with a species name always has a species row and
    is linked to it (audit C-03, 21 Oct 2026).

    Before, the confirm paths left the row to trigger_ai_drafts_for_species, a
    background task that created it in the same session as the network
    enrichment — any enrichment failure rolled the new row back. Five confirmed
    pins (21382, 21453, 21454, 21950, 22074) ended up with no card, edibility or
    enrichment, and rows created later in the background stayed unlinked until
    the next server start (24347/24348/24356).

    Creates a bare row (scientific_name + name_key only; toxicity_severity is
    born 'unknown' by the ORM default, so it fails closed) when no species,
    name_key or synonym match exists. Enrichment still fills it in the
    background, finding it by name_key. Never touches an existing row.
    Call only for confirmed rows; caller commits. Returns obs.species_id."""
    name = obs.species_primary
    if not name or obs.species_id is not None:
        return obs.species_id
    sid = await resolve_species_id(session, name)
    if sid is None:
        from app.services.taxonomy import collapse_autonym
        sci = collapse_autonym(name)
        sp = Species(scientific_name=sci, name_key=normalize_taxon_key(sci))
        session.add(sp)
        await session.flush()
        sid = sp.id
    obs.species_id = sid
    await _clear_orphan_marker(session, name, sid)
    return sid


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
