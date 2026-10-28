"""
Tests for audit batch 11b — the species merge routine and data fixes (Melvin, 27–28 Oct 2026).

  * merge_species_cards re-keys every species-keyed table to the kept card —
    observations (id + name + suggestion), candidates, drafts, recipes, edibility
    history/conditions, lookalikes (both columns), synonyms (+ the discard's own
    name), session/list/dismissal rows (deduped), encounters, sources,
    enrichment_sources, species_resources (string-keyed by name), map note tags,
    walk waypoints, walk override files and experience_publications ids — then
    deletes the discard card.
  * TEXT RULE: the human-edited side wins a conflict; otherwise the kept card's
    text; the losing text is kept in a history row.
  * VERDICT RULE: toxic wins; a human-verified side beats an unverified one;
    the human lock is kept.
  * The routine never calls the rename cascade (AST check), and POST
    /api/species/merge goes through it.
  * Rename re-derives family/genus for the new name (no stale lineage).
  * Cards kept but orphan-marked are absent from GET /api/species/ and not deleted.
  * Pastinaca sativa at caution/none is not a hazard species (the hazard index skips it).

No external calls (GBIF is stubbed); throw-away SQLite DBs.

Run from project root:  python tests/test_batch11b_merge.py
"""
import ast
import asyncio
import json
import os
import pathlib
import sys
import tempfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main  # noqa: E402,F401  (registers every model on Base.metadata)
from app.api.identity import Identity  # noqa: E402
from app.database import Base  # noqa: E402
from app.models.culinary import CulinaryInfo  # noqa: E402
from app.models.observation import Observation  # noqa: E402
from app.models.species import (CulinaryInfoHistory, Species, SpeciesEdibilityHistory,  # noqa: E402
                                new_species_card)
from app.services.species_merge import merge_species_cards  # noqa: E402

CURATOR = Identity(user_id=1, is_guest=False, is_anonymous_guest=False, workshop_session_id=None)


def _db():
    path = os.path.join(tempfile.mkdtemp(prefix="b11b_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    return path, eng, async_sessionmaker(eng, expire_on_commit=False)


def _card(name, verdict="edible", sev="none", verified=True, **kw):
    sp = new_species_card(name, **kw)
    sp.edibility_status, sp.toxicity_severity = verdict, sev
    sp.edibility_verified = verified
    sp.edibility_verified_by = "human" if verified else None
    return sp


async def _seed(S, overrides_dir):
    """Card 1 = keep (accepted name), card 2 = discard, with a row in every table."""
    async with S() as s:
        keep, disc = _card("Mycelis muralis"), _card("Lactuca muralis", common_names='["Wall lettuce"]')
        other = _card("Taraxacum officinale")
        s.add_all([keep, disc, other])
        await s.flush()
        k, d, o = keep.id, disc.id, other.id
        kci = CulinaryInfo(species_id=k, edible_parts="keep parts", id_notes="same")
        dci = CulinaryInfo(species_id=d, edible_parts="discard parts (human)", id_notes="same",
                           taste_notes="discard taste", recipe="discard recipe")
        s.add_all([kci, dci])
        await s.flush()
        s.add(CulinaryInfoHistory(culinary_info_id=dci.id, field_name="edible_parts", old_value=None,
                                  new_value="discard parts (human)", changed_by="human"))
        s.add(Observation(file_path="/tmp/1.jpg", file_hash="h1", review_status="approved",
                          identification_status="identified", species_primary="Lactuca muralis", species_id=d))
        s.add(Observation(file_path="/tmp/2.jpg", file_hash="h2", review_status="needs_review",
                          species_suggested="Lactuca muralis"))
        now = datetime.utcnow().isoformat(sep=" ")
        for sql in (
            f"INSERT INTO species_candidates (observation_id, species_id, scientific_name_raw, confidence_score, rank, api_source, identified_at) VALUES (1, {d}, 'Lactuca muralis', 0.5, 1, 'plantnet', '{now}')",
            f"INSERT INTO species_ai_drafts (species_id, field_name, draft_text, status, generated_at, approved_by) VALUES ({d}, 'taste_notes', 'x', 'pending', '{now}', '')",
            f"INSERT INTO species_recipes (species_id, title, body, season, is_preferred, is_medicinal_prep, source, status, hide_from_public, created_at, updated_at) VALUES ({d}, 'R', 'b', 'all', 0, 0, 'manual', 'approved', 0, '{now}', '{now}')",
            f"INSERT INTO species_edibility_history (species_id, field, old_value, new_value, changed_at, changed_by) VALUES ({d}, 'edibility_status', NULL, 'edible', '{now}', 'human')",
            f"INSERT INTO species_edibility_conditions (species_id, part, preparation, season, safe, created_at, updated_at) VALUES ({d}, 'leaf', 'raw', 'all', 1, '{now}', '{now}')",
            f"INSERT INTO species_lookalikes (species_id, lookalike_species_id, lookalike_name, toxicity_level, created_at, updated_at) VALUES ({o}, {d}, 'Lactuca muralis', 'none', '{now}', '{now}')",
            f"INSERT INTO species_lookalikes (species_id, lookalike_species_id, lookalike_name, toxicity_level, created_at, updated_at) VALUES ({d}, {o}, 'Taraxacum officinale', 'none', '{now}', '{now}')",
            f"INSERT INTO species_synonyms (synonym_name_key, synonym_scientific_name, canonical_species_id, created_at) VALUES ('prenanthes muralis', 'Prenanthes muralis', {d}, '{now}')",
            f"INSERT INTO species_resources (species_name, resource_type, url, added_at) VALUES ('Lactuca muralis', 'link', 'https://a', '{now}')",
            f"INSERT INTO species_resources (species_name, resource_type, url, added_at) VALUES ('Lactuca muralis', 'link', 'https://dup', '{now}')",
            f"INSERT INTO species_resources (species_name, resource_type, url, added_at) VALUES ('Mycelis muralis', 'link', 'https://dup', '{now}')",
            f"INSERT INTO map_notes (latitude, longitude, text, species_tags, created_at) VALUES (1, 1, 'n', '[\"Lactuca muralis\"]', '{now}')",
            f"INSERT INTO saved_walks (name, created_at, waypoints_json) VALUES ('w', '{now}', '[{{\"species_id\": {d}}}]')",
            f"INSERT INTO experience_publications (saved_walk_id, slug, is_default, overrides_json, public_species_json, status, created_at, updated_at) VALUES (1, 'w', 0, '{{\"hide_species_ids\": [{d}]}}', '{{\"species\": [{{\"id\": {d}, \"scientific_name\": \"Lactuca muralis\"}}]}}', 'published', '{now}', '{now}')",
            f"INSERT INTO encounters (user_id, species_id, encounter_date, research_visible, created_at, encounter_type, shared_with_guests) VALUES (1, {d}, '{now}', 0, '{now}', 'field', 0)",
            f"INSERT INTO enrichment_sources (species_id, source_name, retrieved_at) VALUES ({d}, 'wikidata', '{now}')",
        ):
            await s.execute(text(sql))
        await s.commit()
    (pathlib.Path(overrides_dir) / "walk9.json").write_text(json.dumps({"slug": "w", "hide_species_ids": [d, k]}))
    return k, d, o


def test_merge_rekeys_every_table_and_deletes_the_discard():
    async def run():
        path, eng, S = _db()
        ov = tempfile.mkdtemp(prefix="b11b_ov_")
        k, d, o = await _seed(S, ov)
        async with S() as s:
            rep = await merge_species_cards(s, d, k, overrides_dir=pathlib.Path(ov))
            await s.commit()
        async with S() as s:
            q = lambda sql: s.execute(text(sql))
            assert await s.get(Species, d) is None
            obs = (await q("SELECT species_id, species_primary FROM observations WHERE id = 1")).one()
            assert tuple(obs) == (k, "Mycelis muralis"), obs
            assert (await q("SELECT species_suggested FROM observations WHERE id = 2")).scalar() == "Mycelis muralis"
            for t in ("species_candidates", "species_ai_drafts", "species_recipes", "species_edibility_conditions",
                      "encounters", "enrichment_sources"):
                assert (await q(f"SELECT count(*) FROM {t} WHERE species_id = {d}")).scalar() == 0, t
                assert (await q(f"SELECT count(*) FROM {t} WHERE species_id = {k}")).scalar() >= 1, t
            assert (await q(f"SELECT count(*) FROM species_edibility_history WHERE species_id = {d}")).scalar() == 0
            la = (await q("SELECT species_id, lookalike_species_id FROM species_lookalikes ORDER BY id")).all()
            assert [tuple(r) for r in la] == [(o, k), (k, o)], la
            syn = dict((await q("SELECT synonym_scientific_name, canonical_species_id FROM species_synonyms")).all())
            assert syn == {"Prenanthes muralis": k, "Lactuca muralis": k}, syn
            res = (await q("SELECT species_name, url FROM species_resources ORDER BY id")).all()
            assert sorted(tuple(r) for r in res) == [("Mycelis muralis", "https://a"), ("Mycelis muralis", "https://dup")], res
            assert json.loads((await q("SELECT species_tags FROM map_notes")).scalar()) == ["Mycelis muralis"]
            assert json.loads((await q("SELECT waypoints_json FROM saved_walks")).scalar()) == [{"species_id": k}]
            pov, pps = (await q("SELECT overrides_json, public_species_json FROM experience_publications")).one()
            assert json.loads(pov)["hide_species_ids"] == [k]
            # ids re-keyed, the published name left as published
            assert json.loads(pps)["species"] == [{"id": k, "scientific_name": "Lactuca muralis"}]
            assert json.loads((pathlib.Path(ov) / "walk9.json").read_text())["hide_species_ids"] == [k]
            # TEXT RULE: the human-edited discard text wins; the keep text is in history
            ci = (await s.execute(select(CulinaryInfo).where(CulinaryInfo.species_id == k))).scalar_one()
            assert ci.edible_parts == "discard parts (human)"
            assert ci.taste_notes == "discard taste" and ci.recipe == "discard recipe"
            assert (await q(f"SELECT count(*) FROM culinary_info WHERE species_id = {d}")).scalar() == 0
            h = (await q(f"SELECT old_value, new_value, changed_by FROM culinary_info_history WHERE culinary_info_id = {ci.id} "
                         "AND field_name = 'edible_parts' ORDER BY id")).all()
            assert ("keep parts", "discard parts (human)", "human") in [tuple(r) for r in h], h
            sp = await s.get(Species, k)
            assert sp.common_names == '["Wall lettuce"]'          # filled from the discard
            assert rep["deleted"] == d
        await eng.dispose()
    asyncio.run(run())


def test_text_conflict_without_human_edit_keeps_the_accepted_name_text():
    async def run():
        path, eng, S = _db()
        async with S() as s:
            keep, disc = _card("Coronilla varia"), _card("Securigera varia")
            s.add_all([keep, disc])
            await s.flush()
            s.add_all([CulinaryInfo(species_id=keep.id, id_notes="accepted text"),
                       CulinaryInfo(species_id=disc.id, id_notes="synonym text")])
            await s.commit()
            k, d = keep.id, disc.id
        async with S() as s:
            await merge_species_cards(s, d, k, overrides_dir=None)
            await s.commit()
        async with S() as s:
            ci = (await s.execute(select(CulinaryInfo).where(CulinaryInfo.species_id == k))).scalar_one()
            assert ci.id_notes == "accepted text"
            h = (await s.execute(select(CulinaryInfoHistory).where(CulinaryInfoHistory.field_name == "id_notes"))).scalar_one()
            assert (h.old_value, h.new_value) == ("synonym text", "accepted text")
        await eng.dispose()
    asyncio.run(run())


def test_verdict_rule_conservative_and_lock_kept():
    from app.services.species_merge import merged_verdict
    a, b = _card("A a", "edible", "none", True), _card("B b", "toxic", "toxic", False)
    assert merged_verdict(a, b) == ("toxic", "toxic", True)         # toxic wins, lock kept
    a, b = _card("A a", "edible", "none", True), _card("B b", "inedible", "none", False)
    assert merged_verdict(a, b) == ("edible", "none", True)         # human-verified beats unverified
    a, b = _card("A a", "edible", "none", True), _card("B b", "caution", "none", True)
    assert merged_verdict(a, b) == ("caution", "none", True)        # among equals, more conservative

    async def run():
        path, eng, S = _db()
        async with S() as s:
            keep, disc = _card("Keep me", "edible", "none", True), _card("Drop me", "toxic", "toxic", False)
            s.add_all([keep, disc])
            await s.commit()
            k, d = keep.id, disc.id
        async with S() as s:
            await merge_species_cards(s, d, k, overrides_dir=None)
            await s.commit()
        async with S() as s:
            sp = await s.get(Species, k)
            assert (sp.edibility_status, sp.toxicity_severity, sp.edibility_verified) == ("toxic", "toxic", True)
            h = (await s.execute(select(SpeciesEdibilityHistory).where(
                SpeciesEdibilityHistory.species_id == k, SpeciesEdibilityHistory.field == "edibility_status"))).scalars().all()
            assert [x.new_value for x in h] == ["toxic"]
        await eng.dispose()
    asyncio.run(run())


def test_merge_never_uses_the_rename_cascade_and_endpoint_delegates():
    src = pathlib.Path(ROOT, "app/services/species_merge.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    called = {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", "")
              for n in ast.walk(tree) if isinstance(n, ast.Call)}
    assert not called & {"rename_species_by_name", "rename_species", "_auto_merge_into"}, called
    cul = pathlib.Path(ROOT, "app/api/culinary.py").read_text(encoding="utf-8")
    body = cul[cul.index('@router.post("/api/species/merge")'):]
    body = body[:body.index("\n@router.")]
    assert "merge_species_cards(" in body and "_merged_into" not in body


def test_rename_rederives_family_and_genus():
    async def run():
        path, eng, S = _db()
        async with S() as s:
            sp = _card("Boletus edulus", family="Ericaceae", genus="Calluna")
            s.add(sp)
            s.add(Observation(file_path="/tmp/r.jpg", file_hash="r", review_status="approved",
                              species_primary="Boletus edulus"))
            await s.commit()
        import app.integrations.gbif as gbif
        from app.api import culinary
        from app.services import enrichment
        real_tax, real_enrich = gbif.enrich_species_taxonomy, enrichment.enrich_species

        async def fake_tax(sp, **kw):
            sp.family, sp.genus = "Boletaceae", "Boletus"
            return {"status": "EXACT", "flags": []}

        async def no_enrich(**kw):
            return "enriched"
        gbif.enrich_species_taxonomy, enrichment.enrich_species = fake_tax, no_enrich
        try:
            async with S() as s:
                await culinary.rename_species_by_name("Boletus edulus", culinary.RenameRequest(new_name="Boletus edulis"),
                                                      db=s, identity=CURATOR)
            # GBIF unavailable: family left empty (never stale), genus from the name
            async def broken(sp, **kw):
                raise RuntimeError("offline")
            gbif.enrich_species_taxonomy = broken
            async with S() as s:
                sp = await s.scalar(select(Species).where(Species.scientific_name == "Boletus edulis"))
                sp.family, sp.genus = "Ericaceae", "Calluna"
                await s.commit()
            async with S() as s:
                await culinary.rename_species_by_name("Boletus edulis", culinary.RenameRequest(new_name="Imleria badia"),
                                                      db=s, identity=CURATOR)
        finally:
            gbif.enrich_species_taxonomy, enrichment.enrich_species = real_tax, real_enrich
        async with S() as s:
            sp = await s.scalar(select(Species).where(Species.scientific_name == "Imleria badia"))
            assert (sp.family, sp.genus) == (None, "Imleria"), (sp.family, sp.genus)
            h = (await s.execute(select(SpeciesEdibilityHistory.field, SpeciesEdibilityHistory.new_value)
                                 .where(SpeciesEdibilityHistory.changed_by == "system:rename"))).all()
            assert ("family", "Boletaceae") in h and ("genus", "Imleria") in h, h
        await eng.dispose()
    asyncio.run(run())


def test_rename_onto_existing_name_merges_through_merge_species_cards():
    """Rename onto an existing name = a real merge: source card deleted, its rows
    re-keyed, verdict rule applied, synonym row added — no '_merged_into:' marker."""
    async def run():
        path, eng, S = _db()
        async with S() as s:
            keep = _card("Mycelis muralis", "edible", "none", False)
            disc = _card("Lactuca muralis", "caution", "mild", True)
            s.add_all([keep, disc])
            await s.flush()
            k, d = keep.id, disc.id
            s.add(CulinaryInfo(species_id=d, taste_notes="bitter (human)"))
            s.add(Observation(file_path="/tmp/m.jpg", file_hash="m", review_status="approved",
                              identification_status="identified", species_primary="Lactuca muralis", species_id=d))
            await s.commit()
        from app.api import culinary
        from app.services import enrichment, species_merge
        real_enrich, real_merge = enrichment.enrich_species, species_merge.merge_species_cards
        calls = []

        async def no_enrich(**kw):
            return "enriched"

        async def spy_merge(session, discard_id, keep_id, **kw):
            calls.append((discard_id, keep_id))
            return await real_merge(session, discard_id, keep_id, **{**kw, "overrides_dir": None})
        enrichment.enrich_species, species_merge.merge_species_cards = no_enrich, spy_merge
        try:
            async with S() as s:
                out = await culinary.rename_species_by_name(
                    "Lactuca muralis", culinary.RenameRequest(new_name="Mycelis muralis", new_common_name="Wall lettuce"),
                    db=s, identity=CURATOR)
        finally:
            enrichment.enrich_species, species_merge.merge_species_cards = real_enrich, real_merge
        assert out["auto_merged"] and calls == [(d, k)], (out, calls)
        async with S() as s:
            assert (await s.get(Species, d)) is None
            assert (await s.scalar(text("SELECT count(*) FROM species WHERE edibility_status LIKE '%merged_into%'"))) == 0
            sp = await s.get(Species, k)
            assert (sp.edibility_status, sp.edibility_verified) == ("caution", True), sp.edibility_status
            assert json.loads(sp.common_names)[0] == "Wall lettuce"
            o = await s.scalar(select(Observation))
            assert (o.species_id, o.species_primary) == (k, "Mycelis muralis")
            ci = await s.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == k))
            assert ci.taste_notes == "bitter (human)"
            syn = (await s.execute(text("SELECT count(*) FROM species_synonyms WHERE canonical_species_id = :k"), {"k": k})).scalar()
            assert syn >= 1
        await eng.dispose()
    asyncio.run(run())


def test_orphan_marked_kept_cards_are_not_in_the_species_list():
    async def run():
        path, eng, S = _db()
        async with S() as s:
            kept = _card("Allium cepa")
            kept.orphaned_at = datetime.utcnow()
            live = _card("Allium ursinum")
            s.add_all([kept, live])
            await s.flush()
            s.add(Observation(file_path="/tmp/k.jpg", file_hash="k", review_status="rejected",
                              species_primary="Allium cepa", species_id=kept.id))
            s.add(Observation(file_path="/tmp/l.jpg", file_hash="l", review_status="approved",
                              identification_status="identified", species_primary="Allium ursinum", species_id=live.id))
            await s.commit()
            kid = kept.id
        from app.api.culinary import list_species
        async with S() as s:
            names = {r["scientific_name"] for r in await list_species(db=s)}
            assert names == {"Allium ursinum"}, names
            assert (await s.get(Species, kid)) is not None
        await eng.dispose()
    asyncio.run(run())


def test_pastinaca_caution_none_is_not_a_hazard():
    async def run():
        path, eng, S = _db()
        async with S() as s:
            s.add(_card("Pastinaca sativa", "caution", "none", True, family="Apiaceae", genus="Pastinaca"))
            s.add(_card("Conium maculatum", "toxic", "deadly", True))
            await s.commit()
        from app.services.hazard_candidates import load_hazard_index
        from app.services.taxonomy import normalize_taxon_key
        async with S() as s:
            idx = await load_hazard_index(s)
        assert normalize_taxon_key("Pastinaca sativa") not in idx.by_key
        assert normalize_taxon_key("Conium maculatum") in idx.by_key
        await eng.dispose()
    asyncio.run(run())


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
