"""
Tests for app/services/agreement.py — the auto-approve agreement rule.

The key property: with demote_for_approve=False the decision is IDENTICAL to the
pre-demotion rule (scan.py before 19 Oct 2026), which is re-stated literally in
_old_rule() below and compared exhaustively over generated cases.

Run from project root:  python -m pytest tests/test_agreement.py -v
Or standalone:          python tests/test_agreement.py
"""

import itertools
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.integrations.plantnet import PlantNetCandidate
from app.services.agreement import decide_agreement
from app.services.regional_demotion import demote_candidates

T = 0.70


def _pn(names_scores):
    return [PlantNetCandidate(scientific_name=n, common_names=[], score=s, family=None,
                              genus=None, gbif_id=None, rank=i)
            for i, (n, s) in enumerate(names_scores, start=1)]


def _old_rule(pn_raw, inat, force_review, use_pn, use_inat, threshold):
    """Verbatim logic of scan.py's _dual_agree before regional demotion."""
    pn_top_name  = pn_raw[0].scientific_name if pn_raw else None
    pn_top_score = pn_raw[0].score if pn_raw else 0.0
    inat_top_name  = inat[0][0] if inat else None
    inat_top_score = inat[0][1] if inat else 0.0
    ranked = [c.scientific_name for c in pn_raw]
    promoted_from = None
    if ranked and inat and inat[0][0] != ranked[0] and inat[0][0] in ranked[:5]:
        promoted_from = ranked[0]
    return (not force_review and promoted_from is None and use_pn and use_inat
            and pn_top_name is not None and inat_top_name is not None
            and pn_top_name == inat_top_name
            and pn_top_score >= threshold and inat_top_score >= threshold)


# Names: E* are European-listed, N* are not (real names so the reference list decides).
EURO = ["Fagus sylvatica", "Quercus robur", "Larix decidua", "Crataegus monogyna"]
NONEU = ["Abies religiosa", "Pyrus korshinskyi", "Tsuga dumosa", "Cordia trichotoma"]


def test_off_identical_to_old_rule_exhaustive():
    rnd = random.Random(19102026)
    pool = EURO + NONEU
    n = 0
    for _ in range(4000):
        k = rnd.randint(0, 7)
        names = rnd.sample(pool, k)
        scores = sorted((round(rnd.random(), 3) for _ in names), reverse=True)
        raw = _pn(list(zip(names, scores)))
        demoted = demote_candidates(_pn(list(zip(names, scores))))
        inat = []
        if rnd.random() < 0.9:
            inat = [(rnd.choice(pool), round(rnd.random(), 3)) for _ in range(rnd.randint(1, 3))]
        for fr, up, ui in itertools.product((False, True), repeat=3):
            for thr in (0.0, 0.5, T, 1.0):
                old = _old_rule(raw, inat, fr, up, ui, thr)
                new = decide_agreement(demoted, inat, demote_for_approve=False,
                                       force_review=fr, use_pn=up, use_inat=ui, threshold=thr)
                assert new.dual_agree == old, (names, scores, inat, fr, up, ui, thr)
                assert not new.agree_after_demotion
                n += 1
    assert n > 100000


def test_on_uses_demoted_top_with_own_scores():
    # Raw #1 is non-European; the European #2 is what iNat names.
    cands = demote_candidates(_pn([("Abies religiosa", 0.9), ("Larix decidua", 0.75)]))
    inat = [("Larix decidua", 0.8)]
    off = decide_agreement(cands, inat, demote_for_approve=False, force_review=False,
                           use_pn=True, use_inat=True, threshold=T)
    on = decide_agreement(cands, inat, demote_for_approve=True, force_review=False,
                          use_pn=True, use_inat=True, threshold=T)
    assert off.dual_agree is False
    assert on.dual_agree is True and on.pn_top_name == "Larix decidua"
    assert on.pn_top_score == 0.75                  # its OWN score, not 0.9
    assert on.agree_after_demotion and on.pn_raw_top_name == "Abies religiosa"


def test_on_own_pn_score_must_reach_threshold():
    cands = demote_candidates(_pn([("Abies religiosa", 0.9), ("Larix decidua", 0.30)]))
    on = decide_agreement(cands, [("Larix decidua", 0.95)], demote_for_approve=True,
                          force_review=False, use_pn=True, use_inat=True, threshold=T)
    assert on.dual_agree is False


def test_on_own_inat_score_must_reach_threshold():
    cands = demote_candidates(_pn([("Abies religiosa", 0.9), ("Larix decidua", 0.80)]))
    on = decide_agreement(cands, [("Larix decidua", 0.50)], demote_for_approve=True,
                          force_review=False, use_pn=True, use_inat=True, threshold=T)
    assert on.dual_agree is False


def test_on_promoted_candidate_never_agrees():
    # Demoted order: Fagus(#1), Larix(#2), Abies(#3, non-EU). iNat says Larix,
    # which is in the decision top 5 but not #1 → promotion, never agreement.
    cands = demote_candidates(_pn([("Abies religiosa", 0.9), ("Fagus sylvatica", 0.8),
                                   ("Larix decidua", 0.78)]))
    on = decide_agreement(cands, [("Larix decidua", 0.9)], demote_for_approve=True,
                          force_review=False, use_pn=True, use_inat=True, threshold=T)
    assert on.promoted_in_decision and on.dual_agree is False


def test_force_review_always_vetoes():
    cands = demote_candidates(_pn([("Fagus sylvatica", 0.95)]))
    for demote in (False, True):
        d = decide_agreement(cands, [("Fagus sylvatica", 0.95)], demote_for_approve=demote,
                             force_review=True, use_pn=True, use_inat=True, threshold=T)
        assert d.dual_agree is False


def test_on_same_top_no_demotion_note():
    cands = demote_candidates(_pn([("Fagus sylvatica", 0.95), ("Abies religiosa", 0.1)]))
    on = decide_agreement(cands, [("Fagus sylvatica", 0.9)], demote_for_approve=True,
                          force_review=False, use_pn=True, use_inat=True, threshold=T)
    assert on.dual_agree and not on.agree_after_demotion


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
