"""
Tests for app/services/regional_demotion.py against the 19 Oct 2026 A/B sample.

Run from project root:  python -m pytest tests/test_regional_demotion.py -v
Or standalone:          python tests/test_regional_demotion.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.integrations.plantnet import PlantNetCandidate
from app.services.regional_demotion import (
    demote_candidates, display_slots, european_keys, is_non_european, raw_order,
)

_FIX = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures",
                                   "regional_demotion_ab.json")))["cases"]


def _cands(case):
    return [PlantNetCandidate(scientific_name=n, common_names=[], score=s, family=None,
                              genus=None, gbif_id=None, rank=i)
            for i, (n, s) in enumerate(_FIX[case]["cands"], start=1)]


def _find(cands, name):
    return next(c for c in cands if c.scientific_name == name)


def test_reference_list_loaded():
    keys = european_keys()
    assert keys is not None and len(keys) > 10000


def test_scores_never_altered_and_nothing_dropped():
    for case in _FIX:
        before = {(c.scientific_name, c.score) for c in _cands(case)}
        after = demote_candidates(_cands(case))
        assert {(c.scientific_name, c.score) for c in after} == before, case


def test_stable_partition_keeps_plantnet_order():
    for case in _FIX:
        out = demote_candidates(_cands(case))
        flags = [c.non_european for c in out]
        assert flags == sorted(flags), case                    # Europeans first
        for grp in (True, False):
            raws = [c.raw_rank for c in out if c.non_european is grp]
            assert raws == sorted(raws), case                   # PlantNet order kept
        assert [c.rank for c in out] == list(range(1, len(out) + 1))
        assert [c.raw_rank for c in raw_order(out)] == list(range(1, len(out) + 1))


def test_crataegus_moves_up():
    for case in ("8316", "8316_nb30"):
        out = demote_candidates(_cands(case))
        c = _find(out, "Crataegus monogyna")
        assert c.raw_rank == 6 and c.rank < c.raw_rank and c.rank <= 5, (case, c.rank)
        assert c.non_european is False


def test_larix_moves_up():
    for case in ("8310", "8310_nb30"):
        out = demote_candidates(_cands(case))
        c = _find(out, "Larix decidua")
        # Moves up but not into the top 5: the five-list union counts planted
        # conifers (Larix kaempferi, L. laricina, Pseudotsuga) as European.
        assert c.raw_rank == 10 and c.rank < c.raw_rank, (case, c.rank)


def test_aconitum_nb30_present_and_moves_up():
    out = demote_candidates(_cands("21705_nb30"))
    c = _find(out, "Aconitum napellus")
    assert c.raw_rank == 23 and c.rank < c.raw_rank and not c.non_european


def test_garden_exotics_kept_and_flagged():
    for case, name in (("21252", "Helianthus silphioides"),
                       ("20563", "Fuchsia magellanica"),
                       ("20570", "Platanus × hispanica")):
        out = demote_candidates(_cands(case))
        c = _find(out, name)                                   # still present
        if name == "Fuchsia magellanica":
            # Listed in k-northern-europe — European, so not demoted
            assert c.non_european is False and c.rank == 1
        elif name == "Platanus × hispanica":
            # Hybrid — never demoted even though absent from every list
            assert c.non_european is False and c.rank == 1
        else:
            assert c.non_european is True and c.raw_rank == 1 and c.rank > 1
            # ...and an N-slot UI list still shows it, because it was raw #1
            assert c in display_slots(out, 5)


def test_rules_hybrid_infraspecific_genus():
    keys = european_keys()
    assert not is_non_european("Platanus × hispanica", keys)
    assert not is_non_european("Mentha x piperita", keys)
    assert not is_non_european("Daucus carota subsp. sativus", keys)   # parent listed
    assert not is_non_european("Larix decidua decidua", keys)          # autonym
    assert not is_non_european("Crocus", keys)                         # genus only
    assert is_non_european("Abies religiosa", keys)
    assert not is_non_european("Fagus sylvatica", keys)


def test_idempotent():
    once = demote_candidates(_cands("8310_nb30"))
    twice = demote_candidates(once)
    assert [(c.scientific_name, c.rank, c.raw_rank) for c in once] == \
           [(c.scientific_name, c.rank, c.raw_rank) for c in twice]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
