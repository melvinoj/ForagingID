"""
Tests for hazard candidates (Melvin, 22 Oct 2026 — foxglove #24507: Review
proposed Pentanema squarrosum at 90.4% with Digitalis purpurea only in the grey
"Also:" line).

  * One predicate (app/services/hazard_candidates.py): a candidate from any
    source, any rank — including one present ONLY in a raw list — resolving
    (name_key / synonym) to a species that is_hazard_species() is a hazard.
  * It blocks auto-approve at any rank (decide_agreement +
    scan._identify_scanned end to end).
  * Tiers (Melvin, 22 Oct 2026 evening): GATE = top 3 of any source or >= 5%
    in any source — red ☠ line on the card (rendered from review.html's own
    _makeCardHtml), Review's "Hazard candidates" status filter, and approving
    as any other species needs hazard_ack naming it (single approve,
    confirm-species, bulk approve skips it). DEEP = lower: one grey "Also
    listed deep in …" line, no gate.
  * A human decision stands: a manually_verified / human-approved photo gets
    no red line and no gate. Review's Critical block no longer lists hazard
    candidates.
  * Card fixes: the confidence chip states the band of the % shown; the ITIS
    "no match" banner is amber "may be a newer name" when GBIF matched the name
    exactly, red otherwise.

No external calls; throw-away SQLite DBs; JS run in JavaScriptCore.

Run from project root:  python -m pytest tests/test_hazard_candidates.py -v
"""
import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import HTTPException  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main  # noqa: E402,F401  (registers every model on Base.metadata)
import app.api.bulk_actions as bulk_actions  # noqa: E402
import app.api.experience as experience  # noqa: E402
import app.api.observations as observations  # noqa: E402
import app.api.reidentify as reidentify  # noqa: E402
import app.api.scan as scan  # noqa: E402
import app.services.enrichment as enrichment  # noqa: E402
import app.services.observation_service as obs_service  # noqa: E402
from app.database import Base  # noqa: E402
from app.integrations.plantnet import PlantNetCandidate, PlantNetResult  # noqa: E402
from app.models.observation import Observation  # noqa: E402
from app.models.species import Species, SpeciesSynonym  # noqa: E402
from app.services.agreement import decide_agreement  # noqa: E402
from app.services.hazard_candidates import (deep_hazards, gating_hazards,  # noqa: E402
                                            hazard_hits, inat_hit_entries,
                                            load_hazard_index, observation_hazards,
                                            plantnet_raw_entries, undecided_hazard_items)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"

obs_service._copy_to_confirmed = lambda obs: None
bulk_actions._copy_to_confirmed = lambda obs: None


async def _noop(*a, **k):
    return None
enrichment.trigger_ai_drafts_for_species = _noop
bulk_actions.bp_progress = _noop
bulk_actions.bp_finish = _noop

# id, name, severity, verdict
FOXGLOVE = (376, "Digitalis purpurea", "deadly", "toxic")
BEECH = (10, "Fagus sylvatica", "none", "edible")
PENTANEMA = (858, "Pentanema squarrosum", "unknown", "unknown")
IVY = (20, "Hedera helix", "none", "toxic")              # verdict toxic, severity none
NETTLE = (30, "Urtica dioica", "none", "edible")
HEMLOCK = (40, "Conium maculatum", "deadly", "toxic")
HOGWEED = (41, "Heracleum sphondylium", "none", "edible")


def _run(coro):
    return asyncio.run(coro)


def _pn_raw(names_scores):
    return {"results": [{"score": s, "species": {"scientificNameWithoutAuthor": n}}
                        for n, s in names_scores]}


async def _db(extra_obs=()):
    path = os.path.join(tempfile.mkdtemp(prefix="hazard_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    S = async_sessionmaker(eng, expire_on_commit=False)
    async with S() as s:
        for sid, name, sev, verdict in (FOXGLOVE, BEECH, PENTANEMA, IVY, NETTLE, HEMLOCK, HOGWEED):
            s.add(Species(id=sid, scientific_name=name, name_key=name.lower(), kingdom="Plantae",
                          toxicity_severity=sev, edibility_status=verdict,
                          preferred_common_name={376: "Foxglove", 20: "Ivy"}.get(sid)))
        await s.flush()
        s.add(SpeciesSynonym(synonym_name_key="digitalis purpurea subsp. purpurea",
                             synonym_scientific_name="Digitalis purpurea subsp. purpurea",
                             canonical_species_id=FOXGLOVE[0]))
        for kw in extra_obs:
            s.add(Observation(**kw))
        await s.commit()
    return path, eng, S


def _obs(oid, name, sid, status="needs_review", pn=(), cands=(), **kw):
    base = dict(id=oid, file_path=f"/nonexistent/hz_{oid}.jpg", file_hash=f"h{oid}",
                species_primary=name, species_id=sid, review_status=status,
                identification_status="identified", obs_category="plant",
                upload_source="syncthing", latitude=47.7, longitude=7.9,
                plantnet_raw_json=json.dumps(_pn_raw(pn)),
                species_candidates_json=json.dumps([{"scientific_name": n, "score": s,
                                                     "source": "plantnet"} for n, s in cands]))
    base.update(kw)
    return base


# ── the predicate ─────────────────────────────────────────────────────────────

def test_deadly_candidate_at_any_rank_and_only_in_a_raw_list_is_a_hazard():
    async def run():
        path, eng, S = await _db()
        async with S() as s:
            idx = await load_hazard_index(s)
        await eng.dispose()
        raw = [(f"Harmless {i}", 0.01) for i in range(27)] + [("Digitalis purpurea", 0.0047)]
        hits = hazard_hits(plantnet_raw_entries(_pn_raw([("Fagus sylvatica", 0.95)] + raw)), idx)
        none = hazard_hits(plantnet_raw_entries(_pn_raw([("Fagus sylvatica", 0.95), ("Urtica dioica", 0.02)]))
                           + inat_hit_entries([("Fagus sylvatica", 0.9)]), idx)
        syn = hazard_hits(inat_hit_entries([("Fagus sylvatica", 0.9),
                                            ("Digitalis purpurea subsp. purpurea", 0.001)]), idx)
        verdict_only = hazard_hits(inat_hit_entries([("Hedera helix", 0.002)]), idx)
        return hits, none, syn, verdict_only

    hits, none, syn, verdict_only = _run(run())
    assert [h["scientific_name"] for h in hits] == ["Digitalis purpurea"]
    assert hits[0]["level"] == "deadly" and hits[0]["label"] == "Foxglove (Digitalis purpurea)"
    assert hits[0]["sources"] == [{"source": "plantnet", "name": "Digitalis purpurea",
                                   "score": 0.0047, "rank": 29}]
    assert none == []
    assert [h["scientific_name"] for h in syn] == ["Digitalis purpurea"]     # synonym resolves
    assert verdict_only[0]["level"] == "toxic"                               # verdict toxic counts


def test_agreement_refuses_auto_approve_on_hazard():
    pn = [PlantNetCandidate(scientific_name="Fagus sylvatica", common_names=[], score=0.95,
                            family=None, genus=None, gbif_id=None, rank=1, raw_rank=1)]
    kw = dict(demote_for_approve=False, force_review=False, use_pn=True, use_inat=True, threshold=0.7)
    assert decide_agreement(pn, [("Fagus sylvatica", 0.9)], **kw).dual_agree is True
    assert decide_agreement(pn, [("Fagus sylvatica", 0.9)], hazard=True, **kw).dual_agree is False


# ── end to end: scan._identify_scanned ───────────────────────────────────────

class _Hit:
    def __init__(self, name, score):
        self.scientific_name, self.score, self.iconic_taxon_name = name, score, "Plantae"
        self.common_name, self.common_names, self.taxon_id, self.rank = None, [], None, "species"
        self.vision_score, self.geo_score = score, score


def _identify(pn_raw_list):
    """Both APIs name Fagus sylvatica at ≥ 0.9 (a dual-agree auto-approve). The
    PlantNet candidates list holds Fagus only; pn_raw_list is the raw response."""
    async def run():
        d = tempfile.mkdtemp(prefix="hzscan_")
        img = os.path.join(d, "x.jpg")
        open(img, "wb").write(b"\xff\xd8\xff")
        path, eng, S = await _db(extra_obs=[dict(
            id=50, file_path=img, file_hash="h50", review_status="pending",
            identification_status="pending_identification", obs_category="plant",
            upload_source="syncthing", latitude=47.7, longitude=7.9)])
        import app.integrations.inaturalist as inat
        import app.integrations.plantnet as plantnet
        import app.services.id_ratelimit as rl
        import app.services.enrich_gate as gate
        import app.api.itis as itis
        saved = (scan.AsyncSessionLocal, scan.settings.plantnet_api_key, scan.settings.inaturalist_api_token,
                 inat.score_image, inat.last_inat_status, plantnet.identify_image, rl.INAT_DELAY_S,
                 gate.queue_card_enrichment, itis.trigger_itis_for_new_species)

        async def _score(*a, **k):
            return [_Hit("Fagus sylvatica", 0.92)]

        async def _pn(*a, **k):
            return PlantNetResult(best_match="Fagus sylvatica", raw_response=_pn_raw(pn_raw_list), candidates=[
                PlantNetCandidate(scientific_name="Fagus sylvatica", common_names=[], score=0.95,
                                  family=None, genus=None, gbif_id=None, rank=1, raw_rank=1)])
        scan.AsyncSessionLocal = S
        scan.settings.plantnet_api_key, scan.settings.inaturalist_api_token = "key", "tok"
        inat.score_image, inat.last_inat_status = _score, (lambda: {"state": "ok"})
        plantnet.identify_image = _pn
        rl.INAT_DELAY_S = 0
        gate.queue_card_enrichment = lambda name: None
        itis.trigger_itis_for_new_species = _noop
        try:
            await scan._identify_scanned(50)
            async with S() as s:
                o = await s.get(Observation, 50)
                crit = await undecided_hazard_items(s)
                out = (o.review_status, o.review_label, [i["obs_id"] for i in crit])
        finally:
            (scan.AsyncSessionLocal, scan.settings.plantnet_api_key, scan.settings.inaturalist_api_token,
             inat.score_image, inat.last_inat_status, plantnet.identify_image, rl.INAT_DELAY_S,
             gate.queue_card_enrichment, itis.trigger_itis_for_new_species) = saved
            await eng.dispose()
        return out
    return _run(run())


def test_harmless_lists_still_auto_approve():
    status, label, crit = _identify([("Fagus sylvatica", 0.95), ("Urtica dioica", 0.01)])
    assert status == "approved" and crit == []


def test_deep_deadly_candidate_still_blocks_auto_approve_but_does_not_gate():
    # Auto-approve stays blocked at ANY rank; rank 12 at 0.05% is DEEP, so the
    # card is not in the "Hazard candidates" filter (no red line, no gate).
    status, label, crit = _identify([("Fagus sylvatica", 0.95)]
                                    + [(f"Harmless {i}", 0.001) for i in range(10)]
                                    + [("Digitalis purpurea", 0.0005)])
    assert status == "needs_review"
    assert label == "hazard_candidate"
    assert crit == []


def test_gate_tier_candidate_blocks_auto_approve_and_is_listed():
    status, label, crit = _identify([("Fagus sylvatica", 0.95), ("Digitalis purpurea", 0.0005)])
    assert status == "needs_review" and label == "hazard_candidate" and crit == [50]


# ── tiers ─────────────────────────────────────────────────────────────────────

def _idx():
    async def run():
        path, eng, S = await _db()
        async with S() as s:
            idx = await load_hazard_index(s)
        await eng.dispose()
        return idx
    return _run(run())


def test_tier_foxglove_inat_second_gates_hemlock_deep_in_hogweed_does_not():
    idx = _idx()
    # #24507: iNat listed foxglove #2 (low score) — gates by rank.
    fox = hazard_hits(plantnet_raw_entries(_pn_raw([("Pentanema squarrosum", 0.904)]))
                      + inat_hit_entries([("Pentanema squarrosum", 0.317), ("Digitalis purpurea", 0.012)]), idx)
    assert [(h["scientific_name"], h["gate"]) for h in fox] == [("Digitalis purpurea", True)]
    # A hogweed with hemlock at 0.1%, rank 8: DEEP, no gate.
    hog = hazard_hits(plantnet_raw_entries(_pn_raw(
        [("Heracleum sphondylium", 0.88)] + [(f"Harmless {i}", 0.01) for i in range(6)]
        + [("Conium maculatum", 0.001)])), idx)
    assert [(h["scientific_name"], h["gate"], h["sources"][0]["rank"]) for h in hog] == \
        [("Conium maculatum", False, 8)]
    # >= 5% gates at any rank; just under 5% at rank 4 does not.
    pct = hazard_hits(plantnet_raw_entries(_pn_raw(
        [("Heracleum sphondylium", 0.5)] + [(f"Harmless {i}", 0.06) for i in range(5)]
        + [("Conium maculatum", 0.05)])), idx)
    assert pct[0]["gate"] is True
    under = hazard_hits(plantnet_raw_entries(_pn_raw(
        [("Heracleum sphondylium", 0.5)] + [(f"Harmless {i}", 0.06) for i in range(3)]
        + [("Conium maculatum", 0.049)])), idx)
    assert under[0]["gate"] is False
    # Top 3 in ONE source gates even when another source lists it deep.
    mixed = hazard_hits(plantnet_raw_entries(_pn_raw(
        [("Heracleum sphondylium", 0.9)] + [(f"Harmless {i}", 0.01) for i in range(9)]
        + [("Conium maculatum", 0.001)]))
        + inat_hit_entries([("Heracleum sphondylium", 0.7), ("Conium maculatum", 0.01)]), idx)
    assert mixed[0]["gate"] is True


def test_deep_hazard_needs_no_second_tap():
    async def run():
        path, eng, S = await _db(extra_obs=[
            _obs(70, "Heracleum sphondylium", HOGWEED[0],
                 pn=[("Heracleum sphondylium", 0.88)] + [(f"Harmless {i}", 0.01) for i in range(6)]
                 + [("Conium maculatum", 0.001)],
                 cands=[("Heracleum sphondylium", 0.88)])])
        async with S() as s:
            idx = await load_hazard_index(s)
            o = await s.get(Observation, 70)
            tiers = ([h["scientific_name"] for h in gating_hazards(o, idx)],
                     [h["scientific_name"] for h in deep_hazards(o, idx)])
            await observations.update_review(70, _BG(), status="approved", db=s)
        async with S() as s:
            st = (await s.get(Observation, 70)).review_status
        await eng.dispose()
        return tiers, st
    tiers, st = _run(run())
    assert tiers == ([], ["Conium maculatum"])
    assert st == "approved"


# ── a human decision stands ───────────────────────────────────────────────────

def test_human_decided_photo_gets_no_red_line_and_no_gate():
    from datetime import datetime
    fox_pn = [("Pentanema squarrosum", 0.904), ("Digitalis purpurea", 0.2)]

    async def run():
        path, eng, S = await _db(extra_obs=[
            _obs(80, "Pentanema squarrosum", PENTANEMA[0], status="manually_verified", pn=fox_pn,
                 reviewed_at=datetime(2026, 6, 1)),
            _obs(81, "Pentanema squarrosum", PENTANEMA[0], status="approved", pn=fox_pn,
                 reviewed_at=datetime(2026, 6, 1)),                   # human-approved
            _obs(82, "Pentanema squarrosum", PENTANEMA[0], status="approved", pn=fox_pn),  # AI-approved
            _obs(83, "Pentanema squarrosum", PENTANEMA[0], status="needs_review", pn=fox_pn),
        ])
        res = {}
        async with S() as s:
            idx = await load_hazard_index(s)
            for oid in (80, 81, 82, 83):
                o = await s.get(Observation, oid)
                res[oid] = (len(gating_hazards(o, idx)), len(deep_hazards(o, idx)))
            res["filter"] = sorted(i["obs_id"] for i in await undecided_hazard_items(s))
            # Re-confirm / correct a human-decided photo: no second tap asked.
            await reidentify.confirm_species(80, _BG(), reidentify.ConfirmSpeciesRequest(
                scientific_name="Fagus sylvatica"), db=s)
        async with S() as s:
            await observations.update_review(81, _BG(), status="manually_verified", db=s)
        async with S() as s:
            res["80"] = (await s.get(Observation, 80)).species_primary
            res["81"] = (await s.get(Observation, 81)).review_status
            try:
                await observations.update_review(82, _BG(), status="manually_verified", db=s)
                res["82"] = "no gate"
            except HTTPException as e:
                res["82"] = e.status_code
        await eng.dispose()
        return res

    r = _run(run())
    assert r[80] == (0, 0) and r[81] == (0, 0)          # decided: nothing shown
    assert r[82] == (1, 0) and r[83] == (1, 0)          # undecided (incl. AI-approved): gated
    assert r["filter"] == [82, 83]
    assert r["80"] == "Fagus sylvatica" and r["81"] == "manually_verified"
    assert r["82"] == 409                               # AI-approved is still undecided


# ── Review: status filter, Critical block ────────────────────────────────────

def test_status_filter_lists_only_gated_undecided_cards():
    async def run():
        path, eng, S = await _db(extra_obs=[
            _obs(90, "Pentanema squarrosum", PENTANEMA[0], pn=[("Pentanema squarrosum", 0.9),
                                                               ("Digitalis purpurea", 0.01)]),
            _obs(91, "Heracleum sphondylium", HOGWEED[0],
                 pn=[("Heracleum sphondylium", 0.88)] + [(f"Harmless {i}", 0.01) for i in range(6)]
                 + [("Conium maculatum", 0.001)]),
            _obs(92, "Fagus sylvatica", BEECH[0], pn=[("Fagus sylvatica", 0.9)]),
            _obs(93, "Pentanema squarrosum", PENTANEMA[0], status="manually_verified",
                 pn=[("Pentanema squarrosum", 0.9), ("Digitalis purpurea", 0.01)]),
        ])
        async with S() as s:
            rows = await observations.list_observations(
                limit=100, offset=0, geotagged_only=False, no_gps=False, named_only=False,
                unnamed_only=False, review_status="hazard_candidates", upload_source=None,
                obs_category=None, prefilter_category=None, review_label=None, q=None,
                exclude_not_plant=False, sort="added_desc", db=s)
            crit = await experience.critical_hazards(db=s)
        await eng.dispose()
        return rows, crit
    rows, crit = _run(run())
    assert [r["id"] for r in rows] == [90]
    assert [h["scientific_name"] for h in rows[0]["hazard_candidates"]] == ["Digitalis purpurea"]
    assert "candidate_items" not in crit and crit["count"] == 0


def test_review_page_has_no_hazard_candidate_block_and_has_the_filter():
    page = _src("frontend/review.html")
    for gone in ("crit-cand-head", "critical-cand-grid", "_critCandCardHtml", "candidate_items"):
        assert gone not in page, gone
    assert '<option value="hazard_candidates">☠ Hazard candidates</option>' in page
    # The walk Critical block stays.
    assert '<div id="critical-grid"></div>' in page and "function _critCardHtml(" in page


# ── second tap ────────────────────────────────────────────────────────────────

def _hazard_db():
    return _db(extra_obs=[
        # #24507 as it was: Pentanema proposed, Digitalis PlantNet #3.
        _obs(60, "Pentanema squarrosum", PENTANEMA[0],
             pn=[("Pentanema squarrosum", 0.904), ("Verbascum phoeniceum", 0.025), ("Digitalis purpurea", 0.0076)],
             cands=[("Pentanema squarrosum", 0.904)]),
        _obs(61, "Fagus sylvatica", BEECH[0], pn=[("Fagus sylvatica", 0.9)], cands=[("Fagus sylvatica", 0.9)]),
        _obs(62, "Pentanema squarrosum", PENTANEMA[0],
             pn=[("Pentanema squarrosum", 0.904), ("Digitalis purpurea", 0.0076)]),
    ])


def test_approve_as_another_species_needs_hazard_ack_naming_it():
    async def run():
        path, eng, S = await _hazard_db()
        res = {}
        async with S() as s:
            try:
                await observations.update_review(60, _BG(), status="approved", db=s)
                res["no_ack"] = "approved"
            except HTTPException as e:
                res["no_ack"] = (e.status_code, e.detail["code"],
                                 [h["scientific_name"] for h in e.detail["hazards"]])
        async with S() as s:
            try:
                await observations.update_review(60, _BG(), status="approved", hazard_ack="Verbascum x", db=s)
                res["wrong_ack"] = "approved"
            except HTTPException as e:
                res["wrong_ack"] = e.status_code
        async with S() as s:
            await observations.update_review(60, _BG(), status="approved",
                                             hazard_ack="Digitalis purpurea", db=s)
        async with S() as s:
            res["after"] = (await s.get(Observation, 60)).review_status
            # Confirming AS the hazard species needs no ack.
            await reidentify.confirm_species(62, _BG(), reidentify.ConfirmSpeciesRequest(
                scientific_name="Digitalis purpurea"), db=s)
        async with S() as s:
            res["as_hazard"] = (await s.get(Observation, 62)).species_primary
            await observations.update_review(61, _BG(), status="approved", db=s)    # harmless
            res["harmless"] = (await s.get(Observation, 61)).review_status
        await eng.dispose()
        return res

    r = _run(run())
    assert r["no_ack"] == (409, "hazard_ack_required", ["Digitalis purpurea"])
    assert r["wrong_ack"] == 409
    assert r["after"] == "approved"
    assert r["as_hazard"] == "Digitalis purpurea"
    assert r["harmless"] == "approved"


def test_bulk_approve_skips_hazard_rows():
    async def run():
        path, eng, S = await _hazard_db()
        bulk_actions.AsyncSessionLocal = S
        await bulk_actions._bulk_review_task([60, 61], "approved", None)
        async with S() as s:
            out = ((await s.get(Observation, 60)).review_status, (await s.get(Observation, 61)).review_status)
        await eng.dispose()
        return out

    assert _run(run()) == ("needs_review", "approved")


class _BG:
    def add_task(self, *a, **k):
        pass


# ── the card (review.html's own code in JavaScriptCore) ──────────────────────

def _src(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def _fn(src, name):
    m = re.search(r"^function %s\(" % re.escape(name), src, re.M)
    assert m, f"function {name} not found"
    i = src.index("{", m.end())
    depth = 0
    for k in range(i, len(src)):
        depth += {"{": 1, "}": -1}.get(src[k], 0)
        if depth == 0:
            return src[m.start():k + 1]
    raise AssertionError(name)


def _const(src, name):
    """A top-level `const NAME = …;` — one line, or an object literal closed by `};`."""
    m = re.search(r"^const %s = [^\n]*;$" % re.escape(name), src, re.M)
    if not m:
        m = re.search(r"^const %s = \{\n.*?^\};" % re.escape(name), src, re.M | re.S)
    assert m, name
    return m.group(0)


def _card(obs):
    page = _src("frontend/review.html")
    js = "\n".join([
        "var window = this;",
        _src("frontend/static/js/hazard-ack.js"),
        _fn(page, "_resc"), "const _esc = _resc;",
        _fn(page, "confClass"), _const(page, "CONF_BAND_LABEL"), _const(page, "_LABEL_DISPLAY"),
        _fn(page, "_reviewLabelChip"), "const _cardHazards = new Map();",
        "var selectModeActive = false, NON_EUROPEAN_LABEL = 'not European';",
        "function spCommonList(a){return a.join(', ');} function _noneuLabel(){return '';}",
        "function _catLabel(c){return c;}",
        _fn(page, "_makeCardHtml"),
        "print(JSON.stringify(_makeCardHtml(%s)));" % json.dumps(obs),
    ])
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
        p = f.name
    try:
        out = subprocess.run([JSC, p], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(p)
    assert out.returncode == 0, out.stderr or out.stdout
    return json.loads(out.stdout.strip().splitlines()[-1])


FOX_HIT = {"species_id": 376, "scientific_name": "Digitalis purpurea", "common": "Foxglove",
           "level": "deadly", "label": "Foxglove (Digitalis purpurea)",
           "sources": [{"source": "plantnet", "score": 0.0076, "rank": 3}]}


def _obs_24507(**kw):
    o = {"id": 24507, "file_path": "/p/x.jpg", "thumbnail_path": None, "photo_taken_at": None,
         "latitude": 47.7, "longitude": 7.9, "review_status": "needs_review", "review_label": "low_confidence",
         "identification_status": "identified", "species_primary": "Pentanema squarrosum",
         "obs_category": "plant", "itis_name_match": "no_match", "gbif_match_type": "EXACT",
         "species_candidates_json": json.dumps([
             {"scientific_name": "Pentanema squarrosum", "score": 0.9042, "source": "plantnet",
              "common_names": [], "inat_vision_score": 0.3172, "inat_combined_score": 0.7592},
             {"scientific_name": "Verbascum phoeniceum", "score": 0.0246, "source": "plantnet"},
             {"scientific_name": "Digitalis purpurea", "score": 0.0076, "source": "plantnet"}]),
         "hazard_candidates": [FOX_HIT]}
    o.update(kw)
    return o


def test_card_shows_hazard_in_red_above_the_name_and_not_in_also():
    html = _card(_obs_24507())
    line = '<div class="hazard-line hazard-deadly"'
    assert line in html and "☠ Foxglove (Digitalis purpurea) — candidate</div>" in html
    assert html.index(line) < html.index('<div class="sp-name">')
    also = re.search(r'<div class="sp-alts">Also: (.*?)</div>', html).group(1)
    assert "Digitalis" not in also and "Verbascum phoeniceum" in also


def test_harmless_card_has_no_hazard_line():
    html = _card(_obs_24507(hazard_candidates=[]))
    assert "hazard-line" not in html and "hazard-deep-line" not in html


def test_deep_hazard_card_shows_one_grey_line_no_red_line():
    hem = {"species_id": 40, "scientific_name": "Conium maculatum", "common": None, "level": "deadly",
           "label": "Conium maculatum", "gate": False,
           "sources": [{"source": "plantnet", "score": 0.001, "rank": 8}]}
    html = _card(_obs_24507(hazard_candidates=[], hazard_deep=[hem], species_candidates_json=json.dumps([
        {"scientific_name": "Pentanema squarrosum", "score": 0.9042, "source": "plantnet"},
        {"scientific_name": "Conium maculatum", "score": 0.001, "source": "plantnet"},
        {"scientific_name": "Verbascum phoeniceum", "score": 0.0246, "source": "plantnet"}])))
    assert "hazard-line" not in html
    assert html.count('class="hazard-deep-line"') == 1
    assert '<div class="hazard-deep-line">Also listed deep in PlantNet: Conium maculatum 0.1%</div>' in html
    also = re.search(r'<div class="sp-alts">Also: (.*?)</div>', html).group(1)
    assert "Conium" not in also


def test_confidence_chip_matches_the_percent_shown():
    html = _card(_obs_24507())
    assert '<span class="sp-score">90.4%</span>' in html
    assert 'class="species-block conf-high"' in html
    chip = re.search(r'<span class="review-label-pill([^"]*)">(.*?)</span>', html)
    assert chip.group(1) == " conf-high"                       # same band as the 90.4%
    assert chip.group(2) == "High confidence · iNat 31.7%"     # never "Low confidence" beside 90%
    low = _card(_obs_24507(species_candidates_json=json.dumps(
        [{"scientific_name": "Pentanema squarrosum", "score": 0.2, "source": "plantnet"}])))
    assert re.search(r'<span class="review-label-pill conf-low">Low confidence</span>', low)


def test_itis_banner_amber_for_gbif_accepted_name_red_otherwise():
    amber = _card(_obs_24507())
    assert '<div class="itis-banner-newer">⚠ Name not in ITIS — may be a newer name</div>' in amber
    assert "itis-banner-no-match" not in amber
    red = _card(_obs_24507(gbif_match_type="NONE"))
    assert "itis-banner-no-match" in red and "itis-banner-newer" not in red


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
