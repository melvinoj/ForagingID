"""
Tests for fix batch 3 (audit B2-02 / P2, 20 Oct 2026): saving a species'
verdict also sets toxicity_severity, through ONE rule
(app.models.species.severity_for_verdict), with a species_edibility_history
row; 'unknown' = never assessed and fails closed.

Covers the pure rule, both verdict endpoints (PATCH /api/edibility/status and
/bulk-status) against a throw-away SQLite DB, and the ORM default for new
species.

Run from project root:  python -m pytest tests/test_verdict_severity.py -v
Or standalone:          python tests/test_verdict_severity.py
"""

import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import BackgroundTasks, HTTPException  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main  # noqa: E402,F401  (registers every model on Base.metadata, as create_all needs)
from app.database import Base  # noqa: E402
from app.models.species import (  # noqa: E402
    Species, SpeciesEdibilityHistory, SeverityRuleError, culinary_allowed, severity_for_verdict, severity_is_none,
)
from app.api.edibility import (  # noqa: E402
    BulkEdibilityIn, EdibilityStatusIn, bulk_set_edibility_status, set_edibility_status,
)
from app.api.identity import Identity  # noqa: E402

CURATOR = Identity(user_id=None, is_guest=False, is_anonymous_guest=False, workshop_session_id=None)


def _raises(fn, *a):
    try:
        fn(*a)
    except SeverityRuleError:
        return True
    return False


# ── the rule ─────────────────────────────────────────────────────────────────

def test_toxic_sets_toxic_and_keeps_deadly():
    assert severity_for_verdict("toxic", "none") == "toxic"
    assert severity_for_verdict("toxic", "unknown") == "toxic"
    assert severity_for_verdict("toxic", None) == "toxic"
    assert severity_for_verdict("toxic", "toxic") == "toxic"
    assert severity_for_verdict("toxic", "deadly") == "deadly"            # never lowered automatically
    assert severity_for_verdict("toxic", "none", "deadly") == "deadly"    # deadly is a severity of toxic


def test_toxic_cannot_be_none_or_unknown():
    assert _raises(severity_for_verdict, "toxic", "none", "none")
    assert _raises(severity_for_verdict, "toxic", "toxic", "unknown")


def test_edible_and_caution_set_none_when_not_hazardous():
    for v in ("edible", "caution"):
        assert severity_for_verdict(v, "none") == "none"
        assert severity_for_verdict(v, "unknown") == "none"               # the verdict is the assessment
        assert severity_for_verdict(v, None) == "none"


def test_edible_and_caution_never_lower_a_hazard_automatically():
    for v in ("edible", "caution"):
        for cur in ("toxic", "deadly"):
            assert _raises(severity_for_verdict, v, cur)


def test_explicit_relax_is_a_curator_choice():
    assert severity_for_verdict("edible", "toxic", "none") == "none"
    assert severity_for_verdict("caution", "deadly", "none") == "none"
    assert severity_for_verdict("caution", "none", "toxic") == "toxic"   # e.g. toxic parts


def test_edible_cannot_carry_a_hazard_severity():
    assert _raises(severity_for_verdict, "edible", "none", "toxic")
    assert _raises(severity_for_verdict, "edible", "none", "unknown")
    assert _raises(severity_for_verdict, "caution", "none", "deadly")


def test_inedible_leaves_severity_alone_unless_chosen():
    for cur in ("none", "toxic", "unknown"):
        assert severity_for_verdict("inedible", cur) == cur               # inedible ≠ toxic
    assert severity_for_verdict("inedible", "deadly") == "deadly"         # never lowered automatically
    assert severity_for_verdict("inedible", "toxic", "none") == "none"
    assert _raises(severity_for_verdict, "inedible", "none", "deadly")


def test_unknown_verdict_never_reads_as_safe():
    assert severity_for_verdict("unknown", "none") == "unknown"
    assert severity_for_verdict("unknown", "toxic") == "toxic"
    assert severity_for_verdict("unknown", "deadly") == "deadly"
    assert _raises(severity_for_verdict, "unknown", "toxic", "none")


def test_bad_inputs_refused():
    assert _raises(severity_for_verdict, "likely_edible", "none")
    assert _raises(severity_for_verdict, "toxic", "none", "lethal")


def test_unknown_severity_fails_closed():
    # Severity half (severity_is_none) + the full rule (culinary_allowed → safety_decision, 21 Oct).
    assert severity_is_none("none") and not severity_is_none("unknown")
    assert not severity_is_none("toxic") and not severity_is_none("deadly") and not severity_is_none(None)
    assert culinary_allowed("none", "edible") and not culinary_allowed("unknown", "edible")
    assert not culinary_allowed("toxic", "caution") and not culinary_allowed("deadly", "toxic")
    assert not culinary_allowed(None, "edible") and not culinary_allowed("none", "inedible")


# ── endpoints, on a throw-away DB ────────────────────────────────────────────

def _db():
    path = os.path.join(tempfile.mkdtemp(prefix="sevtest_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    return eng, async_sessionmaker(eng, expire_on_commit=False)


async def _add(S, name, status, sev):
    async with S() as s:
        sp = Species(scientific_name=name, name_key=name.lower(), edibility_status=status, toxicity_severity=sev)
        s.add(sp)
        await s.commit()
        return sp.id


async def _state(S, sid):
    async with S() as s:
        sp = await s.get(Species, sid)
        hist = (await s.execute(select(SpeciesEdibilityHistory).where(SpeciesEdibilityHistory.species_id == sid)
                                .order_by(SpeciesEdibilityHistory.id))).scalars().all()
        return sp.edibility_status, sp.toxicity_severity, [(h.field, h.old_value, h.new_value, h.changed_by) for h in hist]


async def _patch(S, sid, **kw):
    async with S() as s:
        return await set_edibility_status(sid, EdibilityStatusIn(**kw), BackgroundTasks(), db=s, identity=CURATOR)


def test_patch_toxic_sets_severity_with_history():
    async def run():
        eng, S = _db()
        sid = await _add(S, "Amanita muscaria", "caution", "none")
        r = await _patch(S, sid, edibility_status="toxic", verified=True)
        assert r["toxicity_severity"] == "toxic"
        st, sev, hist = await _state(S, sid)
        assert (st, sev) == ("toxic", "toxic")
        assert ("toxicity_severity", "none", "toxic", "human") in hist
        assert ("edibility_status", "caution", "toxic", "human") in hist
        await eng.dispose()
    asyncio.run(run())


def test_patch_keeps_deadly():
    async def run():
        eng, S = _db()
        sid = await _add(S, "Atropa bella-donna", "unknown", "deadly")
        await _patch(S, sid, edibility_status="toxic", verified=True)
        st, sev, hist = await _state(S, sid)
        assert (st, sev) == ("toxic", "deadly")
        assert not [h for h in hist if h[0] == "toxicity_severity"]          # unchanged → no severity row
        await eng.dispose()
    asyncio.run(run())


def test_patch_refused_relax_writes_nothing():
    async def run():
        eng, S = _db()
        sid = await _add(S, "Hedera helix", "toxic", "toxic")
        try:
            await _patch(S, sid, edibility_status="edible", verified=True)
        except HTTPException as e:
            assert e.status_code == 400
        else:
            raise AssertionError("edible over a toxic severity must be refused without an explicit severity")
        assert await _state(S, sid) == ("toxic", "toxic", [])
        await eng.dispose()
    asyncio.run(run())


def test_patch_explicit_relax_by_curator():
    async def run():
        eng, S = _db()
        sid = await _add(S, "Sambucus nigra", "toxic", "toxic")
        await _patch(S, sid, edibility_status="caution", verified=True, toxicity_severity="none")
        st, sev, hist = await _state(S, sid)
        assert (st, sev) == ("caution", "none")
        assert ("toxicity_severity", "toxic", "none", "human") in hist
        await eng.dispose()
    asyncio.run(run())


def test_patch_unknown_from_none_becomes_unassessed():
    async def run():
        eng, S = _db()
        sid = await _add(S, "Poa annua", "edible", "none")
        await _patch(S, sid, edibility_status="unknown")
        assert (await _state(S, sid))[:2] == ("unknown", "unknown")
        await eng.dispose()
    asyncio.run(run())


def test_patch_edible_assesses_a_never_assessed_species():
    async def run():
        eng, S = _db()
        sid = await _add(S, "Urtica dioica", "unknown", "unknown")
        await _patch(S, sid, edibility_status="edible", verified=True)
        assert (await _state(S, sid))[:2] == ("edible", "none")
        await eng.dispose()
    asyncio.run(run())


def test_bulk_uses_the_same_rule_and_skips_refusals():
    async def run():
        eng, S = _db()
        a = await _add(S, "Heracleum mantegazzianum", "unknown", "none")
        b = await _add(S, "Conium maculatum", "toxic", "deadly")
        c = await _add(S, "Allium ursinum", "unknown", "unknown")
        async with S() as s:
            r = await bulk_set_edibility_status(BulkEdibilityIn(updates=[
                {"species_id": a, "edibility_status": "toxic"},
                {"species_id": b, "edibility_status": "edible"},            # refused: would lower deadly
                {"species_id": c, "edibility_status": "edible"},
            ]), BackgroundTasks(), db=s, identity=CURATOR)
        assert r["updated"] == 2 and len(r["errors"]) == 1 and str(b) in r["errors"][0]
        st, sev, hist = await _state(S, a)
        assert (st, sev) == ("toxic", "toxic") and ("toxicity_severity", "none", "toxic", "human") in hist
        assert await _state(S, b) == ("toxic", "deadly", [])
        assert (await _state(S, c))[:2] == ("edible", "none")
        await eng.dispose()
    asyncio.run(run())


def test_new_species_is_born_unassessed():
    async def run():
        eng, S = _db()
        async with S() as s:
            sp = Species(scientific_name="Novus speciesus", name_key="novus speciesus", edibility_status="unknown")
            s.add(sp)
            await s.commit()
            assert sp.toxicity_severity == "unknown"
            assert not culinary_allowed(sp.toxicity_severity, sp.edibility_status)
        await eng.dispose()
    asyncio.run(run())


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
