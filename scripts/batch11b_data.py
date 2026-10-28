#!/usr/bin/env python3
"""
Audit batch 11b — data and taxonomy build (Melvin's decisions 27–28 Oct 2026,
DECISIONS_11b_2026-10-27.md).

Every step is a dry run unless --apply. With --apply it first takes a
WAL-consistent DB snapshot (snapshots/db_<ts>.sqlite, app/services/db_snapshot —
no git commit), writes in ONE transaction, commits, then re-reads every changed
row by id and prints it.

    PYTHONPATH=. python scripts/batch11b_data.py merge 704 457 [--apply]
    PYTHONPATH=. python scripts/batch11b_data.py <step> [--apply]

Steps: merge, relink, corrections, review, drafts, species, junk, taxonomy, names.
"""
import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from sqlalchemy import select, text  # noqa: E402

import app.main  # noqa: E402,F401  (registers every model)
from app.database import AsyncSessionLocal  # noqa: E402
from app.models.culinary import CulinaryInfo  # noqa: E402
from app.models.species import Species  # noqa: E402
from app.services.db_snapshot import backup_to_file  # noqa: E402

DB = PROJECT / "data" / "foragingid.db"
NOTE = "audit 11b, Melvin 27–28 Oct 2026"
TRUNC = 90


def snapshot() -> str:
    dest = PROJECT / "snapshots" / f"db_{datetime.now():%Y%m%d_%H%M%S}.sqlite"
    info = backup_to_file(DB, dest)
    print(f"snapshot {dest.name} ({info['bytes']:,} bytes, quick_check {info['quick_check']})")
    return dest.name


def _short(v):
    if isinstance(v, str) and len(v) > TRUNC:
        return v[:TRUNC] + f"…({len(v)})"
    return v


async def show(s, table, ids, cols="*"):
    """Print every row of `table` with these ids, every column."""
    ids = list(ids)
    if not ids:
        print(f"  {table}: —")
        return []
    rows = (await s.execute(text(f"SELECT {cols} FROM {table} WHERE id IN ({','.join(map(str, ids))}) ORDER BY id"))).mappings().all()
    print(f"  {table} ({len(rows)} of {len(ids)} ids):")
    for r in rows:
        print("    " + ", ".join(f"{k}={_short(v)!r}" for k, v in r.items()))
    return rows


# ── A. merges ───────────────────────────────────────────────────────────────
SPECIES_COLS = ("id, scientific_name, name_key, common_names, preferred_common_name, family, genus, kingdom, "
                "edibility_status, toxicity_severity, edibility_verified, edibility_verified_by, orphaned_at")


async def step_merge(args):
    from app.services.species_merge import merge_species_cards
    did, kid = args.ids
    async with AsyncSessionLocal() as s:
        for i in (did, kid):
            await show(s, "species", [i], SPECIES_COLS)
        counts = {}
        for t in ("species_candidates", "species_ai_drafts", "species_recipes", "species_edibility_history",
                  "species_edibility_conditions", "encounters", "sources", "enrichment_sources", "session_species",
                  "personal_list_species", "notification_dismissals", "culinary_info"):
            counts[t] = (await s.execute(text(f"SELECT count(*) FROM {t} WHERE species_id = :d"), {"d": did})).scalar()
        name = (await s.get(Species, did)).scientific_name
        counts["observations"] = (await s.execute(text(
            "SELECT count(*) FROM observations WHERE species_id = :d OR species_primary = :n"), {"d": did, "n": name})).scalar()
        counts["species_resources"] = (await s.execute(text(
            "SELECT count(*) FROM species_resources WHERE species_name = :n"), {"n": name})).scalar()
        print("would move:", {k: v for k, v in counts.items() if v})
    if not args.apply:
        return
    snapshot()
    async with AsyncSessionLocal() as s:
        rep = await merge_species_cards(s, did, kid, changed_by="merge", note=args.note or NOTE)
        await s.commit()
    print("report:", json.dumps({k: v for k, v in rep.items() if k != "moved"}, default=str))
    print("moved ids:", json.dumps({k: v for k, v in rep["moved"].items() if v}))
    # read-back by id
    async with AsyncSessionLocal() as s:
        print("READ-BACK")
        await show(s, "species", [kid], SPECIES_COLS)
        gone = (await s.execute(text("SELECT count(*) FROM species WHERE id = :d"), {"d": did})).scalar()
        print(f"  discard {did} rows in species: {gone}")
        mv = rep["moved"]
        await show(s, "observations", mv.get("observations", []),
                   "id, species_id, species_primary, species_suggested, review_status, identification_status")
        for t in ("species_candidates", "species_ai_drafts", "species_recipes", "species_edibility_history",
                  "species_edibility_conditions", "encounters", "sources", "enrichment_sources", "session_species",
                  "personal_list_species", "notification_dismissals", "species_lookalikes", "species_synonyms",
                  "species_resources", "map_notes", "culinary_info_history"):
            cols = "*"
            if t == "enrichment_sources":
                cols = "id, species_id, source_name, retrieved_at"
            if t == "species_ai_drafts":
                cols = "id, species_id, field_name, status"
            if t == "culinary_info_history":
                cols = "id, culinary_info_id, field_name, changed_by, changed_at, old_value, new_value, notes"
            await show(s, t, mv.get(t, []), cols)
        if rep.get("synonym_added"):
            await show(s, "species_synonyms", [rep["synonym_added"]])
        ci = await s.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == kid))
        await show(s, "culinary_info", [ci.id] if ci else [])
        new_hist = (await s.execute(text(
            "SELECT id FROM culinary_info_history WHERE culinary_info_id = :c AND (notes LIKE :n OR field_name = '_merge_event') "
            "ORDER BY id"), {"c": ci.id if ci else -1, "n": f"merge {did} %"})).scalars().all()
        await show(s, "culinary_info_history", new_hist,
                   "id, field_name, changed_by, old_value, new_value, notes")
        eh = (await s.execute(text("SELECT id FROM species_edibility_history WHERE species_id = :k AND field = '_merge_event'"),
                              {"k": kid})).scalars().all()
        await show(s, "species_edibility_history", eh)
        left = {}
        for t in ("observations", "species_candidates", "species_ai_drafts", "species_recipes", "species_edibility_history",
                  "species_edibility_conditions", "encounters", "sources", "enrichment_sources", "session_species",
                  "personal_list_species", "notification_dismissals", "culinary_info"):
            n = (await s.execute(text(f"SELECT count(*) FROM {t} WHERE species_id = :d"), {"d": did})).scalar()
            if n:
                left[t] = n
        n = (await s.execute(text("SELECT count(*) FROM species_lookalikes WHERE species_id = :d OR lookalike_species_id = :d"),
                             {"d": did})).scalar()
        if n:
            left["species_lookalikes"] = n
        n = (await s.execute(text("SELECT count(*) FROM species_resources WHERE species_name = :n"),
                             {"n": rep["discard_name"]})).scalar()
        if n:
            left["species_resources"] = n
        print("rows still keyed to the discard:", left or "none")
        pubs = (await s.execute(text("SELECT id, public_species_json FROM experience_publications"))).all()
        for pid, ps in pubs:
            ids = [e.get("id") for e in json.loads(ps or "{}").get("species", [])]
            print(f"  publication {pid}: holds {did}? {did in ids}; holds {kid}? {kid in ids}")


# ── shared: Melvin's corrections through the confirm-species helper ─────────
OBS_COLS = ("id, species_id, species_primary, species_suggested, review_status, identification_status, obs_category, "
            "review_label, human_corrected, reviewed_at, reviewer_notes")


async def human_correct(s, oid, name, why):
    """POST /api/observations/{id}/confirm-species, in-process: the shared
    update_observation_status helper (manually_verified, species set by hand,
    hazard second tap checked) + the same ProcessingLog row. A hazard_ack the
    gate asks for is given as Melvin's decision and recorded in the log row.
    The endpoint's background AI-draft trigger is NOT run (no enrichment here)."""
    from fastapi import HTTPException
    from app.models.observation import Observation
    from app.models.processing import ProcessingLog
    from app.services.observation_service import update_observation_status
    obs = await s.get(Observation, oid)
    ack = None
    for _ in range(2):
        try:
            await update_observation_status(session=s, obs=obs, review_status="manually_verified",
                                            species_name=name, update_species=True, edited_by="human",
                                            hazard_ack=ack)
            break
        except HTTPException as e:
            d = e.detail if isinstance(e.detail, dict) else {}
            if e.status_code != 409 or d.get("code") != "hazard_ack_required" or ack:
                raise
            ack = ",".join(h["scientific_name"] for h in d["hazards"])
            print(f"  obs {oid}: hazard second tap needed for {ack} — given as Melvin's decision")
    s.add(ProcessingLog(observation_id=oid, stage="manual_review", status="success",
                        message=(f"action=manual_entry triggered_by=user species={name} source=audit_11b "
                                 f"decision='{why}'" + (f" hazard_ack_by=Melvin hazard_ack={ack}" if ack else ""))))
    return ack


# ── B. relinks ──────────────────────────────────────────────────────────────
RELINK = {8410: "Lepista nuda", 21950: "Erigeron canadensis", 22074: "Erigeron canadensis"}
TO_PERFORATUM = (21556, 21740, 21805, 21819, 22069)


async def step_relink(args):
    from app.models.observation import Observation
    from app.services.observation_service import _log_edit
    from app.services.species_link import set_observation_species
    ids = list(RELINK) + list(TO_PERFORATUM)
    async with AsyncSessionLocal() as s:
        await show(s, "observations", ids, OBS_COLS)
    if not args.apply:
        return
    snapshot()
    async with AsyncSessionLocal() as s:
        for oid, name in RELINK.items():           # spelling only: species_id already on the current-name card
            obs = await s.get(Observation, oid)
            _log_edit(s, obs, "species_primary", obs.species_primary, name, "human")
            await set_observation_species(s, obs, name)
        for oid in TO_PERFORATUM:                   # Melvin 27 Oct: all 187 photos are H. perforatum
            await human_correct(s, oid, "Hypericum perforatum", "187 photos are H. perforatum (Melvin 27 Oct)")
        await s.commit()
    async with AsyncSessionLocal() as s:
        print("READ-BACK")
        await show(s, "observations", ids, OBS_COLS)
        await show(s, "species", [187, 229, 505, 342], SPECIES_COLS)


# ── D. Melvin's corrections ─────────────────────────────────────────────────
CORRECT = {8229: "Bryonia dioica", 19809: "Carpinus betulus", 24068: "Larix decidua", 24069: "Larix decidua",
           8408: "Populus tremula", 8263: "Parthenocissus quinquefolia", 17033: "Usnea", 17046: "Usnea",
           21713: "Oxalis stricta", 18828: "Dryopteris affinis", 24062: "Salix"}
SCENE = (18398,)


async def step_corrections(args):
    from app.api.edibility import _write_verdict
    from app.models.observation import Observation
    from app.models.species import new_species_card
    from app.services.observation_service import _log_edit, update_observation_status
    from app.services.species_link import set_observation_species
    ids = list(SCENE) + list(CORRECT)
    async with AsyncSessionLocal() as s:
        await show(s, "observations", ids, OBS_COLS)
        pq = await s.scalar(select(Species).where(Species.scientific_name == "Parthenocissus quinquefolia"))
        print("Parthenocissus quinquefolia card:", pq.id if pq else "none — will be created")
    if not args.apply:
        return
    snapshot()
    acks = {}
    async with AsyncSessionLocal() as s:
        # Parthenocissus first: card (new_species_card) + Melvin's verdict, so the
        # photo lands on a card that already carries it.
        pq = await s.scalar(select(Species).where(Species.scientific_name == "Parthenocissus quinquefolia"))
        if pq is None:
            pq = new_species_card("Parthenocissus quinquefolia", family="Vitaceae", genus="Parthenocissus",
                                  kingdom="Plantae")
            s.add(pq)
            await s.flush()
        _write_verdict(s, pq, "toxic", True, "toxic", note="Melvin 28 Oct 2026: \"I know it's poisonous\" (audit 11b)",
                       changed_by="human")
        for oid in SCENE:                            # scene: no organism to name (landscape)
            obs = await s.get(Observation, oid)
            _log_edit(s, obs, "obs_category", obs.obs_category, "landscape", "human")
            obs.obs_category = "landscape"
            if obs.species_primary:
                _log_edit(s, obs, "species_primary", obs.species_primary, None, "human")
            await set_observation_species(s, obs, None)
            obs.species_suggested = None
            await update_observation_status(session=s, obs=obs, review_status="manually_verified",
                                            edited_by="human")
        for oid, name in CORRECT.items():
            acks[oid] = await human_correct(s, oid, name, "Melvin 27–28 Oct, 11b decisions")
        await s.commit()
    async with AsyncSessionLocal() as s:
        print("READ-BACK")
        await show(s, "observations", ids, OBS_COLS)
        names = sorted(set(CORRECT.values()))
        sids = (await s.execute(select(Species.id).where(Species.scientific_name.in_(names)))).scalars().all()
        await show(s, "species", sids, SPECIES_COLS)
        eh = (await s.execute(text("SELECT id FROM species_edibility_history WHERE species_id = :p ORDER BY id"),
                              {"p": pq.id})).scalars().all()
        await show(s, "species_edibility_history", eh)
        print("hazard acks given:", {k: v for k, v in acks.items() if v} or "none")


# ── D. back to Review (label 11b_review) ────────────────────────────────────
REVIEW_LABEL = "11b_review"
# obs → suggestions (first one goes into species_suggested when Review can promote it)
TO_REVIEW = {
    # Melvin's suggestions (28 Oct)
    24084: ["Carlina acaulis"], 21252: ["Arctium"], 24348: ["Euphorbia dulcis"], 19780: ["Glechoma hederacea"],
    18937: ["Quercus robur", "Quercus petraea"], 17438: ["Pinus sylvestris", "Pinus nigra"],
    10577: ["Oenothera biennis"], 9465: ["Scorzoneroides autumnalis", "Leontodon hispidus"],
    9466: ["Scorzoneroides autumnalis", "Leontodon hispidus"],
    20684: ["Rhododendron ponticum"], 20685: ["Rhododendron ponticum"], 20688: ["Rhododendron ponticum"],
    # no suggestion (Melvin)
    9477: [], 20893: [], 8370: [],
    # AI-approved: the decisions file's European suggestion
    8300: ["Rubus idaeus"], 22085: ["Rubus idaeus"], 9432: ["Picea abies"], 10515: ["Philadelphus coronarius"],
    10560: ["Erigeron annuus"], 16738: ["Picea × lutzii"], 17789: ["Quercus rubra"], 21472: ["Quercus rubra"],
    19842: ["Viburnum opulus"], 19808: ["Ulmus × hollandica"], 19518: ["Fagus sylvatica"],
    20558: ["Tilia platyphyllos"], 21269: ["Chrysosplenium oppositifolium"],
}
MELVIN_SUGGESTED = {24084, 21252, 24348, 19780, 18937, 17438, 10577, 9465, 9466, 20684, 20685, 20688, 9477, 20893, 8370}


async def step_review(args):
    from app.models.observation import Observation
    from app.services.observation_service import _log_edit
    from app.services.species_link import promotable_suggestion, set_observation_species
    ids = sorted(TO_REVIEW)
    async with AsyncSessionLocal() as s:
        await show(s, "observations", ids, OBS_COLS)
    if not args.apply:
        return
    snapshot()
    plan = {}
    async with AsyncSessionLocal() as s:
        for oid in ids:
            obs = await s.get(Observation, oid)
            was = obs.species_primary
            sugg = TO_REVIEW[oid]
            who = "Melvin" if oid in MELVIN_SUGGESTED else "11b default (AI-approved photo)"
            _log_edit(s, obs, "species_primary", was, None, "human")
            await set_observation_species(s, obs, None)
            new_sug = None
            if sugg:
                obs.species_suggested = sugg[0]
                new_sug = await promotable_suggestion(s, obs)   # only a name Review can promote
            if obs.species_suggested != new_sug:
                obs.species_suggested = new_sug
            _log_edit(s, obs, "species_suggested", None, new_sug, "human")
            note = (f"11b (28 Oct): was {was} — no European range. "
                    + (f"Suggestion ({who}): {' or '.join(sugg)}." if sugg else "No suggestion (Melvin)."))
            old_notes = obs.reviewer_notes
            obs.reviewer_notes = (old_notes + "\n" + note) if old_notes else note
            _log_edit(s, obs, "reviewer_notes", old_notes, obs.reviewer_notes, "human")
            _log_edit(s, obs, "review_status", obs.review_status, "needs_review", "human")
            obs.review_status = "needs_review"
            _log_edit(s, obs, "review_label", obs.review_label, REVIEW_LABEL, "human")
            obs.review_label = REVIEW_LABEL
            plan[oid] = (was, new_sug)
        await s.commit()
    async with AsyncSessionLocal() as s:
        print("READ-BACK")
        await show(s, "observations", ids, OBS_COLS)
        print("species_suggested set (promotable) / note only:")
        for oid, (was, sug) in plan.items():
            print(f"  {oid}: was {was}; species_suggested={sug!r}; suggestions {TO_REVIEW[oid]}")


# ── E. G3-held drafts ───────────────────────────────────────────────────────
G3_HELD = (1657, 1660, 1729, 1869, 1871, 1931, 1933, 1968, 1970, 2141, 2143, 2180, 2193, 3112, 3143, 3160,
           3460, 3498, 3501, 3537, 3541, 3556, 3557)   # docs/audit/2026-10-22/draft_census/apply_plan.json


async def _live_card(s, sid) -> bool:
    return (await s.execute(text("SELECT count(*) FROM observations WHERE species_id = :i AND "
                                 "(review_status IS NULL OR review_status <> 'rejected')"), {"i": sid})).scalar() > 0


async def step_drafts(args):
    from app.models.species import SpeciesAIDraft
    from app.services.verdict_drafts import record_rejection_reason
    plan = {}
    async with AsyncSessionLocal() as s:
        for did in G3_HELD:
            d = await s.get(SpeciesAIDraft, did)
            sp = await s.get(Species, d.species_id)
            live = await _live_card(s, d.species_id)
            plan[did] = "release" if live else "reject"
            print(f"  draft {did} {d.field_name} [{d.status}] on {sp.id} {sp.scientific_name}: live photos={live} → {plan[did]}")
    if not args.apply:
        return
    snapshot()
    async with AsyncSessionLocal() as s:
        for did, act in plan.items():
            d = await s.get(SpeciesAIDraft, did)
            if act == "reject" and d.status == "pending":
                d.status = "rejected"
                record_rejection_reason(d, "11b: the photos moved off this non-European card (Melvin 27–28 Oct 2026)")
        await s.commit()
    async with AsyncSessionLocal() as s:
        print("READ-BACK")
        await show(s, "species_ai_drafts", G3_HELD, "id, species_id, field_name, status, approved_at, approved_by, "
                                                    "generation_context_json")
        print("released (stay pending, normal draft review):", [k for k, v in plan.items() if v == "release"])


# ── H. species items ────────────────────────────────────────────────────────
PASTINACA_PREP = ("Be careful when handling this plant, as the sap burns your skin in sunlight. Wear gloves, and if it "
                  "touches your skin, wash it straight away. And like all members of the carrot family, always ensure "
                  "your ID is 100% certain before consuming.")   # Melvin, verbatim (28 Oct 2026)


async def step_species(args):
    from app.api.edibility import _write_verdict
    from app.models.species import CulinaryInfoHistory, new_species_card
    async with AsyncSessionLocal() as s:
        pa = await s.scalar(select(Species).where(Species.scientific_name == "Pastinaca sativa"))
        rp = await s.get(Species, 877)
        print("Pastinaca sativa card:", pa.id if pa else "none — will be created")
        await show(s, "species", [877], SPECIES_COLS)
    if not args.apply:
        return
    snapshot()
    async with AsyncSessionLocal() as s:
        pa = await s.scalar(select(Species).where(Species.scientific_name == "Pastinaca sativa"))
        if pa is None:
            pa = new_species_card("Pastinaca sativa", family="Apiaceae", genus="Pastinaca", kingdom="Plantae")
            s.add(pa)
            await s.flush()
        _write_verdict(s, pa, "caution", True, "none", note="Melvin 28 Oct 2026 (audit 11b): caution, severity none",
                       changed_by="human")
        ci = await s.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == pa.id))
        if ci is None:
            ci = CulinaryInfo(species_id=pa.id)
            s.add(ci)
            await s.flush()
        old = ci.preparation_warnings or None
        ci.preparation_warnings = PASTINACA_PREP
        s.add(CulinaryInfoHistory(culinary_info_id=ci.id, field_name="preparation_warnings", old_value=old,
                                  new_value=PASTINACA_PREP, changed_by="human",
                                  notes="Melvin verbatim, 28 Oct 2026 (audit 11b)"))
        rp = await s.get(Species, 877)
        _write_verdict(s, rp, "edible", True, "none", note="Melvin 27 Oct 2026 (audit 11b)", changed_by="human")
        await s.commit()
        pid, cid = pa.id, ci.id
    async with AsyncSessionLocal() as s:
        print("READ-BACK")
        await show(s, "species", [pid, 877], SPECIES_COLS)
        await show(s, "culinary_info", [cid], "id, species_id, preparation_warnings, look_alike_warnings")
        h = (await s.execute(text("SELECT id FROM culinary_info_history WHERE culinary_info_id = :c"), {"c": cid})).scalars().all()
        await show(s, "culinary_info_history", h)
        eh = (await s.execute(text("SELECT id FROM species_edibility_history WHERE species_id IN (:a, 877) "
                                   "AND changed_at > datetime('now', '-1 hour') ORDER BY id"), {"a": pid})).scalars().all()
        await show(s, "species_edibility_history", eh)
        from app.services.hazard_candidates import load_hazard_index
        from app.services.taxonomy import normalize_taxon_key
        idx = await load_hazard_index(s)
        print("Pastinaca in hazard index:", normalize_taxon_key("Pastinaca sativa") in idx.by_key)


# ── G. junk cards ───────────────────────────────────────────────────────────
# Cards with no live photo after A, B and D, tiered as in DECISIONS_11b (G1 not a
# plant/fungus species, G2 no native European range): the 57 default deletes,
# 685, and every card left without a live photo (62, 187, …). Kept: toxic/deadly
# cards (hazard index), native European reference cards (G3), 653.
JUNK_DELETE = (1, 4, 5, 26, 62, 108, 145, 146, 147, 150, 151, 152, 153, 167, 187, 192, 203, 245, 250, 253, 272, 279,
               282, 367, 370, 388, 394, 400, 411, 414, 421, 423, 426, 436, 440, 444, 449, 454, 460, 462, 466, 469, 470,
               471, 472, 473, 479, 481, 498, 504, 508, 538, 546, 548, 550, 552, 553, 569, 570, 572, 573, 579, 584,
               598, 631, 671, 685, 691, 695, 707, 751, 752, 753, 755, 760, 766, 772, 775, 776, 784, 791, 803, 807,
               824, 833, 835, 846)
KEEP_HIDDEN = (148, 583, 740, 808, 826)   # Melvin 28 Oct: keep, orphan-marked (off the Species list)
# Species-keyed rows: deleted with the card / kept with species_id NULL (records of photos or people).
# recipes before drafts: species_recipes.ai_draft_id references species_ai_drafts
DELETE_ROWS = ("species_recipes", "species_ai_drafts", "species_edibility_history", "species_edibility_conditions",
               "sources", "enrichment_sources", "session_species", "personal_list_species", "notification_dismissals")
NULL_ROWS = ("observations", "species_candidates", "encounters")


async def step_junk(args):
    from app.models.observation import Observation
    from app.services.observation_service import _log_edit
    async with AsyncSessionLocal() as s:
        q = lambda sql, **p: s.execute(text(sql), p)
        ids = ",".join(map(str, JUNK_DELETE))
        live = (await q(f"SELECT species_id, count(*) FROM observations WHERE species_id IN ({ids}) AND "
                        "(review_status IS NULL OR review_status <> 'rejected') GROUP BY 1")).all()
        if live:
            raise SystemExit(f"STOP: cards on the delete list still have live photos: {live}")
        names = dict((await q(f"SELECT id, scientific_name FROM species WHERE id IN ({ids})")).all())
        stale = (await q("SELECT id, species_suggested, review_status, species_primary FROM observations WHERE species_suggested IN "
                         f"({','.join(':n%d' % i for i in range(len(names)))}) AND (review_status IS NULL OR review_status <> 'rejected')",
                         **{f"n{i}": n for i, n in enumerate(names.values())})).all()
        bad = [r for r in stale if r[2] not in ("approved", "manually_verified") or not r[3]]
        if bad:
            raise SystemExit(f"STOP: a pending photo suggests a card on the delete list: {bad}")
        counts = {}
        for t in DELETE_ROWS + NULL_ROWS + ("culinary_info", "species_synonyms"):
            col = "canonical_species_id" if t == "species_synonyms" else "species_id"
            counts[t] = (await q(f"SELECT count(*) FROM {t} WHERE {col} IN ({ids})")).scalar()
        counts["culinary_info_history"] = (await q(
            f"SELECT count(*) FROM culinary_info_history WHERE culinary_info_id IN (SELECT id FROM culinary_info WHERE species_id IN ({ids}))")).scalar()
        counts["species_lookalikes (card's own)"] = (await q(f"SELECT count(*) FROM species_lookalikes WHERE species_id IN ({ids})")).scalar()
        counts["species_lookalikes (as lookalike → NULL)"] = (await q(
            f"SELECT count(*) FROM species_lookalikes WHERE lookalike_species_id IN ({ids}) AND species_id NOT IN ({ids})")).scalar()
        counts["species_resources"] = (await q(
            f"SELECT count(*) FROM species_resources WHERE species_name IN (SELECT scientific_name FROM species WHERE id IN ({ids}))")).scalar()
        print(f"cards to delete: {len(JUNK_DELETE)}; stale suggestions to clear on confirmed photos: "
              f"{[(r[0], r[1]) for r in stale]}")
        print("species-keyed rows:", counts)
        recipes = (await q(f"SELECT id, species_id, title, status FROM species_recipes WHERE species_id IN ({ids})")).all()
        print("recipes that go:", [tuple(r) for r in recipes])
        for p in (await q("SELECT id, public_species_json FROM experience_publications")).all():
            hit = [e.get("id") for e in json.loads(p[1] or "{}").get("species", []) if e.get("id") in JUNK_DELETE]
            print(f"publication {p[0]} lists a card to delete: {hit or 'no'}")
        import re
        wp = [wid for wid, j in (await q("SELECT id, waypoints_json FROM saved_walks")).all()
              if any(re.search(rf'"species_id"\s*:\s*{i}\b', j or "") for i in JUNK_DELETE)]
        print("saved walks naming one in waypoints:", wp or "none")
        await show(s, "species", KEEP_HIDDEN, SPECIES_COLS)
    if not args.apply:
        return
    snapshot()
    async with AsyncSessionLocal() as s:
        q = lambda sql, **p: s.execute(text(sql), p)
        for oid, sug, _st, _prim in stale:     # a stale suggestion on a confirmed photo
            obs = await s.get(Observation, oid)
            _log_edit(s, obs, "species_suggested", obs.species_suggested, None, "human")
            obs.species_suggested = None
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
        now = datetime.utcnow()
        for sid in KEEP_HIDDEN:                 # kept, off the Species list
            sp = await s.get(Species, sid)
            if sp.orphaned_at is None:
                sp.orphaned_at = now
        await s.commit()
    async with AsyncSessionLocal() as s:
        q = lambda sql, **p: s.execute(text(sql), p)
        print("READ-BACK")
        print("  species rows left with these ids:", (await q(f"SELECT count(*) FROM species WHERE id IN ({ids})")).scalar())
        left = {}
        for t in DELETE_ROWS + NULL_ROWS + ("culinary_info", "species_lookalikes"):
            n = (await q(f"SELECT count(*) FROM {t} WHERE species_id IN ({ids})")).scalar()
            if n:
                left[t] = n
        n = (await q(f"SELECT count(*) FROM species_lookalikes WHERE lookalike_species_id IN ({ids})")).scalar()
        if n:
            left["species_lookalikes.lookalike_species_id"] = n
        n = (await q(f"SELECT count(*) FROM species_synonyms WHERE canonical_species_id IN ({ids})")).scalar()
        if n:
            left["species_synonyms"] = n
        print("  rows still keyed to a deleted card:", left or "none")
        await show(s, "observations", [r[0] for r in stale], OBS_COLS)
        await show(s, "species", KEEP_HIDDEN, SPECIES_COLS)


# ── C. genus / family to GBIF ───────────────────────────────────────────────
KINGDOM_KEEP = {332}   # Physarum stays Fungi (Melvin)


async def _gbif_lineage(client, name, kingdom):
    """GBIF backbone family/genus/kingdom for a card name: the accepted taxon's
    family; the match's kingdom. HIGHERRANK matches still give family/kingdom."""
    p = {"name": name, "strict": "false"}
    if kingdom in ("Plantae", "Fungi"):
        p["kingdom"] = kingdom
    m = (await client.get("https://api.gbif.org/v1/species/match", params=p)).json()
    if m.get("matchType") in (None, "NONE") and "kingdom" not in p:   # homonyms (e.g. Salix): try plant, then fungus
        for k in ("Plantae", "Fungi"):
            m = (await client.get("https://api.gbif.org/v1/species/match", params={**p, "kingdom": k})).json()
            if m.get("matchType") == "EXACT":
                break
    if m.get("matchType") in (None, "NONE"):
        return None
    fam = m.get("family")
    if m.get("acceptedUsageKey"):
        a = (await client.get(f"https://api.gbif.org/v1/species/{m['acceptedUsageKey']}")).json()
        fam = a.get("family") or fam
    return {"family": fam, "kingdom": m.get("kingdom"), "match": m.get("matchType"), "status": m.get("status")}


async def step_taxonomy(args):
    import httpx
    from app.models.species import SpeciesEdibilityHistory
    async with AsyncSessionLocal() as s:
        cards = (await s.execute(select(Species))).scalars().all()
        plan = {}   # every card whose family/genus disagrees with GBIF / its own name, or has no kingdom
        async with httpx.AsyncClient(timeout=30) as client:
            for sp in cards:
                g = await _gbif_lineage(client, sp.scientific_name, sp.kingdom)
                if g is None:
                    continue
                name = sp.scientific_name
                ng = name.split()[0] if name[:1].isupper() else None
                new = {"family": g["family"] or sp.family, "genus": ng or sp.genus,
                       "kingdom": sp.kingdom or (g["kingdom"] if sp.id not in KINGDOM_KEEP else sp.kingdom)}
                ch = {k: (getattr(sp, k), v) for k, v in new.items() if v and getattr(sp, k) != v}
                if ch:
                    plan[sp.id] = (sp.scientific_name, ch)
        print(f"{len(plan)} cards change (of {len(cards)}):")
        for sid, (n, ch) in sorted(plan.items()):
            print(f"  {sid} {n}: " + "; ".join(f"{k} {a!r} → {b!r}" for k, (a, b) in ch.items()))
    if not args.apply:
        return
    snapshot()
    async with AsyncSessionLocal() as s:
        for sid, (n, ch) in plan.items():
            sp = await s.get(Species, sid)
            for k, (old, newv) in ch.items():
                setattr(sp, k, newv)
                s.add(SpeciesEdibilityHistory(species_id=sid, field=k, old_value=old, new_value=newv, changed_by="human",
                                              note="11b genus/family sweep to GBIF (Melvin 27–28 Oct 2026)"))
        await s.commit()
    async with AsyncSessionLocal() as s:
        print("READ-BACK")
        await show(s, "species", sorted(plan), "id, scientific_name, family, genus, kingdom")
        bad = []
        for sid, (n, ch) in plan.items():
            sp = await s.get(Species, sid)
            if any(getattr(sp, k) != v for k, (_o, v) in ch.items()):
                bad.append(sid)
        print("rows not matching the plan:", bad or "none")


# ── F. English names ────────────────────────────────────────────────────────
ENGLISH = {292: "Liberty cap", 349: "Orpine", 493: "Scurfy twiglet", 507: "Goldleaf Shield", 539: "Oyster Mushroom",
           540: "Heath Navel", 541: "Woolly Milkcap", 542: "Buckthorn", 585: "Dyer's greenweed",
           592: "Broadtooth lady's mantle", 593: "Narrow-leaved sorrel", 594: "Garden thyme", 606: "Carthusian pink",
           607: "Narrow-leaved ash", 626: "common hawkweed", 632: "Siberian Spruce", 633: "Black poplar",
           652: "Villar's chervil", 668: "Alpine oxeye daisy", 669: "Sheep's-bit", 670: "Angular Solomon's-seal",
           684: "White water-lily", 686: "white rhododendron", 705: "Black Stone Flower", 706: "Larch bolete",
           710: "Apple Rose", 711: "Fairy ring champignon", 724: "Hawk's-beard", 746: "Intermediate Evening-Primrose",
           747: "Fringed water-lily", 821: "Slender Parasol", 840: "Brown rollrim", 841: "Upright Coral",
           847: "lesser calamint", 850: "Small-leaved Gentian", 851: "Sycamore tar spot", 854: "Deer-colored Trametes",
           862: "Ochre Bracket", 866: "Trooping Funnel", 867: "Weeping willow", 868: "Peppery Bolete",
           869: "Brook Thistle", 870: "fen violet"}   # DECISIONS_11b group F, cards still present


async def step_names(args):
    from app.models.species import SpeciesEdibilityHistory, display_common_name
    async with AsyncSessionLocal() as s:
        plan = {}
        for sid, nm in ENGLISH.items():
            sp = await s.get(Species, sid)
            if sp is None:
                print(f"  {sid}: card gone — skipped")
                continue
            if display_common_name(sp.preferred_common_name, sp.common_names):
                print(f"  {sid} {sp.scientific_name}: already has an English name — skipped")
                continue
            plan[sid] = nm
        print(f"{len(plan)} cards get a name")
    if not args.apply:
        return
    snapshot()
    async with AsyncSessionLocal() as s:
        for sid, nm in plan.items():
            sp = await s.get(Species, sid)
            for f, v in (("common_names", json.dumps([nm])), ("preferred_common_name", nm)):
                s.add(SpeciesEdibilityHistory(species_id=sid, field=f, old_value=getattr(sp, f), new_value=v,
                                              changed_by="human", note="11b English name from GBIF vernacular "
                                                                       "(Melvin 27–28 Oct 2026)"))
                setattr(sp, f, v)
        await s.commit()
    async with AsyncSessionLocal() as s:
        print("READ-BACK")
        await show(s, "species", sorted(plan), "id, scientific_name, common_names, preferred_common_name")


STEPS = {"merge": step_merge, "relink": step_relink, "corrections": step_corrections, "review": step_review,
         "drafts": step_drafts, "species": step_species, "junk": step_junk, "taxonomy": step_taxonomy,
         "names": step_names}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=sorted(STEPS))
    ap.add_argument("ids", nargs="*", type=int)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--note", help="merge: note for the history rows (default: the 11b note)")
    args = ap.parse_args()
    asyncio.run(STEPS[args.step](args))


if __name__ == "__main__":
    main()
