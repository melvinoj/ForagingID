"""
EMA herbal monograph → medicinal_clinical tag adapter.

Deterministic, no LLM. Structured copy only.
Source: docs/Medicines_output_herbal_medicines_en.json
"""
import json
import logging
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.culinary import CulinaryInfo
from app.models.species import CulinaryInfoHistory

log = logging.getLogger(__name__)

EMA_SOURCE_FILE = Path(__file__).parent.parent.parent / "docs" / "Medicines_output_herbal_medicines_en.json"

# EMA binomial → DB scientific_name. Only manually-curated entries allowed here.
SYNONYMS: dict[str, str] = {
    "Matricaria recutita": "Matricaria chamomilla",
    "Tilia vulgaris": "Tilia × europaea",
    "Rhamnus frangula": "Frangula alnus",
    "Hieracium pilosella": "Pilosella officinarum",
    "Plantago indica": "Plantago arenaria",
    "Rhamnus purshianus": "Frangula purshiana",
    "Viola vulgaris": "Viola reichenbachiana",
}

# EMA binomials reviewed and dismissed — genus match exists but species is not in DB
# and is not a synonym of any existing card. Suppresses noise in dry_run output.
DISMISSED_BINOMIALS: frozenset[str] = frozenset({
    "Allium sativum",
    "Epilobium parviflorum",
    "Fragaria ananassa",
    "Fragaria moschata",
    "Fragaria viridis",
    "Ilex paraguariensis",
    "Malva neglecta",
    "Malva sylvestris",
    "Origanum dictamnus",
    "Origanum majorana",
    "Plantago afra",
    "Primula veris",
    "Rosa centifolia",
    "Rosa damascena",
    "Rosa gallica",
    "Solidago virgaurea",
    "Thymus zygis",
    "Tilia platyphyllos",
    "Urtica urens",
    "Vaccinium macrocarpon",
    "Viola arvensis",
    "Viola tricolor",
})

# Traditional Latin organ token → English label
ORGAN: dict[str, str] = {
    "folium": "Leaf",
    "radix": "Root",
    "herba": "Aerial parts",
    "flos": "Flower",
    "fructus": "Fruit",
    "cortex": "Bark",
    "rhizoma": "Rhizome",
    "semen": "Seed",
    "summitas": "Flowering tops",
}


# ── Data loading ──────────────────────────────────────────────────────────────

def _load_finalised_monographs() -> list[dict]:
    """
    Load EMA JSON and return records where:
      - outcome_of_european_assessment contains 'European Union herbal monograph'
      - status == 'F: Assessment finalised'
    Deduped by (latin_name, herbal_medicine_url).
    """
    with open(EMA_SOURCE_FILE) as f:
        records = json.load(f)["data"]
    seen: set[tuple] = set()
    result: list[dict] = []
    for r in records:
        if (
            "European Union herbal monograph" not in r.get("outcome_of_european_assessment", "")
            or r.get("status", "") != "F: Assessment finalised"
            or r.get("combination", "") != "No"
        ):
            continue
        key = (r["latin_name"], r["herbal_medicine_url"])
        if key in seen:
            continue
        seen.add(key)
        result.append(r)
    return result


# ── Binomial extraction ───────────────────────────────────────────────────────

def _extract_binomials(botanical_name: str) -> list[str]:
    """
    Extract genus+species from a possibly multi-species botanical_name field.

    Handles:
    - Semicolon-separated multi-species strings
    - No-space-before-authority bug (e.g. 'Fragaria vescaL.' → 'Fragaria vesca')
    - Hybrid markers (Genus x epithet)
    - 'various' skipping
    """
    results: list[str] = []
    for part in botanical_name.split(";"):
        part = part.strip()
        if not part:
            continue
        # Fix: lowercase letter directly followed by uppercase or '(' — insert space
        fixed = re.sub(r"([a-z])([A-Z(])", r"\1 \2", part)
        tokens = fixed.split()
        if len(tokens) < 2:
            continue
        genus = tokens[0]
        if not genus or not genus[0].isupper():
            continue
        idx = 1
        if tokens[idx].lower() == "x" and len(tokens) > idx + 1:
            species = tokens[idx + 1]
        else:
            species = tokens[idx]
        if not species or not species[0].islower():
            continue
        if species.lower() == "various":
            continue
        results.append(f"{genus} {species}")
    return list(dict.fromkeys(results))  # dedupe, preserve order


# ── Chip construction ─────────────────────────────────────────────────────────

def _part_for(latin_name: str) -> Optional[str]:
    """
    Find the first recognised organ token in the traditional Latin medicine name.
    Splits on whitespace AND semicolons so that combination-product latin_names
    (e.g. 'Hyperici herba;Cimicifugae rhizoma') resolve to the first herb's organ.
    """
    tokens = re.split(r"[\s;,]+", latin_name.lower())
    for tok in tokens:
        clean = tok.strip("()")
        if clean in ORGAN:
            return ORGAN[clean]
    return None


def _chip_for(record: dict) -> dict:
    part = _part_for(record["latin_name"])
    areas = ", ".join(a.strip() for a in record["therapeutic_area"].split(";") if a.strip())
    label = f"{part} — {areas}" if part else areas
    return {
        "label": label,
        "source": "EMA herbal monograph",
        "url": record["herbal_medicine_url"],
    }


# ── Matching ──────────────────────────────────────────────────────────────────

def build_chip_plan(
    db_species: list[tuple[int, str]],
) -> tuple[dict[int, list[dict]], list[dict], list[dict], list[dict]]:
    """
    Match finalised EMA monographs against DB species.

    Matching rules (in order):
      1. Exact binomial match against species.scientific_name
      2. SYNONYMS map (EMA binomial → DB name), curated manually only
      3. DISMISSED_BINOMIALS → known non-matches, logged but never written
      4. Genus-only match → collected as new_candidates, needing review

    Returns:
      chip_plan: {species_id: [chip_dict, ...]}
      resolved_synonyms: [{ema_binomial, db_name, status}, ...] — SYNONYMS entries that resolved
      dismissed: [{ema_binomial, ema_latin_name}, ...] — reviewed and dismissed
      new_candidates: [{ema_binomial, ema_latin_name, db_genus_matches, url}, ...] — need review
    """
    monographs = _load_finalised_monographs()

    exact_map: dict[str, int] = {sname: sid for sid, sname in db_species}
    genus_map: dict[str, list[str]] = defaultdict(list)
    for _sid, sname in db_species:
        parts = sname.split()
        if len(parts) >= 2:
            genus_map[parts[0]].append(sname)

    chip_plan: dict[int, list[dict]] = defaultdict(list)
    resolved_synonyms: list[dict] = []
    dismissed: list[dict] = []
    new_candidates: list[dict] = []
    seen_candidates: set[tuple] = set()

    for rec in monographs:
        binomials = _extract_binomials(rec["botanical_name"])
        if not binomials:
            log.debug("[EMA] No binomial extracted from %r (latin: %r)", rec["botanical_name"], rec["latin_name"])
            continue

        for binom in binomials:
            if binom in exact_map:
                chip_plan[exact_map[binom]].append(_chip_for(rec))
            elif binom in SYNONYMS:
                db_name = SYNONYMS[binom]
                if db_name in exact_map:
                    chip_plan[exact_map[db_name]].append(_chip_for(rec))
                    resolved_synonyms.append({"ema_binomial": binom, "db_name": db_name, "status": "resolved"})
                else:
                    log.warning("[EMA] Synonym %r → %r not found in DB", binom, db_name)
                    resolved_synonyms.append({"ema_binomial": binom, "db_name": db_name, "status": "target_absent"})
            elif binom in DISMISSED_BINOMIALS:
                cand_key = (binom, rec["latin_name"])
                if cand_key not in seen_candidates:
                    seen_candidates.add(cand_key)
                    dismissed.append({"ema_binomial": binom, "ema_latin_name": rec["latin_name"]})
            else:
                genus = binom.split()[0]
                if genus in genus_map:
                    cand_key = (binom, rec["latin_name"])
                    if cand_key not in seen_candidates:
                        seen_candidates.add(cand_key)
                        new_candidates.append({
                            "ema_binomial": binom,
                            "ema_latin_name": rec["latin_name"],
                            "db_genus_matches": sorted(genus_map[genus]),
                            "url": rec["herbal_medicine_url"],
                        })

    return dict(chip_plan), resolved_synonyms, dismissed, new_candidates


# ── Write rules ───────────────────────────────────────────────────────────────

async def _is_human_locked(session: AsyncSession, ci_id: int) -> bool:
    """True if any changed_by='human' row exists for medicinal_clinical on this CulinaryInfo."""
    result = await session.scalar(
        select(CulinaryInfoHistory.id)
        .where(CulinaryInfoHistory.culinary_info_id == ci_id)
        .where(CulinaryInfoHistory.field_name == "medicinal_clinical")
        .where(CulinaryInfoHistory.changed_by == "human")
    )
    return result is not None


# ── Dry run ───────────────────────────────────────────────────────────────────

async def dry_run(
    session: AsyncSession,
    db_species: list[tuple[int, str]],
) -> dict:
    """
    Run matching and write-rule checks without touching the DB.

    Returns a report dict with:
      would_write: [(species_id, scientific_name, [chip_dict, ...])]
      skipped_populated: int
      skipped_human_lock: int
      synonym_candidates: [...]
    """
    chip_plan, resolved_synonyms, dismissed, new_candidates = build_chip_plan(db_species)
    id_to_name = {sid: sname for sid, sname in db_species}

    would_write: list[tuple[int, str, list[dict]]] = []
    skipped_populated = 0
    skipped_human_lock = 0

    for sid, chips in sorted(chip_plan.items(), key=lambda kv: id_to_name.get(kv[0], "")):
        sname = id_to_name.get(sid, f"<id={sid}>")

        ci = await session.scalar(
            select(CulinaryInfo).where(CulinaryInfo.species_id == sid)
        )
        if ci is None:
            log.debug("[EMA dry_run] No culinary_info row for species %s (%s) — skipping", sid, sname)
            continue

        # Rule 1: skip if medicinal_clinical already non-empty
        if ci.medicinal_clinical and ci.medicinal_clinical.strip():
            skipped_populated += 1
            log.debug("[EMA dry_run] Skip %r — medicinal_clinical already populated", sname)
            continue

        # Rule 2: skip if human-locked
        if await _is_human_locked(session, ci.id):
            skipped_human_lock += 1
            log.debug("[EMA dry_run] Skip %r — medicinal_clinical human-locked", sname)
            continue

        would_write.append((sid, sname, chips))

    return {
        "would_write": would_write,
        "skipped_populated": skipped_populated,
        "skipped_human_lock": skipped_human_lock,
        "resolved_synonyms": resolved_synonyms,
        "dismissed": dismissed,
        "new_candidates": new_candidates,
    }


# ── Commit ────────────────────────────────────────────────────────────────────

async def commit(
    session: AsyncSession,
    db_species: list[tuple[int, str]],
) -> dict:
    """
    Apply EMA clinical tags to DB. Idempotent — skips already-populated and
    human-locked species. Records changed_by='ema' provenance in history.

    Do NOT call this without running dry_run first and reviewing the output.
    """
    chip_plan, _, _, _ = build_chip_plan(db_species)
    id_to_name = {sid: sname for sid, sname in db_species}

    written = 0
    skipped_populated = 0
    skipped_human_lock = 0
    skipped_no_ci = 0

    for sid, chips in chip_plan.items():
        sname = id_to_name.get(sid, f"<id={sid}>")

        ci = await session.scalar(
            select(CulinaryInfo).where(CulinaryInfo.species_id == sid)
        )
        if ci is None:
            skipped_no_ci += 1
            continue

        if ci.medicinal_clinical and ci.medicinal_clinical.strip():
            skipped_populated += 1
            continue

        if await _is_human_locked(session, ci.id):
            skipped_human_lock += 1
            continue

        old_value = ci.medicinal_clinical
        ci.medicinal_clinical = json.dumps(chips)
        session.add(CulinaryInfoHistory(
            culinary_info_id=ci.id,
            field_name="medicinal_clinical",
            old_value=old_value,
            new_value=ci.medicinal_clinical,
            changed_at=datetime.utcnow(),
            changed_by="ema",
            notes=f"EMA adapter: {len(chips)} chip(s) from herbal monograph",
        ))
        log.info("[EMA commit] Wrote %d chip(s) for %r", len(chips), sname)
        written += 1

    return {
        "written": written,
        "skipped_populated": skipped_populated,
        "skipped_human_lock": skipped_human_lock,
        "skipped_no_ci": skipped_no_ci,
    }
