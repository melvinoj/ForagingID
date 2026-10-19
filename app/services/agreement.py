"""
agreement.py — the dual-source auto-approve agreement rule, as one pure function.

Used by scan._identify_scanned (the only auto-approve path) and by the
read-only dry run / tests, so the rule that is tested is the rule that runs.
No DB access, no I/O, no side effects.

Rule (unchanged since 15 Oct 2026, plus the regional-demotion switch):
  * never when force_review (file uploads, fungi, unknown origin, overrides);
  * both PlantNet and iNaturalist must have been used and returned candidates;
  * PlantNet's #1 — in the DECISION view — must equal iNat's #1;
  * that species must reach `threshold` on its OWN PlantNet score and its OWN
    iNat score;
  * a promoted iNat candidate (iNat #1 ≠ PlantNet #1 but inside PlantNet's
    top 5, evaluated in the decision view) never counts as agreement.

Decision view: PlantNet's raw order unless demote_for_approve is True, in which
case the regionally demoted order (European-listed first) is used. With
demote_for_approve False the result is identical to the pre-demotion rule.
"""

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

from app.services.regional_demotion import raw_order


@dataclass
class AgreementDecision:
    dual_agree: bool
    pn_top_name: Optional[str]          # decision-view PlantNet #1
    pn_top_score: float
    inat_top_name: Optional[str]
    inat_top_score: float
    pn_raw_top_name: Optional[str]      # PlantNet's own #1 (audit / note)
    promoted_in_decision: bool
    agree_after_demotion: bool          # agreement exists only because of demotion

    @property
    def names_agree(self) -> Optional[bool]:
        """dual_source_agreement evidence: None when either side is empty."""
        if self.pn_top_name is None or self.inat_top_name is None:
            return None
        return self.pn_top_name == self.inat_top_name


def decide_agreement(
    pn_candidates: Sequence,                  # PlantNet candidates in demoted order (with raw_rank)
    inat_hits: Sequence[Tuple[str, float]],   # [(scientific_name, gating score)], iNat's order
    *,
    demote_for_approve: bool,
    force_review: bool,
    use_pn: bool,
    use_inat: bool,
    threshold: float,
) -> AgreementDecision:
    pn_raw = raw_order(pn_candidates) if pn_candidates else []
    pn_dec = list(pn_candidates) if demote_for_approve else pn_raw

    pn_top_name  = pn_dec[0].scientific_name if pn_dec else None
    pn_top_score = pn_dec[0].score if pn_dec else 0.0
    inat_top_name  = inat_hits[0][0] if inat_hits else None
    inat_top_score = inat_hits[0][1] if inat_hits else 0.0
    pn_raw_top_name = pn_raw[0].scientific_name if pn_raw else None

    dec_ranked = [c.scientific_name for c in pn_dec]
    promoted = bool(
        dec_ranked and inat_hits
        and inat_top_name != dec_ranked[0]
        and inat_top_name in dec_ranked[:5]
    )

    dual_agree = (
        not force_review
        and not promoted
        and use_pn
        and use_inat
        and pn_top_name is not None
        and inat_top_name is not None
        and pn_top_name == inat_top_name
        and pn_top_score >= threshold
        and inat_top_score >= threshold
    )
    return AgreementDecision(
        dual_agree=bool(dual_agree),
        pn_top_name=pn_top_name,
        pn_top_score=pn_top_score,
        inat_top_name=inat_top_name,
        inat_top_score=inat_top_score,
        pn_raw_top_name=pn_raw_top_name,
        promoted_in_decision=promoted,
        agree_after_demotion=bool(
            dual_agree and demote_for_approve
            and pn_raw_top_name is not None and pn_raw_top_name != pn_top_name
        ),
    )
