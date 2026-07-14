"""
Taxonomy tree data feed — Unit B wire-to-live.

Read-only. Reshapes species rows into the exact {RAW, FUNGI, UNPLACED} shape
consumed by frontend/taxonomy.html (radial tree prototype, aesthetic-approved
in a prior session). No writes, no schema changes.

Bucket policy (safety-load-bearing — see CLAUDE.md Unit A note on species 412):
a species only gets placed on a real branch if Unit A's own GBIF write-gate
marked it EXACT *and* wrote a full lineage (phylum/class_/order_/family/genus
all non-null). Anything else — conflict-withheld (EXACT but phylum IS NULL),
parked (FUZZY/HIGHERRANK/NONE), incomplete lineage (missing class_/order_),
or never matched — falls into the unplaced bucket. This reuses Unit A's own
withholding signal rather than a second, driftable check, so a
conflict-withheld species (e.g. 412) can never render on a false branch.

Kingdoms outside Plantae/Fungi (Animalia, Chromista — misidentified fauna
that slipped through the pipeline) have no branch in this view's design and
are omitted from the response entirely, not routed into "unplaced" (they
aren't a data-quality problem, just out of scope for a plant/fungi tree).
"""

from collections import defaultdict

from fastapi import APIRouter
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.species import Species
from app.models.observation import Observation

router = APIRouter(tags=["taxonomy"])

_PLACEABLE_KINGDOMS = {"plantae", "fungi"}

# Must match the map's confirmed definition exactly (app/api/map.py
# _CONFIRMED_STATUSES) so a species' obs_state='confirmed' here means the same
# thing as "surfaces on the map". Do not fork this definition.
_CONFIRMED_STATUSES = ("approved", "manually_verified")


async def _compute_obs_state(session) -> dict[str, str]:
    """Return {scientific_name: 'confirmed' | 'in_review' | 'none'} for every
    species. Read-only, SELECT-derived — no writes, no schema change.

    A species counts as having an observation when EITHER linkage column points
    at it (they desync): observations.species_id = species.id OR
    observations.species_primary = species.scientific_name. 'confirmed' uses the
    map's exact status tuple; 'in_review' = has an observation but none confirmed;
    'none' = no observation references it by either column (true phantom).
    """
    species_rows = (
        await session.execute(select(Species.id, Species.scientific_name))
    ).all()

    # Confirmed linkage sets (both columns), map-exact status filter.
    confirmed_ids = set(
        (await session.execute(
            select(Observation.species_id)
            .where(
                Observation.species_id.isnot(None),
                Observation.review_status.in_(_CONFIRMED_STATUSES),
                Observation.identification_status == "identified",
            )
            .distinct()
        )).scalars().all()
    )
    confirmed_names = set(
        (await session.execute(
            select(Observation.species_primary)
            .where(
                Observation.species_primary.isnot(None),
                Observation.review_status.in_(_CONFIRMED_STATUSES),
                Observation.identification_status == "identified",
            )
            .distinct()
        )).scalars().all()
    )

    # Any-observation linkage sets (both columns), no status filter.
    any_ids = set(
        (await session.execute(
            select(Observation.species_id)
            .where(Observation.species_id.isnot(None))
            .distinct()
        )).scalars().all()
    )
    any_names = set(
        (await session.execute(
            select(Observation.species_primary)
            .where(Observation.species_primary.isnot(None))
            .distinct()
        )).scalars().all()
    )

    # Priority so a duplicate scientific_name never downgrades a stronger state.
    _RANK = {"none": 0, "in_review": 1, "confirmed": 2}
    state_map: dict[str, str] = {}
    for sid, sci_name in species_rows:
        if not sci_name:
            continue
        if sid in confirmed_ids or sci_name in confirmed_names:
            state = "confirmed"
        elif sid in any_ids or sci_name in any_names:
            state = "in_review"
        else:
            state = "none"
        prev = state_map.get(sci_name)
        if prev is None or _RANK[state] > _RANK[prev]:
            state_map[sci_name] = state
    return state_map

_UNPLACED_REASONS = {
    "FUZZY": "fuzzy match",
    "HIGHERRANK": "higher rank only",
    "NONE": "no GBIF match",
}


@router.get("/api/species/taxonomy-tree")
async def get_taxonomy_tree():
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(
                    Species.scientific_name,
                    Species.kingdom,
                    Species.class_,
                    Species.order_,
                    Species.family,
                    Species.genus,
                    Species.phylum,
                    Species.gbif_match_type,
                )
            )
        ).all()

        # obs_state per species — read-only, keyed by scientific_name so the
        # frontend popup can look it up without touching the tree geometry.
        obs_state = await _compute_obs_state(session)

    # class_ -> order_ -> family -> genus -> [species...] (same shape for both kingdoms)
    raw_plantae: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    fungi: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    unplaced: list[str] = []

    for scientific_name, kingdom, class_, order_, family, genus, phylum, match_type in rows:
        kingdom_l = (kingdom or "").lower()

        placeable = (
            match_type == "EXACT"
            and phylum is not None
            and class_ is not None
            and order_ is not None
            and family is not None
            and genus is not None
            and kingdom_l in _PLACEABLE_KINGDOMS
        )
        if placeable:
            if kingdom_l == "plantae":
                raw_plantae[class_][order_][family][genus].append(scientific_name)
            else:  # fungi — now nested class->order->family->genus, same shape as Plantae
                fungi[class_][order_][family][genus].append(scientific_name)
            continue

        # Out-of-scope kingdoms (Animalia/Chromista) with otherwise-clean lineage
        # are omitted entirely — not a data-quality issue, just no branch for them.
        # (kingdom_l == "" covers NULL kingdom, which still belongs in unplaced.)
        if kingdom_l and kingdom_l not in _PLACEABLE_KINGDOMS:
            continue

        if match_type == "EXACT" and phylum is None:
            reason = "conflict"
        elif match_type == "EXACT":
            # phylum present (not conflict-withheld) but class_/order_/family/
            # genus incomplete — currently 0 rows in the live DB, but coded
            # explicitly rather than falling through to "not yet matched",
            # which would misrepresent a row that DID match.
            reason = "incomplete lineage"
        elif match_type in _UNPLACED_REASONS:
            reason = _UNPLACED_REASONS[match_type]
        else:
            reason = "not yet matched"
        unplaced.append(f"{scientific_name} ({reason})")

    def _flatten(nested: dict) -> dict:
        """class_ -> order_ -> family -> {genus: [species...]}, all as plain dicts."""
        return {
            cls: {
                ordr: {fam: dict(genera) for fam, genera in families.items()}
                for ordr, families in orders.items()
            }
            for cls, orders in nested.items()
        }

    return {
        "RAW": {"Plantae": _flatten(raw_plantae)},
        "FUNGI": _flatten(fungi),
        "UNPLACED": unplaced,
        "OBS_STATE": obs_state,
    }
