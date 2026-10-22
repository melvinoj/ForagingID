"""
hazard_archive_report.py — READ-ONLY archive report (Melvin, 22 Oct 2026,
after foxglove #24507).

Every approved / manually_verified observation whose stored candidates name a
hazard species (app/services/hazard_candidates.py — the same predicate the
auto-approve guard, Review's Critical section and the second-tap approve use)
but which is confirmed as a DIFFERENT species.

Sources read per observation:
  * PlantNet's raw result list (plantnet_raw_json, PlantNet's own order)
  * the stored merged candidate list (species_candidates_json — PlantNet and
    iNaturalist, with iNat's own rank recomputed from its combined score)
  * every earlier identification run (species_candidates table, append-only)

Writes nothing to the DB. Output: markdown to stdout, or to --out.

    PYTHONPATH=. python scripts/hazard_archive_report.py --out HAZARD_ARCHIVE_REPORT_2026-10-22.md
"""
import argparse
import asyncio
from collections import defaultdict
from datetime import datetime

from sqlalchemy import select

from app.api.walk import walk_membership_for
from app.database import AsyncSessionLocal
from app.models.observation import Observation
from app.models.species import SpeciesCandidate
from app.models.walk import SavedWalk
from app.services.hazard_candidates import (hazard_hits, hazards_other_than, load_hazard_index,
                                            observation_entries)


def _pct(v):
    return f"{v * 100:.2f}%" if isinstance(v, (int, float)) else "—"


async def collect() -> dict:
    """The report's rows, shared with scripts/make_hazard_sheets.py:
    rows = [(Observation, hazard hits other than its species)] in report order
    (deadly first, strongest hazard score first), walk_of = obs id → ["<id>
    <name> (stop N)"], walk_ids = obs id → [walk id], index = the HazardIndex."""
    async with AsyncSessionLocal() as db:
        index = await load_hazard_index(db)
        obs_rows = (await db.execute(select(Observation).where(
            Observation.review_status.in_(["approved", "manually_verified"])))).scalars().all()
        hist = defaultdict(list)
        for oid, name, src, score, rank in (await db.execute(select(
                SpeciesCandidate.observation_id, SpeciesCandidate.scientific_name_raw,
                SpeciesCandidate.api_source, SpeciesCandidate.confidence_score,
                SpeciesCandidate.rank))).all():
            # Older runs stored iNat confidence as 0–100; the report shows 0–1.
            if isinstance(score, (int, float)) and score > 1:
                score = score / 100.0
            hist[oid].append({"name": name, "source": f"{src} (run history)", "score": score, "rank": rank})

        hits_by_obs = {}
        for o in obs_rows:
            hits = hazard_hits(observation_entries(o) + hist.get(o.id, []), index)
            others = hazards_other_than(hits, o.species_primary, o.species_id, index)
            if others:
                hits_by_obs[o.id] = (o, others)

        walk_of, walk_ids = defaultdict(list), defaultdict(list)
        for w in (await db.execute(select(SavedWalk).order_by(SavedWalk.id))).scalars().all():
            mem = await walk_membership_for(db, w)
            for st in mem["stops"]:
                for sp in st["species"]:
                    for oid in sp["obs_ids"]:
                        if oid in hits_by_obs:
                            walk_of[oid].append(f"{w.id} {w.name} (stop {st['label']})")
                            if w.id not in walk_ids[oid]:
                                walk_ids[oid].append(w.id)

    def _top(hits):
        return max((s["score"] or 0) for h in hits for s in h["sources"]
                   if isinstance(s["score"], (int, float)) or s["score"] is None)
    # Deadly first, then the strongest hazard score (any source) first.
    rows = sorted(hits_by_obs.values(),
                  key=lambda t: (t[1][0]["level"] != "deadly", -_top(t[1]), t[0].id))
    return {"rows": rows, "walk_of": walk_of, "walk_ids": walk_ids, "index": index}


async def build() -> str:
    c = await collect()
    rows, walk_of, index = c["rows"], c["walk_of"], c["index"]
    n_deadly = sum(1 for _, h in rows if h[0]["level"] == "deadly")
    n_walk = sum(1 for o, _ in rows if walk_of.get(o.id))
    # AI only = approved with no reviewed_at (every human approve path stamps it).
    n_ai = sum(1 for o, _ in rows if o.review_status == "approved" and o.reviewed_at is None)
    out = [
        f"# Hazard-candidate archive report — {datetime.now():%Y-%m-%d %H:%M} (local)",
        "",
        "Read-only. Approved / manually_verified observations whose candidates (any source, any rank,"
        " any earlier run) name a hazard species (severity toxic/deadly or verdict toxic), confirmed as"
        " a different species. Nothing was changed.",
        "",
        f"- Observations: **{len(rows)}** (deadly candidate: {n_deadly}; on a saved walk: {n_walk};"
        f" confirmed species itself a hazard species, marked ☠: {sum(1 for o, _ in rows if index.resolve(o.species_primary))};"
        f" AI-approved only, no human review: {n_ai})",
        "- Score = that source's own score for the hazard species (PlantNet raw; iNat = min(vision, combined));"
        " rank = that source's own rank.",
        "",
        "| # | Status | Confirmed as | Hazard candidate(s) — source, score, rank | Thumbnail | Walk |",
        "|---|---|---|---|---|---|",
    ]
    for o, hits in rows:
        hz = "<br>".join(
            f"☠ {h['label']} ({h['level']}): " + "; ".join(
                f"{s['source']} {_pct(s['score'])}" + (f" #{s['rank']}" if s['rank'] else "")
                for s in h["sources"])
            for h in hits)
        status = o.review_status + (" (AI only)" if o.review_status == "approved" and o.reviewed_at is None else "")
        own = index.resolve(o.species_primary)
        confirmed = (o.species_primary or "— (scene)") + (f" ☠ ({own.level})" if own else "")
        out.append(f"| {o.id} | {status} | {confirmed} | {hz} | "
                   f"{o.thumbnail_path or '—'} | {'<br>'.join(walk_of.get(o.id, [])) or '—'} |")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    a = ap.parse_args()
    text = asyncio.run(build())
    if a.out:
        with open(a.out, "w") as f:
            f.write(text)
        print(f"wrote {a.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
