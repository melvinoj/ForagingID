"""
Tests for orphan species cards (Melvin, 21 Oct 2026).

  * One shared rule (app/services/species_link.py): a card is orphan-marked only
    when it has no LIVE observation (a non-rejected row pointing at it by
    species_id / species_primary / species_suggested — candidate lists don't
    count) AND it is not a REFERENCE card (human history, recipe, verified by a
    human, look-alike target, synonym canonical, encounter / list / foray entry).
  * Every reject path runs the GC; un-reject clears the marker.
  * The verdict-draft queue, the verdict sweep and the edibility lists show only
    live-or-reference cards.
  * No card is created when iNaturalist files the top name outside
    Plantae/Fungi; kingdom unknown keeps today's behaviour.

No external calls; throw-away SQLite DBs.

Run from project root:  python -m pytest tests/test_orphan_cards.py -v
Or standalone:          python tests/test_orphan_cards.py
"""

import asyncio
import contextlib
import io
import os
import sqlite3
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from fastapi import BackgroundTasks  # noqa: E402,F401
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main  # noqa: E402,F401  (registers every model on Base.metadata)
import app.api.audit as audit  # noqa: E402
import app.api.bulk_actions as bulk_actions  # noqa: E402
import app.api.edibility as edib  # noqa: E402
import app.api.scan as scan  # noqa: E402
import app.services.enrichment as enrichment  # noqa: E402
import app.services.file_cleanup as file_cleanup  # noqa: E402
import app.services.observation_service as obs_service  # noqa: E402
from app.api.identity import Identity  # noqa: E402
from app.database import Base  # noqa: E402
from app.models.culinary import CulinaryInfo  # noqa: E402
from app.models.observation import Observation  # noqa: E402
from app.models.processing import ProcessingLog  # noqa: E402
from app.models.species import (Species, SpeciesAIDraft, SpeciesEdibilityHistory,  # noqa: E402
                                SpeciesLookalike, SpeciesRecipe)
from app.services.species_link import (species_has_live_observation,  # noqa: E402
                                       species_is_reference)
import verdict_sweep_drafts as sweep  # noqa: E402

CURATOR = Identity(user_id=None, is_guest=False, is_anonymous_guest=False, workshop_session_id=None)

# Never copy, delete files or call enrichment from tests.
obs_service._copy_to_confirmed = lambda obs: None
bulk_actions._copy_to_confirmed = lambda obs: None
file_cleanup.delete_observation_file = lambda obs: None
audit.delete_observation_file = lambda obs: None


async def _noop(*a, **k):
    return None
enrichment.trigger_ai_drafts_for_species = _noop
bulk_actions.bp_progress = _noop
bulk_actions.bp_finish = _noop


def _run(coro):
    return asyncio.run(coro)


# id, name, kingdom
JUNK = (250, "Betacoronavirus pandemicum", None)
OENANTHE = (653, "Oenanthe crocata", "Plantae")      # look-alike target + human history
CUCUMIS = (4, "Cucumis sativus", "Plantae")           # recipe
ALLIUM = (583, "Allium cepa", "Plantae")              # recipe + verified by a human
HOGWEED = (10, "Heracleum sphondylium", "Plantae")    # look-alike row owner (not a target)
LIVE = (700, "Urtica dioica", "Plantae")              # plain card with a needs_review photo


def _obs(oid, name, sid, status="needs_review", **kw):
    base = dict(id=oid, file_path=f"/nonexistent/orph_{oid}.jpg", file_hash=f"h{oid}",
                species_primary=name, species_id=sid, review_status=status,
                identification_status="identified", obs_category="plant",
                upload_source="file_upload", latitude=47.7, longitude=7.7)
    base.update(kw)
    return base


async def _db(extra_obs=()):
    path = os.path.join(tempfile.mkdtemp(prefix="orphtest_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    S = async_sessionmaker(eng, expire_on_commit=False)
    async with S() as s:
        for sid, name, kingdom in (JUNK, OENANTHE, CUCUMIS, ALLIUM, HOGWEED, LIVE):
            s.add(Species(id=sid, scientific_name=name, name_key=name.lower(), kingdom=kingdom,
                          edibility_status="unknown", toxicity_severity="unknown",
                          edibility_verified_by="human" if sid == ALLIUM[0] else None))
        await s.flush()
        s.add(SpeciesLookalike(species_id=HOGWEED[0], lookalike_species_id=OENANTHE[0],
                               lookalike_name=OENANTHE[1], toxicity_level="deadly"))
        s.add(SpeciesEdibilityHistory(species_id=OENANTHE[0], field="edibility_status",
                                      old_value=None, new_value="toxic", changed_by="human"))
        s.add(SpeciesRecipe(species_id=CUCUMIS[0], title="Pickles", body="Brine."))
        s.add(SpeciesRecipe(species_id=ALLIUM[0], title="Soup", body="Onions."))
        # Only photo of each (the reject subject), plus a live photo of Urtica.
        s.add(Observation(**_obs(1, JUNK[1], JUNK[0])))
        s.add(Observation(**_obs(2, OENANTHE[1], OENANTHE[0])))
        s.add(Observation(**_obs(3, CUCUMIS[1], CUCUMIS[0])))
        s.add(Observation(**_obs(4, ALLIUM[1], ALLIUM[0])))
        s.add(Observation(**_obs(5, LIVE[1], LIVE[0])))
        for kw in extra_obs:
            s.add(Observation(**kw))
        await s.commit()
    return path, eng, S


async def _set_status(S, oid, status):
    async with S() as s:
        obs = await s.get(Observation, oid)
        await obs_service.update_observation_status(s, obs, status)
        await s.commit()


async def _orphaned(S, sid):
    async with S() as s:
        return (await s.get(Species, sid)).orphaned_at is not None


# ── the predicates ────────────────────────────────────────────────────────────

def test_predicates_live_and_reference():
    async def run():
        path, eng, S = await _db(extra_obs=[
            # A candidate-list mention on a live row does not count as live.
            _obs(9, LIVE[1], LIVE[0], species_candidates_json=
                 '[{"scientific_name": "Heracleum sphondylium", "score": 0.4}]'),
        ])
        async with S() as s:
            live = {sid: await species_has_live_observation(s, sid) for sid, _, _ in
                    (JUNK, OENANTHE, CUCUMIS, ALLIUM, HOGWEED, LIVE)}
            ref = {sid: await species_is_reference(s, sid) for sid, _, _ in
                   (JUNK, OENANTHE, CUCUMIS, ALLIUM, HOGWEED, LIVE)}
        await eng.dispose()
        return live, ref

    live, ref = _run(run())
    assert live == {250: True, 653: True, 4: True, 583: True, 10: False, 700: True}
    assert ref == {250: False, 653: True, 4: True, 583: True, 10: False, 700: False}


# ── reject / un-reject ────────────────────────────────────────────────────────

def test_rejecting_only_photo_of_junk_species_marks_it_orphan():
    async def run():
        path, eng, S = await _db()
        await _set_status(S, 1, "rejected")
        out = await _orphaned(S, JUNK[0])
        await eng.dispose()
        return out

    assert _run(run()) is True


def test_rejecting_only_photo_of_reference_species_does_not_mark_it():
    async def run():
        path, eng, S = await _db()
        for oid in (2, 3, 4):
            await _set_status(S, oid, "rejected")
        out = {sid: await _orphaned(S, sid) for sid in (OENANTHE[0], CUCUMIS[0], ALLIUM[0])}
        await eng.dispose()
        return out

    assert _run(run()) == {653: False, 4: False, 583: False}


def test_rejected_rows_are_not_backing_but_live_rows_are():
    async def run():
        path, eng, S = await _db(extra_obs=[
            _obs(20, JUNK[1], JUNK[0], status="rejected"),              # rejected: not backing
            _obs(21, LIVE[1], LIVE[0], status="needs_review"),          # a second live photo
        ])
        await _set_status(S, 1, "rejected")
        await _set_status(S, 5, "rejected")
        out = (await _orphaned(S, JUNK[0]), await _orphaned(S, LIVE[0]))
        await eng.dispose()
        return out

    assert _run(run()) == (True, False)


def test_species_suggested_keeps_a_card_live():
    async def run():
        path, eng, S = await _db(extra_obs=[
            _obs(22, None, None, identification_status="below_threshold",
                 species_suggested=JUNK[1]),
        ])
        await _set_status(S, 1, "rejected")
        out = await _orphaned(S, JUNK[0])
        await eng.dispose()
        return out

    assert _run(run()) is False


def test_unreject_clears_the_marker():
    async def run():
        path, eng, S = await _db()
        await _set_status(S, 1, "rejected")
        marked = await _orphaned(S, JUNK[0])
        await _set_status(S, 1, "needs_review")
        out = (marked, await _orphaned(S, JUNK[0]))
        await eng.dispose()
        return out

    assert _run(run()) == (True, False)


def test_bulk_reject_and_audit_reject_run_the_gc():
    async def run():
        path, eng, S = await _db(extra_obs=[_obs(30, "Saccharomyces cerevisiae", 469)])
        async with S() as s:
            s.add(Species(id=469, scientific_name="Saccharomyces cerevisiae",
                          name_key="saccharomyces cerevisiae", kingdom="Fungi"))
            await s.commit()
        bulk_actions.AsyncSessionLocal = S
        await bulk_actions._bulk_review_task([1, 3], "rejected", None)
        async with S() as s:
            await audit.audit_reject(audit.RejectPayload(obs_id=30, reason="junk"), db=s)
        out = (await _orphaned(S, JUNK[0]), await _orphaned(S, CUCUMIS[0]), await _orphaned(S, 469))
        await eng.dispose()
        return out

    assert _run(run()) == (True, False, True)


# ── queues ────────────────────────────────────────────────────────────────────

def test_queues_hide_orphan_marked_cards():
    async def run():
        path, eng, S = await _db()
        async with S() as s:
            for did, sid in ((900, JUNK[0]), (901, CUCUMIS[0]), (902, LIVE[0])):
                s.add(SpeciesAIDraft(id=did, species_id=sid, field_name="edibility_status",
                                     status="pending", model="verdict_sweep", draft_text="unknown",
                                     generation_context_json="{}"))
            await s.commit()
        await _set_status(S, 1, "rejected")      # junk → orphan-marked
        await _set_status(S, 3, "rejected")      # Cucumis → reference, stays listed
        async with S() as s:
            q = await edib.list_verdict_drafts(db=s, identity=CURATOR)
        async with S() as s:
            for sid in (JUNK[0], LIVE[0]):
                (await s.get(Species, sid)).edibility_status = "edible"
            await s.commit()
        async with S() as s:
            ed = await edib.list_edibility_species(db=s)
        await eng.dispose()
        return {i["species_id"] for i in q["items"]}, {r["id"] for r in ed}

    queued, ed = _run(run())
    assert queued == {CUCUMIS[0], LIVE[0]}          # junk card's draft hidden
    assert JUNK[0] not in ed and LIVE[0] in ed


def test_sweep_skips_cards_with_no_live_observation_and_no_reference():
    async def run():
        path, eng, S = await _db()
        await _set_status(S, 1, "rejected")
        await _set_status(S, 3, "rejected")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            sweep.main(["--db", path])          # dry run end to end
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        items, skipped = sweep.plan(conn)
        conn.close()
        await eng.dispose()
        return {i["species_id"] for i in items}, skipped

    items, skipped = _run(run())
    assert JUNK[0] not in items and HOGWEED[0] not in items
    assert {CUCUMIS[0], OENANTHE[0], ALLIUM[0], LIVE[0]} <= items
    assert skipped["no live observation and not a reference card (orphan-marked)"] == 1
    assert skipped["no live observation and not a reference card"] == 1      # Heracleum: never marked


# ── kingdom gate at card creation ─────────────────────────────────────────────

class _Hit:
    def __init__(self, name, score, iconic):
        self.scientific_name, self.score, self.iconic_taxon_name = name, score, iconic
        self.common_name, self.common_names, self.taxon_id, self.rank = None, [], None, "species"
        self.vision_score, self.geo_score = score, score


def _identify_with(hits, *, human_corrected=True):
    """Drive scan._identify_scanned on one needs_review row with iNat only.
    human_corrected rows skip the ≥5 % non-plant early return — the path on
    which a non-plant top still reaches the card upsert today."""
    async def run():
        d = tempfile.mkdtemp(prefix="orphscan_")
        img = os.path.join(d, "x.jpg")
        open(img, "wb").write(b"\xff\xd8\xff")
        path, eng, S = await _db(extra_obs=[
            _obs(40, None, None, file_path=img, human_corrected=human_corrected,
                 identification_status="pending_identification"),
        ])
        import app.integrations.inaturalist as inat
        import app.services.id_ratelimit as rl
        import app.services.enrich_gate as gate
        import app.api.itis as itis
        saved = (scan.AsyncSessionLocal, scan.settings.plantnet_api_key, scan.settings.inaturalist_api_token,
                 inat.score_image, inat.last_inat_status, rl.INAT_DELAY_S,
                 gate.queue_card_enrichment, itis.trigger_itis_for_new_species)

        async def _score(*a, **k):
            return list(hits)
        scan.AsyncSessionLocal = S
        scan.settings.plantnet_api_key, scan.settings.inaturalist_api_token = "", "tok"
        inat.score_image, inat.last_inat_status = _score, (lambda: {"state": "ok"})
        rl.INAT_DELAY_S = 0
        gate.queue_card_enrichment = lambda name: None
        itis.trigger_itis_for_new_species = _noop
        try:
            await scan._identify_scanned(40)
            async with S() as s:
                names = set((await s.execute(select(Species.scientific_name))).scalars().all())
                logs = (await s.execute(select(ProcessingLog.stage, ProcessingLog.message)
                                        .where(ProcessingLog.observation_id == 40))).all()
                o = await s.get(Observation, 40)
                state = (o.review_status, o.species_primary)
        finally:
            (scan.AsyncSessionLocal, scan.settings.plantnet_api_key, scan.settings.inaturalist_api_token,
             inat.score_image, inat.last_inat_status, rl.INAT_DELAY_S,
             gate.queue_card_enrichment, itis.trigger_itis_for_new_species) = saved
            await eng.dispose()
        return names, logs, state
    return _run(run())


def test_non_plant_top_candidate_creates_no_card():
    names, logs, state = _identify_with([_Hit("Arachnocampa otwayensis", 0.8, "Insecta")])
    assert "Arachnocampa otwayensis" not in names
    assert any(st == "species_card_skipped" and "Insecta" in m for st, m in logs)
    assert state[0] == "needs_review"                                  # still goes to review


def test_plant_top_candidate_still_creates_a_card():
    names, logs, _ = _identify_with([_Hit("Lamium album", 0.8, "Plantae")])
    assert "Lamium album" in names
    assert not any(st == "species_card_skipped" for st, _m in logs)


def test_unknown_kingdom_keeps_todays_behaviour():
    names, logs, _ = _identify_with([_Hit("Lamium maculatum", 0.8, None)])
    assert "Lamium maculatum" in names


def test_top_candidate_inat_kingdom_matches_by_name_key():
    hits = [_Hit("Lamium album", 0.8, "Plantae"), _Hit("Apis mellifera", 0.1, "Insecta")]
    assert scan.top_candidate_inat_kingdom("lamium  ALBUM", hits) == "Plantae"
    assert scan.top_candidate_inat_kingdom("Apis mellifera", hits) == "Insecta"
    assert scan.top_candidate_inat_kingdom("Urtica dioica", hits) is None
    assert scan.top_candidate_inat_kingdom(None, hits) is None


if __name__ == "__main__":
    for _name, _fn in list(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print("ok", _name)
