"""
Safety gate — DB side of app.models.species.safety_decision() (audit P1 /
batch 5, 21 Oct 2026). The decision itself lives in safety_decision(); this
module only gathers its inputs (severity, verdict, the approved caution
warning) for one species or for a list of names sent by a client.

The caution warning is the curator-authored preparation_warnings (an approved
curator-review warning draft counts — approval writes changed_by='human'),
the same rule as the experience export's rule 8 (gates.caution_warning).

Batch 6 (B2-03): the decision also carries the species' warnings —
`warnings` (in-app: full text + reviewed flag, species_warnings()) and
`handout_warnings` (outgoing: curator-authored only, handout_warnings()).
"""
from typing import Dict, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.culinary import CulinaryInfo
from app.models.species import (CulinaryInfoHistory, Species, WARNING_FIELDS, handout_warnings,
                                safety_decision, species_warnings)
from app.services.taxonomy import normalize_taxon_key


async def _warning_fields(db: AsyncSession, ci: Optional[CulinaryInfo]) -> dict:
    """{column: (current, latest_changed_by, latest_new_value)} for the warning columns."""
    if ci is None:
        return {}
    out = {}
    for col in WARNING_FIELDS.values():
        row = (await db.execute(
            select(CulinaryInfoHistory.changed_by, CulinaryInfoHistory.new_value)
            .where(CulinaryInfoHistory.culinary_info_id == ci.id)
            .where(CulinaryInfoHistory.field_name == col)
            .order_by(CulinaryInfoHistory.changed_at.desc(), CulinaryInfoHistory.id.desc())
            .limit(1)
        )).first()
        out[col] = (getattr(ci, col, None), row[0] if row else None, row[1] if row else None)
    return out


def _with_warnings(decision: dict, warnings: dict) -> dict:
    decision["warnings"] = warnings
    decision["handout_warnings"] = handout_warnings(decision["level"], warnings)
    return decision


async def safety_for_species(db: AsyncSession, sp: Optional[Species],
                             ci: Optional[CulinaryInfo] = None) -> dict:
    """The served decision for one species row. sp=None fails closed (unknown)."""
    if sp is None:
        return _with_warnings(safety_decision(None, None), species_warnings({}))
    if ci is None:
        ci = await db.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == sp.id))
    warnings = species_warnings(await _warning_fields(db, ci))
    prep = warnings["preparation"]
    caution_warning = prep["text"] if (prep and prep["reviewed"]
                                       and (sp.edibility_status or "").strip().lower() == "caution") else None
    return _with_warnings(safety_decision(sp.toxicity_severity, sp.edibility_status, caution_warning), warnings)


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
