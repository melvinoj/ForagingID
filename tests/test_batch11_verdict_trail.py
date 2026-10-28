"""
Tests for audit batch 11 — verdict trail and locks (Melvin, 25 Oct 2026).

  * B2-08: every species-card creation path goes through new_species_card(),
    so a new card is born verdict 'unknown' + severity 'unknown' — never NULL.
    The five paths (confirm / species_link, enrichment ×2, rename, scan upsert)
    are run on a throw-away DB; an AST scan proves no other Species(...) exists.
  * B2-07: init_db no longer writes edibility_verified_by='auto' — a locked,
    PFAF-fingerprinted row with no provenance is unlocked for review instead.
  * B3-05 leftover: the bracken safety constant writes its verdict through the
    shared verdict writer — a verdict history row and verified_by
    'safety_constant' — and never re-stamps a human lock.
  * C-06: 'origin_unknown' history rows never count as human (curator-authored
    text, the verdict sweep's "latest human verdict", the experience gates).

No external calls; throw-away SQLite DBs.

Run from project root:  python tests/test_batch11_verdict_trail.py
"""
import ast
import asyncio
import os
import pathlib
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "scripts", "experience_export"))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main  # noqa: E402,F401  (registers every model on Base.metadata)
import app.database as database  # noqa: E402
from app.api.identity import Identity  # noqa: E402
from app.database import Base  # noqa: E402
from app.models.culinary import CulinaryInfo  # noqa: E402
from app.models.observation import Observation  # noqa: E402
from app.models.species import (Species, SpeciesEdibilityHistory, is_curator_authored,  # noqa: E402
                                new_species_card)

CURATOR = Identity(user_id=1, is_guest=False, is_anonymous_guest=False, workshop_session_id=None)


def _db():
    path = os.path.join(tempfile.mkdtemp(prefix="b11_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    return path, eng, async_sessionmaker(eng, expire_on_commit=False)


async def _card(S, name):
    async with S() as s:
        return await s.scalar(select(Species).where(Species.scientific_name == name))


# ── B2-08: every creation path is born unknown/unknown ───────────────────────

def test_every_creation_path_yields_unknown_verdict_and_severity():
    async def run():
        path, eng, S = _db()
        out = {}
        # 1. confirm path — species_link.ensure_species_row
        from app.services.species_link import ensure_species_row
        async with S() as s:
            obs = Observation(file_path="/tmp/a.jpg", file_hash="a", review_status="needs_review",
                              species_primary="Rubus pedatifolius")
            s.add(obs)
            await s.flush()
            await ensure_species_row(s, obs)
            await s.commit()
        out["confirm"] = await _card(S, "Rubus pedatifolius")
        # 2. enrichment._get_or_create_species
        from app.services import enrichment
        async with S() as s:
            await enrichment._get_or_create_species(s, "Geranium pusillum")
            await s.commit()
        out["enrich_get_or_create"] = await _card(S, "Geranium pusillum")
        # 3. enrichment.trigger_ai_drafts_for_species (its own session; enrich stubbed)
        real_sl, real_enrich = database.AsyncSessionLocal, enrichment.enrich_species

        async def _no_enrich(**kw):
            return "enriched"
        database.AsyncSessionLocal, enrichment.enrich_species = S, _no_enrich
        try:
            await enrichment.trigger_ai_drafts_for_species("Viola stagnina")
        finally:
            database.AsyncSessionLocal, enrichment.enrich_species = real_sl, real_enrich
        out["trigger_drafts"] = await _card(S, "Viola stagnina")
        # 4. rename of a name that exists only on observations
        from app.api.culinary import RenameRequest, rename_species_by_name
        async with S() as s:
            s.add(Observation(file_path="/tmp/b.jpg", file_hash="b", review_status="needs_review",
                              species_primary="Corylus maxim"))
            await s.commit()
        async with S() as s:
            await rename_species_by_name("Corylus maxim", RenameRequest(new_name="Corylus maxima"),
                                         db=s, identity=CURATOR)
        out["rename"] = await _card(S, "Corylus maxima")
        # 5. scan._upsert_species_card (its own session)
        from app.api import scan
        real_scan_sl = scan.AsyncSessionLocal
        scan.AsyncSessionLocal = S
        try:
            cand = {"scientific_name": "Cirsium rivulare", "family": "Asteraceae", "genus": "Cirsium"}
            await scan._upsert_species_card(1, cand, [cand])
        finally:
            scan.AsyncSessionLocal = real_scan_sl
        out["scan_upsert"] = await _card(S, "Cirsium rivulare")
        await eng.dispose()
        return out
    out = asyncio.run(run())
    for path_name, sp in out.items():
        assert sp is not None, f"{path_name}: no card created"
        assert (sp.edibility_status, sp.toxicity_severity) == ("unknown", "unknown"), \
            f"{path_name}: born {sp.edibility_status!r}/{sp.toxicity_severity!r}"
        assert not sp.edibility_verified and sp.edibility_verified_by is None, path_name


def test_no_species_constructor_outside_the_helper():
    found = []
    for p in pathlib.Path(ROOT, "app").rglob("*.py"):
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "Species":
                found.append(f"{p.relative_to(ROOT)}:{n.lineno}")
    assert found == ["app/models/species.py:%d" % _helper_ctor_line()], found


def _helper_ctor_line():
    src = pathlib.Path(ROOT, "app/models/species.py").read_text(encoding="utf-8")
    i = src.index("def new_species_card(")
    return src[:src.index("return Species(", i)].count("\n") + 1


def test_helper_refuses_a_verdict_or_severity():
    for k in ("edibility_status", "toxicity_severity"):
        try:
            new_species_card("Foo bar", **{k: "edible" if k == "edibility_status" else "none"})
        except ValueError:
            continue
        raise AssertionError(f"new_species_card accepted {k}")


# ── B2-07: startup no longer writes 'auto' ───────────────────────────────────

def test_startup_backfill_never_writes_auto():
    src = pathlib.Path(ROOT, "app/database.py").read_text(encoding="utf-8")
    assert "edibility_verified_by = 'auto'" not in src

    async def run():
        path, eng, S = _db()
        async with S() as s:
            sp = Species(scientific_name="Allium testum", name_key="allium testum",
                         edibility_status="edible", toxicity_severity="none", edibility_verified=True)
            s.add(sp)
            await s.flush()
            s.add(CulinaryInfo(species_id=sp.id, ai_approved_fields_json="{}"))   # fingerprinted
            await s.commit()
        con = sqlite3.connect(path)
        con.execute("INSERT INTO enrichment_sources (species_id, source_name, extraction_confidence, retrieved_at) "
                    "VALUES ((SELECT id FROM species), 'pfaf', 0.9, '2026-06-01')")
        con.commit(); con.close()
        real = database.engine
        database.engine = eng
        try:
            await database.init_db()
        finally:
            database.engine = real
        async with S() as s:
            row = await s.scalar(select(Species).where(Species.scientific_name == "Allium testum"))
        await eng.dispose()
        return row
    row = asyncio.run(run())
    assert row.edibility_verified_by == "unlocked_for_review" and not row.edibility_verified, \
        (row.edibility_verified, row.edibility_verified_by)


# ── B3-05 leftover: bracken through the shared verdict writer ────────────────

def _bracken_run(status, verified, verified_by, severity):
    async def run():
        path, eng, S = _db()
        async with S() as s:
            sp = Species(scientific_name="Pteridium aquilinum", name_key="pteridium aquilinum",
                         edibility_status=status, toxicity_severity=severity,
                         edibility_verified=verified, edibility_verified_by=verified_by)
            s.add(sp)
            await s.commit()
        from app.services.enrichment import enrich_species
        async with S() as s:
            sp = await s.scalar(select(Species))
            await enrich_species(session=s, species=sp, re_enrich=True)
            await s.commit()
        async with S() as s:
            sp = await s.scalar(select(Species))
            hist = (await s.execute(select(SpeciesEdibilityHistory.field, SpeciesEdibilityHistory.old_value,
                                           SpeciesEdibilityHistory.new_value, SpeciesEdibilityHistory.changed_by)
                                    .order_by(SpeciesEdibilityHistory.id))).all()
        await eng.dispose()
        return sp, [tuple(h) for h in hist]
    return asyncio.run(run())


def test_bracken_writes_a_verdict_row_stamped_safety_constant():
    sp, hist = _bracken_run("unknown", False, None, "unknown")
    assert (sp.edibility_status, sp.toxicity_severity, sp.edibility_verified, sp.edibility_verified_by) == \
        ("toxic", "toxic", True, "safety_constant")
    assert ("edibility_status", "unknown", "toxic", "safety_constant") in hist
    assert ("edibility_verified_by", None, "safety_constant", "safety_constant") in hist
    assert all(h[3] == "safety_constant" for h in hist)


def test_bracken_never_restamps_a_human_lock():
    sp, hist = _bracken_run("toxic", True, "human", "toxic")
    assert (sp.edibility_status, sp.edibility_verified_by) == ("toxic", "human")
    assert hist == []


# ── C-06: 'origin_unknown' never counts as human ─────────────────────────────

def test_origin_unknown_never_counts_as_human():
    # curator-authored text (experience gates' human_authored + Review approve)
    assert not is_curator_authored("origin_unknown", "edible", "edible")
    assert is_curator_authored("human", "edible", "edible")
    # verdict sweep "latest human verdict" + species_link listability + every
    # history lock: they all compare changed_by == 'human' exactly
    import verdict_sweep_drafts
    src = pathlib.Path(verdict_sweep_drafts.__file__).read_text(encoding="utf-8")
    assert "field = 'edibility_status' AND changed_by = 'human'" in src
    assert "h.field_name = 'edibility_status' AND h.changed_by = 'human'" in src
    link = pathlib.Path(ROOT, "app/services/species_link.py").read_text(encoding="utf-8")
    assert 'SpeciesEdibilityHistory.changed_by == "human"' in link
    # experience gates read the lock flag, never history
    import gates
    assert gates.human_verified({"edibility_verified": 1, "edibility_verified_by": "human"})
    assert not gates.human_verified({"edibility_verified": 1, "edibility_verified_by": "origin_unknown"})
    # no reader anywhere treats "not some machine stamp" as human
    for base in ("app", "scripts"):
        for p in pathlib.Path(ROOT, base).rglob("*.py"):
            t = p.read_text(encoding="utf-8")
            for bad in ("changed_by != 'system", 'changed_by != "system', "changed_by not in",
                        "changed_by.notin_", "changed_by NOT IN", "changed_by <>"):
                assert bad not in t, f"{p}: {bad}"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
