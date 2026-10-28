"""
Tests for the species-rank guard (Melvin, 28 Oct 2026): no genus cards, ever —
every photo is identified to species (a best guess is fine).

  * taxonomy.is_species_rank_name is the ONE definition: bare genus, family,
    'sp.'/'spp.', infrageneric ranks (sect./subg.), aggregates and cf./aff. are
    refused; binomials, hybrids and infraspecific names pass.
  * Backstops: new_species_card and set_observation_species raise
    NonSpeciesNameError before anything changes; ensure_species_row makes no card.
  * Human paths refuse before any write: confirm / correct
    (update_observation_status), retry-confirm, rename (new card, in place, onto
    an existing card), merge (kept card), trust bulk-reassign. Bulk approve and
    the suggestion promote leave the photo for the reviewer.
  * Automated paths: the scan sends a non-species top name to Review (no
    species, no card, never auto-approved); trigger_ai_drafts makes no card.
  * app/main.py turns NonSpeciesNameError into HTTP 400 (code not_species_rank).

No external calls; throw-away SQLite DBs.

Run from project root:  python tests/test_species_rank_guard.py
"""
import asyncio
import json
import os
import pathlib
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main  # noqa: E402,F401  (registers every model on Base.metadata)
from app.api.identity import Identity  # noqa: E402
from app.database import Base  # noqa: E402
from app.models.observation import Observation  # noqa: E402
from app.models.species import Species, new_species_card  # noqa: E402
from app.services.taxonomy import NonSpeciesNameError, is_species_rank_name  # noqa: E402

CURATOR = Identity(user_id=1, is_guest=False, is_anonymous_guest=False, workshop_session_id=None)


def _db():
    path = os.path.join(tempfile.mkdtemp(prefix="rank_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    return eng, async_sessionmaker(eng, expire_on_commit=False)


async def _raises(awaitable):
    try:
        await awaitable
    except NonSpeciesNameError:
        return True
    return False


async def _seed(S):
    async with S() as s:
        sp = new_species_card("Salix caprea")
        s.add(sp)
        await s.flush()
        genus = Species(scientific_name="Crocus", name_key="crocus", edibility_status="toxic",
                        toxicity_severity="toxic")      # a legacy genus card (354), made before the guard
        s.add(genus)
        await s.flush()
        o = Observation(file_path="/tmp/a.jpg", file_hash="a", review_status="needs_review",
                        identification_status="identified", obs_category="plant",
                        species_primary="Salix caprea", species_id=sp.id)
        g = Observation(file_path="/tmp/g.jpg", file_hash="g", review_status="needs_review",
                        identification_status="identified", obs_category="plant",
                        species_primary="Crocus", species_id=genus.id)
        s.add_all([o, g])
        await s.commit()
        return sp.id, genus.id, o.id, g.id


async def _cards(s):
    return sorted(n for (n,) in (await s.execute(select(Species.scientific_name))).all())


def test_predicate():
    yes = ["Salix caprea", "Bryonia dioica", "Picea × lutzii", "× Cupressocyparis leylandii",
           "Geranium x oxonianum", "Daucus carota subsp. sativus", "Larix decidua decidua",
           "Ulmus × hollandica", "Valeriana locusta"]
    no = ["Salix", "Usnea", "Crocus", "Asteraceae", "Napipedinae", "Taraxacum sect. Taraxacum",
          "Rubus subg. Rubus", "Rosa sect. Caninae", "Salix sp.", "Salix spp", "Russula cf. emetica",
          "Amanita aff. muscaria", "Taraxacum officinale agg.", "amanita muscaria", "beech", "", None]
    assert all(is_species_rank_name(n) for n in yes), [n for n in yes if not is_species_rank_name(n)]
    assert not any(is_species_rank_name(n) for n in no), [n for n in no if is_species_rank_name(n)]


def test_new_species_card_refuses():
    for n in ("Salix", "Taraxacum sect. Taraxacum", "Salix sp."):
        try:
            new_species_card(n)
        except NonSpeciesNameError:
            continue
        raise AssertionError(f"new_species_card accepted {n!r}")
    assert new_species_card("Salix caprea").scientific_name == "Salix caprea"


def test_set_observation_species_and_ensure_row_refuse():
    async def run():
        eng, S = _db()
        sid, gid, oid, goid = await _seed(S)
        from app.services.species_link import ensure_species_row, set_observation_species
        async with S() as s:
            o = await s.get(Observation, oid)
            assert await _raises(set_observation_species(s, o, "Salix"))
            assert (o.species_primary, o.species_id) == ("Salix caprea", sid)
            await set_observation_species(s, o, None)          # clearing is always allowed
            assert o.species_primary is None
        async with S() as s:
            o = Observation(file_path="/tmp/n.jpg", file_hash="n", review_status="approved",
                            species_primary="Usnea")           # a pre-guard row
            s.add(o)
            await s.flush()
            assert await _raises(ensure_species_row(s, o))
            await s.rollback()
        async with S() as s:
            assert await _cards(s) == ["Crocus", "Salix caprea"]
        await eng.dispose()
    asyncio.run(run())


def test_confirm_and_correct_refuse_before_any_write():
    async def run():
        eng, S = _db()
        sid, gid, oid, goid = await _seed(S)
        from app.services.observation_service import update_observation_status
        async with S() as s:
            o = await s.get(Observation, oid)
            assert await _raises(update_observation_status(s, o, "manually_verified", species_name="Salix",
                                                           update_species=True))
            g = await s.get(Observation, goid)
            assert await _raises(update_observation_status(s, g, "approved"))   # existing genus name
            assert not s.new, s.new                                              # no edit row queued
            await s.commit()
        async with S() as s:
            o, g = await s.get(Observation, oid), await s.get(Observation, goid)
            assert (o.species_primary, o.review_status) == ("Salix caprea", "needs_review")
            assert (g.species_primary, g.review_status) == ("Crocus", "needs_review")
            assert (await s.scalar(select(func.count()).select_from(
                __import__("app.models.observation", fromlist=["ObservationEdit"]).ObservationEdit))) == 0
            # a species-rank confirm still works
            await update_observation_status(s, o, "manually_verified", species_name="Salix caprea",
                                            update_species=True)
            await s.commit()
            assert o.review_status == "manually_verified"
        await eng.dispose()
    asyncio.run(run())


def test_promote_suggestion_refuses_genus():
    async def run():
        eng, S = _db()
        await _seed(S)
        from app.services.species_link import promotable_suggestion
        async with S() as s:
            o = Observation(file_path="/tmp/p.jpg", file_hash="p", review_status="needs_review",
                            species_suggested="Salix",
                            species_candidates_json=json.dumps([{"scientific_name": "Salix", "score": 0.9}]))
            s.add(o)
            await s.flush()
            assert await promotable_suggestion(s, o) is None
            o.species_suggested = "Salix caprea"
            assert await promotable_suggestion(s, o) == "Salix caprea"     # a card in use
        await eng.dispose()
    asyncio.run(run())


def test_rename_merge_retry_and_reassign_refuse():
    async def run():
        eng, S = _db()
        sid, gid, oid, goid = await _seed(S)
        from app.api import culinary, reidentify, trust
        from fastapi import BackgroundTasks
        async with S() as s:
            # in place / new card
            assert await _raises(culinary.rename_species_by_name(
                "Salix caprea", culinary.RenameRequest(new_name="Salix"), db=s, identity=CURATOR))
            # onto an existing (legacy) genus card — the auto-merge path
            assert await _raises(culinary.rename_species_by_name(
                "Salix caprea", culinary.RenameRequest(new_name="Crocus"), db=s, identity=CURATOR))
            # merge keeping the genus card
            assert await _raises(culinary.merge_species(
                culinary.MergeRequest(keep="Crocus", discard="Salix caprea"), db=s, identity=CURATOR))
            assert await _raises(reidentify.retry_confirm(
                oid, BackgroundTasks(), reidentify.RetryConfirmRequest(scientific_name="Salix sp."), db=s))
            assert await _raises(trust.bulk_reassign(
                trust.BulkReassignPayload(source_species="Salix caprea", target_species="Crocus"), db=s))
        async with S() as s:
            assert await _cards(s) == ["Crocus", "Salix caprea"]
            o = await s.get(Observation, oid)
            assert (o.species_primary, o.species_id, o.review_status) == ("Salix caprea", sid, "needs_review")
        await eng.dispose()
    asyncio.run(run())


def test_trigger_drafts_makes_no_genus_card():
    async def run():
        eng, S = _db()
        await _seed(S)
        import app.database as database
        real = database.AsyncSessionLocal
        database.AsyncSessionLocal = S
        try:
            from app.services.enrichment import trigger_ai_drafts_for_species
            await trigger_ai_drafts_for_species("Usnea")
        finally:
            database.AsyncSessionLocal = real
        async with S() as s:
            assert await _cards(s) == ["Crocus", "Salix caprea"]
        await eng.dispose()
    asyncio.run(run())


def test_http_400_handler():
    from app.main import _non_species_name_handler
    resp = asyncio.run(_non_species_name_handler(None, NonSpeciesNameError("Salix")))
    assert resp.status_code == 400
    body = json.loads(resp.body)
    assert body["code"] == "not_species_rank" and "Salix" in body["detail"]


def test_scan_and_bulk_route_non_species_to_review():
    """Source order: the scan's not-species branch returns before the top name is
    set, before auto-approve and before the card upsert; bulk approve skips a
    non-species name before any write."""
    scan = pathlib.Path(ROOT, "app/api/scan.py").read_text(encoding="utf-8")
    i_branch = scan.index("if not is_species_rank_name(top[\"scientific_name\"]):")
    branch = scan[i_branch:scan.index("return", i_branch)]
    for must in ('review_status         = "needs_review"', '"genus_reid"', "set_observation_species(session, obs, None)"):
        assert must in branch, must
    assert i_branch < scan.index('await set_observation_species(session, obs, top["scientific_name"])')
    assert i_branch < scan.index("if _dual_agree:\n                # Both APIs agree")
    assert i_branch < scan.index("await _upsert_species_card(obs_id, top, candidates)")
    bulk = pathlib.Path(ROOT, "app/api/bulk_actions.py").read_text(encoding="utf-8")
    i_skip = bulk.index("if not is_species_rank_name(obs.species_primary):")
    assert i_skip < bulk.index('_log_edit(session, obs, "review_status", prev_status, status)')


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
