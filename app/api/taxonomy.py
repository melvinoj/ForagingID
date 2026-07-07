"""
Taxonomy tree data feed — Unit B wire-to-live.

Read-only. Reshapes species rows into the exact {RAW, FUNGI, UNPLACED} shape
consumed by frontend/taxonomy.html (radial tree prototype, aesthetic-approved
in a prior session). No writes, no schema changes.

Bucket policy (safety-load-bearing — see CLAUDE.md Unit A note on species 412):
a species only gets placed on a real branch if Unit A's own GBIF write-gate
marked it EXACT *and* wrote a full lineage (phylum/family/genus all non-null).
Anything else — conflict-withheld (EXACT but phylum IS NULL), parked
(FUZZY/HIGHERRANK/NONE), or never matched — falls into the unplaced bucket.
This reuses Unit A's own withholding signal rather than a second, driftable
check, so a conflict-withheld species (e.g. 412) can never render on a false
branch.

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

router = APIRouter(tags=["taxonomy"])

_PLACEABLE_KINGDOMS = {"plantae", "fungi"}

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
                    Species.family,
                    Species.genus,
                    Species.phylum,
                    Species.gbif_match_type,
                )
            )
        ).all()

    raw_plantae: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    fungi: dict[str, list[str]] = defaultdict(list)
    unplaced: list[str] = []

    for scientific_name, kingdom, family, genus, phylum, match_type in rows:
        kingdom_l = (kingdom or "").lower()

        placeable = (
            match_type == "EXACT"
            and phylum is not None
            and family is not None
            and genus is not None
            and kingdom_l in _PLACEABLE_KINGDOMS
        )
        if placeable:
            if kingdom_l == "plantae":
                raw_plantae[family][genus].append(scientific_name)
            else:  # fungi — flat, no genus level (matches approved prototype shape)
                fungi[family].append(scientific_name)
            continue

        # Out-of-scope kingdoms (Animalia/Chromista) with otherwise-clean lineage
        # are omitted entirely — not a data-quality issue, just no branch for them.
        # (kingdom_l == "" covers NULL kingdom, which still belongs in unplaced.)
        if kingdom_l and kingdom_l not in _PLACEABLE_KINGDOMS:
            continue

        if match_type == "EXACT" and phylum is None:
            reason = "conflict"
        elif match_type in _UNPLACED_REASONS:
            reason = _UNPLACED_REASONS[match_type]
        else:
            reason = "not yet matched"
        unplaced.append(f"{scientific_name} ({reason})")

    return {
        "RAW": {"Plantae": {fam: dict(genera) for fam, genera in raw_plantae.items()}},
        "FUNGI": dict(fungi),
        "UNPLACED": unplaced,
    }
