"""
Tests for audit E-03 (fix batch 14, 21 Oct 2026): Second Opinion returned 500
when GBIF named a species the image APIs didn't — the GBIF branch built its own
candidate dict without non_european / pn_rank / pn_raw_rank and the ranking
sort raised KeyError. Every source now builds the same shape (_sop_entry) and
the merge is a pure function (merge_second_opinion_candidates).

No external API calls: tests/fixtures/second_opinion_recorded.json holds the
recorded inputs for the two observations that failed in the log — obs 24149
(Gentiana verna; GBIF adds 'Gentiana vernayi') and obs 24348 (Euphorbia
corollata, logs/server_20261016_064852.log) — their stored scan candidates
(PlantNet / iNaturalist) plus a recorded GBIF species search.

Batch 14 part 2 (21 Oct 2026, Melvin's decision): GBIF-only names are a text
match on the current name, not image evidence — they get no score
(confidence None, name_match_only True) and sort after every photo-backed
candidate. On obs 24149 Gentiana verna now ranks above Gentiana vernayi.

Run from project root:  python -m pytest tests/test_second_opinion_merge.py -v
Or standalone:          python tests/test_second_opinion_merge.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.api.reidentify import _sop_entry, merge_second_opinion_candidates  # noqa: E402
from app.integrations.inaturalist import INatCandidate  # noqa: E402
from app.integrations.plantnet import PlantNetCandidate  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "second_opinion_recorded.json")
RESULT_KEYS = {"rank", "scientific_name", "common_name", "common_names", "confidence", "sources",
               "reference_images", "non_european", "pn_rank", "pn_raw_rank", "name_match_only"}


def _recorded(obs_id):
    rec = json.load(open(FIXTURE, encoding="utf-8"))[str(obs_id)]
    pn, inat = [], []
    for i, c in enumerate(rec["stored_candidates"]):
        if c.get("source") == "plantnet":
            pn.append(PlantNetCandidate(scientific_name=c["scientific_name"], common_names=c.get("common_names") or [],
                                        score=c["score"], family=c.get("family"), genus=c.get("genus"),
                                        gbif_id=c.get("gbif_id"), rank=c.get("rank") or i + 1))
        elif c.get("source") == "inaturalist":
            names = c.get("common_names") or []
            inat.append(INatCandidate(scientific_name=c["scientific_name"], common_name=names[0] if names else None,
                                      score=c["score"], taxon_id=None, rank="species", common_names=names))
    return pn, inat, rec["gbif_results"]


def _check_shape(results):
    for r in results:
        assert set(r) == RESULT_KEYS, set(r) ^ RESULT_KEYS
        assert isinstance(r["sources"], list) and isinstance(r["non_european"], bool)
        # a score exactly when a photo-backed source named it
        photo = "plantnet" in r["sources"] or "inaturalist" in r["sources"]
        assert r["name_match_only"] is (not photo)
        assert (r["confidence"] is None) is (not photo)
    assert [r["rank"] for r in results] == list(range(1, len(results) + 1))
    # every name-match-only row comes after every photo-backed row
    flags = [r["name_match_only"] for r in results]
    assert flags == sorted(flags), flags


def test_obs_24149_gbif_only_name_no_longer_crashes():
    pn, inat, gbif = _recorded(24149)
    results = merge_second_opinion_candidates(pn, inat, gbif)
    _check_shape(results)
    image_names = {c.scientific_name.lower() for c in pn + inat}
    gbif_only = [r for r in results if r["sources"] == ["gbif"]]
    assert gbif_only, "the recorded case must include a GBIF-only name"
    assert all(r["scientific_name"].lower() not in image_names for r in gbif_only)
    assert any(r["scientific_name"] == "Gentiana vernayi" for r in gbif_only)
    for r in gbif_only:
        assert r["confidence"] is None and r["name_match_only"] is True
        assert r["non_european"] is False and r["pn_rank"] is None


def test_obs_24149_verna_ranks_above_name_match_vernayi():
    """Melvin's decision: the photo's own consensus outranks a name-match-only GBIF hit."""
    pn, inat, gbif = _recorded(24149)
    results = merge_second_opinion_candidates(pn, inat, gbif)
    names = [r["scientific_name"] for r in results]
    assert names.index("Gentiana verna") < names.index("Gentiana vernayi")
    assert names[0] == "Gentiana verna" and names[-1] == "Gentiana vernayi"
    verna = results[0]
    assert "plantnet" in verna["sources"] and verna["confidence"] is not None and verna["confidence"] > 0


def test_obs_24348_from_the_log_no_longer_crashes():
    pn, inat, gbif = _recorded(24348)
    _check_shape(merge_second_opinion_candidates(pn, inat, gbif))


def test_old_gbif_dict_shape_is_what_crashed():
    """The pre-fix GBIF entry (no non_european) cannot be sorted by the ranking key."""
    old_gbif_entry = {"scientific_name": "Gentiana vernayi", "common_name": None, "common_names": [],
                      "scores": {"gbif": 0.5}, "sources": {"gbif"}, "reference_images": [], "confidence": 0.5}
    try:
        sorted([old_gbif_entry], key=lambda x: (x["non_european"] and "inaturalist" not in x["sources"],
                                                -x["confidence"]))
    except KeyError as e:
        assert e.args[0] == "non_european"
        return
    raise AssertionError("expected the KeyError the fix removes")


def test_every_source_builds_the_same_shape():
    base = set(_sop_entry("X y", None, []))
    for pn, inat, gbif in (
        ([PlantNetCandidate("A a", [], 0.9, None, None, None, 1)], [], []),
        ([], [INatCandidate("B b", None, 0.8, None, "species")], []),
        ([], [], [{"scientific_name": "C c", "common_name": "Cee"}]),
    ):
        results = merge_second_opinion_candidates(pn, inat, gbif)
        _check_shape(results)
        assert len(results) == 1
    assert {"non_european", "pn_rank", "pn_raw_rank", "scores", "sources", "reference_images"} <= base


def test_gbif_never_replaces_an_image_score_or_names():
    pn = [PlantNetCandidate("Gentiana verna", ["Spring gentian"], 0.52, None, None, None, 1)]
    r = merge_second_opinion_candidates(pn, [], [{"scientific_name": "Gentiana verna", "common_name": "Other"}])
    assert len(r) == 1 and r[0]["sources"] == ["gbif", "plantnet"]
    assert r[0]["confidence"] == 0.52 and r[0]["common_name"] == "Spring gentian"
    assert r[0]["name_match_only"] is False


def test_non_european_demotion_still_applies():
    pn = [PlantNetCandidate("Exotica one", [], 0.9, None, None, None, 1, raw_rank=1, non_european=True),
          PlantNetCandidate("Europa two", [], 0.4, None, None, None, 2, raw_rank=2)]
    r = merge_second_opinion_candidates(pn, [], [{"scientific_name": "Gbif three", "common_name": None}])
    # photo-backed first (demoted non-European last among them), name match after all
    assert [x["scientific_name"] for x in r] == ["Europa two", "Exotica one", "Gbif three"]
    assert r[1]["non_european"] is True and r[1]["pn_raw_rank"] == 1
    assert r[2]["name_match_only"] is True and r[2]["confidence"] is None


def test_name_matches_keep_gbif_order_after_a_weak_image_candidate():
    """Even a 0.1% image candidate sorts above any name match; GBIF's own order is kept."""
    inat = [INatCandidate("Weak image", None, 0.001, None, "species")]
    gbif = [{"scientific_name": "Name one", "common_name": None},
            {"scientific_name": "Name two", "common_name": None}]
    r = merge_second_opinion_candidates([], inat, gbif)
    assert [x["scientific_name"] for x in r] == ["Weak image", "Name one", "Name two"]


def test_gbif_only_name_reaches_no_agreement_or_auto_approve_input():
    """By code: the only auto-approve path is scan._identify_scanned, through
    agreement.decide_agreement(PlantNet candidates, iNat hits, ...). Its inputs
    are those two lists only — no GBIF parameter exists — and Second Opinion is
    read-only. A GBIF pick is applied by confirm-species, a human decision; its
    score is covered in tests/test_b1_08_confirmed_candidate.py (stays None)."""
    import inspect
    from app.services import agreement
    params = list(inspect.signature(agreement.decide_agreement).parameters)
    # hazard (22 Oct 2026): a bool that can only refuse auto-approve, never a name input.
    assert params == ["pn_candidates", "inat_hits", "demote_for_approve", "force_review",
                      "use_pn", "use_inat", "threshold", "hazard"], params
    src = inspect.getsource(agreement)
    assert "gbif" not in src.lower()
    # scan writes dual_source_agreement from decide_agreement only, and builds
    # its candidate list from PlantNet + iNat (no GBIF name search in scan).
    from app.api import scan
    scan_src = inspect.getsource(scan._identify_scanned)
    assert "_gbif_species_search" not in scan_src and "second_opinion" not in scan_src


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
