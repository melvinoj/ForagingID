"""
Tests for audit C-03 and C-04 (fix batch 14, 21 Oct 2026).

C-03 — confirmed observations naming a species with no species row (map pins
with no card, edibility or enrichment: 21382, 21453, 21454, 21950, 22074).
  * resolve_species_id: exact name, then name_key, then a registered synonym.
  * A confirmed species name always gets a linked species row (bare, severity
    'unknown' → fails closed) on every approve path, instead of relying on a
    background enrichment task that rolled the new row back on failure.

C-04 — obs 21585 got species_primary 'norway spruce': the reviewer's typed text
(saved as species_suggested by Look up) was promoted by an Approve that read
the row before the Look-up pick ('Picea abies') had committed.
  * Approve (single and bulk) promotes a suggestion only when it is a
    recognised scientific name; otherwise 409 / row untouched.
  * A species set by hand clears the pending suggestion.

No external calls; throw-away SQLite DBs.

Run from project root:  python -m pytest tests/test_species_link_c03_c04.py -v
Or standalone:          python tests/test_species_link_c03_c04.py
"""

import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import BackgroundTasks, HTTPException  # noqa: E402
from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main  # noqa: E402,F401  (registers every model on Base.metadata)
import app.api.bulk_actions as bulk_actions  # noqa: E402
import app.services.enrichment as enrichment  # noqa: E402
import app.services.observation_service as obs_service  # noqa: E402
from app.database import Base  # noqa: E402
from app.models.observation import Observation, ObservationEdit  # noqa: E402
from app.models.species import Species, SpeciesSynonym  # noqa: E402
from app.services.species_link import ensure_species_row, promotable_suggestion, resolve_species_id  # noqa: E402

# Never copy files or call enrichment from tests.
obs_service._copy_to_confirmed = lambda obs: None
bulk_actions._copy_to_confirmed = lambda obs: None


async def _no_enrich(name):
    return None
enrichment.trigger_ai_drafts_for_species = _no_enrich


def _run(coro):
    return asyncio.run(coro)


async def _db(species=(), synonyms=(), rows=()):
    path = os.path.join(tempfile.mkdtemp(prefix="c0304test_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    S = async_sessionmaker(eng, expire_on_commit=False)
    async with S() as s:
        for kw in species:
            s.add(Species(**kw))
        await s.flush()
        for kw in synonyms:
            s.add(SpeciesSynonym(**kw))
        for kw in rows:
            s.add(Observation(**kw))
        await s.commit()
    return eng, S


def _obs(oid, **kw):
    base = dict(id=oid, file_path=f"/nonexistent/c03_{oid}.jpg", file_hash=f"h{oid}",
                identification_status="below_threshold", review_status="needs_review",
                obs_category="plant", upload_source="syncthing", latitude=47.7, longitude=7.7)
    base.update(kw)
    return base


ERIGERON = dict(id=342, scientific_name="Erigeron canadensis", name_key="erigeron canadensis",
                toxicity_severity="none")
PICEA = dict(id=366, scientific_name="Picea abies", name_key="picea abies", toxicity_severity="none")
CONYZA_SYN = dict(synonym_name_key="conyza canadensis", synonym_scientific_name="Conyza canadensis",
                  canonical_species_id=342)


# ── C-03 ──────────────────────────────────────────────────────────────────────

def test_resolve_species_id_exact_then_name_key_then_synonym():
    async def run():
        eng, S = await _db(species=[ERIGERON, PICEA], synonyms=[CONYZA_SYN])
        async with S() as s:
            out = [await resolve_species_id(s, n) for n in
                   ("Picea abies", "picea  ABIES", "Conyza canadensis", "Filipendula vulgaris", None)]
        await eng.dispose()
        return out
    assert _run(run()) == [366, 366, 342, None, None]


def _approve(S, oid):
    from app.api.observations import update_review
    async def go():
        async with S() as s:
            return await update_review(oid, BackgroundTasks(), status="approved", notes=None,
                                       workshop_suitable=None, db=s)
    return go()


def test_approve_creates_and_links_a_species_row_when_none_exists():
    """21382 'Filipendula vulgaris' (pipeline suggestion approved): a bare row,
    severity 'unknown', linked in the same commit."""
    cands = [{"scientific_name": "Filipendula vulgaris", "score": 0.0337, "source": "plantnet"}]

    async def run():
        eng, S = await _db(rows=[_obs(21382, species_suggested="Filipendula vulgaris",
                                      species_candidates_json=json.dumps(cands))])
        await _approve(S, 21382)
        async with S() as s:
            o = await s.get(Observation, 21382)
            sp = await s.get(Species, o.species_id) if o.species_id else None
            out = (o.species_primary, o.species_id, o.review_status, o.identification_status,
                   sp and (sp.scientific_name, sp.name_key, sp.toxicity_severity, sp.edibility_status))
        await eng.dispose()
        return out

    sp_primary, sid, rs, ids, sp = _run(run())
    assert sp_primary == "Filipendula vulgaris" and sid is not None and rs == "approved" and ids == "identified"
    assert sp[0] == "Filipendula vulgaris" and sp[1] == "filipendula vulgaris"
    assert sp[2] == "unknown"                 # born never-assessed: fails closed
    assert sp[3] in (None, "unknown")         # no verdict invented


def test_approve_links_a_registered_synonym_without_a_new_row():
    """21950 / 22074 'Conyza canadensis' → the Erigeron canadensis card (342)."""
    cands = [{"scientific_name": "Conyza canadensis", "score": 0.3488, "source": "plantnet"}]

    async def run():
        eng, S = await _db(species=[ERIGERON], synonyms=[CONYZA_SYN],
                           rows=[_obs(22074, species_suggested="Conyza canadensis",
                                      species_candidates_json=json.dumps(cands))])
        await _approve(S, 22074)
        async with S() as s:
            o = await s.get(Observation, 22074)
            n = await s.scalar(select(func.count(Species.id)))
            out = (o.species_primary, o.species_id, n)
        await eng.dispose()
        return out

    assert _run(run()) == ("Conyza canadensis", 342, 1)


def test_ensure_species_row_never_touches_a_linked_or_existing_row():
    async def run():
        eng, S = await _db(species=[PICEA], rows=[_obs(1, species_primary="Picea abies", species_id=366),
                                                 _obs(2, species_primary="picea abies")])
        async with S() as s:
            o1, o2 = await s.get(Observation, 1), await s.get(Observation, 2)
            r = (await ensure_species_row(s, o1), await ensure_species_row(s, o2))
            await s.commit()
            n = await s.scalar(select(func.count(Species.id)))
        await eng.dispose()
        return r, n
    assert _run(run()) == ((366, 366), 1)


def test_bulk_approve_links_species_and_skips_unrecognised_names():
    async def _noop(*a, **k):
        return None
    bulk_actions.bp_progress = _noop
    bulk_actions.bp_finish = _noop
    cands = [{"scientific_name": "Ganoderma applanatum", "score": 0.12, "source": "inaturalist"}]

    async def run():
        eng, S = await _db(rows=[
            _obs(21453, species_suggested="Ganoderma applanatum", species_candidates_json=json.dumps(cands)),
            _obs(21585, species_suggested="norway spruce", species_candidates_json="[]"),
        ])
        bulk_actions.AsyncSessionLocal = S
        await bulk_actions._bulk_review_task([21453, 21585], "approved", None)
        async with S() as s:
            a, b = await s.get(Observation, 21453), await s.get(Observation, 21585)
            edits_b = await s.scalar(select(func.count(ObservationEdit.id)).where(ObservationEdit.observation_id == 21585))
            out = ((a.species_primary, a.species_id is not None, a.review_status, a.top_score,
                    json.loads(a.species_candidates_json)[0]["scientific_name"]),
                   (b.species_primary, b.species_id, b.review_status, b.species_suggested, edits_b))
        await eng.dispose()
        return out

    a, b = _run(run())
    assert a == ("Ganoderma applanatum", True, "approved", 0.12, "Ganoderma applanatum")
    assert b == (None, None, "needs_review", "norway spruce", 0)     # untouched


# ── C-04 ──────────────────────────────────────────────────────────────────────

def test_approve_refuses_a_typed_common_name_and_writes_nothing():
    async def run():
        eng, S = await _db(species=[PICEA], rows=[_obs(21585, species_suggested="norway spruce",
                                                       species_candidates_json="[]")])
        try:
            await _approve(S, 21585)
            raised = None
        except HTTPException as e:
            raised = (e.status_code, e.detail)
        async with S() as s:
            o = await s.get(Observation, 21585)
            edits = await s.scalar(select(func.count(ObservationEdit.id)))
            out = (raised, o.species_primary, o.review_status, o.species_suggested, edits)
        await eng.dispose()
        return out

    raised, sp, rs, sug, edits = _run(run())
    assert raised[0] == 409 and "norway spruce" in raised[1]
    assert (sp, rs, sug, edits) == (None, "needs_review", "norway spruce", 0)


def test_promotable_suggestion_rules():
    cands = json.dumps([{"scientific_name": "Picea abies", "score": 0.2}])

    async def run():
        orphan = dict(id=685, scientific_name="norway spruce", name_key="norway spruce",
                      orphaned_at=datetime(2026, 10, 21))
        eng, S = await _db(species=[PICEA, ERIGERON, orphan], synonyms=[CONYZA_SYN])
        out = []
        async with S() as s:
            for sug, cj in (("Picea abies", cands),        # pipeline suggestion (stored candidate)
                            ("picea abies", "[]"),          # typed, a species card in use (name_key)
                            ("Conyza canadensis", "[]"),    # typed, registered synonym
                            ("norway spruce", "[]"),        # typed common name; only an orphaned junk card
                            ("Filipendula vulgaris", "[]")):  # typed, unknown anywhere
                out.append(await promotable_suggestion(
                    s, Observation(species_suggested=sug, species_candidates_json=cj)))
        await eng.dispose()
        return out

    assert _run(run()) == ["Picea abies", "Picea abies", "Conyza canadensis", None, None]


def test_confirm_species_clears_the_pending_suggestion():
    from app.api.reidentify import ConfirmSpeciesRequest, confirm_species

    async def run():
        eng, S = await _db(species=[PICEA], rows=[_obs(21585, species_suggested="norway spruce")])
        async with S() as s:
            await confirm_species(21585, BackgroundTasks(), ConfirmSpeciesRequest(
                scientific_name="Picea abies", common_name="Norway Spruce", source="manual_entry"), db=s)
        await _approve(S, 21585)                               # a later approve keeps the pick
        async with S() as s:
            o = await s.get(Observation, 21585)
            out = (o.species_primary, o.species_id, o.species_suggested, o.review_status)
        await eng.dispose()
        return out

    assert _run(run()) == ("Picea abies", 366, None, "approved")


def test_the_21585_race_no_longer_writes_the_typed_name():
    """Approve's session reads the row BEFORE the Look-up pick commits (stale:
    no species, suggestion 'norway spruce'); the pick then commits; the approve
    continues with its stale row. Before: species_primary became 'norway spruce'.
    Now: 409 and the pick stands."""
    from app.api.observations import update_review
    from app.api.reidentify import ConfirmSpeciesRequest, confirm_species

    async def run():
        eng, S = await _db(species=[PICEA], rows=[_obs(21585, species_suggested="norway spruce")])
        async with S() as approve_s:
            # The stale read. Keep the reference: the identity map holds rows
            # weakly, and a garbage-collected row would be re-read fresh.
            stale = await approve_s.get(Observation, 21585)
            assert stale.species_primary is None and stale.species_suggested == "norway spruce"
            async with S() as pick_s:
                await confirm_species(21585, BackgroundTasks(), ConfirmSpeciesRequest(
                    scientific_name="Picea abies", source="manual_entry"), db=pick_s)
            try:
                await update_review(21585, BackgroundTasks(), status="approved", notes=None,
                                    workshop_suitable=None, db=approve_s)
                raised = None
            except HTTPException as e:
                raised = e.status_code
        async with S() as s:
            o = await s.get(Observation, 21585)
            out = (raised, o.species_primary, o.review_status)
        await eng.dispose()
        return out

    assert _run(run()) == (409, "Picea abies", "manually_verified")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
