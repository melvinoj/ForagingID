#!/usr/bin/env python3
"""
Bryony / Usnea / Salix (Melvin's decisions, 28 Oct 2026).

Every step is a dry run unless --apply. With --apply it first takes a
WAL-consistent DB snapshot (batch11b_data.snapshot), writes in ONE transaction,
commits, then re-reads every changed row by id and prints every field.

    PYTHONPATH=. python scripts/bryony_genus_28oct.py <step> [--apply]

Steps:
  review8229  obs 8229 → needs_review, label bryony_check, reviewer note
  verdict879  card 879 toxic / toxic, verified (human history rows)
  warn879     card 879 look_alike_warnings + preparation_warnings, Melvin verbatim
  genus       photos on 880 Usnea / 881 Salix → needs_review (genus_reid), species
              cleared; then both cards deleted by the 11b step G route.
              --cards 354,530 does the same for Crocus / Taraxacum sect. Taraxacum
              (Melvin, 28 Oct: "treat like Usnea"); rejected photos stay rejected
              (species_id NULL, a suggestion naming the card cleared)
  hide136     card 136 Bryonia syriaca orphan-marked (not deleted, verdict unchanged)
"""
import argparse
import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "scripts"))

from sqlalchemy import select, text  # noqa: E402

from batch11b_data import (DELETE_ROWS, NULL_ROWS, OBS_COLS, SPECIES_COLS,  # noqa: E402
                           show, snapshot)
from app.database import AsyncSessionLocal  # noqa: E402
from app.models.culinary import CulinaryInfo  # noqa: E402
from app.models.observation import Observation  # noqa: E402
from app.models.species import CulinaryInfoHistory, Species  # noqa: E402

BRYONY = 879
GENUS_CARDS = (880, 881)
SYRIACA = 136
CI_COLS = "id, species_id, look_alike_warnings, preparation_warnings, edible_parts"

NOTE_8229 = "Melvin re-check: white bryony (B. dioica) vs B. alba — not black bryony"
LOOKALIKE_879 = (
    "Care must be taken, as young spring shoots are easily mistaken for wild hops. Look out for its coiled "
    "tendrils, alternate leaves with five lobes that are rough and hairy. Hops has no tendrils, its whole stem "
    "twines around, and it has opposite leaves with hooked hairs. Black bryony, which is also toxic, has glossy "
    "shoots with heart-shaped leaves without lobes. As with any root, don't take one unless you know what plant "
    "it's from."
)
PREP_879 = "No preparation makes any part safe to eat."


async def _hist(s, sid, since):
    ids = (await s.execute(text("SELECT id FROM species_edibility_history WHERE species_id = :i AND changed_at >= :t "
                                "ORDER BY id"), {"i": sid, "t": since})).scalars().all()
    await show(s, "species_edibility_history", ids)


async def _obs_edits(s, oids, since):
    ids = (await s.execute(text(f"SELECT id FROM observation_edits WHERE observation_id IN ({','.join(map(str, oids))}) "
                                "AND edited_at >= :t ORDER BY id"), {"t": since})).scalars().all()
    await show(s, "observation_edits", ids)


def _append_note(obs, note):
    from app.services.observation_service import _log_edit
    s = obs._sa_instance_state.session
    old = obs.reviewer_notes
    obs.reviewer_notes = (old + "\n" + note) if old else note
    _log_edit(s, obs, "reviewer_notes", old, obs.reviewer_notes, "human")


async def step_review8229(args):
    from app.services.observation_service import _log_edit
    from app.services.species_link import refresh_orphan_markers, species_has_live_observation
    async with AsyncSessionLocal() as s:
        await show(s, "observations", [8229], OBS_COLS)
        await show(s, "species", [BRYONY], SPECIES_COLS)
    if not args.apply:
        return
    snapshot()
    since = datetime.utcnow().isoformat(sep=" ")
    async with AsyncSessionLocal() as s:
        obs = await s.get(Observation, 8229)
        if obs.species_id != BRYONY:
            raise SystemExit(f"STOP: 8229 species_id is {obs.species_id}, expected {BRYONY}")
        _append_note(obs, NOTE_8229)
        _log_edit(s, obs, "review_status", obs.review_status, "needs_review", "human")
        obs.review_status = "needs_review"
        _log_edit(s, obs, "review_label", obs.review_label, "bryony_check", "human")
        obs.review_label = "bryony_check"
        await refresh_orphan_markers(s, obs)     # live → only ever clears a marker
        await s.commit()
    async with AsyncSessionLocal() as s:
        print("READ-BACK")
        await show(s, "observations", [8229], OBS_COLS)
        await _obs_edits(s, [8229], since)
        await show(s, "species", [BRYONY], SPECIES_COLS)
        print("  879 has a live observation:", await species_has_live_observation(s, BRYONY))


async def step_verdict879(args):
    from app.api.edibility import _write_verdict
    async with AsyncSessionLocal() as s:
        await show(s, "species", [BRYONY], SPECIES_COLS)
    if not args.apply:
        return
    snapshot()
    since = datetime.utcnow().isoformat(sep=" ")
    async with AsyncSessionLocal() as s:
        sp = await s.get(Species, BRYONY)
        _write_verdict(s, sp, "toxic", True, "toxic", note="Melvin 28 Oct", changed_by="human")
        await s.commit()
    async with AsyncSessionLocal() as s:
        print("READ-BACK")
        await show(s, "species", [BRYONY], SPECIES_COLS)
        await _hist(s, BRYONY, since)


async def step_warn879(args):
    async with AsyncSessionLocal() as s:
        ci = await s.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == BRYONY))
        print("culinary_info for 879:", ci.id if ci else "none — will be created")
        if ci:
            await show(s, "culinary_info", [ci.id], CI_COLS)
    if not args.apply:
        return
    snapshot()
    async with AsyncSessionLocal() as s:
        ci = await s.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == BRYONY))
        if ci is None:
            ci = CulinaryInfo(species_id=BRYONY)
            s.add(ci)
            await s.flush()
        for field, val in (("look_alike_warnings", LOOKALIKE_879), ("preparation_warnings", PREP_879)):
            old = getattr(ci, field) or None
            setattr(ci, field, val)
            s.add(CulinaryInfoHistory(culinary_info_id=ci.id, field_name=field, old_value=old, new_value=val,
                                      changed_by="human", notes="Melvin verbatim, 28 Oct 2026"))
        await s.commit()
        cid = ci.id
    async with AsyncSessionLocal() as s:
        print("READ-BACK")
        row = (await s.execute(text("SELECT * FROM culinary_info WHERE id = :c"), {"c": cid})).mappings().one()
        print("  culinary_info (every column):", dict(row))
        h = (await s.execute(text("SELECT id FROM culinary_info_history WHERE culinary_info_id = :c ORDER BY id"),
                             {"c": cid})).scalars().all()
        await show(s, "culinary_info_history", h)
        got = await s.scalar(select(CulinaryInfo).where(CulinaryInfo.id == cid))
        print("  look_alike_warnings verbatim:", got.look_alike_warnings == LOOKALIKE_879)
        print("  preparation_warnings verbatim:", got.preparation_warnings == PREP_879)


async def step_genus(args):
    from app.services.observation_service import _log_edit
    from app.services.species_link import set_observation_species
    cards = tuple(int(x) for x in args.cards.split(",")) if args.cards else GENUS_CARDS
    ids = ",".join(map(str, cards))
    async with AsyncSessionLocal() as s:
        q = lambda sql, **p: s.execute(text(sql), p)
        names = dict((await q(f"SELECT id, scientific_name FROM species WHERE id IN ({ids})")).all())
        print("cards:", names)
        await show(s, "species", cards, SPECIES_COLS)
        np = {f"n{i}": n for i, n in enumerate(names.values())}
        nin = ",".join(f":{k}" for k in np)
        oids = (await q(f"SELECT id FROM observations WHERE species_id IN ({ids}) OR species_primary IN ({nin}) "
                        f"OR species_suggested IN ({nin}) ORDER BY id", **np)).scalars().all()
        rejected = set((await q(f"SELECT id FROM observations WHERE id IN ({','.join(map(str, oids)) or 0}) "
                                "AND review_status = 'rejected'")).scalars().all())
        await show(s, "observations", oids, OBS_COLS)
        print("rejected (stay rejected, species_id NULL, suggestion cleared):", sorted(rejected) or "none")
        from app.services.taxonomy import normalize_taxon_key
        name_keys = {normalize_taxon_key(n) for n in names.values()}
        counts = {}
        for t in DELETE_ROWS + NULL_ROWS + ("culinary_info", "species_synonyms"):
            col = "canonical_species_id" if t == "species_synonyms" else "species_id"
            counts[t] = (await q(f"SELECT count(*) FROM {t} WHERE {col} IN ({ids})")).scalar()
        counts["species_lookalikes"] = (await q(f"SELECT count(*) FROM species_lookalikes WHERE species_id IN ({ids}) "
                                                f"OR lookalike_species_id IN ({ids})")).scalar()
        counts["species_resources"] = (await q(f"SELECT count(*) FROM species_resources WHERE species_name IN ({nin})", **np)).scalar()
        print("species-keyed rows:", counts)
        la = (await q(f"SELECT id, species_id, lookalike_species_id, lookalike_name FROM species_lookalikes "
                      f"WHERE lookalike_species_id IN ({ids})")).all() if counts["species_lookalikes"] else []
        print("look-alike rows naming a card as the look-alike (kept, link → NULL):", [tuple(r) for r in la] or "none")
        rec = (await q(f"SELECT id, species_id, title, status FROM species_recipes WHERE species_id IN ({ids})")).all()
        print("recipes that go:", [tuple(r) for r in rec] or "none")
        for p in (await q("SELECT id, public_species_json FROM experience_publications")).all():
            hit = [e.get("id") for e in json.loads(p[1] or "{}").get("species", []) if e.get("id") in cards]
            print(f"publication {p[0]} lists one: {hit or 'no'}")
        from app.services.species_merge import OVERRIDES_DIR as _od
        ov = [f.name for f in Path(_od).glob("*.json") if any(c in (json.loads(f.read_text()).get("hide_species_ids") or [])
                                                               for c in cards)] if Path(_od).is_dir() else []
        print("walk override files naming one:", ov or "none")
        wp = [wid for wid, j in (await q("SELECT id, waypoints_json FROM saved_walks")).all()
              if any(re.search(rf'"species_id"\s*:\s*{i}\b', j or "") for i in cards)]
        print("saved walks naming one in waypoints:", wp or "none")
    if not args.apply:
        return
    snapshot()
    since = datetime.utcnow().isoformat(sep=" ")
    async with AsyncSessionLocal() as s:
        q = lambda sql, **p: s.execute(text(sql), p)
        for oid in oids:
            obs = await s.get(Observation, oid)
            if oid in rejected:                 # stays rejected; step G NULLs species_id below
                if normalize_taxon_key(obs.species_suggested or "") in name_keys:
                    _log_edit(s, obs, "species_suggested", obs.species_suggested, None, "human")
                    obs.species_suggested = None
                continue
            genus = names.get(obs.species_id) or obs.species_primary or obs.species_suggested
            _log_edit(s, obs, "species_primary", obs.species_primary, None, "human")
            await set_observation_species(s, obs, None)      # species_primary + species_id → NULL
            if normalize_taxon_key(obs.species_suggested or "") in name_keys:
                _log_edit(s, obs, "species_suggested", obs.species_suggested, None, "human")
                obs.species_suggested = None
            _append_note(obs, f"{genus} — identify to species")
            _log_edit(s, obs, "review_status", obs.review_status, "needs_review", "human")
            obs.review_status = "needs_review"
            _log_edit(s, obs, "review_label", obs.review_label, "genus_reid", "human")
            obs.review_label = "genus_reid"
        await s.flush()
        live = (await q(f"SELECT species_id, count(*) FROM observations WHERE species_id IN ({ids}) GROUP BY 1")).all()
        if live:
            raise SystemExit(f"STOP: photos still on 880/881: {live}")
        # 11b step G route
        for t in NULL_ROWS:
            await q(f"UPDATE {t} SET species_id = NULL WHERE species_id IN ({ids})")
        await q(f"DELETE FROM culinary_info_history WHERE culinary_info_id IN (SELECT id FROM culinary_info WHERE species_id IN ({ids}))")
        await q(f"DELETE FROM culinary_info WHERE species_id IN ({ids})")
        await q(f"UPDATE species_recipes SET ai_draft_id = NULL WHERE species_id NOT IN ({ids}) AND ai_draft_id IN "
                f"(SELECT id FROM species_ai_drafts WHERE species_id IN ({ids}))")
        for t in DELETE_ROWS:
            await q(f"DELETE FROM {t} WHERE species_id IN ({ids})")
        await q(f"DELETE FROM species_lookalikes WHERE species_id IN ({ids})")
        await q(f"UPDATE species_lookalikes SET lookalike_species_id = NULL WHERE lookalike_species_id IN ({ids})")
        await q(f"DELETE FROM species_synonyms WHERE canonical_species_id IN ({ids})")
        await q(f"DELETE FROM species_resources WHERE species_name IN (SELECT scientific_name FROM species WHERE id IN ({ids}))")
        await q(f"DELETE FROM species WHERE id IN ({ids})")
        await s.commit()
    async with AsyncSessionLocal() as s:
        q = lambda sql, **p: s.execute(text(sql), p)
        print("READ-BACK")
        await show(s, "observations", oids, OBS_COLS)
        await _obs_edits(s, oids, since)
        print("  species rows left with these ids:", (await q(f"SELECT count(*) FROM species WHERE id IN ({ids})")).scalar())
        left = {}
        for t in DELETE_ROWS + NULL_ROWS + ("culinary_info", "species_lookalikes"):
            n = (await q(f"SELECT count(*) FROM {t} WHERE species_id IN ({ids})")).scalar()
            if n:
                left[t] = n
        for t, col in (("species_lookalikes", "lookalike_species_id"), ("species_synonyms", "canonical_species_id")):
            n = (await q(f"SELECT count(*) FROM {t} WHERE {col} IN ({ids})")).scalar()
            if n:
                left[f"{t}.{col}"] = n
        n = (await q(f"SELECT count(*) FROM species_resources WHERE species_name IN ({nin})", **np)).scalar()
        if n:
            left["species_resources"] = n
        print("  rows still keyed to a deleted card:", left or "none")


async def step_hide136(args):
    async with AsyncSessionLocal() as s:
        await show(s, "species", [SYRIACA], SPECIES_COLS)
        n = (await s.execute(text("SELECT count(*) FROM observations WHERE species_id = :i OR species_primary = "
                                  "'Bryonia syriaca' OR species_suggested = 'Bryonia syriaca'"), {"i": SYRIACA})).scalar()
        print("photos naming 136:", n)
    if not args.apply:
        return
    snapshot()
    async with AsyncSessionLocal() as s:
        sp = await s.get(Species, SYRIACA)
        if sp.orphaned_at is None:
            sp.orphaned_at = datetime.utcnow()
        await s.commit()
    async with AsyncSessionLocal() as s:
        print("READ-BACK")
        row = (await s.execute(text("SELECT * FROM species WHERE id = :i"), {"i": SYRIACA})).mappings().one()
        print("  species (every column):", dict(row))


STEPS = {"review8229": step_review8229, "verdict879": step_verdict879, "warn879": step_warn879,
         "genus": step_genus, "hide136": step_hide136}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=STEPS)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--cards", help="genus step: comma-separated card ids (default 880,881)")
    asyncio.run(STEPS[ap.parse_args().step](ap.parse_args()))
