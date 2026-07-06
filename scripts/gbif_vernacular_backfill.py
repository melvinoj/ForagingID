"""
GBIF German common-name backfill for confirmed species.

Usage:
    python scripts/gbif_vernacular_backfill.py --dry-run    (default)
    python scripts/gbif_vernacular_backfill.py --commit      (writes to DB)

Writes: species.common_names_de (JSON array), species.gbif_usage_key (int).
Does NOT touch culinary_info, edibility, or any other field.
"""
import argparse
import asyncio
import json
import sqlite3
import sys
import time
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "data" / "foragingid.db"

MATCH_URL = "https://api.gbif.org/v1/species/match"
VERNACULAR_URL = "https://api.gbif.org/v1/species/{key}/vernacularNames"
HEADERS = {"User-Agent": "ForagingID/1.0 gbif-vernacular-backfill"}
TIMEOUT = 10.0
DELAY = 1.0


def get_candidates(conn):
    return conn.execute("""
        SELECT s.id, s.scientific_name, s.common_names_de, s.gbif_usage_key
        FROM species s
        WHERE EXISTS (
            SELECT 1 FROM observations o
            WHERE o.species_id = s.id
            AND o.review_status IN ('approved', 'manually_verified')
        )
        AND (s.common_names_de IS NULL
             OR s.common_names_de = '[]'
             OR s.common_names_de = '')
        ORDER BY s.scientific_name
    """).fetchall()


async def resolve_usage_key(client, name):
    """Resolve scientific name → GBIF usageKey. Returns (key, match_type)."""
    try:
        resp = await client.get(MATCH_URL, params={"name": name, "strict": "true"})
        if resp.status_code == 200:
            data = resp.json()
            if data.get("matchType") != "NONE" and data.get("usageKey"):
                return data["usageKey"], "strict"

        await asyncio.sleep(DELAY)

        resp = await client.get(MATCH_URL, params={"name": name, "strict": "false"})
        if resp.status_code == 200:
            data = resp.json()
            if data.get("matchType") != "NONE" and data.get("usageKey"):
                return data["usageKey"], "loose"
    except Exception:
        pass
    return None, "no_match"


async def fetch_german_names(client, usage_key):
    """Fetch German vernacular names for a GBIF usageKey."""
    names = []
    try:
        resp = await client.get(
            VERNACULAR_URL.format(key=usage_key),
            params={"limit": 100},
        )
        if resp.status_code != 200:
            return names
        for entry in resp.json().get("results", []):
            lang = entry.get("language", "")
            if lang in ("deu", "de"):
                vname = entry.get("vernacularName", "").strip()
                if vname:
                    names.append(vname)
    except Exception:
        pass
    return names


def dedupe_names(names):
    """Case-insensitive dedup preserving first occurrence."""
    seen = set()
    result = []
    for n in names:
        key = n.lower()
        if key not in seen:
            seen.add(key)
            result.append(n)
    return result


async def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dry-run", action="store_true", default=True)
    group.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    commit_mode = args.commit

    conn = sqlite3.connect(str(DB_PATH))
    candidates = get_candidates(conn)
    print(f"Candidates (confirmed species, no German name): {len(candidates)}")
    print(f"Mode: {'COMMIT' if commit_mode else 'DRY-RUN'}\n")

    stats = {
        "total": len(candidates),
        "gbif_hit": 0,
        "german_found": 0,
        "would_write": 0,
        "no_match": 0,
        "loose_match": 0,
        "no_german": 0,
        "errors": 0,
    }

    results = []

    async with httpx.AsyncClient(timeout=TIMEOUT, headers=HEADERS) as client:
        for i, (sp_id, sci_name, existing_de, existing_key) in enumerate(candidates):
            if (i + 1) % 10 == 0 or i == 0:
                print(f"  [{i+1}/{len(candidates)}] Processing {sci_name}...")

            usage_key = existing_key
            match_type = "cached" if existing_key else None

            if not usage_key:
                usage_key, match_type = await resolve_usage_key(client, sci_name)
                await asyncio.sleep(DELAY)

            if not usage_key:
                stats["no_match"] += 1
                results.append({
                    "species_id": sp_id,
                    "scientific_name": sci_name,
                    "status": "no_match",
                    "match_type": match_type,
                })
                continue

            stats["gbif_hit"] += 1
            if match_type == "loose":
                stats["loose_match"] += 1

            german_names = await fetch_german_names(client, usage_key)
            await asyncio.sleep(DELAY)

            german_names = dedupe_names(german_names)

            if not german_names:
                stats["no_german"] += 1
                results.append({
                    "species_id": sp_id,
                    "scientific_name": sci_name,
                    "status": "no_german",
                    "match_type": match_type,
                    "usage_key": usage_key,
                })
                continue

            stats["german_found"] += 1
            stats["would_write"] += 1

            # Merge with any existing names
            existing = []
            if existing_de and existing_de not in ("[]", ""):
                try:
                    existing = json.loads(existing_de)
                except json.JSONDecodeError:
                    pass
            merged = dedupe_names(existing + german_names)
            new_names = [n for n in merged if n not in existing]

            results.append({
                "species_id": sp_id,
                "scientific_name": sci_name,
                "status": "would_write",
                "match_type": match_type,
                "usage_key": usage_key,
                "german_names": merged,
                "new_names": new_names,
            })

            if commit_mode:
                conn.execute(
                    "UPDATE species SET common_names_de = ?, gbif_usage_key = ? WHERE id = ?",
                    (json.dumps(merged, ensure_ascii=False), usage_key, sp_id),
                )

    if commit_mode:
        conn.commit()
        print("\n  DB committed.")

    conn.close()

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}\n")
    print(f"  Total candidates:          {stats['total']}")
    print(f"  GBIF match found:          {stats['gbif_hit']}")
    print(f"    - strict match:          {stats['gbif_hit'] - stats['loose_match']}")
    print(f"    - loose match (review):  {stats['loose_match']}")
    print(f"  German names found:        {stats['german_found']}")
    print(f"  {'Written' if commit_mode else 'Would write'}:              {stats['would_write']}")
    print(f"  No GBIF match:             {stats['no_match']}")
    print(f"  GBIF hit, no German name:  {stats['no_german']}")

    # List loose matches for review
    loose = [r for r in results if r.get("match_type") == "loose"]
    if loose:
        print(f"\n  Loose matches (flagged for review):")
        for r in loose:
            names_str = ", ".join(r.get("german_names", [])[:3]) if r.get("german_names") else "—"
            print(f"    {r['scientific_name']:<35} key={r.get('usage_key')} names={names_str}")

    # List no-match species
    no_match = [r for r in results if r["status"] == "no_match"]
    if no_match:
        print(f"\n  No GBIF match ({len(no_match)}):")
        for r in no_match:
            print(f"    {r['scientific_name']}")

    # Sample of what would be written
    writes = [r for r in results if r["status"] == "would_write"]
    if writes:
        print(f"\n  Sample {'writes' if commit_mode else 'would-writes'} (first 15):")
        for r in writes[:15]:
            names = ", ".join(r["german_names"][:3])
            extra = f" (+{len(r['german_names'])-3})" if len(r["german_names"]) > 3 else ""
            print(f"    {r['scientific_name']:<35} [{r['match_type']}] → {names}{extra}")


if __name__ == "__main__":
    asyncio.run(main())
