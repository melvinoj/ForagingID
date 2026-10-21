"""
PFAF fallback — Melvin's decisions D2–D5 (21 Oct 2026, audit REPORT section 0).
The ONLY writer of PFAF text into an AI-drafted field. It replaces A5's
_ensure_medicinal_default, which wrote the false "No known traditional medicinal
uses" (and marked it AI-approved) whenever AI text was missing — even when PFAF
lists uses.

  D2  No AI text for a field → the field gets PFAF's own text for that field.
      PFAF has nothing → the field stays empty.
  D3  PFAF "None known" is no data (pfaf._parse already returns None for it).
      Nothing here writes "No known traditional medicinal uses"; a field still
      holding that retired default (or the model's own "No traditional medicinal
      uses recorded…") counts as EMPTY, so the rule below replaces or clears it.
  D4  Provenance is a culinary_info_history row changed_by=PFAF_FALLBACK_CHANGED_BY
      ('pfaf_fallback') — never a prefix in the stored text. The species card and
      Review show the "PFAF text — replace with your own" chip from it.
  D5  Not curator-authored: is_curator_authored() is True only for 'human', so
      the public experience page never publishes this text.

Guards, every write:
  - the field is empty (or holds the retired no-uses default);
  - no changed_by='human' history row on the field (the human lock);
  - PFAF text is never written for a species excluded from AI content
    (AI_NO_CONTENT_VERDICTS — toxic / inedible / not_edible — or a toxic/deadly
    toxicity_severity); a retired default there is cleared to empty (Melvin C2).
A pending AI draft does not block the fill (Melvin C1, 21 Oct): it stays in the
queue and, once approved, replaces the PFAF text through the normal approve
path (culinary.approve_ai_draft: history old_value = the PFAF text).

PFAF text is read from the stored enrichment_sources row (no scraping), parsed
with the app's own pfaf._parse.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.pfaf import PFAFResult, _parse as _pfaf_parse
from app.models.culinary import CulinaryInfo
from app.models.species import (
    AI_NO_CONTENT_VERDICTS,
    PFAF_FALLBACK_CHANGED_BY,
    CulinaryInfoHistory,
    EnrichmentSource,
    Species,
    is_pfaf_fallback,
    is_toxic_severity,
)
from app.services.ai_placeholder import (has_no_medicinal_uses_claim, is_only_no_medicinal_uses_claim,
                                         strip_no_medicinal_uses_claims)

log = logging.getLogger(__name__)

# AI-drafted field → the PFAFResult attribute holding PFAF's own text for it.
# A field missing here has no PFAF counterpart (taste_notes, recipe, id_notes)
# and stays empty without AI text. medicinal_folklore is deliberately absent: its
# only PFAF source is the same "Medicinal Uses" section, so filling it as well
# would show one PFAF paragraph twice on the card.
PFAF_FALLBACK_SOURCES = {"medicinal_notes": "medicinal_folklore"}

AI_DRAFT_FIELDS = ("taste_notes", "medicinal_notes", "recipe", "medicinal_folklore")

# History marker when a retired no-uses default is cleared — PFAF has no text
# for the field, or the species is toxic/inedible (Melvin C2, 21 Oct 2026).
CLEAR_CHANGED_BY = "system:clear_false_default"

_MEDICINAL_FIELDS = ("medicinal_notes", "medicinal_folklore")


@dataclass
class FallbackDecision:
    field: str
    action: str                  # "fill" | "clear" | "strip" | "skip"
    reason: str                  # why — see _plan()
    old_value: Optional[str] = None
    new_value: Optional[str] = None


def _empty_equivalent(field: str, value: Optional[str]) -> bool:
    """Empty, or the retired no-uses default in a medicinal field (D3)."""
    if not (value or "").strip():
        return True
    return field in _MEDICINAL_FIELDS and is_only_no_medicinal_uses_claim(value)


def ai_content_excluded(species: Species) -> bool:
    """Same exclusion as AI generation, plus a toxic/deadly severity (fails safe)."""
    return species.edibility_status in AI_NO_CONTENT_VERDICTS \
        or is_toxic_severity(species.toxicity_severity)


def _latest_pfaf_row(species_id: int, *columns):
    """SELECT columns of the species' latest stored PFAF page (one definition)."""
    return (
        select(*columns)
        .where(EnrichmentSource.species_id == species_id)
        .where(EnrichmentSource.source_name == "pfaf")
        .where(EnrichmentSource.raw_response_json.is_not(None))
        .where(EnrichmentSource.raw_response_json != "")
        .order_by(EnrichmentSource.retrieved_at.desc(), EnrichmentSource.id.desc())
        .limit(1)
    )


async def stored_pfaf(session: AsyncSession, species: Species) -> Optional[PFAFResult]:
    """The species' latest stored PFAF page, parsed. None when no page was stored."""
    row = (await session.execute(
        _latest_pfaf_row(species.id, EnrichmentSource.source_url, EnrichmentSource.raw_response_json)
    )).first()
    if not row:
        return None
    try:
        return _pfaf_parse(species.scientific_name, row[0] or "", row[1])
    except Exception as e:
        log.warning("[pfaf_fallback] stored PFAF page for %r did not parse: %s", species.scientific_name, e)
        return None


async def stored_pfaf_medicinal_text(session: AsyncSession, species: Species) -> Optional[str]:
    """
    PFAF's own Medicinal Uses text from the stored page — the context the AI
    medicinal draft is given (Melvin A, 21 Oct 2026) and the fallback text.
    None when there is no stored page or PFAF says "None known" (D3: no data).
    """
    row = (await session.execute(_latest_pfaf_row(
        species.id, EnrichmentSource.id, EnrichmentSource.species_id, EnrichmentSource.retrieved_at))).first()
    if row is None:
        return None
    key = tuple(row)
    if key not in _MEDICINAL_TEXT_BY_ROW:             # stored pages are append-only
        pfaf = await stored_pfaf(session, species)
        _MEDICINAL_TEXT_BY_ROW[key] = ((pfaf.medicinal_folklore or "").strip() or None) if pfaf else None
    return _MEDICINAL_TEXT_BY_ROW[key]


# (enrichment_sources.id, species_id, retrieved_at) → parsed PFAF Medicinal Uses
# text. A stored page never changes (a re-fetch adds a new row), so a parse
# (~50 ms) is done once per run; the key also tells apart a restored DB's rows.
_MEDICINAL_TEXT_BY_ROW: dict = {}


# Shown by the approve path (422) and in Review next to such a draft.
FALSE_NO_USES_REASON = (
    "This draft says the species has no traditional medicinal uses, but PFAF lists "
    "Medicinal Uses for it. Reject it, or edit it into your own text."
)


async def is_false_no_uses_claim(session: AsyncSession, species: Species, field: str,
                                 text: Optional[str]) -> bool:
    """
    The ONLY definition of a false "no uses" draft: a medicinal draft that says
    "No (known) traditional medicinal uses…" while the species' stored PFAF page
    lists Medicinal Uses. With no PFAF text the claim may be true and is allowed.
    """
    if field not in _MEDICINAL_FIELDS or not has_no_medicinal_uses_claim(text):
        return False
    return await stored_pfaf_medicinal_text(session, species) is not None


async def _human_locked(session: AsyncSession, ci: CulinaryInfo, field: str) -> bool:
    if not ci.id:
        return False
    return (await session.scalar(
        select(CulinaryInfoHistory.id)
        .where(CulinaryInfoHistory.culinary_info_id == ci.id)
        .where(CulinaryInfoHistory.field_name == field)
        .where(CulinaryInfoHistory.changed_by == "human")
        .limit(1)
    )) is not None


_UNSET = object()


async def _plan(session: AsyncSession, species: Species, ci: CulinaryInfo, field: str,
                pfaf_cache: dict) -> FallbackDecision:
    current = getattr(ci, field, None)
    if field not in PFAF_FALLBACK_SOURCES:
        return FallbackDecision(field, "skip", "no_pfaf_counterpart", current)
    if not _empty_equivalent(field, current):
        if field in _MEDICINAL_FIELDS and has_no_medicinal_uses_claim(current):
            # Real text with a "no uses" sentence in it (after culinary text, or
            # at the end): only that sentence goes; no PFAF text (Melvin, 21 Oct).
            if await _human_locked(session, ci, field):
                return FallbackDecision(field, "skip", "human_locked", current)
            return FallbackDecision(field, "strip", "embedded_claim", current,
                                    strip_no_medicinal_uses_claims(current))
        return FallbackDecision(field, "skip", "has_text", current)
    if await _human_locked(session, ci, field):
        return FallbackDecision(field, "skip", "human_locked", current)
    holds_default = bool((current or "").strip())
    if ai_content_excluded(species):
        if holds_default:
            return FallbackDecision(field, "clear", "toxic_or_inedible", current, None)
        return FallbackDecision(field, "skip", "toxic_or_inedible", current)
    if pfaf_cache.get("pfaf", _UNSET) is _UNSET:
        pfaf_cache["pfaf"] = await stored_pfaf(session, species)
    pfaf = pfaf_cache["pfaf"]
    text = (getattr(pfaf, PFAF_FALLBACK_SOURCES[field], None) or "").strip() if pfaf else ""
    if text:
        return FallbackDecision(field, "fill", "pfaf_text", current, text)
    reason = "pfaf_none" if pfaf else "no_pfaf_page"
    if holds_default:
        return FallbackDecision(field, "clear", reason, current, None)
    return FallbackDecision(field, "skip", reason, current)


async def plan_pfaf_fallback(session: AsyncSession, species: Species, ci: CulinaryInfo,
                             fields: Iterable[str] = AI_DRAFT_FIELDS) -> list:
    """What apply_pfaf_fallback would do, without writing anything (dry runs)."""
    cache: dict = {}
    return [await _plan(session, species, ci, f, cache) for f in fields]


def _drop_ai_approved(ci: CulinaryInfo, field: str) -> None:
    """PFAF text is not AI content; an emptied field has nothing approved."""
    try:
        approved = json.loads(ci.ai_approved_fields_json) if ci.ai_approved_fields_json else []
    except (ValueError, TypeError):
        return
    if isinstance(approved, list) and field in approved:
        ci.ai_approved_fields_json = json.dumps([f for f in approved if f != field])


async def apply_pfaf_fallback(session: AsyncSession, species: Species, ci: Optional[CulinaryInfo],
                              fields: Iterable[str] = AI_DRAFT_FIELDS) -> list:
    """
    Apply D2 to each field: fill with PFAF text, clear a retired no-uses
    default, or leave it. Writes only inside the session (the caller commits);
    every write has a culinary_info_history row. Returns the decisions.
    """
    if ci is None:
        return []
    if not ci.id:
        await session.flush()
    decisions = await plan_pfaf_fallback(session, species, ci, fields)
    for d in decisions:
        if d.action == "skip":
            continue
        setattr(ci, d.field, d.new_value)
        if d.action != "strip":            # a stripped text is still the approved AI text
            _drop_ai_approved(ci, d.field)
        session.add(CulinaryInfoHistory(
            culinary_info_id=ci.id,
            field_name=d.field,
            old_value=d.old_value if (d.old_value or "").strip() else None,
            new_value=d.new_value,
            changed_at=datetime.utcnow(),
            changed_by=PFAF_FALLBACK_CHANGED_BY if d.action == "fill" else CLEAR_CHANGED_BY,
            notes=("PFAF Medicinal Uses — no AI text available (D2)" if d.action == "fill"
                   else "false 'no medicinal uses' sentence removed, rest kept (D3)" if d.action == "strip"
                   else f"retired no-uses default — no data ({d.reason}, D3)"),
        ))
        log.info("[pfaf_fallback] %s %s for %r (%s)", d.action, d.field, species.scientific_name, d.reason)
    return decisions


async def pfaf_fallback_fields(session: AsyncSession, ci_ids: Iterable[int]) -> dict:
    """{culinary_info_id: {field, …}} — fields whose CURRENT value is PFAF fallback text (D4 chip)."""
    ids = [i for i in ci_ids if i]
    if not ids:
        return {}
    rows = (await session.execute(
        select(CulinaryInfoHistory.culinary_info_id, CulinaryInfoHistory.field_name,
               CulinaryInfoHistory.changed_by, CulinaryInfoHistory.new_value)
        .where(CulinaryInfoHistory.culinary_info_id.in_(ids))
        .where(CulinaryInfoHistory.field_name.in_(tuple(PFAF_FALLBACK_SOURCES)))
        .order_by(CulinaryInfoHistory.changed_at.desc(), CulinaryInfoHistory.id.desc())
    )).all()
    latest: dict = {}
    for ci_id, field, changed_by, new_value in rows:
        latest.setdefault((ci_id, field), (changed_by, new_value))
    current = {c.id: c for c in (await session.execute(
        select(CulinaryInfo).where(CulinaryInfo.id.in_({k[0] for k in latest}))
    )).scalars().all()} if latest else {}
    out: dict = {}
    for (ci_id, field), (changed_by, new_value) in latest.items():
        ci = current.get(ci_id)
        if ci is not None and is_pfaf_fallback(changed_by, new_value, getattr(ci, field, None)):
            out.setdefault(ci_id, set()).add(field)
    return out
