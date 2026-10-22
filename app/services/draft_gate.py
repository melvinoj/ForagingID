"""
draft_gate.py — the ONE pre-save check and saver for AI-generated drafts
(taste_notes, recipe, medicinal_notes, medicinal_folklore). Melvin, 22 Oct 2026,
after the AI draft census: every path that creates an AI draft (enrichment,
backfill, Repopulate, Regenerate, recipe regenerate) saves through
save_ai_draft(); nothing else constructs an AI draft.

A draft is NOT saved when (check_ai_draft):
  placeholder        the shared placeholder / refusal predicate (ai_placeholder)
  no_use             its substance is "no medicinal / culinary use known", any wording
  chat_phrasing      "your notes", "here you go", "I appreciate your request",
                     "written in … voice", "based solely / strictly on the provided"
  no_edible_parts    a recipe or taste note for a species whose edible_parts is
                     empty or "None known"
  toxic_culinary     a taste note or recipe on a toxic / deadly / inedible species
  deadly_internal    a medicinal draft on a deadly species that describes
                     internal use or doses
Curly and straight apostrophes match alike. Before a recipe is saved, a leading
"None known" safety line (every variant the census found) is stripped.

Skips are logged and counted — never silent: a DraftSummary (contextvar) is
filled by every save_ai_draft call inside summary_scope(); run summaries and
endpoint responses report it. Saving never invalidates another draft: a new
version sits beside the pending one in Review until Melvin keeps one
(culinary.approve_ai_draft invalidates the others then).
"""
import contextvars
import json
import logging
import re
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.models.species import AI_NO_CONTENT_VERDICTS, SpeciesAIDraft
from app.services.ai_placeholder import is_ai_placeholder, is_only_no_medicinal_uses_claim

log = logging.getLogger(__name__)

AI_DRAFT_FIELDS = ("taste_notes", "recipe", "medicinal_notes", "medicinal_folklore")
MEDICINAL = ("medicinal_notes", "medicinal_folklore")
CULINARY = ("taste_notes", "recipe")


def _plain(text: str) -> str:
    """Curly quotes → straight, whitespace collapsed (matching only)."""
    t = (text or "").replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", t).strip()


CHAT = re.compile(
    r"\byour notes\b|\bhere you go\b|\bI appreciate your request\b|\bwritten in\b.{0,60}?\bvoice\b"
    r"|\bbased (solely|strictly) on the provided\b", re.I)

# "No medicinal uses known / recorded / documented …" — the census wordings,
# including "No specific medicinal uses are recorded" (3714).
_NO_MED = re.compile(
    r"\b(has|have|there (are|is)|with|lacks)\s+no\s+((documented|recorded|known|reported|established|significant|"
    r"specific|traditional|notable)\s+)*((traditional|folk|herbal)\s+)?(medicinal|herbal)\s+(use|uses|history|application)"
    r"|\bno\s+((documented|recorded|known|reported|traditional|specific)\s+)+((traditional|folk)\s+)?"
    r"(medicinal|herbal)\s+(use|uses|history|applications?)"
    r"|\b(lacks|without)\s+(any\s+)?(known\s+)?(traditional\s+)?medicinal\s+uses?"
    r"|\b(medicinal|herbal)\s+uses?\s+(are|is)\s+(not|un)\s*(documented|recorded|known|reported)"
    r"|\bnot\s+(documented|recorded|known|cited)\s+(as|for)\s+(a\s+|any\s+)?(traditional\s+)?(medicinal|herbal)", re.I)
_NO_CULINARY = re.compile(
    r"\bno\s+((known|documented|recorded|reported)\s+)+(culinary|food|edible|tasting)\s+(use|uses|account|value)"
    r"|\bno\s+tasting\s+or\s+culinary\s+account\b|\bhas no known food use\b"
    r"|\b(is|are)\s+not\s+(known\s+to\s+be\s+)?edible\b|\bnone known\b.{0,40}\bedible\b", re.I)

_DEADLY_INTERNAL = re.compile(
    r"\binternal(ly)?\b|\btaken\b|\bingest\w*|\bswallow\w*|\bdrunk\b|\bdrink\b|\b(tea|teas|infusion|tincture|"
    r"decoction|syrup|capsules?|tablets?)\b|\bdos(e|es|age)\b|\b\d+(\.\d+)?\s?(mg|g|ml|drops?|grams?|cups?|"
    r"teaspoons?|tsp|tablespoons?|tbsp)\b", re.I)

# Leading safety line on a recipe — every census variant ("None known",
# "**None known**", "Safety note: None known", "Safety Warning: None known",
# "Safety note — preparation warning: None known", "SAFETY (mandatory): None
# known", "None known — though …").
_NONE_LINE = re.compile(r"^((safety( note| warning)?( \(mandatory\))?|preparation warnings?|warning)"
                        r"([\s:—–-]+preparation warnings?)?[\s:—–-]+)?none known\b", re.I)


def strip_none_known_line(text: str) -> str:
    """Drop a leading "None known" safety line (and a '---' rule right after it)."""
    lines = (text or "").split("\n")
    if not lines or not _NONE_LINE.match(re.sub(r"[*_#>`]", "", lines[0]).strip()):
        return text
    rest = lines[1:]
    while rest and not rest[0].strip():
        rest = rest[1:]
    if rest and re.fullmatch(r"\s*-{3,}\s*", rest[0]):
        rest = rest[1:]
    return "\n".join(rest).strip()


def _no_edible_parts(edible_parts: Optional[str]) -> bool:
    t = (edible_parts or "").strip().lower()
    return not t or t in ("none known", "none known.", "none") or t.startswith("none - toxic")


def is_no_use_claim(field: str, text: str) -> bool:
    head = _plain(text)[:400]
    if field in MEDICINAL:
        return is_only_no_medicinal_uses_claim(text) or bool(_NO_MED.search(head))
    return bool(_NO_CULINARY.search(head))


@dataclass
class GateResult:
    ok: bool
    text: Optional[str] = None
    reason: Optional[str] = None       # one of the codes in the module docstring


def check_ai_draft(field: str, text: Optional[str], species, ci) -> GateResult:
    if not (text or "").strip():
        return GateResult(False, reason="empty")
    if field == "recipe":
        text = strip_none_known_line(text)
        if not text.strip():
            return GateResult(False, reason="empty")
    edib = (getattr(species, "edibility_status", None) or "").lower()
    sev = (getattr(species, "toxicity_severity", None) or "").lower()
    if field in CULINARY and (edib in AI_NO_CONTENT_VERDICTS or sev in ("toxic", "deadly")):
        return GateResult(False, reason="toxic_culinary")
    if field in CULINARY and _no_edible_parts(getattr(ci, "edible_parts", None) if ci else None):
        return GateResult(False, reason="no_edible_parts")
    if is_ai_placeholder(field, text):
        return GateResult(False, reason="placeholder")
    if CHAT.search(_plain(text)):
        return GateResult(False, reason="chat_phrasing")
    if is_no_use_claim(field, text):
        return GateResult(False, reason="no_use")
    if field in MEDICINAL and sev == "deadly" and _DEADLY_INTERNAL.search(_plain(text)):
        return GateResult(False, reason="deadly_internal")
    return GateResult(True, text=text)


@dataclass
class DraftSummary:
    created: int = 0
    skipped: Counter = field(default_factory=Counter)
    skipped_examples: list = field(default_factory=list)     # (species, field, reason)
    review_queued: Counter = field(default_factory=Counter)  # source-update review drafts, by field

    def as_dict(self) -> dict:
        return {"drafts_created": self.created, "drafts_skipped": dict(self.skipped),
                "drafts_skipped_total": sum(self.skipped.values()),
                "review_drafts_queued": dict(self.review_queued)}


_summary: contextvars.ContextVar[Optional[DraftSummary]] = contextvars.ContextVar("lm_draft_summary", default=None)


def current_summary() -> Optional["DraftSummary"]:
    return _summary.get()


@contextmanager
def summary_scope():
    """Collect every save_ai_draft outcome inside this block."""
    s = DraftSummary()
    token = _summary.set(s)
    try:
        yield s
    finally:
        _summary.reset(token)


def save_ai_draft(session, species, ci, field_name: str, text: Optional[str], *,
                  model: Optional[str], context_json: Optional[str] = None) -> Optional[SpeciesAIDraft]:
    """Check, then add one pending AI draft beside any existing ones. Returns the
    draft, or None when the check refused it (logged + counted)."""
    if field_name not in AI_DRAFT_FIELDS:
        raise ValueError(f"save_ai_draft is for AI draft fields only, not {field_name!r}")
    g = check_ai_draft(field_name, text, species, ci)
    s = _summary.get()
    if not g.ok:
        log.warning("[draft gate] not saved: %r → %s — %s (starts: %r)", species.scientific_name, field_name,
                    g.reason, _plain(text or "")[:80])
        if s is not None:
            s.skipped[g.reason] += 1
            if len(s.skipped_examples) < 200:
                s.skipped_examples.append((species.scientific_name, field_name, g.reason))
        return None
    d = SpeciesAIDraft(species_id=species.id, field_name=field_name, draft_text=g.text, status="pending",
                       generated_at=datetime.utcnow(), generation_context_json=context_json, model=model)
    session.add(d)
    if s is not None:
        s.created += 1
    return d
