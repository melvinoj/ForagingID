"""
Tests for fix batch 3b (21 Oct 2026): verdict drafts.

  * The proposal rules (app/services/verdict_drafts.py): stored sources only,
    no family heuristic, 'unknown' + a reason when sources are thin or disagree,
    never 'deadly' from text, never a lowered severity.
  * The sweep (scripts/verdict_sweep_drafts.py) end to end on a throw-away DB.
  * The approve path (POST /api/edibility/verdict-drafts/{id}/approve): writes
    through the shared verdict writer (severity_for_verdict + history rows
    changed_by 'human'); REFUSED, with nothing written, when the species changed
    after drafting, for a combination the severity rule refuses, for a draft
    that isn't a pending verdict draft. Reject leaves the species alone.
  * Never part of "Approve all": not listed in AI Draft Review, and the generic
    draft approve refuses the field.

No external calls. Throw-away SQLite DBs only.

Run from project root:  python -m pytest tests/test_verdict_drafts.py -v
Or standalone:          python tests/test_verdict_drafts.py
"""

import asyncio
import contextlib
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from fastapi import BackgroundTasks, HTTPException  # noqa: E402
from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main  # noqa: E402,F401  (registers every model on Base.metadata)
import app.api.edibility as edib  # noqa: E402
import app.services.enrichment as enrichment  # noqa: E402
from app.api.identity import Identity  # noqa: E402
from app.database import Base  # noqa: E402
from app.models.observation import Observation  # noqa: E402
from app.models.species import (EnrichmentSource, Species, SpeciesAIDraft,  # noqa: E402
                                SpeciesEdibilityHistory)
from app.services.verdict_drafts import (changes_since, pfaf_signal, propose,  # noqa: E402
                                         toxic_mentions)
import verdict_sweep_drafts as sweep  # noqa: E402

CURATOR = Identity(user_id=None, is_guest=False, is_anonymous_guest=False, workshop_session_id=None)
GUEST = Identity(user_id=None, is_guest=True, is_anonymous_guest=True, workshop_session_id=None)


async def _no_drafts(name):
    return None
enrichment.trigger_ai_drafts_for_species = _no_drafts      # never call out from tests


# ── proposal rules ────────────────────────────────────────────────────────────

def test_negated_poison_wording_does_not_count():
    cases = {
        "No known toxicity.": ([], ["toxicity"]),
        "The plant is non-toxic.": ([], ["toxic"]),
        "No members of this genus are known to be poisonous, but nitrates build up.": ([], ["poisonous"]),
        "This is a matter of tolerance rather than toxicity.": ([], ["toxicity"]),
        "The plant is poisonous, causing paralysis.": (["poisonous"], []),
        "Although no reports of toxicity have been seen, some members of this genus have poisonous fruits.":
            (["poisonous"], ["toxicity"]),
        "No known toxicity. The seeds are poisonous.": (["poisonous"], ["toxicity"]),
    }
    for text, want in cases.items():
        assert toxic_mentions(text) == want, (text, toxic_mentions(text))


def _p(rating, hazards, url="https://pfaf.org/user/Plant.aspx?LatinName=Testus%20plantus"):
    return {"rating": rating, "hazards": hazards, "edible_uses": "Leaves raw.", "url": url,
            "enrichment_source_id": 7}


def test_pfaf_signal_rules():
    S = "Testus plantus"
    assert pfaf_signal(_p(3, "None known"), S)["says"] == "edible"
    assert pfaf_signal(_p(2, "Contains oxalic acid."), S)["says"] == "caution"
    assert pfaf_signal(_p(4, "No known toxicity. Avoid sprayed verges."), S)["says"] == "caution"
    s = pfaf_signal(_p(3, "Although toxic, saponins are poorly absorbed."), S)
    assert s["says"] is None and s["conflicting"] and "'toxic'" in s["why"]
    assert pfaf_signal(_p(0, "The plant is poisonous, causing paralysis[74]."), S)["says"] == "toxic"
    assert pfaf_signal(_p(0, "No known toxicity."), S)["says"] is None
    assert pfaf_signal(_p(0, "None known"), S)["says"] is None
    assert pfaf_signal(_p(None, "None known"), S)["says"] is None
    # not about this species
    assert pfaf_signal(_p(1, "None known", url="https://pfaf.org/user/Plant.aspx?LatinName=Crocus"), "Crocus")["says"] is None
    assert pfaf_signal(_p(3, "None known", url="https://pfaf.org/user/Plant.aspx?LatinName=Other%20species"), S)["says"] is None
    # quotes are the exact text
    q = pfaf_signal(_p(0, "The plant is poisonous, causing paralysis[74]."), S)["quotes"]
    assert {"field": "Known Hazards", "text": "The plant is poisonous, causing paralysis[74]."} in q


def _src(says, label="X", why="w"):
    return {"source": label.lower(), "label": label, "says": says, "why": why}


def test_propose_combines_conservatively():
    p = propose("unknown", [])
    assert (p["edibility_status"], p["toxicity_severity"], p["evidence"]) == ("unknown", "unknown", "thin")
    p = propose("unknown", [_src("edible", "PFAF")])
    assert (p["edibility_status"], p["toxicity_severity"], p["evidence"]) == ("edible", "none", "single_source")
    p = propose("unknown", [_src("edible", "PFAF"), _src("caution", "Conditions")])
    assert (p["edibility_status"], p["evidence"]) == ("caution", "multiple_sources") and "careful" in p["reason"]
    p = propose("unknown", [_src("edible", "PFAF"), _src("toxic", "Human")])
    assert (p["edibility_status"], p["toxicity_severity"], p["evidence"]) == ("unknown", "unknown", "conflict")
    assert "PFAF says edible" in p["reason"] and "Human says toxic" in p["reason"]
    # a recorded deadly severity is kept; 'deadly' is never proposed from text
    p = propose("deadly", [_src("toxic", "Recorded toxicity severity"), _src("toxic", "PFAF")])
    assert (p["edibility_status"], p["toxicity_severity"], p["evidence"]) == ("toxic", "deadly", "multiple_sources")
    p = propose("unknown", [_src("toxic", "PFAF")])
    assert p["toxicity_severity"] == "toxic"
    # a proposal never lowers a recorded severity
    p = propose("toxic", [_src("edible", "PFAF")])
    assert (p["edibility_status"], p["toxicity_severity"], p["evidence"]) == ("unknown", "toxic", "conflict")
    # PFAF contradicting itself, nothing else
    p = propose("unknown", [{"source": "pfaf", "label": "PFAF", "says": None, "conflicting": True, "why": "w"}])
    assert (p["edibility_status"], p["evidence"]) == ("unknown", "conflict")


def test_changes_since():
    st = {"edibility_status": None, "toxicity_severity": "unknown", "edibility_verified": False,
          "edibility_verified_by": None, "last_species_history_id": 5, "last_ci_verdict_history_id": None}
    assert changes_since(st, dict(st)) == []
    assert changes_since(st, {**st, "toxicity_severity": "toxic"}) == ["toxicity_severity was 'unknown', now 'toxic'"]
    assert changes_since(st, {**st, "last_species_history_id": 6}) == ["its verdict history has new rows"]
    assert changes_since(None, st)


def test_sweep_scope():
    assert sweep.in_scope(None, "unknown") and sweep.in_scope("unknown", "deadly") and sweep.in_scope("unclear", "none")
    assert sweep.in_scope("edible", "toxic") and sweep.in_scope("toxic", "none")        # out of sync
    assert not sweep.in_scope("toxic", "deadly") and not sweep.in_scope("caution", "none")
    assert not sweep.in_scope("_merged_into:Rosa canina", "none")


# ── sweep + endpoints on a throw-away DB ──────────────────────────────────────

def _run(coro):
    return asyncio.run(coro)


def _pfaf_html(rating, hazards, edible="Leaves - raw or cooked."):
    return ("<html><body><!-- " + "x" * 1200 + " --><table>"
            f"<tr><td>Edibility Rating</td><td>{rating} (1-5)</td></tr>"
            f"<tr><td><b>Known Hazards</b></td><td>{hazards}</td></tr></table>"
            f"<h2>Edible Uses</h2><p>{edible}</p></body></html>")


SPECIES = [
    # id, name, verdict, severity, kingdom, pfaf (rating, hazards) or None, confirmed pins
    (1, "Galeopsis speciosa", None, "unknown", "Plantae", (0, "The plant is poisonous, causing paralysis[74]."), 2),
    (2, "Tragopogon pratensis", "unknown", "unknown", "Plantae", (3, "None known"), 5),
    (3, "Agrimonia eupatoria", "unknown", "unknown", "Plantae", (2, "Contains tannins."), 0),
    (4, "Leucocoprinus leucothites", None, "unknown", "Fungi", None, 1),
    (5, "Sambucus nigra", "caution", "none", "Plantae", (3, "Contains a toxin."), 9),        # not in scope
    (6, "Orphanus cardus", "unknown", "unknown", "Plantae", None, 0),                     # orphan-marked
]


async def _db():
    from datetime import datetime
    path = os.path.join(tempfile.mkdtemp(prefix="vdtest_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    S = async_sessionmaker(eng, expire_on_commit=False)
    async with S() as s:
        oid = 0
        for sid, name, verdict, sev, kingdom, pf, pins in SPECIES:
            s.add(Species(id=sid, scientific_name=name, name_key=name.lower(), edibility_status=verdict,
                          toxicity_severity=sev, kingdom=kingdom,
                          orphaned_at=datetime(2026, 10, 20) if sid == 6 else None))
            if pf:
                s.add(EnrichmentSource(species_id=sid, source_name="pfaf", parsing_method="html_scrape",
                                       source_url=f"https://pfaf.org/user/Plant.aspx?LatinName={name.replace(' ', '%20')}",
                                       raw_response_json=_pfaf_html(*pf), retrieved_at=datetime(2026, 10, 1)))
            for _ in range(pins):
                oid += 1
                s.add(Observation(id=oid, file_path=f"/nonexistent/vd{oid}.jpg", file_hash=f"h{oid}",
                                  species_id=sid, species_primary=name, review_status="approved",
                                  identification_status="identified", latitude=47.7, longitude=7.7))
        s.add(SpeciesAIDraft(id=900, species_id=4, field_name="edibility_status", status="pending",
                             model="fao_fungi+mushroom_observer",
                             draft_text="Fungi edibility lookup: status=unknown, confidence=0.00. Sources: no source data."))
        s.add(SpeciesAIDraft(id=901, species_id=2, field_name="medicinal_notes", status="pending",
                             model="claude", draft_text="Some text."))
        await s.commit()
    return path, eng, S


def _sweep(path, apply=True):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        sweep.main(["--db", path] + (["--apply"] if apply else []))
    return out.getvalue()


async def _draft_for(S, sid):
    async with S() as s:
        return await s.scalar(select(SpeciesAIDraft).where(SpeciesAIDraft.species_id == sid,
                                                           SpeciesAIDraft.model == "verdict_sweep"))


def test_sweep_end_to_end_dry_run_then_apply():
    async def run():
        path, eng, S = await _db()
        dry = _sweep(path, apply=False)
        async with S() as s:
            n_dry = await s.scalar(select(func.count(SpeciesAIDraft.id)).where(SpeciesAIDraft.model == "verdict_sweep"))
        out = _sweep(path)
        drafts = {sid: await _draft_for(S, sid) for sid in (1, 2, 3, 4, 5, 6)}
        async with S() as s:
            fungi = await s.get(SpeciesAIDraft, 900)
            other = await s.get(SpeciesAIDraft, 901)
        again = _sweep(path)
        await eng.dispose()
        return dry, n_dry, out, drafts, fungi, other, again

    dry, n_dry, out, d, fungi, other, again = _run(run())
    assert n_dry == 0 and "Dry run — nothing written." in dry
    assert "Drafts to create: 4" in out and "read-back mismatches: 0" in out
    assert d[5] is None and d[6] is None                       # out of scope / orphan-marked
    ctx = {k: json.loads(v.generation_context_json) for k, v in d.items() if v}
    assert (d[1].draft_text, ctx[1]["proposed"]["toxicity_severity"], ctx[1]["evidence"]) == ("toxic", "toxic", "single_source")
    assert {"field": "Known Hazards", "text": "The plant is poisonous, causing paralysis[74]."} in ctx[1]["sources"][0]["quotes"]
    assert (d[2].draft_text, ctx[2]["proposed"]["toxicity_severity"]) == ("edible", "none")
    assert d[3].draft_text == "caution"
    assert (d[4].draft_text, ctx[4]["evidence"]) == ("unknown", "thin")
    assert ctx[4]["superseded_draft_ids"] == [900] and fungi.status == "invalidated"
    assert other.status == "pending"                            # other drafts untouched
    assert all(v.status == "pending" and v.field_name == "edibility_status" for v in d.values() if v)
    assert ctx[1]["at_draft"]["edibility_status"] is None and ctx[1]["confirmed_pins"] == 2
    assert "Drafts to create: 0" in again                       # idempotent


async def _approve(S, draft_id, **kw):
    async with S() as s:
        return await edib.approve_verdict_draft(draft_id, edib.VerdictDraftApproveIn(**kw), BackgroundTasks(),
                                                db=s, identity=CURATOR)


async def _state(S, sid, draft_id):
    async with S() as s:
        sp = await s.get(Species, sid)
        d = await s.get(SpeciesAIDraft, draft_id)
        hist = (await s.execute(select(SpeciesEdibilityHistory).where(SpeciesEdibilityHistory.species_id == sid)
                                .order_by(SpeciesEdibilityHistory.id))).scalars().all()
        return ((sp.edibility_status, sp.toxicity_severity, bool(sp.edibility_verified), sp.edibility_verified_by),
                (d.status, d.final_text, d.approved_at is not None),
                [(h.field, h.old_value, h.new_value, h.changed_by, h.note) for h in hist])


def test_approve_as_proposed_writes_verdict_severity_and_history():
    async def run():
        path, eng, S = await _db()
        _sweep(path)
        d = await _draft_for(S, 1)
        res = await _approve(S, d.id, edibility_status="toxic", toxicity_severity="toxic")
        st = await _state(S, 1, d.id)
        await eng.dispose()
        return d.id, res, st

    did, res, (sp, dr, hist) = _run(run())
    assert res["ok"] and res["draft_status"] == "approved"
    assert sp == ("toxic", "toxic", True, "human")
    assert dr[0] == "approved" and dr[1] == "toxic / toxic" and dr[2]
    note = f"verdict draft #{did} (batch 3b sweep)"
    assert hist == [("toxicity_severity", "unknown", "toxic", "human", note),
                    ("edibility_status", None, "toxic", "human", note)]


def test_approve_with_the_curators_own_choice_is_edited_approved():
    async def run():
        path, eng, S = await _db()
        _sweep(path)
        d = await _draft_for(S, 2)                 # proposed edible / none
        res = await _approve(S, d.id, edibility_status="caution", toxicity_severity="none", note="leaves only")
        st = await _state(S, 2, d.id)
        await eng.dispose()
        return res, st

    res, (sp, dr, hist) = _run(run())
    assert res["draft_status"] == "edited_approved"
    assert sp == ("caution", "none", True, "human") and dr[0] == "edited_approved"
    assert hist[-1][:4] == ("edibility_status", "unknown", "caution", "human") and hist[-1][4].endswith(": leaves only")


def test_refused_when_the_species_was_edited_after_drafting():
    """The curator set Tragopogon on the species page after the sweep: the
    draft's approval is refused and nothing is written."""
    async def run():
        path, eng, S = await _db()
        _sweep(path)
        d = await _draft_for(S, 2)
        async with S() as s:                        # edit through the normal verdict endpoint
            await edib.set_edibility_status(2, edib.EdibilityStatusIn(edibility_status="caution", verified=True),
                                            BackgroundTasks(), db=s, identity=CURATOR)
        before = await _state(S, 2, d.id)
        try:
            await _approve(S, d.id, edibility_status="edible", toxicity_severity="none")
            err = None
        except HTTPException as e:
            err = (e.status_code, e.detail)
        after = await _state(S, 2, d.id)
        await eng.dispose()
        return err, before, after

    err, before, after = _run(run())
    assert err[0] == 409 and "changed after this draft was made" in err[1] and "Nothing was written" in err[1]
    assert before == after and after[1][0] == "pending" and after[0][0] == "caution"


def test_refused_when_severity_changed_after_drafting():
    async def run():
        path, eng, S = await _db()
        _sweep(path)
        d = await _draft_for(S, 3)
        async with S() as s:
            sp = await s.get(Species, 3)
            sp.toxicity_severity = "toxic"           # e.g. a later safety write
            await s.commit()
        try:
            await _approve(S, d.id, edibility_status="caution", toxicity_severity="none")
            err = None
        except HTTPException as e:
            err = e.status_code
        st = await _state(S, 3, d.id)
        await eng.dispose()
        return err, st

    err, (sp, dr, hist) = _run(run())
    assert err == 409 and sp[:2] == ("unknown", "toxic") and dr[0] == "pending" and hist == []


def test_refused_combinations_and_wrong_drafts_write_nothing():
    async def run():
        path, eng, S = await _db()
        _sweep(path)
        d = await _draft_for(S, 2)
        errs = []
        for kw in ({"edibility_status": "edible", "toxicity_severity": "deadly"},     # severity rule
                   {"edibility_status": "lethal", "toxicity_severity": "none"}):       # not a verdict
            try:
                await _approve(S, d.id, **kw)
            except HTTPException as e:
                errs.append(e.status_code)
        for draft_id in (901, 900):                  # a medicinal draft; an invalidated fungi lookup
            try:
                await _approve(S, draft_id, edibility_status="edible", toxicity_severity="none")
            except HTTPException as e:
                errs.append(e.status_code)
        try:
            async with S() as s:
                await edib.approve_verdict_draft(d.id, edib.VerdictDraftApproveIn(
                    edibility_status="edible", toxicity_severity="none"), BackgroundTasks(), db=s, identity=GUEST)
        except HTTPException as e:
            errs.append(e.status_code)
        st = await _state(S, 2, d.id)
        await _approve(S, d.id, edibility_status="edible", toxicity_severity="none")
        try:
            await _approve(S, d.id, edibility_status="edible", toxicity_severity="none")
        except HTTPException as e:
            errs.append(e.status_code)                # already approved
        await eng.dispose()
        return errs, st

    errs, (sp, dr, hist) = _run(run())
    assert errs == [400, 422, 400, 400, 403, 409], errs
    assert sp[:2] == ("unknown", "unknown") and dr[0] == "pending" and hist == []


def test_reject_leaves_the_species_and_is_not_redrafted():
    async def run():
        path, eng, S = await _db()
        _sweep(path)
        d = await _draft_for(S, 3)
        async with S() as s:
            res = await edib.reject_verdict_draft(d.id, db=s, identity=CURATOR)
        st = await _state(S, 3, d.id)
        again = _sweep(path)
        await eng.dispose()
        return res, st, again

    res, (sp, dr, hist), again = _run(run())
    assert res["draft_status"] == "rejected" and dr[0] == "rejected"
    assert sp[:2] == ("unknown", "unknown") and hist == []
    assert "verdict draft already rejected" in again


def test_never_in_approve_all():
    from app.api.culinary import DraftEditApprove, ai_draft_review_queue, approve_ai_draft

    async def run():
        path, eng, S = await _db()
        _sweep(path)
        async with S() as s:
            queue = await ai_draft_review_queue(db=s)
            try:
                await approve_ai_draft("Tragopogon pratensis", "edibility_status", DraftEditApprove(),
                                       db=s, identity=CURATOR)
                err = None
            except HTTPException as e:
                err = e.status_code
        await eng.dispose()
        return queue, err

    queue, err = _run(run())
    fields = {d["field_name"] for sp in queue for d in sp["drafts"]}
    assert fields == {"medicinal_notes"} and err == 400


def test_queue_puts_walk_species_first_then_pins():
    async def run():
        path, eng, S = await _db()
        _sweep(path)

        async def fake_walks(db):
            return {3: ["Rümmelsbühl foray"]}       # Agrimonia: 0 pins but on a saved walk
        real, edib.species_on_saved_walks = edib.species_on_saved_walks, fake_walks
        try:
            async with S() as s:
                out = await edib.list_verdict_drafts(db=s, identity=CURATOR)
        finally:
            edib.species_on_saved_walks = real
        await eng.dispose()
        return out

    out = _run(run())
    order = [(i["scientific_name"], i["confirmed_pins"], i["walks"]) for i in out["items"]]
    assert [o[0] for o in order] == ["Agrimonia eupatoria", "Tragopogon pratensis", "Galeopsis speciosa",
                                     "Leucocoprinus leucothites"], order
    item = out["items"][0]
    assert item["proposed"] == {"edibility_status": "caution", "toxicity_severity": "none"}
    assert item["changed_since_draft"] == [] and item["severity_defaults"]["toxic"] == "toxic"
    assert out["allowed_severities"]["edible"] == ["none"]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
