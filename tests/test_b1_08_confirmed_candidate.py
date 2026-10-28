"""
Tests for audit B1-08 (fix batch 14, 21 Oct 2026): after a human species change
the confirmed species goes to the front of species_candidates_json with ITS OWN
score, and top_score follows it — so the review card %, its "Also:" line, the
map pin's confidence and top_score describe the confirmed species, not another
candidate. Also: a GBIF name-match-only pick from Second Opinion never gets a
score (the client's number is never stored).

Recorded input: tests/fixtures/b1_08_obs24353.json — obs 24353's stored
candidates (Lysimachia nemorum confirmed; card showed "31.9%" = PlantNet's
Micromeria douglasii; Second Opinion showed 46% = iNat's gate for L. nemorum).

No external calls; endpoint tests run on a throw-away SQLite DB.

Run from project root:  python -m pytest tests/test_b1_08_confirmed_candidate.py -v
Or standalone:          python tests/test_b1_08_confirmed_candidate.py
"""

import asyncio
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import BackgroundTasks  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main  # noqa: E402,F401  (registers every model on Base.metadata)
import app.services.observation_service as obs_service  # noqa: E402
from app.database import Base  # noqa: E402
from app.models.observation import Observation  # noqa: E402
from app.services.species_link import candidate_own_score, confirmed_candidate_first  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "b1_08_obs24353.json")
obs_service._copy_to_confirmed = lambda obs: None     # never copy files from tests


def _rec():
    return json.load(open(FIXTURE, encoding="utf-8"))["24353"]


def _original_24353():
    """24353's candidates as identify left them (19 Oct): Micromeria first and
    L. nummularia second — both were stripped later by the two corrections."""
    head = [
        {"scientific_name": "Micromeria douglasii", "score": 0.3186, "source": "plantnet",
         "common_names": ["Yerba buena"]},
        {"scientific_name": "Lysimachia nummularia", "score": 0.0651, "source": "plantnet",
         "inat_vision_score": 0.0334, "inat_combined_score": 0.0569, "common_names": ["Creeping Jenny"]},
    ]
    return head + _rec()["species_candidates"]


def _names(obs):
    return [c["scientific_name"] for c in json.loads(obs.species_candidates_json)]


# ── pure helper ───────────────────────────────────────────────────────────────

def test_own_score_is_the_best_stored_image_score():
    nemorum = next(c for c in _rec()["species_candidates"] if c["scientific_name"] == "Lysimachia nemorum")
    assert candidate_own_score(nemorum) == 0.4613           # iNat gate min(0.4613, 0.8512) > PN 0.0245
    assert candidate_own_score({"score": 0.3, "inat_vision_score": 0.9}) == 0.9
    assert candidate_own_score({"score": 0.3, "inat_vision_score": 0.9, "inat_combined_score": 0.1}) == 0.3
    assert candidate_own_score({"score": None}) is None
    assert candidate_own_score({}) is None


def test_obs_24353_lysimachia_nemorum_goes_first_with_its_own_score():
    rec = _rec()
    obs = Observation(species_primary="Lysimachia nemorum",
                      species_candidates_json=json.dumps(rec["species_candidates"]), top_score=0.3186)
    assert confirmed_candidate_first(obs) is True
    cands = json.loads(obs.species_candidates_json)
    top = cands[0]
    assert top["scientific_name"] == "Lysimachia nemorum"
    assert top["score"] == 0.4613 and obs.top_score == 0.4613    # the 46% Second Opinion showed
    assert top["listed_score"] == 0.0245 and top["score_basis"] == "inaturalist"
    assert top["inat_vision_score"] == 0.4613 and top["inat_combined_score"] == 0.8512
    # "Also:" = the rest in their stored order; nothing lost, nothing duplicated
    before = [c["scientific_name"] for c in rec["species_candidates"]]
    assert _names(obs)[1:] == [n for n in before if n != "Lysimachia nemorum"]
    assert sorted(_names(obs)) == sorted(before)


def test_listed_score_kept_when_it_is_already_the_best():
    obs = Observation(species_primary="Veronica hederifolia",
                      species_candidates_json=json.dumps(_rec()["species_candidates"]))
    confirmed_candidate_first(obs)
    top = json.loads(obs.species_candidates_json)[0]
    assert top["scientific_name"] == "Veronica hederifolia" and top["score"] == 0.0292
    assert "listed_score" not in top and "score_basis" not in top and obs.top_score == 0.0292


def test_name_no_api_listed_gets_a_scoreless_curator_entry():
    obs = Observation(species_primary="Gentiana vernayi",
                      species_candidates_json=json.dumps(_rec()["species_candidates"]), top_score=0.0367)
    confirmed_candidate_first(obs, ["Himalayan gentian"])
    top = json.loads(obs.species_candidates_json)[0]
    assert top == {"scientific_name": "Gentiana vernayi", "common_names": ["Himalayan gentian"],
                   "score": None, "source": "curator"}
    assert obs.top_score is None                            # no invented score
    assert len(_names(obs)) == len(_rec()["species_candidates"]) + 1


def test_empty_or_null_cache_and_name_key_matching():
    for raw in (None, "", "[]", "null"):
        obs = Observation(species_primary="Picea abies", species_candidates_json=raw, top_score=0.5)
        confirmed_candidate_first(obs)
        assert _names(obs) == ["Picea abies"] and obs.top_score is None
    # name_key: case / spacing / hybrid marker
    obs = Observation(species_primary="Geranium × oxonianum", species_candidates_json=json.dumps(
        [{"scientific_name": "Rosa canina", "score": 0.6}, {"scientific_name": "geranium  oxonianum", "score": 0.2}]))
    confirmed_candidate_first(obs)
    assert _names(obs) == ["geranium  oxonianum", "Rosa canina"] and obs.top_score == 0.2


def test_no_species_is_a_no_op():
    raw = json.dumps(_rec()["species_candidates"])
    obs = Observation(species_primary=None, species_candidates_json=raw, top_score=0.1)
    assert confirmed_candidate_first(obs) is False
    assert obs.species_candidates_json == raw and obs.top_score == 0.1


# ── endpoints on a throw-away DB ──────────────────────────────────────────────

def _run(coro):
    return asyncio.run(coro)


async def _db(rows):
    path = os.path.join(tempfile.mkdtemp(prefix="b108test_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    S = async_sessionmaker(eng, expire_on_commit=False)
    async with S() as s:
        for kw in rows:
            s.add(Observation(**kw))
        await s.commit()
    return eng, S


def _obs_row(oid, **kw):
    base = dict(id=oid, file_path=f"/nonexistent/b108_{oid}.jpg", file_hash=f"h{oid}",
                identification_status="identified", review_status="needs_review", obs_category="plant",
                upload_source="syncthing", latitude=47.7, longitude=7.7)
    base.update(kw)
    return base


def test_confirm_species_timeline_of_obs_24353():
    """10:58 manual entry L. nummularia, 14:01 Second Opinion L. nemorum (client
    sent 0.4613; here it sends 0.99 to prove the client's number is not stored)."""
    from app.api.reidentify import ConfirmSpeciesRequest, confirm_species

    async def run():
        eng, S = await _db([_obs_row(24353, species_primary="Micromeria douglasii", top_score=0.3186,
                                     dual_source_agreement=0,
                                     species_candidates_json=json.dumps(_original_24353()))])
        async with S() as s:
            await confirm_species(24353, BackgroundTasks(), ConfirmSpeciesRequest(
                scientific_name="Lysimachia nummularia", source="manual_entry"), db=s)
        async with S() as s:
            o = await s.get(Observation, 24353)
            first = (_names(o), o.top_score, o.review_status)
        async with S() as s:
            await confirm_species(24353, BackgroundTasks(), ConfirmSpeciesRequest(
                scientific_name="Lysimachia nemorum", common_name="Yellow Pimpernel",
                confidence=0.99, source="second_opinion"), db=s)
        async with S() as s:
            o = await s.get(Observation, 24353)
            second = (_names(o), o.top_score, json.loads(o.species_candidates_json)[0], o.dual_source_agreement)
        await eng.dispose()
        return first, second

    (n1, ts1, rs1), (n2, ts2, top2, dsa2) = _run(run())
    assert n1[0] == "Lysimachia nummularia" and "Micromeria douglasii" not in n1
    assert ts1 == 0.0651 and rs1 == "manually_verified"      # PN 0.0651 > iNat gate 0.0334
    assert n2[0] == "Lysimachia nemorum" and "Lysimachia nummularia" not in n2
    assert ts2 == 0.4613 and top2["score"] == 0.4613           # stored evidence, not the client's 0.99
    assert n2[1:3] == ["Veronica sublobata", "Veronica hederifolia"]   # the card's new "Also:"
    assert dsa2 == 0                                           # agreement is evidence; never touched


def test_gbif_name_match_pick_never_gets_a_score_or_approval():
    """A GBIF-only Second Opinion row sends confidence null (an old client sent
    0.50): the stored score stays None, agreement is untouched, and the row is
    manually_verified (a human decision) — never auto 'approved'."""
    from app.api.reidentify import ConfirmSpeciesRequest, confirm_species

    async def run():
        eng, S = await _db([_obs_row(24149, species_primary="Gentiana verna", top_score=0.5242,
                                     dual_source_agreement=1, species_candidates_json=json.dumps(
                                         [{"scientific_name": "Gentiana verna", "score": 0.5242,
                                           "source": "plantnet"}]))])
        async with S() as s:
            await confirm_species(24149, BackgroundTasks(), ConfirmSpeciesRequest(
                scientific_name="Gentiana vernayi", confidence=0.5, source="second_opinion"), db=s)
        async with S() as s:
            o = await s.get(Observation, 24149)
            out = (json.loads(o.species_candidates_json), o.top_score, o.dual_source_agreement, o.review_status)
        await eng.dispose()
        return out

    cands, ts, dsa, rs = _run(run())
    assert cands[0]["scientific_name"] == "Gentiana vernayi" and cands[0]["score"] is None
    assert cands[0]["source"] == "curator" and ts is None
    assert dsa == 1 and rs == "manually_verified"


def test_map_pin_confidence_follows_the_species():
    from app.api.identity import Identity
    from app.api.map import map_geojson
    nemorum_first = json.dumps([{"scientific_name": "Lysimachia nemorum", "score": 0.4613},
                                {"scientific_name": "Veronica sublobata", "score": 0.0367}])
    stale = json.dumps([{"scientific_name": "Veronica sublobata", "score": 0.0367},
                        {"scientific_name": "Lysimachia nemorum", "score": 0.0245}])

    async def run():
        eng, S = await _db([
            _obs_row(1, review_status="approved", species_primary="Lysimachia nemorum",
                     species_candidates_json=nemorum_first),
            _obs_row(2, review_status="approved", species_primary="Lysimachia nemorum",
                     species_candidates_json=stale),        # an older unfixed / renamed row
            _obs_row(3, review_status="approved", species_primary="Gentiana vernayi",
                     species_candidates_json=json.dumps([{"scientific_name": "Gentiana vernayi",
                                                          "score": None, "source": "curator"}])),
        ])
        async with S() as s:
            gj = await map_geojson(db=s, min_lng=None, min_lat=None, max_lng=None, max_lat=None,
                                   identity=Identity(user_id=1, is_guest=False, is_anonymous_guest=False,
                                                     workshop_session_id=None))
        await eng.dispose()
        return {f["properties"]["id"]: f["properties"]["confidence"] for f in gj["features"]}

    conf = _run(run())
    assert conf == {1: 0.4613, 2: None, 3: None}, conf      # never another species' score


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
