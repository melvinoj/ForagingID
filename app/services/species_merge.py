"""
species_merge.py — the ONE species-merge routine (audit batch 11b, Melvin 27–28 Oct 2026).

Folds a duplicate species card (discard) into the card that keeps the GBIF
accepted name (keep), re-keying every species-keyed table, then DELETES the
discard card. It never goes through the rename cascade (POST
/api/species/{name}/rename — B3-01: that path clears safety text and keeps the
old family/genus); POST /api/species/merge calls this.

Re-keyed (discard → keep):
  observations          species_id, species_primary, species_suggested (+ an
                        observation_edits row per moved species_primary)
  species_candidates, species_ai_drafts, species_recipes, species_edibility_history,
  species_edibility_conditions, encounters, sources, enrichment_sources
  species_lookalikes    both columns; self-references dropped
  species_synonyms      re-pointed, plus a row for the discard's own name so a
                        later ID of that name resolves to keep (and the hazard
                        index sees it)
  session_species, personal_list_species, notification_dismissals
                        re-pointed; a row the keep card already has is dropped
  species_resources     STRING-keyed by species_name: re-keyed to keep's name
                        (a URL keep already has is dropped)
  map_notes.species_tags  names
  culinary_info (+ history)  field by field — see TEXT RULE; the discard row's
                        history rows move to keep's row, then the row is deleted
  saved_walks.waypoints_json  any "species_id": discard
  walk overrides        scripts/experience_export/overrides/*.json hide_species_ids
  experience_publications  overrides_json hide_species_ids, and the ids (only the
                        ids) in public_species_json — that is the live page's
                        snapshot, so its names stay what was published; the page
                        itself changes on the next republish.
Walk membership is computed from observations (walk_membership.py) — moving the
observations moves it; nothing is stored.

TEXT RULE (culinary_info text fields): equal → nothing; one side empty → the
other side's text; both set and different → the side with a changed_by='human'
history row for that field wins, else keep's (accepted-name) text; the losing
text always goes into a culinary_info_history row on keep's row (notes say
where it came from). Curator text that lands on keep is stamped
changed_by='human' so the enrichment human-lock still holds.

VERDICT RULE: a toxic verdict on either side wins (fails safe). Otherwise a
human-verified side beats an unverified one; among equals the more
conservative verdict wins (inedible > caution > unknown > edible), and the
higher severity allowed for that verdict. Written through edibility._write_verdict
only when keep's verdict actually changes; the human lock (edibility_verified)
is kept if either side had it.

The caller takes the snapshot, holds the transaction and commits.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.culinary import CulinaryInfo
from app.models.observation import ObservationEdit
from app.models.species import (CulinaryInfoHistory, Species, SpeciesEdibilityHistory, SpeciesSynonym)
from app.services.taxonomy import normalize_taxon_key

PROJECT = Path(__file__).resolve().parents[2]
OVERRIDES_DIR = PROJECT / "scripts" / "experience_export" / "overrides"

TEXT_FIELDS = (
    "edible_parts", "flavour_profile", "preparation_methods", "cooking_techniques", "preservation_methods",
    "seasonal_peak", "harvest_stage", "pairing_ideas", "culinary_traditions", "recipe_ideas", "traditional_uses",
    "cultural_notes", "medicinal_folklore", "look_alike_warnings", "preparation_warnings", "id_notes",
    "taste_notes", "medicinal_notes", "recipe", "medicinal_clinical",
)
# Non-text culinary_info columns: filled on keep only where keep's is empty.
FILL_FIELDS = (
    "workshop_value_score", "primary_source_url", "sources_json", "id_notes_sources_json", "culinary_links_json",
    "ai_generated_fields_json", "ai_approved_fields_json",
)
SPECIES_FILL_FIELDS = (
    "common_names", "preferred_common_name", "common_names_de", "flower_months", "fruit_months", "leaf_months",
    "peak_season", "foraging_notes", "inaturalist_taxon_id",
)
# Simple species_id re-keys (no unique constraint on species_id).
REKEY_TABLES = ("species_candidates", "species_ai_drafts", "species_recipes", "species_edibility_history",
                "species_edibility_conditions", "encounters", "sources", "enrichment_sources")
# species_id re-keys where keep may already hold the same row (unique together with these columns).
DEDUPE_TABLES = {"session_species": ("session_id",), "personal_list_species": ("list_id",),
                 "notification_dismissals": ("user_id", "season_key")}

_VERDICT_RANK = {"inedible": 4, "caution": 3, "unknown": 2, "edible": 1}
_SEVERITY_RANK = {"deadly": 4, "toxic": 3, "unknown": 2, "none": 1}


def merged_verdict(keep: Species, discard: Species) -> tuple[str, str, bool]:
    """(verdict, severity, verified) the merged card carries — the VERDICT RULE above."""
    from app.models.species import ALLOWED_SEVERITIES
    sides = [keep, discard]
    toxic = [s for s in sides if (s.edibility_status or "") == "toxic"]
    if toxic:
        pool, verdict = toxic, "toxic"
    else:
        verified = [s for s in sides if s.edibility_verified]
        pool = verified or sides
        verdict = max((s.edibility_status or "unknown" for s in pool), key=lambda v: _VERDICT_RANK.get(v, 2))
    sev_pool = [s.toxicity_severity or "unknown" for s in sides if (s.edibility_status or "unknown") == verdict]
    allowed = ALLOWED_SEVERITIES.get(verdict, ("unknown",))
    sev_pool = [v for v in sev_pool if v in allowed] or [allowed[0]]
    severity = max(sev_pool, key=lambda v: _SEVERITY_RANK.get(v, 2))
    return verdict, severity, bool(keep.edibility_verified or discard.edibility_verified)


async def _human_fields(session: AsyncSession, ci_id: Optional[int]) -> set:
    if ci_id is None:
        return set()
    rows = await session.execute(select(CulinaryInfoHistory.field_name).where(
        CulinaryInfoHistory.culinary_info_id == ci_id, CulinaryInfoHistory.changed_by == "human").distinct())
    return {r[0] for r in rows}


def _swap_ids(ids, did: int, kid: int):
    out, changed = [], False
    for x in ids:
        if x == did:
            x, changed = kid, True
        if x not in out:
            out.append(x)
    return out, changed


async def merge_species_cards(session: AsyncSession, discard_id: int, keep_id: int,
                              changed_by: str = "merge", note: str = "",
                              overrides_dir: Optional[Path] = OVERRIDES_DIR) -> dict:
    """Merge card discard_id into keep_id and delete discard_id. Returns a report
    of every re-keyed row (ids) for the caller's read-back. Caller commits."""
    if discard_id == keep_id:
        raise ValueError("cannot merge a species card into itself")
    keep = await session.get(Species, keep_id)
    disc = await session.get(Species, discard_id)
    if keep is None or disc is None:
        raise ValueError(f"species card not found: keep={keep_id} discard={discard_id}")
    did, kid, dname, kname = disc.id, keep.id, disc.scientific_name, keep.scientific_name
    tag = f"merge {did} {dname} → {kid} {kname}" + (f" ({note})" if note else "")
    rep: dict = {"keep": kid, "discard": did, "keep_name": kname, "discard_name": dname, "moved": {}}

    async def ids(sql, **p):
        return [r[0] for r in (await session.execute(text(sql), p)).all()]

    # ── observations ────────────────────────────────────────────────────────
    obs_rows = (await session.execute(text(
        "SELECT id, species_primary FROM observations WHERE species_id = :d OR species_primary = :dn"),
        {"d": did, "dn": dname})).all()
    for oid, prim in obs_rows:
        if prim == dname:
            session.add(ObservationEdit(observation_id=oid, field_name="species_primary",
                                        old_value=dname, new_value=kname, edited_by=changed_by))
    await session.execute(text(
        "UPDATE observations SET species_id = :k, species_primary = CASE WHEN species_primary = :dn "
        "THEN :kn ELSE species_primary END WHERE species_id = :d OR species_primary = :dn"),
        {"k": kid, "d": did, "dn": dname, "kn": kname})
    sug = await ids("SELECT id FROM observations WHERE species_suggested = :dn", dn=dname)
    for oid in sug:
        session.add(ObservationEdit(observation_id=oid, field_name="species_suggested",
                                    old_value=dname, new_value=kname, edited_by=changed_by))
    await session.execute(text("UPDATE observations SET species_suggested = :kn WHERE species_suggested = :dn"),
                          {"kn": kname, "dn": dname})
    rep["moved"]["observations"] = sorted(r[0] for r in obs_rows)
    rep["moved"]["observations.species_suggested"] = sug

    # ── simple re-keys ──────────────────────────────────────────────────────
    for t in REKEY_TABLES:
        rows = await ids(f"SELECT id FROM {t} WHERE species_id = :d", d=did)
        await session.execute(text(f"UPDATE {t} SET species_id = :k WHERE species_id = :d"), {"k": kid, "d": did})
        rep["moved"][t] = rows
    for t, cols in DEDUPE_TABLES.items():
        same = " AND ".join(f"x.{c} = {t}.{c}" for c in cols)
        dropped = await ids(f"SELECT id FROM {t} WHERE species_id = :d AND EXISTS "
                            f"(SELECT 1 FROM {t} x WHERE x.species_id = :k AND {same})", d=did, k=kid)
        if dropped:
            await session.execute(text(f"DELETE FROM {t} WHERE id IN ({','.join(map(str, dropped))})"))
        rows = await ids(f"SELECT id FROM {t} WHERE species_id = :d", d=did)
        await session.execute(text(f"UPDATE {t} SET species_id = :k WHERE species_id = :d"), {"k": kid, "d": did})
        rep["moved"][t] = rows
        if dropped:
            rep["moved"][t + " (duplicate dropped)"] = dropped

    # ── lookalikes (both columns) ────────────────────────────────────────────
    la = await ids("SELECT id FROM species_lookalikes WHERE species_id = :d OR lookalike_species_id = :d", d=did)
    await session.execute(text("UPDATE species_lookalikes SET species_id = :k WHERE species_id = :d"), {"k": kid, "d": did})
    await session.execute(text("UPDATE species_lookalikes SET lookalike_species_id = :k WHERE lookalike_species_id = :d"),
                          {"k": kid, "d": did})
    selfref = await ids("SELECT id FROM species_lookalikes WHERE species_id = :k AND lookalike_species_id = :k", k=kid)
    if selfref:
        await session.execute(text(f"DELETE FROM species_lookalikes WHERE id IN ({','.join(map(str, selfref))})"))
    rep["moved"]["species_lookalikes"] = la

    # ── synonyms ────────────────────────────────────────────────────────────
    syn = await ids("SELECT id FROM species_synonyms WHERE canonical_species_id = :d", d=did)
    await session.execute(text("UPDATE species_synonyms SET canonical_species_id = :k WHERE canonical_species_id = :d"),
                          {"k": kid, "d": did})
    rep["moved"]["species_synonyms"] = syn
    dkey = disc.name_key or normalize_taxon_key(dname)
    existing = await session.scalar(select(SpeciesSynonym).where(SpeciesSynonym.synonym_name_key == dkey))
    if existing is None:
        s = SpeciesSynonym(synonym_name_key=dkey, synonym_scientific_name=dname, canonical_species_id=kid)
        session.add(s)
        await session.flush()
        rep["synonym_added"] = s.id
    elif existing.canonical_species_id != kid:
        existing.canonical_species_id = kid
        rep["synonym_repointed"] = existing.id

    # ── species_resources (string-keyed) ────────────────────────────────────
    dup = await ids("SELECT id FROM species_resources WHERE species_name = :dn AND url IS NOT NULL AND url IN "
                    "(SELECT url FROM species_resources WHERE species_name = :kn)", dn=dname, kn=kname)
    if dup:
        await session.execute(text(f"DELETE FROM species_resources WHERE id IN ({','.join(map(str, dup))})"))
    res = await ids("SELECT id FROM species_resources WHERE species_name = :dn", dn=dname)
    await session.execute(text("UPDATE species_resources SET species_name = :kn WHERE species_name = :dn"),
                          {"kn": kname, "dn": dname})
    rep["moved"]["species_resources"] = res
    if dup:
        rep["moved"]["species_resources (duplicate dropped)"] = dup

    # ── map note tags ───────────────────────────────────────────────────────
    notes = []
    for nid, tags in (await session.execute(text(
            "SELECT id, species_tags FROM map_notes WHERE species_tags LIKE :p"), {"p": f"%{dname}%"})).all():
        try:
            lst = json.loads(tags)
        except (TypeError, ValueError):
            continue
        if dname in lst:
            new = []
            for t in lst:
                t = kname if t == dname else t
                if t not in new:
                    new.append(t)
            await session.execute(text("UPDATE map_notes SET species_tags = :t WHERE id = :i"),
                                  {"t": json.dumps(new), "i": nid})
            notes.append(nid)
    rep["moved"]["map_notes"] = notes

    # ── culinary_info, field by field ───────────────────────────────────────
    dci = await session.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == did))
    kci = await session.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == kid))
    text_log = []
    if dci is not None and kci is None:
        dci.species_id = kid
        rep["moved"]["culinary_info"] = [dci.id]
    elif dci is not None:
        dh, kh = await _human_fields(session, dci.id), await _human_fields(session, kci.id)
        for f in TEXT_FIELDS:
            dv, kv = (getattr(dci, f) or "").strip(), (getattr(kci, f) or "").strip()
            if not dv or dv == kv:
                continue
            if not kv:
                setattr(kci, f, getattr(dci, f))
                session.add(CulinaryInfoHistory(culinary_info_id=kci.id, field_name=f, old_value=None,
                                                new_value=getattr(dci, f),
                                                changed_by="human" if f in dh else changed_by,
                                                notes=f"{tag}: copied from {did}"))
                text_log.append((f, "copied from discard"))
                continue
            discard_wins = f in dh and f not in kh
            win, lose = (getattr(dci, f), getattr(kci, f)) if discard_wins else (getattr(kci, f), getattr(dci, f))
            if discard_wins:
                setattr(kci, f, win)
            session.add(CulinaryInfoHistory(
                culinary_info_id=kci.id, field_name=f, old_value=lose, new_value=win,
                changed_by="human" if (f in dh or f in kh) else changed_by,
                notes=f"{tag}: conflict — kept the {'human-edited ' + str(did) if discard_wins else str(kid)} "
                      f"text; old_value is the text not kept (from {kid if discard_wins else did})"))
            text_log.append((f, f"conflict, {'discard (human)' if discard_wins else 'keep'} wins"))
        for f in FILL_FIELDS:
            if getattr(kci, f) in (None, "") and getattr(dci, f) not in (None, ""):
                setattr(kci, f, getattr(dci, f))
        hist = await ids("SELECT id FROM culinary_info_history WHERE culinary_info_id = :c", c=dci.id)
        await session.execute(text("UPDATE culinary_info_history SET culinary_info_id = :k WHERE culinary_info_id = :c"),
                              {"k": kci.id, "c": dci.id})
        rep["moved"]["culinary_info_history"] = hist
        rep["culinary_info_deleted"] = dci.id
        await session.delete(dci)
    rep["text"] = text_log

    # ── species-row columns: fill keep's empties ────────────────────────────
    filled = []
    for f in SPECIES_FILL_FIELDS:
        if getattr(keep, f) in (None, "") and getattr(disc, f) not in (None, ""):
            setattr(keep, f, getattr(disc, f))
            filled.append(f)
    rep["species_fields_filled"] = filled

    # ── verdict ─────────────────────────────────────────────────────────────
    verdict, severity, verified = merged_verdict(keep, disc)
    rep["verdict_before"] = {"keep": (keep.edibility_status, keep.toxicity_severity, bool(keep.edibility_verified)),
                             "discard": (disc.edibility_status, disc.toxicity_severity, bool(disc.edibility_verified))}
    if (verdict, severity, verified) != (keep.edibility_status, keep.toxicity_severity, bool(keep.edibility_verified)):
        from app.api.edibility import _write_verdict
        _write_verdict(session, keep, verdict, True if verified else None, severity,
                       note=f"{tag}: more conservative verdict kept", changed_by="human" if verified else changed_by)
    rep["verdict_after"] = (keep.edibility_status, keep.toxicity_severity, bool(keep.edibility_verified))

    # ── walks & publications ────────────────────────────────────────────────
    walks = []
    for wid, wp in (await session.execute(text("SELECT id, waypoints_json FROM saved_walks"))).all():
        if wp and re.search(rf'"species_id"\s*:\s*{did}\b', wp):
            new = re.sub(rf'("species_id"\s*:\s*){did}\b', rf"\g<1>{kid}", wp)
            await session.execute(text("UPDATE saved_walks SET waypoints_json = :w WHERE id = :i"), {"w": new, "i": wid})
            walks.append(wid)
    rep["moved"]["saved_walks.waypoints_json"] = walks
    pubs = []
    for pid, ov, ps in (await session.execute(text(
            "SELECT id, overrides_json, public_species_json FROM experience_publications"))).all():
        changed = False
        if ov:
            try:
                o = json.loads(ov)
            except ValueError:
                o = None
            if isinstance(o, dict) and isinstance(o.get("hide_species_ids"), list):
                o["hide_species_ids"], c = _swap_ids(o["hide_species_ids"], did, kid)
                if c:
                    ov, changed = json.dumps(o, ensure_ascii=False), True
        if ps:
            try:
                p = json.loads(ps)
            except ValueError:
                p = None
            if isinstance(p, dict):
                for e in p.get("species") or []:
                    if isinstance(e, dict) and e.get("id") == did:
                        e["id"], changed = kid, True
                if changed:
                    ps = json.dumps(p, ensure_ascii=False)
        if changed:
            await session.execute(text("UPDATE experience_publications SET overrides_json = :o, "
                                       "public_species_json = :p WHERE id = :i"), {"o": ov, "p": ps, "i": pid})
            pubs.append(pid)
    rep["moved"]["experience_publications"] = pubs
    files = []
    if overrides_dir is not None and Path(overrides_dir).is_dir():
        for f in sorted(Path(overrides_dir).glob("*.json")):
            data = json.loads(f.read_text())
            if isinstance(data.get("hide_species_ids"), list):
                data["hide_species_ids"], c = _swap_ids(data["hide_species_ids"], did, kid)
                if c:
                    f.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
                    files.append(f.name)
    rep["moved"]["override_files"] = files

    # ── audit rows on keep, then delete discard ─────────────────────────────
    if kci is None:
        kci = await session.scalar(select(CulinaryInfo).where(CulinaryInfo.species_id == kid))
    if kci is not None:
        session.add(CulinaryInfoHistory(culinary_info_id=kci.id, field_name="_merge_event", old_value=None,
                                        new_value=f"Merged {did} '{dname}' into {kid} '{kname}'",
                                        changed_by=changed_by, notes=note or None))
    session.add(SpeciesEdibilityHistory(species_id=kid, field="_merge_event", old_value=f"{did} {dname}",
                                        new_value=f"{kid} {kname}", changed_by=changed_by, note=tag))
    await session.flush()
    left = {}
    for t in REKEY_TABLES + tuple(DEDUPE_TABLES) + ("culinary_info",):
        n = (await session.execute(text(f"SELECT count(*) FROM {t} WHERE species_id = :d"), {"d": did})).scalar()
        if n:
            left[t] = n
    for col in ("species_id",):
        n = (await session.execute(text(f"SELECT count(*) FROM observations WHERE {col} = :d"), {"d": did})).scalar()
        if n:
            left["observations"] = n
    if left:
        raise RuntimeError(f"merge {did}→{kid}: rows still keyed to the discard card: {left}")
    await session.delete(disc)
    await session.flush()
    rep["deleted"] = did
    return rep
