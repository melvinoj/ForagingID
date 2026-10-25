"""
hazard_candidates.py — "did any identification source name a hazard species
for this photo?" (Melvin, 22 Oct 2026, after foxglove #24507 was proposed as
Pentanema squarrosum at 90.4% with Digitalis only in the grey "Also:" line).

ONE rule, used everywhere:
  a candidate from ANY source — PlantNet's raw result list (before regional
  demotion), iNaturalist's list, and the stored merged candidate list — that
  resolves to a species card (exact name, name_key, or a registered synonym)
  which is_hazard_species() (severity toxic/deadly OR verdict toxic) makes the
  observation a hazard case, at any rank and any score.

A hazard case can never auto-approve, at any rank (scan._identify_scanned /
decide_agreement — every hit, hazard_hits()).

Tiers (Melvin, 22 Oct 2026 evening — cut the noise, keep human decisions):
  * GATE — a hazard candidate within the top GATE_TOP_RANK of any source, or
    scoring >= GATE_MIN_SCORE in any source (hit["gate"]). On a card no human
    has decided (gating_hazards()): red ☠ line by name on the review card,
    a second explicit tap naming it to approve as any OTHER species
    (hazard_ack — require_hazard_ack(), server-side backstop), never
    bulk-approved / bulk-confirmed, listed by Review's "Hazard candidates"
    status filter.
  * DEEP — named lower than that: one grey "Also listed deep in …" line on the
    card (deep_hazards()), no gate.
  * A human decision stands: a photo a human has decided (manually_verified,
    human-approved, rejected — is_undecided_by_human() False) gets no red line
    and no gate; the rule never reopens or re-flags it.

Read-only: builds an index from species / species_synonyms and inspects
candidate lists. Never writes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.species import (Species, SpeciesSynonym, display_common_name,
                                hazard_level, is_hazard_species)
from app.services.taxonomy import normalize_taxon_key


@dataclass(frozen=True)
class HazardSpecies:
    species_id: int
    scientific_name: str
    common: Optional[str]
    level: str                      # 'deadly' | 'toxic'

    @property
    def label(self) -> str:
        """'Foxglove (Digitalis purpurea)' — or the scientific name alone."""
        return f"{self.common} ({self.scientific_name})" if self.common else self.scientific_name


@dataclass
class HazardIndex:
    by_key: Dict[str, HazardSpecies] = field(default_factory=dict)

    def resolve(self, name: Optional[str]) -> Optional[HazardSpecies]:
        if not name:
            return None
        return self.by_key.get(normalize_taxon_key(name))


async def load_hazard_index(session: AsyncSession) -> HazardIndex:
    """Every hazard species card under its name_key, its exact scientific name's
    key, and every registered synonym that points at it."""
    rows = (await session.execute(select(
        Species.id, Species.scientific_name, Species.name_key,
        Species.preferred_common_name, Species.common_names,
        Species.toxicity_severity, Species.edibility_status,
    ))).all()
    idx = HazardIndex()
    by_id: Dict[int, HazardSpecies] = {}
    for sid, sci, key, pref, commons, sev, verdict in rows:
        if not is_hazard_species(sev, verdict):
            continue
        hs = HazardSpecies(
            species_id=sid, scientific_name=sci,
            common=display_common_name(pref, commons) or None,
            level=hazard_level(sev, verdict),
        )
        by_id[sid] = hs
        for k in {key, normalize_taxon_key(sci or "")}:
            if k:
                idx.by_key[k] = hs
    syn = (await session.execute(select(
        SpeciesSynonym.synonym_name_key, SpeciesSynonym.canonical_species_id))).all()
    for k, sid in syn:
        if k and sid in by_id:
            idx.by_key.setdefault(k, by_id[sid])
    return idx


# ── Candidate collectors ─────────────────────────────────────────────────────
# Each yields dicts {name, source, score, rank}. Scores are 0–1.

def plantnet_raw_entries(raw: Optional[dict]) -> List[dict]:
    """PlantNet's own result list, in PlantNet's own order (before demotion)."""
    out = []
    for i, r in enumerate((raw or {}).get("results") or []):
        sp = r.get("species") or {}
        name = sp.get("scientificNameWithoutAuthor") or sp.get("scientificName")
        if name:
            out.append({"name": name, "source": "plantnet", "score": r.get("score"), "rank": i + 1})
    return out


def inat_hit_entries(hits: Sequence) -> List[dict]:
    """iNaturalist hits (INatCandidate objects or (name, score) pairs), iNat's order."""
    out = []
    for i, h in enumerate(hits or []):
        if isinstance(h, (tuple, list)):
            name, score = h[0], h[1]
            vision = None
        else:
            name, score, vision = h.scientific_name, h.score, getattr(h, "vision_score", None)
        if name:
            out.append({"name": name, "source": "inaturalist", "score": score,
                        "vision_score": vision, "rank": i + 1})
    return out


def stored_candidate_entries(species_candidates_json: Optional[str]) -> List[dict]:
    """The stored merged list. An entry carrying iNat scores was also named by
    iNat, so it is reported once per source that named it."""
    try:
        cands = json.loads(species_candidates_json or "[]") or []
    except (TypeError, ValueError):
        return []
    out, inat = [], []
    for c in cands:
        if not isinstance(c, dict) or not c.get("scientific_name"):
            continue
        name = c["scientific_name"]
        src = c.get("source") or "unknown"
        if src != "inaturalist":
            out.append({"name": name, "source": src,
                        "score": c.get("listed_score", c.get("score")),
                        "rank": c.get("pn_raw_rank") or c.get("rank")})
        v, cb = c.get("inat_vision_score"), c.get("inat_combined_score")
        if src == "inaturalist" or v is not None or cb is not None:
            known = [x for x in (v, cb) if x is not None]
            inat.append({"name": name, "source": "inaturalist",
                         "score": min(known) if known else c.get("score"),
                         "combined": cb if cb is not None else (v if v is not None else c.get("score"))})
    # iNat's own rank: inaturalist.score_image orders by the combined score.
    inat.sort(key=lambda e: -(e["combined"] or 0))
    for i, e in enumerate(inat):
        out.append({"name": e["name"], "source": "inaturalist", "score": e["score"], "rank": i + 1})
    return out


def observation_entries(obs) -> List[dict]:
    """Every candidate stored on an observation row (ORM row or dict)."""
    get = (obs.get if isinstance(obs, dict) else lambda k: getattr(obs, k, None))
    raw = get("plantnet_raw_json")
    try:
        raw = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except ValueError:
        raw = {}
    return plantnet_raw_entries(raw) + stored_candidate_entries(get("species_candidates_json"))


# ── The predicate ────────────────────────────────────────────────────────────

GATE_TOP_RANK = 3          # top 3 of any source …
GATE_MIN_SCORE = 0.05      # … or >= 5% in any source (scores are 0–1)


def entry_gates(e: dict) -> bool:
    """Is this one source's listing high enough to gate (GATE tier)?"""
    rank, score = e.get("rank"), e.get("score")
    try:
        if rank is not None and int(rank) <= GATE_TOP_RANK:
            return True
    except (TypeError, ValueError):
        pass
    try:
        return score is not None and float(score) >= GATE_MIN_SCORE
    except (TypeError, ValueError):
        return False


def hazard_hits(entries: Iterable[dict], index: HazardIndex) -> List[dict]:
    """One hit per hazard species (deadly first), with every source that named
    it. Empty list = no hazard. hit["gate"]: any listing of it, in any source,
    is in the GATE tier (entry_gates)."""
    found: Dict[int, dict] = {}
    for e in entries:
        hs = index.resolve(e.get("name"))
        if hs is None:
            continue
        hit = found.setdefault(hs.species_id, {
            "species_id": hs.species_id, "scientific_name": hs.scientific_name,
            "common": hs.common, "level": hs.level, "label": hs.label, "sources": [],
            "gate": False,
        })
        hit["gate"] = hit["gate"] or entry_gates(e)
        # One entry per source; the first seen wins (collectors put the raw
        # lists first, so PlantNet's unrounded raw score is the one kept).
        if any(s["source"] == e.get("source") for s in hit["sources"]):
            continue
        hit["sources"].append({"source": e.get("source"), "name": e.get("name"),
                               "score": e.get("score"), "rank": e.get("rank")})
    return sorted(found.values(), key=lambda h: (h["level"] != "deadly", h["scientific_name"]))


def observation_hazards(obs, index: HazardIndex) -> List[dict]:
    """Every hazard hit, any tier, decided or not (archive report)."""
    return hazard_hits(observation_entries(obs), index)


def gating_hazards(obs, index: HazardIndex) -> List[dict]:
    """The hits that gate THIS card: GATE tier, and only while no human has
    decided the photo. The red line, the second tap, bulk skips, the publish
    panel and Review's "Hazard candidates" filter all read this."""
    if not is_undecided_by_human(obs):
        return []
    return [h for h in observation_hazards(obs, index) if h["gate"]]


def deep_hazards(obs, index: HazardIndex) -> List[dict]:
    """DEEP tier hits for the card's grey "Also listed deep in …" line (no
    gate). Empty for a photo a human has decided."""
    if not is_undecided_by_human(obs):
        return []
    return [h for h in observation_hazards(obs, index) if not h["gate"]]


def hazards_other_than(hits: Sequence[dict], approving_name: Optional[str],
                       approving_species_id: Optional[int], index: HazardIndex) -> List[dict]:
    """Hazard hits that are NOT the species being approved — approving AS the
    hazard species is not 'approving with another species'."""
    own = index.resolve(approving_name)
    skip = {approving_species_id, own.species_id if own else None} - {None}
    return [h for h in hits if h["species_id"] not in skip]


def require_hazard_ack(hits: Sequence[dict], approving_name: Optional[str],
                       approving_species_id: Optional[int], index: HazardIndex,
                       hazard_ack: Optional[str]) -> None:
    """Server-side backstop for the second tap: approving as another species
    needs hazard_ack naming every other hazard species (comma-separated
    scientific names). Raises 409 {code: hazard_ack_required, hazards: [...]}."""
    others = hazards_other_than(hits, approving_name, approving_species_id, index)
    if not others:
        return
    acked = {normalize_taxon_key(n) for n in (hazard_ack or "").split(",") if n.strip()}
    missing = [h for h in others if normalize_taxon_key(h["scientific_name"]) not in acked]
    if missing:
        raise HTTPException(status_code=409, detail={
            "code": "hazard_ack_required",
            "message": ("☠ " + "; ".join(h["label"] for h in missing)
                        + " was a candidate for this photo. Approving as "
                        + (approving_name or "this species") + " needs a second tap naming it."),
            "approving": approving_name,
            "hazards": [{"scientific_name": h["scientific_name"], "label": h["label"],
                         "level": h["level"]} for h in missing],
        })


# ── Review's "Hazard candidates" filter ─────────────────────────────────────

def is_undecided_by_human(obs) -> bool:
    """Still waiting for a human: in the queue (pending / needs_review), or
    approved by the pipeline only (approved with no reviewed_at — every human
    approve path stamps it; see is_human_confirmed). manually_verified and
    rejected are human decisions."""
    get = (obs.get if isinstance(obs, dict) else lambda k: getattr(obs, k, None))
    st = get("review_status")
    if st in ("pending", "needs_review"):
        return True
    return st == "approved" and get("reviewed_at") is None


async def undecided_hazard_items(session: AsyncSession) -> List[dict]:
    """Every observation no human has decided with a GATE-tier hazard
    candidate (gating_hazards) — deadly first. Read-only. Backs Review's
    "Hazard candidates" status filter."""
    from pathlib import Path
    from sqlalchemy import and_, or_
    from app.models.observation import Observation

    index = await load_hazard_index(session)
    rows = (await session.execute(
        select(Observation.id, Observation.species_candidates_json, Observation.plantnet_raw_json,
               Observation.review_status, Observation.reviewed_at, Observation.species_primary,
               Observation.species_suggested, Observation.thumbnail_path)
        .where(or_(Observation.review_status.in_(["pending", "needs_review"]),
                   and_(Observation.review_status == "approved", Observation.reviewed_at.is_(None))))
    )).all()
    items = []
    for oid, cj, pj, st, rv, sp, sug, thumb in rows:
        d = {"species_candidates_json": cj, "plantnet_raw_json": pj,
             "review_status": st, "reviewed_at": rv}
        if not is_undecided_by_human(d):
            continue
        hits = gating_hazards(d, index)
        if not hits:
            continue
        name = Path(thumb).name if thumb else None
        items.append({
            "obs_id": oid, "proposed": sp or sug, "review_status": st,
            "ai_approved": st == "approved",
            "hazards": hits, "level": hits[0]["level"],
            "thumbnail": f"/thumbnails/{name}" if name else None,
        })
    items.sort(key=lambda i: (i["level"] != "deadly", -i["obs_id"]))
    return items


async def check_hazard_ack(session: AsyncSession, obs, approving_name: Optional[str],
                           approving_species_id: Optional[int], hazard_ack: Optional[str]) -> None:
    """require_hazard_ack() for one observation row — called by the shared
    approve helper (observation_service.update_observation_status) and by
    retry-confirm, before any write. GATE tier only, and never on a photo a
    human has already decided (gating_hazards)."""
    index = await load_hazard_index(session)
    require_hazard_ack(gating_hazards(obs, index), approving_name,
                       approving_species_id, index, hazard_ack)
