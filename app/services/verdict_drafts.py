"""
Verdict drafts (fix batch 3b, Melvin 20 Oct 2026) — the ONLY definition of how
a species' stored sources become a PROPOSED edibility verdict + severity, and of
"has this species changed since its draft was made".

A proposal is a review draft (species_ai_drafts, field_name 'edibility_status',
model MODEL). Nothing here writes a verdict: the curator approves one species at
a time through POST /api/edibility/verdict-drafts/{id}/approve, which writes
through severity_for_verdict with history rows changed_by='human'. Verdict
drafts are never in "Approve all" (they are not listed in AI Draft Review).

Sources — stored only, never a new external call, never a family heuristic
(no-veto decision; Wikidata's "likely_edible" comes from a family list and is
listed as excluded):

  severity   a recorded toxic / deadly toxicity_severity → 'toxic' (keeps deadly)
  human      the latest human verdict in the history tables, when it is a real
             verdict → that verdict
  conditions curator edibility conditions → 'caution'
  pfaf       the stored PFAF page (parsed offline with pfaf._parse):
               rating ≥ 1, Known Hazards "None known"            → 'edible'
               rating ≥ 1, hazards without poison/toxic wording   → 'caution'
               rating ≥ 1, hazards WITH poison/toxic wording      → no verdict:
                          PFAF contradicts itself ("say why")
               rating 0,   hazards with poison/toxic wording      → 'toxic'
               rating 0,   no such wording / rating missing       → no verdict
             "poison/toxic wording" ignores negated mentions in the same sentence
             ("No known toxicity", "non-toxic"); a genus-level card, or a page
             stored for another name, gives no verdict
  fungi      a stored FAO / Mushroom Observer lookup, when it names a status

Combining: no verdict from any source → 'unknown' (evidence 'thin'). Sources
naming different verdicts → 'unknown' (evidence 'conflict') — except edible vs
caution, where the more careful 'caution' is proposed. 'deadly' is never
proposed from text: only a recorded deadly severity is kept. The proposed
severity is severity_for_verdict(verdict, current severity) — the same rule the
approve path applies — so a proposal never lowers a recorded severity.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Iterable, List, Optional

from app.models.species import SeverityRuleError, severity_for_verdict

MODEL = "verdict_sweep"
FIELD = "edibility_status"
VERDICTS = ("edible", "caution", "inedible", "toxic", "unknown")
NO_VERDICT = (None, "", "unknown", "unclear")


def record_rejection_reason(draft, reason: str) -> None:
    """The ONLY writer of a draft's rejection reason (Melvin, 21 Oct 2026):
    generation_context_json["rejected_reason"] / ["rejected_at"] — the same
    place the 21 Oct invalidations keep theirs (invalidated_reason /
    invalidated_at). Does not change the draft's status; the caller does."""
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("rejection reason is empty")
    try:
        ctx = json.loads(draft.generation_context_json or "{}")
    except ValueError:
        ctx = {"original_context": draft.generation_context_json}   # never drop what was there
    if not isinstance(ctx, dict):
        ctx = {"original_context": ctx}
    ctx["rejected_reason"] = reason
    ctx["rejected_at"] = datetime.utcnow().isoformat()
    draft.generation_context_json = json.dumps(ctx, ensure_ascii=False)

# Poison/toxic wording in a PFAF Known Hazards text, and the negations that
# cancel it within the same sentence ("No known toxicity", "non-toxic", "No
# members of this genus are known to be poisonous").
TOXIC_WORDING = re.compile(r"\b(poison\w*|toxic\w*|toxin\w*|deadly|fatal\w*|lethal)\b", re.I)
NEGATION = re.compile(r"\b(no|not|non|never|without|rather\s+than)\b", re.I)
NEGATION_WINDOW_WORDS = 10


def toxic_mentions(text: Optional[str]) -> tuple:
    """(affirmed, negated) poison/toxic words in text. A word is negated when a
    negation stands within the NEGATION_WINDOW_WORDS words before it in the same
    clause (split at . ; , : ! ? and newlines — so "Although no reports …, some
    members … have poisonous fruits" still counts the second clause). Only affirmed words count as poison/toxic wording."""
    affirmed, negated = [], []
    t = text or ""
    for m in TOXIC_WORDING.finditer(t):
        before = t[:m.start()]
        cut = max(before.rfind(c) for c in (". ", "; ", ", ", ": ", "! ", "? ", "\n"))
        window = " ".join(re.findall(r"[\w'-]+", before[cut + 1:])[-NEGATION_WINDOW_WORDS:])
        (negated if NEGATION.search(window.replace("-", " ")) else affirmed).append(m.group(0))
    return affirmed, negated


def _page_name(url: Optional[str]) -> Optional[str]:
    from urllib.parse import parse_qs, urlparse
    try:
        v = parse_qs(urlparse(url or "").query).get("LatinName")
        return v[0].strip() if v else None
    except Exception:
        return None

EVIDENCE_LABELS = {
    "multiple_sources": "several stored sources agree",
    "single_source": "one stored source",
    "thin": "not enough stored evidence",
    "conflict": "stored sources disagree",
}


def _quote(text: Optional[str]) -> Optional[str]:
    t = (text or "").strip()
    return t or None


def pfaf_signal(pfaf: Optional[dict], species_name: Optional[str] = None) -> Optional[dict]:
    """pfaf = {rating, hazards, edible_uses, url, enrichment_source_id} from the
    stored page, or None. Returns a source entry (says = verdict or None).
    species_name: the card's name — a genus-level card, or a page stored for a
    different name, gives no verdict (the evidence isn't about this species)."""
    if not pfaf:
        return None
    from app.services.taxonomy import normalize_taxon_key
    rating = pfaf.get("rating")
    hazards = _quote(pfaf.get("hazards"))
    no_hazards = hazards is None or hazards.lower() == "none known"
    affirmed, negated = toxic_mentions(hazards) if (hazards and not no_hazards) else ([], [])
    toxic_words = bool(affirmed)
    words = ", ".join(f"'{w}'" for w in dict.fromkeys(w.lower() for w in affirmed))
    entry = {
        "source": "pfaf",
        "label": f"PFAF (edibility rating {rating if rating is not None else '—'}/5)",
        "quotes": [q for q in (
            {"field": "Known Hazards", "text": hazards} if hazards else None,
            {"field": "Edible Uses", "text": _quote(pfaf.get("edible_uses"))} if _quote(pfaf.get("edible_uses")) else None,
        ) if q],
        "url": pfaf.get("url"),
        "ref": {"enrichment_source_id": pfaf.get("enrichment_source_id")},
    }
    if species_name and len(species_name.split()) < 2:
        return {**entry, "says": None,
                "why": f"'{species_name}' is a genus-level card — PFAF evidence isn't about one species"}
    page = _page_name(pfaf.get("url"))
    if species_name and page and normalize_taxon_key(page) != normalize_taxon_key(species_name):
        return {**entry, "says": None, "why": f"the stored PFAF page is for '{page}', not this species"}
    if rating is None:
        return {**entry, "says": None, "why": "no edibility rating on the stored page"}
    if rating >= 1 and no_hazards:
        return {**entry, "says": "edible", "why": f"rated {rating}/5 for food, Known Hazards: none known"}
    if rating >= 1 and not toxic_words:
        return {**entry, "says": "caution", "why": f"rated {rating}/5 for food, with a known hazard"
                + (" (its poison/toxic wording is negated)" if negated else "")}
    if rating >= 1:
        return {**entry, "says": None, "conflicting": True,
                "why": f"rated {rating}/5 for food, but its hazard text uses {words} — read the text and decide"}
    if toxic_words:
        return {**entry, "says": "toxic", "why": f"no edible use (rating 0) and its hazard text uses {words}"}
    return {**entry, "says": None,
            "why": "no edible use (rating 0) and no poison/toxic hazard — no evidence either way"}


def propose(current_severity: Optional[str], sources: Iterable[dict]) -> dict:
    """Combine source entries (each with 'says': a verdict or None) into a
    proposal: {edibility_status, toxicity_severity, evidence, reason}."""
    sources = list(sources)
    named = [s for s in sources if s.get("says") in VERDICTS and s.get("says") != "unknown"]
    says = {s["says"] for s in named}
    # edible and caution are one class (caution is the careful form of edible);
    # toxic and inedible are classes of their own.
    classes = {"edible/caution" if v in ("edible", "caution") else v for v in says}
    contradictions = [s for s in sources if s.get("conflicting")]

    if contradictions and not named:
        verdict, evidence = "unknown", "conflict"
        reason = "; ".join(f"{s['label']}: {s['why']}" for s in contradictions)
    elif not named:
        verdict, evidence = "unknown", "thin"
        checked = [f"{s['label']}: {s['why']}" for s in sources if s.get("why")]
        reason = "No stored source gives a verdict" + (f" ({'; '.join(checked)})" if checked else
                                                      " — no stored PFAF page, recorded severity, human verdict, "
                                                      "curator condition or fungi lookup with a result")
    elif len(classes) > 1 or contradictions:
        verdict, evidence = "unknown", "conflict"
        reason = "Sources disagree: " + "; ".join(
            f"{s['label']} says {s['says']} ({s['why']})" if s.get("says") else f"{s['label']}: {s['why']}"
            for s in named + contradictions)
    else:
        verdict = "caution" if "caution" in says else next(iter(says))
        evidence = "multiple_sources" if len(named) > 1 else "single_source"
        reason = "; ".join(f"{s['label']} says {s['says']} ({s['why']})" for s in named)
        if says == {"edible", "caution"}:
            reason += " — the more careful 'caution' is proposed"

    try:
        severity = severity_for_verdict(verdict, current_severity)
    except SeverityRuleError as e:          # e.g. edible over a recorded toxic severity
        verdict, evidence = "unknown", "conflict"
        reason = f"{reason}; but {e}"
        severity = severity_for_verdict("unknown", current_severity)
    return {"edibility_status": verdict, "toxicity_severity": severity,
            "evidence": evidence, "reason": reason}


# ---------------------------------------------------------------------------
# "Changed since drafting" — the approve path refuses when the species'
# verdict state or its verdict history moved after the draft was made.
# ---------------------------------------------------------------------------
STATE_KEYS = ("edibility_status", "toxicity_severity", "edibility_verified", "edibility_verified_by",
              "last_species_history_id", "last_ci_verdict_history_id")


def verdict_state(sp, last_species_history_id: Optional[int], last_ci_verdict_history_id: Optional[int]) -> dict:
    return {
        "edibility_status": sp.edibility_status,
        "toxicity_severity": sp.toxicity_severity,
        "edibility_verified": bool(sp.edibility_verified),
        "edibility_verified_by": sp.edibility_verified_by,
        "last_species_history_id": last_species_history_id,
        "last_ci_verdict_history_id": last_ci_verdict_history_id,
    }


def changes_since(at_draft: Optional[dict], now: dict) -> List[str]:
    """Human-readable differences between the state stored in the draft and
    now; empty when unchanged. A draft with no stored state counts as changed."""
    if not at_draft:
        return ["the draft has no record of the species' state when it was made"]
    out = []
    for k in STATE_KEYS:
        if at_draft.get(k) != now.get(k):
            if k.startswith("last_"):
                out.append("its verdict history has new rows")
            else:
                out.append(f"{k} was {at_draft.get(k)!r}, now {now.get(k)!r}")
    return sorted(set(out), key=out.index)
