"""
Fungi edibility resolution service — Phase 12 Prompt 1.

Aggregates FAO Wild Edible Fungi and Mushroom Observer edibility signals into a
single authoritative verdict using a two-source agreement model.

Safety rules (non-negotiable, enforced in code):
  - Toxic OR caution signal from EITHER source → requires_review=True, edibility_verified=False
  - edibility_verified may only be True when requires_review is False
  - FAO returning None (no authoritative data) → requires_review=True
  - confidence < 0.7 → requires_review=True

Public function:
  resolve_fungi_edibility(scientific_name: str) -> dict
"""

import asyncio
import logging
from typing import Optional

log = logging.getLogger(__name__)

# Statuses that always force manual review regardless of source agreement
_UNSAFE_STATUSES = frozenset({"toxic", "caution"})

# Minimum combined confidence required for auto-verification
_MIN_VERIFIED_CONFIDENCE = 0.7

# Confidence model constants
_FAO_BASE_CONFIDENCE      = 0.6   # FAO hit
_MO_CORROBORATE_BONUS     = 0.3   # MO agrees (edible or unknown)
_MO_CONFLICT_PENALTY      = 0.3   # MO explicitly conflicts
_SINGLE_SOURCE_MAX        = 0.5   # cap when only one source has data


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def resolve_fungi_edibility(scientific_name: str) -> dict:
    """
    Resolve fungi edibility for a species by concurrently querying:
      - FAO Wild Edible Fungi (authoritative structured source)
      - Mushroom Observer (community text, lower confidence)

    Returns a dict with keys:
        edibility_status   str    "edible" | "toxic" | "caution" | "conflicted" | "unknown"
        edibility_verified bool   True only if FAO=edible AND MO corroborates AND confidence≥0.7
        confidence         float  0.0–0.9
        sources            list   source dicts from each integration
        requires_review    bool   True if any safety signal, conflict, low confidence, or no FAO data

    SAFETY INVARIANT (enforced at the end of this function — never bypassed):
        If requires_review is True, edibility_verified is always False.
        If either source returns toxic or caution, requires_review is always True.
    """
    from app.integrations.fao_fungi import fetch_fao_edibility
    from app.integrations.mushroom_observer import fetch_mo_edibility

    # Run both integrations concurrently — neither should block the other
    fao_result, mo_result = await asyncio.gather(
        _safe_fetch(fetch_fao_edibility, scientific_name, "fao_fungi"),
        _safe_fetch(fetch_mo_edibility,  scientific_name, "mushroom_observer"),
    )

    fao_status = (fao_result or {}).get("edibility_status", "unknown")
    mo_status  = (mo_result  or {}).get("edibility_status", "unknown")

    sources = []
    if fao_result:
        sources.append({"source": "fao_fungi",         **fao_result})
    if mo_result:
        sources.append({"source": "mushroom_observer", **mo_result})

    # ── Confidence calculation ────────────────────────────────────────────

    if fao_result is None and mo_result is None:
        # Both integrations failed — no data at all
        return _build_result(
            edibility_status="unknown",
            edibility_verified=False,
            confidence=0.0,
            sources=sources,
            requires_review=True,   # no authoritative data → review
        )

    if fao_result is None:
        # FAO missing — no authoritative source, cap confidence
        confidence = min(_SINGLE_SOURCE_MAX, (mo_result or {}).get("confidence", 0.0))
        return _build_result(
            edibility_status=mo_status,
            edibility_verified=False,
            confidence=confidence,
            sources=sources,
            requires_review=True,   # rule: FAO None → always review
        )

    # FAO has data — start from base confidence
    confidence = _FAO_BASE_CONFIDENCE

    # MO corroboration / conflict adjustment
    if mo_result is not None:
        if mo_status in _UNSAFE_STATUSES:
            # MO signals danger — conflict or confirmation of toxicity
            confidence -= _MO_CONFLICT_PENALTY
        elif mo_status == fao_status or mo_status == "unknown":
            # MO agrees or has no opinion — corroboration
            confidence += _MO_CORROBORATE_BONUS
        else:
            # MO has different edibility verdict (e.g. FAO edible, MO unknown+neither)
            confidence -= _MO_CONFLICT_PENALTY
    else:
        # MO unavailable — single source, cap at 0.5
        confidence = min(confidence, _SINGLE_SOURCE_MAX)

    confidence = max(0.0, min(1.0, confidence))  # clamp to [0, 1]

    # ── Edibility status resolution ───────────────────────────────────────

    # Toxic from FAO is definitive
    if fao_status in _UNSAFE_STATUSES:
        resolved_status = fao_status
    elif mo_status in _UNSAFE_STATUSES:
        # MO signals danger even if FAO says otherwise — escalate for review
        resolved_status = mo_status
    elif fao_status == "edible" and mo_status in ("edible", "unknown"):
        resolved_status = "edible"
    elif fao_status == "edible" and mo_status == "caution":
        resolved_status = "conflicted"
    elif fao_status == "unknown":
        resolved_status = mo_status if mo_result else "unknown"
    elif fao_status != mo_status and mo_status != "unknown" and mo_result is not None:
        resolved_status = "conflicted"
    else:
        resolved_status = fao_status

    # ── requires_review determination ────────────────────────────────────
    #
    # SAFETY: Any toxic or caution signal from ANY source → ALWAYS review.
    # This check is explicit and cannot be short-circuited by the logic above.

    any_unsafe = (
        fao_status in _UNSAFE_STATUSES
        or mo_status  in _UNSAFE_STATUSES
        or resolved_status in _UNSAFE_STATUSES
    )

    requires_review = any(
        [
            any_unsafe,                                # safety signal from either source
            resolved_status == "conflicted",           # sources disagree
            resolved_status == "unknown",              # no usable verdict
            confidence < _MIN_VERIFIED_CONFIDENCE,     # insufficient confidence
            fao_result is None,                        # no authoritative FAO data
        ]
    )

    # ── edibility_verified — strict gate ─────────────────────────────────
    #
    # Verified only when:
    #   - FAO explicitly returns "edible"
    #   - MO corroborates (edible or no opinion)
    #   - Combined confidence ≥ 0.7
    #   - No review flag (which covers all unsafe/conflict/unknown cases)

    edibility_verified = (
        not requires_review
        and fao_status == "edible"
        and mo_status in ("edible", "unknown")
        and confidence >= _MIN_VERIFIED_CONFIDENCE
    )

    result = _build_result(
        edibility_status=resolved_status,
        edibility_verified=edibility_verified,
        confidence=confidence,
        sources=sources,
        requires_review=requires_review,
    )

    # FINAL SAFETY INVARIANT — enforced unconditionally at return point.
    # Cannot be bypassed by any code path above.
    if result["requires_review"]:
        result["edibility_verified"] = False

    log.info(
        "[fungi_edibility] %r → status=%r verified=%s confidence=%.2f requires_review=%s "
        "(fao=%r mo=%r)",
        scientific_name,
        result["edibility_status"],
        result["edibility_verified"],
        result["confidence"],
        result["requires_review"],
        fao_status,
        mo_status,
    )

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_result(
    edibility_status: str,
    edibility_verified: bool,
    confidence: float,
    sources: list,
    requires_review: bool,
) -> dict:
    return {
        "edibility_status":   edibility_status,
        "edibility_verified": edibility_verified,
        "confidence":         round(confidence, 3),
        "sources":            sources,
        "requires_review":    requires_review,
    }


async def _safe_fetch(fetch_fn, scientific_name: str, label: str) -> Optional[dict]:
    """
    Call an async fetch function and catch all exceptions.
    Returns None on any error — logs at WARNING.
    """
    try:
        return await fetch_fn(scientific_name)
    except Exception as exc:
        log.warning("[fungi_edibility] %s fetch failed for %r: %s", label, scientific_name, exc)
        return None
