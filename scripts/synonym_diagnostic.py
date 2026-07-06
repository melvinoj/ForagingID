"""
EMA synonym candidate diagnostic.
Classifies each candidate using the deterministic cascade:
  1. RESOLVED_BY_NAME_KEY — normalize_taxon_key matches existing species
  2. AUTONYM_SUBSPECIES — collapse_autonym resolves to existing species
  3. CROSS_GENUS_SYNONYM / SAME_GENUS_SYNONYM — ITIS/GBIF accepted name matches existing card
  4. SYNONYM_TO_ABSENT — ITIS/GBIF gives accepted name but no matching card
  5. NO_DB_MATCH — neither authority resolves it

Read-only: no DB writes, no SYNONYMS map changes.
"""

import asyncio
import csv
import json
import re
import sys
import time
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.taxonomy import normalize_taxon_key, collapse_autonym

# Inline the pure functions from ema_clinical to avoid SQLAlchemy imports
EMA_SOURCE_FILE = PROJECT_ROOT / "docs" / "Medicines_output_herbal_medicines_en.json"


def _load_finalised_monographs() -> list:
    with open(EMA_SOURCE_FILE) as f:
        records = json.load(f)["data"]
    seen: set = set()
    result: list = []
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


def _extract_binomials(botanical_name: str) -> list:
    results: list = []
    for part in botanical_name.split(";"):
        part = part.strip()
        if not part:
            continue
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
    return list(dict.fromkeys(results))


SYNONYMS: dict = {
    "Matricaria recutita": "Matricaria chamomilla",
}

# ITIS + GBIF config
ITIS_BASE = "https://www.itis.gov/ITISWebService/jsonservice"
ITIS_TIMEOUT = 15.0
GBIF_SPECIES_URL = "https://api.gbif.org/v1/species"
GBIF_MATCH_URL = "https://api.gbif.org/v1/species/match"
GBIF_TIMEOUT = 10.0
DELAY_BETWEEN_CALLS = 0.5  # seconds


@dataclass
class LookupResult:
    status: str = ""  # "accepted", "synonym", "no_match", "error"
    accepted_name: Optional[str] = None
    matches_existing: bool = False
    error: Optional[str] = None


@dataclass
class CandidateRow:
    ema_binomial: str
    name_key: str
    matching_species: str = "—"
    collapsed_form: str = "—"
    itis_status: str = "—"
    itis_accepted: str = "—"
    itis_matches_existing: str = "—"
    gbif_accepted: str = "—"
    gbif_matches_existing: str = "—"
    bucket: str = ""


async def itis_lookup(name: str) -> LookupResult:
    """Query ITIS for accepted name."""
    try:
        async with httpx.AsyncClient(timeout=ITIS_TIMEOUT) as client:
            resp = await client.get(
                f"{ITIS_BASE}/searchByScientificName",
                params={"srchKey": name},
            )
            if resp.status_code != 200:
                return LookupResult(status="error", error=f"HTTP {resp.status_code}")
            data = resp.json()
            names = data.get("scientificNames") or []
            hits = [n for n in names if n and n.get("tsn")]
            if not hits:
                return LookupResult(status="no_match")

            # Find exact match
            q_parts = name.strip().lower().split()
            hit = None
            for h in hits:
                cn = (h.get("combinedName") or "").strip().lower().split()
                if len(cn) >= len(q_parts) and " ".join(cn[:len(q_parts)]) == " ".join(q_parts):
                    hit = h
                    break
            if not hit:
                for h in hits:
                    u1 = (h.get("unitName1") or "").strip().lower()
                    u2 = (h.get("unitName2") or "").strip().lower()
                    combined = f"{u1} {u2}".strip() if u2 else u1
                    if combined == " ".join(q_parts):
                        hit = h
                        break
            if not hit:
                return LookupResult(status="no_match")

            tsn = int(hit["tsn"])

            # Get accepted names
            resp2 = await client.get(
                f"{ITIS_BASE}/getAcceptedNamesFromTSN",
                params={"tsn": str(tsn)},
            )
            if resp2.status_code != 200:
                return LookupResult(status="error", error=f"accepted HTTP {resp2.status_code}")
            data2 = resp2.json()
            acc_names = data2.get("acceptedNames") or []
            acc_names = [n for n in acc_names if n and (n.get("acceptedName") or n.get("completeName"))]

            if not acc_names:
                return LookupResult(status="accepted", accepted_name=name)

            acc = acc_names[0]
            raw = (acc.get("acceptedName") or acc.get("completeName") or "").strip()
            parts = raw.split()
            accepted = f"{parts[0]} {parts[1]}" if len(parts) >= 2 else raw

            acc_tsn = acc.get("acceptedTsn") or acc.get("tsn")
            if acc_tsn and int(str(acc_tsn)) == tsn:
                return LookupResult(status="accepted", accepted_name=name)

            return LookupResult(status="synonym", accepted_name=accepted)

    except Exception as e:
        return LookupResult(status="error", error=str(e)[:60])


async def gbif_lookup(name: str) -> LookupResult:
    """Query GBIF species/match for accepted name."""
    try:
        async with httpx.AsyncClient(timeout=GBIF_TIMEOUT) as client:
            resp = await client.get(
                GBIF_MATCH_URL,
                params={"name": name, "strict": "true"},
            )
            if resp.status_code != 200:
                return LookupResult(status="error", error=f"HTTP {resp.status_code}")
            data = resp.json()

            match_type = data.get("matchType", "NONE")
            if match_type == "NONE":
                return LookupResult(status="no_match")

            status = (data.get("status") or "").upper()
            canonical = data.get("canonicalName") or data.get("species") or ""

            if status == "SYNONYM":
                # The accepted name is in the "species" field or we need to follow the acceptedUsageKey
                accepted_key = data.get("acceptedUsageKey")
                if accepted_key:
                    resp2 = await client.get(f"{GBIF_SPECIES_URL}/{accepted_key}")
                    if resp2.status_code == 200:
                        acc_data = resp2.json()
                        accepted = acc_data.get("canonicalName") or acc_data.get("species") or ""
                        if accepted:
                            return LookupResult(status="synonym", accepted_name=accepted)
                # Fallback: use species field from match response
                species_field = data.get("species") or ""
                if species_field and species_field.lower() != name.lower():
                    return LookupResult(status="synonym", accepted_name=species_field)
                return LookupResult(status="synonym", accepted_name=canonical or name)

            elif status == "ACCEPTED":
                return LookupResult(status="accepted", accepted_name=canonical or name)

            elif status == "DOUBTFUL":
                return LookupResult(status="no_match")

            else:
                # Other statuses (HETEROTYPIC_SYNONYM, HOMOTYPIC_SYNONYM, etc.)
                accepted_key = data.get("acceptedUsageKey")
                if accepted_key:
                    resp2 = await client.get(f"{GBIF_SPECIES_URL}/{accepted_key}")
                    if resp2.status_code == 200:
                        acc_data = resp2.json()
                        accepted = acc_data.get("canonicalName") or acc_data.get("species") or ""
                        if accepted:
                            return LookupResult(status="synonym", accepted_name=accepted)
                return LookupResult(status="accepted", accepted_name=canonical or name)

    except Exception as e:
        return LookupResult(status="error", error=str(e)[:60])


async def main():
    # ── Load DB species (read-only via sqlite3, no server needed) ──
    import sqlite3
    db_path = PROJECT_ROOT / "data" / "foragingid.db"
    if not db_path.exists():
        print(f"ERROR: DB not found at {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(str(db_path))
    rows = conn.execute("SELECT id, scientific_name FROM species WHERE scientific_name IS NOT NULL").fetchall()
    conn.close()

    db_species: list[tuple[int, str]] = [(r[0], r[1]) for r in rows]
    print(f"Loaded {len(db_species)} species from DB")

    # Build name_key → species lookup
    name_key_to_species: dict[str, str] = {}
    for _id, sname in db_species:
        key = normalize_taxon_key(sname)
        name_key_to_species[key] = sname

    # ── STEP 1: Generate synonym candidates ──
    monographs = _load_finalised_monographs()
    print(f"Finalised monographs loaded: {len(monographs)}")

    exact_map: dict[str, int] = {sname: sid for sid, sname in db_species}
    genus_map: dict[str, list[str]] = defaultdict(list)
    for _sid, sname in db_species:
        parts = sname.split()
        if len(parts) >= 2:
            genus_map[parts[0]].append(sname)

    # Reproduce candidate generation from build_chip_plan
    synonym_candidates: list[dict] = []
    seen_candidates: set[tuple] = set()

    for rec in monographs:
        binomials = _extract_binomials(rec["botanical_name"])
        if not binomials:
            continue
        for binom in binomials:
            if binom in exact_map:
                continue
            if binom in SYNONYMS:
                continue
            genus = binom.split()[0]
            if genus in genus_map:
                cand_key = (binom, rec["latin_name"])
                if cand_key not in seen_candidates:
                    seen_candidates.add(cand_key)
                    synonym_candidates.append({
                        "ema_binomial": binom,
                        "ema_latin_name": rec["latin_name"],
                        "db_genus_matches": sorted(genus_map[genus]),
                    })

    print(f"\n{'='*70}")
    print(f"STEP 1: Synonym candidates = {len(synonym_candidates)}")
    print(f"{'='*70}")
    for i, c in enumerate(synonym_candidates, 1):
        print(f"  {i:2}. {c['ema_binomial']:<35} (genus matches: {len(c['db_genus_matches'])})")
    print()

    # ── STEP 2: Classify each candidate ──
    print(f"{'='*70}")
    print("STEP 2: Classifying candidates...")
    print(f"{'='*70}\n")

    results: list[CandidateRow] = []
    lookup_errors = 0

    for i, cand in enumerate(synonym_candidates):
        binom = cand["ema_binomial"]
        nkey = normalize_taxon_key(binom)
        row = CandidateRow(ema_binomial=binom, name_key=nkey)

        print(f"  [{i+1}/{len(synonym_candidates)}] {binom}...", end=" ", flush=True)

        # Cascade 1: name_key match
        if nkey in name_key_to_species:
            row.matching_species = name_key_to_species[nkey]
            row.bucket = "RESOLVED_BY_NAME_KEY"
            print(f"→ {row.bucket} ({row.matching_species})")
            results.append(row)
            continue

        # Cascade 2: autonym collapse
        collapsed = collapse_autonym(binom)
        if collapsed != binom:
            row.collapsed_form = collapsed
            collapsed_key = normalize_taxon_key(collapsed)
            if collapsed_key in name_key_to_species:
                row.matching_species = name_key_to_species[collapsed_key]
                row.bucket = "AUTONYM_SUBSPECIES"
                print(f"→ {row.bucket} ({row.matching_species})")
                results.append(row)
                continue

        # Cascade 3+4+5: ITIS and GBIF lookup
        # ITIS
        itis_result = await itis_lookup(binom)
        await asyncio.sleep(DELAY_BETWEEN_CALLS)

        if itis_result.status == "error":
            row.itis_status = f"error: {itis_result.error}"
            lookup_errors += 1
        else:
            row.itis_status = itis_result.status
            if itis_result.accepted_name:
                row.itis_accepted = itis_result.accepted_name
                acc_key = normalize_taxon_key(itis_result.accepted_name)
                if acc_key in name_key_to_species:
                    row.itis_matches_existing = name_key_to_species[acc_key]
                    itis_result.matches_existing = True

        # GBIF
        gbif_result = await gbif_lookup(binom)
        await asyncio.sleep(DELAY_BETWEEN_CALLS)

        if gbif_result.status == "error":
            row.gbif_accepted = f"error: {gbif_result.error}"
            lookup_errors += 1
        else:
            if gbif_result.accepted_name:
                row.gbif_accepted = gbif_result.accepted_name
                acc_key = normalize_taxon_key(gbif_result.accepted_name)
                if acc_key in name_key_to_species:
                    row.gbif_matches_existing = name_key_to_species[acc_key]
                    gbif_result.matches_existing = True

        # Determine bucket
        if itis_result.matches_existing or gbif_result.matches_existing:
            # Determine genus relationship
            resolved_name = (
                name_key_to_species.get(normalize_taxon_key(itis_result.accepted_name or ""))
                or name_key_to_species.get(normalize_taxon_key(gbif_result.accepted_name or ""))
                or ""
            )
            row.matching_species = resolved_name
            ema_genus = binom.split()[0].lower()
            resolved_genus = resolved_name.split()[0].lower() if resolved_name else ""
            if ema_genus != resolved_genus:
                row.bucket = "CROSS_GENUS_SYNONYM"
            else:
                row.bucket = "SAME_GENUS_SYNONYM"
        elif (
            (itis_result.status == "synonym" and itis_result.accepted_name)
            or (gbif_result.status == "synonym" and gbif_result.accepted_name)
        ):
            row.bucket = "SYNONYM_TO_ABSENT"
        else:
            row.bucket = "NO_DB_MATCH"

        print(f"→ {row.bucket}")
        results.append(row)

    # ── STEP 3: Output table ──
    print(f"\n{'='*70}")
    print("STEP 3: Results Table")
    print(f"{'='*70}\n")

    # Header
    hdr = f"{'EMA Name':<35} {'name_key':<35} {'Existing Match':<30} {'Collapsed':<25} {'ITIS status':<12} {'ITIS accepted':<30} {'ITIS→DB':<25} {'GBIF accepted':<30} {'GBIF→DB':<25} {'Bucket'}"
    print(hdr)
    print("-" * len(hdr))

    for r in results:
        print(
            f"{r.ema_binomial:<35} {r.name_key:<35} {r.matching_species:<30} "
            f"{r.collapsed_form:<25} {r.itis_status:<12} {r.itis_accepted:<30} "
            f"{r.itis_matches_existing:<25} {r.gbif_accepted:<30} "
            f"{r.gbif_matches_existing:<25} {r.bucket}"
        )

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}\n")

    buckets = Counter(r.bucket for r in results)
    for bucket, count in sorted(buckets.items(), key=lambda x: -x[1]):
        print(f"  {bucket:<25} {count}")
    print(f"  {'TOTAL':<25} {len(results)}")

    # Authority resolution stats
    authority_resolved = sum(
        1 for r in results
        if r.bucket in ("CROSS_GENUS_SYNONYM", "SAME_GENUS_SYNONYM")
    )
    neither_resolved = sum(
        1 for r in results
        if r.bucket == "NO_DB_MATCH"
    )
    print(f"\n  Synonyms resolved by authority (ITIS/GBIF → existing card): {authority_resolved}")
    print(f"  Neither authority resolved: {neither_resolved}")
    print(f"  Lookup errors: {lookup_errors}")

    # Write CSV
    csv_path = PROJECT_ROOT / "docs" / "synonym_diagnostic.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "ema_binomial", "name_key", "matching_species", "collapsed_form",
            "itis_status", "itis_accepted", "itis_matches_existing",
            "gbif_accepted", "gbif_matches_existing", "bucket",
        ])
        for r in results:
            writer.writerow([
                r.ema_binomial, r.name_key, r.matching_species, r.collapsed_form,
                r.itis_status, r.itis_accepted, r.itis_matches_existing,
                r.gbif_accepted, r.gbif_matches_existing, r.bucket,
            ])
    print(f"\n  CSV written to: {csv_path}")


if __name__ == "__main__":
    asyncio.run(main())
