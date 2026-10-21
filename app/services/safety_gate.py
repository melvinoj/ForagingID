"""
Safety gate — DB side of app.models.species.safety_decision() (audit P1 /
batch 5, 21 Oct 2026). The decision itself lives in safety_decision(); this
module only gathers its inputs (severity, verdict, the approved caution
warning) for one species or for a list of names sent by a client.

The caution warning is the curator-authored preparation_warnings (an approved
curator-review warning draft counts — approval writes changed_by='human'),
the same rule as the experience export's rule 8 (gates.caution_warning).
"""
from typing import Dict, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.culinary import CulinaryInfo
from app.models.species import CulinaryInfoHistory, Species, is_curator_authored, safety_decision
from app.services.taxonomy import normalize_taxon_key


async def _caution_warning(db: AsyncSession, sp: Species, ci: Optional[CulinaryInfo]) -> Optional[str]:
    if (sp.edibility_status or "").strip().lower() != "caution":
        return None
    if ci is None:
        ci = await db.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id))
    pw = ci.preparation_warnings if ci else None
    if not (pw or "").strip():
        return None
    row = (await db.execute(
        select(CulinaryInfoHistory.changed_by, CulinaryInfoHistory.new_value)
        .where(CulinaryInfoHistory.culinary_info_id == ci.id)
        .where(CulinaryInfoHistory.field_name == "preparation_warnings")
        .order_by(CulinaryInfoHistory.changed_at.desc(), CulinaryInfoHistory.id.desc())
        .limit(1)
    )).first()
    if row and is_curator_authored(row[0], row[1], pw):
        return pw.strip()
    return None


async def safety_for_species(db: AsyncSession, sp: Optional[Species],
                             ci: Optional[CulinaryInfo] = None) -> dict:
    """The served decision for one species row. sp=None fails closed (unknown)."""
    if sp is None:
        return safety_decision(None, None)
    return safety_decision(sp.toxicity_severity, sp.edibility_status, await _caution_warning(db, sp, ci))


async def safety_by_names(db: AsyncSession, names: Iterable[str]) -> Dict[str, dict]:
    """{name as sent: decision} for client-supplied scientific names (PDF, walk
    Export summary). Looked up by name_key; a name with no species row gets the
    fail-closed 'unknown' decision — client-sent severity is never trusted."""
    names = [n for n in dict.fromkeys(names) if n]
    keys = {n: normalize_taxon_key(n) for n in names}
    rows = (await db.execute(
        select(Species).where(Species.name_key.in_(set(keys.values())))
    )).scalars().all() if names else []
    by_key = {r.name_key: r for r in rows}
    return {n: await safety_for_species(db, by_key.get(keys[n])) for n in names}
