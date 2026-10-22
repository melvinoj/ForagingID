"""
enrichment_scope.py — which species a bulk enrichment / backfill run may touch
(Melvin, 22 Oct 2026). One resolver shared by every bulk endpoint and its dry
run, so the dry run and the run always count the same species.

Scopes (no default — no scope = nothing runs):
  walk  — a saved walk's species: walk_membership, the same members the map shows
  list  — "Current list": the species on the Foraging List (lists.js, sent by the page)
  all   — every eligible species; kept, never the default

Each endpoint passes its own eligible names; the resolver intersects them with
the scope, puts walk species first, and caps the run (default 25). Species
beyond the cap are not queued — `remaining` says how many are left for a later
run. Read-only.
"""
from dataclasses import dataclass, field
from typing import Iterable, List, Optional

from fastapi import HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.taxonomy import normalize_taxon_key

SCOPES = ("walk", "list", "all")
DEFAULT_CAP = 25
NO_SCOPE_DETAIL = "Choose a scope (a saved walk, Current list or All eligible) — nothing runs without one"


@dataclass
class ScopeRequest:
    scope: Optional[str] = None
    walk_id: Optional[int] = None
    species: List[str] = field(default_factory=list)
    cap: int = DEFAULT_CAP


def scope_params(
    scope: Optional[str] = Query(None, description="walk | list | all — required for a bulk run"),
    walk_id: Optional[int] = Query(None, description="scope=walk: the saved walk"),
    species: List[str] = Query([], description="scope=list: the Foraging List species"),
    cap: int = Query(DEFAULT_CAP, ge=1, le=1000, description="species per run; the rest are not queued"),
) -> ScopeRequest:
    """FastAPI dependency: the scope query params every bulk endpoint takes."""
    return ScopeRequest(scope=scope, walk_id=walk_id, species=list(species), cap=cap)


async def walk_species(db: AsyncSession, walk_id: int) -> tuple[str, list]:
    """(walk name, species names in stop order) — walk_membership, as the map."""
    from app.api.walk import walk_membership_for
    from app.models.walk import SavedWalk
    from app.services import walk_membership as wm
    walk = await db.get(SavedWalk, walk_id)
    if walk is None:
        raise HTTPException(404, f"saved walk {walk_id} not found")
    names: list = []
    for st in wm.public_stops(await walk_membership_for(db, walk)):
        for sp in st.get("species") or []:
            if sp.get("name") and sp["name"] not in names:
                names.append(sp["name"])
    return walk.name, names


async def resolve(db: AsyncSession, req: ScopeRequest, eligible: Iterable[str]) -> dict:
    """The species this run queues: eligible ∩ scope, walk species first, capped.

    Returns {scope, scope_label, eligible_in_scope, names (queued, priority
    order), remaining, cap}. Raises 400 when no scope is chosen."""
    if req.scope not in SCOPES:
        raise HTTPException(400, NO_SCOPE_DETAIL)
    eligible = list(dict.fromkeys(n for n in eligible if n))
    by_key = {}
    for n in eligible:
        by_key.setdefault(normalize_taxon_key(n), n)

    def pick(names: Iterable[str]) -> list:
        out = []
        for n in names:
            hit = by_key.get(normalize_taxon_key(n or ""))
            if hit and hit not in out:
                out.append(hit)
        return out

    if req.scope == "walk":
        if req.walk_id is None:
            raise HTTPException(400, "scope=walk needs walk_id")
        walk_name, names = await walk_species(db, req.walk_id)
        ordered, label = pick(names), f"walk: {walk_name}"
    else:
        if req.scope == "list":
            if not req.species:
                raise HTTPException(400, "Current list is empty — add species to the Foraging List first")
            in_scope, label = pick(req.species), f"Current list ({len(req.species)} species)"
        else:
            in_scope, label = eligible, "all eligible species"
        # Walk species first (any saved walk), then the rest; order kept within each.
        from app.api.walk import species_on_saved_walks
        on_walk = {normalize_taxon_key(n) for n in (await species_on_saved_walks(db))}
        ordered = ([n for n in in_scope if normalize_taxon_key(n) in on_walk]
                   + [n for n in in_scope if normalize_taxon_key(n) not in on_walk])
    queued = ordered[:req.cap]
    return {
        "scope": req.scope,
        "scope_label": label,
        "eligible_in_scope": len(ordered),
        "names": queued,
        "remaining": len(ordered) - len(queued),
        "cap": req.cap,
    }


def scope_summary(res: dict) -> dict:
    """The scope fields a dry run / run summary carries (no name list)."""
    return {k: res[k] for k in ("scope", "scope_label", "eligible_in_scope", "remaining", "cap")} | {
        "queued": len(res["names"])}
