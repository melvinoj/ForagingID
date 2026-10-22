"""
enrichment_plan.py — the dry-run summary every enrichment / backfill button
shows before it runs (Melvin, 22 Oct 2026): how many species, which fields it
may fill (empty now), which filled fields may get a review draft instead, which
AI drafts it may create. Read-only. Shared by culinary.py and enrich.py.
"""
from collections import Counter
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.culinary import CulinaryInfo
from app.models.species import AI_NO_CONTENT_VERDICTS, Species, SpeciesAIDraft

# enrichment.REVIEW_FIELDS — filled only when empty; changed text → review draft
REVIEW_FIELDS = ("edible_parts", "seasonal_peak", "id_notes", "preparation_warnings", "look_alike_warnings")
# other source fields PFAF / Wikidata write
OTHER_SOURCE_FIELDS = ("preparation_methods", "culinary_traditions", "harvest_stage", "traditional_uses")
AI_FIELDS = ("taste_notes", "medicinal_notes", "recipe", "medicinal_folklore")


async def plan(db: AsyncSession, names: Iterable[str], *, sources: bool = True, drafts: bool = True,
               regenerate: bool = False, only_field: Optional[str] = None, note: str = "") -> dict:
    names = list(dict.fromkeys(n for n in names if n))
    fill, review, update, draft_fields = Counter(), Counter(), Counter(), Counter()
    new_species = 0
    for name in names:
        sp = await db.scalar(select(Species).where(Species.scientific_name == name))
        ci = await db.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id)) if sp else None
        if sp is None or ci is None:
            new_species += 1
        if sources:
            for f in REVIEW_FIELDS:
                if not ((getattr(ci, f, None) or "").strip() if ci else ""):
                    fill[f] += 1
                else:
                    review[f] += 1
            for f in OTHER_SOURCE_FIELDS:
                (update if ci and (getattr(ci, f, None) or "").strip() else fill)[f] += 1
        if drafts and sp is not None:
            if (sp.edibility_status or "") in AI_NO_CONTENT_VERDICTS:
                wanted = [f for f in AI_FIELDS if f in ("medicinal_notes", "medicinal_folklore")]
            else:
                wanted = list(AI_FIELDS)
            if only_field:
                wanted = [f for f in wanted if f == only_field]
            covered_st = ("approved", "edited_approved", "rejected") + (() if regenerate else ("pending",))
            covered = set((await db.scalars(
                select(SpeciesAIDraft.field_name).where(SpeciesAIDraft.species_id == sp.id,
                                                        SpeciesAIDraft.status.in_(covered_st)))).all())
            for f in wanted:
                if f not in covered:
                    draft_fields[f] += 1
    return {
        "dry_run": True,
        "species_count": len(names),
        "new_species": new_species,
        "fields_may_fill": dict(fill),                 # empty now — may be filled
        "fields_may_get_review_draft": dict(review),   # have text — changed source text → review card
        "fields_may_update": dict(update),             # other source fields with text
        "drafts_may_create": dict(draft_fields),
        "drafts_note": ("new versions sit beside pending ones; nothing is replaced until you keep one"
                        if regenerate else "only fields with no pending draft; no draft is replaced or invalidated"),
        "note": note,
        "species_sample": names[:12],
    }
